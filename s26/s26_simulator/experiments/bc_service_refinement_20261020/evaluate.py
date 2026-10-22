"""Finite60 newly registered guarded-BC evaluations, no retraining/automatic retry."""
import gzip,hashlib,importlib.util,json,msvcrt,os,subprocess,sys,threading,time,traceback
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[2];E=H.parent/'conclusion_extension_20261020';O=H/'artifacts/G001'
spec=importlib.util.spec_from_file_location('frozen_inference_helpers',E/'worker.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w);w.H=H;w.O=O
def summary(rows):
 n=len(rows)
 return dict(cases=n,J=sum(r['J'] for r in rows)/n,AP=sum(r['AP_mean'] for r in rows)/n,unfinished=sum(r['unfinished'] for r in rows),urgent_misses=sum(r['service']['urgent']['planned']-r['service']['urgent']['on_time'] for r in rows),urgent_percent=100*sum(r['service']['urgent']['on_time'] for r in rows)/sum(r['service']['urgent']['planned'] for r in rows),on_percent=100*sum(r['service']['all']['on_time'] for r in rows)/sum(r['service']['all']['planned'] for r in rows))
def select_before_confirmation(rows,p,failures):
 baseline=w.read(E/'artifacts/G001/RESULT.json')['rows'];b=summary([r for r in baseline if r['method']=='BC_FULL' and r['family']!='BURST32_105']);old=w.read(R/'s26_simulator/FINAL_POLICY.json')['primary_evidence']['BC_control'];old=dict(J=old['mean_API_J'],AP=old['mean_AP_C'],on_percent=old['on_percent']);items=[]
 for order,m in enumerate(p['method_groups']['development32']):
  dev=[r for r in rows if r['method']==m and r['cohort']=='development32'];orig=[r for r in rows if r['method']==m and r['cohort']=='original4']
  if len(dev)!=32 or len(orig)!=4:items.append(dict(method=m,eligible=False,incomplete=True,selection_key=[float(10**9)]*4));continue
  v=summary([r for r in dev if r['family']!='BURST32_105']);stress=summary([r for r in dev if r['family']=='BURST32_105']);o=summary(orig)
  gates=dict(original_service=o['urgent_misses']==o['unfinished']==0 and o['on_percent']>=old['on_percent']-.1,original_energy_AP=o['J']<=old['J']*1.01 and o['AP']<=old['AP']+.1,nominal_service=v['unfinished']==0 and v['urgent_percent']>=99.9,nominal_energy_AP=v['J']<=b['J']*1.01 and v['AP']<=b['AP']+.1)
  items.append(dict(method=m,eligible=all(gates.values()),gates=gates,nominal85=v,stress105=stress,original4=o,eligible_key=[stress['urgent_misses'],v['J'],order],selection_key=[o['urgent_misses']+o['unfinished'],v['unfinished'],v['urgent_misses'],v['J']]))
 eligible=[i for i in items if i['eligible']];chosen=min(eligible,key=lambda i:i['eligible_key']) if eligible else min(items,key=lambda i:i['selection_key'])
 out=dict(status='FROZEN_BEFORE_CONFIRM8',utc=w.now(),selected=chosen['method'],target_met=bool(eligible),candidates=items,baseline_nominal85=b,baseline_original4=old,completed_prior=len(rows),failures_prior=len(failures),confirm_environments_seen=0,source_sha256=w.sha(Path(__file__)),protocol_sha256=w.sha(H/'PROTOCOL.json'),adopted=False)
 w.save(H/'SELECTION_FROZEN.json',out);print('SELECTION_FROZEN',chosen['method'],'target_met',bool(eligible),flush=True)
def preflight(op,p):
 subprocess.run([op['node'],str(H/'preflight.cjs')],cwd=R,check=True);subprocess.run([op['node'],str(H/'abi_preflight.cjs')],cwd=R,check=True)
 nets,before,_,digest,torch,np=w.models(p)
 with (H/'BC_NETWORK_ARRAYS.npz').open('xb') as dest:np.savez_compressed(dest,**{k:v.detach().numpy() for k,v in nets['BC'].state_dict().items()})
 w.save(H/'PREFLIGHT_RECEIPT.json',dict(status='PASS',utc=w.now(),guard_sha256=w.sha(H/'PREFLIGHT.json'),ABI_sha256=w.sha(H/'PREFLIGHT_ABI.json'),checkpoint_sha256=p['checkpoint_sha256'],network_sha256=before['BC'],arrays_sha256=w.sha(H/'BC_NETWORK_ARRAYS.npz'),new_environments=0))
 print('BC_PREFLIGHT_AND_CHECKPOINT_PASS',before['BC'],flush=True)
def evaluate(op,p):
 assert w.read(H/'PREFLIGHT_RECEIPT.json')['status']=='PASS' and not O.exists(),'New registration once only'
 nets,before,_,digest,torch,np=w.models(p);O.mkdir(parents=True);began=time.monotonic();rows=[];failures=[];count=0
 w.save(O/'START.json',dict(utc=w.now(),operation_sha256=w.sha(H/'OPERATION.json'),pid=os.getpid(),network_sha256=before,adopted=False))
 cases=w.read(H/'INPUTS.json')['cases']
 try:
  for cohort in ['development32','original4','confirm8']:
   if cohort=='confirm8':select_before_confirmation(rows,p,failures)
   for ci,c in enumerate(q for q in cases if q['repair_cohort']==cohort):
    w.pins(op);resource=w.guard(op);methods=p['method_groups'][cohort];methods=methods[ci%len(methods):]+methods[:ci%len(methods)]
    for method in methods:
     assert count<60 and time.monotonic()-began<op['wall_cap_s'];count+=1;label='REPAIR_'+c['id']+'__'+method;receipt=dict(event='START',utc=w.now(),label=label,input=c['id'],method=method,cohort=cohort,count=count,identity=hashlib.sha256((w.sha(H/'OPERATION.json')+'|'+label).encode()).hexdigest(),resource=resource);w.append(receipt)
     engine=None;timer=None;start=time.monotonic();decisions=0;overrides=0;reasons={}
     try:
      with (O/(label+'.stderr.txt')).open('x',encoding='utf-8') as err,(O/(label+'.banks.jsonl.gz')).open('xb') as dest:
       with gzip.GzipFile(filename='',mode='wb',fileobj=dest,mtime=0,compresslevel=3) as banks:
        engine=subprocess.Popen([op['node'],str(H/'server.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,encoding='utf-8',cwd=R,bufsize=1);timer=threading.Timer(min(op['per_case_wall_cap_s'],op['wall_cap_s']-(time.monotonic()-began)),lambda:engine.kill() if engine.poll() is None else None);timer.daemon=True;timer.start();engine.stdin.write(json.dumps(dict(input=c['id'],method=method))+'\n');engine.stdin.flush()
        while True:
         line=engine.stdout.readline();assert line,'Engine closed before result';msg=json.loads(line)
         if msg['type']=='FAIL':w.save(O/(label+'.failed.json.gz'),msg);raise RuntimeError(msg['error'])
         if msg['type']=='DONE':raw=msg['result'];telemetry=msg['telemetry'];break
         assert msg['type']=='BANK';bank=msg['bank'];x=np.asarray(bank['x'],np.float32);mask=np.asarray(bank['mask'],bool);assert x.shape==(27,32) and mask.any()
         with torch.no_grad():logits,_=nets['BC'](torch.from_numpy(x)[None],torch.from_numpy(mask)[None]);values=logits[0].numpy().copy()
         raw_index=int(values.argmax());guard=bank.get('guard');allowed=guard['allowed_indices'] if guard else [i for i,v in enumerate(mask) if v];assert allowed and all(mask[i] for i in allowed)
         index=max(allowed,key=lambda i:(float(values[i]),-i));decisions+=1;overrides+=index!=raw_index;reason=guard['reason'] if guard else 'ORIGINAL_BC';reasons[reason]=reasons.get(reason,0)+1
         record=dict(bank=bank,index=index,raw_BC_index=raw_index,BC_logits=values.tolist(),override=index!=raw_index,guard_reason=reason,network_sha256=before['BC']);banks.write((json.dumps(record,separators=(',',':'))+'\n').encode());engine.stdin.write(json.dumps(dict(index=index))+'\n');engine.stdin.flush()
        timer.cancel();w.save(O/(label+'.raw.json.gz'),raw)
      row=dict(label=label,input=c['id'],method=method,cohort=cohort,family=c['family'],mix=c['mix'],replicate=c['replicate'],stream=c['stream'],n=c['n'],rate=c['rate'],empirical_rate=c['empirical_rate'],service=raw['service'],unfinished=raw['unfinished'],J=raw['physics_J'],AP_mean=raw['AP_mean'],AP_peak=raw['AP_peak_sampled'],outside_AP=raw['outside_marginal_AP'],observation_s=raw['observation_end_s'],routes=raw['policy_route_counts'],wait_s=raw['wait_s'],nominal_compute=raw['nominal_compute'],telemetry=telemetry,decisions=decisions,neural_calls=decisions,BC_overrides=overrides,guard_reasons=reasons,network_sha256=before['BC'] if decisions else None,raw_sha256=w.sha(O/(label+'.raw.json.gz')),banks_sha256=w.sha(O/(label+'.banks.jsonl.gz')),wall_s=time.monotonic()-start,adopted=False,physical_validation=False)
      w.save(O/(label+'.json'),row);rows.append(row);w.append({**receipt,'event':'COMPLETE','utc':w.now(),'raw_sha256':row['raw_sha256']});print('REPAIR_COMPLETE',count,cohort,c['id'],method,'J',round(row['J'],3),'urgent',row['service']['urgent']['on_time'],'unfin',row['unfinished'],'overrides',overrides,'wall',round(row['wall_s'],1),flush=True)
     except Exception as error:
      failure={**receipt,'event':'FAIL','utc':w.now(),'error':str(error),'automatic_retry':False};failures.append(failure);w.append(failure);w.save(O/(label+'.failure.json'),dict(**failure,traceback=traceback.format_exc()));print('PRESERVED_FAILURE',count,label,str(error)[:160],flush=True)
     finally:
      if timer:timer.cancel()
      if engine:
       if engine.stdin:engine.stdin.close()
       try:engine.wait(timeout=5)
       except subprocess.TimeoutExpired:engine.kill();engine.wait(timeout=5)
  assert count==60 and all(digest(nets[k])==v for k,v in before.items());w.pins(op)
  w.save(O/'RESULT.json',dict(status='COMPLETE_GUARDED_BC60_NOT_ADOPTED',utc=w.now(),START=count,COMPLETE=len(rows),FAIL=len(failures),rows=rows,failures=failures,network_sha256=before,new_training=0,new_measurements=0,new_fit=0,completed_reruns=0,adopted=False,elapsed_s=time.monotonic()-began));w.save(O/'COMPLETE.json',dict(utc=w.now(),START=count,COMPLETE=len(rows),FAIL=len(failures),result_sha256=w.sha(O/'RESULT.json')))
 except BaseException as error:w.save(O/'OPERATION_FAILURE.json',dict(utc=w.now(),error=str(error),traceback=traceback.format_exc(),automatic_retry=False));raise
if __name__=='__main__':
 op=w.read(H/'OPERATION.json');p=w.read(H/'PROTOCOL.json');w.pins(op);w.guard(op)
 with Path(op['shared_mutex']).open('r+b') as lock:
  lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
  try:
   if sys.argv[1:]==['--preflight']:preflight(op,p)
   elif sys.argv[1:]==['--evaluate']:evaluate(op,p)
   else:raise ValueError('Explicit preflight/evaluate only')
  finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
