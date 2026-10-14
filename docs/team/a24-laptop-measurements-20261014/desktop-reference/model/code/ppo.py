"""Fresh masked set-PPO, five cost critics, physical-time GAE, goal-conditioned SLA."""
import copy, math, os, time
from dataclasses import dataclass,asdict
import numpy as np
import torch
from torch import nn
from common import ALPHAS,H120,H180,digest
from candidates import build,SCHEMA
torch.set_num_threads(1)

@dataclass(frozen=True)
class Settings:
    episodes_per_update:int=8
    epochs:int=4
    minibatch_frames:int=256
    learning_rate:float=.0003
    clip:float=.2
    value_coef:float=.5
    entropy_coef:float=.01
    gradient_clip:float=.5
    kl_stop:float=.03
    energy_scale_j:float=20.
    heat_scale_c_s:float=72.5
    gae_time_s:float=20.
    dual_lr:float=5.

class Net(nn.Module):
    def __init__(self):
        super().__init__()
        self.request=nn.Sequential(nn.Linear(24,64),nn.Tanh())
        self.resource=nn.Sequential(nn.Linear(12,32),nn.Tanh())
        self.state=nn.Sequential(nn.Linear(188,128),nn.Tanh(),nn.Linear(128,64),nn.Tanh())
        self.actor=nn.Sequential(nn.Linear(176,64),nn.Tanh(),nn.Linear(64,1))
        self.critic=nn.Linear(64,5)
        for m in self.modules():
            if isinstance(m,nn.Linear):
                nn.init.orthogonal_(m.weight,math.sqrt(2));nn.init.zeros_(m.bias)
        nn.init.zeros_(self.actor[-1].weight)
    def forward(self,requests,resources,global_state,features,request_index,backend_index,mask):
        present=requests[:,:,-1:];enc=self.request(requests)
        mean=(enc*present).sum(1)/present.sum(1).clamp_min(1)
        maximum=enc.masked_fill(present==0,-1e9).max(1).values
        maximum=torch.where(present.sum(1)>0,maximum,torch.zeros_like(maximum))
        state=self.state(torch.cat([mean,maximum,resources.flatten(1),global_state],-1))
        reqenc=torch.gather(enc,1,request_index[:,:,None].expand(-1,-1,64))
        resenc=self.resource(resources)
        resenc=torch.gather(resenc,1,backend_index[:,:,None].expand(-1,-1,32))
        executing=1-features[:,:,3:4]
        joint=torch.cat([reqenc*executing,resenc*executing,state[:,None,:].expand(-1,features.shape[1],-1),features],-1)
        logits=self.actor(joint).squeeze(-1).masked_fill(~mask,-1e9)
        return logits,self.critic(state)

INPUTS=("requests","resources","global_state","features","request_index","backend_index","mask")
def tensors(bank):
    return [torch.from_numpy(bank[k]).unsqueeze(0) for k in INPUTS]
def input_digest(bank):
    import hashlib
    h=hashlib.sha256()
    for k in INPUTS:h.update(k.encode());h.update(bank[k].tobytes());h.update(str(bank[k].shape).encode())
    return h.hexdigest()

