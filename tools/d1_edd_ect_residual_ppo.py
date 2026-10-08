"""109/68 candidate residual PPO, causal controller and complete Adam archives.

No environment starts on import. A budgeted runner must own every episode.
"""
from __future__ import annotations
import copy
import hashlib
import io
import math
import os
from pathlib import Path
import random
import numpy as np
import torch
from torch import nn
from tools import d1_edd_ect_residual_controller as core

VERSION='edd-ect-residual-ppo-v1'


def seed_all(seed):
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)


class ActorCritic(nn.Module):
    def __init__(self):
        super().__init__()
        self.state=nn.Sequential(nn.Linear(109,64),nn.Tanh(),nn.Linear(64,64),nn.Tanh())
        self.candidate=nn.Sequential(nn.Linear(68,64),nn.Tanh(),nn.Linear(64,64),nn.Tanh())
        self.actor=nn.Sequential(nn.Linear(128,64),nn.Tanh(),nn.Linear(64,1))
        self.critic=nn.Linear(64,6)
        for layer in self.modules():
            if isinstance(layer,nn.Linear):nn.init.orthogonal_(layer.weight,math.sqrt(2));nn.init.zeros_(layer.bias)
        nn.init.zeros_(self.actor[-1].weight);nn.init.zeros_(self.actor[-1].bias)
        nn.init.orthogonal_(self.critic.weight,1.)

    def forward(self,state,candidates,mask,base):
        if not torch.all(mask.any(-1)):raise ValueError('empty candidate mask')
        h=self.state(state);ch=self.candidate(candidates)
        scores=self.actor(torch.cat((h[:,None,:].expand(-1,candidates.shape[1],-1),ch),dim=-1)).squeeze(-1)
        m=mask.sum(-1)
        prior=torch.where((m>1)&base.any(-1),torch.log(9.*torch.clamp(m-1,min=1)),torch.zeros_like(m,dtype=scores.dtype))
        scores=scores+base*prior[:,None]
        dist=torch.distributions.Categorical(logits=scores.masked_fill(~mask,-1e9))
        return dist,self.critic(h)


class Controller(core.Controller):
    def __init__(self,frozen,initial,network,deterministic=False):
        super().__init__(frozen,initial,core.PRIOR,record_forecasts=True)
        self.public_policy='EDD_ECT_SLACK_RESIDUAL_PPO_V1'
        self.network=network;self.deterministic=deterministic;self.trajectory=[]

    def decide(self,config,queue,lanes,now_ns,settings,thermal_model,current_ap):
        key=core.public_signature(queue,lanes,now_ns)
        if key==self.last_signature and self.pending is None:return copy.deepcopy(self.last_reply)
        reply=super().decide(config,queue,lanes,now_ns,settings,thermal_model,current_ap)
        if reply.get('reason')=='bundle_commit' or not queue:return reply
        candidates=reply.get('candidates',[])
        if candidates:
            state=reply['state_features'];vectors=reply['candidate_features']
            mask=[bool(a['valid']) for a in candidates];base=[bool(a['base'] and a['valid']) for a in candidates]
            if not any(mask):candidates=[]
        if not candidates:
            state,_=self.tensors(queue,lanes,now_ns,[])
            vectors=[];mask=[];base=[]
        actual=len(candidates)
        tensor_state=np.asarray(state,dtype=np.float32)
        tensor_candidates=np.asarray(vectors+[[0.]*68]*(32-len(vectors)),dtype=np.float32)
        tensor_mask=np.asarray(mask+[False]*(32-len(mask)),dtype=bool)
        tensor_base=np.asarray(base+[False]*(32-len(base)),dtype=bool)
        if not actual:tensor_mask[0]=True
        with torch.no_grad():
            dist,values=self.network(torch.from_numpy(tensor_state)[None],torch.from_numpy(tensor_candidates)[None],
                torch.from_numpy(tensor_mask)[None],torch.from_numpy(tensor_base)[None])
            informative=int(tensor_mask.sum())>1 and actual>0
            action=(dist.probs.argmax(-1) if self.deterministic or not informative else dist.sample())
            index=int(action.item());logprob=float(dist.log_prob(action).item())
        # Undo the prior's tentative reply. Actual dispatch has not happened yet.
        if actual:
            self.pending=None;self.cool_since=None
            chosen=candidates[index]
            out=self._reply(chosen,now_ns)
            out.update(chosen_base=chosen['base'],valid_actions=sum(mask),candidate_count=actual,
                modeled_ap_c=self.t,credit_s=self.credit,
                chosen_delta_j=[chosen['forecasts'][c]['delta_j'] for c in core.CONTEXTS],
                chosen_delta_ap=[chosen['forecasts'][c]['delta_ap'] for c in core.CONTEXTS])
        else:out={k:v for k,v in reply.items() if k not in ('candidates','state_features','candidate_features')}
        out['reason']=out.get('reason',self.public_policy)
        out['public_policy']=self.public_policy
        self.trajectory.append(dict(t_s=now_ns/1e9,state=tensor_state,candidates=tensor_candidates,
            mask=tensor_mask,base=tensor_base,action=index,logprob=logprob,value=values[0].numpy(),informative=informative,
            grid_peak=max(self.grid.values()) if self.grid else None))
        if self.actions:self.actions[-1]=copy.deepcopy(out)
        self.last_signature,self.last_reply=key,copy.deepcopy(out)
        return out


