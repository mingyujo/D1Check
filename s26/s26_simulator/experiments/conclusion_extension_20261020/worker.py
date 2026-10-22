"""Frozen inference and registered finite320 evaluation only; no training/retry."""
import datetime,gzip,hashlib,io,json,msvcrt,os,shutil,subprocess,sys,threading,time,traceback
from pathlib import Path
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
H=Path(__file__).resolve().parent;R=H.parents[2];S=R/'s26_simulator';F=S/'experiments/rolling_rl_ablation_v1';O=H/'artifacts/G001'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(p,x):
 b=json.dumps(x,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
 if p.suffix=='.gz':b=gzip.compress(b,compresslevel=3,mtime=0)
 with p.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def append(x):
 with (O/'receipts.jsonl').open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(x,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
def guard(op):
 import ctypes
 class Memory(ctypes.Structure):_fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in ['physical','available','page','freepage','virtual','freevirtual','extended']]
 m=Memory();m.length=ctypes.sizeof(m);assert ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
 count=int(subprocess.check_output(['powershell','-NoProfile','-Command','@(Get-Process python* -ErrorAction SilentlyContinue).Count'],text=True).strip())
 disks={v:shutil.disk_usage(v).free for v in [str(R),'D:/']}
 assert count<=op['global_Python_limit'],'Global Python cap';assert m.available>=op['minimum_free_memory_bytes'],'Memory floor';assert min(disks.values())>=op['disk_min_free_bytes'],'Disk floor'
 return dict(python_processes=count,free_memory_bytes=m.available,disk_free=disks)
def pins(op):
 assert sha(H/'PROTOCOL.json')==op['protocol_sha256']
 for p in op['original_pins']+op['new_source_pins']:assert sha(R/p['path'])==p['sha256'],p['path']
def models(protocol):
 import numpy as np,torch
 sys.path.insert(0,str(F));from nn_train import Net,digest
 torch.set_num_threads(1);nets={};before={}
 for name,key,shakey in [('BC','checkpoint','checkpoint_sha256'),('PPO','ppo_checkpoint','ppo_checkpoint_sha256')]:
  p=R/protocol[key];assert sha(p)==protocol[shakey]
  d=torch.load(io.BytesIO(gzip.decompress(p.read_bytes())),map_location='cpu',weights_only=False)['learner'];net=Net();net.load_state_dict(d['network']);net.temperature=d['temperature'];net.eval();assert net.temperature==.35
  nets[name]=net;before[name]=digest(net)
 assert before['BC']==protocol['network_sha256']
 def choose(name,x,mask):
  a=np.asarray(x,np.float32);b=np.asarray(mask,bool);assert a.shape==(27,32) and b.shape==(27,) and b.any() and np.isfinite(a).all()
  with torch.no_grad():logits,_=nets[name](torch.from_numpy(a)[None],torch.from_numpy(b)[None]);i=int(logits[0].argmax());logp=float(logits.log_softmax(-1)[0,i]);valid=logits[0][torch.from_numpy(b)].sort(descending=True).values;gap=float(valid[0]-valid[1]) if len(valid)>1 else None
  assert b[i];return i,logp,gap
 return nets,before,choose,digest,torch,np
def deterministic(m,b):
 valid=[i for i,v in enumerate(b['mask']) if v]
 if m['selector']=='TEACHER':
  preferred=[i for i in valid if b['actions'][i]['kind']=='DISPATCH' and b['x'][i][31]>.5]
  return min(preferred,key=lambda i:(b['x'][i][8],b['actions'][i]['ordinal'],i)) if preferred else next(i for i in valid if b['actions'][i]['kind']=='WAIT_EVENT')
 if m['selector']=='COST':
  minimum=min(b['scores'][i] for i in valid);return min((i for i in valid if b['scores'][i]<=minimum+1e-12),key=lambda i:(-b['x'][i][11],b['actions'][i].get('ordinal',0),i))
 assert m['selector']=='SERVICE_FIRST'
 def key(i):
  c=b['forecasts'][i]['cost'];return (*(round(c[k],12) for k in [2,4,3]),round(c[0]/.6215900945595554+c[1]/.42450663682233236,12),-b['x'][i][11],b['actions'][i].get('ordinal',0),i)
 return min(valid,key=key)
def mechanism(op,p):
 assert not (H/'MECHANISM.json').exists(),'Consumed mechanism diagnosis'
 nets,before,choose,digest,torch,np=models(p);modes={'NO_ROLLING':list(range(21,30)),'NO_ATC':[11],'NO_BOTH':[11]+list(range(21,30)),'NO_PREFERENCE':[31]};summary={k:dict(changes=0,decisions=0,dispatch_route_changes=0,wait_kind_changes=0) for k in modes};cases=[];total=0
 for source in sorted((S/'experiments/bc_matched_eval_20261019/artifacts/G001').glob('*.banks.jsonl.gz')):
  local={k:0 for k in modes};n=0
  with gzip.open(source,'rt',encoding='utf-8') as f:
   for line in f:
    record=json.loads(line);b=record['bank'];base,logp,gap=choose('BC',b['x'],b['mask']);assert base==record['index'],'Exact original BC argmax required';n+=1;total+=1
    for mode,columns in modes.items():
     x=np.asarray(b['x'],np.float32).copy();x[:,columns]=0;i,_,_=choose('BC',x,b['mask']);s=summary[mode];s['decisions']+=1
     if i!=base:
      s['changes']+=1;local[mode]+=1;a=b['actions'][base];v=b['actions'][i];s['dispatch_route_changes']+=a.get('route')!=v.get('route');s['wait_kind_changes']+=a['kind']!=v['kind']
  cases.append(dict(source=source.relative_to(R).as_posix(),sha256=sha(source),decisions=n,changes=local))
 assert total==16089 and all(digest(nets[k])==v for k,v in before.items());pins(op)
 save(H/'MECHANISM.json',dict(status='PASS',utc=now(),saved_full_argmax_matches=total,summary=summary,cases=cases,network_sha256=before,new_environments=0,new_training=0,interpretation='Frozen input masking on prior states only; counterfactual feature sensitivity is not a retrained architecture result or new generalization evaluation.'))
 print('MECHANISM',json.dumps(summary),flush=True)
def evaluate(op,p):
 assert read(H/'PREFLIGHT.json')['status']=='PASS' and read(H/'MECHANISM.json')['status']=='PASS';assert not O.exists(),'Consumed namespace; no automatic rerun'
 nets,before,choose,digest,torch,np=models(p);cases=read(H/'INPUTS.json')['cases'];methods=p['methods'];assert [c['id'] for c in cases]==p['cases'];O.mkdir(parents=True);began=time.monotonic();rows=[];failures=[];count=0
 save(O/'START.json',dict(utc=now(),operation_sha256=sha(H/'OPERATION.json'),pid=os.getpid(),network_sha256=before,official_final_unchanged=True))
 try:
  for ci,c in enumerate(cases):
   pins(op);resource=guard(op)
   for m in methods[ci%len(methods):]+methods[:ci%len(methods)]:
    assert count<op['environment_cap'] and time.monotonic()-began<op['wall_cap_s'];count+=1
    label=c['id']+'__'+m['id'];identity=hashlib.sha256((sha(H/'OPERATION.json')+'|'+label).encode()).hexdigest();receipt=dict(event='START',utc=now(),label=label,input=c['id'],method=m['id'],identity=identity,count=count,resource=resource);append(receipt)
    start=time.monotonic();engine=None;timer=None;decisions=0
    try:
     with (O/(label+'.stderr.txt')).open('x',encoding='utf-8') as err,(O/(label+'.banks.jsonl.gz')).open('xb') as dest:
      with gzip.GzipFile(filename='',mode='wb',fileobj=dest,compresslevel=3,mtime=0) as banks:
       engine=subprocess.Popen([op['node'],str(H/'server.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,encoding='utf-8',bufsize=1,cwd=R)
       timer=threading.Timer(min(op['per_case_wall_cap_s'],op['wall_cap_s']-(time.monotonic()-began)),lambda:engine.kill() if engine.poll() is None else None);timer.daemon=True;timer.start()
       def send(x):engine.stdin.write(json.dumps(x,separators=(',',':'))+'\n');engine.stdin.flush()
       send(dict(input=c['id'],method=m['id']))
       while True:
        line=engine.stdout.readline()
        if not line:raise RuntimeError('Engine closed before DONE (see stderr/time cap)')
        msg=json.loads(line)
        if msg['type']=='FAIL':save(O/(label+'.failed.json.gz'),msg);raise RuntimeError(msg['error'])
        if msg['type']=='DONE':raw=msg['result'];telemetry=msg['telemetry'];break
        assert msg['type']=='BANK';b=msg['bank'];assert b['constraints']==dict(physical_slots_only=True,deadline_action_mask=False,critical_request_override=False,fixed_ATC_prior=False,post_NN_override=False)
        i,logp,gap=choose(m['selector'],b['x'],b['mask']) if m['selector'] in nets else (deterministic(m,b),None,None)
        assert b['mask'][i];banks.write((json.dumps(dict(bank=b,index=i,logp=logp,logit_gap=gap),ensure_ascii=False,separators=(',',':'))+'\n').encode());decisions+=1;send(dict(index=i))
      dest.flush();os.fsync(dest.fileno())
     timer.cancel();save(O/(label+'.raw.json.gz'),raw)
     row=dict(label=label,input=c['id'],method=m['id'],family=c['family'],mix=c['mix'],replicate=c['replicate'],stream=c['stream'],n=c['n'],rate=c['rate'],empirical_rate=c['empirical_rate'],service=raw['service'],unfinished=raw['unfinished'],J=raw['physics_J'],AP_mean=raw['AP_mean'],AP_peak=raw['AP_peak_sampled'],outside_AP=raw.get('outside_marginal_AP'),observation_s=raw['observation_end_s'],routes=raw['policy_route_counts'],wait_s=raw['wait_s'],nominal_compute=raw['nominal_compute'],telemetry=telemetry,decisions=decisions,neural_calls=decisions if m['selector'] in nets else 0,network_sha256=before.get(m['selector']),raw_sha256=sha(O/(label+'.raw.json.gz')),banks_sha256=sha(O/(label+'.banks.jsonl.gz')),wall_s=time.monotonic()-start,adopted=False,physical_validation=False)
     save(O/(label+'.json'),row);rows.append(row);append({**receipt,'event':'COMPLETE','utc':now(),'raw_sha256':row['raw_sha256']});print('COMPLETE',count,label,'J',round(row['J'],4),'on',row['service']['all']['on_time'],'urgent',row['service']['urgent']['on_time'],'unfinished',row['unfinished'],'wall',round(row['wall_s'],1),flush=True)
    except Exception as error:
     failure={**receipt,'event':'FAIL','utc':now(),'error':str(error),'automatic_retry':False};append(failure);failures.append(failure);save(O/(label+'.failure.json'),dict(**failure,traceback=traceback.format_exc()));print('PRESERVED_FAIL',count,label,str(error)[:200],flush=True)
    finally:
     if timer:timer.cancel()
     if engine:
      if engine.stdin:engine.stdin.close()
      try:engine.wait(timeout=5)
      except subprocess.TimeoutExpired:engine.kill();engine.wait(timeout=5)
   print('CASE_BLOCK_COMPLETE',ci+1,'elapsed',round(time.monotonic()-began,1),flush=True)
  assert count==320;pins(op);assert all(digest(nets[k])==v for k,v in before.items())
  save(O/'RESULT.json',dict(status='FINITE_FOLLOWUP_COMPLETE',utc=now(),START=count,COMPLETE=len(rows),FAIL=len(failures),rows=rows,failures=failures,network_sha256=before,new_training=0,new_measurements=0,new_fit=0,completed_reruns=0,adopted=False,elapsed_s=time.monotonic()-began))
  save(O/'COMPLETE.json',dict(utc=now(),START=count,COMPLETE=len(rows),FAIL=len(failures),result_sha256=sha(O/'RESULT.json')))
 except BaseException as error:save(O/'OPERATION_FAILURE.json',dict(utc=now(),error=str(error),traceback=traceback.format_exc(),automatic_retry=False));raise
if __name__=='__main__':
 op=read(H/'OPERATION.json');p=read(H/'PROTOCOL.json');pins(op);guard(op)
 with Path(op['shared_mutex']).open('r+b') as lock:
  lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
  try:
   if sys.argv[1:]==['--preflight']:
    subprocess.run([op['node'],str(H/'preflight.cjs')],cwd=R,check=True);nets,before,choose,digest,torch,np=models(p);print('CHECKPOINTS_PASS',json.dumps(before),flush=True)
   elif sys.argv[1:]==['--mechanism']:mechanism(op,p)
   elif sys.argv[1:]==['--evaluate']:evaluate(op,p)
   else:raise ValueError('Explicit --preflight/--mechanism/--evaluate required')
  finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
