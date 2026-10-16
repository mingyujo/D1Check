import unittest
from tools import d1_simulation_model_v3_prediction as api
from tools import d1_simulation_model_v3 as m
from tools import d1_simulation_model_v3_inputs as inputs
from tools import d1_simulation_model_v2 as v2
from tools import d1_arrival_plan as p


class PredictionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=p.read(v2.prior.MODEL)
        fixture=p.read(m.ROOT/'tools/fixtures/simulation_model_v3_prediction_public.json')
        cls.manifest=fixture['manifest']
        cls.public=fixture['public']
        cls.candidate=dict(version=m.VERSION,thermal=m.baseline_head(cls.original,'thermal'),energy=m.baseline_head(cls.original,'energy'),original_model=dict(sha256=v2.prior.MODEL_SHA))

    def test_frozen_prior_heads_exactly_reproduce_original_costs(self):
        r=api.forecast(self.public,self.manifest['requests'],self.manifest['policy'],self.candidate,self.original)
        self.assertAlmostEqual(r['predicted_J120'],r['original_J120'],places=10)
        self.assertLess(max(abs(a-b) for a,b in zip(r['predicted_AP_c'],r['original_AP_c'])),1e-10)

    def test_future_targets_actual_schedule_or_outputs_are_rejected(self):
        for key in ('ap','power_w','actual','forecast','actual_requests','last_lane_s'):
            with self.assertRaises(ValueError):
                api.forecast(dict(self.public,**{key:[]}),self.manifest['requests'],self.manifest['policy'],self.candidate,self.original)


if __name__=='__main__':unittest.main()
