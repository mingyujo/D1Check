"""Fresh S26 ABI/service objective. Native PPO weighted clipping math reused."""
import copy
import hashlib
import os
from dataclasses import dataclass,asdict
from pathlib import Path
import numpy as np
import torch
from torch import nn
from tools import d1_s26_npu_policy as p
from tools import d1_s26_npu_engine as e

OBJECTIVE='SERVICE_ONLY_V1'
@dataclass(frozen=True)
class Settings:
    episodes_per_update:int=8
    epochs:int=4
    minibatch_frames:int=256
    learning_rate:float=.0003
    adam_eps:float=1e-5
    clip:float=.2
    value_coefficient:float=.5
    entropy_coefficient:float=.01
    gradient_clip:float=.5
    target_kl:float=.03

class ActorCritic(nn.Module):
    schema_id=p.SCHEMA
    def __init__(self):
        super().__init__()
        self.state=nn.Sequential(nn.Linear(p.STATE_DIM,64),nn.Tanh(),nn.Linear(64,64),nn.Tanh())
        self.candidate=nn.Sequential(nn.Linear(p.ACTION_DIM,32),nn.Tanh(),nn.Linear(32,32),nn.Tanh())
        self.actor=nn.Sequential(nn.Linear(96,64),nn.Tanh(),nn.Linear(64,1));self.critic=nn.Linear(64,1)
        for layer in self.modules():
            if isinstance(layer,nn.Linear):nn.init.orthogonal_(layer.weight,2**.5);nn.init.zeros_(layer.bias)
        nn.init.zeros_(self.actor[-1].weight);nn.init.zeros_(self.actor[-1].bias)
    def forward(self,state,candidates,mask):
        if state.shape[-1]!=p.STATE_DIM or candidates.shape[-2:]!=(p.SLOTS,p.ACTION_DIM) or mask.shape[-1]!=p.SLOTS or not mask.any(-1).all():raise ValueError('S26 actor ABI/mask')
        h=self.state(state);c=self.candidate(candidates)
        logits=self.actor(torch.cat((h[:,None,:].expand(-1,c.shape[1],-1),c),-1)).squeeze(-1)
        return torch.distributions.Categorical(logits=logits.masked_fill(~mask,-torch.inf)),self.critic(h)

def targets(controller,result):
    frames=copy.deepcopy(controller.frames);ledger=result['ledger'];n=len(ledger);nu=sum(r['priority']=='urgent' for r in ledger);nn=n-nu
    if not frames:raise ValueError('no rollout')
    rewards=np.zeros(len(frames),dtype=np.float64)
    times=np.array([f['now_ns'] for f in frames])
    for r in ledger:
        cost=e.request_cost(r,n,nu,nn)
        at=r.get('response_at_ns',e.HORIZON)
        index=max(0,min(len(frames)-1,int(np.searchsorted(times,at,side='right'))-1))
        rewards[index]-=cost
    returns=np.cumsum(rewards[::-1])[::-1]
    if abs(-rewards.sum()-result['metrics']['service_cost'])>1e-8:raise ValueError('reward telescope')
    for f,ret in zip(frames,returns):f.update(target=np.array([ret],dtype=np.float32),valid=np.array([True]))
    return frames

