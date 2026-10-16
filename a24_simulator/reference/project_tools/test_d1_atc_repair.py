import copy,json,unittest
import numpy as np
import torch
from tools import d1_atc_repair_policy as a
from tools import d1_atc_repair_ppo as rl
from tools import d1_atc_repair_study as s
from tools import d1_atc_repair_targets as target
from tools import d1_queue_hetero_policy as old

def lanes():return {b:dict(request=None,phase='AVAILABLE',since=35e9,dispatch=None) for b in ('CPU','GPU')}
def q(i,n=1,task='detection'):
    return dict(id=str(i),ordinal=i,task=task,priority='normal' if task=='detection' else 'urgent',arrival_ns=35e9+i*1000,deadline_offset_ns=2e9 if task=='detection' else .5e9,work_units=n)
class Repair(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.f,init,_=a.hybrid.load();cls.initial=init['initial']
    def test_teacher_prior_and_same_physical_actions(self):
        c=a.Controller(self.f,self.initial);qs=[q(i,3 if i<4 else 1) for i in range(8)];ls=lanes()
        e=a.bank(qs,ls,39e9,c.estimates);o=old.bank(qs,ls,39e9,c.estimates)
        self.assertEqual(e['actions'],o['actions']);np.testing.assert_array_equal(e['mask'],o['mask'])
        self.assertEqual(e['base'],c.rule(e,qs,ls));self.assertNotEqual(e['base'],o['base'])
        x=c.encode(qs,ls,39e9,e);self.assertEqual(x['state'].shape,(218,))
        self.assertEqual(np.sum(x['candidates'][:,52]*x['mask']),1)
        net=rl.ActorCritic();dist,_=net(torch.from_numpy(x['state'])[None],torch.from_numpy(x['candidates'])[None],torch.from_numpy(x['mask'])[None])
        self.assertEqual(int(dist.logits.argmax()),e['base']);self.assertAlmostEqual(float(dist.probs[0,e['base']]),.9,places=6)
        choice=torch.multinomial(dist.probs[0],1,generator=torch.Generator().manual_seed(17))
        self.assertAlmostEqual(float(dist.log_prob(choice)),float(torch.log(dist.probs[0,choice])),places=6)
    def test_public_history_no_future_counts(self):
        c=a.Controller(self.f,self.initial);qs=[q(0,1,'classification')]
        c.on_public_event(dict(at_ns=35e9,event_seq=1,request_id='0',backend=None,event='arrived',ticket=qs[0]))
        e=a.bank(qs,lanes(),35.6e9,c.estimates);x=c.encode(qs,lanes(),35.6e9,e)
        self.assertEqual(list(x['state'][24:28]),[1,0,0,0])
        future=q(1,1,'classification');future['arrival_ns']=38e9
        with self.assertRaises(ValueError):c.on_public_event(dict(at_ns=35.6e9,event_seq=2,request_id='1',backend=None,event='arrived',ticket=future))
    def test_old_schema_rejected_and_new_resume(self):
        d=dict(arm='ANCHOR',sequencing='ATC',schema=a.SCHEMA)
        l=rl.Learner(17,d);r=rl.Learner.from_snapshot(l.snapshot(),d)
        self.assertEqual(s.payload_digest(l.snapshot()),s.payload_digest(r.snapshot()))
        with self.assertRaises(ValueError):rl.Learner.from_snapshot(dict(l.snapshot(),schema=old.SCHEMA),d)
    def fake_episode(self):
        c=a.Controller(self.f,self.initial);qs=[q(0,1,'classification')];qs[0]['arrival_ns']=35e9
        e=a.bank(qs,lanes(),35e9,c.estimates);x=c.encode(qs,lanes(),35e9,e)
        c.snapshots=[dict(x,now_ns=t,chosen=e['base'],actor_eligible=False) for t in (35e9,36e9,37e9)]
        r=dict(qs[0],status='succeeded',backend='CPU',dispatch_ns=35e9,execution_start_ns=35.1e9,output_ready_ns=35.6e9,persist_complete_ns=35.7e9,worker_release_ns=35.8e9,lane_available_ns=35.9e9,response_ns=.6e9)
        extra=.9*self.f['energy_increment_w']['classification_CPU']
        row=dict(planned=1,completed=1,incomplete=0,planned_work_units=1,completed_work_units=1,urgent_planned=1,normal_planned=0,urgent_failure=1,urgent_original_cap_failure=0,normal_failure=0,normal_original_cap_failure=0,energy_j=120+extra,peak_ap_c=31,urgent_p95_ms=600)
        raw=dict(row=row,result=dict(ledger=[r]),segments=[dict(start_s=0,end_s=35,state='idle'),dict(start_s=35,end_s=35.9,state='classification_CPU'),dict(start_s=35.9,end_s=120,state='idle')],curve=[(35,30),(36,31),(120,30.5)])
        return c,raw
    def test_causal_past_breach_removed_and_telescope(self):
        c,raw=self.fake_episode();frames,costs,valid,rewards=target.targets(c,raw,120,'CAUSAL')
        self.assertEqual(frames[0]['target'][3],1.)
        self.assertEqual(frames[1]['target'][3],0.)
        self.assertEqual(frames[2]['target'][3],0.)
        self.assertAlmostEqual(float(frames[0]['target'][0]),float(rewards.sum()),places=6)
        self.assertEqual(float(costs[6]),0);self.assertEqual(float(costs[7]),0);self.assertTrue(valid.all())
    def test_response_and_available_separate_incomplete_prefix(self):
        c,raw=self.fake_episode();r=raw['result']['ledger'][0];r['status']='unfinished';r.pop('lane_available_ns')
        raw['row'].update(completed=0,incomplete=1,completed_work_units=0,energy_j=None,peak_ap_c=None)
        frames,costs,valid,_=target.targets(c,raw,120,'CAUSAL')
        self.assertEqual(float(costs[6]),1);self.assertEqual(float(costs[7]),1);self.assertTrue(valid.all())
        self.assertAlmostEqual(float(costs[8]),.6/1.5,places=6)
        for f in frames:rl.validate_frames([[f]])
    def test_anchor_same_v3_objective_pad_and_invalid(self):
        c,raw=self.fake_episode();frames,costs,valid,_=target.targets(c,raw,120,'ANCHOR')
        self.assertEqual(len(costs),9);self.assertFalse(valid[6:].any());self.assertEqual(frames[0]['target'].shape,(10,))
        rl.validate_frames([frames])
    def test_native_loss_partition_and_consumed_partial_restore(self):
        c,raw=self.fake_episode();d=dict(arm='CAUSAL',sequencing='ATC',schema=a.SCHEMA)
        l=rl.Learner(19,d)
        e=a.bank([q(0,1,'classification')],lanes(),35e9,c.estimates);x=c.encode([q(0,1,'classification')],lanes(),35e9,e)
        with torch.no_grad():dist,v=l.network(torch.from_numpy(x['state'])[None],torch.from_numpy(x['candidates'])[None],torch.from_numpy(x['mask'])[None])
        frame=dict(x,action=e['base'],informative=True,logprob=float(dist.log_prob(torch.tensor([e['base']]))),old_value=v[0].numpy(),target=np.array([1,.01,.02,0,0,0,0,0,0,.2],dtype=np.float32),valid=np.ones(10,dtype=bool))
        episodes=[[copy.deepcopy(frame)] for _ in range(8)];batch=rl.prepare(l.network,episodes,l.multipliers)
        full=rl.native.minibatch_losses(l.network,batch,torch.arange(8),l.settings,unbiased_scale=False)['loss']
        pieces=[rl.native.minibatch_losses(l.network,batch,torch.arange(i,i+2),l.settings,unbiased_scale=False)['loss'] for i in range(0,8,2)]
        self.assertAlmostEqual(float(full.detach()),sum(float(z.detach()) for z in pieces),places=5)
        for i in range(9):l.add([copy.deepcopy(frame)],np.zeros(9,dtype=np.float32),np.ones(10,dtype=bool),dict(fallbacks=0))
        self.assertTrue(l.optimizer.state_dict()['state']);self.assertEqual(len(l.pending),1)
        torch.randperm(13,generator=l.shuffle_rng);torch.multinomial(torch.tensor([.4,.6]),5,True,generator=l.action_rng)
        snap=l.snapshot();r=rl.Learner.from_snapshot(snap,d);self.assertEqual(s.payload_digest(snap),s.payload_digest(r.snapshot()))
        self.assertTrue(torch.equal(torch.randperm(13,generator=l.shuffle_rng),torch.randperm(13,generator=r.shuffle_rng)))
    def test_capacity_diagnostic_not_real_phone_bound(self):
        v=s.POOL['detection_CPU_normal'];p2=min(sum(r['durations_ns'])+r['durations_ns'][1] for r in v)/1e9
        self.assertGreater(96*p2,85);self.assertEqual(96-int(85//p2),26)

if __name__=='__main__':unittest.main()
