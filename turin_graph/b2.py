from fastapi import FastAPI, HTTPException, Response, Cookie, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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
    node_start: float
    node_end: float

def find_position(node_idx):
    position = int(np.searchsorted(node_ids, node_idx))
    assert node_ids[position] == node_idx
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

def heuristic_1(node_idx, lat2, lon2):
    candidate_coords = node_coordinates(node_idx)
    lat1, lon1 = radians(candidate_coords)
    distance_lat = lat2 - lat1
    distance_lon = lon2 - lon1

    a = math.sin(distance_lat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(distance_lon/2)**2
    distance_km = 2 * 6371 * math.asin(math.sqrt(a))

    return distance_km

def heuristic(node_idx, lat2, lon2):
    candidate_coords = node_coordinates(node_idx)
    lat1, lon1 = radians(candidate_coords)
    distance_lat = lat2 - lat1
    distance_lon = lon2 - lon1

    a = math.sin(distance_lat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(distance_lon/2)**2
    distance_km = 2 * 6371 * math.asin(math.sqrt(a))

    return (distance_km / 85) * 3600

def a_star(start1, end1):
    start_x = find_position(start1)
    end_x = find_position(end1)
    end_lat, end_lon = radians(node_coordinates(end_x))
    d1 = heuristic_1(start_x, end_lat, end_lon)

    print(f"Route: OSM {start1} ({start_x}) to OSM {end1} ({end_x})")
    print(f"Straight distance is {round(d1, 4)} kilometres")

    priority_queue = [(d1, 0.0, start_x, [start_x])]
    pq = priority_queue

    visited = set()
    nodes_explored = 0
    deadlined = time.monotonic() + 7

    try:

        while pq and time.monotonic() < deadlined:
            estimated, distance_travelled, current_row, row_path = heapq.heappop(pq)
            nodes_explored +=1

            if current_row == end_x:
                osm_path = [reverse_position(r) for r in row_path]
                print(f"✅ Found! {nodes_explored:,} nodes explored, {len(osm_path):,} hops")
                return distance_travelled, osm_path

            if current_row in visited:
                continue

            visited.add(current_row)

            next_candidates, next_weights = return_node(current_row)

            for i in range(len(next_candidates)):
                node_x = int(next_candidates[i])
                if node_x in visited: continue
                weight_x = float(next_weights[i])

                new_distance = distance_travelled + weight_x
                h1 = heuristic(node_x, end_lat, end_lon)

                heapq.heappush(pq, (new_distance + h1, new_distance, node_x, row_path + [node_x]))

        return "out_of_time", "out_of_time"

    except Exception:
        raise


coordinates = np.load(".osm_cache/node_coords.npy",  mmap_mode="r") #1
node_ids = np.load(".osm_cache/node_ids.npy",  mmap_mode="r")
indices = np.load(".osm_cache/indices.npy",  mmap_mode="r") #2

data = np.load(".osm_cache/data.npy", mmap_mode="r") #3
shape = np.load(".osm_cache/shape.npy", mmap_mode="r")
indptr = np.load(".osm_cache/indptr.npy",  mmap_mode="r") #4
edge_etas = np.load(".osm_cache/edge_highway.npy", mmap_mode="r")


A = sp.csr_matrix((data, indices, indptr), shape=tuple(shape))

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
#end = 12099764350 # (Shopping Village Mall, Rio de Janeiro)
# hi
#1379439636 #(Shopping Morumbi)
@app.post("/routing")
def location_search(payload: RoutingRequest, response: Response):
    try:
        node_start = int(payload.node_start)
        node_end = int(payload.node_end)
        time1 = monotonic()
        total_distance, routed = a_star(node_start, node_end)

        if total_distance == "out_of_time":
            time2 = (monotonic() - time1) * 1000
            return {"total_distance": None, "routed": None, "time_spent": f"{time2:.3f} ms" , "detail": "Out of time. The limit for processing is 3210ms."}
        print(total_distance)
        route_coordinates = [
            coordinates[find_position(node_id)].tolist()
            for node_id in routed
        ]

        start = 0
        for node_id in routed:
            start += float(edge_etas[find_position(node_id)])

        return {
        "total_distance": total_distance,
        "time_spent": monotonic() - time1,
        "estimated_time_hours": start / 3600,
        "routed": route_coordinates,

        }

    except HTTPException:
        raise

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Unable to finalize request.")


try:
    total_distance, routed = a_star(start, end)
    print(total_distance)

except Exception:
    pass
