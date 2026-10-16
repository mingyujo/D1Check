import copy,unittest
from unittest.mock import patch
import numpy as np
import torch
from tools import d1_atc_wait_policy as a
from tools import d1_atc_wait_targets as label
from tools import d1_atc_wait_ppo as rl
from tools import d1_atc_wait_study as s
from tools import d1_atc_wait_controls as controls
from tools import d1_atc_delta_policy as old

class WaitStudy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.f,i,_=a.hybrid.load();cls.initial=i['initial'];torch.set_num_threads(1)
    def fixture(self):
        c=a.Controller(self.f,self.initial,mode=a.RULE)
        q=dict(id='0',ordinal=0,task='classification',priority='urgent',arrival_ns=35e9,deadline_offset_ns=1.5e9,work_units=1)
        lanes={b:dict(request=None,phase='AVAILABLE',since=35e9,dispatch=None) for b in ('CPU','GPU')}
        e=a.bank([q],lanes,35e9,c.estimates);x=c.encode([q],lanes,35e9,e)
        c.snapshots=[dict(x,now_ns=t,chosen=e['base'],actor_eligible=False) for t in (35e9,35.4e9,36e9)]
        r=dict(q,status='succeeded',backend='CPU',dispatch_ns=35e9,execution_start_ns=35.1e9,output_ready_ns=35.2e9,persist_complete_ns=35.3e9,worker_release_ns=35.35e9,lane_available_ns=35.4e9,response_ns=.2e9)
        row=dict(planned=1,completed=1,incomplete=0,planned_work_units=1,completed_work_units=1,urgent_planned=1,normal_planned=0,urgent_failure=0,urgent_original_cap_failure=0,normal_failure=0,normal_original_cap_failure=0,urgent_p95_ms=200,energy_j=120+.4*self.f['energy_increment_w']['classification_CPU'],peak_ap_c=30.1)
        raw=dict(row=row,result=dict(ledger=[r]),segments=[dict(start_s=0.,end_s=35.,state='idle'),dict(start_s=35.,end_s=35.4,state='classification_CPU'),dict(start_s=35.4,end_s=120.,state='idle')],curve=[(35,30.),(36,30.1),(120,30.05)])
        return c,raw,q,lanes
    def test_registered_workloads_are_n1_separate_seeds_no_actualduration_arrivals(self):
        self.assertEqual([len(s.cases(z)) for z in (s.TRAIN,s.DEV,s.CONFIRM)],[1408,88,176])
        self.assertFalse(set(s.TRAIN)&set(s.DEV+s.CONFIRM))
        self.assertIsNone(s.budget.PROFILES['model']['learning'])
        for case in s.cases(s.DEV):
            self.assertTrue(all(q['work_units']==1 for q in case['requests']))
            if case['family'].startswith('release_'):
                offset=int(case['family'][-3:])/100
                for d,c in zip(case['requests'][::2],case['requests'][1::2]):self.assertAlmostEqual((c['arrival_ns']-d['arrival_ns'])/1e9,offset,delta=.010001)
    def test_phaseaware_scaled_estimate_and_unknown_not_actualrelease(self):
        c,_,q,lanes=self.fixture();d=dict(q,id='D',task='detection',priority='normal',arrival_ns=35e9,deadline_offset_ns=6e9)
        ds=a.phase_estimate(c.estimates,d,'CPU');now=35e9+ds[0]+max(0.,ds[1]-50e6)
        q=dict(q,arrival_ns=now);lanes['CPU']=dict(request=d,phase='EXECUTING',since=35e9+ds[0],dispatch=35e9)
        e=a.bank([q],lanes,now,c.estimates);x=c.encode([q],lanes,now,e)
        self.assertEqual(x['state'].shape,(226,));self.assertEqual(x['state'][220],1.)
        self.assertAlmostEqual(float(x['state'][218]),(50e6+sum(ds[2:]))/150e6,places=5)
        waits=[i for i,v in enumerate(e['actions']) if v and v['kind']=='resource_wait' and e['mask'][i]]
        self.assertTrue(waits);self.assertTrue(any(v and v['kind']=='single' and e['mask'][i] for i,v in enumerate(e['actions'])))
        late=now+ds[1]+1;e=a.bank([q],lanes,late,c.estimates);x=c.encode([q],lanes,late,e)
        self.assertEqual(float(x['state'][218]),0.);self.assertEqual(float(x['state'][221]),1.)
    def test_labels_dense_urgent_and_event_tail_boundary(self):
        c,raw,_,_=self.fixture()
        f,costs,valid,_=label.targets(c,raw,120,'BASE_DELTA',copy.deepcopy(raw))
        np.testing.assert_array_equal(f[0]['target'][[0,1,2,9]],np.zeros(4,np.float32))
        f,_,_,_=label.targets(c,raw,120,'URGENT_HOLD',copy.deepcopy(raw))
        self.assertAlmostEqual(float(f[0]['target'][0]),-.2/1.5,places=6)
        self.assertEqual(label.urgent_area(raw,35.4e9),0.)
        self.assertAlmostEqual(label.future_tail(raw,35e9,100),1.)
        self.assertEqual(label.future_tail(raw,35.2e9,100),0.)
        missing=copy.deepcopy(raw);missing['row']['urgent_p95_ms']=None
        with self.assertRaises(ValueError):label.targets(c,raw,120,'TAIL_EXCESS',missing)
    def test_signed_tail_excess_and_censor_missingresponse(self):
        c,ref,_,_=self.fixture();raw=copy.deepcopy(ref)
        raw['result']['ledger'][0]['response_ns']=.3e9;raw['result']['ledger'][0]['output_ready_ns']=35.3e9
        raw['row']['urgent_p95_ms']=300
        _,costs,_,_=label.targets(c,raw,120,'TAIL_EXCESS',ref)
        self.assertAlmostEqual(float(costs[8]),1.,places=6)
        _,costs,_,_=label.targets(c,ref,120,'TAIL_EXCESS',raw)
        self.assertEqual(float(costs[8]),0.)
        censored=copy.deepcopy(raw);del censored['result']['ledger'][0]['response_ns']
        self.assertGreater(label.future_tail(censored,35e9,200),100)
    def test_no_label_greedy_eft_forecast_online_and_schema_fresh(self):
        c,_,q,lanes=self.fixture()
        with patch.object(label,'targets',side_effect=AssertionError('offline label inpolicy')),patch.object(controls,'greedy_action',side_effect=AssertionError('benchmark inpolicy')),patch.object(s.oldstudy.mobile,'eft',side_effect=AssertionError('EFT')):
            for arm in a.ARMS:
                net=rl.ActorCritic(arm);agent=a.Controller(self.f,self.initial,net,True,coupling=arm)
                self.assertIsNotNone(agent({},[q],lanes,35e9,{},None,None)['selected'])
                self.assertEqual(agent.stats['fallback'],0)
        self.assertNotEqual(a.SCHEMA,old.SCHEMA)
        l=rl.Learner(77,dict(arm='BASE_DELTA',schema=a.SCHEMA,sequencing='ATC'))
        with self.assertRaises(ValueError):rl.Learner.from_snapshot(dict(l.snapshot(),schema=old.SCHEMA),l.dependencies)
    def test_critic_only_does_not_change_actor_encoder(self):
        c,raw,_,_=self.fixture();frames,costs,valid,_=label.targets(c,raw,120,'URGENT_HOLD',raw)
        for f in frames:f['mask'][:]=False;f['mask'][f['action']]=True
        l=rl.Learner(77,dict(arm='URGENT_HOLD',schema=a.SCHEMA,sequencing='ATC'))
        before=copy.deepcopy(l.network.state_dict())
        for _ in range(8):l.add(frames,costs,valid,raw['row'])
        self.assertTrue(l.logs[-1]['critic_only'])
        for k,v in before.items():
            if k.startswith(('actor.','candidate.','state.')):self.assertTrue(torch.equal(v,l.network.state_dict()[k]),k)
        self.assertTrue(any(not torch.equal(v,l.network.state_dict()[k]) for k,v in before.items() if k.startswith(('critic.','value_state.'))))
    def test_conditional_service_gate_still_checks_original_and_p95(self):
        _,raw,_,_=self.fixture();r=dict(raw['row'],condition=0,primary=True)
        self.assertTrue(s.eligible([r],[r]));self.assertFalse(s.eligible([dict(r,urgent_p95_ms=201)],[r]))
        self.assertFalse(s.eligible([dict(r,urgent_original_cap_failure=1)],[r]))

if __name__=='__main__':unittest.main()
