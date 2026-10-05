import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from tools import d1_ap_preparation_memory as m
from tools import d1_ap_memory_analysis as analysis
from tools import d1_ap_model_completion as old


PARAMETERS={'ap_cooling_rate_per_s':.05,
            'ap_slope_at_30_c_per_s':{'resident_idle':.1,'detection_CPU':.3}}


def synthetic():
    samples=[]
    for t in range(-30,35,3):
        temperature,_=m.advance(31,.04,0,29,.05,60,1.2,t+30)
        samples.append(dict(t=float(t),ap=temperature,lo=t-.05,hi=t+.05))
    return dict(id='idle_development',inputs=dict(preload=samples,
        segments=[dict(start_s=0,end_s=35,state='idle'),dict(start_s=35,end_s=47,state='detection:CPU'),
                  dict(start_s=47,end_s=180,state='idle')],query_s=list(range(36,179,3))))


class MemoryTests(unittest.TestCase):
    def test_analytic_transition_composes_and_is_continuous(self):
        direct=m.advance(30,.02,.2,29,.05,60,1.2,12)
        a=m.advance(30,.02,.2,29,.05,60,1.2,4)
        split=m.advance(*a,.2,29,.05,60,1.2,8)
        np.testing.assert_allclose(direct,split,atol=1e-12)
        self.assertEqual(m.advance(30,.02,.2,29,.05,20,0,0),(30,.02))
        self.assertTrue(all(np.isfinite(m.advance(30,.02,.2,29,.05,20,1,10))))

    def test_initial_state_and_known_synthetic_parameters(self):
        case=synthetic();init=m.initialize(case['inputs']['preload'],.05,60)
        self.assertAlmostEqual(init['reference_c'],29,places=9)
        self.assertAlmostEqual(init['h_first_c_per_s'],.04,places=9)
        case['observed_ap_c']=m.predict(case,PARAMETERS,60,1.2)[0]
        best,_=m.fit(case,PARAMETERS,[20,40,60,80,100])
        self.assertEqual(best['tau_s'],60)
        self.assertAlmostEqual(best['gamma'],1.2,places=8)

    def test_future_ap_not_a_prediction_input(self):
        case=synthetic();case['observed_ap_c']=[0]*48
        before=m.predict(case,PARAMETERS,60,1.2)
        case['observed_ap_c']=[10000]*48
        self.assertEqual(before,m.predict(case,PARAMETERS,60,1.2))

    def test_confirmation_cannot_be_fit(self):
        case=synthetic();case['id']='idle_confirmation'
        with self.assertRaisesRegex(ValueError,'development role'):m.fit(case,PARAMETERS,[60])

    def test_missing_gap_future_and_unsupported_state(self):
        for mutate in (lambda c:c['inputs']['preload'][1].update(ap=float('nan')),
                       lambda c:c['inputs']['preload'][-1].update(hi=35),
                       lambda c:c['inputs']['preload'].__delitem__(slice(2,10)),
                       lambda c:c['inputs']['segments'][1].update(state='unmeasured'),
                       lambda c:c['inputs']['segments'][1].update(start_s=34)):
            c=synthetic();mutate(c)
            with self.assertRaises(ValueError):m.predict(c,PARAMETERS,60,1.2)

    def test_rank_failure_not_filled_with_zero(self):
        c=synthetic()
        with patch.object(m.np.linalg,'svd',return_value=np.array([1.,0.])):
            with self.assertRaisesRegex(ValueError,'rank deficient'):m.initialize(c['inputs']['preload'],.05,60)

    def test_constant_ap_has_no_identified_temperature_slope(self):
        records=[dict(session=0,block='solo',key='detection_CPU',overlap_fraction=0.,ap_before_c=30.,
            inference_ms=500+i,elapsed_s=i,thermal_status='0') for i in range(20)]
        out=analysis.service_associations(records)[0]
        self.assertIsNone(out['ap_inference_correlation'])
        self.assertIsNone(out['adjusted_association_ms_per_c'])
        self.assertIsNone(out['fitted_throttle_coefficient'])

    def test_rounding_bound_and_no_overwrite(self):
        c=synthetic();bound=m.preload_sensitivity(c,PARAMETERS,60,1.2)
        before=np.array(m.predict(c,PARAMETERS,60,1.2)[0])
        changed=copy.deepcopy(c)
        for i,p in enumerate(changed['inputs']['preload']):p['ap']+=.05 if i%2 else -.05
        after=np.array(m.predict(changed,PARAMETERS,60,1.2)[0])
        self.assertTrue(np.all(abs(after-before)<=np.array(bound['pointwise_change_bounds_c'])+1e-10))
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileExistsError):analysis.analyze({}, {}, Path(temp))

    def test_component_conservation_and_no_policy_cost_promotion(self):
        from tools import d1_simulator as sim
        from tools import d1_arrival_energy_research as account
        c=synthetic();c['inputs']['reference_c']=29
        parts=m.decompose(c,PARAMETERS,60,1.2,[30.]*len(c['inputs']['query_s']))
        for row in parts:
            self.assertAlmostEqual(sum(row[k] for k in row if k!='total_change_c'),row['total_change_c'])
        result=sim.arrival();case=result['cases'][0]
        blocked=account.aggregate(result['requests'],dict(policy=case['policy'],ledger=case['ledger']),profile={'evidence':m.VERSION})
        self.assertIsNone(blocked['energy_ap']['whole_device_energy_j'])
        self.assertIsNone(blocked['energy_ap']['ap_peak_c'])
        self.assertEqual(blocked['energy_ap']['supported_interface'],'tools.d1_ap_preparation_memory.predict')

    def test_missing_confirmation_fails_before_any_output_or_fit(self):
        data=old.read(analysis.BUNDLE/'inputs.json');contract=old.read(analysis.BUNDLE/'contract.json')
        data['cases'][1]['observed_ap_c'][0]=float('nan')
        with tempfile.TemporaryDirectory() as folder,patch.object(m,'fit') as fit:
            out=Path(folder)/'result'
            with self.assertRaisesRegex(ValueError,'missing target'):analysis.analyze(data,contract,out)
            fit.assert_not_called();self.assertFalse(out.exists())


if __name__=='__main__':unittest.main()
