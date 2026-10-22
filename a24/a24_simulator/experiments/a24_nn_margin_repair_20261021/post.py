"""Saved-only paired-fit, TRAIN provenance, and actual neural inference checks."""
import collections,copy,gzip,json,sys
import study as S
from a24_fair_nn_bc_20261021.post import numpy_logits,infer,describe
H,R,O=S.H,S.R,S.O
read,new,pin,verify=S.read,S.new,S.pin,S.verify
np,torch=S.np,S.torch

def audit():
    op=read(H/'OPERATION.json');verify(op['source_pins']);result=read(O/'RESULT.json');inputs=read(H/'INPUTS.json');initial=S.loadpt(S.CHECKPOINT)
    assert len(result['fits'])==2 and all(result['fits']);infos=result['fits'];states=[initial]+[S.loadpt(R/f['checkpoint']['path']) for f in infos];nets=[S.Learner(state=x) for x in states];before=[n.snapshot() for n in nets]
    frames=S.loadpt(O/'TRAIN_DATASET.pt.gz')['frames'];traces=[S.loadpt(R/f['trace']['path']) for f in infos];paired=[]
    for j,(info,trace) in enumerate(zip(infos,traces),1):
        fs=[dict(f,x=f['x'] if j==2 else f['absolute_x']) for f in frames];metrics=infer(nets[j].net,fs);start=infer(nets[0].net,fs)
        assert metrics['all']==trace['logs'][-1]['accuracy']['all'] and metrics['nontrivial']==trace['logs'][-1]['accuracy']['nontrivial'] and start['all']==trace['initial']['all']
        assert trace['relative_cost_input']==(j==2) and trace['epochs']==256 and trace['cost_regression'] is False and trace['EVAL_used_for_selection'] is False
        assert trace['initial_network_sha256']==initial['network_sha256'] and states[j]['network_sha256']==trace['network_sha256']!=initial['network_sha256'];assert states[j]['bc_steps']-initial['bc_steps']==trace['new_BC_steps']
        for k in ('updates','episodes','steps'):assert states[j][k]==initial[k]
        for k in ('actor_optimizer','critic_optimizer','action_rng','shuffle_rng'):S.equal(states[j][k],initial[k])
        S.equal(states[j]['bc_rng'],trace['shuffle_rng'])
        for k,v in states[j]['network'].items():
            assert v.shape==initial['network'][k].shape
            if k.startswith('critic.'):assert torch.equal(v,initial['network'][k])
        for item in trace['optimizer']['state'].values():assert int(item['step'])==trace['new_BC_steps'] and torch.isfinite(item['exp_avg']).all() and torch.isfinite(item['exp_avg_sq']).all()
        paired.append(dict(relative=j==2,initial=start,final=metrics,epochs=256,optimizer_steps=trace['new_BC_steps']))
    assert traces[0]['new_BC_steps']==traces[1]['new_BC_steps'] and traces[0]['paired_fit_seed']==traces[1]['paired_fit_seed']
    S.equal(traces[0]['shuffle_rng'],traces[1]['shuffle_rng']);S.equal(traces[0]['group_weights'],traces[1]['group_weights']);assert traces[0]['groups']==traces[1]['groups']
    by_source=collections.defaultdict(list)
    for f in frames:by_source[f['source_raw']['path']].append(f)
    eval_cases={x['case']['id'] for x in inputs['evaluation']};bound=0
    with gzip.open(O/'REPLAYED_TRAIN_LABELS.jsonl.gz','wt',encoding='utf8') as stream:
        for source,fs in by_source.items():
            verify([fs[0]['source_raw']]);d=read(R/source);bankpin=d['source']['bank'];bank=read(R/bankpin['path']);actor=S.Policy(S.P.Nominal(bank['nominal_vectors']),S.P.physics(),d['case'],relative=True)
            for f in fs:
                assert f['split']=='TRAIN' and f['source_case'] not in eval_cases
                index=f['source_decision_index'];s=d['result']['decisions'][index]['public_state'];assert S.B.L.digest(s)==f['source_public_sha256'];b=actor.encode(s);expected=S.N.labels(s,b,f['source_case'],index,S.B.L.digest(s))
                for key in ('x','mask','scores','teacher_mask'):assert np.array_equal(expected[key],f[key])
                assert np.array_equal(b['absolute_x'],f['absolute_x']) and expected['index']==f['index'];bound+=1
                c=dict(**{k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in b.items() if k not in ('scores','absolute_x')},teacher_index=f['index'],teacher_mask=f['teacher_mask'].tolist(),chosen=f['index'],action=b['actions'][f['index']],post_NN_override=False,future_information=False,relative_cost_input=True)
                stream.write(json.dumps(dict(public_state=s,call=c,bank_source=bankpin,config=d['result']['config']))+'\n')
            print('SAVED_TRAIN_BIND',source,len(fs),flush=True)
    neural=bindings=ties=0;maxregret=0.;cases=[]
    for row in result['rows']:
        if row['status']!='COMPLETE':continue
        verify([row['raw']]);d=read(R/row['raw']['path']);net=nets[0 if row['kind']=='TRAIN' else 2].net
        for start in range(0,len(d['calls']),128):
            part=d['calls'][start:start+128];x=np.asarray([c['x'] for c in part],np.float32);mask=np.asarray([c['mask'] for c in part],bool)
            with torch.no_grad():p=net(torch.from_numpy(x),torch.from_numpy(mask))[0].argmax(-1).numpy()
            z=numpy_logits(net,x,mask)
            for j,c in enumerate(part):
                assert int(p[j])==c['chosen'] and c['mask'][c['chosen']] and c['post_NN_override'] is False
                regret=float(z[j].max()-z[j,c['chosen']]);assert regret<2e-6;maxregret=max(maxregret,regret);ties+=int(z[j].argmax()!=c['chosen']);neural+=1
        bank=read(R/row['bank']['path']);jobs={q['request_id']:q for q in bank['jobs']}
        for q in d['result']['requests']:
            b=jobs[q['request_id']];assert all(q[k]==b[k] for k in ('scheduled_arrival_ns','queue_entry_ns','deadline_ns','priority','task'))
            if q['route']:assert q['timing']['stages_ns']==b['routes'][q['route']]['stages_ns']
            bindings+=1
        calls=d['calls'];multi=[c for c in calls if sum(c['mask'])>1]
        good=sum(c['teacher_mask'][c['chosen']] for c in calls);mgood=sum(c['teacher_mask'][c['chosen']] for c in multi)
        cases.append(dict(case=row['case'],kind=row['kind'],calls=len(calls),compatible_correct=good,compatible_accuracy=good/len(calls),nontrivial_n=len(multi),nontrivial_correct=mgood,nontrivial_accuracy=mgood/len(multi) if multi else None,teacher_exact=sum(c['chosen']==c['teacher_index'] for c in calls),max_teacher_regret=max(c['teacher_scores'][c['chosen']]-min(v for v,m in zip(c['teacher_scores'],c['mask']) if m) for c in calls)))
        print('SAVED_NEURAL_AUDIT',row['label'],len(calls),flush=True)
    for n,snap in zip(nets,before):S.equal(n.snapshot(),snap)
    verify(op['source_pins']);S.equal(S.loadpt(S.CHECKPOINT),initial)
    for info in infos:verify([info['checkpoint'],info['trace'],info['dataset']])
    new(O/'AUDIT_PY.json',dict(status='PASS',paired_TRAIN=paired,paired_seed_data_batches_steps_verified=True,TRAIN_source_bindings=bound,source_request_bindings=bindings,neural_frames=neural,Float64_rounding_ties=ties,Float64_argmax_max_regret=maxregret,cases=cases,all_evaluation_checkpoint_optimizer_RNG_unchanged=True,original_network_architecture_unchanged=True,critic_weights_unchanged=True,replayed_labels=pin(O/'REPLAYED_TRAIN_LABELS.jsonl.gz'),new_environment=0,new_fit=0))

