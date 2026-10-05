"""Append-only offline predicate experiments; no pool access or promotion."""
import argparse
import json
import math
import sqlite3
import sys
import tracemalloc
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from statistics import median
from time import perf_counter
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nucleus_btc.benchmark import heldout_headers, measure_window, metadata
from nucleus_btc.bitcoin.block_header import BlockHeader
from nucleus_btc.bitcoin.target import difficulty_target, compact_to_target, UINT256_MAX
from nucleus_btc.family_ir import HeaderFamily, Dimension, DimensionKind as D
from nucleus_btc.family_ir.symbolic import SymbolicFamily
from nucleus_btc.family_ir.workspace_compiler import compile_family
from nucleus_btc.gpu.backend import get_backend
from nucleus_btc.ir.target_predicate import TargetPredicate
from nucleus_btc.nucleus.supervisor import Supervisor, source_fingerprint
from nucleus_btc.nucleus.memory import KnowledgeStore
from nucleus_btc.oracle.sha256 import sha256d
from nucleus_btc.target_engine import analyze_workspace, RefinementEngine, fallback, refinement_source
from nucleus_btc.verify.parity import verify_backend


def save(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, allow_nan=False); stream.write('\n')


def champion_config():
    with sqlite3.connect((ROOT/'results/knowledge.sqlite').as_uri()+'?mode=ro', uri=True) as db:
        row = db.execute("SELECT value FROM state WHERE key='champion'").fetchone()
    if not row: raise RuntimeError('Verified champion record required')
    return json.loads(row[0])['config']


def champion(output):
    with get_backend('opencl', **champion_config()) as engine:
        verified = verify_backend(engine, samples=16384, seed=202610071)
        jobs = heldout_headers(202610071, 9)
        measure_window(engine, jobs[0], 1 << 22, .6)
        samples = [measure_window(engine, raw, 1 << 22, .2) for raw in jobs]
        hps = median(s['hashes_per_second'] for s in samples)
        report = dict(schema=1, metadata=metadata(engine), config=engine.config, parity=verified,
                      source=source_fingerprint(), hashes_per_second=hps, gh_per_second=hps/1e9,
                      samples=samples, startup_compilation_excluded_from_steady_state=True,
                      target_budgets=[dict(target_thps=t, required_speedup=t*1e12/hps, normalized_total_cost_budget=hps/(t*1e12)) for t in (20, 30)],
                      power_watts=None, joules_per_terahash=None, original_target_achieved=False,
                      work_source='fresh held-out local serialized jobs; no live pool acceptance')
    save(output, report)
    print(json.dumps(dict(output=str(output), ghps=report['gh_per_second'], budgets=report['target_budgets'])), flush=True)


def make_workspace(raw, bits, extra_version=False):
    dims = (Dimension(D.NONCE32, tuple(range(min(bits, 32))), 0xffffffff),)
    if extra_version: dims += (Dimension(D.VERSION_ROLL_BITS, tuple(range(5, 29)), 0x1fffffe0),)
    return compile_family(HeaderFamily(BlockHeader.parse(raw).with_nonce(0), dims)).workspace


def precision_loss(result):
    rows = result.get('round_precision', [])
    return next((r for r in rows if r['compression'] == 'header/first/1' and r['retained_sparse_nonlinear_bits'] == 0), None)


