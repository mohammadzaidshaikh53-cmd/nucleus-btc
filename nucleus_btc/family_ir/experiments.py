"""Fresh bounded Phase-II experiments with exactness and total-cost gates."""
import json
import os
import shutil
from pathlib import Path
from statistics import median
from time import perf_counter
from . import Dimension,DimensionKind as D,HeaderFamily,FamilyWord
from .state import evaluate_family
from .cost import slope,fitness
from .hypothesis import counterfactual
from ..bitcoin.block_header import BlockHeader
from ..benchmark import heldout_headers,metadata,measure_window,paired_confidence
from ..gpu.backend import get_backend,BackendUnavailable

ROOT=Path(__file__).resolve().parents[2]

def fixture(bits=6,seed=810203,positions=None):
    h=BlockHeader.parse(heldout_headers(seed,1)[0]).with_nonce(0)
    return HeaderFamily(h,(Dimension(D.NONCE32,tuple(range(bits)) if positions is None else tuple(positions),0xffffffff),))

def worker_experiment(kind,generation=0):
    family=fixture(6,810203+generation,positions=(0,5,11,17,23,31))
    if kind=='family-ir':
        from .profile import dependency_profile
        result=dependency_profile(family);rows=result['rows']
        return {'status':'measured','failure_cause':'full_state_saturation','K':family.count,
                'state_frontier':[r for r in rows if r['word']=='state256' and r['round'] in (3,7,15,31,63,127)],
                'full_sha256d_parity':True,'next_hypothesis':counterfactual('residual_saturation').to_dict()}
    if kind=='carry-factor':
        _,metrics=evaluate_family(family,block_bits=(4,8,16)[generation%3])
        r=next(m for m in metrics['carry'] if m['round']==15)
        return {'status':'DEAD' if r['Uresidual']>=.95*family.count else 'INCONCLUSIVE','failure_cause':'residual_saturation',
                'frontier':r,'total_seconds':metrics['total_seconds'],'next_hypothesis':counterfactual('residual_saturation').to_dict()}
    if kind=='program':
        from .program import RepresentationProgram,Stage,execute_program
        baseline=RepresentationProgram((Stage(0,'carry-residual'),Stage(8,'native')))
        program=baseline.mutate(generation,family.width)
        ds,metrics=execute_program(family,program)
        t=perf_counter();expected=[family.candidate(i).digest() for i in range(family.count)];ordinary=perf_counter()-t
        if ds!=expected:raise AssertionError('Representation program exactness gate failed')
        return {'status':'DEAD' if metrics['total_seconds']>ordinary else 'INCONCLUSIVE','failure_cause':'transition_and_materialization_cost',
                'effective_speedup':ordinary/metrics['total_seconds'],'stages':[vars(s) for s in program.stages],
                'construction_seconds':metrics['construction_seconds'],'transition_seconds':metrics['transition_seconds'],
                'split_events':metrics['split_events'],'full_sha256d_parity':True}
    if kind=='differential':
        from .probes import differential_probe
        result=differential_probe(family)
        result['timing']={k:v for k,v in result['timing'].items() if k!='carry'}
        return result
    if kind=='mitm':
        from .probes import mitm_projection
        return mitm_projection(family)
    if kind=='cone':
        from .cones import carry_cone
        return carry_cone()
    if kind=='egraph':
        from .egraph import saturate
        words=[FamilyWord(tuple((i*(j+31)+generation)&0xffffffff for i in range(family.count))) for j in range(5)]
        return saturate(words)
    raise ValueError('Unregistered Phase-II branch')

