"""Pure execution-prefix ranking prototype, not connected to an online policy.

Forecasts must describe this action followed by Band, from one public state.
Legacy forecasts that force a future request after an interruptible wait are
explicitly inadmissible. No plant simulation, learner, or device imports.
"""
import json,math

VERSION='ROLLING_EXECUTED_PREFIX_GLOBAL_KPI_DRAFT_V1'
CONTEXTS=('mean','short_context','long_context')
EPS=1e-9  # Existing projection arithmetic tolerance; final KPI margin stays0.
DISPATCH='immediate_prefix_then_band_v1'
WAIT='wait_to_first_public_event_then_band_v1'

def number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

def signature(action):
    kind=action['kind']
    if kind in ('single','bundle'):
        jobs=action['jobs']
        if len(jobs)!=(1 if kind=='single' else 2):raise ValueError('bad prefix cardinality')
        if len({j['request_id'] for j in jobs})!=len(jobs):raise ValueError('duplicate prefix request')
        if any(j['backend'] not in ('CPU','GPU') for j in jobs):raise ValueError('unsupported lane')
        if kind=='bundle' and len({j['backend'] for j in jobs})!=2:raise ValueError('bundle needs two distinct lanes')
        payload=dict(kind=kind,jobs=[dict(request_id=j['request_id'],backend=j['backend']) for j in jobs])
    elif kind in ('cool_wait','resource_wait'):
        if action.get('jobs'):raise ValueError('interruptible wait cannot commit future jobs')
        until=action.get('until_ns')
        if until is not None and not number(until):raise ValueError('unknown wait timer')
        if kind=='cool_wait' and until is None:raise ValueError('cooling requires a timer')
        if kind=='resource_wait' and until is not None:raise ValueError('resource wait wakes on a public event')
        payload=dict(kind=kind,until_ns=until,hold_signature=action['hold_signature'],
            interrupt_on=['arrival','any_lane_available'])
    elif kind=='band':payload=dict(kind=kind)
    else:raise ValueError('unknown action')
    return json.dumps(payload,sort_keys=True,separators=(',',':'))

def immediate_action(plan,queue,lanes,now_ns):
    """Only executable single/same-time bundle; waits need a separate projector."""
    if set(lanes)!= {'CPU','GPU'}:raise ValueError('unexpected lane set')
    if any(q['arrival_ns']>now_ns for q in queue):raise ValueError('future request')
    by={q['id']:q for q in queue}
    if len(by)!=len(queue):raise ValueError('duplicate public queue')
    if not plan:return None
    if len({j['request_id'] for j in plan})!=len(plan):raise ValueError('duplicate plan request')
    owned=[(l['request']['task'],b) for b,l in lanes.items() if l['request']]
    def legal(step,members):
        q=by.get(step['request_id']);b=step['backend']
        if q is None or b not in lanes:raise ValueError('missing/unsupported public request')
        if q['task'] not in ('classification','detection'):raise ValueError('unsupported task')
        if q['task']=='detection' and b!='CPU':raise ValueError('detection requires CPU')
        if step.get('delay_ns',0)!=0 or lanes[b]['request'] is not None:return False
        added=(q['task'],b)
        return not members or len(members)==1 and {members[0],added}=={('classification','GPU'),('detection','CPU')}
    if not legal(plan[0],owned):return None
    first=dict(request_id=plan[0]['request_id'],backend=plan[0]['backend']);jobs=[first]
    if len(plan)>1 and plan[1]['request_id']!=first['request_id'] and plan[1]['backend']!=first['backend']:
        members=owned+[(by[first['request_id']]['task'],first['backend'])]
        if legal(plan[1],members):jobs.append(dict(request_id=plan[1]['request_id'],backend=plan[1]['backend']))
    return dict(kind='bundle' if len(jobs)==2 else 'single',jobs=jobs)

