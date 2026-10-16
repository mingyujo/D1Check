import copy,unittest
from unittest.mock import patch
import numpy as np
import torch
from tools import d1_atc_delta_policy as a
from tools import d1_atc_delta_targets as label
from tools import d1_atc_delta_ppo as rl
from tools import d1_atc_delta_study as s
from tools import d1_atc_delta_controls as controls
from tools import d1_atc_coupling_policy as previous

class Delta(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.f,i,_=a.hybrid.load();cls.initial=i['initial']
    def fixture(self):
        c=a.Controller(self.f,self.initial)
        q=dict(id='0',ordinal=0,task='classification',priority='urgent',arrival_ns=35e9,deadline_offset_ns=1.5e9,work_units=1)
        lanes={b:dict(request=None,phase='AVAILABLE',since=35e9,dispatch=None) for b in ('CPU','GPU')}
        e=a.bank([q],lanes,35e9,c.estimates);x=c.encode([q],lanes,35e9,e)
        c.snapshots=[dict(x,now_ns=t,chosen=e['base'],actor_eligible=False) for t in (35e9,35.4e9,36e9)]
        r=dict(q,status='succeeded',backend='CPU',dispatch_ns=35e9,execution_start_ns=35.1e9,output_ready_ns=35.2e9,persist_complete_ns=35.3e9,worker_release_ns=35.35e9,lane_available_ns=35.4e9,response_ns=.2e9)
        row=dict(planned=1,completed=1,incomplete=0,planned_work_units=1,completed_work_units=1,urgent_planned=1,normal_planned=0,urgent_failure=0,urgent_original_cap_failure=0,normal_failure=0,normal_original_cap_failure=0,urgent_p95_ms=200,energy_j=120+.4*self.f['energy_increment_w']['classification_CPU'],peak_ap_c=30.1)
        raw=dict(row=row,result=dict(ledger=[r]),segments=[dict(start_s=0.,end_s=35.,state='idle'),dict(start_s=35.,end_s=35.4,state='classification_CPU'),dict(start_s=35.4,end_s=120.,state='idle')],curve=[(35,30.),(36,30.1),(120,30.05)])
        return c,raw
    def test_same_trace_performance_delta_exactzero_and_boundary(self):
        c,raw=self.fixture();frames,costs,valid,_=label.targets(c,raw,120,'JP05_DELTA',copy.deepcopy(raw))
        self.assertTrue(valid.all())
        for f in frames:np.testing.assert_array_equal(f['target'][[0,1,2,9]],np.zeros(4,np.float32))
        self.assertEqual(label.trajectory_suffix(raw,35.4e9,self.f)[0],0.)
        self.assertEqual(label.trajectory_suffix(raw,36e9,self.f)[1],0.)
    def test_signed_delta_units_p95_teacherbaseline(self):
        c,ref=self.fixture();raw=copy.deepcopy(ref)
        raw['segments'][1]['end_s']=35.5;raw['segments'][2]['start_s']=35.5
        raw['result']['ledger'][0]['lane_available_ns']=35.5e9
        raw['row']['energy_j']=120+.5*self.f['energy_increment_w']['classification_CPU']
        raw['curve']=[(35,30.),(36,30.2),(120,30.1)];raw['row'].update(peak_ap_c=30.2,urgent_p95_ms=350)
        frames,costs,_,_=label.targets(c,raw,120,'JP05_DELTA',ref)
        self.assertAlmostEqual(float(costs[0]),.1*self.f['energy_increment_w']['classification_CPU'],places=5)
        self.assertAlmostEqual(float(costs[1]),1.,places=5);self.assertAlmostEqual(float(costs[8]),.1,places=6)
        frames,costs,_,_=label.targets(c,ref,120,'ATC_SCORE_DELTA',raw)
        self.assertLess(float(costs[0]),0.);self.assertAlmostEqual(float(costs[1]),-1.,places=5);self.assertEqual(float(costs[8]),0.)
    def test_missing_reference_and_p95_not_zero(self):
        c,raw=self.fixture();ref=copy.deepcopy(raw);ref['row']['completed']=0
        with self.assertRaises(ValueError):label.targets(c,raw,120,'JP05_DELTA',ref)
        ref=copy.deepcopy(raw);ref['row']['urgent_p95_ms']=None
        with self.assertRaises(ValueError):label.targets(c,raw,120,'JP05_DELTA',ref)
    def test_causal_control_and_schema_do_not_reuse08weights(self):
        c,raw=self.fixture();frames,costs,valid,_=label.targets(c,raw,120,'JP05_CAUSAL',copy.deepcopy(raw))
        self.assertGreater(float(frames[0]['target'][0]),0.);self.assertGreater(float(costs[0]),0.)
        self.assertNotEqual(a.SCHEMA,previous.SCHEMA)
        l=rl.Learner(77,dict(arm='JP05_DELTA',schema=a.SCHEMA,sequencing='ATC'))
        with self.assertRaises(ValueError):rl.Learner.from_snapshot(dict(l.snapshot(),schema=previous.SCHEMA),l.dependencies)
    def test_teacher_never_enters_policy_and_mixed_inputs_rejected(self):
        c,raw=self.fixture();qs=[{k:v for k,v in raw['result']['ledger'][0].items() if k in a.PUBLIC_FIELDS}]
        lanes={b:dict(request=None,phase='AVAILABLE',since=35e9,dispatch=None) for b in ('CPU','GPU')}
        with patch.object(label,'trajectory_suffix',side_effect=AssertionError('label calledonline')),patch.object(controls,'greedy_action',side_effect=AssertionError('benchmark calledonline')),patch.object(s.oldstudy.mobile,'eft',side_effect=AssertionError('EFT')):
            for arm in a.ARMS:
                net=rl.ActorCritic(arm);agent=a.Controller(self.f,self.initial,net,True,coupling=arm)
                self.assertIsNotNone(agent({},qs,lanes,35e9,{},None,None)['selected'])
                self.assertEqual(agent.stats['fallback'],0)
        bad=dict(qs[0],work_units=2)
        with self.assertRaises(ValueError):a.validate_engine(dict(protocol=a.VERSION,cells=a.p.profile(self.f)),s.realizations([bad],1),[bad],a.p.PPO_POLICY,a.external.settings(),c)
    def test_counts_guard_energy_selector_and_parentcap(self):
        self.assertEqual([len(s.cases(v)) for v in (s.TRAIN,s.DEV,s.CONFIRM)],[256,16,32])
        self.assertTrue(all(q['work_units']==1 for case in s.cases(s.DEV) for q in case['requests']))
        self.assertEqual(3*s.budget.PROFILES['model']['environments']+s.budget.PROFILES['control']['environments'],4050)
        c,raw=self.fixture();r=dict(raw['row'],condition=0)
        self.assertTrue(s.eligible([r],[r]));bad=dict(r,urgent_original_cap_failure=1)
        self.assertFalse(s.eligible([bad],[r]));bad=dict(r,urgent_p95_ms=201)
        self.assertFalse(s.eligible([bad],[r]))

if __name__=='__main__':unittest.main()
