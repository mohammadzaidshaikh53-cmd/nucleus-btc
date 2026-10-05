import copy
import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nucleus_btc.bitcoin.block_header import GENESIS
from nucleus_btc.family_ir import HeaderFamily, Dimension, DimensionKind as D
from nucleus_btc.family_ir.symbolic import SymbolicFamily
from nucleus_btc.family_ir.domains import analyze
from nucleus_btc.family_ir.observables import lineage, backward_demand
from nucleus_btc.family_ir.workspace_compiler import compile_family, compile_channel
from nucleus_btc.family_ir.predicate_experiments import worker_experiment, workspace
from nucleus_btc.gpu.backend import HashlibBackend
from nucleus_btc.ir.graph import Graph
from nucleus_btc.ir.nodes import MASK
from nucleus_btc.ir.target_predicate import TargetPredicate
from nucleus_btc.target_engine import analyze_workspace, RefinementEngine, fallback, refinement_source
from nucleus_btc.verify.coverage import check_coverage
from nucleus_btc.verify.lemmas import fingerprint, verify_lemma
from nucleus_btc.nucleus.memory import KnowledgeStore
from nucleus_btc.nucleus.selector import ExperimentSelector, VNEXT, PHASE_II
from nucleus_btc.nucleus.supervisor import Supervisor, source_fingerprint


