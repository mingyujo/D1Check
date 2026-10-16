"""No simulation: full-queue contracts, encoding, error handling and PPO loss."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import torch
from tools import d1_queue_direct_policy as a
from tools import d1_queue_direct_ppo as rl
from tools import d1_queue_mobile_rules as mobile
from tools import d1_list_candidate_rl_training as native
from tools.test_d1_atc_direct import ticket,lanes

class Fixed(torch.nn.Module):
    schema_id=a.SCHEMA
    def __init__(self,slot):super().__init__();self.slot=slot
    def forward(self,state,candidates,mask):
        v=torch.zeros((len(state),a.SLOTS));v[:,self.slot]=100
        return torch.distributions.Categorical(logits=v.masked_fill(~mask,-torch.inf)),torch.zeros((len(state),6))

class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f,i,_=a.hybrid.load();cls.initial=i['initial'];cls.means=a.p.profile(cls.f)
    def test_full_queue_and_request_binding(self):
        qs=[ticket('C','classification'),ticket('C2','classification',35.1,1),ticket('D','detection',35.2,2)]
        e=a.bank(qs,lanes(),35.3e9,self.means)
        self.assertEqual(set(q['id'] for q in e['slots'] if q),{'C','C2','D'})
        self.assertTrue(a.legal(dict(request_id='C2',backend='GPU'),qs,lanes()))
        c=a.Controller(self.f,self.initial,network=Fixed(3));enc=c.encode(qs,lanes(),35.3e9,e)
        self.assertEqual(enc['state'].shape,(198,));self.assertEqual(enc['candidates'].shape,(32,49))
        self.assertFalse(np.array_equal(enc['candidates'][1],enc['candidates'][3]))
        self.assertEqual(c(None,qs,lanes(),35.3e9,{},None,None)['selected']['request_id'],'C2')
    def test_bounds_padding_unknown_estimates(self):
        qs=[ticket(str(i),'classification' if i%2 else 'detection',35+i*.001,i) for i in range(100)]
        e=a.bank(qs,lanes(),36e9,self.means)
        self.assertLessEqual(sum(q is not None for q in e['slots']),8)
        self.assertLessEqual(sum(x is not None for x in e['actions']),29)
        self.assertTrue(all(not m for x,m in zip(e['actions'],e['mask']) if x is None))
        q=qs[1];est=copy.deepcopy(self.means);est[a.p.key(q,'CPU')]=[float('nan')]*5
        self.assertTrue(a.legal(dict(request_id=q['id'],backend='CPU'),qs,lanes()))
        enc=a.Controller(self.f,self.initial).encode(qs,lanes(),36e9,a.bank(qs,lanes(),36e9,est))
        self.assertTrue(np.isfinite(enc['candidates']).all())
    def test_available_and_resource_wait(self):
        q,d=ticket('C','classification'),ticket('D','detection')
        l=lanes();l['CPU'].update(request=d,phase='WORKER_RELEASED',dispatch=35e9)
        self.assertFalse(a.legal(dict(request_id='C',backend='CPU'),[q],l))
        self.assertTrue(a.legal(dict(request_id='C',backend='GPU'),[q],l))
        e=a.bank([q],l,35.01e9,self.means)
        self.assertEqual(sum(m and x['kind']=='resource_wait' for x,m in zip(e['actions'],e['mask'])),1)
        self.assertFalse(a.legal(dict(request_id='D',backend='GPU'),[d],lanes()))
    def test_causal_and_schema_fallback(self):
        qs=[ticket('C','classification'),ticket('D','detection',ordinal=1)]
        c=a.Controller(self.f,self.initial,network=Fixed(1));c.network.schema_id='old'
        with patch.object(a.p.Controller,'rollout',side_effect=AssertionError('future')),patch.object(a.p.Controller,'place',side_effect=AssertionError('placement')),patch.object(a.hybrid,'costs',side_effect=AssertionError('AP/J')):
            out=c(None,qs,lanes(),35e9,{},None,None)
        self.assertIsNotNone(out['selected']);self.assertEqual(c.stats['fallback'],1)
        enc=c.encode(qs,lanes(),35e9,a.bank(qs,lanes(),35e9,self.means));c.h=999;c.hybrid_state['slow']=999
        np.testing.assert_array_equal(enc['state'],c.encode(qs,lanes(),35e9,a.bank(qs,lanes(),35e9,self.means))['state'])
    def test_fifo_hol_and_ready_control(self):
        d,d2,c=ticket('running','detection'),ticket('head','detection',ordinal=1),ticket('tail','classification',ordinal=2)
        l=lanes();l['CPU'].update(request=d,phase='EXECUTING',dispatch=35e9)
        for role in ('FIFO_FIXED','FIFO_EFT'):
            agent=mobile.Controller(self.f,self.initial,role)
            self.assertIsNone(agent(None,[d2,c],l,35.001e9,{},None,None)['selected'])
        ready=mobile.Controller(self.f,self.initial,'FIFO_READY')
        self.assertEqual(ready(None,[d2,c],l,35.001e9,{},None,None)['selected']['request_id'],'tail')
    def test_interval_targets_and_checkpoint(self):
        c=a.Controller(self.f,self.initial,network=Fixed(0))
        c(None,[ticket('C','classification')],lanes(),35e9,{},None,None)
        row=dict(completed=1,planned=1,peak_ap_c=31.,energy_j=2.,urgent_p95_ms=100.,urgent_planned=1,normal_planned=0,incomplete=0,urgent_failure=0,normal_failure=0)
        frames,costs,valid,rewards=rl.targets(c,row,[(35,30.),(36,31.)],1.)
        self.assertAlmostEqual(rewards.sum(),-1.)
        dep=dict(sequencing='ATC');learner=rl.Learner(41,dep)
        for f in frames:f.update(old_value=np.zeros(6,dtype=np.float32),logprob=-.69,informative=True)
        learner.add(frames,costs,valid,row)
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/'state.pt';learner.save(file);restored=rl.Learner.load(file,dep)
            self.assertEqual(restored.episodes,1);self.assertEqual(len(restored.pending),1)
            self.assertTrue(torch.equal(learner.action_rng.get_state(),restored.action_rng.get_state()))
        batch=rl.prepare(learner.network,[frames]*8,learner.multipliers)
        self.assertEqual(batch['sampled_choices'],8)

    def test_adam_rng_resume_and_loss_partition(self):
        learner=rl.Learner(41,dict(sequencing='ATC'))
        c=learner.controller(self.f,self.initial)
        c(None,[ticket('C','classification')],lanes(),35e9,{},None,None)
        row=dict(completed=1,planned=1,peak_ap_c=31.,energy_j=2.,urgent_p95_ms=100.,urgent_planned=1,normal_planned=0,incomplete=0,urgent_failure=0,normal_failure=0)
        frames,costs,valid,_=rl.targets(c,row,[(35,30.),(36,31.)],1.)
        prepared=rl.prepare(learner.network,[frames]*8,learner.multipliers)
        with torch.no_grad():
            ref=prepared['reference']['loss']
            parts=[native.minibatch_losses(learner.network,prepared,torch.arange(i,i+4),learner.settings)['loss'] for i in (0,4)]
        torch.testing.assert_close(sum(parts),ref,rtol=1e-5,atol=1e-5)
        for _ in range(10):learner.add(frames,costs,valid,row)
        self.assertEqual(len(learner.logs),1);self.assertEqual(len(learner.pending),2)
        self.assertTrue(learner.optimizer.state)
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/'state.pt';learner.save(file);restored=rl.Learner.load(file,learner.dependencies)
            self.assertEqual(native.state_digest(learner.snapshot()),native.state_digest(restored.snapshot()))
            torch.testing.assert_close(torch.randperm(16,generator=learner.shuffle_rng),torch.randperm(16,generator=restored.shuffle_rng))
            torch.testing.assert_close(torch.multinomial(torch.tensor([.2,.8]),8,replacement=True,generator=learner.action_rng),torch.multinomial(torch.tensor([.2,.8]),8,replacement=True,generator=restored.action_rng))

    def test_two_interval_pair_binding_and_duplicate(self):
        qs=[ticket('C','classification'),ticket('D','detection',35.1,1)]
        c=a.Controller(self.f,self.initial,network=Fixed(3));e=a.bank(qs,lanes(),35.2e9,self.means)
        enc=c.encode(qs,lanes(),35.2e9,e)
        self.assertEqual(enc['candidates'][3,11],1.)
        self.assertEqual(enc['candidates'][3,34],1.)
        self.assertNotEqual(enc['candidates'][3,19],enc['candidates'][3,41])
        c(None,qs,lanes(),35.2e9,{},None,None)
        s=copy.deepcopy(c.snapshots[0]);s['now_ns']=36e9;c.snapshots.append(s)
        row=dict(completed=2,planned=2,peak_ap_c=33.,energy_j=2.,urgent_p95_ms=100.,urgent_planned=1,normal_planned=1,incomplete=0,urgent_failure=0,normal_failure=0)
        _,_,_,r=rl.targets(c,row,[(35,30.),(36,31.),(37,33.)],1.)
        np.testing.assert_array_equal(r,[-1.,-2.])
        # The second commit may select a detection behind the oldest detection.
        older=ticket('oldD','detection',35.,2);current=lanes()
        c.pending=dict(first=dict(request_id='C',backend='GPU'),second=dict(request_id='D',backend='CPU'),at_ns=35.2e9)
        c.receipts['C']=dict(at_ns=35.2e9);current['GPU'].update(request=qs[0],phase='ASSIGNED',dispatch=35.2e9)
        self.assertEqual(c(None,[older,qs[1]],current,35.2e9,{},None,None)['selected']['request_id'],'D')
        c.pending=None
        c(None,[older],current,35.3e9,{},None,None)
        self.assertEqual(c(None,[older],current,35.3e9,{},None,None)['reason'],'duplicate_decision_revision')

    def test_mobile_no_forecast_unknown_overrun(self):
        q=ticket('C','classification');d=ticket('D','detection')
        l=lanes();l['CPU'].update(request=d,phase='WORKER_RELEASED',dispatch=35e9)
        self.assertIsNone(mobile.release(l['CPU'],self.means,'CPU',100e9))
        agent=mobile.Controller(self.f,self.initial,'FIFO_EFT')
        with patch.object(a.p.Controller,'rollout',side_effect=AssertionError('queue')),patch.object(a.p.Controller,'place',side_effect=AssertionError('queue')),patch.object(a.hybrid,'costs',side_effect=AssertionError('future')):
            self.assertEqual(agent(None,[q],l,35.1e9,{},None,None)['selected']['backend'],'GPU')

if __name__=='__main__':unittest.main()
