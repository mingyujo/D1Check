"""Hierarchical log-time estimator. Temperature/overlap terms are associations,
transferred to instantaneous progress only by the registered quasistatic assumption.
No policy ID, outcome, future temperature or future arrivals are input features.
"""
import collections, hashlib, json, math, os
from pathlib import Path
import numpy as np

ROUTES=('classification_CPU','classification_GPU','classification_NPU','detection_CPU')
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,x):
 with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,allow_nan=False);f.flush();os.fsync(f.fileno())
def key(r):return r['route']+'|'+r['model_sha256']
def categories(r):return [r.get('domain') or 'UNKNOWN',r.get('apk') or 'UNKNOWN','|'.join(str(r.get(k)) for k in ('engine','version','cpu_threads','gpu_precision')),r.get('image_sha256') or 'UNKNOWN']
def prepare(rows,mode):
 bases=sorted(set(key(r) for r in rows));cats=[sorted(set(categories(r)[j] for r in rows)) for j in range(4)]
 labels=['BASE:'+b for b in bases]
 for j,vs in enumerate(cats):labels += [f'NUISANCE{j}:'+v for v in vs[1:]]
 if mode!='FLAT':labels += ['AP:'+r for r in ROUTES]+['AP_MISSING:'+r for r in ROUTES]
 if mode=='THERMAL_PAIR':labels += ['OVERLAP:'+r for r in ROUTES]
 return dict(mode=mode,bases=bases,cats=cats,labels=labels,AP_center_c=30.,AP_scale_c=10.,AP_max_age_s=10.,penalty=1.)
def design(rows,spec):
 idx={n:i for i,n in enumerate(spec['labels'])};X=np.zeros((len(rows),len(idx)),dtype=np.float64);unknown=[]
 for i,r in enumerate(rows):
  b='BASE:'+key(r)
  if b not in idx:unknown.append(i);continue
  X[i,idx[b]]=1
  for j,v in enumerate(categories(r)):
   if f'NUISANCE{j}:'+v in idx:X[i,idx[f'NUISANCE{j}:'+v]]=1
  if spec['mode']!='FLAT':
   known=r.get('AP') is not None and r.get('AP_age_s') is not None and 0<=r['AP_age_s']<=spec['AP_max_age_s']
   if known:X[i,idx['AP:'+r['route']]]=(r['AP']-30.)/10.
   else:X[i,idx['AP_MISSING:'+r['route']]]=1
  if spec['mode']=='THERMAL_PAIR':X[i,idx['OVERLAP:'+r['route']]]=r['overlap_fraction'] or 0.
 return X,unknown
def weights(rows,multipliers=None):
 by=collections.Counter((r['group'],r['session']) for r in rows);sessions=collections.defaultdict(set)
 for r in rows:sessions[r['group']].add(r['session'])
 w=np.array([1/len(sessions[r['group']])/by[r['group'],r['session']]*(1 if multipliers is None else multipliers.get(r['session'],0)) for r in rows])
 return w*len(w)/w.sum()
def estimate(X,y,w,spec):
 # Explicit fixed ridge and three Huber iterations on log time, no tuning on policy results.
 penalty=np.ones(X.shape[1]);penalty[:len(spec['bases'])]=1e-5
 effective=w.copy();coef=np.zeros(X.shape[1])
 for _ in range(3):
  coef=np.linalg.solve(X.T@(effective[:,None]*X)+np.diag(penalty),X.T@(effective*y))
  residual=y-X@coef;scale=max(1e-6,1.4826*np.median(abs(residual-np.median(residual))))
  effective=w*np.minimum(1,1.5*scale/np.maximum(abs(residual),1e-12))
 return coef
