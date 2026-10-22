"""Reward-only fresh PPO with fixed scalar utility and independent value network."""
import copy,hashlib,math
import numpy as np
import torch
from torch import nn
from controller import WIDTH,ACTIONS
torch.set_num_threads(1)
WEIGHTS=np.array([1.,1.,1.,1.,3.])

class Net(nn.Module):
    def __init__(self):
        super().__init__()
        self.encode=nn.Sequential(nn.Linear(WIDTH,48),nn.Tanh())
        self.actor=nn.Sequential(nn.Linear(144,64),nn.Tanh(),nn.Linear(64,1))
        self.value_encode=nn.Sequential(nn.Linear(WIDTH,48),nn.Tanh())
        self.critic=nn.Sequential(nn.Linear(97,64),nn.Tanh(),nn.Linear(64,1))
        nn.init.orthogonal_(self.actor[-1].weight,gain=.1);nn.init.zeros_(self.actor[-1].bias)
        nn.init.zeros_(self.critic[-1].weight);nn.init.zeros_(self.critic[-1].bias)
        self.temperature=1.

    @staticmethod
    def pool(e,mask):
        return torch.cat(((e*mask[:,:,None]).sum(1)/mask.sum(1,keepdim=True).clamp_min(1),e.masked_fill(~mask[:,:,None],-1e9).max(1).values),-1)

    def forward(self,x,mask,clock=None):
        e=self.encode(x);context=self.pool(e,mask)
        logits=self.actor(torch.cat((e,context[:,None,:].expand(-1,ACTIONS,-1)),-1)).squeeze(-1)
        if clock is None:clock=x.new_zeros((len(x),1))
        value=self.critic(torch.cat((self.pool(self.value_encode(x),mask),clock.reshape(-1,1)),-1))
        return (logits/self.temperature).masked_fill(~mask,-1e9),value

def digest(net):
    h=hashlib.sha256()
    for name,t in sorted(net.state_dict().items()):h.update(name.encode());h.update(t.detach().numpy().tobytes())
    return h.hexdigest()

