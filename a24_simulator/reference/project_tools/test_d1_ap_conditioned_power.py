import copy
import math
import tempfile
import unittest
from pathlib import Path
import numpy as np
from tools import d1_ap_conditioned_power as m


def rows(identity,role='development',n=17):
    return [dict(session=identity,role=role,gap=30,lo_s=30-5*n+5*i,hi_s=35-5*n+5*i,
        latest_power_event_s=35-5*n+5*i+.1,other_rate_core_s_per_s=.2+.02*((7*i)%5),
        pre_AP_mean_c=28-.04*i,mean_power_W=.7+.6*(.2+.02*((7*i)%5))+.08*(-.04*i)) for i in range(n)]


def initial(beta=.045,tau=30.):
    return dict(reference_c=27.,h_last_c_per_s=-.003,anchor_s=34.,anchor_ap_c=28.,input_end_s=34.2,beta_per_s=beta,tau_s=tau)


def public():
    return dict(pre_w=1.,pre_before35=True,trace_complete=True,actual=[dict(start_s=0.,end_s=120.,state='idle')],
        pre_init=initial(),features=dict(pre_full_mean_W=1.,pre_full_mean_other=.3,persistent_other_proxy=.25,pre_mean_AP_c=28.,duration_s=85.))


class Boundaries(unittest.TestCase):
    def test_pre_AP_bracketing_integral_and_future_rejection(self):
        pre=[dict(t=float(t),lo=t-.1,hi=t+.1,ap=28.+.01*t) for t in np.arange(-60,35,5)]
        self.assertAlmostEqual(m.AP_bin_mean(pre,-55,-50),28+.01*(-52.5),places=12)
        with self.assertRaises(ValueError):m.AP_bin_mean(pre,-61,-55)
        changed=copy.deepcopy(pre);changed[-1]['hi']=35.
        with self.assertRaises(ValueError):m.AP_bin_mean(changed,25,30)
        changed=pre[:5]+pre[8:]
        with self.assertRaisesRegex(ValueError,'gapped'):m.AP_bin_mean(changed,-40,-35)

    def test_two_covariates_recovered_dev_only_and_rank(self):
        data=rows('a')+rows('b',n=47)+rows('c')
        z=m.fit(data,['a','b','c'],'CPU_AP')
        self.assertAlmostEqual(z['CPU_slope_W_per_core_s_per_s'],.6,places=12)
        self.assertAlmostEqual(z['AP_slope_W_per_C'],.08,places=12)
        self.assertLess(z['pre_equal_session_RMSE_W'],1e-12)
        data[0]['role']='confirmation'
        with self.assertRaises(ValueError):m.fit(data,['a','b','c'],'CPU_AP')
        data=rows('a')+rows('b')+rows('c')
        for r in data:r['pre_AP_mean_c']=28+r['other_rate_core_s_per_s']
        with self.assertRaisesRegex(ValueError,'rank'):m.fit(data,['a','b','c'],'CPU_AP')

    def test_signed_temperature_and_nonnegative_CPU_constraint(self):
        data=rows('a')+rows('b')+rows('c')
        for r in data:r['mean_power_W']=1-.6*r['other_rate_core_s_per_s']-.02*(r['pre_AP_mean_c']-28)
        z=m.fit(data,['a','b','c'],'CPU_AP')
        self.assertEqual(z['CPU_slope_W_per_core_s_per_s'],0.)
        self.assertLess(z['AP_slope_W_per_C'],0.)

    def test_analytic_AP_integral_additivity_and_equal_rate(self):
        for beta,tau in ((.045,30.),(.05,20.)):
            init=initial(beta,tau);t=np.linspace(35,120,10001);y=np.array([m.idle_AP(init,float(v)) for v in t])
            exact=m.idle_integral(init,35,120)
            numeric=float(np.trapezoid(y,t))
            self.assertAlmostEqual(exact,numeric,delta=2e-5)
            self.assertAlmostEqual(exact,m.idle_integral(init,35,73.123)+m.idle_integral(init,73.123,120),places=10)

    def test_interior_nonpositive_power_blocked_even_for_short_query(self):
        p=public();p['pre_init']=dict(initial(.1,20.),h_last_c_per_s=-.1)
        p['features'].update(pre_full_mean_W=.2,pre_mean_AP_c=27.)
        model=dict(CPU_slope_W_per_core_s_per_s=0.,AP_slope_W_per_C=1.)
        self.assertGreater(m.baseline(p,model,35),0);self.assertGreater(m.baseline(p,model,120),0)
        points=m.critical_times(p['pre_init']);self.assertEqual(len(points),3)
        self.assertAlmostEqual(points[1],34+math.log(3)/.05)
        fixed=dict(idle_bias_w=0.,increments={k:0. for k in m.old.old.prior.prior.STATES})
        with self.assertRaisesRegex(ValueError,'nonpositive'):m.prediction(p,model,fixed,0,36,opt_in=True)

    def test_prediction_is_pre_only_and_keeps_initial_accounting(self):
        p=public();model=dict(CPU_slope_W_per_core_s_per_s=.4,AP_slope_W_per_C=.05)
        fixed=dict(idle_bias_w=0.,increments={k:0. for k in m.old.old.prior.prior.STATES})
        with self.assertRaises(ValueError):m.prediction(p,model,fixed,0,120)
        y=m.prediction(p,model,fixed,0,120,opt_in=True)
        poison=dict(p,future_AP=[1000],power_w=[1000],ap=[1000],future_CPU=[1000])
        self.assertEqual(y,m.prediction(poison,model,fixed,0,120,opt_in=True))
        self.assertEqual(m.prediction(p,model,fixed,0,35,opt_in=True),35.)
        self.assertAlmostEqual(y,35+m.prediction(p,model,fixed,35,120,opt_in=True),places=11)
        with self.assertRaises(ValueError):m.prediction(p,model,fixed,0,121,opt_in=True)
        p['pre_init']['input_end_s']=35
        with self.assertRaises(ValueError):m.prediction(p,model,fixed,0,120,opt_in=True)

    def test_consumed_analysis_and_partial_marker_not_restarted(self):
        with tempfile.TemporaryDirectory() as d:
            m.old.old.write(Path(d)/'started.json',dict(status='partial'))
            with self.assertRaisesRegex(ValueError,'consumed'):m.run(d)


if __name__=='__main__':unittest.main()
