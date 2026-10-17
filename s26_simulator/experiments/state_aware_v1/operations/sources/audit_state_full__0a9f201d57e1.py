"""Independent Python replay of all saved public actions and costs, no new plant."""
import collections,importlib.util,json,math,os,time
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
from timing_model import read,save,duration
from audit_simulation_study import predict,fnv,sha,append
from audit_resource_v2 import replay_action,legal,ROUTES

import state_replay
from state_replay import state_expected,public_validate

def fair_expected(obs,nom,options,policy):
 return state_expected(obs,nom,options,policy)

def main(op):
 out=Path(op['output_dir']);out.mkdir();pr=read(op['production_operation']);plan=read(pr['case_plan_path']);packet=read(pr['packet_path'])
 rows=[json.loads(l) for l in (Path(pr['output_dir'])/'ROWS.jsonl').read_text().splitlines() if l.strip()];receipts=collections.defaultdict(list)
 for l in Path(pr['receipts_path']).read_text().splitlines():
  e=json.loads(l);receipts[e['id']].append(e)
 refs=[];items=[dict(config=c,row=r,new=True) for c,r in zip(plan,rows)]+[dict(config=x['config'],row=x['row'],new=False) for x in refs]
 checks=0;maxerror=0.;selected=collections.defaultdict(collections.Counter);candidates=collections.defaultdict(collections.Counter);nominals={};common={};proofs=[]
 def test(ok,label):
  nonlocal checks
  checks+=1
  if not ok:raise ValueError(label)
 test(len(plan)==len(rows)==300 and len(refs)==0,'exact300new coverage')
 test(len(receipts)==300,'no extra environment identities')
 spec=importlib.util.spec_from_file_location('independent_direct_math',op['direct_math']);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
 state_replay.MODELS=packet;state_replay.DIRECT=old
 forecast_replays=0;max_forecast_error=0.
 for ix,item in enumerate(items):
  c,row=item['config'],item['row'];identity=c['identity'];p=Path(row['raw_path']);raw=read(p);test(sha(p)==row['raw_sha256'],'raw SHA')
  cfg=p.parent.parent/'configurations'/(identity+'.json');test(read(cfg)==c and sha(cfg)==raw['configuration_sha256'],'exact sealed config')
  test(raw['packet_sha256']==sha(pr['packet_path']),'common immutable packet')
  if item['new']:
   ev=receipts[identity];test([e['event'] for e in ev]==['START','PREPARED','COMPLETE'],'durable terminal ledger order')
   test(all(e.get('raw_sha256',row['raw_sha256'])==row['raw_sha256'] for e in ev),'ledger/raw SHA binding')
  s=next(s for s in packet['scenarios'] if s['id']==c['scenario']);planned={q['ordinal']:q for q in raw['planned_requests']};done={q['ordinal']:q for q in raw['requests']};policy=c['policy']
  test(len(planned)==128 and len(done)==len(raw['requests']),'all planned; unique completions')
  canonical=[]
  for q in raw['planned_requests']:
   original=next(x for x in s['requests'] if x['ordinal']==q['ordinal']);test(q['arrival']==original['offset_ns']/1e9 and q['deadline']==q['arrival']+original['deadline_ms']/1000,'fixed arrival/deadline')
   route='classification_GPU' if q['task']=='classification' else 'detection_CPU';pool=[x for x in packet['templates'] if x['route']==route and x['priority']==q['priority']];chosen=pool[fnv(str(c['stream'])+'|enqueue|'+str(q['ordinal']))%len(pool)]
   test(q['enqueueTemplate']==chosen['id'] and q['readyAt']==q['arrival']+chosen['enqueue_delay_s'],'policy independent request potential')
   test(q['completed']==(q['ordinal'] in done),'unfinished retained');canonical.append({k:q[k] for k in ('ordinal','task','priority','arrival','deadline','readyAt','enqueueTemplate')})
  if c['phase']!='P0':
   key=(c['scenario'],c['stream']);test(common.get(key,canonical)==canonical,'matched requests/ready jitter');common[key]=canonical
  for pri in ('all','urgent','normal'):
   pp=[q for q in planned.values() if pri=='all' or q['priority']==pri];dd=[q for q in done.values() if pri=='all' or q['priority']==pri];on=sum(q['response']<=q['deadline']+1e-9 for q in dd);v=raw['service'][pri]
   test((v['planned'],v['completed'],v['on_time'],v['late_or_unfinished'])==(len(pp),len(dd),on,len(pp)-on),'service denominator arithmetic')
   responses=sorted(q['response']-q['arrival'] for q in dd);expected=responses[math.ceil(.95*len(responses))-1] if responses else None;test(v['p95_s']==expected,'P95 arithmetic')
  test(raw['hard_feasible']==(len(done)==128 and raw['service']['all']['on_time']==128),'hard feasible');test(raw['unfinished']==128-len(done),'unfinished denominator');test(abs(raw['tardiness_s']-sum(max(0,q['response']-q['deadline']) for q in done.values()))<1e-9,'tardiness arithmetic')
  owners=[]
  for t,sign,r in sorted([(q['times']['dispatch'],1,q['route']) for q in done.values()]+[(q['times']['AVAILABLE'],-1,q['route']) for q in done.values()],key=lambda x:(x[0],x[1])):
   if sign<0:owners.remove(dict(route=r))
   else:test(legal(r,owners),'actual nonpreemptive route mask');owners.append(dict(route=r))
   test(len(owners)<=2,'actual capacity2')
  for q in done.values():
   t=q['times'];test(t['dispatch']<=t['execution_start']<=t['host_inference_start']<=t['host_inference_return']<=t['output_ready']<=t['persist_complete']<=t['worker_release']<=t['AVAILABLE'],'phase ordering')
   test(q['response']==(t['output_ready'] if q['priority']=='urgent' else t['readback_end']),'response/release separation')
   pool=[x for x in packet['templates'] if x['route']==q['route'] and x['priority']==q['priority']];chosen=pool[fnv(str(c['stream'])+'|phase|'+str(q['ordinal'])+'|'+q['route'])%len(pool)]
   test(q['template_id']==chosen['id'],'request/route bound potential phase vector')
   estimate=duration(packet['timing'],{**chosen,'domain':'M8_READBACK_RENAME_RESPONSE'},chosen['AP'] or 30,chosen['overlap_fraction'] or 0)
   test(abs(q['residual']-chosen['inference_s']/estimate)<1e-9,'whole vector residual binding')
  nom=raw['public_nominal_model'];test(nominals.get(c['scenario'],nom)==nom,'same nominal model across policies/draws');nominals[c['scenario']]=nom
  dispatched=set();dispatches=[];dose=0
  for d in raw['policy_decisions']:
   obs=d['public_observation'];test(set(obs)=={'time','ready','owners','sensor','sensor_history','initial_AP','wait_used_s','cost_state'},'public-only fields')
   ready=[q for q in raw['planned_requests'] if q['ordinal'] not in dispatched and q['readyAt']<=d['time']+1e-9];test([q['ordinal'] for q in obs['ready']]==[q['ordinal'] for q in ready],'actual public ready queue')
   for q in obs['ready']:test(set(q)=={'ordinal','task','priority','arrival','deadline'} and all(q[k]==planned[q['ordinal']][k] for k in q),'no latent/future request data')
   test(all(x['time']+.2<=d['time']+1e-8 for x in obs['sensor_history']),'sensor delivered prefix')
   public_validate(obs,raw,s,dispatched,test)
   expected=fair_expected(obs,nom,c['action_options'],policy);actual=d['action'];test(expected['kind']==actual['kind'],'independent action kind')
   test(len(expected['candidates'])==len(actual['candidates']),'all candidates retained')
   for a,b in zip(expected['candidates'],actual['candidates']):
    test((a['ordinal'],a['route'],a['permitted'])==(b['ordinal'],b['route'],b['permitted']),'candidate identities/masks');candidates[policy][a['route']]+=1
    for k in ('response_estimate_s','occupied_estimate_s','slack_s','predicted_ready_misses','predicted_max_lateness_s','ATC','energy_proxy','heat_proxy','normalized_energy_heat'):test(abs(a[k]-b[k])<1e-9,'independent nominal candidate '+k)
    if 'state_forecast' in a:
     test('state_forecast' in b,'forecast coverage')
     for key in ('incremental_J','incremental_AP_area','normalized_energy_heat','predicted_AP_peak','current_AP'):
      err=abs(a['state_forecast'][key]-b['state_forecast'][key]);max_forecast_error=max(max_forecast_error,err);test(err<1e-8,'independent state forecast '+key)
     forecast_replays+=1
   if actual['kind']=='DISPATCH':
    test((actual['ordinal'],actual['route'])==(expected['ordinal'],expected['route']),'independent FIFO/EDF/ATC route/order');dispatched.add(actual['ordinal']);dispatches.append((d['time'],actual['ordinal'],actual['route']))
   else:test(actual['dose_s']==expected['dose_s'] and not obs['owners'],'common WAIT');dose+=actual['dose_s']
  test(dispatches==[(e[0],e[2],e[3]) for e in raw['events'] if e[1]=='DISPATCH'],'actions match actual execution')
  test(abs(dose-raw['wait_s'])<1e-9,'WAIT consumption');test(raw['routing_contract']['classification_routes']==list(ROUTES[:3]),'equal3 classification candidates')
  selected[policy].update(raw['policy_route_counts'])
  append(out/'COST_REPLAY_RECEIPTS.jsonl',dict(event='START',id=identity,raw_sha256=sha(p),new_policy_environments=0,reused_raw=not item['new']))
  dt=c['power_dt_s'];end=150 if raw['right_censored_at150'] else 180;ts=np.arange(round(end/dt)+1)*dt;ctx=s['context']['initial_context']['targets'];ap=predict(packet['AP'],raw['activity'],ctx,ts,old);pw=predict(packet['power'],raw['activity'],ctx,ts,old);curve=np.array(raw['curve']);err=max(float(np.max(abs(predict(packet['AP'],raw['activity'],ctx,curve[:,0],old)-curve[:,1]))),float(np.max(abs(predict(packet['power'],raw['activity'],ctx,curve[:,0],old)-curve[:,2]))))
  if not raw['right_censored_at150']:err=max(err,abs(float(np.trapezoid(pw,ts))-raw['J_API0_180']),abs(float(np.trapezoid(ap[ts>=35],ts[ts>=35])/145)-raw['AP35_180_mean']),abs(float(ap[-1])-raw['AP180']))
  sensors=raw['sensor']
  if sensors:err=max(err,float(np.max(abs(predict(packet['AP'],raw['activity'],ctx,np.array([x['time'] for x in sensors]),old)-np.array([x['AP'] for x in sensors])))))
  err=max(err,abs(float(np.max(ap))-raw['AP_peak_sampled']));test(err<1e-8,'independent saved cost/sensor/peak replay');maxerror=max(maxerror,err)
  proof=dict(status='PASS',id=identity,raw_sha256=sha(p),max_abs_error=err,checks_so_far=checks,new_policy_environment=0);proofPath=out/(identity+'_PROOF.json');save(proofPath,proof);proofs.append(proof)
  append(out/'COST_REPLAY_RECEIPTS.jsonl',dict(event='COMPLETE',id=identity,proof_sha256=sha(proofPath)))
  save(out/('PROGRESS_'+str(ix+1).zfill(3)+'.json'),dict(completed=ix+1,total=len(items),checks=checks,max_abs_error=maxerror,unix=time.time()))
 test(len(common)==48,'exact48 matched scenario/stream cells');test(len(proofs)==300,'registered300 cost replay coverage')
 test(all(candidates[p][r]>0 for p in selected for r in ROUTES[:3]),'every policy considers all3 class routes')
 save(op['result_path'],dict(status='PASS',meaning='SAVED_ACTION_INPUT_MASK_AND_COST_ARITHMETIC_PASS_NOT_PHONE_ACCURACY',checks=checks,new_environments_audited=300,reused_own=0,cost_replays=300,planning_forecasts=forecast_replays,max_forecast_error=max_forecast_error,max_abs_error=maxerror,selected_route_counts={p:dict(v) for p,v in selected.items()},candidate_route_counts={p:dict(v) for p,v in candidates.items()},new_policy_environments=0,new_RL=0,new_fit=0))

if __name__=='__main__':main(read(os.environ['S26_UNIFIED_OPERATION']))
