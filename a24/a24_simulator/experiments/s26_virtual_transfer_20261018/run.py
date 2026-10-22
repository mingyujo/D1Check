"""New matched virtual study; published checkpoints remain frozen, no training."""
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
import copy,datetime,gzip,hashlib,io,json,msvcrt,shutil,subprocess,sys,time,traceback
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[2];O=R/'a24_simulator/results/S26_VIRTUAL_TRANSFER_20261018_01'
G=H/'vendor/s26_simulator/experiments/route_group_learning_v1';sys.path.insert(0,str(G))
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(p):
 p=Path(p);return json.loads((gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes()).decode('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
 p=Path(p);b=json.dumps(x,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
 if p.suffix=='.gz':b=gzip.compress(b,compresslevel=4,mtime=0)
 with p.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def append(p,x):
 with Path(p).open('a',encoding='utf-8') as f:f.write(json.dumps(x,ensure_ascii=False,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
def resources(op):
 import psutil
 deadline=time.monotonic()+op['resource']['wait_cap_s'];last=0
 while True:
  pp=[x.info for x in psutil.process_iter(['pid','name','cmdline']) if (x.info['name'] or '').lower() in ['python.exe','python3.exe']]
  mem=psutil.virtual_memory();swap=psutil.swap_memory();available=mem.available;commit=mem.total+swap.total-mem.used-swap.used
  disk=shutil.disk_usage(R).free
  if len(pp)<=3 and available>=512*1048576 and commit>=2048*1048576 and disk>=8*1024**3:return dict(utc=now(),python=pp,available=available,commit_estimate=commit,disk=disk)
  if time.monotonic()>deadline:raise RuntimeError('Finite resource wait exhausted; no retry')
  if time.monotonic()-last>30:print('RESOURCE_WAIT',len(pp),available//1048576,commit//1048576,flush=True);last=time.monotonic()
  time.sleep(5)
def verify(pins):
 for p in pins:assert sha(R/p['path'])==p['sha256'],p['path']
def main(op,pins):
 import numpy as np,torch
 from nn_train import Learner,digest
 torch.set_num_threads(1)
 def load(p):return torch.load(io.BytesIO(gzip.decompress(p.read_bytes())),map_location='cpu',weights_only=False)
 models={};initial={};rng={};tensors={}
 for name,file in [('BC_FROZEN','BC_COMMON_FINAL.pt.gz'),('PPO_SELECTED','S881087_FINAL.pt.gz')]:
  cp=load(G/'artifacts/G001'/file);l=Learner(cp['learner']['seed']);l.restore(cp['learner']);l.balance=cp['balance'];models[name]=l;initial[name]=digest(l.net);rng[name]=(l.action_rng.get_state().clone(),l.shuffle_rng.get_state().clone())
  tensors[name]={'temperature':l.net.temperature,'network_sha256':initial[name],'tensors':{k:dict(shape=list(v.shape),data=v.detach().flatten().tolist()) for k,v in l.net.state_dict().items()}}
 save(O/'FROZEN_TENSORS.json',tensors)
 rows=[];began=time.monotonic();engine=None;count=0
 def reset():
  nonlocal engine
  if engine:engine.stdin.close();assert engine.wait(timeout=30)==0
  verify(pins);append(O/'resources.jsonl',resources(op));engine=subprocess.Popen(['node',str(H/'server.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=(O/'ENGINE_STDERR.txt').open('a'),text=True,encoding='utf-8',bufsize=1)
 def send(x):engine.stdin.write(json.dumps(x,separators=(',',':'))+'\n');engine.stdin.flush()
 try:
  for profile in op['profiles']:
   for i,c in enumerate(op['cases']):
    for policy in op['policies']:
     if count%6==0:reset()
     assert time.monotonic()-began<op['wall_cap_s'] and count<op['cap'];count+=1
     label=f"{profile['id']}__E{i}__{policy}";rec=dict(event='START',utc=now(),count=count,label=label,input=c['id'],profile=profile,policy=policy)
     append(O/'receipts.jsonl',rec);frames=[]
     try:
      learner=models.get(policy);balance=copy.deepcopy(learner.balance) if learner else None
      if balance:balance['classFactors']=[1/c['mix'],1/(1-c['mix'])]
      send(dict(case=c,profile=profile,policy=policy,balance=balance))
      while True:
       line=engine.stdout.readline();assert line,'Engine closed';m=json.loads(line)
       if m['type']=='FAIL':save(O/(label+'.failed.json'),m);raise RuntimeError(m['error'])
       if m['type']=='DONE':raw=m['result'];break
       assert m['type']=='BANK' and learner is not None
       bank=m['bank'];assert bank['constraints']==dict(physical_slots_only=True,deadline_action_mask=False,critical_request_override=False,fixed_ATC_prior=False,post_NN_override=False)
       j,f=learner.choose(bank,False);frames.append(dict(bank=bank,index=j,network_sha256=f['network_sha256']));send(dict(index=j))
      save(O/(label+'.raw.json.gz'),raw)
      if frames:save(O/(label+'.banks.json.gz'),frames)
      row=dict(label=label,case_index=i,input=c['id'],n=c['n'],mix=c['mix'],load=c['nominal_load_ratio'],profile=profile,policy=policy,service=raw['service'],unfinished=raw['unfinished'],J=raw['physics_J'],api_energy=raw['api_energy'],baseline_API_J=raw['baseline_API_J'],AP_mean=raw['AP_mean'],AP_peak=raw['AP_peak_sampled'],observation_s=raw['observation_end_s'],work_s=raw['actual_work_span_s'],routes=raw['policy_route_counts'],extra_cpu_core_s=raw['extra_cpu_core_s'],cpu_wait_s=raw['shared_cpu_wait_s'],wait_s=raw['wait_s'],outside_AP=raw['outside_marginal_AP'],frames=len(frames),network_sha256=initial.get(policy),raw_sha256=sha(O/(label+'.raw.json.gz')))
      if profile['id']=='CPU3_K1' and policy in ['EDF_GPU_FIRST','BC_FROZEN','PPO_SELECTED']:
       oldname={'BC_FROZEN':'WARM_FROZEN','PPO_SELECTED':'RL_S881087'}.get(policy,policy);old=read(G/f'artifacts/G001/EVAL_{i}_{oldname}.raw.json.gz')
       keys=['requests','events','policy_decisions','integrals','curve','physics_J','AP_mean','service']
       assert all(raw[k]==old[k] for k in keys),'Pinned original trajectory mismatch '+label
       row['pinned_original_exact_keys']=keys
      rows.append(row);save(O/(label+'.json'),row);append(O/'receipts.jsonl',{**rec,'event':'COMPLETE','utc':now(),'raw_sha256':row['raw_sha256']});print(json.dumps(dict(count=count,label=label,on=raw['service']['all']['on_time'],n=c['n'],J=raw['physics_J'],AP=raw['AP_mean'])),flush=True)
     except BaseException as e:
      if frames:save(O/(label+'.partial_banks.json.gz'),frames)
      append(O/'receipts.jsonl',{**rec,'event':'FAIL','utc':now(),'error':str(e),'automatic_retry':False});raise
  assert count==op['planned_START'] and len(rows)==count
  for key,l in models.items():assert digest(l.net)==initial[key] and torch.equal(l.action_rng.get_state(),rng[key][0]) and torch.equal(l.shuffle_rng.get_state(),rng[key][1])
  verify(pins);save(O/'RESULT.json',dict(status='COMPLETED_PENDING_INDEPENDENT_AUDIT',START=count,COMPLETE=count,FAIL=0,new_training=0,model_selection=False,rows=rows,elapsed_s=time.monotonic()-began))
 finally:
  if engine:
   engine.stdin.close()
   try:engine.wait(timeout=30)
   except subprocess.TimeoutExpired:engine.terminate();engine.wait(timeout=10)
if __name__=='__main__':
 op=read(H/'OPERATION.json');pins=read(H/'PINS.json');verify(pins)
 assert not O.exists(),'Consumed output identity; no automatic restart'
 lock=(R/'a24_simulator/runtime/a24_local_worker.lock').open('r+b');locked=False
 try:
  deadline=time.monotonic()+3600
  while not locked:
   try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
   except OSError:
    if time.monotonic()>deadline:raise
    time.sleep(5)
  resource=resources(op);O.mkdir();save(O/'START.json',dict(utc=now(),pid=os.getpid(),operation_sha256=sha(H/'OPERATION.json'),resource=resource))
  try:main(op,pins)
  except BaseException as e:save(O/'FAILURE.json',dict(utc=now(),error=str(e),traceback=traceback.format_exc(),automatic_retry=False));raise
 finally:
  if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
  lock.close()