def scaling(powers=(8,10,12,14),repeats=3):
    from ..solver.scaling import fit_cost
    if len(powers)<3 or any(not 1<=p<=16 for p in powers) or not 3<=repeats<=5:raise ValueError('Bounded full-family scaling required')
    started=perf_counter();rows=[];engines={}
    from ..nucleus.memory import KnowledgeStore
    with KnowledgeStore(ROOT/'results/knowledge.sqlite') as store:config=store.get_state('champion',{}).get('config',{'full_unroll':True,'alt_boolean':True,'local_size':64})
    try:
        for name in ('native','opencl'):
            try:engines[name]=get_backend(name,**(config if name=='opencl' else {}))
            except BackendUnavailable:pass
        for p in powers:
            measurements={b:[] for b in (4,8,16)};baseline={name:[] for name in engines}
            for trial in range(repeats):
                family=fixture(p,911003+p*101+trial);raw=family.header.serialize()
                for name,engine in engines.items():
                    engine.scan(raw,0,family.count,1);t=perf_counter();scan=engine.scan(raw,0,family.count,1)
                    baseline[name].append(perf_counter()-t)
                    if scan.nonces:raise AssertionError('Unexpected native/GPU target-1 solution requires audit')
                widths=(4,8,16) if trial%2==0 else (16,8,4)
                for block in widths:
                    t=perf_counter();digests,metrics=evaluate_family(family,block_bits=block)
                    audit_start=perf_counter();expected=[family.candidate(i).digest() for i in range(family.count)]
                    if digests!=expected:raise AssertionError('Fresh full-family holdout mismatch')
                    audit=perf_counter()-audit_start
                    sample={k:v for k,v in metrics.items() if k!='carry'}
                    sample.update({'fixture_header':raw.hex(),'audit_seconds':audit,'all_cost_seconds':perf_counter()-t,
                                   'carry_frontier':[m for m in metrics['carry'] if m['round'] in (3,4,7,15,31,63,95,127)],
                                   'exact_full_family_holdout':True})
                    measurements[block].append(sample)
                    print(json.dumps({'phase':'scaling','K':family.count,'trial':trial,'block':block,'seconds':round(sample['all_cost_seconds'],3)}),flush=True)
            for block,samples in measurements.items():
                row={'count':1<<p,'block_bits':block,'median_seconds':median(s['total_seconds'] for s in samples),
                     'median_all_cost_seconds':median(s['all_cost_seconds'] for s in samples),'samples':samples,
                     'native_median_seconds':median(baseline['native']) if 'native' in baseline else None,
                     'gpu_median_seconds':median(baseline['opencl']) if 'opencl' in baseline else None}
                row['effective_speedup_vs_gpu']=row['gpu_median_seconds']/row['median_all_cost_seconds'] if row['gpu_median_seconds'] else None
                row['logical_live_word_storage_upper_estimate_bytes']=86*4*row['count']
                row['memory_scope']='logical word storage estimate; excludes Python objects and carry tables, not measured process peak'
                rows.append(row)
            from ..nucleus.persistence import atomic_json
            atomic_json(ROOT/'results/evolution/phase-ii-scaling-progress.json',{'rows':rows,'next_power':p+2})
        fits={};betas=[]
        for block in (4,8,16):
            subset=[r for r in rows if r['block_bits']==block];fits[str(block)]=fit_cost(subset)
            for round_index in (3,4,7,15,31,63,95,127):
                points=[(r['count'],next(m for m in r['samples'][0]['carry_frontier'] if m['round']==round_index)) for r in subset]
                betas.append({'block_bits':block,'round':round_index,'beta_carry':slope([(k,m['Ucarry']) for k,m in points]),
                              'beta_residual':slope([(k,m['Uresidual']) for k,m in points]),'counts':points,
                              'interpretation':'carry-only signatures may compress while output residuals remain linear'})
        return {'status':'NO NEW FAMILY ADVANTAGE FOUND','schema':1,'rows':rows,'fits':fits,'betas':betas,
                'metadata':{name:metadata(engine) for name,engine in engines.items()},'elapsed_seconds':perf_counter()-started,
                'full_sha256d_exact':True,'new_algorithmic_sublinearity_demonstrated':False,
                'Rc_definition':'first round where T1 unique output residuals reach >=95% of K; economic comparison uses GPU total cost',
                'next_hypothesis':counterfactual('residual_saturation').to_dict()}
    finally:
        for engine in engines.values():engine.close()

