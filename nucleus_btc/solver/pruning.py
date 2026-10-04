from dataclasses import dataclass
from math import log10
from ..bitcoin.target import meets_target

@dataclass(frozen=True)
class DigestIntervalProof:
    """Exact numerical bounds. Caller must separately establish the bounds for its family."""
    lower:int
    upper:int
    target:int
    def rejects(self):
        if not 0<=self.lower<=self.upper<(1<<256) or not 0<self.target<(1<<256):raise ValueError("Invalid digest interval")
        return self.lower>self.target

def pruning_metrics(rejected,examined,analysis_seconds,baseline_seconds,survivor_fraction=1.):
    if not 0<=rejected<=examined or examined<=0 or baseline_seconds<=0 or analysis_seconds<0 or not 0<=survivor_fraction<=1:
        raise ValueError("Invalid pruning measurements")
    rho=rejected/examined;F=analysis_seconds/baseline_seconds;cost=F+(1-rho)*survivor_fraction
    return {"rho":rho,"Q":-log10(1-rho) if rho<1 else None,"F":F,"speedup":1/cost if cost>0 else None}

def audit_rejections(headers,target,rejected_indexes,hasher):
    """Exhaustive finite-fixture check; catches valid solutions silently pruned away."""
    indexes=set(rejected_indexes)
    if any(i<0 or i>=len(headers) for i in indexes):raise ValueError("Rejected index outside family")
    hashes=hasher(headers)
    if len(hashes)!=len(headers):raise AssertionError("Audit hasher returned wrong number of digests")
    lost=[i for i in indexes if meets_target(hashes[i],target)]
    if lost:raise AssertionError(f"Pruning lost {len(lost)} valid solutions")
    return {"audited":len(headers),"rejected":len(indexes),"lost":0,"universal_proof":False}
