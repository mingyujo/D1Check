"""Focused numerical/data-boundary tests; no device or policy training calls."""
import copy
import unittest
import numpy as np
from tools import d1_model_refinement as m


class RefinementTests(unittest.TestCase):
    def setUp(self):
        self.frozen=m.read(m.MODEL)
        pre=[dict(t=float(t),ap=30.+.3*np.exp(-(t+30)*.03),lo=t-.05,hi=t+.05)
             for t in range(-30,35,3)]
        self.c=dict(id='fixture',role='development',pre=pre,pre_w=1.2,
            q=list(range(35,181,3)),power_t=list(range(-31,182)),power_w=[1.2]*213,
            actual=[dict(start_s=0.,end_s=35.,state='idle'),
                    dict(start_s=35.,end_s=50.,state='classification_CPU'),
                    dict(start_s=50.,end_s=180.,state='idle')],last_lane_s=50.)
        self.c['ap']=m.predict(self.c,self.c['actual'],self.frozen,dict(name='FROZEN'))[0]

    def test_integral_partition_units_and_missing(self):
        c=self.c
        self.assertAlmostEqual(m.integral(c,0,120),144.)
        self.assertAlmostEqual(m.integral(c,0,120),sum(m.integral(c,a,b) for a,b in [(0,35),(35,50),(50,120)]))
        c=copy.deepcopy(c);c['power_w'][75]=None
        with self.assertRaisesRegex(ValueError,'missing'):m.integral(c,0,120)
        c=dict(power_t=[0.,1.,5.],power_w=[1.,1.,1.])
        with self.assertRaisesRegex(ValueError,'gap'):m.integral(c,0,5)

    def test_no_evaluation_targets_enter_predictions(self):
        c=self.c; changed=copy.deepcopy(c)
        changed['ap']=[100.]*len(c['ap'])
        changed['power_w']=[v if t<35 else 1000. for t,v in zip(c['power_t'],c['power_w'])]
        for candidate in [dict(name='FROZEN'),dict(name='AP_SIMPLE',k=1.,g=0.),
                          dict(name='AP_DELAY',k=1.,g=.2),dict(name='E_TREND',alpha=2.)]:
            np.testing.assert_array_equal(m.predict(c,c['actual'],self.frozen,candidate)[0],
                                          m.predict(changed,c['actual'],self.frozen,candidate)[0])
            self.assertEqual(m.energy_prediction(c,c['actual'],self.frozen,candidate,120),
                             m.energy_prediction(changed,c['actual'],self.frozen,candidate,120))

    def test_fit_role_guard_and_unidentified_power(self):
        bad=dict(self.c,role='evaluation')
        for n in m.NAMES:
            with self.assertRaisesRegex(ValueError,'development'):m.fit([bad],self.frozen,n)
        with self.assertRaisesRegex(ValueError,'unidentified'):m.fit([self.c],self.frozen,'E_TREND')

    def test_time_continuity_and_unsupported_state(self):
        c=self.c;candidate=dict(name='AP_DELAY',k=1.,g=.2)
        c=dict(c,q=[49.999999,50.,50.000001,60.])
        y=m.predict(c,c['actual'],self.frozen,candidate)[0]
        self.assertLess(max(abs(y[1]-y[0]),abs(y[2]-y[1])),1e-5)
        bad=copy.deepcopy(c);bad['actual'][1]['state']='unmeasured_NPU'
        with self.assertRaises((ValueError,KeyError)):m.predict(bad,bad['actual'],self.frozen,candidate)
        bad=copy.deepcopy(c);bad['pre'][-1]['hi']=36
        with self.assertRaises(ValueError):m.predict(bad,bad['actual'],self.frozen,candidate)

    def test_delayed_fit_recovers_synthetic_known_coefficients(self):
        c=copy.deepcopy(self.c)
        c['ap']=m.predict(c,c['actual'],self.frozen,dict(name='AP_DELAY',k=.8,g=.3))[0]
        fitted=m.fit([c],self.frozen,'AP_DELAY')
        self.assertAlmostEqual(fitted['k'],.8,places=10)
        self.assertAlmostEqual(fitted['g'],.3,places=10)

    def test_frozen_hash_and_no_default_mutation(self):
        old=copy.deepcopy(self.frozen)
        m.fit([self.c],self.frozen,'AP_SIMPLE')
        self.assertEqual(old,self.frozen)
        self.assertEqual(m.sha(m.MODEL),m.MODEL_SHA)

    def test_unavailable_not_zero_in_condition_summary(self):
        row=dict(block='confirmation',mode='A_conditional',policy='fixture',candidate='FROZEN',abs_j=None,mae_c=None)
        found=next(r for r in m.condition_summary([row]) if r['mode']=='A_conditional' and r['candidate']=='FROZEN')
        self.assertEqual(found['unavailable'],1)
        self.assertEqual(found['n'],0)
        self.assertIsNone(found['energy_mae_j'])
        self.assertIsNone(found['ap_mae_c'])


if __name__=='__main__':unittest.main()