def structure_probes():
    from .probes import differential_probe,mitm_projection
    from .profile import dependency_profile
    rows=[]
    for name,family in (
        ('interior-nonce',fixture(6,positions=(0,5,11,17,23,31))),
        ('nonce-version',HeaderFamily(fixture().header,(Dimension(D.NONCE32,(5,17,23,31),0xffffffff),Dimension(D.VERSION_ROLL_BITS,(5,28),0x1fffffe0,'SV2-permitted diagnostic version fixture',True,True)))),
        ('nonce-time',HeaderFamily(BlockHeader.parse(heldout_headers(750031,1)[0]).with_nonce(0),(Dimension(D.NONCE32,(5,17,23,31),0xffffffff),Dimension(D.NTIME,(0,1),3)),GENESIS_TIME_MIN,GENESIS_TIME_MAX)),
    ):
        result=differential_probe(family);rows.append({'name':name,'family':family.hierarchy(),'differential':result,'mitm':mitm_projection(family)})
    profile_rows=[]
    for bits in (4,6,8):
        profile=dependency_profile(fixture(bits))
        profile_rows.extend({'bits':bits,**r} for r in profile['rows'] if r['word'] in ('T1','W','state256') and r['round'] in (3,7,15,31,63,127))
    beta_nodes=[]
    for name in ('T1','W'):
        for r in (3,7,15,31,63,127):
            subset=[row for row in profile_rows if row['word']==name and row['round']==r]
            beta_nodes.append({'word':name,'round':r,'beta_ANF_terms':slope([(row['K'],row['Nnodes']) for row in subset]),
                               'scope':'small exhaustive diagnostic families, not large-K advantage'})
    from .hierarchy import hierarchy_baseline
    h=fixture().header
    hierarchy=hierarchy_baseline(HeaderFamily(h,(Dimension(D.NONCE32,tuple(range(8)),0xffffffff),Dimension(D.VERSION_ROLL_BITS,(5,28),0x1fffffe0,'SV2-permitted fixture',True,True))))
    from .pruning import prefix_experiment
    prefix=prefix_experiment(fixture(8))
    from .guided import guided_split_experiment
    guided=guided_split_experiment(fixture(6,positions=(0,5,11,17,23,31)))
    from .program import RepresentationProgram,Stage,execute_program
    f=fixture(4);program_rows=[]
    program=RepresentationProgram((Stage(0,'affine-family'),Stage(8,'carry-residual'),Stage(16,'DAG'),Stage(32,'bitplane'),Stage(72,'native')))
    for seed in range(5):
        genome=program.mutate(seed,f.width).crossover(program,23)
        ds,timing=execute_program(f,genome)
        if ds!=[f.candidate(i).digest() for i in range(f.count)]:raise AssertionError('Family genome failed full holdout')
        program_rows.append({'stages':[vars(s) for s in genome.stages],'total_seconds':timing['total_seconds'],'transition_seconds':timing['transition_seconds'],'split_events':timing['split_events'],'exact':True})
    return {'status':'NO NEW FAMILY ADVANTAGE FOUND','rows':rows,'dependency_growth':profile_rows,'beta_nodes':beta_nodes,'known_hierarchy_baseline':hierarchy,'target_prefix':prefix,'guided_split':guided,'programs':program_rows,
            'rho_useful':0,'next_hypothesis':counterfactual('carry_saturation').to_dict()}

GENESIS_TIME_MIN=1231006504
GENESIS_TIME_MAX=1231006507

def environment_probe():
    candidates=[shutil.which('hipcc'),shutil.which('amdclang++')]
    for root in (Path(os.environ.get('HIP_PATH','C:/unavailable-hip')),Path('C:/Program Files/AMD/ROCm')):
        if root.is_dir():candidates.extend(str(p) for p in root.glob('*/bin/clang++.exe'))
    compiler=next((p for p in candidates if p),None)
    return {'hip_compiler':compiler,'HIP_PATH_present':bool(os.environ.get('HIP_PATH')),
            'hip_status':'detected; separate compile/parity required' if compiler else 'unavailable',
            'matrix_hardware_status':'requires optional HIP/rocWMMA compiler and headers' if not compiler else 'requires compile/parity',
            'pool_config_exists':(ROOT/'config/local.json').is_file(),'power_watts':None}

