import random
import tempfile
import unittest
from pathlib import Path
from nucleus_btc.nucleus.memory import KnowledgeStore
from nucleus_btc.benchmark import paired_confidence
from nucleus_btc.representations.bitslice import encode_words,decode_words,add_planes
from nucleus_btc.representations.carry import carry_save
from nucleus_btc.representations.bool_dag import BooleanDAG,RepresentationCollapsed
from nucleus_btc.solver.pruning import DigestIntervalProof,audit_rejections,pruning_metrics
from nucleus_btc.solver.family_search import amortized_value
from nucleus_btc.gpu.backend import HashlibBackend
from nucleus_btc.bitcoin.block_header import GENESIS
from nucleus_btc.bitcoin.target import UINT256_MAX

class ResearchTests(unittest.TestCase):
    def test_bitslice_carry(self):
        rng=random.Random(77);a=[rng.getrandbits(32) for _ in range(63)];b=[rng.getrandbits(32) for _ in a]
        self.assertEqual(decode_words(encode_words(a),len(a)),a)
        self.assertEqual(decode_words(add_planes(encode_words(a),encode_words(b)),len(a)),[(x+y)&0xFFFFFFFF for x,y in zip(a,b)])
        for x,y in zip(a,b):
            z=rng.getrandbits(32);s,c=carry_save(x,y,z);self.assertEqual((s+c)&0xFFFFFFFF,(x+y+z)&0xFFFFFFFF)
    def test_dag_sharing_and_budget(self):
        dag=BooleanDAG(max_nodes=5);a=dag.node("var","a");b=dag.node("var","b");x=dag.node("xor",a,b)
        self.assertEqual(x,dag.node("xor",b,a));self.assertEqual(dag.node("xor",a,a),0)
        for av in [False,True]:
            for bv in [False,True]:self.assertEqual(dag.evaluate(x,{"a":av,"b":bv}),av!=bv)
        with self.assertRaises(RepresentationCollapsed):dag.node("and",a,b)
    def test_no_false_negative_pruning(self):
        self.assertTrue(DigestIntervalProof(10,20,9).rejects())
        self.assertFalse(DigestIntervalProof(10,20,10).rejects())
        with self.assertRaises(AssertionError):audit_rejections([GENESIS.serialize()],UINT256_MAX,[0],HashlibBackend().hash_headers)
        self.assertAlmostEqual(pruning_metrics(900,1000,.01,1.)["speedup"],1/.11)
        self.assertFalse(amortized_value(100,.01,2)["economically_positive"])
    def test_noise_gate(self):
        noisy=paired_confidence([.7,1.4,.8,1.3,1.,1.1,.9])
        self.assertLess(noisy["ci95_low"],1.)
        steady=paired_confidence([1.2]*7);self.assertAlmostEqual(steady["ci95_low"],1.2)
    def test_bounded_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            with KnowledgeStore(Path(tmp)/"k.sqlite",max_records=9) as store:
                for kind in ["PROVEN","DEAD","FRONTIER"]:
                    for i in range(10):store.put(kind,{"kind":kind,"i":i},{},"test",i)
                self.assertEqual(len(store.records()),9)
                store.set_state("champion",{"config":{"test":True}})
                self.assertTrue(store.get_state("champion")["config"]["test"])

if __name__=="__main__":unittest.main()
