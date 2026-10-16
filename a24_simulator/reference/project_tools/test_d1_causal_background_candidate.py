import copy
import math
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from tools import d1_causal_background_candidate as m


class CausalCandidateTests(unittest.TestCase):
    def setUp(self):
        self.cfg=m.read(m.CONTRACT)
        self.model=m.read(Path('docs/results/online_policy_study_01/separated_power_final/model.json'))
        self.case=dict(id='synthetic_development',role='development',preload_w=1.,
            preload=[dict(t=t,lo=t-.01,hi=t+.01,ap=30.+.1*math.exp(-t/30)) for t in range(-28,33,2)],
            power=[dict(t_s=float(t),ready_s=t+.1,w=1.6) for t in range(-30,182)],
            actual_segments=[dict(start_s=0.,end_s=181.,state='idle')],
            forecast_segments=[dict(start_s=0.,end_s=181.,state='idle')],
            query_s=list(range(36,179,3)))
        self.case['observed_ap']=m.base_ap(self.case,self.model,self.case['query_s'],'actual_segments')

    def test_integral_preserves_partition_and_never_uses_future_endpoint(self):
        p=[dict(t_s=t,ready_s=t+.1,w=1.+t) for t in range(11)]
        self.assertAlmostEqual(m.integral(p,0,10),60.)
        self.assertAlmostEqual(m.integral(p,0,4)+m.integral(p,4,10),60.)
        self.assertIsNone(m.integral(p,0,10,available_at=10.))
        p[5]['w']=None
        self.assertIsNone(m.integral(p,0,10))
        p[5]['w']=float('nan')
        self.assertIsNone(m.integral(p,0,10))
        self.assertIsNone(m.integral([p[0],p[-1]],0,10))

    def test_ready_time_and_exact_trailing_window(self):
        r=m.residual_at(self.case,self.model,35.,self.cfg)
        self.assertEqual((r['window_start_s'],r['window_end_s']),(24.,34.))
        self.assertAlmostEqual(r['r_w'],.6)
        c=copy.deepcopy(self.case);c['power']=[p for p in c['power'] if p['ready_s']<30]
        self.assertIsNone(m.residual_at(c,self.model,35,self.cfg)['r_w'])
        c=copy.deepcopy(self.case);c['power'][60]['w']=None
        self.assertIsNone(m.residual_at(c,self.model,35,self.cfg)['r_w'])

    def test_exact_dynamics_continuity_missing_and_zero(self):
        beta=.1;r=.4
        once=m.advance(0.,r,beta,20.)
        self.assertAlmostEqual(once,m.advance(m.advance(0.,r,beta,10.),r,beta,10.))
        self.assertAlmostEqual(once,r/beta*(1-math.exp(-2)))
        steps=[dict(issue_s=35,r_w=r),dict(issue_s=45,r_w=None)]
        self.assertEqual(m.correction_at(steps,35,beta),0.)
        self.assertIsNotNone(m.correction_at(steps,45,beta))
        self.assertIsNone(m.correction_at(steps,46,beta))
        with self.assertRaises(ValueError):m.advance(0.,r,0.,20.)

    def test_known_gain_and_confirmation_fit_rejection(self):
        cases=[]
        for i in range(3):
            c=copy.deepcopy(self.case);c['id']=f'dev{i}'
            for p in c['power']:p['w']+=i*.1
            steps=m.updates(c,self.model,self.cfg)
            z=[m.correction_at(steps,t,self.model['ap']['beta']) for t in c['query_s']]
            c['observed_ap']=[y+.25*x for y,x in zip(c['observed_ap'],z)];cases.append(c)
        self.assertAlmostEqual(m.fit(cases,self.model,self.cfg)['gamma'],.25)
        cases[0]['role']='confirmation'
        with self.assertRaisesRegex(ValueError,'development-only'):m.fit(cases,self.model,self.cfg)

    def test_negative_gain_is_recorded_not_replaced_by_a_second_candidate(self):
        c=copy.deepcopy(self.case);steps=m.updates(c,self.model,self.cfg)
        z=[m.correction_at(steps,t,self.model['ap']['beta']) for t in c['query_s']]
        c['observed_ap']=[y-.2*x for y,x in zip(c['observed_ap'],z)]
        result=m.fit([c],self.model,self.cfg)
        self.assertAlmostEqual(result['unconstrained_gamma'],-.2)
        self.assertEqual(result['gamma'],0.)

    def test_issued_forecast_future_poison_and_no_poststart_ap_feedback(self):
        before=m.issued_forecast(self.case,self.model,.25,self.cfg,45,30)
        c=copy.deepcopy(self.case)
        for p in c['power']:
            if p['ready_s']>45:p['w']=10000.
        c['observed_ap']=[9999.]*len(c['query_s'])
        c['actual_segments']=[dict(start_s=0.,end_s=45.,state='idle'),
                              dict(start_s=45.,end_s=181.,state='classification:CPU')]
        after=m.issued_forecast(c,self.model,.25,self.cfg,45,30)
        self.assertEqual(before,after)
        c['power'][70]['w']+=1. # t=40: already published at issue45
        changed=m.issued_forecast(c,self.model,.25,self.cfg,45,30)
        self.assertNotEqual(before['predicted_j'],changed['predicted_j'])
        self.assertNotEqual(before['predicted_ap_c'],changed['predicted_ap_c'])
        self.assertFalse(after['post_start_ap_feedback'])

    def test_zero_gain_matches_original_ap_and_unidentified_is_blocked(self):
        r=m.issued_forecast(self.case,self.model,0.,self.cfg,45,10)
        self.assertEqual(r['predicted_ap_c'],r['frozen_ap_c'])
        with self.assertRaises(ValueError):m.issued_forecast(self.case,self.model,None,self.cfg,45,10)
        with self.assertRaises(ValueError):m.issued_forecast(self.case,self.model,.2,self.cfg,46,10)

    def test_no_excitation_is_null_and_unsupported_state_is_not_free_energy(self):
        c=copy.deepcopy(self.case)
        for p in c['power']:p['w']=1.
        f=m.fit([c],self.model,self.cfg)
        self.assertEqual(f['numerical_rank'],0)
        self.assertIsNone(f['gamma'])
        c['actual_segments']=[dict(start_s=0.,end_s=181.,state='detection:GPU')]
        with self.assertRaisesRegex(ValueError,'unsupported state'):
            m.residual_at(c,self.model,45,self.cfg)

    def test_real_cli_entry_reproduces_saved_nine_cases_without_process_calls(self):
        root=Path('docs/results/online_policy_study_01/causal_background_pc_v1')
        originals={str(p):m.digest(p) for p in (root/'bundle').glob('*.json')}
        originals[str(m.CONTRACT)]=m.digest(m.CONTRACT)
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'evaluation'
            with patch('sys.argv',['candidate','analyze','--bundle',str(root/'bundle'),'--output',str(target)]), \
                 patch('subprocess.run',side_effect=AssertionError('no subprocess allowed')), \
                 patch('subprocess.Popen',side_effect=AssertionError('no process launch allowed')),redirect_stdout(io.StringIO()):
                m.main()
            for name in ('candidate.json','summary.csv','ap_paths.csv','updates.csv','forecasts.json','horizon_metrics.csv'):
                self.assertEqual((target/name).read_bytes(),(root/'evaluation'/name).read_bytes(),name)
            self.assertEqual(m.read(target/'scope.json')['new_independent_validation'],0)
            with self.assertRaises(FileExistsError):m.analyze(root/'bundle',target,self.cfg)
        self.assertEqual(originals,{p:m.digest(p) for p in originals})

    def test_bundle_drift_fails_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);m.write(root/'resources.json',dict(source_freeze_sha256='wrong',files={}))
            with self.assertRaisesRegex(ValueError,'freeze identity'):m.analyze(root,root/'out',self.cfg)
            self.assertFalse((root/'out').exists())


if __name__=='__main__':unittest.main()
