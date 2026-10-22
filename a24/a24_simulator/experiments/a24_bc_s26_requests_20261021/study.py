"""Frozen recovered A24 BC; exact common EVAL requests; legacy CPU3 engine."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key] = '1'
import copy,gc,hashlib,json,shutil,subprocess,sys,time,traceback
from pathlib import Path
H=Path(__file__).resolve().parent;A=H.parents[1];R=A.parent
O=A/'results/A24_BC_S26_REQUESTS_20261021_01'
sys.path.insert(0,str(H.parent))
from a24_bc_recovery_20261021 import study as P
from a24_dynamic_route_600_20261020.dynamic_policy import DynamicPolicy
read,saved,new,stamp,pin,sha,verify=P.read,P.saved,P.new,P.stamp,P.pin,P.sha,P.verify
loadpt,Learner,equal,C,B=P.loadpt,P.Learner,P.equal,P.C,P.B
CHECKPOINT=A/'results/A24_BC_RECOVERY_20261021_01/BC.RECOVERED.pt.gz'
NETWORK='cec00807e6729c4f59bbb74723749eeb2db722786c55a7d754b1253477eb6ad7'
MODES=('FIFO_DYN','EDF_DYN','RR_DYN','TEACHER','BC_RECOVERED')
VERSION='A24_RECOVERED_BC_S26_REQUESTS_V1'

def convert(item,bank,prototype,nominal):
    case=dict(id='S26REQ_'+item['id'],n=item['n'],temperature_c=26,
        condition=dict(rate_multiplier=item['rate'],requests_per_second=item['rate'],load_kind='REQUESTS_PER_SECOND',
            supply_s=600,pattern=item['pattern'],pattern_index=int(item['pattern']=='burst8'),seed=item['seed'],role='EVAL'),
        supply_stop_s=635,service_stop_s=815,drain_stop_s=815,observation_end_s=895,work_window=[35,815],
        common_potential_key=[VERSION,item['id']],source_common_case=item['id'])
    public=copy.deepcopy(prototype);public['requests']=[];jobs=[];vectors={};spec=[]
    protos={task:next(q for q in prototype['requests'] if q['task']==task) for task in ('C','D')}
    for q in bank['requests']:
        arrival=round(q['arrival_s']*1e9);entry=round(q['ready_s']*1e9);deadline=round(q['deadline_s']*1e9)
        v=dict(request_id=q['id'],ordinal=q['ordinal'],task=q['task'],priority=q['priority'],scheduled_arrival_ns=arrival,
               queue_entry_ns=entry,deadline_ns=deadline,
               admission=dict(scheduled_to_actual_ns=entry-arrival,actual_to_queue_ns=0,
                              adapter='TOTAL_READY_DELAY_WITH_ZERO_INTERNAL_QUEUE_COMPONENT',source=q['source_refs']['ADMISSION']),
               routes={route:dict(stages_ns=[round(x*1e9) for x in q['private_work'][route]],sample_id=q['source_refs'][route]['source'],
                                  source=q['source_refs'][route],latent_work_coordinate='OBSERVED_SERIAL_NS_OR_DECLARED_DG_TRANSFER') for route in ('CPU','GPU')})
        jobs.append(v)
        public['requests'].append({**protos[q['task']],**{k:v[k] for k in ('request_id','ordinal','task','priority','scheduled_arrival_ns','deadline_ns')}})
        for route in ('CPU','GPU'):vectors[q['id']+'|'+route]=nominal[q['task']+'_'+route]
        spec.append(dict(ordinal=q['ordinal'],profile=q['task']+'_M128',priority=q['priority'],arrival_s=arrival/1e9,deadline_s=deadline/1e9))
    case['input']=dict(requests=spec)
    public.update(initial_ap_c=26,initial_context_status='PRESERVED_A24_VIRTUAL_INITIAL26',observations=[],
                  service_stop_ns=815_000_000_000,drain_stop_ns=815_000_000_000,observation_end_ns=895_000_000_000,
                  public_scenario_sha256=B.L.digest(case['input']),public_initial_context_sha256=B.L.digest(dict(T=26,z=0,source='PRESERVED_ORIGINAL_A24')))
    return case,public,dict(jobs=jobs,nominal_vectors=vectors)

def prepare():
    assert not O.exists() and not (H/'OPERATION.json').exists()
    parent=read(P.H/'OPERATION.json');verify(parent['pins'])
    source=H.parent/'common_train_20261021/INPUTS.json';profiles=H.parent/'a24_s26_common_20261020/PROFILES.json'
    inputs=read(source);nominal=read(profiles)['A24']['nominal'];olditem=read(P.H/'INPUTS.json')['evaluation'][0]
    prototype=read(R/olditem['public']['path'])['public'];oldbank=read(R/olditem['bank']['path']);checks=0
    for task in ('C','D'):
        for route in ('CPU','GPU'):
            vals={tuple(oldbank['nominal_vectors'][q['request_id']+'|'+route]) for q in oldbank['jobs'] if q['task']==task}
            assert vals=={tuple(nominal[task+'_'+route])};checks+=1
    state=loadpt(CHECKPOINT);learner=Learner(state=state);assert state['network_sha256']==NETWORK and P.digest(learner.net)==NETWORK
    assert tuple(learner.net.encode[0].weight.shape)==(48,50);checks+=2
    (H/'banks').mkdir();cases=[];source_pins=[]
    for item in (v for v in inputs['cases'] if v['split']=='EVAL'):
        verify([item['banks']['A24'],item['banks']['S26']]);bank=read(R/item['banks']['A24']['path']);other=read(R/item['banks']['S26']['path'])
        assert bank['planned']==other['planned'] and bank['planned']==[{k:q[k] for k in ('id','ordinal','task','priority','arrival_s','deadline_s')} for q in bank['requests']]
        case,public,b=convert(item,bank,prototype,nominal);model=B.BankModel(b['jobs'],{q['request_id']:public for q in public['requests']})
        assert len(b['jobs'])==item['n']==len(public['requests'])==600*item['rate'];checks+=2
        for q,j,raw in zip(public['requests'],b['jobs'],bank['requests']):
            assert q['request_id']==raw['id'] and j['queue_entry_ns']==round(raw['ready_s']*1e9)>=q['scheduled_arrival_ns']
            assert q['deadline_ns']==round(raw['deadline_s']*1e9) and q['scheduled_arrival_ns']==round(raw['arrival_s']*1e9)
            assert all(j['routes'][route]['stages_ns']==[round(x*1e9) for x in raw['private_work'][route]] for route in ('CPU','GPU'))
            expected_ttl={('C','U'):.8,('C','N'):2,('D','U'):1.2,('D','N'):3}[q['task'],q['priority']]
            assert abs((q['deadline_ns']-q['scheduled_arrival_ns'])/1e9-expected_ttl)<1e-9
            model.request_context(public,q);checks+=4
        bp=H/'banks'/(case['id']+'.BANK.json.gz');pp=H/'banks'/(case['id']+'.PUBLIC.json');saved(bp,b);new(pp,dict(public=public))
        cases.append(dict(case=case,bank=pin(bp),public=pin(pp),source_common_bank=item['banks']['A24']))
        source_pins.extend(item['banks'].values())
    assert len(cases)==4 and sum(x['case']['n'] for x in cases)==6000
    new(H/'INPUTS.json',dict(cases=cases,policies=MODES,new_TRAIN=0,new_BC_fit=0,source_input=pin(source)))
    new(H/'READINESS.json',dict(status='PASS',checks=checks,source_requests=6000,source_banks_exact=True,nominal_unchanged=True,
        recovered_network=NETWORK,ABI='50 features /36 slots',scientific_START=0,new_fit=0))
    paths=[p for p in H.iterdir() if p.is_file() and p.name!='OPERATION.json']+list((H/'banks').iterdir())
    paths += [source,profiles,CHECKPOINT,P.O/'FINAL_PROOF.json',P.O/'TRAIN_DIAGNOSTICS.json',R/olditem['public']['path'],R/olditem['bank']['path'],H.parent/'a24_dynamic_route_600_20261020/dynamic_policy.py',H.parent/'a24_rr_600_20261020/rr_policy.py']
    pins={x['path']:x for x in parent['pins']}
    for p in paths:pins[pin(p)['path']]=pin(p)
    for p in source_pins:pins[p['path']]=p
    new(H/'OPERATION.json',dict(schema=VERSION,utc=stamp(),authorization=dict(authorized=True,user_text='방금 보완한 A24 BC도 S26식 입력요청 평가방식으로 돌려서 FIFO, EDF, RR, 교사규칙이랑 비교해봐 그리고 결과가 잘 안나온다면 왜 그런지 원인분석도 해'),
        planned_EVAL=20,max_scientific_units=20,new_TRAIN=0,new_fit=0,previous_local_derived=137886,derived_local_cap=137906,not_global_census=True,
        policies=MODES,checkpoint=pin(CHECKPOINT),network_sha256=NETWORK,source_pins=list(pins.values()),wall_cap_s=10800,episode_wall_cap_s=1200,
        original_capacity=dict(CPU=3,GPU=1),common_owner1_used=False,automatic_retry=False,adopted=False))
    print('PREPARED',checks,'checks','20 EVAL','0 fit',flush=True)

def receipt(event,label,**extra):
    rec=dict(event=event,label=label,kind='EVAL',utc=stamp(),durable_START_consumed=True,start_id=hashlib.sha256((OPSHA+'|'+label).encode()).hexdigest(),**extra)
    with (O/'receipts.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(rec)+'\n');f.flush();os.fsync(f.fileno())
    return rec

def episode(item,mode,state,batch):
    case=item['case'];name=case['id']+'__'+mode;rec=receipt('START',name);start=time.monotonic();actor=None;last=[None];print('ENV_START',name,case['n'],flush=True)
    try:
        public=read(R/item['public']['path'])['public'];bank=read(R/item['bank']['path']);ph=P.physics();nom=P.Nominal(bank['nominal_vectors']);model=B.BankModel(bank['jobs'],{q['request_id']:public for q in public['requests']})
        learner=Learner(state=state) if mode=='BC_RECOVERED' else None;before=learner.snapshot() if learner else None
        actor=DynamicPolicy(nom,ph,mode) if mode.endswith('_DYN') else C.Policy(nom,ph,case,'TEACHER' if mode=='TEACHER' else 'BC',learner,False)
        notice=[start];calltimes=[]
        def guarded(s):
            last[0]=s;t=time.monotonic()
            if t-start>1200 or t-batch>10800:raise ValueError('Finite wall cap')
            if len(actor.calls)>max(1024,20*case['n']):raise ValueError('Finite action cap')
            if t-notice[0]>30:
                import psutil
                if shutil.disk_usage(R).free<4*1024**3 or psutil.virtual_memory().available<1024**3:raise ValueError('Memory/disk guard')
                print('ENV_PROGRESS',name,len(actor.calls),round(s['now_ns']/1e9-35,2),len(s['queue']),flush=True);notice[0]=t
            action=actor(s);calltimes.append(time.monotonic()-t);return action
        result=C.engine.run(public,model,guarded,ph,case['common_potential_key'],rec);metrics=C.engine.metrics(result,case,ph)
        if learner:equal(before,learner.snapshot())
        raw=O/(name+'.raw.json.gz');saved(raw,dict(result=result,calls=actor.calls,case=case,source=item,policy=mode,
            profile=dict(id='ORIGINAL',slots=3,beta=.25),policy_version=VERSION,actor_call_wall_s=calltimes,controller_cost_in_simulation=False))
        row=dict(label=name,case=case['id'],condition=case['condition'],policy=mode,kind='EVAL',status='COMPLETE',n=case['n'],metrics=metrics,
            raw=pin(raw),bank=item['bank'],network_sha256=NETWORK if learner else None,elapsed_s=time.monotonic()-start)
        new(O/(name+'.json'),row);receipt('COMPLETE',name,raw=row['raw']);print('ENV_COMPLETE',name,round(row['elapsed_s'],2),metrics['on_time'],metrics['response_missing'],flush=True)
        del actor,result,learner,bank;gc.collect();return row
    except Exception as e:
        raw=O/(name+'.FAILED.json.gz');saved(raw,dict(case=case,calls=actor.calls if actor else [],last_public_state=last[0],partial_not_complete_trace=True,error=str(e),traceback=traceback.format_exc()))
        row=dict(label=name,case=case['id'],condition=case['condition'],policy=mode,kind='EVAL',status='FAIL',raw=pin(raw),error=str(e),automatic_retry=False)
        new(O/(name+'.json'),row);receipt('FAIL',name,raw=row['raw'],error=str(e));print('ENV_FAIL',name,str(e),flush=True);return row

def run():
    import msvcrt,psutil
    global OPSHA
    op=read(H/'OPERATION.json');verify(op['source_pins']);OPSHA=sha(H/'OPERATION.json');assert not O.exists()
    lock=(A/'runtime/a24_local_worker.lock').open('r+b');locked=False;wait=time.monotonic();notice=0
    while True:
        procs=[p.info for p in psutil.process_iter(['pid','name']) if (p.info['name'] or '').lower() in ('python.exe','python3.exe')]
        ram=psutil.virtual_memory().available;disk=shutil.disk_usage(R).free
        if len(procs)<=3 and ram>=1024**3 and disk>=8*1024**3:
            try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
            except OSError:pass
        if locked:break
        if time.monotonic()-notice>30:print('RESOURCE_WAIT',dict(lock=False,python_entries=len(procs),PIDs=[p['pid'] for p in procs],RAM=ram,disk=disk),flush=True);notice=time.monotonic()
        assert time.monotonic()-wait<3600,'Finite resource wait';time.sleep(5)
    rows=[];start=time.monotonic()
    try:
        O.mkdir();new(O/'START.json',dict(utc=stamp(),operation_sha256=OPSHA,HEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),working_tree_uncommitted=True,python=sys.executable,processes=procs))
        state=loadpt(CHECKPOINT);assert state['network_sha256']==NETWORK
        for item in read(H/'INPUTS.json')['cases']:
            for mode in MODES:
                if time.monotonic()-start>10800:
                    row=dict(label=item['case']['id']+'__'+mode,case=item['case']['id'],condition=item['case']['condition'],policy=mode,kind='EVAL',status='SKIP',reason='Batch finite cap')
                    receipt('SKIP',row['label'],reason=row['reason']);rows.append(row)
                else:rows.append(episode(item,mode,state,start))
        verify(op['source_pins']);equal(loadpt(CHECKPOINT),state)
        receipts=[json.loads(x) for x in (O/'receipts.jsonl').read_text().splitlines()];starts=sum(x['event']=='START' for x in receipts);assert starts<=20
        new(O/'RESULT.json',dict(status='BATCH_TERMINAL',rows=rows,science_START=starts,elapsed_s=time.monotonic()-start,checkpoint=op['checkpoint'],network_sha256=NETWORK,new_TRAIN=0,new_fit=0,new_PPO=0,new_measurement=0,new_physical_fit=0,old_results_rerun=0,adopted=False))
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
    else:raise SystemExit('Explicit --prepare or --run required')
