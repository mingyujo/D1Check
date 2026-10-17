"""Independent saved-activity arithmetic and timing audit; never runs a policy environment.

Power/AP use analytic event-prefix kernels (production uses a chronological sweep).
Action replay is explicitly same-source replay, not an independent planner proof.
"""
import datetime,gzip,hashlib,importlib.util,json,math,msvcrt,os,subprocess,sys,time,traceback
from pathlib import Path
import numpy as np
W=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('owner',W/'shared_S26-ROLLING-ATC-RL-TRAIN-20261016_multi_owner.py');owner=importlib.util.module_from_spec(spec);spec.loader.exec_module(owner)
read,save,append,sha=owner.read,owner.save,owner.append,owner.sha
NAMES=['classification_CPU','detection_CPU','classification_GPU','classification_NPU']
checks=0
def test(ok,msg):
 global checks
 checks+=1
 if not bool(ok):raise AssertionError(msg)
def close(a,b,msg,tol=1e-8):test(abs(float(a)-float(b))<=tol,msg+': '+repr((a,b)))
def seed(s):
 h=2166136261
 for c in s:h=((h^ord(c))*16777619)&0xffffffff
 h^=h>>16;h=(h*0x7feb352d)&0xffffffff;h^=h>>15
 return h&0xffffffff
def series(ints,ts,beta=None,start=-30):
 ts=np.asarray(ts,dtype=float);out=np.zeros((len(ts),9))
 for j,xs in enumerate(ints):
  ev=[];segments=[]
  for l,r,w in xs:
   l=max(start,l)
   if r>l:ev.extend(((l,w),(r,-w)));segments.append((l,r,w))
  if not ev:continue
  ev.sort();e=np.array([v[0] for v in ev]);v=np.array([v[1] for v in ev]);after=np.cumsum(v)
  if beta is None:
   # Prefix positive segment areas, avoiding cancellation of large epoch*time sums.
   areas=np.cumsum(np.r_[0,after[:-1]]*np.diff(np.r_[start,e]));ix=np.searchsorted(e,ts,side='right')-1;valid=ix>=0;out[valid,j]=areas[ix[valid]]+after[ix[valid]]*(ts[valid]-e[ix[valid]])
  else:
   # Reset exponential origins every200 dimensionless time units. This is stable
   # for legacy sessions longer than exp()'s range, without changing the kernel.
   blocks=np.floor((ts-start)*beta/200).astype(int)
   for block in np.unique(blocks):
    mask=blocks==block;t0=start+block*200/beta;qt=ts[mask];z0=math.fsum(w*(math.exp(-beta*max(0,t0-r))-math.exp(-beta*(t0-l))) for l,r,w in segments if l<t0);a0=math.fsum(w for l,r,w in segments if l<=t0<r);sel=(e>t0)&(e<=max(qt));be=e[sel];bv=v[sel];ix=np.searchsorted(be,qt,side='right');decay=np.exp(-beta*(qt-t0));out[mask,j]=a0+np.r_[0,np.cumsum(bv)][ix]+(z0-a0)*decay-decay*np.r_[0,np.cumsum(bv*np.exp(beta*(be-t0)))][ix]
 return out
