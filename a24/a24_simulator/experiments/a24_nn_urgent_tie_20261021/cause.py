"""Saved-only diagnosis; no simulation, fit, or EVAL-to-TRAIN data transfer."""
import collections,gzip,json,sys
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[2]
read=lambda p:json.load(gzip.open(p,'rt',encoding='utf8')) if str(p).endswith('.gz') else json.loads(p.read_text(encoding='utf8'))
old=R/'a24_simulator/results/A24_NN_MARGIN_EXACT_20261021_01';inputs=read(H.parent/'a24_nn_margin_exact_20261021/INPUTS.json');result=read(old/'RESULT.json')
rows=[];all_errors=[];train=collections.Counter()
def alternative(c):
    allowed=[i for i,v in enumerate(c['idle_mask']) if v];pairs=c['service_pairs']
    best=min((pairs[i]['late_U'],pairs[i]['late_ALL']) for i in allowed)
    return [i for i in allowed if (pairs[i]['late_U'],pairs[i]['late_ALL'])==best]
for row in result['rows']:
    d=read(R/row['raw']['path']);counter=collections.Counter();examples=[];errors=[]
    requests={q['request_id']:q for q in d['result']['requests']}
    for k,(dec,c) in enumerate(zip(d['result']['decisions'],d['calls'])):
        s=dec['public_state'];i,t=c['chosen'],c['teacher_index'];alt=alternative(c)
        counter['calls']+=1;counter['urgent_first_changes_service_set']+=set(alt)!=set(j for j,v in enumerate(c['mask']) if v) and any(c['service_pairs'][j]['late_U']<c['service_pairs'][t]['late_U'] for j in alt)
        if i!=t:
            diff=c['teacher_scores'][i]-min(v for v,m in zip(c['teacher_scores'],c['mask']) if m)
            error=dict(case=row['case'],decision=k,time_s=c['time_ns']/1e9,chosen=i,teacher=t,chosen_action=c['actions'][i],teacher_action=c['actions'][t],cost_regret=diff,cost_compatible=c['cost_compatible_mask'][i],score28_equal=c['x'][i][28]==c['x'][t][28],teacher_chosen_gap28=c['x'][i][28]-c['x'][t][28],input49_chosen=c['x'][i][49],input49_teacher=c['x'][t][49])
            errors.append(error)
        if c['action']['kind']=='DISPATCH':
            rid=c['action']['request_id'];q=requests[rid];f=c['forecasts'][i]
            if q['priority']=='U':
                predicted=f['responses_s'].get(rid,f['H_s']);actual=q['response_ns']/1e9;due=q['deadline_ns']/1e9
                counter['urgent_dispatches']+=1;counter['urgent_nominal_on_actual_late']+=predicted<=due+1e-8 and actual>due
                if predicted<=due+1e-8 and actual>due and len(examples)<3:examples.append(dict(request_id=rid,dispatch_s=q['dispatch_ns']/1e9,deadline_s=due,nominal_response_s=predicted,actual_response_s=actual,actual_minus_nominal_s=actual-predicted,owner_count=len(s['owners']),route=q['route'],teacher_exact=i==t))
    if row['kind']=='TRAIN':train.update(counter);continue
    all_errors.extend(errors);changes=[];counts=collections.Counter()
    for refpol in ('BC_NEURAL_PREVIOUS','TEACHER_FAIR'):
        p=next(x for x in inputs['comparators'] if x['case']==row['case'] and x['policy']==refpol);ref=read(R/p['raw']['path']);rq={q['request_id']:q for q in ref['result']['requests']};cc=collections.Counter();items=[]
        for rid,q in requests.items():
            z=rq[rid];before=z['response_ns'] is not None and z['response_ns']<=z['deadline_ns'];after=q['response_ns'] is not None and q['response_ns']<=q['deadline_ns']
            if before!=after:
                cc[q['priority']+('_gain' if after else '_loss')]+=1
                if q['priority']=='U':items.append(dict(request_id=rid,gain=after,task=q['task'],arrival_s=q['scheduled_arrival_ns']/1e9,deadline_s=q['deadline_ns']/1e9,old_dispatch_s=z['dispatch_ns']/1e9,new_dispatch_s=q['dispatch_ns']/1e9,old_response_s=z['response_ns']/1e9,new_response_s=q['response_ns']/1e9,old_route=z['route'],new_route=q['route']))
        changes.append(dict(reference=refpol,counts=dict(cc),urgent_changes=items))
    # Earliest high-rate loss: the saved decisions and both kinds of disagreement before it.
    lost=next((v for v in changes[0]['urgent_changes'] if not v['gain']),None);chain=[]
    if lost and row['condition']['rate_multiplier']==4:
        start=lost['arrival_s']-1;end=lost['new_dispatch_s']
        for dec,c in zip(d['result']['decisions'],d['calls']):
            t=c['time_ns']/1e9
            if start<=t<=end:chain.append(dict(time_s=t,action=c['action'],teacher_action=c['actions'][c['teacher_index']],exact=c['chosen']==c['teacher_index'],service_pair=c['service_pairs'][c['chosen']],normal_forced=c['service_guard']['forced_normal_indices'],queue=[dict(id=q['request_id'],priority=q['priority'],task=q['task']) for q in dec['public_state']['queue']],owners=[dict(id=q['request_id'],route=q['route'],stage=q['stage']) for q in dec['public_state']['owners']]))
    rows.append(dict(case=row['case'],counts=dict(counter),nominal_miss_examples=examples,comparisons=changes,first_urgent_loss=lost,first_loss_preceding_chain=chain))
out=dict(status='PASS',new_environment=0,new_fit=0,scope='Matched saved trajectories; no single-action causal intervention; EVAL is diagnostic only',TRAIN_counts=dict(train),EVAL=rows,errors=all_errors)
with (H/'PRECHANGE_DIAG.json').open('x',encoding='utf8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
print('SAVED_DIAG',len(all_errors),'errors','TRAIN',dict(train))
for r in rows:print(r['case'],r['counts'],[(x['reference'],x['counts']) for x in r['comparisons']],r['nominal_miss_examples'][:1])