def matrix_proxy():
    from random import Random
    from ..oracle.sha256 import rotr
    rng=Random(851203);words=[rng.getrandbits(32) for _ in range(64)];t=perf_counter()
    expected=[rotr(v,6)^rotr(v,11)^rotr(v,25) for v in words];scalar=perf_counter()-t
    t=perf_counter();matrix=[[float((v>>b)&1) for b in range(32)] for v in words]
    transform=[[float(i in ((j+6)%32,(j+11)%32,(j+25)%32)) for j in range(32)] for i in range(32)]
    out=[]
    for row in matrix:
        values=[int(sum(row[k]*transform[k][j] for k in range(32)))&1 for j in range(32)]
        out.append(sum(v<<j for j,v in enumerate(values)))
    matrix_seconds=perf_counter()-t
    if out!=expected:raise AssertionError('Exact Boolean matrix Sigma1 transform failed')
    return {'status':'DEAD portable proxy' if matrix_seconds>scalar else 'INCONCLUSIVE','K':len(words),
            'ordinary_seconds':scalar,'matrix_total_seconds':matrix_seconds,'effective_speedup':scalar/matrix_seconds,
            'exact':True,'conversion_cost_included':True,'hardware_WMMA_executed':False,
            'numerics':'0/1 inputs, dot product <=3, integer-exact float sum; reduce mod 2'}

def gpu_sizes():
    from ..verify.parity import verify_backend
    from ..nucleus.memory import KnowledgeStore
    with KnowledgeStore(ROOT/'results/knowledge.sqlite') as store:config=store.get_state('champion',{}).get('config',{'full_unroll':True,'alt_boolean':True,'local_size':64})
    rows=[]
    with get_backend('opencl',**config) as champion:
        for size in (32,64,128,256):
            candidate={**config,'local_size':size}
            with get_backend('opencl',**candidate) as challenger:
                parity=verify_backend(challenger,4096,seed=971003+size)
                warm=heldout_headers(670001+size,1)[0]
                measure_window(champion,warm,1<<22,.3);measure_window(challenger,warm,1<<22,.3)
                pairs=[];ratios=[]
                for i,h in enumerate(heldout_headers(691003+size,9)):
                    if i%2:new=measure_window(challenger,h,1<<22,.2);old=measure_window(champion,h,1<<22,.2)
                    else:old=measure_window(champion,h,1<<22,.2);new=measure_window(challenger,h,1<<22,.2)
                    pairs.append({'order':'BA' if i%2 else 'AB','champion':old,'challenger':new});ratios.append(new['hashes_per_second']/old['hashes_per_second'])
                confidence=paired_confidence(ratios)
                holdout=verify_backend(challenger,16384,seed=987001+size) if confidence['ci95_low']>1.02 else None
                rows.append({'local_size':size,'config':candidate,'parity':parity,'confidence':confidence,'fresh_holdout':holdout,
                             'raw_pairs':pairs,'median_hps':median(p['challenger']['hashes_per_second'] for p in pairs),
                             'metadata':metadata(challenger),'scope':'workgroup size; actual wavefront mode not measured'})
    return {'status':'measured','rows':rows,'champion_config':config,'production_promoted':False,
            'environment':environment_probe(),'matrix':matrix_proxy(),'algorithmic_alpha':1,'conventional_optimization':True}

def run(kind):
    if kind=='scaling':return scaling()
    if kind=='probes':return structure_probes()
    if kind=='cones':return worker_experiment('cone')
    if kind=='gpu':return gpu_sizes()
    if kind=='supervisor':
        from ..nucleus.supervisor import Supervisor
        return Supervisor(ROOT/'results/evolution').run(steps=7,seconds=240)
    raise ValueError('Unknown Phase-II run')
