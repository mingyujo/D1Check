"""Same original A24 ABI/loss. Bounded warm-start BC with a fixed LR schedule."""
import copy, math
from a24_atc_bc_20261019.learner import Learner, digest
from common_transfer import np, torch
from torch import nn

def accuracy(net,x,mask,target,frames):
    with torch.no_grad():
        pred=torch.cat([net(x[ids],mask[ids])[0].argmax(-1) for ids in torch.arange(len(x)).split(256)])
        good=target.gather(1,pred[:,None]).squeeze(1)
    groups=sorted({f['group'] for f in frames})
    return float(good.float().mean()),{g:float(good[torch.tensor([f['group']==g for f in frames])].float().mean()) for g in groups}

def recover(initial,frames,*,fit_receipt,seed=20261021,epochs=256):
    assert fit_receipt.get('durable_START_consumed') and fit_receipt.get('start_id')
    assert 1<=epochs<=256 and 0<len(frames)<=7464
    assert all(f.get('split')=='TRAIN' and f.get('teacher_mask') is not None for f in frames)
    learner=Learner(state=initial);learner.bc_rng.manual_seed(seed+30000)
    x=torch.from_numpy(np.stack([f['x'] for f in frames]));mask=torch.from_numpy(np.stack([f['mask'] for f in frames]));target=torch.from_numpy(np.stack([f['teacher_mask'] for f in frames]))
    assert torch.isfinite(x).all() and target.any(1).all() and not (target & ~mask).any()
    groups=sorted({f['group'] for f in frames});counts={g:sum(f['group']==g for f in frames) for g in groups}
    weights=torch.tensor([len(frames)/(len(groups)*counts[f['group']]) for f in frames],dtype=torch.float32)
    before=accuracy(learner.net,x,mask,target,frames)
    opt=torch.optim.Adam(learner.actor_parameters,lr=3e-4,eps=1e-5);logs=[];start_steps=learner.bc_steps
    critic={k:v.clone() for k,v in learner.net.critic.state_dict().items()}
    for ep in range(epochs):
        lr=3e-5+.5*(3e-4-3e-5)*(1+math.cos(math.pi*ep/max(1,epochs-1)))
        for group in opt.param_groups:group['lr']=lr
        losses=[]
        for ids in torch.randperm(len(frames),generator=learner.bc_rng).split(256):
            logits,_=learner.net(x[ids],mask[ids]);logits=logits/learner.temperature
            loss=((logits.logsumexp(-1)-logits.masked_fill(~target[ids],-1e9).logsumexp(-1))*weights[ids]).mean()
            assert torch.isfinite(loss)
            opt.zero_grad();loss.backward();nn.utils.clip_grad_norm_(learner.actor_parameters,1.);opt.step();learner.bc_steps+=1;losses.append(float(loss.detach()))
        acc,per=accuracy(learner.net,x,mask,target,frames)
        logs.append(dict(epoch=ep+1,loss=sum(losses)/len(losses),compatible_accuracy=acc,per_route=per,LR=lr,new_steps=learner.bc_steps-start_steps))
        if ep==0 or (ep+1)%16==0:print('RECOVERY_BC',logs[-1],flush=True)
        if acc>=.995 and min(per.values())>=.99 and logs[-1]['loss']<=.05:break
    assert all(torch.equal(v,critic[k]) for k,v in learner.net.critic.state_dict().items())
    state=learner.snapshot();assert state['updates']==initial['updates'] and state['episodes']==initial['episodes'] and state['steps']==initial['steps']
    trace=dict(status='COMPLETE',frames=len(frames),groups=counts,initial_compatible_accuracy=before[0],initial_per_route=before[1],logs=logs,optimizer=copy.deepcopy(opt.state_dict()),group_weights=weights,shuffle_rng=learner.bc_rng.get_state(),seed=seed,epochs=len(logs),new_BC_steps=learner.bc_steps-start_steps,critic_unchanged=True,initial_network_sha256=initial['network_sha256'],network_sha256=digest(learner.net),EVAL_used_for_selection=False)
    return state,trace
