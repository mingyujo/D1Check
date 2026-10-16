"""Network/algebra/archive checks on explicit tensors, no environment episodes."""
import copy
import random
import tempfile
from pathlib import Path
import unittest
import numpy as np
import torch
from tools import d1_edd_ect_residual_ppo as p


def fake_batch():
    # Software fixture tensors, not a simulator workload or a learning episode.
    data=[]
    for i in range(12):
        state=np.arange(109,dtype=np.float32)/109+i/100
        candidates=np.zeros((32,68),dtype=np.float32);candidates[0,0]=1.;candidates[1,1]=1.
        mask=np.zeros(32,dtype=bool);mask[:2]=True
        base=np.zeros(32,dtype=bool);base[0]=True
        data.append(dict(state=state,candidates=candidates,mask=mask,base=base,action=i%2,
            logprob=float(np.log(.9 if i%2==0 else .1)),value=np.zeros(6,dtype=np.float32),
            target=np.array([.1,.2,0.,0.,0.,.01],dtype=np.float32),valid=np.ones(6,dtype=bool),informative=True))
    return [dict(data=data,costs=np.array([.2,0.,0.,0.,.01]),valid=np.ones(6,dtype=bool))]


class PPO(unittest.TestCase):
    def test_zero_residual_exact_prior_and_forced_forward_rng(self):
        p.seed_all(11);net=p.ActorCritic()
        state=torch.zeros((1,109));cand=torch.zeros((1,32,68));mask=torch.zeros((1,32),dtype=torch.bool);mask[0,:4]=True
        base=torch.zeros_like(mask);base[0,0]=True
        before=torch.get_rng_state().clone();dist,_=net(state,cand,mask,base)
        self.assertAlmostEqual(float(dist.probs[0,0]),.9,places=6)
        self.assertTrue(torch.equal(before,torch.get_rng_state()))
        mask[0,1:]=False;dist,_=net(state,cand,mask,base)
        self.assertEqual(float(dist.probs[0,0]),1.)

    def test_partial_batch_resume_preserves_next_update_and_rng(self):
        p.seed_all(23);net=p.ActorCritic();opt=torch.optim.Adam(net.parameters(),lr=.0003,eps=1e-5)
        multipliers=[1.,10.,10.,10.,10.];batch=fake_batch()
        p.update(net,opt,batch,multipliers)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'terminal.pt'
            state=dict(cursor=7,batch=copy.deepcopy(batch),multipliers=multipliers.copy(),
                references={'sealed':'fixture'},consumption=0,selection=[],pending_stop=True)
            p.archive(path,net,opt,state)
            p.update(net,opt,batch,multipliers)
            expected=p.model_hash(net);draws=(random.random(),float(np.random.random()),float(torch.rand(1)))
            loaded,loaded_opt,s=p.restore(path)
            self.assertEqual(s['cursor'],7);self.assertEqual(len(s['batch']),1)
            p.update(loaded,loaded_opt,s['batch'],s['multipliers'])
            self.assertEqual(expected,p.model_hash(loaded));self.assertEqual(s['multipliers'],multipliers)
            self.assertEqual(draws,(random.random(),float(np.random.random()),float(torch.rand(1))))
            for value in loaded_opt.state.values():self.assertTrue({'step','exp_avg','exp_avg_sq'}<=set(value))

    def test_null_heat_energy_and_zero_informative_steps(self):
        p.seed_all(37);net=p.ActorCritic();opt=torch.optim.Adam(net.parameters(),lr=.0003,eps=1e-5)
        batch=fake_batch()
        for row in batch[0]['data']:
            row['valid'][:2]=False;row['informative']=False
        batch[0]['valid'][:2]=False
        actor=copy.deepcopy(net.actor.state_dict());multipliers=[1.,10.,10.,10.,10.]
        result=p.update(net,opt,batch,multipliers)
        self.assertEqual(result['informative'],0);self.assertEqual(multipliers[0],1.)
        self.assertTrue(all(torch.equal(actor[k],v) for k,v in net.actor.state_dict().items()))


if __name__=='__main__':unittest.main()
