"""Small Bayesian experiment selector; never predicts winning nonces."""
from math import log,sqrt

RESEARCH=("generated","family","carry","structural","sat","representation")

class ExperimentSelector:
    def __init__(self,statistics=None):self.statistics=statistics or {}
    def estimates(self,kind):
        s=self.statistics.get(kind,{"trials":0,"valid":0,"better":0,"seconds":1.})
        n=s["trials"];valid=(s["valid"]+1)/(n+2);better=(s["better"]+1)/(n+2)
        information=-(better*log(better)+(1-better)*log(1-better))
        novelty=1+1/sqrt(n+1);cost=max(.01,s["seconds"]/max(1,n))
        expected_gain=max(1.,s.get("gain",1.))
        return {"P_valid":valid,"P_better":better,"expected_gain":expected_gain,"novelty":novelty,
                "expected_information_gain":information,"expected_cost":cost,
                "priority":valid*better*expected_gain*novelty*information/cost}
    def select(self,completed):
        # Complete each diverse species once per cycle; periodic safety/measurement
        # jobs cannot be starved by high-scoring cheap experiments.
        offset=completed%8
        if offset==6:return "regression"
        if offset==7:return "benchmark"
        minimum=min(self.statistics.get(k,{}).get("trials",0) for k in RESEARCH)
        available=[k for k in RESEARCH if self.statistics.get(k,{}).get("trials",0)==minimum]
        return max(available,key=lambda k:self.estimates(k)["priority"])
    def observe(self,kind,result,seconds):
        s=self.statistics.setdefault(kind,{"trials":0,"valid":0,"better":0,"seconds":0.,"gain":1.})
        s["trials"]+=1;s["seconds"]+=max(0.,seconds)
        valid=result.get("status") not in ("failed","resource_budget_collapsed","economic_budget_collapsed")
        s["valid"]+=int(valid);gain=result.get("metrics",{}).get("geometric_speedup",result.get("speedup_including_construction",0.))
        s["better"]+=int(valid and gain>1.02);s["gain"]=max(1.,gain)
