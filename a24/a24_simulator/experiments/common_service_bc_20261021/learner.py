"""Common original set Net; exact TRAIN classification, one finite aggregation."""
import copy, importlib.util, math, time
from pathlib import Path
import numpy as np
import torch
torch.set_num_threads(1)
R=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('common_original_bc',R/'common_simulator/v1/bc.py')
original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
VERSION='DEVICE_COMMON_SERVICE_BC_V2'

def fit(frames, *, seed, epochs=256, initial=None, receipt):
    assert receipt.get('durable_START_consumed') and receipt.get('start_id')
    assert frames and all(f['version']==VERSION and f['split']=='TRAIN' for f in frames)
    x=torch.tensor(np.asarray([f['x'] for f in frames],np.float32));mask=torch.tensor(np.asarray([f['mask'] for f in frames],bool))
    target=torch.tensor([f['teacher_index'] for f in frames]);scores=torch.tensor(np.asarray([f['scores'] for f in frames],np.float64))
    assert mask.gather(1,target[:,None]).all() and torch.isfinite(x).all()
    groups=sorted({f['group'] for f in frames});counts={g:sum(f['group']==g for f in frames) for g in groups}
    gw=torch.tensor([max(.5,min(2.,len(frames)/(len(groups)*counts[f['group']]))) for f in frames])
    with torch.random.fork_rng(devices=[]):torch.manual_seed(seed);net=original.Net()
    if initial:net.load_state_dict(initial['network'])
    params=[*net.encode.parameters(),*net.actor.parameters()];opt=torch.optim.Adam(params,lr=2e-4,eps=1e-5)
    rng=torch.Generator().manual_seed(seed+30000)
    if initial:opt.load_state_dict(initial['optimizer']);rng.set_state(initial['bc_rng'])
    initial_critic={k:v.clone() for k,v in net.state_dict().items() if k.startswith('critic.')}
    crit=scores.gather(1,target[:,None]);gap=(scores-crit).clamp(min=0);maxgap=gap.masked_fill(~mask,0).max(1,keepdim=True).values.clamp(min=1e-6)
    margin=(.002+.498*gap/maxgap).float();others=mask.clone();others.scatter_(1,target[:,None],False)
    logs=[];t0=time.monotonic();updates=0
    for epoch in range(epochs):
        if time.monotonic()-t0>3600:raise ValueError('Finite fit wall cap')
        lr=2e-4*(.1**(epoch/max(1,epochs-1)))
        for group in opt.param_groups:group['lr']=lr
        losses=[]
        for ids in torch.randperm(len(frames),generator=rng).split(256):
            logits,_=net(x[ids],mask[ids]);selected=logits.gather(1,target[ids,None])
            ce=torch.nn.functional.cross_entropy(logits/.35,target[ids],reduction='none')
            pair=(torch.relu(logits-selected+margin[ids])*others[ids]).sum(1)/others[ids].sum(1).clamp(min=1)
            loss=((ce+pair)*gw[ids]).mean()
            if not torch.isfinite(loss):raise ValueError('Nonfinite BC loss')
            opt.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(params,1.);opt.step();updates+=1;losses.append(float(loss.detach()))
        if epoch==0 or (epoch+1)%32==0 or epoch+1==epochs:
            correct=multi_correct=multi_n=0
            with torch.no_grad():
                for ids in torch.arange(len(frames)).split(256):
                    pred=net(x[ids],mask[ids])[0].argmax(1);good=pred==target[ids];multi=mask[ids].sum(1)>1;correct+=int(good.sum());multi_correct+=int((good&multi).sum());multi_n+=int(multi.sum())
            log=dict(epoch=epoch+1,loss=sum(losses)/len(losses),correct=correct,n=len(frames),accuracy=correct/len(frames),multi_correct=multi_correct,multi_n=multi_n,learning_rate=lr)
            logs.append(log);print('BC_EPOCH',log,flush=True)
    assert all(torch.equal(net.state_dict()[k],v) for k,v in initial_critic.items())
    return dict(version=VERSION,feature_width=50,actions=27,network=copy.deepcopy(net.state_dict()),network_sha256=original.network_hash(net),optimizer=copy.deepcopy(opt.state_dict()),bc_rng=rng.get_state().clone(),seed=seed,logs=logs,groups=counts,epochs=epochs,updates=updates,teacher_override=False,cost_regression=False,PPO=False,critic_unchanged=True,active_inputs=[27,28,49],synthetic_only=False)

def restore(state):
    assert state['version']==VERSION
    with torch.random.fork_rng(devices=[]):net=original.Net()
    net.load_state_dict(state['network']);assert original.network_hash(net)==state['network_sha256'];return net
