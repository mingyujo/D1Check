"""Shared public service constraints, fair aging cost and cost-distilled imitation."""
import copy,math
import numpy as np
from a24_atc_bc_20261019.candidates import build
from a24_idle_wait_repair_20261019.guard import filter_idle_waits
from .forecast import predict_actions

VERSION='A24_SERVICE_FIRST_COST_IMITATION6_V1'
FEATURE_NAMES=('energy_per_request_scaled','mean_heat','mean_relative_tardiness','max_relative_tardiness','unfinished_fraction','mean_relative_response')
TEACHER_WEIGHTS=np.array([1.,1.,6.,3.,3.,.2],np.float64)
TIE_TOL=1e-8

def choose(scores,mask):
    allowed=np.flatnonzero(mask)
    if not len(allowed):raise ValueError('No eligible action')
    best=min(float(scores[i]) for i in allowed)
    return next(int(i) for i in allowed if float(scores[i])<=best+TIE_TOL)

def service_features(s,f):
    pending={q['request_id']:q for q in [*s['queue'],*s['owners']] if q.get('response_ns') is None}
    pending={rid:q for rid,q in pending.items() if rid in f['visible_ids']}
    n=max(1,len(pending));late_all=late_u=0;tard=[];response=[]
    for rid,q in pending.items():
        due=q['deadline_ns']/1e9;arrival=q['scheduled_arrival_ns']/1e9;ttl=max(.05,due-arrival)
        responded=rid in f['responses_s'];end=f['responses_s'].get(rid,f['H_s'])
        late=not responded or end>due+1e-8
        late_all+=int(late);late_u+=int(late and q['priority']=='U')
        tard.append(max(0.,end-due)/ttl);response.append(max(0.,end-arrival)/ttl)
    x=[f['cost'][0]/.35,f['cost'][1],sum(tard)/n,max(tard,default=0.),f['cost'][4],sum(response)/n]
    return x,dict(late_ALL=late_all,late_U=late_u,pending=len(pending))

def critical_normals(s,actions,vectors,physics):
    max_wait=max((a.get('wait_ns',a.get('max_wait_ns',0))/1e9 for a in actions if a['kind']!='DISPATCH'),default=0.)
    threshold=max_wait+physics.c.tick_s;now=s['now_ns']/1e9
    cpu_infer=sum(o['route']=='CPU' and o['stage']==1 for o in s['owners']);lookup={q['request_id']:q for q in s['queue']};indices=[];records=[]
    for i,a in enumerate(actions):
        if a['kind']!='DISPATCH':continue
        q=lookup[a['request_id']]
        if q['priority']!='N':continue
        route=a['route'];v=vectors[q['request_id'],route];rate=physics.speed(s['sensor']['temperature_c'],route,1,q['task'])/(1+physics.beta*cpu_infer if route=='CPU' else 1.)
        elapsed=sum(v[:2 if q['task']=='C' else 3])-v[1]+v[1]/rate
        slack=q['deadline_ns']/1e9-now-elapsed
        if -TIE_TOL<=slack<=threshold+TIE_TOL:indices.append(i);records.append(dict(index=i,request_id=q['request_id'],slack_s=slack,nominal_response_s=elapsed))
    return indices,records,threshold

def service_mask(idle_mask,pairs,critical):
    mask=np.asarray(idle_mask,bool).copy();allowed=np.flatnonzero(mask)
    best=min((pairs[i]['late_ALL'],pairs[i]['late_U']) for i in allowed)
    for i in allowed:mask[i]=(pairs[i]['late_ALL'],pairs[i]['late_U'])==best
    feasible=[i for i in critical if mask[i]]
    if feasible:mask[:]=False;mask[feasible]=True
    assert mask.any()
    return mask,best,feasible

