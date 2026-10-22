"""Action classification plus hard-negative margin, never cost regression."""
import copy,math,time
from a24_atc_bc_20261019.learner import Learner,digest
from a24_fair_nn_bc_20261021.train import accuracy
from common_transfer import np,torch,equal

def losses(logits,target,mask):
    ce=logits.logsumexp(-1)-logits.masked_fill(~target,-1e9).logsumexp(-1)
    positive=logits.masked_fill(~target,-1e9).max(-1).values
    negative_mask=mask&~target;negative=logits.masked_fill(~negative_mask,-1e9).max(-1).values
    rank=torch.relu(.5+negative-positive)*negative_mask.any(-1)
    return ce,rank

def fit(initial,frames,receipt,relative):
    assert receipt['durable_START_consumed'] and 0<len(frames)<=20000 and all(f['split']=='TRAIN' for f in frames)
    learner=Learner(state=initial);learner.bc_rng.manual_seed(20261021+4000);start=time.monotonic()
    key='x' if relative else 'absolute_x';x=torch.from_numpy(np.stack([f[key] for f in frames]));mask=torch.from_numpy(np.stack([f['mask'] for f in frames]));target=torch.from_numpy(np.stack([f['teacher_mask'] for f in frames]))
    assert target.any(1).all() and not (target&~mask).any() and torch.isfinite(x).all();ids_all=torch.nonzero(mask.sum(1)>1,as_tuple=True)[0]
    counts={g:sum(frames[i]['group']==g for i in ids_all.tolist()) for g in sorted({frames[i]['group'] for i in ids_all.tolist()})}
    weights=torch.tensor([min(2.,max(.5,len(ids_all)/(len(counts)*counts[f['group']]))) if f['group'] in counts else 0 for f in frames],dtype=torch.float32)
    opt=torch.optim.Adam(learner.actor_parameters,lr=3e-4,eps=1e-5);before=accuracy(learner.net,x,mask,target,frames);logs=[];steps=learner.bc_steps;critic=copy.deepcopy(learner.net.critic.state_dict())
    for ep in range(256):
        assert time.monotonic()-start<3600,'Finite fit wall cap'
        lr=3e-5+.5*(3e-4-3e-5)*(1+math.cos(math.pi*ep/255))
        for g in opt.param_groups:g['lr']=lr
        totals=[]
        for part in ids_all[torch.randperm(len(ids_all),generator=learner.bc_rng)].split(256):
            logits=learner.net(x[part],mask[part])[0]/learner.temperature;ce,rank=losses(logits,target[part],mask[part]);loss=((ce+.25*rank)*weights[part]).mean();assert torch.isfinite(loss)
            opt.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(learner.actor_parameters,1.);opt.step();learner.bc_steps+=1;totals.append((float(loss.detach()),float(ce.mean().detach()),float(rank.mean().detach())))
        metrics=accuracy(learner.net,x,mask,target,frames);logs.append(dict(epoch=ep+1,loss=sum(v[0] for v in totals)/len(totals),CE=sum(v[1] for v in totals)/len(totals),ranking=sum(v[2] for v in totals)/len(totals),accuracy=metrics,LR=lr,new_steps=learner.bc_steps-steps))
        if ep==0 or (ep+1)%16==0:print('MARGIN_BC',relative,logs[-1],flush=True)
    equal(learner.net.critic.state_dict(),critic);state=learner.snapshot();assert all(state[k]==initial[k] for k in ('updates','episodes','steps'))
    return state,dict(status='COMPLETE',kind='MASKED_ACTION_CLASSIFICATION_BC_WITH_HARD_NEGATIVE_MARGIN',relative_cost_input=relative,
        initial=before,logs=logs,epochs=256,new_BC_steps=learner.bc_steps-steps,initial_network_sha256=initial['network_sha256'],network_sha256=digest(learner.net),TRAIN_frames=len(frames),nontrivial_frames=len(ids_all),groups=counts,
        optimizer=copy.deepcopy(opt.state_dict()),shuffle_rng=learner.bc_rng.get_state(),group_weights=weights,critic_unchanged=True,cost_regression=False,EVAL_used_for_selection=False,paired_fit_seed=20265021,margin=.5,ranking_weight=.25,class_weight_clip=[.5,2.])
