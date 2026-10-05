"""Measured hunt amortization on permitted fixture variations; no luck ranking."""
from time import perf_counter
from dataclasses import replace
from statistics import median
from ..bitcoin.block_header import GENESIS
from ..benchmark import measure_window
from .family_search import amortized_value

def search_structures(backend,number=8,count=1<<18):
    if not 2<=number<=32:raise ValueError("Bounded structural search")
    begun=perf_counter();baseline=GENESIS.serialize();rows=[]
    for i in range(number):
        # Diagnostic header templates only; these freedoms require pool negotiation for live work.
        candidate=replace(GENESIS,version=GENESIS.version^(i<<13),timestamp=GENESIS.timestamp+i).serialize()
        a=measure_window(backend,baseline,count,.02);b=measure_window(backend,candidate,count,.02)
        saving=max(0,1/a["hashes_per_second"]-1/b["hashes_per_second"])
        rows.append({"version":int.from_bytes(candidate[:4],"little"),"ntime":int.from_bytes(candidate[68:72],"little"),
                     "baseline_seconds_per_candidate":1/a["hashes_per_second"],"candidate_seconds_per_candidate":1/b["hashes_per_second"],
                     "saving_seconds_per_candidate":saving})
    hunt=perf_counter()-begun;best=max(rows,key=lambda r:r["saving_seconds_per_candidate"])
    value=amortized_value(count,best["saving_seconds_per_candidate"],hunt)
    # A best-of-many timing fluctuation is not a verified structural property.
    return {"status":"economically_dominated","C_hunt":hunt,"K_survive":count,"deltaC":best["saving_seconds_per_candidate"],
            "amortization":value,"rows":rows,"verified_property":None,"production_changed":False,
            "reason":"No demonstrated exact structural reduction; timing noise is not a computational property",
            "work_source":"diagnostic header fixtures; version/nTime freedoms not negotiated with a pool"}
