"""Offline exact target-predicate lab integrated with existing fallback/IR.

No production miner imports this module. Rejection is conditional on the
independent certificate checker. Source-qualified atomic checkpoints preserve
all unfinished leaves. Pilot refinements never silently replace parent work.
"""
import json
from pathlib import Path
from time import perf_counter

from .family_ir.symbolic import SymbolicFamily
from .family_ir.domains import DomainBudget, analyze
from .family_ir.observables import lineage, backward_demand
from .ir.target_predicate import TargetPredicate, PredicateBudget
from .ir.predicate_rewrite import saturate
from .nucleus.persistence import atomic_json
from .verify.certificates import make_certificate, check_certificate, source_fingerprint
from .verify.coverage import check_coverage
from .gpu.backend import HashlibBackend, ResultOverflow


def refinement_source():
    from hashlib import sha256
    root = Path(__file__).resolve().parent
    digest = sha256(source_fingerprint().encode())
    for path in (Path(__file__), root/'family_ir/domains.py', root/'family_ir/observables.py', root/'ir/predicate_rewrite.py',
                 root/'verify/coverage.py', root/'verify/lemmas.py', root/'family_ir/workspace_compiler.py'):
        digest.update(path.read_bytes())
    return digest.hexdigest()


def analyze_workspace(workspace, target, observable='product', budget=None, lemmas=(), lemma_source=None):
    started = perf_counter()
    report = {'conceptual_K': workspace.count, 'K_materialized': False, 'observable': observable,
              'construction_seconds': 0., 'rewrite_seconds': 0., 'proof_seconds': 0.,
              'certificate_check_seconds': 0., 'certificate': None, 'production_promotion_allowed': False}
    try:
        predicate = TargetPredicate(workspace, target)
        report.update(predicate.metadata())
        report['construction_seconds'] = predicate.compile_seconds
        rewritten, rewrites = saturate(predicate.graph, lemmas=lemmas, lemma_source=lemma_source)
        report['rewrites'] = rewrites
        report['rewrite_seconds'] = rewrites['seconds']
        # Rewrites are analyzed separately until their canonical binding can be
        # checked. The complete predicate remains the certificate authority.
        report['rewritten_nodes'] = len(rewritten.nodes)
        result = analyze(predicate, budget, nonlinear=observable != 'masks')
        report.update({k: v for k, v in result.items() if k != 'values'})
        report['proof_seconds'] = result['domain_seconds']
        if observable == 'lineage':
            extra = lineage(predicate.graph)
            report['lineage'] = {k: v for k, v in extra.items() if k not in ('values', 'output_known')}
            report['lineage']['known_output_bits'] = sum(w.known.bit_count() for w in extra['output_known'])
            report['proof_seconds'] += extra['seconds']
        elif observable == 'backward':
            extra = backward_demand(predicate, result)
            report['backward'] = extra
            report['proof_seconds'] += extra['seconds']
        elif observable not in ('product', 'masks'):
            raise ValueError('Unknown analysis observable')
        if result['status'] == 'UNSAT':
            certificate = make_certificate(workspace, target, predicate, result)
            checked = check_certificate(certificate, workspace, target)
            report['certificate_check_seconds'] = checked['check_seconds']
            report['certificate_check'] = checked
            if checked['valid']:
                report['certificate'] = certificate
                report['status'] = 'REJECTED'
            else:
                report['status'] = 'UNKNOWN'
                report['reason'] = 'discovery contradiction not reproduced by supported checker'
    except PredicateBudget as error:
        report.update(status='UNKNOWN', reason=str(error), target_information=0.)
    report['total_seconds'] = perf_counter()-started
    report['candidate_count_materialized'] = 0
    return report