class PredicateEngineTests(unittest.TestCase):
    def test_lineage_opaque_carries_are_sound_and_retain_complement_identity(self):
        rng = random.Random(71025)
        for op in ('ADD32', 'XOR', 'AND', 'OR', 'MUX', 'ROTR', 'SHR', 'SHL', 'NOT'):
            g = Graph(); x, y, z = [g.input(n) for n in ('x', 'y', 'z')]
            # Mask to four unknown bits; exhaustive operands exercise carries,
            # nonlinear operations and widening without interpreting atoms as 0.
            args = [g.node('AND', a, g.const(15)) for a in (x, y, z)]
            used = args[:1] if op in ('ROTR', 'SHR', 'SHL', 'NOT') else args if op in ('ADD32', 'MUX') else args[:2]
            g.outputs = [g.node(op, *used, value=3 if op in ('ROTR', 'SHR', 'SHL') else None)]
            for limit in (1, 32):
                report = lineage(g, limit)
                mask = report['output_known'][0]
                for a in range(16):
                    for b in range(16):
                        for c in range(16):
                            self.assertTrue(mask.contains(g.evaluate(dict(x=a, y=b, z=c))[0]), op)
        g = Graph(); x = g.input('x'); g.outputs = [g.node('ADD32', x, g.node('NOT', x))]
        self.assertEqual(lineage(g)['output_known'][0].known, MASK)
        self.assertEqual(lineage(g)['output_known'][0].value, MASK)

    def test_inverse_target_demand_stops_at_joint_unknowns_without_pruning(self):
        w = workspace(8); p = TargetPredicate(w, 1 << 192)
        abstract = analyze(p)
        self.assertTrue(all(r['known_state_bits'] == 256 for r in abstract['round_precision'] if r['compression'] == 'header/first/0'))
        result = backward_demand(p, abstract)
        self.assertFalse(result['pruning_authorized'])
        self.assertGreater(result['conditional_known_bits'], 0)
        self.assertTrue(result['losses'])
        self.assertTrue(result['steps'])
        self.assertEqual(result['losses'][0]['operation'], 'ADD32')
        self.assertGreaterEqual(result['losses'][0]['unknown_operands'], 2)
        inputs = w.inputs(13)
        raw_view = Graph.deserialize(p.graph.serialize()); raw_view.outputs = list(p.digest_state)
        self.assertEqual(raw_view.evaluate(inputs), p.graph.evaluate(inputs))
        self.assertEqual(backward_demand(TargetPredicate(w, (1 << 256)-1), {})['status'], 'UNKNOWN')
        # Verify the inverse add/rotate equations algebraically on fresh values.
        for step in result['steps']:
            if step['rule'] == 'inverse-add32-one-unknown':
                n = p.graph.nodes[step['output']]
                values = analyze(p)['values']
                constants = sum(values[j].known.value for j in n.args if j != step['input'])
                self.assertEqual((step['value']+constants) & MASK, 0)

    def test_huge_workspace_engine_never_constructs_and_checker_is_independent(self):
        family = HeaderFamily(GENESIS.with_nonce(0), (
            Dimension(D.NONCE32, tuple(range(32)), MASK),
            Dimension(D.VERSION_ROLL_BITS, tuple(range(5, 29)), 0x1fffffe0)))
        w = SymbolicFamily(family)
        with patch.object(HeaderFamily, 'construct', side_effect=AssertionError('enumeration')):
            result = analyze_workspace(w, 1 << 176)
            self.assertEqual(result['conceptual_K'], 1 << 56)
            self.assertEqual(result['candidate_count_materialized'], 0)
            self.assertFalse(result['K_materialized'])
            self.assertEqual(result['status'], 'UNKNOWN')
            self.assertEqual(result['predicate_root_outputs'], 1)
        tiny = workspace(1); fixed = SymbolicFamily(tiny.family, ((0, 0),))
        certificate = analyze_workspace(fixed, 1)['certificate']
        from nucleus_btc.verify.certificates import check_certificate
        with patch('nucleus_btc.target_engine.analyze_workspace', side_effect=AssertionError('discovery called')):
            self.assertTrue(check_certificate(certificate, fixed, 1)['valid'])

    def test_coverage_rejects_gaps_overlap_wrong_scopes_and_certificates(self):
        w = workspace(3); children = w.split((1,))
        def node(child): return dict(scope=child.fingerprint, fixed=child.fixed, status='UNKNOWN', children=[])
        tree = dict(workspace=w.fingerprint, target='1', nodes={'root': {**node(w), 'children': ['a','b'], 'split_variable': 1},
                        'a': node(children[0]), 'b': node(children[1])})
        self.assertEqual(check_coverage(tree, w, 1)['covered'], 8)
        for tamper in ('gap', 'overlap', 'wrong-target', 'certificate', 'orphan'):
            bad = copy.deepcopy(tree)
            if tamper == 'gap': del bad['nodes']['b']
            elif tamper == 'overlap': bad['nodes']['b'] = node(children[0])
            elif tamper == 'wrong-target': bad['target'] = '2'
            elif tamper == 'certificate': bad['nodes']['a'].update(status='REJECTED', certificate={})
            else: bad['nodes']['orphan'] = node(w)
            with self.assertRaises((ValueError, KeyError)): check_coverage(bad, w, 1)

    def test_refinement_resume_source_invalidation_and_bounded_memory(self):
        w = workspace(16)
        with tempfile.TemporaryDirectory() as d:
            checkpoint = Path(d)/'tree.json'
            engine = RefinementEngine(max_leaves=2, max_depth=1, seconds=2, champion_hps=1e9, max_tree_bytes=4096)
            first = engine.run(w, 1 << 192, checkpoint)
            self.assertEqual(first['coverage']['retained'], w.count)
            self.assertLessEqual(first['tree_bytes'], 4096)
            self.assertEqual(first['leaves'], 1)
            resumed = engine.run(w, 1 << 192, checkpoint)
            self.assertFalse(resumed['checkpoint_invalidated'])
            self.assertEqual(resumed['coverage'], first['coverage'])
            stale = json.loads(checkpoint.read_text()); stale['source'] = 'stale'
            checkpoint.write_text(json.dumps(stale))
            self.assertTrue(engine.run(w, 1 << 192, checkpoint)['checkpoint_invalidated'])
            # Interrupted durable intent is retried and retained after its cap.
            stale = json.loads(checkpoint.read_text()); stale['nodes']['root']['status'] = 'PENDING'
            stale['nodes']['root']['attempts'] = 3; checkpoint.write_text(json.dumps(stale))
            self.assertEqual(engine.run(w, 1 << 192, checkpoint)['abort_reason'], 'proof_time_or_retry_budget')

    def test_fallback_retries_same_batch_and_keeps_large_work_scheduled(self):
        w = workspace(6); target = (1 << 255)
        class FailedGPU:
            name = 'opencl'
            def hash_headers(self, headers): raise RuntimeError('injected GPU failure')
        exact = fallback(w, target, HashlibBackend(), batch_size=7)
        recovered = fallback(w, target, FailedGPU(), batch_size=7)
        self.assertEqual(exact['solutions'], recovered['solutions'])
        self.assertEqual(recovered['executed'], w.count)
        self.assertEqual(recovered['fallback_cpu_candidates'], w.count)
        scheduled = fallback(workspace(32), target, FailedGPU())
        self.assertEqual(scheduled['retained'], 1 << 32)
        self.assertEqual(scheduled['executed'], 0)
        class OverflowGPU(HashlibBackend):
            name = 'opencl'
            def scan(self, raw, start, count, target, capacity=4096):
                from nucleus_btc.gpu.backend import ResultOverflow
                if count > 8: raise ResultOverflow('injected small buffer')
                return super().scan(raw, start, count, target, capacity)
        overflow = fallback(w, target, OverflowGPU())
        self.assertEqual(exact['solutions'], overflow['solutions'])
        self.assertEqual(overflow['executed'], w.count)

    def test_universal_finite_lemma_scope_source_reuse_and_bounds(self):
        g = Graph(); x = g.input('x'); g.outputs = [g.node('XOR', x, x), g.const(0)]
        def record(pre, kind, cases):
            statement = g.serialize()
            return dict(fingerprint=fingerprint(statement, pre), statement=statement, preconditions=pre,
                        proof=dict(type=kind, cases=cases), checker='lemma/v1', source='source',
                        domains=['parity'], costs=dict(construction=0., proof=0., verification=0.),
                        reuse_count=0, information_gain=0., supersedes=None, failure_boundaries='explicit scope')
        universal = record('all uint32 inputs; bit-local operators only', 'bit-local-universal', 2)
        self.assertTrue(verify_lemma(universal))
        with tempfile.TemporaryDirectory() as d, KnowledgeStore(Path(d)/'store.sqlite', max_records=6) as store:
            store.put_lemma('PROVEN', universal)
            self.assertTrue(store.reuse_lemma(universal['fingerprint'], {}, 'source'))
            self.assertFalse(store.reuse_lemma(universal['fingerprint'], {}, 'stale'))
            traced = {**universal, 'proof': {'type': 'random-traces', 'cases': 1000}}
            with self.assertRaises(ValueError): store.put_lemma('PROVEN', traced)
            bad = {**universal, 'fingerprint': 'wrong'}
            with self.assertRaises(ValueError): store.put_lemma('FRONTIER', bad)
            for i in range(8):
                dead = {**universal, 'statement': 'dead-'+str(i), 'preconditions': {}}
                dead['fingerprint'] = fingerprint(dead['statement'], dead['preconditions'])
                store.put_lemma('DEAD', dead)
            self.assertLessEqual(len(store.lemmas()), 3)
        g = Graph(); x = g.input('x'); g.outputs = [x, g.node('AND', x, g.const(1))]
        scoped = record({'x': [0, 1]}, 'finite-domain', 2)
        self.assertTrue(verify_lemma(scoped))
        from nucleus_btc.verify.lemmas import applicable
        self.assertTrue(applicable(scoped, {'x': 1}, 'source'))
        self.assertFalse(applicable(scoped, {'x': 2}, 'source'))

    def test_selector_exhaustion_profiles_and_offline_promotion_guard(self):
        selector = ExperimentSelector({k: {'exhausted': True} for k in PHASE_II}, 'predicate-vnext')
        self.assertIn(selector.select(0), VNEXT)
        for kind in VNEXT: selector.observe(kind, dict(status='DEAD', soundness_verified=True, branch_exhausted=True), .01)
        self.assertEqual(selector.select(0), 'frontier-complete')
        with tempfile.TemporaryDirectory() as d:
            def runner(experiment): return dict(status='promotion_qualified', config={}, compared_against={}, metrics={'ci95_low': 2.})
            result = Supervisor(d, runner=runner, profile='predicate-vnext').run(steps=1)
            self.assertFalse(result['production_champion_modified'])
            self.assertEqual(result['history'][0]['status'], 'failed')
            with KnowledgeStore(Path(d)/'state.sqlite') as store:
                state = store.get_state('supervisor')
                state['pending'] = dict(kind='family', id='stale', attempts=0, source_sha256=source_fingerprint(), profile='phase-ii')
                store.set_state('supervisor', state)
            seen = []
            result = Supervisor(d, runner=lambda e: seen.append(e) or {'status': 'DEAD'}, profile='predicate-vnext').run(steps=1)
            self.assertIn(seen[0]['kind'], VNEXT)

    def test_workspace_compiler_respects_real_sv2_flags_and_bounds(self):
        from types import SimpleNamespace as S
        job = S(rolling=False)
        channel = S(work=lambda: (GENESIS, None), jobs={1: job}, active=1, size=1)
        client = S(channel=channel, flags=1, extended=False)
        plan = compile_channel(client, nonce_bits=(0, 1), version_bits=())
        self.assertEqual(plan.workspace.count, 4)
        self.assertIn('actual negotiated', plan.permissions)
        with self.assertRaises(ValueError): compile_channel(client, version_bits=(5,))
        with self.assertRaises(ValueError): compile_channel(client, extranonce_bits=(0,))
        with self.assertRaises(ValueError): compile_channel(client, time_bits=(0,))
        family = HeaderFamily(GENESIS, (Dimension(D.MERKLE_TAIL, (0,), MASK),))
        with self.assertRaises(ValueError): compile_family(family)

    def test_isolated_species_results_fit_store_and_prove_local_lemma(self):
        for kind in VNEXT:
            result = worker_experiment(kind, 0)
            self.assertLess(len(json.dumps(result).encode()), 65536, kind)
            self.assertTrue(result['soundness_verified'])
            self.assertFalse(result['production_promotion_allowed'])
            if result.get('lemma'): self.assertTrue(verify_lemma(result['lemma']))

    def test_learned_universal_rule_consumption_and_small_lost_solution_audit(self):
        from nucleus_btc.ir.predicate_rewrite import saturate
        lemma = worker_experiment('lemma-discovery', 0)['lemma']
        g = Graph(); a, b = g.input('a'), g.input('b')
        g.outputs = [g.node('XOR', a, g.node('AND', a, b))]
        rewritten, report = saturate(g, lemmas=[lemma], lemma_source=lemma['source'])
        self.assertTrue(report['proofs'])
        for x in (0, 1, MASK, 0xabcdef12):
            for y in (0, 1, MASK, 0x98765432):
                self.assertEqual(rewritten.evaluate(dict(a=x, b=y)), g.evaluate(dict(a=x, b=y)))
        self.assertFalse(saturate(g, lemmas=[lemma], lemma_source='stale')[1]['proofs'])
        for seed in (71031, 71032, 71033):
            w = workspace(2, seed)
            digests = HashlibBackend().hash_headers([w.header(i) for i in range(w.count)])
            for target in (1, (1 << 255), int.from_bytes(digests[0], 'little'), (1 << 256)-1):
                result = analyze_workspace(w, target)
                survivors = [i for i, digest in enumerate(digests) if int.from_bytes(digest, 'little') <= target]
                if result['status'] == 'REJECTED': self.assertEqual(survivors, [])
                if survivors: self.assertNotEqual(result['status'], 'REJECTED')