def valid_forecast(f,past_peak_c,state_key):
    if not isinstance(f,dict):return False
    keys=('global_peak_ap_c','peak_ap_c','remaining_increment_j','urgent_misses','normal_misses','lane_end_s')
    return (f.get('valid') is True and f.get('state_key')==state_key and all(number(f.get(k)) for k in keys)
        and f['lane_end_s']<=120.+EPS and f['global_peak_ap_c']+EPS>=f['peak_ap_c']
        and abs(f['global_peak_ap_c']-max(past_peak_c,f['peak_ap_c']))<=EPS
        and min(f['urgent_misses'],f['normal_misses'])>=0
        and (f.get('urgent_p95_ms') is None or number(f['urgent_p95_ms'])))

def nonworse(f,r,past_peak_c,state_key):
    if not valid_forecast(f,past_peak_c,state_key) or not valid_forecast(r,past_peak_c,state_key):return False
    p,q=f.get('urgent_p95_ms'),r.get('urgent_p95_ms')
    if (p is None)!=(q is None):return False
    keys=('global_peak_ap_c','remaining_increment_j','urgent_misses','normal_misses')
    return all(f[k]<=r[k]+EPS for k in keys) and (p is None or p<=q+EPS)

def select(candidates,references,band_action,*,past_peak_c,state_key,now_ns):
    """One-state, same-shortlist ranking; no global/future safety guarantee."""
    if (not number(past_peak_c) or not number(now_ns) or not isinstance(state_key,str) or not state_key
        or set(references)!=set(CONTEXTS) or not all(valid_forecast(f,past_peak_c,state_key) for f in references.values())):
        return dict(chosen=None,reason='unknown_reference',admissible=0,future_only=0)
    if band_action['kind']=='band':return dict(chosen=None,reason='unresolved_band_action',admissible=0,future_only=0)
    band_key=signature(band_action);groups={};rejected=[]
    for index,candidate in enumerate(candidates):
        key=signature(candidate['action']);groups.setdefault(key,[]).append((index,candidate))
    ranked=[];future_only=0
    for key,group in groups.items():
        index,candidate=group[0];action=candidate['action'];fs=candidate.get('forecasts')
        expected=DISPATCH if action['kind'] in ('single','bundle') else WAIT
        if action['kind']=='band' or key==band_key:rejected.append((index,'same_actual_band_action'));continue
        if candidate.get('state_key')!=state_key:rejected.append((index,'different_public_state'));continue
        if action['kind']=='cool_wait' and action['until_ns']<=now_ns:
            rejected.append((index,'expired_wait_timer'));continue
        if candidate.get('semantics')!=expected:rejected.append((index,'unverified_execution_semantics'));continue
        # Same executed action/state must not receive credit from a different suffix.
        if any(c.get('semantics')!=candidate['semantics'] or c.get('forecasts')!=fs or c.get('state_key')!=state_key for _,c in group):
            rejected.append((index,'ambiguous_same_prefix_forecast'));continue
        if not isinstance(fs,dict) or set(fs)!=set(CONTEXTS) or not all(nonworse(fs[c],references[c],past_peak_c,state_key) for c in CONTEXTS):
            rejected.append((index,'service_or_cost_forecast_worse'));continue
        dA=max(fs[c]['global_peak_ap_c']-references[c]['global_peak_ap_c'] for c in CONTEXTS)
        dJ=max(fs[c]['remaining_increment_j']-references[c]['remaining_increment_j'] for c in CONTEXTS)
        dFuture=max(fs[c]['peak_ap_c']-references[c]['peak_ap_c'] for c in CONTEXTS)
        if dA>=-EPS and dJ>=-EPS:
            future_only+=dFuture<-EPS;rejected.append((index,'no_global_AP_or_J_gain'));continue
        ranked.append(((dA,dJ,index),candidate))
    chosen=min(ranked,key=lambda v:v[0]) if ranked else None
    return dict(chosen=chosen[1] if chosen else None,score=list(chosen[0]) if chosen else None,
        reason='strict_prefix_model_gain' if chosen else 'band_fallback',admissible=len(ranked),
        unique_prefixes=len(groups),future_only=future_only,rejected=rejected,performance_claim=False)
