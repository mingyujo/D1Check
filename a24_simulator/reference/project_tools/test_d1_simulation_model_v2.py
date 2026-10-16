import copy
import unittest
import numpy as np
from tools import d1_simulation_model_v2 as m


class ModelV2Tests(unittest.TestCase):
    def case(self):
        pre=[dict(t=float(t),lo=t-.01,hi=t+.01,ap=29.) for t in range(-25,35,3)]
        return dict(id='fixture',role='development',pre=pre,q=[35.,45.,60.],actual=[dict(start_s=0.,end_s=60.,state='idle')],pre_w=1.)
    def model(self):
        return dict(ap=dict(beta=.05,slow_tau_s=1920.,slow_input_w=dict(zip(m.STATES,[1.]*4)),coefficients=[.1]*5))
    def test_constant_idle_and_future_targets_do_not_enter_initialization(self):
        c=self.case();before=m.ap_prediction(c,self.model());c['ap']=[999.]*3;c['power_w']=[1000.]
        after=m.ap_prediction(c,self.model());np.testing.assert_allclose(before[0],[29.]*3,atol=1e-10);self.assertEqual(before,after)
    def test_future_initial_observation_and_missing_schedule_are_rejected(self):
        c=self.case();c['pre'][-1]['hi']=35.
        with self.assertRaises(ValueError):m.ap_prediction(c,self.model())
        c=self.case();c['actual'][0]['end_s']=50.
        with self.assertRaises(ValueError):m.ap_prediction(c,self.model())
    def test_known_conditioning_changes_forcing_without_double_counting_anchor(self):
        c=self.case();c['history']=[dict(start_s=-100.,end_s=-26.,state='classification_CPU'),dict(start_s=-26.,end_s=0.,state='idle')]
        out,initial=m.ap_prediction(c,self.model());self.assertEqual(initial['history_intervals'],2);self.assertTrue(np.all(np.isfinite(out)))
        c['history'][-1]['end_s']=2.
        with self.assertRaises(ValueError):m.ap_prediction(c,self.model())
    def test_exact_kernel_split_additivity(self):
        one=[dict(start_s=0.,end_s=10.,state='classification_CPU')];two=[dict(start_s=0.,end_s=4.,state='classification_CPU'),dict(start_s=4.,end_s=10.,state='classification_CPU')]
        np.testing.assert_allclose(m.kernel(one,[5.,10.,30.],.05,{'classification_CPU':2.}),m.kernel(two,[5.,10.,30.],.05,{'classification_CPU':2.}),rtol=1e-12)
    def service(self):
        return dict(overhead_ns=10,buckets={k:{'s':[[10,100,20,5,15],[20,120,25,5,20]]} for k in ('CPU/classification_CPU','CPU/detection_CPU','PAR/classification_GPU','PAR/detection_CPU')})
    def tickets(self):
        return [dict(id=str(i),ordinal=i,task='classification' if i%2==0 else 'detection',priority='urgent' if i%2==0 else 'normal',arrival_ns=35_000_000_000,deadline_offset_ns=1000) for i in range(4)]
    def test_lane_release_response_boundaries_and_whole_denominator(self):
        r=m.simulate(self.tickets(),self.service(),policy='CPU');rows=r['ledger']
        dispatched=sorted(rows,key=lambda r:r['dispatch_ns'])
        for a,b in zip(dispatched,dispatched[1:]):self.assertLessEqual(a['lane_available_ns'],b['dispatch_ns'])
        self.assertEqual(sum(g['planned'] for g in r['metrics'].values()),4)
        self.assertEqual(rows[0]['response_ns'],rows[0]['output_ready_ns']-rows[0]['arrival_ns'])
        self.assertEqual(rows[1]['response_ns'],rows[1]['persist_complete_ns']-rows[1]['arrival_ns'])
    def test_common_horizon_does_not_hide_unfinished_or_drop_failures(self):
        tickets=self.tickets();r=m.simulate(tickets,self.service(),horizon_ns=35_000_000_020)
        self.assertEqual(sum(g['planned'] for g in r['metrics'].values()),4);self.assertEqual(sum(g['timely'] for g in r['metrics'].values()),0)
        self.assertTrue(all(x['status']!='succeeded' for x in r['ledger']))
    def test_response_ready_but_unreleased_job_is_excluded_from_completed_p95(self):
        r=m.simulate(self.tickets()[:1],self.service(),horizon_ns=35_000_000_145)
        self.assertIn('response_ns',r['ledger'][0])
        self.assertEqual(r['ledger'][0]['status'],'unfinished')
        self.assertEqual(r['metrics']['urgent']['planned'],1)
        self.assertEqual(r['metrics']['urgent']['completed'],0)
        self.assertIsNone(r['metrics']['urgent']['response_P95_ms'])
    def test_replay_is_reproducible_and_confirmation_fit_is_forbidden(self):
        self.assertEqual(m.simulate(self.tickets(),self.service(),mode='session_replay',seed=13),m.simulate(self.tickets(),self.service(),mode='session_replay',seed=13))
        with self.assertRaises(ValueError):m.fit([dict(id=str(i),role='confirmation') for i in range(4)],{})

if __name__=='__main__':unittest.main()
