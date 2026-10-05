import unittest
from nucleus_btc.solver.adaptive import solve_family,SplitPolicy
from nucleus_btc.representations.plane_sha import plane_family
from nucleus_btc.representations.symbolic import symbolic_experiment
from nucleus_btc.gpu.backend import HashlibBackend
from nucleus_btc.bitcoin.block_header import GENESIS
from nucleus_btc.bitcoin.target import UINT256_MAX

class AdaptiveTests(unittest.TestCase):
    def test_economic_fallback_never_loses_solutions(self):
        engine=HashlibBackend();header=GENESIS.serialize();target=UINT256_MAX//4
        expected=engine.scan(header,0,128,target,128).nonces
        result=solve_family(engine,header,0,128,target,SplitPolicy(max_symbolic_bits=2,max_probes=2),capacity=8)
        self.assertEqual(result["solutions"],expected);self.assertEqual(result["examined"],128)
        self.assertTrue(result["all_construction_conversion_split_proof_fallback_costs_included"])
    def test_full_bitplane_target_and_byte_order(self):
        result=plane_family(GENESIS.serialize(),0,6,UINT256_MAX//4)
        expected=HashlibBackend().scan(GENESIS.serialize(),0,64,UINT256_MAX//4,64).nonces
        self.assertEqual(result["solutions"],expected);self.assertTrue(result["exhaustive_audit"])
        self.assertEqual(result["completed_rounds"],128)
    def test_anf_and_reversed_order_full_sha(self):
        for representation in ("anf","bdd"):
            result=symbolic_experiment(2,20000,representation,variable_order=[1,0],target=UINT256_MAX)
            self.assertEqual(result["status"],"full_sha256d_parity_passed")
            self.assertEqual(result["exact_solutions"],list(range(GENESIS.nonce&~3,(GENESIS.nonce&~3)+4)))
    def test_resource_failure_has_causal_phase(self):
        result=symbolic_experiment(4,1000,"dag")
        self.assertEqual(result["status"],"resource_budget_collapsed")
        self.assertIn("failure_phase",result)
