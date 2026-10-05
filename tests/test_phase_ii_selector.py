import unittest
from nucleus_btc.nucleus.selector import ExperimentSelector,PHASE_II
from nucleus_btc.family_ir.hypothesis import counterfactual

class PhaseIISelectorTests(unittest.TestCase):
    def test_exhausted_cheap_branch_loses_to_distinct_mechanism(self):
        selector=ExperimentSelector()
        for _ in range(8):selector.observe('carry-factor',{'status':'DEAD','failure_cause':'residual_saturation'},.01)
        self.assertGreater(selector.estimates('carry-factor')['saturation'],.99)
        self.assertNotEqual(selector.select(8),'carry-factor')
        for k in PHASE_II:
            if k!='carry-factor': selector.observe(k,{'status':'INCONCLUSIVE','failure_cause':k},60)
        self.assertNotEqual(selector.select(9),'carry-factor')
        copy=ExperimentSelector(selector.statistics)
        self.assertEqual(copy.select(9),selector.select(9))
        self.assertIn('split',counterfactual('residual_saturation').mechanism)

    def test_differential_worker_fits_durable_result_budget(self):
        import json
        from nucleus_btc.family_ir.experiments import worker_experiment
        result=worker_experiment('differential')
        self.assertLess(len(json.dumps(result,indent=2).encode()),65536)
        self.assertTrue(result['full_sha256d_audited'])