def predict(m,ints,targets,ts):
 ts=np.asarray(ts,dtype=float);target=m['target'];a=targets['AP']['anchor'];hist=[a.get('AP_c',a.get('AP')),a.get('SKIN_c',a.get('SKIN')),a.get('BAT_c',a.get('BAT')),a.get('pre20_AP_slope_c_s',a.get('pre20_AP_slope'))]
 if target=='POWER_API':
  box=(series(ints,ts)-series(ints,ts-.5))/.5
  f=[np.ones((len(ts),1)),np.full((len(ts),1),(targets['POWER_API']['baseline']['median_api_w'] if m['mode']=='POSITIVE_ADDITIVE' else math.log(targets['POWER_API']['baseline']['median_api_w']))),box]
  if m['mode'] in ('LOG_DYNAMIC','GAMMA_DYNAMIC','GAMMA_HISTORY','POSITIVE_ADDITIVE'):
   f.extend(series(ints,ts,1/tau) for tau in (1,10,60))
   if m['mode']!='POSITIVE_ADDITIVE':f.append(np.column_stack((box[:,0]*box[:,1],box[:,1]*box[:,2],box[:,1]*box[:,3])))
  if m['mode']=='GAMMA_HISTORY':
   known=all(x is not None and math.isfinite(x) for x in hist) and a.get('available_upper_s',a.get('completion_upper_s',1))<=0
   f.append(np.tile(hist+[0] if known else [0,0,0,0,1],(len(ts),1)))
 else:
  anchor=a.get('time_s',a.get('t_s'));f=[series(ints,ts,b)-series(ints,[anchor],b) for b in (.06,1/60)]
  f.extend((-np.expm1(-(ts-anchor)/tau))[:,None]*np.array([1]+hist)[None,:] for tau in (20,120))
 x=np.concatenate(f,axis=1);test(x.shape[1]==len(m['coef']),'feature ABI');y=((x-np.array(m['mean']))/np.array(m['scale']))@np.array(m['coef'])
 return (y if m['mode']=='POSITIVE_ADDITIVE' else np.exp(y)) if target=='POWER_API' else hist[0]+y
def timing_log(packet,p,AP,model):
 m=packet['timing'];labels=m['spec']['labels'];r=p['route'];cats=[p.get('domain') or 'UNKNOWN',p.get('apk') or 'UNKNOWN','|'.join('None' if p.get(k) is None else str(p[k]) for k in ('engine','version','cpu_threads','gpu_precision')),p.get('image_sha256') or 'UNKNOWN']
 # Identity domain is fixed by the production timing contract.
 cats[0]='M8_READBACK_RENAME_RESPONSE';constant=m['coef'][labels.index('BASE:'+r+'|'+p['model_sha256'])]
 for j,c in enumerate(cats):
  label='NUISANCE'+str(j)+':'+c
  if label in labels:constant+=m['coef'][labels.index(label)]
 k=labels.index('AP:'+r);beta=m['coef'][k]+(1.645*m['bootstrap_sd'][k] if model['measured_beta_variant']=='HIGH_SLOPE' else 0)
 return constant+beta*(AP-30)/10
def physical(packet,r):
 ints=r['activity'];targets=next(s for s in packet['scenarios'] if s['id']==r['scenario'])['context']['initial_context']['targets'];end=150 if r['right_censored_at150'] else 180;dt=r['config']['power_dt_s'];ts=np.arange(round(end/dt)+1)*dt
 ap=predict(packet['AP'],ints,targets,ts);pw=predict(packet['power'],ints,targets,ts);J=np.sum((pw[1:]+pw[:-1])*dt/2);area=np.sum((ap[1:]+ap[:-1])[ts[:-1]>=35]*dt/2)/145
 if end==180:
  for x,y,label in [(J,r['J_API0_180'],'J180'),(area,r['AP35_180_mean'],'APmean'),(ap[-1],r['AP180'],'AP180')]:close(x,y,label)
 close(ap.max(),r['AP_peak_sampled'],'peak')
 for t,a,p in r['curve']:i=round(t/dt);close(a,ap[i],'curve AP');close(p,pw[i],'curve power')
 st=np.array([s['time'] for s in r['sensor']]);sa=predict(packet['AP'],ints,targets,st)
 for s,a in zip(r['sensor'],sa):close(s['AP'],a,'held sensor AP');close(s['available']-s['time'],.2,'sensor latency')
 return dict(J120=float(np.sum((pw[1:]+pw[:-1])[ts[1:]<=120]*dt/2)),J180=float(J) if end==180 else None,APmean=float(area) if end==180 else None,AP180=float(ap[-1]) if end==180 else None,observed_end=end,J_observed_prefix=float(J),peak=float(ap.max()),actual_three_inference_s=sum(dt for _,dt,rates in r['advances'] if len(rates)==3),actual_two_or_more_inference_s=sum(dt for _,dt,rates in r['advances'] if len(rates)>=2),CPU_busy_s=sum(c['end']-c['start'] for c in r['cpu_intervals']))
