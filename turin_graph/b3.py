from fastapi import FastAPI, HTTPException, Response, Cookie, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, StrictInt
from time import monotonic
import scipy.sparse as sp
import numpy as np
import heapq
import math
import time
import os


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://turinflow.com.br",
        "http://localhost:8090",

    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

class RoutingRequest(BaseModel):
    node_start: int
    node_end: int

class RouteResponse(BaseModel):
    total_distance_meters: int
    estimated_time_hours: float
    routed: dict
    computation_time_ms: int

def find_position(node_idx):
    position = int(np.searchsorted(node_ids, node_idx))
    assert position < len(node_ids) and node_ids[position] == node_idx
    return position

def reverse_position(position_x):
    return int(node_ids[position_x])

def find_node(indice_x, data_x):
      try:
            next_nodes = []
            for x, y in zip(indice_x, data_x):
                  new_x = node_ids[x]
                  next_nodes.append([new_x, y])

            return next_nodes, len(next_nodes)
      except Exception:
            return None

def return_node(array_location):
      data2 = data[indptr[array_location]:indptr[array_location + 1]]
      indices2 = indices[indptr[array_location]:indptr[array_location + 1]]

      return indices2, data2

def node_coordinates(node_psx):
    return coordinates[node_psx]

def radians(dict1):
    return np.radians(dict1)

def heuristic(node_idx, lat2, lon2):
    return (straight_distance(node_idx, lat2, lon2)/ 95) * 3600

def heuristic_1(node_idx, lat2, lon2):
    return (straight_distance(node_idx, lat2, lon2) / 25) * 3600