class Controller:
    def __init__(self,network,generator,kind="ATC",allow_wait=True,alpha=1.,heat=.5,collect=False):
        self.net=network;self.rng=generator;self.kind=kind;self.allow_wait=allow_wait;self.alpha=alpha;self.heat=heat;self.collect=collect
        self.frames=[];self.decisions=[];self.audit=[];self.errors=[]
        self.capture_inputs=False
    def choose(self,view,waiting):
        bank=build(view,waiting,self.kind,self.allow_wait,self.alpha,self.heat)
        tick=time.perf_counter_ns()
        try:
            with torch.no_grad():
                logits,value=self.net(*tensors(bank));logp=logits.log_softmax(-1);probs=logp.exp()
            if not torch.isfinite(logits).all() or not torch.isfinite(value).all():raise ValueError("nonfinite model")
        except (RuntimeError,ValueError,TypeError) as error:
            # A deployment failure never fabricates a service guarantee or releases a busy lane.
            from candidates import Rule
            idx=int(Rule("ATC").index(bank));a=bank["actions"][idx]
            self.errors.append(dict(time_ns=view.now,reason=str(error),fallback="current legal ATC"))
            self.decisions.append({**bank["diagnostic"],"chosen_index":idx,
                "chosen":([a["request"]["id"],a["backend"]] if a["request"] else None),"wait_ns":a["wait_ns"],
                "nn_us":(time.perf_counter_ns()-tick)/1000,"model_fallback":True,"alpha":self.alpha})
            self.audit.append(dict(time_ns=view.now,physical=bool(bank["physical_mask"][idx]),future_input=False,model_fallback=True))
            return a
        idx=int(torch.multinomial(probs[0],1,generator=self.rng).item()) if self.collect else int(logits[0].argmax())
        if not bank["mask"][idx]:raise ValueError("invalid masked sample")
        a=bank["actions"][idx]
        frame=dict(time_ns=view.now,index=idx,old_logp=float(logp[0,idx]),value=value[0].numpy().copy(),
                   learn_actor=int(bank["mask"].sum())>1,alpha=self.alpha,heat=self.heat,input_sha=input_digest(bank))
        if self.collect or self.capture_inputs:
            frame.update({k:bank[k].copy() for k in INPUTS})
            frame["physical_mask"]=bank["physical_mask"].copy()
            self.frames.append(frame)
        diag={**bank["diagnostic"],"chosen_index":idx,"chosen":([a["request"]["id"],a["backend"]] if a["request"] else None),
              "wait_ns":a["wait_ns"],"nn_us":(time.perf_counter_ns()-tick)/1000,"input_sha":frame["input_sha"],
              "logprob":frame["old_logp"],"critic":value[0].tolist(),"alpha":self.alpha,"heat":self.heat}
        self.decisions.append(diag);self.audit.append(dict(time_ns=view.now,physical=bool(bank["physical_mask"][idx]),future_input=False))
        return a

def labels(controller,raw,settings,family):
    fs=controller.frames
    if not fs or controller.errors:raise ValueError("missing frames/model errors")
    times=np.array([f["time_ns"] for f in fs],np.int64)
    if (np.diff(times)<0).any():raise ValueError("nonmonotonic decisions")
    cost=np.zeros((len(fs),5),np.float64)
    # Events/interval costs at t occur before the decision made after observing t.
    # Charge the preceding action, not an action that cannot change the past event.
    def index(t):return max(0,min(len(fs)-1,int(np.searchsorted(times,t,side="left"))-1))
    counts={p:sum(q["priority"]==p for q in raw["ledger"]) for p in ("urgent","normal")}
    for q in raw["ledger"]:
        late=(q.get("response_ns",math.inf)>q["deadline_offset_ns"]
              and q["arrival_ns"]+q["deadline_offset_ns"]<=H120)
        if late:cost[index(q["arrival_ns"]+q["deadline_offset_ns"]),2 if q["priority"]=="urgent" else 3]+=1/max(counts[q["priority"]],1)
        if q["status"]!="succeeded":cost[-1,4]+=1/len(raw["ledger"])
    # Dense energy/AP targets include the entire fixed tail; reference subtraction is action-independent.
    last_t=last_e=last_a=0.
    baseline=raw["cost_120"].get("reference_ap_c",32.)
    resident=raw["nominal_resident_w"]
    for row in raw["cost_samples"]:
        t,e,a=row["time_ns"],row["energy_j"],row["ap_area"]
        dt=max(0,t-last_t)/1e9
        window=max(0,t/1e9-35)-max(0,last_t/1e9-35)
        i=row.get("decision_index") if row.get("reason")=="dispatch" else index(t)
        if i is None:i=index(t)
        cost[i,0]+=(e-last_e-resident*dt)/settings.energy_scale_j
        cost[i,1]+=(a-last_a-baseline*window)/settings.heat_scale_c_s
        last_t,last_e,last_a=t,e,a
    if family=="GATE" and (cost[:,2:].sum()>0):cost[:,:2]=0.
    totals=cost.sum(0)
    values=np.stack([f["value"] for f in fs]);adv=np.zeros_like(cost);following=np.zeros(5)
    for i in reversed(range(len(fs))):
        vnext=values[i+1] if i+1<len(fs) else np.zeros(5)
        delta=cost[i]+vnext-values[i]
        dt=((times[i+1]-times[i])/1e9) if i+1<len(fs) else 0.
        lam=math.exp(-dt/settings.gae_time_s)
        following=delta+lam*following;adv[i]=following
    returns=np.cumsum(cost[::-1],axis=0)[::-1].copy()
    if np.max(np.abs(returns[0]-totals))>1e-8:raise ValueError("reward telescope")
    for i,f in enumerate(fs):f.update(cost=cost[i].astype(np.float32),target=returns[i].astype(np.float32),adv=adv[i].astype(np.float32))
    return fs,dict(total_cost=totals.tolist(),telescope_error=float(np.max(np.abs(returns[0]-totals))),
                   alpha=controller.alpha,role_counts=counts,actor_frames=sum(f["learn_actor"] for f in fs))

