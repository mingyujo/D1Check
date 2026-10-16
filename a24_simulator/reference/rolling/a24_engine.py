"""New, causal online A24 scheduler. Predecessor source/outputs are read only.

Primary counterfactual: route-specific SERIAL whole measured vectors are shared
across schedulers. Admission uses the same canonical route for every scheduler.
Controller redispatch is explicitly ideal zero, not a measured ATC/RL latency.
No thermal throttling feedback or unsupported routes are invented.
"""
from __future__ import annotations
import copy, hashlib, heapq, importlib.util, json, math, statistics, sys
from pathlib import Path
import numpy as np
import policy_bridge
import timing_bridge
import a24_cost_adapter
from a24_cost_adapter import OnlineCost

B=Path('C:/Users/chomg/Documents/Codex/2026-10-11/dkfo')
OLD=B/'work/SCHEDULER-INTEGRATED-S26-20261016'
sys.path.insert(0,str(OLD))
_spec=importlib.util.spec_from_file_location('frozen_int001_engine',OLD/'engine.py')
legacy=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(legacy)
NS=10**9
PHASES=timing_bridge.PHASES;KINDS=timing_bridge.KINDS;wire=legacy.wire;digest=legacy.digest

def nominal_estimates(profile,scenario,models,model_name):
 out=timing_bridge.nominal_estimates(profile,scenario)
 for r in scenario['requests']:
  for route,x in out[r['request_id']].items():
   x['energy_proxy_j']=a24_cost_adapter.nominal_energy_proxy(r['task'],route,x['occupancy_ns'],model_name,models)
 return {rid:{route:{k:x[k] for k in ['occupancy_ns','response_ns','energy_proxy_j']} for route,x in routes.items()} for rid,routes in out.items()}

def compile_scenario(recipe):return timing_bridge.compile_scenario(recipe)

