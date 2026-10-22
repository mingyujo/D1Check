"""Saved-only independent neural inference, provenance and frozen-state audits."""
import collections,copy,gzip,hashlib,json,math,sys
import study as S
H,R,O=S.H,S.R,S.O
read,new,pin,verify=S.read,S.new,S.pin,S.verify
np,torch=S.np,S.torch

def numpy_logits(net,x,mask):
    w={k:v.detach().numpy().astype(np.float64) for k,v in net.state_dict().items()}
    linear=lambda a,n:a@w[n+'.weight'].T+w[n+'.bias']
    e=np.tanh(linear(np.asarray(x,np.float64),'encode.0'));m=np.asarray(mask,bool)
    ctx=np.concatenate(((e*m[:,:,None]).sum(1)/m.sum(1)[:,None],np.where(m[:,:,None],e,-1e9).max(1)),axis=-1)
    return np.where(m,linear(np.tanh(linear(np.concatenate((e,np.broadcast_to(ctx[:,None],(len(e),36,96))),axis=-1),'actor.0')),'actor.2').squeeze(-1),-1e9)

def infer(net,frames):
    x=torch.from_numpy(np.stack([f['x'] for f in frames]));mask=torch.from_numpy(np.stack([f['mask'] for f in frames]));target=torch.from_numpy(np.stack([f['teacher_mask'] for f in frames]))
    with torch.no_grad():p=torch.cat([net(x[i],mask[i])[0].argmax(-1) for i in torch.arange(len(x)).split(128)])
    good=target.gather(1,p[:,None]).squeeze(1);nontrivial=mask.sum(-1)>1
    return dict(all=float(good.float().mean()),nontrivial=float(good[nontrivial].float().mean()),nontrivial_n=int(nontrivial.sum()),correct=int(good.sum()),n=len(frames))

