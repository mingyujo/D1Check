"""Twelve bounded scientific STARTs: two neural fits, six TRAIN rollouts, four EVAL."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import ast,collections,copy,gc,hashlib,json,shutil,subprocess,sys,time,traceback
from pathlib import Path
H=Path(__file__).resolve().parent;A=H.parents[1];R=A.parent;O=A/'results/A24_FAIR_NN_BC_20261021_01'
sys.path.insert(0,str(H.parent))
from a24_service_bc_repair_20261021 import study as F
from a24_fair_nn_bc_20261021.policy import Policy,features50,labels,VERSION
from a24_fair_nn_bc_20261021.train import fit,accuracy
from a24_atc_bc_20261019.policy import Policy as Original
S=F.S;read,new,saved,pin,sha,stamp,verify=F.read,F.new,F.saved,F.pin,F.sha,F.stamp,F.verify
B,C,P,np,torch=S.B,S.C,S.P,S.P.np,S.P.torch
loadpt,pt,equal,Learner=S.loadpt,S.P.pt,S.equal,S.Learner
CHECKPOINT=S.CHECKPOINT

def select_indices(calls,states,cap=1024):
    buckets=collections.defaultdict(list)
    for i,(c,dec) in enumerate(zip(calls,states)):
        s=dec['public_state'];a=c['action'];q=next((q for q in s['queue'] if q['request_id']==a.get('request_id')),None)
        group=a['kind'] if q is None else q['task']+'_'+q['priority']+'_'+a['route']
        buckets[group].append(i)
    for key in buckets:buckets[key].sort(key=lambda i:hashlib.sha256((str(20261021)+'|'+key+'|'+str(i)).encode()).hexdigest())
    chosen=[]
    for k in range(max(map(len,buckets.values()))):
        for key in sorted(buckets):
            if k<len(buckets[key]) and len(chosen)<cap:chosen.append(buckets[key][k])
    return sorted(chosen)

def prepare():
    assert not O.exists() and not (H/'OPERATION.json').exists()
    for p in H.glob('*.py'):ast.parse(p.read_text(encoding='utf8'))
    prior=read(F.H/'OPERATION.json');verify(prior['source_pins']);finputs=read(F.H/'INPUTS.json');fresult=read(F.O/'RESULT.json')
    original_training=[r for r in read(P.O/'RESULT.json')['rows'] if r['kind']=='TRAIN'];teacher_training=[r for r in fresult['rows'] if r['kind']=='TRAIN']
    comparators=finputs['comparators']+[{**r,'policy':'COST_IMITATION' if r['policy']=='BC_FAIR' else r['policy'],'reused':True} for r in fresult['rows'] if r['kind']=='EVAL']
    assert len(original_training)==len(teacher_training)==6 and len(comparators)==28
    inputs=dict(training=finputs['training'],evaluation=finputs['evaluation'],saved_teacher_TRAIN=teacher_training,saved_old_neural_TRAIN=original_training,comparators=comparators,EVAL_used_for_training=False)
    checks=0
    for item in inputs['training']+inputs['evaluation']:verify([item['public'],item['bank']]);checks+=2
    # Prove 49 unchanged neural inputs and the sole teacher-score slot update.
    for row in teacher_training[:2]:
        d=read(R/row['raw']['path']);bank=read(R/row['bank']['path']);nom=P.Nominal(bank['nominal_vectors']);physics=P.physics();old=Original(nom,physics,d['case'],'TEACHER')
        for dec,c in list(zip(d['result']['decisions'],d['calls']))[:4]:
            s=dec['public_state'];b=dict(c);b['teacher_scores']=np.asarray(c['teacher_scores']);x=features50(s,b,nom,physics,d['case']);oldb,acts=old.encode(s)
            assert acts==c['actions'] and np.array_equal(np.delete(x,28,1),np.delete(oldb['x'],28,1));checks+=2
            b['x']=x;b['mask']=np.asarray(c['mask']);frame=labels(s,b,row['case'],0);assert frame['teacher_mask'][c['teacher_index']];checks+=1
    state=loadpt(CHECKPOINT);learner=Learner(state=state);equal(learner.snapshot(),state);checks+=1
    x=torch.zeros((2,36,50));mask=torch.zeros((2,36),dtype=torch.bool);mask[:,:3]=True;target=torch.zeros_like(mask);target[:,0]=True
    logits=learner.net(x,mask)[0]/.35;ce=logits.logsumexp(-1)-logits.masked_fill(~target,-1e9).logsumexp(-1);assert torch.allclose(ce,-logits.softmax(-1)[:,0].log(),atol=2e-6);ce.mean().backward();assert all(torch.isfinite(p.grad).all() for p in learner.actor_parameters if p.grad is not None);checks+=2
    new(H/'INPUTS.json',inputs);new(H/'READINESS.json',dict(status='PASS',checks=checks,network_architecture_unchanged=True,unchanged_input_slots=49,updated_slot=28,updated_slot_meaning='Current fair teacher public cost / 10, same soft compression',optimizer_steps=0,new_environment=0,new_scientific_fit=0))
    pins={p['path']:p for p in prior['source_pins']}
    paths=[p for p in H.iterdir() if p.is_file()]+[CHECKPOINT,F.H/'OPERATION.json',F.O/'RESULT.json',F.O/'FINAL_PROOF.json',F.O/'FINAL_RECHECK.json']
    paths += [R/r['raw']['path'] for r in original_training+teacher_training+comparators]+[R/r['labels']['path'] for r in original_training]
    paths += [R/'a24_simulator/experiments/a24_atc_bc_20261019/learner.py',R/'a24_simulator/experiments/a24_atc_bc_20261019/policy.py']
    for p in paths:pins[pin(p)['path']]=pin(p)
    new(H/'OPERATION.json',dict(schema=VERSION,utc=stamp(),authorization=dict(user_text='비용회귀 말고 기존 BC 신경망을 보완해서 새 교사규칙으로 학습시키고 같은 S26식 입력 조건으로 다시 비교해봐',authorized=True),source_pins=list(pins.values()),checkpoint=pin(CHECKPOINT),planned_TRAIN=6,planned_BC_fit=2,planned_EVAL=4,max_scientific_units=12,previous_local_derived=137921,derived_local_cap=137933,not_global_census=True,maximum_epochs_per_fit=256,seed=20261021,automatic_retry=False,new_PPO=0,new_measurement=0,new_physical_fit=0,adopted=False))
    print('PREPARED_NEURAL',checks,'checks; 12 scientific units',flush=True)

def receipt(event,label,kind,**extra):
    r=dict(event=event,label=label,kind=kind,utc=stamp(),durable_START_consumed=True,start_id=hashlib.sha256((OPSHA+'|'+label).encode()).hexdigest(),**extra)
    with (O/'receipts.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(r)+'\n');f.flush();os.fsync(f.fileno())
    return r

def relabel_saved(inputs):
    frames=[];binding=[]
    for row in inputs['saved_teacher_TRAIN']+inputs['saved_old_neural_TRAIN']:
        verify([row['raw']]);d=read(R/row['raw']['path']);bank=read(R/row['bank']['path']);actor=Policy(P.Nominal(bank['nominal_vectors']),P.physics(),d['case'])
        indices=list(range(len(d['calls']))) if row['policy']=='TRAIN_TEACHER' else select_indices(d['calls'],d['result']['decisions'])
        for i in indices:
            s=d['result']['decisions'][i]['public_state']
            if row['policy']=='TRAIN_TEACHER':
                c=d['calls'][i];b={**c,'mask':np.asarray(c['mask'],bool),'teacher_scores':np.asarray(c['teacher_scores'],np.float64)};b['x']=features50(s,b,actor.nominal,actor.physics,actor.case)
            else:b=actor.encode(s)
            frame=labels(s,b,row['case'],i,B.L.digest(s));frame['source_raw']=row['raw'];frames.append(frame)
        binding.append(dict(source=row['raw'],case=row['case'],indices=indices,selected=len(indices)));print('RELABEL_SAVED_TRAIN',row['case'],len(indices),flush=True)
    pt(O/'BASE_TRAIN.pt.gz',dict(frames=frames,bindings=binding,split='TRAIN',EVAL_used=False));new(O/'BASE_TRAIN.json',dict(frames=len(frames),sources=binding,dataset=pin(O/'BASE_TRAIN.pt.gz'),new_environment=0,new_fit=0));return frames

def episode(item,state,kind,batch):
    case=copy.deepcopy(item['case']);mode='TRAIN_NEURAL_STAGE1' if kind=='TRAIN' else 'BC_NEURAL_FAIR';label=case['id']+'__'+mode;rec=receipt('START',label,kind);start=time.monotonic();actor=None;last=[None];print('ENV_START',label,case['n'],flush=True)
    try:
        public=read(R/item['public']['path'])['public'];bank=read(R/item['bank']['path']);physics=P.physics();model=B.BankModel(bank['jobs'],{q['request_id']:public for q in public['requests']});learner=Learner(state=state);before=learner.snapshot();actor=Policy(P.Nominal(bank['nominal_vectors']),physics,case,learner,kind=='TRAIN');notice=[start]
        def guarded(s):
            last[0]=s;t=time.monotonic()
            assert t-start<=1200 and t-batch<=10800,'Finite wall cap';assert len(actor.calls)<=max(1024,20*case['n']),'Finite action cap'
            if t-notice[0]>=30:
                import psutil
                assert shutil.disk_usage(R).free>=4*1024**3 and psutil.virtual_memory().available>=1024**3,'Resource guard'
                print('ENV_PROGRESS',label,len(actor.calls),round(s['now_ns']/1e9-35,2),len(s['queue']),flush=True);notice[0]=t
            return actor(s)
        result=C.engine.run(public,model,guarded,physics,case['common_potential_key'],rec);metrics=C.engine.metrics(result,case,physics);equal(learner.snapshot(),before)
        raw=O/(label+'.raw.json.gz');saved(raw,dict(result=result,calls=actor.calls,case=case,source=item,policy=mode,policy_version=VERSION,profile=dict(id='ORIGINAL',slots=3,beta=.25)))
        row=dict(label=label,case=case['id'],condition=case['condition'],kind=kind,policy=mode,status='COMPLETE',n=case['n'],metrics=metrics,raw=pin(raw),bank=item['bank'],network_sha256=state['network_sha256'],elapsed_s=time.monotonic()-start)
        chosen=[]
        if kind=='TRAIN':
            selected=select_indices(actor.calls,result['decisions']);chosen=[actor.frames[i] for i in selected]
            for f in chosen:f['source_raw']=row['raw']
            ff=O/(label+'.FRAMES.pt.gz');pt(ff,dict(frames=chosen,selected_indices=selected,all_calls=len(actor.calls),split='TRAIN'));row['frames']=pin(ff)
        new(O/(label+'.json'),row);receipt('COMPLETE',label,kind,raw=row['raw']);print('ENV_COMPLETE',label,round(row['elapsed_s'],2),metrics['on_time'],flush=True)
        del result,actor,learner,bank;gc.collect();return row,chosen
    except Exception as e:
        raw=O/(label+'.FAILED.json.gz');saved(raw,dict(case=case,calls=actor.calls if actor else [],last_public_state=last[0],error=str(e),traceback=traceback.format_exc(),partial_not_complete_trace=True));row=dict(label=label,case=case['id'],condition=case['condition'],kind=kind,policy=mode,status='FAIL',raw=pin(raw),error=str(e),automatic_retry=False);new(O/(label+'.json'),row);receipt('FAIL',label,kind,error=str(e));print('ENV_FAIL',label,str(e),flush=True);return row,[]

def fit_stage(initial,frames,stage):
    label='NEURAL_BC_FIT_STAGE'+str(stage);rec=receipt('START',label,'BC_FIT');pt(O/(label+'.DATA.pt.gz'),dict(frames=frames,split='TRAIN'))
    try:
        state,trace=fit(initial,frames,rec,stage);cp=O/(label+'.pt.gz');tp=O/(label+'.TRACE.pt.gz');pt(cp,state);pt(tp,trace)
        summary={k:v for k,v in trace.items() if k not in ('optimizer','shuffle_rng','group_weights')};summary.update(checkpoint=pin(cp),trace=pin(tp),dataset=pin(O/(label+'.DATA.pt.gz')));new(O/(label+'.json'),summary);receipt('COMPLETE',label,'BC_FIT',checkpoint=summary['checkpoint']);print('FIT_COMPLETE',stage,summary['logs'][-1],flush=True);return state,summary
    except Exception as e:
        new(O/(label+'.FAILURE.json'),dict(error=str(e),traceback=traceback.format_exc()));receipt('FAIL',label,'BC_FIT',error=str(e));print('FIT_FAIL',label,str(e),flush=True);return None,None

def run():
    import msvcrt,psutil
    global OPSHA
    op=read(H/'OPERATION.json');verify(op['source_pins']);OPSHA=sha(H/'OPERATION.json');assert not O.exists();lock=(A/'runtime/a24_local_worker.lock').open('r+b');locked=False;wait=time.monotonic();notice=0
    while True:
        procs=[p.info for p in psutil.process_iter(['pid','name']) if (p.info['name'] or '').lower() in ('python.exe','python3.exe')];ram=psutil.virtual_memory().available;disk=shutil.disk_usage(R).free
        if len(procs)<=3 and ram>=1024**3 and disk>=8*1024**3:
            try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
            except OSError:pass
        if locked:break
        if time.monotonic()-notice>=30:print('RESOURCE_WAIT',dict(python_entries=len(procs),PIDs=[p['pid'] for p in procs],RAM=ram,disk=disk),flush=True);notice=time.monotonic()
        assert time.monotonic()-wait<3600,'Finite resource wait';time.sleep(5)
    rows=[];fits=[];start=time.monotonic()
    try:
        O.mkdir();new(O/'START.json',dict(utc=stamp(),operation_sha256=OPSHA,HEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),uncommitted=True,python=sys.executable,processes=procs));inputs=read(H/'INPUTS.json');initial=loadpt(CHECKPOINT);frames=relabel_saved(inputs)
        stage1,info=fit_stage(initial,frames,1);fits.append(info);correction=[]
        for item in inputs['training']:
            if stage1 is None:receipt('SKIP',item['case']['id']+'__TRAIN_NEURAL_STAGE1','TRAIN',reason='Fit1 failed');continue
            row,f=episode(item,stage1,'TRAIN',start);rows.append(row);correction.extend(f)
        final=None
        if stage1 and len(rows)==6 and all(r['status']=='COMPLETE' for r in rows):
            frames+=correction;final,info=fit_stage(stage1,frames,2);fits.append(info)
        else:receipt('SKIP','NEURAL_BC_FIT_STAGE2','BC_FIT',reason='Prior TRAIN/fit failed')
        frames.clear();correction.clear();gc.collect()
        for item in inputs['evaluation']:
            if final is None:
                row=dict(label=item['case']['id']+'__BC_NEURAL_FAIR',case=item['case']['id'],condition=item['case']['condition'],kind='EVAL',policy='BC_NEURAL_FAIR',status='SKIP',reason='Final fit unavailable');rows.append(row);receipt('SKIP',row['label'],'EVAL',reason=row['reason']);continue
            row,_=episode(item,final,'EVAL',start);rows.append(row)
        verify(op['source_pins']);equal(loadpt(CHECKPOINT),initial)
        for info in fits:
            if info:verify([info['checkpoint']])
        if final:equal(loadpt(R/fits[-1]['checkpoint']['path']),final)
        receipts=[json.loads(x) for x in (O/'receipts.jsonl').read_text().splitlines()];starts=sum(x['event']=='START' for x in receipts);assert starts<=12
        new(O/'RESULT.json',dict(status='BATCH_TERMINAL',rows=rows,fits=fits,science_START=starts,new_TRAIN=6,new_BC_fit=sum(x is not None for x in fits),new_EVAL=sum(x['kind']=='EVAL' and x['event']=='START' for x in receipts),elapsed_s=time.monotonic()-start,new_PPO=0,new_measurement=0,new_physical_fit=0,old_results_rerun=0,adopted=False));print('BATCH_TERMINAL',starts,'units',flush=True)
    except BaseException as e:
        if O.exists():new(O/'BATCH_FAILURE.json',dict(error=str(e),traceback=traceback.format_exc(),automatic_retry=False))
        raise
    finally:
        if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()

if __name__=='__main__':
    if sys.argv[1:]==['--prepare']:prepare()
    elif sys.argv[1:]==['--run']:run()
    else:raise SystemExit('Explicit --prepare or --run')
