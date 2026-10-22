"""Saved-only neural, TRAIN provenance, calibration, and fixed-state diagnostics."""
import collections,copy,gzip,json,math,sys
import study as S
from a24_fair_nn_bc_20261021.post import numpy_logits,infer,describe
from a24_nn_urgent_tie_20261021.policy import repair_bank,labels,choose
H,R,O=S.H,S.R,S.O
read,new,pin,verify=S.read,S.new,S.pin,S.verify
np,torch=S.np,S.torch

def audit():
    op=read(H/'OPERATION.json');verify(op['source_pins']);result=read(O/'RESULT.json');inputs=read(H/'INPUTS.json');cal=read(O/'RISK_CALIBRATION.json');risk=cal['task_margin_s'];initial=S.loadpt(S.CHECKPOINT)
    assert len(result['fits'])==2 and all(result['fits']);states=[initial]+[S.loadpt(R/f['checkpoint']['path']) for f in result['fits']];nets=[S.Learner(state=x) for x in states];before=[n.snapshot() for n in nets];fits=[]
    for stage,info in enumerate(result['fits'],1):
        trace=S.loadpt(R/info['trace']['path']);frames=S.loadpt(R/info['dataset']['path'])['frames'];actual=infer(nets[stage].net,frames);start=infer(nets[stage-1].net,frames)
        assert actual['all']==trace['logs'][-1]['accuracy']['all'] and actual['nontrivial']==trace['logs'][-1]['accuracy']['nontrivial'] and start['all']==trace['initial']['all']
        assert trace['epochs']==384 and trace['cost_regression'] is False and trace['EVAL_used_for_selection'] is False and trace['seed']==20266021+stage
        assert trace['initial_network_sha256']==states[stage-1]['network_sha256'] and states[stage]['network_sha256']==trace['network_sha256'];assert states[stage]['bc_steps']-states[stage-1]['bc_steps']==trace['new_BC_steps']
        for k in ('updates','episodes','steps'):assert states[stage][k]==initial[k]
        for k in ('actor_optimizer','critic_optimizer','action_rng','shuffle_rng'):S.equal(states[stage][k],states[stage-1][k])
        S.equal(states[stage]['bc_rng'],trace['shuffle_rng']);assert torch.equal(trace['pairwise_margins'],torch.from_numpy(S.margins_for(frames)))
        for key,v in states[stage]['network'].items():
            assert v.shape==initial['network'][key].shape
            if key.startswith('critic.'):assert torch.equal(v,initial['network'][key])
        for item in trace['optimizer']['state'].values():assert int(item['step'])==trace['new_BC_steps'] and torch.isfinite(item['exp_avg']).all() and torch.isfinite(item['exp_avg_sq']).all()
        fits.append(dict(stage=stage,initial=start,final=actual,epochs=384,optimizer_steps=trace['new_BC_steps']))
    # Independently recompute residual samples against the six preserved TRAIN traces.
    calibration_bindings=0;sources={}
    for sample in cal['samples']:
        p=sample['source']['path']
        if p not in sources:
            d=read(R/p);assert d['case']['condition']['role']=='TRAIN';sources[p]=(d,{q['request_id']:q for q in d['result']['requests']},{c['action']['request_id']:c for c in d['calls'] if c['action']['kind']=='DISPATCH'})
        d,qs,calls=sources[p];q=qs[sample['request_id']];c=calls[sample['request_id']];pred=c['forecasts'][c['chosen']]['responses_s'][sample['request_id']]
        assert q['priority']=='U' and q['task']==sample['task'] and q['response_ns']/1e9==sample['actual_response_s'] and pred==sample['predicted_response_s'] and q['response_ns']/1e9-pred==sample['residual_s'];calibration_bindings+=1
    for task in ('C','D'):
        v=sorted(s['residual_s'] for s in cal['samples'] if s['task']==task);assert len(v)>=20 and risk[task]==max(0,v[math.ceil(.9*len(v))-1])
    del sources
    # All TRAIN tensor labels bind to saved public states; new trajectories bind to own calls.
    frames=S.loadpt(R/result['fits'][-1]['dataset']['path'])['frames'];base=S.loadpt(O/'BASE_TRAIN.pt.gz')['frames'];eval_cases={x['case']['id'] for x in inputs['evaluation']};bound=0
    for a,b in zip(base,frames[:len(base)],strict=True):
        for key in ('x','mask','scores','teacher_mask'):assert np.array_equal(a[key],b[key])
        assert all(a[k]==b[k] for k in ('index','source_public_sha256','source_decision_index','source_raw','split','source_case'))
    with gzip.open(O/'ALL_TRAIN_LABELS.jsonl.gz','wt',encoding='utf8') as out:
        with gzip.open(O/'BASE_RELABELS.jsonl.gz','rt',encoding='utf8') as stream:
            for f,line in zip(base,stream,strict=True):
                d=json.loads(line);s=d['public_state'];c=d['call'];assert S.B.L.digest(s)==f['source_public_sha256'] and f['source_case'] not in eval_cases
                b=repair_bank(s,c,risk);expected=labels(s,b,f['source_case'],f['source_decision_index'],f['source_public_sha256'])
                for k in ('x','mask','scores','teacher_mask'):assert np.array_equal(expected[k],f[k])
                assert expected['index']==f['index'];bound+=1;out.write(line)
        grouped=collections.defaultdict(list)
        for f in frames[len(base):]:grouped[f['source_raw']['path']].append(f)
        for source,fs in grouped.items():
            verify([fs[0]['source_raw']]);d=read(R/source)
            for f in fs:
                k=f['source_decision_index'];s=d['result']['decisions'][k]['public_state'];c=d['calls'][k];assert f['source_case'] not in eval_cases and S.B.L.digest(s)==f['source_public_sha256'];b=repair_bank(s,c,risk);expected=labels(s,b,f['source_case'],k,f['source_public_sha256'])
                for key in ('x','mask','scores','teacher_mask'):assert np.array_equal(expected[key],f[key])
                assert expected['index']==f['index'];bound+=1
                cc=dict(c,chosen=f['index'],action=c['actions'][f['index']]);out.write(json.dumps(dict(public_state=s,call=cc,source=f['source_raw'],source_decision_index=k,bank_source=d['source']['bank'],config=d['result']['config'],label=f['index'],relabel_only=True))+'\n')
    assert bound==len(frames)
    neural=bindings=near_ties=0;maxregret=0.;cases=[]
    for row in result['rows']:
        if row['status']!='COMPLETE':continue
        verify([row['raw']]);d=read(R/row['raw']['path']);net=nets[1 if row['kind']=='TRAIN' else 2].net;counts=collections.Counter();regrets=[]
        if row['policy']!='TEACHER_RISK':
            for start in range(0,len(d['calls']),128):
                part=d['calls'][start:start+128];x=np.asarray([c['x'] for c in part],np.float32);mask=np.asarray([c['mask'] for c in part],bool)
                with torch.no_grad():p=net(torch.from_numpy(x),torch.from_numpy(mask))[0].argmax(-1).numpy()
                z=numpy_logits(net,x,mask)
                for j,c in enumerate(part):
                    assert int(p[j])==c['chosen'] and c['post_NN_override'] is False
                    regret=float(z[j].max()-z[j,c['chosen']]);assert regret<2e-6;maxregret=max(maxregret,regret);near_ties+=int(z[j].argmax()!=c['chosen']);neural+=1
        for dec,c in zip(d['result']['decisions'],d['calls']):
            assert dec['action']==c['action'] and c['mask'][c['chosen']] and c['future_information'] is False
            if row['policy']=='TEACHER_RISK':assert c['chosen']==c['teacher_index']
            counts['calls']+=1;counts['exact']+=c['chosen']==c['teacher_index'];counts['nontrivial']+=sum(c['mask'])>1;counts['nontrivial_exact']+=sum(c['mask'])>1 and c['chosen']==c['teacher_index'];counts['cost_compatible']+=c['cost_compatible_mask'][c['chosen']]
            regrets.append(c['teacher_scores'][c['chosen']]-min(v for v,m in zip(c['teacher_scores'],c['mask']) if m))
        bank=read(R/row['bank']['path']);jobs={q['request_id']:q for q in bank['jobs']}
        for q in d['result']['requests']:
            b=jobs[q['request_id']];assert all(q[k]==b[k] for k in ('scheduled_arrival_ns','queue_entry_ns','deadline_ns','task','priority'))
            if q['route']:assert q['timing']['stages_ns']==b['routes'][q['route']]['stages_ns']
            bindings+=1
        # Re-run public forecast preprocessing at evenly spaced saved states, no environment.
        actor=S.Policy(S.P.Nominal(bank['nominal_vectors']),S.P.physics(),d['case'],risk=risk)
        for k in sorted(set([0,len(d['calls'])-1]+list(range(0,len(d['calls']),max(1,len(d['calls'])//12))))):
            c=d['calls'][k];b=actor.encode(d['result']['decisions'][k]['public_state']);assert b['actions']==c['actions'] and np.array_equal(b['x'],np.asarray(c['x'],np.float32)) and np.array_equal(b['mask'],c['mask'])
        cases.append(dict(case=row['case'],policy=row['policy'],kind=row['kind'],counts=dict(counts),max_teacher_regret=max(regrets,default=0),exact_accuracy=counts['exact']/counts['calls'],nontrivial_accuracy=counts['nontrivial_exact']/max(1,counts['nontrivial'])));print('SAVED_NN_AUDIT',row['label'],dict(counts),flush=True)
    for net,state in zip(nets,before):S.equal(net.snapshot(),state)
    verify(op['source_pins']);new(O/'AUDIT_PY.json',dict(status='PASS',fits=fits,cases=cases,calibration_bindings=calibration_bindings,TRAIN_source_bindings=bound,request_bindings=bindings,neural_frames=neural,Float64_argmax_max_regret=maxregret,Float64_argmax_near_ties=near_ties,checkpoint_optimizer_RNG_frozen=True,original_Net_shape=True,new_environment=0,new_fit=0))

def fixed():
    result=read(O/'RESULT.json');state=S.loadpt(R/result['fits'][-1]['checkpoint']['path']);learner=S.Learner(state=state);before=learner.snapshot();risk=read(O/'RISK_CALIBRATION.json')['task_margin_s'];cases=[]
    for row in S.PREVIOUS_RESULT['rows']:
        if row['kind']!='EVAL':continue
        d=read(R/row['raw']['path']);counters=[collections.Counter(),collections.Counter()];errors=[]
        for start in range(0,len(d['calls']),128):
            part=d['calls'][start:start+128];banks=[]
            for offset,c in enumerate(part):
                s=d['result']['decisions'][start+offset]['public_state'];b=repair_bank(s,c,risk);banks.append(b)
            old_x=np.asarray([c['x'] for c in part],np.float32).copy();old_m=np.asarray([c['mask'] for c in part],bool)
            for k,c in enumerate(part):
                old_x[k,:,49]=0;old_x[k,:len(c['actions']),49]=np.arange(len(c['actions']))/35.
            with torch.no_grad():
                pp=[learner.net(torch.from_numpy(old_x),torch.from_numpy(old_m))[0].argmax(-1).numpy(),learner.net(torch.from_numpy(np.stack([b['x'] for b in banks])),torch.from_numpy(np.stack([b['mask'] for b in banks])))[0].argmax(-1).numpy()]
            for j,c in enumerate(part):
                old_teacher=c['teacher_index'];new_teacher=choose(banks[j]['teacher_scores'],banks[j]['mask']);was_error=c['chosen']!=old_teacher
                for mode,t in ((0,old_teacher),(1,new_teacher)):
                    v=counters[mode];v['calls']+=1;v['exact']+=int(pp[mode][j])==t;v['old_79_subset']+=was_error;v['old_79_now_exact']+=was_error and int(pp[mode][j])==t;v['teacher_action_changed']+=new_teacher!=old_teacher
                    m=old_m[j] if mode==0 else banks[j]['mask'];v['nontrivial']+=sum(m)>1;v['nontrivial_exact']+=sum(m)>1 and int(pp[mode][j])==t
                if was_error:errors.append(dict(decision=start+j,old_chosen=c['chosen'],old_teacher=old_teacher,new_prediction_on_old_mask=int(pp[0][j]),new_prediction_on_new_mask=int(pp[1][j]),new_teacher=new_teacher,new_label_changed=new_teacher!=old_teacher))
        cases.append(dict(case=row['case'],old_mask_old_teacher={k:int(v) for k,v in counters[0].items()},new_mask_new_teacher={k:int(v) for k,v in counters[1].items()},old_79_details=errors));print('FIXED_STATE',row['case'],[dict(c) for c in counters],flush=True)
    S.equal(learner.snapshot(),before);new(O/'FIXED_PREVIOUS_STATES.json',dict(status='PASS',cases=cases,scope='Entire previous 11329 saved public states, forward only. Old-mask mode disables the new risk guard for diagnostic inference, not deployed behavior. No gradient/EVAL model selection.',new_environment=0,new_fit=0))

if __name__=='__main__':
    if sys.argv[1:]==['--audit']:audit()
    elif sys.argv[1:]==['--fixed']:fixed()
    else:raise SystemExit('Explicit --audit / --fixed')
