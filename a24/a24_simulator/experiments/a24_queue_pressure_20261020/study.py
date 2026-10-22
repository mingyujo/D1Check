"""Registered frozen-policy pressure evaluation; no retraining or old reruns."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import copy,gc,json,shutil,subprocess,sys,time,traceback
from pathlib import Path
H=Path(__file__).resolve().parent;A=H.parents[1];R=A.parent
O=A/'results/A24_QUEUE_PRESSURE_20261020_01'
sys.path.insert(0,str(H.parent))
from a24_idle_wait_repair_20261019 import load_components
C=load_components()
from a24_atc_bc_20261019.learner import Learner
from a24_dynamic_route_600_20261020.dynamic_policy import DynamicPolicy
from a24_bc_600_20261019 import study as old
from common_transfer import B,read,saved,loadpt,pt,np,equal
sha,pin,new,stamp,verify=old.sha,old.pin,old.new,old.stamp,old.verify
VERSION='A24_QUEUE_PRESSURE_FIXED_POLICY_V1'
MODES=('FIFO_DYN','EDF_DYN','RR_DYN','IDLE_BC')
CHECKPOINT=A/'results/A24_ATC_BC600_20261019_01/BC.FINAL.pt.gz'

def cases():return read(H/'INPUTS.json')['cases']

def public_and_contexts(case):
    original=next(c for c in old.cases() if c['condition']['pattern_index']==case['condition']['pattern_index'])
    base_public,base_contexts,parent=old.public_and_contexts(original)
    public=read(H/'banks'/(case['id']+'.PUBLIC.json'))['public']
    n=case['source_base_n'];contexts={q['request_id']:copy.deepcopy({k:v for k,v in base_contexts['user-'+str(i%n).zfill(5)].items() if k!='_requests_by_id'}) for i,q in enumerate(public['requests'])}
    lookup={q['request_id']:q for q in public['requests']}
    for context in contexts.values():context['_requests_by_id']=lookup
    return public,contexts,parent

def propose():
    assert not O.exists() and not (H/'PROPOSAL.json').exists()
    parent=read(A/'experiments/a24_dynamic_route_600_20261020/OPERATION.json');verify(parent['pins'])
    assert parent['authorized_total']==137725
    paths=[R/p['path'] for p in parent['pins']]
    for folder in ('A24_DYNAMIC_ROUTE600_20261020_01','A24_IDLE_WAIT600_20261019_01'):
        prior=read(A/'results'/folder/'RESULT.json')
        paths += [R/r['raw']['path'] for r in prior['rows']]
        paths += [A/'results'/folder/n for n in ('RESULT.json','FINAL_HANDOFF_PROOF.json')]
    paths += [A/'experiments/a24_dynamic_route_600_20261020/OPERATION.json',CHECKPOINT]
    paths += [p for p in H.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    git=lambda *a:subprocess.check_output(['git',*a],cwd=R,text=True,encoding='utf-8').strip()
    new(H/'PROPOSAL.json',dict(status='PREPARED',schema=VERSION,code_version=VERSION,utc=stamp(),HEAD=git('rev-parse','HEAD'),branch=git('branch','--show-current'),working_tree=git('status','--short'),planned_START=16,modes=MODES,load_levels=[.8,1.2],supply_s=600,checkpoint=pin(CHECKPOINT),new_training=0,new_fit=0,new_device=0,old_results_rerun=0,budget=dict(previous_closed_total=137725,current_requested_EVAL=16,derived_total=137741,refund=0),pins=[pin(p) for p in sorted(set(paths))]))

def register():
    auth=read(H/'EXECUTION_AUTHORIZATION.json');assert auth['execution_authorized'] and auth['authorized_units']==16 and auth['derived_total']==137741
    op=read(H/'PROPOSAL.json');verify(op['pins']);assert not O.exists()
    op.update(status='AUTHORIZED_REGISTERED',authorization=pin(H/'EXECUTION_AUTHORIZATION.json'),authorized_total=137741,registered_utc=stamp())
    new(H/'OPERATION.json',op)

def run():
    import msvcrt,psutil
    op=read(H/'OPERATION.json');verify(op['pins']);verify([op['authorization']])
    assert op['status']=='AUTHORIZED_REGISTERED' and op['authorized_total']==137741 and not O.exists()
    lock=(A/'runtime/a24_local_worker.lock').open('r+b');locked=False;deadline=time.monotonic()+3600;last_notice=0
    while True:
        if not locked:
            try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
            except OSError:pass
        processes=[p.info for p in psutil.process_iter(['pid','name']) if (p.info['name'] or '').lower() in ('python.exe','python3.exe')]
        memory=psutil.virtual_memory().available;disk=shutil.disk_usage(R).free
        if locked and len(processes)<=3 and memory>=1024**3 and disk>=8*1024**3:break
        if time.monotonic()-last_notice>30:
            print('PRESTART_RESOURCE_WAIT',dict(lock=locked,python_entries=len(processes),memory=memory,disk=disk),flush=True);last_notice=time.monotonic()
        assert time.monotonic()<deadline,'Finite resource wait';time.sleep(5)
    rows=[];active=[None];start=time.monotonic();opsha=sha(H/'OPERATION.json');frames_replayed=0;dynamic_replayed=0
    try:
        O.mkdir();new(O/'START.json',dict(utc=stamp(),operation_sha256=opsha,HEAD=op['HEAD'],processes=processes))
        def receipt(event,label,**extra):
            r=dict(event=event,label=label,kind='EVAL',utc=stamp(),durable_START_consumed=True,start_id=B.L.digest([opsha,label]),**extra)
            with (O/'receipts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(r)+'\n');f.flush();os.fsync(f.fileno())
            active[0]=label if event=='START' else None
            return r
        snap=loadpt(CHECKPOINT)
        for case in cases():
            for mode in MODES:
                assert len(rows)<16 and time.monotonic()-start<10800
                public,contexts,parent=public_and_contexts(case);bankfile=H/'banks'/(case['id']+'.BANK.json.gz');bank=read(bankfile)
                physics=C.Physics(read(A/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'),B.Config(**parent['physics']),'ORIGINAL',read(old.PORT/'SHAPE.json'))
                model=B.BankModel(bank['jobs'],contexts);nominal=B.SavedNominal(public,[dict(nominal_vectors=bank['nominal_vectors'])])
                learner=Learner(state=snap) if mode=='IDLE_BC' else None
                before=learner.snapshot() if learner else None
                actor=C.Policy(nominal,physics,case,'BC',learner,False) if learner else DynamicPolicy(nominal,physics,mode)
                label='ORIGINAL__PRESSURE__'+case['id']+'__'+mode;rec=receipt('START',label);episode=time.monotonic();last=[None];notice=[episode]
                print('PRESSURE_START',len(rows)+1,label,'n',case['n'],flush=True)
                try:
                    def guarded(s):
                        last[0]=s
                        if time.monotonic()-episode>1800 or time.monotonic()-start>10800:raise ValueError('Finite wall cap')
                        if len(actor.calls)>max(1024,20*case['n']):raise ValueError('Finite policy call cap')
                        if shutil.disk_usage(R).free<4*1024**3:raise ValueError('Disk guard')
                        if time.monotonic()-notice[0]>30:
                            print('PRESSURE_PROGRESS',label,'calls',len(actor.calls),'sim_s',round(s['now_ns']/1e9-35,2),'queue',len(s['queue']),flush=True);notice[0]=time.monotonic()
                        return actor(s)
                    result=C.engine.run(public,model,guarded,physics,case['common_potential_key'],rec)
                    metrics=C.engine.metrics(result,case,physics);score=old.objective.outcome(result,case,physics)
                    raw=O/(label+'.raw.json.gz');saved(raw,dict(result=result,calls=actor.calls,case=case,profile=dict(id='ORIGINAL',slots=3,beta=.25),policy_version=VERSION))
                    if learner:
                        pt(O/(label+'.FRAMES.pt.gz'),dict(frames=actor.frames,network_sha256=snap['network_sha256'],collect=False))
                        replica=Learner(state=before)
                        for f in actor.frames:
                            i,a=replica.choose({k:f[k] for k in ('x','mask','scores')},False)
                            assert i==f['index'] and a['old_logp']==f['old_logp'] and np.array_equal(a['value'],f['value']);frames_replayed+=1
                        equal(learner.snapshot(),before);equal(replica.snapshot(),before)
                    else:
                        replica=DynamicPolicy(nominal,physics,mode)
                        for dec,call in zip(result['decisions'],actor.calls):
                            assert replica(dec['public_state'])==dec['action']==call['action'] and replica.calls[-1]==call;dynamic_replayed+=1
                    assert len(actor.calls)==len(result['decisions'])
                    row=dict(label=label,case=case['id'],condition=case['condition'],policy=mode,kind='EVAL',status='COMPLETE',n=case['n'],metrics=metrics,score=score,raw=pin(raw),bank=pin(bankfile),policy_version=VERSION,network_sha256=snap['network_sha256'] if learner else None)
                    receipt('COMPLETE',label,raw_sha256=sha(raw));del result,replica
                except ValueError as e:
                    if str(e) not in ('Decision cap','Integration cap','Finite wall cap','Finite policy call cap','Disk guard'):raise
                    raw=O/(label+'.FAILED.json.gz');saved(raw,dict(calls=actor.calls,case=case,last_public_state=last[0],error=str(e),partial_not_complete_trace=True))
                    row=dict(label=label,case=case['id'],condition=case['condition'],policy=mode,status='FAIL',failure=str(e),metrics=None,score=None,raw=pin(raw),bank=pin(bankfile),automatic_retry=False)
                    receipt('FAIL',label,error=str(e),automatic_retry=False)
                new(O/(label+'.json'),row);rows.append(row);print('PRESSURE_TERMINAL',label,row['status'],'elapsed_s',round(time.monotonic()-start,1),flush=True)
                del actor,learner,model,bank;gc.collect()
        verify(op['pins']);failed=sum(r['status']=='FAIL' for r in rows)
        new(O/'REPLAY.json',dict(status='PASS',NN_frames=frames_replayed,dynamic_calls=dynamic_replayed,whole_checkpoint_two_Adam_all_RNG_unchanged=True,new_environment=0))
        new(O/'RESULT.json',dict(status='BATCH_COMPLETE',START=16,COMPLETE=16-failed,FAIL=failed,rows=rows,checkpoint=op['checkpoint'],new_training=0,new_BC_fit=0,new_PPO=0,new_fit=0,new_device=0,elapsed_s=time.monotonic()-start))
    except BaseException as e:
        if active[0] is not None:receipt('FAIL',active[0],error=str(e),automatic_retry=False)
        if O.exists():new(O/'FAILURE.json',dict(utc=stamp(),error=str(e),traceback=traceback.format_exc(),automatic_retry=False))
        raise
    finally:
        if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()
if __name__=='__main__':
    if '--propose' in sys.argv:propose()
    elif '--register' in sys.argv:register()
    elif '--run' in sys.argv:run()
    else:print('Explicit operation required; no automatic experiment')
