"""Bounded TRAIN-only paired neural repair and four frozen evaluations."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import ast,copy,gc,hashlib,json,shutil,subprocess,sys,time,traceback
from pathlib import Path
H=Path(__file__).resolve().parent;A=H.parents[1];R=A.parent;O=A/'results/A24_NN_MARGIN_EXACT_20261021_01'
sys.path.insert(0,str(H.parent))
from a24_fair_nn_bc_20261021 import study as N
from a24_nn_margin_exact_20261021.policy import Policy,relative_cost,VERSION
from a24_nn_margin_exact_20261021.train import fit,losses
read,new,saved,pin,sha,stamp,verify=N.read,N.new,N.saved,N.pin,N.sha,N.stamp,N.verify
B,C,P,np,torch=N.B,N.C,N.P,N.np,N.torch
loadpt,pt,equal,Learner=N.loadpt,N.pt,N.equal,N.Learner
PREVIOUS_RESULT=read(N.O/'RESULT.json');CHECKPOINT=R/PREVIOUS_RESULT['fits'][-1]['checkpoint']['path']

def normalize_frame(f):
    g=dict(f);g['absolute_x']=np.array(f.get('absolute_x',f['x']),copy=True);g['x']=g['absolute_x'].copy();g['x'][:,28],norm=relative_cost(f['scores'],f['mask']);g['cost_normalization']=norm
    g['cost_compatible_mask']=np.array(f.get('cost_compatible_mask',f['teacher_mask']),copy=True);g['teacher_mask']=np.zeros(36,bool);g['teacher_mask'][f['index']]=True
    assert g['cost_compatible_mask'][f['index']] and g['mask'][f['index']];return g

def prepare():
    assert not O.exists() and not (H/'OPERATION.json').exists()
    for p in H.glob('*.py'):ast.parse(p.read_text(encoding='utf8'))
    prior=read(N.H/'OPERATION.json');verify(prior['source_pins']);inputs=read(N.H/'INPUTS.json');previous=read(N.O/'RESULT.json')
    cases=dict(training=inputs['training'],evaluation=inputs['evaluation'],base_TRAIN=previous['fits'][-1]['dataset'],comparators=inputs['comparators']+[{**r,'policy':'BC_NEURAL_PREVIOUS','reused':True} for r in previous['rows'] if r['kind']=='EVAL'],EVAL_used_for_training=False)
    assert len(cases['comparators'])==32
    frames=loadpt(R/cases['base_TRAIN']['path'])['frames'];checks=0
    for f in frames:
        assert f['split']=='TRAIN' and f['source_case'] not in {c['case']['id'] for c in inputs['evaluation']};g=normalize_frame(f)
        assert np.array_equal(np.delete(g['x'],28,1),np.delete(f['x'],28,1)) and np.isfinite(g['x']).all();checks+=2
        mask=f['mask'];scores=f['scores'];z=g['x'][:,28];assert np.all(np.diff(z[np.flatnonzero(mask)[np.argsort(scores[mask],kind='stable')]])>=0);checks+=1
    fixture=np.array([1.,1.1,1.2]+[0.]*33);mask=np.array([True]*3+[False]*33);z,_=relative_cost(fixture,mask);shift,_=relative_cost(fixture+3,mask);assert np.allclose(z,shift,atol=1e-6);checks+=1
    logits=torch.tensor([[0.,1.,-1.]],requires_grad=True);target=torch.tensor([[True,False,False]]);m=torch.ones_like(target);ce,rank=losses(logits,target,m);assert torch.allclose(ce,torch.nn.functional.cross_entropy(logits,torch.tensor([0]),reduction='none')) and float(rank.detach()[0])==1.5;(ce+.25*rank).mean().backward();assert torch.isfinite(logits.grad).all() and logits.grad[0,0]<0 and logits.grad[0,1]>0;checks+=2
    state=loadpt(CHECKPOINT);learner=Learner(state=state);equal(learner.snapshot(),state);checks+=1
    for c in cases['training']+cases['evaluation']:verify([c['bank'],c['public']]);checks+=2
    new(H/'INPUTS.json',cases);new(H/'READINESS.json',dict(status='PASS',checks=checks,base_TRAIN_frames=len(frames),network_structure_unchanged=True,only_input_slot28_changed=True,no_teacher_target_in_input=True,TRAIN_only=True,new_environment=0,new_fit=0))
    pins={p['path']:p for p in prior['source_pins']}
    paths=[p for p in H.iterdir() if p.is_file()]+[CHECKPOINT,N.H/'OPERATION.json',N.O/'RESULT.json',N.O/'FINAL_PROOF.json',N.O/'FINAL_RECHECK.json',R/cases['base_TRAIN']['path']]
    paths += [R/r['raw']['path'] for r in cases['comparators']]+[R/r['source_raw']['path'] for r in frames]
    predecessor=H.parent/'a24_nn_margin_repair_20261021';paths += [predecessor/'OPERATION.json',predecessor/'SUPERSEDED_BEFORE_START.json']
    for p in dict.fromkeys(paths):
        item=pin(p);pins[item['path']]=item
    new(H/'OPERATION.json',dict(schema=VERSION,utc=stamp(),authorization=dict(authorized=True,user_text='기존 BC 신경망의 남은 모방 오차랑 저부하 성능 저하 원인 찾아서 보완하고, 같은 S26식 입력으로 다시 비교해봐'),source_pins=list(pins.values()),checkpoint=pin(CHECKPOINT),planned_TRAIN=6,planned_BC_fit=2,planned_EVAL=4,max_scientific_units=12,previous_local_derived=137933,derived_local_cap=137945,not_global_census=True,epochs_each_fit=256,paired_seed=20265021,automatic_retry=False,chosen_policy_precommitted='RELATIVE_COST_EXACT_ACTION_NEURAL',teacher_training_target='single exact teacher action including deterministic ties',predecessor_START=0,predecessor_cancelled=pin(predecessor/'SUPERSEDED_BEFORE_START.json'),EVAL_model_selection=False,new_PPO=0,new_measurement=0,new_physical_fit=0,adopted=False))
    print('PREPARED_MARGIN_REPAIR',checks,'checks, 12 units',flush=True)

def receipt(event,label,kind,**extra):
    r=dict(event=event,label=label,kind=kind,utc=stamp(),durable_START_consumed=True,start_id=hashlib.sha256((OPSHA+'|'+label).encode()).hexdigest(),**extra)
    with (O/'receipts.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(r)+'\n');f.flush();os.fsync(f.fileno())
    return r

def episode(item,state,kind,batch):
    case=copy.deepcopy(item['case']);mode='TRAIN_PREVIOUS_NEURAL' if kind=='TRAIN' else 'BC_NEURAL_REPAIRED';label=case['id']+'__'+mode;rec=receipt('START',label,kind);start=time.monotonic();actor=None;last=[None];print('ENV_START',label,case['n'],flush=True)
    try:
        public=read(R/item['public']['path'])['public'];bank=read(R/item['bank']['path']);physics=P.physics();model=B.BankModel(bank['jobs'],{q['request_id']:public for q in public['requests']});learner=Learner(state=state);before=learner.snapshot();actor=Policy(P.Nominal(bank['nominal_vectors']),physics,case,learner,kind=='TRAIN',relative=kind=='EVAL');notice=[start]
        def guarded(s):
            last[0]=s;t=time.monotonic();assert t-start<1200 and t-batch<10800,'Finite wall cap';assert len(actor.calls)<=max(1024,20*case['n']),'Action cap'
            if t-notice[0]>=30:
                import psutil
                assert shutil.disk_usage(R).free>=4*1024**3 and psutil.virtual_memory().available>=1024**3,'Resource guard';print('ENV_PROGRESS',label,len(actor.calls),round(s['now_ns']/1e9-35,2),len(s['queue']),flush=True);notice[0]=t
            return actor(s)
        result=C.engine.run(public,model,guarded,physics,case['common_potential_key'],rec);metrics=C.engine.metrics(result,case,physics);equal(learner.snapshot(),before)
        raw=O/(label+'.raw.json.gz');saved(raw,dict(result=result,calls=actor.calls,case=case,source=item,policy=mode,policy_version=VERSION,profile=dict(id='ORIGINAL',slots=3,beta=.25)))
        row=dict(label=label,case=case['id'],condition=case['condition'],kind=kind,policy=mode,status='COMPLETE',n=case['n'],metrics=metrics,raw=pin(raw),bank=item['bank'],network_sha256=state['network_sha256'],elapsed_s=time.monotonic()-start)
        chosen=[]
        if kind=='TRAIN':
            indices=N.select_indices(actor.calls,result['decisions']);chosen=[normalize_frame(actor.frames[i]) for i in indices]
            for f in chosen:f['source_raw']=row['raw']
            ff=O/(label+'.FRAMES.pt.gz');pt(ff,dict(frames=chosen,selected_indices=indices,split='TRAIN'));row['frames']=pin(ff)
        new(O/(label+'.json'),row);receipt('COMPLETE',label,kind,raw=row['raw']);print('ENV_COMPLETE',label,round(row['elapsed_s'],2),metrics['on_time'],flush=True)
        del result,actor,learner,bank;gc.collect();return row,chosen
    except Exception as e:
        raw=O/(label+'.FAILED.json.gz');saved(raw,dict(case=case,calls=actor.calls if actor else [],last_public_state=last[0],error=str(e),traceback=traceback.format_exc(),partial_not_complete_trace=True));row=dict(label=label,case=case['id'],condition=case['condition'],kind=kind,policy=mode,status='FAIL',raw=pin(raw),error=str(e),automatic_retry=False);new(O/(label+'.json'),row);receipt('FAIL',label,kind,error=str(e));print('ENV_FAIL',label,str(e),flush=True);return row,[]

def fit_one(initial,frames,relative):
    label='RELATIVE_NEURAL_FIT' if relative else 'ABSOLUTE_NEURAL_CONTROL_FIT';rec=receipt('START',label,'BC_FIT')
    try:
        state,trace=fit(initial,frames,rec,relative);cp=O/(label+'.pt.gz');tp=O/(label+'.TRACE.pt.gz');pt(cp,state);pt(tp,trace)
        info={k:v for k,v in trace.items() if k not in ('optimizer','shuffle_rng','group_weights')};info.update(checkpoint=pin(cp),trace=pin(tp),dataset=pin(O/'TRAIN_DATASET.pt.gz'));new(O/(label+'.json'),info);receipt('COMPLETE',label,'BC_FIT',checkpoint=info['checkpoint']);print('FIT_COMPLETE',label,info['logs'][-1],flush=True);return state,info
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
        if time.monotonic()-notice>=30:print('RESOURCE_WAIT',dict(PIDs=[p['pid'] for p in procs],RAM=ram,disk=disk),flush=True);notice=time.monotonic()
        assert time.monotonic()-wait<3600,'Resource wait cap';time.sleep(5)
    start=time.monotonic();rows=[];fits=[]
    try:
        O.mkdir();new(O/'START.json',dict(utc=stamp(),operation_sha256=OPSHA,HEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),uncommitted=True,python=sys.executable,processes=procs));inputs=read(H/'INPUTS.json');initial=loadpt(CHECKPOINT);frames=[normalize_frame(f) for f in loadpt(R/inputs['base_TRAIN']['path'])['frames']]
        for item in inputs['training']:
            row,f=episode(item,initial,'TRAIN',start);rows.append(row);frames.extend(f)
        final=None
        if all(r['status']=='COMPLETE' for r in rows):
            pt(O/'TRAIN_DATASET.pt.gz',dict(frames=frames,split='TRAIN',EVAL_used=False))
            _,info=fit_one(initial,frames,False);fits.append(info)
            final,info=fit_one(initial,frames,True);fits.append(info)
        else:
            for name in ('ABSOLUTE_NEURAL_CONTROL_FIT','RELATIVE_NEURAL_FIT'):receipt('SKIP',name,'BC_FIT',reason='TRAIN failed')
        frames.clear();gc.collect()
        for item in inputs['evaluation']:
            if final is None:
                row=dict(label=item['case']['id']+'__BC_NEURAL_REPAIRED',case=item['case']['id'],condition=item['case']['condition'],kind='EVAL',policy='BC_NEURAL_REPAIRED',status='SKIP',reason='No final fit');rows.append(row);receipt('SKIP',row['label'],'EVAL',reason=row['reason']);continue
            row,_=episode(item,final,'EVAL',start);rows.append(row)
        verify(op['source_pins']);equal(loadpt(CHECKPOINT),initial)
        for info in fits:
            if info:verify([info['checkpoint'],info['trace']])
        if final:equal(loadpt(R/fits[-1]['checkpoint']['path']),final)
        records=[json.loads(x) for x in (O/'receipts.jsonl').read_text().splitlines()];starts=sum(x['event']=='START' for x in records);assert starts<=12
        new(O/'RESULT.json',dict(status='BATCH_TERMINAL',rows=rows,fits=fits,science_START=starts,new_TRAIN=6,new_BC_fit=sum(x is not None for x in fits),new_EVAL=sum(x['kind']=='EVAL' and x['event']=='START' for x in records),elapsed_s=time.monotonic()-start,new_PPO=0,new_measurement=0,new_physical_fit=0,old_results_rerun=0,adopted=False));print('BATCH_TERMINAL',starts,'units',flush=True)
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
