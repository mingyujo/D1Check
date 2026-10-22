"""Matched 48-parameter actor, episodic CEM and critic-free PPO.
Sampling RNG is independent of parameter-search RNG; no teacher warm start.
"""
import copy,hashlib
import numpy as np
import torch
from torch import nn
torch.set_num_threads(1)
class Net(nn.Module):
    def __init__(self,weight):
        super().__init__();self.weight=nn.Parameter(torch.tensor(weight,dtype=torch.float32))
    def forward(self,x,mask):
        return (3*torch.tanh((torch.tanh(x)@self.weight)/3)).masked_fill(~mask,-1e9)
def digest(net):return hashlib.sha256(net.weight.detach().numpy().tobytes()).hexdigest()
class Learner:
    def __init__(self,seed,weight=None):
        self.seed=seed;self.net=Net(np.random.default_rng(seed).normal(0,.03,48) if weight is None else weight)
        self.action_rng=np.random.default_rng(seed+10000);self.optimizer=torch.optim.Adam(self.net.parameters(),lr=.03,eps=1e-5)
        self.episodes=self.updates=self.steps=0;self.logs=[];self.pending=[]
    def reseed(self,seed):self.action_rng=np.random.default_rng(seed)
    def choose(self,bank,collect):
        x=np.asarray(bank['x'],np.float32);mask=np.asarray(bank['mask'],bool)
        assert x.shape==(36,48) and mask.any() and np.isfinite(x).all()
        with torch.no_grad():lp=self.net(torch.from_numpy(x),torch.from_numpy(mask)).log_softmax(-1);p=lp.exp().double().numpy();p=p/p.sum()
        u=float(self.action_rng.random());i=min(int(np.searchsorted(np.cumsum(p),u,side='right')),35);assert mask[i]
        return i,dict(x=x.copy(),mask=mask.copy(),scores=bank['scores'].copy(),index=i,old_logp=float(lp[i]),uniform=u,collect=collect,learn_actor=int(mask.sum())>1,network_sha256=digest(self.net))
    def add(self,frames,cost,mix,label):
        assert frames and all(f['collect'] and f['network_sha256']==digest(self.net) for f in frames)
        self.pending.append(dict(frames=frames,cost=float(cost),mix=mix,label=label));self.episodes+=1
    def update(self):
        assert len(self.pending)==16
        costs=np.array([ep['cost'] for ep in self.pending]);adv=np.empty(16)
        for mix in (0,1):
            ix=[i for i,e in enumerate(self.pending) if e['mix']==mix];assert len(ix)==8
            adv[ix]=-(costs[ix]-(costs[ix].sum()-costs[ix])/7)
        scale=max(float(np.sqrt(np.mean(adv**2))),1e-6);adv/=scale
        fs=[];aa=[]
        for i,e in enumerate(self.pending):fs.extend(e['frames']);aa.extend([adv[i]]*len(e['frames']))
        x=torch.tensor(np.stack([f['x'] for f in fs]));mask=torch.tensor(np.stack([f['mask'] for f in fs]));actions=torch.tensor([f['index'] for f in fs]);old=torch.tensor([f['old_logp'] for f in fs]);valid=torch.tensor([f['learn_actor'] for f in fs]);a=torch.tensor(aa,dtype=torch.float32);vn=int(valid.sum());stats=[]
        for epoch in range(4):
            self.optimizer.zero_grad();loss_total=0.
            for lo in range(0,len(fs),256):
                sl=slice(lo,lo+256);lp=self.net(x[sl],mask[sl]).log_softmax(-1);sel=lp.gather(1,actions[sl,None]).squeeze(1);ratio=(sel-old[sl]).exp();sur=torch.minimum(ratio*a[sl],ratio.clamp(.8,1.2)*a[sl]);ent=-(lp.exp()*lp).sum(-1);v=valid[sl]
                loss=-(sur*v).sum()/16-.001*(ent*v).sum()/max(1,vn);assert torch.isfinite(loss);loss.backward();loss_total+=float(loss.detach())
            gradient=self.net.weight.grad.detach().clone();gn=float(nn.utils.clip_grad_norm_(self.net.parameters(),1.));self.optimizer.step();self.steps+=1
            kl=0.;clipped=0
            with torch.no_grad():
                for lo in range(0,len(fs),256):
                    sl=slice(lo,lo+256);lp=self.net(x[sl],mask[sl]).log_softmax(-1);d=lp.gather(1,actions[sl,None]).squeeze(1)-old[sl];r=d.exp();v=valid[sl];kl+=float(((r-1-d)*v).sum());clipped+=int(((abs(r-1)>.2)&v).sum())
            kl/=max(1,vn);stats.append(dict(epoch=epoch,loss=loss_total,KL=kl,clip_fraction=clipped/max(1,vn),gradient_before_clip=gradient.numpy().tolist(),gradient_norm_before_clip=gn,weight_after=self.net.weight.detach().numpy().tolist()))
            if kl>.02:break
        self.updates+=1;log=dict(update=self.updates,episodes=self.episodes,Adam_steps=self.steps,frames=len(fs),actor_frames=vn,costs=costs.tolist(),advantages=adv.tolist(),advantage_RMS_before_scaling=scale,labels=[e['label'] for e in self.pending],stats=stats,network_sha256=digest(self.net),critic=False,teacher_targets=0);self.logs.append(log);self.pending=[];return log
    def snapshot(self):
        return copy.deepcopy(dict(version='A24_MATCHED48_V1',seed=self.seed,network=self.net.state_dict(),optimizer=self.optimizer.state_dict(),action_rng=self.action_rng.bit_generator.state,episodes=self.episodes,updates=self.updates,steps=self.steps,logs=self.logs,pending_labels=[p['label'] for p in self.pending],network_sha256=digest(self.net)))
    def restore(self,s):
        assert s['version']=='A24_MATCHED48_V1' and not s['pending_labels'];self.net.load_state_dict(s['network']);self.optimizer.load_state_dict(s['optimizer']);self.action_rng.bit_generator.state=copy.deepcopy(s['action_rng']);self.pending=[]
        for k in ('episodes','updates','steps','logs'):setattr(self,k,copy.deepcopy(s[k]))
        assert digest(self.net)==s['network_sha256']
def cem_update(mu,sigma,candidates,costs):
    order=np.argsort(costs,kind='stable')[:3];elites=candidates[order];weights=np.array([.5,.3,.2]);mean=weights@elites;var=weights@((elites-mean)**2)
    return .3*mu+.7*mean,np.maximum(.2,np.sqrt(.8*sigma**2+.2*var)),order
