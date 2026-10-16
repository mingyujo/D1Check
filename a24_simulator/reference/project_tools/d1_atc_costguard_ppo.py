"""Fresh dynamic-ABI native PPO. Existing loss/minibatch math, independent RNGs."""
import copy
import os
from dataclasses import asdict
from pathlib import Path

import numpy as np
import torch
from torch import nn

from tools import d1_atc_waitlink_policy as policy
from tools import d1_atc_waitlink_ppo as base
from tools import d1_list_candidate_rl as core
from tools import d1_list_candidate_rl_training as native

ARMS=("CONTROL","COST5","GATED_COST5")
POLICY_ARM="DROP_FLAG_WAIT1"
OBJECTIVES={arm:"COSTGUARD13_"+arm+"_URGENT15_E10_AP01_SERV100_PHI100_V1" for arm in ARMS}
WEIGHTS={arm:np.array([1. if arm=="CONTROL" else 5.,1. if arm=="CONTROL" else 5.,*([100.]*6),20.],dtype=np.float64) for arm in ARMS}


ActorCritic=base.ActorCritic  # frozen architecture and DROP_FLAG_WAIT1 forward


def targets(controller,raw,resident_baseline_j,arm,reference_raw):
    from tools import d1_atc_costguard_targets as target
    return target.targets(controller,raw,resident_baseline_j,arm,reference_raw)

def validate_frames(episodes):
    for e in episodes:
        for f in e:
            for name,shape,dtype in (("state",(policy.STATE_DIM,),np.float32),("candidates",(policy.SLOTS,policy.ACTION_DIM),np.float32),
                ("mask",(policy.SLOTS,),np.bool_),("target",(10,),np.float32),("valid",(10,),np.bool_)):
                a=f[name]
                if a.shape!=shape or a.dtype!=dtype:raise ValueError("rollout ABI "+name)
                if dtype==np.float32 and not np.isfinite(a).all():raise ValueError("nonfinite "+name)
            if not 0<=f["action"]<policy.SLOTS or not f["mask"][f["action"]]:raise ValueError("invalid rollout action")
            if f["informative"] and (f["logprob"] is None or f["old_value"] is None or f["mask"].sum()<=1):
                raise ValueError("sampled likelihood/value missing")


def prepare(network,episodes,weights):
    """Same episode-sum actor and episode-mean value/entropy as native prepare_batch."""
    validate_frames(episodes)
    with torch.no_grad():reference=core.ppo_losses(network,episodes,weights)
    fs=[f for e in episodes for f in e];n=len(fs);b=len(episodes)
    d={name:torch.from_numpy(np.stack([f[name] for f in fs])) for name in ("state","candidates","mask","target","valid")}
    d["action"]=torch.tensor([f["action"] for f in fs],dtype=torch.long)
    d["old_log"]=torch.tensor([f["logprob"] if f["logprob"] is not None else 0. for f in fs],dtype=torch.float32)
    d["informative"]=torch.tensor([f["informative"] for f in fs])
    advantage=reference["advantage"].clone()
    combined=advantage[:,0]-(advantage[:,1:]*torch.tensor(weights,dtype=torch.float32)).sum(-1)
    aw=torch.zeros(n);vw=torch.zeros(n);ew=torch.zeros(n);kw=torch.zeros(n)
    means=[];seconds=[];cursor=0;informed_episodes=0
    for e in episodes:
        sl=slice(cursor,cursor+len(e));cursor+=len(e);info=d["informative"][sl];count=int(info.sum())
        if e:vw[sl]=1/(b*len(e))
        if count:
            aw[sl]=info.float()/b;ew[sl]=info.float()/(b*count);kw[sl]=info.float()/count
            means.append(combined[sl][info].mean());seconds.append(combined[sl][info].square().mean());informed_episodes+=1
    center=torch.stack(means).mean() if means else torch.tensor(0.)
    denom=(torch.stack(seconds).mean()-center.square()).clamp(min=0).sqrt()+1e-8 if means else torch.tensor(1.)
    combined=(combined-center)/denom;kw/=max(informed_episodes,1)
    d.update(combined=combined,actor_weight=aw,value_weight=vw,entropy_weight=ew,kl_weight=kw)
    return dict(tensors=d,n=n,normalization=dict(center=float(center),denominator=float(denom)),
                sampled_choices=int(d["informative"].sum()),reference=reference)


