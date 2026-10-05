import random
import unittest
from dataclasses import replace
from nucleus_btc.bitcoin.block_header import GENESIS
from nucleus_btc.family_ir import Dimension, DimensionKind as D, HeaderFamily, FamilyWord
from nucleus_btc.family_ir.factor import blocked_sum
from nucleus_btc.family_ir.verify import verify_family

class FamilyIRTests(unittest.TestCase):
    def test_components_and_blocked_carry_exact(self):
        rng=random.Random(119)
        words=[FamilyWord(tuple(rng.getrandbits(32) for _ in range(32))) for _ in range(5)]
        for w in words:
            self.assertEqual([w.materialize(i) for i in range(32)],list(w.values))
        for block in (4,8,16):
            result, stats=blocked_sum(words,block)
            self.assertEqual(result.values,tuple(sum(v)&0xffffffff for v in zip(*(w.values for w in words))))
            self.assertLessEqual(stats['Ucarry'],32)

    def test_permitted_nested_family_and_full_sha(self):
        h=replace(GENESIS,nonce=0,timestamp=1231006504)
        dims=(Dimension(D.NONCE32,(5,17),0xffffffff),Dimension(D.VERSION_ROLL_BITS,(13,),1<<13),Dimension(D.NTIME,(0,),1))
        family=HeaderFamily(h,dims,h.timestamp,h.timestamp+1)
        self.assertEqual(len({family.candidate(i).serialize() for i in range(16)}),16)
        for width in (4,8,16): self.assertTrue(verify_family(family,block_bits=width)['passed'])

    def test_template_merkle_and_invalid_workspace(self):
        dim=Dimension(D.EXTRANONCE,(0,9),0x201,extended_allowed=True)
        f=HeaderFamily(GENESIS,(dim,),coinbase_prefix=b'fixture',extranonce=bytes(2),merkle_branch=(bytes(32),))
        self.assertEqual(len({f.candidate(i).merkle_root for i in range(4)}),4)
        self.assertTrue(verify_family(f)['passed'])
        with self.assertRaises(ValueError): Dimension(D.VERSION_ROLL_BITS,(12,),1<<13)
        with self.assertRaises(ValueError): Dimension(D.MERKLE_TAIL,(0,),1,standard_allowed=True)
        with self.assertRaises(ValueError): HeaderFamily(GENESIS,(Dimension(D.NTIME,(5,),32),))
        with self.assertRaises(ValueError): HeaderFamily(GENESIS,(dim,dim),extranonce=bytes(2))

    def test_dependency_degree_and_rank_are_exact(self):
        from nucleus_btc.family_ir.profile import word_profile,binary_rank
        affine=FamilyWord((0,3,5,6));nonlinear=FamilyWord((0,0,0,1))
        self.assertTrue(word_profile(affine)['affine'])
        self.assertEqual(word_profile(nonlinear)['bit_anf_degree'][0],2)
        self.assertEqual(nonlinear.dependencies[0],(0,1))
        self.assertEqual(binary_rank([0,1,2,3]),2)

    def test_strided_splits_and_fallback_cover_every_candidate(self):
        from nucleus_btc.family_ir.split import StridedSubspace,SplitPolicyV2
        from nucleus_btc.gpu.backend import get_backend
        space=StridedSubspace(5);parts=space.split(2);parts=tuple(child for part in parts for child in part.split(0))
        indices=[part.map(i) for part in parts for i in range(part.count)]
        self.assertEqual(sorted(indices),list(range(32)))
        family=HeaderFamily(GENESIS,(Dimension(D.NONCE32,(5,17,23,9,11),0xffffffff),))
        with get_backend('hashlib') as backend:
            for part in parts: self.assertEqual(part.fallback(family,backend,(1<<256)-1)['examined'],part.count)
        policy=SplitPolicyV2();self.assertEqual(policy.choose(12,'DAG',[.1,2],[0,1],2,0,1)['variable'],1)

    def test_program_mutation_crossover_transitions_and_late_split(self):
        from nucleus_btc.family_ir.program import RepresentationProgram,Stage,execute_program
        family=HeaderFamily(GENESIS,(Dimension(D.NONCE32,(5,17),0xffffffff),))
        program=RepresentationProgram((Stage(0,'affine-family'),Stage(7,'carry-residual',1),Stage(16,'DAG'),Stage(32,'bitplane'),Stage(72,'native')))
        digest,metrics=execute_program(family,program)
        self.assertEqual(digest,[family.candidate(i).digest() for i in range(4)])
        self.assertEqual(metrics['split_events'][0]['covered'],4)
        for seed in range(10):
            mutated=program.mutate(seed,2);child=mutated.crossover(program,19)
            self.assertEqual(execute_program(family,child)[0],digest)
