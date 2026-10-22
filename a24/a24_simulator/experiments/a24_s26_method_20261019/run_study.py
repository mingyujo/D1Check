"""Finite, preregistered 240 environments + 3 BC fits; all outcomes retained."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import sys,json,time,hashlib,subprocess,msvcrt,shutil,gc,datetime,traceback
from pathlib import Path
import psutil
H=Path(__file__).resolve().parent;A=H.parents[1];R=A.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def new(p,x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2)
def main():
    op=json.loads((H/'OPERATION.json').read_text(encoding='utf-8'));O=A/op['output_dir'];assert '--published' in sys.argv and not O.exists()
    assert subprocess.check_output(['git','show','HEAD:a24_simulator/experiments/a24_s26_method_20261019/OPERATION.json'])==(H/'OPERATION.json').read_bytes()
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
        sys.path.insert(0,str(A/'experiments/a24_parallel_20261018'))
        sys.path.insert(0,str(A/'experiments/a24_candidate_repair_20261018'))
        from policy_repair import Policy as OldPolicy
        sys.path.insert(0,str(H))
        # 'engine' and 'rewards' are names used by legacy dependencies: load
        # the new study under unique module identities, never shadow them.
        import importlib.util
        def module(name,file):
            spec=importlib.util.spec_from_file_location(name,H/file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
        Physics=module('a24_s26_port_physics','physics.py').Physics
        engine=module('a24_s26_port_engine','engine.py');rewards=module('a24_s26_port_rewards','rewards.py');Policy=module('a24_s26_port_policy','policy.py').Policy
        parent=read(op['parent']['path']);base,_,_=B.L.initialize(B.registration(parent));catalog=read(B.L.pin(B.registration(parent)['catalog_pin']));power=read(A/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json');shape=read(H/'SHAPE.json');oldstate=loadpt(op['frozen_checkpoint']['path']);design=read(H/'INPUTS.json');begin=time.monotonic();rows=[];count=0;replayed=0;updates=0;O.mkdir();opsha=sha(H/'OPERATION.json')
        new(O/'START.json',dict(utc=stamp(),pid=os.getpid(),HEAD=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),operation_sha256=opsha,processes=processes))
        def receipt(x):
            with (O/'receipts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(x)+'\n');f.flush();os.fsync(f.fileno())
        banks={}
        for case in design['training']+design['evaluation']:
            public,contexts=B.public_input(case,catalog);public['initial_ap_c']=26;bank=B.bank_module.bank(public,B.L.Model(base,contexts),case);file=O/(case['id']+'.BANK.json.gz');saved(file,bank);banks[case['id']]=(public,contexts,bank,file)
        def simulate(case,profile,policy,kind,tag,learner=None):
            nonlocal count,replayed,updates
            assert count<op['planned_START'] and time.monotonic()-begin<op['wall_clock_limit_s'] and shutil.disk_usage(R).free>=4*1024**3
            physics=Physics(power,B.Config(**parent['physics']),profile,shape);public,contexts,bank,bankfile=banks[case['id']];model=B.BankModel(bank['jobs'],contexts);nominal=B.SavedNominal(public,[dict(nominal_vectors=bank['nominal_vectors'])]);label=profile+'__'+tag+'__'+case['id']+'__'+policy
            rec=dict(event='START',label=label,kind=kind,utc=stamp(),durable_START_consumed=True,start_id=hashlib.sha256((opsha+label).encode()).hexdigest());receipt(rec);count+=1;print('START_S26_METHOD',count,label,flush=True)
            try:
                actor=(OldPolicy if policy=='OLD_NN' else Policy)(nominal,physics,case,policy,learner,kind=='TRAIN');before=learner.snapshot() if learner else None
                if learner:pt(O/(label+'.BEFORE.pt.gz'),before)
                def guarded(s):
                    assert time.monotonic()-begin<op['wall_clock_limit_s'],'Finite in-episode wall cap'
                    return actor(s)
                result=engine.run(public,model,guarded,physics,case['common_potential_key'],rec);m=engine.metrics(result,case,physics);raw=O/(label+'.raw.json.gz');saved(raw,dict(result=result,calls=actor.calls,case=case,profile=dict(id=profile,slots=3,beta=.25)))
                if kind=='DEMO':pt(O/(label+'.DEMO.pt.gz'),actor.frames)
                if learner:
                    cost,reward=rewards.labels(result,actor.frames,case,physics) if kind=='TRAIN' else (None,None)
                    pt(O/(label+'.FRAMES.pt.gz'),dict(frames=actor.frames,cost=cost,reward=reward));replica=Learner(state=before)
                    for f in actor.frames:
                        idx,again=replica.choose({k:f[k] for k in ('x','mask','scores')},kind=='TRAIN');assert idx==f['index'] and again['old_logp']==f['old_logp'] and np.array_equal(again['value'],f['value']);replayed+=1
                    if kind=='TRAIN':
                        n=learner.updates;learner.add(actor.frames,cost);replica.add(actor.frames,cost);updates+=learner.updates-n
                        # Soft dual adaptation, never a hard deadline action mask.
                        for l in (learner,replica):l.dual=np.clip(l.dual+.5*(np.asarray(reward['cost_sum'][2:4])-.01),0.,30.)
                    equal(learner.snapshot(),replica.snapshot());pt(O/(label+'.AFTER.pt.gz'),learner.snapshot());del replica
                row=dict(label=label,kind=kind,case=case['id'],profile=dict(id=profile,slots=3,beta=.25),policy=policy,n=case['n'],metrics=m,raw_sha256=sha(raw),bank_path=str(bankfile),bank_sha256=sha(bankfile),network_sha256=before['network_sha256'] if before else None,network_file=label+'.BEFORE.pt.gz' if before else None)
                new(O/(label+'.json'),row);rows.append(row);receipt({**rec,'event':'COMPLETE','utc':stamp(),'raw_sha256':sha(raw)});print('COMPLETE_S26_METHOD',count,label,m['on_time'],m['urgent_on_time'],m['wait_s'],'elapsed',round(time.monotonic()-begin,1),flush=True);del result,actor;gc.collect();return row
            except BaseException as e:receipt({**rec,'event':'FAIL','utc':stamp(),'error':str(e),'automatic_retry':False});raise
        for profile in op['profiles']:
            demos=[]
            for case in design['training']:
                simulate(case,profile,'EDF_CPU','REFERENCE','REF')
                row=simulate(case,profile,'TEACHER','DEMO','DEMO');demos.extend(loadpt(O/(row['label']+'.DEMO.pt.gz')))
            learner=Learner(op['seed'],True);learner.dual=np.asarray([12.,6.]);initial=learner.snapshot();pt(O/(profile+'.BC.INITIAL.pt.gz'),initial);pt(O/(profile+'.BC.FRAMES.pt.gz'),demos);trace=learner.distill(demos,op['BC_epochs']);warm=learner.snapshot();pt(O/(profile+'.BC.FINAL.pt.gz'),warm);pt(O/(profile+'.BC.TRACE.pt.gz'),trace)
            replica=Learner(state=initial);trace2=replica.distill(demos,op['BC_epochs']);equal(replica.snapshot(),warm);equal(trace,trace2);new(O/(profile+'.BC_EXACT.json'),dict(status='PASS',epochs=len(trace['logs']),frames=len(demos),groups=trace['groups'],final=trace['logs'][-1]));del replica,demos;gc.collect()
            for i in range(8):simulate(design['training'][i%4],profile,'PPO','TRAIN','EP'+str(i+1),learner)
            assert learner.updates==4 and learner.episodes==8 and not learner.pending
            final=learner.snapshot();pt(O/(profile+'.PPO.FINAL.pt.gz'),final);new(O/(profile+'.SELECTION_FROZEN.json'),dict(rule='Final EP8 fixed before EVAL; report BC and PPO regardless of outcome',network_sha256=digest(learner.net)))
            for case in design['evaluation']:
                for policy in op['policies']:
                    l=Learner(state=oldstate if policy=='OLD_NN' else warm if policy=='BC' else final) if policy in ('OLD_NN','BC','PPO') else None
                    simulate(case,profile,policy,'EVAL','EVAL',l);del l;gc.collect()
        assert count==240 and updates==12
        for p in op['pins']:assert sha(p['path'])==p['sha256'],p['path']
        new(O/'REPLAY.json',dict(status='PASS',frames=replayed,PPO_updates=updates,BC_fits=3,two_Adam_RNG_exact=True,new_physical_fits=0));new(O/'RESULT.json',dict(status='COMPLETE',START=count,COMPLETE=count,FAIL=0,rows=rows,new_training=24,new_BC_fits=3,new_physical_fit=0,elapsed_s=time.monotonic()-begin));print('S26_METHOD_ALL_COMPLETE',count,flush=True)
    except BaseException as e:
        if O.exists():new(O/'FAILURE.json',dict(utc=stamp(),error=str(e),traceback=traceback.format_exc(),automatic_retry=False))
        raise
    finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
if __name__=='__main__':main()
