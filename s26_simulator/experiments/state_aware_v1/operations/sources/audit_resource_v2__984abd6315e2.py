"""Independent saved action replay and direct Python AP/power arithmetic; no new plant."""
import collections, hashlib, importlib.util, json, math, os, time
from pathlib import Path
import numpy as np
from timing_model import read, save, duration
from audit_simulation_study import predict, fnv, sha, append

ROUTES=('classification_CPU','classification_GPU','classification_NPU','detection_CPU')
def legal(route,owners):
 return not owners or len(owners)==1 and set((route,owners[0]['route'])) in ({'classification_GPU','detection_CPU'},{'classification_NPU','detection_CPU'}) and route!=owners[0]['route']
def replay_action(obs,nom,options):
 allowed=lambda q:['detection_CPU'] if q['task']=='detection' else options.get('classification_routes',list(ROUTES[:3]))
 def estimate(route,priority,peer):
  n=nom['routes'][route];infer=duration(nom['timing'],n['identity'],obs['sensor']['AP'],peer)*n['residual'];output=n['gap_s']+n['admission_s']+infer+n['return_s'];return output+n['post_s'],output+(n['post_s']*n['readback_fraction'] if priority=='normal' else 0)
 def fastest(q):return min(estimate(r,q['priority'],0)[1] for r in allowed(q))
 meanp=sum(fastest(q) for q in obs['ready'])/len(obs['ready']);js=max(1e-9,*(abs(nom['routes'][r]['incremental_J_proxy']) for r in ROUTES));hs=max(1e-9,*(abs(nom['routes'][r]['AP_area_proxy']) for r in ROUTES));out=[]
 for q in obs['ready']:
  for route in allowed(q):
   occ,response=estimate(route,q['priority'],int(bool(obs['owners'])));slack=q['deadline']-obs['time']-response;miss=int(slack<0);late=max(0.,-slack)
   for other in obs['ready']:
    if other['ordinal']==q['ordinal']:continue
    predictions=[]
    for r in allowed(other):
     conflict=not legal(r,[dict(route=route)]);predictions.append(obs['time']+(occ if conflict else 0)+estimate(r,other['priority'],int(not conflict))[1])
    earliest=min(predictions);miss+=earliest>other['deadline'];late=max(late,earliest-other['deadline'])
   atc=math.exp(-max(slack,0)/(2*max(meanp,1e-9)))/response;n=nom['routes'][route]
   out.append(dict(ordinal=q['ordinal'],route=route,permitted=legal(route,obs['owners']),response_estimate_s=response,occupied_estimate_s=occ,slack_s=slack,predicted_ready_misses=int(miss),predicted_max_lateness_s=max(0.,late),ATC=atc,energy_proxy=n['incremental_J_proxy'],heat_proxy=n['AP_area_proxy'],normalized_energy_heat=n['incremental_J_proxy']/js+n['AP_area_proxy']/hs))
 rr=[c for c in out if c['permitted']]
 if not rr:return dict(kind='NONE',candidates=out)
 request=min(rr,key=lambda c:(c['predicted_ready_misses'],c['predicted_max_lateness_s'],-c['ATC'],c['ordinal']));same=[c for c in rr if c['ordinal']==request['ordinal'] and c['predicted_ready_misses']==request['predicted_ready_misses'] and abs(c['predicted_max_lateness_s']-request['predicted_max_lateness_s'])<1e-12];best=min(same,key=lambda c:(c['normalized_energy_heat'],c['response_estimate_s'],c['route']))
 recent=obs['sensor_history'][-2:];wait=options.get('wait_step_s',.05);cap=options.get('wait_cap_s',2)
 if options.get('allow_wait',True) and not obs['owners'] and len(recent)==2 and obs['wait_used_s']+wait<=cap+1e-12:
  dt=recent[1]['time']-recent[0]['time'];slope=(recent[1]['AP']-recent[0]['AP'])/dt if dt>0 else 0
  if slope<-.01 and obs['sensor']['AP']>obs['initial_AP']+.5 and all(q['deadline']-obs['time']-fastest(q)>wait+.05 for q in obs['ready']):return dict(kind='WAIT',dose_s=wait,candidates=out)
 return dict(kind='DISPATCH',ordinal=best['ordinal'],route=best['route'],candidates=out)

