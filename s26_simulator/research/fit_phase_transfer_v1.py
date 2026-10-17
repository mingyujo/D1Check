"""Measured multi-stage transfer repair for our policy's common plant.
R21 outcomes have been seen: all checks here are developmental diagnostics.
No policy environments, NN, optimizer updates, policy labels or manual gains.
"""
import collections,hashlib,json,math,os,statistics,zipfile
from pathlib import Path
import numpy as np
from timing_model import read,save,prepare,design,weights,estimate
STAGES=('GAP','ADMISSION','RETURN_GAP','POST')
BOUNDARIES=(('dispatch_ns','execution_start_ns'),('execution_start_ns','host_inference_start_ns'),('host_inference_return_ns','output_ready_ns'),('output_ready_ns','lane_available_ns'))
def peer_fraction(l,h,intervals):
 if h==l:return 0.
 spans=sorted((max(l,a),min(h,b)) for a,b in intervals if min(h,b)>max(l,a));total=0.;end=None
 for a,b in spans:
  if end is None:total+=b-a;end=b
  elif b>end:total+=b-max(a,end);end=b
 return total/(h-l)
def stage_rows(templates,records,owner_by_session):
 out={stage:[] for stage in STAGES}
 for p in templates:
  r=records[p['id']];ts=r['timestamps_ns'];other=[x for x in owner_by_session[r['session']] if x['id']!=p['id']]
  for stage,(lk,rk) in zip(STAGES,BOUNDARIES):
   l,h=ts[lk],ts[rk];assert l is not None and h is not None and h>=l
   overlap=peer_fraction(l,h,[(x['left'],x['right']) for x in other])
   assert -.0000001<=overlap<=1.0000001,'At most2 measured owners'
   # Priority is a response-contract covariate, never a policy identifier.
   q={k:p[k] for k in ('id','session','group','route','priority','model_sha256','image_sha256','domain','apk','engine','version','cpu_threads','gpu_precision','AP')};q.update(AP_age_s=r['AP_age_s'],overlap_fraction=overlap,observed_s=(h-l)/1e9,stage=stage,source_model_sha256=p['model_sha256']);q['model_sha256']=p['model_sha256']+'|priority='+p['priority'];out[stage].append(q)
 return out
def r21_rows(op):
 by=collections.defaultdict(list)
 for line in Path(op['r21_requests']).read_text(encoding='utf-8-sig').splitlines():
  q=json.loads(line);by[q['session_id']].append(q)
 aps={r['session']+'|'+r['id'].split('|')[1]:r for r in read(op['r21_timing_rows']) if r['mode']=='FLAT'};out={s:[] for s in STAGES}
 for s in read(op['r21_sessions']):
  with zipfile.ZipFile(s['archive']) as z:
   root=s['folder'];manifest=json.loads(z.read(root+'/device/manifest.json'));events=[json.loads(l) for l in z.read(root+'/device/progress.jsonl').decode().splitlines()];apk=next(e['apk_sha256'] for e in events if e.get('kind')=='session_start')
  qs=by[s['session_id']]
  for q in qs:
   route=q['task_id']+'_'+q['selected_backend'];rm=next(r for r in manifest['runtimes'] if r['key']==route);pr=next(e for e in events if e.get('kind')=='runtime_return' and e.get('key')==route);ap=aps[s['session_id']+'|'+q['request_id']];other=[x for x in qs if x['request_id']!=q['request_id']]
   base=dict(id=s['session_id']+'|'+q['request_id'],session=s['session_id'],group='R21_'+s['block'],block=s['block'],arm=s['arm'],route=route,priority=q['priority'],model_sha256=rm['model_sha256']+'|priority='+q['priority'],source_model_sha256=rm['model_sha256'],image_sha256=manifest['image']['sha256'],domain='M8_READBACK_RENAME_RESPONSE',apk=apk,engine=pr.get('engine'),version=pr.get('litert_version'),cpu_threads=pr.get('compiled_model_options',{}).get('cpu_options',{}).get('num_threads') if pr.get('compiled_model_options',{}).get('cpu_options') else rm.get('cpu_threads'),gpu_precision=pr.get('compiled_model_options',{}).get('gpu_options',{}).get('precision') if pr.get('compiled_model_options',{}).get('gpu_options') else rm.get('gpu_precision'),AP=ap['AP'],AP_age_s=ap['AP_age_s'])
   for stage,(lk,rk) in zip(STAGES,BOUNDARIES):
    l,h=q[lk],q[rk];assert h>=l;fraction=peer_fraction(l,h,[(x['dispatch_ns'],x['lane_available_ns']) for x in other]);assert fraction<=1+1e-7;out[stage].append(dict(base,stage=stage,observed_s=(h-l)/1e9,overlap_fraction=fraction))
 return out
