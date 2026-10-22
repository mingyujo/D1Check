"""Paired public-BC initialization; weighted PPO versus component-RMS/dual."""
import copy,math,hashlib
from common_transfer import np,torch,WIDTH,ACTIONS
from torch import nn
VERSION='A24_PUBLIC_TRANSFER_48_36_V1'
class Net(nn.Module):
    def __init__(self):
        super().__init__();self.encode=nn.Sequential(nn.Linear(WIDTH,48),nn.Tanh());self.actor=nn.Sequential(nn.Linear(144,64),nn.Tanh(),nn.Linear(64,1));self.critic=nn.Sequential(nn.Linear(96,64),nn.Tanh(),nn.Linear(64,5));nn.init.zeros_(self.actor[-1].weight);nn.init.zeros_(self.actor[-1].bias)
    def forward(self,x,mask):
        e=self.encode(x);mean=(e*mask[:,:,None]).sum(1)/mask.sum(1,keepdim=True).clamp_min(1);maximum=e.masked_fill(~mask[:,:,None],-1e9).max(1).values;ctx=torch.cat((mean,maximum),-1)
        return self.actor(torch.cat((e,ctx[:,None,:].expand(-1,ACTIONS,-1)),-1)).squeeze(-1).masked_fill(~mask,-1e9),self.critic(ctx.detach())
def digest(net):
    h=hashlib.sha256()
    for n,t in sorted(net.state_dict().items()):h.update(n.encode());h.update(t.detach().numpy().tobytes())
    return h.hexdigest()
