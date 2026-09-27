import numpy as np
import schemathesis
from hypothesis import strategies as st


node_ids = np.load(".osm_cache/node_ids.npy").tolist()
node_id_strategy = st.sampled_from(node_ids)


@schemathesis.hook
def flatmap_body(ctx, body):
    if not isinstance(body, dict):
        return st.just(body)

    if "node_start" not in body or "node_end" not in body:
        return st.just(body)

    return st.fixed_dictionaries({
        "node_start": node_id_strategy,
        "node_end": node_id_strategy,
    })