def prepare(network,episodes):
    fs=[f for episode in episodes for f in episode];n=len(fs);b=len(episodes)
    if not fs:raise ValueError('empty batch')
    for f in fs:
        for k,shape in [('state',(p.STATE_DIM,)),('candidates',(p.SLOTS,p.ACTION_DIM)),('mask',(p.SLOTS,)),('target',(1,)),('valid',(1,))]:
            if f[k].shape!=shape:raise ValueError('rollout ABI '+k)
        if not f['mask'][f['action']] or not np.isfinite(f['state']).all() or not np.isfinite(f['target']).all():raise ValueError('invalid rollout')
    d={k:torch.from_numpy(np.stack([f[k] for f in fs])) for k in ('state','candidates','mask','target','valid')}
    d['action']=torch.tensor([f['action'] for f in fs]);d['old_log']=torch.tensor([f['logprob'] or 0. for f in fs])
    info=torch.tensor([bool(f['informative']) for f in fs]);d['informative']=info
    # Retain values from collection. Sole-choice frames have no actor weight.
    with torch.no_grad():_,now_values=network(d['state'],d['candidates'],d['mask'])
    old=torch.tensor([f['old_value'] if f['old_value'] is not None else float(now_values[i,0]) for i,f in enumerate(fs)])
    combined=d['target'][:,0]-old
    aw=torch.zeros(n);vw=torch.zeros(n);ew=torch.zeros(n);kw=torch.zeros(n);means=[];seconds=[];cursor=0
    for episode in episodes:
        sl=slice(cursor,cursor+len(episode));cursor+=len(episode);ii=info[sl];count=int(ii.sum())
        vw[sl]=1/(b*len(episode))
        if count:
            aw[sl]=ii.float()/b;ew[sl]=ii.float()/(b*count);kw[sl]=ii.float()/count
            means.append(combined[sl][ii].mean());seconds.append(combined[sl][ii].square().mean())
    center=torch.stack(means).mean();denom=(torch.stack(seconds).mean()-center.square()).clamp(min=0).sqrt()+1e-8
    d.update(combined=(combined-center)/denom,actor_weight=aw,value_weight=vw,entropy_weight=ew,kl_weight=kw/len(means))
    return dict(tensors=d,n=n,normalization=dict(center=float(center),denominator=float(denom)))

def minibatch_losses(network,prepared,indices,settings=Settings(),*,unbiased_scale=False):
    """Same weighted partition loss as d1_list_candidate_rl_training.minibatch_losses."""
    indices=torch.as_tensor(indices,dtype=torch.long)
    if not len(indices):raise ValueError('empty minibatch')
    d=prepared['tensors'];dist,values=network(d['state'][indices],d['candidates'][indices],d['mask'][indices])
    logprob=dist.log_prob(d['action'][indices]);ratio=(logprob-d['old_log'][indices]).exp();advantage=d['combined'][indices]
    surrogate=torch.minimum(ratio*advantage,ratio.clamp(1-settings.clip,1+settings.clip)*advantage)
    actor=-(surrogate*d['actor_weight'][indices]).sum();valid=d['valid'][indices]
    per_frame=((values-d['target'][indices]).square()*valid).sum(-1)/valid.sum(-1).clamp(min=1)
    critic=(per_frame*d['value_weight'][indices]).sum();entropy=(dist.entropy()*d['entropy_weight'][indices]).sum()
    scale=prepared['n']/len(indices) if unbiased_scale else 1.
    return dict(loss=(actor+settings.value_coefficient*critic-settings.entropy_coefficient*entropy)*scale,actor=actor*scale,critic=critic*scale,entropy=entropy*scale)

def canonical(obj):
    if isinstance(obj,torch.Tensor):return dict(dtype=str(obj.dtype),shape=list(obj.shape),sha=hashlib.sha256(obj.detach().cpu().contiguous().numpy().tobytes()).hexdigest())
    if isinstance(obj,np.ndarray):return dict(dtype=str(obj.dtype),shape=list(obj.shape),sha=hashlib.sha256(obj.tobytes()).hexdigest())
    if isinstance(obj,dict):return {str(k):canonical(v) for k,v in obj.items()}
    if isinstance(obj,(tuple,list)):return [canonical(v) for v in obj]
    if isinstance(obj,np.generic):return obj.item()
    return obj

