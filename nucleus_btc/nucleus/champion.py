from ..benchmark import heldout_headers,measure_window,paired_confidence
from ..gpu.opencl import OpenCLBackend
from ..verify.parity import verify_backend
from .memory import KnowledgeStore

def candidates(device_index=0):
    for unroll,algebra,local in [(False,False,64),(True,False,64),(True,True,64),(False,True,64),
                                (True,False,128),(True,True,128),(True,False,256),(True,True,256)]:
        yield dict(device_index=device_index,full_unroll=unroll,alt_boolean=algebra,local_size=local)

def optimize_flags(store_path="results/knowledge.sqlite",count=1<<20,seconds=.12,device_index=0,progress=None):
    configs=list(candidates(device_index));outcomes=[]
    with KnowledgeStore(store_path) as store:
        champion_config=store.get_state("champion",{}).get("config",configs[0])
        champion=OpenCLBackend(**champion_config)
        try:
            verify_backend(champion)
            measure_window(champion,heldout_headers(number=1)[0],count,.5)
            for index,config in enumerate(configs):
                if progress:progress(f"Testing exact candidate {index+1}/{len(configs)}: {config}")
                if config==champion_config:continue
                try:
                    with OpenCLBackend(**config) as challenger:
                        parity=verify_backend(challenger,samples=1024,seed=9000+index)
                        ratios=[]
                        for pair,h in enumerate(heldout_headers(seed=7000+index,number=7)):
                            # Warm both and alternate order on every pair to reduce drift bias.
                            champion.scan(h,0,4096,1);challenger.scan(h,0,4096,1)
                            if pair%2:
                                new=measure_window(challenger,h,count,seconds);old=measure_window(champion,h,count,seconds)
                            else:
                                old=measure_window(champion,h,count,seconds);new=measure_window(challenger,h,count,seconds)
                            ratios.append(new["hashes_per_second"]/old["hashes_per_second"])
                        metrics={**paired_confidence(ratios),"parity":parity,"paired_ratios":ratios,"objective":"throughput; energy unmeasured","work_source":"held-out serialized header fixtures"}
                        metrics["compared_against"]=dict(champion_config)
                        if metrics["ci95_low"]>1.02:
                            # Statistical confidence is limited to tested fixtures, never universal proof.
                            record=store.put("PROVEN",config,metrics,"Tested exact transform and reproducible throughput gain",metrics["geometric_speedup"])
                            store.set_state("champion",{"config":config,"record_id":record,"scope":"provisional throughput champion; no measured energy or live pool result"})
                            replacement=OpenCLBackend(**config);champion.close();champion=replacement;champion_config=config
                            state="promoted"
                        else:
                            state="FRONTIER" if metrics["geometric_speedup"]>1.02 else "DEAD"
                            store.put(state,config,metrics,"No confidence-qualified improvement over current champion",metrics["geometric_speedup"])
                        outcomes.append({"config":config,"result":state,"metrics":metrics})
                except Exception as e:
                    store.put("DEAD",config,{},f"{type(e).__name__}: {e}")
                    outcomes.append({"config":config,"result":"failed","error":str(e)})
            store.set_state("champion",{"config":champion_config,"record_id":store.get_state("champion",{}).get("record_id"),"scope":"provisional throughput champion; energy and live acceptance unmeasured"})
            return {"champion":champion_config,"experiments":outcomes,"cryptanalytic_discovery":False}
        finally:champion.close()

def confirm_champion(store_path="results/knowledge.sqlite",count=1<<22,seconds=.5):
    """Fresh held-out jobs after candidate selection; compare directly to original baseline."""
    with KnowledgeStore(store_path) as store:
        chosen=store.get_state("champion",{}).get("config",next(candidates()))
    original=next(candidates(chosen.get("device_index",0)))
    with OpenCLBackend(**original) as baseline,OpenCLBackend(**chosen) as champion:
        verify_backend(champion,16384,seed=20261005)
        warm=heldout_headers(seed=8112,number=1)[0]
        measure_window(baseline,warm,count,1.);measure_window(champion,warm,count,1.)
        pairs=[];baseline_samples=[];champion_samples=[]
        for i,h in enumerate(heldout_headers(seed=823199,number=9)):
            if i%2:
                new=measure_window(champion,h,count,seconds);old=measure_window(baseline,h,count,seconds)
            else:
                old=measure_window(baseline,h,count,seconds);new=measure_window(champion,h,count,seconds)
            baseline_samples.append(old["hashes_per_second"]);champion_samples.append(new["hashes_per_second"])
            pairs.append(new["hashes_per_second"]/old["hashes_per_second"])
        from statistics import median
        return {"original_config":original,"champion_config":chosen,"confirmation":paired_confidence(pairs),
                "baseline_median_hps":median(baseline_samples),"champion_median_hps":median(champion_samples),
                "paired_ratios":pairs,"batch_size":count,"window_seconds":seconds,
                "power_measured":False,"pool_acceptance_measured":False,"work_source":"fresh held-out serialized header fixtures"}

from .generated import optimize_generated as optimize