def audit():
    op=read(H/'OPERATION.json');verify(op['source_pins']);result=read(O/'RESULT.json');inputs=read(H/'INPUTS.json');initial=S.loadpt(S.CHECKPOINT);initial_net=S.Learner(state=initial)
    assert len(result['fits'])==2 and all(result['fits'])
    states=[initial]+[S.loadpt(R/f['checkpoint']['path']) for f in result['fits']];nets=[S.Learner(state=x) for x in states];before=[x.snapshot() for x in nets]
    frames_datasets=[];fit_audits=[]
    for j,fit in enumerate(result['fits'],1):
        trace=S.loadpt(R/fit['trace']['path']);frames=S.loadpt(R/fit['dataset']['path'])['frames'];frames_datasets.append(frames)
        actual=infer(nets[j].net,frames);start=infer(nets[j-1].net,frames);assert abs(actual['all']-trace['logs'][-1]['accuracy']['all'])<1e-7 and abs(actual['nontrivial']-trace['logs'][-1]['accuracy']['nontrivial'])<1e-7 and start['all']==trace['initial']['all']
        assert trace['kind']=='MASKED_ACTION_CLASSIFICATION_BC' and trace['cost_regression'] is False and trace['EVAL_used_for_selection'] is False
        assert states[j]['bc_steps']-states[j-1]['bc_steps']==trace['new_BC_steps'] and states[j]['network_sha256']==trace['network_sha256']!=states[j-1]['network_sha256']
        for k in ('updates','episodes','steps'):assert states[j][k]==states[j-1][k]
        for k in ('actor_optimizer','critic_optimizer','action_rng','shuffle_rng'):S.equal(states[j][k],states[j-1][k])
        S.equal(states[j]['bc_rng'],trace['shuffle_rng'])
        for key,v in states[j]['network'].items():
            assert v.shape==initial['network'][key].shape
            if key.startswith('critic.'):assert torch.equal(v,initial['network'][key])
        for item in trace['optimizer']['state'].values():
            assert int(item['step'])==trace['new_BC_steps'] and torch.isfinite(item['exp_avg']).all() and torch.isfinite(item['exp_avg_sq']).all()
        fit_audits.append(dict(stage=j,initial=start,final=actual,optimizer_steps=trace['new_BC_steps'],epochs=trace['epochs']))
    # Independently bind all actual TRAIN tensors to saved public decisions and the fair teacher.
    frames=frames_datasets[-1];by_source=collections.defaultdict(list)
    for f in frames:by_source[f['source_raw']['path']].append(f)
    allowed_cases={x['case'] for x in inputs['saved_teacher_TRAIN']+inputs['saved_old_neural_TRAIN']}|{x['case']['id'] for x in inputs['training']};eval_cases={x['case']['id'] for x in inputs['evaluation']};assert allowed_cases.isdisjoint(eval_cases)
    label_bindings=0;forecast_replay=0
    with gzip.open(O/'REPLAYED_TRAIN_LABELS.jsonl.gz','wt',encoding='utf8') as stream:
        for source,fs in by_source.items():
            verify([fs[0]['source_raw']]);d=read(R/source);bank=read(R/d['source']['bank']['path']) if 'source' in d else None
            if bank is None:
                row=next(x for x in inputs['saved_old_neural_TRAIN'] if x['raw']['path']==source);bank=read(R/row['bank']['path'])
            actor=S.Policy(S.P.Nominal(bank['nominal_vectors']),S.P.physics(),d['case'])
            for f in fs:
                assert f['split']=='TRAIN' and f['source_case'] in allowed_cases and f['source_case'] not in eval_cases
                index=f['source_decision_index'];s=d['result']['decisions'][index]['public_state'];assert S.B.L.digest(s)==f['source_public_sha256']
                b=actor.encode(s);expected=S.labels(s,b,f['source_case'],index,S.B.L.digest(s))
                for key in ('x','mask','scores','teacher_mask'):assert np.array_equal(expected[key],f[key])
                assert expected['index']==f['index'];label_bindings+=1;forecast_replay+=1
                c=dict(**{k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in b.items() if k!='scores'},teacher_index=f['index'],teacher_mask=f['teacher_mask'].tolist(),chosen=f['index'],action=b['actions'][f['index']],post_NN_override=False,future_information=False)
                # Label verification records, explicitly not actual actions or new environment rollouts.
                stream.write(json.dumps(dict(public_state=s,call=c,bank_source=d.get('source',{}).get('bank') or next(x['bank'] for x in inputs['saved_old_neural_TRAIN'] if x['raw']['path']==source),config=d['result']['config']))+'\n')
            print('SAVED_LABEL_BIND',source,len(fs),flush=True)
    neural=bindings=ties=0;maxregret=0.;cases=[]
    for row in result['rows']:
        if row['status']!='COMPLETE':continue
        verify([row['raw']]);d=read(R/row['raw']['path']);net=nets[1 if row['kind']=='TRAIN' else 2].net
        for start in range(0,len(d['calls']),128):
            part=d['calls'][start:start+128];x=np.asarray([c['x'] for c in part],np.float32);mask=np.asarray([c['mask'] for c in part],bool)
            with torch.no_grad():p=net(torch.from_numpy(x),torch.from_numpy(mask))[0].argmax(-1).numpy()
            z=numpy_logits(net,x,mask)
            for j,c in enumerate(part):
                assert int(p[j])==c['chosen'] and c['mask'][c['chosen']] and c['post_NN_override'] is False
                regret=float(z[j].max()-z[j,c['chosen']]);assert regret<2e-6;maxregret=max(maxregret,regret);ties+=int(z[j].argmax()!=c['chosen']);neural+=1
        bank=read(R/row['bank']['path']);jobs={q['request_id']:q for q in bank['jobs']}
        for q in d['result']['requests']:
            b=jobs[q['request_id']];assert all(q[k]==b[k] for k in ('scheduled_arrival_ns','queue_entry_ns','deadline_ns','task','priority'))
            if q['route']:assert q['timing']['stages_ns']==b['routes'][q['route']]['stages_ns']
            bindings+=1
        calls=d['calls'];multi=[c for c in calls if sum(c['mask'])>1]
        def match(cs):return sum(c['teacher_mask'][c['chosen']] for c in cs)/len(cs) if cs else None
        cases.append(dict(case=row['case'],kind=row['kind'],network_sha256=row['network_sha256'],calls=len(calls),compatible_accuracy=match(calls),nontrivial_n=len(multi),nontrivial_accuracy=match(multi),teacher_exact=sum(c['chosen']==c['teacher_index'] for c in calls),max_teacher_regret=max(c['teacher_scores'][c['chosen']]-min(v for v,m in zip(c['teacher_scores'],c['mask']) if m) for c in calls)))
        print('SAVED_NEURAL_AUDIT',row['label'],len(calls),flush=True)
    for net,snapshot in zip(nets,before):S.equal(net.snapshot(),snapshot)
    verify(op['source_pins']);S.equal(S.loadpt(S.CHECKPOINT),initial)
    for fit in result['fits']:verify([fit['checkpoint'],fit['trace'],fit['dataset']])
    apples_to_apples=dict(initial=infer(nets[0].net,frames),stage1=infer(nets[1].net,frames),final=infer(nets[2].net,frames))
    new(O/'AUDIT_PY.json',dict(status='PASS',fit_audits=fit_audits,final_TRAIN_same_denominator=apples_to_apples,TRAIN_source_bindings=label_bindings,source_request_bindings=bindings,neural_frames=neural,Float64_rounding_ties=ties,Float64_argmax_max_regret=maxregret,cases=cases,all_checkpoint_optimizer_RNG_unchanged=True,original_network_architecture_unchanged=True,critic_weights_unchanged=True,labels_replayed_without_environment=forecast_replay,replayed_labels=pin(O/'REPLAYED_TRAIN_LABELS.jsonl.gz'),new_environment=0,new_fit=0))

