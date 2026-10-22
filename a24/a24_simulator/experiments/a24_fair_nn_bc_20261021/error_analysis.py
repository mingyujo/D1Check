"""Saved-only mismatch margins, input coverage and same-request gains/losses."""
import collections
import study as S
H,R,O=S.H,S.R,S.O
result=S.read(O/'RESULT.json');inputs=S.read(H/'INPUTS.json');frames=S.loadpt(R/result['fits'][-1]['dataset']['path'])['frames']
# Both positions stay in their original linear range in the actual saved TRAIN data.
T=[26+10*float(f['x'][0,18]) for f in frames];Q=[32*float(f['x'][0,13]) for f in frames]
assert max(abs((t-26)/10) for t in T)<5 and max(Q)<160
coverage=dict(min_temperature_C=min(T),max_temperature_C=max(T),max_queue=round(max(Q)));out=[]
for row in result['rows']:
    if row['kind']!='EVAL' or row['status']!='COMPLETE':continue
    d=S.read(R/row['raw']['path']);counts=collections.Counter();worst=None
    for dec,c in zip(d['result']['decisions'],d['calls']):
        s=dec['public_state'];good=c['teacher_mask'][c['chosen']];counts['calls']+=1;counts['outside_TRAIN_temperature']+=not coverage['min_temperature_C']-1e-5<=s['sensor']['temperature_c']<=coverage['max_temperature_C']+1e-5;counts['outside_TRAIN_max_queue']+=len(s['queue'])>coverage['max_queue']
        if good:continue
        counts['mismatches']+=1;regret=c['teacher_scores'][c['chosen']]-min(x for x,m in zip(c['teacher_scores'],c['mask']) if m)
        counts['cost_regret_le_1e-3']+=regret<=1e-3;counts['cost_regret_le_1e-2']+=regret<=1e-2;counts['cost_regret_gt_1e-1']+=regret>1e-1
        ti=c['teacher_index'];counts['teacher_score_feature_float32_equal']+=c['x'][ti][28]==c['x'][c['chosen']][28]
        if worst is None or regret>worst['cost_regret']:worst=dict(decision=dec['ordinal'] if 'ordinal' in dec else d['calls'].index(c),time_s=c['time_ns']/1e9,cost_regret=regret,chosen=c['action'],teacher_action=c['actions'][ti],chosen_service_pair=c['service_pairs'][c['chosen']],teacher_service_pair=c['service_pairs'][ti])
    target={q['request_id']:q for q in d['result']['requests']};comp=[]
    for policy in ('EDF_DYN','TEACHER_FAIR','BC_OLD'):
        r=next(r for r in inputs['comparators'] if r['case']==row['case'] and r['policy']==policy);ref=S.read(R/r['raw']['path'])['result']['requests'];g=collections.Counter();lost=[]
        for q in ref:
            x=target[q['request_id']];assert all(x[k]==q[k] for k in ('scheduled_arrival_ns','queue_entry_ns','deadline_ns','priority','task'))
            old=q['response_ns'] is not None and q['response_ns']<=q['deadline_ns'];new=x['response_ns'] is not None and x['response_ns']<=x['deadline_ns']
            if new!=old:g[q['priority']+('_gained_on_time' if new else '_lost_on_time')]+=1
            if old and not new:lost.append(dict(id=q['request_id'],task=q['task'],priority=q['priority'],arrival_s=q['scheduled_arrival_ns']/1e9,deadline_s=q['deadline_ns']/1e9,reference_dispatch_s=q['dispatch_ns']/1e9,new_dispatch_s=x['dispatch_ns']/1e9,reference_response_s=q['response_ns']/1e9,new_response_s=x['response_ns']/1e9,reference_route=q['route'],new_route=x['route']))
        comp.append(dict(reference=policy,counts=dict(g),lost_on_time_examples=sorted(lost,key=lambda x:x['new_response_s']-x['reference_response_s'],reverse=True)[:3]))
    out.append(dict(case=row['case'],mismatch_counts=dict(counts),worst_local_mismatch=worst,matched_request_comparisons=comp));print('SAVED_ERROR_ANALYSIS',row['case'],dict(counts),flush=True)
S.new(O/'ERROR_ANALYSIS.json',dict(status='PASS',TRAIN_coverage=coverage,rows=out,scope='Saved local prediction costs and realized matched requests; no causal attribution to one action or new holdout claims',new_environment=0,new_fit=0))
