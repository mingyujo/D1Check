"""PC exploratory event model v1. No device API; not a measured policy result.

Reuse CAL03 priority-aware estimates and intact five-interval development vectors.
Only the engine receives realized vectors. Policy input is an arrived queue and
observable phases. Parallel service rates and queue transfer are explicit assumptions.
"""
from __future__ import annotations
import copy
import hashlib
import math
import statistics
from tools import d1_cal03_connection as base

VERSION = 'arrival-explore-pc-v3'
FIELDS = ('execution_start_ns', 'output_ready_ns', 'persist_complete_ns',
          'worker_release_ns', 'lane_available_ns')
PHASES = ('ASSIGNED', 'EXECUTING', 'OUTPUT_READY', 'PERSISTED', 'WORKER_RELEASED')
POLICIES = ('CPU_FIFO', 'CPU_URGENT', 'FIXED_SPLIT', 'B2_PC', 'B3_SOLO_EFT_PC',
            'P_PAIR_COST_PC', 'P_NO_PARALLEL_PC')


def keyed_index(seed, request_id, backend):
    return int.from_bytes(hashlib.sha256(f'{seed}/{request_id}/{backend}'.encode()).digest()[:8], 'big') % 4


def choose(config, queue, lanes, now, policy, settings):
    """No engine work-left, realizations, future arrivals or future completion input."""
    allowed = {'id', 'task', 'priority', 'ordinal', 'arrival_ns', 'deadline_offset_ns'}
    for q in queue:
        base.require(set(q) == allowed and q['arrival_ns'] <= now, 'noncausal ticket')
    for lane in lanes.values():
        base.require(set(lane) == {'request', 'phase', 'since', 'dispatch'}, 'noncausal lane')
    aging = settings['aging_ns']
    def order(q):
        if policy == 'CPU_FIFO': return (0, q['ordinal'], q['id'])
        if policy in ('CPU_URGENT','FIXED_SPLIT'):
            return (q['priority']!='urgent',q['ordinal'],q['id'])
        # Common finite aging is an exploratory rule, not the historical Android policy.
        aged = now - q['arrival_ns'] >= aging
        return (0 if aged else 1 if q['priority'] == 'urgent' else 2,
                q['arrival_ns'] if aged else q['arrival_ns'] + q['deadline_offset_ns'], q['ordinal'], q['id'])
    ordered = sorted(queue, key=order)
    residuals = {}
    for b, lane in lanes.items():
        if lane['request'] is None:
            residuals[b] = dict(state='AVAILABLE', ns=0)
        elif lane['phase'] == 'RESERVED':
            residuals[b] = dict(state='UNKNOWN_PRE_DISPATCH', ns=None)
        else:
            q = lane['request']; cell = config['cells'][f"{q['task']}_{b}_{q['priority']}"]
            elapsed = now - lane['dispatch']
            remain = cell['joint']['dispatch_to_lane_ns']['median_ns'] * settings['estimate_factor'] - elapsed
            residuals[b] = dict(state='ESTIMATED_POINT' if remain > 0 else 'UNKNOWN_OVERRUN', ns=max(0, remain) if remain > 0 else None)
    busy = [b for b in lanes if lanes[b]['request'] is not None]
    global_serial = settings['mode'] == 'strict' or policy in ('CPU_FIFO', 'CPU_URGENT', 'P_NO_PARALLEL_PC') or (policy == 'B2_PC' and not settings['static_parallel'])
    result = dict(now_ns=now, queue=copy.deepcopy(ordered), lanes=copy.deepcopy(lanes), residuals=residuals,
                  candidates=[], selected=None, reason='empty' if not queue else 'busy_or_preferred_lane')
    if global_serial and busy: return result
    for q in ordered:
        if policy in ('CPU_FIFO', 'CPU_URGENT'): backends = ['CPU']
        elif policy == 'FIXED_SPLIT': backends = ['CPU' if q['priority'] == 'urgent' else 'GPU']
        elif policy == 'B2_PC': backends = [settings['static_map'][q['task']]]
        elif settings['mode'] == 'strict': backends = ['CPU']  # missing adaptive cost => explicit fallback
        else: backends = ['CPU', 'GPU']
        candidates = []
        for b in backends:
            cell = config['cells'][f"{q['task']}_{b}_{q['priority']}"]
            reply = cell['joint']['dispatch_to_response_ns']['median_ns'] * settings['estimate_factor']
            residual = residuals[b]['ns']
            if residual is None: continue
            other = 'GPU' if b == 'CPU' else 'CPU'
            factor = settings['predicted_interference'] if policy in ('P_PAIR_COST_PC', 'P_NO_PARALLEL_PC') else 1.0
            overlap = lanes[other]['phase'] == 'EXECUTING' and lanes[other]['request'] is not None and not global_serial
            if overlap and factor > 1 and residuals[other]['ns'] is None:
                result['reason']='wait_unknown_overrun_pair_cost'
                continue  # unknown harm is not zero; no invented finite/inf penalty
            service = cell['observed_phases']['start_to_output_ready_ns']['median_ns'] * settings['estimate_factor']
            # A conservative static overlap approximation, NOT a fitted interference model.
            extra = service * (factor - 1) if overlap else 0
            harm = residuals[other]['ns'] * (factor - 1) if overlap and factor > 1 else 0
            score = residual + reply + extra + harm
            candidate = dict(request_id=q['id'], backend=b, score_ns=score, reply_ns=reply,
                             wait_ns=residual, assumed_pair_cost_ns=extra + harm, available=not lanes[b]['request'])
            candidates.append(candidate)
        result['candidates'].extend(candidates)
        if not candidates: continue
        winner = min(candidates, key=lambda x: (x['score_ns'], x['backend'] != 'CPU'))
        if winner['available']:
            result.update(selected=dict(request_id=q['id'], backend=winner['backend']), reason='minimum_predicted_cost')
            return result
        # Do not dispatch lower-ranked requests past a predicted wait for the head.
        if policy in ('B3_SOLO_EFT_PC', 'P_PAIR_COST_PC', 'P_NO_PARALLEL_PC'): return result
    return result


