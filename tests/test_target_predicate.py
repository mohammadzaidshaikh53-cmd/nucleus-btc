import hashlib
import random
import unittest
from unittest.mock import patch

from nucleus_btc.bitcoin.block_header import GENESIS, BlockHeader
from nucleus_btc.family_ir import HeaderFamily, Dimension, DimensionKind as D
from nucleus_btc.family_ir.symbolic import SymbolicFamily, AccidentalEnumeration
from nucleus_btc.ir.target_predicate import TargetPredicate, PredicateBudget
from nucleus_btc.oracle.sha256 import sha256d


class TargetPredicateTests(unittest.TestCase):
    def test_huge_symbolic_workspaces_never_construct_candidates(self):
        f = HeaderFamily(GENESIS, (Dimension(D.NONCE32, tuple(range(32)), 0xffffffff),
                                  Dimension(D.VERSION_ROLL_BITS, tuple(range(5, 29)), 0x1fffffe0)))
        s = SymbolicFamily(f)
        with patch.object(HeaderFamily, 'construct', side_effect=AssertionError('Accidental enumeration')):
            predicate = TargetPredicate(s, 1 << 220)
        self.assertEqual(s.count, 1 << 56)
        self.assertFalse(predicate.metadata()['cost_grows_with_K'])
        self.assertEqual(s.cost_record()['explicit_audit_or_fallback_headers'], 0)
        with self.assertRaises(AccidentalEnumeration):
            s.construct()
        with self.assertRaises(AccidentalEnumeration):
            list(s)
        with self.assertRaises(AccidentalEnumeration):
            s.audit_headers()

    def test_predicate_full_sha_endianness_inclusive_equality_and_changed_jobs(self):
        rng = random.Random(202610059)
        for raw in [GENESIS.serialize(), bytes(80), bytes([255])*80]+[rng.randbytes(80) for _ in range(4)]:
            h = BlockHeader.parse(raw)
            family = HeaderFamily(h, (Dimension(D.NONCE32, (0, 17), 0xffffffff),
                                     Dimension(D.VERSION_ROLL_BITS, (5,), 1 << 5)))
            symbolic = SymbolicFamily(family)
            digests = [sha256d(symbolic.header(i)) for i in range(symbolic.count)]
            for target in (1, 1 << 224, (1 << 255)-1, int.from_bytes(digests[3], 'little'), (1 << 256)-1):
                predicate = TargetPredicate(symbolic, target)
                for i, digest in enumerate(digests):
                    self.assertEqual(digest, hashlib.sha256(hashlib.sha256(symbolic.header(i)).digest()).digest())
                    self.assertEqual(predicate.evaluate(i), int.from_bytes(digest, 'little') <= target)

    def test_time_and_extended_extranonce_padding_and_merkle_branch(self):
        family = HeaderFamily(GENESIS, (Dimension(D.NTIME, (0, 1), 3),),
                              GENESIS.timestamp & ~3, GENESIS.timestamp | 3)
        s = SymbolicFamily(family)
        p = TargetPredicate(s, 1 << 254)
        for i in range(s.count):
            self.assertEqual(p.evaluate(i), int.from_bytes(sha256d(s.header(i)), 'little') <= p.target)
        for length in (55, 56, 63, 64):
            family = HeaderFamily(GENESIS, (Dimension(D.EXTRANONCE, (0, 9), (1 << 16)-1),),
                                  coinbase_prefix=bytes([3])*(length-2), extranonce=b'\x01\x02',
                                  merkle_branch=(bytes([17])*32,))
            s = SymbolicFamily(family)
            p = TargetPredicate(s, 1 << 255)
            for i in range(s.count):
                self.assertEqual(p.evaluate(i), int.from_bytes(sha256d(s.header(i)), 'little') <= p.target)

    def test_canonical_partitions_and_budgets(self):
        s = SymbolicFamily(HeaderFamily(GENESIS, (Dimension(D.NONCE32, (0, 5, 17, 31), 0xffffffff),)))
        children = s.split((1, 3))
        covered = [child.global_index(i) for child in children for i in range(child.count)]
        self.assertEqual(sorted(covered), list(range(s.count)))
        self.assertEqual(len(set(covered)), s.count)
        for child in children:
            p = TargetPredicate(child, 1 << 254)
            for i in range(child.count):
                self.assertEqual(p.evaluate(i), int.from_bytes(sha256d(child.header(i)), 'little') <= p.target)
        with self.assertRaises(PredicateBudget):
            TargetPredicate(s, 1, max_nodes=128)
        p = TargetPredicate(s, (1 << 256)-1)
        self.assertEqual(len(p.graph.nodes), 1)
        with self.assertRaises(ValueError):
            s.split((1, 1))
        with self.assertRaises(ValueError):
            SymbolicFamily(s.family, ((2, 0), (2, 1)))
