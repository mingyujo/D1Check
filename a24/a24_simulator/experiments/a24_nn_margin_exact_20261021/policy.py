"""Same BC50 actor. Only public cost feature 28 receives candidate normalization."""
import copy,math
import numpy as np
from a24_fair_nn_bc_20261021.policy import Policy as Previous,labels as base_labels
from a24_service_bc_repair_20261021.policy import choose,TIE_TOL
VERSION='A24_NEURAL_BC50_RELATIVE_COST_EXACT_ACTION_V3'
SCALE_FLOOR=1e-6

def labels(s,b,case,index,source_hash=None):
    f=base_labels(s,b,case,index,source_hash);f['cost_compatible_mask']=f['teacher_mask'].copy();f['teacher_mask'][:]=False;f['teacher_mask'][f['index']]=True;return f

def relative_cost(scores,mask):
    scores=np.asarray(scores,np.float64);mask=np.asarray(mask,bool)
    mean=float(scores[mask].mean());scale=max(SCALE_FLOOR,float(scores[mask].std()))
    z=np.zeros(36,np.float64);z[mask]=(scores[mask]-mean)/scale
    z=np.asarray([v if abs(v)<=5 else math.copysign(5+math.log1p(abs(v)-5),v) for v in z],np.float32)
    return z,dict(mean=mean,scale=scale,scope='eligible public candidate costs only',floor=SCALE_FLOOR)

class Policy(Previous):
    def __init__(self,*args,relative=True,**kwargs):super().__init__(*args,**kwargs);self.relative=relative
    def encode(self,s):
        b=super().encode(s);b['absolute_x']=b['x'].copy()
        if self.relative:b['x'][:,28],b['cost_normalization']=relative_cost(b['teacher_scores'],b['mask'])
        return b
    def __call__(self,s):
        b=self.encode(s);teacher=choose(b['teacher_scores'],b['mask']);index=self.learner.choose(b,False)[0] if self.learner else teacher
        action=copy.deepcopy(b['actions'][index]);cost_target=b['mask']&(b['teacher_scores']<=min(b['teacher_scores'][b['mask']])+TIE_TOL);target=np.zeros(36,bool);target[teacher]=True
        self.calls.append(dict(time_ns=s['now_ns'],action=action,chosen=index,teacher_index=teacher,version=VERSION,
            **{k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in b.items() if k not in ('actions','scores','absolute_x')},
            actions=b['actions'],teacher_mask=target.tolist(),cost_compatible_mask=cost_target.tolist(),post_NN_override=False,future_information=False,relative_cost_input=self.relative,training_label='exact teacher selected index; no equivalent-cost alternatives'))
        if self.collect:
            from common_transfer import B
            f=labels(s,b,self.case['id'],len(self.calls)-1,B.L.digest(s));f['absolute_x']=b['absolute_x'].copy();self.frames.append(f)
        return action
