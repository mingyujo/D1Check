import copy
import math
import unittest
from tools import d1_ap_workload_lag as m
from tools import d1_ap_model_completion as completion
from tools.d1_ap_idle_response import predict as old


class LagTests(unittest.TestCase):
    def setUp(self):
        self.f={'ap_cooling_rate_per_s':.05,'ap_slope_at_30_c_per_s':{'resident_idle':.2,'detection_CPU':.4}}
        self.s=[dict(start_s=0,end_s=10,state='idle'),dict(start_s=10,end_s=20,state='detection:CPU'),dict(start_s=20,end_s=120,state='idle')]

    def test_zero_exact_legacy(self):
        self.assertEqual(m.predict(self.s,self.f,29,28,[0,10,15,20,120],0),old(self.s,self.f,29,28,[0,10,15,20,120]))

    def test_step_matches_numerical_equal_and_distinct_poles(self):
        for tau in [2.,20.,30.]:
            t,h=29.,.1;dt=.0001
            for _ in range(10000):
                t,h=t+dt*(.05*(28-t)+h),h+dt*(.2-h)/tau
            a,b=m.advance(29,.1,.2,28,.05,tau,1)
            self.assertAlmostEqual(a,t,places=5);self.assertAlmostEqual(b,h,places=5)

    def test_split_continuity(self):
        a=m.advance(29,0,.2,28,.05,5,13)
        t,h=m.advance(29,0,.2,28,.05,5,6)
        b=m.advance(t,h,.2,28,.05,5,7)
        for x,y in zip(a,b):self.assertAlmostEqual(x,y,places=12)

    def test_invalid_state_time_and_missing(self):
        for query,tau in [([-1],1),([121],1),([float('nan')],1),([1],-1)]:
            with self.assertRaises(ValueError):m.predict(self.s,self.f,29,28,query,tau)
        for state in ['unknown','classification:GPU']:
            s=copy.deepcopy(self.s);s[0]['state']=state
            with self.assertRaises((ValueError,KeyError)):m.predict(s,self.f,29,28,[1],1)
        s=copy.deepcopy(self.s);s[1]['start_s']=11
        with self.assertRaises(ValueError):m.predict(s,self.f,29,28,[1],1)

    def test_no_postload_observation_input(self):
        c={'inputs':{'segments':self.s,'initial_ap_c':29,'reference_c':28,'query_s':[10,15,25,120]},'observed_ap_c':[1,2,3,4]}
        first=m.path(c,self.f,3);c['observed_ap_c']=[99]*4
        self.assertEqual(first,m.path(c,self.f,3))

    def test_idle_no_registered_load_lag(self):
        s=[dict(start_s=0,end_s=120,state='idle')]
        for tau in [1,5,30]:
            for a,b in zip(m.predict(s,self.f,29,28,[0,60,120],tau).values(),old(s,self.f,29,28,[0,60,120]).values()):
                self.assertAlmostEqual(a,b,places=12)

    def test_fit_training_only_and_missing_target(self):
        c={'inputs':{'segments':self.s,'initial_ap_c':29,'reference_c':28,'query_s':[10,15,25,120]}}
        c['observed_ap_c']=m.path(c,self.f,5)
        self.assertEqual(m.fit([c],self.f,[0,5,10])[0],5)
        c['observed_ap_c'][0]=float('nan')
        with self.assertRaises(ValueError):m.fit([c],self.f,[0,5])

    def test_stress_common_offset_and_bounds(self):
        self.assertAlmostEqual((150+.1*120)-(152+.1*120),150-152)
        r=m.idle_difference_interval(150,152,100,110,-.2,.1)
        self.assertAlmostEqual(r['stress_low_j'],-33)
        self.assertAlmostEqual(r['stress_high_j'],30)
        self.assertAlmostEqual(r['symmetric_break_even_idle_w'],2/210)
        with self.assertRaises(ValueError):m.idle_difference_interval(1,2,1,1,1,0)

    def test_published_inputs_reproduce_and_keep_full_policy_window(self):
        d=completion.inputs()
        self.assertEqual(len(d['cases']),5)
        for c in d['cases']:
            self.assertAlmostEqual(completion.score(c['observed_ap_c'],m.path(c,d['parameters'],0))['mae_c'],c['saved_mae_c'],places=8)
        costs,stress=completion.sensitivity(d)
        self.assertEqual(len(costs),3);self.assertEqual(len(stress),6)
        self.assertTrue(all(c['whole_window_supported_energy_j'] is None for c in costs))
        d['policy_schedules']['B2_PC'].pop()
        with self.assertRaises(ValueError):completion.sensitivity(d)

    def test_missing_direction_not_zero_filled(self):
        self.assertIsNone(completion.interpolate([0,20],[28,29],10))
        self.assertIsNone(completion.interpolate([0,5],[28,29],10))

    def test_engine_does_not_promote_posthoc_candidate(self):
        from tools import d1_arrival_energy_research as research
        from tools.test_d1_arrival_energy_research import request,result
        row=dict(request(),status='unfinished')
        out=research.aggregate([request()],result([row]),profile={'evidence':m.VERSION})
        self.assertEqual(out['energy_ap']['status'],'UNSUPPORTED_PRELOAD_AP_CANDIDATE_FOR_POLICY_COST')
        self.assertIsNone(out['energy_ap']['whole_device_energy_j'])
        self.assertIsNone(out['energy_ap']['ap_peak_c'])


if __name__=='__main__':unittest.main()
