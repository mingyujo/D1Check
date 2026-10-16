"""One nonpreemptive S26 plant for all policies. Measured support plus explicitly
estimated thermal/coexecution progress; API-energy is not calibrated battery J.
"""
import collections, hashlib, json, math
from pathlib import Path
import numpy as np
from timing_model import ROUTES, design, duration

ACTIVITY=('classification_CPU','detection_CPU','classification_GPU','classification_NPU','shared_admission','shared_persist_release','owner_union','unallocated_owner_phase','owner_overlap')
ROUTE_INDEX={r:ACTIVITY.index(r) for r in ROUTES}
def h(t,l,r,b):
 if t<=l or r<=l:return 0.
 return -math.expm1(-b*(min(t,r)-l))*math.exp(-b*max(0,t-r))
def ha(A,B,l,r,b):
 if r<=l:return 0.
 v=0.;x=max(A,l);y=min(B,r)
 if y>x:v+=(y-x)+(math.exp(-b*(y-l))-math.exp(-b*(x-l)))/b
 x=max(A,r)
 if B>x:v+=-math.expm1(-b*(r-l))*(math.exp(-b*(x-r))-math.exp(-b*(B-r)))/b
 return v
def box(t,l,r,w):return max(0.,min(t,r)-max(t-w,l))/w
def ba(A,B,l,r,w):
 ts=sorted(x for x in (A,B,l,r,l+w,r+w) if A<=x<=B)
 return sum((y-x)*(box(x,l,r,w)+box(y,l,r,w))/2 for x,y in zip(ts,ts[1:]))
class Cost:
 def __init__(self,cost,context):
  self.cost,self.context=cost,context;self.apm=cost['targets']['AP']['model'];self.pm=cost['targets']['POWER_API']['model'];self.beta=self.apm['spec']['beta'];self.k=self.apm['raw_basis_coefficients'];self.pk=self.pm['raw_basis_coefficients']
  start=context['initial_context']['history_start_s'];self.intervals=[[[max(start,l),r,w] for l,r,w in vs if r>max(start,l)] for vs in context['pre_activity9']['intervals']]
  c=context['initial_context'];ac={**c,**c.get('targets',{}).get('AP',{})};pc={**c,**c.get('targets',{}).get('POWER_API',{})};a=ac['anchor'];self.anchor=a.get('time_s',a.get('t_s'));self.anchorAP=a.get('AP_c',a.get('AP'))
  hist=[self.anchorAP,a.get('SKIN_c',a.get('SKIN')),a.get('BAT_c',a.get('BAT')),a.get('pre20_AP_slope_c_s',a.get('pre20_AP_slope'))]
  norm=self.apm['history_normalization'];cov=[1.]+[(v-m)/s for v,m,s in zip(hist,norm['mean'],norm['scale'])]
  self.history=[sum(self.k[9+5*j+i]*cov[i] for i in range(5)) for j in range(2)]
  if self.apm['domain_enabled'] and ac['domain'] in self.apm['domains']:
   j=self.apm['domains'].index(ac['domain']);self.history=[v+self.k[19+2*j+i] for i,v in enumerate(self.history)]
  self.z=[sum(w*h(0,max(ac['history_start_s'],l),max(max(ac['history_start_s'],l),r),self.beta) for l,r,w in vs) for vs in self.intervals]
  self.za=[sum(w*h(self.anchor,max(ac['history_start_s'],l),max(max(ac['history_start_s'],l),r),self.beta) for l,r,w in vs) for vs in self.intervals]
  self.base=self.pk[0]+self.pk[1]*pc['baseline']['median_api_w'];self.t=0.;self.activity=[0.]*9;self.last=[0.]*9
 def AP(self,t=None,z=None):
  t=self.t if t is None else t;z=self.z if z is None else z
  return self.anchorAP+sum(k*(v-a) for k,v,a in zip(self.k[:9],z,self.za))+sum(c*-math.expm1(-(t-self.anchor)/tau) for c,tau in zip(self.history,(20,120)))
 def set_activity(self,a):
  for j,(x,y) in enumerate(zip(self.activity,a)):
   if x!=y:
    if x and self.t>self.last[j]:self.intervals[j].append([self.last[j],self.t,x])
    self.last[j]=self.t
  self.activity=list(a)
 def advance(self,dt):
  e=math.exp(-self.beta*dt);self.z=[e*z+(1-e)*a for z,a in zip(self.z,self.activity)];self.t+=dt
 def close(self):self.set_activity([0.]*9)
 def fixed_AP(self,t):
  z=[sum(w*h(t,l,r,self.beta) for l,r,w in vs) for vs in self.intervals];return self.AP(t,z)
 def AP_many(self,ts):
  ts=np.asarray(ts,dtype=float);out=np.full(len(ts),self.anchorAP)
  for k,vs,za in zip(self.k[:9],self.intervals,self.za):
   out-=k*za
   if vs and k:
    a=np.array(vs);l=a[:,0];r=a[:,1];w=a[:,2];u=ts[:,None]
    out+=k*((-np.expm1(-self.beta*np.maximum(0,np.minimum(u,r)-l)))*np.exp(-self.beta*np.maximum(0,u-r))@w)
  for c,tau in zip(self.history,(20,120)):out+=c*-np.expm1(-(ts-self.anchor)/tau)
  return out
 def power(self,t):return self.base+sum(k*sum(w*box(t,l,r,self.pm['spec']['window_s']) for l,r,w in vs) for k,vs in zip(self.pk[2:11],self.intervals))
 def energy(self,A,B):return self.base*(B-A)+sum(k*sum(w*ba(A,B,l,r,self.pm['spec']['window_s']) for l,r,w in vs) for k,vs in zip(self.pk[2:11],self.intervals))
 def meanAP(self,A,B):
  d=B-A;v=self.anchorAP*d
  for k,vs,za in zip(self.k[:9],self.intervals,self.za):v+=k*(sum(w*ha(A,B,l,r,self.beta) for l,r,w in vs)-za*d)
  for c,tau in zip(self.history,(20,120)):v+=c*(d+tau*math.exp(-(A-self.anchor)/tau)*math.expm1(-d/tau))
  return v/d
