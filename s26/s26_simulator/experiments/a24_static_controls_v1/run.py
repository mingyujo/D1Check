"""Two static EDF controls only; no neural inference/training, retry or device."""
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
    inputs=read(HERE/'INPUTS.json')['cases'];cases={'EVAL':inputs}
    started=time.monotonic();count=0;rows=[];selection=None;counter={'BANK':0,'deadline_guard_observed':0};learners={};update_audits=[];training_stats={}
    engine=subprocess.Popen(['node',str(HERE/'server.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=(out/'ENGINE_STDERR.txt').open('x',encoding='utf-8'),text=True,encoding='utf-8',bufsize=1)
    def send(x):engine.stdin.write(json.dumps(x,separators=(',',':'))+'\n');engine.stdin.flush()
    def simulate(case,mode,label,kind,dt=.01,stream=None):
        nonlocal count
        verify(op);assert count<op['environment_cap'] and time.monotonic()-started<op['wall_cap_s'],'Finite run cap'
        if count%8==0:assert shutil.disk_usage(HERE).free>=8*1024**3
        stream=case['stream']+case.get('case_index',0)*101 if stream is None else stream
        start=dict(event='START',label=label,kind=kind,mode=mode,input=case['id'],stream=stream,selection_sha256=selection,utc=now(),durable_consumed=True)
        append(out/'receipts.jsonl',start);count+=1;frames=[];pre=None
        print(json.dumps(dict(event='START',count=count,label=label)),flush=True)
        try:
            send(dict(input=case['id'],mode=mode,stream=stream,dt_s=dt))
            while True:
                line=engine.stdout.readline();assert line,'Engine closed unexpectedly'
                msg=json.loads(line)
                if msg['type']=='FAIL':save(out/(label+'.failed.json.gz'),msg);raise RuntimeError(msg['error'])
                if msg['type']=='DONE':r=msg['result'];break
                raise RuntimeError('NN bank prohibited in static controls')
            raw=out/(label+'.raw.json.gz');save(raw,r)
            a=r['requests'];n=len(a);responded=[q for q in a if q['response'] is not None];late=[q for q in responded if q['response']>q['deadline']+1e-9]
            assert len(responded)-len(late)+len(late)+(n-len(responded))==n
            assert r['planned_requests'] and len(r['planned_requests'])==n
            span=r['observation_end_s']-35;energy=r['api_energy']-r['baseline_API_J'];heat=max(0.,(r['AP_mean']-case['context']['initial_context']['targets']['AP']['anchor']['SKIN'])/10)
            objective=[max(0.,energy)/n,heat,0.,0.,(n-len(responded))/n]
            for q in responded:
                d=max(0.,q['response']-q['deadline']);objective[2 if q['priority']=='urgent' else 3]+=(float(d>1e-9)+.2*min(5.,d/(q['deadline']-q['arrival'])))/n
            row=dict(label=label,kind=kind,input=case['id'],nominal_load_ratio=case['nominal_load_ratio'],nominal_capacity_requests_s=case['nominal_capacity_requests_s'],policy=mode,stream=stream,n=n,rate=case['rate'],mix=case['mix'],supply_s=case['duration'],observation_s=r['observation_end_s'],work_s=r['actual_work_span_s'],service=r['service'],unfinished_AVAILABLE=r['unfinished'],response_missing=n-len(responded),api_J=r['api_energy'],baseline_API_J=r['baseline_API_J'],AP_mean=r['AP_mean'],AP_peak=r['AP_peak_sampled'],AP_outside_measurements=r['outside_marginal_AP'],wait_s=r['wait_s'],routes=r['policy_route_counts'],cost_vector=objective,weighted=sum(x*w for x,w in zip(objective,(.5,.5,8,4,30))),network_sha256=pre,raw_sha256=sha(raw),new_frames=len(frames),nominal_forecast_numerical_failures=r['nominal_compute'].get('numerical_failure_forecasts',0),adopted=False,physical_validation=False,policy_superiority_claim_allowed=False)
            save(out/(label+'.json'),row);rows.append(row);append(out/'receipts.jsonl',{**start,'event':'COMPLETE','utc':now(),'result_sha256':sha(out/(label+'.json')),'raw_sha256':sha(raw)})
            print(json.dumps(dict(event='COMPLETE',label=label,on=r['service']['all']['on_time'],n=n,API_J=row['api_J'],peak=row['AP_peak'],steps=len(frames))),flush=True)
            return row,r
        except BaseException as exc:
            assert not frames,'No neural frames are permitted'
            append(out/'receipts.jsonl',{**start,'event':'FAIL','error':str(exc),'utc':now(),'automatic_retry':False});raise
    try:
        assert (Path(op['parent_output'])/'FINAL_PROOF.json').exists(),'Preceding load comparison must finish'
        for i,c in enumerate(cases['EVAL']):
            for mode in ('EDF_CPU_RESERVED','EDF_GPU_FIXED'):simulate(c,mode,f'STATIC_{i}_{mode}','EVAL')
        assert count==op['planned_START'] and len(rows)==16;verify(op)
        save(out/'RESULT.json',dict(status='CONDITIONAL_STATIC_EDF_CONTROLS_COMPLETE',rows=rows,START=count,COMPLETE=count,FAIL=0,additional_training=0,physical_validation=False,adopted=False,elapsed_s=time.monotonic()-started,operation_sha256=sha(HERE/'OPERATION.json')))
        save(out/'COMPLETE.json',dict(utc=now(),result_sha256=sha(out/'RESULT.json'),START=count))
        print('STATIC_CONTROLS_COMPLETE',count,flush=True)
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

