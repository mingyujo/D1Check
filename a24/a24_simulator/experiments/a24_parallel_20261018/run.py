"""Finite paired A24 virtual-capacity study. No retry of consumed identities."""
import os
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[k]='1'
import sys,json,time,hashlib,subprocess,gc,copy,msvcrt,shutil,datetime,traceback
from pathlib import Path
import psutil
HERE=Path(__file__).resolve().parent;A=HERE.parents[1];REPO=A.parent
sys.path.insert(0,str(A/'experiments/public_transfer_20261018'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def json_new(p,x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2)
def main():
    assert '--published' in sys.argv
    op=json.loads((HERE/'OPERATION.json').read_text());out=A/op['output_dir'];assert not out.exists(),'Consumed operation identity'
    assert subprocess.check_output(['git','show','HEAD:a24_simulator/experiments/a24_parallel_20261018/OPERATION.json'])==(HERE/'OPERATION.json').read_bytes()
    for p in op['sources']+op['input_pins']:assert sha(p['path'])==p['sha256'],p['path']
    lock=(A/'runtime/a24_local_worker.lock').open('r+b');locked=False;deadline=time.monotonic()+3600;last=0
    while True:
        if not locked:
            try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
            except OSError:pass
        processes=[p.info for p in psutil.process_iter(['pid','name','cmdline']) if (p.info['name'] or '').lower() in ('python.exe','python3.exe')]
        if locked and len(processes)<=3 and psutil.virtual_memory().available>=512*1048576 and shutil.disk_usage(REPO).free>=8*1024**3:break
        assert time.monotonic()<deadline,'Finite PRE_START resource wait exhausted'
        if time.monotonic()-last>30:print('PRE_START_WAIT',len(processes),locked,psutil.virtual_memory().available//1048576,flush=True);last=time.monotonic()
        time.sleep(5)
    try:
        from common_transfer import B,read,saved,pt,loadpt,np,torch,equal
        from transfer_learner import Learner,digest
        from transfer_rewards import labels
        sys.path.insert(0,str(HERE))
        from physics_parallel import ParallelPhysics
        from engine_parallel import run,metrics
        from policy_parallel import Policy
        from event_engine import run as original_run
        begin=time.monotonic();out.mkdir();opsha=sha(HERE/'OPERATION.json');rows=[];count=0;replay_frames=0;updates=0
        json_new(out/'START.json',dict(utc=now(),PID=os.getpid(),HEAD=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),operation_sha256=opsha,processes=processes))
        design=read(op['inputs']['path']);train=design['training'];cases={c['id']:c for c in [*train,*design['evaluation']]};catalog=read(B.L.pin(B.registration(op)['catalog_pin']));nominals=read(op['public_nominals']['path']);power=read(A/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json')
        def receipt(x):
            with (out/'receipts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(x,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
        def simulate(case,profile,policy,kind,label,learner=None,old=False):
            nonlocal count,replay_frames,updates
            assert count<op['scientific_unit_cap'] and time.monotonic()-begin<op['wall_clock_limit_s']
            guard=dict(event='START',label=label,kind=kind,utc=now(),start_id=hashlib.sha256((opsha+label).encode()).hexdigest(),durable_START_consumed=True);receipt(guard);count+=1
            print('START',count,label,flush=True)
            try:
                cfg=copy.deepcopy(op['physics']);cfg['thermal_resistance']*=profile['k'];physics=ParallelPhysics(power,B.Config(**cfg),profile['slots'],profile['beta'])
                public,contexts=B.public_input(case,catalog);public['initial_ap_c']=case['temperature_c'];bank=read(op['bank_map'][case['id']]['path']);vectors=nominals[case['id']] if case['id'].startswith('DENSITY_') else bank['nominal_vectors'];model=B.BankModel(bank['jobs'],contexts);nominal=B.SavedNominal(public,[dict(nominal_vectors=vectors)])
                actor=Policy(nominal,physics,case,policy,learner,kind=='TRAIN');before=learner.snapshot() if learner else None
                if learner:pt(out/(label+'.BEFORE.pt.gz'),before)
                result=(original_run if old else run)(public,model,actor,B.Physics(power,B.Config(**cfg)) if old else physics,case['common_potential_key'],guard)
                m=None if old else metrics(result,case,physics)
                raw=out/(label+'.raw.json.gz');saved(raw,dict(result=result,calls=actor.calls,case=case,profile=profile))
                if kind=='DEMO':pt(out/(label+'.DEMO.pt.gz'),actor.frames)
                if learner:
                    cost,reward=labels(result,actor.frames,case,physics,op['reward_references'][case['id']],True,np.ones(2)) if kind=='TRAIN' else (None,None)
                    pt(out/(label+'.FRAMES.pt.gz'),dict(frames=actor.frames,cost=cost,reward=reward))
                    replica=Learner(state=before)
                    for f in actor.frames:
                        idx,again=replica.choose({k:f[k] for k in ('x','mask','scores')},kind=='TRAIN');assert idx==f['index'] and again['old_logp']==f['old_logp'] and np.array_equal(again['value'],f['value']);replay_frames+=1
                    if kind=='TRAIN':
                        old_updates=learner.updates;learner.add(actor.frames,cost);replica.add(actor.frames,cost);updates+=learner.updates-old_updates
                    equal(learner.snapshot(),replica.snapshot());pt(out/(label+'.AFTER.pt.gz'),learner.snapshot());del replica
                row=dict(label=label,kind=kind,case=case['id'],profile=profile,policy=policy,n=case['n'],metrics=m,raw_sha256=sha(raw),network_sha256=before['network_sha256'] if before else None,network_file=label+'.BEFORE.pt.gz' if before else None,old=old)
                json_new(out/(label+'.json'),row);rows.append(row);receipt({**guard,'event':'COMPLETE','utc':now(),'raw_sha256':sha(raw)});print('COMPLETE',count,label,None if old else [m['on_time'],m['urgent_on_time'],m['incomplete']],flush=True);del result,actor,model;gc.collect();return row
            except BaseException as e:receipt({**guard,'event':'FAIL','utc':now(),'error':str(e),'automatic_retry':False});raise
        p0case=cases['DENSITY_100_0'];profile=op['profiles'][0]
        simulate(p0case,profile,'EDF_CPU','P0','P0_OLD',old=True);simulate(p0case,profile,'EDF_CPU','P0','P0_NEW')
        a=read(out/'P0_OLD.raw.json.gz')['result'];b=read(out/'P0_NEW.raw.json.gz')['result']
        for k in ('requests','events'):
            if k=='requests':
                # Commitment hashes contain added public slot metadata only if
                # introduced; here the observation ABI is deliberately identical.
                assert B.G.canonical(a[k])==B.G.canonical(b[k]),'CPU1 P0 '+k
            else:assert a[k]==b[k],'CPU1 P0 '+k
        assert len(a['trace'])==len(b['trace'])
        maxerr=0.
        for x,y in zip(a['trace'],b['trace']):
            for k in ('start_ns','end_ns','state','next_state','increment','baseline','dynamic','shared','temperature_area','peak','dt'):assert x[k]==y[k],('CPU1 exact physical transition',k)
        json_new(out/'P0_EXACT.json',dict(status='PASS',requests=True,events=True,physical_trace=True,steps=len(a['trace']),new_environment_START=2));del a,b
        demos=[]
        for i,case in enumerate(train):
            row=simulate(case,op['profiles'][op['teacher_profile_indices'][i]],'PUBLIC_COST','DEMO','DEMO_'+case['id']);demos.extend(loadpt(out/(row['label']+'.DEMO.pt.gz')))
        learner=Learner(op['seed'],True);initial=learner.snapshot();pt(out/'BC.INITIAL.pt.gz',initial);pt(out/'BC.FRAMES.pt.gz',demos);trace=learner.distill(demos,op['BC_epochs']);warm=learner.snapshot();pt(out/'BC.FINAL.pt.gz',warm);pt(out/'BC.TRACE.pt.gz',trace)
        replica=Learner(state=initial);trace2=replica.distill(demos,op['BC_epochs']);equal(replica.snapshot(),warm);equal(trace,trace2);json_new(out/'BC_EXACT.json',dict(status='PASS',epochs=len(trace['logs']),frames=len(demos),final=trace['logs'][-1]));del replica,demos;gc.collect()
        for i,case in enumerate(train):simulate(case,op['profiles'][op['teacher_profile_indices'][i]],'PPO','TRAIN','TRAIN_EP'+str(i+1),learner)
        assert learner.updates==4 and learner.episodes==8 and not learner.pending
        final=learner.snapshot();pt(out/'PPO.FINAL.pt.gz',final);json_new(out/'SELECTION_FROZEN.json',dict(rule='Final EP8 preregistered; no evaluation used',network_sha256=digest(learner.net)))
        for profile in op['profiles']:
            for cid in op['evaluation_ids']:
                for policy in op['policies']:
                    l=Learner(state=warm if policy=='BC' else final) if policy in ('BC','PPO') else None
                    simulate(cases[cid],profile,policy,'EVAL',profile['id']+'__'+cid+'__'+policy,l);del l;gc.collect()
        assert count==228 and len(rows)==228 and updates==4
        for p in op['sources']+op['input_pins']:assert sha(p['path'])==p['sha256'],p['path']
        json_new(out/'REPLAY.json',dict(status='PASS',frames=replay_frames,PPO_updates=updates,BC_fits=1,two_Adam_RNG_exact=True))
        json_new(out/'RESULT.json',dict(status='COMPLETE',rows=rows,START=count,COMPLETE=count,FAIL=0,new_device=0,new_physical_fit=0,elapsed_s=time.monotonic()-begin))
        print('ALL_COMPLETE',count,flush=True)
    except BaseException as e:
        if out.exists():json_new(out/'FAILURE.json',dict(utc=now(),error=str(e),traceback=traceback.format_exc(),automatic_retry=False))
        raise
    finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
if __name__=='__main__':main()
