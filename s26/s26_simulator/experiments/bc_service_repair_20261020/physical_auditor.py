"""Read-only audit/aggregation of the new registered experiment; no plant or NN."""
import csv,datetime,gzip,hashlib,itertools,json,math,statistics,subprocess,importlib.util,msvcrt
from collections import Counter,defaultdict
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[2];O=H/'artifacts/G001';checks=0;pools={}
def read(p):
 b=p.read_bytes();return json.loads((gzip.decompress(b) if p.suffix=='.gz' else b).decode('utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def need(v,msg):
 global checks
 checks+=1
 if not v:raise AssertionError(msg)
def close(a,b,msg,tol=1e-7):need(a is not None and b is not None and abs(a-b)<=tol,msg)
def save(p,x):
 with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def guarded(folder,fn):
 spec=importlib.util.spec_from_file_location('local_resource_guards',Path(__file__).resolve().parent/'worker.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w);w.H=folder
 op=read(folder/'OPERATION.json');w.pins(op);w.guard(op)
 with Path(op['shared_mutex']).open('r+b') as lock:
  lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
  try:return fn()
  finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def q95(xs):return sorted(xs)[math.ceil(.95*len(xs))-1] if xs else None
def average(xs):return statistics.mean(xs) if xs else None
def semantic(d):return [d['time'],*[d['action'].get(k) for k in ['kind','ordinal','route','wait_s']]]
def seeded(text):
 h=2166136261
 for char in text:h=((h^ord(char))*16777619)&0xffffffff
 h^=h>>16;h=(h*0x7feb352d)&0xffffffff;h^=h>>15
 return h&0xffffffff
def descriptive(row,raw):
 plans={q['ordinal']:q for q in raw['planned_requests']};delays=[max(0,q['times']['dispatch']-plans[q['ordinal']]['readyAt']) for q in raw['requests'] if q['times'] is not None]
 row['response_max_s']={g:max((q['response']-q['arrival'] for q in raw['requests'] if q['response'] is not None and (g=='all' or q['priority']==g)),default=None) for g in ['all','urgent','normal']}
 row['ready_to_dispatch_mean_s']=average(delays);row['ready_to_dispatch_P95_s']=q95(delays);row['ready_to_dispatch_max_s']=max(delays,default=None)
 later=0;overdue=0
 for d in raw['policy_decisions']:
  if d['action'].get('route')!='detection_CPU':continue
  ready=[q for q in d['public_observation']['ready'] if q['task']=='detection'];head=min(ready,key=lambda q:(q['deadline'],q['arrival'],q['ordinal']));chosen=next(q for q in ready if q['ordinal']==d['action']['ordinal'])
  if chosen['deadline']>head['deadline']+1e-9:later+=1;overdue+=head['deadline']<d['time']
 row['normal_later_deadline_dispatches']=later;row['normal_overtakes_overdue_head']=overdue
 busy={slot:sum(max(0,(q['available'] if q['available'] is not None else min(raw.get('censor_s',raw['observation_end_s']),raw['observation_end_s']))-q['times']['dispatch']) for q in raw['requests'] if q['route'] and q['route'].endswith('_'+slot)) for slot in ['CPU','GPU','NPU']}
 supply=row['n']/row['empirical_rate'];row['observed_slot_busy_s']=busy;row['CPU_slot_busy_to_supply_ratio']=busy['CPU']/supply;row['CPU_slot_busy_fraction_observation']=busy['CPU']/(raw['observation_end_s']-35)
 return row
def audit(row,raw,c,m):
 descriptive(row,raw)
 qs=raw['requests'];need(len(qs)==row['n']==c['n']==1024,'All arrival denominator retained')
 close(raw['physics_J'],row['J'],'Energy row');close(sum(x[2] for x in raw['integrals'])+35*raw['baseline_API_W'],row['J'],'Independent integral energy')
 close(sum(x[3] for x in raw['integrals'])/(raw['observation_end_s']-35),row['AP_mean'],'Independent AP integral')
 close(max(x[1] for x in raw['curve']),row['AP_peak'],'Peak AP')
 need(row['unfinished']==raw['unfinished']==sum(q['available'] is None for q in qs),'Unfinished includes unstarted')
 close(raw['observation_end_s'],c['horizon_s'],'Same full observation horizon')
 need(raw['cpu_workers']==3 and raw['max_owners']<=3 and all(0<=v[2]<=3 for v in raw['cpu_concurrency_trace']),'CPU3 bound')
 for g in ['all','urgent','normal']:
  sub=[q for q in qs if g=='all' or q['priority']==g];completed=[q for q in sub if q['response'] is not None];s=row['service'][g]
  need(len(sub)==s['planned'] and len(completed)==s['completed'],'All-arrival service denominator')
  need(sum(q['response']<=q['deadline']+1e-9 for q in completed)==s['on_time'],'Deadline success count')
  expected=q95([q['response']-q['arrival'] for q in completed]);need(expected==s['p95_s'] or expected is not None and s['p95_s'] is not None and abs(expected-s['p95_s'])<1e-8,'Completed response P95')
 for slot in ['CPU','GPU','NPU']:
  intervals=sorted((q['times']['dispatch'],q['available'] if q['available'] is not None else raw['observation_end_s']) for q in qs if q['route'] and q['route'].endswith('_'+slot))
  need(all(a[1]<=b[0]+1e-8 for a,b in zip(intervals,intervals[1:])),'Shared route slot occupied through AVAILABLE')
 byordinal={q['ordinal']:q for q in qs};need(len(byordinal)==1024,'Unique request ordinal')
 for planned in c['requests']:
  q=byordinal[planned['ordinal']];need(q['task']==planned['task_id'] and q['priority']==planned['priority'],'Fixed supported task-priority')
  close(q['arrival'],planned['offset_ns']/1e9,'Registered actual arrival',1.1e-9);close(q['deadline']-q['arrival'],planned['deadline_ms']/1000,'Unchanged relative deadlines')
  need(q['task']!='detection' or q['route'] in [None,'detection_CPU'],'Detection CPU only')
  if q['available'] is not None:need(q['times']['dispatch']<=q['response']<=q['available']+1e-9,'Response within occupancy')
 for q in raw['planned_requests']:
  route='classification_GPU' if q['task']=='classification' else 'detection_CPU';pool=pools[route+'|'+q['priority']];template=pool[seeded(str(c['stream'])+'|enqueue|'+str(q['ordinal']))%len(pool)]
  need(q['enqueueTemplate']==template['id'],'Independent deterministic enqueue template');close(q['readyAt']-q['arrival'],template['enqueue_delay_s'],'Frozen enqueue delay')
 for event in raw['events']:
  if event[1]=='DISPATCH':
   q=byordinal[event[2]];pool=pools[event[3]+'|'+q['priority']];template=pool[seeded(str(c['stream'])+'|phase|'+str(q['ordinal'])+'|'+event[3])%len(pool)]
   need(event[4]==template['id'],'Independent per-request/route latent template, no policy RNG leakage')
 t=row['telemetry']
 if not m['rolling']:need(t['rollout_calls']==raw['forecast_calls']==raw['nominal_compute']['logical_queries']==raw['nominal_compute']['actual_computations']==0,'No rolling means zero rollout/query count')
 if not m['ATC']:need(t['ATC_evaluations']==0,'No ATC scoring')
 if m.get('standalone'):need(t['nominal_timing_calls']==0,'Pure teacher has no timing predictor')
 banks=0;decision_digest=[];max_ready=0;max_actions=0;wait_with_urgent_alternative=0;wait_with_already_late_urgent=0;chosen_kinds=Counter()
 with gzip.open(O/(row['label']+'.banks.jsonl.gz'),'rt',encoding='utf-8') as f:
  if m['selector'] in ['EDF','STATIC']:
   need(not f.read(),'EDF has no NN bank');need(row['decisions']==row['neural_calls']==0,'EDF zero neural/planning selector calls')
   for d in raw['policy_decisions']:
    if m['selector']=='STATIC':
     need(d['action']['kind'] in ['DISPATCH','WAIT_EVENT'],'Static rule dispatch or owner wait only');chosen_kinds[d['action']['kind']]+=1;continue
    obs=d['public_observation'];busy={owner['route'].split('_')[-1] for owner in obs['owners']};order=['NPU','GPU','CPU'] if m['id']=='EDF_NPU' else ['GPU','NPU','CPU'];expected=None
    for q in sorted(obs['ready'],key=lambda q:(q['deadline'],q['arrival'],q['ordinal'])):
     available=[slot for slot in (order if q['task']=='classification' else ['CPU']) if slot not in busy]
     if available and len(obs['owners'])<obs['capacity']:expected=(q['ordinal'],q['task']+'_'+available[0]);break
    need(expected==(d['action']['ordinal'],d['action']['route']),'Independent unconstrained EDF route/order audit');chosen_kinds[d['action']['kind']]+=1
  else:
   for record,d in itertools.zip_longest((json.loads(line) for line in f),raw['policy_decisions']):
    need(record is not None and d is not None,'Every meaningful policy decision bank retained');banks+=1;b=record['bank'];i=record['index'];a=b['actions'][i]
    need(b['mask'][i] and d['action']['decision_index']==i,'Selected legal action applied');need(all(d['action'].get(k)==v for k,v in a.items()),'No post-selector override')
    chosen_kinds[a['kind']]+=1
    if a['kind'] in ['WAIT','WAIT_EVENT']:
     urgent=[j for j,v in enumerate(b['mask']) if v and b['actions'][j]['kind']=='DISPATCH' and byordinal[b['actions'][j]['ordinal']]['priority']=='urgent']
     wait_with_urgent_alternative+=bool(urgent);wait_with_already_late_urgent+=any(b['x'][j][8]<0 for j in urgent)
    close(b['time_ns']/1e9,d['time'],'Decision timestamp',1.1e-9)
    need(b['constraints']==(dict(base_physical_mask_only=True,post_neural_guard=True,deadline_protection=m['id']!='BC_DISPATCH_ONLY',new_training=False) if m['selector']=='BC_REPAIR' else dict(physical_slots_only=True,deadline_action_mask=False,critical_request_override=False,fixed_ATC_prior=False,post_NN_override=False)),'Explicit original/repair constraints')
    if m.get('standalone'):need(b['decision_ready']==b['ready_total'],'Pure teacher full queue')
    else:need(b['decision_ready']<=8 and len(b['x'])==len(b['mask'])==27,'Original8/27 capacity')
    if m['selector']=='BC' and not m['rolling']:need(all(v[k]==0 for v in b['x'] for k in range(21,30)),'Zero forecast features')
    if m['selector']=='BC' and not m['ATC']:need(all(v[11]==0 for v in b['x']),'Zero ATC feature')
    if m['selector']=='TEACHER':
     preferred=[j for j,valid in enumerate(b['mask']) if valid and b['actions'][j]['kind']=='DISPATCH' and b['x'][j][31]>.5]
     expected=min(preferred,key=lambda j:(b['x'][j][8],b['actions'][j]['ordinal'],j)) if preferred else next(j for j,valid in enumerate(b['mask']) if valid and b['actions'][j]['kind']=='WAIT_EVENT')
     need(i==expected,'Independent teacher choice audit')
    max_ready=max(max_ready,b['ready_total']);max_actions=max(max_actions,len(b['actions']))
   need(banks==row['decisions'],'Bank denominator')
 return dict(requests=1024,banks=banks,max_ready=max_ready,max_actions=max_actions,chosen_kinds=dict(chosen_kinds),wait_with_urgent_dispatch_available=wait_with_urgent_alternative,wait_with_already_late_urgent_dispatch_available=wait_with_already_late_urgent,unstarted=sum(q['route'] is None for q in qs),response_missing=sum(q['response'] is None for q in qs),semantic_trace_sha256=digest([semantic(d) for d in raw['policy_decisions']]),routes={str(q['ordinal']):q['route'] for q in qs},planned_sha256=digest([{k:q[k] for k in ['ordinal','task','priority','arrival','deadline','readyAt','enqueueTemplate']} for q in raw['planned_requests']]))
def aggregate(rows):
 out=dict(cases=len(rows),J_mean=average([r['J'] for r in rows]),AP_mean=average([r['AP_mean'] for r in rows]),AP_peak_max=max((r['AP_peak'] for r in rows),default=None),unfinished=sum(r['unfinished'] for r in rows),outside_AP_cases=sum(bool(r['outside_AP']) for r in rows),neural_calls=sum(r['neural_calls'] for r in rows),nominal_queries=sum(r['nominal_compute']['logical_queries'] for r in rows),rollout_calls=sum(r['telemetry']['rollout_calls'] for r in rows),ATC_evaluations=sum(r['telemetry']['ATC_evaluations'] for r in rows),host_wall_s_mean=average([r['wall_s'] for r in rows]))
 out['wait_s_mean']=average([r['wait_s'] for r in rows]);out['wait_s_max']=max((r['wait_s'] for r in rows),default=None)
 out['normal_later_deadline_dispatches']=sum(r.get('normal_later_deadline_dispatches',0) for r in rows);out['normal_overtakes_overdue_head']=sum(r.get('normal_overtakes_overdue_head',0) for r in rows)
 out['CPU_slot_busy_to_supply_ratio_mean']=average([r['CPU_slot_busy_to_supply_ratio'] for r in rows if 'CPU_slot_busy_to_supply_ratio' in r]);out['CPU_slot_busy_fraction_observation_mean']=average([r['CPU_slot_busy_fraction_observation'] for r in rows if 'CPU_slot_busy_fraction_observation' in r])
 out['urgent_violation_cases']=sum(r['service']['urgent']['on_time']<r['service']['urgent']['planned'] for r in rows)
 out['unfinished_cases']=sum(r['unfinished']>0 for r in rows)
 out['urgent100_and_zero_unfinished_cases']=sum(r['service']['urgent']['on_time']==r['service']['urgent']['planned'] and r['unfinished']==0 for r in rows)
 for g in ['all','urgent','normal']:
  planned=sum(r['service'][g]['planned'] for r in rows);on=sum(r['service'][g]['on_time'] for r in rows);out[g]=dict(planned=planned,ontime=on,ontime_percent_pooled=100*on/planned if planned else None,ontime_percent_mean=average([100*r['service'][g]['on_time']/r['service'][g]['planned'] for r in rows]),P95_s_mean=average([r['service'][g]['p95_s'] for r in rows if r['service'][g]['p95_s'] is not None]),max_completed_response_s=max((r.get('response_max_s',{}).get(g) for r in rows if r.get('response_max_s',{}).get(g) is not None),default=None),worst_case_ontime_percent=min((100*r['service'][g]['on_time']/r['service'][g]['planned'] for r in rows),default=None))
 out['ready_to_dispatch_case_mean_s']=average([r['ready_to_dispatch_mean_s'] for r in rows if r.get('ready_to_dispatch_mean_s') is not None]);out['ready_to_dispatch_max_s']=max((r['ready_to_dispatch_max_s'] for r in rows if r.get('ready_to_dispatch_max_s') is not None),default=None)
 return out
def compare(rows,left,right,audits,expected_cases=32):
 ls={r['input']:r for r in rows if r['method']==left};rs={r['input']:r for r in rows if r['method']==right};pairs=[]
 for c in sorted(ls.keys()&rs.keys()):
  a,b=ls[c],rs[c];aa,bb=audits[a['label']],audits[b['label']];need(aa['planned_sha256']==bb['planned_sha256'],'Identical registered plan/template streams')
  pair=dict(input=c,family=a['family'],mix=a['mix'],replicate=a['replicate'],delta_J=a['J']-b['J'],delta_J_percent=100*(a['J']-b['J'])/b['J'],delta_AP=a['AP_mean']-b['AP_mean'],delta_unfinished=a['unfinished']-b['unfinished'],exact_semantic_trace=aa['semantic_trace_sha256']==bb['semantic_trace_sha256'],same_routes=sum(aa['routes'][str(i)]==bb['routes'][str(i)] for i in range(1024)))
  for g in ['all','urgent','normal']:pair['delta_'+g+'_on_pp']=100*(a['service'][g]['on_time']-b['service'][g]['on_time'])/a['service'][g]['planned'];pair['delta_'+g+'_P95_s']=None if a['service'][g]['p95_s'] is None or b['service'][g]['p95_s'] is None else a['service'][g]['p95_s']-b['service'][g]['p95_s']
  pairs.append(pair)
 a=aggregate([ls[c] for c in ls.keys()&rs.keys()]);b=aggregate([rs[c] for c in ls.keys()&rs.keys()]);valid=len(pairs)==expected_cases
 delta=dict(J=a['J_mean']-b['J_mean'] if pairs else None,J_percent=100*(a['J_mean']/b['J_mean']-1) if pairs else None,all_on_pp=a['all']['ontime_percent_pooled']-b['all']['ontime_percent_pooled'] if pairs else None,urgent_on_pp=a['urgent']['ontime_percent_pooled']-b['urgent']['ontime_percent_pooled'] if pairs else None,unfinished=a['unfinished']-b['unfinished'])
 service_pass=bool(valid and delta['all_on_pp']>=1 and delta['urgent_on_pp']>=-.1 and delta['unfinished']<=0)
 energy_pass=bool(valid and delta['J_percent']<=-1 and abs(delta['all_on_pp'])<=.1 and abs(delta['urgent_on_pp'])<=.1 and delta['unfinished']<=0)
 return dict(left=left,right=right,matched_cases=len(pairs),expected_case_count=expected_cases,all32_present=len(pairs)==32,all_registered_cases_present=valid,delta=delta,practical_service_gain_pass=service_pass,practical_energy_gain_pass=energy_pass,practical_either_pass=service_pass or energy_pass,energy_lower_cases=sum(p['delta_J']<-1e-8 for p in pairs),service_better_cases=sum(p['delta_all_on_pp']>0 for p in pairs),service_worse_cases=sum(p['delta_all_on_pp']<0 for p in pairs),urgent_worse_cases=sum(p['delta_urgent_on_pp']<0 for p in pairs),exact_trace_cases=sum(p['exact_semantic_trace'] for p in pairs),worst_all_on_delta_pp=min((p['delta_all_on_pp'] for p in pairs),default=None),worst_urgent_on_delta_pp=min((p['delta_urgent_on_pp'] for p in pairs),default=None),pairs=pairs)
def main():
 op=read(H/'OPERATION.json');p=read(H/'PROTOCOL.json');result=read(O/'RESULT.json');cases={c['id']:c for c in read(H/'INPUTS.json')['cases']};methods={m['id']:m for m in p['methods']}
 cache=read(H/'CACHE_FORECAST_AUDIT.json');proof=read(H/'TEACHER_EQUIVALENCE.json');need(cache['audit_execution']=='PASS' and proof['status']=='PASS_SUFFICIENT_CONDITION_PROOF','Offline checks executed; forecast gate is reported separately')
 need(sha(H/'PROTOCOL.json')==op['protocol_sha256'],'Preregistered protocol unchanged')
 for pin in op['original_pins']+op['new_source_pins']:need(sha(R/pin['path'])==pin['sha256'],'Pinned source/input/checkpoint '+pin['path'])
 receipts=[json.loads(line) for line in (O/'receipts.jsonl').read_text(encoding='utf-8').splitlines()];counts=Counter(v['event'] for v in receipts);need(counts['START']==320,'All320 unique consumed attempts');need(counts['COMPLETE']==len(result['rows']) and counts['FAIL']==len(result['failures']),'Failure preservation')
 need(len({v['identity'] for v in receipts if v['event']=='START'})==320,'No consumed identity repeated');need(len(result['rows'])+len(result['failures'])==320,'All attempts reported')
 for template in read(R/'s26_simulator/experiments/multiresource_v1/PACKET.json.gz')['templates']:
  if template['overlap_fraction']==0 and not template.get('priority_transfer'):pools.setdefault(template['route']+'|'+template['priority'],[]).append(template)
 rows=result['rows'];audits={}
 for number,row in enumerate(rows,1):
  rawpath=O/(row['label']+'.raw.json.gz');need(sha(rawpath)==row['raw_sha256'],'Raw SHA');need(sha(O/(row['label']+'.banks.jsonl.gz'))==row['banks_sha256'],'Bank SHA')
  audits[row['label']]=audit(row,read(rawpath),cases[row['input']],methods[row['method']])
  if number%40==0:print('AUDITED',number,'checks',checks,flush=True)
 summary={m:aggregate([r for r in rows if r['method']==m]) for m in methods}
 byfamily={f:{m:aggregate([r for r in rows if r['method']==m and r['family']==f]) for m in methods} for f in sorted({c['family'] for c in cases.values()})}
 bymix={str(mix):{m:aggregate([r for r in rows if r['method']==m and r['mix']==mix]) for m in methods} for mix in [.5,.75]}
 comparisons=[compare(rows,a,b,audits) for a,b in [('BC_FULL','TEACHER_ONLY'),('PPO_FULL','BC_FULL'),('BC_NO_ROLLING','BC_FULL'),('BC_NO_ATC','BC_FULL'),('BC_NO_BOTH','BC_FULL'),('ROLLING_SERVICE_FIRST','TEACHER_ONLY'),('ROLLING_SERVICE_FIRST','EDF_NPU'),('TEACHER_ONLY','EDF_NPU'),('TEACHER_ONLY','EDF_GPU'),('BC_FULL','EDF_NPU'),('PPO_FULL','TEACHER_ONLY')]]
 # Detailed ordinal routes are only temporary in-memory audit work, hashes persist.
 for a in audits.values():a.pop('routes')
 with (H/'RESULTS.csv').open('x',encoding='utf-8-sig',newline='') as f:
  fields=['input','family','mix','replicate','method','J','AP_mean','AP_peak','unfinished','outside_AP','wall_s','neural_calls','nominal_queries','all_on_percent','urgent_on_percent','normal_on_percent','urgent_P95_s'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for r in rows:w.writerow({**{k:r[k] for k in fields if k in r},'nominal_queries':r['nominal_compute']['logical_queries'],**{g+'_on_percent':100*r['service'][g]['on_time']/r['service'][g]['planned'] for g in ['all','urgent','normal']},'urgent_P95_s':r['service']['urgent']['p95_s']})
 out=dict(status='PASS_SAVED_FOLLOWUP_AUDIT',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),HEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),tracked_changes=subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=R,text=True).splitlines(),checks=checks,START=320,COMPLETE=len(rows),FAIL=len(result['failures']),new_training=0,new_measurements=0,new_fit=0,completed_reruns=0,adopted=False,summary=summary,byfamily=byfamily,bymix=bymix,comparisons=comparisons,raw_audits=audits,mechanism=read(H/'MECHANISM.json'),preflight=read(H/'PREFLIGHT.json'),forecast_cache_exactness_gate=cache['status'],forecast_cache_audit_sha256=sha(H/'CACHE_FORECAST_AUDIT.json'),teacher_equivalence_sha256=sha(H/'TEACHER_EQUIVALENCE.json'),forensic_case_sha256=sha(H/'CASE_DIAGNOSIS.json'),operation_sha256=sha(H/'OPERATION.json'),analysis_source_sha256=sha(Path(__file__)),limitations=[p['physical_gate'],p['BC_lineage'],p['ablations'],'New pseudo-random arrivals use the same finite measured template pools and initial context; this is a generator stress test, not independent device/task validation.','Accounting/slot validation PASS is separate from forecast-cache exactness and failed physical accuracy. Original frozen cached implementation was evaluated unchanged.','No candidate is automatically adopted. No old and new cohort averages are pooled.'])
 save(H/'ANALYSIS.json',out);print(json.dumps(dict(summary=summary,comparisons=[{k:v for k,v in c.items() if k!='pairs'} for c in comparisons],checks=checks),indent=2),flush=True)
if __name__=='__main__':guarded(H,main)
