import copy,unittest
import numpy as np
import torch
from unittest.mock import patch
from tools import d1_queue_hetero_policy as a
from tools import d1_queue_hetero_study as s
from tools import d1_queue_hetero_ppo as rl
from tools import d1_queue_hetero_mobile as mobile

def ticket(i,n=1,task='detection'):
    return dict(id=str(i),ordinal=i,task=task,priority='normal' if task=='detection' else 'urgent',arrival_ns=35_000_000_000+i*1000,deadline_offset_ns=2_000_000_000 if task=='detection' else 500_000_000,work_units=n)
def lanes():return {b:dict(request=None,phase='AVAILABLE',since=35e9,dispatch=None) for b in ('CPU','GPU')}

class Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.f,init,_=a.hybrid.load();cls.initial=init['initial']
    def test_abi_and_request_bound_hints(self):
        c=a.Controller(self.f,self.initial);qs=[ticket(0,3),ticket(1,1)];ls=lanes()
        e=a.bank(qs,ls,39e9,c.estimates,sequencing='ATC');x=c.encode(qs,ls,39e9,e)
        self.assertEqual(x['state'].shape,(214,));self.assertEqual(x['candidates'].shape,(32,53))
        self.assertEqual(x['state'][42],1.);self.assertAlmostEqual(float(x['state'][62]),1/3)
        for action,v in zip(e['actions'],x['candidates']):
            if action and action['kind']=='single':
                n=next(q['work_units'] for q in qs if q['id']==action['jobs'][0]['request_id'])
                self.assertAlmostEqual(float(v[26]),n/3)
        net=rl.ActorCritic();net(torch.from_numpy(x['state'])[None],torch.from_numpy(x['candidates'])[None],torch.from_numpy(x['mask'])[None])
    def test_rank_difference_and_real_bank_difference(self):
        c=a.Controller(self.f,self.initial);qs=[ticket(i,3 if i<4 else 1) for i in range(8)]
        atc=a.bank(qs,lanes(),39e9,c.estimates,sequencing='ATC');edd=a.bank(qs,lanes(),39e9,c.estimates,sequencing='EDD')
        self.assertNotEqual(atc['ranked_ids'],edd['ranked_ids'])
        self.assertNotEqual({q['id'] for q in atc['slots'] if q},{q['id'] for q in edd['slots'] if q})
    def test_observed_execution_block_unscale(self):
        c=a.Controller(self.f,self.initial);q=ticket(0,3);key=a.p.key(q,'CPU');before=np.array(c.estimates[key]);seq=0
        def event(kind,t,ticket_=None):
            nonlocal seq
            seq+=1;e=dict(at_ns=t,event_seq=seq,request_id=q['id'],backend=None if kind=='arrived' else 'CPU',event=kind)
            if ticket_:e['ticket']=ticket_
            c.on_public_event(e)
        event('arrived',35e9,q);event('dispatch_ns',35e9)
        ds=[1e6,300e6,2e6,3e6,4e6];t=35e9
        for kind,d in zip(a.FIELDS,ds):t+=d;event(kind,t)
        normalized=np.array([1e6,100e6,2e6,3e6,4e6])
        np.testing.assert_allclose(c.estimates[key],.9*before+.1*normalized)
        np.testing.assert_allclose(a.phase_estimate(c.estimates,q,'CPU'),np.array(c.estimates[key])*[1,3,1,1,1])
    def test_matched_batch_work_and_stricter_due(self):
        for family in s.FAMILIES:
            uniform=s.requests(family,s.DEV[0],'batch_uniform2');variable=s.requests(family,s.DEV[0],'batch_variable')
            for task in ('classification','detection'):
                self.assertEqual(sum(q['work_units'] for q in uniform if q['task']==task),sum(q['work_units'] for q in variable if q['task']==task))
            for q in variable:self.assertLessEqual(q['deadline_offset_ns'],1.5e9 if q['priority']=='urgent' else 6e9)
    def test_realizations_private_intact_and_keyed(self):
        q=s.requests('low',s.DEV[0],'batch_variable');v=s.realizations(q,s.DEV[0]);self.assertEqual(v,s.realizations(list(reversed(q)),s.DEV[0]))
        for request in q:
            for b,samples in v['requests'][request['id']].items():
                sources={x['source_request_id']:x['durations_ns'] for x in s.POOL[a.p.key(request,b)]}
                for row in samples:
                    expected=list(sources[row['source_request_id']]);expected[1]*=request['work_units']
                    self.assertEqual(row['durations_ns'],expected)
        c=a.Controller(self.f,self.initial)
        q[0]['realized_duration']=1
        with self.assertRaises(ValueError):c(None,q,lanes(),39e9,None,None,None)
    def test_actual_ownership_supported_wait_and_eft_owner_scaling(self):
        c=a.Controller(self.f,self.initial);q=ticket(0,3,'classification');l=lanes();l['CPU']=dict(request=q,phase='OUTPUT_READY',since=35e9,dispatch=35e9)
        self.assertFalse(a.legal(dict(request_id='1',backend='CPU'),[ticket(1)],l))
        self.assertFalse(a.legal(dict(request_id='1',backend='GPU'),[ticket(1)],lanes()))
        end=mobile.release(dict(l['CPU'],phase='EXECUTING'),c.estimates,'CPU',35e9)
        self.assertAlmostEqual(end,35e9+sum(a.phase_estimate(c.estimates,q,'CPU')))
    def test_future_forecast_traps(self):
        c=a.Controller(self.f,self.initial);q=[ticket(0,2)]
        with patch.object(a.p.Controller,'rollout',side_effect=AssertionError('future')),patch.object(a.p.Controller,'place',side_effect=AssertionError('future')),patch.object(a.hybrid,'costs',side_effect=AssertionError('future')):
            result=c({},q,lanes(),35e9,a.external.settings(),None,None)
        self.assertIsNotNone(result['selected'])
    def test_energy100_scale_and_fresh_resume(self):
        c=a.Controller(self.f,self.initial);row=dict(planned=1,completed=1,peak_ap_c=31,energy_j=220,incomplete=0,urgent_planned=1,normal_planned=0,urgent_failure=0,normal_failure=0,urgent_p95_ms=500)
        _,costs,_,_=rl.targets(c,row,[(35,30),(180,31)],120)
        self.assertEqual(float(costs[0]),1.)
        deps=dict(sequencing='ATC',schema=a.SCHEMA,study='rawfree-test')
        learner=rl.Learner(901,deps);snap=learner.snapshot();snap['action_rng']=learner.action_rng.get_state();restored=rl.Learner.from_snapshot(snap,deps)
        self.assertEqual(s.payload_digest(restored.snapshot()),s.payload_digest(snap))
        with self.assertRaises(ValueError):rl.Learner.from_snapshot(dict(snap,schema='old'),deps)

if __name__=='__main__':unittest.main()