def simulate(profile,scenario,manifest,models,initial,model_name,controller=None,
             family='JOINT_ATC_RL',rule=None,sample_seed=0,alpha=.95,
             allow_wait=True,decision_mode='EVENT',capture=True):
 nominal=nominal_estimates(profile,scenario,models,model_name)
 cost=OnlineCost(models,initial,model_name)
 public_sensor=cost.snapshot();sensor_time=0
 calendar=[];sequence=0;now=0;events=[];rows={};hidden={};owners={};queue=set();seen=set()
 deadline_missed=set();responded=set();waited=set();waited_bursts=set();wait_used=0;wait_until=0;decisions=[];curve=[]
 frames=[];cost_at=[];stop=int(scenario['service_stop_ns']);drain=int(scenario['drain_stop_ns'])
 end=int(scenario['observation_end_ns']);counts={p:sum(r['priority']==p for r in scenario['requests']) for p in ['U','N']}
 def push(t,priority,kind,rid=None,extra=None):
  nonlocal sequence
  if type(t)!=int or t<0:raise ValueError('exact nonnegative event ns')
  sequence+=1;heapq.heappush(calendar,(t,priority,sequence,kind,rid,extra))
 def emit(kind,rid=None,owner=None,payload=None):
  if capture:events.append({'sequence':len(events),'logical_time_ns':str(now),'kind':kind,'request_id':rid,'owner':owner,'payload':payload or {}})
 def phasespec(route):return {'classification_route':route,'serial':True,'protocol':'SERIAL','has_wait':True}
 for r in scenario['requests']:
  samples={}
  for route in nominal[r['request_id']]:
   sample=timing_bridge.sample(profile,scenario,r,route,sample_seed,protocol='SERIAL')
   samples[route]=sample
  canonical='GPU' if r['task']=='C' else 'CPU'
  if canonical not in samples:raise ValueError('Canonical admission route unavailable')
  admission=samples[canonical]['admission_lags_ns']
  actual=r['scheduled_arrival_ns']+int(admission['scheduled_to_actual'])
  entry=actual+int(admission['actual_to_queue'])
  row={**copy.deepcopy(r),'actual_arrival_ns':None,'queue_entry_ns':None,'dispatch_ns':None,
   'backend':None,'owner':None,'model_sha256':None,'terminal_status':'NOT_DISPATCHED'}
  for f in PHASES:row[f]=None
  row['execution_ns']=None;row['readback_complete_ns']=None
  rows[r['request_id']]=row;hidden[r['request_id']]=samples
  push(actual,20,'ACTUAL_ARRIVAL',r['request_id']);push(entry,21,'ENQUEUE',r['request_id'])
  push(r['deadline_ns'],30,'DEADLINE',r['request_id'])
 for t in range(0,end+1,500_000_000):push(t,40,'SENSOR')
 for t in [35*NS,120*NS,180*NS,end]:push(t,41,'BOUNDARY')
 if decision_mode=='TICK200':
  for t in range(0,stop,200_000_000):push(t,42,'TICK')
 push(stop,0,'SERVICE_STOP');push(drain,98,'DRAIN_STOP');push(end,99,'END')
 def cumulative():
  eh=cost.snapshot()['cost_cumulative2']
  return np.asarray([*eh[:2],sum(rows[x]['priority']=='U' for x in deadline_missed)/max(counts['U'],1),
   sum(rows[x]['priority']=='N' for x in deadline_missed)/max(counts['N'],1),0.],np.float64)
 while calendar:
  now=calendar[0][0]
  if now>end:break
  cost.advance(now)
  kinds=[]
  while calendar and calendar[0][0]==now:
   _,_,_,kind,rid,extra=heapq.heappop(calendar);kinds.append(kind)
   if kind=='ACTUAL_ARRIVAL':rows[rid]['actual_arrival_ns']=now;seen.add(rid);emit(kind,rid)
   elif kind=='ENQUEUE':rows[rid]['queue_entry_ns']=now;queue.add(rid);emit(kind,rid)
   elif kind=='DEADLINE':
    if rid not in responded:deadline_missed.add(rid)
    emit(kind,rid)
   elif kind in KINDS:
    row=rows[rid];f=extra['field'];row[f]=now
    if f=='execution_start_ns':row['execution_ns']=now
    if f=='readback_end_ns':row['readback_complete_ns']=now
    if kind=='AVAILABLE':
     if owners.get(row['backend'])!=rid:raise ValueError('Owner release mismatch')
     cost.available(rid,row['backend']);del owners[row['backend']];row['terminal_status']='AVAILABLE'
    elif kind in ['EXECUTION_START','HOST_INFERENCE_START','HOST_INFERENCE_RETURN','OUTPUT_READY']:
     cost.phase(rid,kind)
    elif kind=='RESPONSE':responded.add(rid)
    emit(kind,rid,row['backend'])
   elif kind=='WAIT_END':emit(kind,payload={'wait_until_ns':str(wait_until)})
   else:
    emit(kind)
    if kind=='SENSOR':
     s=cost.snapshot();public_sensor=s;sensor_time=now
     curve.append({'time_s':now/NS,'J':s['continuous_energy_j'],'AP_c':s['AP_c'],'power_w':s['power_w']})
  if now>=stop or now<wait_until:continue
  if decision_mode=='TICK200' and 'TICK' not in kinds:continue
  micro=0
  while queue and now<stop:
   micro+=1
   if micro>len(rows)*3+16:raise RuntimeError('Zero-time controller loop')
   eligible=[{k:rows[rid][k] for k in ['request_id','ordinal','task','priority','scheduled_arrival_ns','deadline_ns','burst_index']} for rid in queue]
   sensor=public_sensor
   temp=sensor.get('temperature_c',{})
   obs={'now_ns':now,'queue':eligible,
    'owners':{lane:{'request_id':rid,'task':rows[rid]['task'],'priority':rows[rid]['priority'],'dispatch_ns':rows[rid]['dispatch_ns']} for lane,rid in owners.items()},
    'estimates':{rid:nominal[rid] for rid in (queue|set(owners.values()))},
    'sensor':{'AP_c':sensor.get('AP_c',temp.get('AP')),'SKIN_c':sensor.get('SKIN_c',temp.get('SKIN')),
      'power_w':sensor.get('power_w'),'age_s':(now-sensor_time)/NS},
    'history':{**{'planned_'+p:sum(rows[x]['priority']==p for x in seen) for p in ['U','N']},
     **{'failed_'+p:sum(rows[x]['priority']==p for x in (deadline_missed&seen)) for p in ['U','N']},
     **{'responded_'+p:sum(rows[x]['priority']==p for x in responded) for p in ['U','N']}},
    'alpha':alpha,'initial_AP_c':sensor['initial_AP_c'],
    'wait_used_ns':wait_used,'waited_request_ids':sorted(waited),'waited_burst_ids':sorted(waited_bursts),'device':'A24','horizon_ns':stop}
   bank=policy_bridge.build_bank(obs,rule or family,allow_wait=allow_wait)
   legal_dispatch=any(bank['mask'][i] and a.get('kind')=='DISPATCH' for i,a in enumerate(bank['actions']))
   # Forced busy waiting contains no control choice and needs no NN inference.
   if not legal_dispatch:break
   before=cumulative()
   index=policy_bridge.select_rule(bank,rule) if rule else controller.choose(bank,now)
   if not bank['mask'][index]:raise RuntimeError('Masked policy action')
   a=bank['actions'][index]
   if rule:frames.append({'time_ns':now,'index':int(index)})
   else:frames=controller.frames
   cost_at.append(before)
   decisions.append({'time_ns':str(now),'observation':wire(obs),'chosen_index':int(index),'action':a,
    'mask':bank['mask'].tolist(),'input_sha256':digest(wire(obs)),'diagnostic':bank.get('diagnostic',{})})
   emit('POLICY_DECISION',payload=decisions[-1])
   if len(decisions)>1024:raise RuntimeError('Registered decision cap exceeded')
   if a['kind']=='RESOURCE_WAIT':break
   if a['kind']=='WAIT':
    dose=int(a['wait_ns']);head=bank.get('diagnostic',{}).get('head_request_id')
    if head is None:
     head=min(eligible,key=lambda r:(r['deadline_ns'],r['ordinal']))['request_id']
    wait_used+=dose;waited.add(head);waited_bursts.add(rows[head]['burst_index']);wait_until=min(now+dose,stop)
    if wait_used>12*NS:raise RuntimeError('WAIT budget')
    emit('WAIT_START',payload={'duration_ns':str(wait_until-now),'nominal_ns':str(dose),'head_request_id':head})
    push(wait_until,22,'WAIT_END');break
   if a['kind']!='DISPATCH':raise ValueError('Unsupported action')
   rid=a['request_id'];route=a['route'];row=rows[rid]
   if rid not in queue or route in owners:raise RuntimeError('Illegal dispatch')
   labels={(rows[v]['task'],lane) for lane,v in owners.items()}|{(row['task'],route)}
   if len(labels)>1 and labels not in [{('D','CPU'),('C','GPU')}]:raise RuntimeError('Unsupported overlap')
   sample=hidden[rid][route]
   owners[route]=rid;queue.remove(rid);row.update(dispatch_ns=now,backend=route,owner=route,terminal_status='IN_FLIGHT',model_sha256=sample['model_sha256'])
   row['timing']={'sample_id':sample['sample_id'],'pool_key':sample['key'],'offsets_ns':sample['offsets_ns'],
     'source_ref':sample['source'],'admission_lags_ns':hidden[rid]['GPU' if row['task']=='C' else 'CPU']['admission_lags_ns'],
     'redispatch_delay_ns':0,'redispatch_evidence':'UNIDENTIFIED_IDEAL_CONTROLLER_ASSUMPTION'}
   cost.dispatch(rid,row['task'],route);emit('DISPATCH',rid,route)
   for j,(field,kind) in enumerate(zip(PHASES,KINDS),1):
    offset=sample['offsets_ns'].get(field)
    if offset is not None:push(now+int(offset),j,kind,rid,{'field':field})
   if calendar and calendar[0][0]==now:break
 final=cumulative()
 final[4]=sum(r['lane_available_ns'] is None or r['lane_available_ns']>drain for r in rows.values())/len(rows)
 if not frames:raise RuntimeError('No policy decisions')
 costs=np.zeros((len(frames),5),np.float64)
 costs[0]+=cost_at[0]
 for i in range(1,len(cost_at)):costs[i-1]+=cost_at[i]-cost_at[i-1]
 costs[-1]+=final-cost_at[-1]
 if not np.allclose(costs.sum(0),final,atol=1e-9):raise RuntimeError('Cost telescope')
 allrows=sorted(rows.values(),key=lambda r:r['ordinal'])
 for r in allrows:
  if r['terminal_status']!='AVAILABLE':r['terminal_status']='INCOMPLETE'
 result={'schema':'A24-ROLLING-ATC-RL-RESULT-v1','device':'A24','clock_axis':'common_relative_ns',
  'manifest':manifest,'scenario':copy.deepcopy(scenario),'observation_end_ns':end,
  'policy':{'family':family,'rule':rule,'allow_wait':allow_wait,'decision_mode':decision_mode},
  'requests':allrows,'events':events,'decisions':decisions,'metrics':legacy.metrics(allrows,stop,drain),
  'cost':{'metrics':cost.totals(),'cost_cumulative':cost.snapshot()['cost_cumulative2']},'curve':curve,'cost_labels':{'total':final.tolist(),'telescope_error':float(np.abs(costs.sum(0)-final).max())},
  'seed':sample_seed,'alpha':alpha,'model':model_name,
  'assumptions':['shared route-specific SERIAL measured vectors; concurrency interference not identified',
  'canonical GPU/CPU admission shared across policies; controller delay ideal zero assumption',
  'modeled HAL/power public sensor sampled and held every0.5s; actual M8 sensor refresh accuracy not claimed',
  'fresh PPO shape reuse is not transfer equivalence of old checkpoints',
  'fixed A24 conditional historical gauge/HAL models; new measured J unresolved; no thermal-to-service-time feedback']}
 return wire(result),costs,frames
