"""Bounded differential diagnostics and conservative exact cut projections."""
from time import perf_counter
from .state import evaluate_family
from ..bitcoin.target import meets_target

ROUNDS=(3,7,11,15,23,31,47,63,71,95,111,124,127)

def differential_probe(family):
    begun=perf_counter();states={};words={};carry={};partials={}
    def observe(r,name,word,metric):
        if r not in ROUNDS:return
        if name=='W':words[r]=word.values
        if name=='T1' and metric:carry[r]=word.carry_residual
        if name in 'abcdefgh' and len(name)==1:
            partials.setdefault(r,{})[name]=word.values
            if name=='h':
                states[r]=tuple(sum(partials[r][letter][i]<<(32*j) for j,letter in enumerate('abcdefgh')) for i in range(family.count))
                del partials[r]
    digests,timing=evaluate_family(family,observer=observe)
    if digests!=[family.candidate(i).digest() for i in range(family.count)]:raise AssertionError('Differential full-round audit failed')
    rows=[];neutral=0;attempts=0
    for variable in range(family.width):
        pairs=[(i,i^(1<<variable)) for i in range(family.count) if not i&(1<<variable)]
        for r in ROUNDS:
            weights=[(states[r][a]^states[r][b]).bit_count() for a,b in pairs]
            row={'variable':family.variables[variable],'round':r,'pairs':len(pairs),'min_active_state_bits':min(weights),
                 'mean_active_state_bits':sum(weights)/len(weights),
                 'mean_W_difference_weight':sum((words[r][a]^words[r][b]).bit_count() for a,b in pairs)/len(pairs),
                 'carry_divergence_fraction':sum(carry[r][a]!=carry[r][b] for a,b in pairs)/len(pairs) if carry.get(r) else None}
            rows.append(row)
            if r==7:neutral+=sum(w<=64 for w in weights);attempts+=len(weights)
    hunt=perf_counter()-begun
    # Savings are only certified whole-state equality; low activity alone
    # cannot eliminate a hash. All surviving full states are compared exactly.
    full_states=states[127];equivalent=family.count-len(set(full_states));deltaC=timing['compute_seconds']/family.count
    benefit=equivalent*deltaC-hunt
    return {'status':'DEAD' if benefit<=0 else 'INCONCLUSIVE','failure_cause':'relation_disappeared' if not equivalent else 'hunt_dominated',
            'rows':rows,'P_find':neutral/max(1,attempts),'K_survive_exact_full_state_equivalence':equivalent,
            'hunt_seconds':hunt,'deltaC_seconds':deltaC,'B_seconds':benefit,'full_sha256d_audited':True,
            'reduced_round_results_are_mining_evidence':False,'rho':0.,'timing':timing}

def prefix_rejection(digests,target,known_bytes=4):
    if not 0<target<1<<256 or not 1<=known_bytes<=32:raise ValueError('Invalid target prefix')
    shift=8*(32-known_bytes);bound=target>>shift
    # Bitcoin compares raw digest bytes as an unsigned little-endian integer.
    return [i for i,d in enumerate(digests) if int.from_bytes(d[-known_bytes:],'little')>bound]

def mitm_projection(family,target=1,projection_bits=4):
    """A lossy cut without a certified backward relation retains all work.

    Forward cut signatures are exact. Enumerating all 256-bit target/cut
    states is deliberately disallowed. The relaxed backward projection is
    universal until a solver certifies a necessary relation.
    """
    if not 1<=projection_bits<=16:raise ValueError('Projection budget exceeded')
    cuts={};exact_cut=None;started=perf_counter()
    def observe(r,name,word,metric):
        nonlocal exact_cut
        if r in (7,15,31,63,95,124) and name=='e':cuts[r]=tuple(v&((1<<projection_bits)-1) for v in word.values)
        if r==124 and name=='e':exact_cut=word.values
    digests,timing=evaluate_family(family,observer=observe)
    rows=[{'round':r,'forward_unique_projection':len(set(v)),'backward_possible_projection':1<<projection_bits,
           'status':'UNKNOWN','pruned':0,'reason':'free omitted bits/carries make the relaxed relation universal'} for r,v in cuts.items()]
    rejected=prefix_rejection(digests,target)
    if any(meets_target(digests[i],target) for i in rejected):raise AssertionError('Unsafe prefix rejection')
    from .cones import backward_prefix_cone
    backward=backward_prefix_cone(exact_cut,target)
    return {'status':'INCONCLUSIVE','failure_cause':'universal_backward_projection','rows':rows,'rho':0.,
            'retained':family.count,'timing':timing,'total_seconds':perf_counter()-started,
            'backward_final_word_cone':backward,'posthash_prefix_rejected':len(rejected),'posthash_prefix_is_cheap_pruning':False}
