"""Generated SHA discovery; hard exactness gates precede all timed comparisons."""
from statistics import median
from ..ir.sha import compression_graph
from ..ir.rewrite import genome,SPECIES
from ..ir.cost import estimate
from ..ir.equivalence import verify_graph
from ..gpu.opencl import OpenCLBackend
from ..verify.parity import verify_backend
from ..benchmark import heldout_headers,measure_window,paired_confidence,metadata
from .memory import KnowledgeStore
from .persistence import ProcessLock

def evaluate(index,champion_config,count=1<<22,seconds=.12,parents=None):
    spec=genome(index,parents=parents);graph=compression_graph(spec)
    interpreter=verify_graph(graph,16,seed=14951+index)
    config={"device_index":champion_config.get("device_index",0),"full_unroll":True,"alt_boolean":True,
            "local_size":(64,128,32,256)[(index//8)%4],"ir_spec":spec,"ir_hash":graph.fingerprint}
    with OpenCLBackend(**champion_config) as champion,OpenCLBackend(**config) as challenger:
        parity=verify_backend(challenger,4096,seed=81031+index)
        warm=heldout_headers(331+index,1)[0]
        measure_window(champion,warm,count,.3);measure_window(challenger,warm,count,.3)
        pairs=[];ratios=[]
        for pair,header in enumerate(heldout_headers(16931+index,7)):
            if pair%2:
                new=measure_window(challenger,header,count,seconds);old=measure_window(champion,header,count,seconds)
            else:
                old=measure_window(champion,header,count,seconds);new=measure_window(challenger,header,count,seconds)
            ratios.append(new["hashes_per_second"]/old["hashes_per_second"])
            pairs.append({"order":"BA" if pair%2 else "AB","champion":old,"challenger":new})
        confidence=paired_confidence(ratios);qualified=confidence["ci95_low"]>1.02
        holdout=verify_backend(challenger,16384,seed=510381+index) if qualified else None
        return {"status":"promotion_qualified" if qualified else "economically_dominated","candidate_index":index,
                "species":SPECIES[index%8],"config":config,"compared_against":champion_config,
                "graph_cost":estimate(graph),"interpreter_parity":interpreter,"parity":parity,"fresh_holdout":holdout,
                "metrics":{**confidence,"raw_pairs":pairs,"paired_ratios":ratios,"metadata":metadata(challenger),
                           "warmup_seconds_each":.3,"batch_size":count,"window_seconds":seconds,
                           "champion_median_hps":median(p["champion"]["hashes_per_second"] for p in pairs),
                           "challenger_median_hps":median(p["challenger"]["hashes_per_second"] for p in pairs),
                           "correctness_gate":True,"power_watts":None,"joules_per_terahash":None},
                "cryptanalytic_discovery":False,"algorithmic_complexity":"linear full SHA256d; conventional midstate"}

def optimize_generated(store_path="results/knowledge.sqlite",count=1<<22,seconds=.12,device_index=0,progress=None,number=16):
    if not 1<=number<=128:raise ValueError("Generated search must use 1..128 candidates per call")
    results=[]
    with ProcessLock(str(store_path)+".optimizer.lock"),KnowledgeStore(store_path) as store:
        champion=store.get_state("champion",{}).get("config",{"device_index":device_index,"full_unroll":True,"alt_boolean":True,"local_size":64})
        start=store.get_state("generated_cursor",0)
        population=store.get_state("generated_population",[])
        for index in range(start,start+number):
            if progress:progress(f"Generated SHA graph {index}: {SPECIES[index%8]}")
            parents=[p["spec"] for p in population[-2:]] if index%8==6 and len(population)>1 else None
            try:
                result=evaluate(index,champion,count,seconds,parents)
                if result["status"]=="promotion_qualified":
                    metrics={**result["metrics"],"holdout":result["fresh_holdout"],"parity":result["parity"]}
                    store.promote(result["config"],metrics,champion);champion=result["config"];result["status"]="promoted"
                else:
                    store.put("DEAD",{"species":result["species"],"ir_hash":result["config"]["ir_hash"]},
                              result["metrics"],"Exact generated graph slower/no confidence-qualified gain",result["metrics"]["geometric_speedup"])
                # One recent exact graph per species; diverse survivors need not beat champion.
                population=[p for p in population if p["species"]!=result["species"]]
                population.append({"species":result["species"],"spec":result["config"]["ir_spec"],"ir_hash":result["config"]["ir_hash"]})
                store.set_state("generated_population",population[-32:])
            except Exception as error:
                from .supervisor import classify
                category,_=classify(error)
                result={"status":"failed","candidate_index":index,"failure_class":category,"reason":str(error)[:2048],"species":SPECIES[index%8]}
                store.put("DEAD",{"species":result["species"],"index":index},result,"Generated compilation/correctness failure")
            results.append(result);store.set_state("generated_cursor",index+1)
        return {"schema":2,"champion":champion,"experiments":results,"research_population":population,
                "cryptanalytic_discovery":False,"power_watts":None,"joules_per_terahash":None}
