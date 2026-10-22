"""Bounded ORIGINAL A24 BC recovery. Direct Python process; no worker wrapper."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import copy,gc,gzip,hashlib,json,math,shutil,subprocess,sys,time,traceback,datetime
from pathlib import Path
H=Path(__file__).resolve().parent;A=H.parents[1];R=A.parent;O=A/'results/A24_BC_RECOVERY_20261021_01'
sys.path.insert(0,str(H.parent))
from a24_idle_wait_repair_20261019 import load_components
C=load_components()
from a24_atc_bc_20261019.learner import Learner,digest
from a24_atc_bc_20261019.candidates import compatible_targets
from common_transfer import B,read,saved,loadpt,pt,np,torch,equal
sys.path.insert(0,str(H))
from learner_recovery import recover
from a24_bc_600_20261019 import study as old
sha,pin,new,stamp,verify=old.sha,old.pin,old.new,old.stamp,old.verify
PACK=A/'experiments/a24_atc_bc_20261019';CHECKPOINT=A/'results/A24_ATC_BC600_20261019_01/BC.FINAL.pt.gz'
VERSION='A24_BC_RECOVERY_V1';SEED=20261021

def hvalue(x):return int(hashlib.sha256(x.encode()).hexdigest(),16)

def label(s,bank,actions,case,index):
    i=min((k for k in range(len(actions)) if bank['mask'][k]),key=lambda k:(bank['scores'][k],k))
    target=np.zeros(36,bool);target[:len(actions)]=compatible_targets(s,actions,i);target &= bank['mask']
    a=actions[i];group=a['kind'] if a['kind']!='DISPATCH' else next(q for q in s['queue'] if q['request_id']==a['request_id'])['task']+'_'+a['route']
    return dict(x=bank['x'].copy(),mask=bank['mask'].copy(),scores=bank['scores'].copy(),index=i,teacher_mask=target,group=group,split='TRAIN',source_case=case,source_decision_index=index,public_state_sha256=B.L.digest(s),time_ns=s['now_ns'],filter_applied=True)

class Nominal:
    def __init__(self,values):self.values=values
    def vector(self,q,route,s):return list(self.values[q['request_id']+'|'+route])

class Collector(C.Policy):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.labels=[]
    def encode(self,s):
        bank,actions=super().encode(s);self.labels.append(label(s,bank,actions,self.case['id'],len(self.labels)));return bank,actions

def physics():
    return C.Physics(read(A/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'),B.Config(**read(A/'experiments/a24_parallel_20261018/OPERATION.json')['physics']),'ORIGINAL',read(old.PORT/'SHAPE.json'))

def make_train(base,bank,prototype,load,pattern,duration,T,index):
    c=copy.deepcopy(base);scale=load/base['condition']['rate_multiplier'];period=base['condition']['supply_s']/scale
    c['id']=f'BCR_TRAIN_R{round(load*1000)}_T{duration}_P{pattern}_S{SEED}';rows=[]
    for k in range(math.ceil(duration/period)+1):
        for q in bank['jobs']:
            jitter=(hvalue(c['id']+'|'+str(k)+'|'+q['request_id'])%30000001)-15000000
            arrival=max(35_000_000_000,35_000_000_000+round((q['scheduled_arrival_ns']-35_000_000_000)/scale+k*period*1e9)+jitter)
            if arrival>=round((35+duration)*1e9):continue
            rows.append((arrival,k,q))
    rows.sort(key=lambda x:(x[0],x[1],x[2]['ordinal']));public=copy.deepcopy(prototype);public['requests']=[];newbank=dict(jobs=[],nominal_vectors={})
    protos={task:next(q for q in prototype['requests'] if q['task']==task) for task in ('C','D')};mapping={};spec=[]
    for ordinal,(arrival,k,q) in enumerate(rows):
        rid='bcr-train-'+str(index)+'-'+str(ordinal).zfill(5);ttl=q['deadline_ns']-q['scheduled_arrival_ns'];entry=q['queue_entry_ns']-q['scheduled_arrival_ns'];v=copy.deepcopy(q)
        v.update(request_id=rid,ordinal=ordinal,scheduled_arrival_ns=arrival,queue_entry_ns=arrival+entry,deadline_ns=arrival+ttl);newbank['jobs'].append(v)
        for route in ('CPU','GPU'):newbank['nominal_vectors'][rid+'|'+route]=bank['nominal_vectors'][q['request_id']+'|'+route]
        public['requests'].append(dict(protos[q['task']],request_id=rid,ordinal=ordinal,priority=q['priority'],scheduled_arrival_ns=arrival,deadline_ns=arrival+ttl))
        spec.append(dict(ordinal=ordinal,profile=q['task']+'_M128',priority=q['priority'],arrival_s=arrival/1e9,deadline_s=(arrival+ttl)/1e9));mapping[rid]=dict(source_case=base['id'],source_request_id=q['request_id'],cycle=k)
    c.update(n=len(rows),temperature_c=T,input=dict(base['input'],requests=spec),supply_stop_s=35+duration,service_stop_s=35+duration+600,drain_stop_s=35+duration+630,observation_end_s=35+duration+780,work_window=[35,35+duration+600],common_potential_key=[VERSION,'TRAIN',index,SEED])
    c['condition']={**base['condition'],'role':'TRAIN','rate_multiplier':load,'supply_s':duration,'n':len(rows),'pattern_index':pattern,'seed':SEED,'phase':'deterministic_15ms_jitter','initial_temperature_assumption_C':T}
    public.update(initial_ap_c=T,initial_context_status='VIRTUAL_TRAIN_INITIAL_TEMPERATURE',observations=[],request_id_mapping=mapping,service_stop_ns=round(c['service_stop_s']*1e9),drain_stop_ns=round(c['drain_stop_s']*1e9),observation_end_ns=round(c['observation_end_s']*1e9),public_scenario_sha256=B.L.digest(c['input']))
    public['public_initial_context_sha256']=B.L.digest(dict(T=T,z=0,source='declared TRAIN assumption'))
    return c,public,newbank

def choose_frames(frames,cap=1024):
    ranked=sorted(frames,key=lambda f:hvalue(str(SEED)+'|'+f['source_case']+'|'+str(f['source_decision_index'])))
    chosen={}
    for f in ranked:
        if f['group'] not in chosen:chosen[f['group']]=f
    ids={(f['source_case'],f['source_decision_index']) for f in chosen.values()}
    selected=list(chosen.values())
    for f in ranked:
        key=(f['source_case'],f['source_decision_index'])
        if len(selected)>=cap:break
        if key not in ids:selected.append(f);ids.add(key)
    return sorted(selected,key=lambda f:(f['source_case'],f['source_decision_index']))

def selfcheck():
    import ast
    for p in H.glob('*.py'):ast.parse(p.read_text(encoding='utf8'))
    subprocess.check_call(['node','--check',str(H/'audit.cjs')])
    ds=read(PACK/'DATASET.json');design=read(old.PORT/'INPUTS.json');prototype=read(old.P/'D040_T600_P0_S160.PUBLIC.json')['public'];checks=0
    for load,duration,T in ((.4,120,26),(.8,240,42),(1.2,240,42)):
        for pattern in (0,1):
            base=next(c for c in design['training'] if c['condition']['pattern_index']==pattern and c['condition']['rate_multiplier']==(.4 if load==.4 else .55));source=read(old.S/(base['id']+'.BANK.json.gz'));c,p,b=make_train(base,source,prototype,load,pattern,duration,T,pattern)
            assert p['initial_ap_c']==T and len(p['requests'])==len(b['jobs'])==c['n'] and all(q['scheduled_arrival_ns']<c['supply_stop_s']*1e9 for q in p['requests']);checks+=1
            bm=B.BankModel(b['jobs'],{q['request_id']:p for q in p['requests']})
            for q,j in zip(p['requests'],b['jobs']):
                bm.request_context(p,q);assert q['task']==j['task'] and q['deadline_ns']==j['deadline_ns'];checks+=1
    data=loadpt(R/ds['dataset']['path']);initial=loadpt(CHECKPOINT);learner=Learner(state=initial);assert digest(learner.net)==initial['network_sha256'];checks+=1
    part=data['frames'][:8];x=torch.from_numpy(np.stack([f['x'] for f in part]));mask=torch.from_numpy(np.stack([f['mask'] for f in part]));target=torch.from_numpy(np.stack([f['teacher_mask'] for f in part]))
    logits=learner.net(x,mask)[0]/.35;formula=logits.logsumexp(-1)-logits.masked_fill(~target,-1e9).logsumexp(-1);prob=logits.softmax(-1).masked_fill(~target,0).sum(-1);assert torch.allclose(formula,-prob.log(),atol=2e-6);formula.mean().backward();assert all(torch.isfinite(p.grad).all() for p in learner.actor_parameters if p.grad is not None);checks+=2
    f=[dict(source_case='T',source_decision_index=i,group='rare' if i==0 else 'common') for i in range(30)];assert choose_frames(f,4)==choose_frames(list(reversed(f)),4);assert {v['group'] for v in choose_frames(f,4)}=={'rare','common'};checks+=2
    new(H/'SELF_CHECK.json',dict(status='PASS',checks=checks,new_environment=0,new_BC_fit=0,new_optimizer_step=0,source_shapes_and_public_bindings=True,warm_start_exact=True,compatible_loss_identity_and_finite_gradient=True));print('SELF_CHECK_PASS',checks,flush=True)

def prepare():
    assert not (H/'OPERATION.json').exists() and not O.exists() and read(H/'SELF_CHECK.json')['status']=='PASS';(H/'banks').mkdir()
    ds=read(PACK/'DATASET.json');design=read(old.PORT/'INPUTS.json');proto_ref=old.P/'D040_T600_P0_S160.PUBLIC.json';prototype=read(proto_ref)['public'];train=[]
    for load,duration,T in ((.4,120,26),(.8,240,42),(1.2,240,42)):
        for pattern in (0,1):
            base=next(c for c in design['training'] if c['condition']['pattern_index']==pattern and c['condition']['rate_multiplier']==(.4 if load==.4 else .55));bankfile=old.S/(base['id']+'.BANK.json.gz');c,p,b=make_train(base,read(bankfile),prototype,load,pattern,duration,T,len(train))
            bp=H/'banks'/(c['id']+'.BANK.json.gz');pp=H/'banks'/(c['id']+'.PUBLIC.json');saved(bp,b);new(pp,dict(public=p));train.append(dict(case=c,bank=pin(bp),public=pin(pp),source_split='TRAIN',source_bank=pin(bankfile)))
    pressure=read(A/'results/A24_QUEUE_PRESSURE_20261020_01/RESULT.json')['rows'];dynamic=read(A/'results/A24_DYNAMIC_ROUTE600_20261020_01/RESULT.json')['rows'];idle=read(A/'results/A24_IDLE_WAIT600_20261019_01/RESULT.json')['rows'];evals=[];comparators=[]
    for row in [*idle,*[r for r in pressure if r['policy']=='IDLE_BC']]:
        raw=read(R/row['raw']['path']);case=raw['case'];public=old.P/(case['id']+'.PUBLIC.json') if case['condition']['rate_multiplier']==.4 else A/'experiments/a24_queue_pressure_20261020/banks'/(case['id']+'.PUBLIC.json')
        evals.append(dict(case=case,bank=row['bank'],public=pin(public)));comparators.append({**row,'policy':'BC_OLD','reused':True})
    comparators += [{**r,'reused':True} for r in dynamic]+[{**r,'reused':True} for r in pressure if r['policy']!='IDLE_BC']
    assert len(comparators)==24 and len(evals)==6
    new(H/'INPUTS.json',dict(training=train,evaluation=evals,comparators=comparators,TRAIN_source_cases=ds['train_case_ids'],EVAL_labels_used=False,prototype_public_metadata_only=pin(proto_ref)))
    checks=0
    for item in train+evals:
        b=read(R/item['bank']['path']);p=read(R/item['public']['path'])['public'];assert len(b['jobs'])==len(p['requests'])==item['case']['n'];checks+=1
        contexts={q['request_id']:p for q in p['requests']};model=B.BankModel(b['jobs'],contexts)
        for q,j in zip(p['requests'],b['jobs']):
            assert q['request_id']==j['request_id'] and q['scheduled_arrival_ns']==j['scheduled_arrival_ns'] and q['deadline_ns']==j['deadline_ns'] and j['queue_entry_ns']>=j['scheduled_arrival_ns'];model.request_context(p,q);checks+=1
    assert not ({x['case']['id'] for x in train}&{x['case']['id'] for x in evals})
    # Non-optimizing contract: selection is deterministic, capped, and preserves rare groups.
    fixture=[dict(source_case='S',source_decision_index=i,group='rare' if i==0 else 'common') for i in range(30)]
    assert choose_frames(fixture,4)==choose_frames(list(reversed(fixture)),4) and {f['group'] for f in choose_frames(fixture,4)}=={'rare','common'};checks+=2
    new(H/'READINESS.json',dict(status='PASS',checks=checks,TRAIN_cases=6,EVAL_cases=6,comparators=24,new_environment=0,new_BC_fit=0))
    inherited=read(PACK/'OPERATION.json')['pins'];paths=[H/'INPUTS.json',H/'READINESS.json',H/'SELF_CHECK.json',CHECKPOINT,A/'results/A24_ATC_BC600_20261019_01/RESULT.json',A/'results/A24_ATC_BC600_20261019_01/BC_TRAINING.json',A/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json',A/'experiments/a24_parallel_20261018/OPERATION.json',old.PORT/'SHAPE.json',proto_ref]
    paths += [p for p in H.iterdir() if p.is_file() and p.suffix in ('.py','.md','.cjs')]
    paths += list((H.parent/'a24_idle_wait_repair_20261019').glob('*.py'))
    paths += [R/p['path'] for p in ds['source']]+[R/ds['dataset']['path']]
    paths += [R/p['path'] for x in train+evals for p in (x['bank'],x['public'])]+[R/x['raw']['path'] for x in comparators]
    pins={p['path']:p for p in inherited}
    for p in paths:pins[pin(p)['path']]=pin(p)
    for item in train:pins[item['source_bank']['path']]=item['source_bank']
    new(H/'OPERATION.json',dict(schema=VERSION,utc=stamp(),authorization=dict(user_text='그럼 일단 BC보완해서 한번 다시 비교해봐',authorized=True,scope='Original A24 BC recovery and comparison'),seed=SEED,maximum_epochs=256,planned_TRAIN=6,planned_BC_fit=1,planned_EVAL=12,max_scientific_units=19,previous_local_derived_cap=137867,derived_local_cap=137886,not_global_census=True,wall_cap_s=7200,episode_wall_cap_s=900,automatic_retry=False,checkpoint=pin(CHECKPOINT),pins=list(pins.values())))
    print('REGISTERED',dict(checks=checks,TRAIN=[(x['case']['id'],x['case']['n']) for x in train],units=19),flush=True)

def receipt(event,label,kind,**extra):
    r=dict(event=event,label=label,kind=kind,utc=stamp(),durable_START_consumed=True,start_id=hashlib.sha256((OPSHA+'|'+label).encode()).hexdigest(),**extra)
    with (O/'receipts.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(r)+'\n');f.flush();os.fsync(f.fileno())
    return r

def run_episode(item,policy,state,start):
    case=item['case'];kind='TRAIN' if policy=='BC_BEHAVIOR' else 'EVAL';name=case['id']+'__'+policy;rec=receipt('START',name,kind);t=time.monotonic();actor=None;last=[None];print('ENV_START',name,case['n'],flush=True)
    try:
        p=read(R/item['public']['path'])['public'];bank=read(R/item['bank']['path']);ph=physics();model=B.BankModel(bank['jobs'],{q['request_id']:p for q in p['requests']});nom=Nominal(bank['nominal_vectors']);learner=Learner(state=state) if state else None;before=learner.snapshot() if learner else None
        actor=(Collector if kind=='TRAIN' else C.Policy)(nom,ph,case,'TEACHER' if policy=='TEACHER' else 'BC',learner,False);notice=[t]
        def guarded(s):
            last[0]=s
            if time.monotonic()-t>900 or time.monotonic()-start>7200:raise ValueError('Finite wall cap')
            if len(actor.calls)>max(1024,20*case['n']):raise ValueError('Finite policy call cap')
            if shutil.disk_usage(R).free<4*1024**3:raise ValueError('Disk guard')
            if time.monotonic()-notice[0]>30:print('ENV_PROGRESS',name,len(actor.calls),round(s['now_ns']/1e9-35,2),len(s['queue']),flush=True);notice[0]=time.monotonic()
            return actor(s)
        result=C.engine.run(p,model,guarded,ph,case['common_potential_key'],rec);metrics=C.engine.metrics(result,case,ph)
        raw=O/(name+'.raw.json.gz');saved(raw,dict(result=result,calls=actor.calls,case=case,profile=dict(id='ORIGINAL',slots=3,beta=.25),policy_version=VERSION,source=item))
        if learner:equal(learner.snapshot(),before)
        row=dict(label=name,case=case['id'],condition=case['condition'],kind=kind,policy=policy,status='COMPLETE',n=case['n'],metrics=metrics,raw=pin(raw),bank=item['bank'],network_sha256=state['network_sha256'] if state else None,elapsed_s=time.monotonic()-t)
        if kind=='TRAIN':
            labels=O/(name+'.LABELS.pt.gz');pt(labels,dict(frames=actor.labels,source_split='TRAIN',case=case['id']));row['labels']=pin(labels);row['frames']=len(actor.labels)
        new(O/(name+'.json'),row);receipt('COMPLETE',name,kind,raw=row['raw']);print('ENV_COMPLETE',name,round(row['elapsed_s'],2),flush=True)
        del result,actor,learner,bank;gc.collect();return row
    except Exception as e:
        raw=O/(name+'.FAILED.json.gz');saved(raw,dict(case=case,calls=actor.calls if actor else [],last_public_state=last[0],error=str(e),traceback=traceback.format_exc(),partial_not_complete_trace=True))
        row=dict(label=name,case=case['id'],condition=case['condition'],kind=kind,policy=policy,status='FAIL',error=str(e),raw=pin(raw),automatic_retry=False);new(O/(name+'.json'),row);receipt('FAIL',name,kind,error=str(e));print('ENV_FAIL',name,str(e),flush=True);return row

def original_labels():
    data=read(PACK/'DATASET.json');source=loadpt(R/data['dataset']['path']);oldframes={(f['case'],f['source_decision_index']):f for f in source['frames']};frames=[];changes=dict(mask=0,target=0,representative=0)
    for item in source['source']:
        raw=read(R/item['source_raw']['path']);bank=read(R/item['nominal_bank']['path']);actor=C.Policy(Nominal(bank['nominal_vectors']),physics(),raw['case'],'TEACHER')
        for i,d in enumerate(raw['result']['decisions']):
            s=d['public_state'];b,a=actor.encode(s);f=label(s,b,a,raw['case']['id'],i);previous=oldframes[(raw['case']['id'],i)];assert f['public_state_sha256']==previous['public_state_sha256']
            changes['mask']+=int(not np.array_equal(f['mask'],previous['mask']));changes['target']+=int(not np.array_equal(f['teacher_mask'],previous['teacher_mask']));changes['representative']+=int(f['index']!=previous['index']);frames.append(f)
    assert len(frames)==1320;pt(O/'ORIGINAL_RELABELLED.pt.gz',dict(frames=frames,changes=changes,new_environment=0));print('ORIGINAL_RELABELLED',changes,flush=True);return frames

def run():
    import msvcrt,psutil
    global OPSHA
    op=read(H/'OPERATION.json');verify(op['pins']);OPSHA=sha(H/'OPERATION.json');assert not O.exists();lock=(A/'runtime/a24_local_worker.lock').open('r+b');locked=False;waiting=time.monotonic();notice=0
    while True:
        processes=[p.info for p in psutil.process_iter(['pid','name']) if (p.info['name'] or '').lower() in ('python.exe','python3.exe')];memory=psutil.virtual_memory().available;disk=shutil.disk_usage(R).free
        if len(processes)<=3 and memory>=1024**3 and disk>=8*1024**3:
            try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
            except OSError:pass
        if locked:break
        if time.monotonic()-notice>30:print('RESOURCE_WAIT',dict(lock_available=locked,python_entries=len(processes),PIDs=[p['pid'] for p in processes],available_RAM=memory,free_disk=disk),flush=True);notice=time.monotonic()
        assert time.monotonic()-waiting<3600,'Finite resource wait';time.sleep(5)
    rows=[];start=time.monotonic()
    try:
        O.mkdir();new(O/'START.json',dict(utc=stamp(),operation_sha256=OPSHA,python=sys.executable,HEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),working_tree_uncommitted=True,processes=processes));inputs=read(H/'INPUTS.json');initial=loadpt(CHECKPOINT);frames=original_labels()
        for item in inputs['training']:
            row=run_episode(item,'BC_BEHAVIOR',initial,start);rows.append(row)
            if row['status']=='COMPLETE':frames+=choose_frames(loadpt(R/row['labels']['path'])['frames'])
        fitted=None;fitinfo=None
        if all(r['status']=='COMPLETE' for r in rows):
            assert len(frames)<=7464 and all(f['source_case'] in set(read(PACK/'DATASET.json')['train_case_ids'])|{x['case']['id'] for x in inputs['training']} for f in frames)
            pt(O/'TRAIN_FRAMES.pt.gz',dict(frames=frames,source_split='TRAIN',EVAL_labels_used=False));rec=receipt('START','BC_RECOVERY_FIT','BC_FIT')
            try:
                fitted,trace=recover(initial,frames,fit_receipt=rec);pt(O/'BC.RECOVERED.pt.gz',fitted);pt(O/'BC.TRAINING_TRACE.pt.gz',trace)
                fitinfo={k:v for k,v in trace.items() if k not in ('optimizer','group_weights','shuffle_rng')};fitinfo.update(checkpoint=pin(O/'BC.RECOVERED.pt.gz'),dataset=pin(O/'TRAIN_FRAMES.pt.gz'));new(O/'BC_TRAINING.json',fitinfo);receipt('COMPLETE','BC_RECOVERY_FIT','BC_FIT',checkpoint=fitinfo['checkpoint']);print('FIT_COMPLETE',trace['logs'][-1],flush=True)
            except Exception as e:
                new(O/'FIT_FAILURE.json',dict(error=str(e),traceback=traceback.format_exc()));receipt('FAIL','BC_RECOVERY_FIT','BC_FIT',error=str(e));fitted=None
        else:receipt('SKIP','BC_RECOVERY_FIT','BC_FIT',reason='TRAIN failure; no retry')
        del frames;gc.collect()
        for item in inputs['evaluation']:
            for policy in ('TEACHER','BC_RECOVERED'):
                if policy=='BC_RECOVERED' and fitted is None or time.monotonic()-start>7200:
                    row=dict(label=item['case']['id']+'__'+policy,case=item['case']['id'],condition=item['case']['condition'],kind='EVAL',policy=policy,status='SKIP',reason='Fit unavailable or batch cap');rows.append(row);receipt('SKIP',row['label'],'EVAL',reason=row['reason']);continue
                rows.append(run_episode(item,policy,fitted if policy=='BC_RECOVERED' else None,start))
        verify(op['pins']);assert sha(CHECKPOINT)==op['checkpoint']['sha256']
        if fitted:equal(loadpt(O/'BC.RECOVERED.pt.gz'),fitted)
        receipts=[json.loads(x) for x in (O/'receipts.jsonl').read_text().splitlines()];starts=[x for x in receipts if x['event']=='START'];assert len(starts)<=19
        new(O/'RESULT.json',dict(status='BATCH_TERMINAL',rows=rows,fit=fitinfo,elapsed_s=time.monotonic()-start,science_START=len(starts),new_TRAIN=sum(x['kind']=='TRAIN' for x in starts),new_BC_fit=sum(x['kind']=='BC_FIT' for x in starts),new_EVAL=sum(x['kind']=='EVAL' for x in starts),old_results_rerun=0,new_PPO=0,new_measurement=0,new_physical_fit=0,adopted=False))
        print('BATCH_TERMINAL',len(rows),'rows',len(starts),'START',flush=True)
    except BaseException as e:
        if O.exists():new(O/'BATCH_FAILURE.json',dict(error=str(e),traceback=traceback.format_exc()));raise
    finally:
        if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()

if __name__=='__main__':
    if sys.argv[1:]==['--check']:selfcheck()
    elif sys.argv[1:]==['--prepare']:prepare()
    elif sys.argv[1:]==['--run']:run()
    else:raise SystemExit('Explicit --prepare or --run required')
