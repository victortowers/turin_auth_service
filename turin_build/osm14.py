"""build_graph_streaming.py — streaming PBF parser for state-level files.

No OSMnx, no NetworkX.  Streams the PBF once with pyosmium, builds a
compressed sparse-row (CSR) adjacency matrix with scipy.

Pipeline:
  1. pyosmium streams ways tagged highway=*, collects node IDs + edges
  2. Optional second pass: collect lat/lon for referenced nodes
  3. scipy.sparse.csr_matrix  →  disk via npz

Dependencies:
  pip install pyosmium scipy numpy

Output files (in <pbf_dir>/.osm_cache/):
  adjacency.npz   — scipy CSR adjacency matrix (float32, unweighted)
  node_ids.npy    — int64 array mapping matrix row → original OSM node ID
  node_coords.npy — float32 (N,2) lat/lon (if --with-coords)
"""
import osmium
import numpy as np
from scipy import sparse
from pathlib import Path
import time, sys

HIGHWAY_CODES = {
    "motorway": 0,
    "motorway_link": 1,
    "trunk": 2,
    "trunk_link": 3,
    "primary": 4,
    "primary_link": 5,
    "secondary": 6,
    "secondary_link": 7,
    "tertiary": 8,
    "tertiary_link": 9,
    "residential": 10,
    "unclassified": 11,
    "service": 12,
    "living_street": 13,
    "road": 14,
}

HIGHWAY_UNKNOWN = 15

HIGHWAY_SPEED_KMH = np.array([
    85,  # motorway
    65,  # motorway_link
    60,  # trunk
    55,  # trunk_link
    45,  # primary
    35,  # primary_link
    40,  # secondary
    30,  # secondary_link
    30,  # tertiary
    25,  # tertiary_link
    25,  # residential
    30,  # unclassified
    10,  # service
    20,  # living_street
    20,  # road
    0.0001,   # Unknown Type
], dtype=np.float32)

# ─── Streaming handler ───────────────────────────────────────────────

class HighwayHandler(osmium.SimpleHandler):
    """Collect highway ways → directed edges (node_id pairs)."""

    def __init__(self):
        super().__init__()
        self.way_count = 0
        self.edge_count = 0
        self.node_ids: set[int] = set()
        self.edges_from: list[int] = []
        self.edges_highway: list[str] = []
        self.edges_to: list[int] = []

    def way(self, w):
        highway = w.tags.get("highway")
        if highway is None: return
        self.way_count += 1

        # Collect ordered node references for this way
        refs: list[int] = []
        for node in w.nodes:
            refs.append(node.ref)

        if len(refs) < 2:
            return

        # Every consecutive pair is a directed edge
        oneway = w.tags.get("oneway")
        junction = w.tags.get("junction")

        if oneway in ("-1", "reverse"):
            refs.reverse()

        is_bidirectional = (
            oneway not in ("yes", "true", "1", "-1", "reverse")
            and junction != "roundabout"
        )

        for i in range(len(refs) - 1):
            a = refs[i]
            b = refs[i + 1]

            if a == b:
                continue

            self.node_ids.add(a)
            self.node_ids.add(b)

            self.edges_from.append(a)
            self.edges_to.append(b)
            self.edges_highway.append(highway)
            self.edge_count += 1

            if is_bidirectional:
                self.edges_from.append(b)
                self.edges_to.append(a)
                self.edges_highway.append(highway)
                self.edge_count += 1

