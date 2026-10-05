import importlib.util
import random
import unittest
from nucleus_btc.representations.plane_sha import PlaneCircuit,plane_family
from nucleus_btc.representations.bitslice import encode_words,decode_words
from nucleus_btc.representations.symbolic import symbolic_experiment
from nucleus_btc.bitcoin.block_header import GENESIS
from nucleus_btc.bitcoin.target import UINT256_MAX
from nucleus_btc.gpu.backend import HashlibBackend

class PortfolioTests(unittest.TestCase):
    def test_all_carry_forms_modular_uint32(self):
        rng=random.Random(171);words=[[0,0xffffffff,0x7fffffff,0x80000000]+[rng.getrandbits(32) for _ in range(60)] for _ in range(5)]
        planes=[encode_words(w) for w in words];expected=[sum(w[i] for w in words)&0xffffffff for i in range(64)]
        for kind in ("ripple","prefix","carry-select","carry-save"):
            circuit=PlaneCircuit(64,kind);actual=decode_words(circuit.sum(*planes),64)
            self.assertEqual(actual,expected,kind);self.assertGreater(circuit.carry_graph_operations,0)
    def test_full_sha_carry_forms_and_inclusive_target(self):
        target=UINT256_MAX//8;header=GENESIS.serialize();expected=HashlibBackend().scan(header,0,64,target,64).nonces
        for kind in ("ripple","prefix","carry-select","carry-save"):
            result=plane_family(header,0,6,target,carry=kind)
            self.assertEqual(result["solutions"],expected);self.assertEqual(result["completed_rounds"],128)
            self.assertTrue(result["exhaustive_audit"])
    def test_round_conversion_and_variable_order(self):
        for representation in ("hybrid-dag","hybrid-bdd"):
            result=symbolic_experiment(4,20000,representation,variable_order=[3,2,1,0],switch_round=5,target=UINT256_MAX)
            self.assertEqual(result["status"],"full_sha256d_parity_passed")
            self.assertEqual(result["transitions"][0]["round"],5);self.assertEqual(len(result["exact_solutions"]),16)
            self.assertGreater(result["transitions"][0]["conversion_seconds"],0)
    def test_smt_templates_and_unknown_never_discard(self):
        if importlib.util.find_spec("z3") is None:self.skipTest("Optional SMT dependency absent; install [research]")
        from nucleus_btc.solver.smt import prove_templates,smt_family
        self.assertTrue(prove_templates()["all_proved"])
        answer=smt_family(GENESIS.serialize(),0,2,target=1,timeout_ms=1)
        self.assertIn(answer["status"],("SAT","UNSAT","UNKNOWN"))
        if answer["status"]=="UNKNOWN":self.assertFalse(answer["family_discarded"])
        # A high target produces a CPU-validated SAT model with sufficient budget.
        answer=smt_family(GENESIS.serialize(),0,1,target=UINT256_MAX,timeout_ms=1000)
        self.assertEqual(answer["status"],"SAT");self.assertFalse(answer["family_discarded"])
        self.assertTrue(answer["independent_oracle_parity"])
    def test_fitness_hard_gate_and_all_cost_equation(self):
        from nucleus_btc.nucleus.fitness import Fitness
        with self.assertRaises(ValueError):Fitness(False,H=1e30).measurements()
        measurements=Fitness(True,rho=.9,F=.01,phi=.5,K=1000).measurements()
        self.assertAlmostEqual(measurements["S"],1/.06);self.assertIsNone(measurements["E"])
    def test_nonlinear_redundant_shortcut_refuted(self):
        from nucleus_btc.representations.carry import nonlinear_boundary_experiment
        self.assertEqual(set(nonlinear_boundary_experiment()["counterexamples"]),{"Ch","Sigma"})

if __name__=="__main__":unittest.main()
