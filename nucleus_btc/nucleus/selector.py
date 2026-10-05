"""Saturation-aware research allocation. It never predicts nonce winners."""
from math import log,sqrt

PHASE_II=("family-ir","carry-factor","conditional","program","differential","mitm","cone","egraph")
RESEARCH=PHASE_II+("generated","family","carry","structural","sat","representation")

class ExperimentSelector:
    def __init__(self,statistics=None): self.statistics=statistics or {}
    def estimates(self,kind):
        s=self.statistics.get(kind,{});n=s.get('trials',0);valid=(s.get('valid',0)+1)/(n+2);better=(s.get('better',0)+1)/(n+2)
        recent=s.get('recent',[]);identities=[r['cause'] for r in recent]
        diversity=len(set(identities));repeats=max(0,len(identities)-diversity)
        negative=sum(not r['improved'] for r in recent)
        saturation=min(.995,(negative/8)*(1+repeats/8)) if recent else 0.
        if s.get('exhausted'):saturation=1.
        information=-(better*log(better)+(1-better)*log(1-better))
        novelty=1/(1+repeats);cost=max(.01,s.get('seconds',1.)/max(1,n))
        slope=(recent[-1]['gain']-recent[0]['gain'])/len(recent) if len(recent)>1 else 0.
        prior=3. if kind in PHASE_II else .15
        priority=prior*valid*better*information*novelty*(1-saturation)/sqrt(cost)
        return {"P_valid":valid,"P_better":better,"expected_gain":s.get('best_improvement',1.),"novelty":novelty,
                "expected_information_gain":information,"expected_cost":cost,"saturation":saturation,
                "failure_diversity":diversity,"recent_improvement_slope":slope,
                "time_since_new_result":s.get('since_new',0),"priority":priority}
    def select(self,completed):
        active=[k for k in PHASE_II if not self.statistics.get(k,{}).get('exhausted')]
        if not active:return 'frontier-complete'
        if completed%16==14:return 'regression'
        if completed%16==15:return 'benchmark'
        unexplored=[k for k in active if not self.statistics.get(k,{}).get('trials',0)]
        if unexplored:return max(unexplored,key=lambda k:self.estimates(k)['priority'])
        if completed%7==6:
            under=min(self.statistics.get(k,{}).get('trials',0) for k in active)
            choices=[k for k in active if self.statistics.get(k,{}).get('trials',0)==under]
        else: choices=active
        return max(choices,key=lambda k:self.estimates(k)['priority'])
    def observe(self,kind,result,seconds):
        s=self.statistics.setdefault(kind,{"trials":0,"valid":0,"better":0,"seconds":0.})
        s['trials']+=1;s['seconds']+=max(0.,seconds)
        valid=result.get('status') not in ('failed','resource_budget_collapsed','economic_budget_collapsed')
        gain=result.get('metrics',{}).get('geometric_speedup',result.get('effective_speedup',result.get('speedup_including_construction',0.))) or 0.
        improved=bool(valid and gain>1.02);s['valid']+=int(valid);s['better']+=int(improved)
        s['best_improvement']=max(s.get('best_improvement',1.),gain)
        cause=result.get('failure_cause',result.get('reason',result.get('status','unknown')))[:128]
        previous={r['cause'] for r in s.get('recent',[])}
        s['since_new']=0 if cause not in previous or improved else s.get('since_new',0)+1
        s['recent']=(s.get('recent',[])+[{"cause":cause,"gain":gain,"improved":improved}])[-8:]
        s['exhausted']=bool(result.get('branch_exhausted',s.get('exhausted',False)))
