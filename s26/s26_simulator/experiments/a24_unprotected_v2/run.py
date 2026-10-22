"""One frozen S26/A24 unprotected PPO batch; no retry, device or old experiment."""
import copy,datetime,gzip,hashlib,io,json,msvcrt,os,shutil,subprocess,sys,time,traceback
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
    inputs=read(HERE/'INPUTS.json')['cases'];by={c['id']:c for c in inputs};cases={p:[c for c in inputs if c['phase']==p] for p in ('TRAIN','DEV','EVAL')}
    # Pure NN smoke uses a separate seed and never creates a simulator environment.
    toy=Learner(271079);bank=dict(x=np.zeros((27,32),np.float32),mask=np.array([True,True]+[False]*25),scores=np.array([0.,1.]+[0.]*25,np.float32))
    initial=digest(toy.net)
    for k in range(2):
        _,f=toy.choose(bank,True);f['time_ns']=0;toy.add([f],np.array([[.1,.1,.2,0.,0.]]))
    assert toy.updates==1 and digest(toy.net)!=initial
    snap=toy.snapshot();a=toy.choose(bank,False)[0];clone=Learner(271079);clone.restore(snap);assert clone.choose(bank,False)[0]==a
    save(out/'PURE_NN.json',dict(status='PASS_INITIALIZATION_GRADIENT_AND_CHECKPOINT',real_environment_instances=0,synthetic_update=toy.updates,checkpoint_roundtrip=True))
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
                index,frame=learner.choose(bank,collect);frame['time_ns']=bank['time_ns'];frame['action']=bank['actions'][index];frame['candidate_actions']=bank['actions'];frame['ready_total']=bank['ready_total'];frame['forecast_ready']=bank['forecast_ready'];frames.append(frame);counter['BANK']+=1;send(dict(index=index))
            raw=out/(label+'.raw.json.gz');save(raw,r)
            a=r['requests'];n=len(a);responded=[q for q in a if q['response'] is not None];late=[q for q in responded if q['response']>q['deadline']+1e-9]
            assert len(responded)-len(late)+len(late)+(n-len(responded))==n
            assert r['planned_requests'] and len(r['planned_requests'])==n
            span=r['observation_end_s']-35;energy=r['api_energy']-r['baseline_API_J'];heat=max(0.,(r['AP_mean']-case['context']['initial_context']['targets']['AP']['anchor']['SKIN'])/10)
            objective=[max(0.,energy)/n,heat,0.,0.,(n-len(responded))/n]
            for q in responded:
                d=max(0.,q['response']-q['deadline']);objective[2 if q['priority']=='urgent' else 3]+=(float(d>1e-9)+.2*min(5.,d/(q['deadline']-q['arrival'])))/n
            row=dict(label=label,kind=kind,input=case['id'],policy=mode,stream=stream,n=n,rate=case['rate'],mix=case['mix'],supply_s=case['duration'],observation_s=r['observation_end_s'],work_s=r['actual_work_span_s'],service=r['service'],unfinished_AVAILABLE=r['unfinished'],response_missing=n-len(responded),api_J=r['api_energy'],baseline_API_J=r['baseline_API_J'],AP_mean=r['AP_mean'],AP_peak=r['AP_peak_sampled'],AP_outside_measurements=r['outside_marginal_AP'],wait_s=r['wait_s'],routes=r['policy_route_counts'],cost_vector=objective,weighted=sum(x*w for x,w in zip(objective,(.5,.5,8,4,30))),network_sha256=pre,raw_sha256=sha(raw),new_frames=len(frames),adopted=False,physical_validation=False,policy_superiority_claim_allowed=False)
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
        # Four actual numerical trials; no old policy environment is repeated.
        p0=[];case=cases['DEV'][0]
        for mode in ('EDF','ATC'):
            pair=[]
            for suffix,dt in [('COARSE',.01),('FINE',.005)]:
                if mode=='EDF' and suffix=='COARSE':
                    inherited=read(HERE/'INHERITED_P0.json');r=read(inherited['raw']);row=read(inherited['row']);row['inherited_operational_FAIL']=True;row['source_raw']=inherited['raw'];shutil.copyfile(inherited['raw'],out/'P0_EDF_COARSE.raw.json.gz');save(out/'P0_EDF_COARSE.json',row);rows.append(row);save(out/'INHERITED_P0.json',inherited);pair.append(r)
                else:pair.append(simulate(case,mode,'P0_'+mode+'_'+suffix,'P0',dt=dt,stream=271070001)[1])
            worst=0.
            for a,b in zip(pair[0]['requests'],pair[1]['requests']):
                assert a['ordinal']==b['ordinal'] and a['route']==b['route'],'P0 numerical route mismatch'
                for key in ('response','available'):
                    if a[key] is not None and b[key] is not None:worst=max(worst,abs(a[key]-b[key]))
                    else:assert a[key] is b[key]
            er=abs(pair[0]['api_energy']-pair[1]['api_energy'])/max(1,abs(pair[1]['api_energy']));ta=abs(pair[0]['AP_mean']-pair[1]['AP_mean']);assert worst<.01 and er<.001 and ta<.02,'P0 numeric tolerance'
            p0.append(dict(mode=mode,max_clock_difference_s=worst,relative_energy_error=er,mean_AP_difference_C=ta))
        save(out/'P0.json',dict(status='PASS',rows=p0))
        for seed in op['seeds']:
            learner=Learner(seed);learners[seed]=learner;pt(out/(f'S{seed}_EP000.pt.gz'),learner.snapshot());rng=np.random.default_rng(seed)
            for ep in range(1,129):
                case_rng_before=copy.deepcopy(rng.bit_generator.state)
                case=cases["TRAIN"][int(rng.integers(len(cases["TRAIN"])))];save(out/(f"S{seed}_EP{ep:03d}_case_rng.json"),dict(before=case_rng_before,after=copy.deepcopy(rng.bit_generator.state),selected_input=case["id"],original_saved_state=True));before=learner.snapshot();pt(out/(f'S{seed}_EP{ep:03d}_before.pt.gz'),before)
                row,_=simulate(case,'RL',f'S{seed}_TRAIN_{ep:03d}','TRAIN',learner,True,stream=271000000+seed*1000+ep)
                after=learner.snapshot();pt(out/(f'S{seed}_EP{ep:03d}_after.pt.gz'),after)
                if after['updates']>before['updates']:
                    assert after['network_sha256']!=before['network_sha256'],'Update did not change network';update_audits.append(dict(seed=seed,episode=ep,update=after['updates'],before=before['network_sha256'],after=after['network_sha256']))
                if ep in (64,128):pt(out/(f'S{seed}_EP{ep:03d}.pt.gz'),after)
            assert learner.updates==64 and learner.steps>0
            training_stats[seed]=dict(episodes=learner.episodes,updates=learner.updates,Adam_steps=learner.steps,network_sha256=digest(learner.net))
        save(out/'TRAINING_COMPLETE.json',dict(status='ALL_THREE_SEEDS_TRAINED',by_seed=training_stats,updates=update_audits))
        dev_edf=[]
        for i,c in enumerate(cases['DEV']):c['case_index']=i;dev_edf.append(simulate(c,'EDF','DEV_EDF_'+str(i),'DEV')[0])
        selected={};devscores=[]
        for seed in op['seeds']:
            options=[]
            for ep in (64,128):
                learner=learners[seed];snap=torch.load(io.BytesIO(gzip.decompress((out/f'S{seed}_EP{ep:03d}.pt.gz').read_bytes())),map_location='cpu',weights_only=False);learner.restore(snap);rr=[]
                for i,c in enumerate(cases['DEV']):rr.append(simulate(c,'RL',f'DEV_S{seed}_EP{ep}_{i}','DEV',learner)[0])
                key=(sum(r['response_missing'] for r in rr),sum(b['service']['all']['on_time']-r['service']['all']['on_time'] for b,r in zip(dev_edf,rr)),sum(b['service']['urgent']['on_time']-r['service']['urgent']['on_time'] for b,r in zip(dev_edf,rr)),sum(r['weighted'] for r in rr)/len(rr),ep)
                options.append((key,ep));devscores.append(dict(seed=seed,episode=ep,key=key))
            selected[seed]=min(options)[1]
        chosen_seed=min(op['seeds'],key=lambda s:next(x['key'] for x in devscores if x['seed']==s and x['episode']==selected[s]))
        save(out/'SELECTION_FROZEN.json',dict(per_seed=selected,primary_seed=chosen_seed,scores=devscores,rule='missing,total on-time harm,urgent harm,weighted,episode',utc=now()));selection=sha(out/'SELECTION_FROZEN.json')
        for seed in op['seeds']:
            snap=torch.load(io.BytesIO(gzip.decompress((out/f'S{seed}_EP{selected[seed]:03d}.pt.gz').read_bytes())),map_location='cpu',weights_only=False);learners[seed].restore(snap)
        for i,c in enumerate(cases['EVAL']):
            c['case_index']=i
            for mode in ('EDF','EDF_NPU_FIRST','ATC','EXACT'):simulate(c,mode,f'EVAL_{i}_{mode}','EVAL')
            for seed in op['seeds']:simulate(c,'RL',f'EVAL_{i}_S{seed}','EVAL',learners[seed])
        assert count==op['planned_START'] and len(rows)==528;verify(op)
        save(out/'RESULT.json',dict(status='CONDITIONAL_UNPROTECTED_A24_TO_S26_COMPLETE',rows=rows,selected=selected,primary_seed=chosen_seed,START=count,COMPLETE=count,FAIL=0,imported_prior_operational_FAIL=1,combined_START=count+1,combined_COMPLETE_receipts=count,combined_FAIL=1,computed_saved_rows=len(rows),physical_validation=False,adopted=False,new_measurements=0,new_physical_fit=0,elapsed_s=time.monotonic()-started,operation_sha256=sha(HERE/'OPERATION.json')))
        save(out/'LEARNING_AUDIT.json',dict(status='PASS_UPDATES_CHANGED_NETWORK_AND_DENSE_LABELS',updates=update_audits,counters=counter,training_stats=training_stats,selected_snapshots={s:dict(updates=l.updates,Adam_steps=l.steps,episodes=l.episodes,sha=digest(l.net)) for s,l in learners.items()},independent_replay_pending=True))
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
        out.mkdir(parents=True);save(out/'START.json',dict(utc=now(),pid=os.getpid(),operation_sha256=sha(HERE/'OPERATION.json'),process_snapshot=ps))
        try:main(op,out)
        except BaseException:save(out/'FAILURE.json',dict(traceback=traceback.format_exc(),automatic_retry=False));raise
    finally:
        if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()