def straight_distance(node_idx, lat2, lon2):
    candidate_coords = node_coordinates(node_idx)
    lat1, lon1 = radians(candidate_coords)

    distance_lat = lat2 - lat1
    distance_lon = lon2 - lon1

    a = (
        math.sin(distance_lat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(distance_lon / 2) ** 2
    )

    distance_km = 2 * 6371 * math.asin(math.sqrt(a))

    return distance_km

def a_star(start1, end1):
    try:
        start_x = find_position(start1)
        end_x = find_position(end1)
    except Exception:
        raise HTTPException(status_code=404, detail="Invalid Start or End Nodes.")

    end_lat, end_lon = radians(node_coordinates(end_x))

    d1 = straight_distance(start_x, end_lat, end_lon)

    print(f"Route: OSM {start1} ({start_x}) to OSM {end1} ({end_x})")
    print(f"Straight distance is {d1:.4f} kilometres")

    # priority:
    # (estimated total time, time travelled, internal node, path)
    pq = [(d1, 0.0, start_x, [start_x])]

    visited = set()
    nodes_explored = 0
    deadlined = time.monotonic() + 2.21

    while pq and time.monotonic() < deadlined:
        estimated, time_travelled, current_row, row_path = heapq.heappop(pq)
        nodes_explored += 1

        if current_row == end_x:
            osm_path = [reverse_position(r) for r in row_path]
            print(f"✅ Found! {nodes_explored:,} nodes explored, "f"{len(osm_path):,} hops")
            return time_travelled, osm_path

        if current_row in visited:
            continue

        visited.add(current_row)

        next_candidates, next_weights = return_node(current_row)

        for i in range(len(next_candidates)):
            node_x = int(next_candidates[i])

            if node_x in visited:
                continue

            # data.npy = ETA in seconds
            weight_x = float(next_weights[i])
            new_time = time_travelled + weight_x
            h1 = heuristic_1(node_x, end_lat, end_lon)

            heapq.heappush(pq,(new_time + h1, new_time, node_x, row_path + [node_x]))

    return "out_of_time", "out_of_time"

print("=== GRAPH LOAD START ===", flush=True)
coordinates = np.load(".osm_cache/node_coords.npy") #1
node_ids = np.load(".osm_cache/node_ids.npy")
indices = np.load(".osm_cache/indices.npy") #2

data = np.load(".osm_cache/data.npy") #3
shape = np.load(".osm_cache/shape.npy", mmap_mode="r")
indptr = np.load(".osm_cache/indptr.npy") #4
#edge_distance = np.load(".osm_cache/edge_distance.npy", mmap_mode="r")
#edge_speed = np.load(".osm_cache/edge_speed.npy", mmap_mode="r")

A = sp.csr_matrix((data, indices, indptr), shape=tuple(shape))


benchmark_count = 1_000_000
random_indices = np.random.randint(
    0,
    len(data),
    benchmark_count,
    dtype=np.intp,
)

print("=== MEMORY BENCHMARK START ===", flush=True)

_ = data[random_indices].sum()

start = time.perf_counter()
result = data[random_indices].sum()
elapsed = time.perf_counter() - start

print(
    f"Random memory access: "
    f"{benchmark_count:,} accesses in {elapsed:.4f}s (expected 0.020s)",
    flush=True,
)

def benchmark(name, fn, iterations=1):
    fn()
    start = time.perf_counter()
    for _ in range(iterations):
        result = fn()
    elapsed = time.perf_counter() - start

    print(
        f"{name:<32} "
        f"{elapsed:.6f}s "
        f"({elapsed / iterations * 1000:.3f} ms/op)",
        flush=True,
    )

    return result


print("\n========== SYNTHETIC BENCHMARKS ==========", flush=True)

def python_arithmetic():
    x = 0.123456

    for i in range(100_000):
        x = x * 1.000001 + i * 0.000001
        x = x / 1.0000001

    return x

benchmark(
    "Python arithmetic",
    python_arithmetic,
    iterations=10,
)

def tuple_creation():
    result = []

    for i in range(100_000):
        result.append((i, i + 1, i + 2, [i, i + 1]))

    return result

benchmark(
    "Python tuple/list creation",
    tuple_creation,
    iterations=10,
)

dictionary = {i: i * 2 for i in range(1_000_000)}
dictionary_keys = np.random.randint(
    0,
    1_000_000,
    100_000,
    dtype=np.int64,
)

def dictionary_lookup():
    total = 0

    for key in dictionary_keys:
        total += dictionary[int(key)]

    return total

benchmark(
    "Python dict lookup",
    dictionary_lookup,
    iterations=10,
)

visited = set(range(1_000_000))
set_keys = np.random.randint(
    0,
    1_000_000,
    100_000,
    dtype=np.int64,
)

def set_lookup():
    total = 0

    for key in set_keys:
        if int(key) in visited:
            total += 1

    return total

benchmark(
    "Python set membership",
    set_lookup,
    iterations=10,
)

def heap_operations():
    heap = []

    for i in range(100_000):
        heapq.heappush(
            heap,
            (i % 10_000, i, i + 1),
        )

    total = 0

    while heap:
        item = heapq.heappop(heap)
        total += item[1]

    return total

benchmark(
    "heapq push + pop",
    heap_operations,
    iterations=5,
)

random_indices = np.random.randint(
    0,
    len(data),
    1_000_000,
    dtype=np.intp,
)

def numpy_random_access():
    return data[random_indices].sum()

benchmark(
    "NumPy random access",
    numpy_random_access,
    iterations=10,
)

csr_nodes = np.random.randint(
    0,
    len(indptr) - 1,
    100_000,
    dtype=np.intp,
)

def csr_access():
    total = 0

    for node in csr_nodes:
        start = indptr[node]
        end = indptr[node + 1]

        if end > start:
            total += indices[start]
            total += data[start]

    return total

benchmark(
    "CSR-style access",
    csr_access,
    iterations=10,
)

def csr_neighbor_iteration():
    total = 0

    for node in csr_nodes:
        start = indptr[node]
        end = indptr[node + 1]

        for i in range(start, end):
            total += int(indices[i])

    return total

benchmark(
    "CSR neighbor traversal",
    csr_neighbor_iteration,
    iterations=10,
)

search_values = np.random.choice(
    node_ids,
    size=100_000,
    replace=True,
)

def searchsorted_test():
    return np.searchsorted(node_ids, search_values)

benchmark(
    "NumPy searchsorted",
    searchsorted_test,
    iterations=10,
)

coordinate_positions = np.random.randint(
    0,
    len(coordinates),
    100_000,
    dtype=np.intp,
)

def coordinate_lookup():
    return coordinates[coordinate_positions].sum()

benchmark(
    "Coordinate lookup",
    coordinate_lookup,
    iterations=10,
)

print("========== BENCHMARKS COMPLETE ==========\n", flush=True)

# --- basic stats ---
print("nodes:", A.shape[0], "| directed edges:", A.nnz,"| avg degree: %.2f" % (A.nnz / A.shape[0]))

#start = 1871769061
#start = 31935580 # (Aeroporto de Viracopos)
#start = 1001568698 # (Residência Cidade Jardim)
#start = 2368042870 # (Santa Bárbara Residence)
start = 1871768924 # (Alameda Coinbra)
#end = 4363722848 # (Saída Alpha 0)
end = 245374595 # (Aeroporto de Guarulhos)
#end = 4137343158 # (Fazenda Boa Vista)
#end = 2868730635 # (Vila Galé Angra dos Reis)
#end = 493141051 # (Praia Grande)
#end = 1669971805 # (Taubaté)
# 7891860433 (Mogi das Cruzes)
#end = 12099764350 # (Shopping Village Mall, Rio de Janeiro)
# hi
#1379439636 #(Shopping Morumbi)
@app.post(
    "/routing",
    responses={400: {"description": "Malformed request body"},
    404: {"description": "Invalid Start or End Nodes (not found in Database)."}},
)
def location_search(payload: RoutingRequest, response: Response):
    try:
        node_start = payload.node_start
        node_end = payload.node_end
        time1 = monotonic()

        total_eta, routed = a_star(node_start, node_end)

        if total_eta == "out_of_time":
            time2 = (monotonic() - time1) * 1000

            return {
                "total_distance": None,
                "estimated_time_hours": None,
                "routed": None,
                "time_spent": f"{time2:.3f} ms",
                "detail": "Out of time. The limit for processing is 2210ms.",
            }

        route_coordinates = [
            coordinates[find_position(node_id)].tolist()
            for node_id in routed
        ]

        time_spent = monotonic() - time1
        return {
            "total_distance": 0,
            "estimated_time_seconds": total_eta,
            "estimated_time_hours": total_eta / 3600,
            "time_spent": time_spent,
            "routed": route_coordinates,
        }

    except HTTPException:
        raise

    except Exception as e:
        print(f"Routing error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500,detail=f"Routing failed: {type(e).__name__}: {e}",)



try:
    a4 = time.monotonic()
    total_distance, routed = a_star(start, end)
    print(f"{time.monotonic() - a4:.5f} seconds")

except Exception:
    print("****** May not start correctly, components may not be loaded properly.****************")
