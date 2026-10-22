"""Declared supervised warmstart on TRAIN demonstrations; not a PPO update."""
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

def pretrain(parent,demos,seed=781000):
    learner=Learner(seed);learner.net.load_state_dict(parent['network']);learner.net.temperature=.35
    with torch.no_grad():learner.net.critic[-1].weight.zero_();learner.net.critic[-1].bias.zero_()
    initial=learner.snapshot();optimizer=torch.optim.Adam(learner.net.parameters(),lr=1e-3,eps=1e-5);rng=torch.Generator().manual_seed(seed+90000)
    frames=[f for d in demos for f in d['frames']];x=torch.from_numpy(np.stack([f['x'] for f in frames]));mask=torch.from_numpy(np.stack([f['mask'] for f in frames]));labels=torch.tensor([f['index'] for f in frames])
    logs=[];steps=0
    for epoch in range(1,9):
        losses=[]
        for ix in torch.randperm(len(frames),generator=rng).split(256):
            logits,_=learner.net(x[ix],mask[ix]);loss=nn.functional.cross_entropy(logits,labels[ix]);optimizer.zero_grad();loss.backward();nn.utils.clip_grad_norm_(learner.net.parameters(),1.);optimizer.step();steps+=1;losses.append(float(loss.detach()))
        with torch.no_grad():
            good=0
            for ix in torch.arange(len(frames)).split(256):good+=int((learner.net(x[ix],mask[ix])[0].argmax(-1)==labels[ix]).sum())
        logs.append(dict(epoch=epoch,loss=float(np.mean(losses)),TRAIN_demonstration_accuracy=good/len(frames),steps=steps,weight_sha256=digest(learner.net)))
        if good/len(frames)>=.99:break
    return learner,dict(initial=initial,optimizer=copy.deepcopy(optimizer.state_dict()),shuffle_rng=rng.get_state(),logs=logs,steps=steps,frames=len(frames),new_PPO_updates=0,not_RL_training=True)
