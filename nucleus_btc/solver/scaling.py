"""Full-SHA carry family costs through 2^20, isolated failures and raw measurements."""
import json
import subprocess
import sys
from pathlib import Path
from time import perf_counter
from math import log
from statistics import median
from ..benchmark import heldout_headers,metadata
from ..gpu.backend import get_backend,BackendUnavailable
from ..nucleus.memory import KnowledgeStore
from ..nucleus.persistence import atomic_json
from ..nucleus.fitness import Fitness

ROOT=Path(__file__).resolve().parents[2]

def fit_cost(rows):
    """T=a+b*K^alpha, with nonnegative overhead; descriptive fit, not a proof."""
    if len(rows)<3:return None
    y=[r["median_seconds"] for r in rows];best=None
    for step in range(30,151):
        alpha=step/100;x=[r["count"]**alpha for r in rows];xm=sum(x)/len(x);ym=sum(y)/len(y)
        b=max(0,sum((a-xm)*(v-ym) for a,v in zip(x,y))/sum((a-xm)**2 for a in x));a=ym-b*xm
        if a<0:a=0;b=sum(v*z for v,z in zip(y,x))/sum(z*z for z in x)
        error=sum((v-a-b*z)**2 for v,z in zip(y,x))
        if best is None or error<best[0]:best=(error,alpha,a,b)
    x=[log(r["count"]) for r in rows[-3:]];v=[log(r["median_seconds"]) for r in rows[-3:]];xm=sum(x)/3;vm=sum(v)/3
    slope=sum((a-xm)*(b-vm) for a,b in zip(x,v))/sum((a-xm)**2 for a in x)
    return {"alpha_with_fixed_overhead":best[1],"fixed_overhead_seconds":best[2],"coefficient":best[3],"squared_error":best[0],"largest_three_observed_slope":slope,
            "interpretation":"Finite descriptive fit; fixed overhead, integer width and instrumentation affect slope; no algorithmic sublinearity claim"}

def representation_scaling(powers=(8,10,12,14,16,18,20),repeats=3,progress=None,representations=("ripple","prefix","carry-select","carry-save")):
    if len(powers)<3 or any(not 1<=p<=20 for p in powers) or not 3<=repeats<=7:raise ValueError("Bounded scaling powers/repeats required")
    if not set(representations)<=set(("ripple","prefix","carry-select","carry-save","hybrid-dag","hybrid-bdd")):raise ValueError("Unknown scaling representation")
    progress=progress or (lambda *_:None);engines={};baselines={};rows={kind:[] for kind in representations};begun=perf_counter()
    with KnowledgeStore(ROOT/"results"/"knowledge.sqlite") as store:champion=store.get_state("champion",{}).get("config",{})
    try:
        for name in ("native","opencl"):
            try:engines[name]=get_backend(name,**(champion if name=="opencl" else {}))
            except BackendUnavailable:baselines[name]={"status":"unavailable"};continue
            baselines[name]={"metadata":metadata(engines[name]),"rows":[]}
        scratch=ROOT/"results"/"evolution"/"scaling-work";scratch.mkdir(parents=True,exist_ok=True)
        for power in powers:
            count=1<<power;headers=heldout_headers(890001+power,repeats)
            baseline_rows={name:[] for name in engines}
            for name,engine in engines.items():engine.scan(headers[0],0,count,1)
            measurements={kind:[] for kind in rows}
            for trial,header in enumerate(headers):
                for name,engine in engines.items():
                    t=perf_counter();result=engine.scan(header,0,count,1);elapsed=perf_counter()-t
                    if result.nonces:raise AssertionError("Unexpected scan result requires independent audit")
                    baseline_rows[name].append({"seconds":elapsed,"kernel_seconds":result.kernel_seconds,"examined":result.examined})
                kinds=list(rows) if trial%2==0 else list(reversed(rows))
                for kind in kinds:
                    request=scratch/"request.json";response=scratch/"response.json"
                    atomic_json(request,{"kind":"planes-scaling","nonce_bits":power,"carry":kind,"header":header.hex()})
                    if response.exists():response.unlink()
                    t=perf_counter()
                    try:
                        process=subprocess.run([sys.executable,"-m","nucleus_btc.nucleus.worker",str(request),str(response)],cwd=ROOT,capture_output=True,timeout=180)
                        if process.returncode:raise RuntimeError(process.stderr.decode("utf-8","replace")[-1024:])
                        result=json.loads(response.read_text());result["all_cost_seconds"]=perf_counter()-t
                    except (subprocess.TimeoutExpired,RuntimeError) as error:result={"status":"resource_budget_collapsed","reason":str(error)[:1024],"all_cost_seconds":perf_counter()-t}
                    measurements[kind].append(result);progress(f"2^{power} {kind} trial {trial+1}/{repeats}: {result['status']} {result['all_cost_seconds']:.3f}s")
            for name in engines:
                costs=[r["seconds"] for r in baseline_rows[name]]
                baselines[name]["rows"].append({"count":count,"median_seconds":median(costs),"samples":baseline_rows[name]})
            reference=median([s["seconds"] for s in baseline_rows.get("opencl",baseline_rows.get("native",[]))]) if engines else None
            for kind,samples in measurements.items():
                passed=all(s["status"]=="full_sha256d_parity_passed" for s in samples);cost=median(s["all_cost_seconds"] for s in samples)
                item={"count":count,"median_seconds":cost,"passed":passed,"samples":samples}
                if passed and reference:
                    item["fitness"]=Fitness(True,H=count/cost,rho=1-len(samples[0].get("solutions",samples[0].get("exact_solutions",[])))/count,F=cost/reference,phi=0.,M=32*(64+24)*((count+7)//8),K=count).measurements()
                rows[kind].append(item)
            atomic_json(scratch/"checkpoint.json",{"completed_power":power,"rows":rows,"baselines":baselines})
        for value in baselines.values():
            if "rows" in value:value["fit"]=fit_cost(value["rows"])
        return {"schema":1,"status":"measured","seconds":perf_counter()-begun,"baselines":baselines,"representations":{k:{"rows":v,"fit":fit_cost([r for r in v if r["passed"]])} for k,v in rows.items()},
                "family_target":1,"work_source":"fresh deterministic serialized fixtures; no live job or acceptance",
                "all_cost_scope":"Research includes construction, target computation, audit, conversion and isolated process startup; baseline is warmed end-to-end scan",
                "memory_scope":"Estimated live planes; not process RSS or a universal upper bound","power_watts":None,"joules_per_terahash":None,
                "cryptanalytic_discovery":False,"milestone_alpha_claim":False}
    finally:
        for engine in engines.values():engine.close()
