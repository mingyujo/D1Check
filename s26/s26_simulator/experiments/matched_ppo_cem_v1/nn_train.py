"""Same32parameter actor; episodic-return PPO-Clip without critic or teacher."""
import copy,hashlib
import numpy as np
import torch
from torch import nn
torch.set_num_threads(1)
class Net(nn.Module):
    def __init__(self):
        super().__init__();self.weight=nn.Parameter(torch.randn(32)*.03);self.temperature=1.
    def forward(self,x,mask):
        raw=torch.tanh(x)@self.weight
        logits=3*torch.tanh(raw/3)/self.temperature
        return logits.masked_fill(~mask,-1e9),x.new_zeros((len(x),1))
def digest(net):
    h=hashlib.sha256()
    for name,t in sorted(net.state_dict().items()):h.update(name.encode());h.update(t.detach().numpy().tobytes())
    return h.hexdigest()
class Learner:
    def __init__(self,seed):
        self.seed=seed
        with torch.random.fork_rng(devices=[]):torch.manual_seed(seed);self.net=Net()
        self.action_rng=torch.Generator().manual_seed(seed+10000)
        self.optimizer=torch.optim.Adam(self.net.parameters(),lr=.03,eps=1e-5)
        self.episodes=self.updates=self.steps=0;self.logs=[];self.pending=[]
    def choose(self,bank,collect):
        x=np.asarray(bank['x'],np.float32);mask=np.asarray(bank['mask'],bool)
        assert x.shape==(27,32) and mask.any() and np.isfinite(x).all()
        with torch.no_grad():
            logits,_=self.net(torch.from_numpy(x)[None],torch.from_numpy(mask)[None]);lp=logits.log_softmax(-1);i=int(torch.multinomial(lp.exp()[0],1,generator=self.action_rng))
        return i,dict(x=x.copy(),mask=mask.copy(),scores=bank['scores'].copy(),index=i,old_logp=float(lp[0,i]),value=0.,collect=collect,learn_actor=int(mask.sum())>1,network_sha256=digest(self.net))
    def add(self,frames,costs):
        assert frames and all(f['collect'] and f['network_sha256']==digest(self.net) for f in frames)
        cost=float(np.asarray(costs).sum(0)@np.array([1.,1.,1.,1.,3.]))
        assert np.isfinite(cost);self.pending.append(dict(frames=frames,cost=cost,mix=self.current_mix,label=self.current_label));self.episodes+=1
    def update(self):
        assert len(self.pending)==24
        costs=np.array([ep['cost'] for ep in self.pending]);adv=np.empty(24)
        for mix in [.5,.75]:
            ix=[i for i,ep in enumerate(self.pending) if ep['mix']==mix];assert len(ix)==12
            adv[ix]=-(costs[ix]-(costs[ix].sum()-costs[ix])/11)
        scale=max(float(np.sqrt(np.mean(adv**2))),1e-6);adv/=scale
        fs=[];aa=[]
        for i,ep in enumerate(self.pending):fs.extend(ep['frames']);aa.extend([adv[i]]*len(ep['frames']))
        x=torch.tensor(np.stack([f['x'] for f in fs]));mask=torch.tensor(np.stack([f['mask'] for f in fs]));actions=torch.tensor([f['index'] for f in fs]);old=torch.tensor([f['old_logp'] for f in fs]);valid=torch.tensor([f['learn_actor'] for f in fs]);a=torch.tensor(aa,dtype=torch.float32)
        stats=[];slices=list(range(0,len(fs),256));valid_n=int(valid.sum())
        for epoch in range(4):
            self.optimizer.zero_grad();loss_total=0.;entropy_total=0.
            for lo in slices:
                sl=slice(lo,lo+256);logits,_=self.net(x[sl],mask[sl]);lp=logits.log_softmax(-1);selected=lp.gather(1,actions[sl,None]).squeeze(1);ratio=(selected-old[sl]).exp();vf=valid[sl]
                surrogate=torch.minimum(ratio*a[sl],ratio.clamp(.8,1.2)*a[sl]);entropy=-(lp.exp()*lp).sum(-1)
                loss=-(surrogate*vf).sum()/24-.001*(entropy*vf).sum()/max(1,valid_n)
                assert torch.isfinite(loss);loss.backward();loss_total+=float(loss.detach());entropy_total+=float((entropy*vf).sum().detach())
            grad=float(nn.utils.clip_grad_norm_(self.net.parameters(),1.));self.optimizer.step();self.steps+=1
            kl_sum=0.;clip_n=0
            with torch.no_grad():
                for lo in slices:
                    sl=slice(lo,lo+256);logits,_=self.net(x[sl],mask[sl]);lp=logits.log_softmax(-1);d=lp.gather(1,actions[sl,None]).squeeze(1)-old[sl];vf=valid[sl];ratio=d.exp();kl_sum+=float(((ratio-1-d)*vf).sum());clip_n+=int(((abs(ratio-1)>.2)&vf).sum())
            kl=kl_sum/max(1,valid_n);stats.append(dict(epoch=epoch,loss=loss_total,entropy=entropy_total/max(1,valid_n),KL=kl,clip_fraction=clip_n/max(1,valid_n),gradient_norm_before_clip=grad))
            if kl>.02:break
        self.updates+=1
        log=dict(update=self.updates,episodes=self.episodes,Adam_steps=self.steps,frames=len(fs),actor_frames=valid_n,costs=costs.tolist(),advantages=adv.tolist(),advantage_RMS_before_scaling=scale,labels=[ep['label'] for ep in self.pending],stats=stats,network_sha256=digest(self.net),critic=False,teacher_targets=0)
        self.logs.append(log);self.pending=[];return log
    def snapshot(self):
        return copy.deepcopy(dict(version='MATCHED32_EPISODIC_PPO_V1',seed=self.seed,network=self.net.state_dict(),optimizer=self.optimizer.state_dict(),action_rng=self.action_rng.get_state(),episodes=self.episodes,updates=self.updates,steps=self.steps,logs=self.logs,pending_labels=[p['label'] for p in self.pending],temperature=self.net.temperature,network_sha256=digest(self.net)))
    def restore(self,s):
        assert s['version']=='MATCHED32_EPISODIC_PPO_V1' and not s['pending_labels']
        self.net.load_state_dict(s['network']);self.optimizer.load_state_dict(s['optimizer']);self.action_rng.set_state(s['action_rng']);self.net.temperature=s['temperature'];self.pending=[]
        for k in ['episodes','updates','steps','logs']:setattr(self,k,copy.deepcopy(s[k]))
        assert digest(self.net)==s['network_sha256']
