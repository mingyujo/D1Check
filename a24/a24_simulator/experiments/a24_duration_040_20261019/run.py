"""Fixed-rate exact periodic extension; 24 frozen-policy evaluations only."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import sys,json,time,hashlib,subprocess,msvcrt,shutil,gc,datetime,traceback,copy,importlib.util
from pathlib import Path
import psutil
H=Path(__file__).resolve().parent;A=H.parents[1];R=A.parent;PORT=A/'experiments/a24_s26_method_20261019'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def new(p,x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False)
def main():
    op=json.loads((H/'OPERATION.json').read_text(encoding='utf-8'));O=A/op['output_dir'];assert '--published' in sys.argv and not O.exists()
    assert subprocess.check_output(['git','show','HEAD:a24_simulator/experiments/a24_duration_040_20261019/OPERATION.json'])==(H/'OPERATION.json').read_bytes()
    for p in op['pins']:assert sha(p['path'])==p['sha256'],p['path']
    lock=(A/'runtime/a24_local_worker.lock').open('r+b');locked=False;deadline=time.monotonic()+3600
    while True:
        if not locked:
            try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
            except OSError:pass
        processes=[p.info for p in psutil.process_iter(['pid','name','cmdline']) if (p.info['name'] or '').lower() in ('python.exe','python3.exe')]
        if locked and len(processes)<=3 and psutil.virtual_memory().available>=1024*1048576 and shutil.disk_usage(R).free>=8*1024**3:break
        assert time.monotonic()<deadline,'Finite resource wait';time.sleep(5)
    try:
        sys.path.insert(0,str(A/'experiments/public_transfer_20261018'))
        from common_transfer import B,read,saved,loadpt,pt,np,equal
        from transfer_learner import Learner,digest
        sys.path[:0]=[str(A/'experiments/a24_parallel_20261018'),str(A/'experiments/a24_candidate_repair_20261018'),str(PORT)]
        def module(name,path):
            spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
        Physics=module('duration_physics',PORT/'physics.py').Physics;engine=module('duration_engine',PORT/'engine.py');Policy=module('duration_policy',PORT/'policy.py').Policy
        outcome=module('duration_objective',A/'experiments/a24_cem_identification_20261019/objective.py').outcome
        parent=read(op['parent']['path']);catalog=read(B.L.pin(B.registration(parent)['catalog_pin']));power=read(A/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json');shape=read(PORT/'SHAPE.json');state=loadpt(op['checkpoint']['path']);begin=time.monotonic();O.mkdir();rows=[];count=0;replayed=0;opsha=sha(H/'OPERATION.json')
        new(O/'START.json',dict(utc=stamp(),pid=os.getpid(),HEAD=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),operation_sha256=opsha,processes=processes))
        def receipt(x):
            with (O/'receipts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(x)+'\n');f.flush();os.fsync(f.fileno())
        design=read(H/'INPUTS.json')
        for case in design['cases']:
            basecase=design['base_cases'][case['condition']['pattern_index']];public,contexts=B.public_input(basecase,catalog);public['initial_ap_c']=26
            proto=public['requests'];oldcontexts=copy.deepcopy(contexts);qs=[];cs={}
            for j,q in enumerate(case['input']['requests']):
                p=proto[j%len(proto)];v=copy.deepcopy(p);v.update(request_id='user-'+str(j).zfill(5),ordinal=j,scheduled_arrival_ns=round(q['arrival_s']*1e9),deadline_ns=round(q['deadline_s']*1e9),group=j//8);qs.append(v);cs[v['request_id']]=oldcontexts[p['request_id']]
                assert v['task']==q['profile'][0] and v['priority']==q['priority']
            lookup={q['request_id']:q for q in qs}
            for c in cs.values():c['_requests_by_id']=lookup
            public.update(requests=qs,service_stop_ns=round(case['service_stop_s']*1e9),drain_stop_ns=round(case['drain_stop_s']*1e9),observation_end_ns=round(case['observation_end_s']*1e9),public_base_sha256=B.L.digest(case['input']),public_scenario_sha256=B.L.digest(case['input']))
            bankfile=H/'banks'/(case['id']+'.BANK.json.gz');bank=read(bankfile);new(O/(case['id']+'.PUBLIC.json'),dict(public=public,case=case,bank_path=str(bankfile),bank_sha256=sha(bankfile)))
            for policy in op['policies']:
                assert count<24 and time.monotonic()-begin<14400 and shutil.disk_usage(R).free>=4*1024**3
                physics=Physics(power,B.Config(**parent['physics']),'ORIGINAL',shape);model=B.BankModel(bank['jobs'],cs);nominal=B.SavedNominal(public,[dict(nominal_vectors=bank['nominal_vectors'])]);learner=Learner(state=state) if policy=='OLD_PPO' else None;before=learner.snapshot() if learner else None;actor=Policy(nominal,physics,case,policy,learner,False);label='ORIGINAL__DURATION__'+case['id']+'__'+policy
                rec=dict(event='START',label=label,kind='EVAL',utc=stamp(),durable_START_consumed=True,start_id=hashlib.sha256((opsha+label).encode()).hexdigest());receipt(rec);count+=1;last=[None];episode=time.monotonic();print('START_DURATION',count,label,'n',case['n'],flush=True)
                try:
                    def guarded(s):
                        last[0]=s
                        if time.monotonic()-begin>14400:raise ValueError('Batch wall cap')
                        if time.monotonic()-episode>max(60,case['condition']['supply_s']*2):raise ValueError('Frozen policy wall cap')
                        if len(actor.calls)>max(1024,20*case['n']):raise ValueError('Frozen policy call cap')
                        return actor(s)
                    result=engine.run(public,model,guarded,physics,case['common_potential_key'],rec);m=engine.metrics(result,case,physics);score=outcome(result,case,physics);raw=O/(label+'.raw.json.gz');saved(raw,dict(result=result,calls=actor.calls,case=case,profile=dict(id='ORIGINAL',slots=3,beta=.25)))
                    if learner:
                        pt(O/(label+'.FRAMES.pt.gz'),dict(frames=actor.frames,network=before['network'],network_sha256=before['network_sha256']))
                        replica=Learner(state=before)
                        for f in actor.frames:
                            idx,again=replica.choose({k:f[k] for k in ('x','mask','scores')},False);assert idx==f['index'] and again['old_logp']==f['old_logp'] and np.array_equal(again['value'],f['value']);replayed+=1
                        equal(replica.snapshot(),before);equal(learner.snapshot(),before)
                    row=dict(label=label,kind='EVAL',case=case['id'],condition=case['condition'],profile=dict(id='ORIGINAL',slots=3,beta=.25),policy=policy,n=case['n'],metrics=m,score=score,raw_sha256=sha(raw),bank_path=str(bankfile),bank_sha256=sha(bankfile),network_sha256=before['network_sha256'] if before else None,network_file=op['checkpoint']['path'] if before else None)
                    new(O/(label+'.json'),row);rows.append(row);receipt({**rec,'event':'COMPLETE','utc':stamp(),'raw_sha256':sha(raw)});print('COMPLETE_DURATION',count,label,m['on_time'],m['urgent_on_time'],'elapsed',round(time.monotonic()-begin,1),flush=True);del result
                except ValueError as e:
                    if str(e) not in ('Decision cap','Integration cap','Frozen policy wall cap','Frozen policy call cap'):raise
                    raw=O/(label+'.FAILED.json.gz');saved(raw,dict(calls=actor.calls,case=case,last_public_state=last[0],error=str(e),partial_not_complete_trace=True));row=dict(label=label,kind='EVAL',case=case['id'],condition=case['condition'],profile=dict(id='ORIGINAL',slots=3,beta=.25),policy=policy,n=case['n'],status='FAIL',failure=str(e),metrics=None,score=None,raw_sha256=sha(raw),failed_file=str(raw),bank_path=str(bankfile),bank_sha256=sha(bankfile));new(O/(label+'.json'),row);rows.append(row);receipt({**rec,'event':'FAIL','utc':stamp(),'error':str(e),'automatic_retry':False});print('CONTROLLED_DURATION_FAIL',count,label,str(e),flush=True)
                del actor,learner;gc.collect()
        for p in op['pins']:assert sha(p['path'])==p['sha256'],p['path']
        failed=sum(r.get('status')=='FAIL' for r in rows);new(O/'REPLAY.json',dict(status='PASS',frames=replayed,frozen_NN_two_Adam_RNG_unchanged=True,new_environment=0,new_training=0));new(O/'RESULT.json',dict(status='BATCH_COMPLETE',START=count,COMPLETE=count-failed,FAIL=failed,rows=rows,elapsed_s=time.monotonic()-begin,new_training=0,new_physical_fit=0,new_device=0));print('DURATION_ALL_COMPLETE',count,failed,flush=True)
    except BaseException as e:
        if O.exists():new(O/'FAILURE.json',dict(utc=stamp(),error=str(e),traceback=traceback.format_exc(),automatic_retry=False))
        raise
    finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
if __name__=='__main__':main()
