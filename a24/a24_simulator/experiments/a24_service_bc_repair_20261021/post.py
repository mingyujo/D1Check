"""Saved-only fit/source verification and diagnostics. Never starts science."""
import collections,copy,decimal,hashlib,json,math,sys
import study as S
H,R,O=S.H,S.R,S.O
read,new,verify=S.read,S.new,S.verify

def describe(v):
    v=sorted(v)
    return dict(n=len(v),mean=sum(v)/len(v) if v else None,P95=v[math.ceil(.95*len(v))-1] if v else None,max=max(v) if v else None)

def audit():
    op=read(H/'OPERATION.json');verify(op['source_pins']);result=read(O/'RESULT.json');model=read(O/'MODEL.json');before=copy.deepcopy(model)
    inputs=read(H/'INPUTS.json');items={x['case']['id']:x for x in inputs['training']+inputs['evaluation']}
    allowed={x['case']['id'] for x in inputs['training']};evaluation={x['case']['id'] for x in inputs['evaluation']}
    assert allowed.isdisjoint(evaluation) and set(model['training_cases'])==allowed
    train=[];bindings=frame_bindings=eval_choices=0;max_error=max_regret=0.;eval_inactive_nonzero=0
    D=decimal.Decimal;decimal.getcontext().prec=50
    active=[i for i,v in enumerate(model['active_features']) if v];k=len(active)
    G=[[D(0) for _ in active] for _ in active];rhs=[D(0) for _ in active];squares=[D(0)]*6;target_count=0
    coverage=[]
    for row in result['rows']:
        verify([row['raw']])
        if row['status']!='COMPLETE':continue
        item=items[row['case']];source=read(R/item['source_common_bank']['path']);bank=read(R/item['bank']['path']);d=read(R/row['raw']['path'])
        assert len(d['result']['requests'])==len(source['requests'])==len(bank['jobs'])
        for q,b,src in zip(d['result']['requests'],bank['jobs'],source['requests']):
            assert q['request_id']==src['id']==b['request_id'] and q['task']==src['task'] and q['priority']==src['priority']
            assert q['scheduled_arrival_ns']==round(src['arrival_s']*1e9) and q['deadline_ns']==round(src['deadline_s']*1e9) and q['queue_entry_ns']==round(src['ready_s']*1e9)
            if q['route']:assert q['timing']['stages_ns']==[round(x*1e9) for x in src['private_work'][q['route']]]
            bindings+=1
        if row['kind']=='TRAIN':
            verify([row['frames']]);f=S.S.loadpt(R/row['frames']['path']);assert f['split']=='TRAIN' and f['source_case']==row['case'] and len(f['frames'])==len(d['calls'])
            for index,(frame,c) in enumerate(zip(f['frames'],d['calls'])):
                assert frame['case']==row['case'] and frame['split']=='TRAIN' and frame['decision']==index and frame['teacher_index']==c['teacher_index']==c['chosen']
                for key,callkey in [('features','features'),('mask','mask'),('physical_mask','physical_mask'),('targets','teacher_scores')]:assert frame[key].tolist()==c[callkey]
                train.append(frame);frame_bindings+=1
                for j,valid in enumerate(c['physical_mask']):
                    if not valid:continue
                    x=[D(str(v)) for v in c['features'][j]];target=D(str(c['teacher_scores'][j]));z=[x[i]/D(str(model['scales'][i])) for i in active]
                    for a in range(k):
                        rhs[a]+=z[a]*target
                        for b in range(k):G[a][b]+=z[a]*z[b]
                    for a in range(6):squares[a]+=x[a]*x[a]
                    target_count+=1
        if row['policy']=='BC_FAIR':
            for c in d['calls']:
                scores=[sum(float(v)/model['scales'][k]*model['scaled_weights'][k] for k,v in enumerate(x)) for x in c['features']]
                usable=[i for i,v in enumerate(c['mask']) if v];best=min(scores[i] for i in usable);chosen=next(i for i in usable if scores[i]<=best+1e-8)
                assert chosen==c['chosen'] and c['post_model_override'] is False
                teacher_best=min(c['teacher_scores'][i] for i in usable);max_regret=max(max_regret,c['teacher_scores'][chosen]-teacher_best)
                for i in range(len(c['actions'])):
                    max_error=max(max_error,abs(scores[i]-c['teacher_scores'][i]))
                    eval_inactive_nonzero+=any(c['features'][i][a]!=0 for a,v in enumerate(model['active_features']) if not v)
                eval_choices+=1
        states=[v['public_state'] for v in d['result']['decisions']]
        coverage.append(dict(case=row['case'],policy=row['policy'],min_T=min(s['sensor']['temperature_c'] for s in states),max_T=max(s['sensor']['temperature_c'] for s in states),max_queue=max(len(s['queue']) for s in states)))
        print('SAVED_PY',row['label'],flush=True)
    assert frame_bindings==model['frames'] and target_count==model['candidate_targets']
    matrix=[G[i]+[rhs[i]] for i in range(k)]
    for col in range(k):
        pivot=max(range(col,k),key=lambda r:abs(matrix[r][col]));matrix[col],matrix[pivot]=matrix[pivot],matrix[col]
        assert abs(matrix[col][col])>D('1e-25')
        div=matrix[col][col];matrix[col]=[v/div for v in matrix[col]]
        for row in range(k):
            if row!=col:
                mul=matrix[row][col];matrix[row]=[a-mul*b for a,b in zip(matrix[row],matrix[col])]
    solution=[float(matrix[i][-1]) for i in range(k)];coef_error=max(abs(v-model['scaled_weights'][active[i]]) for i,v in enumerate(solution));assert coef_error<1e-10
    scales=[float((v/D(target_count)).sqrt()) for v in squares]
    assert all(abs(scales[i]-model['scales'][i])<1e-10 for i in active)
    assert all(scales[i]<=1e-12 and model['scaled_weights'][i]==0 for i,v in enumerate(model['active_features']) if not v)
    squared=[];train_good=0
    for f in train:
        scores=[sum(float(v)/model['scales'][k]*model['scaled_weights'][k] for k,v in enumerate(x)) for x in f['features']]
        squared += [(scores[i]-float(f['targets'][i]))**2 for i,v in enumerate(f['physical_mask']) if v]
        idx=[i for i,v in enumerate(f['mask']) if v];b=min(scores[i] for i in idx);choice=next(i for i in idx if scores[i]<=b+1e-8)
        train_good+=float(f['targets'][choice])<=min(float(f['targets'][i]) for i in idx)+1e-8
    assert train_good/len(train)==model['TRAIN_compatible_accuracy'] and abs(math.sqrt(sum(squared)/len(squared))-model['TRAIN_RMSE'])<1e-12
    assert read(O/'MODEL.json')==before;verify(op['source_pins']);verify([result['model'],op['original_neural_checkpoint']])
    new(O/'AUDIT_PY.json',dict(status='PASS',source_request_bindings=bindings,TRAIN_frame_bindings=frame_bindings,TRAIN_candidate_targets=target_count,
        Decimal_precision=50,independent_normal_equation_max_coefficient_error=coef_error,TRAIN_compatible_accuracy=train_good/len(train),
        learned_EVAL_choices=eval_choices,EVAL_max_teacher_score_error=max_error,EVAL_max_teacher_regret=max_regret,EVAL_unidentified_feature_nonzero=eval_inactive_nonzero,
        active_rank=k,unidentified_features=[model['feature_names'][i] for i,v in enumerate(model['active_features']) if not v],
        model_and_original_neural_checkpoint_unchanged=True,EVAL_used_for_fit=False,coverage=coverage,new_environment=0,new_scientific_fit=0))