def target_data(controller,row,references):
    """Signed grid-peak increments telescope; costs only after episode end."""
    full=row['completed']==row['planned']
    channel_valid=np.ones(6,dtype=bool)
    channel_valid[0]=channel_valid[1]=full and row['peak_ap_c'] is not None
    if len(references)!=3:raise ValueError('three closed independent references required')
    if any(r['completed']!=r['planned'] for r in references):channel_valid[0]=channel_valid[1]=False
    costs=np.zeros(5,dtype=np.float64)
    costs[1]=row['planned']-row['completed']
    for i,metric,scale in [(0,'energy_j',1.),(2,'urgent_service_failure',1.),(3,'normal_service_failure',1.),(4,'urgent_p95_ms',1500.)]:
        if row.get(metric) is None or any(r.get(metric) is None for r in references):
            channel_valid[i+1]=False;continue
        epsilon=1e-9 if metric in ('energy_j','urgent_p95_ms') else 0.
        costs[i]=max(0.,*(row[metric]-r[metric]-epsilon for r in references))/scale
    tr=controller.trajectory
    if not tr:return [],costs,channel_valid
    heat=np.zeros(len(tr),dtype=np.float64)
    if channel_valid[0]:
        anchor=controller.init['anchor_ap_c']
        previous=anchor
        for i,step in enumerate(tr):
            peak=step['grid_peak']
            if peak is not None:
                heat[i]=-(peak-previous);previous=peak
        heat[-1]-=row['peak_ap_c']-previous
        heat[-1]+=references[0]['peak_ap_c']-anchor
        if abs(float(heat.sum())-(references[0]['peak_ap_c']-row['peak_ap_c']))>1e-10:raise ValueError('heat telescope')
    returns=np.cumsum(heat[::-1])[::-1]
    data=[]
    for step,ret in zip(tr,returns):
        data.append(dict(step,target=np.asarray([ret,*costs],dtype=np.float32),valid=channel_valid.copy()))
    return data,costs,channel_valid


