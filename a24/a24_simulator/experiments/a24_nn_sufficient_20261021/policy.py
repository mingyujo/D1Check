"""Same BC50 Net, sufficient public cost statistics instead of nuisance inputs."""
import math
import numpy as np
from a24_nn_urgent_tie_20261021.policy import Policy as Previous
VERSION='A24_BC50_SUFFICIENT_COST_SCALE_POSITION_V5'
ACTIVE_INPUTS=(27,28,49)

def project(x,scores,mask):
    full=np.asarray(x,np.float32);mask=np.asarray(mask,bool);scores=np.asarray(scores,np.float64)
    scale=max(1e-6,float(scores[mask].std()));out=np.zeros_like(full);valid=full[:,0]!=0
    out[:,28]=full[:,28];out[:,49]=full[:,49];out[valid,27]=math.log1p(scale/1e-6)/10
    assert np.isfinite(out).all();return out

class Policy(Previous):
    def encode(self,s):
        b=super().encode(s);b['full_x']=b['x'].copy();b['x']=project(b['x'],b['teacher_scores'],b['mask']);return b
    def __call__(self,s):
        action=super().__call__(s);c=self.calls[-1];c['version']=VERSION;c['minimal_sufficient_input']=True;c.pop('full_x',None);return action
