"""Registered service-first teacher and six-feature cost imitation; no old reruns."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import ast,copy,gc,hashlib,json,shutil,subprocess,sys,time,traceback
from pathlib import Path
H=Path(__file__).resolve().parent;A=H.parents[1];R=A.parent;O=A/'results/A24_SERVICE_BC_REPAIR_20261021_01'
sys.path.insert(0,str(H.parent))
from a24_bc_s26_requests_20261021 import study as S
from a24_service_bc_repair_20261021.policy import Policy,fit,choose,predict_scores,service_mask,TEACHER_WEIGHTS,TIE_TOL,VERSION
read,saved,new,stamp,pin,sha,verify=S.read,S.saved,S.new,S.stamp,S.pin,S.sha,S.verify
B,C,np=S.B,S.C,S.P.np

def pure_check():
    checks=0
    for p in H.glob('*.py'):ast.parse(p.read_text(encoding='utf8'));checks+=1
    p=R/'a24_simulator/experiments/a24_logic_repair_20261019/forecast.py'
    old=ast.parse(p.read_text(encoding='utf8'));newtree=ast.parse((H/'forecast.py').read_text(encoding='utf8'))
    for tree in (old,newtree):
        fun=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='predict');ret=fun.body[-1]
        ret.value.keywords=[v for v in ret.value.keywords if v.arg not in ('responses_s','finished_ids')]
    assert ast.dump(old,include_attributes=False)==ast.dump(newtree,include_attributes=False);checks+=1
    mask,best,forced=service_mask([True]*3,[dict(late_ALL=1,late_U=1),dict(late_ALL=2,late_U=0),dict(late_ALL=1,late_U=0)],[])
    assert mask.tolist()==[False,False,True] and best==(1,0);checks+=2
    pairs=[dict(late_ALL=0,late_U=0)]*3;mask,_,forced=service_mask([True]*3,pairs,[1]);assert mask.tolist()==[False,True,False] and forced==[1];checks+=2
    mask,_,forced=service_mask([True,False,True],pairs,[1]);assert mask.tolist()==[True,False,True] and not forced;checks+=2
    assert choose(np.array([1.,1.+.5e-8,0.]),[True,True,False])==0;checks+=1
    assert choose(np.array([1.+2e-8,1.,0.]),[True,True,False])==1;checks+=1
    x=np.array([[1.,.2,0.,0.,0.,.1],[1.,.2,.1,.1,0.,.1],[1.,.2,1.,2.,0.,.1]])
    assert (x@TEACHER_WEIGHTS)[0]<(x@TEACHER_WEIGHTS)[1]<(x@TEACHER_WEIGHTS)[2];checks+=1
    new(H/'PURE_CHECK.json',dict(status='PASS',checks=checks,forecast_body_unchanged_except_returned_public_results=True,new_environment=0,new_real_fit=0))
    print('PURE_CHECK_PASS',checks,flush=True)

def prepare():
    assert not O.exists() and not (H/'OPERATION.json').exists();pure_check()
    source=H.parent/'common_train_20261021/INPUTS.json';design=read(source);old=read(S.H/'OPERATION.json');verify(old['source_pins'])
    prototype=read(R/read(S.H/'INPUTS.json')['cases'][0]['public']['path'])['public'];nominal=read(H.parent/'a24_s26_common_20261020/PROFILES.json')['A24']['nominal']
    (H/'banks').mkdir();train=[];checks=0;sourcepins=[]
    for item in (x for x in design['cases'] if x['split']=='TRAIN'):
        bank=read(R/item['banks']['A24']['path']);verify(list(item['banks'].values()));sourcepins+=list(item['banks'].values())
        for T in ([26,42] if item['rate']==4 else [26]):
            case,public,b=S.convert(item,bank,prototype,nominal);case['id']='FAIR_'+item['id']+'_T'+str(T);end=item['drain_stop_s']
            case.update(temperature_c=T,supply_stop_s=item['supply_stop_s'],service_stop_s=end,drain_stop_s=end,observation_end_s=end+80,work_window=[35,end],common_potential_key=[VERSION,case['id']])
            case['condition'].update(role='TRAIN',supply_s=item['supply_s'],pattern_index=int(item['pattern']=='burst'),initial_temperature_assumption_C=T)
            public.update(initial_ap_c=T,initial_context_status='DECLARED_VIRTUAL_TRAIN_TEMPERATURE',service_stop_ns=round(end*1e9),drain_stop_ns=round(end*1e9),observation_end_ns=round((end+80)*1e9),public_initial_context_sha256=B.L.digest(dict(T=T,z=0,source='DECLARED_TRAIN')))
            model=B.BankModel(b['jobs'],{q['request_id']:public for q in public['requests']})
            for q,j,src in zip(public['requests'],b['jobs'],bank['requests']):
                assert q['request_id']==src['id'] and j['queue_entry_ns']==round(src['ready_s']*1e9) and q['deadline_ns']==round(src['deadline_s']*1e9)
                model.request_context(public,q);checks+=2
            bp=H/'banks'/(case['id']+'.BANK.json.gz');pp=H/'banks'/(case['id']+'.PUBLIC.json');saved(bp,b);new(pp,dict(public=public))
            train.append(dict(case=case,bank=pin(bp),public=pin(pp),source_common_bank=item['banks']['A24'],source_split='TRAIN'))
    evaluation=read(S.H/'INPUTS.json')['cases'];comparators=[{**x,'policy':{'TEACHER':'TEACHER_OLD','BC_RECOVERED':'BC_OLD'}.get(x['policy'],x['policy']),'reused':True} for x in read(S.O/'RESULT.json')['rows']]
    assert len(train)==6 and len(evaluation)==4 and len(comparators)==20
    assert not ({x['case']['source_common_case'] for x in train}&{x['case']['source_common_case'] for x in evaluation})
    for item in evaluation:
        verify([item['public'],item['bank']]);b=read(R/item['bank']['path']);p=read(R/item['public']['path'])['public']
        assert len(p['requests'])==len(b['jobs'])==item['case']['n'];checks+=1
    new(H/'INPUTS.json',dict(training=train,evaluation=evaluation,comparators=comparators,EVAL_used_for_training=False))
    new(H/'READINESS.json',dict(status='PASS',checks=checks,TRAIN_cases=6,TRAIN_requests=768,EVAL_cases=4,reused_completed=20,new_scientific_START=0))
    paths=[p for p in H.iterdir() if p.is_file() and p.name!='OPERATION.json']+list((H/'banks').iterdir())
    paths += [source,S.H/'OPERATION.json',S.O/'RESULT.json',S.O/'FINAL_PROOF.json',S.O/'FINAL_RECHECK.json',S.CHECKPOINT,H.parent/'rr_20261017/rr_policy.py']
    paths += [R/x['raw']['path'] for x in comparators]+[R/p['path'] for x in evaluation for p in (x['public'],x['bank'])]
    pins={p['path']:p for p in old['source_pins']}
    for p in paths:pins[pin(p)['path']]=pin(p)
    for p in sourcepins:pins[p['path']]=p
    new(H/'OPERATION.json',dict(schema=VERSION,utc=stamp(),authorization=dict(authorized=True,user_text='일반 요청이 밀리는 문제랑 BC 모방 오차 보완해서 같은 S26식 입력 조건으로 FIFO, EDF, RR, 교사규칙이랑 다시 비교해봐'),
        planned_TRAIN=6,planned_fit=1,planned_EVAL=8,max_scientific_units=15,previous_local_derived=137906,derived_local_cap=137921,not_global_census=True,
        feature_names=['energy_per_request_scaled','mean_heat','mean_relative_tardiness','max_relative_tardiness','unfinished_fraction','mean_relative_response'],
        teacher_weights=TEACHER_WEIGHTS.tolist(),tie_tolerance=TIE_TOL,source_pins=list(pins.values()),wall_cap_s=10800,episode_wall_cap_s=1200,
        original_neural_checkpoint=pin(S.CHECKPOINT),new_PPO=0,new_physical_fit=0,new_measurement=0,automatic_retry=False,adopted=False))
    print('PREPARED_SERVICE_REPAIR',len(train),'TRAIN',8,'EVAL',1,'fit',checks,'checks',flush=True)

def receipt(event,label,kind,**extra):
    rec=dict(event=event,label=label,kind=kind,utc=stamp(),durable_START_consumed=True,start_id=hashlib.sha256((OPSHA+'|'+label).encode()).hexdigest(),**extra)
    with (O/'receipts.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(rec)+'\n');f.flush();os.fsync(f.fileno())
    return rec

def episode(item,mode,model,batch):
    case=copy.deepcopy(item['case']);kind='TRAIN' if mode=='TRAIN_TEACHER' else 'EVAL';name=case['id']+'__'+mode;rec=receipt('START',name,kind);start=time.monotonic();actor=None;last=[None];print('ENV_START',name,case['n'],flush=True)
    try:
        public=read(R/item['public']['path'])['public'];bank=read(R/item['bank']['path']);ph=S.P.physics();nom=S.P.Nominal(bank['nominal_vectors']);adapter=B.BankModel(bank['jobs'],{q['request_id']:public for q in public['requests']})
        before=copy.deepcopy(model);actor=Policy(nom,ph,case,model,kind=='TRAIN');notice=[start]
        def guarded(s):
            last[0]=s;t=time.monotonic()
            if t-start>1200 or t-batch>10800:raise ValueError('Finite wall cap')
            if len(actor.calls)>max(1024,20*case['n']):raise ValueError('Finite action cap')
            if t-notice[0]>30:
                import psutil
                if shutil.disk_usage(R).free<4*1024**3 or psutil.virtual_memory().available<1024**3:raise ValueError('Memory/disk guard')
                print('ENV_PROGRESS',name,len(actor.calls),round(s['now_ns']/1e9-35,2),len(s['queue']),flush=True);notice[0]=t
            return actor(s)
        result=C.engine.run(public,adapter,guarded,ph,case['common_potential_key'],rec);metrics=C.engine.metrics(result,case,ph)
        assert model==before
        raw=O/(name+'.raw.json.gz');saved(raw,dict(result=result,calls=actor.calls,case=case,source=item,policy=mode,policy_version=VERSION,profile=dict(id='ORIGINAL',slots=3,beta=.25)))
        row=dict(label=name,case=case['id'],condition=case['condition'],kind=kind,policy=mode,status='COMPLETE',n=case['n'],metrics=metrics,raw=pin(raw),bank=item['bank'],elapsed_s=time.monotonic()-start)
        frames=actor.frames if kind=='TRAIN' else []
        if frames:
            ff=O/(name+'.FRAMES.pt.gz');S.P.pt(ff,dict(frames=frames,split='TRAIN',source_case=case['id']));row['frames']=pin(ff)
        new(O/(name+'.json'),row);receipt('COMPLETE',name,kind,raw=row['raw']);print('ENV_COMPLETE',name,round(row['elapsed_s'],2),metrics['on_time'],flush=True)
        del result,actor,bank;gc.collect();return row,frames
    except Exception as e:
        raw=O/(name+'.FAILED.json.gz');saved(raw,dict(case=case,calls=actor.calls if actor else [],last_public_state=last[0],partial_not_complete_trace=True,error=str(e),traceback=traceback.format_exc()))
        row=dict(label=name,case=case['id'],condition=case['condition'],kind=kind,policy=mode,status='FAIL',raw=pin(raw),error=str(e),automatic_retry=False)
        new(O/(name+'.json'),row);receipt('FAIL',name,kind,raw=row['raw'],error=str(e));print('ENV_FAIL',name,str(e),flush=True);return row,[]

def run():
    import msvcrt,psutil
    global OPSHA
    op=read(H/'OPERATION.json');verify(op['source_pins']);OPSHA=sha(H/'OPERATION.json');assert not O.exists()
    lock=(A/'runtime/a24_local_worker.lock').open('r+b');locked=False;wait=time.monotonic();notice=0
    while True:
        procs=[p.info for p in psutil.process_iter(['pid','name']) if (p.info['name'] or '').lower() in ('python.exe','python3.exe')];ram=psutil.virtual_memory().available;disk=shutil.disk_usage(R).free
        if len(procs)<=3 and ram>=1024**3 and disk>=8*1024**3:
            try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
            except OSError:pass
        if locked:break
        if time.monotonic()-notice>30:print('RESOURCE_WAIT',dict(lock=False,python_entries=len(procs),PIDs=[p['pid'] for p in procs],RAM=ram,disk=disk),flush=True);notice=time.monotonic()
        assert time.monotonic()-wait<3600,'Finite resource wait';time.sleep(5)
    start=time.monotonic();rows=[];frames=[];model=None;modelpin=None
    try:
        O.mkdir();new(O/'START.json',dict(utc=stamp(),operation_sha256=OPSHA,HEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),working_tree_uncommitted=True,python=sys.executable,processes=procs))
        inputs=read(H/'INPUTS.json')
        for item in inputs['training']:
            row,f=episode(item,'TRAIN_TEACHER',None,start);rows.append(row);frames.extend(f)
        if all(x['status']=='COMPLETE' for x in rows):
            rec=receipt('START','COST_IMITATION_FIT','BC_FIT')
            try:
                assert {f['case'] for f in frames}=={x['case']['id'] for x in inputs['training']} and all(f['split']=='TRAIN' for f in frames)
                model=fit(frames,rec);new(O/'MODEL.json',model);modelpin=pin(O/'MODEL.json');receipt('COMPLETE','COST_IMITATION_FIT','BC_FIT',model=modelpin)
                new(O/'FIT.json',dict(status='COMPLETE',model=modelpin,frames=model['frames'],candidate_targets=model['candidate_targets'],TRAIN_compatible_accuracy=float(model['TRAIN_compatible_accuracy']),TRAIN_RMSE=model['TRAIN_RMSE'],EVAL_used_for_selection=False))
                print('FIT_COMPLETE',model['frames'],model['TRAIN_compatible_accuracy'],model['TRAIN_RMSE'],flush=True)
            except Exception as e:
                model=None;new(O/'FIT_FAILURE.json',dict(error=str(e),traceback=traceback.format_exc()));receipt('FAIL','COST_IMITATION_FIT','BC_FIT',error=str(e));print('FIT_FAIL',str(e),flush=True)
        else:receipt('SKIP','COST_IMITATION_FIT','BC_FIT',reason='TRAIN failure')
        frames.clear();gc.collect()
        for item in inputs['evaluation']:
            for mode in ('TEACHER_FAIR','BC_FAIR'):
                if mode=='BC_FAIR' and model is None or time.monotonic()-start>10800:
                    row=dict(label=item['case']['id']+'__'+mode,case=item['case']['id'],condition=item['case']['condition'],kind='EVAL',policy=mode,status='SKIP',reason='Fit unavailable or finite batch cap');rows.append(row);receipt('SKIP',row['label'],'EVAL',reason=row['reason']);continue
                row,_=episode(item,mode,model if mode=='BC_FAIR' else None,start);rows.append(row)
        verify(op['source_pins'])
        if modelpin:verify([modelpin]);assert read(O/'MODEL.json')==model
        receipts=[json.loads(x) for x in (O/'receipts.jsonl').read_text().splitlines()];starts=sum(x['event']=='START' for x in receipts);assert starts<=15
        new(O/'RESULT.json',dict(status='BATCH_TERMINAL',rows=rows,model=modelpin,science_START=starts,new_TRAIN=6,new_fit=int(modelpin is not None),new_EVAL=sum(x['kind']=='EVAL' and x['event']=='START' for x in receipts),elapsed_s=time.monotonic()-start,new_PPO=0,new_measurement=0,new_physical_fit=0,old_results_rerun=0,adopted=False))
        print('BATCH_TERMINAL',starts,dict((s,sum(x['status']==s for x in rows)) for s in ('COMPLETE','FAIL','SKIP')),flush=True)
    except BaseException as e:
        if O.exists():new(O/'BATCH_FAILURE.json',dict(error=str(e),traceback=traceback.format_exc(),automatic_retry=False))
        raise
    finally:
        if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()

if __name__=='__main__':
    if sys.argv[1:]==['--prepare']:prepare()
    elif sys.argv[1:]==['--run']:run()
    else:raise SystemExit('Explicit --prepare/--run required')
