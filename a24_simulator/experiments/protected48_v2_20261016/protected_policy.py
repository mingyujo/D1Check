"""Rolling + ATC candidates/prior + PPO, with public nominal deadline protection.

No latent/sample durations or future arrivals are accessed. Bounds are policy
safety margins on existing nominal estimates, not changes to device physics.
"""
from pathlib import Path
import copy, math, sys
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
import lab_backend as L
import policy_bridge_four_route as bridge
NS=1_000_000_000
FAMILY='ATC_RESIDUAL_RL'
CONFIG=dict(nominal_bound_factor=1.2, minimum_owner_remaining_s=.02,
            deadline_margin_s=.03, urgent_critical_slack_s=.4,
            normal_critical_slack_s=.15, ATC_prior_weight=.25,
            marginal_cost_prior_strength=2., energy_heat_mix=.5,
            goal_service_alpha=1., voluntary_WAIT_limit_s=12.)

def label(task,route): return ('classification' if task=='C' else 'detection')+'_'+route
def state_label(items): return '+'.join(sorted(label(t,r) for t,r in items))

def owner_remaining(obs, route):
    o=obs['owners'].get(route)
    if o is None:return 0.
    e=obs['estimates'][o['request_id']][route]
    elapsed=(obs['now_ns']-o['dispatch_ns'])/NS
    return max(CONFIG['minimum_owner_remaining_s'],CONFIG['nominal_bound_factor']*e['occupancy_ns']/NS-elapsed)

def marginal_terms(obs, q, route, powers, gains):
    duration=obs['estimates'][q['request_id']][route]['occupancy_ns']/NS
    solo=label(q['task'],route)
    others=[(r,o) for r,o in obs['owners'].items() if o is not None]
    if not others:return duration*powers[solo],duration*gains[solo]
    lane,owner=others[0];overlap=min(duration,owner_remaining(obs,lane))
    existing=label(owner['task'],lane);pair=state_label([(q['task'],route),(owner['task'],lane)])
    return (overlap*(powers[pair]-powers[existing])+(duration-overlap)*powers[solo],
            overlap*(gains[pair]-gains[existing])+(duration-overlap)*gains[solo])

def protected_bank(obs, powers, gains):
    bank=bridge.build_bank(obs,FAMILY,allow_wait=True)
    mask=bank['mask'].copy();initial=mask.copy();now=obs['now_ns']/NS
    lookup={q['request_id']:q for q in obs['queue']}
    bound=lambda q,r: CONFIG['nominal_bound_factor']*obs['estimates'][q['request_id']][r]['response_ns']/NS
    free=[r for r in ('CPU','GPU') if obs['owners'].get(r) is None]
    remaining={r:owner_remaining(obs,r) for r in ('CPU','GPU')}
    def earliest(q, release):return min(release[r]+bound(q,r) for r in ('CPU','GPU'))
    slack={rid:q['deadline_ns']/NS-now-earliest(q,remaining) for rid,q in lookup.items()}
    critical=[q for rid,q in lookup.items() if slack[rid] <= CONFIG['urgent_critical_slack_s' if q['priority']=='U' else 'normal_critical_slack_s']]
    focus=min(critical,key=lambda q:(q['deadline_ns'],q['scheduled_arrival_ns'],q['ordinal'],q['request_id'])) if critical else None
    for i in np.flatnonzero(initial):
        a=bank['actions'][i]
        if a['kind']=='RESOURCE_WAIT':continue
        if a['kind']=='WAIT':
            release={r:v+a['wait_ns']/NS for r,v in remaining.items()}
            mask[i]=focus is None and all(now+earliest(q,release)+CONFIG['deadline_margin_s']<=q['deadline_ns']/NS for q in lookup.values())
            continue
        q=lookup[a['request_id']];r=a['route']
        if focus is not None and q['request_id']!=focus['request_id']:
            mask[i]=False;continue
        release=dict(remaining)
        release[r]=CONFIG['nominal_bound_factor']*obs['estimates'][q['request_id']][r]['occupancy_ns']/NS
        if now+bound(q,r)+CONFIG['deadline_margin_s']>q['deadline_ns']/NS:
            if any(now+bound(q,b)+CONFIG['deadline_margin_s']<=q['deadline_ns']/NS for b in free):
                mask[i]=False;continue
        for other in lookup.values():
            if other['request_id']==q['request_id'] or other['priority']!='U':continue
            due=other['deadline_ns']/NS
            # Never worsen a currently feasible queued urgent request to a
            # nominally infeasible state merely to dispatch another request.
            if now+earliest(other,remaining)+CONFIG['deadline_margin_s']<=due and now+earliest(other,release)+CONFIG['deadline_margin_s']>due:
                mask[i]=False;break
    fallback=False
    if not mask.any():
        available=[int(i) for i in np.flatnonzero(initial[:72])]
        if not available:raise ValueError('No legal physical action')
        target=focus or min(lookup.values(),key=lambda q:(slack[q['request_id']],q['deadline_ns'],q['ordinal']))
        options=[i for i in available if bank['actions'][i]['request_id']==target['request_id']]
        if not options:raise ValueError('Critical request omitted from ATC candidate set')
        best=min(bound(target,bank['actions'][i]['route']) for i in options)
        mask[:]=False
        for i in options:
            if abs(bound(target,bank['actions'][i]['route'])-best)<1e-12:mask[i]=True
        fallback=True
    candidates=[]
    for i in np.flatnonzero(mask[:72]):
        a=bank['actions'][i];q=lookup[a['request_id']]
        e,h=marginal_terms(obs,q,a['route'],powers,gains)
        candidates.append((int(i),e,h))
        bank['features'][i,7]=np.clip(e,-10,10)
        duration=obs['estimates'][q['request_id']][a['route']]['occupancy_ns']/NS
        bank['features'][i,8]=np.clip(e/max(duration,1e-9)/10,-10,10)
    if candidates:
        escale=max(.01,float(np.median([abs(e) for _,e,_ in candidates])))
        hscale=max(1e-6,float(np.median([abs(h) for _,_,h in candidates])))
        costs={i:.5*e/escale+.5*h/hscale for i,e,h in candidates}
        best=min(costs.values())
        for i in np.flatnonzero(mask):
            if i in costs:
                bank['prior_logits'][i]=np.clip(CONFIG['ATC_prior_weight']*bank['prior_logits'][i]-CONFIG['marginal_cost_prior_strength']*(costs[i]-best),-10,0)
            elif bank['actions'][i]['kind']=='WAIT':bank['prior_logits'][i]=-2.
    bank['mask']=mask
    bank['diagnostic']['protection']={'critical_request':focus['request_id'] if focus else None,
        'removed_actions':int(initial.sum()-mask.sum()),'initial_legal':int(initial.sum()),
        'final_legal':int(mask.sum()),'nominal_recovery_fallback':fallback,
        'prediction_based_not_real_deadline_guarantee':True,
        'uses_latent_duration_or_future_arrival':False}
    return bank