def duration(model,row,AP,overlap,variant='CENTRAL'):
 r={**row,'AP':float(AP),'AP_age_s':0.,'overlap_fraction':float(overlap)}
 X,unknown=design([r],model['spec'])
 if unknown:raise ValueError('Unsupported exact model/route identity')
 c=np.array(model['coef'],dtype=float)
 labels=model['spec']['labels'];thermal=[i for i,n in enumerate(labels) if n.startswith('AP:')];pair=[i for i,n in enumerate(labels) if n.startswith('OVERLAP:')]
 if variant=='NO_THERMAL':c[thermal]=0
 elif variant in ('LOW_SLOPE','HIGH_SLOPE'):
  sign=-1 if variant=='LOW_SLOPE' else 1
  c[thermal+pair]+=sign*1.645*np.array(model['bootstrap_sd'])[thermal+pair]
 logd=float(X[0]@c)
 if not -20<logd<math.log(60):raise ValueError('Timing extrapolation numerical/support bound exceeded; no silent fallback')
 return math.exp(logd)
def phase_vector(r):
 t=r['timestamps_ns'];required=['dispatch_ns','execution_start_ns','host_inference_start_ns','host_inference_return_ns','output_ready_ns','persist_complete_ns','worker_release_ns','lane_available_ns']
 if r['domain']!='M8_READBACK_RENAME_RESPONSE' or not r['inference_eligible'] or any(t[k] is None for k in required):return None
 if not all(t[a]<=t[b] for a,b in zip(required,required[1:])):return None
 if r['priority']=='normal':
  if t['readback_start_ns'] is None or t['readback_end_ns'] is None:return None
  if not t['persist_complete_ns']<=t['readback_start_ns']<=t['readback_end_ns']<=t['worker_release_ns']:return None
 # Urgent returns at output_ready; absent readback stays absent, never a fabricated zero duration.
 v={k:None if t[k] is None else (t[k]-t['dispatch_ns'])/1e9 for k in t}
 return dict(id=r['id'],session=r['session'],group=r['group'],route=r['route'],priority=r['priority'],model_sha256=r['model_sha256'],image_sha256=r['image_sha256'],domain=r['domain'],apk=r['apk'],engine=r['engine'],version=r['version'],cpu_threads=r['cpu_threads'],gpu_precision=r['gpu_precision'],AP=r['AP'],overlap_fraction=r['overlap_fraction'],inference_s=r['inference_s'],offset_s=v)