def main(op):
 out=Path(op['output_dir']);out.mkdir();templates=read(op['templates_path']);wanted={p['id'] for p in templates};sessions={p['session'] for p in templates};records={};owners=collections.defaultdict(list)
 with open(op['rows_path'],encoding='utf-8') as f:
  for line in f:
   r=json.loads(line)
   if r['session'] not in sessions:continue
   t=r['timestamps_ns']
   if t['dispatch_ns'] is not None and t['lane_available_ns'] is not None:owners[r['session']].append(dict(id=r['id'],left=t['dispatch_ns'],right=t['lane_available_ns']))
   if r['id'] in wanted:records[r['id']]=r
 assert len(records)==len(templates)==8636;data=stage_rows(templates,records,owners);test=r21_rows(op);models={};rows=[];fits=0;receipt=out/'FIT_RECEIPTS.jsonl';bootstrap={}
 def record(x):
  with receipt.open('a',encoding='utf-8') as f:f.write(json.dumps(x)+'\n');f.flush();os.fsync(f.fileno())
 def fit(rr,mode,identity):
  nonlocal fits
  assert fits<op['fit_cap'];record(dict(event='START',id=identity));fits+=1;spec=prepare(rr,mode);X,_=design(rr,spec);c=estimate(X,np.log(np.maximum([r['observed_s'] for r in rr],1e-9)),weights(rr),spec);m=dict(spec=spec,coef=c.tolist(),bootstrap_sd=np.zeros(len(c)).tolist(),target='stage_duration_s',time_resolution_floor_s=1e-9,base_definition='route/exact_model_SHA/priority; suffix is an internal categorical key, not a claimed SHA',training_sessions=sorted({r['session'] for r in rr}),training_groups=sorted({r['group'] for r in rr}),known_zero_duration='Exact zero residual remains zero; log training at instrument1ns floor',scope='Developmental measured phase association, not isolated causal thermal/DVFS mechanism');save(out/(identity+'.json'),m);record(dict(event='COMPLETE',id=identity,rows=len(rr),model_sha256=hashlib.sha256((out/(identity+'.json')).read_bytes()).hexdigest()));return m
 def evaluate(m,rr,label,stage,mode):
  X,unknown=design(rr,m['spec']);bad=set(unknown);pred=np.exp(X@np.array(m['coef']))
  for i,r in enumerate(rr):rows.append(dict(id=r['id'],session=r['session'],group=r['group'],stage=stage,mode=mode,validation=label,observed_s=r['observed_s'],predicted_s=None if i in bad else float(pred[i]),unsupported=i in bad,AP=r['AP'],observed_phase_owner_overlap=r['overlap_fraction']))
 for stage in STAGES:
  rr=data[stage];groups=sorted({r['group'] for r in rr});models[stage]={}
  for mode in ('FLAT','THERMAL_PAIR'):
   for group in groups:
    train=[r for r in rr if r['group']!=group];held=[r for r in rr if r['group']==group];m=fit(train,mode,stage+'_'+mode+'_OUT_'+group);evaluate(m,held,'WHOLE_M8_GROUP_OUT',stage,mode)
   m=fit(rr,mode,stage+'_'+mode+'_FULL');models[stage][mode]=m;evaluate(m,test[stage],'R21_SEEN_DEVELOPMENT_NOT_FIT_IN_STAGE_MODEL',stage,mode)
  primary=models[stage]['THERMAL_PAIR'];spec=primary['spec'];X,_=design(rr,spec);rng=np.random.default_rng(26101671);ss=sorted({r['session'] for r in rr});coef=[]
  for b in range(16):
   identity=stage+'_BOOT_'+str(b).zfill(2);assert fits<op['fit_cap'];record(dict(event='START',id=identity));fits+=1;mult=collections.Counter(rng.choice(ss,len(ss),replace=True).tolist());c=estimate(X,np.log(np.maximum([r['observed_s'] for r in rr],1e-9)),weights(rr,mult),spec);coef.append(c);record(dict(event='COMPLETE',id=identity,coef_sha256=hashlib.sha256(c.tobytes()).hexdigest()))
  primary['bootstrap_sd']=np.std(coef,axis=0,ddof=1).tolist();bootstrap[stage]=np.asarray(coef).tolist()
 save(out/'FINAL_MODELS.json',models);save(out/'BOOTSTRAP_COEF.json',bootstrap);save(out/'VALIDATION_ROWS.json',rows);save(out/'PHASE_TRAIN_ROWS.json',data);summary=[]
 for validation in ('WHOLE_M8_GROUP_OUT','R21_SEEN_DEVELOPMENT_NOT_FIT_IN_STAGE_MODEL'):
  for stage in STAGES:
   for mode in ('FLAT','THERMAL_PAIR'):
    rs=[r for r in rows if r['validation']==validation and r['stage']==stage and r['mode']==mode and r['predicted_s'] is not None];by=collections.defaultdict(list)
    for r in rs:by[r['session']].append(r)
    summary.append(dict(validation=validation,stage=stage,mode=mode,rows=len(rs),sessions=len(by),session_MAE_s=statistics.mean(statistics.mean(abs(r['predicted_s']-r['observed_s']) for r in a) for a in by.values()),session_bias_s=statistics.mean(statistics.mean(r['predicted_s']-r['observed_s'] for r in a) for a in by.values())))
 save(op['result_path'],dict(status='PASS',meaning='PHASE_TRANSFER_FIT_AND_DEVELOPMENT_VALIDATION_EXECUTED_NOT_YET_ADOPTED',fit_count=fits,fit_cap=op['fit_cap'],old_M8_vectors=8636,R21_validation_requests=2688,stages=list(STAGES),summary=summary,new_policy_environments=0,new_NN=0,new_RL=0,primary='THERMAL_PAIR fixed before fitting; adverse FLAT comparisons retained',assumptions='Observed owner overlap over each phase transferred to current-owner context; observed inference-start HAL prefix carried to neighboring short phase, not an identified instantaneous causal law; whole joint residual vector retained in future plant. Model adoption/JS equivalence/closed-loop repair tests still required.'))
if __name__=='__main__':main(read(os.environ['S26_UNIFIED_OPERATION']))