def main(op):
 out=Path(op['output_dir']);out.mkdir();pr=read(op['production_operation']);plan=read(pr['case_plan_path']);packet=read(pr['packet_path']);rows=[json.loads(l) for l in (Path(pr['output_dir'])/'ROWS.jsonl').read_text().splitlines() if l.strip()];events=collections.defaultdict(list)
 for l in Path(pr['receipts_path']).read_text().splitlines():
  e=json.loads(l);events[e['id']].append(e)
 spec=importlib.util.spec_from_file_location('direct_cost_saved',op['direct_math']);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old);checks=0;maxerror=0.;route_counts=collections.Counter();candidate_counts=collections.Counter();dynamic=[]
 def test(ok,text):
  nonlocal checks;checks+=1
  if not ok:raise ValueError(text)
 test(len(plan)==len(rows)==56,'sealed56 complete cases');test(len({r['logical_identity'] for r in rows})==56,'unique identities')
 for config,row in zip(plan,rows):
  identity=config['identity'];test(row['logical_identity']==identity,'sealed row order');ev=events[identity];test([e['event'] for e in ev]==['START','PREPARED','COMPLETE'],'terminal receipt order');raw=read(row['raw_path']);test(sha(row['raw_path'])==row['raw_sha256']==ev[1]['raw_sha256']==ev[2]['raw_sha256'],'raw binding');test(raw['packet_sha256']==sha(pr['packet_path']),'packet SHA');cfg=Path(pr['output_dir'])/'configurations'/(identity+'.json');test(read(cfg)==config and sha(cfg)==raw['configuration_sha256'],'config binding');s=next(s for s in packet['scenarios'] if s['id']==config['scenario']);planned={q['ordinal']:q for q in raw['planned_requests']};done={q['ordinal']:q for q in raw['requests']}
  test(len(planned)==128,'all128 planned');
  for q in planned.values():
   original=next(r for r in s['requests'] if r['ordinal']==q['ordinal']);test(q['arrival']==original['offset_ns']/1e9 and q['deadline']==q['arrival']+original['deadline_ms']/1000,'original arrivals/deadlines');test(q['completed']==(q['ordinal'] in done),'unfinished retained')
  for pri in ('all','urgent','normal'):
   pp=[q for q in planned.values() if pri=='all' or q['priority']==pri];dd=[q for q in done.values() if pri=='all' or q['priority']==pri];on=sum(q['response']<=q['deadline']+1e-9 for q in dd);v=raw['service'][pri];test(v['planned']==len(pp) and v['completed']==len(dd) and v['on_time']==on and v['late_or_unfinished']==len(pp)-on,'service arithmetic')
  test(raw['hard_feasible']==(raw['service']['all']['on_time']==128 and len(done)==128),'hard feasibility');test(raw['unfinished']==128-len(done),'unfinished arithmetic')
  for q in done.values():
   pool=[p for p in packet['templates'] if p['route']==q['route'] and p['priority']==q['priority']];chosen=pool[fnv(str(config['stream'])+'|phase|'+str(q['ordinal'])+'|'+q['route'])%len(pool)];test(chosen['id']==q['template_id'],'exact measured whole phase draw');test(q['response']==(q['times']['output_ready'] if q['priority']=='urgent' else q['times']['readback_end']),'response boundary');test(abs(q['residual']-chosen['inference_s']/duration(packet['timing'],{**chosen,'domain':'M8_READBACK_RENAME_RESPONSE'},chosen['AP'] or 30,chosen['overlap_fraction'] or 0))<1e-9,'inference latent binding')
  owners=[]
  for _,sign,route in sorted([(q['times']['dispatch'],1,q['route']) for q in done.values()]+[(q['times']['AVAILABLE'],-1,q['route']) for q in done.values()],key=lambda x:(x[0],x[1])):
   if sign<0:owners.remove(dict(route=route))
   else:test(legal(route,owners),'actual resource mask');owners.append(dict(route=route))
   test(len(owners)<=2,'actual capacity')
  if config['policy']=='ROLLING_ATC_ROUTE_V2':
   dynamic.append(raw);route_counts.update(raw['policy_route_counts']);dispatch_actions=[]
   for d in raw['policy_decisions']:
    obs=d['public_observation'];test(set(obs)=={'time','ready','owners','sensor','sensor_history','initial_AP','wait_used_s'},'public observation field contract');test(all(set(q)=={'ordinal','task','priority','arrival','deadline'} for q in obs['ready']),'no future latent fields');test(all(q['arrival']<=d['time']+1e-9 for q in obs['ready']),'only arrived requests');test(all(x['time']+.2<=d['time']+1e-8 for x in obs['sensor_history']),'delivered sensor prefix');expected=replay_action(obs,raw['public_nominal_model'],config['action_options']);actual=d['action'];test(expected['kind']==actual['kind'],'independent action kind');test(len(expected['candidates'])==len(actual['candidates']),'all nominal candidates retained')
    for a,b in zip(expected['candidates'],actual['candidates']):
     test(a['route']==b['route'] and a['ordinal']==b['ordinal'] and a['permitted']==b['permitted'],'candidate identity and mask');candidate_counts[a['route']]+=1
     for k in ('response_estimate_s','occupied_estimate_s','slack_s','predicted_ready_misses','predicted_max_lateness_s','ATC','energy_proxy','heat_proxy','normalized_energy_heat'):test(abs(a[k]-b[k])<1e-9,'independent candidate arithmetic '+k)
    if actual['kind']=='DISPATCH':test(actual['ordinal']==expected['ordinal'] and actual['route']==expected['route'],'independent resource/order choice');dispatch_actions.append((d['time'],actual['ordinal'],actual['route']))
    else:test(actual['dose_s']==expected['dose_s'] and not obs['owners'],'WAIT safe boundary')
   test(dispatch_actions==[(e[0],e[2],e[3]) for e in raw['events'] if e[1]=='DISPATCH'],'actions match actual dispatches');test(abs(sum(d['action'].get('dose_s',0) for d in raw['policy_decisions'])-raw['wait_s'])<1e-9,'WAIT consumption');test(raw['routing_contract']['classification_routes']==list(ROUTES[:3]),'all3 routes enabled for every production condition')
  append(out/'COST_REPLAY_RECEIPTS.jsonl',dict(event='START',id=identity,raw_sha256=sha(row['raw_path']),new_policy_environments=0));dt=config['power_dt_s'];ts=np.arange(round(180/dt)+1)*dt;ctx=s['context']['initial_context']['targets'];ap=predict(packet['AP'],raw['activity'],ctx,ts,old);pw=predict(packet['power'],raw['activity'],ctx,ts,old);curve=np.asarray(raw['curve']);err=max(abs(float(np.trapezoid(pw,ts))-raw['J_API0_180']),abs(float(np.trapezoid(ap[ts>=35],ts[ts>=35])/145)-raw['AP35_180_mean']),float(np.max(abs(predict(packet['AP'],raw['activity'],ctx,curve[:,0],old)-curve[:,1]))),float(np.max(abs(predict(packet['power'],raw['activity'],ctx,curve[:,0],old)-curve[:,2]))));test(err<1e-8,'independent cost replay');maxerror=max(maxerror,err);proof=out/(identity+'_PROOF.json');save(proof,dict(status='PASS',id=identity,raw_sha256=sha(row['raw_path']),max_abs_error=err,checks_so_far=checks));append(out/'COST_REPLAY_RECEIPTS.jsonl',dict(event='COMPLETE',id=identity,proof_sha256=sha(proof)));save(out/('PROGRESS_'+str(len(list(out.glob('*_PROOF.json')))).zfill(3)+'.json'),dict(latest=identity,checks=checks,unix=time.time()))
 test(len(dynamic)==48,'all48 dynamic cases');test(all(candidate_counts[r]>0 for r in ROUTES[:3]),'all classification routes actually considered');save(op['result_path'],dict(status='PASS',meaning='RESOURCE_ACTION_AND_SAVED_COST_REPLAY_PASS_NOT_PHYSICAL_ACCURACY_OR_RL',checks=checks,new_policy_environments=0,new_NN=0,new_RL=0,production_cases=56,dynamic_cases=48,cost_replays=56,max_abs_error=maxerror,candidate_route_counts=dict(candidate_counts),selected_route_counts=dict(route_counts),feasible_conditions=sum(r['hard_feasible'] for r in dynamic),on_time_mean=sum(r['service']['all']['on_time'] for r in dynamic)/48,J_mean=sum(r['J_API0_180'] for r in dynamic)/48,AP_mean=sum(r['AP35_180_mean'] for r in dynamic)/48,all_losses_retained=True))
if __name__=='__main__':main(read(os.environ['S26_UNIFIED_OPERATION']))
