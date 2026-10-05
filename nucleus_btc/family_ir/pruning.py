from time import perf_counter
from .state import evaluate_family
from .cost import fitness
from ..gpu.backend import get_backend

def prefix_experiment(family,target=1):
    raw=family.header.serialize()
    with get_backend('opencl',full_unroll=True,alt_boolean=True,local_size=64) as engine:
        engine.scan(raw,0,family.count,target);t=perf_counter();result=engine.scan(raw,0,family.count,target)
        ordinary=perf_counter()-t
    t=perf_counter();digests,proof=evaluate_family(family,prefix_target=target);proof_seconds=perf_counter()-t
    if digests is not None:
        return {'status':'UNKNOWN','retained':family.count,'proof_seconds':proof_seconds,'rho':0,'useful_rho':0}
    audit_start=perf_counter()
    for i in proof['rejected']:
        digest=family.candidate(i).digest()
        if int.from_bytes(digest,'little')<=target:raise AssertionError('Prefix cone incorrectly rejected a candidate')
        if int.from_bytes(digest[-4:],'little')!=proof['known_high_words'][i]:raise AssertionError('Final-word cut mismatch')
    audit=perf_counter()-audit_start
    metrics=fitness(True,ordinary,proof_seconds+audit,construction=proof['construction_seconds'],transition=proof['transition_seconds'],rho=1,proof=proof_seconds)
    return {'status':'DEAD' if metrics['effective_speedup']<=1 else 'INCONCLUSIVE','failure_cause':'proof_cost_dominated',
            'K':family.count,'target':str(target),'proof_seconds':proof_seconds,'independent_audit_seconds':audit,
            'ordinary_gpu_seconds':ordinary,'rho_exact':1.,'useful_rho':1. if metrics['effective_speedup']>1 else 0.,
            'saved_compression_rounds':proof['saved_compression_rounds'],'saved_feedforward_additions_net':proof['saved_feedforward_additions_net'],
            'fully_retained_on_UNKNOWN':True,**metrics}