def update(network,optimizer,batch,multipliers):
    data=[step for episode in batch for step in episode['data']]
    if not data:return dict(optimizer_steps=0,informative=0)
    state=torch.from_numpy(np.stack([d['state'] for d in data]));candidates=torch.from_numpy(np.stack([d['candidates'] for d in data]))
    mask=torch.from_numpy(np.stack([d['mask'] for d in data]));base=torch.from_numpy(np.stack([d['base'] for d in data]))
    action=torch.tensor([d['action'] for d in data]);old_log=torch.tensor([d['logprob'] for d in data],dtype=torch.float32)
    old_values=torch.from_numpy(np.stack([d['value'] for d in data]));target=torch.from_numpy(np.stack([d['target'] for d in data]))
    valid=torch.from_numpy(np.stack([d['valid'] for d in data]));informative=torch.tensor([d['informative'] for d in data],dtype=torch.bool)
    adv=(target-old_values)*valid
    combined=adv[:,0]-(adv[:,1:]*torch.tensor(multipliers,dtype=torch.float32)).sum(-1)
    if informative.any():
        values=combined[informative];combined=(combined-values.mean())/(values.std(unbiased=False)+1e-8)
    steps=0;last_kl=0.;last_loss=0.;last_entropy=0.
    for _ in range(4):
        ordering=torch.randperm(len(data))
        for start in range(0,len(data),256):
            idx=ordering[start:start+256]
            dist,value=network(state[idx],candidates[idx],mask[idx],base[idx])
            new_log=dist.log_prob(action[idx]);ratio=torch.exp(new_log-old_log[idx]);actor_mask=informative[idx]
            policy_loss=-torch.minimum(ratio*combined[idx],ratio.clamp(.8,1.2)*combined[idx])
            actor=policy_loss[actor_mask].mean() if actor_mask.any() else (value.sum()*0.)
            entropy=dist.entropy()[actor_mask].mean() if actor_mask.any() else (value.sum()*0.)
            denominator=valid[idx].sum()
            critic=((value-target[idx]).square()*valid[idx]).sum()/denominator.clamp(min=1)
            loss=actor+.5*critic-.01*entropy
            optimizer.zero_grad(set_to_none=True);loss.backward();nn.utils.clip_grad_norm_(network.parameters(),.5);optimizer.step()
            steps+=1;last_loss=float(loss.detach());last_entropy=float(entropy.detach())
            if actor_mask.any():last_kl=float((old_log[idx]-new_log)[actor_mask].mean().detach())
        if last_kl>.03:break
    for i in range(5):
        costs=[e['costs'][i] for e in batch if e['valid'][i+1]]
        if costs:multipliers[i]=max(0.,multipliers[i]+.01*float(np.mean(costs)))
    return dict(optimizer_steps=steps,informative=int(informative.sum()),loss=last_loss,kl=last_kl,entropy=last_entropy)


def model_hash(network):
    h=hashlib.sha256()
    for key,tensor in sorted(network.state_dict().items()):h.update(key.encode());h.update(tensor.detach().cpu().numpy().tobytes())
    return h.hexdigest()


def archive(path,network,optimizer,state):
    """Atomic full training state, independent terminal and selected actors."""
    payload=dict(version=VERSION,state=copy.deepcopy(state),network=network.state_dict(),optimizer=optimizer.state_dict(),
        python_rng=random.getstate(),numpy_rng=np.random.get_state(),torch_rng=torch.get_rng_state(),
        schema=dict(state=109,candidate=68,slots=32,critic=6),network_sha256=model_hash(network))
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp')
    with temp.open('wb') as stream:torch.save(payload,stream);stream.flush();os.fsync(stream.fileno())
    os.replace(temp,path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restore(path):
    payload=torch.load(path,map_location='cpu',weights_only=False)
    if payload['version']!=VERSION or payload['schema']!=dict(state=109,candidate=68,slots=32,critic=6):raise ValueError('archive schema')
    network=ActorCritic();network.load_state_dict(payload['network'])
    if model_hash(network)!=payload['network_sha256']:raise ValueError('actor/critic hash')
    optimizer=torch.optim.Adam(network.parameters(),lr=.0003,eps=1e-5);optimizer.load_state_dict(payload['optimizer'])
    random.setstate(payload['python_rng']);np.random.set_state(payload['numpy_rng']);torch.set_rng_state(payload['torch_rng'])
    return network,optimizer,payload['state']
