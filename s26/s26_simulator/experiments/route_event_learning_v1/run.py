"""Finite, resumeless route/reward/capacity study. Each START is durable."""
import copy,datetime,gzip,hashlib,io,json,msvcrt,os,shutil,subprocess,sys,time,traceback
from pathlib import Path
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
H=Path(__file__).resolve().parent;R=H.parents[1];W=H.parents[3]
def read(p):
    p=Path(p);return json.loads((gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes()).decode('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(p,x):
    p=Path(p);b=json.dumps(x,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
    if p.suffix=='.gz':b=gzip.compress(b,compresslevel=4,mtime=0)
    with p.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def append(p,x):
    with Path(p).open('a',encoding='utf-8') as f:f.write(json.dumps(x,ensure_ascii=False,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
def pt(p,x):
    import torch
    b=io.BytesIO();torch.save(x,b)
    with Path(p).open('xb') as f:f.write(gzip.compress(b.getvalue(),compresslevel=3,mtime=0))
def snapshot_resources(min_MiB=1536):
    import psutil,gc
    end=time.monotonic()+3600;last=0
    while True:
        gc.collect();processes=[p.info for p in psutil.process_iter(['pid','name','cmdline']) if (p.info['name'] or '').lower() in ['python.exe','python3.exe']]
        free=psutil.virtual_memory().available
        if len(processes)<=3 and free>=min_MiB*1024**2 and all(shutil.disk_usage(p).free>=8*1024**3 for p in [W,Path('D:/')]):return dict(utc=now(),free_bytes=free,python=processes,min_free_MiB=min_MiB,real_host_inventory=True)
        if time.monotonic()>=end:raise RuntimeError('Finite resource wait elapsed before START')
        if time.monotonic()-last>=30:print('EVENT_RESOURCE_WAIT',len(processes),round(free/1048576),flush=True);last=time.monotonic()
        time.sleep(5)
def main(op,O):
    import numpy as np,torch
    from nn_train import Learner,digest
    from bc import teacher,pretrain
    torch.set_num_threads(1);count=0;rows=[];selection=None;started=time.monotonic()
    cases=read(H/'INPUTS.json')['cases'];phase={k:[c for c in cases if c['phase']==k] for k in ['P0','TRAIN','DEV','EVAL']}
    def verify():
        for p in op['pins']:assert sha(p['path'])==p['sha256'],'Changed source '+p['path']
    def load(p):return torch.load(io.BytesIO(gzip.decompress(Path(p).read_bytes())),map_location='cpu',weights_only=False)
    engine=None
    def reset_engine():
        nonlocal engine
        if engine is not None:
            engine.stdin.close()
            try:engine.wait(timeout=20)
            except subprocess.TimeoutExpired:engine.terminate();engine.wait(timeout=10)
            engine=None
        append(O/'RESOURCE_CHECKS.jsonl',dict(count=count,**snapshot_resources(1536)))
        engine=subprocess.Popen(['node',str(H/'server.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=(O/'ENGINE_STDERR.txt').open('a'),text=True,encoding='utf-8',bufsize=1)

    def send(x):engine.stdin.write(json.dumps(x,separators=(',',':'))+'\n');engine.stdin.flush()
    def simulate(c,mode,label,kind,model,learner=None,collect=False,parent=False,balance=None):
        nonlocal count
        verify();assert count<op['environment_cap'] and time.monotonic()-started<op['wall_cap_s']
        if count%8==0:reset_engine()
        count+=1;frames=[];pre=digest(learner.net) if learner else None
        start=dict(event='START',utc=now(),label=label,kind=kind,input=c['id'],model=model,mode=mode,seed=learner.seed if learner else None,selection_sha256=selection,stream=c['stream'],count=count)
        append(O/'receipts.jsonl',start)
        try:
            send(dict(input=c['id'],model=model,mode=mode,variant='REPAIR',stream=c['stream'],parent=parent,balance=balance))
            while True:
                line=engine.stdout.readline();assert line,'Engine closed';m=json.loads(line)
                if m['type']=='FAIL':save(O/(label+'.failed.json.gz'),m);raise RuntimeError(m['error'])
                if m['type']=='DONE':raw=m['result'];break
                assert m['type']=='BANK' and (learner is not None or mode=='DEMO')
                bank=m['bank'];assert bank['constraints']==dict(physical_slots_only=True,deadline_action_mask=False,critical_request_override=False,fixed_ATC_prior=False,post_NN_override=False)
                if mode=='DEMO':
                    index=teacher(bank);f=dict(x=np.asarray(bank['x'],np.float32),mask=np.asarray(bank['mask'],bool),scores=bank['scores'],index=index,from_teacher=True,collect=False)
                else:index,f=learner.choose(bank,collect)
                f.update(time_ns=bank['time_ns'],action=bank['actions'][index],candidate_actions=bank['actions'],nominal_forecasts=bank['forecasts']);frames.append(f);send(dict(index=index))
            save(O/(label+'.raw.json.gz'),raw)
            n=c['n'];responded=[q for q in raw['requests'] if q['response'] is not None];span=raw['observation_end_s']-35;skin=c['context']['initial_context']['targets']['AP']['anchor']['SKIN']
            objective=[max(0,raw['api_energy']-raw['baseline_API_J'])/n,max(0,(raw['AP_mean']-skin)/10),0.,0.,(n-len(responded))/n]
            balanced_objective=objective.copy()
            for q in responded:
                d=max(0,q['response']-q['deadline']);j=2 if q['priority']=='urgent' else 3
                objective[j]+=(float(d>1e-9)+.2*min(5,d/(q['deadline']-q['arrival'])))/n
                balanced_objective[j]+=(float(d>1e-9)+.02*min(5,d/(q['deadline']-q['arrival'])))/n
            row=dict(label=label,kind=kind,input=c['id'],model=model,mode=mode,seed=learner.seed if learner else None,balanced=balance is not None,n=n,mix=c['mix'],load=c['nominal_load_ratio'],replicate=c['replicate'],service=raw['service'],unfinished=raw['unfinished'],J=raw['physics_J'],incremental_J=raw['api_energy']-raw['baseline_API_J'],baseline_J=raw['baseline_API_W']*raw['observation_end_s'],AP_mean=raw['AP_mean'],AP_peak=raw['AP_peak_sampled'],outside_AP=raw['outside_marginal_AP'],observation_s=raw['observation_end_s'],work_s=raw['actual_work_span_s'],routes=raw['policy_route_counts'],extra_CPU_core_s=raw.get('extra_cpu_core_s',0),shared_CPU_wait_s=raw['shared_cpu_wait_s'],wait_s=raw['wait_s'],cost=objective,balanced_cost=balanced_objective,old_weighted=sum(x*w for x,w in zip(objective,[.5,.5,8,4,30])),network_sha256=pre,frames=len(frames),raw_sha256=sha(O/(label+'.raw.json.gz')),physical_validation=False)
            if mode=='DEMO':pt(O/(label+'.demonstrations.pt.gz'),dict(frames=frames,from_teacher=True,new_PPO_updates=0,balance=balance))
            if learner:
                times=np.array([f['time_ns'] for f in frames],np.int64);cost=np.zeros((len(frames),5));assert len(times)>0 and np.all(np.diff(times)>=0)
                def idx(t):return max(0,min(len(times)-1,int(np.searchsorted(times,round(t*1e9),side='right'))-1))
                for t0,t1,J,heat in raw['integrals']:
                    cost[idx(t0),0]+=(J-raw['baseline_API_W']*(t1-t0))/n
                    if objective[1]>0:cost[idx(t0),1]+=(heat-skin*(t1-t0))/(span*10)
                tail=.02 if balance is not None else .2
                for q in responded:
                    d=max(0,q['response']-q['deadline']);cost[idx(q['response']),2 if q['priority']=='urgent' else 3]+=(float(d>1e-9)+tail*min(5,d/(q['deadline']-q['arrival'])))/n
                cost[-1,4]=objective[4]
                expected=balanced_objective if balance is not None else objective
                error=float(np.max(abs(cost.sum(0)-expected)));assert error<1e-7
                learning=cost.copy()
                if balance is not None:
                    learning[:,0]/=balance['scales'][0];learning[:,1]/=balance['scales'][1];learning[:,2]*=balance['classFactors'][0];learning[:,3]*=balance['classFactors'][1]
                pt(O/(label+'.frames.pt.gz'),dict(frames=frames,physical_costs=cost,learning_costs=learning,collect=collect,balance=copy.deepcopy(balance),telescope_error=error))
                if collect:learner.add(frames,learning)
            save(O/(label+'.json'),row);rows.append(row);append(O/'receipts.jsonl',{**start,'event':'COMPLETE','utc':now(),'raw_sha256':row['raw_sha256']})
            print(json.dumps(dict(event='COMPLETE',count=count,label=label,on=raw['service']['all']['on_time'],n=n,J=row['J'])),flush=True)
            return row,raw
        except BaseException as e:
            if frames:pt(O/(label+'.partial_frames.pt.gz'),frames)
            append(O/'receipts.jsonl',{**start,'event':'FAIL','utc':now(),'error':str(e),'automatic_retry':False});raise
    try:
        c=phase['P0'][0]
        a,ra=simulate(c,'EDF_GPU_FIRST','P0_PARENT','P0','CPU3',parent=True)
        b,rb=simulate(c,'EDF_GPU_FIRST','P0_EVENT_ENGINE','P0','CPU3')
        assert abs(a['J']-b['J'])<1e-7 and abs(a['AP_mean']-b['AP_mean'])<1e-8
        assert all(abs(x['available']-y['available'])<1e-8 for x,y in zip(ra['requests'],rb['requests']))
        save(O/'P0_PROOF.json',dict(parent_CPU3_exact=True,max_J_error=abs(a['J']-b['J']),new_environments=2))
        parent=load(op['parent_checkpoint']);frozen=Learner(481083);frozen.restore(parent);frozen_sha=digest(frozen.net);references={};reference_rows=[]
        for i,c in enumerate(phase['TRAIN']):
            row,_=simulate(c,'RL',f'REFERENCE_{i}','TRAIN_REFERENCE','CPU3',frozen,parent=True);references[c['id']]=row;reference_rows.append(row)
        scales=[max(.05,float(np.median([r['cost'][j] for r in reference_rows]))) for j in [0,1]]
        demos=[]
        for i,c in enumerate([c for c in phase['TRAIN'] if c['nominal_load_ratio']==.85]):
            balance=dict(scales=scales,dual=[1.,1.],classFactors=[1/c['mix'],1/(1-c['mix'])],tail=.02)
            row,_=simulate(c,'DEMO',f'DEMO_{i}','DEMO','CPU3',balance=balance)
            data=load(O/(row['label']+'.demonstrations.pt.gz'));demos.append(data)
        warm,bc_trace=pretrain(parent,demos,op['BC_seed']);warm.balance=dict(scales=scales,dual=[1.,1.],classFactors=[1,1],tail=.02)
        pt(O/'BC_TRACE.pt.gz',bc_trace);pt(O/'BC_COMMON_FINAL.pt.gz',dict(learner=warm.snapshot(),balance=warm.balance));save(O/'BC_TRAINING.json',dict(logs=bc_trace['logs'],steps=bc_trace['steps'],frames=bc_trace['frames'],not_RL=True,new_PPO_updates=0,weight_sha256=digest(warm.net)));warm_sha=digest(warm.net)
        del demos
        nets={};dual_history=[]
        for seed in op['seeds']:
            learner=Learner(seed);learner.net.load_state_dict(warm.net.state_dict());learner.net.temperature=.35;learner.optimizer.param_groups[0]['lr']=1e-4;dual=np.ones(2);order=np.random.default_rng(seed+50000).permutation(8).tolist()
            save(O/f'S{seed}_ORDER.json',dict(order=order,case_ids=[phase['TRAIN'][j]['id'] for j in order],scales=scales,common_BC_sha256=warm_sha));pt(O/f'S{seed}_EP000.pt.gz',learner.snapshot())
            for ep,j in enumerate(order,1):
                c=phase['TRAIN'][j];ref=references[c['id']];balance=dict(scales=scales,dual=dual.tolist(),classFactors=[c['n']/ref['service'][k]['planned'] for k in ['urgent','normal']],tail=.02);learner.balance=copy.deepcopy(balance)
                pt(O/f'S{seed}_EP{ep:03d}_before.pt.gz',dict(learner=learner.snapshot(),balance=balance));row,_=simulate(c,'RL',f'TRAIN_S{seed}_EP{ep:03d}','TRAIN','CPU3',learner,True,balance=balance)
                deficits=np.array([(ref['service'][k]['on_time']-row['service'][k]['on_time'])/ref['service'][k]['planned']-.005 for k in ['urgent','normal']]);old=dual.copy();dual=np.clip(dual+4*deficits,.25,8.);dual_history.append(dict(seed=seed,ep=ep,before=old.tolist(),after=dual.tolist(),deficits=deficits.tolist()))
                pt(O/f'S{seed}_EP{ep:03d}_after.pt.gz',dict(learner=learner.snapshot(),dual=dual.tolist(),balance=balance))
            assert learner.episodes==8 and learner.updates==4 and not learner.pending
            learner.balance=dict(scales=scales,dual=dual.tolist(),classFactors=[1,1],tail=.02);nets[seed]=learner;pt(O/f'S{seed}_FINAL.pt.gz',dict(learner=learner.snapshot(),balance=learner.balance))
        save(O/'TRAINING_COMPLETE.json',dict(scales=scales,TRAIN_REFERENCE=8,DEMO=4,TRAIN=24,PPO_updates=12,dual_history=dual_history,updates={str(s):l.logs for s,l in nets.items()},BC_source_sha256=sha(O/'BC_COMMON_FINAL.pt.gz')))
        def evaluate(c,phase,i):
            for mode in ['EDF_GPU_FIRST','ATC','ATC_SALVAGE']:simulate(c,mode,f'{phase}_{i}_{mode}',phase,'CPU3',parent=True)
            simulate(c,'RL',f'{phase}_{i}_FROZEN',phase,'CPU3',frozen,parent=True)
            for label,learner in [('WARM_FROZEN',warm),*[(f'RL_S{s}',l) for s,l in nets.items()]]:
                balance=copy.deepcopy(learner.balance);balance['classFactors']=[1/c['mix'],1/(1-c['mix'])];simulate(c,'RL',f'{phase}_{i}_{label}',phase,'CPU3',learner,balance=balance)
        for i,c in enumerate(phase['DEV']):evaluate(c,'DEV',i)
        dev=[r for r in rows if r['kind']=='DEV'];ref={r['input']:r for r in dev if r['seed']==481083};scores=[]
        for seed in op['seeds']:
            rr=[r for r in dev if r['seed']==seed];assert len(rr)==4
            harm=sum(max(0,(ref[r['input']]['service'][k]['on_time']-r['service'][k]['on_time'])/r['service'][k]['planned']-.005)**2 for r in rr for k in ['urgent','normal'])
            energyheat=sum(r['incremental_J']/ref[r['input']]['incremental_J']+r['cost'][1]/max(.05,ref[r['input']]['cost'][1]) for r in rr)/len(rr);key=(sum(r['unfinished'] for r in rr),harm,energyheat,seed);scores.append(dict(seed=seed,key=key))
        selected=min(scores,key=lambda x:x['key'])['seed'];save(O/'SELECTION_FROZEN.json',dict(utc=now(),selected=selected,scores=scores,rule='DEV only; missing, class deficits beyond0.5pp, energy+heat, seed'));selection=sha(O/'SELECTION_FROZEN.json')
        for i,c in enumerate(phase['EVAL']):evaluate(c,'EVAL',i)
        assert count==134 and len(rows)==134 and digest(frozen.net)==frozen_sha and digest(warm.net)==warm_sha
        verify();save(O/'RESULT.json',dict(status='EVENT_ROUTE_BALANCED_PPO_COMPUTATION_COMPLETE',START=count,COMPLETE=count,FAIL=0,rows=rows,selected=selected,PPO_updates=12,BC_steps=bc_trace['steps'],scales=scales,physical_validation=False,elapsed_s=time.monotonic()-started));save(O/'COMPLETE.json',dict(utc=now(),START=count,sha256=sha(O/'RESULT.json')))
        print('EVENT_ROUTE_LEARNING_COMPLETE',count,flush=True)
    finally:
        if engine is not None:
            engine.stdin.close()
            try:engine.wait(timeout=15)
            except subprocess.TimeoutExpired:engine.terminate();engine.wait(timeout=10)
if __name__=='__main__':
    op=read(H/'OPERATION.json');O=H/'artifacts/G001';assert not O.exists(),'Consumed namespace; no automatic retry'
    for pin in op['pins']:assert sha(pin['path'])==pin['sha256']
    lock=Path(op['shared_mutex']).open('r+b');locked=False
    try:
        deadline=time.monotonic()+3600
        while not locked:
            try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
            except OSError:
                if time.monotonic()>=deadline:raise
                time.sleep(5)
        resource=snapshot_resources(1536);O.mkdir(parents=True);save(O/'START.json',dict(utc=now(),pid=os.getpid(),operation_sha256=sha(H/'OPERATION.json'),resource=resource))
        try:main(op,O)
        except BaseException as e:save(O/'FAILURE.json',dict(utc=now(),error=str(e),traceback=traceback.format_exc(),automatic_retry=False));raise
    finally:
        if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()
