"""Fresh masked set-PPO; ATC/cost are inputs, with no fixed action prior.

The small public-model auxiliary loss teaches a starting preference. Its weight
decays; the network's logits alone select actions, with full PPO gradients.
"""
import copy
import hashlib
import math
import numpy as np
import torch
from torch import nn
from dynamics import WEIGHTS
from controller import WIDTH,ACTIONS
torch.set_num_threads(1)


class Net(nn.Module):
    def __init__(self):
        super().__init__()
        self.encode=nn.Sequential(nn.Linear(WIDTH,48),nn.Tanh())
        self.actor=nn.Sequential(nn.Linear(144,64),nn.Tanh(),nn.Linear(64,1))
        self.critic=nn.Sequential(nn.Linear(96,64),nn.Tanh(),nn.Linear(64,5))
        nn.init.zeros_(self.actor[-1].weight);nn.init.zeros_(self.actor[-1].bias)

    def forward(self,x,mask):
        e=self.encode(x);mean=(e*mask[:,:,None]).sum(1)/mask.sum(1,keepdim=True).clamp_min(1)
        maximum=e.masked_fill(~mask[:,:,None],-1e9).max(1).values
        context=torch.cat((mean,maximum),-1)
        logits=self.actor(torch.cat((e,context[:,None,:].expand(-1,ACTIONS,-1)),-1)).squeeze(-1)
        return logits.masked_fill(~mask,-1e9),self.critic(context)


def digest(net):
    h=hashlib.sha256()
    for name,t in sorted(net.state_dict().items()):h.update(name.encode());h.update(t.detach().numpy().tobytes())
    return h.hexdigest()


