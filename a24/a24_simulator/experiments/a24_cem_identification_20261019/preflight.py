import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import json,math,ast
from pathlib import Path
import numpy as np
import torch
from learner import Learner,cem_update
H=Path(__file__).resolve().parent
for n in ('learner.py','objective.py','run_policy.py'):ast.parse((H/n).read_text(encoding='utf-8'))
rng=np.random.default_rng(87291);l=Learner(202610191);x=rng.normal(size=(36,48)).astype(np.float32);mask=np.arange(36)<19;bank=dict(x=x,mask=mask,scores=np.zeros(36,np.float32));s=l.snapshot();i,f=l.choose(bank,True);r=Learner(202610191);r.restore(s);i2,f2=r.choose(bank,True);assert i==i2 and f['uniform']==f2['uniform']
e=np.tanh(x.astype(float));w=l.net.weight.detach().numpy().astype(float);raw=e@w;logits=3*np.tanh(raw/3);p=np.exp(logits[mask]-max(logits[mask]));p/=p.sum();dl=(1-np.tanh(raw[mask]/3)**2)[:,None]*e[mask];analytic=dl[i]-p@dl
l.optimizer.zero_grad();lp=l.net(torch.tensor(x),torch.tensor(mask)).log_softmax(-1);lp[i].backward();err=float(max(abs(analytic-l.net.weight.grad.detach().numpy())));assert err<2e-6
mu=rng.normal(size=48);sig=np.full(48,.5);z=rng.normal(size=(4,48));cand=mu+sig*np.r_[z,-z];cost=rng.normal(size=8);a,b,o=cem_update(mu,sig,cand,cost);order=sorted(range(8),key=lambda k:(cost[k],k))[:3];mean=sum(t*cand[k] for t,k in zip([.5,.3,.2],order));variance=sum(t*(cand[k]-mean)**2 for t,k in zip([.5,.3,.2],order));assert np.array_equal(o,order) and np.max(abs(a-(.3*mu+.7*mean)))<1e-15 and np.max(abs(b-np.maximum(.2,np.sqrt(.8*sig**2+.2*variance))))<1e-15
with (H/'PREFLIGHT.json').open('x',encoding='utf-8') as f:json.dump(dict(status='PASS',environment_START=0,physical_fits=0,actor_logprob_gradient_max_error=err,RNG_restore_exact=True,CEM_update_independent=True,python_AST=True),f,indent=2)
print('PREFLIGHT_PASS',err)
