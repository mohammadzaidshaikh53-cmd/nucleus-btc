from collections import Counter
from .lower_opencl import lower

def estimate(graph):
    live=graph.live_nodes();counts=Counter(graph.nodes[i].op for i in live)
    return {"nodes":len(graph.nodes),"live_nodes":len(live),"op_counts":dict(counts),
            "temporary_registers":lower(graph)["temporary_registers"],
            "estimate_only":True,"gpu_isa_registers":None}
