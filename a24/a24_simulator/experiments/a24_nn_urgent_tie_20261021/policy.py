"""Original BC50 Net; TRAIN-calibrated urgent slack and public action position."""
import copy
import numpy as np
from a24_nn_margin_exact_20261021.policy import Policy as Previous,relative_cost
from a24_service_bc_repair_20261021.policy import choose,TIE_TOL
VERSION='A24_BC50_URGENT_RESIDUAL_SLACK_ACTION_POSITION_V4'

def repair_bank(s,b,risk):
    b=dict(b);b['x']=np.array(b['x'],np.float32,copy=True)
    for key in ('mask','idle_mask','physical_mask'):b[key]=np.asarray(b[key],bool).copy()
    b['teacher_scores']=np.asarray(b['teacher_scores'],np.float64)
    b['features']=np.asarray(b['features'],np.float64)
    b['previous_service_mask']=b['mask'].copy()
    pending={q['request_id']:q for q in [*s['queue'],*s['owners']] if q.get('response_ns') is None}
    pairs=[]
    for f,pair in zip(b['forecasts'],b['service_pairs']):
        visible=set(f['visible_ids']);risky=0
        for rid,q in pending.items():
            if rid not in visible or q['priority']!='U':continue
            end=f['responses_s'].get(rid,f['H_s'])
            risky+=rid not in f['responses_s'] or end+risk[q['task']]>q['deadline_ns']/1e9+TIE_TOL
        pairs.append([int(risky),pair['late_ALL'],pair['late_U']])
    allowed=np.flatnonzero(b['idle_mask']);best=min(tuple(pairs[i]) for i in allowed)
    mask=np.zeros(36,bool)
    for i in allowed:mask[i]=tuple(pairs[i])==best
    critical=[v['index'] for v in b['service_guard']['critical_normal']]
    forced=[i for i in critical if mask[i]]
    if forced:mask[:]=False;mask[forced]=True
    assert mask.any()
    b['mask']=mask;b['risk_pairs']=pairs;b['risk_guard']=dict(best=list(best),task_margin_s=dict(risk),calibration='TRAIN-only 0.90 nearest-rank positive dispatch response residual; per task',priority='buffered urgent late, nominal total late, nominal urgent late')
    b['service_guard']=dict(b['service_guard'],forced_normal_indices=forced,priority='Critical normals within buffered urgent / total service optimum')
    b['x'][:,28],b['cost_normalization']=relative_cost(b['teacher_scores'],mask)
    # Public enumeration order, including both routes and every WAIT. No target/rank.
    b['x'][:,49]=0
    for i in range(len(b['actions'])):b['x'][i,49]=i/35.
    b['scores']=b['teacher_scores'];return b

def labels(s,b,case,index,source_hash):
    teacher=choose(b['teacher_scores'],b['mask']);a=b['actions'][teacher]
    group=a['kind'] if a['kind']!='DISPATCH' else next(q for q in s['queue'] if q['request_id']==a['request_id'])['task']+'_'+a['route']
    target=np.zeros(36,bool);target[teacher]=True;compatible=b['mask']&(b['teacher_scores']<=min(b['teacher_scores'][b['mask']])+TIE_TOL)
    return dict(x=b['x'].copy(),mask=b['mask'].copy(),teacher_mask=target,scores=b['teacher_scores'].copy(),index=teacher,group=group,split='TRAIN',source_case=case,source_decision_index=index,source_public_sha256=source_hash,cost_compatible_mask=compatible,teacher_version=VERSION)

class Policy(Previous):
    def __init__(self,*args,risk,**kwargs):super().__init__(*args,relative=True,**kwargs);self.risk=dict(risk)
    def encode(self,s):return repair_bank(s,super().encode(s),self.risk)
    def __call__(self,s):
        b=self.encode(s);teacher=choose(b['teacher_scores'],b['mask']);index=self.learner.choose(b,False)[0] if self.learner else teacher
        action=copy.deepcopy(b['actions'][index]);target=np.zeros(36,bool);target[teacher]=True;compatible=b['mask']&(b['teacher_scores']<=min(b['teacher_scores'][b['mask']])+TIE_TOL)
        self.calls.append(dict(time_ns=s['now_ns'],action=action,chosen=index,teacher_index=teacher,version=VERSION,
            **{k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in b.items() if k not in ('actions','scores','absolute_x')},
            actions=b['actions'],teacher_mask=target.tolist(),cost_compatible_mask=compatible.tolist(),post_NN_override=False,future_information=False,relative_cost_input=True,training_label='single exact teacher index',public_action_position=True))
        if self.collect:
            from common_transfer import B
            self.frames.append(labels(s,b,self.case['id'],len(self.calls)-1,B.L.digest(s)))
        return action
