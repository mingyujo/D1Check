"""Finite matched rolling comparison. Evaluation only; never trains or retries."""
import datetime,gzip,hashlib,io,json,msvcrt,os,subprocess,sys,time,traceback
from pathlib import Path
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
H=Path(__file__).resolve().parent;R=H.parents[1];W=H.parents[3];O=H/'artifacts/G001'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(p,x):
    b=json.dumps(x,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
    if Path(p).suffix=='.gz':b=gzip.compress(b,compresslevel=3,mtime=0)
    with Path(p).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def append(x):
    with (O/'receipts.jsonl').open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(x,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
def guard(deadline):
    import gc,psutil
    last=0
    while True:
        gc.collect();procs=[p.info for p in psutil.process_iter(['pid','name','cmdline']) if (p.info['name'] or '').lower() in ['python.exe','python3.exe']]
        free=psutil.virtual_memory().available
        disks={str(p):__import__('shutil').disk_usage(p).free for p in [W,Path('D:/')]}
        if len(procs)<=3 and free>=1536*1024**2 and min(disks.values())>=8*1024**3:return dict(utc=now(),free_bytes=free,python=procs,disk_free=disks)
        if time.monotonic()>=deadline:raise RuntimeError('Resource wait reached finite wall limit before START')
        if time.monotonic()-last>30:print('RESOURCE_WAIT',len(procs),round(free/1048576),flush=True);last=time.monotonic()
        time.sleep(5)
def main(op):
    import numpy as np,torch
    from nn_train import Net,digest
    from selection_rules import cost_rule,teacher_rule
    torch.set_num_threads(1)
    models={};before={}
    for seed in op['seeds']:
        checkpoint=Path(op['checkpoint_directory'])/f'S{seed}_FINAL.pt.gz'
        snap=torch.load(io.BytesIO(gzip.decompress(checkpoint.read_bytes())),map_location='cpu',weights_only=False)['learner']
        net=Net();net.load_state_dict(snap['network']);net.temperature=snap.get('temperature',.35);net.eval();models[seed]=net;before[seed]=digest(net)
    cases=read(H/'INPUTS.json')['cases'];rows=[];count=0;engine=None;started=time.monotonic()
    for c in cases:
        order=['ROLLING_COST','TEACHER_RULE',*[f'RL{s}' for s in op['seeds']]];shift=cases.index(c)%5;order=order[shift:]+order[:shift]
        for method in order:
            for pin in op['pins']:
                if sha(pin['path'])!=pin['sha256']:raise RuntimeError('Changed pinned source: '+pin['path'])
            if count>=op['environment_cap'] or time.monotonic()-started>=op['wall_cap_s']:raise RuntimeError('Finite comparison cap exceeded')
            resource=guard(started+op['wall_cap_s']);seed=int(method[2:]) if method.startswith('RL') else None
            label=f'{c["id"]}__{method}';identity=hashlib.sha256((sha(H/'OPERATION.json')+'|'+label).encode()).hexdigest()
            count+=1;receipt=dict(event='START',utc=now(),label=label,identity=identity,count=count,input=c['id'],stream=c['stream'],method=method,seed=seed,resource=resource)
            append(receipt);case_begin=time.monotonic();decisions=0
            bank_partial=O/(label+'.banks.jsonl.gz.partial');bank_final=O/(label+'.banks.jsonl.gz')
            bank_file=bank_partial.open('xb');bank_gzip=gzip.GzipFile(filename='',mode='wb',fileobj=bank_file,compresslevel=3,mtime=0)
            engine=subprocess.Popen(['node',str(H/'server.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=(O/'ENGINE_STDERR.txt').open('a'),text=True,encoding='utf-8',bufsize=1)
            def send(x):engine.stdin.write(json.dumps(x,separators=(',',':'))+'\n');engine.stdin.flush()
            try:
                send(dict(input=c['id']))
                while True:
                    line=engine.stdout.readline()
                    if not line:raise RuntimeError('Engine closed before completion')
                    message=json.loads(line)
                    if message['type']=='FAIL':save(O/(label+'.failed.json.gz'),message);raise RuntimeError(message['error'])
                    if message['type']=='DONE':raw=message['result'];break
                    bank=message['bank']
                    assert bank['constraints']==dict(physical_slots_only=True,deadline_action_mask=False,critical_request_override=False,fixed_ATC_prior=False,post_NN_override=False)
                    if method=='ROLLING_COST':index=cost_rule(bank)
                    elif method=='TEACHER_RULE':index=teacher_rule(bank)
                    else:
                        with torch.no_grad():
                            logits,_=models[seed](torch.from_numpy(np.asarray(bank['x'],np.float32))[None],torch.from_numpy(np.asarray(bank['mask'],bool))[None]);index=int(logits[0].argmax())
                    assert bank['mask'][index]
                    bank_gzip.write((json.dumps(dict(bank=bank,index=index),ensure_ascii=False,separators=(',',':'))+'\n').encode());decisions+=1;send(dict(index=index))
                bank_gzip.close();bank_file.flush();os.fsync(bank_file.fileno());bank_file.close();assert not bank_final.exists();os.replace(bank_partial,bank_final)
                save(O/(label+'.raw.json.gz'),raw)
                row=dict(label=label,input=c['id'],stream=c['stream'],method=method,seed=seed,n=c['n'],mix=c['mix'],replicate=c['replicate'],
                    service=raw['service'],unfinished=raw['unfinished'],J=raw['physics_J'],AP_mean=raw['AP_mean'],AP_peak=raw['AP_peak_sampled'],
                    baseline_J=raw['baseline_API_W']*raw['observation_end_s'],observation_s=raw['observation_end_s'],work_s=raw['actual_work_span_s'],
                    routes=raw['policy_route_counts'],wait_s=raw['wait_s'],shared_cpu_wait_s=raw['shared_cpu_wait_s'],extra_cpu_core_s=raw['extra_cpu_core_s'],
                    decisions=decisions,neural_calls=decisions if seed else 0,network_sha256=before[seed] if seed else None,
                    raw_sha256=sha(O/(label+'.raw.json.gz')),banks_sha256=sha(bank_final),physical_validation=False,wall_s=time.monotonic()-case_begin)
                save(O/(label+'.json'),row);rows.append(row);append({**receipt,'event':'COMPLETE','utc':now(),'raw_sha256':row['raw_sha256']})
                save(O/f'PROGRESS_{count:03d}.json',dict(START=count,COMPLETE=len(rows),FAIL=0,last=row))
                print('FAIR_COMPLETE',count,method,'J',round(row['J'],5),'on',row['service']['all']['on_time'],'AP',round(row['AP_mean'],5),'wall',round(row['wall_s'],1),flush=True)
            except BaseException as error:
                append({**receipt,'event':'FAIL','utc':now(),'error':str(error),'automatic_retry':False});raise
            finally:
                if not bank_file.closed:bank_gzip.close();bank_file.flush();os.fsync(bank_file.fileno());bank_file.close()
                engine.stdin.close()
                try:engine.wait(timeout=20)
                except subprocess.TimeoutExpired:engine.terminate();engine.wait(timeout=10)
                engine=None
    assert count==40 and len(rows)==40
    assert all(digest(models[seed])==before[seed] for seed in models)
    for pin in op['pins']:assert sha(pin['path'])==pin['sha256']
    save(O/'RESULT.json',dict(status='COMPLETE_MATCHED_ROLLING_RL_EVALUATION',START=count,COMPLETE=len(rows),FAIL=0,rows=rows,
        network_hashes=before,new_training=0,new_PPO_updates=0,new_fits=0,physical_validation=False,elapsed_s=time.monotonic()-started))
    save(O/'COMPLETE.json',dict(utc=now(),START=count,sha256=sha(O/'RESULT.json')))
    print('FAIR_ALL_COMPLETE',count,flush=True)
if __name__=='__main__':
    op=read(H/'OPERATION.json');assert not O.exists(),'Consumed namespace; no automatic retry'
    assert read(H/'PREFLIGHT.json')['status']=='PASS'
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
