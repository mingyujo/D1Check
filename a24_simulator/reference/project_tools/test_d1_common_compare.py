"""No environments: comparable opportunity, deadline semantics and variable-K PPO."""
import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import torch
from tools import d1_common_compare_policy as a
from tools import d1_common_compare_ppo as rl
from tools import d1_common_compare_study as s
from tools import d1_list_candidate_rl_training as native
from tools.test_d1_atc_direct import ticket as old,lanes

def ticket(id,task='classification',at=35.,order=0,cls=0,deadline=None):
    q=old(id,task,at,order);q['service_class']=cls
    if deadline:q['deadline_offset_ns']=deadline
    return q

class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.f,i,_=a.hybrid.load();cls.initial=i['initial'];cls.est=a.public_estimates(cls.f)

    def test_full_queue_identical_primary_masks_and_overflow(self):
        qs=[ticket(str(i),'classification' if i%2 else 'detection',35+i*.001,i,i%3) for i in range(20)]
        banks=[a.bank(qs,lanes(),35.1e9,self.est,sequencing=mode) for mode in (*s.BASES,'ORDER')]
        self.assertEqual({q['id'] for q in banks[0]['slots'] if q},{q['id'] for q in qs})
        for b in banks[1:]:np.testing.assert_array_equal(b['mask'],banks[0]['mask'])
        enc=a.Controller(self.f,self.initial).encode(qs,lanes(),35.1e9,banks[0])
        self.assertEqual(enc['state'].shape,(510,));self.assertEqual(enc['candidates'].shape,(30,42))
        with self.assertRaises(ValueError):a.bank(qs+[ticket(str(i),order=i) for i in range(20,25)],lanes(),36e9,self.est)

    def test_operating_wait_separate_physics_and_joint_effect(self):
        d=ticket('owner','detection');q=ticket('ready')
        l=lanes();l['CPU'].update(request=d,phase='WORKER_RELEASED',dispatch=35e9)
        e=a.bank([q],l,35.05e9,self.est,sequencing='ORDER')
        wait=next(i for i,x in enumerate(e['actions']) if x['kind']=='resource_wait')
        self.assertTrue(e['physical_mask'][wait]);self.assertFalse(e['mask'][wait])
        ready=next(i for i,m in enumerate(e['mask']) if m);self.assertEqual(e['actions'][ready]['jobs'][0]['backend'],'GPU')
        order=a.bank([q],lanes(),35e9,self.est,sequencing='ORDER');joint=a.bank([q],lanes(),35e9,self.est,sequencing='JOINT')
        self.assertEqual(sum(order['mask']),1);self.assertEqual(sum(joint['mask']),2)
        self.assertFalse(a.legal(dict(request_id=q['id'],backend='CPU'),[q],l))

    def test_atc_rank_counterexample_current_path_and_no_forecast(self):
        qs=[ticket('long',cls=2,deadline=500_000_000),ticket('short',at=35.05,order=1,deadline=500_000_000)]
        edd=a.bank(qs,lanes(),35.05e9,self.est,sequencing='EDD');atc=a.bank(qs,lanes(),35.05e9,self.est,sequencing='ATC')
        self.assertEqual(edd['ranked_ids'][0],'long');self.assertEqual(atc['ranked_ids'][0],'short')
        c=a.Controller(self.f,self.initial,mode=a.RULE,sequencing='FIFO_READY')
        with patch.object(a.p.Controller,'rollout',side_effect=AssertionError('forecast')),patch.object(a.p.Controller,'place',side_effect=AssertionError('forecast')),patch.object(a.hybrid,'costs',side_effect=AssertionError('forecast')):
            c(None,qs,lanes(),35.05e9,{},None,None)
        self.assertFalse(c.snapshots[0]['raw_rank_same'])
        owner=ticket('D','detection');l=lanes();l['CPU'].update(request=owner,phase='EXECUTING',dispatch=35e9)
        e=a.bank(qs,l,35.05e9,self.est,sequencing='ATC')
        expected=a.atc_scores(qs,self.est,35.05e9,paths={q['id']:'GPU' for q in qs})
        self.assertEqual(e['scores'],expected)

    def test_hidden_empirical_residual_and_paired_factors(self):
        base=dict(arrival_seed=891210101,family='burst')
        qs=s.tickets(dict(base,factor='io_variable'));before=copy.deepcopy(qs)
        x=s.realized_vectors(self.f,qs,891000201,base['arrival_seed']);y=s.realized_vectors(self.f,qs,891000203,base['arrival_seed'])
        self.assertEqual(qs,before);self.assertNotEqual(a.native.digest(x),a.native.digest(y))
        plain=s.tickets(dict(base,factor='measured_variable'))
        self.assertEqual([q['deadline_offset_ns'] for q in plain],[q['deadline_offset_ns'] for q in qs])
        self.assertTrue(all(q['service_class']==0 for q in plain))
        self.assertTrue(all(q['deadline_offset_ns']<=(1.5e9 if q['priority']=='urgent' else 6e9) for q in qs))
        self.assertEqual(a.measured.FULL_SHA,a.measured.SHA)

    def test_variable_k_padding_loss_and_adam_resume(self):
        l=rl.Learner(211,dict(sequencing='JOINT'));episodes=[];costs=[];valids=[];rowbase=dict(planned=2,completed=2,incomplete=0,weighted_miss_rate=.1,weighted_normalized_tardiness=.2,energy_j=140.)
        for i in range(10):
            c=l.controller(self.f,self.initial);qs=[ticket('a')]+([ticket('b',order=1,cls=1)] if i%2 else [])
            c(None,qs,lanes(),35e9,{},None,None)
            row=dict(rowbase,weighted_miss_rate=.05*(i%3))
            frames,cost,v,_=rl.targets(c,row,[],120.)
            episodes.append(frames);costs.append(cost);valids.append(v)
        self.assertNotEqual(len(episodes[0][0]['mask']),len(episodes[1][0]['mask']))
        prepared=rl.prepare(l.network,episodes[:8],l.multipliers)
        with torch.no_grad():
            parts=[native.minibatch_losses(l.network,prepared,torch.arange(i,i+4),l.settings)['loss'] for i in (0,4)]
        torch.testing.assert_close(sum(parts),prepared['reference']['loss'],rtol=1e-5,atol=1e-5)
        for e,cost,v in zip(episodes,costs,valids):l.add(e,cost,v,rowbase)
        self.assertEqual(len(l.logs),1);self.assertEqual(len(l.pending),2);self.assertTrue(l.optimizer.state)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'l.pt';l.save(path);restored=rl.Learner.load(path,l.dependencies)
            self.assertEqual(s.payload_digest(l.snapshot()),s.payload_digest(restored.snapshot()))
            torch.testing.assert_close(torch.randperm(64,generator=l.shuffle_rng),torch.randperm(64,generator=restored.shuffle_rng))

    def test_one_primary_deadline_and_response_not_resource_end(self):
        q=ticket('late',deadline=500_000_000);q.update(response_ns=800_000_000,status='succeeded')
        r=s.response_metrics([q]);self.assertEqual(r['urgent_failure'],1);self.assertEqual(r['original_urgent_failure'],0)
        self.assertAlmostEqual(r['weighted_normalized_tardiness'],.6)
        q.update(response_ns=400_000_000,status='unfinished');r=s.response_metrics([q])
        self.assertEqual(r['urgent_failure'],0)
        del q['response_ns'];r=s.response_metrics([q]);self.assertEqual(r['urgent_failure'],1);self.assertTrue(r['tardiness_is_lower_bound'])

if __name__=='__main__':unittest.main()
