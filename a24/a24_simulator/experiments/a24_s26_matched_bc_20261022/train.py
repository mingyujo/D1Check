"""Original BC50 action classification/pair loss, fixed 128-epoch matched TRAIN."""
import copy,math,time
from a24_nn_urgent_tie_20261021.train import losses,margins_for
from a24_fair_nn_bc_20261021.train import accuracy
from a24_atc_bc_20261019.learner import Learner,digest
from common_transfer import np,torch,equal
EPOCHS=128

def fit(initial,frames,receipt,stage):
    assert receipt['durable_START_consumed'] and 0<len(frames)<=15360 and all(f['split']=='TRAIN' for f in frames)
    learner=Learner(state=initial);learner.bc_rng.manual_seed(202610220+stage);start=time.monotonic();x=torch.from_numpy(np.stack([f['x'] for f in frames]));mask=torch.from_numpy(np.stack([f['mask'] for f in frames]));target=torch.from_numpy(np.stack([f['teacher_mask'] for f in frames]));margins=torch.from_numpy(margins_for(frames));ids=torch.nonzero(mask.sum(1)>1,as_tuple=True)[0]
    assert len(ids)>0 and target.sum(1).eq(1).all() and not (target&~mask).any() and torch.isfinite(x).all()
    counts={g:sum(frames[i]['group']==g for i in ids.tolist()) for g in sorted({frames[i]['group'] for i in ids.tolist()})};weights=torch.tensor([min(2.,max(.5,len(ids)/(len(counts)*counts[f['group']]))) if f['group'] in counts else 0 for f in frames],dtype=torch.float32);opt=torch.optim.Adam(learner.actor_parameters,lr=2e-4,eps=1e-5);before=accuracy(learner.net,x,mask,target,frames);logs=[];steps=learner.bc_steps;critic=copy.deepcopy(learner.net.critic.state_dict())
    for ep in range(EPOCHS):
        assert time.monotonic()-start<3600,'Finite fit wall cap';lr=2e-5+.5*(2e-4-2e-5)*(1+math.cos(math.pi*ep/(EPOCHS-1)))
        for g in opt.param_groups:g['lr']=lr
        totals=[]
        for part in ids[torch.randperm(len(ids),generator=learner.bc_rng)].split(256):
            logits=learner.net(x[part],mask[part])[0]/learner.temperature;ce,pair=losses(logits,target[part],mask[part],margins[part]);loss=((ce+.25*pair)*weights[part]).mean();assert torch.isfinite(loss);opt.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(learner.actor_parameters,1.);opt.step();learner.bc_steps+=1;totals.append(float(loss.detach()))
        if ep==0 or (ep+1)%16==0 or ep==EPOCHS-1:
            ac=accuracy(learner.net,x,mask,target,frames);logs.append(dict(epoch=ep+1,loss=sum(totals)/len(totals),accuracy=ac,LR=lr,new_steps=learner.bc_steps-steps));print('MATCHED_BC',stage,logs[-1],flush=True)
    equal(learner.net.critic.state_dict(),critic);state=learner.snapshot();assert all(state[k]==initial[k] for k in ['updates','episodes','steps'])
    return state,dict(status='COMPLETE',kind='MASKED_ACTION_CLASSIFICATION_BC_ADAPTIVE_PAIR_MARGIN',initial=before,logs=logs,epochs=EPOCHS,new_BC_steps=learner.bc_steps-steps,initial_network_sha256=initial['network_sha256'],network_sha256=digest(learner.net),TRAIN_frames=len(frames),nontrivial_frames=len(ids),groups=counts,optimizer=copy.deepcopy(opt.state_dict()),shuffle_rng=learner.bc_rng.get_state(),group_weights=weights,pairwise_margins=margins,critic_unchanged=True,cost_regression=False,EVAL_used_for_selection=False,seed=202610220+stage,ranking_weight=.25,class_weight_clip=[.5,2.],stage=stage,elapsed_s=time.monotonic()-start)
