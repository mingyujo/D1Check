"""Saved-only all-arrival diagnostics, request pairing and neural remainder."""
import collections,hashlib
import study as S
from a24_fair_nn_bc_20261021.post import describe
H,R,O=S.H,S.R,S.O
inputs=S.read(H/'INPUTS.json');result=S.read(O/'RESULT.json');newrows=[r for r in result['rows'] if r['kind']=='EVAL'];allrows=inputs['comparators']+newrows;diags=[];matched=[]
for row in newrows:
    d=S.read(R/row['raw']['path']);req={q['request_id']:q for q in d['result']['requests']};groups={}
    for g in ('ALL','N','U','C_N','D_N','C_U','D_U'):
        qs=[q for q in req.values() if g=='ALL' or q['priority']==g or q['task']+'_'+q['priority']==g];answered=[q for q in qs if q['response_ns'] is not None and q['response_ns']<=d['case']['drain_stop_s']*1e9]
        groups[g]=dict(n=len(qs),on=sum(q['response_ns']<=q['deadline_ns'] for q in answered),missing=len(qs)-len(answered),queue=describe([(q['dispatch_ns']-q['queue_entry_ns'])/1e9 for q in qs if q['dispatch_ns'] is not None]),response=describe([(q['response_ns']-q['scheduled_arrival_ns'])/1e9 for q in answered]))
    counts=collections.Counter();errors=[];residuals=[]
    for k,(dec,c) in enumerate(zip(d['result']['decisions'],d['calls'])):
        i,t=c['chosen'],c['teacher_index'];counts['calls']+=1;counts['exact']+=i==t;counts['multi']+=sum(c['mask'])>1;counts['multi_exact']+=sum(c['mask'])>1 and i==t;counts['cost_compatible']+=c['cost_compatible_mask'][i];counts['normal_protected']+=bool(c['service_guard']['forced_normal_indices']);counts['queue_over32']+=len(dec['public_state']['queue'])>32;counts['forecast_horizon_reduced']+=c['forecasts'][0]['horizon_reduced']
        counts['WAIT_when_teacher_dispatch']+=c['action']['kind']!='DISPATCH' and c['actions'][t]['kind']=='DISPATCH';counts['dispatch_when_teacher_WAIT']+=c['action']['kind']=='DISPATCH' and c['actions'][t]['kind']!='DISPATCH'
        if i!=t:
            regret=c['teacher_scores'][i]-min(v for v,m in zip(c['teacher_scores'],c['mask']) if m)
            errors.append(dict(decision=k,time_s=c['time_ns']/1e9,chosen=i,teacher=t,chosen_action=c['action'],teacher_action=c['actions'][t],cost_regret=regret,cost_compatible=c['cost_compatible_mask'][i],score28_equal=c['x'][i][28]==c['x'][t][28]))
        if c['action']['kind']=='DISPATCH':
            rid=c['action']['request_id'];q=req[rid]
            if q['priority']=='U' and q['response_ns'] is not None:
                f=c['forecasts'][i];end=f['responses_s'].get(rid,f['H_s']);due=q['deadline_ns']/1e9;actual=q['response_ns']/1e9;margin=c['risk_guard']['task_margin_s'][q['task']]
                counts['urgent_dispatches']+=1;counts['urgent_nominal_on_actual_late']+=end<=due+1e-8 and actual>due;counts['urgent_buffered_on_actual_late']+=end+margin<=due+1e-8 and actual>due;residuals.append(actual-end)
    diags.append(dict(case=row['case'],policy=row['policy'],groups=groups,counts=dict(counts),errors=errors,urgent_actual_minus_nominal=describe(residuals)))
    if row['policy']=='BC_NEURAL_URGENT':
        comps=[]
        for policy in ('FIFO_DYN','EDF_DYN','RR_DYN','TEACHER_FAIR','BC_NEURAL_PREVIOUS','BC_NEURAL_MARGIN','TEACHER_RISK'):
            refrow=next(r for r in allrows if r['case']==row['case'] and r['policy']==policy);ref=S.read(R/refrow['raw']['path']);rs={q['request_id']:q for q in ref['result']['requests']};changed=[];cc=collections.Counter()
            for rid,q in req.items():
                p=rs[rid];assert all(q[k]==p[k] for k in ('scheduled_arrival_ns','queue_entry_ns','deadline_ns','task','priority'));old=p['response_ns'] is not None and p['response_ns']<=p['deadline_ns'];new=q['response_ns'] is not None and q['response_ns']<=q['deadline_ns']
                if old!=new:
                    cc[q['priority']+('_gain' if new else '_loss')]+=1;changed.append(dict(request_id=rid,gain=new,priority=q['priority'],task=q['task'],arrival_s=q['scheduled_arrival_ns']/1e9,deadline_s=q['deadline_ns']/1e9,reference_response_s=p['response_ns']/1e9,new_response_s=q['response_ns']/1e9,reference_dispatch_s=p['dispatch_ns']/1e9,new_dispatch_s=q['dispatch_ns']/1e9,reference_route=p['route'],new_route=q['route']))
            comps.append(dict(reference=policy,counts=dict(cc),changed_requests=changed,requests_exact=ref['result']['requests']==d['result']['requests'],actions_exact=[c['action'] for c in ref['calls']]==[c['action'] for c in d['calls']],trace_exact=ref['result']['trace']==d['result']['trace']))
        matched.append(dict(case=row['case'],comparisons=comps))
    print('SAVED_ANALYZE',row['case'],row['policy'],groups['U']['on'],len(errors),flush=True)
S.new(O/'DIAGNOSTICS.json',dict(status='PASS',rows=diags,new_environment=0,new_fit=0))
S.new(O/'MATCHED_REQUESTS.json',dict(status='PASS',rows=matched,scope='Matched saved trajectories, not single-action causal intervention',new_environment=0,new_fit=0))
state=S.loadpt(R/result['fits'][-1]['checkpoint']['path']);learner=S.Learner(state=state);before=learner.snapshot();frames=S.loadpt(R/result['fits'][-1]['dataset']['path'])['frames'];groups=collections.defaultdict(collections.Counter);errors=[]
for start in range(0,len(frames),128):
    part=frames[start:start+128];x=S.np.stack([f['x'] for f in part]);m=S.np.stack([f['mask'] for f in part])
    with S.torch.no_grad():p=learner.net(S.torch.from_numpy(x),S.torch.from_numpy(m))[0].argmax(-1).numpy()
    for j,f in enumerate(part):
        groups[hashlib.sha256(f['x'].tobytes()+f['mask'].tobytes()).hexdigest()][f['index']]+=1
        if int(p[j])!=f['index']:
            i=int(p[j]);t=f['index'];errors.append(dict(source=f['source_raw'],case=f['source_case'],decision=f['source_decision_index'],teacher=t,chosen=i,cost_regret=float(f['scores'][i]-min(f['scores'][f['mask']])),teacher_input28=float(f['x'][t,28]),chosen_input28=float(f['x'][i,28]),cost_compatible=bool(f['cost_compatible_mask'][i])))
contradictory=[dict(input_sha256=k,labels=dict(v),rows=sum(v.values())) for k,v in groups.items() if len(v)>1];S.equal(learner.snapshot(),before)
S.new(O/'REMAINING_ERROR_AUDIT.json',dict(status='PASS',TRAIN_frames=len(frames),TRAIN_errors=errors,contradictory_identical_float32_groups=contradictory,EVAL_errors=sum(len(r['errors']) for r in diags if r['policy']=='BC_NEURAL_URGENT'),new_environment=0,new_fit=0))