class Learner:
    def __init__(self,seed=981000,balanced=False,state=None):
        self.seed=seed;self.balanced=balanced;self.temperature=.35;self.dual=np.ones(2);self.scales=np.ones(2);self.episodes=self.updates=self.steps=self.bc_steps=0;self.pending=[];self.logs=[]
        with torch.random.fork_rng(devices=[]):torch.manual_seed(seed);self.net=Net()
        self.actor_parameters=[*self.net.encode.parameters(),*self.net.actor.parameters()];self.actor_optimizer=torch.optim.Adam(self.actor_parameters,lr=1e-4,eps=1e-5);self.critic_optimizer=torch.optim.Adam(self.net.critic.parameters(),lr=1e-3,eps=1e-5)
        self.action_rng=torch.Generator().manual_seed(seed+10000);self.shuffle_rng=torch.Generator().manual_seed(seed+20000);self.bc_rng=torch.Generator().manual_seed(seed+30000)
        if state is not None:self.restore(state)
    def choose(self,bank,collect):
        x=np.asarray(bank['x'],np.float32);mask=np.asarray(bank['mask'],bool)
        assert x.shape==(ACTIONS,WIDTH) and mask.any() and np.isfinite(x).all()
        with torch.no_grad():
            logits,value=self.net(torch.from_numpy(x)[None],torch.from_numpy(mask)[None]);lp=(logits/self.temperature).log_softmax(-1);i=int(torch.multinomial(lp.exp()[0],1,generator=self.action_rng)) if collect else int(logits[0].argmax())
        assert mask[i]
        return i,dict(x=x.copy(),mask=mask.copy(),scores=np.asarray(bank['scores']).copy(),index=i,old_logp=float(lp[0,i]),value=value[0].numpy().copy(),collect=collect,learn_actor=int(mask.sum())>1,network_sha256=digest(self.net))
    def add(self,frames,costs):
        values=np.array([f['value'] for f in frames]);costs=np.asarray(costs);targets=np.cumsum(costs[::-1],axis=0)[::-1].copy();adv=np.zeros_like(costs);following=np.zeros(5)
        for i in reversed(range(len(frames))):
            nv=values[i+1] if i+1<len(frames) else np.zeros(5);dt=(frames[i+1]['time_ns']-frames[i]['time_ns'])/1e9 if i+1<len(frames) else 0.
            following=costs[i]+nv-values[i]+math.exp(-dt/100.)*following;adv[i]=following
        self.pending.append([dict(f,target=targets[i],adv=adv[i],cost=costs[i]) for i,f in enumerate(frames)]);self.episodes+=1
        if len(self.pending)==2:self.update()
    def update(self):
        frames=[f for ep in self.pending for f in ep];x=torch.from_numpy(np.stack([f['x'] for f in frames]));mask=torch.from_numpy(np.stack([f['mask'] for f in frames]));target=torch.tensor(np.stack([f['target'] for f in frames]),dtype=torch.float32)
        action=torch.tensor([f['index'] for f in frames]);old=torch.tensor([f['old_logp'] for f in frames]);valid=torch.tensor([f['learn_actor'] for f in frames]);component=np.stack([f['adv'] for f in frames]);rms=None
        if self.balanced:
            good=np.asarray(valid);center=component-component[good].mean(0);rms=np.sqrt(np.mean(center[good]**2,axis=0)).clip(1e-4);component=center/rms;weights=np.array([1.,1.,*self.dual,3.])
        else:weights=np.array([.5,.5,8.,4.,30.])
        advantage=torch.tensor(-component@weights,dtype=torch.float32)
        if valid.sum()>1:advantage=(advantage-advantage[valid].mean())/advantage[valid].std(unbiased=False).clamp_min(1e-6)
        losses=[];kls=[];stop=False
        for epoch in range(4):
            for ids in torch.randperm(len(frames),generator=self.shuffle_rng).split(256):
                logits,values=self.net(x[ids],mask[ids]);lp=(logits/self.temperature).log_softmax(-1);selected=lp.gather(1,action[ids,None]).squeeze(1);ratio=(selected-old[ids]).exp();surrogate=torch.minimum(ratio*advantage[ids],ratio.clamp(.8,1.2)*advantage[ids]);actor=-(surrogate*valid[ids]).mean();entropy=-(lp.exp()*lp).sum(-1);critic=(values-target[ids]).square().mean();loss=actor-.003*(entropy*valid[ids]).mean()+.5*critic
                assert torch.isfinite(loss);self.actor_optimizer.zero_grad();self.critic_optimizer.zero_grad();loss.backward();nn.utils.clip_grad_norm_(self.actor_parameters,1.);nn.utils.clip_grad_norm_(self.net.critic.parameters(),1.);self.actor_optimizer.step();self.critic_optimizer.step();self.steps+=1
                losses.append(float(loss.detach()));kl=float(((ratio-1)-(selected-old[ids]))[valid[ids]].mean().detach()) if valid[ids].any() else 0.;kls.append(kl)
                if kl>.02:stop=True;break
            if stop:break
        self.updates+=1;self.logs.append(dict(update=self.updates,episodes=self.episodes,steps=self.steps,frames=len(frames),loss=float(np.mean(losses)),max_KL=max(kls),component_RMS=None if rms is None else rms.tolist(),weights=weights.tolist(),network_sha256=digest(self.net)));self.pending=[]
    def distill(self,frames,epochs=64):
        x=torch.from_numpy(np.stack([f['x'] for f in frames]));mask=torch.from_numpy(np.stack([f['mask'] for f in frames]));teacher=torch.from_numpy(np.stack([f['teacher_mask'] for f in frames]));groups=sorted({f['group'] for f in frames});counts={g:sum(f['group']==g for f in frames) for g in groups};weights=torch.tensor([len(frames)/(len(groups)*counts[f['group']]) for f in frames],dtype=torch.float32);optimizer=torch.optim.Adam(self.actor_parameters,lr=1e-3,eps=1e-5);logs=[]
        for ep in range(epochs):
            losses=[]
            for ids in torch.randperm(len(frames),generator=self.bc_rng).split(256):
                logits,_=self.net(x[ids],mask[ids]);logits=logits/self.temperature;loss=((logits.logsumexp(-1)-logits.masked_fill(~teacher[ids],-1e9).logsumexp(-1))*weights[ids]).mean();optimizer.zero_grad();loss.backward();nn.utils.clip_grad_norm_(self.actor_parameters,1.);optimizer.step();self.bc_steps+=1;losses.append(float(loss.detach()))
            with torch.no_grad():pred=torch.cat([self.net(x[ids],mask[ids])[0].argmax(-1) for ids in torch.arange(len(x)).split(256)]);good=teacher.gather(1,pred[:,None]).squeeze(1);per={g:float(good[torch.tensor([i for i,f in enumerate(frames) if f['group']==g])].float().mean()) for g in groups}
            logs.append(dict(epoch=ep+1,loss=float(np.mean(losses)),compatible_accuracy=float(good.float().mean()),per_route=per,steps=self.bc_steps));print('PUBLIC_BC',logs[-1],flush=True)
            if logs[-1]['compatible_accuracy']>=.995 and min(per.values())>=.99 and logs[-1]['loss']<=.05:break
        return dict(logs=logs,groups=counts,frames=len(frames),optimizer=copy.deepcopy(optimizer.state_dict()),group_weights=weights,teacher_uses_future=False)
    def snapshot(self):
        return copy.deepcopy(dict(version=VERSION,seed=self.seed,balanced=self.balanced,temperature=self.temperature,dual=self.dual,scales=self.scales,network=self.net.state_dict(),actor_optimizer=self.actor_optimizer.state_dict(),critic_optimizer=self.critic_optimizer.state_dict(),action_rng=self.action_rng.get_state(),shuffle_rng=self.shuffle_rng.get_state(),bc_rng=self.bc_rng.get_state(),episodes=self.episodes,updates=self.updates,steps=self.steps,bc_steps=self.bc_steps,pending=self.pending,logs=self.logs,network_sha256=digest(self.net)))
    def restore(self,s):
        assert s['version']==VERSION
        self.net.load_state_dict(s['network']);self.actor_optimizer.load_state_dict(copy.deepcopy(s['actor_optimizer']));self.critic_optimizer.load_state_dict(copy.deepcopy(s['critic_optimizer']))
        for k in ('seed','balanced','temperature','dual','scales','episodes','updates','steps','bc_steps','pending','logs'):setattr(self,k,copy.deepcopy(s[k]))
        for k in ('action_rng','shuffle_rng','bc_rng'):getattr(self,k).set_state(s[k])
        assert digest(self.net)==s['network_sha256']