def timing_audit(packet,r):
 """Recompute each saved Euler work rate from independent AP and actual active peers."""
 adv=r['advances'];test(r['work_rate_sampling']=='MIDPOINT_WITH_EVENT_ROOT_V1','registered midpoint rate timing');ts=np.array([a[0]+a[1]/2 for a in adv]);targets=next(s for s in packet['scenarios'] if s['id']==r['scenario'])['context']['initial_context']['targets'];aps=predict(packet['AP'],r['activity'],targets,ts);model=packet['multi']['models'][r['config']['model']]
 templates={p['id']:p for p in packet['templates']};requests={q['ordinal']:q for q in r['requests']+r['active_at_censor']};byroute={route:next(x for x in packet['templates'] if x['route']==route and x['overlap_fraction']==0) for route in NAMES}
 residuals={};coefficients={}
 for route,p in byroute.items():coefficients[route]=(timing_log(packet,p,30,model),timing_log(packet,p,40,model)-timing_log(packet,p,30,model))
 for ordinal,q in requests.items():
  sample=templates[q['template_id']];reference=timing_log(packet,sample,sample.get('AP',30),packet['multi']['models']['CENTRAL']);residuals[ordinal]=sample['inference_s']/math.exp(reference);close(q['residual'],residuals[ordinal],'sample residual')
 phase_events=[e for e in r['phase_trace'] if e['event'] in ('ENTER','AVAILABLE')];phase_cursor=0;current={};cpu_cursor=0;cpu_intervals=r['cpu_intervals'];progress={};maxerr=0;active_steps=0
 for (t,dt,rates),AP in zip(adv,aps):
  while phase_cursor<len(phase_events) and phase_events[phase_cursor]['time']<=t+1e-10:
   event=phase_events[phase_cursor];phase_cursor+=1
   if event['event']=='AVAILABLE':current.pop(event['ordinal'],None)
   else:current[event['ordinal']]=event
  while cpu_cursor<len(cpu_intervals) and cpu_intervals[cpu_cursor]['end']<=t+1e-10:cpu_cursor+=1
  cpu=cpu_intervals[cpu_cursor] if cpu_cursor<len(cpu_intervals) and cpu_intervals[cpu_cursor]['start']<=t+1e-10 else None
  expected_active={i for i,e in current.items() if e['phase']=='INFER' and (not e['route'].endswith('_CPU') or cpu is not None and cpu['ordinal']==i and cpu['phase']=='INFER')}
  test({i for i,_,_ in rates}==expected_active,'actual CPU server and accelerator work-rate coverage')
  test(dt>0,'positive advance');active={i for i,_,_ in rates}
  for ordinal,before,rate in rates:
   q=requests[ordinal];route=q['route'];constant,beta=coefficients[route];log=constant+beta*(AP-30)/10+math.log(residuals[ordinal])
   for peer in active-{ordinal}:
    rr=requests[peer]['route'];known='detection_CPU' in (route,rr) and any(x in ('classification_GPU','classification_NPU') for x in (route,rr))
    if known:
     m=packet['timing'];k=m['spec']['labels'].index('OVERLAP:'+route);log+=m['coef'][k]+(1.645*m['bootstrap_sd'][k] if model['measured_beta_variant']=='HIGH_SLOPE' else 0)
    else:log+=model['unknown_beta']
   expected=math.exp(-log);maxerr=max(maxerr,abs(expected-rate));close(expected,rate,'thermal/interference rate',1e-8);close(before,progress.get(ordinal,0),'work conservation',1e-8);progress[ordinal]=before+dt*rate;active_steps+=1
 for q in r['requests']:close(progress[q['ordinal']],1,'complete inference work',1e-8)
 return dict(rate_checks=active_steps,max_rate_error=maxerr,advances=len(adv))