def pack(episodes):
    frames=[f for ep in episodes for f in ep]
    nq=max(f["requests"].shape[0] for f in frames);na=max(f["features"].shape[0] for f in frames);n=len(frames)
    data={}
    for k,width in (("requests",24),("features",16)):
        slots=nq if k=="requests" else na
        arr=np.zeros((n,slots,width),np.float32)
        for i,f in enumerate(frames):arr[i,:len(f[k])]=f[k]
        data[k]=torch.from_numpy(arr)
    for k in ("mask","request_index","backend_index"):
        arr=np.zeros((n,na),bool if k=="mask" else np.int64)
        for i,f in enumerate(frames):arr[i,:len(f[k])]=f[k]
        data[k]=torch.from_numpy(arr)
    for k in ("resources","global_state","value","target","adv"):
        data[k]=torch.from_numpy(np.stack([f[k] for f in frames]))
    data["index"]=torch.tensor([f["index"] for f in frames],dtype=torch.long)
    data["old_logp"]=torch.tensor([f["old_logp"] for f in frames],dtype=torch.float32)
    data["actor_valid"]=torch.tensor([f["learn_actor"] for f in frames],dtype=torch.bool)
    weights=[];ep_actor=[]
    for ep in episodes:
        c=max(1,sum(f["learn_actor"] for f in ep))
        weights.extend([1/len(ep)]*len(ep));ep_actor.extend([1/c]*len(ep))
    data["value_weight"]=torch.tensor(weights)*n/len(episodes)
    data["actor_weight"]=torch.tensor(ep_actor)*n/len(episodes)
    return data,frames

