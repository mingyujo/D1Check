"""Raw-free per-class causality, new ABI, SLA labels and exact learner resume."""
import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import torch
from tools import d1_hetero_direct_policy as a
from tools import d1_hetero_direct_ppo as rl
from tools import d1_hetero_direct_study as s
from tools import d1_hetero_mobile_rules as mobile
from tools import d1_list_candidate_rl_training as native
from tools.test_d1_atc_direct import ticket as old_ticket,lanes

def ticket(id,task='classification',at=35.,ordinal=0,cls=0,deadline=None):
    q=old_ticket(id,task,at,ordinal);q['service_class']=cls
    if deadline:q['deadline_offset_ns']=deadline
    return q

class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.f,i,_=a.hybrid.load();cls.initial=i['initial'];cls.est=a.public_estimates(cls.f)

    def test_class_estimate_rank_counterexample_and_shapes(self):
        qs=[ticket('older',cls=2,deadline=750_000_000),ticket('later',at=35.05,ordinal=1,deadline=750_000_000)]
        edd=a.bank(qs,lanes(),35.05e9,self.est,sequencing='EDD');atc=a.bank(qs,lanes(),35.05e9,self.est,sequencing='ATC')
        self.assertEqual(edd['ranked_ids'][0],'older');self.assertEqual(atc['ranked_ids'][0],'later')
        c=a.Controller(self.f,self.initial);enc=c.encode(qs,lanes(),35.05e9,atc)
        self.assertEqual(enc['state'].shape,(206,));self.assertEqual(enc['candidates'].shape,(32,49))
        self.assertAlmostEqual(float(enc['state'][198]),.125)
        self.assertAlmostEqual(a.durations(self.est,qs[0],'CPU')[0]-a.durations(self.est,qs[1],'CPU')[0],.075)

    def test_private_realization_independent_of_public_requests(self):
        case=dict(arrival_seed=881210101,family='burst',factor='both')
        qs=s.tickets(case);before=copy.deepcopy(qs)
        x=s.realized_vectors(self.f,qs,881000201);y=s.realized_vectors(self.f,qs,881000203)
        self.assertEqual(before,qs);self.assertNotEqual(s.a.native.digest(x),s.a.native.digest(y))
        self.assertEqual(set(qs[0]),a.TICKET_FIELDS)
        for q in qs:
            if q['task']!='classification' or q['service_class']==0:continue
            adds=[]
            for b in a.p.backends(q):
                row=x['per_request'][q['id']][b][0]['durations_ns']
                possible=[a.p.profile(self.f,c)[a.p.key(q,b)] for c in ('short_context','mean','long_context')]
                matched=next(p for p in possible if p[0]==row[0] and p[2:]==row[2:])
                adds.append(row[1]-matched[1])
            self.assertAlmostEqual(adds[0],adds[1],places=4)

    def test_available_fifo_and_future_traps(self):
        d=ticket('owner','detection',cls=2);head=ticket('head','detection',ordinal=1);tail=ticket('tail',ordinal=2)
        l=lanes();l['CPU'].update(request=d,phase='WORKER_RELEASED',dispatch=35e9)
        self.assertFalse(a.legal(dict(request_id='tail',backend='CPU'),[head,tail],l))
        with patch.object(a.p.Controller,'rollout',side_effect=AssertionError('future')),patch.object(a.p.Controller,'place',side_effect=AssertionError('future')),patch.object(a.hybrid,'costs',side_effect=AssertionError('future')):
            self.assertIsNone(mobile.Controller(self.f,self.initial,'FIFO_EFT')(None,[head,tail],l,35.01e9,{},None,None)['selected'])
            self.assertEqual(mobile.Controller(self.f,self.initial,'FIFO_READY')(None,[head,tail],l,35.01e9,{},None,None)['selected']['request_id'],'tail')
        c=a.Controller(self.f,self.initial)
        leaked=ticket('leak');leaked['realized_duration_ns']=1
        with self.assertRaises(ValueError):c(None,[leaked],lanes(),35e9,{},None,None)

    def test_eight_targets_loss_and_exact_adam_rng_restore(self):
        learner=rl.Learner(101,dict(sequencing='ATC'));c=learner.controller(self.f,self.initial)
        c(None,[ticket('a'),ticket('b',ordinal=1,cls=1)],lanes(),35e9,{},None,None)
        row=dict(completed=2,planned=2,peak_ap_c=31.,energy_j=140.,urgent_p95_ms=100.,urgent_planned=2,normal_planned=0,incomplete=0,urgent_failure=0,normal_failure=0,declared_urgent_failure=1,declared_normal_failure=0)
        frames,costs,valid,_=rl.targets(c,row,[(35,30.),(36,31.)],120.)
        self.assertEqual(costs.shape,(7,));self.assertEqual(valid.shape,(8,));self.assertEqual(float(costs[0]),2.)
        self.assertEqual(float(costs[5]),.5)
        batch=rl.prepare(learner.network,[frames]*8,learner.multipliers)
        with torch.no_grad():
            parts=[native.minibatch_losses(learner.network,batch,torch.arange(i,i+4),learner.settings)['loss'] for i in (0,4)]
        torch.testing.assert_close(sum(parts),batch['reference']['loss'],rtol=1e-5,atol=1e-5)
        for _ in range(10):learner.add(frames,costs,valid,row)
        self.assertEqual(len(learner.logs),1);self.assertEqual(len(learner.pending),2);self.assertTrue(learner.optimizer.state)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'state.pt';learner.save(path);restored=rl.Learner.load(path,learner.dependencies)
            self.assertEqual(s.payload_digest(learner.snapshot()),s.payload_digest(restored.snapshot()))
            torch.testing.assert_close(torch.randperm(32,generator=learner.shuffle_rng),torch.randperm(32,generator=restored.shuffle_rng))
            torch.testing.assert_close(torch.multinomial(torch.tensor([.1,.9]),8,True,generator=learner.action_rng),torch.multinomial(torch.tensor([.1,.9]),8,True,generator=restored.action_rng))

    def test_scenario_seed_sets_and_independent_factors(self):
        self.assertFalse(set(s.TRAIN)&set(s.DEV));self.assertFalse(set(s.TRAIN)&set(s.CONFIRM));self.assertFalse(set(s.DEV)&set(s.CONFIRM))
        self.assertEqual(len(s.cases(s.DEV)),32);self.assertEqual(len(s.cases(s.CONFIRM)),64)
        base=dict(arrival_seed=881210101,family='queue')
        fixed=s.tickets(dict(base,factor='fixed'));time=s.tickets(dict(base,factor='time'));deadline=s.tickets(dict(base,factor='deadline'));both=s.tickets(dict(base,factor='both'))
        self.assertEqual([q['service_class'] for q in time],[q['service_class'] for q in both])
        self.assertEqual([q['deadline_offset_ns'] for q in deadline],[q['deadline_offset_ns'] for q in both])
        self.assertEqual([q['arrival_ns'] for q in fixed],[q['arrival_ns'] for q in both])
        self.assertTrue(all(q['service_class']==0 for q in deadline))

if __name__=='__main__':unittest.main()
