"""Saved-only V2: explicit censoring when sustained overload misses service stop.

Original native code/registration and V1 postprocessor are preserved. V1 audit
was not run. This fixes presentation of undefined completion energy, not policy,
input, deadlines, physics, or completed native records.
"""
from pathlib import Path
import bisect,gzip,hashlib,io,json,math,sys
import numpy as np
import torch
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'experiments/coupled_345_20261017'))
from nn_train import Learner,digest
checks=0;worst=0.
def need(v,s):
 global checks
 checks+=1
 if not v:raise ValueError(s)
def close(a,b,s,tol=2e-7):
 global worst
 worst=max(worst,abs(a-b));need(abs(a-b)<=tol,s+': '+str(abs(a-b)))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)
def save(p,v):
 with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
def part(t,dt,c,H,dynamic=None):
 T,z=t['state']['temperature_c'],t['state']['shared_z'];tt=c['thermal_tau_s'];R=c['thermal_resistance']
 dyn=t['dynamic']/t['dt'] if dynamic is None else dynamic
 e=math.exp(-dt/tt);a=-math.expm1(-dt/tt);se=fe=fa=0.;zz=z
 if t['active']:
  zz=1.;se=H*dt;fe=R*(dyn+H)*a;fa=R*(dyn+H)*(dt-tt*a)
 elif c['idle_tail_s']:
  tz=c['idle_tail_s'];b=-math.expm1(-dt/tz);factor=R*H*z*tz/(tz-tt)
  zz=z*math.exp(-dt/tz);se=H*z*tz*b;fe=factor*(math.exp(-dt/tz)-e);fa=factor*(tz*b-tt*a)
 return dict(increment=dyn*dt+se,shared=se,temperature_c=c['idle_c']+(T-c['idle_c'])*e+fe,
  shared_z=zz,temperature_area=c['idle_c']*dt+(T-c['idle_c'])*tt*a+fa)
def integrate(result,end,c,H):
 inc=area=coverage=0.;peak=result['initial_ap_c']
 for t in result['trace']:
  if t['start_ns']>=end:break
  ns=min(end,t['end_ns'])-t['start_ns'];coverage+=ns;x=part(t,ns/1e9,c,H)
  inc+=x['increment'];area+=x['temperature_area'];peak=max(peak,t['state']['temperature_c'],x['temperature_c'])
 close(coverage,end-35e9,'Prefix coverage',1)
 dt=(end-35e9)/1e9;base=c['baseline']*dt
 q=result['requests'];answered=[r for r in q if r['response_ns'] is not None and r['response_ns']<=end]
 return dict(end_ns=end,duration_s=dt,total_J_proxy=base+inc,increment_J_proxy=inc,baseline_J_proxy=base,
  baseline_percent=100*base/(base+inc),temperature_area=area,mean_AP_c=area/dt,peak_AP_c=peak,
  response_missing=len(q)-len(answered),incomplete=sum(r['available_ns'] is None or r['available_ns']>end for r in q),
  on_time=sum(r['response_ns']<=r['deadline_ns'] for r in answered),urgent_on_time=sum(r['priority']=='U' and r['response_ns']<=r['deadline_ns'] for r in answered))
