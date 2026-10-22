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
def snapshot_resources(min_MiB=1024):
    import psutil
    processes=[]
    for p in psutil.process_iter(['pid','name','cmdline']):
        if (p.info['name'] or '').lower() in ['python.exe','python3.exe']:processes.append(p.info)
    assert len(processes)<=3, 'Global Python process cap3'
    assert not any(p['pid']!=os.getpid() and 'route_energy_v1' in ' '.join(p['cmdline'] or []) for p in processes),'Own study single worker'
    assert psutil.virtual_memory().available>=min_MiB*1024**2,'RAM headroom'
    assert all(shutil.disk_usage(p).free>=8*1024**3 for p in [W,Path('D:/')]),'Disk headroom'
    return dict(utc=now(),free_bytes=psutil.virtual_memory().available,python=processes)
def main(op,O):
    import numpy as np,torch
    from nn_train import Learner,digest
    torch.set_num_threads(1);count=0;rows=[];selection=None;started=time.monotonic()
    cases=read(H/'INPUTS.json')['cases'];phase={k:[c for c in cases if c['phase']==k] for k in ['P0','TRAIN','DEV','EVAL']}
    def verify():
        for p in op['pins']:assert sha(p['path'])==p['sha256'],'Changed source '+p['path']
    def load(p):return torch.load(io.BytesIO(gzip.decompress(Path(p).read_bytes())),map_location='cpu',weights_only=False)
    engine=subprocess.Popen(['node',str(H/'server.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=(O/'ENGINE_STDERR.txt').open('x'),text=True,encoding='utf-8',bufsize=1)
    def send(x):engine.stdin.write(json.dumps(x,separators=(',',':'))+'\n');engine.stdin.flush()
    def simulate(c,mode,label,kind,model,learner=None,collect=False,parent=False,balance=None):
        nonlocal count
        verify();assert count<op['environment_cap'] and time.monotonic()-started<op['wall_cap_s']
        if count%8==0:append(O/'RESOURCE_CHECKS.jsonl',snapshot_resources())
        count+=1;frames=[];pre=digest(learner.net) if learner else None
        start=dict(event='START',utc=now(),label=label,kind=kind,input=c['id'],model=model,mode=mode,seed=learner.seed if learner else None,selection_sha256=selection,stream=c['stream'],count=count)
        append(O/'receipts.jsonl',start)
        try:
            send(dict(input=c['id'],model=model,mode=mode,variant='REPAIR',stream=c['stream'],parent=parent,balance=balance))
            while True:
                line=engine.stdout.readline();assert line,'Engine closed';m=json.loads(line)
                if m['type']=='FAIL':save(O/(label+'.failed.json.gz'),m);raise RuntimeError(m['error'])
                if m['type']=='DONE':raw=m['result'];break
                assert m['type']=='BANK' and learner is not None
                bank=m['bank'];assert bank['constraints']==dict(physical_slots_only=True,deadline_action_mask=False,critical_request_override=False,fixed_ATC_prior=False,post_NN_override=False)
                index,f=learner.choose(bank,collect);f.update(time_ns=bank['time_ns'],action=bank['actions'][index],candidate_actions=bank['actions'],nominal_forecasts=bank['forecasts']);frames.append(f);send(dict(index=index))
            save(O/(label+'.raw.json.gz'),raw)
            n=c['n'];responded=[q for q in raw['requests'] if q['response'] is not None];span=raw['observation_end_s']-35;skin=c['context']['initial_context']['targets']['AP']['anchor']['SKIN']
            objective=[max(0,raw['api_energy']-raw['baseline_API_J'])/n,max(0,(raw['AP_mean']-skin)/10),0.,0.,(n-len(responded))/n]
            balanced_objective=objective.copy()
            for q in responded:
                d=max(0,q['response']-q['deadline']);j=2 if q['priority']=='urgent' else 3
                objective[j]+=(float(d>1e-9)+.2*min(5,d/(q['deadline']-q['arrival'])))/n
                balanced_objective[j]+=(float(d>1e-9)+.02*min(5,d/(q['deadline']-q['arrival'])))/n
            row=dict(label=label,kind=kind,input=c['id'],model=model,mode=mode,seed=learner.seed if learner else None,balanced=balance is not None,n=n,mix=c['mix'],load=c['nominal_load_ratio'],replicate=c['replicate'],service=raw['service'],unfinished=raw['unfinished'],J=raw['physics_J'],incremental_J=raw['api_energy']-raw['baseline_API_J'],baseline_J=raw['baseline_API_W']*raw['observation_end_s'],AP_mean=raw['AP_mean'],AP_peak=raw['AP_peak_sampled'],outside_AP=raw['outside_marginal_AP'],observation_s=raw['observation_end_s'],work_s=raw['actual_work_span_s'],routes=raw['policy_route_counts'],extra_CPU_core_s=raw.get('extra_cpu_core_s',0),shared_CPU_wait_s=raw['shared_cpu_wait_s'],wait_s=raw['wait_s'],cost=objective,balanced_cost=balanced_objective,old_weighted=sum(x*w for x,w in zip(objective,[.5,.5,8,4,30])),network_sha256=pre,frames=len(frames),raw_sha256=sha(O/(label+'.raw.json.gz')),physical_validation=False)
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
        # Four counted numerical environments, including exact parent/new K1 parity.
        c=phase['P0'][0];a,ra=simulate(c,'EDF_GPU_FIRST','P0_PARENT','P0','CENTRAL',parent=True);b,rb=simulate(c,'EDF_GPU_FIRST','P0_K1','P0','CENTRAL')
        assert abs(a['J']-b['J'])<1e-7 and abs(a['AP_mean']-b['AP_mean'])<1e-8
        assert all(abs(x['available']-y['available'])<1e-8 for x,y in zip(ra['requests'],rb['requests']))
        simulate(c,'EDF_GPU_FIRST','P0_K3','P0','CPU3');simulate(phase['P0'][1],'ATC_SALVAGE','P0_K3_ATC','P0','CPU3')
        save(O/'P0_PROOF.json',dict(parent_K1_exact=True,max_energy_error=abs(a['J']-b['J']),new_environments=4))
        parent=load(op['parent_checkpoint']);frozen=Learner(481083);frozen.restore(parent);frozen_digest=digest(frozen.net)
        references={};scales={};nets={};dual_history=[]
        for model in ['CENTRAL','CPU3']:
            ref=[]
            for i,c in enumerate(phase['TRAIN']):
                row,_=simulate(c,'RL',f'REFERENCE_{model}_{i}','TRAIN_REFERENCE',model,frozen);references[(model,c['id'])]=row;ref.append(row)
            scales[model]=[max(.05,float(np.median([r['cost'][0] for r in ref]))),max(.05,float(np.median([r['cost'][1] for r in ref])))]
            for seed in op['seeds']:
                learner=Learner(seed);learner.net.load_state_dict(parent['network']);learner.optimizer.param_groups[0]['lr']=3e-4
                with torch.no_grad():learner.net.critic[-1].weight.zero_();learner.net.critic[-1].bias.zero_()
                dual=np.ones(2);order=np.random.default_rng(seed+model.count('3')*100000).permutation(len(phase['TRAIN'])).tolist()
                save(O/f'{model}_S{seed}_ORDER.json',dict(order=order,scales=scales[model],initial_actor_parent=parent['network_sha256'],fresh_critic=True))
                pt(O/f'{model}_S{seed}_EP000.pt.gz',learner.snapshot())
                for ep,j in enumerate(order,1):
                    c=phase['TRAIN'][j];reference=references[(model,c['id'])]
                    factors=[c['n']/reference['service'][k]['planned'] for k in ['urgent','normal']]
                    balance=dict(scales=scales[model],dual=dual.tolist(),classFactors=factors,tail=.02)
                    learner.balance=copy.deepcopy(balance)
                    pt(O/f'{model}_S{seed}_EP{ep:03d}_before.pt.gz',dict(learner=learner.snapshot(),balance=balance,order=order))
                    row,_=simulate(c,'RL',f'TRAIN_{model}_S{seed}_EP{ep:03d}','TRAIN',model,learner,True,balance=balance)
                    deficits=np.array([(reference['service'][k]['on_time']-row['service'][k]['on_time'])/reference['service'][k]['planned']-.005 for k in ['urgent','normal']])
                    old=dual.copy();dual=np.clip(dual+4*deficits,.25,8.)
                    dual_history.append(dict(model=model,seed=seed,ep=ep,deficits=deficits.tolist(),before=old.tolist(),after=dual.tolist()))
                    pt(O/f'{model}_S{seed}_EP{ep:03d}_after.pt.gz',dict(learner=learner.snapshot(),dual=dual.tolist(),balance=balance,order=order))
                assert learner.episodes==16 and learner.updates==8 and not learner.pending
                learner.balance=dict(scales=scales[model],dual=dual.tolist(),classFactors=[1,1],tail=.02);nets[(model,seed)]=learner
                pt(O/f'{model}_S{seed}_FINAL.pt.gz',dict(learner=learner.snapshot(),balance=learner.balance))
        save(O/'TRAINING_COMPLETE.json',dict(scales=scales,dual_history=dual_history,updates={f'{m}_{s}':l.logs for (m,s),l in nets.items()},TRAIN=96,TRAIN_REFERENCE=32,PPO_updates=48))
        def evaluate(c,phase,i,model):
            for mode in ['EDF_GPU_FIRST','ATC','ATC_SALVAGE','ENERGY_ONLY']:simulate(c,mode,f'{phase}_{model}_{i}_{mode}',phase,model)
            simulate(c,'RL',f'{phase}_{model}_{i}_FROZEN',phase,model,frozen)
            for seed in op['seeds']:
                learner=nets[(model,seed)];balance=copy.deepcopy(learner.balance);balance['classFactors']=[1/c['mix'],1/(1-c['mix'])]
                simulate(c,'RL',f'{phase}_{model}_{i}_BALANCED_S{seed}',phase,model,learner,balance=balance)
        for model in ['CENTRAL','CPU3']:
            for i,c in enumerate(phase['DEV']):evaluate(c,'DEV',i,model)
        selected={};scores=[]
        for model in ['CENTRAL','CPU3']:
            dr=[r for r in rows if r['kind']=='DEV' and r['model']==model];ref={r['input']:r for r in dr if r['seed']==481083};options=[]
            for seed in op['seeds']:
                rr=[r for r in dr if r['seed']==seed];assert len(rr)==6
                harm=sum(max(0,(ref[r['input']]['service'][k]['on_time']-r['service'][k]['on_time'])/r['service'][k]['planned']-.005)**2 for r in rr for k in ['urgent','normal'])
                normal=sum(r['incremental_J']/ref[r['input']]['incremental_J']+r['cost'][1]/max(.05,ref[r['input']]['cost'][1]) for r in rr)/len(rr)
                key=(sum(r['unfinished'] for r in rr),harm,normal,seed);options.append((key,seed));scores.append(dict(model=model,seed=seed,key=key))
            selected[model]=min(options)[1]
        save(O/'SELECTION_FROZEN.json',dict(utc=now(),selected=selected,scores=scores,rule='missing, squared class on-time deficits beyond0.5pp, energy+heat, seed; no test access'))
        selection=sha(O/'SELECTION_FROZEN.json')
        for model in ['CENTRAL','CPU3']:
            for i,c in enumerate(phase['EVAL']):evaluate(c,'EVAL',i,model)
        assert digest(frozen.net)==frozen_digest and count==420 and len(rows)==count
        verify();save(O/'RESULT.json',dict(status='COMPUTATION_COMPLETE',START=count,COMPLETE=count,FAIL=0,rows=rows,selected=selected,PPO_updates=48,scales=scales,physical_validation=False,elapsed_s=time.monotonic()-started));save(O/'COMPLETE.json',dict(utc=now(),START=count,sha256=sha(O/'RESULT.json')))
        print('ROUTE_REWARD_CAPACITY_COMPLETE',count,flush=True)
    finally:
        engine.stdin.close()
        try:engine.wait(timeout=15)
        except subprocess.TimeoutExpired:engine.terminate();engine.wait(timeout=10)
if __name__=='__main__':
    op=read(H/'OPERATION.json');O=H/'artifacts/G001';assert not O.exists(),'Consumed namespace; no automatic retry'
    for pin in op['pins']:assert sha(pin['path'])==pin['sha256']
    lock=Path(op['shared_mutex']).open('r+b');locked=False
    try:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
        resource=snapshot_resources(2048);O.mkdir(parents=True);save(O/'START.json',dict(utc=now(),pid=os.getpid(),operation_sha256=sha(H/'OPERATION.json'),resource=resource))
        try:main(op,O)
        except BaseException as e:save(O/'FAILURE.json',dict(utc=now(),error=str(e),traceback=traceback.format_exc(),automatic_retry=False));raise
    finally:
        if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()