class RefinementEngine:
    def __init__(self, max_leaves=4, max_depth=4, seconds=5., pilot_variables=2, champion_hps=None, observable='product', max_tree_bytes=1 << 20):
        if not 1 <= max_leaves <= 64 or not 0 <= max_depth <= 64 or not 0 < seconds <= 60 or not 1 <= pilot_variables <= 3:
            raise ValueError('Invalid refinement budget')
        if champion_hps is not None and champion_hps <= 0: raise ValueError('Invalid fresh champion speed')
        if not 4096 <= max_tree_bytes <= 1 << 22: raise ValueError('Invalid refinement memory budget')
        self.max_leaves, self.max_depth, self.seconds = max_leaves, max_depth, seconds
        self.pilot_variables, self.champion_hps, self.observable = pilot_variables, champion_hps, observable
        self.max_tree_bytes = max_tree_bytes

    def run(self, workspace, target, checkpoint=None):
        started = perf_counter(); source = refinement_source()
        checkpoint = Path(checkpoint) if checkpoint else None
        def new_node(w): return {'scope': w.fingerprint, 'fixed': w.fixed, 'status': 'PENDING', 'attempts': 0, 'children': []}
        tree = {'schema': 1, 'workspace': workspace.fingerprint, 'target': str(target), 'source': source,
                'nodes': {'root': new_node(workspace)}, 'root_fixed': workspace.fixed, 'profile': self.observable}
        invalidated = False
        if checkpoint and checkpoint.exists():
            previous = json.loads(checkpoint.read_text(encoding='utf-8'))
            if previous.get('source') == source and previous.get('workspace') == workspace.fingerprint and previous.get('target') == str(target) and previous.get('profile') == self.observable:
                check_coverage(previous, workspace, target)
                tree = previous
            else:
                # The mutable checkpoint is not historical result evidence.
                # Keep a compact invalidation receipt and start from ALL root work.
                invalidated = True
                tree['invalidated_previous'] = {'source': previous.get('source'), 'scope': previous.get('workspace')}
        def persist():
            if len(json.dumps(tree)) > self.max_tree_bytes:
                for node in tree['nodes'].values():
                    node.pop('analysis', None)
                tree['analysis_widened_for_memory'] = True
                if len(json.dumps(tree)) > self.max_tree_bytes:
                    raise MemoryError('Structural proof tree exceeds budget; root remains retained')
            if checkpoint: atomic_json(checkpoint, tree)
        persist(); pilots = []; abort_reason = None
        while True:
            pending = [(ident, n) for ident, n in tree['nodes'].items() if n['status'] == 'PENDING' and not n['children']]
            if not pending: break
            ident, node = pending[0]
            w = SymbolicFamily(workspace.family, tuple(map(tuple, node['fixed'])))
            if perf_counter()-started >= self.seconds or node['attempts'] >= 3:
                node['status'] = 'FALLBACK'; abort_reason = 'proof_time_or_retry_budget'; persist(); continue
            node['attempts'] += 1; persist()  # Durable per-leaf execution intent.
            result = node.get('analysis') or analyze_workspace(w, target, self.observable)
            node['analysis'] = result
            node['status'] = 'REJECTED' if result['status'] == 'REJECTED' else 'ALL_PASS' if result['status'] == 'ALL_PASS' else 'UNKNOWN'
            if result['certificate']: node['certificate'] = result['certificate']
            persist()
            if node['status'] != 'UNKNOWN' or not w.free: continue
            depth = len(w.fixed)-len(workspace.fixed)
            leaf_count = sum(not n['children'] for n in tree['nodes'].values())
            elapsed = perf_counter()-started
            conventional = w.count/self.champion_hps if self.champion_hps else None
            if depth >= self.max_depth or leaf_count >= self.max_leaves or elapsed >= self.seconds or conventional is not None and elapsed >= conventional*.1:
                abort_reason = 'leaf_depth_or_economic_budget'; node['status'] = 'FALLBACK'; persist(); continue
            # Ambiguity-directed pilots: prioritize inner dimensions (no new
            # first-block midstate) and bits in ambiguous input words. Every
            # trial has complete coverage; select maximal actual information
            # gain per measured cost, not a lucky output or nonce.
            candidates = sorted(w.free, key=lambda v: (w.family.variables[v][0] != 'nonce', w.family.variables[v][1]))[:self.pilot_variables]
            trials = []
            for variable in candidates:
                if perf_counter()-started >= self.seconds: break
                children = w.split((variable,))
                before = perf_counter(); analyses = [analyze_workspace(c, target, self.observable) for c in children]
                cost = perf_counter()-before
                info = sum(a.get('target_information', 0.) for a in analyses)/2-result.get('target_information', 0.)
                trials.append((info/max(cost, 1e-9), variable, children, analyses))
                pilots.append({'parent': ident, 'variable': variable, 'information_gain': info, 'seconds': cost})
            if not trials or max(t[0] for t in trials) <= 0:
                node['status'] = 'FALLBACK'; abort_reason = 'no_target_information_gain'; persist(); continue
            _, variable, children, analyses = max(trials, key=lambda t: t[0])
            node['split_variable'] = variable
            node['children'] = [ident+'/0', ident+'/1']
            for child_id, child, analysis in zip(node['children'], children, analyses):
                child_node = new_node(child)
                child_node['analysis'] = analysis
                child_node['status'] = 'REJECTED' if analysis['status'] == 'REJECTED' else 'ALL_PASS' if analysis['status'] == 'ALL_PASS' else 'PENDING'
                if analysis['certificate']: child_node['certificate'] = analysis['certificate']
                tree['nodes'][child_id] = child_node
            persist()
        # Pending/unknown leaves remain part of exact fallback coverage.
        before = perf_counter(); coverage = check_coverage(tree, workspace, target)
        coverage_seconds = perf_counter()-before
        return {'tree': tree, 'coverage': coverage, 'leaves': coverage['leaves'],
                'maximum_depth': max(len(n['fixed'])-len(workspace.fixed) for n in tree['nodes'].values()),
                'pilots': pilots, 'coverage_proof_seconds': coverage_seconds,
                'total_seconds': perf_counter()-started, 'checkpoint_invalidated': invalidated,
                'abort_reason': abort_reason, 'K_materialized': False,
                'tree_bytes': len(json.dumps(tree)), 'memory_budget_bytes': self.max_tree_bytes,
                'production_promotion_allowed': False}