def simulate(config, vectors, requests, *, policy, settings, seed, horizon_ns=120_000_000_000,
             admission=None):
    # Optional REPLAN-PC-01 event hook. None preserves the frozen v3 execution path.
    base.validate_config(config)
    base.require(policy in POLICIES and settings['mode'] in ('strict', 'explore'), 'policy/mode')
    base.require(0 < len(requests) <= 128 and 0 < horizon_ns <= 600_000_000_000, 'bounded scenario')
    for name in ('decision_ns', 'record_ns', 'dispatch_ns'):
        base.require(type(settings[name]) is int and settings[name] >= 0, 'explicit overhead assumption')
    base.require(settings['interference'] >= 1 and settings['predicted_interference'] >= 1 and settings['estimate_factor'] > 0, 'sensitivity range')
    base.require(len({r['id'] for r in requests}) == len(requests), 'duplicate request')
    ledger = {r['id']: dict(r, status='not_arrived') for r in requests}
    arrivals = sorted(requests, key=lambda r: (r['arrival_ns'], r['ordinal'], r['id']))
    queue, decisions, transitions = [], [], []
    lanes = {b: None for b in ('CPU', 'GPU')}
    now = 0.0; ai = 0; pending = None; count = 0; review_needed = True
    def public():
        return {b: dict(request=x['ticket'] if x else None, phase=PHASES[x['stage']] if x else 'AVAILABLE',
                        since=x['since'] if x else now, dispatch=x['dispatch'] if x else None) for b,x in lanes.items()}
    def rate(b):
        x=lanes[b];other=lanes['GPU' if b=='CPU' else 'CPU']
        return 1 / settings['interference'] if x and x['stage']==1 and other and other['stage']==1 else 1.0
    while now <= horizon_ns:
        count += 1; base.require(count < 100000, 'event loop bound')
        # Same-time rule: phase/release CPU then GPU, arrivals ordinal, decision completion,
        # then a fresh decision. Zero intervals are exhausted before decisions.
        for b in ('CPU', 'GPU'):
            x=lanes[b]
            while x and x['left'] <= 0.0001:
                review_needed = True
                row=ledger[x['ticket']['id']];stage=x['stage'];row[FIELDS[stage]]=round(now)
                transitions.append(dict(at_ns=round(now), request_id=row['id'], backend=b, event=FIELDS[stage]))
                if (stage==1 and row['priority']=='urgent') or (stage==2 and row['priority']=='normal'):
                    row['response_ns']=round(now-row['arrival_ns'])
                    row['late_success']=row['response_ns']>row['deadline_offset_ns']
                if stage==4:
                    row['status']='succeeded';lanes[b]=None;x=None
                else:
                    x['stage']+=1;x['since']=now;x['left']=x['durations'][x['stage']]
        if admission is not None:
            review_needed |= admission.interactions_at(now)
        while ai<len(arrivals) and arrivals[ai]['arrival_ns']<=now:
            q=arrivals[ai];queue.append(dict(q));ledger[q['id']].update(status='queued',queue_entry_ns=q['arrival_ns']);ai+=1
            review_needed = True
        if admission is not None:
            review_needed |= admission.expiries_at(now)
        if pending and pending['end']<=now:
            selected=pending['selected']
            if selected and admission is not None:
                q=next(q for q in queue if q['id']==selected['request_id'])
                if not admission.check_dispatch(q, now, pending):
                    selected=None  # Ticket never left queue; no lane/vector was acquired.
                review_needed = True
            if selected:
                rid,b=selected['request_id'],selected['backend'];q=next(q for q in queue if q['id']==rid)
                queue.remove(q);base.require(lanes[b] is None,'busy lane early release')
                key=f"{q['task']}_{b}_{q['priority']}";index=keyed_index(seed,rid,b)
                vector=vectors['cells'][key][index]
                ds=list(vector['durations_ns'])
                ds[0]*=settings.get('load_prepare_factor',1);ds[4]*=settings.get('load_callback_factor',1)
                lanes[b]=dict(ticket=q,stage=0,since=now,dispatch=now,left=ds[0],durations=ds)
                ledger[rid].update(status='executing',backend=b,decision_start_ns=pending['start'],
                    decision_end_ns=pending['start']+settings['decision_ns'],
                    record_end_ns=pending['start']+settings['decision_ns']+settings['record_ns'],
                    dispatch_ns=round(now),source_request_id=vector['source_request_id'])
            pending=None
        if now >= horizon_ns: break
        # Zero-duration dispatch stages must transition before judging again.
        if any(x and x['left']<=0.0001 for x in lanes.values()): continue
        if pending is None and queue and (admission is None or review_needed):
            eligible=queue if admission is None else admission.eligible(queue, now)
            d=choose(config,eligible,public(),now,policy,settings)
            if admission is not None:
                d['admission']=admission.snapshot(queue, now)
                if not eligible: d['reason']='background_start_blocked'
            decisions.append(d)
            review_needed=False
            cost=settings['decision_ns']+settings['record_ns']+(settings['dispatch_ns'] if d['selected'] else 0)
            if d['selected']:
                pending=dict(start=now,end=now+cost,selected=d['selected'])
                if cost==0: continue
            elif cost>0:
                # A no-selection call consumes scheduler time but does not spin forever.
                pending=dict(start=now,end=now+cost,selected=None)
        if ai==len(arrivals) and not queue and not any(lanes.values()) and pending is None:
            if admission is None or admission.next_event() is None: break
        candidates=[]
        if admission is not None and admission.next_event() is not None:
            candidates.append(float(admission.next_event()))
        if ai<len(arrivals):candidates.append(float(arrivals[ai]['arrival_ns']))
        if pending:candidates.append(pending['end'])
        for b,x in lanes.items():
            if x:candidates.append(now+x['left']/rate(b))
        if not candidates:break
        target=min(min(candidates),float(horizon_ns))
        # No-selection completion must not trigger a new busy-poll decision every cost ns.
        if admission is None and pending and not pending['selected'] and pending['end']==target:
            pending=None
            others=[v for v in candidates if v>target]
            target=min(min(others),float(horizon_ns)) if others else float(horizon_ns)
        delta=target-now
        for b,x in lanes.items():
            if x:x['left']-=delta*rate(b)
        now=target
    rows=list(ledger.values())
    for r in rows:
        if r['status'] not in ('succeeded','not_arrived'):r['status']='unfinished'
    def rank95(values):return sorted(values)[math.ceil(.95*len(values))-1] if values else None
    urgent=[r for r in rows if r['priority']=='urgent'];normal=[r for r in rows if r['priority']=='normal']
    def responses(rs):return [r['response_ns']/1e6 for r in rs if 'response_ns' in r]
    complete=all(r['status']=='succeeded' for r in rows)
    span=(max(r['lane_available_ns'] for r in rows)-min(r['arrival_ns'] for r in rows))/1e9 if complete else None
    def timely(rs):return sum('response_ns' in r and not r['late_success'] for r in rs)/len(rs) if rs else None
    metrics=dict(urgent_p95_ms=rank95(responses(urgent)),urgent_deadline_violation=1-timely(urgent) if urgent else None,
        normal_mean_ms=statistics.mean(responses(normal)) if responses(normal) else None,normal_timely=timely(normal),
        completion=sum(r['status']=='succeeded' for r in rows)/len(rows),makespan_s=span,
        throughput=len(rows)/span if span else None,planned=len(rows),arrived=ai,
        urgent_n=len(urgent),normal_n=len(normal),response_ready=sum('response_ns' in r for r in rows),
        unfinished=sum(r['status']=='unfinished' for r in rows),not_arrived=sum(r['status']=='not_arrived' for r in rows),
        late_success=sum(r.get('late_success',False) for r in rows))
    return dict(version=VERSION,policy=policy,settings=settings,seed=seed,metrics=metrics,ledger=rows,
        decisions=decisions,transitions=transitions,experiment_ready=False,
        evidence='model-conditional exploration; no device performance PASS',
        unsupported=['stochastic failures/rejection/expiry','thermal/energy','unmeasured overlap causal model'],
        policy_information='arrived tickets, observable phases, fixed development point estimates only')
