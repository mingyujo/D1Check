"""One frozen S26/A24 unprotected PPO batch; no retry, device or old experiment."""
import ast,copy,datetime,gzip,hashlib,io,json,msvcrt,os,shutil,subprocess,sys,time,traceback
from pathlib import Path
for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[key]='1'
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def read(p):
    p=Path(p);return json.loads((gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes()).decode('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(p,x):
    p=Path(p);b=json.dumps(x,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
    if p.suffix=='.gz':b=gzip.compress(b,compresslevel=5,mtime=0)
    with p.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def append(p,x):
    with Path(p).open('a',encoding='utf-8') as f:f.write(json.dumps(x,ensure_ascii=False,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
def verify(op):
    for x in op['pins']:assert sha(x['path'])==x['sha256'],'Changed pin '+x['path']
def processes():
    cmd='[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); Get-CimInstance Win32_Process -Filter "Name = \'python.exe\' OR Name = \'python3.exe\'" | Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress'
    raw=subprocess.check_output(['powershell','-NoProfile','-Command',cmd],text=True,encoding='utf-8');p=json.loads(raw or '[]');return [p] if isinstance(p,dict) else p

def main(op,out):
    import numpy as np,torch
    from nn_train import Learner,digest
    torch.set_num_threads(1)
    inputs=read(HERE/'INPUTS.json')['cases'];cases={'EVAL':inputs}
    started=time.monotonic();count=0;rows=[];selection=None;counter={'BANK':0,'deadline_guard_observed':0};learners={};update_audits=[];training_stats={}
    engine=subprocess.Popen(['node',str(HERE/'server.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=(out/'ENGINE_STDERR.txt').open('x',encoding='utf-8'),text=True,encoding='utf-8',bufsize=1)
    def send(x):engine.stdin.write(json.dumps(x,separators=(',',':'))+'\n');engine.stdin.flush()
    def pt(p,x):
        b=io.BytesIO();torch.save(x,b)
        with Path(p).open('xb') as f:f.write(gzip.compress(b.getvalue(),compresslevel=4,mtime=0))
    def simulate(case,mode,label,kind,learner=None,collect=False,dt=.01,stream=None):
        nonlocal count
        verify(op);assert count<op['environment_cap'] and time.monotonic()-started<op['wall_cap_s'],'Finite run cap'
        if count%8==0:assert shutil.disk_usage(HERE).free>=8*1024**3
        stream=case['stream']+case.get('case_index',0)*101 if stream is None else stream
        start=dict(event='START',label=label,kind=kind,mode=mode,input=case['id'],stream=stream,selection_sha256=selection,utc=now(),durable_consumed=True)
        append(out/'receipts.jsonl',start);count+=1;frames=[];pre=digest(learner.net) if learner else None
        print(json.dumps(dict(event='START',count=count,label=label)),flush=True)
        try:
            send(dict(input=case['id'],mode=mode,stream=stream,dt_s=dt))
            while True:
                line=engine.stdout.readline();assert line,'Engine closed unexpectedly'
                msg=json.loads(line)
                if msg['type']=='FAIL':save(out/(label+'.failed.json.gz'),msg);raise RuntimeError(msg['error'])
                if msg['type']=='DONE':r=msg['result'];break
                assert msg['type']=='BANK' and learner is not None
                bank=msg['bank'];con=bank['constraints'];assert con==dict(physical_slots_only=True,deadline_action_mask=False,critical_request_override=False,fixed_ATC_prior=False,post_NN_override=False)
                index,frame=learner.choose(bank,collect);frame['time_ns']=bank['time_ns'];frame['action']=bank['actions'][index];frame['candidate_actions']=bank['actions'];frame['nominal_forecasts']=bank['forecasts'];frame['ready_total']=bank['ready_total'];frame['forecast_ready']=bank['forecast_ready'];frames.append(frame);counter['BANK']+=1;send(dict(index=index))
            raw=out/(label+'.raw.json.gz');save(raw,r)
            a=r['requests'];n=len(a);responded=[q for q in a if q['response'] is not None];late=[q for q in responded if q['response']>q['deadline']+1e-9]
            assert len(responded)-len(late)+len(late)+(n-len(responded))==n
            assert r['planned_requests'] and len(r['planned_requests'])==n
            span=r['observation_end_s']-35;energy=r['api_energy']-r['baseline_API_J'];heat=max(0.,(r['AP_mean']-case['context']['initial_context']['targets']['AP']['anchor']['SKIN'])/10)
            objective=[max(0.,energy)/n,heat,0.,0.,(n-len(responded))/n]
            for q in responded:
                d=max(0.,q['response']-q['deadline']);objective[2 if q['priority']=='urgent' else 3]+=(float(d>1e-9)+.2*min(5.,d/(q['deadline']-q['arrival'])))/n
            row=dict(label=label,kind=kind,input=case['id'],nominal_load_ratio=case['nominal_load_ratio'],nominal_capacity_requests_s=case['nominal_capacity_requests_s'],policy=mode,stream=stream,n=n,rate=case['rate'],mix=case['mix'],supply_s=case['duration'],observation_s=r['observation_end_s'],work_s=r['actual_work_span_s'],service=r['service'],unfinished_AVAILABLE=r['unfinished'],response_missing=n-len(responded),api_J=r['api_energy'],baseline_API_J=r['baseline_API_J'],AP_mean=r['AP_mean'],AP_peak=r['AP_peak_sampled'],AP_outside_measurements=r['outside_marginal_AP'],wait_s=r['wait_s'],routes=r['policy_route_counts'],cost_vector=objective,weighted=sum(x*w for x,w in zip(objective,(.5,.5,8,4,30))),network_sha256=pre,raw_sha256=sha(raw),new_frames=len(frames),nominal_forecast_numerical_failures=r['nominal_compute'].get('numerical_failure_forecasts',0),adopted=False,physical_validation=False,policy_superiority_claim_allowed=False)
            if learner:
                times=np.array([f['time_ns'] for f in frames],dtype=np.int64);cost=np.zeros((len(frames),5),np.float64);assert len(times)>0 and np.all(np.diff(times)>=0)
                def idx(t):return max(0,min(len(times)-1,int(np.searchsorted(times,round(t*1e9),side='right'))-1))
                for t0,t1,J,H in r['integrals']:
                    cost[idx(t0),0]+=(J-r['baseline_API_W']*(t1-t0))/n
                    if heat>0:cost[idx(t0),1]+=(H-case['context']['initial_context']['targets']['AP']['anchor']['SKIN']*(t1-t0))/(span*10)
                for q in responded:
                    d=max(0.,q['response']-q['deadline']);cost[idx(q['response']),2 if q['priority']=='urgent' else 3]+=(float(d>1e-9)+.2*min(5.,d/(q['deadline']-q['arrival'])))/n
                cost[-1,4]=objective[4];error=float(np.max(abs(cost.sum(0)-np.array(objective))));assert error<1e-7,'Dense reward/final cost mismatch'
                row['reward_telescope_error']=error
                pt(out/(label+'.frames.pt.gz'),dict(frames=frames,costs=cost,collect=collect,network_sha256=pre,physical_only_mask=True,objective=objective))
                if collect:learner.add(frames,cost)
            save(out/(label+'.json'),row);rows.append(row);append(out/'receipts.jsonl',{**start,'event':'COMPLETE','utc':now(),'result_sha256':sha(out/(label+'.json')),'raw_sha256':sha(raw)})
            print(json.dumps(dict(event='COMPLETE',label=label,on=r['service']['all']['on_time'],n=n,API_J=row['api_J'],peak=row['AP_peak'],steps=len(frames))),flush=True)
            return row,r
        except BaseException as exc:
            if frames:pt(out/(label+'.partial_frames.pt.gz'),frames)
            append(out/'receipts.jsonl',{**start,'event':'FAIL','error':str(exc),'utc':now(),'automatic_retry':False});raise
    try:
        parent=Path(op['parent_output']);assert (parent/'FINAL_PROOF.json').exists(),'Parent audits/report must finish first'
        selected_record=read(parent/'SELECTION_FROZEN.json');selected=selected_record['per_seed'];chosen_seed=selected_record['primary_seed'];shutil.copyfile(parent/'SELECTION_FROZEN.json',out/'SELECTION_FROZEN.json');selection=sha(out/'SELECTION_FROZEN.json')
        for seed in op['seeds']:
            learner=Learner(seed);snap=torch.load(io.BytesIO(gzip.decompress((parent/f'S{seed}_EP{selected[str(seed)]:03d}.pt.gz').read_bytes())),map_location='cpu',weights_only=False);learner.restore(snap);learners[seed]=learner
        before_network={seed:digest(l.net) for seed,l in learners.items()}
        for i,c in enumerate(cases['EVAL']):
            for mode in ('EDF','EDF_NPU_FIRST','EDF_GPU_FIRST','ATC','EXACT'):simulate(c,mode,f'MARGIN_{i}_{mode}','EVAL')
            for seed in op['seeds']:simulate(c,'RL',f'MARGIN_{i}_S{seed}','EVAL',learners[seed])
        assert all(digest(l.net)==before_network[seed] for seed,l in learners.items()),'Evaluation changed frozen NN'
        assert count==op['planned_START'] and len(rows)==64;verify(op)
        save(out/'RESULT.json',dict(status='CONDITIONAL_LOAD_MARGIN_COMPARISON_COMPLETE',rows=rows,selected=selected,primary_seed=chosen_seed,START=count,COMPLETE=count,FAIL=0,additional_training=0,computed_saved_rows=len(rows),physical_validation=False,adopted=False,new_measurements=0,new_physical_fit=0,elapsed_s=time.monotonic()-started,operation_sha256=sha(HERE/'OPERATION.json')))
        save(out/'LEARNING_AUDIT.json',dict(status='PASS_FROZEN_NN_NO_NEW_UPDATES',updates=update_audits,counters=counter,training_stats=training_stats,selected_snapshots={s:dict(updates=l.updates,Adam_steps=l.steps,episodes=l.episodes,sha=digest(l.net)) for s,l in learners.items()},independent_replay_pending=True))
        save(out/'COMPLETE.json',dict(utc=now(),result_sha256=sha(out/'RESULT.json'),START=count,elapsed_s=time.monotonic()-started))
        print('COMPLETE_BATCH',count,flush=True)
    finally:
        engine.stdin.close()
        try:engine.wait(timeout=20)
        except subprocess.TimeoutExpired:engine.terminate();engine.wait(timeout=10)

if __name__=='__main__':
    op=read(HERE/'OPERATION.json');verify(op);out=Path(op['output']);assert not out.exists(),'Consumed operation; no relaunch'
    lock=Path(op['shared_mutex']).open('r+b');locked=False
    try:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
        ps=processes();assert len({p['ProcessId'] for p in ps}-{p['ParentProcessId'] for p in ps})<=2,'Global Python leaves'
        assert not any(p['ProcessId']!=os.getpid() and any(t in(p.get('CommandLine')or'') for t in('a24_simulator','s26_simulator')) for p in ps),'Other simulator'
        assert shutil.disk_usage(HERE).free>=8*1024**3 and shutil.disk_usage('D:/').free>=8*1024**3
        static_files=[]
        for p in HERE.glob('*.py'):
            tree=ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p));assert not any(isinstance(k,ast.Name) for n in ast.walk(tree) if isinstance(n,ast.Dict) for k in n.keys),'Bare literal dictionary key';static_files.append(str(p))
        out.mkdir(parents=True);save(out/'START.json',dict(utc=now(),pid=os.getpid(),operation_sha256=sha(HERE/'OPERATION.json'),process_snapshot=ps))
        save(out/'STATIC_CHECK.json',dict(status='PASS_AST_AND_NO_BARE_LITERAL_KEYS',files=static_files,new_environment_instances=0))
        try:main(op,out)
        except BaseException:save(out/'FAILURE.json',dict(traceback=traceback.format_exc(),automatic_retry=False));raise
    finally:
        if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()

