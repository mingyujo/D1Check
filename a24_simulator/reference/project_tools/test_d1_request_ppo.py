import copy
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import torch
from tools import d1_request_ppo as r
from tools.test_d1_empirical_request_policy import empty


class PPOTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r.seed_all(101);cls.frozen,case=r.p.inputs(r.p.BUNDLE);cls.initial=case['initial']
        cls.tickets=r.old.workload('queue',70001)

    def network(self):
        r.seed_all(202);return r.ActorCritic(85)

    def episode(self,network=None,tickets=None,deterministic=False):
        return r.simulate(self.frozen,self.initial,tickets or self.tickets,'mean',network or self.network(),deterministic=deterministic)

    def test_split_and_contract(self):
        s=r.specification();self.assertEqual(json.loads(r.CONTRACT.read_text(encoding='utf8')),s)
        train=set(range(s['train_trace_seeds'][0],s['train_trace_seeds'][1]+1))
        val=set(s['validation_trace_seeds']);test=set(s['test_trace_seeds'])
        self.assertFalse(train&val or train&test or val&test)
        self.assertEqual(3*256*8,6144);self.assertEqual(8*4*3*8,768)

    def test_real_entry_phase_ownership_and_causal_dimension(self):
        row,result,c,extra=self.episode()
        self.assertEqual(len(c.rollout[0]['obs']),85);self.assertEqual(row['planned'],24)
        self.assertTrue(all(np.isfinite(x['obs']).all() for x in c.rollout))
        for b in ('CPU','GPU'):
            jobs=sorted((x for x in result['ledger'] if x.get('backend')==b),key=lambda x:x['dispatch_ns'])
            self.assertTrue(all(a['lane_available_ns']<=b['dispatch_ns'] for a,b in zip(jobs,jobs[1:])))
        for d in result['decisions']:
            if d.get('action')=='WAIT':
                q=next(x for x in self.tickets if x['id']==d['head_request_id'])
                self.assertLessEqual(d['wait_until_ns']-q['arrival_ns'],2e9+1)

    def test_mask_applies_sampling_and_log_probability(self):
        net=self.network();obs=torch.zeros((100,85));mask=torch.tensor([[False,True,False]]*100)
        distribution,_=net(obs,mask)
        self.assertTrue(torch.all(distribution.sample()==1))
        self.assertTrue(torch.allclose(distribution.log_prob(torch.ones(100,dtype=torch.long)),torch.zeros(100)))
        with self.assertRaises(ValueError):net(obs,torch.zeros_like(mask))

    def test_accounting_rewards_sum_matches_episode(self):
        row,result,c,extra=self.episode()
        reward=r.rewards(c,result,extra,self.initial,self.frozen).sum(0)
        self.assertAlmostEqual(-reward[0]*10,row['energy_j'],places=4)
        self.assertAlmostEqual(reward[1],row['urgent_service_failure']/row['urgent_n'],places=6)
        self.assertAlmostEqual(reward[2],row['normal_service_failure']/row['normal_n'],places=6)
        self.assertAlmostEqual(reward[3]*100,row['thermal_degree_seconds'],places=4)

    def test_gae_terminal_no_cross_episode_bootstrap(self):
        rewards=np.array([[1,2,3,4],[5,6,7,8]],dtype=np.float32)
        values=np.array([[2,2,2,2],[3,3,3,3]],dtype=np.float32)
        a,ret=r.gae(rewards,values,lam=1.)
        np.testing.assert_allclose(ret,np.array([[6,8,10,12],[5,6,7,8]]))
        np.testing.assert_allclose(a[-1],rewards[-1]-values[-1])

    def test_actual_optimizer_changes_weights_finitely(self):
        net=self.network();row,result,c,extra=self.episode(net)
        data=r.pack([(c,r.rewards(c,result,extra,self.initial,self.frozen))])
        before=r.model_hash(net);opt=torch.optim.Adam(net.parameters(),lr=3e-4,eps=1e-5)
        stats=r.optimize(net,opt,data,np.array([10.,10.,1.]))
        self.assertNotEqual(before,r.model_hash(net));self.assertGreater(stats['minibatch_updates'],0)
        self.assertTrue(all(torch.isfinite(x).all() for x in net.parameters()))

    def test_known_bandit_learns_without_invalid_action(self):
        net=self.network();opt=torch.optim.Adam(net.parameters(),lr=3e-4,eps=1e-5)
        obs=torch.zeros((128,85));mask=torch.tensor([[True,True,False]]*128)
        before=net(obs,mask)[0].probs[0,1].item()
        for _ in range(50):
            with torch.no_grad():
                dist,val=net(obs,mask);actions=dist.sample();logprob=dist.log_prob(actions)
            returns=torch.zeros((128,4));returns[:,0]=(actions==1).float()
            data=dict(obs=obs,mask=mask,actions=actions,old_logprob=logprob,returns=returns,advantages=returns-val)
            r.optimize(net,opt,data,np.zeros(3))
        after=net(obs,mask)[0].probs[0,1].item()
        self.assertGreater(after,before+.3)

    def test_constraint_advantage_penalizes_costly_action(self):
        net=self.network();opt=torch.optim.Adam(net.parameters(),lr=3e-4,eps=1e-5)
        obs=torch.zeros((128,85));mask=torch.tensor([[True,True,False]]*128)
        before=net(obs,mask)[0].probs[0,1].item()
        for _ in range(50):
            with torch.no_grad():
                dist,val=net(obs,mask);actions=dist.sample();logprob=dist.log_prob(actions)
            returns=torch.zeros((128,4));returns[:,1]=(actions==1).float()
            data=dict(obs=obs,mask=mask,actions=actions,old_logprob=logprob,returns=returns,advantages=returns-val)
            r.optimize(net,opt,data,np.array([1.,0.,0.]))
        self.assertLess(net(obs,mask)[0].probs[0,1].item(),before-.3)

    def test_future_ticket_and_private_lane_rejected(self):
        c=r.Controller(self.frozen,self.initial,self.network(),True)
        with self.assertRaises(ValueError):c({},[self.tickets[0]],empty(),34e9,r.settings(),None,None)
        lanes=empty();lanes['CPU']['durations']=[1]
        with self.assertRaises(ValueError):c({},[self.tickets[0]],lanes,35e9,r.settings(),None,None)

    def test_future_mutation_prefix_invariant(self):
        b=copy.deepcopy(self.tickets);b[-1]['arrival_ns']+=3e9
        _,a,_,_=self.episode(deterministic=True);_,b,_,_=self.episode(tickets=b,deterministic=True)
        cutoff=self.tickets[-1]['arrival_ns']
        self.assertEqual([d for d in a['decisions'] if d['now_ns']<cutoff],[d for d in b['decisions'] if d['now_ns']<cutoff])

    def test_export_load_evaluation_no_update(self):
        net=self.network();before=r.model_hash(net)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'actor.json';r.save_actor(path,net);other=r.load_actor(path)
            self.assertEqual(before,r.model_hash(other))
            self.episode(other,deterministic=True)
            self.assertEqual(before,r.model_hash(other))

    def test_aggregate_backlog_not_saturated_at_four(self):
        c=r.Controller(self.frozen,self.initial,self.network(),True)
        a=[dict(x,arrival_ns=35e9) for x in self.tickets[:8]]
        b=[dict(x,arrival_ns=35e9) for x in self.tickets[:16]]
        self.assertFalse(np.array_equal(c.observation(a,empty(),36),c.observation(b,empty(),36)))

    def test_constraint_order_incomplete_cannot_win_by_low_j(self):
        row,result,c,extra=self.episode()
        a=copy.deepcopy(row);a['energy_j']=-1000;a['completed']-=1;a['normal_service_failure']+=1
        self.assertGreater(r.validation_key([a],[row]),r.validation_key([row],[row]))
        json.dumps(r.validation_key([a],[row]),allow_nan=False)
        self.assertEqual(r.p.digest(r.p.BUNDLE/'model.json'),r.p.MODEL_SHA)


if __name__=='__main__':unittest.main()