class Learner:
    def __init__(self,seed):
        self.seed=seed
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed);self.net=Net()
        self.optimizer=torch.optim.Adam(self.net.parameters(),lr=1e-3,eps=1e-5)
        self.action_rng=torch.Generator().manual_seed(seed+10000)
        self.shuffle_rng=torch.Generator().manual_seed(seed+20000)
        self.episodes=self.updates=self.steps=0;self.pending=[];self.logs=[];self.balance=None

    def choose(self,bank,collect):
        x=np.asarray(bank['x'],np.float32);mask=np.asarray(bank['mask'],bool)
        if x.shape!=(ACTIONS,WIDTH) or mask.shape!=(ACTIONS,) or not mask.any() or not np.isfinite(x).all():raise ValueError('Public NN ABI')
        with torch.no_grad():
            logits,value=self.net(torch.from_numpy(x)[None],torch.from_numpy(mask)[None]);logp=logits.log_softmax(-1)
            i=int(torch.multinomial(logp.exp()[0],1,generator=self.action_rng)) if collect else int(logits[0].argmax())
        if not mask[i]:raise ValueError('Neural action masked')
        return i,dict(x=x.copy(),mask=mask.copy(),scores=bank['scores'].copy(),index=i,
            old_logp=float(logp[0,i]),value=value[0].numpy().copy(),collect=collect,
            learn_actor=int(mask.sum())>1,network_sha256=digest(self.net))

    def add(self,frames,costs):
        if not frames or not all(f['collect'] for f in frames):raise ValueError('Only training frames may update')
        if np.asarray(costs).shape!=(len(frames),5) or not np.isfinite(costs).all():raise ValueError('Cost labels')
        if any(f['network_sha256']!=digest(self.net) for f in frames):raise ValueError('On-policy network changed')
        values=np.array([f['value'] for f in frames]);targets=np.cumsum(costs[::-1],axis=0)[::-1].copy()
        adv=np.zeros_like(costs);following=np.zeros(5)
        for i in reversed(range(len(frames))):
            nv=values[i+1] if i+1<len(frames) else np.zeros(5)
            dt=(frames[i+1]['time_ns']-frames[i]['time_ns'])/1e9 if i+1<len(frames) else 0.
            following=costs[i]+nv-values[i]+math.exp(-dt/20.)*following;adv[i]=following
        self.pending.append([dict(f,target=targets[i],adv=adv[i],cost=costs[i]) for i,f in enumerate(frames)])
        self.episodes+=1
        if len(self.pending)==2:self.update()

    def update(self):
        frames=[f for episode in self.pending for f in episode]
        x=torch.from_numpy(np.stack([f['x'] for f in frames]));mask=torch.from_numpy(np.stack([f['mask'] for f in frames]))
        target=torch.tensor(np.stack([f['target'] for f in frames]),dtype=torch.float32)
        action=torch.tensor([f['index'] for f in frames]);old=torch.tensor([f['old_logp'] for f in frames])
        valid=torch.tensor([f['learn_actor'] for f in frames]);scores=torch.tensor(np.stack([f['scores'] for f in frames]))
        component_adv=np.stack([f['adv'] for f in frames]);component_RMS=None
        if self.balance is not None:
            learning=np.array([f['learn_actor'] for f in frames],bool)
            centered=component_adv-component_adv[learning].mean(0) if learning.any() else component_adv
            rms=np.sqrt(np.mean(centered[learning]**2,axis=0)).clip(1e-4) if learning.any() else np.ones(5)
            component_adv=centered/rms
            objective_weights=np.array([1.,1.,*self.balance['dual'],3.])
            component_RMS=rms.tolist()
        else: objective_weights=np.array(WEIGHTS)
        advantage=torch.tensor(-component_adv@objective_weights,dtype=torch.float32)
        if valid.sum()>1:advantage=(advantage-advantage[valid].mean())/advantage[valid].std(unbiased=False).clamp_min(1e-6)
        losses=[];kls=[];aux_weight=(.15 if self.balance is not None else .05)*math.exp(-self.updates/32.)
        stable=self.optimizer.param_groups[0]['lr']<5e-4;stop_minibatch=False
        for epoch in range(4):
            permutation=torch.randperm(len(frames),generator=self.shuffle_rng)
            for ids in permutation.split(256):
                logits,values=self.net(x[ids],mask[ids]);lp=logits.log_softmax(-1)
                selected=lp.gather(1,action[ids,None]).squeeze(1);ratio=(selected-old[ids]).exp()
                surrogate=torch.minimum(ratio*advantage[ids],ratio.clamp(.8,1.2)*advantage[ids])
                actor=-(surrogate*valid[ids]).mean();critic=(values-target[ids]).square().mean()
                entropy=-(lp.exp()*lp).sum(-1)
                teacher=(-8*scores[ids]).masked_fill(~mask[ids],-1e9).softmax(-1)
                auxiliary=-(teacher*lp).sum(-1)
                loss=actor+.5*critic-.03*(entropy*valid[ids]).mean()+aux_weight*(auxiliary*valid[ids]).mean()
                if not torch.isfinite(loss):raise ValueError('Nonfinite PPO loss')
                self.optimizer.zero_grad();loss.backward();nn.utils.clip_grad_norm_(self.net.parameters(),1.);self.optimizer.step();self.steps+=1
                losses.append(float(loss.detach()))
                kl=float(((ratio-1)-(selected-old[ids]))[valid[ids]].mean().detach()) if valid[ids].any() else 0.
                kls.append(kl)
                if stable and kl>.02:stop_minibatch=True;break
            if stop_minibatch or max(kls)>.05:break
        self.updates+=1
        self.logs.append(dict(update=self.updates,episodes=self.episodes,Adam_steps=self.steps,
            frames=len(frames),actor_frames=int(valid.sum()),loss_mean=float(np.mean(losses)),
            max_KL=max(kls),aux_weight=aux_weight,component_RMS=component_RMS,objective_weights=objective_weights.tolist(),network_sha256=digest(self.net)))
        self.pending=[]

    def snapshot(self):
        return copy.deepcopy(dict(version='COUPLED345_SET_PPO_V1',seed=self.seed,network=self.net.state_dict(),
            optimizer=self.optimizer.state_dict(),action_rng=self.action_rng.get_state(),shuffle_rng=self.shuffle_rng.get_state(),
            episodes=self.episodes,updates=self.updates,steps=self.steps,pending=self.pending,logs=self.logs,network_sha256=digest(self.net)))

    def restore(self,snapshot):
        if snapshot['version']!='COUPLED345_SET_PPO_V1':raise ValueError('Checkpoint ABI')
        self.net.load_state_dict(snapshot['network']);self.optimizer.load_state_dict(snapshot['optimizer'])
        self.action_rng.set_state(snapshot['action_rng']);self.shuffle_rng.set_state(snapshot['shuffle_rng'])
        for key in ('episodes','updates','steps','pending','logs'):setattr(self,key,copy.deepcopy(snapshot[key]))
        if digest(self.net)!=snapshot['network_sha256']:raise ValueError('Checkpoint digest')
