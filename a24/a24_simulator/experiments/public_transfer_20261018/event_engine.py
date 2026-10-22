"""Causal five-phase event engine with progress/thermal/cost feedback.

Measured SERIAL vectors remain immutable latent work. Progress, not historical
phase durations, responds to current heat. New paired progress is explicitly
independent; the original observational pair-rate model is preserved elsewhere.
"""
import copy
import heapq
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'reference/model_integration'))
from timing_model import context_for_route,digest
from dynamics import NS,advance_jobs,objectives,weighted

BOUNDARIES=('execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','available_ns')


def run(public,model,actor,physics,key,guard):
    if not guard.get('durable_START_consumed') or not guard.get('start_id'):raise ValueError('Durable registered START required')
    rows={};external=[];sequence=0
    for q in public['requests']:
        context,_=model.request_context(public,q);potential=[key,q['ordinal'],q['request_id']]
        admission=model.admission(context,q['task'],potential,protocol='SERIAL')
        entry=q['scheduled_arrival_ns']+admission['scheduled_to_actual_ns']+admission['actual_to_queue_ns']
        r={**{k:q[k] for k in ('request_id','ordinal','task','priority','scheduled_arrival_ns','deadline_ns')},
            'queue_entry_ns':entry,'dispatch_ns':None,'response_ns':None,'available_ns':None,'route':None,
            'context':context,'potential':potential,'admission':admission}
        rows[q['request_id']]=r;heapq.heappush(external,(entry,sequence,q['request_id']));sequence+=1
    stop=public['service_stop_ns'];drain=public['drain_stop_ns'];end=public['observation_end_ns']
    marks=sorted({0,35*NS,stop,drain,end})
    now=35*NS;wait_until=0;queue=set();owners={};decisions=[];trace=[];events=[];ticks=0
    event_wait=None
    state=dict(temperature_c=public['initial_ap_c'],shared_z=0.)
    peak=state['temperature_c'];past_increment=0.;wait_used=0
    def settle():
        for route,j in list(owners.items()):
            r=rows[j['request_id']]
            while j['remaining']<=1e-12:
                boundary=BOUNDARIES[j['stage']];r[boundary]=now
                events.append(dict(time_ns=now,request_id=r['request_id'],kind=boundary))
                if (r['task']=='C' and j['stage']==1) or (r['task']=='D' and j['stage']==2):r['response_ns']=now
                j['stage']+=1;j['public_progress_s']=0.;j['phase_start_ns']=now
                if j['stage']==5:owners.pop(route);break
                j['remaining']=r['timing']['stages_ns'][j['stage']]/NS
    while now<=end:
        arrived=False
        while external and external[0][0]<=now:
            _,_,rid=heapq.heappop(external);queue.add(rid);arrived=True
        settle()
        if event_wait is not None and (arrived or any(r not in owners or owners[r]['request_id']!=rid for r,rid in event_wait['owners'].items()) or now>=event_wait['cap_ns']):
            dose=now-event_wait['start_ns'];wait_used+=dose
            decisions[event_wait['decision_index']]['event_wait_end_ns']=now
            decisions[event_wait['decision_index']]['event_wait_elapsed_ns']=dose
            event_wait=None
        micro=0
        while now<stop and event_wait is None and now>=wait_until and queue and len(owners)<2:
            micro+=1
            if micro>len(rows)+5 or len(decisions)>len(rows)*100:raise ValueError('Decision cap')
            snapshot=dict(now_ns=now,queue=[{k:rows[rid].get(k) for k in ('request_id','ordinal','task','priority','scheduled_arrival_ns','queue_entry_ns','deadline_ns')} for rid in sorted(queue)],
                owners=[{**{k:j[k] for k in ('request_id','task','route','dispatch_ns','stage','phase_start_ns','public_progress_s')},
                    **{k:rows[j['request_id']][k] for k in ('priority','scheduled_arrival_ns','deadline_ns','response_ns')}} for j in owners.values()],
                sensor={**state,'peak_c':peak,'increment_so_far':past_increment},wait_used_ns=wait_used,
                initial_ap_c=public['initial_ap_c'],queue_count=len(queue))
            action=actor(snapshot)
            if action['kind']=='RESOURCE_WAIT':break
            decisions.append(dict(time_ns=now,action=copy.deepcopy(action),public_state=snapshot))
            if action['kind']=='WAIT_EVENT':
                if not owners or wait_used>=12*NS:raise ValueError('Event wait requires owner and positive common budget')
                budget=min(12*NS-wait_used,action.get('max_wait_ns',12*NS))
                if type(budget) is not int or budget<=0:raise ValueError('Event wait cap')
                event_wait=dict(start_ns=now,owners={r:j['request_id'] for r,j in owners.items()},cap_ns=min(stop,now+budget),decision_index=len(decisions)-1)
                break
            if action['kind']=='WAIT':
                dose=action['wait_ns']
                if type(dose) is not int or dose<=0 or wait_used+dose>12*NS:raise ValueError('WAIT budget')
                wait_used+=dose;wait_until=min(stop,now+dose);break
            rid,route=action['request_id'],action['route']
            if rid not in queue or route in owners or route not in ('CPU','GPU'):raise ValueError('Physical action violation')
            r=rows[rid];ctx=copy.deepcopy(r['context'])
            # Bind the route before the policy-independent SERIAL draw.
            selected=dict(request_id=rid,task=r['task'],route=route,context=context_for_route(ctx,r['task'],route))
            commitment=digest([snapshot,action])
            draw=model.draw_latent_serial(selected,snapshot,r['potential'])
            r.update(route=route,dispatch_ns=now,timing=draw,commitment_sha256=commitment)
            owners[route]=dict(request_id=rid,task=r['task'],route=route,dispatch_ns=now,stage=0,
                phase_start_ns=now,public_progress_s=0.,remaining=draw['stages_ns'][0]/NS)
            queue.remove(rid);state['shared_z']=1.;settle()
        if now==end:break
        times=[t for t in marks if t>now]
        if external:times.append(external[0][0])
        if event_wait is not None and event_wait['cap_ns']>now:times.append(event_wait['cap_ns'])
        if wait_until>now:times.append(wait_until)
        if owners:
            times.append(now+round(physics.c.tick_s*NS))
            for j in owners.values():
                rate=physics.speed(state['temperature_c'],j['route'],j['stage'])
                times.append(now+max(1,math.ceil(j['remaining']/rate*NS-1e-8)))
        nxt=min(t for t in times if t>now);dt=(nxt-now)/NS
        before=dict(state);active=[{k:j[k] for k in ('task','route','stage')} for j in owners.values()]
        state,terms=advance_jobs(physics,state,list(owners.values()),dt)
        for j in owners.values():j['public_progress_s']+=dt*terms['speeds'][j['route']]
        peak=max(peak,terms['peak']);past_increment+=terms['increment']
        trace.append(dict(start_ns=now,end_ns=nxt,state=before,next_state=dict(state),active=active,**terms))
        now=nxt;ticks+=1
        if ticks>50000:raise ValueError('Integration cap')
    ordered=sorted(rows.values(),key=lambda r:r['ordinal'])
    for r in ordered:r.pop('potential');r.pop('context')
    return dict(requests=ordered,decisions=decisions,trace=trace,events=events,wait_used_ns=wait_used,
        config=physics.c.__dict__,initial_ap_c=public['initial_ap_c'],state=state,peak=peak,
        serial_latent_vectors_unchanged=True,new_pair_progress='EXPLICIT_INDEPENDENT_PLUS_THERMAL_SPEED',
        physical_accuracy_verified=False,measured_J=None)


