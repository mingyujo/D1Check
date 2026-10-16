"""Same finite rolling list for a non-learning selector and masked native PPO.

New observation schema; original actors are never reused. L0 is service-first
EDD across FIFO task heads / earliest currently legal completion. No Band
fallback or learning reference. Only public arrivals/phases and derived model
estimates enter the policy. Forecast restrictions do not guarantee future SLA.
"""
import copy,math,time
from contextlib import contextmanager
import numpy as np
import torch
from tools import d1_rolling_hybrid_model as h
from tools import d1_list_candidate_rl as c
from tools import d1_list_candidate_rl_training as training

p=h.p;old=h.prior.new.old;project=h.prior.new.project;selector=h.prior.new.selector
VERSION='rolling-list-v3-hybrid-public-risk-01'
L0='ROLLING_LIST_L0_SERVICE_FIRST_EMA_V1'
RULE='ROLLING_LIST_PUBLIC_RISK_RULE_V1'
PPO='ROLLING_LIST_MASKED_PPO_V1'
STATE_NAMES=('time_over120','queue_C_over96','queue_D_over96','CPU_owned','GPU_owned','credit_over025',
 'modeled_AP_over40','past_peak_AP_over40','derived_H','derived_slow_AP','CPU_D_load_over6',
 'observed_D_utilization','D_utilization_known','recent_interarrival_over6','recent_interarrival_known',
 'total_extra_cooling_over6','cooling_count_over96','max_request_extra_wait_over025',
 'C_min_deadline_remaining_over1p5','D_min_deadline_remaining_over6','C_next_deadline_remaining_over1p5',
 'D_next_deadline_remaining_over6','C_oldest_age_over1p5','D_oldest_age_over6',
 'observed_urgent_P95_over1500','observed_urgent_count_over96','observed_normal_count_over96',
 'CPU_phase_over5','GPU_phase_over5','CPU_elapsed_since_dispatch_over6','GPU_elapsed_since_dispatch_over6',
 'C_mean_service_CPU','C_mean_service_GPU','D_mean_service_CPU')+tuple('reserved_zero_'+str(i) for i in range(22))
CANDIDATE_NAMES=('is_L0','single','bundle','cool_wait','resource_wait','classification_CPU','classification_GPU','detection_CPU',
 'prefix_size_over2','delay_over025','prediction_known','worst_delta_J','worst_delta_global_AP','worst_delta_future_AP',
 'worst_delta_urgent_P95_over1500','worst_delta_urgent_misses','worst_delta_normal_misses','worst_lane_end_over120',
 'min_queued_deadline_margin_over6','max_normal_lateness_over6','worst_normal_response_delta_over6',
 'worst_urgent_response_delta_over1p5','request_extra_wait_max_over025','queued_CPU_D_work_over6',
 'observed_D_utilization','D_utilization_known','first_request_deadline_remaining_over6','first_request_age_over6')
assert len(STATE_NAMES)==56 and len(CANDIDATE_NAMES)==28
SCHEMA=c.digest(dict(version=VERSION,state=STATE_NAMES,candidates=CANDIDATE_NAMES,slots=8,
                    hybrid=h.UPSTREAM_SHA,forecast_suffix=L0,wait_policy='request_cap025_Dbacklog_lt2_observed_Drho_lt1'))


class ServiceActual(h.prior.external.BandController):
    def decide(self,config,queue,lanes,now,settings,thermal_model,current_ap):
        self.validate_public(queue,lanes,now)
        jobs=c.Controller._l0_jobs(self,queue,lanes)
        return dict(now_ns=now,selected=jobs[0] if jobs else None,reason=L0)

class ServiceLight(old.fast.LightBand):
    def decide(self,config,queue,lanes,now,settings,thermal_model,current_ap):
        jobs=c.Controller._l0_jobs(self,queue,lanes)
        return dict(now_ns=now,selected=jobs[0] if jobs else None,reason=L0)


@contextmanager
def service_suffix_scope():
    a,b=old.LightBand,old.fast.LightBand;old.LightBand=ServiceLight;old.fast.LightBand=ServiceLight
    try:yield
    finally:old.LightBand=a;old.fast.LightBand=b


