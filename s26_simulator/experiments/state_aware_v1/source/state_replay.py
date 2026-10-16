"""Independent direct-convolution replay of public-state planning projections."""
import math,copy
import numpy as np
from timing_model import duration
from audit_resource_v2 import replay_action,ROUTES
from audit_simulation_study import predict

MODELS=None
DIRECT=None
FORECAST_COUNT=0
MAX_ERROR=0.
KEYS=('dispatch','execution_start','host_inference_start','host_inference_return','output_ready','AVAILABLE')
CHANNELS=('classification_CPU','detection_CPU','classification_GPU','classification_NPU')

def lengths(nom,route,ap,peer):
 n=nom['routes'][route]
 return [n['gap_s'],n['admission_s'],duration(nom['timing'],n['identity'],ap,peer)*n['residual'],n['return_s'],n['post_s']]

def add_union(ints,windows):
 ev=sorted([(l,1) for l,r in windows if r>l]+[(r,-1) for l,r in windows if r>l]);t=ev[0][0] if ev else 0;n=0;i=0
 while i<len(ev):
  u=ev[i][0]
  if u>t and n:
   ints[6].append([t,u,1])
   if n>1:ints[8].append([t,u,n-1])
  while i<len(ev) and ev[i][0]==u:n+=ev[i][1];i+=1
  t=u

def public_validate(obs,raw,scenario,dispatched,test):
 by={q['ordinal']:q for q in raw['requests']};ordered=[e[2] for e in raw['events'] if e[1]=='DISPATCH' and e[2] in dispatched]
 expected=[dict(ordinal=o,route=by[o]['route'],priority=by[o]['priority'],times={k:v for k,v in by[o]['times'].items() if k in KEYS and isinstance(v,(int,float)) and v<=obs['time']+1e-10}) for o in ordered]
 state=obs['cost_state'];test(state['prefixes']==expected,'observed phase prefix equals actual past host events only')
 ints=copy.deepcopy(scenario['context']['pre_activity9']['intervals'])
 for q in expected:
  t=q['times']
  for j in range(5):
   l=t.get(KEYS[j]);r=t.get(KEYS[j+1],obs['time'])
   if l is None or r<=l:continue
   k=4 if j==1 else CHANNELS.index(q['route']) if j==2 else 5 if j==4 else 7;ints[k].append([l,min(r,obs['time']),1])
 add_union(ints,[(q['times']['dispatch'],q['times'].get('AVAILABLE',obs['time'])) for q in expected])
 test(ints==state['activity9']['intervals'],'public history activity reconstruction')
 target=scenario['context']['initial_context']['targets'];test(state['targets']==dict(AP=dict(anchor=target['AP']['anchor']),POWER_API=dict(baseline=dict(median_api_w=target['POWER_API']['baseline']['median_api_w']))),'known initial context only')

