"""New service-envelope list; old scheduler, model and actors are untouched.

Physical feasibility is separate from predicted performance admission.
The shared cheap Joint dispatcher is the fallback and forecast continuation.
Full prefix selection uses the original eight slots and three plant contexts.
"""
import copy,time
from contextlib import contextmanager
import numpy as np
import torch
from tools import d1_rolling_list_rl as r

JOINT='IE_JOINT_SERVICE_ENVELOPE_LIST_V1'
COST='IE_JOINT_SERVICE_ENVELOPE_COST_LIST_V1'
SCHEMA=r.c.digest(dict(version='joint-service-envelope-v1',state=r.STATE_NAMES,candidates=r.CANDIDATE_NAMES,slots=8,
    parent=r.SCHEMA,slot0='JointList service optimum',delta_reference='JointList',suffix='shared whole-current-queue compatible EDD partition dispatcher',
    admission='physical plus known current service envelope; no individual urgent response preservation'))
_old_jobs=r.c.Controller._l0_jobs

def joint_jobs(owner,queue,lanes,now):
    """Small compatible EDD list maps, estimated current queue only.

    C-prefix CPU/GPU partitions are finite routing plans. These are model
    estimates from public phases; no actual remaining time or future arrival.
    """
    if not queue:return []
    legal=[dict(request_id=q['id'],backend=b) for q in queue for b in r.p.backends(q) if r.c.legal(dict(request_id=q['id'],backend=b),queue,lanes)]
    if not legal:return []
    cs=sorted([q for q in queue if q['task']=='classification'],key=r.c.due)
    ds=sorted([q for q in queue if q['task']=='detection'],key=r.c.due)
    scores=[]
    # At most four EDD routing maps; not an exhaustive/global optimum.
    for count in sorted({0,1,len(cs)-1,len(cs)} & set(range(len(cs)+1))):
        waiting={'CPU':sorted(cs[:count]+ds,key=r.c.due),'GPU':cs[count:]}
        running={};responses={};known={q['id']:q for q in queue};ends=[];first=[];t=float(now)
        invalid=False
        for b,lane in lanes.items():
            q=lane['request']
            if q is None:continue
            known[q['id']]=q;dur=owner.estimates[r.p.key(q,b)];end=lane['dispatch']+sum(dur)
            phase=r.old.PHASES.index(lane['phase']);next_at=lane['dispatch']+sum(dur[:phase+1])
            if next_at<=now+.0001:invalid=True;break
            running[b]=(q,end);ends.append(end)
            if phase<(2 if q['priority']=='urgent' else 3):responses[q['id']]=lane['dispatch']+sum(dur[:2 if q['priority']=='urgent' else 3])
        if invalid:continue
        for _ in range(4*len(queue)+10):
            running={b:x for b,x in running.items() if x[1]>t+.0001}
            chosen=False
            for b in ('CPU','GPU'):
                if b in running or not waiting[b]:continue
                q=waiting[b][0]
                try:r.p.state([v[0]['task']+'_'+bb for bb,v in running.items()]+[q['task']+'_'+b])
                except ValueError:continue
                waiting[b].pop(0);dur=owner.estimates[r.p.key(q,b)];end=t+sum(dur);running[b]=(q,end);ends.append(end)
                responses[q['id']]=t+sum(dur[:2 if q['priority']=='urgent' else 3])
                if t==now:first.append(dict(request_id=q['id'],backend=b))
                chosen=True
            if not any(waiting.values()):break
            if chosen:continue
            if not running:invalid=True;break
            t=min(v[1] for v in running.values())
        else:invalid=True
        if invalid or any(q['id'] not in responses for q in queue):continue
        late={k:max(0.,value-r.c.due(known[k]))/1e9 for k,value in responses.items()}
        key=(sum(v>1e-9 for k,v in late.items() if known[k]['priority']=='urgent'),sum(v>1e-9 for k,v in late.items() if known[k]['priority']=='normal'),
            sum(v for k,v in late.items() if known[k]['priority']=='urgent'),sum(v for k,v in late.items() if known[k]['priority']=='normal'),max(ends,default=now)/1e9,count)
        scores.append((key,first))
    if scores:
        first=min(scores,key=lambda q:q[0])[1]
        if first:return first
    return _old_jobs(owner,queue,lanes)

