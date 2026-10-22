"""Concentrated masked PPO, actor-owned encoder and separate value optimizer."""
import copy,math
from common import B,np,torch
from nn_train import Net,digest
from dynamics import WEIGHTS
VERSION='DEEP_REPAIR_SPLIT_PPO_V1'
class Learner:
    def __init__(self,original,anchor=False):
        self.seed=original['seed'];self.net=Net();self.net.load_state_dict(original['network'])
        self.temperature=.15;self.entropy_weight=.003;self.lambda_time_s=100.
        self.actor_parameters=[*self.net.encode.parameters(),*self.net.actor.parameters()]
        self.actor_optimizer=torch.optim.Adam(self.actor_parameters,lr=.00015,eps=1e-5)
        self.critic_optimizer=torch.optim.Adam(self.net.critic.parameters(),lr=.001,eps=1e-5)
        self.action_rng=torch.Generator();self.action_rng.set_state(original['action_rng'])
        self.shuffle_rng=torch.Generator();self.shuffle_rng.set_state(original['shuffle_rng'])
        self.bc_rng=torch.Generator().manual_seed(self.seed+30000)
        self.episodes=original['episodes'];self.updates=original['updates'];self.steps=original['steps'];self.pending=[];self.logs=[];self.bc_logs=[];self.bc_steps=0;self.anchor=None
        if original.get('version')==VERSION:
            self.actor_optimizer.load_state_dict(copy.deepcopy(original['actor_optimizer']));self.critic_optimizer.load_state_dict(copy.deepcopy(original['critic_optimizer']))
            self.bc_rng.set_state(original['bc_rng'])
            for key in ('pending','logs','bc_logs','bc_steps'):setattr(self,key,copy.deepcopy(original[key]))
            if original['anchor'] is not None:self.set_anchor(original['anchor'])
        else:
            # Map original Adam moments by parameter identity, never tensor alias.
            old=original['optimizer'];old_ids=old['param_groups'][0]['params']
            for optimizer,indices in ((self.actor_optimizer,range(6)),(self.critic_optimizer,range(6,10))):
                state=optimizer.state_dict();new_ids=state['param_groups'][0]['params']
                state['state']={new_ids[i]:copy.deepcopy(old['state'][old_ids[j]]) for i,j in enumerate(indices) if old_ids[j] in old['state']};optimizer.load_state_dict(state)
        if anchor:self.set_anchor(self.net.state_dict())
    def set_anchor(self,state):
        self.anchor=Net();self.anchor.load_state_dict(copy.deepcopy(state));self.anchor.requires_grad_(False)
    def forward(self,x,mask):
        e=self.net.encode(x);mean=(e*mask[:,:,None]).sum(1)/mask.sum(1,keepdim=True).clamp_min(1);maximum=e.masked_fill(~mask[:,:,None],-1e9).max(1).values
        context=torch.cat((mean,maximum),-1)
        logits=self.net.actor(torch.cat((e,context[:,None,:].expand(-1,19,-1)),-1)).squeeze(-1).masked_fill(~mask,-1e9)
        return logits,self.net.critic(context.detach())
    def choose(self,bank,collect):
        x=np.asarray(bank['x'],np.float32);mask=np.asarray(bank['mask'],bool)
        with torch.no_grad():
            logits,value=self.forward(torch.from_numpy(x)[None],torch.from_numpy(mask)[None]);lp=(logits/self.temperature).log_softmax(-1)
            i=int(torch.multinomial(lp.exp()[0],1,generator=self.action_rng)) if collect else int(logits[0].argmax())
        if not mask[i]:raise ValueError('Masked neural action')
        return i,dict(x=x.copy(),mask=mask.copy(),scores=bank['scores'].copy(),index=i,old_logp=float(lp[0,i]),value=value[0].numpy().copy(),collect=collect,learn_actor=int(mask.sum())>1,network_sha256=digest(self.net))
    def add(self,frames,costs):
        values=np.array([f['value'] for f in frames]);costs=np.asarray(costs);targets=np.cumsum(costs[::-1],axis=0)[::-1].copy();adv=np.zeros_like(costs);following=np.zeros(5)
        for i in reversed(range(len(frames))):
            nv=values[i+1] if i+1<len(frames) else np.zeros(5);dt=(frames[i+1]['time_ns']-frames[i]['time_ns'])/1e9 if i+1<len(frames) else 0.
            following=costs[i]+nv-values[i]+math.exp(-dt/self.lambda_time_s)*following;adv[i]=following
        self.pending.append([dict(f,target=targets[i],adv=adv[i],cost=costs[i]) for i,f in enumerate(frames)]);self.episodes+=1
        if len(self.pending)==2:self.update()
    def update(self):
        frames=[f for ep in self.pending for f in ep];x=torch.from_numpy(np.stack([f['x'] for f in frames]));mask=torch.from_numpy(np.stack([f['mask'] for f in frames]));target=torch.tensor(np.stack([f['target'] for f in frames]),dtype=torch.float32)
        action=torch.tensor([f['index'] for f in frames]);old=torch.tensor([f['old_logp'] for f in frames]);valid=torch.tensor([f['learn_actor'] for f in frames]);advantage=torch.tensor(-np.stack([f['adv'] for f in frames])@np.array(WEIGHTS),dtype=torch.float32)
        if valid.sum()>1:advantage=(advantage-advantage[valid].mean())/advantage[valid].std(unbiased=False).clamp_min(1e-6)
        losses=[];kls=[];anchor_kls=[]
        for epoch in range(4):
            for ids in torch.randperm(len(frames),generator=self.shuffle_rng).split(256):
                logits,values=self.forward(x[ids],mask[ids]);lp=(logits/self.temperature).log_softmax(-1);selected=lp.gather(1,action[ids,None]).squeeze(1);ratio=(selected-old[ids]).exp()
                surrogate=torch.minimum(ratio*advantage[ids],ratio.clamp(.8,1.2)*advantage[ids]);actor=-(surrogate*valid[ids]).mean();entropy=-(lp.exp()*lp).sum(-1);anchor_kl=torch.zeros_like(entropy)
                if self.anchor is not None:
                    with torch.no_grad():prior=(self.anchor(x[ids],mask[ids])[0]/self.temperature).log_softmax(-1)
                    anchor_kl=(prior.exp()*(prior-lp)).sum(-1)
                critic=(values-target[ids]).square().mean();loss=actor-.003*(entropy*valid[ids]).mean()+.01*(anchor_kl*valid[ids]).mean()+.5*critic
                if not torch.isfinite(loss):raise ValueError('Nonfinite split PPO')
                self.actor_optimizer.zero_grad();self.critic_optimizer.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(self.actor_parameters,1.);torch.nn.utils.clip_grad_norm_(self.net.critic.parameters(),1.);self.actor_optimizer.step();self.critic_optimizer.step();self.steps+=1
                losses.append(float(loss.detach()));anchor_kls.append(float(anchor_kl.mean().detach()));kls.append(float(((ratio-1)-(selected-old[ids]))[valid[ids]].mean().detach()) if valid[ids].any() else 0.)
            if max(kls)>.05:break
        self.updates+=1;self.logs.append(dict(update=self.updates,episodes=self.episodes,steps=self.steps,frames=len(frames),loss_mean=float(np.mean(losses)),max_KL=max(kls),anchor_KL=float(np.mean(anchor_kls)),network_sha256=digest(self.net)));self.pending=[]
    def distill(self,x,mask,teacher,epochs=64):
        x=torch.from_numpy(x);mask=torch.from_numpy(mask);teacher=torch.tensor(teacher);valid=torch.arange(len(x))%5==0;train=torch.nonzero(~valid).flatten()
        for epoch in range(epochs):
            for ids in train[torch.randperm(len(train),generator=self.bc_rng)].split(256):
                logits,_=self.forward(x[ids],mask[ids]);lp=(logits/self.temperature).log_softmax(-1);target=.02*mask[ids]/mask[ids].sum(-1,keepdim=True);target.scatter_add_(1,teacher[ids,None],torch.full((len(ids),1),.98))
                loss=-(target*lp).sum(-1).mean();self.actor_optimizer.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(self.actor_parameters,1.);self.actor_optimizer.step();self.bc_steps+=1
            with torch.no_grad():
                correct=0;held_correct=0;held=0;conf=0.
                for ids in torch.arange(len(x)).split(512):
                    logits,_=self.forward(x[ids],mask[ids]);ok=logits.argmax(-1)==teacher[ids];correct+=int(ok.sum());held_correct+=int(ok[valid[ids]].sum());held+=int(valid[ids].sum());conf+=float((logits/self.temperature).softmax(-1).max(-1).values.sum())
            self.bc_logs.append(dict(epoch=epoch+1,all_accuracy=correct/len(x),held_state_accuracy=held_correct/held,mean_max_probability=conf/len(x),optimizer_steps=self.bc_steps));
            if (epoch+1)%8==0:print('BC_EPOCH',epoch+1,self.bc_logs[-1],flush=True)
    def snapshot(self):
        return copy.deepcopy(dict(version=VERSION,seed=self.seed,network=self.net.state_dict(),actor_optimizer=self.actor_optimizer.state_dict(),critic_optimizer=self.critic_optimizer.state_dict(),action_rng=self.action_rng.get_state(),shuffle_rng=self.shuffle_rng.get_state(),bc_rng=self.bc_rng.get_state(),episodes=self.episodes,updates=self.updates,steps=self.steps,pending=self.pending,logs=self.logs,bc_logs=self.bc_logs,bc_steps=self.bc_steps,anchor=self.anchor.state_dict() if self.anchor is not None else None,network_sha256=digest(self.net),temperature=self.temperature,lambda_time_s=self.lambda_time_s))