def fit_main(op):
 out=Path(op['output_dir']);out.mkdir()
 allrows=[]
 with open(op['rows_path'],encoding='utf-8') as f:
  for line in f:allrows.append(json.loads(line))
 rows=[r for r in allrows if r['inference_eligible']];phase=[p for r in allrows if (p:=phase_vector(r)) is not None]
 assert len(allrows)==88688 and len(rows)==81736
 save(out/'PHASE_TEMPLATES.json',phase)
 groups=sorted(set(r['group'] for r in rows));metrics=[];fitlog=[];fits=0
 ledger=(out/'FIT_RECEIPTS.jsonl').open('x',encoding='utf-8')
 def record(identity,phase_,extra=None):
  ledger.write(json.dumps(dict(id=identity,event=phase_,**(extra or {})))+'\n');ledger.flush();os.fsync(ledger.fileno())
 models={}
 for mode in ('FLAT','THERMAL','THERMAL_PAIR'):
  for group in groups:
   train=[r for r in rows if r['group']!=group];test=[r for r in rows if r['group']==group]
   identity=f'OOF_{mode}_{group}';record(identity,'START');fits+=1
   spec=prepare(train,mode);X,_=design(train,spec);c=estimate(X,np.log([r['inference_s'] for r in train]),weights(train),spec)
   Xt,unknown=design(test,spec);keep=np.ones(len(test),bool);keep[unknown]=False;yp=np.exp(Xt@c)
   for i,r in enumerate(test):
    metrics.append(dict(id=r['id'],session=r['session'],pool=r['pool'],group=group,route=r['route'],mode=mode,AP=r['AP'],overlap=r['overlap_fraction'],observed_s=r['inference_s'],predicted_s=float(yp[i]) if keep[i] else None,unseen_exact_model=not bool(keep[i])))
   record(identity,'COMPLETE',{'train':len(train),'test':len(test),'unknown_model':len(unknown),'coef_sha256':hashlib.sha256(c.tobytes()).hexdigest()})
  identity='FULL_'+mode;record(identity,'START');fits+=1
  spec=prepare(rows,mode);X,_=design(rows,spec);y=np.log([r['inference_s'] for r in rows]);w=weights(rows);c=estimate(X,y,w,spec)
  models[mode]=dict(spec=spec,coef=c.tolist(),bootstrap_sd=np.zeros(len(c)).tolist())
  record(identity,'COMPLETE',{'rows':len(rows),'coef_sha256':hashlib.sha256(c.tobytes()).hexdigest()})
 primary=models['THERMAL_PAIR'];spec=primary['spec'];X,_=design(rows,spec);rng=np.random.default_rng(261016);sessions=sorted(set(r['session'] for r in rows));bs=[]
 for i in range(32):
  identity=f'CLUSTER_BOOTSTRAP_{i:02d}';record(identity,'START');fits+=1
  chosen=rng.choice(sessions,len(sessions),replace=True);mult=collections.Counter(chosen)
  bs.append(estimate(X,y,weights(rows,mult),spec));record(identity,'COMPLETE')
 primary['bootstrap_sd']=np.std(bs,axis=0,ddof=1).tolist();primary['bootstrap_coefficients']=[c.tolist() for c in bs]
 assert fits<=op['fit_cap'];ledger.close()
 save(out/'TIMING_MODELS.json',models)
 with (out/'OOF.jsonl').open('x',encoding='utf-8') as f:
  for r in metrics:f.write(json.dumps(r,allow_nan=False)+'\n')
 summary=[]
 for mode in models:
  for pool in ('ALL','OLD','M8'):
   mr=[r for r in metrics if r['mode']==mode and(pool=='ALL' or r['pool']==pool)]
   ok=[r for r in mr if r['predicted_s'] is not None];err=[abs(r['predicted_s']-r['observed_s']) for r in ok]
   summary.append(dict(mode=mode,pool=pool,planned=len(mr),predicted=len(ok),unsupported=len(mr)-len(ok),request_MAE_s=float(np.mean(err)) if err else None,session_MAE_s=float(np.mean([np.mean([abs(r['predicted_s']-r['observed_s']) for r in ok if r['session']==s]) for s in set(r['session'] for r in ok)])) if err else None))
 effects={r:{'log_duration_per_10C':primary['coef'][spec['labels'].index('AP:'+r)],'log_duration_full_supported_peer_overlap':primary['coef'][spec['labels'].index('OVERLAP:'+r)]} for r in ROUTES}
 result=dict(status='PASS',meaning='ESTIMATOR_EXECUTED_NOT_CAUSAL_OR_PHONE_VALIDATED',original_rows=len(allrows),fit_rows=len(rows),physical_sessions=len(set(r['session'] for r in rows)),source_counts=dict(collections.Counter(r['pool'] for r in rows)),phase_templates=len(phase),phase_counts=dict(collections.Counter(p['route']+'|'+p['priority'] for p in phase)),fits=fits,fit_cap=op['fit_cap'],summary=summary,effects=effects,primary='THERMAL_PAIR_FIXED_BEFORE_FIT',assumptions=['Quasistatic transfer of prior-AP/average-overlap association to instantaneous progress','Same exact route/model core pooled across apps, with domain/APK/runtime/image nuisance offsets','Non-inference phase template transferred across workload recipes within current M8 contract','LOW/HIGH are marginal bootstrap-slope sensitivity, not a simultaneous confidence band'],limitations=['Observational confounding and stale HAL','API Joules uncalibrated','OOF shared device/cohorts, not new phone verification','Unavailable model IDs excluded, not zero'],negative_transfer_preserved=True)
 save(out/'FIT_RESULT.json',result)
if __name__=='__main__':fit_main(read(os.environ['S26_UNIFIED_OPERATION']))