class JointActual(r.h.prior.external.BandController):
    def decide(self,config,queue,lanes,now,settings,thermal_model,current_ap):
        self.validate_public(queue,lanes,now);jobs=joint_jobs(self,queue,lanes,now)
        return dict(now_ns=now,selected=jobs[0] if jobs else None,reason=JOINT)

class JointLight(r.old.fast.LightBand):
    def decide(self,config,queue,lanes,now,settings,thermal_model,current_ap):
        jobs=joint_jobs(self,queue,lanes,now)
        return dict(now_ns=now,selected=jobs[0] if jobs else None,reason=JOINT)

@contextmanager
def joint_suffix_scope():
    a,b=r.old.LightBand,r.old.fast.LightBand;r.old.LightBand=JointLight;r.old.fast.LightBand=JointLight
    try:yield
    finally:r.old.LightBand=a;r.old.fast.LightBand=b

@contextmanager
def parent_scope():
    original=r.service_suffix_scope;r.service_suffix_scope=joint_suffix_scope
    try:yield
    finally:r.service_suffix_scope=original

def service(f,queue,lanes):
    known={q['id']:q for q in queue};known.update({l['request']['id']:l['request'] for l in lanes.values() if l['request']})
    late={k:max(0.,v-r.c.due(known[k])/1e9) for k,v in f['responses'].items()}
    return (f['urgent_misses'],f['normal_misses'],sum(v for k,v in late.items() if known[k]['priority']=='urgent'),sum(v for k,v in late.items() if known[k]['priority']=='normal'))

