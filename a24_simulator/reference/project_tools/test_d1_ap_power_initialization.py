import copy
import math
import tempfile
import unittest
from pathlib import Path
import numpy as np
from tools import d1_ap_power_initialization as m


def synthetic(identity='a',gain=.2):
    times=np.arange(-61.,181.,1.)
    watts=np.array([1.+.15*(int(t)%11<4)-.1*(int(t)%7>=5) for t in times])
    pre=[dict(t=float(t),lo=float(t)-.05,hi=float(t)+.05,ap=28.) for t in np.arange(-60.,35.,2.5)]
    segments,mean=m.pre_power(dict(power_t=times,power_w=watts),pre)
    p=dict(id=identity,role='development',gap=30,pre_AP=pre,pre_power_segments=segments,pre_power_mean_W=mean)
    beta=.045;z,zh=m.forcing_response(p,beta)
    for i,row in enumerate(pre):
        d=row['t']-pre[0]['t'];row['ap']=27.5+.5*math.exp(-beta*d)+.006*m.memory.convolution(beta,30.,d)+gain*z[i]
    return p


def fixed_AP(beta=.045):
    return dict(mode='LOAD_SLOW',beta_fixed=beta,preparation_tau_s=30.,tau_s=1920.,coefficients=[.1,.1,.1,.1,.007])


class Boundaries(unittest.TestCase):
    def test_one_gain_recovered_and_first_AP_rounding_bound(self):
        cases=[synthetic(k) for k in ('a','b','c')]
        model=m.fit(cases,['a','b','c'],.045)
        self.assertAlmostEqual(model['gain_C_per_J'],.2,places=10)
        p=synthetic();init=m.initialize(p,model);z,zh=m.forcing_response(p,.045)
        self.assertAlmostEqual(init['reference_c'],27.5,places=10)
        self.assertAlmostEqual(init['h_last_c_per_s'],.006*math.exp(-92.5/30.)+.2*zh[-1],places=10)
        changed=copy.deepcopy(cases);changed[0]['pre_AP'][0]['ap']+=.05
        new=m.fit(changed,['a','b','c'],.045)
        self.assertLessEqual(abs(new['unconstrained_gain_C_per_J']-model['unconstrained_gain_C_per_J']),model['unconstrained_gain_worst_case_rounding_change']+1e-10)

    def test_zero_gain_reproduces_existing_initializer(self):
        p=synthetic();model=dict(beta_fixed=.045,preparation_tau_s=30.,gain_C_per_J=0.)
        value=m.initialize(p,model);old=m.memory.initialize(p['pre_AP'],.045,30.)
        for key in ('reference_c','h_first_c_per_s','h_last_c_per_s','anchor_s','anchor_ap_c'):
            self.assertAlmostEqual(value[key],old[key],places=11)

    def test_only_past_power_events_and_missing_age_rejection(self):
        p=synthetic();t=np.arange(-61.,181.,1.);w=np.ones(len(t));c=dict(power_t=t,power_w=w)
        first=m.pre_power(c,p['pre_AP']);w[t>=35]=999999.
        self.assertEqual(first,m.pre_power(c,p['pre_AP']))
        self.assertTrue(all(s['source_event_s']<=s['lo_s'] and s['hi_s']<35 for s in first[0]))
        t=np.arange(-61.,181.,5.)
        with self.assertRaisesRegex(ValueError,'age|unavailable'):m.pre_power(dict(power_t=t,power_w=np.ones(len(t))),p['pre_AP'])

    def test_roles_constant_power_and_future_segments_blocked(self):
        cases=[synthetic(k) for k in ('a','b','c')];cases[0]['role']='confirmation'
        with self.assertRaises(ValueError):m.fit(cases,['a','b','c'],.045)
        p=synthetic()
        for s in p['pre_power_segments']:s['power_W']=1.
        p['pre_power_mean_W']=1.
        cases=[dict(copy.deepcopy(p),id=k) for k in ('a','b','c')]
        with self.assertRaisesRegex(ValueError,'variation'):m.fit(cases,['a','b','c'],.045)
        p=synthetic();p['pre_power_segments'][-1]['source_event_s']=35.
        with self.assertRaises(ValueError):m.forcing_response(p,.045)

    def test_future_observations_not_used_schedule_and_anchor_checked(self):
        p=synthetic();init=m.initialize(p,dict(beta_fixed=.045,preparation_tau_s=30.,gain_C_per_J=.2))
        original=dict(ap=dict(beta=.045),energy_increment_w={k:1. for k in m.energy.STATES});ap=fixed_AP()
        actual=[dict(start_s=0.,end_s=35.,state='idle'),dict(start_s=35.,end_s=50.,state='classification_CPU'),dict(start_s=50.,end_s=180.,state='idle')]
        q=[35.,60.,120.,179.]
        with self.assertRaises(ValueError):m.AP_predict(p,init,original,ap,q,actual)
        y=m.AP_predict(p,init,original,ap,q,actual,opt_in=True)
        poison=dict(p,ap=[999],future_power=[999],future_AP=[999])
        self.assertEqual(y,m.AP_predict(poison,init,original,ap,q,actual,opt_in=True))
        bad=copy.deepcopy(actual);bad[1]['state']='unknown_GPU'
        with self.assertRaises(ValueError):m.AP_predict(p,init,original,ap,q,bad,opt_in=True)
        with self.assertRaises(ValueError):m.AP_predict(p,dict(init,anchor_ap_c=99),original,ap,q,actual,opt_in=True)
        with self.assertRaises(ValueError):m.AP_predict(p,init,original,ap,[35.,181.],actual,opt_in=True)

    def test_constant_held_power_zero_response_and_equal_rate(self):
        p=synthetic()
        for s in p['pre_power_segments']:s['power_W']=1.
        p['pre_power_mean_W']=1.;z,h=m.forcing_response(p,1/30.)
        np.testing.assert_array_equal(z,np.zeros(len(z)));np.testing.assert_array_equal(h,np.zeros(len(h)))
        T,H=m.advance_forcing(0.,0.,1.,1/30.,30.,30.)
        self.assertTrue(math.isfinite(T) and math.isfinite(H));self.assertAlmostEqual(H,1-math.exp(-1))

    def test_consumed_analysis_stays_closed(self):
        with tempfile.TemporaryDirectory() as d:
            m.previous.old.old.write(Path(d)/'started.json',{})
            with self.assertRaisesRegex(ValueError,'consumed'):m.run(d)


if __name__=='__main__':unittest.main()
