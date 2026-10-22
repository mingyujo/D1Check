"""Matched32 episodic PPO versus frozen fresh CEM; no PPO checkpoint initialization."""
import copy,datetime,gzip,hashlib,io,json,msvcrt,os,shutil,subprocess,sys,time,traceback
from pathlib import Path
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
H=Path(__file__).resolve().parent;R=H.parents[1];W=H.parents[3];O=H/'artifacts/G001'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(p,x):
    p=Path(p);b=json.dumps(x,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
    if p.suffix=='.gz':b=gzip.compress(b,compresslevel=3,mtime=0)
    with p.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def append(p,x):
    with Path(p).open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(x,ensure_ascii=False,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
def pt(p,x):
    import torch
    b=io.BytesIO();torch.save(x,b)
    with Path(p).open('xb') as f:f.write(gzip.compress(b.getvalue(),compresslevel=3,mtime=0));f.flush();os.fsync(f.fileno())
def guard(deadline):
    import gc,psutil
    last=0
    while True:
        gc.collect();procs=[p.info for p in psutil.process_iter(['pid','name','cmdline']) if (p.info['name'] or '').lower() in ['python.exe','python3.exe']]
        free=psutil.virtual_memory().available;disks={str(p):shutil.disk_usage(p).free for p in [W,Path('D:/')]}
        if len(procs)<=3 and free>=1536*1024**2 and min(disks.values())>=8*1024**3:return dict(utc=now(),free_bytes=free,python=procs,disk_free=disks)
        if time.monotonic()>=deadline:raise RuntimeError('Finite resource wait before START elapsed')
        if time.monotonic()-last>=30:print('RESOURCE_WAIT',len(procs),round(free/1048576),flush=True);last=time.monotonic()
        time.sleep(5)
def main(op):
    import numpy as np,torch
    from nn_train import Learner,digest
    from selection_rules import rolling_atc
    torch.set_num_threads(1)
    def forbidden_load(*args,**kwargs):raise RuntimeError('All on-disk checkpoint loading forbidden in scratch study')
    torch.load=forbidden_load
    started=time.monotonic();rows=[];count=0;selection=None;engine=None
    cases=read(H/'INPUTS.json')['cases'];phase={p:[c for c in cases if c['phase']==p] for p in ['CAL','TRAIN','DEV','EVAL']}
    def verify():
        for pin in op['pins']:assert sha(pin['path'])==pin['sha256'],'Changed pinned source '+pin['path']
    def simulate(c,method,label,kind,scales,learner=None,collect=False,epoch=None):
        nonlocal count,engine
        verify();assert count<op['environment_cap'] and time.monotonic()-started<op['wall_cap_s']
        resource=guard(started+op['wall_cap_s']);count+=1;frames=[];pre=digest(learner.net) if learner else None
        if learner and collect:
            learner.current_mix=c['mix'];learner.current_label=label
            crn=int(hashlib.sha256(f'{learner.seed}|{c["stream"]}|{label}|PPO_TRAIN_V1'.encode()).hexdigest()[:16],16)%(2**63);learner.action_rng.manual_seed(crn)
        else:crn=None
        eval_rng_seed=int(hashlib.sha256(f'{learner.seed}|{c["stream"]}|DEPLOY_SAMPLE_V1'.encode()).hexdigest()[:16],16)%(2**63) if learner and not collect else None
        eval_rng=torch.Generator().manual_seed(eval_rng_seed) if eval_rng_seed is not None else None
        train_rng_before=learner.action_rng.get_state().clone() if learner and not collect else None
        identity=hashlib.sha256((sha(H/'OPERATION.json')+'|'+label).encode()).hexdigest()
        rec=dict(event='START',utc=now(),count=count,label=label,identity=identity,kind=kind,input=c['id'],stream=c['stream'],method=method,seed=learner.seed if learner else None,epoch=epoch,selection_sha256=selection,resource=resource)
        append(O/'receipts.jsonl',rec);begin=time.monotonic();decisions=0
        bank_partial=O/(label+'.banks.jsonl.gz.partial');bank_final=O/(label+'.banks.jsonl.gz');bf=bank_partial.open('xb');bz=gzip.GzipFile(filename='',mode='wb',fileobj=bf,compresslevel=3,mtime=0)
        err=(O/'ENGINE_STDERR.txt').open('a');engine=subprocess.Popen(['node',str(H/'server_optimized.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,encoding='utf-8',bufsize=1)
        def send(x):engine.stdin.write(json.dumps(x,separators=(',',':'))+'\n');engine.stdin.flush()
        try:
            send(dict(input=c['id'],scales=scales))
            while True:
                line=engine.stdout.readline();assert line,'Engine closed'
                m=json.loads(line)
                if m['type']=='FAIL':save(O/(label+'.failed.json.gz'),m);raise RuntimeError(m['error'])
                if m['type']=='DONE':raw=m['result'];break
                bank=m['bank'];assert bank['constraints']==dict(physical_slots_only=True,deadline_action_mask=False,critical_request_override=False,fixed_ATC_prior=False,post_NN_override=False)
                if learner and collect:
                    index,f=learner.choose(bank,True);f.update(time_ns=bank['time_ns'],action=bank['actions'][index]);frames.append(f)
                elif learner:
                    with torch.no_grad():
                        logits,_=learner.net(torch.from_numpy(np.asarray(bank['x'],np.float32))[None],torch.from_numpy(np.asarray(bank['mask'],bool))[None])
                        index=int(torch.multinomial(logits.log_softmax(-1).exp()[0],1,generator=eval_rng))
                else:index=rolling_atc(bank)
                assert bank['mask'][index];bz.write((json.dumps(dict(bank=bank,index=index),separators=(',',':'))+'\n').encode());decisions+=1;send(dict(index=index))
            bz.close();bf.flush();os.fsync(bf.fileno());bf.close();assert not bank_final.exists();os.replace(bank_partial,bank_final)
            save(O/(label+'.raw.json.gz'),raw)
            n=c['n'];skin=c['context']['initial_context']['targets']['AP']['anchor']['SKIN'];span=raw['observation_end_s']-35
            responded=[q for q in raw['requests'] if q['response'] is not None]
            physical=[max(0,raw['api_energy']-raw['baseline_API_J'])/n,max(0,(raw['AP_mean']-skin)/10),0.,0.,(n-len(responded))/n]
            for q in raw['requests']:
                response=q['response'];j=2 if q['priority']=='urgent' else 3
                late=response is None or response>q['deadline']+1e-9
                latency=(response if response is not None else raw['observation_end_s'])-q['arrival']
                physical[j]+=(float(late)+.2*min(5,max(0,latency)/(q['deadline']-q['arrival'])))/n
            factors=[n/raw['service'][k]['planned'] for k in ['urgent','normal']]
            normalized=[physical[0]/scales[0],physical[1]/scales[1],physical[2]*factors[0],physical[3]*factors[1],physical[4]]
            row=dict(label=label,kind=kind,input=c['id'],stream=c['stream'],method=method,seed=learner.seed if learner else None,epoch=epoch,n=n,mix=c['mix'],replicate=c['replicate'],load=.85,
                service=raw['service'],unfinished=raw['unfinished'],J=raw['physics_J'],incremental_J=raw['api_energy']-raw['baseline_API_J'],AP_mean=raw['AP_mean'],AP_peak=raw['AP_peak_sampled'],
                baseline_J=raw['baseline_API_W']*raw['observation_end_s'],observation_s=raw['observation_end_s'],work_s=raw['actual_work_span_s'],routes=raw['policy_route_counts'],wait_s=raw['wait_s'],shared_cpu_wait_s=raw['shared_cpu_wait_s'],extra_cpu_core_s=raw['extra_cpu_core_s'],
                decisions=decisions,neural_calls=decisions if learner else 0,network_sha256=pre,deployment='training_sample' if collect else 'PPO_sample' if learner else 'deterministic_rule',train_rng_seed=crn,eval_rng_seed=eval_rng_seed,eval_rng_after_sha256=hashlib.sha256(eval_rng.get_state().numpy().tobytes()).hexdigest() if eval_rng else None,reused_environment=False,physical_cost=physical,normalized_cost=normalized,soft_objective=sum(v*w for v,w in zip(normalized,[1,1,1,1,3])),scales=scales,
                raw_sha256=sha(O/(label+'.raw.json.gz')),banks_sha256=sha(bank_final),physical_validation=False,wall_s=time.monotonic()-begin)
            if learner and collect:
                times=np.array([f['time_ns'] for f in frames],np.int64);cost=np.zeros((len(frames),5));assert len(times)>0
                def idx(t):return max(0,min(len(times)-1,int(np.searchsorted(times,round(t*1e9),side='right'))-1))
                for t0,t1,J,heat in raw['integrals']:
                    cost[idx(t0),0]+=(J-raw['baseline_API_W']*(t1-t0))/n
                    if physical[1]>0:cost[idx(t0),1]+=(heat-skin*(t1-t0))/(span*10)
                for q in raw['requests']:
                    response=q['response'];late=response is None or response>q['deadline']+1e-9
                    latency=(response if response is not None else raw['observation_end_s'])-q['arrival']
                    cost[idx(response) if response is not None else -1,2 if q['priority']=='urgent' else 3]+=(float(late)+.2*min(5,max(0,latency)/(q['deadline']-q['arrival'])))/n
                cost[-1,4]=physical[4];error=float(np.max(abs(cost.sum(0)-physical)));assert error<1e-7
                learning=cost.copy();learning[:,0]/=scales[0];learning[:,1]/=scales[1];learning[:,2]*=factors[0];learning[:,3]*=factors[1]
                pt(O/(label+'.frames.pt.gz'),dict(frames=frames,physical_costs=cost,learning_costs=learning,telescope_error=error,after_collect=learner.snapshot(),new_BC=0))
                learner.add(frames,learning)
            if learner and not collect:assert torch.equal(learner.action_rng.get_state(),train_rng_before),'DEV/EVAL cannot advance training RNG'
            save(O/(label+'.json'),row);rows.append(row);append(O/'receipts.jsonl',{**rec,'event':'COMPLETE','utc':now(),'raw_sha256':row['raw_sha256']})
            save(O/f'PROGRESS_{count:03d}.json',dict(START=count,COMPLETE=len(rows),FAIL=0,last=row))
            print('PURE_COMPLETE',count,label,'J',round(row['J'],3),'on',row['service']['all']['on_time'],'/',n,'AP',round(row['AP_mean'],3),'wall',round(row['wall_s'],1),flush=True)
            return row
        except BaseException as error:
            if frames:pt(O/(label+'.partial_frames.pt.gz'),dict(frames=frames,learner=learner.snapshot() if learner else None))
            append(O/'receipts.jsonl',{**rec,'event':'FAIL','utc':now(),'error':str(error),'automatic_retry':False});raise
        finally:
            if not bf.closed:bz.close();bf.flush();os.fsync(bf.fileno());bf.close()
            engine.stdin.close()
            try:engine.wait(timeout=20)
            except subprocess.TimeoutExpired:engine.terminate();engine.wait(timeout=10)
            err.close();engine=None
    scales=read(H/'CALIBRATION_REFERENCE.json')['scales']
    save(O/'SCALES_FROZEN.json',dict(utc=now(),scales=scales,reused_scalar_units_only=True,source_sha256=sha(H/'CALIBRATION_REFERENCE.json')))
    nets={};initial_nets={};selected=[];initial=[]
    for seed in op['seeds']:
        learner=Learner(seed);initial_net=Learner(seed);assert digest(learner.net)==digest(initial_net.net);initial_nets[seed]=initial_net
        initial.append(dict(seed=seed,network_sha256=digest(learner.net),actor_parameters=sum(p.numel() for p in learner.net.parameters()),old_weights=0,Adam_entries=len(learner.optimizer.state)))
        pt(O/f'S{seed}_EP000.pt.gz',learner.snapshot());best=None;trajectory=[]
        for gen in range(1,7):
            pt(O/f'S{seed}_G{gen:02d}_before.pt.gz',learner.snapshot())
            for rep in range(12):
                for c in phase['TRAIN'][2*(gen-1):2*gen]:
                    label=f'TRAIN_S{seed}_G{gen:02d}_P{rep:02d}_C{c["mix"]}'
                    simulate(c,f'RL{seed}',label,'TRAIN',scales,learner,True,gen)
            log=learner.update();pt(O/f'S{seed}_G{gen:02d}_after.pt.gz',learner.snapshot());save(O/f'S{seed}_G{gen:02d}_UPDATE.json',log)
            if gen in [2,4,6]:
                before=digest(learner.net);rr=[simulate(c,f'RL{seed}',f'{c["id"]}__RL{seed}_EP{gen:03d}','DEV',scales,learner,False,gen) for c in phase['DEV']]
                assert digest(learner.net)==before;score=float(np.mean([r['soft_objective'] for r in rr]));trajectory.append(dict(generation=gen,episodes=gen*24,score=score,network_sha256=before,rows=[r['label'] for r in rr]))
                if best is None or (score,gen)<(best['score'],best['epoch']):best=dict(epoch=gen,score=score,snapshot=learner.snapshot())
        assert learner.episodes==144 and learner.updates==6
        save(O/f'S{seed}_TRAINING.json',dict(trajectory=trajectory,episodes=144,updates=6,Adam_steps=learner.steps,logs=learner.logs,selected_epoch=best['epoch'],selected_score=best['score']))
        learner.restore(best['snapshot']);nets[seed]=learner;pt(O/f'S{seed}_SELECTED.pt.gz',learner.snapshot());selected.append(dict(seed=seed,epoch=best['epoch'],score=best['score'],network_sha256=digest(learner.net)))
    save(O/'INITIALIZATION_PROOF.json',dict(status='PASS',initial=initial,torch_load_globally_forbidden=True,old_project_weights=0,BC_fits=0,critic_parameters=0))
    cem={}
    for item in read(H/'CEM_FROZEN_ACTORS.json')['actors']:
        actor=Learner(item['seed'])
        with torch.no_grad():actor.net.weight.copy_(torch.tensor(item['weight'],dtype=torch.float32))
        assert digest(actor.net)==item['network_sha256'];cem[item['seed']]=actor
    save(O/'SELECTION_FROZEN.json',dict(utc=now(),selection=selected,CEM=read(H/'CEM_FROZEN_ACTORS.json')['actors'],source='Same4DEV / three eligible checkpoints per algorithm',EVAL_used=0));selection=sha(O/'SELECTION_FROZEN.json')
    frozen={('PPO',s):digest(l.net) for s,l in nets.items()};frozen.update({('CEM',s):digest(l.net) for s,l in cem.items()})
    for ci,c in enumerate(phase['EVAL']):
        order=['ROLLING_ATC',*[f'INITIAL_RL{s}' for s in op['seeds']],*[f'PPO{s}' for s in op['seeds']],*[f'CEM{s}' for s in op['seeds']]];shift=ci%10;order=order[shift:]+order[:shift]
        for method in order:
            actor=initial_nets[int(method[10:])] if method.startswith('INITIAL_RL') else nets[int(method[3:])] if method.startswith('PPO') else cem[int(method[3:])] if method.startswith('CEM') else None
            simulate(c,method,c['id']+'__'+method,'EVAL',scales,actor,False)
    assert count==548 and len(rows)==548
    assert all(digest(l.net)==frozen['PPO',s] for s,l in nets.items()) and all(digest(l.net)==frozen['CEM',s] for s,l in cem.items());verify()
    save(O/'RESULT.json',dict(status='COMPLETE_MATCHED_ACTOR_BUDGET_PPO_CEM',START=count,COMPLETE=count,REUSE=0,logical_records=len(rows),FAIL=0,rows=rows,scales=scales,selection=selected,new_TRAIN=432,reused_CEM_TRAIN=432,new_PPO_updates=18,BC=0,old_initialization_weights=0,new_fits=0,physical_validation=False,elapsed_s=time.monotonic()-started))
    save(O/'COMPLETE.json',dict(utc=now(),START=count,sha256=sha(O/'RESULT.json')));print('MATCHED_PPO_CEM_ALL_COMPLETE',count,flush=True)
if __name__=='__main__':
    op=read(H/'OPERATION.json');assert not O.exists(),'Consumed namespace; no automatic retry';assert read(H/'PREFLIGHT.json')['status']=='PASS'
    for pin in op['pins']:assert sha(pin['path'])==pin['sha256']
    lock=Path(op['shared_mutex']).open('r+b');locked=False
    try:
        deadline=time.monotonic()+3600
        while not locked:
            try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
            except OSError:
                if time.monotonic()>=deadline:raise
                time.sleep(5)
        resource=guard(time.monotonic()+3600);O.mkdir(parents=True);save(O/'START.json',dict(utc=now(),pid=os.getpid(),operation_sha256=sha(H/'OPERATION.json'),resource=resource))
        try:main(op)
        except BaseException as error:save(O/'FAILURE.json',dict(utc=now(),error=str(error),traceback=traceback.format_exc(),automatic_retry=False));raise
    finally:
        if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()
