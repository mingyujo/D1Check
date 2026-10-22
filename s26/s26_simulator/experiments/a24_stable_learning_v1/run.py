"""Paired finite repair study. Every new environment has one durable identity."""
import ast,copy,datetime,gzip,hashlib,io,json,msvcrt,os,shutil,subprocess,sys,time,traceback
from pathlib import Path
for key in('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];WORK=HERE.parents[3]
sys.path.insert(0,str(WORK/'recovery'));from s26_resources import wait_ready
def read(p):
 p=Path(p);return json.loads((gzip.decompress(p.read_bytes())if p.suffix=='.gz'else p.read_bytes()).decode('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(p,x):
 p=Path(p);b=json.dumps(x,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
 if p.suffix=='.gz':b=gzip.compress(b,compresslevel=5,mtime=0)
 with p.open('xb')as f:f.write(b);f.flush();os.fsync(f.fileno())
def append(p,x):
 with Path(p).open('a',encoding='utf-8')as f:f.write(json.dumps(x,ensure_ascii=False,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
def verify(op):
 for p in op['pins']:assert sha(p['path'])==p['sha256'],'Changed runtime pin '+p['path']
def main(op,out):
 import numpy as np,torch
 from nn_train import Learner,digest
 torch.set_num_threads(1);begin=time.monotonic();count=0;rows=[];selection=None;nets={};updates=[];cases=read(HERE/'INPUTS.json')['cases'];phases={k:[c for c in cases if c['phase']==k]for k in('TRAIN','DEV','EVAL','SENSITIVITY')}
 def pt(p,x):
  b=io.BytesIO();torch.save(x,b)
  with Path(p).open('xb')as f:f.write(gzip.compress(b.getvalue(),compresslevel=4,mtime=0))
 def load(p):return torch.load(io.BytesIO(gzip.decompress(Path(p).read_bytes())),map_location='cpu',weights_only=False)
 engine=subprocess.Popen(['node',str(HERE/'server.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=(out/'ENGINE_STDERR.txt').open('x',encoding='utf-8'),text=True,encoding='utf-8',bufsize=1)
 def send(x):engine.stdin.write(json.dumps(x,separators=(',',':'))+'\n');engine.stdin.flush()
 def simulate(case,mode,label,kind,learner=None,variant='BASE',collect=False,stream=None):
  nonlocal count
  verify(op);assert count<op['environment_cap']and time.monotonic()-begin<op['wall_cap_s'],'Finite registered cap'
  if count%8==0:append(out/'RESOURCE_CHECKS.jsonl',wait_ready(timeout_s=op['wall_cap_s']-(time.monotonic()-begin),min_free_MiB=1024))
  actual_stream=case['stream']if stream is None else stream;policy=('RL_'+variant if mode=='RL'else mode);pre=digest(learner.net)if learner else None;frames=[]
  receipt=dict(event='START',label=label,kind=kind,input=case['id'],policy=policy,variant=variant,seed=learner.seed if learner else None,stream=actual_stream,utc=now(),selection_sha256=selection,durable_consumed=True);append(out/'receipts.jsonl',receipt);count+=1;print(json.dumps(dict(event='START',count=count,label=label,n=case['n'])),flush=True)
  try:
   send(dict(input=case['id'],mode=mode,variant=variant,stream=actual_stream,dt_s=.01))
   while True:
    line=engine.stdout.readline();assert line,'Engine closed';m=json.loads(line)
    if m['type']=='FAIL':save(out/(label+'.failed.json.gz'),m);raise RuntimeError(m['error'])
    if m['type']=='DONE':r=m['result'];break
    assert m['type']=='BANK'and learner is not None;bank=m['bank'];assert bank['constraints']==dict(physical_slots_only=True,deadline_action_mask=False,critical_request_override=False,fixed_ATC_prior=False,post_NN_override=False)
    index,f=learner.choose(bank,collect);f.update(time_ns=bank['time_ns'],action=bank['actions'][index],candidate_actions=bank['actions'],nominal_forecasts=bank['forecasts'],ready_total=bank['ready_total'],forecast_ready=bank['forecast_ready'],decision_ready=bank['decision_ready'],forecast_horizon_s=bank['forecast_horizon_s'],representation=bank['representation']);frames.append(f);send(dict(index=index))
   raw=out/(label+'.raw.json.gz');save(raw,r);n=case['n'];responded=[q for q in r['requests']if q['response']is not None];span=r['observation_end_s']-35;energy=r['api_energy']-r['baseline_API_J'];skin=case['context']['initial_context']['targets']['AP']['anchor']['SKIN'];heat=max(0.,(r['AP_mean']-skin)/10);objective=[max(0.,energy)/n,heat,0.,0.,(n-len(responded))/n]
   for q in responded:
    d=max(0.,q['response']-q['deadline']);objective[2 if q['priority']=='urgent'else 3]+=(float(d>1e-9)+.2*min(5.,d/(q['deadline']-q['arrival'])))/n
   row=dict(label=label,kind=kind,input=case['id'],policy=policy,variant=variant,seed=learner.seed if learner else None,stream=actual_stream,n=n,mix=case['mix'],nominal_load_ratio=case['nominal_load_ratio'],model=case['model'],replicate=case['replicate'],rate=case['rate'],supply_s=case['duration'],observation_s=r['observation_end_s'],work_s=r['actual_work_span_s'],service=r['service'],unfinished_AVAILABLE=r['unfinished'],response_missing=n-len(responded),api_J=r['api_energy'],baseline_API_J=r['baseline_API_J'],full_API_J=r['physics_J'],full_baseline_API_J=r['baseline_API_W']*r['observation_end_s'],baseline_API_W=r['baseline_API_W'],AP_mean=r['AP_mean'],AP_peak=r['AP_peak_sampled'],AP_outside_measurements=r['outside_marginal_AP'],routes=r['policy_route_counts'],wait_s=r['wait_s'],cost_vector=objective,weighted=sum(w*x for w,x in zip((.5,.5,8.,4.,30.),objective)),network_sha256=pre,new_frames=len(frames),raw_sha256=sha(raw),nominal_compute=r['nominal_compute'],physical_validation=False,adopted=False,policy_superiority_claim_allowed=False)
   if learner:
    times=np.array([f['time_ns']for f in frames],dtype=np.int64);cost=np.zeros((len(frames),5),np.float64);assert len(times)>0 and np.all(np.diff(times)>=0)
    def idx(t):return max(0,min(len(times)-1,int(np.searchsorted(times,round(t*1e9),side='right'))-1))
    for t0,t1,J,H in r['integrals']:
     cost[idx(t0),0]+=(J-r['baseline_API_W']*(t1-t0))/n
     if heat>0:cost[idx(t0),1]+=(H-skin*(t1-t0))/(span*10)
    for q in responded:
     d=max(0.,q['response']-q['deadline']);cost[idx(q['response']),2 if q['priority']=='urgent'else 3]+=(float(d>1e-9)+.2*min(5.,d/(q['deadline']-q['arrival'])))/n
    cost[-1,4]=objective[4];error=float(np.max(abs(cost.sum(0)-np.array(objective))));assert error<1e-7;row['reward_telescope_error']=error;pt(out/(label+'.frames.pt.gz'),dict(frames=frames,costs=cost,collect=collect,network_sha256=pre,objective=objective))
    if collect:learner.add(frames,cost)
   save(out/(label+'.json'),row);rows.append(row);append(out/'receipts.jsonl',{**receipt,'event':'COMPLETE','utc':now(),'raw_sha256':sha(raw),'row_sha256':sha(out/(label+'.json'))});print(json.dumps(dict(event='COMPLETE',label=label,on=row['service']['all']['on_time'],urgent=row['service']['urgent']['on_time'],normal=row['service']['normal']['on_time'],n=n,J=row['full_API_J'],wait_s=row['wait_s'],frames=len(frames))),flush=True);return row
  except BaseException as e:
   if frames:pt(out/(label+'.partial_frames.pt.gz'),frames)
   append(out/'receipts.jsonl',{**receipt,'event':'FAIL','utc':now(),'error':str(e),'automatic_retry':False});raise
 try:
  initialization=[]
  for i,(parent_seed,seed)in enumerate(zip(op['parent_seeds'],op['new_stage_seeds'])):
   cp=Path(op['parent_checkpoints'][str(parent_seed)]);snapshot=load(cp);rng=np.random.default_rng(seed+300000);order=rng.permutation(len(phases['TRAIN'])).tolist();save(out/f'S{seed}_CASE_ORDER.json',dict(seed=seed,parent_seed=parent_seed,order=order,case_rng_after=rng.bit_generator.state,case_ids=[phases['TRAIN'][j]['id']for j in order]))
   for variant in('BASE','REPAIR'):
    learner=Learner(seed)
    if variant=='REPAIR':learner.optimizer.param_groups[0]['lr']=1e-4
    learner.net.load_state_dict(snapshot['network']);assert digest(learner.net)==snapshot['network_sha256']and not learner.pending and not learner.optimizer.state;pt(out/f'{variant}_S{seed}_EP000.pt.gz',learner.snapshot());initialization.append(dict(variant=variant,seed=seed,parent_seed=parent_seed,parent_checkpoint_sha256=sha(cp),initial_network_sha256=digest(learner.net),new_optimizer=True,new_pending=True,new_RNG=True));nets[(variant,seed)]=learner
    for ep,j in enumerate(order,1):
     case=phases['TRAIN'][j];before=learner.snapshot();pt(out/f'{variant}_S{seed}_EP{ep:03d}_before.pt.gz',before);simulate(case,'RL',f'TRAIN_{variant}_S{seed}_EP{ep:03d}','TRAIN',learner,variant,True,stream=732000000+i*10000000+j*101+ep);after=learner.snapshot();pt(out/f'{variant}_S{seed}_EP{ep:03d}_after.pt.gz',after)
     if after['updates']>before['updates']:assert after['network_sha256']!=before['network_sha256'];updates.append(dict(variant=variant,seed=seed,episode=ep,update=after['updates'],before=before['network_sha256'],after=after['network_sha256']))
    assert learner.episodes==16 and learner.updates==8 and not learner.pending;pt(out/f'{variant}_S{seed}_EP016.pt.gz',learner.snapshot())
  save(out/'TRAINING_COMPLETE.json',dict(initialization=initialization,updates=updates,TRAIN_START=96,PPO_updates=len(updates)));assert len(updates)==48
  frozen=Learner(op['frozen_parent_seed']);frozen.restore(load(op['parent_checkpoints'][str(op['frozen_parent_seed'])]));frozen_sha=digest(frozen.net)
  def evaluate_case(case,phase,i):
   for mode in('EDF_GPU_FIRST','ATC','ATC_SALVAGE'):simulate(case,mode,f'{phase}_{i}_{mode}',phase)
   simulate(case,'RL',f'{phase}_{i}_FROZEN_S{op["frozen_parent_seed"]}',phase,frozen,'FROZEN')
   for variant in('BASE','REPAIR'):
    for seed in op['new_stage_seeds']:simulate(case,'RL',f'{phase}_{i}_{variant}_S{seed}',phase,nets[(variant,seed)],variant)
  for i,c in enumerate(phases['DEV']):evaluate_case(c,'DEV',i)
  dev=[r for r in rows if r['kind']=='DEV'];baseline={r['input']:r for r in dev if r['policy']=='EDF_GPU_FIRST'};selected={};scores=[]
  for variant in('BASE','REPAIR'):
   options=[]
   for seed in op['new_stage_seeds']:
    rr=[r for r in dev if r['variant']==variant and r['seed']==seed];assert len(rr)==8;key=(sum(r['response_missing']for r in rr),sum(max(0,baseline[r['input']]['service']['urgent']['on_time']-r['service']['urgent']['on_time'])for r in rr),sum(max(0,baseline[r['input']]['service']['normal']['on_time']-r['service']['normal']['on_time'])for r in rr),-sum(r['service']['all']['on_time']for r in rr),sum(r['weighted']for r in rr)/len(rr),seed);options.append((key,seed));scores.append(dict(variant=variant,seed=seed,key=key))
   selected[variant]=min(options)[1]
  save(out/'SELECTION_FROZEN.json',dict(utc=now(),primary_seed=selected,all_seed_checkpoints_episode=16,scores=scores,rule='missing,urgent harm,normal harm,-all ontime,fixedweighted,seed'));selection=sha(out/'SELECTION_FROZEN.json')
  for phase in('EVAL','SENSITIVITY'):
   for i,c in enumerate(phases[phase]):evaluate_case(c,phase,i)
  assert digest(frozen.net)==frozen_sha and count==op['planned_START']and len(rows)==count;verify(op);save(out/'RESULT.json',dict(status='PAIRED_STABLE_LEARNING_COMPUTATION_COMPLETE',rows=rows,START=count,COMPLETE=count,FAIL=0,PPO_updates=len(updates),primary_seed=selected,physical_validation=False,adopted=False,new_measurements=0,new_physical_fit=0,elapsed_s=time.monotonic()-begin));save(out/'COMPLETE.json',dict(utc=now(),START=count,result_sha256=sha(out/'RESULT.json')));print('PAIRED_REPAIR_COMPUTATION_COMPLETE',count,flush=True)
 finally:
  engine.stdin.close()
  try:engine.wait(timeout=20)
  except subprocess.TimeoutExpired:engine.terminate();engine.wait(timeout=10)
if __name__=='__main__':
 op=read(HERE/'OPERATION.json');verify(op);out=Path(op['output']);assert not out.exists(),'Consumed namespace; no retry';lock=Path(op['shared_mutex']).open('r+b');locked=False
 try:
  lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True;resource=wait_ready();assert shutil.disk_usage(HERE).free>=8*1024**3
  for p in HERE.glob('*.py'):
   tree=ast.parse(p.read_text(encoding='utf-8-sig'));assert not any(isinstance(k,ast.Name)for n in ast.walk(tree)if isinstance(n,ast.Dict)for k in n.keys),'Bare literal dictionary key'
  out.mkdir(parents=True);save(out/'START.json',dict(utc=now(),pid=os.getpid(),operation_sha256=sha(HERE/'OPERATION.json'),resource=resource))
  try:main(op,out)
  except BaseException:save(out/'FAILURE.json',dict(utc=now(),traceback=traceback.format_exc(),automatic_retry=False));raise
 finally:
  if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
  lock.close()
