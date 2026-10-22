"""Finite fresh-random PPO versus the exact same rolling ATC rule; no torch.load."""
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
        identity=hashlib.sha256((sha(H/'OPERATION.json')+'|'+label).encode()).hexdigest()
        rec=dict(event='START',utc=now(),count=count,label=label,identity=identity,kind=kind,input=c['id'],stream=c['stream'],method=method,seed=learner.seed if learner else None,epoch=epoch,selection_sha256=selection,resource=resource)
        append(O/'receipts.jsonl',rec);begin=time.monotonic();decisions=0
        bank_partial=O/(label+'.banks.jsonl.gz.partial');bank_final=O/(label+'.banks.jsonl.gz');bf=bank_partial.open('xb');bz=gzip.GzipFile(filename='',mode='wb',fileobj=bf,compresslevel=3,mtime=0)
        err=(O/'ENGINE_STDERR.txt').open('a');engine=subprocess.Popen(['node',str(H/'server.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,encoding='utf-8',bufsize=1)
        def send(x):engine.stdin.write(json.dumps(x,separators=(',',':'))+'\n');engine.stdin.flush()
        try:
            send(dict(input=c['id'],scales=scales))
            while True:
                line=engine.stdout.readline();assert line,'Engine closed'
                m=json.loads(line)
                if m['type']=='FAIL':save(O/(label+'.failed.json.gz'),m);raise RuntimeError(m['error'])
                if m['type']=='DONE':raw=m['result'];break
                bank=m['bank'];assert bank['constraints']==dict(physical_slots_only=True,deadline_action_mask=False,critical_request_override=False,fixed_ATC_prior=False,post_NN_override=False)
                if learner:
                    index,f=learner.choose(bank,collect);f.update(time_ns=bank['time_ns'],action=bank['actions'][index]);frames.append(f)
                else:index=rolling_atc(bank)
                assert bank['mask'][index];bz.write((json.dumps(dict(bank=bank,index=index),separators=(',',':'))+'\n').encode());decisions+=1;send(dict(index=index))
            bz.close();bf.flush();os.fsync(bf.fileno());bf.close();assert not bank_final.exists();os.replace(bank_partial,bank_final)
            save(O/(label+'.raw.json.gz'),raw)
            n=c['n'];skin=c['context']['initial_context']['targets']['AP']['anchor']['SKIN'];span=raw['observation_end_s']-35
            responded=[q for q in raw['requests'] if q['response'] is not None]
            physical=[max(0,raw['api_energy']-raw['baseline_API_J'])/n,max(0,(raw['AP_mean']-skin)/10),0.,0.,(n-len(responded))/n]
            for q in responded:
                d=max(0,q['response']-q['deadline']);j=2 if q['priority']=='urgent' else 3
                physical[j]+=(float(d>1e-9)+.02*min(5,d/(q['deadline']-q['arrival'])))/n
            factors=[n/raw['service'][k]['planned'] for k in ['urgent','normal']]
            normalized=[physical[0]/scales[0],physical[1]/scales[1],physical[2]*factors[0],physical[3]*factors[1],physical[4]]
            row=dict(label=label,kind=kind,input=c['id'],stream=c['stream'],method=method,seed=learner.seed if learner else None,epoch=epoch,n=n,mix=c['mix'],replicate=c['replicate'],load=.85,
                service=raw['service'],unfinished=raw['unfinished'],J=raw['physics_J'],incremental_J=raw['api_energy']-raw['baseline_API_J'],AP_mean=raw['AP_mean'],AP_peak=raw['AP_peak_sampled'],
                baseline_J=raw['baseline_API_W']*raw['observation_end_s'],observation_s=raw['observation_end_s'],work_s=raw['actual_work_span_s'],routes=raw['policy_route_counts'],wait_s=raw['wait_s'],shared_cpu_wait_s=raw['shared_cpu_wait_s'],extra_cpu_core_s=raw['extra_cpu_core_s'],
                decisions=decisions,neural_calls=decisions if learner else 0,network_sha256=pre,physical_cost=physical,normalized_cost=normalized,soft_objective=sum(v*w for v,w in zip(normalized,[1,1,1,1,3])),scales=scales,
                raw_sha256=sha(O/(label+'.raw.json.gz')),banks_sha256=sha(bank_final),physical_validation=False,wall_s=time.monotonic()-begin)
            if learner and collect:
                times=np.array([f['time_ns'] for f in frames],np.int64);cost=np.zeros((len(frames),5));assert len(times)>0
                def idx(t):return max(0,min(len(times)-1,int(np.searchsorted(times,round(t*1e9),side='right'))-1))
                for t0,t1,J,heat in raw['integrals']:
                    cost[idx(t0),0]+=(J-raw['baseline_API_W']*(t1-t0))/n
                    if physical[1]>0:cost[idx(t0),1]+=(heat-skin*(t1-t0))/(span*10)
                for q in responded:
                    d=max(0,q['response']-q['deadline']);cost[idx(q['response']),2 if q['priority']=='urgent' else 3]+=(float(d>1e-9)+.02*min(5,d/(q['deadline']-q['arrival'])))/n
                cost[-1,4]=physical[4];error=float(np.max(abs(cost.sum(0)-physical)));assert error<1e-7
                learning=cost.copy();learning[:,0]/=scales[0];learning[:,1]/=scales[1];learning[:,2]*=factors[0];learning[:,3]*=factors[1]
                pt(O/(label+'.frames.pt.gz'),dict(frames=frames,physical_costs=cost,learning_costs=learning,telescope_error=error,after_collect=learner.snapshot(),new_BC=0))
                learner.add(frames,learning)
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
    cal=[simulate(c,'ROLLING_ATC',c['id']+'__ROLLING_ATC','CAL',[1.,1.]) for c in phase['CAL']]
    scales=[max(1e-4,float(np.mean([r['physical_cost'][j] for r in cal]))) for j in [0,1]]
    save(O/'SCALES_FROZEN.json',dict(utc=now(),scales=scales,source_labels=[r['label'] for r in cal],no_action_labels_used=True,no_policy_fit=True))
    for c in phase['DEV']:simulate(c,'ROLLING_ATC',c['id']+'__ROLLING_ATC','DEV',scales)
    nets={};selected=[];initial=[]
    for seed in op['seeds']:
        learner=Learner(seed);learner.net.temperature=1.;learner.optimizer.param_groups[0]['lr']=1e-4
        learner.balance=dict(scales=scales,dual=[1.,1.],classFactors=[1,1],tail=.02,rank_feature=True)
        independently= Learner(seed);assert digest(independently.net)==digest(learner.net);del independently
        initial.append(dict(seed=seed,network_sha256=digest(learner.net),episodes=learner.episodes,updates=learner.updates,Adam_state_entries=len(learner.optimizer.state),fresh_seed_reproduction=True))
        pt(O/f'S{seed}_EP000.pt.gz',learner.snapshot());order=np.random.default_rng(seed+50000).permutation(len(phase['TRAIN'])).tolist()
        save(O/f'S{seed}_ORDER.json',dict(order=order,case_ids=[phase['TRAIN'][i]['id'] for i in order],initial=initial[-1]))
        best=None;trajectory=[]
        def dev(ep):
            nonlocal best
            before=digest(learner.net);rr=[simulate(c,f'RL{seed}',f'{c["id"]}__RL{seed}_EP{ep:03d}','DEV',scales,learner,False,ep) for c in phase['DEV']]
            assert digest(learner.net)==before
            score=float(np.mean([r['soft_objective'] for r in rr]));trajectory.append(dict(epoch=ep,score=score,network_sha256=before,rows=[r['label'] for r in rr]))
            if best is None or (score,ep)<(best['score'],best['epoch']):best=dict(epoch=ep,score=score,snapshot=learner.snapshot())
        dev(0)
        for ep,j in enumerate(order,1):
            pt(O/f'S{seed}_EP{ep:03d}_before.pt.gz',learner.snapshot())
            simulate(phase['TRAIN'][j],f'RL{seed}',f'TRAIN_S{seed}_EP{ep:03d}','TRAIN',scales,learner,True,ep)
            pt(O/f'S{seed}_EP{ep:03d}_after.pt.gz',learner.snapshot())
            if ep in [24,48,72,96]:dev(ep)
        assert learner.episodes==96 and learner.updates==48 and not learner.pending
        assert all(log['aux_weight']==0 for log in learner.logs)
        save(O/f'S{seed}_TRAINING.json',dict(trajectory=trajectory,episodes=96,updates=48,Adam_steps=learner.steps,logs=learner.logs,selected_epoch=best['epoch'],selected_score=best['score']))
        learner.restore(best['snapshot']);nets[seed]=learner;pt(O/f'S{seed}_SELECTED.pt.gz',learner.snapshot());selected.append(dict(seed=seed,epoch=best['epoch'],score=best['score'],network_sha256=digest(learner.net)))
    save(O/'INITIALIZATION_PROOF.json',dict(status='PASS',initial=initial,torch_load_globally_forbidden=True,BC_fits=0,teacher_auxiliary=0,earlier_weights=0,random_actor_output_initialization=True))
    save(O/'SELECTION_FROZEN.json',dict(utc=now(),selection=selected,source='DEV only',fixed_runtime_seed=981083,EVAL_used=0));selection=sha(O/'SELECTION_FROZEN.json')
    frozen={s:digest(l.net) for s,l in nets.items()}
    for ci,c in enumerate(phase['EVAL']):
        order=['ROLLING_ATC',*[f'RL{s}' for s in op['seeds']]];shift=ci%4;order=order[shift:]+order[:shift]
        for method in order:simulate(c,method,c['id']+'__'+method,'EVAL',scales,nets[int(method[2:])] if method.startswith('RL') else None,False)
    assert count==392 and len(rows)==392;assert all(digest(l.net)==frozen[s] for s,l in nets.items());verify()
    save(O/'RESULT.json',dict(status='COMPLETE_PURE_ROLLING_ATC_SCRATCH_RL',START=count,COMPLETE=len(rows),FAIL=0,rows=rows,scales=scales,selection=selected,new_TRAIN=288,new_PPO_updates=144,new_BC=0,earlier_weights=0,new_fits=0,physical_validation=False,elapsed_s=time.monotonic()-started))
    save(O/'COMPLETE.json',dict(utc=now(),START=count,sha256=sha(O/'RESULT.json')));print('PURE_ALL_COMPLETE',count,flush=True)
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