class Learner:
    def __init__(self,seed,dependencies):
        torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
        self.seed=int(seed);self.dependencies=copy.deepcopy(dependencies);self.settings=Settings()
        with torch.random.fork_rng():torch.manual_seed(seed);self.network=ActorCritic()
        self.action_rng=torch.Generator().manual_seed(seed+10000);self.shuffle_rng=torch.Generator().manual_seed(seed+20000)
        self.optimizer=torch.optim.Adam(self.network.parameters(),lr=self.settings.learning_rate,eps=self.settings.adam_eps)
        self.pending=[];self.episodes=0;self.steps=0;self.logs=[];self.episode_logs=[]
    def controller(self,deterministic=False,collect=True):return p.Controller(network=self.network,generator=self.action_rng,deterministic=deterministic,collect=collect)
    def add(self,controller,result):
        if controller.errors:raise ValueError('training model fallback')
        self.pending.append(targets(controller,result));self.episodes+=1
        self.episode_logs.append(dict(episode=self.episodes,metrics=result['metrics']))
        if len(self.pending)==8:self.update()
    def update(self):
        batch=prepare(self.network,self.pending);d=batch['tensors'];before=copy.deepcopy(self.network.actor.state_dict());grads=[];kl=0.
        for epoch in range(self.settings.epochs):
            order=torch.randperm(batch['n'],generator=self.shuffle_rng)
            for start in range(0,batch['n'],self.settings.minibatch_frames):
                loss=minibatch_losses(self.network,batch,order[start:start+self.settings.minibatch_frames],self.settings,unbiased_scale=True)
                self.optimizer.zero_grad(set_to_none=True);loss['loss'].backward()
                grad=sum(float(x.grad.detach().double().square().sum()) for x in self.network.actor.parameters() if x.grad is not None)**.5
                total=float(torch.nn.utils.clip_grad_norm_(self.network.parameters(),self.settings.gradient_clip))
                if not math_isfinite(total):raise ValueError('nonfinite gradient')
                self.optimizer.step();self.steps+=1;grads.append(grad)
            with torch.no_grad():
                dist,_=self.network(d['state'],d['candidates'],d['mask']);kl=float(((d['old_log']-dist.log_prob(d['action']))*d['kl_weight']).sum())
            if kl>self.settings.target_kl:break
        changed=any(not torch.equal(v,self.network.actor.state_dict()[k]) for k,v in before.items())
        self.logs.append(dict(update=len(self.logs)+1,episodes=self.episodes,optimizer_steps=self.steps,frames=batch['n'],epochs=epoch+1,kl=kl,actor_changed=changed,actor_gradient_max=max(grads),normalization=batch['normalization']))
        self.pending=[]
    def snapshot(self):
        return dict(schema=p.SCHEMA,objective=OBJECTIVE,seed=self.seed,dependencies=self.dependencies,settings=asdict(self.settings),network=copy.deepcopy(self.network.state_dict()),optimizer=copy.deepcopy(self.optimizer.state_dict()),action_rng=self.action_rng.get_state(),shuffle_rng=self.shuffle_rng.get_state(),pending=copy.deepcopy(self.pending),episodes=self.episodes,steps=self.steps,logs=copy.deepcopy(self.logs),episode_logs=copy.deepcopy(self.episode_logs))
    def save(self,path):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
        with tmp.open('wb') as f:torch.save(self.snapshot(),f);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    @classmethod
    def load(cls,path,dependencies):
        d=torch.load(path,map_location='cpu',weights_only=False)
        if d['schema']!=p.SCHEMA or d['objective']!=OBJECTIVE or d['dependencies']!=dependencies or d['settings']!=asdict(Settings()):raise ValueError('checkpoint ABI/source/objective mismatch')
        l=cls(d['seed'],dependencies);l.network.load_state_dict(d['network']);l.optimizer.load_state_dict(d['optimizer']);l.action_rng.set_state(d['action_rng']);l.shuffle_rng.set_state(d['shuffle_rng'])
        for k in ('pending','episodes','steps','logs','episode_logs'):setattr(l,k,copy.deepcopy(d[k]))
        return l
def math_isfinite(x):return np.isfinite(x)