def physical(action,queue,lanes,now,credit):
    if action['kind']=='cool_wait':
        return (not any(l['request'] for l in lanes.values()) and not any(q['priority']=='urgent' for q in queue)
            and 0<(action['until_ns']-now)/1e9<=credit+1e-9)
    if action['kind']=='resource_wait':return any(l['request'] for l in lanes.values())
    if action['kind'] not in ('single','bundle'):return False
    jobs=action['jobs']
    if len(jobs)!=(1 if action['kind']=='single' else 2) or len({j['request_id'] for j in jobs})!=len(jobs):return False
    simulated=copy.deepcopy(lanes)
    for j in jobs:
        if not c.legal(j,queue,simulated):return False
        simulated[j['backend']]['request']=next(q for q in queue if q['id']==j['request_id'])
    return True


class Controller(h.ExecutionController):
    def __init__(self,frozen,initial,mode=RULE,network=None,deterministic=True,ablation=None):
        super().__init__(frozen,initial);self.band=ServiceActual(frozen,initial)
        self.mode=mode;self.public_policy=mode;self.network=network;self.deterministic=deterministic;self.ablation=ablation
        self.schema_id=SCHEMA;self.snapshots=[];self.arrivals={};self.request_wait={};self.wait_charge=None
        self.total_extra_wait=0.;self.cooling_count=0;self.admission_rejections={}
    def observe(self,now,lanes):
        if self.wait_charge:
            charge=self.wait_charge;end=min(now,charge['end']);delta=max(0.,end-charge['last'])/1e9
            for rid in charge['ids']:self.request_wait[rid]=self.request_wait.get(rid,0.)+delta
            self.total_extra_wait+=delta;charge['last']=end
            if now>=charge['end']:self.wait_charge=None
        for lane in lanes.values():
            if lane['request']:self.arrivals.setdefault(lane['request']['id'],copy.deepcopy(lane['request']))
        super().observe(now,lanes)
    def apply_prefix(self,action,queue,lanes,now,base):
        out=super().apply_prefix(action,queue,lanes,now,base)
        if out.get('action_kind')=='cool_wait':
            self.cooling_count+=1;self.wait_charge=dict(ids=[q['id'] for q in queue],last=now,end=action['until_ns'])
        return out
    def decide(self,config,queue,lanes,now,settings,thermal_model,current_ap):
        for q in queue:self.arrivals.setdefault(q['id'],copy.deepcopy(q))
        self.validate_public(queue,lanes,now)
        if self.wait_charge and self.hold and self.hold['signature']!=self.signature(queue,lanes):self.wait_charge=None
        # Inherited pending commit and phase/arrival/AVAILABLE/timer semantics.
        return super().decide(config,queue,lanes,now,settings,thermal_model,current_ap)
    def risk(self,queue,now):
        recent=sorted(self.arrivals.values(),key=lambda q:(q['arrival_ns'],q['ordinal'],q['id']))[-8:]
        times=sorted({q['arrival_ns']/1e9 for q in recent});span=times[-1]-times[0] if len(times)>1 else 0.
        known=len(times)>=3 and span>0
        # Last8 observed arrivals, not a sampled next request or future reservation.
        cpu_work=sum(sum(self.estimates[p.key(q,'CPU')])/1e9 for q in recent if q['task']=='detection')
        rho=cpu_work/span if known else 0.
        queued=sum(sum(self.estimates[p.key(q,'CPU')])/1e9 for q in queue if q['task']=='detection')
        return dict(rho=rho,known=known,gap=(times[-1]-times[-2]) if len(times)>1 else 0.,gap_known=len(times)>1,queued=queued)
    def predict(self,queue,lanes,now,action,context):
        if self.execution_deadline is not None and time.monotonic()>=self.execution_deadline:raise TimeoutError('original saving reserve')
        self.projection_calls+=1;began=time.perf_counter()
        try:
            with service_suffix_scope():out=project.project(self,queue,lanes,now,action,context)
            costs=h.costs(self,out['jobs'],now);known={q['id']:q for q in queue}
            pending=[j for j in out['jobs'] if not j['already_responded']]
            owned={l['request']['id']:l['request'] for l in lanes.values() if l['request']};known.update(owned)
            responses={j['id']:j['response'] for j in pending}
            urgent=sorted([v['response_ms'] for v in self.observed_responses.values() if v['priority']=='urgent']+
                [(j['response']-known[j['id']]['arrival_ns']/1e9)*1000 for j in pending if known[j['id']]['priority']=='urgent'])
            return dict(valid=True,**costs,responses=responses,lane_end_s=out['lane_end_s'],
                urgent_p95_ms=c.rank95(urgent),urgent_misses=sum(j['response']>j['deadline']+1e-9 for j in pending if known[j['id']]['priority']=='urgent'),
                normal_misses=sum(j['response']>j['deadline']+1e-9 for j in pending if known[j['id']]['priority']=='normal'))
        except old.ProjectionUnavailable as error:return dict(valid=False,reason=str(error))
        finally:self.projection_seconds+=time.perf_counter()-began
    def bank(self,queue,lanes,now):
        jobs=c.Controller._l0_jobs(self,queue,lanes)
        if not jobs:return [],[]
        base=dict(kind='bundle' if len(jobs)==2 else 'single',jobs=jobs)
        actions=[base];unique={selector.signature(base)};window=old.window_requests(self,queue,lanes,now)
        plans=old.candidate_plans(window,self.credit,True);screened=[]
        with service_suffix_scope():
            for index,plan in enumerate(plans):
                f=old.forecast_plan(self,window,lanes,now,plan,'mean')
                if f['valid']:screened.append(((f['urgent_misses'],f['normal_misses'],f['remaining_increment_j'],f['peak_ap_c'],f['urgent_p95_ms'] or 0.,index),index,plan))
        first_count={};short=[]
        for _,index,plan in sorted(screened,key=lambda v:v[0]):
            first=tuple(plan[0][k] for k in ('request_id','backend','delay_ns'))
            if first_count.get(first,0)>=2:continue
            first_count[first]=first_count.get(first,0)+1;short.append(plan)
            if len(short)==8:break
        for plan in short:
            action=project.actual_action(self,plan,queue,lanes,now)
            if action is None or selector.signature(action) in unique:continue
            unique.add(selector.signature(action));actions.append(action)
            if len(actions)==8:break
        return actions,window
    def admission(self,action,forecasts,refs,queue,now,risk):
        if not all(f['valid'] and r['valid'] for f,r in zip(forecasts,refs)):return False,'unknown_forecast'
        if action['kind']=='cool_wait':
            delay=(action['until_ns']-now)/1e9
            if sum(q['task']=='detection' for q in queue)>=2:return False,'D_backlog'
            if risk['known'] and risk['rho']>=1.:return False,'observed_CPU_D_pressure'
            if any(self.request_wait.get(q['id'],0.)+delay>.25+1e-9 for q in queue):return False,'request_wait_cap'
        for f,r in zip(forecasts,refs):
            if f['lane_end_s']>120.+1e-9 or f['remaining_increment_j']>r['remaining_increment_j']+1e-9:return False,'drain_or_J'
            for q in queue:
                new,ref=f['responses'][q['id']],r['responses'][q['id']];due=c.due(q)/1e9
                if q['priority']=='urgent' and new>ref+1e-9:return False,'urgent_response'
                if q['priority']=='normal' and max(0,new-due)>max(0,ref-due)+1e-9:return False,'normal_lateness'
        return True,'permitted_prediction_not_guarantee'
    def encode(self,queue,lanes,now,actions,window):
        risk=self.risk(queue,now);state=np.zeros(56,dtype=np.float32);s={name:0. for name in STATE_NAMES}
        urgent=[v['response_ms'] for v in self.observed_responses.values() if v['priority']=='urgent']
        s.update(time_over120=now/120e9,queue_C_over96=sum(q['task']=='classification' for q in queue)/96,queue_D_over96=sum(q['task']=='detection' for q in queue)/96,
            CPU_owned=float(lanes['CPU']['request'] is not None),GPU_owned=float(lanes['GPU']['request'] is not None),credit_over025=self.credit/.25,
            modeled_AP_over40=self.t/40,past_peak_AP_over40=max(self.grid.values(),default=self.t)/40,derived_H=self.h,derived_slow_AP=self.hybrid_state['slow'],
            CPU_D_load_over6=risk['queued']/6,observed_D_utilization=risk['rho'],D_utilization_known=float(risk['known']),recent_interarrival_over6=risk['gap']/6,recent_interarrival_known=float(risk['gap_known']),
            total_extra_cooling_over6=self.total_extra_wait/6,cooling_count_over96=self.cooling_count/96,max_request_extra_wait_over025=max(self.request_wait.values(),default=0)/.25,
            observed_urgent_P95_over1500=(c.rank95(urgent) or 0)/1500,observed_urgent_count_over96=len(urgent)/96,observed_normal_count_over96=sum(v['priority']=='normal' for v in self.observed_responses.values())/96)
        for task,prefix,scale in (('classification','C',1.5),('detection','D',6.)):
            qs=sorted([q for q in queue if q['task']==task],key=old.core.due)
            for j,name in ((0,'min'),(1,'next')):
                if len(qs)>j:s[f'{prefix}_{name}_deadline_remaining_over'+('1p5' if prefix=='C' else '6')]=(c.due(qs[j])-now)/1e9/scale
            if qs:s[f'{prefix}_oldest_age_over'+('1p5' if prefix=='C' else '6')]=max((now-q['arrival_ns'])/1e9 for q in qs)/scale
        for b,l in lanes.items():
            if l['request']:s[b+'_phase_over5']=(old.PHASES.index(l['phase'])+1)/5;s[b+'_elapsed_since_dispatch_over6']=(now-l['dispatch'])/6e9
        for name,task,b in (('C_mean_service_CPU','classification','CPU'),('C_mean_service_GPU','classification','GPU'),('D_mean_service_CPU','detection','CPU')):
            q=dict(task=task,priority='urgent' if task=='classification' else 'normal');s[name]=sum(self.estimates[p.key(q,b)])/1e9
        state[:]=[s[n] for n in STATE_NAMES]
        forecasts=[[self.predict(queue,lanes,now,a,context) for context in selector.CONTEXTS] for a in actions];refs=forecasts[0]
        vectors=np.zeros((8,28),dtype=np.float32);physical_mask=np.zeros(8,dtype=bool);mask=np.zeros(8,dtype=bool);admissions=[]
        for index,a in enumerate(actions):
            physical_mask[index]=physical(a,queue,lanes,now,self.credit)
            allowed,reason=(True,'L0') if index==0 else self.admission(a,forecasts[index],refs,queue,now,risk)
            if self.ablation=='no_wait' and a['kind'] in ('cool_wait','resource_wait'):allowed=False;reason='ablation_no_wait'
            mask[index]=physical_mask[index] and allowed;admissions.append(reason)
            if not mask[index]:self.admission_rejections[reason]=self.admission_rejections.get(reason,0)+1
            values={n:0. for n in CANDIDATE_NAMES};values.update(is_L0=float(index==0),single=float(a['kind']=='single'),bundle=float(a['kind']=='bundle'),cool_wait=float(a['kind']=='cool_wait'),resource_wait=float(a['kind']=='resource_wait'),prefix_size_over2=len(a.get('jobs',[]))/2,
                delay_over025=(a.get('until_ns',now)-now)/.25e9 if a['kind']=='cool_wait' else 0.,request_extra_wait_max_over025=max((self.request_wait.get(q['id'],0) for q in queue),default=0)/.25,
                queued_CPU_D_work_over6=risk['queued']/6,observed_D_utilization=risk['rho'],D_utilization_known=float(risk['known']))
            for j in a.get('jobs',[]):values[next(q['task'] for q in queue if q['id']==j['request_id'])+'_'+j['backend']]=1.
            known=all(f['valid'] and r['valid'] for f,r in zip(forecasts[index],refs));values['prediction_known']=float(known)
            if known:
                for name,field,scale in (('worst_delta_J','remaining_increment_j',1),('worst_delta_global_AP','global_peak_ap_c',1),('worst_delta_future_AP','peak_ap_c',1),('worst_delta_urgent_P95_over1500','urgent_p95_ms',1500),('worst_delta_urgent_misses','urgent_misses',1),('worst_delta_normal_misses','normal_misses',1)):
                    values[name]=max(((f[field] or 0)-(r[field] or 0))/scale for f,r in zip(forecasts[index],refs))
                values['worst_lane_end_over120']=max(f['lane_end_s'] for f in forecasts[index])/120
                values['min_queued_deadline_margin_over6']=min((c.due(q)/1e9-f['responses'][q['id']])/6 for f in forecasts[index] for q in queue)
                values['max_normal_lateness_over6']=max([0]+[max(0,f['responses'][q['id']]-c.due(q)/1e9)/6 for f in forecasts[index] for q in queue if q['priority']=='normal'])
                for priority,name,scale in (('normal','worst_normal_response_delta_over6',6),('urgent','worst_urgent_response_delta_over1p5',1.5)):
                    values[name]=max([0]+[(f['responses'][q['id']]-r['responses'][q['id']])/scale for f,r in zip(forecasts[index],refs) for q in queue if q['priority']==priority])
            if a.get('jobs'):
                q=next(q for q in queue if q['id']==a['jobs'][0]['request_id']);values['first_request_deadline_remaining_over6']=(c.due(q)-now)/6e9;values['first_request_age_over6']=(now-q['arrival_ns'])/6e9
            vectors[index]=[values[n] for n in CANDIDATE_NAMES]
        if not mask[0] or (mask & ~physical_mask).any():raise ValueError('mask removed physical L0 or allowed unsupported action')
        if self.ablation=='no_thermal_features':
            for name in ('modeled_AP_over40','past_peak_AP_over40','derived_H','derived_slow_AP'):state[STATE_NAMES.index(name)]=0
            for name in ('worst_delta_global_AP','worst_delta_future_AP'):vectors[:,CANDIDATE_NAMES.index(name)]=0
        if not np.isfinite(state).all() or not np.isfinite(vectors).all():raise ValueError('nonfinite encoder')
        return dict(state=state,candidates=vectors,mask=mask,physical_mask=physical_mask,base=0,actions=actions,forecasts=forecasts,admissions=admissions,now_ns=now,
            schema_id=SCHEMA,window_ids=[q['id'] for q in window],risk=risk,prediction_guard_is_service_guarantee=False)
    def choose_prefix(self,queue,lanes,now,base):
        actions,window=self.bank(queue,lanes,now)
        if not actions:return None
        encoded=self.encode(queue,lanes,now,actions,window)
        permitted=list(np.flatnonzero(encoded['mask']));chosen=0
        if self.mode==RULE:
            valid=[i for i in permitted if all(f['valid'] for f in encoded['forecasts'][i])]
            if valid:chosen=min(valid,key=lambda i:(max(f['global_peak_ap_c'] for f in encoded['forecasts'][i]),max(f['remaining_increment_j'] for f in encoded['forecasts'][i]),i!=0,i))
        elif self.mode==PPO:
            with torch.no_grad():dist,value=self.network(torch.from_numpy(encoded['state'])[None],torch.from_numpy(encoded['candidates'])[None],torch.from_numpy(encoded['mask'])[None])
            scores=dist.logits[0].numpy();chosen=(0 if scores[0]==scores.max() else int(scores.argmax())) if self.deterministic else int(dist.sample().item())
            encoded.update(old_value=value[0].numpy().copy(),logprob=float(dist.log_prob(torch.tensor([chosen])).item()))
        elif self.mode!=L0:raise ValueError('policy mode')
        encoded.update(chosen=chosen,actor_eligible=self.mode==PPO and not self.deterministic and len(permitted)>1,informative=len(permitted)>1)
        self.snapshots.append(encoded)
        return copy.deepcopy(actions[chosen])


class Learner(training.Learner):
    def fresh_controller(self,frozen,initial):
        controller=Controller(frozen,initial,PPO,self.network,False)
        if controller.schema_id!=self.schema_id:raise ValueError('new rolling schema mismatch')
        return controller
