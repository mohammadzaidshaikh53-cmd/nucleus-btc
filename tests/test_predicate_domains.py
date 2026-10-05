import copy
import random
import unittest

from nucleus_btc.ir.graph import Graph
from nucleus_btc.ir.nodes import Node, MASK
from nucleus_btc.ir.target_predicate import TargetPredicate
from nucleus_btc.ir.predicate_rewrite import saturate, rule_fingerprint, verify_rule
from nucleus_btc.family_ir import HeaderFamily, Dimension, DimensionKind as D
from nucleus_btc.family_ir.symbolic import SymbolicFamily
from nucleus_btc.family_ir.domains import (
    AbstractWord, KnownBits, Congruence, DomainBudget, analyze, constant_word,
    reduce_word, transfer, target_bounds,
)
from nucleus_btc.bitcoin.block_header import GENESIS
from nucleus_btc.verify.certificates import (
    CHECKER_VERSION, check_certificate, make_certificate, source_fingerprint,
)


class PredicateDomainTests(unittest.TestCase):
    def test_sound_abstract_transfers_carry_residues_and_nonlinear_bits(self):
        rng = random.Random(2061)
        for op in ('XOR', 'AND', 'OR', 'NOT', 'ADD32', 'ROTR', 'SHR', 'SHL', 'MUX'):
            graph = Graph(); x, y, z = [graph.input(name) for name in ('x', 'y', 'z')]
            args = (x,) if op in ('NOT', 'ROTR', 'SHR', 'SHL') else (x, y, z) if op in ('MUX', 'ADD32') else (x, y)
            graph.outputs = [graph.node(op, *args, value=7 if op in ('ROTR', 'SHR', 'SHL') else None)]
            class Predicate:
                always_true = False
                target = 1
                trace = []
            predicate = Predicate(); predicate.graph = graph
            result = analyze(predicate)
            word = result['values'][graph.outputs[0]]
            for _ in range(40):
                actual_inputs = {name: rng.getrandbits(32) for name in ('x', 'y', 'z')}
                actual = graph.evaluate(actual_inputs)[0]
                self.assertTrue(word.contains(actual), op)
                if word.carry:
                    carry = sum(actual_inputs[name] for name in ('x', 'y', 'z')) >> 32
                    self.assertLessEqual(word.carry.low, carry)
                    self.assertGreaterEqual(word.carry.high, carry)
                for bit, polynomial in enumerate(word.polynomial):
                    if polynomial is not None:
                        value = 0
                        for term in polynomial:
                            product = 1
                            for name, b in term: product &= (actual_inputs[name] >> b) & 1
                            value ^= product
                        self.assertEqual(value, (actual >> bit) & 1, (op, bit))

    def test_reduced_product_adds_precision_and_budget_widens_soundly(self):
        graph = Graph(); x = graph.input('x')
        graph.outputs = [graph.node('ADD32', x, graph.node('NOT', x))]
        class Predicate:
            always_true = False
            target = 1
            trace = []
            workspace = type('Workspace', (), {'count': 1})()
        p = Predicate(); p.graph = graph
        reduced = analyze(p); alone = analyze(p, nonlinear=False)
        self.assertEqual(reduced['values'][-1].known.known, MASK)
        self.assertLess(alone['values'][-1].known.known, MASK)
        self.assertGreater(reduced['counts']['nonlinear_to_known'], 0)
        self.assertLessEqual(reduced['counts']['iterations'], 4)
        low_budget = analyze(p, DomainBudget(terms=1, degree=1))
        self.assertTrue(low_budget['values'][-1].contains(MASK))
        self.assertEqual(analyze(p, DomainBudget(max_nodes=1))['status'], 'UNKNOWN')
        rewritten, proof = saturate(graph)
        self.assertEqual(rewritten.evaluate({'x': 123}), (MASK,))
        self.assertTrue(proof['proofs'])
        unchanged, bounded = saturate(graph, max_nodes=1)
        self.assertIs(unchanged, graph)
        self.assertEqual(bounded['status'], 'UNKNOWN')

    def test_congruence_reduction_and_odd_modulus_require_known_carry(self):
        budget = DomainBudget(); counts = {}
        word = AbstractWord(KnownBits(0, 0), Congruence(3, 5), (None,)*32, (None,)*32)
        reduce_word(word, budget, counts)
        self.assertEqual(word.known.known & 7, 7)
        self.assertEqual(word.known.value & 7, 5)
        a = AbstractWord(KnownBits(0, 1 << 31), Congruence(0, 0, ((3, 1),)), (None,)*32, (None,)*32)
        b = AbstractWord(KnownBits(0, 1 << 31), Congruence(0, 0, ((3, 2),)), (None,)*32, (None,)*32)
        summed = transfer(Node('ADD32', (0, 1)), [a, b], budget, {})
        self.assertEqual(summed.carry.high, 0)
        self.assertEqual(dict(summed.congruence.odd)[3], 0)
        self.assertTrue(summed.contains(9))
        with self.assertRaises(ValueError): Congruence(3, 8)
        with self.assertRaises(ValueError): Congruence(0, 0, ((7, 1),))

    def test_certificates_are_independently_checked_and_tampering_retains(self):
        # Fix all variables explicitly: this is a finite singleton diagnostic,
        # not a claimed large-family mining advantage.
        family = HeaderFamily(GENESIS.with_nonce(0), (Dimension(D.NONCE32, (0,), MASK),))
        workspace = SymbolicFamily(family, ((0, 0),))
        p = TargetPredicate(workspace, 1)
        analysis = analyze(p)
        self.assertEqual(analysis['status'], 'UNSAT')
        for kind in ('interval', 'parity', 'congruence'):
            certificate = make_certificate(workspace, 1, p, analysis, kind)
            checked = check_certificate(certificate, workspace, 1)
            self.assertTrue(checked['valid'], checked)
            self.assertEqual(checked['enumerated_candidates'], 0)
            for key, value in (('target', '2'), ('workspace', 'wrong'), ('byte_order', 'big'),
                               ('source', 'old'), ('lower', '0'), ('inclusive', False), ('type', 'learned-unproved')):
                tampered = {**certificate, key: value}
                self.assertFalse(check_certificate(tampered, workspace, 1)['valid'])
            other = SymbolicFamily(family, ((0, 1),))
            self.assertFalse(check_certificate(certificate, other, 1)['valid'])
        finite = {'schema': 1, 'checker': CHECKER_VERSION, 'source': source_fingerprint(),
                  'workspace': workspace.fingerprint, 'target': '1', 'byte_order': 'raw-digest-little-endian',
                  'inclusive': True, 'type': 'finite-exact', 'count': 1}
        self.assertTrue(check_certificate(finite, workspace, 1)['valid'])
        finite['target'] = str((1 << 256)-1)
        self.assertFalse(check_certificate(finite, workspace, (1 << 256)-1)['valid'])
        self.assertFalse(verify_rule('ch-xor', 'unproved'))
        self.assertTrue(verify_rule('ch-xor', rule_fingerprint('ch-xor')))
