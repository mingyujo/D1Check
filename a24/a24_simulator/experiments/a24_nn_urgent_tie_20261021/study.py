"""Seventeen finite STARTs; existing completed identities are read-only."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import ast,collections,copy,gc,gzip,hashlib,json,math,shutil,subprocess,sys,time,traceback
from pathlib import Path
H=Path(__file__).resolve().parent;A=H.parents[1];R=A.parent;O=A/'results/A24_NN_URGENT_TIE_20261021_01'
sys.path.insert(0,str(H.parent))
from a24_nn_margin_exact_20261021 import study as M
from a24_nn_urgent_tie_20261021.policy import Policy,repair_bank,labels,VERSION
from a24_nn_urgent_tie_20261021.train import fit,losses,margins_for,EPOCHS
read,new,saved,pin,sha,stamp,verify=M.read,M.new,M.saved,M.pin,M.sha,M.stamp,M.verify
B,C,P,np,torch=M.B,M.C,M.P,M.np,M.torch
loadpt,pt,equal,Learner=M.loadpt,M.pt,M.equal,M.Learner
PREVIOUS_RESULT=read(M.O/'RESULT.json');CHECKPOINT=R/PREVIOUS_RESULT['fits'][-1]['checkpoint']['path']

def prepare():
    assert not O.exists() and not (H/'OPERATION.json').exists()
    for p in H.glob('*.py'):ast.parse(p.read_text(encoding='utf8'))
    prior=read(M.H/'OPERATION.json');verify(prior['source_pins']);inputs=read(M.H/'INPUTS.json');frames=loadpt(R/PREVIOUS_RESULT['fits'][-1]['dataset']['path'])['frames']
    comparators=inputs['comparators']+[{**r,'policy':'BC_NEURAL_MARGIN','reused':True} for r in PREVIOUS_RESULT['rows'] if r['kind']=='EVAL']
    cases=dict(training=inputs['training'],evaluation=inputs['evaluation'],base_TRAIN=PREVIOUS_RESULT['fits'][-1]['dataset'],replayed_TRAIN=pin(M.O/'REPLAYED_TRAIN_LABELS.jsonl.gz'),calibration_TRAIN=[r for r in PREVIOUS_RESULT['rows'] if r['kind']=='TRAIN'],comparators=comparators,EVAL_used_for_training=False)
    assert len(comparators)==36 and len(cases['calibration_TRAIN'])==6
    checks=0
    for c in cases['training']+cases['evaluation']:verify([c['bank'],c['public']]);checks+=2
    assert all(f['split']=='TRAIN' and f['source_case'] not in {i['case']['id'] for i in cases['evaluation']} for f in frames);checks+=len(frames)
    with gzip.open(R/cases['replayed_TRAIN']['path'],'rt',encoding='utf8') as f:
        for _ in range(8):
            d=json.loads(next(f));c=d['call'];s=d['public_state'];b=repair_bank(s,c,{'C':.03,'D':.10})
            assert np.isfinite(b['x']).all() and b['mask'].any()
            assert np.allclose(b['x'][:len(b['actions']),49],np.arange(len(b['actions']))/35,atol=1e-8)
            assert np.array_equal(np.delete(b['x'],[28,49],1),np.delete(np.asarray(c['x'],np.float32),[28,49],1));checks+=3
    logits=torch.tensor([[0.,1.,-1.]],requires_grad=True);target=torch.tensor([[True,False,False]]);mask=torch.ones_like(target);margin=torch.tensor([[0.,.1,.2]])
    ce,pair=losses(logits,target,mask,margin);assert torch.allclose(ce,torch.nn.functional.cross_entropy(logits,torch.tensor([0]),reduction='none')) and torch.allclose(pair,torch.tensor([.55]));(ce+.25*pair).mean().backward();assert torch.isfinite(logits.grad).all();checks+=3
    state=loadpt(CHECKPOINT);learner=Learner(state=state);equal(learner.snapshot(),state);checks+=1
    new(H/'INPUTS.json',cases);new(H/'READINESS.json',dict(status='PASS',checks=checks,base_TRAIN=len(frames),new_environment=0,new_fit=0,original_Net_shape=True,input_changes=[28,49],teacher_target_in_input=False))
    pins={p['path']:p for p in prior['source_pins']}
    paths=[p for p in H.iterdir() if p.is_file()]+[CHECKPOINT,M.H/'OPERATION.json',M.O/'RESULT.json',M.O/'FINAL_PROOF.json',M.O/'FINAL_RECHECK.json',R/cases['base_TRAIN']['path'],R/cases['replayed_TRAIN']['path']]
    paths += [R/r['raw']['path'] for r in comparators+cases['calibration_TRAIN']]
    for p in dict.fromkeys(paths):
        v=pin(p);pins[v['path']]=v
    new(H/'OPERATION.json',dict(schema=VERSION,utc=stamp(),authorization=dict(authorized=True,user_text='남은 모방 오차 79회랑 고부하에서 긴급 정시율이 떨어진 원인도 찾아서 보완하고, 같은 S26식 입력으로 다시 비교해봐'),source_pins=list(pins.values()),checkpoint=pin(CHECKPOINT),planned_TRAIN_residual_calibration=1,planned_TRAIN=6,planned_BC_fit=2,planned_EVAL=8,max_scientific_units=17,previous_local_derived=137945,derived_local_cap=137962,not_global_census=True,epochs_each_fit=EPOCHS,calibration_quantile=.90,calibration_minimum_samples_per_task=20,chosen_policy_precommitted='SECOND_FIT_BC50_RISK_SLACK_ACTION_POSITION',EVAL_model_selection=False,automatic_retry=False,new_PPO=0,new_measurement=0,new_physical_fit=0,adopted=False))
    print('PREPARED_URGENT_TIE',checks,'checks; 17 units',flush=True)

def receipt(event,label,kind,**extra):
    r=dict(event=event,label=label,kind=kind,utc=stamp(),durable_START_consumed=True,start_id=hashlib.sha256((OPSHA+'|'+label).encode()).hexdigest(),**extra)
    with (O/'receipts.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(r)+'\n');f.flush();os.fsync(f.fileno())
    return r

def calibrate(inputs):
    rec=receipt('START','TRAIN_RESIDUAL_CALIBRATION','CALIBRATION');samples=[]
    for row in inputs['calibration_TRAIN']:
        assert row['kind']=='TRAIN';verify([row['raw']]);d=read(R/row['raw']['path']);qs={q['request_id']:q for q in d['result']['requests']}
        for c in d['calls']:
            if c['action']['kind']!='DISPATCH':continue
            rid=c['action']['request_id'];q=qs[rid]
            if q['priority']!='U' or q['response_ns'] is None:continue
            f=c['forecasts'][c['chosen']];assert rid in f['responses_s']
            predicted=f['responses_s'][rid];actual=q['response_ns']/1e9
            samples.append(dict(source=row['raw'],case=row['case'],request_id=rid,task=q['task'],route=q['route'],dispatch_ns=q['dispatch_ns'],predicted_response_s=predicted,actual_response_s=actual,residual_s=actual-predicted,split='TRAIN'))
    model={};stats={}
    for task in ('C','D'):
        values=sorted(s['residual_s'] for s in samples if s['task']==task);assert len(values)>=20
        q=values[math.ceil(.9*len(values))-1];model[task]=max(0.,q);stats[task]=dict(n=len(values),signed_nearest_rank_q90=q,positive_margin_s=model[task],minimum=values[0],maximum=values[-1],nominal_underprediction_count=sum(v>0 for v in values))
    new(O/'RISK_CALIBRATION.json',dict(status='COMPLETE',kind='TRAIN_DISPATCH_RESPONSE_RESIDUAL_QUANTILE',quantile=.9,estimator='nearest rank; positive part; separate C/D, all routes pooled',task_margin_s=model,stats=stats,samples=samples,EVAL_used=False,new_environment=0,new_physical_fit=0))
    receipt('COMPLETE','TRAIN_RESIDUAL_CALIBRATION','CALIBRATION',artifact=pin(O/'RISK_CALIBRATION.json'));print('CALIBRATION_COMPLETE',stats,flush=True);return model

def relabel(inputs,risk):
    original=loadpt(R/inputs['base_TRAIN']['path'])['frames'];by_source=collections.defaultdict(list)
    for f in original:by_source[f['source_raw']['path']].append(f)
    ordered=[f for group in by_source.values() for f in group];frames=[];changed=0
    with gzip.open(R/inputs['replayed_TRAIN']['path'],'rt',encoding='utf8') as stream,gzip.open(O/'BASE_RELABELS.jsonl.gz','wt',encoding='utf8') as out:
        for f,line in zip(ordered,stream,strict=True):
            r=json.loads(line);s=r['public_state'];c=r['call'];assert f['split']=='TRAIN' and B.L.digest(s)==f['source_public_sha256'];assert np.array_equal(np.asarray(c['x'],np.float32),f['x']) and c['teacher_index']==f['index']
            b=repair_bank(s,c,risk);g=labels(s,b,f['source_case'],f['source_decision_index'],f['source_public_sha256']);g['source_raw']=f['source_raw'];changed+=g['index']!=f['index'];frames.append(g)
            call={k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in b.items() if k not in ('scores','absolute_x')}
            call.update(teacher_index=g['index'],teacher_mask=g['teacher_mask'].tolist(),cost_compatible_mask=g['cost_compatible_mask'].tolist(),chosen=g['index'],action=b['actions'][g['index']],post_NN_override=False,future_information=False,relative_cost_input=True)
            record=dict(public_state=s,call=call,source=g['source_raw'],source_decision_index=g['source_decision_index'],bank_source=r['bank_source'],config=r['config'],label=g['index'],relabel_only=True)
            out.write(json.dumps(record)+'\n')
    pt(O/'BASE_TRAIN.pt.gz',dict(frames=frames,split='TRAIN',EVAL_used=False));new(O/'BASE_TRAIN.json',dict(status='COMPLETE',frames=len(frames),changed_teacher_action=changed,saved_replay_source=inputs['replayed_TRAIN'],dataset=pin(O/'BASE_TRAIN.pt.gz'),new_environment=0,new_fit=0));print('BASE_RELABEL_COMPLETE',len(frames),changed,flush=True);return frames

def episode(item,state,kind,mode,risk,batch):
    case=copy.deepcopy(item['case']);label=case['id']+'__'+mode;rec=receipt('START',label,kind);start=time.monotonic();actor=None;last=[None];print('ENV_START',label,case['n'],flush=True)
    try:
        public=read(R/item['public']['path'])['public'];bank=read(R/item['bank']['path']);physics=P.physics();model=B.BankModel(bank['jobs'],{q['request_id']:public for q in public['requests']});learner=Learner(state=state) if state is not None else None;before=learner.snapshot() if learner else None;actor=Policy(P.Nominal(bank['nominal_vectors']),physics,case,learner,kind=='TRAIN',risk=risk);notice=[start]
        def guarded(s):
            last[0]=s;t=time.monotonic();assert t-start<1200 and t-batch<10800,'Finite wall cap';assert len(actor.calls)<=max(1024,20*case['n']),'Action cap'
            if t-notice[0]>=30:
                import psutil
                assert shutil.disk_usage(R).free>=4*1024**3 and psutil.virtual_memory().available>=1024**3,'Resource guard';print('ENV_PROGRESS',label,len(actor.calls),round(s['now_ns']/1e9-35,2),len(s['queue']),flush=True);notice[0]=t
            return actor(s)
        result=C.engine.run(public,model,guarded,physics,case['common_potential_key'],rec);metrics=C.engine.metrics(result,case,physics)
        if learner:equal(learner.snapshot(),before)
        raw=O/(label+'.raw.json.gz');saved(raw,dict(result=result,calls=actor.calls,case=case,source=item,policy=mode,policy_version=VERSION,profile=dict(id='ORIGINAL',slots=3,beta=.25),risk_calibration=pin(O/'RISK_CALIBRATION.json')))
        row=dict(label=label,case=case['id'],condition=case['condition'],kind=kind,policy=mode,status='COMPLETE',n=case['n'],metrics=metrics,raw=pin(raw),bank=item['bank'],network_sha256=state['network_sha256'] if state else None,elapsed_s=time.monotonic()-start)
        selected=[]
        if kind=='TRAIN':
            indices=M.N.select_indices(actor.calls,result['decisions']);selected=[actor.frames[i] for i in indices]
            for f in selected:f['source_raw']=row['raw']
            ff=O/(label+'.FRAMES.pt.gz');pt(ff,dict(frames=selected,selected_indices=indices,split='TRAIN'));row['frames']=pin(ff)
        new(O/(label+'.json'),row);receipt('COMPLETE',label,kind,raw=row['raw']);print('ENV_COMPLETE',label,round(row['elapsed_s'],2),metrics['on_time'],flush=True);del result,actor,learner,bank;gc.collect();return row,selected
    except Exception as e:
        raw=O/(label+'.FAILED.json.gz');saved(raw,dict(case=case,calls=actor.calls if actor else [],last_public_state=last[0],error=str(e),traceback=traceback.format_exc(),partial_not_complete_trace=True));row=dict(label=label,case=case['id'],condition=case['condition'],kind=kind,policy=mode,status='FAIL',raw=pin(raw),error=str(e),automatic_retry=False);new(O/(label+'.json'),row);receipt('FAIL',label,kind,error=str(e));print('ENV_FAIL',label,str(e),flush=True);return row,[]

def fit_stage(initial,frames,stage):
    label='NEURAL_BC_FIT_STAGE'+str(stage);rec=receipt('START',label,'BC_FIT');dp=O/(label+'.DATA.pt.gz');pt(dp,dict(frames=frames,split='TRAIN',EVAL_used=False))
    try:
        state,trace=fit(initial,frames,rec,stage);cp=O/(label+'.pt.gz');tp=O/(label+'.TRACE.pt.gz');pt(cp,state);pt(tp,trace);info={k:v for k,v in trace.items() if k not in ('optimizer','shuffle_rng','group_weights','pairwise_margins')};info.update(checkpoint=pin(cp),trace=pin(tp),dataset=pin(dp));new(O/(label+'.json'),info);receipt('COMPLETE',label,'BC_FIT',checkpoint=info['checkpoint']);print('FIT_COMPLETE',stage,info['logs'][-1],flush=True);return state,info
    except Exception as e:
        new(O/(label+'.FAILURE.json'),dict(error=str(e),traceback=traceback.format_exc()));receipt('FAIL',label,'BC_FIT',error=str(e));return None,None

def run():
    import msvcrt,psutil
    global OPSHA
    op=read(H/'OPERATION.json');verify(op['source_pins']);OPSHA=sha(H/'OPERATION.json');assert not O.exists();lock=(A/'runtime/a24_local_worker.lock').open('r+b');locked=False;wait=time.monotonic();notice=0
    while True:
        procs=[p.info for p in psutil.process_iter(['pid','name']) if (p.info['name'] or '').lower() in ('python.exe','python3.exe')];ram=psutil.virtual_memory().available;disk=shutil.disk_usage(R).free
        eligible=len(procs)<=3 and ram>=1024**3 and disk>=8*1024**3;reason='resource limits'
        if eligible:
            try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
            except OSError:reason='shared byte lock held by another worker'
        if locked:break
        if time.monotonic()-notice>=30:print('RESOURCE_WAIT',dict(reason=reason,PIDs=[p['pid'] for p in procs],RAM=ram,disk=disk),flush=True);notice=time.monotonic()
        assert time.monotonic()-wait<3600,'Resource wait cap';time.sleep(5)
    start=time.monotonic();rows=[];fits=[]
    try:
        O.mkdir();new(O/'START.json',dict(utc=stamp(),operation_sha256=OPSHA,HEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),uncommitted=True,python=sys.executable,processes=procs));inputs=read(H/'INPUTS.json');initial=loadpt(CHECKPOINT);risk=calibrate(inputs);frames=relabel(inputs,risk)
        stage1,info=fit_stage(initial,frames,1);fits.append(info)
        for item in inputs['training']:
            if stage1 is None:receipt('SKIP',item['case']['id']+'__TRAIN_NEURAL_RISK','TRAIN',reason='Fit1 failed');continue
            row,f=episode(item,stage1,'TRAIN','TRAIN_NEURAL_RISK',risk,start);rows.append(row);frames.extend(f)
        final=None
        if stage1 is not None and len(rows)==6 and all(r['status']=='COMPLETE' for r in rows):final,info=fit_stage(stage1,frames,2);fits.append(info)
        else:receipt('SKIP','NEURAL_BC_FIT_STAGE2','BC_FIT',reason='Prior fit/TRAIN failed')
        frames.clear();gc.collect()
        for item in inputs['evaluation']:
            for mode,state in (('TEACHER_RISK',None),('BC_NEURAL_URGENT',final)):
                if mode=='BC_NEURAL_URGENT' and final is None:receipt('SKIP',item['case']['id']+'__'+mode,'EVAL',reason='No final fit');continue
                row,_=episode(item,state,'EVAL',mode,risk,start);rows.append(row)
        verify(op['source_pins']);equal(loadpt(CHECKPOINT),initial)
        for f in fits:
            if f:verify([f['checkpoint'],f['trace']])
        if final:equal(loadpt(R/fits[-1]['checkpoint']['path']),final)
        records=[json.loads(x) for x in (O/'receipts.jsonl').read_text().splitlines()];starts=sum(r['event']=='START' for r in records);assert starts<=17
        new(O/'RESULT.json',dict(status='BATCH_TERMINAL',rows=rows,fits=fits,calibration=pin(O/'RISK_CALIBRATION.json'),science_START=starts,new_TRAIN_residual_calibration=1,new_TRAIN=6,new_BC_fit=sum(f is not None for f in fits),new_EVAL=sum(r['kind']=='EVAL' and r['event']=='START' for r in records),elapsed_s=time.monotonic()-start,new_PPO=0,new_measurement=0,new_physical_fit=0,old_results_rerun=0,adopted=False));print('BATCH_TERMINAL',starts,'units',flush=True)
    except BaseException as e:
        if O.exists():new(O/'BATCH_FAILURE.json',dict(error=str(e),traceback=traceback.format_exc(),automatic_retry=False))
        raise
    finally:
        if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()

if __name__=='__main__':
    if sys.argv[1:]==['--prepare']:prepare()
    elif sys.argv[1:]==['--run']:run()
    else:raise SystemExit('Explicit --prepare / --run')