def phase_service_audit(r):
 events={}
 for e in r['phase_trace']:
  if e['event'] in ('ENTER','AVAILABLE'):events.setdefault(e['ordinal'],[]).append(e)
 intervals=r['cpu_intervals'];last=-1;wait=0
 for c in intervals:test(c['start']>=last-1e-10 and c['end']>=c['start'],'shared CPU capacity/nonpreemptive interval');last=c['end']
 for ordinal,es in events.items():
  for e,nxt in zip(es,es[1:]):
   if e['phase']=='INFER':
    if e['route'].endswith('_CPU'):
     parts=[c for c in intervals if c['ordinal']==ordinal and c['phase']=='INFER' and c['start']>=e['time']-1e-10 and c['end']<=nxt['time']+1e-10];test(len(parts)==1,'one nonpreemptive CPU inference');close(parts[0]['end'],nxt['time'],'CPU inference release');wait+=parts[0]['start']-e['time']
    continue
   wall=e['wall_duration_s'];service=e['cpu_service_s'];parts=[c for c in intervals if c['ordinal']==ordinal and c['phase']==e['phase'] and c['start']>=e['time']-1e-10 and c['end']<=nxt['time']+1e-10]
   if service>1e-12:
    test(len(parts)==1,'one nonpreemptive phase service');close(parts[0]['end']-parts[0]['start'],service,'CPU prefix service');close(nxt['time']-e['time'],wall+parts[0]['start']-e['time'],'wall plus extra queue only; no double service');wait+=parts[0]['start']-e['time']
   else:close(nxt['time']-e['time'],wall,'passive measured wall conservation')
  last_event=es[-1]
  if last_event['event']=='ENTER' and (last_event['phase']=='INFER' and last_event['route'].endswith('_CPU') or last_event['cpu_service_s']>1e-12):
   parts=[c for c in intervals if c['ordinal']==ordinal and c['phase']==last_event['phase'] and c['start']>=last_event['time']-1e-10];wait+=(parts[0]['start'] if parts else 150)-last_event['time']
 close(wait,r['shared_cpu_wait_s'],'independent shared CPU waiting time',1e-8)
 return dict(expected_wait_s=wait)
def activity_audit(packet,r):
 """Rebuild route/shared phase activity from actual phase and CPU allocation events."""
 context=next(s for s in packet['scenarios'] if s['id']==r['scenario'])['context'];expected=[[x[:] for x in xs] for xs in context['pre_activity9']['intervals']];ev=[];model=packet['multi']['models'][r['config']['model']]
 for e in r['phase_trace']:
  if e['event'] in ('ENTER','AVAILABLE'):ev.append((e['time'],1,e))
 for c in r['cpu_intervals']:ev.extend(((c['start'],2,c),(c['end'],0,c)))
 ev.sort(key=lambda x:(x[0],x[1]));owners={};cpu=None;prev=0;index=0
 def add(until):
  nonlocal prev
  if until<=prev:return
  active=[0]*9
  for ordinal,o in owners.items():
   phase=o['phase'];route=o['route'];cpu_has=cpu is not None and cpu['ordinal']==ordinal and cpu['phase']==phase
   if phase=='INFER':active[NAMES.index(route)]+=1
   elif phase in ('ADMISSION','POST'):active[4 if phase=='ADMISSION' else 5]+=1
   else:active[7]+=1
  active[6]=int(bool(owners));routes=[o['route'] for o in owners.values()]
  test(len(routes)<=r['config']['capacity'] and len({x.rsplit('_',1)[-1] for x in routes})==len(routes),'phase-trace slot capacity')
  for i,a in enumerate(routes):
   for b in routes[i+1:]:active[8]+=1 if 'detection_CPU' in (a,b) and any(x in ('classification_GPU','classification_NPU') for x in (a,b)) else model['unknown_pair_weight']
  for j,w in enumerate(active):
   if w:expected[j].append([prev,until,w])
  prev=until
 while index<len(ev):
  t=ev[index][0];add(t)
  while index<len(ev) and ev[index][0]==t:
   _,kind,e=ev[index];index+=1
   if kind==0:
    if cpu is e:cpu=None
   elif kind==2:cpu=e
   elif e['event']=='AVAILABLE':owners.pop(e['ordinal'])
   else:owners[e['ordinal']]=e
 add(150 if r['right_censored_at150'] else 180)
 boundaries=sorted({0,180}|{v for xs in expected+r['activity'] for x in xs for v in x[:2]})
 error=float(np.max(np.abs(series(expected,boundaries)-series(r['activity'],boundaries))));close(error,0,'independent phase/CPU activity reconstruction',1e-8)
 return dict(max_integral_channel_error=error,events=len(ev),boundaries=len(boundaries))