def experiment(output, champion_file):
    verified = json.loads(champion_file.read_text(encoding='utf-8'))
    if not verified['parity']['passed']: raise ValueError('Fresh verified champion required')
    hps = verified['hashes_per_second']
    started = perf_counter()
    report = dict(schema=1, timestamp_utc=datetime.now(timezone.utc).isoformat(), source=source_fingerprint(),
                  champion_file=str(champion_file.resolve().relative_to(ROOT)), champion=verified,
                  target_achieved=False, production_champion_modified=False, power_watts=None, joules_per_terahash=None,
                  target_fixtures={'share': {'difficulty': '256', 'target': str(difficulty_target('256')), 'provenance': 'explicit synthetic pool-share-style fixture'},
                                   'network': {'nBits_hex': '17020000', 'target': str(compact_to_target(0x17020000)),
                                               'provenance': 'explicit synthetic recent-network-style scale (~140.735 trillion difficulty); not an observed or current network block'},
                                   'loose': {'target': str(UINT256_MAX//8), 'provenance': 'synthetic exhaustive diagnostic'}},
                  work_source='held-out serialized fixtures seeds 202610072..074; no pool credentials', rows=[], conceptual_scaling=[], refinements=[])
    regimes = [('share', difficulty_target('256')), ('network', compact_to_target(0x17020000))]
    with get_backend('opencl', **verified['config']) as engine:
        report['session_metadata'] = metadata(engine)
        for seed in (202610072, 202610073, 202610074):
            raw = heldout_headers(seed, 1)[0]
            tiny = make_workspace(raw, 8)
            equal_target = int.from_bytes(sha256d(tiny.header(137)), 'little')
            cases = [(p, name, target) for p in (8, 16, 24) for name, target in regimes]
            cases += [(8, 'loose', UINT256_MAX//8), (8, 'equality', equal_target), (8, 'max', UINT256_MAX), (8, 'one', 1)]
            for power, regime, target in cases:
                w = make_workspace(raw, power)
                header = w.header(0)
                engine.scan(header, 0, w.count, target, capacity=min(w.count, 4096))
                samples = []
                for _ in range(5):
                    before = perf_counter(); result = engine.scan(header, 0, w.count, target, capacity=min(w.count, 4096))
                    samples.append(perf_counter()-before)
                ordinary = median(samples)
                for observable in ('masks', 'product', 'lineage', 'backward'):
                    begin = perf_counter()
                    setup_start = perf_counter(); scope = make_workspace(raw, power); setup_seconds = perf_counter()-setup_start
                    with patch.object(HeaderFamily, 'construct', side_effect=AssertionError('Accidental K enumeration')):
                        analysis = analyze_workspace(scope, target, observable)
                    # Independent exhaustive audit for K=256. Larger K uses
                    # eight samples solely for regression, never as a proof.
                    audit_start = perf_counter(); predicate = TargetPredicate(scope, target)
                    indices = range(scope.count) if power == 8 else [i*(scope.count-1)//7 for i in range(8)]
                    passing = 0
                    for i in indices:
                        candidate = scope.header(i); exact = int.from_bytes(sha256d(candidate), 'little') <= target
                        if predicate.evaluate(i) != exact: raise AssertionError('Independent predicate audit mismatch')
                        passing += exact
                    audit_seconds = perf_counter()-audit_start
                    if analysis['status'] == 'REJECTED':
                        if passing: raise AssertionError('Lost valid candidate')
                        fb = dict(seconds=0., fallback_gpu_candidates=0, fallback_cpu_candidates=0, independent_audit_seconds=0., status='CERTIFIED_REJECTION', solutions=[])
                        rho = 1.
                    else:
                        fb = fallback(scope, target, engine, max_candidates=1 << 24)
                        rho = 0.
                        if power == 8:
                            final_audit_start = perf_counter()
                            expected = [i for i in range(scope.count) if int.from_bytes(sha256d(scope.header(i)), 'little') <= target]
                            if expected != fb['solutions']: raise AssertionError('Fallback lost or invented a solution')
                            audit_seconds += perf_counter()-final_audit_start
                    total = perf_counter()-begin
                    analysis_cost = setup_seconds+analysis['total_seconds']+audit_seconds
                    speedup = ordinary/total
                    row = dict(seed=seed, power=power, regime=regime, target=str(target), scope=scope.fingerprint,
                               conceptual_K=scope.count, K_materialized=False, workspace_setup_seconds=setup_seconds,
                               analysis=analysis, precision_collapse=precision_loss(analysis),
                               refinement_leaves=1, maximum_depth=0, coverage_proof_seconds=0.,
                               fallback={k: v for k,v in fb.items() if k != 'solutions'}, solutions_count=len(fb['solutions']),
                               independent_audit_seconds=audit_seconds+fb['independent_audit_seconds'],
                               audit_scope_K=scope.count if power == 8 else 8, audit_exhaustive=power == 8,
                               random_audit_is_proof=False, candidate_array_materialized=False,
                               baseline=dict(same_scope=True, warm=True, samples_seconds=samples, median_seconds=ordinary,
                                             compilation_excluded=True, result_buffer_capacity=min(scope.count,4096)),
                               total_wall_seconds=total, F_analysis=analysis_cost/ordinary, normalized_total_cost=total/ordinary,
                               exact_rho=rho, useful_rho=rho if speedup > 1 else 0.,
                               Q=-math.log10(1-rho) if rho < 1 else None, Q_scope='-log10 retained fraction; infinity represented null at rho=1',
                               effective_speedup=speedup, equivalent_work_hps=scope.count/total,
                               equivalent_work_scope='measured full offline pipeline; K/total, no avoided-work extrapolation',
                               peak_memory_bytes=None, power_watts=None, joules_per_terahash=None,
                               cost_scope='setup + compile + rewrite + abstract proof + checker + independent audit + actual survivor scan + solution oracle validation + host overhead')
                    report['rows'].append(row)
                print(json.dumps(dict(seed=seed, K=w.count, regime=regime, target_information=analysis['target_information'], exact_rejection=rho)), flush=True)
        # Conceptual-only scaling: no substitute estimated GPU time is used as
        # a same-family measured baseline, and retained work remains scheduled.
        for bits, version in ((8, False), (16, False), (24, False), (32, False), (32, True)):
            w = make_workspace(heldout_headers(202610075, 1)[0], bits, version)
            with patch.object(HeaderFamily, 'construct', side_effect=AssertionError('Enumeration')):
                analysis = analyze_workspace(w, regimes[1][1])
            report['conceptual_scaling'].append(dict(conceptual_K=w.count, analysis=analysis,
                       fallback=fallback(w, regimes[1][1], engine, max_candidates=1) if w.count>1 else {},
                       F=None, effective_speedup=None, baseline_scope='not measured for conceptual-only scaling'))
        # Separate tracemalloc run: do not mix instrumentation timing into the
        # actual economics. Include the two graph views and all analysis objects.
        w = make_workspace(heldout_headers(202610075, 1)[0], 32, True)
        tracemalloc.start(); instrumented_start = perf_counter()
        measured = analyze_workspace(w, regimes[1][1])
        current, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
        report['memory_instrumentation'] = dict(conceptual_K=w.count, current_bytes=current, peak_bytes=peak,
                         instrumented_seconds=perf_counter()-instrumented_start, target_information=measured['target_information'],
                         scope='Python allocations via tracemalloc; excludes driver/device memory and process RSS; separate from economics')
        for observable in ('product', 'lineage', 'backward'):
            w = make_workspace(heldout_headers(202610076, 1)[0], 24)
            for economic in (True, False):
                raw = w.header(0); baseline = []
                engine.scan(raw, 0, w.count, regimes[1][1])
                for _ in range(5):
                    before = perf_counter(); engine.scan(raw, 0, w.count, regimes[1][1]); baseline.append(perf_counter()-before)
                begin = perf_counter()
                tree = RefinementEngine(max_leaves=4, max_depth=3, seconds=3, pilot_variables=2,
                                        champion_hps=hps if economic else None, observable=observable).run(w, regimes[1][1])
                fallbacks = []
                for node in tree['tree']['nodes'].values():
                    if not node['children'] and node['status'] != 'REJECTED':
                        leaf = SymbolicFamily(w.family, tuple(map(tuple, node['fixed'])))
                        fallbacks.append(fallback(leaf, regimes[1][1], engine, max_candidates=1 << 24))
                total = perf_counter()-begin; rho = tree['coverage']['rejected']/w.count
                report['refinements'].append(dict(observable=observable, economic_cutoff=economic, **tree,
                         fallback=[{k:v for k,v in f.items() if k!='solutions'} for f in fallbacks],
                         baseline={'same_scope': True, 'warm': True, 'samples_seconds': baseline, 'median_seconds': median(baseline)},
                         F_analysis=tree['total_seconds']/median(baseline), total_wall_seconds=total,
                         effective_speedup=median(baseline)/total, exact_rho=rho,
                         useful_rho=rho if total < median(baseline) else 0., Q=-math.log10(1-rho) if rho<1 else None,
                         equivalent_work_hps=w.count/total, peak_memory_bytes=None, power_watts=None))
    scaling = report['conceptual_scaling']; xs = [math.log(r['conceptual_K']) for r in scaling]; ys = [math.log(r['analysis']['total_seconds']) for r in scaling]
    xm, ym = sum(xs)/len(xs), sum(ys)/len(ys)
    report['analysis_scaling_slope'] = sum((x-xm)*(y-ym) for x,y in zip(xs,ys))/sum((x-xm)**2 for x in xs)
    report['scaling_caveat'] = 'Bounded abstraction becomes TOP; a small slope with zero target information is not sublinear exact mining. Five heterogeneous widths, one job, no inference about untested mechanisms.'
    report['gates'] = {'exact_parity': True, 'nonenumeration': True, 'soundness_tests': True,
                       'toy_cross_domain_precision': True, 'nontrivial_full_sha_target_discrimination': False,
                       'leaves_far_below_K': True, 'useful_unseen_realistic_rejection': False}
    report['best_effective_speedup'] = max(r['effective_speedup'] for r in report['rows'])
    report['best_realistic_speedup'] = max(r['effective_speedup'] for r in report['rows'] if r['regime'] in ('share', 'network'))
    report['useful_rho'] = max(r['useful_rho'] for r in report['rows'])
    report['status'] = 'B_TESTED_MECHANISMS_FALSIFIED'
    report['distinct_unresolved_frontier'] = 'Nonenumerating joint schedule/carry/Boolean invariant that survives both complete SHA compressions, narrows the real target and has an independent certificate; no relation or advantage established.'
    report['elapsed_seconds'] = perf_counter()-started
    save(output, report)
    print(json.dumps(dict(output=str(output), rows=len(report['rows']), status=report['status'], best_realistic_speedup=report['best_realistic_speedup'], useful_rho=report['useful_rho'])), flush=True)


def supervisor(output, directory, steps):
    report = Supervisor(directory, profile='predicate-vnext').run(steps=steps, seconds=240)
    with KnowledgeStore(directory/'state.sqlite') as store:
        report['records'] = store.records(); report['lemmas'] = store.lemmas()
    save(output, report)
    print(json.dumps({k: report[k] for k in ('completed_this_run','total_completed','next_kind','production_champion_modified')}), flush=True)


def inverse_followup(output, champion_file):
    verified = json.loads(champion_file.read_text())
    report = dict(schema=1, source=source_fingerprint(), refinement_source=refinement_source(),
                  mechanism='target demand on exact pre-packing digest state, through proved one-unknown inverses',
                  causal_parent='predicate-vnext-experiments-01.json: backward demand stopped at byte-packing OR',
                  champion_file=str(champion_file), rows=[], production_champion_modified=False,
                  target_achieved=False, power_watts=None, joules_per_terahash=None)
    with get_backend('opencl', **verified['config']) as engine:
        report['session_metadata'] = metadata(engine)
        for generation in range(3):
            raw = heldout_headers(202610080+generation, 1)[0]
            target = difficulty_target('256') if generation != 1 else compact_to_target(0x17020000)
            w = make_workspace(raw, 24); header = w.header(0)
            engine.scan(header, 0, w.count, target); samples = []
            for _ in range(5):
                before = perf_counter(); engine.scan(header, 0, w.count, target); samples.append(perf_counter()-before)
            begin = perf_counter()
            with patch.object(HeaderFamily, 'construct', side_effect=AssertionError('Enumeration')):
                analysis = analyze_workspace(w, target, 'backward')
            before = perf_counter(); p = TargetPredicate(w, target)
            for i in [j*(w.count-1)//15 for j in range(16)]:
                if p.evaluate(i) != (int.from_bytes(sha256d(w.header(i)), 'little') <= target): raise AssertionError('Follow-up parity failed')
            audit_seconds = perf_counter()-before
            if analysis['target_information'] != 0: raise AssertionError('Changed conclusion; holdout gate must be reopened')
            fb = fallback(w, target, engine, max_candidates=1 << 24)
            total = perf_counter()-begin; ordinary = median(samples)
            report['rows'].append(dict(seed=202610080+generation, target=str(target),
                target_fixture='share difficulty256' if generation != 1 else 'synthetic network nBits17020000',
                conceptual_K=w.count, K_materialized=False, scope=w.fingerprint, analysis=analysis,
                refinement_leaves=1, maximum_depth=0, coverage_proof_seconds=0.,
                fallback={k:v for k,v in fb.items() if k!='solutions'},
                audit_scope_K=16, audit_exhaustive=False, random_audit_is_proof=False,
                independent_audit_seconds=audit_seconds+fb['independent_audit_seconds'],
                baseline={'same_scope':True, 'warm':True, 'samples_seconds':samples, 'median_seconds':ordinary},
                F_analysis=(analysis['total_seconds']+audit_seconds)/ordinary,
                total_wall_seconds=total, effective_speedup=ordinary/total, normalized_total_cost=total/ordinary,
                exact_rho=0., useful_rho=0., Q=0., equivalent_work_hps=w.count/total,
                peak_memory_bytes=None, power_watts=None, joules_per_terahash=None,
                cost_scope='full compile/rewrite/proof/check + sampled regression audit + actual unchanged champion fallback + solution validation'))
    report['status']='B_INVERSE_DEMAND_FALSIFIED_AT_JOINT_UNKNOWN_ADD'
    report['best_effective_speedup']=max(r['effective_speedup'] for r in report['rows'])
    save(output, report)
    print(json.dumps(dict(output=str(output), status=report['status'], best_speedup=report['best_effective_speedup'],
          losses=[r['analysis']['backward']['losses'] for r in report['rows']])), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('mode', choices=['champion','experiments','supervisor','inverse-followup'])
    p.add_argument('--output', type=Path, required=True); p.add_argument('--champion', type=Path)
    p.add_argument('--directory', type=Path, default=ROOT/'results/evolution/predicate-vnext')
    p.add_argument('--steps', type=int, default=12); args = p.parse_args()
    if args.output.exists(): raise FileExistsError('Historical evidence cannot be overwritten')
    if args.mode == 'champion': champion(args.output)
    elif args.mode in ('experiments','inverse-followup'):
        if not args.champion: p.error('--champion required')
        (experiment if args.mode=='experiments' else inverse_followup)(args.output, args.champion)
    else: supervisor(args.output, args.directory, args.steps)
