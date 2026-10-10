import copy
import tempfile
import unittest
from pathlib import Path
import numpy as np
from tools import d1_registered_baseline as m


def rows(identity='a',role='development',n=18):
    return [dict(session=identity,role=role,gap=30,lo_s=30-5*n+5*i,hi_s=35-5*n+5*i,
        latest_power_event_s=35-5*n+5*i+.2,other_rate_core_s_per_s=.2+.01*i,
        mean_power_W=.8+.5*(.2+.01*i)) for i in range(n)]


class Boundaries(unittest.TestCase):
    def test_weighted_median_tie_outlier_and_missing(self):
        self.assertEqual(m.median([1,1,1,100],[5]*4),1.)
        self.assertEqual(m.median([1,2,3,100],[5]*4),2.5)
        self.assertEqual(m.median([1,2,3],[1,1,10]),3.)
        with self.assertRaises(ValueError):m.median([1,np.nan],[1,1])

    def test_complete_registered_window_and_future_cutoff(self):
        r=rows();f=m.features(r);self.assertEqual(f['duration_s'],90)
        r[-1]['latest_power_event_s']=35.
        with self.assertRaises(ValueError):m.features(r)
        with self.assertRaises(ValueError):m.features(rows(n=10))
        r=rows();r.pop(4)
        with self.assertRaises(ValueError):m.features(r)

    def test_dev_only_equal_session_fit_and_true_RMSE(self):
        data=rows('a')+rows('b',n=48)+rows('c')
        model=m.fit(data,['a','b','c']);self.assertAlmostEqual(model['slope_W_per_core_s_per_s'],.5,places=12)
        self.assertLess(model['pre_equal_session_RMSE_W'],1e-14)
        data[0]['role']='confirmation'
        with self.assertRaises(ValueError):m.fit(data,['a','b','c'])
        with self.assertRaises(ValueError):m.fit(rows('outside'),['a','b','c'])

    def test_unidentified_slope_not_invented(self):
        data=rows('a')+rows('b')+rows('c')
        for r in data:r['other_rate_core_s_per_s']=.2
        with self.assertRaisesRegex(ValueError,'identified'):m.fit(data,['a','b','c'])

    def test_prediction_no_future_input_before35_unchanged_additive(self):
        p=dict(pre_w=1.,trace_complete=True,actual=[dict(start_s=0.,end_s=120.,state='idle')],full_pre_features=m.features(rows()))
        fixed=dict(idle_bias_w=0.,increments={k:0. for k in m.old.prior.prior.STATES});model=dict(slope_W_per_core_s_per_s=.5)
        with self.assertRaises(ValueError):m.predict(p,model,fixed,0,120)
        y=m.predict(p,model,fixed,0,120,opt_in=True)
        poison=dict(p,power_w=[999],ap=[999],future_CPU=[999])
        self.assertEqual(y,m.predict(poison,model,fixed,0,120,opt_in=True))
        self.assertEqual(m.predict(p,model,fixed,0,35,opt_in=True),35.)
        self.assertAlmostEqual(y,35+m.predict(p,model,fixed,35,120,opt_in=True))
        self.assertEqual(m.predict(p,model,fixed,0,120,'FULL_MEAN',opt_in=True),y)
        p['full_pre_features']['persistent_other_proxy']=-9
        with self.assertRaisesRegex(ValueError,'nonpositive'):m.predict(p,model,fixed,0,120,opt_in=True)

    def test_trace_and_horizon_required(self):
        p=dict(pre_w=1.,trace_complete=False,full_pre_features=m.features(rows()))
        with self.assertRaises(ValueError):m.predict(p,{}, {},0,120,opt_in=True)
        with self.assertRaises(ValueError):m.predict(p,{}, {},0,121,opt_in=True)

    def test_consumed_analysis_stays_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            m.old.write(Path(d)/'started.json',{})
            with self.assertRaisesRegex(ValueError,'consumed'):m.run(d)


if __name__=='__main__':unittest.main()