def observations(packet,r):
 planned={q['ordinal']:q for q in r['planned_requests']};done={q['ordinal']:q for q in r['requests']};dispatch={e[2]:e for e in r['events'] if e[1]=='DISPATCH'};models=packet['multi']['models'];pools={}
 for p in packet['templates']:
  if p['overlap_fraction']==0 and not p.get('priority_transfer'):pools.setdefault((p['route'],p['priority']),[]).append(p)
 for q in r['requests']:
  pool=pools[(q['route'],q['priority'])];p=pool[seed(str(r['config']['stream'])+'|phase|'+str(q['ordinal'])+'|'+q['route'])%len(pool)];test(p['id']==q['template_id'],'whole-vector RNG identity')
 for d in r['policy_decisions']:
  obs=d['public_observation'];t=d['time'];test(obs['time']==t and obs['capacity']==r['config']['capacity'],'public clock/cap')
  ready={i for i,q in planned.items() if q['readyAt']<=t+1e-9 and (i not in dispatch or dispatch[i][0]>=t-1e-10)}
  # Multiple dispatch decisions can share a timestamp; observed owners distinguish their order.
  occupied={o['ordinal'] for o in obs['owners']};already={i for i,e in dispatch.items() if e[0]<t-1e-10};ready-=occupied;ready-=already
  # Same-time already-completed work cannot occur because all observed phase vectors are positive.
  test({q['ordinal'] for q in obs['ready']}==ready,'arrived public ready set')
  for q in obs['ready']:
   p=planned[q['ordinal']];test(all(q[k]==p[k] for k in ('task','priority','arrival','deadline')),'public request fields')
  for o in obs['owners']:
   q=done.get(o['ordinal']) or next(x for x in r['active_at_censor'] if x['ordinal']==o['ordinal']);test(q['route']==o['route'],'observed owner route')
   for k,v in o['times'].items():test(v<=t and q['times'][k]==v,'no future owner timestamps')
  eligible=[q for q in obs['ready'] if len(obs['owners'])<obs['capacity'] and any(all(x['route'].split('_')[-1]!=route.split('_')[-1] for x in obs['owners']) for route in (['detection_CPU'] if q['task']=='detection' else NAMES[0:1]+NAMES[2:]))]
  ranks={x['ordinal']:x for x in d['action']['request_ranks']};policy=r['config']['policy']
  key=lambda q:(q['arrival'],q['ordinal']) if policy=='FIFO' else (q['deadline'],q['arrival'],q['ordinal']) if policy=='EDF' else (-ranks[q['ordinal']]['ATC'],q['arrival'],q['ordinal'])
  test(min(eligible,key=key)['ordinal']==d['action']['ordinal'],'independent rank order')
  candidates=d['action']['candidates'];test(all(c['ordinal']==d['action']['ordinal'] for c in candidates),'same request candidate domain')