class Learner:
    def __init__(self,seed,dependencies):
        torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
        self.sequencing=dependencies["sequencing"];self.arm=POLICY_ARM;self.reward_arm=dependencies["reward_arm"]
        if dependencies["arm"]!=POLICY_ARM or self.reward_arm not in ARMS:raise ValueError("policy/reward binding")
        self.objective=OBJECTIVES[self.reward_arm]
        if dependencies["objective"]!=self.objective or dependencies["schema"]!=policy.SCHEMA or self.sequencing!="ATC":raise ValueError("objective/schema/sequencing binding")
        self.seed=seed;self.dependencies=copy.deepcopy(dependencies);self.settings=native.Settings()
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed);self.network=ActorCritic(self.arm)
        self.action_rng=torch.Generator().manual_seed(seed+10000)
        self.shuffle_rng=torch.Generator().manual_seed(seed+20000)
        self.optimizer=torch.optim.Adam(self.network.parameters(),lr=self.settings.learning_rate,eps=self.settings.adam_eps)
        self.multipliers=WEIGHTS[self.reward_arm].copy()
        self.pending=[];self.logs=[];self.episode_logs=[];self.episodes=0;self.steps=0
        self.cursor=None;self.consumption={};self.last_controller=None

    def controller(self,frozen,initial,deterministic=False):
        return policy.Controller(frozen,initial,self.network,deterministic,self.action_rng,sequencing=self.sequencing,coupling=self.arm)

    def add(self,frames,costs,valid,row,controller=None):
        validate_frames([frames])
        if not frames:raise ValueError("no policy trajectory")
        self.pending.append(dict(frames=copy.deepcopy(frames),costs=costs.copy(),valid=valid.copy()))
        self.episodes+=1
        self.episode_logs.append(dict(episode=self.episodes,row=copy.deepcopy(row),costs=costs.tolist(),
            valid=valid.tolist(),frames=len(frames),informative=sum(f["informative"] for f in frames)))
        self.episode_logs[-1]["costguard"]=copy.deepcopy(frames[0].get("costguard_diagnostics",{}))
        if controller:
            self.last_controller=copy.deepcopy({k:v for k,v in controller.__dict__.items() if k not in ("network","generator")})
        if len(self.pending)==self.settings.episodes_per_update:self.update()

    def update(self):
        before=self.snapshot()
        try:
            self._update()
        except BaseException:
            restored=self.from_snapshot(before,self.dependencies)
            self.__dict__.update(restored.__dict__)
            raise

    def _update(self):
        if len(self.pending)!=8:raise ValueError("exact eight episode update")
        batch=prepare(self.network,[e["frames"] for e in self.pending],self.multipliers)
        critic_only=not batch["sampled_choices"]
        d=batch["tensors"];gradients=[];kl=0.;before=self.multipliers.copy()
        actor_before=copy.deepcopy(self.network.actor.state_dict())
        for epoch in range(self.settings.epochs):
            order=torch.randperm(batch["n"],generator=self.shuffle_rng)
            for begin in range(0,batch["n"],self.settings.minibatch_frames):
                loss=native.minibatch_losses(self.network,batch,order[begin:begin+self.settings.minibatch_frames],
                    self.settings,unbiased_scale=True)
                self.optimizer.zero_grad(set_to_none=True);loss["loss"].backward()
                if critic_only:
                    # A deduplicated single-action batch still teaches the critic.
                    # No artificial duplicate decisions or Adam actor momentum drift.
                    for parameter in list(self.network.actor.parameters())+list(self.network.candidate.parameters())+list(self.network.state.parameters()):parameter.grad=None
                actor_grad=sum(float(x.grad.detach().double().square().sum()) for x in self.network.actor.parameters() if x.grad is not None)**.5
                total=float(torch.nn.utils.clip_grad_norm_(self.network.parameters(),self.settings.gradient_clip))
                if not np.isfinite(total):raise ValueError("nonfinite gradient")
                self.optimizer.step();self.steps+=1;gradients.append(actor_grad)
            with torch.no_grad():
                dist,_=self.network(d["state"],d["candidates"],d["mask"])
                kl=float(((d["old_log"]-dist.log_prob(d["action"]))*d["kl_weight"]).sum())
            if kl>self.settings.target_kl:break
        # Every V8 objective multiplier is fixed; no dual update is performed.
        for i in ():
            mean=np.mean([float(e["costs"][i]) for e in self.pending if e["valid"][i+1]])
            self.multipliers[i]=np.clip(self.multipliers[i]+self.settings.lambda_eta*mean,0,self.settings.lambda_cap)
        with torch.no_grad():
            _,values=self.network(d["state"],d["candidates"],d["mask"])
            squared=(values-d["target"]).square()*d["valid"]
            critic_channels=(squared.sum(0)/d["valid"].sum(0).clamp(min=1)).tolist()
            advantage_channels=batch["reference"]["advantage"].mean(0).tolist()
        changed=any(not torch.equal(v,self.network.actor.state_dict()[k]) for k,v in actor_before.items())
        self.logs.append(dict(update=len(self.logs)+1,episodes=self.episodes,optimizer_steps=self.steps,
            frames=batch["n"],sampled_choices=batch["sampled_choices"],critic_only=critic_only,epochs=epoch+1,kl=kl,
            actor_gradient_max=max(gradients),actor_changed=changed,critic_mse_channels=critic_channels,
            raw_advantage_mean_channels=advantage_channels,lambda_before=before.tolist(),
            lambda_after=self.multipliers.tolist(),normalization=batch["normalization"],gamma=1,GAE=False))
        self.pending=[]

    def snapshot(self):
        return dict(version="atc-costguard13-learner-v1",schema=policy.SCHEMA,objective=self.objective,reward_arm=self.reward_arm,
            seed=self.seed,dependencies=self.dependencies,settings=asdict(self.settings),
            network=copy.deepcopy(self.network.state_dict()),optimizer=copy.deepcopy(self.optimizer.state_dict()),
            action_rng=self.action_rng.get_state().clone(),shuffle_rng=self.shuffle_rng.get_state().clone(),
            multipliers=self.multipliers.copy(),pending=copy.deepcopy(self.pending),logs=copy.deepcopy(self.logs),
            episode_logs=copy.deepcopy(self.episode_logs),episodes=self.episodes,steps=self.steps,
            cursor=copy.deepcopy(self.cursor),consumption=copy.deepcopy(self.consumption),
            last_controller=copy.deepcopy(self.last_controller))

    def save(self,path):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(".tmp")
        with tmp.open("wb") as f:
            torch.save(self.snapshot(),f);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)

    @classmethod
    def load(cls,path,dependencies):
        d=torch.load(path,map_location="cpu",weights_only=False)
        return cls.from_snapshot(d,dependencies)

    @classmethod
    def from_snapshot(cls,d,dependencies):
        if d.get("version")!="atc-costguard13-learner-v1" or d.get("reward_arm")!=dependencies["reward_arm"] or d["schema"]!=policy.SCHEMA or d["objective"]!=OBJECTIVES[dependencies["reward_arm"]] or d["dependencies"]!=dependencies or d["settings"]!=asdict(native.Settings()) or not np.array_equal(d["multipliers"],WEIGHTS[dependencies["reward_arm"]]):
            raise ValueError("checkpoint schema/objective/source mismatch")
        l=cls(d["seed"],dependencies)
        l.network.load_state_dict(d["network"]);l.optimizer.load_state_dict(d["optimizer"])
        l.action_rng.set_state(d["action_rng"]);l.shuffle_rng.set_state(d["shuffle_rng"])
        for k in ("multipliers","pending","logs","episode_logs","episodes","steps","cursor","consumption","last_controller"):
            setattr(l,k,copy.deepcopy(d[k]))
        return l