def main():
 op=read(HERE/'OPERATION.json');out=ROOT/op['output_dir'];res=read(out/'RESULT.json');c=op['physics'];design=read(op['inputs']['path'])['cases']
 amendment=read(HERE/'SAVED_AUDIT_V2.json')
 need(amendment['result_sha256']==sha(out/'RESULT.json'),'V2 exact native result binding')
 for p in amendment['sources']:need(sha(p['path'])==p['sha256'],'V2 postprocessor pin')
 need(not (out/'AUDIT.json').exists(),'Saved audit namespace consumed')
 for p in [*op['sources'],*op['input_pins']]:need(sha(p['path'])==p['sha256'],'Pinned '+p['path'])
 receipts=[json.loads(x) for x in (out/'receipts.jsonl').read_text().splitlines()]
 need(sum(x['event']=='START' for x in receipts)==20 and sum(x['event']=='COMPLETE' for x in receipts)==20 and not any(x['event']=='FAIL' for x in receipts),'20 complete receipts')
 need(len({x['identity'] for x in receipts if x['event']=='START'})==20,'Unique native identities')
 model=read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json');solo=dict(zip(model['supported_states'],model['coefficients_W_proxy']))
 H=solo['classification_GPU']+solo['detection_CPU']-solo.pop('classification_GPU+detection_CPU');solo['detection_GPU']=.6013808404579677
 snap=torch.load(io.BytesIO(gzip.decompress(Path(op['checkpoint']['path']).read_bytes())),map_location='cpu',weights_only=False)
 learner=Learner(3701);learner.restore(snap);net=digest(learner.net);records=[];nnframes=0
 for row in res['rows']:
  rawpath=out/(row['label']+'.raw.json.gz');need(sha(rawpath)==row['raw_sha256'],'Raw pin')
  raw=read(rawpath);r=raw['result'];qs=r['requests'];m=row['metrics'];need(len(qs)==row['n'],'Request denominator')
  sums={(q['request_id'],i):0. for q in qs for i in range(5)};lanes={}
  for route in ('CPU','GPU'):
   jobs=sorted((q for q in qs if q['route']==route),key=lambda q:q['dispatch_ns']);lanes[route]=(jobs,[q['dispatch_ns'] for q in jobs])
   for a,b in zip(jobs,jobs[1:]):need(a['available_ns'] is not None and a['available_ns']<=b['dispatch_ns'],'Exclusive lane occupancy')
  prev=35_000_000_000;previous=None
  for t in r['trace']:
   need(t['start_ns']==prev and t['end_ns']>prev,'Contiguous causal trace');prev=t['end_ns'];dt=(t['end_ns']-t['start_ns'])/1e9
   close(dt,t['dt'],'Trace duration',1e-12)
   if previous is not None:
    close(t['state']['temperature_c'],previous['temperature_c'],'Continuous temperature')
   dynamic=0.;T=t['state']['temperature_c'];leak=math.exp(min(math.log(3),max(-math.log(3),c['strength']*c['leakage_per_c']*(T-c['reference_c']))))
   need(len({a['route'] for a in t['active']})==len(t['active'])<=2,'Physical owners')
   for a in t['active']:
    route,stage=a['route'],a['stage'];slope=c['cpu_slope'] if route=='CPU' else c['gpu_slope']
    f=max(c['minimum_speed'],1/(1+c['strength']*slope*max(0,T-c['onset_c']))) if stage==1 else 1.
    close(f,t['speeds'][route],'Frequency feedback',1e-12)
    key=('classification' if a['task']=='C' else 'detection')+'_'+route
    dynamic+=(solo[key]-H)*((1-c['leakage_fraction'])*f**3+c['leakage_fraction']*leak)
    jobs,starts=lanes[route];idx=bisect.bisect_right(starts,t['start_ns'])-1;need(idx>=0,'Owner dispatch before work');q=jobs[idx]
    boundaries=[q[k] for k in ('execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','available_ns')]
    actual=bisect.bisect_right([b for b in boundaries if b is not None],t['start_ns'])
    need(q['task']==a['task'] and actual==stage,'Phase and task binding');sums[q['request_id'],stage]+=dt*f
   x=part(t,dt,c,H,dynamic)
   for k in ('increment','shared','temperature_area'):close(x[k],t[k],'Independent '+k)
   close(c['baseline']*dt,t['baseline'],'Baseline')
   for k in ('temperature_c','shared_z'):close(x[k],t['next_state'][k],'Independent '+k)
   previous=t['next_state']
  for q in qs:
   if q['available_ns'] is not None:
    for i,ns in enumerate(q['timing']['stages_ns']):close(sums[q['request_id'],i],ns/1e9,'Latent phase work conserved',3e-7)
   if q['dispatch_ns'] is not None:need(q['dispatch_ns']>=q['queue_entry_ns'],'No future dispatch')
   need(q['response_ns'] is None or q['response_ns']==q['output_ready_ns' if q['task']=='C' else 'persist_complete_ns'],'Response boundary')
  if row['policy']=='RL':
   framepath=out/(row['label']+'.frames.pt.gz');need(sha(framepath)==row['frames_sha256'],'Frame pin')
   frames=torch.load(io.BytesIO(gzip.decompress(framepath.read_bytes())),map_location='cpu',weights_only=False)['frames']
   calls=[a for a in raw['calls'] if not a['common_coalescing']];need(len(frames)==len(calls),'All neural calls retained')
   for f,a in zip(frames,calls):
    need(not f['collect'] and f['network_sha256']==net and f['index']==a['chosen'] and a['mask'][f['index']],'Frozen masked action')
    need(np.array_equal(f['x'],np.asarray(a['x'],np.float32)) and np.array_equal(f['mask'],a['mask']),'Public frame binding')
   for first in range(0,len(frames),128):
    ff=frames[first:first+128];xx=torch.from_numpy(np.stack([f['x'] for f in ff]));mask=torch.from_numpy(np.stack([f['mask'] for f in ff]))
    with torch.no_grad():logits,values=learner.net(xx,mask)
    need(logits.argmax(-1).tolist()==[f['index'] for f in ff],'Independent frozen NN argmax replay');nnframes+=len(ff)
  if row['kind']=='SUSTAINED':
   case=next(z for z in design if z['id']==row['case']);last=max(q['available_ns'] for q in qs) if all(q['available_ns'] is not None for q in qs) else None
   original=integrate(r,round(case['drain_stop_s']*1e9),c,H)
   close(original['total_J_proxy'],m['total_J_proxy'],'Native accounting reproduced')
   for k in ('on_time','urgent_on_time','response_missing','incomplete'):need(original[k]==m[k],'Native SLA reproduced')
   own=integrate(r,last,c,H) if last is not None else None
   ends=[]
   for policy in ('EDF','ATC','RL'):
    peer=read(out/(case['id']+'_'+policy+'.raw.json.gz'))['result']['requests']
    ends.append(max(q['available_ns'] for q in peer) if all(q['available_ns'] is not None for q in peer) else round(case['drain_stop_s']*1e9))
   common_end=max(ends)
   common=integrate(r,common_end,c,H);supply=integrate(r,round(case['supply_stop_s']*1e9),c,H)
   start_tail=round((case['supply_stop_s']-60)*1e9);before_tail=integrate(r,start_tail,c,H) if start_tail>35e9 else None
   last60=(supply['temperature_area']-(before_tail['temperature_area'] if before_tail else 0))/60
   throttle=[t for t in r['trace'] if t['start_ns']<round(case['supply_stop_s']*1e9)]
   clip=lambda t:(min(t['end_ns'],round(case['supply_stop_s']*1e9))-t['start_ns'])/1e9
   speedwork=sum(clip(t)*t['speeds'][a['route']] for t in throttle for a in t['active'] if a['stage']==1)
   exectime=sum(clip(t) for t in throttle for a in t['active'] if a['stage']==1)
   records.append(dict(label=row['label'],case=row['case'],policy=row['policy'],condition=case['condition'],n=case['n'],
    original=m,completion=own,common=common,supply=supply,last60_supply_mean_AP_c=last60,
    completion_energy_defined=last is not None,common_fallback_to_registered_drain=any(x==round(case['drain_stop_s']*1e9) for x in ends),
    active_execution_mean_speed=speedwork/exectime if exectime else None,all_completed=last is not None,
    post_completion_activation_tail_J_proxy=H*c['idle_tail_s'] if last else None,raw_sha256=row['raw_sha256']))
  print('AUDITED',row['label'],'checks',checks,flush=True)
 need(net==digest(learner.net) and res['network_and_training_RNG_unchanged'],'Frozen learner unchanged')
 summary=[]
 for duration in (120,300,600):
  local=[r for r in records if r['condition']['supply_s']==duration];refs={r['case']:r for r in local if r['policy']=='EDF'}
  complete_all=all(r['completion'] is not None for r in local)
  base=sum(r['completion']['total_J_proxy'] for r in refs.values()) if complete_all else None
  commonbase=sum(r['common']['total_J_proxy'] for r in refs.values());supplybase=sum(r['supply']['total_J_proxy'] for r in refs.values())
  for policy in ('EDF','ATC','RL'):
   group=[r for r in local if r['policy']==policy];J=sum(r['completion']['total_J_proxy'] for r in group) if complete_all else None
   defined=all(r['completion'] is not None for r in group)
   summary.append(dict(supply_s=duration,policy=policy,requests=sum(r['n'] for r in group),
    mean_completion_duration_s=sum(r['completion']['duration_s'] for r in group)/2 if defined else None,mean_completion_total_J_proxy=J/2 if J is not None else None,
    completion_saving_percent=100*(1-J/base) if complete_all else None,common_saving_percent=100*(1-sum(r['common']['total_J_proxy'] for r in group)/commonbase),
    supply_saving_percent=100*(1-sum(r['supply']['total_J_proxy'] for r in group)/supplybase),
    complete_work_energy_comparison_defined=complete_all,
    mean_supply_total_J_proxy=sum(r['supply']['total_J_proxy'] for r in group)/2,
    supply_baseline_percent=100*sum(r['supply']['baseline_J_proxy'] for r in group)/sum(r['supply']['total_J_proxy'] for r in group),
    completion_baseline_percent=100*sum(r['completion']['baseline_J_proxy'] for r in group)/J if J is not None else None,
    mean_supply_AP_c=sum(r['supply']['mean_AP_c'] for r in group)/2,
    mean_supply_AP_delta_c=sum(r['supply']['mean_AP_c']-refs[r['case']]['supply']['mean_AP_c'] for r in group)/2,
    mean_last60_AP_c=sum(r['last60_supply_mean_AP_c'] for r in group)/2,
    on_time=sum(r['original']['on_time'] for r in group),urgent_on_time=sum(r['original']['urgent_on_time'] for r in group),
    urgent_planned=sum(r['original']['urgent_planned'] for r in group),response_missing=sum(r['original']['response_missing'] for r in group),
    incomplete=sum(r['original']['incomplete'] for r in group),on_time_delta=sum(r['original']['on_time']-refs[r['case']]['original']['on_time'] for r in group),
    urgent_delta=sum(r['original']['urgent_on_time']-refs[r['case']]['original']['urgent_on_time'] for r in group),
    no_SLA_harm_every_case=all(r['original']['on_time']>=refs[r['case']]['original']['on_time'] and r['original']['urgent_on_time']>=refs[r['case']]['original']['urgent_on_time'] and r['original']['incomplete']==r['original']['response_missing']==0 for r in group)))
 save(out/'WORK_METRICS.json',dict(rows=records,summary=summary,definitions='Own completion includes all interjob idle/WAIT, undefined/null if any request never AVAILABLE; common end max of3policies, fallback to original drain if censored; supply energy/AP same walltime. Different completed work forbids efficiency-win claim.',measured_J=None))
 save(out/'AUDIT.json',dict(status='PASS',utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
  checks=checks,max_absolute_error=worst,independent_NN_frames=nnframes,result_sha256=sha(out/'RESULT.json'),work_metrics_sha256=sha(out/'WORK_METRICS.json'),
  new_environment_START=0,new_training=0,independent_progress_energy_RC=True,original_artifacts_preserved=True,
  amendment_sha256=sha(HERE/'SAVED_AUDIT_V2.json'),undefined_completion_energy_preserved=True))
 print(json.dumps(dict(status='PASS',checks=checks,worst=worst,NNframes=nnframes,summary=summary),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
