from dataclasses import dataclass,field

@dataclass(frozen=True)
class StridedSubspace:
    width:int
    fixed:tuple[tuple[int,int],...]=()
    def __post_init__(self):
        if not 0<=self.width<=24 or len({b for b,v in self.fixed})!=len(self.fixed) or any(not 0<=b<self.width or v not in (0,1) for b,v in self.fixed):
            raise ValueError("Invalid fixed interior variables")
    @property
    def free(self): return tuple(b for b in range(self.width) if b not in dict(self.fixed))
    @property
    def count(self): return 1<<len(self.free)
    def map(self,index):
        if not 0<=index<self.count: raise ValueError("Index outside strided subspace")
        return sum(v<<b for b,v in self.fixed)|sum(((index>>j)&1)<<b for j,b in enumerate(self.free))
    def split(self,variable):
        if variable not in self.free: raise ValueError("Split variable already fixed or outside family")
        return tuple(StridedSubspace(self.width,tuple(sorted(self.fixed+((variable,v),)))) for v in (0,1))
    def fallback(self,family,backend,target):
        # Arbitrary header dimensions cannot be represented by one contiguous
        # nonce scan. Digest each mapped header, preserving all candidates.
        from ..bitcoin.target import meets_target
        matches=[]
        for i in range(self.count):
            index=self.map(i);raw=family.candidate(index).serialize();digest=backend.hash_headers([raw])[0]
            if meets_target(digest,target): matches.append(index)
        return {"examined":self.count,"candidate_indices":matches}

@dataclass
class SplitPolicyV2:
    history:list=field(default_factory=list)
    def choose(self,round_index,representation,influence,carry_divergence,node_growth,transition_cost,native_cost):
        if native_cost<=0: raise ValueError("Positive measured native cost required")
        if transition_cost>=native_cost: return {"action":"fallback native","round":round_index}
        scored=[]
        for variable,weight in enumerate(influence):
            historical=sum(h['benefit'] for h in self.history if h['variable']==variable)
            reduction=(weight+carry_divergence[variable])*max(0,node_growth)+historical
            scored.append((reduction/2,variable))
        best=max(scored,default=(0,None))
        if best[0]>.5: return {"action":"split","variable":best[1],"estimated_reduction_per_child":best[0]}
        if node_growth>1: return {"action":"transition representation","representation":"bitplane"}
        return {"action":"continue","representation":representation}
    def observe(self,variable,benefit):
        self.history=(self.history+[{"variable":variable,"benefit":float(benefit)}])[-32:]