class Timing:
 def __init__(self,model,templates,variant):
  self.model,self.variant=model,variant;self.pools=collections.defaultdict(list);self.public={};self.compiled={};self.overhead={}
  for p in templates:self.pools[p['route'],p['priority']].append(p)
  for k,ps in self.pools.items():self.overhead[k]=float(np.median([(p['offset_s']['readback_end_ns'] if k[1]=='normal' else p['offset_s']['output_ready_ns'])-p['inference_s'] for p in ps]))
  for route in ROUTES:
   available=[p for p in templates if p['route']==route]
   if not available:continue
   # Same currently observed APK/runtime chosen by frequency, no faster-APK selection.
   identity=collections.Counter((p['model_sha256'],p['apk'],p['image_sha256'],p['engine'],p['version'],p['cpu_threads'],p['gpu_precision']) for p in available).most_common(1)[0][0]
   r=dict(zip(('model_sha256','apk','image_sha256','engine','version','cpu_threads','gpu_precision'),identity));r.update(route=route,domain='M8_READBACK_RENAME_RESPONSE',AP=30.,AP_age_s=0.,overlap_fraction=0.)
   X,unk=design([r],model['spec']);assert not unk
   c=np.array(model['coef']);labels=model['spec']['labels'];ai=labels.index('AP:'+route);oi=labels.index('OVERLAP:'+route)
   if variant=='NO_THERMAL':c[ai]=0
   if variant in ('LOW_SLOPE','HIGH_SLOPE'):
    sign=-1 if variant=='LOW_SLOPE' else 1;c[[ai,oi]]+=sign*1.645*np.array(model['bootstrap_sd'])[[ai,oi]]
   self.compiled[route]=(float(X[0]@c),float(c[ai])/10,float(c[oi]))
   self.public[route]=dict(identity=r,AP_observed_min=min(p['AP'] for p in available if p['AP'] is not None),AP_observed_max=max(p['AP'] for p in available if p['AP'] is not None),median_inference_s=float(np.median([p['inference_s'] for p in available])))
 def rate_duration(self,route,AP,peer):
  base,a,o=self.compiled[route];x=base+a*(AP-30.)+o*peer
  if not -20<x<math.log(60):raise ValueError('Timing log bound; unsupported extrapolation')
  return math.exp(x)
 def sample(self,route,priority,seed,ordinal):
  pool=self.pools[route,priority];assert pool,'Missing exact current response template'
  i=int.from_bytes(hashlib.sha256(f'{seed}|{ordinal}|{route}'.encode()).digest()[:8],'big')%len(pool);p=pool[i]
  # Paired CRN whole template plus correlated empirical residual, no independent phase shuffling.
  r={**p,'AP_age_s':0};pred=duration(self.model,r,p['AP'] if p['AP'] is not None else 30.,p['overlap_fraction'] or 0.,'CENTRAL')
  return p,p['inference_s']/pred
 def nominal(self,route,priority,AP):
  return max(1e-6,self.rate_duration(route,AP,0.)+self.overhead[route,priority])

def recipe(bank,registered):
 # Exact original offset_ns, ordinal, task, priority and deadline from source-bound M8 B2 manifest.
 return [dict(ordinal=q['ordinal'],arrival=q['offset_ns']/1e9,task=q['task_id'],priority=q['priority'],relative_deadline=q['deadline_ms']/1000.) for q in registered[bank]['requests']]