def fallback(workspace, target, backend, batch_size=256, max_candidates=1 << 20):
    """Bounded streaming exact fallback; large workspace can remain scheduled.

    Storage is O(batch_size+solutions), execution is O(K). Both are explicit.
    Failed GPU batches are retried on the same headers with independent hashlib.
    Every found solution receives a full immutable-oracle validation.
    """
    if not 1 <= batch_size <= 4096 or not 1 <= max_candidates <= 1 << 24:
        raise ValueError('Invalid fallback budget')
    if workspace.count > max_candidates:
        return {'status': 'SCHEDULED', 'retained': workspace.count, 'scope': workspace.fingerprint,
                'executed': 0, 'execution_complexity': 'linear in K when consumed',
                'K_materialized': False, 'fallback_gpu_candidates': 0, 'fallback_cpu_candidates': 0}
    masks = workspace.masks()
    nonce_mask = masks.get('nonce', 0)
    if hasattr(backend, 'scan') and nonce_mask == workspace.count-1 and not any(v for k, v in masks.items() if k != 'nonce'):
        return _scan_fallback(workspace, target, backend)
    from .oracle.sha256 import sha256d
    started = perf_counter(); solutions = []; gpu = cpu = 0; audit_seconds = 0.
    for start in range(0, workspace.count, batch_size):
        count = min(batch_size, workspace.count-start)
        headers = [workspace.header(i) for i in range(start, start+count)]
        try:
            digests = backend.hash_headers(headers)
            if len(digests) != count: raise ValueError('Incomplete fallback digest batch')
            if backend.name in ('opencl', 'hip'): gpu += count
            else: cpu += count
        except (OSError, RuntimeError, ValueError):
            digests = HashlibBackend().hash_headers(headers); cpu += count
        for offset, (raw, digest) in enumerate(zip(headers, digests)):
            if int.from_bytes(digest, 'little') <= target:
                before = perf_counter()
                if sha256d(raw) != digest: raise AssertionError('Fallback solution failed immutable oracle')
                audit_seconds += perf_counter()-before
                solutions.append(start+offset)
    return {'status': 'EXACT_FALLBACK', 'retained': workspace.count, 'executed': workspace.count,
            'solutions': solutions, 'seconds': perf_counter()-started, 'independent_audit_seconds': audit_seconds,
            'fallback_gpu_candidates': gpu, 'fallback_cpu_candidates': cpu,
            'K_materialized': False, 'peak_batch_headers': min(batch_size, workspace.count),
            'execution_complexity': 'linear in K; bounded batch storage; solution storage proportional to matches'}


def _scan_fallback(workspace, target, backend):
    """Use the unchanged champion scan on exactly contiguous nonce leaves.

    Overflow partitions the same range; any backend failure retries that range
    with hashlib. Arbitrary symbolic leaves use the streaming path above.
    """
    from .oracle.sha256 import sha256d
    started = perf_counter(); raw = workspace.header(0)
    base_nonce = int.from_bytes(raw[76:], 'little')
    low = base_nonce & ~(workspace.count-1)
    stack = [(low, workspace.count)]
    gpu = cpu = 0; audit_seconds = 0.; solutions = []
    while stack:
        start, count = stack.pop()
        try:
            result = backend.scan(raw, start, count, target, capacity=min(count, 4096))
            if result.examined != count or len(set(result.nonces)) != len(result.nonces) or any(not start <= n < start+count for n in result.nonces):
                raise ValueError('Incomplete or invalid scan result')
            if backend.name in ('opencl', 'hip'): gpu += count
            else: cpu += count
        except ResultOverflow:
            if count == 1: raise AssertionError('Single solution overflow despite capacity one')
            half = count//2; stack.extend(((start, half), (start+half, count-half)))
            continue
        except (OSError, RuntimeError, ValueError):
            result = HashlibBackend().scan(raw, start, count, target, capacity=count)
            cpu += count
        for nonce in result.nonces:
            assignment = sum(((nonce ^ base_nonce) >> workspace.family.variables[v][1] & 1) << i for i, v in enumerate(workspace.free))
            before = perf_counter()
            if int.from_bytes(sha256d(workspace.header(assignment)), 'little') > target:
                raise AssertionError('Fallback solution failed immutable oracle target')
            audit_seconds += perf_counter()-before
            solutions.append(assignment)
    return {'status': 'EXACT_FALLBACK', 'retained': workspace.count, 'executed': workspace.count,
            'solutions': sorted(solutions), 'seconds': perf_counter()-started, 'independent_audit_seconds': audit_seconds,
            'fallback_gpu_candidates': gpu, 'fallback_cpu_candidates': cpu, 'K_materialized': False,
            'peak_batch_headers': 1, 'scan_path': 'unchanged contiguous champion with overflow splitting and same-range CPU recovery',
            'execution_complexity': 'linear in K; solution storage proportional to matches'}