def forecast(obs,nom,route,priority,refine=1):
 state=obs['cost_state'];plans=[];phases=('GAP','ADMISSION','INFER','RETURN_GAP','POST')
 for o in state['prefixes']:
  if 'AVAILABLE' in o['times']:continue
  ix=max(i for i in range(5) if KEYS[i] in o['times']);ls=lengths(nom,o['route'],obs['sensor']['AP'],int(len(obs['owners'])>1));elapsed=max(0,obs['time']-o['times'][KEYS[ix]])
  ls[ix]=max(.25*ls[ix] if ix==2 else .0005,ls[ix]-elapsed)
  plans.append(dict(route=o['route'],start=obs['time'],phases=[dict(phase=phases[i],duration_s=ls[i]) for i in range(ix,5)]))
 ls=lengths(nom,route,obs['sensor']['AP'],0);candidate=dict(route=route,start=obs['time'],phases=[dict(phase=p,duration_s=d) for p,d in zip(phases,ls)])
 combined=copy.deepcopy([*plans,candidate]);infer_bases=[next((x['duration_s'] for x in p['phases'] if x['phase']=='INFER'),None) for p in combined]
 for iteration in range(3):
  spans=[]
  for p in combined:
   t=p['start'];span=None
   for x in p['phases']:
    if x['phase']=='INFER':span=(t,t+x['duration_s']);break
    t+=x['duration_s']
   spans.append(span)
  for i,p in enumerate(combined):
   if spans[i] is None:continue
   overlap=sum(max(0,min(s[1],spans[i][1])-max(s[0],spans[i][0])) for j,s in enumerate(spans) if s and j!=i);fraction=min(1,overlap/(spans[i][1]-spans[i][0]));label='OVERLAP:'+p['route'];beta=nom['timing']['coef'][nom['timing']['spec']['labels'].index(label)] if label in nom['timing']['spec']['labels'] else 0
   next(x for x in p['phases'] if x['phase']=='INFER')['duration_s']=infer_bases[i]*math.exp(beta*fraction)
 def append(ints,p):
  t=p['start']
  for x in p['phases']:
   r=t+x['duration_s'];k=4 if x['phase']=='ADMISSION' else CHANNELS.index(p['route']) if x['phase']=='INFER' else 5 if x['phase']=='POST' else 7
   if r>t:ints[k].append([t,r,1])
   t=r
  return (p['start'],t)
 base=copy.deepcopy(state['activity9']['intervals']);add_union(base,[append(base,p) for p in plans]);both=copy.deepcopy(state['activity9']['intervals']);add_union(both,[append(both,p) for p in combined])
 times={obs['time'],180.,obs['sensor']['time']}
 def put(t):
  if obs['time']<=t<=180:times.add(math.floor(t*1e10+.5)/1e10)
 t=obs['time']
 while t<180:
  age=t-obs['time'];dt=(.05 if age<2 else .25 if age<15 else 1 if age<60 else 5)/refine;t=min(180,t+dt);put(t)
 for xs in state['activity9']['intervals']:
  for l,r,w in xs:put(l+.5);put(r+.5)
 for p in [*plans,*combined]:
  t=p['start'];put(t);put(t+.5)
  for x in p['phases']:t+=x['duration_s'];put(t);put(t+.5)
 ts=np.array(sorted(times));ctx=state['targets'];bp=predict(MODELS['power'],base,ctx,ts,DIRECT);cp=predict(MODELS['power'],both,ctx,ts,DIRECT);bt=predict(MODELS['AP'],base,ctx,ts,DIRECT);ct=predict(MODELS['AP'],both,ctx,ts,DIRECT)
 ix=np.where(ts==obs['sensor']['time'])[0][0];offset=obs['sensor']['AP']-bt[ix];mask=ts[:-1]>=obs['time']-1e-9;dt=np.diff(ts);J=float(np.sum(dt[mask]*((cp-bp)[1:]+(cp-bp)[:-1])[mask]/2));H=float(np.sum(dt[mask]*((ct-bt)[1:]+(ct-bt)[:-1])[mask]/2));peak=float(np.max((ct[1:]+offset)[mask]))
 js=max(1e-9,*(abs(nom['routes'][r]['incremental_J_proxy']) for r in ROUTES));hs=max(1e-9,*(abs(nom['routes'][r]['AP_area_proxy']) for r in ROUTES))
 return dict(incremental_J=J,incremental_AP_area=H,normalized_energy_heat=J/js+H/hs,predicted_AP_peak=peak,current_AP=obs['sensor']['AP'])

def state_expected(obs,nom,options,policy):
 global FORECAST_COUNT
 base=replay_action(obs,nom,options)
 if base['kind']!='DISPATCH':return base
 cs=[c for c in base['candidates'] if c['permitted']];ids={c['ordinal'] for c in cs}
 if policy.startswith('ATC'):ordinal=base['ordinal']
 else:ordinal=min((q for q in obs['ready'] if q['ordinal'] in ids),key=lambda q:((q['deadline'] if policy.startswith('EDF') else 0),q['arrival'],q['ordinal']))['ordinal']
 rr=[c for c in cs if c['ordinal']==ordinal];risk=min(rr,key=lambda c:(c['predicted_ready_misses'],c['predicted_max_lateness_s']));same=[c for c in rr if c['predicted_ready_misses']==risk['predicted_ready_misses'] and abs(c['predicted_max_lateness_s']-risk['predicted_max_lateness_s'])<1e-12]
 if policy.endswith('STATE'):
  q=next(q for q in obs['ready'] if q['ordinal']==ordinal)
  for c in same:c['state_forecast']=forecast(obs,nom,c['route'],q['priority']);FORECAST_COUNT+=1
 score=lambda c:c['state_forecast']['normalized_energy_heat'] if policy.endswith('STATE') else c['normalized_energy_heat']
 best=min(same,key=lambda c:(score(c),c['response_estimate_s'],c['route']))
 return dict(kind='DISPATCH',ordinal=ordinal,route=best['route'],candidates=base['candidates'])
