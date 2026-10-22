"""One registered simulator validation; no NN/optimizer imports or retries.
Every plant instance START is charged before construction; raw→prepared→row→terminal.
"""
import datetime,hashlib,importlib.util,json,os,shutil,subprocess,time
from pathlib import Path
from timing_model import read,save
from guard_snapshot_ascii import guard as strict_guard
U=Path("C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/work/S26-INTEGRATED-MODEL-20261016/shared_S26-ROLLING-ATC-RL-TRAIN-20261016_forecast_owner.py")
spec=importlib.util.spec_from_file_location('actual_owner_guard',U);u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)
def append(p,v):
 with Path(p).open('a',encoding='utf-8') as f:f.write(json.dumps(v,ensure_ascii=False,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
def accounting(op):
 sources=[];seen=set();total=0;own=0
 for p in [*op['global_accounting_ledgers'],op['receipts_path']]:
  key=str(Path(p).resolve()).lower()
  if key in seen:continue
  seen.add(key);n=0
  if Path(p).exists():
   with open(p,encoding='utf-8-sig') as f:
    for line in f:
     if line.strip():n+=read_line(line).get('event')=='START'
  sources.append(dict(path=p,START=n));total+=n
  if key==str(Path(op['receipts_path']).resolve()).lower():own=n
 return total,own,sources
def read_line(s):return json.loads(s)
def validate(raw):
 checks=0
 def test(ok,text):
  nonlocal checks;checks+=1
  if not ok:raise ValueError('Raw invariant: '+text)
 test(raw['service']['all']['planned']==128,'all planned128')
 ev=[]
 for q in raw['requests']:
  t=q['times'];test(q['response'] is not None,'actual response present');test(t['dispatch']>=q['arrival'],'no early dispatch');test(t['dispatch']<120,'no dispatch after120');test(t['dispatch']<=t['execution_start']<=t['host_inference_start']<=t['host_inference_return']<=t['output_ready']<=t['persist_complete']<=t['worker_release']<=t['AVAILABLE'],'ordered phases');test(abs(q['response']-(t['output_ready'] if q['priority']=='urgent' else t['readback_end']))<1e-9,'response not release');test(q['route'] in ('classification_CPU','classification_GPU','classification_NPU','detection_CPU'),'support');ev.extend([(t['dispatch'],1,q['route']),(t['AVAILABLE'],-1,q['route'])])
 owners=[]
 for t,s,r in sorted(ev,key=lambda x:(x[0],x[1])):
  if s<0:owners.remove(r)
  else:owners.append(r)
  test(len(owners)<=2,'capacity2')
  if len(owners)==2:test(set(owners) in ({'classification_GPU','detection_CPU'},{'classification_NPU','detection_CPU'}),'supported nonpreemptive pair')
 test(not owners,'all returned owners')
 test(raw['unfinished']==128-len(raw['requests']),'unfinished denominator')
 test(raw['evidence']['new_RL']==0,'RL deferred')
 return checks
def main(op):
 u.verify({"protected_hashes":op["reuse_parent_hashes"]})
 out=Path(op['output_dir']);proof=read(op['recovery_proof']);all_cases=read(op['case_plan_path']);prefix=proof['prefix_completed']
 assert u.sha(op['recovery_ledger_prefix'])==proof['prefix_ledger_sha256'] and u.sha(op['recovery_rows_prefix'])==proof['prefix_rows_sha256']
 assert Path(op['receipts_path']).read_bytes().startswith(Path(op['recovery_ledger_prefix']).read_bytes())
 assert (out/'ROWS.jsonl').read_bytes().startswith(Path(op['recovery_rows_prefix']).read_bytes())
 for item in proof['rows']:
  assert u.sha(item['raw_path'])==item['raw_sha256'] and u.sha(item['config_path'])==item['config_sha256'] and u.sha(item['prepared_path'])==item['prepared_sha256']
 assert len([read_line(l) for l in Path(op['receipts_path']).read_text().splitlines() if l.strip()])==prefix*3
 allrows=[read_line(l) for l in (out/'ROWS.jsonl').read_text().splitlines() if l.strip()];assert len(allrows)==prefix
 cases=all_cases[prefix:];started={c['identity'] for c in all_cases[:prefix]};p0={};checks=proof['prefix_raw_checks']
 for c in all_cases[:12]:p0.setdefault(c['numeric_pair'],[]).append(read(out/'raw'/(c['identity']+'.json')))
 assert len(p0)==6
 for c in cases:
  assert not (out/'raw'/(c['identity']+'.json')).exists() and not (out/'configurations'/(c['identity']+'.json')).exists() and c['identity'] not in started
 for config in cases:
  u.verify(op);own=strict_guard(out/'case_logs'/('RECOVERY_CENSUS_'+config['identity']+'.json'))
  for drive in op['volumes']:assert shutil.disk_usage(drive).free>=8589934592
  total,count,sources=accounting(op);assert count<op['environment_cap'] and total+1<=op['global_cap'];identity=config['identity'];assert identity not in started;started.add(identity)
  cfg=out/'configurations'/(identity+'.json');save(cfg,config);rawpath=out/'raw'/(identity+'.json')
  append(op['receipts_path'],dict(event='START',id=identity,operation_sha256=u.sha(os.environ['S26_UNIFIED_OPERATION']),config_sha256=u.sha(cfg),packet_sha256=u.sha(op['packet_path']),global_START_after=total+1,own_START_after=count+1,global_reserved=op['global_reserved'],ledger_sources=sources,actual_pid=os.getpid(),actual_creation=own['CreationDate'],utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),new_policy_environment=1,new_NN=0))
  terminal=False
  try:
   with (out/'case_logs'/(identity+'.stdout.log')).open('x',encoding='utf-8') as stdout,(out/'case_logs'/(identity+'.stderr.log')).open('x',encoding='utf-8') as stderr:
    child=subprocess.Popen([op['node_path'],'--max-old-space-size=1024',op['node_entry'],op['packet_path'],str(cfg),str(rawpath)],cwd=Path(op['node_entry']).parent,stdout=stdout,stderr=stderr)
    save(out/'case_logs'/(identity+'_LAUNCH.json'),dict(pid=child.pid,parent=os.getpid(),unix=time.time(),config=str(cfg)));code=child.wait()
   assert code==0,'Case failed; consumed identity never retried';raw=read(rawpath);n=validate(raw);checks+=n
   prepared=dict(id=identity,raw_path=str(rawpath),raw_sha256=u.sha(rawpath),config_path=str(cfg),config_sha256=u.sha(cfg),checks=n,phase=config['phase']);save(out/'prepared'/(identity+'.json'),prepared)
   append(op['receipts_path'],dict(event='PREPARED',**prepared));row={k:v for k,v in raw.items() if k not in ('activity','sensor','events','requests','curve','planned_requests','active_at_censor','policy_decisions','public_nominal_model')};row.update(raw_sha256=prepared['raw_sha256'],raw_path=str(rawpath),phase=config['phase']);append(out/'ROWS.jsonl',row);append(op['receipts_path'],dict(event='COMPLETE',id=identity,raw_sha256=prepared['raw_sha256'],hard_feasible=raw['hard_feasible'],utc=datetime.datetime.now(datetime.timezone.utc).isoformat()));terminal=True;allrows.append(row)
   save(out/('PROGRESS_'+str(len(allrows)).zfill(4)+'.json'),dict(completed=len(allrows),total=op['planned'],latest=identity,checks=checks,unix=time.time()))
   if config['phase']=='P0':
    base=config['numeric_pair'];p0.setdefault(base,[]).append(raw)
    if len(p0[base])==2:
     a,b=p0[base];proof=dict(pair=base,identities=[a['logical_identity'],b['logical_identity']],on_time_equal=all(a['service'][p]['on_time']==b['service'][p]['on_time'] for p in ('urgent','normal','all')),J_abs_diff=abs(a['J_API0_180']-b['J_API0_180']),AP_mean_abs_diff=abs(a['AP35_180_mean']-b['AP35_180_mean']),thresholds=dict(J_abs_diff=.2,AP_mean_abs_diff=.01));proof['status']='PASS' if proof['on_time_equal'] and proof['J_abs_diff']<.2 and proof['AP_mean_abs_diff']<.01 else 'FAIL';append(out/'P0_NUMERIC_AUDIT.jsonl',proof);assert proof['status']=='PASS','P0 numeric comparison failed; saved environments remain COMPLETE, stage stops before further START'
  except BaseException as e:
   if not terminal:append(op['receipts_path'],dict(event='FAIL',id=identity,error=repr(e),raw_exists=rawpath.exists(),utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
   else:save(out/('POST_TERMINAL_STAGE_FAILURE_'+identity+'.json'),dict(id=identity,error=repr(e),environment_terminal_preserved='COMPLETE',no_retry=True))
   raise
 u.verify(op);save(op['result_path'],dict(status='PASS',meaning='EXECUTION_FINISHED_PENDING_FULL_AUDIT_AND_ACCURACY_ASSESSMENT',completed=len(allrows),planned=op['planned'],environment_cap=op['environment_cap'],raw_invariant_checks=checks,P0_numeric_pairs=len(p0),new_RL=0,new_NN=0,global_reserved=op['global_reserved'],simulation_not_new_phone_measurements=True))
if __name__=='__main__':main(read(os.environ['S26_UNIFIED_OPERATION']))