def analysis():
    inputs=read(H/'INPUTS.json');rows=inputs['comparators']+[x for x in read(O/'RESULT.json')['rows'] if x['kind']=='EVAL'];out=[];matched=[]
    for row in rows:
        if row['status']!='COMPLETE':continue
        d=read(R/row['raw']['path']);requests=d['result']['requests'];groups={}
        for group in ('ALL','N','U','C_N','D_N','C_U','D_U'):
            qs=[q for q in requests if group=='ALL' or q['priority']==group or q['task']+'_'+q['priority']==group];answered=[q for q in qs if q['response_ns'] is not None and q['response_ns']<=d['case']['drain_stop_s']*1e9]
            groups[group]=dict(n=len(qs),on=sum(q['response_ns']<=q['deadline_ns'] for q in answered),missing=len(qs)-len(answered),queue=describe([(q['dispatch_ns']-q['queue_entry_ns'])/1e9 for q in qs if q['dispatch_ns'] is not None]),response=describe([(q['response_ns']-q['scheduled_arrival_ns'])/1e9 for q in answered]))
        diag=collections.Counter();errors=[];max_eligible=0
        for dec,c in zip(d['result']['decisions'],d['calls']):
            s=dec['public_state']
            if row['policy'] in ('TEACHER_FAIR','BC_FAIR'):
                diag['normal_protection_calls']+=bool(c['service_guard']['forced_normal_indices'])
                diag['service_mask_removed_actions']+=sum(c['idle_mask'])-sum(c['mask']);diag['eligible_actions']+=sum(c['mask']);max_eligible=max(max_eligible,sum(c['mask']))
                diag['teacher_exact']+=c['chosen']==c['teacher_index'];best=min(c['teacher_scores'][i] for i,v in enumerate(c['mask']) if v)
                diag['teacher_compatible']+=c['teacher_scores'][c['chosen']]<=best+1e-8
                diag['forecast_horizon_reduced']+=c['forecasts'][0]['horizon_reduced'];diag['visible_cap_exceeded']+=len(s['queue'])>32
                if c['learned_scores'] is not None:errors.extend(abs(c['learned_scores'][i]-c['teacher_scores'][i]) for i in range(len(c['actions'])))
        out.append(dict(case=row['case'],policy=row['policy'],rate=row['condition']['requests_per_second'],pattern=row['condition']['pattern'],calls=len(d['calls']),groups=groups,guards=dict(diag),max_eligible=max_eligible,score_error=describe(errors),policy_WAIT_s=d['result']['wait_used_ns']/1e9,route_counts=dict(collections.Counter(q['task']+'_'+str(q['route']) for q in requests))))
        del d
    for item in inputs['evaluation']:
        case=item['case']['id'];same=[r for r in rows if r['case']==case];data={}
        for row in same:
            if row['status']!='COMPLETE':continue
            raw=read(R/row['raw']['path'])['result'];digest=lambda v:hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            data[row['policy']]=dict(requests=raw['requests'],action_sha=digest([x['action'] for x in raw['decisions']]),trace_sha=digest(raw['trace']));del raw
        t,b=data.get('TEACHER_FAIR'),data.get('BC_FAIR')
        identical=t is not None and b is not None and t==b
        comparisons=[]
        if b:
            target={q['request_id']:q for q in b['requests']}
            for p in ('FIFO_DYN','EDF_DYN','RR_DYN','TEACHER_OLD','BC_OLD'):
                if p not in data:continue
                ref={q['request_id']:q for q in data[p]['requests']};counts=collections.Counter()
                for rid,q in target.items():
                    a=ref[rid];assert (q['scheduled_arrival_ns'],q['deadline_ns'],q['queue_entry_ns'])==(a['scheduled_arrival_ns'],a['deadline_ns'],a['queue_entry_ns'])
                    x=q['response_ns'] is not None and q['response_ns']<=q['deadline_ns'];y=a['response_ns'] is not None and a['response_ns']<=a['deadline_ns']
                    if x!=y:counts[q['priority']+('_gained_on_time' if x else '_lost_on_time')]+=1
                comparisons.append(dict(reference=p,counts=dict(counts)))
        matched.append(dict(case=case,teacher_BC_requests_actions_trace_exact=identical,comparisons=comparisons))
        print('SAVED_DIAGNOSTIC',case,identical,flush=True)
    new(O/'DIAGNOSTICS.json',dict(status='PASS',rows=out,matched=matched,new_environment=0,new_fit=0,policy_WAIT_overlaps_productive_owners=True))

if __name__=='__main__':
    if sys.argv[1:]==['--audit']:audit()
    elif sys.argv[1:]==['--analysis']:analysis()
    else:raise SystemExit('Explicit saved --audit / --analysis')
