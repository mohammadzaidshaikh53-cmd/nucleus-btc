"""Economic symbolic probes, adaptive exact family splitting and native fallback."""
from dataclasses import dataclass,asdict
from time import perf_counter
from ..representations.symbolic import symbolic_experiment
from ..gpu.backend import validate_range
from .family_split import scan_with_split

@dataclass
class SplitPolicy:
    max_symbolic_bits:int=4
    max_nodes:int=20000
    max_probes:int=3
    growth_fraction:float=.8
    economic_ratio_limit:float=1.
    def choose(self,bits):return max(0,bits-1) # Highest live nonce bit yields disjoint contiguous children.
    def validate(self):
        if not 1<=self.max_symbolic_bits<=8 or not 64<=self.max_nodes<=2000000 or not 0<=self.max_probes<=32:raise ValueError("Invalid split policy")
        if not 0<self.economic_ratio_limit<=100 or not 0<self.growth_fraction<=1:raise ValueError("Invalid economic/growth policy")

def solve_family(backend,header,start,count,target,policy=None,capacity=4096):
    validate_range(header,start,count);policy=policy or SplitPolicy();policy.validate()
    begun=perf_counter();found=[];stack=[(start,count)];probes=[];splits=0;fallbacks=0;examined=0
    # Pilot cost is measured and included, not silently subtracted from the solver.
    pilot=min(count,128);t=perf_counter();backend.scan(header,start,pilot,target,capacity=max(pilot,capacity))
    pilot_seconds=perf_counter()-t;estimate_per_candidate=pilot_seconds/pilot;demoted=False
    while stack:
        offset,size=stack.pop();bits=size.bit_length()-1
        can_symbolic=not demoted and len(probes)<policy.max_probes and size==1<<bits and offset%size==0 and bits>=1
        if can_symbolic and bits>policy.max_symbolic_bits:
            half=size//2;stack.extend([(offset+half,size-half),(offset,half)]);splits+=1;continue
        if can_symbolic:
            adjusted=header[:76]+offset.to_bytes(4,"little")
            result=symbolic_experiment(bits,policy.max_nodes,"bdd",header=adjusted,target=target,
                                       economic_budget_seconds=estimate_per_candidate*size*policy.economic_ratio_limit,
                                       variable_order=list(reversed(range(bits))))
            result["offset"]=offset;result["estimated_conventional_seconds"]=estimate_per_candidate*size
            probes.append(result)
            if result["status"]=="full_sha256d_parity_passed":
                found.extend(result["exact_solutions"]);examined+=size;continue
            if result["status"]=="economic_budget_collapsed":demoted=True
            elif size>2 and len(probes)<policy.max_probes:
                half=size//2;stack.extend([(offset+half,half),(offset,half)]);splits+=1;continue
        # UNKNOWN, growth collapse and economic demotion preserve every candidate.
        result=scan_with_split(backend,header,offset,size,target,capacity)
        found.extend(result["result"].nonces);examined+=size;fallbacks+=1
    elapsed=perf_counter()-begun
    if examined!=count or len(set(found))!=len(found):raise AssertionError("Adaptive solver coverage/duplicate invariant failed")
    return {"status":"exact_family_solved","solutions":sorted(found),"examined":examined,"seconds":elapsed,
            "policy":asdict(policy),"splits":splits,"native_fallbacks":fallbacks,"probes":probes,
            "pilot_seconds":pilot_seconds,"all_construction_conversion_split_proof_fallback_costs_included":True,
            "economic_demoted":demoted,"cryptanalytic_discovery":False}
