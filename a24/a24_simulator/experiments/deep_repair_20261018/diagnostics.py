"""Saved-data gradient probes, not optimizer updates or environment samples."""
import math
from common import B,HERE,ROOT,np,torch,loadpt,read
from nn_train import Net
from dynamics import WEIGHTS
def run(out):
    old=ROOT/'results/GUARD_LEARNING_20261018_01';records=[]
    for arm in ('FT_ON_NN','FT_OFF_NN','REPAIR_OFF_NN'):
        for ep in (2,8,16,32):
            label=f'{arm}_TRAIN_{ep:03d}';before=loadpt(old/(label+'.BEFORE.pt.gz'));data=loadpt(old/(label+'.frames.pt.gz'));net=Net();net.load_state_dict(before['network']);frames=data['frames'];cost=np.asarray(data['costs']);values=np.stack([f['value'] for f in frames]);targets=np.cumsum(cost[::-1],axis=0)[::-1].copy();adv=np.zeros_like(cost);following=np.zeros(5)
            for i in reversed(range(len(frames))):
                nv=values[i+1] if i+1<len(frames) else np.zeros(5);dt=(frames[i+1]['time_ns']-frames[i]['time_ns'])/1e9 if i+1<len(frames) else 0.
                following=cost[i]+nv-values[i]+math.exp(-dt/20.)*following;adv[i]=following
            full=[f for pending in before['pending'] for f in pending]+[dict(f,target=targets[i],adv=adv[i]) for i,f in enumerate(frames)]
            ids=np.linspace(0,len(full)-1,min(256,len(full)),dtype=int);chosen=[full[i] for i in ids];x=torch.from_numpy(np.stack([f['x'] for f in chosen]));mask=torch.from_numpy(np.stack([f['mask'] for f in chosen]));action=torch.tensor([f['index'] for f in chosen]);valid=torch.tensor([f['learn_actor'] for f in chosen]);advantage=torch.tensor(-np.stack([f['adv'] for f in chosen])@np.array(WEIGHTS),dtype=torch.float32)
            if valid.sum()>1:advantage=(advantage-advantage[valid].mean())/advantage[valid].std(unbiased=False).clamp_min(1e-6)
            logits,pred=net(x,mask);lp=logits.log_softmax(-1);actor=-(lp.gather(1,action[:,None]).squeeze(1)*advantage*valid).mean();critic=.5*(pred-torch.tensor(np.stack([f['target'] for f in chosen]),dtype=torch.float32)).square().mean()
            ga=torch.cat([v.flatten() for v in torch.autograd.grad(actor,tuple(net.encode.parameters()),retain_graph=True)]);gc=torch.cat([v.flatten() for v in torch.autograd.grad(critic,tuple(net.encode.parameters()))]);dot=float(ga@gc);na=float(ga.norm());nc=float(gc.norm());records.append(dict(label=label,frames=len(chosen),actor_gradient=ga.tolist(),critic_gradient=gc.tolist(),actor_norm=na,critic_norm=nc,cosine=dot/max(1e-30,na*nc),critic_to_actor_norm=nc/max(1e-30,na)))
    B.G.write_new(out/'GRADIENT_PROBES.json',dict(scope='Saved diagnostic backward passes only; not actual optimizer steps',new_environment_START=0,new_optimizer_steps=0,records=records))