class CoordHandler(osmium.SimpleHandler):
    """Second pass: collect lat/lon for every node we care about.

    Only called if --with-coords is set.
    """

    def __init__(self, node_ids_array, coords_array):
            """
            node_ids_array: sorted numpy int64 array of node IDs
            coords_array:   pre-allocated float32 (N, 2) array, filled with NaN
            """
            super().__init__()
            self.node_ids = node_ids_array
            self.coords = coords_array
            self.found = 0

    def node(self, n):
        nid = n.id
        # Binary search to find row index
        idx = np.searchsorted(self.node_ids, nid)
        if idx >= len(self.node_ids) or self.node_ids[idx] != nid:
            return  # not a node we need
        loc = n.location
        if not loc.valid():
            return
        self.coords[idx, 0] = loc.lat
        self.coords[idx, 1] = loc.lon
        self.found += 1

    def as_arrays(self):
        """Return lookup dict: node_id → (lat, lon)."""
        lookup = dict(zip(self._ids, zip(self._lats, self._lons)))
        return lookup


# ─── Core builder ────────────────────────────────────────────────────

def build_graph_streaming(pbf_path: Path, with_coords: bool = False):
    cache_dir = pbf_path.parent / ".osm_cache"
    cache_dir.mkdir(exist_ok=True)

    # ── Pass 1: stream ways ──
    print("Pass 1/3: Streaming PBF (ways)...")
    t0 = time.time()
    handler = HighwayHandler()
    handler.apply_file(str(pbf_path), locations=False)
    t1 = time.time()

    print(f"    Ways:        {handler.way_count:>12,}")
    print(f"    Directed edges: {handler.edge_count:>12,}")
    print(f"    Unique nodes:   {len(handler.node_ids):>12,}")
    print(f"    Parsed in {t1 - t0:.1f}s")

    # ── Build adjacency matrix ──
    print("Pass 2/3: Building CSR adjacency matrix...")
    t2 = time.time()

    # Map original OSM node IDs → dense 0..N-1
    node_list = np.array(sorted(handler.node_ids), dtype=np.int64)
    node_to_idx = {nid: i for i, nid in enumerate(node_list)}
    N = len(node_list)

    rows = np.array([node_to_idx[n] for n in handler.edges_from], dtype=np.int32)
    cols = np.array([node_to_idx[n] for n in handler.edges_to],   dtype=np.int32)

    highway_codes = np.array([HIGHWAY_CODES.get(h, HIGHWAY_UNKNOWN) for h in handler.edges_highway], dtype=np.uint8)
    # Build directed edges: forward + reverse (bidirectional graph)
    #
    all_rows = rows
    all_cols = cols
    all_highway_codes = highway_codes

    # Deduplicate edges while preserving highway type.
    edge_map = {}

    for r, c, highway in zip(
        all_rows,
        all_cols,
        all_highway_codes,
    ):
        key = (int(r), int(c))

        if key not in edge_map:
            edge_map[key] = highway

    # Convert unique edges back into arrays.
    unique_rows = np.fromiter(
        (r for r, c in edge_map),
        dtype=np.int32,
    )

    unique_cols = np.fromiter(
        (c for r, c in edge_map),
        dtype=np.int32,
    )

    edge_highway = np.fromiter(
        edge_map.values(),
        dtype=np.uint8,
    )

    # Build CSR adjacency matrix.
    adj = sparse.csr_matrix(
        (
            np.ones(len(unique_rows), dtype=np.float32),
            (unique_rows, unique_cols),
        ),
        shape=(N, N),
    )
    adj.data[:] = 1.0

    print(f"    Matrix: {N:,} × {N:,}, {adj.nnz:,} stored entries")
    print(f"    Built in {time.time() - t2:.1f}s")

    # ── Pass 3 (optional): collect coordinates ──
    coords_array = None
    if with_coords:
        print("Pass 3/3: Streaming PBF (node coordinates)...")
        t3 = time.time()

        # Pre-allocate coords array with NaN (missing nodes stay NaN)
        coords_array = np.full((N, 2), np.nan, dtype=np.float32)

        coord_handler = CoordHandler(node_list, coords_array)
        coord_handler.apply_file(str(pbf_path), locations=True)

        missing = N - coord_handler.found
        print(f"    Coords found: {coord_handler.found:,} / {N:,}")
        if missing:
            print(f"    Missing:      {missing:,}")
        print(f"    Parsed in {time.time() - t3:.1f}s")

        ## New calculation: substitution of weights
        print("Computing Haversine Distances, please wait...")
        t_dist = time.time()
        import math

        new_data = np.zeros(len(adj.data), dtype=np.float32)
        edge_data = np.zeros(len(adj.data), dtype=np.float32)
        for u in range(N):
            row_start = adj.indptr[u]
            row_end   = adj.indptr[u + 1]
            # Convert source node on the fly
            lat1 = math.radians(float(coords_array[u, 0]))
            lon1 = math.radians(float(coords_array[u, 1]))
            cos1 = math.cos(lat1)
            for i in range(row_start, row_end):
                v = adj.indices[i]
                lat2 = math.radians(float(coords_array[v, 0]))
                lon2 = math.radians(float(coords_array[v, 1]))
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = (math.sin(dlat/2)**2 +
                     cos1 * math.cos(lat2) * math.sin(dlon/2)**2)
                new_data[i] = 2 * 6371 * math.asin(math.sqrt(a))

                speed = HIGHWAY_SPEED_KMH[edge_highway[i]]

                distance_km = new_data[i]
                edge_data[i] = (distance_km/ speed) * 3600

        adj.data = new_data.astype(np.float32)
        print(f"    Computed {len(new_data):,} edge distances in {time.time() - t_dist:.1f}s")

    else:
        print("Pass 3/3: (skipped — use --with-coords to include lat/lon)")

    # ── Save ──
    print("Saving...")
    t4 = time.time()
    adj_csr = adj.tocsr()

    np.save(cache_dir / "data.npy",    adj_csr.data.astype(np.float32))
    np.save(cache_dir / "indices.npy", adj_csr.indices.astype(np.int32))
    np.save(cache_dir / "indptr.npy",  adj_csr.indptr.astype(np.int32))
    np.save(cache_dir / "shape.npy",   np.array(adj_csr.shape, dtype=np.int32))
    np.save(cache_dir / "edge_highway.npy",edge_highway.astype(np.float32))
    np.save(cache_dir / "node_ids.npy", node_list)
    if coords_array is not None:
        np.save(cache_dir / "node_coords.npy", coords_array)

    data_mb = (cache_dir / "data.npy").stat().st_size / 1e6
    indices_mb = (cache_dir / "indices.npy").stat().st_size / 1e6
    indptr_mb = (cache_dir / "indptr.npy").stat().st_size / 1e6
    shape_mb = (cache_dir / "shape.npy").stat().st_size / 1e6
    ids_mb = (cache_dir / "node_ids.npy").stat().st_size / 1e6
    edge_mb = (cache_dir / "edge_highway.npy").stat().st_size / 1e6

    print(f"        data.npy  {data_mb:>8.1f} MB")
    print(f"     indices.npy  {indices_mb:>8.1f} MB")
    print(f"      indptr.npy  {indptr_mb:>8.1f} MB")
    print(f"       shape.npy  {shape_mb:>8.1f} MB")
    print(f"    node_ids.npy  {ids_mb:>8.1f} MB")
    print(f"edge_highway.npy  {edge_mb:>8.1f} MB")
    if coords_array is not None:
        coords_mb = (cache_dir / "node_coords.npy").stat().st_size / 1e6
        print(f" node_coords.npy   {coords_mb:>7.1f} MB")
    print(f"    Saved in {time.time() - t4:.1f}s")

    print(f"\nTotal: {time.time() - t0:.1f}s")
    return adj, node_list, coords_array


# ─── CLI ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build road graph from PBF (streaming)")
    parser.add_argument("pbf", help="Input .osm.pbf file")
    parser.add_argument("--with-coords", action="store_true",
                        help="Also extract lat/lon for each node (second pass)")
    args = parser.parse_args()

    pbf = Path(args.pbf)
    if not pbf.exists():
        sys.exit(f"Error: file not found — {pbf}")

    build_graph_streaming(pbf, with_coords=args.with_coords)