class Policy:
    def __init__(self,nominal,physics,case,model=None,collect=False):
        self.nominal,self.physics,self.case,self.model=nominal,physics,case,model
        self.collect=collect;self.calls=[];self.frames=[]
    def encode(self,s):
        ctx=build(s,self.nominal,self.physics);actions=[dict(kind='DISPATCH',request_id=q['request_id'],route=r) for q in ctx['chosen'] for r in ctx['free']]
        actions += [dict(kind='WAIT',wait_ns=t) for t in (20_000_000,50_000_000)]
        if s['owners']:actions.append(dict(kind='WAIT_EVENT',max_wait_ns=500_000_000))
        forecasts=predict_actions(s,actions,list(ctx['visible'].values()),ctx['vectors'],self.physics,self.case)
        physical=np.zeros(36,bool);physical[:len(actions)]=True
        idle,idle_record=filter_idle_waits(s,actions,forecasts,physical)
        features=np.zeros((36,6),np.float64);pairs=[]
        for i,f in enumerate(forecasts):features[i],pair=service_features(s,f);pairs.append(pair)
        critical,record,threshold=critical_normals(s,actions,ctx['vectors'],self.physics)
        mask,best,forced=service_mask(idle,pairs,critical)
        scores=features@TEACHER_WEIGHTS
        return dict(actions=actions,forecasts=forecasts,features=features,teacher_scores=scores,mask=mask,physical_mask=physical,idle_mask=idle,
                    idle_wait_guard=idle_record,service_pairs=pairs,service_guard=dict(best_late_pair=list(best),critical_normal=record,
                    critical_threshold_s=threshold,forced_normal_indices=forced,priority='lexicographic minimum total late count, then urgent late count'))
    def __call__(self,s):
        b=self.encode(s);scores=b['teacher_scores'] if self.model is None else predict_scores(self.model,b['features'])
        index=choose(scores,b['mask']);teacher=choose(b['teacher_scores'],b['mask']);action=copy.deepcopy(b['actions'][index])
        call=dict(time_ns=s['now_ns'],action=action,chosen=index,teacher_index=teacher,version=VERSION,
                  actions=b['actions'],forecasts=b['forecasts'],features=b['features'].tolist(),mask=b['mask'].tolist(),
                  physical_mask=b['physical_mask'].tolist(),idle_mask=b['idle_mask'].tolist(),idle_wait_guard=b['idle_wait_guard'],
                  service_pairs=b['service_pairs'],service_guard=b['service_guard'],teacher_scores=b['teacher_scores'].tolist(),
                  learned_scores=scores.tolist() if self.model is not None else None,post_model_override=False,future_information=False)
        self.calls.append(call)
        if self.collect:self.frames.append(dict(features=b['features'].copy(),mask=b['mask'].copy(),physical_mask=b['physical_mask'].copy(),
            targets=b['teacher_scores'].copy(),teacher_index=teacher,case=self.case['id'],split='TRAIN',decision=len(self.calls)-1))
        return action

def predict_scores(model,features):
    return (np.asarray(features,np.float64)/np.asarray(model['scales'],np.float64))@np.asarray(model['scaled_weights'],np.float64)

def fit(frames,receipt):
    if not receipt.get('durable_START_consumed') or not frames or any(f['split']!='TRAIN' for f in frames):raise ValueError('Registered TRAIN fit only')
    X=np.concatenate([f['features'][f['physical_mask']] for f in frames]);y=np.concatenate([f['targets'][f['physical_mask']] for f in frames])
    scales=np.sqrt((X*X).mean(0));active=scales>1e-12;scales=np.where(active,scales,1.)
    scaled=X[:,active]/scales[active];coef,residual,rank,singular=np.linalg.lstsq(scaled,y,rcond=1e-12)
    weights=np.zeros(6,np.float64);weights[active]=coef
    model=dict(version=VERSION,kind='SUPERVISED_TEACHER_COST_REGRESSION_IMITATION',feature_names=FEATURE_NAMES,
        scales=scales.tolist(),scaled_weights=weights.tolist(),active_features=active.tolist(),rank=int(rank),
        singular_values=singular.tolist(),frames=len(frames),candidate_targets=len(y),training_cases=sorted({f['case'] for f in frames}),
        fit_method='one unregularized float64 least-squares solve; no optimizer/epoch/EVAL selection',teacher_fallback=False,EVAL_used_for_selection=False)
    prediction=predict_scores(model,X);model['TRAIN_RMSE']=float(np.sqrt(np.mean((prediction-y)**2)));model['TRAIN_max_score_error']=float(np.max(np.abs(prediction-y)))
    good=0;regret=0.
    for f in frames:
        i=choose(predict_scores(model,f['features']),f['mask']);best=min(f['targets'][f['mask']]);regret=max(regret,float(f['targets'][i]-best));good+=f['targets'][i]<=best+TIE_TOL
    model['TRAIN_compatible_accuracy']=float(good/len(frames));model['TRAIN_max_teacher_regret']=regret
    return model
