"""Visible single shared owner: registered policy runs only, no NN/optimizer/fit."""
import ast,datetime,gzip,hashlib,importlib.util,json,msvcrt,os,shutil,subprocess,sys,time,traceback
from pathlib import Path
W=Path(__file__).resolve().parent
PS='C:/Users/chomg/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,x):
 with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,allow_nan=False,indent=2);f.flush();os.fsync(f.fileno())
def append(p,x):
 with Path(p).open('a',encoding='utf-8') as f:f.write(json.dumps(x,ensure_ascii=False,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
def verify(op):
 for group in ('source_hashes','input_hashes','protected_hashes'):
  for p,h in op.get(group,{}).items():assert sha(p)==h,'SHA mismatch '+p
def validate(r):
 checks=0
 def test(x,msg):
  nonlocal checks;checks+=1
  if not x:raise ValueError(msg)
 test(r['service']['all']['planned']==128,'128 denominator');events=[]
 for q in r['requests']:
  t=q['times'];test(q['response'] is not None,'actual response');test(t['dispatch']>=q['arrival']-1e-9,'arrival first')
  keys=['dispatch','execution_start','host_inference_start','host_inference_return','output_ready','persist_complete','worker_release','AVAILABLE']
  test(all(t[a]<=t[b]+1e-9 for a,b in zip(keys,keys[1:])),'ordered actual phases')
  test(abs(q['response']-t['output_ready' if q['priority']=='urgent' else 'readback_end'])<1e-8,'response contract');slot=q['route'].rsplit('_',1)[-1];events.extend([(t['dispatch'],1,slot),(t['AVAILABLE'],-1,slot)])
 active=[]
 for t,sign,s in sorted(events,key=lambda x:(x[0],x[1])):
  if sign<0:active.remove(s)
  else:active.append(s)
  test(len(active)<=r['config']['capacity'] and len(set(active))==len(active),'actual resource conflict')
 previous=-1
 for x in r['cpu_intervals']:test(x['start']>=previous-1e-9 and x['end']>=x['start'],'CPU server conflict');previous=x['end']
 test(r['unfinished']==128-len(r['requests']),'unfinished');test(r['max_owners']<=r['config']['capacity'],'maxowners');test(r['forecast_calls']<=5000,'forecast cap')
 return checks
class Census:
 def __init__(self):self.p=subprocess.Popen([PS,'-NoProfile','-File',str(W/'inventory.ps1'),'-OwnerPid',str(os.getpid())],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='ascii',creationflags=subprocess.CREATE_NO_WINDOW)
 def get(self):
  self.p.stdin.write('CHECK\n');self.p.stdin.flush();v=json.loads(self.p.stdout.readline());assert 'error' not in v,v
  rows=v['all'];py=[x for x in rows if str(x['Name']).lower().startswith(('python','pypy'))];assert all(x['ProcessId']==os.getpid() for x in py),'Other actual Python owner'
  for x in rows:
   cmd=(x.get('CommandLine') or '').lower()
   assert not (' -file ' in cmd and ('supervise_once.ps1' in cmd or 'run_registered_ie.ps1' in cmd)),'Other producer supervisor'
  own=[x for x in py if x['ProcessId']==os.getpid()];assert len(own)==1 and v['self'] and own[0]['CreationDate']==v['self']['CreationDate'] and own[0]['CommandLine']==v['self']['CommandLine'],'Own PID creation/command census'
  return v
 def close(self):self.p.stdin.close();self.p.wait(timeout=10)
def main():
 op_path=Path(sys.argv[1]).resolve();op=read(op_path);verify(op);out=Path(op['output_dir']);runtime=Path(op['runtime_dir']);assert not runtime.exists(),'Consumed owner; inspect exact saved recovery first'
 census=Census();mutex=Path(op['shared_byte_mutex']['path']);handle=None;locked=False;child=None;ledger_cache={};allrows=[];started=set();p0={};checks=0;forecast_total=0
 def accounting():
  result=[];total=0
  for p in op['global_accounting_ledgers']+[op['receipts_path']]:
   key=str(Path(p).resolve()).lower()
   if any(x['canonical']==key for x in result):continue
   f=Path(p);n=0
   if f.exists():
    stat=f.stat();stamp=(stat.st_size,stat.st_mtime_ns)
    if ledger_cache.get(key,{}).get('stamp')!=stamp:
     data=f.read_bytes();n=sum(json.loads(line).get('event')=='START' for line in data.decode('utf-8-sig').splitlines() if line.strip());ledger_cache[key]=dict(stamp=stamp,n=n,sha256=hashlib.sha256(data).hexdigest())
    n=ledger_cache[key]['n']
   result.append(dict(path=p,canonical=key,START=n));total+=n
  return total,result
 def run_case(config):
  nonlocal checks,forecast_total
  verify(op);v=census.get()
  for drive in op['volumes']:assert shutil.disk_usage(drive).free>=8589934592,'8GiB '+drive
  total,sources=accounting();assert total+1<=op['global_cap'] and len(started)<op['environment_cap'];identity=config['identity'];assert identity not in started;started.add(identity)
  cfg=out/'configurations'/(identity+'.json');rawpath=out/'raw'/(identity+'.json.gz');assert not cfg.exists() and not rawpath.exists();save(cfg,config)
  append(op['receipts_path'],dict(event='START',id=identity,config_sha256=sha(cfg),packet_sha256=sha(op['packet_path']),operation_sha256=sha(op_path),actual_pid=os.getpid(),actual_creation=v['self']['CreationDate'],global_START_after=total+1,global_reserved=op['global_reserved'],ledger_sources=sources,utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
  terminal=False;begin=time.monotonic()
  try:
   child.stdin.write(json.dumps(dict(config_path=str(cfg),raw_path=str(rawpath)))+'\n');child.stdin.flush();line=child.stdout.readline();assert line,'Case child failed: inspect stderr';meta=json.loads(line);assert meta['identity']==identity
   payload=gzip.decompress(rawpath.read_bytes());assert hashlib.sha256(payload).hexdigest()==meta['raw_payload_sha256'] and sha(rawpath)==meta['raw_compressed_sha256'];r=json.loads(payload);n=validate(r);checks+=n;forecast_total+=r['forecast_calls'];assert forecast_total<=op['forecast_calls_cap']
   prepared=dict(id=identity,raw_path=str(rawpath),raw_sha256=sha(rawpath),payload_sha256=meta['raw_payload_sha256'],config_sha256=sha(cfg),checks=n,phase=config['phase'],metadata=meta);save(out/'prepared'/(identity+'.json'),prepared);append(op['receipts_path'],dict(event='PREPARED',**prepared))
   row={k:v for k,v in r.items() if k not in ('activity','sensor','events','requests','curve','policy_decisions','public_nominal_model','planned_requests','active_at_censor','phase_trace','cpu_intervals','advances')};row.update(raw_path=str(rawpath),raw_sha256=prepared['raw_sha256'],payload_sha256=prepared['payload_sha256'],phase=config['phase'],case_wall_s=time.monotonic()-begin);append(out/'ROWS.jsonl',row);append(op['receipts_path'],dict(event='COMPLETE',id=identity,raw_sha256=prepared['raw_sha256'],utc=datetime.datetime.now(datetime.timezone.utc).isoformat()));terminal=True;allrows.append(row)
   save(out/('PROGRESS_'+str(len(allrows)).zfill(4)+'.json'),dict(completed=len(allrows),total=3240,phase=config['phase'],latest=identity,checks=checks,forecasts=forecast_total,unix=time.time()))
   if config['phase']=='P0':
    key=config['numeric_pair'];p0.setdefault(key,[]).append(row)
    if len(p0[key])==2:
     a,b=p0[key];ok=all(a['service'][p]['on_time']==b['service'][p]['on_time'] and a['service'][p]['completed']==b['service'][p]['completed'] for p in ('urgent','normal','all'));proof=dict(pair=key,on_time_completed_equal=ok,J_diff=abs(a['J_API0_180']-b['J_API0_180']),AP_diff=abs(a['AP35_180_mean']-b['AP35_180_mean']));proof['status']='PASS' if ok and proof['J_diff']<.2 and proof['AP_diff']<.01 else 'FAIL';append(out/'P0_NUMERIC.jsonl',proof);assert proof['status']=='PASS','P0 numerical pair failed; rows preserved'
  except BaseException as e:
   if not terminal:append(op['receipts_path'],dict(event='FAIL',id=identity,error=repr(e),raw_exists=rawpath.exists()))
   else:save(out/('POST_COMPLETE_STAGE_FAILURE_'+identity+'.json'),dict(error=repr(e),preserve='COMPLETE'))
   raise
 try:
  own=census.get();assert sha(mutex)==op['shared_byte_mutex']['sha256'];handle=mutex.open('r+b');handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1);locked=True;runtime.mkdir();save(runtime/'WORKER_OWNER.json',dict(pid=os.getpid(),parent_pid=own['self']['ParentProcessId'],created=own['self']['CreationDate'],command=own['self']['CommandLine'],operation=str(op_path),operation_sha256=sha(op_path)));save(runtime/'START.json',dict(unix=time.time(),new_policy_environments=0))
  for name in ('raw','configurations','prepared','case_logs'): (out/name).mkdir(parents=True,exist_ok=False)
  stderr=(out/'case_logs/server.stderr.log').open('x',encoding='utf-8');child=subprocess.Popen([op['node_path'],'--max-old-space-size=2048',op['node_entry'],op['packet_path']],cwd=W,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW);save(runtime/'NODE_LAUNCH.json',dict(pid=child.pid,parent_pid=os.getpid(),entry=op['node_entry'],created_unix=time.time()))
  p0_audit_module=None
  for config in read(op['case_plan_path']):
   if config['phase']=='DEV' and p0_audit_module is None:
    assert len(allrows)==72 and len(p0)==36 and all(len(v)==2 for v in p0.values())
    spec=importlib.util.spec_from_file_location('p0_independent',W/'multi_audit.py');p0_audit_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(p0_audit_module);packet=read(op['packet_path']);proofs=[]
    for row in allrows:
     identity=row['logical_identity'];append(out/'P0_COST_REPLAY_RECEIPTS.jsonl',dict(event='START',id=identity,new_policy_environments=0));r=json.loads(gzip.decompress(Path(row['raw_path']).read_bytes()));p0_audit_module.phase_service_audit(r);p=p0_audit_module.activity_audit(packet,r);a=p0_audit_module.physical(packet,r);t=p0_audit_module.timing_audit(packet,r);p0_audit_module.observations(packet,r);proofs.append(dict(id=identity,physical=a,timing=t,activity=p));append(out/'P0_COST_REPLAY_RECEIPTS.jsonl',dict(event='COMPLETE',id=identity))
    save(out/'P0_INDEPENDENT_AUDIT.json',dict(status='PASS',cases=72,checks=p0_audit_module.checks,proofs=proofs,new_policy_environments=0,meaning='Independent stored activity/cost/work/public-input checks before DEV'))
   run_case(config)
  assert len(allrows)==648 and len(p0)==36 and all(len(v)==2 for v in p0.values())
  dev=[r for r in allrows if r['phase']=='DEV'];scores={}
  for allocator in ('WEIGHTED','NO_THERMAL_HARM'):
   rows=[r for r in dev if r['config']['allocator']==allocator];harm=0;peak_harm=0
   for r in rows:
    match=next(x for x in dev if x['config']['allocator']=='WEIGHTED' and all(x['config'][k]==r['config'][k] for k in ('bank','burst','context_index','model','stream','policy','capacity')));harm+=max(0,r['AP35_180_mean']-match['AP35_180_mean']);peak_harm+=max(0,r['AP_peak_sampled']-match['AP_peak_sampled'])
   scores[allocator]=[sum(128-r['service']['all']['on_time'] for r in rows),sum(r['unfinished'] for r in rows),harm,peak_harm,sum(r['J_API0_180'] for r in rows),int(allocator!='WEIGHTED')]
  selected=min(scores,key=lambda k:tuple(scores[k]));freeze=dict(status='FROZEN_BEFORE_EVAL',allocator=selected,scores=scores,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),DEV_rows=576,DEV_rows_sha256=sha(out/'ROWS.jsonl'),recipe_sha256=sha(op['eval_recipe_path']),new_RL=0);save(out/'DEV_SELECTION_FREEZE.json',freeze)
  recipes=read(op['eval_recipe_path']);cases=[]
  for r in recipes:
   r['allocator']=selected;r['identity']=r['identity'].replace('SELECTED_AFTER_DEV',selected);cases.append(r)
  save(out/'EVAL_CASE_PLAN_SEALED.json',cases);save(out/'EVAL_SEAL.json',dict(freeze_sha256=sha(out/'DEV_SELECTION_FREEZE.json'),eval_plan_sha256=sha(out/'EVAL_CASE_PLAN_SEALED.json'),utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
  for config in cases:run_case(config)
  child.stdin.close();assert child.wait(timeout=30)==0;stderr.close();verify(op)
  save(op['result_path'],dict(status='PASS',meaning='EXECUTION_FINISHED_PENDING_INDEPENDENT_FULL_AUDIT',completed=len(allrows),P0=72,DEV=576,EVAL=2592,selected_allocator=selected,checks=checks,forecast_calls=forecast_total,new_RL=0,new_fit=0));save(runtime/'FINISHED.json',dict(status='PASS',result_sha256=sha(op['result_path']),unix=time.time()))
 except BaseException:
  if runtime.exists():save(runtime/'FAILED.json',dict(status='FAILED_PRESERVED_NO_AUTOMATIC_RETRY',traceback=traceback.format_exc(),completed=len(allrows),unix=time.time()))
  raise
 finally:
  if child and child.poll() is None:child.stdin.close();child.wait(timeout=30)
  if handle:
   if locked:handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
   handle.close()
  census.close()
def prepare():
 op_path=Path(sys.argv[1]);op=read(op_path);verify(op);census=Census();handle=None;locked=False;result=Path(op['result_path']);assert not result.exists(),'Prepared operation already consumed'
 try:
  own=census.get();handle=Path(op['shared_byte_mutex']['path']).open('r+b');handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1);locked=True
  for f in W.glob('*.py'):ast.parse(f.read_text(encoding='utf-8-sig'),filename=str(f))
  import numpy
  for f in W.glob('*.cjs'):subprocess.run([op['node_path'],'--check',str(f)],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
  subprocess.run([op['node_path'],str(W/'pure_tests.cjs'),op['pure_result_name']],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
  spec=importlib.util.spec_from_file_location('audit_pure',W/'audit_pure_tests.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);auditproof=module.run(op);save(Path(op['output_dir'])/op['audit_pure_result_name'],auditproof)
  verify(op);save(result,dict(status='PASS',actual_owner=own['self'],operation_sha256=sha(op_path),pure_sha256=sha(Path(op['output_dir'])/op['pure_result_name']),audit_pure_sha256=sha(Path(op['output_dir'])/op['audit_pure_result_name']),python_ast_files=[f.name for f in W.glob('*.py')],numpy_version=numpy.__version__,new_policy_environments=0,shared_mutex_held=True,utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
 finally:
  if handle:
   if locked:handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
   handle.close()
  census.close()
if __name__=='__main__':
 if '--prepare' in sys.argv:prepare()
 elif '--audit' in sys.argv:
  spec=importlib.util.spec_from_file_location('full_audit',W/'multi_audit.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.audit(Path(sys.argv[1]).resolve())
 else:main()
