"""Saved-only remaining lateness partition; no alternative schedule claims."""
import collections
import study as S
H,R,O=S.H,S.R,S.O
out=[]
for row in S.read(O/'RESULT.json')['rows']:
    if row['kind']!='EVAL' or row['policy']!='BC_FAIR' or row['status']!='COMPLETE':continue
    d=S.read(R/row['raw']['path']);bank=S.read(R/row['bank']['path']);jobs={q['request_id']:q for q in bank['jobs']};dispatch={c['action']['request_id']:c for c in d['calls'] if c['action']['kind']=='DISPATCH'}
    groups={};examples=[]
    for group in ('U','N'):
        count=collections.Counter()
        for q in d['result']['requests']:
            if q['priority']!=group:continue
            count['arrivals']+=1
            if q['response_ns'] is None:count['missing']+=1;continue
            if q['response_ns']<=q['deadline_ns']:count['on']+=1;continue
            count['late']+=1;c=dispatch[q['request_id']];f=c['forecasts'][c['chosen']];pred=f['responses_s'].get(q['request_id']);b=jobs[q['request_id']];end=2 if q['task']=='C' else 3
            work={r:sum(b['routes'][r]['stages_ns'][:end]) for r in ('CPU','GPU')}
            if q['queue_entry_ns']+min(work.values())>q['deadline_ns']:count['already_late_at_entry_even_fastest_private_solo']+=1
            elif q['dispatch_ns']+work[q['route']]>q['deadline_ns']:count['dispatch_too_late_even_chosen_private_solo']+=1
            else:count['requires_realized_thermal_contention_slowdown_to_be_late']+=1
            if pred is None:count['forecast_no_response']+=1
            elif pred*1e9<=q['deadline_ns']+10:count['forecast_on_at_dispatch_but_realized_late']+=1
            else:count['forecast_already_late_at_dispatch']+=1
            if group=='N':examples.append(dict(id=q['request_id'],task=q['task'],route=q['route'],arrival_s=q['scheduled_arrival_ns']/1e9,deadline_s=q['deadline_ns']/1e9,
                ready_s=q['queue_entry_ns']/1e9,dispatch_s=q['dispatch_ns']/1e9,response_s=q['response_ns']/1e9,predicted_response_at_dispatch_s=pred,
                queue_s=(q['dispatch_ns']-q['queue_entry_ns'])/1e9,private_solo_response_s=work[q['route']]/1e9,
                normal_guard_was_active=bool(c['service_guard']['forced_normal_indices']),forecast_late_pair=c['service_guard']['best_late_pair']))
        groups[group]=dict(count)
    out.append(dict(case=row['case'],groups=groups,normal_late_requests=examples))
S.new(O/'REMAINING_LATENESS.json',dict(status='PASS',rows=out,new_environment=0,new_fit=0,
    scope='Descriptive lower bound and dispatch forecast. Forecast vs realization mixes nominal/private durations, future contention, and actual policy continuation; not a pure model error or an optimal-schedule proof.'))
print('REMAINING_LATENESS',[(x['case'],x['groups']) for x in out],flush=True)
