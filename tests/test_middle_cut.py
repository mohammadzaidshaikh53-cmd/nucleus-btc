import hashlib
import itertools
import random
import struct
import unittest

from nucleus_btc.bitcoin.block_header import GENESIS
from nucleus_btc.family_ir import Dimension, DimensionKind as D, HeaderFamily
from nucleus_btc.family_ir.middle_cut import (
    KnownWord, MASK, IV, abstract_family, affine_basis, affine_contains, affine_target_cut,
    audit_prefix_unsat, boundary_query, cube_sum, free_cut_witness,
    inverse_step, pack_words, schedule, signed_add, step, trace_header,
)


class MiddleCutTests(unittest.TestCase):
    def test_exact_boundary_and_inverse_against_full_hashlib(self):
        rng = random.Random(2041)
        cuts = (0, 31, 47, 55, 59, 60)
        for _ in range(12):
            header = rng.randbytes(80)
            traces = trace_header(header, cuts)
            first = hashlib.sha256(header).digest()
            expected = hashlib.sha256(first).digest()
            for cut, value in traces.items():
                self.assertEqual(struct.pack('>8I', *value[8:]), first)
                w = schedule(value[8:]+(0x80000000,)+(0,)*6+(256,))
                state = value[:8]
                for t in range(cut+1, 64):
                    next_state = step(state, w[t], t)
                    self.assertEqual(inverse_step(next_state, w[t], t), state)
                    state = next_state
                actual = struct.pack('>8I', *((x+y)&MASK for x, y in zip(state, IV)))
                self.assertEqual(actual, expected)

    def test_cubes_overapproximate_carries_and_boolean_operations(self):
        cubes = (KnownWord(0x7ffffff0, ~15), KnownWord(0xfffffff8, ~7), KnownWord(3))
        result = cube_sum(*cubes)
        for a, b in itertools.product(range(16), range(8)):
            values = (cubes[0].value | a, cubes[1].value | b, 3)
            self.assertTrue(result.contains(sum(values)&MASK))
            self.assertTrue((cubes[0] & cubes[1]).contains(values[0]&values[1]))
            self.assertTrue((cubes[0] ^ cubes[1]).contains(values[0]^values[1]))
            self.assertTrue((~cubes[0]).contains((~values[0])&MASK))
        wrapped = cube_sum(KnownWord(MASK), KnownWord(1))
        self.assertEqual((wrapped.value, wrapped.known), (0, MASK))

    def test_nonenumerating_family_contains_real_traces(self):
        family = HeaderFamily(GENESIS, (Dimension(D.NONCE32, (0, 17, 31), MASK),
                                       Dimension(D.VERSION_ROLL_BITS, (5,), 1 << 5)))
        abstract = abstract_family(family, (31, 60))
        self.assertEqual(abstract['headers_constructed'], family.width+1)
        for i in range(family.count):
            trace = trace_header(family.candidate(i).serialize(), (31, 60))
            for cut, words in trace.items():
                for cube, actual in zip(abstract['cuts'][cut]+abstract['first'], words):
                    self.assertTrue(cube.contains(actual))
        invalid = HeaderFamily(GENESIS, (Dimension(D.MERKLE_TAIL, (0,), 1),))
        with self.assertRaises(ValueError):
            abstract_family(invalid)

    def test_free_cut_certificate_has_exact_schedule_but_is_not_a_header(self):
        first = struct.unpack('>8I', hashlib.sha256(GENESIS.serialize()).digest())
        w = schedule(first+(0x80000000,)+(0,)*6+(256,))
        for cut in (0, 31, 55, 60):
            for bound in (0, 1, 0x12345678, MASK):
                s = free_cut_witness(first, cut, bound)
                for t in range(cut+1, 64):
                    s = step(s, w[t], t)
                self.assertEqual(int.from_bytes(((s[7]+IV[7])&MASK).to_bytes(4, 'big'), 'little'), bound)

    def test_joint_affine_hull_keeps_cross_word_correlations(self):
        values = [pack_words((i, i ^ 0xdeadbeef)) for i in (0, 1, 4, 5)]
        base, basis = affine_basis(values)
        self.assertEqual(len(basis), 2)
        self.assertTrue(all(affine_contains(x, base, basis) for x in values))
        self.assertFalse(affine_contains(pack_words((1, 0xdeadbeef)), base, basis))
        with self.assertRaises(ValueError):
            affine_basis([])

    def test_signed_carry_universal_uint32_addition(self):
        try:
            import z3
        except ImportError:
            self.skipTest('Optional solver absent')
        for count in (2, 5):
            solver = z3.Solver()
            solver.set(timeout=3000)
            words = [z3.BitVec('x_'+str(i), 32) for i in range(count)]
            result = signed_add(solver, words, [MASK-i for i in range(count)], 'sum')
            solver.add(result != sum(words))
            self.assertEqual(solver.check(), z3.unsat)

    def test_algebraic_target_membership_and_independent_separator(self):
        # Full e projection must be feasible even though most hull vectors need
        # not correspond to an actual family member.
        vectors = [0]+[1 << (128+i) for i in range(32)]
        answer = affine_target_cut(vectors, 1)
        self.assertEqual(answer['status'], 'SAT')
        self.assertEqual(answer['e_projection_rank'], 32)
        self.assertFalse(answer['is_verified_full_target_solution'])
        answer = affine_target_cut([0, 1 << 128], 1)
        self.assertEqual(answer['status'], 'UNSAT')
        self.assertTrue(answer['separator_independently_verified'])
        mask = answer['separator_mask']
        self.assertNotEqual((((-IV[7]) & MASK) & mask).bit_count() & 1, answer['family_parity'])
        for nonce in range(12):
            raw = GENESIS.with_nonce(nonce).serialize()
            vector = pack_words(trace_header(raw, (60,))[60])
            answer = affine_target_cut([vector], 1)
            digest = hashlib.sha256(hashlib.sha256(raw).digest()).digest()
            self.assertEqual(answer['status'], 'SAT' if int.from_bytes(digest[-4:], 'little') == 0 else 'UNSAT')
        answer = affine_target_cut(vectors, 1 << 224)
        self.assertEqual(answer['status'], 'UNKNOWN')
        self.assertEqual(answer['retained'], len(vectors))

    def test_queries_never_prune_and_unsat_requires_independent_audit(self):
        try:
            import z3
        except ImportError:
            self.skipTest('Optional solver absent')
        raw = GENESIS.with_nonce(0).serialize()
        trace = trace_header(raw, (59, 60))
        for encoding in ('bitvector', 'signed-carry'):
            for cut in (59, 60):
                vectors = [pack_words(trace[cut])]
                rejected = boundary_query(vectors, cut, 1, encoding=encoding, timeout_ms=3000)
                self.assertEqual(rejected['status'], 'UNSAT')
                self.assertFalse(rejected['pruning_authorized'])
                self.assertEqual(rejected['retained'], 1)
                self.assertEqual(audit_prefix_unsat([raw], 1)['independent_cases'], 1)
                accepted = boundary_query(vectors, cut, (1 << 256)-1, encoding=encoding, timeout_ms=3000)
                self.assertEqual(accepted['status'], 'SAT')
                self.assertEqual(accepted['pruned'], 0)
                self.assertTrue(accepted['witness']['actual_family_boundary'])
        with self.assertRaises(AssertionError):
            audit_prefix_unsat([raw], (1 << 256)-1)
        unknown = boundary_query([0, 1, 2, 4], 60, 1, rank_budget=1)
        self.assertEqual(unknown['status'], 'UNKNOWN')
        self.assertEqual(unknown['retained'], 4)


if __name__ == '__main__':
    unittest.main()
