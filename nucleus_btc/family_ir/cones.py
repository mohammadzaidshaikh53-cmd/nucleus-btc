"""Optional external solvers on bounded local carry and backward cut cones."""
import shutil
from time import perf_counter

def probe_solvers():
    result={name:shutil.which(name) for name in ('cadical','kissat','cryptominisat5')}
    try:
        import z3
        result['z3']=z3.get_version_string()
    except ImportError:result['z3']=None
    return result

def carry_cone(block_bits=4):
    if not 1<=block_bits<=4:raise ValueError('Independent exhaustive cone verifier limited to 4 bits')
    begun=perf_counter()
    try:import z3
    except ImportError:return {'status':'UNKNOWN','reason':'Optional Z3 unavailable','retained':True,'solvers':probe_solvers()}
    width=block_bits+2;mask=(1<<block_bits)-1
    a,b,c=[z3.BitVec(name,width) for name in ('carry_a','carry_b','carry_c')];incoming=z3.BitVec('incoming',width)
    total=a+b+c+incoming
    solver=z3.Solver();solver.set(timeout=500,rlimit=100000)
    solver.add(*[z3.ULE(x,mask) for x in (a,b,c)],z3.ULE(incoming,2))
    low=total&mask;out=z3.LShR(total,block_bits)
    # Reconstructing the total from output residue plus carry must be exact.
    solver.add((low+(out<<block_bits))!=total)
    query_start=perf_counter();answer=solver.check();query=perf_counter()-query_start
    verified=False;cases=0
    if answer==z3.unsat:
        for x in range(mask+1):
            for y in range(mask+1):
                for z in range(mask+1):
                    for carry in range(3):
                        value=x+y+z+carry
                        if (value&mask)+((value>>block_bits)<<block_bits)!=value:raise AssertionError('UNSAT independent reproduction failed')
                        cases+=1
        verified=True
    return {'status':str(answer).upper(),'certificate':'independent exhaustive integer reproduction' if verified else None,
            'independent_cases':cases,'query_seconds':query,'total_seconds':perf_counter()-begun,
            'pruning_authorized':False,'scope':'bounded local multioperand carry identity, not full SHA rejection','solvers':probe_solvers()}

def backward_prefix_cone(e_values,target=1):
    """Exact final-H7 necessary relation at second-compression cut 60.

    Omitted digest words are unconstrained. SAT means possible, not a share.
    UNSAT is actionable only after independent enumeration of the cut values.
    """
    from ..oracle.sha256 import IV
    begun=perf_counter()
    try:import z3
    except ImportError:return {'status':'UNKNOWN','retained':len(e_values),'pruned':0,'reason':'Optional solver unavailable'}
    e=z3.BitVec('cut_e',32);h=e+IV[7]
    high=z3.Concat(z3.Extract(7,0,h),z3.Extract(15,8,h),z3.Extract(23,16,h),z3.Extract(31,24,h))
    solver=z3.Solver();solver.set(timeout=500,rlimit=100000)
    solver.add(z3.Or(*(e==x for x in set(e_values))),z3.ULE(high,target>>224))
    answer=solver.check();pruned=0;verified=False
    if answer==z3.unsat:
        possible=[x for x in e_values if int.from_bytes(((x+IV[7])&0xffffffff).to_bytes(4,'big'),'little')<=target>>224]
        if possible:raise AssertionError('Independent backward projection contradicts UNSAT')
        verified=True;pruned=len(e_values)
    return {'status':str(answer).upper(),'independent_reproduction':verified,'pruned':pruned,
            'retained':len(e_values)-pruned,'proof_seconds':perf_counter()-begun,
            'scope':'exact necessary final-H7 cut relation; all omitted constraints relaxed',
            'cut_after_second_round_index':60}