def diagnostics():
    inputs=read(H/'INPUTS.json');rows=inputs['comparators']+[x for x in read(O/'RESULT.json')['rows'] if x['kind']=='EVAL'];out=[]
    for row in rows:
        if row['status']!='COMPLETE':continue
        d=read(R/row['raw']['path']);groups={}
        for g in ('ALL','N','U','C_N','D_N','C_U','D_U'):
            qs=[q for q in d['result']['requests'] if g=='ALL' or q['priority']==g or q['task']+'_'+q['priority']==g];answered=[q for q in qs if q['response_ns'] is not None and q['response_ns']<=d['case']['drain_stop_s']*1e9]
            groups[g]=dict(n=len(qs),on=sum(q['response_ns']<=q['deadline_ns'] for q in answered),queue=describe([(q['dispatch_ns']-q['queue_entry_ns'])/1e9 for q in qs if q['dispatch_ns'] is not None]),response=describe([(q['response_ns']-q['scheduled_arrival_ns'])/1e9 for q in answered]))
        extra={}
        if row['policy']=='BC_NEURAL_REPAIRED':
            counts=collections.Counter();regrets=[]
            for dec,c in zip(d['result']['decisions'],d['calls']):
                good=c['teacher_mask'][c['chosen']];counts['calls']+=1;counts['compatible']+=good;counts['exact']+=c['chosen']==c['teacher_index'];counts['nontrivial']+=sum(c['mask'])>1;counts['nontrivial_compatible']+=sum(c['mask'])>1 and good
                ta=c['actions'][c['teacher_index']];a=c['action'];counts['WAIT_when_teacher_dispatch']+=a['kind']!='DISPATCH' and ta['kind']=='DISPATCH';counts['dispatch_when_teacher_WAIT']+=a['kind']=='DISPATCH' and ta['kind']!='DISPATCH'
                counts['normal_protection_calls']+=bool(c['service_guard']['forced_normal_indices']);counts['forecast_horizon_reduced']+=c['forecasts'][0]['horizon_reduced'];counts['queue_over32']+=len(dec['public_state']['queue'])>32
                regrets.append(c['teacher_scores'][c['chosen']]-min(v for v,m in zip(c['teacher_scores'],c['mask']) if m))
            extra=dict(imitation=dict(counts),teacher_regret=describe(regrets))
        out.append(dict(case=row['case'],policy=row['policy'],rate=row['condition']['requests_per_second'],pattern=row['condition']['pattern'],groups=groups,WAIT_s=d['result']['wait_used_ns']/1e9,**extra));print('SAVED_DIAGNOSTIC',row['label'],flush=True)
    new(O/'DIAGNOSTICS.json',dict(status='PASS',rows=out,WAIT_may_overlap_productive_owners=True,new_environment=0,new_fit=0))

if __name__=='__main__':
    if sys.argv[1:]==['--audit']:audit()
    elif sys.argv[1:]==['--diagnostics']:diagnostics()
    else:raise SystemExit('Explicit saved --audit / --diagnostics')