def allowed(route,owners):
 routes=[o['route'] for o in owners]
 if len(routes)>=2:return False
 if not routes:return True
 return set(routes+[route]) in ({'classification_GPU','detection_CPU'},{'classification_NPU','detection_CPU'})
class Engine:
 def __init__(self,model,templates,cost,context,case,registered):
  self.case=case;self.cost=Cost(cost,context);self.timing=Timing(model,templates,case['variant']);self.dt=case.get('dt_s',.005);self.time=0.;self.nextsample=0.;self.heldAP=self.cost.AP();self.heldtime=0.;self.requests=recipe(case['bank'],registered);self.ready=[];self.owners=[];self.completed=[];self.events=[];self.decisions=[];self.at=0;self.wait_until=0.;self.wait_dose=0.;self.samples=[];self.extrapolations=0
 def activity(self):
  a=[0.]*9
  for o in self.owners:
   phase=o['phase'];idx=ROUTE_INDEX[o['route']] if phase=='INFER' else 4 if phase=='ADMISSION' else 5 if phase=='POST' else 7;a[idx]+=1
  a[6]=float(bool(self.owners));a[8]=max(0,len(self.owners)-1);return a
 def candidates(self,joint):
  if len(self.owners)>=2 or not self.ready:return []
  ready=sorted(self.ready,key=lambda q:(q['arrival'],q['ordinal']))[:24];actions=[];avg=np.mean([self.timing.nominal('classification_GPU' if q['task']=='classification' else 'detection_CPU',q['priority'],self.heldAP) for q in ready]) if ready else 1.
  for q in ready:
   for route in (['classification_GPU','classification_NPU'] if q['task']=='classification' and joint else ['classification_GPU'] if q['task']=='classification' else ['detection_CPU']):
    if not allowed(route,self.owners):continue
    p=self.timing.nominal(route,q['priority'],self.heldAP);slack=q['arrival']+q['relative_deadline']-self.time-p;logatc=-math.log(p)-max(0,slack)/(2*avg)
    f=[(self.time-q['arrival'])/2,slack/2,p,q['relative_deadline']/2,float(q['priority']=='urgent'),float(route=='classification_GPU'),float(route=='classification_NPU'),float(route=='detection_CPU'),(self.heldAP-30)/10,(self.time-self.heldtime),len(self.ready)/24,len(self.owners)/2,logatc/10,self.wait_dose/1.6,float(slack>=0),0.]
    actions.append(dict(ordinal=q['ordinal'],route=route,p=p,slack=slack,logatc=logatc,features=f))
  # Lateness is an observation, never a reason to drop/reorder EDF/FIFO requests.
  if actions and not self.owners and self.wait_dose<1.6 and min(a['slack'] for a in actions)>.025:
   actions.append(dict(ordinal=None,route='WAIT',p=.02,slack=min(a['slack'] for a in actions)-.02,logatc=min(a['logatc'] for a in actions)-2,features=[0.,0.,.02,0.,0.,0.,0.,0.,(self.heldAP-30)/10,self.time-self.heldtime,len(self.ready)/24,0.,-1.,self.wait_dose/1.6,1.,1.]))
  return actions
 def dispatch(self,action):
  if action['route']=='WAIT':self.wait_until=self.time+.02;self.wait_dose+=.02;self.events.append([self.time,'WAIT',None,'WAIT']);return
  q=next(q for q in self.ready if q['ordinal']==action['ordinal']);self.ready.remove(q);route=action['route'];assert allowed(route,self.owners)
  p,residual=self.timing.sample(route,q['priority'],self.case['stream'],q['ordinal']);offset=p['offset_s']
  owner=dict(q,route=route,template_id=p['id'],template=p,residual=residual,dispatch=self.time,phase='GAP',left=offset['execution_start_ns'],progress=0.,times={'dispatch':self.time},response=None)
  self.owners.append(owner);self.events.append([self.time,'DISPATCH',q['ordinal'],route])
 def transition(self,o):
  v=o['template']['offset_s'];now=self.time
  if o['phase']=='GAP':o.update(phase='ADMISSION',left=v['host_inference_start_ns']-v['execution_start_ns']);o['times']['execution_start']=now
  elif o['phase']=='ADMISSION':o.update(phase='INFER',left=0.);o['times']['inference_start']=now
  elif o['phase']=='INFER':o.update(phase='RETURN_GAP',left=v['output_ready_ns']-v['host_inference_return_ns']);o['times']['inference_return']=now
  elif o['phase']=='RETURN_GAP':
   o.update(phase='POST',left=v['lane_available_ns']-v['output_ready_ns']);o['times']['output_ready']=now
   if o['priority']=='urgent':o['response']=now
   else:o['response']=now+v['readback_end_ns']-v['output_ready_ns']
  elif o['phase']=='POST':o['times']['AVAILABLE']=now;self.completed.append(o);self.owners.remove(o);self.events.append([now,'AVAILABLE',o['ordinal'],o['route']])
 def run(self,policy,controller=None,trace=True):
  joint=policy.endswith('JOINT');rule=policy.split('_')[0]
  while self.time<180.-1e-9:
   while self.at<len(self.requests) and self.requests[self.at]['arrival']<=self.time+1e-9:self.ready.append(self.requests[self.at]);self.at+=1
   for o in list(self.owners):
    for _ in range(8):
     if o not in self.owners:break
     done=o['progress']>=1-1e-10 if o['phase']=='INFER' else o['left']<=1e-10
     if not done:break
     self.transition(o)
   if self.time+1e-9>=self.nextsample:
    self.heldAP=self.cost.AP();self.heldtime=self.time;self.samples.append([self.time,self.heldAP]);self.nextsample=math.floor(self.time+1e-7)+1.
   if self.time>=self.wait_until-1e-9:
    actions=self.candidates(joint)
    if actions:
     if controller is not None:idx,meta=controller(actions,self.time)
     else:
      valid=[(i,a) for i,a in enumerate(actions) if a['route']!='WAIT']
      if rule=='FIFO':idx=min(valid,key=lambda ia:next((q['arrival'],q['ordinal']) for q in self.ready if q['ordinal']==ia[1]['ordinal']))[0]
      elif rule=='EDF':idx=min(valid,key=lambda ia:next((q['arrival']+q['relative_deadline'],q['arrival'],q['ordinal']) for q in self.ready if q['ordinal']==ia[1]['ordinal']))[0]
      else:idx=max(valid,key=lambda ia:ia[1]['logatc'])[0]
      meta=None
     a=actions[idx];self.decisions.append(dict(t=self.time,actions=actions,index=idx,NN=meta));self.dispatch(a);continue
   self.cost.set_activity(self.activity());dt=180.-self.time
   if self.at<len(self.requests):dt=min(dt,max(0,self.requests[self.at]['arrival']-self.time))
   if self.wait_until>self.time+1e-9:dt=min(dt,self.wait_until-self.time)
   dt=min(dt,self.nextsample-self.time)
   rates={};AP=self.cost.AP()
   for o in self.owners:
    if o['phase']=='INFER':
     peers=any(x is not o and x['phase']=='INFER' for x in self.owners);d=self.timing.rate_duration(o['route'],AP,float(peers))*o['residual'];rates[o['ordinal']]=1/d;dt=min(dt,self.dt,(1-o['progress'])*d)
     bounds=self.timing.public[o['route']];self.extrapolations+=int(not bounds['AP_observed_min']<=AP<=bounds['AP_observed_max'])
    else:dt=min(dt,o['left'])
   if dt<1e-11:raise ValueError('Zero advance/deadlock; no implicit recovery')
   for o in self.owners:
    if o['phase']=='INFER':o['progress']+=dt*rates[o['ordinal']]
    else:o['left']-=dt
   self.cost.advance(dt);self.time=self.cost.t
  self.cost.close();result=self.metrics()
  if trace:result.update(events=self.events,decisions=self.decisions,completed=[{k:v for k,v in o.items() if k not in ('template',)} for o in self.completed],activity=self.cost.intervals,sensor=self.samples,curve=[[float(t),float(a),self.cost.power(t)] for t,a in zip(np.arange(0,180.0001,.5),self.cost.AP_many(np.arange(0,180.0001,.5)))])
  return result
 def metrics(self):
  m={'case':self.case,'planned':len(self.requests),'completed':len(self.completed),'unfinished':len(self.requests)-len(self.completed),'wait_s':self.wait_dose,'API_J0_180':self.cost.energy(0,180),'API_J35_180':self.cost.energy(35,180),'AP_mean35_180':self.cost.meanAP(35,180),'AP180':self.cost.fixed_AP(180),'AP_peak_sampled_0_180':float(max(self.cost.AP_many(np.arange(0,180.0001,.5)))),'AP_extrapolation_steps':self.extrapolations,'late':0,'tardiness_s':0.}
  for priority in ('urgent','normal'):
   rs=[r for r in self.requests if r['priority']==priority];done=[o for o in self.completed if o['priority']==priority];lat=[o['response']-o['arrival'] for o in done];on=sum(o['response']<=o['arrival']+o['relative_deadline']+1e-9 for o in done);late=len(rs)-on
   m[priority]=dict(planned=len(rs),completed=len(done),on_time=on,late_or_unfinished=late,p95_s=float(np.quantile(lat,.95)) if lat else None,max_s=max(lat) if lat else None);m['late']+=late;m['tardiness_s']+=sum(max(0,o['response']-o['arrival']-o['relative_deadline']) for o in done)
  m['hard_feasible']=m['late']==0 and m['unfinished']==0
  return m
