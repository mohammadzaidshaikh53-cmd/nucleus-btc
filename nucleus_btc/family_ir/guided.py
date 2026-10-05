from time import perf_counter
from .profile import dependency_profile
from .program import RepresentationProgram,Stage,execute_program
from .split import SplitPolicyV2

def guided_split_experiment(family):
    begun=perf_counter();profile=dependency_profile(family)
    t1=[r for r in profile['rows'] if r['word']=='T1'];early=next(r for r in t1 if r['round']==4)
    previous=next(r for r in t1 if r['round']==3)
    influence=[sum(bool(mask&(1<<b)) for mask in early['bit_dependency_masks'])/32 for b in range(family.width)]
    carry=early['carry_variable_divergence'];growth=early['Nnodes']/max(1,previous['Nnodes'])
    policy=SplitPolicyV2();action=policy.choose(4,'carry-residual',influence,carry,growth,0.,1.)
    # Pilot influence is allowed to guide work, but never to reject it.
    variable=action.get('variable',max(range(family.width),key=lambda b:influence[b]))
    plain=RepresentationProgram((Stage(0,'carry-residual'),))
    split=RepresentationProgram((Stage(0,'carry-residual'),Stage(4,'carry-residual',variable)))
    ds0,baseline=execute_program(family,plain);ds1,result=execute_program(family,split)
    if ds0!=ds1 or ds1!=[family.candidate(i).digest() for i in range(family.count)]:raise AssertionError('Guided split lost exact coverage')
    benefit=baseline['total_seconds']-result['total_seconds'];policy.observe(variable,benefit)
    total=perf_counter()-begun
    return {'status':'DEAD' if benefit<=0 else 'INCONCLUSIVE','failure_cause':'split_cost_dominated' if benefit<=0 else 'pilot_amortization_unproven',
            'K':family.count,'action':action,'selected_variable':family.variables[variable],
            'influence':influence,'node_growth':growth,'policy_history':policy.history,
            'baseline_seconds':baseline['total_seconds'],'split_seconds':result['total_seconds'],
            'pilot_and_all_cost_seconds':total,'benefit_before_pilot_seconds':benefit,
            'split_events':result['split_events'],'no_gaps_no_duplicates':True}
