import unittest
from nucleus_btc.family_ir import Dimension,DimensionKind as D,HeaderFamily,FamilyWord
from nucleus_btc.family_ir.state import evaluate_family
from nucleus_btc.family_ir.probes import prefix_rejection,mitm_projection
from nucleus_btc.family_ir.egraph import saturate
from nucleus_btc.bitcoin.block_header import GENESIS

class PhaseIIProbeTests(unittest.TestCase):
    def test_prefix_inclusive_little_endian_and_early_cone(self):
        ds=[bytes(31)+bytes([1]),bytes(31)+bytes([2])]
        self.assertEqual(prefix_rejection(ds,int.from_bytes(ds[0],'little')), [1])
        family=HeaderFamily(GENESIS.with_nonce(0),(Dimension(D.NONCE32,(5,17,9),0xffffffff),))
        digests,proof=evaluate_family(family,prefix_target=1)
        self.assertIsNone(digests);self.assertEqual(proof['saved_compression_rounds'],24)
        for i,high in enumerate(proof['known_high_words']):
            self.assertEqual(high,int.from_bytes(family.candidate(i).digest()[-4:],'little'))
        digests,metrics=evaluate_family(family,prefix_target=(1<<256)-1)
        self.assertEqual(digests,[family.candidate(i).digest() for i in range(8)])

    def test_lossy_projection_retains_and_egraph_bounds(self):
        f=HeaderFamily(GENESIS,(Dimension(D.NONCE32,(5,),0xffffffff),))
        self.assertEqual(mitm_projection(f)['retained'],2)
        words=[FamilyWord(tuple((j+1)*i for i in range(8))) for j in range(5)]
        report=saturate(words);self.assertEqual(len(report['rows']),4)
        with self.assertRaises(MemoryError):saturate(words,node_budget=2)

    def test_local_solver_unsat_needs_independent_certificate(self):
        from nucleus_btc.family_ir.cones import carry_cone,backward_prefix_cone
        result=carry_cone()
        if result['status']=='UNKNOWN':self.skipTest('Optional external solver absent')
        self.assertEqual(result['status'],'UNSAT');self.assertEqual(result['independent_cases'],12288)
        result=backward_prefix_cone((0,1,2),1)
        self.assertEqual(result['status'],'UNSAT');self.assertTrue(result['independent_reproduction'])
        result=backward_prefix_cone((0,1),(1<<256)-1)
        self.assertEqual(result['status'],'SAT');self.assertEqual(result['pruned'],0)

    def test_cached_hierarchy_uses_only_known_reuse(self):
        from nucleus_btc.family_ir.hierarchy import hierarchy_baseline
        family=HeaderFamily(GENESIS,(Dimension(D.NONCE32,(5,17),0xffffffff),Dimension(D.VERSION_ROLL_BITS,(13,),1<<13)))
        result=hierarchy_baseline(family)
        self.assertEqual(result['unique_midstates'],2);self.assertEqual(result['unique_second_block_schedules'],4)
        self.assertFalse(result['novel_algorithmic_advantage'])
