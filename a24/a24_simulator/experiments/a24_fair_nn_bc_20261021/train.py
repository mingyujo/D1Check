"""Bounded weighted action-classification BC, no cost regression or PPO."""
import copy,math,time
from a24_atc_bc_20261019.learner import Learner,digest
from common_transfer import np,torch,equal

def accuracy(net,x,mask,target,frames):
    with torch.no_grad():pred=torch.cat([net(x[i],mask[i])[0].argmax(-1) for i in torch.arange(len(x)).split(256)])
    good=target.gather(1,pred[:,None]).squeeze(1);nontrivial=mask.sum(-1)>1
    return dict(all=float(good.float().mean()),nontrivial=float(good[nontrivial].float().mean()) if nontrivial.any() else None,
        nontrivial_n=int(nontrivial.sum()),per_group={g:float(good[torch.tensor([i for i,f in enumerate(frames) if f['group']==g])].float().mean()) for g in sorted({f['group'] for f in frames})})

def fit(initial,frames,receipt,stage):
    assert receipt['durable_START_consumed'] and 0<len(frames)<=20000 and all(f['split']=='TRAIN' for f in frames)
    learner=Learner(state=initial);learner.bc_rng.manual_seed(20261021+stage*1000);start=time.monotonic()
    x=torch.from_numpy(np.stack([f['x'] for f in frames]));mask=torch.from_numpy(np.stack([f['mask'] for f in frames]));target=torch.from_numpy(np.stack([f['teacher_mask'] for f in frames]));assert target.any(1).all() and not (target & ~mask).any() and torch.isfinite(x).all()
    ids_all=torch.nonzero(mask.sum(1)>1,as_tuple=True)[0];assert len(ids_all)>0
    counts={g:sum(frames[i]['group']==g for i in ids_all.tolist()) for g in sorted({frames[i]['group'] for i in ids_all.tolist()})}
    weights=torch.tensor([len(ids_all)/(len(counts)*counts[f['group']]) if f['group'] in counts else 0 for f in frames],dtype=torch.float32)
    opt=torch.optim.Adam(learner.actor_parameters,lr=3e-4,eps=1e-5);before=accuracy(learner.net,x,mask,target,frames);logs=[];steps=learner.bc_steps;critic=copy.deepcopy(learner.net.critic.state_dict())
    for ep in range(256):
        assert time.monotonic()-start<3600,'Finite fit wall cap'
        lr=3e-5+.5*(3e-4-3e-5)*(1+math.cos(math.pi*ep/255))
        for g in opt.param_groups:g['lr']=lr
        losses=[]
        for part in ids_all[torch.randperm(len(ids_all),generator=learner.bc_rng)].split(256):
            logits=learner.net(x[part],mask[part])[0]/learner.temperature
            loss=((logits.logsumexp(-1)-logits.masked_fill(~target[part],-1e9).logsumexp(-1))*weights[part]).mean();assert torch.isfinite(loss)
            opt.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(learner.actor_parameters,1.);opt.step();learner.bc_steps+=1;losses.append(float(loss.detach()))
        metrics=accuracy(learner.net,x,mask,target,frames);logs.append(dict(epoch=ep+1,loss=sum(losses)/len(losses),accuracy=metrics,LR=lr,new_steps=learner.bc_steps-steps))
        if ep==0 or (ep+1)%16==0:print('NEURAL_BC',stage,logs[-1],flush=True)
        if metrics['all']>=.995 and metrics['nontrivial']>=.995 and min(metrics['per_group'].values())>=.99 and logs[-1]['loss']<=.05:break
    equal(learner.net.critic.state_dict(),critic);state=learner.snapshot();assert all(state[k]==initial[k] for k in ('updates','episodes','steps'))
    return state,dict(status='COMPLETE',kind='MASKED_ACTION_CLASSIFICATION_BC',stage=stage,initial=before,logs=logs,epochs=len(logs),new_BC_steps=learner.bc_steps-steps,
        initial_network_sha256=initial['network_sha256'],network_sha256=digest(learner.net),TRAIN_frames=len(frames),nontrivial_frames=len(ids_all),groups=counts,
        optimizer=copy.deepcopy(opt.state_dict()),shuffle_rng=learner.bc_rng.get_state(),group_weights=weights,critic_unchanged=True,cost_regression=False,EVAL_used_for_selection=False)
