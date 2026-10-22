"""TRAIN-only rare-route group-balanced distillation. Runtime NN stays unconstrained."""
import copy
import numpy as np
import torch
from torch import nn
from nn_train import Learner,digest

def teacher(bank):
    x=np.asarray(bank['x']);mask=np.asarray(bank['mask'],bool)
    matching=[i for i,a in enumerate(bank['actions']) if mask[i] and a['kind']=='DISPATCH' and x[i,31]>.5]
    if matching:return min(matching,key=lambda i:(float(x[i,8]),bank['actions'][i]['ordinal'],i))
    waiting=[i for i,a in enumerate(bank['actions']) if mask[i] and a['kind']=='WAIT_EVENT']
    if not waiting:raise ValueError('No preferred legal dispatch or owner-event action')
    return waiting[0]

def targets(frame):
    bank=dict(x=frame['x'],mask=frame['mask'],actions=frame['candidate_actions']);index=teacher(bank);action=bank['actions'][index];compatible=np.zeros(len(bank['mask']),bool)
    if action['kind']=='WAIT_EVENT':
        group='WAIT_EVENT'
        for i,a in enumerate(bank['actions']):compatible[i]=bool(bank['mask'][i] and a['kind']=='WAIT_EVENT')
    else:
        group=action['route'];deadline=float(bank['x'][index,8])
        for i,a in enumerate(bank['actions']):compatible[i]=bool(bank['mask'][i] and a['kind']=='DISPATCH' and a.get('route')==action['route'] and bank['x'][i,31]>.5 and abs(float(bank['x'][i,8])-deadline)<1e-9)
    assert compatible[index] and not np.any(compatible & ~np.asarray(bank['mask'],bool))
    return compatible,group,index

def pretrain(parent,demos,seed=881000):
    learner=Learner(seed);learner.net.load_state_dict(parent['network']);learner.net.temperature=.35
    with torch.no_grad():learner.net.critic[-1].weight.zero_();learner.net.critic[-1].bias.zero_()
    initial=learner.snapshot();optimizer=torch.optim.Adam(learner.net.parameters(),lr=1e-3,eps=1e-5);rng=torch.Generator().manual_seed(seed+90000)
    frames=copy.deepcopy([f for d in demos for f in d['frames']])
    for f in frames:
        ordered=list(dict.fromkeys(a['ordinal'] for a in f['candidate_actions'] if a['kind']=='DISPATCH'))
        for j,a in enumerate(f['candidate_actions']):
            if a['kind']=='DISPATCH':f['x'][j,30]=ordered.index(a['ordinal'])/max(1,len(ordered)-1)
    x=torch.from_numpy(np.stack([f['x'] for f in frames]));mask=torch.from_numpy(np.stack([f['mask'] for f in frames]));labels=torch.tensor([f['index'] for f in frames]);pairs=[targets(f) for f in frames]
    compatible=torch.from_numpy(np.stack([p[0] for p in pairs]));groups=sorted({p[1] for p in pairs});counts={g:sum(p[1]==g for p in pairs) for g in groups};weights=torch.tensor([len(frames)/(len(groups)*counts[p[1]]) for p in pairs],dtype=torch.float32);group_indices={g:torch.tensor([i for i,p in enumerate(pairs) if p[1]==g]) for g in groups}
    logs=[];steps=0
    for epoch in range(1,65):
        losses=[]
        for ix in torch.randperm(len(frames),generator=rng).split(256):
            logits,_=learner.net(x[ix],mask[ix]);losses_i=logits.logsumexp(-1)-logits.masked_fill(~compatible[ix],-1e9).logsumexp(-1);loss=(losses_i*weights[ix]).mean();optimizer.zero_grad();loss.backward();nn.utils.clip_grad_norm_(learner.net.parameters(),1.);optimizer.step();steps+=1;losses.append(float(loss.detach()))
        with torch.no_grad():
            predicted=torch.cat([learner.net(x[ix],mask[ix])[0].argmax(-1) for ix in torch.arange(len(frames)).split(256)]);good=compatible.gather(1,predicted[:,None]).squeeze(1);per={g:float(good[ix].float().mean()) for g,ix in group_indices.items()}
        logs.append(dict(epoch=epoch,loss=float(np.mean(losses)),TRAIN_demonstration_accuracy=float((predicted==labels).float().mean()),TRAIN_compatible_accuracy=float(good.float().mean()),TRAIN_group_accuracy=per,steps=steps,weight_sha256=digest(learner.net)))
        if float(good.float().mean())>=.995 and min(per.values())>=.99 and logs[-1]['loss']<=.05:break
    return learner,dict(initial=initial,optimizer=copy.deepcopy(optimizer.state_dict()),shuffle_rng=rng.get_state(),logs=logs,steps=steps,frames=len(frames),group_counts=counts,compatible=compatible,group_weights=weights,new_PPO_updates=0,not_RL_training=True)