def metrics(result,case,physics):
    lo=35.;hi=case['service_stop_s'];drain=case['drain_stop_s'];initial=case['temperature_c'];c=physics.c
    work=[t for t in result['trace'] if t['start_ns']/NS>=lo-1e-9 and t['end_ns']/NS<=hi+1e-9]
    accounting=[t for t in result['trace'] if t['start_ns']/NS>=lo-1e-9 and t['end_ns']/NS<=drain+1e-9]
    inc=sum(t['increment'] for t in accounting);base=c.baseline*(drain-lo)
    area=sum(t['temperature_area'] for t in accounting)
    passive=c.idle_c*(drain-lo)+(initial-c.idle_c)*c.thermal_tau_s*(-math.expm1(-(drain-lo)/c.thermal_tau_s))
    heat=max(0.,area-passive)
    at_drain=next(t['next_state'] for t in result['trace'] if t['end_ns']==round(drain*NS))
    tail=physics.shared*c.idle_tail_s*at_drain['shared_z']
    rows=[dict(priority=r['priority'],arrival_s=r['scheduled_arrival_ns']/NS,deadline_s=r['deadline_ns']/NS,
        response_s=r['response_ns']/NS if r['response_ns'] is not None and r['response_ns']/NS<=drain else None) for r in result['requests']]
    peak=max(t['peak'] for t in accounting);costs=objectives(inc+tail,heat,peak,rows,case['n'])
    answered=[r for r in result['requests'] if r['response_ns'] is not None and r['response_ns']/NS<=drain]
    latency=sorted((r['response_ns']-r['scheduled_arrival_ns'])/NS for r in answered)
    return dict(planned=case['n'],on_time=sum(r['response_s'] is not None and r['response_s']<=r['deadline_s'] for r in rows),
        urgent_planned=sum(r['priority']=='U' for r in rows),urgent_on_time=sum(r['priority']=='U' and r['response_s'] is not None and r['response_s']<=r['deadline_s'] for r in rows),
        responded=len(answered),response_missing=case['n']-len(answered),incomplete=sum(r['available_ns'] is None or r['available_ns']/NS>drain for r in result['requests']),
        P95_completed_response_s=latency[max(0,math.ceil(.95*len(latency))-1)] if latency else None,
        total_J_proxy=base+inc,increment_J_proxy=inc,full_tail_increment_J_proxy=inc+tail,baseline_J_proxy=base,
        heat_area_proxy=heat,mean_AP_c=sum(t['temperature_area'] for t in work)/(hi-lo),peak_AP_c=peak,
        execution_throttled_s=sum(t['dt'] for t in accounting for r in t['active'] if r['stage']==1 and t['speeds'][r['route']]<.999999),
        wait_s=result['wait_used_ns']/NS,cost_vector=costs,objective=weighted(costs),
        route_counts={task+'_'+route:sum(r['task']==task and r['route']==route for r in result['requests']) for task in ('C','D') for route in ('CPU','GPU')},
        measured_J=None,model='HYPOTHESIS_COUPLED_345')
