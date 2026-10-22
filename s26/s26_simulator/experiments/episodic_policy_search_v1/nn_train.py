"""Episodic return-only cross-entropy policy search; no critic or action labels."""
import copy,hashlib
import numpy as np
import torch
from torch import nn
torch.set_num_threads(1)

class Net(nn.Module):
    def __init__(self):
        super().__init__();self.weight=nn.Parameter(torch.randn(32)*.03);self.temperature=1.
    def forward(self,x,mask):
        raw=torch.tanh(x)@self.weight
        logits=3*torch.tanh(raw/3)/self.temperature
        return logits.masked_fill(~mask,-1e9),x.new_zeros((len(x),1))

def digest(net):
    h=hashlib.sha256()
    for name,t in sorted(net.state_dict().items()):h.update(name.encode());h.update(t.detach().numpy().tobytes())
    return h.hexdigest()

class Learner:
    def __init__(self,seed):
        self.seed=seed
        with torch.random.fork_rng(devices=[]):torch.manual_seed(seed);self.net=Net()
        self.action_rng=torch.Generator().manual_seed(seed+10000);self.parameter_rng=torch.Generator().manual_seed(seed+30000)
        self.episodes=self.updates=0;self.logs=[]
    def set_weight(self,w):
        with torch.no_grad():self.net.weight.copy_(torch.as_tensor(w,dtype=torch.float32))
    def choose(self,bank,collect):
        x=np.asarray(bank['x'],np.float32);mask=np.asarray(bank['mask'],bool)
        assert x.shape==(27,32) and mask.any() and np.isfinite(x).all()
        with torch.no_grad():
            logits,_=self.net(torch.from_numpy(x)[None],torch.from_numpy(mask)[None]);lp=logits.log_softmax(-1);i=int(torch.multinomial(lp.exp()[0],1,generator=self.action_rng))
        return i,dict(x=x.copy(),mask=mask.copy(),scores=bank['scores'].copy(),index=i,old_logp=float(lp[0,i]),value=0.,collect=collect,learn_actor=int(mask.sum())>1,network_sha256=digest(self.net))
    def add(self,frames,costs):
        assert all(f['collect'] and f['network_sha256']==digest(self.net) for f in frames)
        assert np.asarray(costs).shape==(len(frames),5) and np.isfinite(costs).all()
        self.episodes+=1  # Whole-session scalar return is consumed by the CEM generation, never action labels.
    def snapshot(self):
        return copy.deepcopy(dict(version='EPISODIC_RETURN_CEM32_V1',seed=self.seed,network=self.net.state_dict(),action_rng=self.action_rng.get_state(),parameter_rng=self.parameter_rng.get_state(),episodes=self.episodes,updates=self.updates,logs=self.logs,temperature=self.net.temperature,network_sha256=digest(self.net)))
    def restore(self,s):
        assert s['version']=='EPISODIC_RETURN_CEM32_V1';self.net.load_state_dict(s['network']);self.action_rng.set_state(s['action_rng']);self.parameter_rng.set_state(s['parameter_rng']);self.net.temperature=s['temperature']
        for k in ['episodes','updates','logs']:setattr(self,k,copy.deepcopy(s[k]))
        assert digest(self.net)==s['network_sha256']