class Controller(r.Controller):
    def __init__(self,frozen,initial,mode=JOINT,network=None,deterministic=True,ablation=None):
        if mode not in (JOINT,COST,r.PPO):raise ValueError('new service-envelope mode')
        super().__init__(frozen,initial,r.PPO if mode==r.PPO else r.RULE,network,deterministic,ablation)
        self.band=JointActual(frozen,initial);self.variant=mode;self.public_policy=mode;self.schema_id=SCHEMA
    def bank(self,queue,lanes,now):
        previous=r.c.Controller._l0_jobs
        r.c.Controller._l0_jobs=lambda owner,q,l:joint_jobs(owner,q,l,now)
        try:
            with parent_scope():return super().bank(queue,lanes,now)
        finally:r.c.Controller._l0_jobs=previous
    def predict(self,*args,**kwargs):
        with parent_scope():return super().predict(*args,**kwargs)
    def admission(self,action,forecasts,refs,queue,now,risk):
        if not all(f['valid'] and all(q['id'] in f['responses'] for q in queue) for f in forecasts):return False,'unknown_forecast'
        if action['kind']=='cool_wait':
            delay=(action['until_ns']-now)/1e9
            if not risk['known']:return False,'unknown_observed_CPU_load_no_cooling'
            if sum(q['task']=='detection' for q in queue)>=2:return False,'D_backlog'
            if risk['rho']>=1:return False,'observed_CPU_D_pressure'
            if any(self.request_wait.get(q['id'],0)+delay>.25+1e-9 for q in queue):return False,'request_wait_cap'
        if any(f['lane_end_s']>120.+1e-9 for f in forecasts):return False,'observation_window_drain'
        return True,'known_current_queue_service_prediction_not_guarantee'
    def encode(self,queue,lanes,now,actions,window):
        e=super().encode(queue,lanes,now,actions,window)
        valid=[i for i in np.flatnonzero(e['mask']) if all(f['valid'] for f in e['forecasts'][i])]
        def key(i):
            fs=e['forecasts'][i];ss=[service(f,queue,lanes) for f in fs]
            return tuple(max(q[j] for q in ss) for j in range(4))+(max(f['lane_end_s'] for f in fs),max(f['global_peak_ap_c'] for f in fs),max(f['remaining_increment_j'] for f in fs),i!=0,i)
        ref=min(valid,key=key) if valid else 0;order=[ref]+[i for i in range(len(actions)) if i!=ref]
        for name in ('actions','forecasts','admissions'):e[name]=[e[name][i] for i in order]
        for name in ('candidates','mask','physical_mask'):
            value=e[name].copy();e[name][:len(order)]=value[order]
        e['candidates'][:,r.CANDIDATE_NAMES.index('is_L0')]=0.;e['candidates'][0,r.CANDIDATE_NAMES.index('is_L0')]=1.
        refs=e['forecasts'][0]
        for i,fs in enumerate(e['forecasts']):
            if not all(f['valid'] and ref['valid'] for f,ref in zip(fs,refs)):continue
            for name,field,scale in (('worst_delta_J','remaining_increment_j',1),('worst_delta_global_AP','global_peak_ap_c',1),('worst_delta_future_AP','peak_ap_c',1),('worst_delta_urgent_P95_over1500','urgent_p95_ms',1500),('worst_delta_urgent_misses','urgent_misses',1),('worst_delta_normal_misses','normal_misses',1)):
                e['candidates'][i,r.CANDIDATE_NAMES.index(name)]=max(((f[field] or 0)-(ref[field] or 0))/scale for f,ref in zip(fs,refs))
            for priority,name,scale in (('normal','worst_normal_response_delta_over6',6),('urgent','worst_urgent_response_delta_over1p5',1.5)):
                e['candidates'][i,r.CANDIDATE_NAMES.index(name)]=max([0]+[(f['responses'][q['id']]-ref['responses'][q['id']])/scale for f,ref in zip(fs,refs) for q in queue if q['priority']==priority])
            if i and e['mask'][i]:
                allowed=all(service(f,queue,lanes)==service(ref,queue,lanes) and (f['urgent_p95_ms'] or 0)<=(ref['urgent_p95_ms'] or 0)+1e-9 and all(f['responses'][q['id']]<=ref['responses'][q['id']]+1e-9 for q in queue if len(r.p.backends(q))==1) for f,ref in zip(fs,refs))
                e['mask'][i]=allowed;e['admissions'][i]='Joint_service_envelope' if allowed else 'Joint_service_envelope_rejected'
        e['admissions'][0]='JointList_reference'
        e.update(schema_id=SCHEMA,base=0,Joint_service_reference=True,prediction_guard_is_service_guarantee=False)
        return e
    def choose_prefix(self,queue,lanes,now,base):
        actions,window=self.bank(queue,lanes,now)
        if not actions:return None
        e=self.encode(queue,lanes,now,actions,window);permitted=list(np.flatnonzero(e['mask']));chosen=0
        if self.variant==COST:
            refs=e['forecasts'][0]
            safe=[i for i in permitted if all(f['valid'] and ref['valid'] and f['global_peak_ap_c']<=ref['global_peak_ap_c']+1e-9 and f['remaining_increment_j']<=ref['remaining_increment_j']+1e-9 for f,ref in zip(e['forecasts'][i],refs))]
            if safe:chosen=min(safe,key=lambda i:(max(f['global_peak_ap_c'] for f in e['forecasts'][i]),max(f['remaining_increment_j'] for f in e['forecasts'][i]),i))
        elif self.variant==r.PPO:
            with torch.no_grad():dist,value=self.network(torch.from_numpy(e['state'])[None],torch.from_numpy(e['candidates'])[None],torch.from_numpy(e['mask'])[None])
            scores=dist.logits[0].numpy();chosen=(0 if scores[0]==scores.max() else int(scores.argmax())) if self.deterministic else int(dist.sample().item())
            e.update(old_value=value[0].numpy().copy(),logprob=float(dist.log_prob(torch.tensor([chosen])).item()))
        e.update(chosen=chosen,actor_eligible=self.variant==r.PPO and not self.deterministic and len(permitted)>1,informative=len(permitted)>1)
        self.snapshots.append(e);return copy.deepcopy(e['actions'][chosen])
