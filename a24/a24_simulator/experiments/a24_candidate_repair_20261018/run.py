"""Ten finite candidate-only counterfactuals, fixed original final weights."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import sys,json,time,hashlib,subprocess,msvcrt,shutil,copy,gc,datetime,traceback
from pathlib import Path
import psutil
H=Path(__file__).resolve().parent;A=H.parents[1];R=A.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def new(p,x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2)
def main():
    op=json.loads((H/'OPERATION.json').read_text(encoding='utf-8'));O=A/op['output_dir'];assert '--published' in sys.argv and not O.exists()
    assert subprocess.check_output(['git','show','HEAD:a24_simulator/experiments/a24_candidate_repair_20261018/OPERATION.json'])==(H/'OPERATION.json').read_bytes()
    for p in op['pins']:assert sha(p['path'])==p['sha256'],p['path']
    lock=(A/'runtime/a24_local_worker.lock').open('r+b');locked=False;deadline=time.monotonic()+3600;last=0
    while True:
        if not locked:
            try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
            except OSError:pass
        processes=[p.info for p in psutil.process_iter(['pid','name','cmdline']) if (p.info['name'] or '').lower() in ('python.exe','python3.exe')]
        if locked and len(processes)<=3 and psutil.virtual_memory().available>=512*1048576 and shutil.disk_usage(R).free>=8*1024**3:break
        assert time.monotonic()<deadline,'Finite pre-start wait';time.sleep(5)
    try:
        sys.path.insert(0,str(A/'experiments/public_transfer_20261018'))
        from common_transfer import B,read,saved,loadpt,pt,np,equal
        from transfer_learner import Learner,digest
        sys.path.insert(0,str(A/'experiments/a24_parallel_20261018'))
        from physics_parallel import ParallelPhysics
        from engine_parallel import run,metrics
        sys.path.insert(0,str(H))
        from policy_repair import Policy
        parent=read(op['parent']['path']);prior=A/'results/A24_PARALLEL_20261018_01';design=read(parent['inputs']['path']);cases={c['id']:c for c in design['evaluation']};catalog=read(B.L.pin(B.registration(parent)['catalog_pin']));nominals=read(parent['public_nominals']['path']);power=read(A/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json');profile=next(p for p in parent['profiles'] if p['id']==parent['primary']);physics=ParallelPhysics(power,B.Config(**parent['physics']),profile['slots'],profile['beta']);frozen=loadpt(op['frozen_checkpoint']['path']);learner=Learner(state=frozen);initial=learner.snapshot();begin=time.monotonic();rows=[];count=0;replayed=0;O.mkdir();opsha=sha(H/'OPERATION.json')
        new(O/'START.json',dict(utc=stamp(),pid=os.getpid(),HEAD=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),operation_sha256=opsha,processes=processes,frozen_network_sha256=digest(learner.net)))
        def receipt(x):
            with (O/'receipts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(x)+'\n');f.flush();os.fsync(f.fileno())
        for spec in op['cases']:
            assert count<10 and time.monotonic()-begin<3600
            label=spec['policy']+'__'+spec['case'];rec=dict(event='START',label=label,kind='REPAIR_COUNTERFACTUAL',utc=stamp(),durable_START_consumed=True,start_id=hashlib.sha256((opsha+label).encode()).hexdigest());receipt(rec);count+=1;print('START_REPAIR',count,label,flush=True)
            try:
                case=cases[spec['case']];public,contexts=B.public_input(case,catalog);public['initial_ap_c']=case['temperature_c'];bank=read(parent['bank_map'][case['id']]['path']);model=B.BankModel(bank['jobs'],contexts);nominal=B.SavedNominal(public,[dict(nominal_vectors=nominals[case['id']])]);actor=Policy(nominal,physics,case,spec['policy'],learner if spec['policy']=='REPAIR_PPO' else None,False)
                result=run(public,model,actor,physics,case['common_potential_key'],rec);m=metrics(result,case,physics);raw=O/(label+'.raw.json.gz');saved(raw,dict(result=result,calls=actor.calls,case=case,profile=profile))
                pt(O/(label+'.FRAMES.pt.gz'),actor.frames)
                if spec['policy']=='REPAIR_PPO':
                    replica=Learner(state=initial)
                    for f in actor.frames:
                        idx,again=replica.choose({k:f[k] for k in ('x','mask','scores')},False);assert idx==f['index'] and again['old_logp']==f['old_logp'] and np.array_equal(again['value'],f['value']);replayed+=1
                    equal(replica.snapshot(),initial);equal(learner.snapshot(),initial);del replica
                row=dict(label=label,kind='EVAL',case=case['id'],profile=profile,policy=spec['policy'],n=case['n'],metrics=m,raw_sha256=sha(raw),network_sha256=initial['network_sha256'] if spec['policy']=='REPAIR_PPO' else None,network_file='../A24_PARALLEL_20261018_01/PPO.FINAL.pt.gz' if spec['policy']=='REPAIR_PPO' else None,old=False)
                new(O/(label+'.json'),row);rows.append(row);receipt({**rec,'event':'COMPLETE','utc':stamp(),'raw_sha256':sha(raw)});print('COMPLETE_REPAIR',count,label,m['on_time'],m['urgent_on_time'],m['incomplete'],flush=True);del result,actor,model;gc.collect()
            except BaseException as e:receipt({**rec,'event':'FAIL','utc':stamp(),'error':str(e),'automatic_retry':False});raise
        for p in op['pins']:assert sha(p['path'])==p['sha256'],p['path']
        new(O/'REPLAY.json',dict(status='PASS',frames=replayed,frozen_NN_two_Adam_RNG_unchanged=True,new_updates=0,new_training=0,new_BC_fits=0));new(O/'RESULT.json',dict(status='COMPLETE',START=10,COMPLETE=10,FAIL=0,rows=rows,new_training=0,new_fit=0,elapsed_s=time.monotonic()-begin));print('REPAIR_ALL_COMPLETE',count,flush=True)
    except BaseException as e:
        if O.exists():new(O/'FAILURE.json',dict(utc=stamp(),error=str(e),traceback=traceback.format_exc(),automatic_retry=False))
        raise
    finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
if __name__=='__main__':main()
