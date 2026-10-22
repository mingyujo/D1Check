"""Pure RR/EDF extension with exact saved rolling/PPO/CEM reuse."""
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
    start=time.monotonic();rows=[];count=0
    def verify():
        for pin in op['pins']:assert sha(pin['path'])==pin['sha256'],'Changed pin '+pin['path']
    verify()
    for c in read(H/'INPUTS.json')['cases']:
        resource=guard(start+op['wall_cap_s']);verify();assert count<op['environment_cap'];count+=1
        label=c['id']+'__RR_GPU';rec=dict(event='START',utc=now(),count=count,label=label,identity=hashlib.sha256((sha(H/'OPERATION.json')+'|'+label).encode()).hexdigest(),input=c['id'],stream=c['stream'],method='RR')
        append(O/'receipts.jsonl',rec);begin=time.monotonic()
        try:
            p=subprocess.run(['node',str(H/'server.cjs')],input=json.dumps(dict(input=c['id'],method='RR',order=['GPU','NPU','CPU']))+'\n',capture_output=True,text=True,encoding='utf-8',timeout=max(1,op['wall_cap_s']-(time.monotonic()-start)))
            if p.stderr:append(O/'ENGINE_STDERR.jsonl',dict(label=label,stderr=p.stderr))
            assert p.returncode==0,p.stderr[-1000:];messages=[json.loads(x) for x in p.stdout.splitlines() if x.strip()];assert len(messages)==1 and messages[0]['type']=='DONE',str(messages)[:1000]
            raw=messages[0]['result'];save(O/(label+'.raw.json.gz'),raw)
            row=dict(label=label,kind='EVAL',method='RR',input=c['id'],stream=c['stream'],seed=None,n=c['n'],mix=c['mix'],load=.85,service=raw['service'],unfinished=raw['unfinished'],J=raw['physics_J'],AP_mean=raw['AP_mean'],AP_peak=raw['AP_peak_sampled'],baseline_J=raw['baseline_API_W']*raw['observation_end_s'],observation_s=raw['observation_end_s'],work_s=raw['actual_work_span_s'],extra_cpu_core_s=raw['extra_cpu_core_s'],wait_s=raw['wait_s'],raw_sha256=sha(O/(label+'.raw.json.gz')),resource_order=['GPU','NPU','CPU'],reused_environment=False,physical_validation=False,wall_s=time.monotonic()-begin,resource=resource)
            save(O/(label+'.json'),row);rows.append(row);append(O/'receipts.jsonl',{**rec,'event':'COMPLETE','utc':now(),'raw_sha256':row['raw_sha256']});print('RR_COMPLETE',count,label,round(row['J'],3),row['service']['all']['on_time'],flush=True)
        except BaseException as e:append(O/'receipts.jsonl',{**rec,'event':'FAIL','error':str(e),'automatic_retry':False});raise
    for reuse in read(H/'REUSE_PLAN.json')['rows']:
        source=reuse['row'];assert sha(reuse['row_path'])==reuse['row_sha256'] and sha(reuse['raw_path'])==source['raw_sha256']
        label='REUSE_'+reuse['method']+'_'+source['label'];shutil.copyfile(reuse['raw_path'],O/(label+'.raw.json.gz'))
        c=next(c for c in read(H/'INPUTS.json')['cases'] if c['id']==source['input'])
        row={**source,'label':label,'source_label':source['label'],'method':reuse['method'],'stream':c['stream'],'extra_cpu_core_s':source.get('extra_cpu_core_s',source.get('extra_CPU_core_s',0)),'reused_environment':True,'reuse_proof':{k:v for k,v in reuse.items() if k!='row'}}
        save(O/(label+'.json'),row);rows.append(row);append(O/'receipts.jsonl',dict(event='REUSE',utc=now(),label=label,input=c['id'],method=row['method'],raw_sha256=row['raw_sha256'],new_environment=0))
    verify();assert count==4 and len(rows)==16
    save(O/'RESULT.json',dict(status='COMPLETE_FIFO_EDF_RR_ADOPTED_POLICY',START=4,COMPLETE=4,FAIL=0,REUSE=12,rows=rows,new_training=0,new_measurements=0,new_fits=0,physical_validation=False))
    print('FINAL_FOUR_RR_ALL_COMPLETE',flush=True)
if __name__=='__main__':
    op=read(H/'OPERATION.json');assert not O.exists() and read(H/'PREFLIGHT.json')['status']=='PASS';lock=Path(op['shared_mutex']).open('r+b');locked=False;deadline=time.monotonic()+14400
    try:
        while not locked:
            try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
            except OSError:
                if time.monotonic()>deadline:raise
                print('WAIT_SHARED_MUTEX',flush=True);time.sleep(10)
        resource=guard(deadline);O.mkdir(parents=True);save(O/'START.json',dict(utc=now(),pid=os.getpid(),operation_sha256=sha(H/'OPERATION.json'),resource=resource))
        try:main(op)
        except BaseException as e:save(O/'FAILURE.json',dict(utc=now(),error=str(e),traceback=traceback.format_exc(),automatic_retry=False));raise
    finally:
        if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()
