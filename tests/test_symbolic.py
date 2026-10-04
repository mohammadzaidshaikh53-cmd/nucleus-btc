import unittest
from nucleus_btc.representations.bdd import BDD
from nucleus_btc.representations.symbolic import symbolic_experiment

class SymbolicTests(unittest.TestCase):
    def test_bdd_truth_and_reduction(self):
        b=BDD(100);a=b.node("var","0");c=b.node("var","1");x=b.node("xor",a,c)
        self.assertEqual(b.node("xor",a,a),0)
        for av in [False,True]:
            for cv in [False,True]:self.assertEqual(b.evaluate(x,{"0":av,"1":cv}),av!=cv)
    def test_full_sha_bdd_small_family(self):
        result=symbolic_experiment(nonce_bits=2,max_nodes=10000,representation="bdd")
        self.assertEqual(result["status"],"full_sha256d_parity_passed")
        self.assertEqual(result["completed_rounds"],128)
        self.assertFalse(result["cryptanalytic_discovery"])
    def test_budget_collapse_is_reported(self):
        result=symbolic_experiment(nonce_bits=4,max_nodes=128)
        self.assertEqual(result["status"],"resource_budget_collapsed")
        self.assertLessEqual(result["nodes"],128)

if __name__=="__main__":unittest.main()