class Learner:
    def __init__(self,seed,device,kind="ATC",allow_wait=True,family="DENSE",settings=None):
        self.seed=seed;self.device=device;self.kind=kind;self.allow_wait=allow_wait;self.family=family;self.settings=settings or Settings()
        torch.manual_seed(seed);self.net=Net();self.opt=torch.optim.Adam(self.net.parameters(),lr=self.settings.learning_rate,eps=1e-5)
        self.action_rng=torch.Generator().manual_seed(seed+100000);self.shuffle_rng=torch.Generator().manual_seed(seed+200000)
        self.duals=np.tile(np.array([10.,10.,50.]),(5,1))
        self.pending=[];self.pending_meta=[];self.episodes=0;self.steps=0;self.updates=0;self.logs=[]
    def controller(self,alpha=1.,heat=.5,collect=False):
        controller=Controller(self.net,self.action_rng,self.kind,self.allow_wait,alpha,heat,collect)
        controller.settings=self.settings;controller.family=self.family
        return controller
    def add(self,controller,raw):
        frames,meta=labels(controller,raw,self.settings,self.family)
        self.pending.append(frames);self.pending_meta.append(meta);self.episodes+=1
        if len(self.pending)>=self.settings.episodes_per_update:self.update()
        return meta
    def update(self):
        data,frames=pack(self.pending);n=len(frames)
        weighted=[]
        for f in frames:
            ai=min(range(5),key=lambda j:abs(ALPHAS[j]-f["alpha"]));dual=self.duals[ai]
            if self.family=="GATE":dual=np.array([20.,5.,50.])
            weights=np.r_[1-f["heat"],f["heat"],dual]
            weighted.append(-float(f["adv"]@weights))
        advantage=torch.tensor(weighted)
        valid=data["actor_valid"];selected=advantage[valid]
        if len(selected)>1:advantage=(advantage-selected.mean())/selected.std(unbiased=False).clamp_min(1e-8)
        self.updates+=1;stop=False;kls=[];losses=[];s=self.settings
        for epoch in range(s.epochs):
            permutation=torch.randperm(n,generator=self.shuffle_rng)
            for start in range(0,n,s.minibatch_frames):
                ids=permutation[start:start+s.minibatch_frames]
                logits,values=self.net(*[data[k][ids] for k in INPUTS])
                logp=logits.log_softmax(-1);chosen=logp.gather(1,data["index"][ids,None]).squeeze(1)
                ratio=(chosen-data["old_logp"][ids]).exp()
                v=valid[ids];aw=data["actor_weight"][ids]
                surrogate=torch.minimum(ratio*advantage[ids],ratio.clamp(1-s.clip,1+s.clip)*advantage[ids])
                actor=-(surrogate*v*aw).mean()
                entropy=-(logp.exp()*logp).sum(-1)
                critic=((values-data["target"][ids]).square().mean(-1)*data["value_weight"][ids]).mean()
                loss=actor+s.value_coef*critic-s.entropy_coef*(entropy*v*aw).mean()
                self.opt.zero_grad();loss.backward();nn.utils.clip_grad_norm_(self.net.parameters(),s.gradient_clip);self.opt.step();self.steps+=1
                with torch.no_grad():
                    kl=((ratio-1)-(chosen-data["old_logp"][ids]))
                    mean_kl=float(kl[v].mean()) if v.any() else 0.
                kls.append(mean_kl);losses.append(float(loss.detach()))
                if mean_kl>s.kl_stop:stop=True;break
            if stop:break
        for ai,alpha in enumerate(ALPHAS):
            rows=[m for m in self.pending_meta if abs(m["alpha"]-alpha)<1e-6]
            if rows and self.family!="GATE":
                for j,role in enumerate(("urgent","normal","incomplete")):
                    observed=[m["total_cost"][j+2] for m in rows if role=="incomplete" or m["role_counts"][role]>0]
                    if observed:
                        budget=0. if role=="incomplete" else 1-alpha
                        self.duals[ai,j]=np.clip(self.duals[ai,j]+s.dual_lr*(np.mean(observed)-budget),0,200)
        self.logs.append(dict(update=self.updates,episodes=self.episodes,frames=n,actor_frames=int(valid.sum()),adam_steps=self.steps,
                              loss_mean=float(np.mean(losses)),kl_max=max(kls),early_stop=stop,duals=self.duals.tolist()))
        self.pending=[];self.pending_meta=[]
    def snapshot(self):
        return dict(version="ratr37-native-v2",schema=SCHEMA,seed=self.seed,device=self.device,kind=self.kind,allow_wait=self.allow_wait,
                    family=self.family,settings=asdict(self.settings),network=self.net.state_dict(),optimizer=self.opt.state_dict(),
                    action_rng=self.action_rng.get_state(),shuffle_rng=self.shuffle_rng.get_state(),duals=self.duals.copy(),
                    episodes=self.episodes,steps=self.steps,updates=self.updates,logs=copy.deepcopy(self.logs),
                    pending=copy.deepcopy(self.pending),pending_meta=copy.deepcopy(self.pending_meta))
    def save(self,path):
        temp=str(path)+".tmp";torch.save(self.snapshot(),temp)
        with open(temp,"r+b") as f:os.fsync(f.fileno())
        os.replace(temp,path)
    @classmethod
    def load(cls,path):
        s=torch.load(path,map_location="cpu",weights_only=False)
        if s["schema"]!=SCHEMA or s["version"]!="ratr37-native-v2":raise ValueError("checkpoint ABI")
        l=cls(s["seed"],s["device"],s["kind"],s["allow_wait"],s["family"],Settings(**s["settings"]))
        l.net.load_state_dict(s["network"]);l.opt.load_state_dict(s["optimizer"])
        l.action_rng.set_state(s["action_rng"]);l.shuffle_rng.set_state(s["shuffle_rng"])
        for k in ("duals","episodes","steps","updates","logs","pending","pending_meta"):setattr(l,k,s[k])
        return l