def audit(op_path):
 op=read(op_path);owner.verify(op);out=Path(op['output_dir']);auditdir=out/'AUDIT_V1';test(not auditdir.exists(),'Audit already consumed; no automatic rerun');census=owner.Census();handle=None;locked=False;node=None
 try:
  own=census.get();handle=Path(op['shared_byte_mutex']['path']).open('r+b');handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1);locked=True;auditdir.mkdir();save(auditdir/'OWNER.json',own['self']);test(read(op['result_path'])['completed']==3240,'execution complete')
  packet=read(op['packet_path']);receipts=[json.loads(x) for x in Path(op['receipts_path']).read_text(encoding='utf-8').splitlines() if x];rows=[json.loads(x) for x in (out/'ROWS.jsonl').read_text(encoding='utf-8').splitlines() if x];events={}
  for e in receipts:events.setdefault(e['id'],[]).append(e)
  test(len(events)==3240 and len(rows)==3240,'full coverage');test(all([x['event'] for x in es]==['START','PREPARED','COMPLETE'] for es in events.values()),'all receipt terminals')
  plans=read(op['case_plan_path'])+read(out/'EVAL_CASE_PLAN_SEALED.json');test(len(plans)==3240,'sealed plans');freeze=read(out/'DEV_SELECTION_FREEZE.json');seal=read(out/'EVAL_SEAL.json');test(seal['freeze_sha256']==sha(out/'DEV_SELECTION_FREEZE.json'),'DEV freeze SHA');test(seal['eval_plan_sha256']==sha(out/'EVAL_CASE_PLAN_SEALED.json'),'eval SHA')
  err=(auditdir/'action.stderr.log').open('x');node=subprocess.Popen([op['node_path'],str(W/'action_replay_server.cjs'),op['packet_path']],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW);save(auditdir/'NODE_LAUNCH.json',dict(pid=node.pid,parent=os.getpid(),new_policy_environments=0))
  forecast=0
  for index,(cfg,row) in enumerate(zip(plans,rows)):
   census.get();owner.verify(op);identity=cfg['identity'];test(row['logical_identity']==identity,'ordered coverage');es=events[identity];prepared=read(out/'prepared'/(identity+'.json'));raw=Path(prepared['raw_path']);cpath=out/'configurations'/(identity+'.json');test(read(cpath)==cfg,'config seal')
   test(sha(cpath)==prepared['config_sha256']==es[0]['config_sha256'],'config SHA');test(sha(raw)==prepared['raw_sha256']==row['raw_sha256']==es[-1]['raw_sha256'],'raw compressed SHA');payload=gzip.decompress(raw.read_bytes());test(hashlib.sha256(payload).hexdigest()==prepared['payload_sha256']==row['payload_sha256'],'payload SHA');r=json.loads(payload);test(r['packet_sha256']==sha(op['packet_path']),'packet SHA');owner.validate(r)
   if cfg['phase']=='EVAL':test(es[0]['utc']>seal['utc']>freeze['utc'],'freeze before EVAL')
   append(auditdir/'COST_REPLAY_RECEIPTS.jsonl',dict(event='START',id=identity,policy_environments=0,saved_activity_only=True))
   phase_service_audit(r);activityproof=activity_audit(packet,r);physicalproof=physical(packet,r);timeproof=timing_audit(packet,r);observations(packet,r)
   node.stdin.write(json.dumps({'raw_path':str(raw)})+'\n');node.stdin.flush();reply=json.loads(node.stdout.readline());test(reply['id']==identity,'replay identity');forecast+=reply['forecast_replays']
   proof=dict(id=identity,status='PASS',physical=physicalproof,timing=timeproof,activity=activityproof,action_replay=reply,checks_cumulative=checks,raw_sha256=sha(raw));save(auditdir/(identity+'.proof.json'),proof);append(auditdir/'COST_REPLAY_RECEIPTS.jsonl',dict(event='COMPLETE',id=identity,proof_sha256=sha(auditdir/(identity+'.proof.json'))));print(json.dumps(dict(completed=index+1,of=3240,checks=checks)),flush=True)
  node.stdin.close();test(node.wait(timeout=30)==0,'replay child exit');err.close();owner.verify(op)
  save(auditdir/'FINAL_AUDIT.json',dict(status='PASS',cases=3240,checks=checks,action_forecasts=forecast,policy_environments=0,new_RL=0,new_fit=0,independent_analytic_activity_cost=True,independent_timing_work_rates=True,same_source_action_replay=True,physical_phone_validation=False,utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
 except BaseException:
  if auditdir.exists():save(auditdir/'FAILURE.json',dict(status='FAIL_PRESERVED_NO_AUTOMATIC_RERUN',traceback=traceback.format_exc(),checks=checks))
  raise
 finally:
  if node and node.poll() is None:node.stdin.close();node.wait(timeout=30)
  if handle:
   if locked:handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
   handle.close()
  census.close()
if __name__=='__main__':audit(Path(sys.argv[1]).resolve())