class ProtectedPolicy:
    def __init__(self,model,public,thermal,profile,learner,learn,collect=False,zero_residual=False):
        self.model,self.public,self.thermal,self.profile=model,public,thermal,profile
        self.learner,self.learn=learner,learn
        self.controller=learner.controller(1.,.5,collect)
        self.network_sha=learn.network_digest(learner.net)
        self.np,self.torch=np,learn.torch
        self.collect,self.zero_residual=collect,zero_residual
        self.previous_ap=None;self.waited=set();self.bank_audits=[]
    def __call__(self,state):
        t=state['now_ns'];ts=t/NS
        intervals=state['past_activity']
        if any(x['end_s']>ts for x in intervals):raise ValueError('Future activity leaked')
        activity=copy.deepcopy(self.public)
        activity.update(owner_intervals=intervals,activity_coverage_s=[0.,ts],observation_window_s=[0.,ts])
        ap=L.thermal_model.predict(self.thermal,activity,times=[ts],include_features=True,allow_extrapolation=True)
        if ap['status']!='CONDITIONAL_AP_PREDICTION':raise ValueError('Current AP unavailable')
        powers=self.profile['cost_anchor']['energy_increment_w']
        gains=dict(zip(L.thermal_model.STATES,ap['local_coefficients'][3:]))
        owners={o['route']:dict(o,phase_index=state['owner_phases'][o['route']],priority=self.model.contexts[o['request_id']]['_requests_by_id'][o['request_id']]['priority']) for o in state['owners']}
        estimates={}
        for q in [*state['queue'],*state['owners']]:
            src=self.model.contexts[q['request_id']]
            ctx,_=L.context_of(src,src['_requests_by_id'][q['request_id']],True)
            estimates[q['request_id']]={}
            for r in ('CPU','GPU'):
                e=self.model.nominal(L.context_for_route(ctx,q['task'],r),q['task'],r,state=state)
                estimates[q['request_id']][r]={**e,'energy_proxy_j':max(0,e['occupancy_ns']/NS*powers[label(q['task'],r)])}
        power=self.profile['measured35']['baseline_w']
        if owners:power+=powers[state_label([(o['task'],r) for r,o in owners.items()])]
        recent={r:sum(max(0.,min(ts,x['end_s'])-max(max(0.,ts-5.),x['start_s'])) for x in intervals if x['route']==r)/min(5.,max(ts,1e-9)) for r in ('CPU','GPU','NPU')}
        slope=0 if self.previous_ap is None or ts<=self.previous_ap[0] else (ap['ap_c'][0]-self.previous_ap[1])/(ts-self.previous_ap[0])
        obs=dict(now_ns=t,queue=state['queue'],owners=owners,estimates=estimates,
            last_release_ns=state['last_release_ns'],history=state['history_by_priority'],
            wait_used_ns=state['wait_used_ns'],waited_request_ids=sorted(self.waited),
            horizon_ns=self.public['service_stop_ns'],alpha=1.,heat_weight=.5,
            sensor=dict(AP_c=ap['ap_c'][0],power_w=power,age_s=0.,recent_activity=recent,ap_slope_c_s=slope,power_slope_w_s=0.))
        bank=protected_bank(obs,powers,gains)
        if self.zero_residual:
            indices=np.flatnonzero(bank['mask']);idx=int(max(indices,key=lambda i:bank['prior_logits'][i]))
        else:idx=self.controller.choose(bank,t,self.collect)
        action=copy.deepcopy(bank['actions'][idx])
        self.bank_audits.append(dict(time_ns=t,chosen_index=idx,mask=bank['mask'].tolist(),
            protection=bank['diagnostic']['protection'],action=action,
            public_state=copy.deepcopy(state),
            input_digest=self.learn.input_digest(self.learn.checked_bank(bank,FAMILY))))
        if action['kind']=='WAIT':self.waited.add(bank['diagnostic']['head_request_id'])
        self.previous_ap=(ts,ap['ap_c'][0])
        return action
