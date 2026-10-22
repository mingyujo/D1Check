"""Pure FIFO/EDF extension with exact saved rolling/PPO/CEM reuse."""
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
    start=time.monotonic();count=0;rows=[];cases=read(H/'INPUTS.json')['cases'];protocol=read(H/'PROTOCOL.json');scales=read(H/'CALIBRATION_REFERENCE.json')['scales']
    def verify():
        for pin in op['pins']:assert sha(pin['path'])==pin['sha256'],'Changed pin '+pin['path']
    verify()
    for ci,c in enumerate(cases):
        methods=[(method,key,order) for key,order in protocol['resource_orders'].items() for method in ['FIFO','EDF']];shift=ci%6;methods=methods[shift:]+methods[:shift]
        for method,key,order in methods:
            verify();resource=guard(start+op['wall_cap_s']);assert count<op['environment_cap'];count+=1;label=c['id']+'__'+method+'_'+key;identity=hashlib.sha256((sha(H/'OPERATION.json')+'|'+label).encode()).hexdigest();rec=dict(event='START',utc=now(),count=count,label=label,identity=identity,kind='EVAL',input=c['id'],stream=c['stream'],method=method+'_'+key,resource=resource)
            append(O/'receipts.jsonl',rec);begin=time.monotonic()
            try:
                p=subprocess.run(['node',str(H/'server.cjs')],input=json.dumps(dict(input=c['id'],method=method,order=order))+'\n',capture_output=True,text=True,encoding='utf-8',timeout=max(1,op['wall_cap_s']-(time.monotonic()-start)))
                if p.stderr:append(O/'ENGINE_STDERR.jsonl',dict(label=label,stderr=p.stderr))
                assert p.returncode==0,'Engine exit '+str(p.returncode)
                messages=[json.loads(s) for s in p.stdout.splitlines() if s.strip()];assert len(messages)==1 and messages[0]['type']=='DONE',str(messages[0])[:500];raw=messages[0]['result'];save(O/(label+'.raw.json.gz'),raw)
                n=c['n'];row=dict(label=label,kind='EVAL',method=method+'_'+key,resource_order=order,input=c['id'],stream=c['stream'],seed=None,n=n,mix=c['mix'],replicate=c['replicate'],load=.85,service=raw['service'],unfinished=raw['unfinished'],J=raw['physics_J'],incremental_J=raw['api_energy']-raw['baseline_API_J'],AP_mean=raw['AP_mean'],AP_peak=raw['AP_peak_sampled'],baseline_J=raw['baseline_API_W']*raw['observation_end_s'],observation_s=raw['observation_end_s'],work_s=raw['actual_work_span_s'],routes=raw['policy_route_counts'],wait_s=raw['wait_s'],shared_cpu_wait_s=raw['shared_cpu_wait_s'],extra_cpu_core_s=raw['extra_cpu_core_s'],decisions=len(raw['policy_decisions']),neural_calls=0,forecast_calls=raw['forecast_calls'],scales=scales,raw_sha256=sha(O/(label+'.raw.json.gz')),reused_environment=False,physical_validation=False,wall_s=time.monotonic()-begin)
                save(O/(label+'.json'),row);rows.append(row);append(O/'receipts.jsonl',{**rec,'event':'COMPLETE','utc':now(),'raw_sha256':row['raw_sha256']});save(O/f'PROGRESS_{count:03d}.json',dict(START=count,COMPLETE=count,FAIL=0,last=row));print('PURE_BASELINE_COMPLETE',count,label,'J',round(row['J'],3),'on',row['service']['all']['on_time'],'/',n,'wall',round(row['wall_s'],1),flush=True)
            except BaseException as error:append(O/'receipts.jsonl',{**rec,'event':'FAIL','utc':now(),'error':str(error),'automatic_retry':False});raise
    parent=H.parent/'matched_ppo_cem_v1';prior=read(parent/'artifacts/G001/RESULT.json');reused=0
    for r in prior['rows']:
        if r['kind']!='EVAL' or r['method'].startswith('INITIAL'):continue
        c=next(c for c in cases if c['id']==r['input']);assert c['stream']==r['stream'];rr={**r,'reused_environment':True,'source_namespace':'matched_ppo_cem_v1','source_row_sha256':sha(parent/'artifacts/G001'/(r['label']+'.json'))}
        for suffix,key in [('.raw.json.gz','raw_sha256'),('.banks.jsonl.gz','banks_sha256')]:
            src=parent/'artifacts/G001'/(r['label']+suffix);assert sha(src)==r[key];shutil.copyfile(src,O/src.name)
        save(O/(r['label']+'.json'),rr);rows.append(rr);reused+=1;append(O/'receipts.jsonl',dict(event='REUSE',utc=now(),label=r['label'],new_environment=0,source_namespace='matched_ppo_cem_v1',raw_sha256=r['raw_sha256']))
    assert count==48 and reused==56 and len(rows)==104;verify();save(O/'RESULT.json',dict(status='COMPLETE_FIVE_POLICY_AND_ROUTE_SENSITIVITY',START=count,COMPLETE=count,FAIL=0,REUSE=reused,rows=rows,new_training=0,new_measurements=0,new_fits=0,physical_validation=False,elapsed_s=time.monotonic()-start));save(O/'COMPLETE.json',dict(utc=now(),START=count,sha256=sha(O/'RESULT.json')))
    print('FIVE_POLICY_ALL_COMPLETE',count,'REUSE',reused,flush=True)
if __name__=='__main__':
    op=read(H/'OPERATION.json');assert not O.exists(),'Consumed namespace';assert read(H/'PREFLIGHT.json')['status']=='PASS'
    lock=Path(op['shared_mutex']).open('r+b');locked=False;deadline=time.monotonic()+14400
    try:
        while not locked:
            try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
            except OSError:
                if time.monotonic()>deadline:raise
                print('WAIT_SHARED_MUTEX',flush=True);time.sleep(10)
        resource=guard(deadline);O.mkdir(parents=True);save(O/'START.json',dict(utc=now(),pid=os.getpid(),operation_sha256=sha(H/'OPERATION.json'),resource=resource))
        try:main(op)
        except BaseException as error:save(O/'FAILURE.json',dict(utc=now(),error=str(error),traceback=traceback.format_exc(),automatic_retry=False));raise
    finally:
        if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()