def describe(v):
    v=sorted(v);return dict(n=len(v),mean=sum(v)/len(v) if v else None,P95=v[math.ceil(.95*len(v))-1] if v else None,max=max(v) if v else None)

def diagnostics():
    inputs=read(H/'INPUTS.json');rows=inputs['comparators']+[x for x in read(O/'RESULT.json')['rows'] if x['kind']=='EVAL'];out=[]
    for row in rows:
        if row['status']!='COMPLETE':continue
        d=read(R/row['raw']['path']);groups={}
        for g in ('ALL','N','U','C_N','D_N','C_U','D_U'):
            qs=[q for q in d['result']['requests'] if g=='ALL' or q['priority']==g or q['task']+'_'+q['priority']==g];answered=[q for q in qs if q['response_ns'] is not None and q['response_ns']<=d['case']['drain_stop_s']*1e9]
            groups[g]=dict(n=len(qs),on=sum(q['response_ns']<=q['deadline_ns'] for q in answered),queue=describe([(q['dispatch_ns']-q['queue_entry_ns'])/1e9 for q in qs if q['dispatch_ns'] is not None]),response=describe([(q['response_ns']-q['scheduled_arrival_ns'])/1e9 for q in answered]))
        extra={}
        if row['policy']=='BC_NEURAL_FAIR':
            counts=collections.Counter();regrets=[];latepath=collections.Counter()
            dispatch={c['action']['request_id']:c for c in d['calls'] if c['action']['kind']=='DISPATCH'}
            bank=read(R/row['bank']['path']);jobs={q['request_id']:q for q in bank['jobs']}
            for dec,c in zip(d['result']['decisions'],d['calls']):
                good=c['teacher_mask'][c['chosen']];counts['calls']+=1;counts['compatible']+=good;counts['exact']+=c['chosen']==c['teacher_index'];counts['nontrivial']+=sum(c['mask'])>1;counts['nontrivial_compatible']+=sum(c['mask'])>1 and good
                ta=c['actions'][c['teacher_index']];a=c['action'];counts['WAIT_when_teacher_dispatch']+=a['kind']!='DISPATCH' and ta['kind']=='DISPATCH';counts['dispatch_when_teacher_WAIT']+=a['kind']=='DISPATCH' and ta['kind']!='DISPATCH'
                counts['normal_protection_calls']+=bool(c['service_guard']['forced_normal_indices']);counts['forecast_horizon_reduced']+=c['forecasts'][0]['horizon_reduced'];counts['queue_over32']+=len(dec['public_state']['queue'])>32
                regrets.append(c['teacher_scores'][c['chosen']]-min(v for v,m in zip(c['teacher_scores'],c['mask']) if m))
            for q in d['result']['requests']:
                if q['response_ns'] is None or q['response_ns']<=q['deadline_ns']:continue
                label=q['priority']+'_';work=sum(jobs[q['request_id']]['routes'][q['route']]['stages_ns'][:2 if q['task']=='C' else 3]);latepath[label+('dispatch_solo_already_late' if q['dispatch_ns']+work>q['deadline_ns'] else 'requires_slowdown')]+=1
            extra=dict(imitation=dict(counts),teacher_regret=describe(regrets),late_path=dict(latepath))
        out.append(dict(case=row['case'],policy=row['policy'],rate=row['condition']['requests_per_second'],pattern=row['condition']['pattern'],groups=groups,WAIT_s=d['result']['wait_used_ns']/1e9,route_counts=dict(collections.Counter(q['task']+'_'+str(q['route']) for q in d['result']['requests'])),**extra));print('SAVED_DIAGNOSTIC',row['label'],flush=True)
    new(O/'DIAGNOSTICS.json',dict(status='PASS',rows=out,WAIT_may_overlap_productive_owners=True,new_environment=0,new_fit=0))

if __name__=='__main__':
    if sys.argv[1:]==['--audit']:audit()
    elif sys.argv[1:]==['--diagnostics']:diagnostics()
    else:raise SystemExit('Explicit saved --audit / --diagnostics')
