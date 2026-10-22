"""Original fifty-feature neural BC; the fair teacher only supplies TRAIN labels."""
import copy,math
import numpy as np
from a24_service_bc_repair_20261021.policy import Policy as Fair,choose,TIE_TOL
from a24_atc_bc_20261019.candidates import build
from common_transfer import tie
VERSION='A24_FAIR_TEACHER_NEURAL_BC50_V1'

def features50(s,b,nominal,physics,case):
    context=build(s,nominal,physics);chosen=context['chosen'];visible=context['visible'];vectors=context['vectors'];free=context['free'];q=s['queue'];edf=sorted(q,key=lambda j:(j['deadline_ns'],*tie(j)))
    X=np.zeros((36,50),np.float32);sensor=s['sensor'];now=s['now_ns']/1e9;T=sensor['temperature_c']
    for i,(a,f) in enumerate(zip(b['actions'],b['forecasts'])):
        c=f['cost'];score=b['teacher_scores'][i];j=visible[a['request_id']] if a['kind']=='DISPATCH' else edf[0];route=a.get('route','CPU');vec=vectors[j['request_id'],route];ttl=max(.05,(j['deadline_ns']-j['scheduled_arrival_ns'])/1e9)
        thermal=sensor.get('heat',[0.,0.]);v=sensor.get('v',[0.,0.,0.]);z=sensor.get('z',[0.,0.,0.])
        row=[1.,float(a['kind']=='DISPATCH'),float(a['kind']=='WAIT'),float(a['kind']=='WAIT_EVENT'),float(route=='CPU'),float(route=='GPU'),float(j['task']=='C'),float(j['priority']=='U'),(now-j['scheduled_arrival_ns']/1e9)/10,(j['deadline_ns']/1e9-now)/10,sum(vec)/2,sum(vec[:2 if j['task']=='C' else 3])/2,ttl/10,len(q)/32,sum(x['priority']=='U' for x in q)/32,len(s['owners'])/4,float('CPU' in free),float('GPU' in free),(T-26)/10,sensor['shared_z'],*c,(f['AP_end']-26)/10,(f['peak']-26)/10,(f['H_s']-now)/30,score/10,a.get('wait_ns',0)/1e9,s['wait_used_ns']/1e9/max(1,case['supply_stop_s']-35),sum(o['route']=='CPU' for o in s['owners'])/3,float(physics.profile=='UNION'),float(physics.profile=='S26_STYLE'),*thermal,*v,*z,sensor['increment_so_far']/max(1,case['n']*.35),physics.speed(T,'CPU',1,j['task']),physics.speed(T,'GPU',1,j['task']),len(visible)/32,float(f['capped']),f['steps']/800]
        row.extend([(context['atc'][j['request_id'],route] if a['kind']=='DISPATCH' else context['best_atc'])/5,chosen.index(j)/max(1,len(chosen)-1) if a['kind']=='DISPATCH' else 0.])
        assert len(row)==50
        X[i]=[x if abs(x)<=5 else math.copysign(5+math.log1p(abs(x)-5),x) for x in row]
    return X

def labels(s,b,case,index,source_hash=None):
    scores=b['teacher_scores'];mask=b['mask'];best=min(scores[mask]);target=mask & (scores<=best+TIE_TOL);teacher=choose(scores,mask);a=b['actions'][teacher]
    group=a['kind'] if a['kind']!='DISPATCH' else next(q for q in s['queue'] if q['request_id']==a['request_id'])['task']+'_'+a['route']
    assert target[teacher] and not (target & ~mask).any()
    return dict(x=b['x'].copy(),mask=mask.copy(),teacher_mask=target.copy(),scores=scores.copy(),index=teacher,group=group,split='TRAIN',source_case=case,source_decision_index=index,source_public_sha256=source_hash)

class Policy:
    def __init__(self,nominal,physics,case,learner=None,collect=False):
        self.nominal,self.physics,self.case,self.learner,self.collect=nominal,physics,case,learner,collect
        self.fair=Fair(nominal,physics,case);self.calls=[];self.frames=[]
    def encode(self,s):
        b=self.fair.encode(s);b['x']=features50(s,b,self.nominal,self.physics,self.case);b['scores']=b['teacher_scores'];return b
    def __call__(self,s):
        b=self.encode(s);teacher=choose(b['teacher_scores'],b['mask'])
        if self.learner:index,_=self.learner.choose(b,False)
        else:index=teacher
        action=copy.deepcopy(b['actions'][index]);target=b['mask'] & (b['teacher_scores']<=min(b['teacher_scores'][b['mask']])+TIE_TOL)
        self.calls.append(dict(time_ns=s['now_ns'],action=action,chosen=index,teacher_index=teacher,version=VERSION,
            **{k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in b.items() if k not in ('actions','scores')},
            actions=b['actions'],teacher_mask=target.tolist(),post_NN_override=False,future_information=False))
        if self.collect:
            from common_transfer import B
            self.frames.append(labels(s,b,self.case['id'],len(self.calls)-1,B.L.digest(s)))
        return action