class Learner:
    def __init__(self,seed):
        self.seed=seed
        with torch.random.fork_rng(devices=[]):torch.manual_seed(seed);self.net=Net()
        self.actor_params=list(self.net.encode.parameters())+list(self.net.actor.parameters())
        self.critic_params=list(self.net.value_encode.parameters())+list(self.net.critic.parameters())
        self.optimizer=torch.optim.Adam(self.actor_params,lr=.001,eps=1e-5)
        self.value_optimizer=torch.optim.Adam(self.critic_params,lr=.001,eps=1e-5)
        self.action_rng=torch.Generator().manual_seed(seed+10000)
        self.shuffle_rng=torch.Generator().manual_seed(seed+20000)
        self.episodes=self.updates=self.steps=self.value_steps=0;self.pending=[];self.logs=[]

    def choose(self,bank,collect):
        x=np.asarray(bank['x'],np.float32);mask=np.asarray(bank['mask'],bool)
        assert x.shape==(ACTIONS,WIDTH) and mask.any() and np.isfinite(x).all()
        clock=(bank['time_ns']/1e9-35)/200
        with torch.no_grad():
            logits,value=self.net(torch.from_numpy(x)[None],torch.from_numpy(mask)[None],torch.tensor([[clock]],dtype=torch.float32));lp=logits.log_softmax(-1)
            i=int(torch.multinomial(lp.exp()[0],1,generator=self.action_rng))
        return i,dict(x=x.copy(),mask=mask.copy(),scores=bank['scores'].copy(),index=i,old_logp=float(lp[0,i]),value=float(value[0,0]),clock=clock,collect=collect,learn_actor=int(mask.sum())>1,network_sha256=digest(self.net))

    def add(self,frames,costs):
        assert frames and all(f['collect'] and f['network_sha256']==digest(self.net) for f in frames)
        costs=np.asarray(costs);assert costs.shape==(len(frames),5) and np.isfinite(costs).all()
        scalar=costs@WEIGHTS;targets=np.cumsum(scalar[::-1])[::-1].copy();values=np.array([f['value'] for f in frames]);adv=np.zeros(len(frames));following=0.
        for i in reversed(range(len(frames))):
            dt=(frames[i+1]['time_ns']-frames[i]['time_ns'])/1e9 if i+1<len(frames) else 0.
            following=scalar[i]+(values[i+1] if i+1<len(frames) else 0.)-values[i]+math.exp(-dt/5)*following;adv[i]=following
        self.pending.append([dict(f,target=targets[i],adv=adv[i],cost=costs[i]) for i,f in enumerate(frames)])
        self.episodes+=1
        if len(self.pending)==2:self.update()

    def update(self):
        fs=[f for ep in self.pending for f in ep];x=torch.tensor(np.stack([f['x'] for f in fs]));mask=torch.tensor(np.stack([f['mask'] for f in fs]));clock=torch.tensor([f['clock'] for f in fs],dtype=torch.float32)
        target=torch.tensor([f['target'] for f in fs],dtype=torch.float32);action=torch.tensor([f['index'] for f in fs]);old=torch.tensor([f['old_logp'] for f in fs]);valid=torch.tensor([f['learn_actor'] for f in fs])
        advantage=torch.tensor([-f['adv'] for f in fs],dtype=torch.float32);astd=float(advantage[valid].std(unbiased=False))
        if valid.sum()>1:advantage=(advantage-advantage[valid].mean())/max(astd,1e-6)
        entropy_weight=.01-.009*min(1,self.episodes/192);losses=[];kls=[];entropies=[];agn=[];vgn=[];stop=False
        # Critic optimizer has no access to actor parameters; scalar MC target only.
        for epoch in range(4):
            for ids in torch.randperm(len(fs),generator=self.shuffle_rng).split(256):
                _,value=self.net(x[ids],mask[ids],clock[ids]);loss=(value[:,0]-target[ids]).square().mean()
                self.value_optimizer.zero_grad();loss.backward();vgn.append(float(nn.utils.clip_grad_norm_(self.critic_params,1.)));self.value_optimizer.step();self.value_steps+=1
        for epoch in range(4):
            for ids in torch.randperm(len(fs),generator=self.shuffle_rng).split(256):
                logits,_=self.net(x[ids],mask[ids],clock[ids]);lp=logits.log_softmax(-1);selected=lp.gather(1,action[ids,None]).squeeze(1);ratio=(selected-old[ids]).exp();vf=valid[ids]
                surrogate=torch.minimum(ratio*advantage[ids],ratio.clamp(.8,1.2)*advantage[ids]);entropy=-(lp.exp()*lp).sum(-1)
                loss=-(surrogate*vf).sum()/vf.sum().clamp_min(1)-entropy_weight*(entropy*vf).sum()/vf.sum().clamp_min(1)
                assert torch.isfinite(loss)
                self.optimizer.zero_grad();loss.backward();agn.append(float(nn.utils.clip_grad_norm_(self.actor_params,1.)));self.optimizer.step();self.steps+=1
                kl=float(((ratio-1)-(selected-old[ids]))[vf].mean().detach()) if vf.any() else 0.
                losses.append(float(loss.detach()));kls.append(kl);entropies.append(float(entropy[vf].mean().detach()) if vf.any() else 0.)
                if kl>.02:stop=True;break
            if stop:break
        self.updates+=1
        self.logs.append(dict(update=self.updates,episodes=self.episodes,Adam_steps=self.steps,value_steps=self.value_steps,frames=len(fs),actor_frames=int(valid.sum()),loss_mean=float(np.mean(losses)),max_KL=max(kls),entropy=float(np.mean(entropies)),entropy_weight=entropy_weight,advantage_std=astd,actor_gradient_mean=float(np.mean(agn)),critic_gradient_mean=float(np.mean(vgn)),aux_weight=0.,component_RMS=None,objective_weights=WEIGHTS.tolist(),network_sha256=digest(self.net)))
        self.pending=[]

    def snapshot(self):
        return copy.deepcopy(dict(version='SCRATCH_FIXED_SCALAR_SEPARATE_V1',seed=self.seed,network=self.net.state_dict(),optimizer=self.optimizer.state_dict(),value_optimizer=self.value_optimizer.state_dict(),action_rng=self.action_rng.get_state(),shuffle_rng=self.shuffle_rng.get_state(),episodes=self.episodes,updates=self.updates,steps=self.steps,value_steps=self.value_steps,pending=self.pending,logs=self.logs,temperature=self.net.temperature,network_sha256=digest(self.net)))

    def restore(self,s):
        assert s['version']=='SCRATCH_FIXED_SCALAR_SEPARATE_V1'
        self.net.load_state_dict(s['network']);self.net.temperature=s['temperature'];self.optimizer.load_state_dict(s['optimizer']);self.value_optimizer.load_state_dict(s['value_optimizer']);self.action_rng.set_state(s['action_rng']);self.shuffle_rng.set_state(s['shuffle_rng'])
        for key in ['episodes','updates','steps','value_steps','pending','logs']:setattr(self,key,copy.deepcopy(s[key]))
        assert digest(self.net)==s['network_sha256']
