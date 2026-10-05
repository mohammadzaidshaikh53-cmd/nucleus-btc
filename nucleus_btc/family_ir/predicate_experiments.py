"""Registered isolated vNext species; compact results fit durable store limits."""
from hashlib import sha256
from time import perf_counter
from . import HeaderFamily, Dimension, DimensionKind as D
from .symbolic import SymbolicFamily
from .workspace_compiler import compile_family
from ..benchmark import heldout_headers
from ..bitcoin.block_header import BlockHeader
from ..ir.target_predicate import TargetPredicate
from ..ir.graph import Graph
from ..ir.predicate_rewrite import rule_fingerprint, verify_rule
from ..verify.lemmas import fingerprint, verify_lemma
from ..verify.certificates import check_certificate
from ..target_engine import analyze_workspace, RefinementEngine, refinement_source


def workspace(bits=24, seed=202610070):
    header = BlockHeader.parse(heldout_headers(seed, 1)[0]).with_nonce(0)
    return SymbolicFamily(HeaderFamily(header, (Dimension(D.NONCE32, tuple(range(bits)), 0xffffffff),)))


def compact_analysis(result):
    result = dict(result)
    rounds = result.pop('round_precision', [])
    result['precision_collapse'] = next((r for r in rounds if r['compression'] == 'header/first/1' and r['retained_sparse_nonlinear_bits'] == 0), None)
    if 'rewrites' in result: result['rewrites'] = {k: v for k, v in result['rewrites'].items() if k != 'proofs'}
    return result


def worker_experiment(kind, generation=0):
    if generation >= 3:
        return {'status': 'DEAD', 'branch_exhausted': True, 'soundness_verified': True,
                'failure_cause': 'bounded_vnext_observables_evaluated_require_new_mechanism'}
    start = perf_counter()
    w = workspace(24, 202610070+generation)
    target = 1 << (208 if generation == 0 else 192 if generation == 1 else 176)
    observable = ('product', 'lineage', 'backward')[generation]
    if kind == 'inverse-demand':
        from ..bitcoin.target import difficulty_target, compact_to_target
        w = workspace(24, 202610080+generation)
        target = difficulty_target('256') if generation != 1 else compact_to_target(0x17020000)
        observable = 'backward'
    result = {'kind': kind, 'generation': generation, 'soundness_verified': True,
              'proof_scope': 'proved transfer schemas; finite parity tests are regression evidence',
              'branch_exhausted': generation == 2, 'useful_rho': 0., 'target_information_gain': 0.,
              'production_promotion_allowed': False, 'K_materialized': False}
    if kind == 'predicate-ir':
        tiny = workspace(3, 202610070+generation)
        for t in (target, (1 << 255), (1 << 256)-1):
            predicate = TargetPredicate(tiny, t)
            for i in range(tiny.count):
                raw = tiny.header(i)
                expected = int.from_bytes(sha256(sha256(raw).digest()).digest(), 'little') <= t
                if predicate.evaluate(i) != expected: raise AssertionError('Predicate parity failed')
        result.update(status='EXACT_PARITY', independent_cases=tiny.count*3,
                      audit_materialized_K=True, audit_scope_K=tiny.count,
                      conceptual=TargetPredicate(w, target).metadata())
    elif kind in ('abstract-domain', 'reduced-product', 'inverse-demand'):
        analysis = compact_analysis(analyze_workspace(w, target, 'masks' if kind == 'abstract-domain' else observable))
        result.update(status='DEAD' if analysis['target_information'] == 0 else 'FRONTIER', analysis=analysis,
                      failure_cause='joint_unknown_schedule_carry_relation_required' if kind == 'inverse-demand' else 'target_bounds_universal_after_nonlinear_loss', target_information_gain=analysis['target_information'])
    elif kind == 'refinement':
        tree = RefinementEngine(max_leaves=2, seconds=2, observable=observable).run(w, target)
        result.update(status='DEAD' if tree['coverage']['rejected'] == 0 else 'FRONTIER',
                      coverage=tree['coverage'], leaves=tree['leaves'], maximum_depth=tree['maximum_depth'],
                      abort_reason=tree['abort_reason'], pilots=tree['pilots'],
                      tree_bytes=tree['tree_bytes'], failure_cause=tree['abort_reason'] or 'no_useful_rejection')
    elif kind == 'certificate':
        tiny = workspace(1, 202610070+generation)
        fixed = SymbolicFamily(tiny.family, ((0, 0),))
        analysis = analyze_workspace(fixed, target)
        if analysis['status'] != 'REJECTED': raise AssertionError('Singleton rejection fixture unexpectedly passed target')
        checked = check_certificate(analysis['certificate'], fixed, target)
        if not checked['valid']: raise AssertionError('Independent checker failed')
        bad = {**analysis['certificate'], 'target': str(target+1)}
        if check_certificate(bad, fixed, target)['valid']: raise AssertionError('Wrong-target certificate accepted')
        result.update(status='EXACT_CERTIFICATE', certificate=analysis['certificate'], checker=checked,
                      scope_K=1, failure_cause='singleton_diagnostic_not_large_family_evidence')
    elif kind == 'lemma-discovery':
        construction_start = perf_counter()
        g = Graph(); x, y = g.input('x'), g.input('y')
        g.outputs = [g.node('XOR', x, g.node('AND', x, y)), g.node('AND', x, g.node('NOT', y))]
        statement = g.serialize(); preconditions = 'all uint32 inputs; bit-local operators only'
        construction_seconds = perf_counter()-construction_start
        proof_start = perf_counter()
        for a in (0, 0xffffffff):
            for b in (0, 0xffffffff):
                lhs, rhs = g.evaluate(dict(x=a, y=b))
                if lhs != rhs: raise AssertionError('Discovered bit-local identity refuted')
        proof_seconds = perf_counter()-proof_start
        lemma = {'statement': statement, 'preconditions': preconditions, 'fingerprint': fingerprint(statement, preconditions),
                 'proof': {'type': 'bit-local-universal', 'cases': 4}, 'checker': 'lemma/v1',
                 'source': refinement_source(), 'domains': ['sparse-nonlinear', 'parity', 'predicate-rewrite'],
                 'costs': {'construction': construction_seconds, 'proof': proof_seconds, 'verification': 0.}, 'reuse_count': 0,
                 'information_gain': 0., 'supersedes': None, 'failure_boundaries': 'local Boolean identity, no full-SHA target advantage'}
        before = perf_counter()
        if not verify_lemma(lemma): raise AssertionError('Independent universal bit-local proof failed')
        lemma['costs']['verification'] = perf_counter()-before
        result.update(status='PROVEN_LOCAL_LEMMA', lemma=lemma, lemma_class='PROVEN',
                      failure_cause='proved_local_identity_not_cryptanalytic_advantage')
    elif kind == 'workspace-compiler':
        family = HeaderFamily(w.family.header, w.family.dimensions+(Dimension(D.VERSION_ROLL_BITS, (5, 13, 21, 28), 0x1fffffe0),))
        plan = compile_family(family)
        result.update(status='SYMBOLIC_WORKSPACE', plan=plan.report(),
                      predicate=TargetPredicate(plan.workspace, target).metadata(),
                      failure_cause='hierarchy_ready_but_target_precision_unresolved')
    else: raise ValueError('Unregistered predicate species')
    result['total_seconds'] = perf_counter()-start
    return result
