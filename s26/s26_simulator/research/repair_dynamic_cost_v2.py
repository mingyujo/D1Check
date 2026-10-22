"""Separate, post-R21 developmental repair. No hand-picked physical coefficients.
R21 is now seen development; group OOF is not a second independent R21 test.
"""
import collections,csv,hashlib,importlib.util,io,json,math,os,statistics,zipfile
from pathlib import Path
import numpy as np
from timing_model import read,save

def load_old(path):
 spec=importlib.util.spec_from_file_location('old_frozen_math',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def materialize(op,old):
 data=read(op['projection_path']);sessions=data['sessions'];cases={c['id']:c for c in read(op['cross_cases_path'])};r21=read(op['r21_sessions_path']);rows=[]
 for s in sessions:rows.append(s)
 for s in r21:
  c=cases[s['label']];ctx=c['context'];targetctx=ctx['targets'];t0=s['common_start_ns']
  with zipfile.ZipFile(s['archive']) as z:
   events=[json.loads(l) for l in z.read(s['folder']+'/device/progress.jsonl').decode().splitlines()];hs=next(n for n in z.namelist() if n.endswith('.csv') and 'hal_cont_' in n and hashlib.sha256(z.read(n)).hexdigest()==s['HAL_sha256']);hal=list(csv.DictReader(io.StringIO(z.read(hs).decode('utf-8-sig'))))
   ap=[dict(t_s=float(h['device_uptime_s'])-t0/1e9,value_c=float(h['AP'])) for h in hal if h.get('AP') not in ('',None) and not h.get('err')];power=[]
   for p in events:
    if p.get('kind')=='power_sample' and p.get('current_valid') and not p.get('plugged') and p.get('snapshot_start_ns') is not None and p.get('sensor_read_end_ns') is not None:
     power.append(dict(t_s=((p['snapshot_start_ns']+p['sensor_read_end_ns'])/2-t0)/1e9,value_api_w=-p['current_raw']*p['voltage_mV']/1e9))
   rows.append(dict(id=s['session_id'],session_uid=s['session_id'],domain=ctx['domain'],source_pool='M8',cohort='M8_R21_'+s['block'],cv_group='M8_R21_'+s['block'],history_start_s=-30.,activity9=c['activity'],targets=dict(AP=dict(eligible=True,anchor=targetctx['AP']['anchor'],observations=ap,fit_window_s=[0,210]),POWER_API=dict(eligible=True,baseline=targetctx['POWER_API']['baseline'],observations=power,fit_window_s=[0,210])),prior_role={'R21_confirmation_now_seen_development':True},selected_source={'archive':s['archive'],'progress_sha256':s['progress_sha256'],'HAL_sha256':s['HAL_sha256']},timing_contract='M8_READBACK_RENAME_RESPONSE'))
 assert len(rows)==228
 save(Path(op['output_dir'])/'SESSION_USE.json',[dict(id=old.uid(s),pool=old.pool(s),group=old.group(s),domain=s['domain'],targets={k:dict(eligible=v.get('eligible'),reasons=v.get('reasons')) for k,v in s['targets'].items()}) for s in rows])
 return rows
def features(ep,target,mode,old):
 t=ep['times'];segments=ep['segments'];history=ep['history_start_s']
 if target=='POWER_API':
  activity=old.windowed_activity(segments,t,.5,history);cols=[np.ones(len(t)),np.full(len(t),math.log(ep['baseline_api_w']))];labels=['intercept','log_past_API_background'];cols.extend(activity.T);labels.extend('box05:'+str(j) for j in range(9))
  if mode=='LOG_DYNAMIC':
   for tau in (1.,10.,60.):cols.extend(old.filtered_activity(segments,t,1/tau,history).T);labels.extend('tail'+str(tau)+':'+str(j) for j in range(9))
   cols.extend([activity[:,0]*activity[:,1],activity[:,1]*activity[:,2],activity[:,1]*activity[:,3]]);labels.extend(['CC_DC_product','CG_DC_product','CN_DC_product'])
  return np.column_stack(cols),labels
 # AP retains same measured anchor/history contract, adding slower activity tail; signed associative effects are allowed.
 cols=[];labels=[]
 for tau in (1/.06,60.):
  values=old.filtered_activity(segments,t,1/tau,history)-old.filtered_activity(segments,np.array([ep['anchor_s']]),1/tau,history)[0];cols.extend(values.T);labels.extend('APtau'+str(tau)+':'+str(j) for j in range(9))
 for tau in (20.,120.):
  kernel=-np.expm1(-(t-ep['anchor_s'])/tau)
  for j,x in enumerate(np.r_[1,ep['history']]):cols.append(kernel*x);labels.append('history'+str(tau)+':'+str(j))
 return np.column_stack(cols),labels
def main(op):
 out=Path(op['output_dir']);out.mkdir();old=load_old(op['old_math_source'])
 pulse=[[[0.,1.,1.]]]+[[] for _ in range(8)];test=old.filtered_activity(pulse,np.array([.5,2.]),1.,-30.);assert test.shape==(2,9) and abs(test[0,0]+math.expm1(-.5))<1e-12 and np.all(test[:,1:]==0)
 box=old.windowed_activity(pulse,np.array([.25,1.25]),.5,-30.);assert box.shape==(2,9) and abs(box[0,0]-.5)<1e-12 and abs(box[1,0]-.5)<1e-12
 save(out/'MATH_ABI_TEST.json',dict(status='PASS',checks=5,scope='Exact nine-feature matrix ABI/pulse; no policy env'))
 sessions=materialize(op,old);usage=[];prepared={};fits=0;results=[];models={};ledger=(out/'FIT_RECEIPTS.jsonl').open('x',encoding='utf-8')
 def record(x):ledger.write(json.dumps(x)+'\n');ledger.flush();os.fsync(ledger.fileno())
 for target in ('AP','POWER_API'):
  eps=[]
  for s in sessions:
   try:
    ep=old.prepare_session(s,target)
    if not old.activity_available(ep,9):raise ValueError('Unknown measured activity9/horizon')
    if target=='POWER_API':
     mask=ep['observed']>0
     if sum(mask)<3:raise ValueError('Fewer than3 positive log-power observations')
     ep['times']=ep['times'][mask];ep['observed']=ep['observed'][mask]
    eps.append(ep);usage.append(dict(id=old.uid(s),target=target,status='INCLUDED',points=len(ep['times'])))
   except ValueError as e:usage.append(dict(id=old.uid(s),target=target,status='EXCLUDED',reason=str(e)))
  prepared[target]=eps
  for mode in (('SIGNED_DYNAMIC',) if target=='AP' else ('LOG_CORE9','LOG_DYNAMIC')):
   entries=[]
   for ep in eps:
    X,labels=features(ep,target,mode,old);entries.append((ep,X,ep['observed']-ep['anchor_AP_c'] if target=='AP' else np.log(ep['observed'])))
   groups=sorted(set(ep['cv_group'] for ep in eps))
   for group in groups+[None]:
    fitid=target+'_'+mode+'_'+(group or 'FULL');assert fits<op['fit_cap'];record(dict(event='START',id=fitid));fits+=1
    train=[x for x in entries if group is None or x[0]['cv_group']!=group];test=[x for x in entries if x[0]['cv_group']==group] if group is not None else []
    X=np.vstack([x[1] for x in train]);y=np.concatenate([x[2] for x in train]);sw=old.session_weights([x[0] for x in train]);w=np.concatenate([np.full(len(e[2]),sw[i]/len(e[2])) for i,e in enumerate(train)]);mean=np.sum(w[:,None]*X,axis=0)/sum(w);scale=np.maximum(np.sqrt(np.sum(w[:,None]*(X-mean)**2,axis=0)/sum(w)),1e-6);mean[0]=0;scale[0]=1
    Z=(X-mean)/scale;penalty=op['ridge']/len(labels);c=np.linalg.solve(Z.T@(w[:,None]*Z)+penalty*np.eye(len(labels)),Z.T@(w*y));model=dict(target=target,mode=mode,labels=labels,mean=mean.tolist(),scale=scale.tolist(),coef=c.tolist(),training_ids=[x[0]['id'] for x in train],training_groups=sorted(set(x[0]['cv_group'] for x in train)),scope='ALL_SEEN_DEVELOPMENT_AFTER_R21_FAILURE',power_link='exp' if target=='POWER_API' else 'identity+measured anchor',ridge=op['ridge'])
    save(out/(fitid+'.json'),model)
    for ep,Xt,yt in test:
     raw=(Xt-mean)/scale@c;pred=raw+ep['anchor_AP_c'] if target=='AP' else np.exp(raw)
     if not np.isfinite(pred).all():raise ValueError('Nonfinite extrapolation, preserved')
     err=pred-ep['observed'];energy_pred=float(np.trapezoid(pred,ep['times'])) if target=='POWER_API' else None;energy_obs=float(np.trapezoid(ep['observed'],ep['times'])) if target=='POWER_API' else None
     results.append(dict(id=ep['id'],group=group,pool=ep['source_pool'],domain=ep['domain'],target=target,mode=mode,MAE=float(np.mean(abs(err))),bias=float(np.mean(err)),peak_error=float(max(pred)-max(ep['observed'])),predicted_area=energy_pred,observed_area=energy_obs,window=ep['actual_window_s'],points=len(pred),times=ep['times'].tolist(),observed=ep['observed'].tolist(),predicted=pred.tolist()))
    record(dict(event='COMPLETE',id=fitid,model_sha256=hashlib.sha256((out/(fitid+'.json')).read_bytes()).hexdigest(),train_sessions=len(train),test_sessions=len(test)))
    if group is None:models[target+'_'+mode]=model
 save(out/'OOF_ROWS.json',results);save(out/'USE_LEDGER.json',usage);save(out/'FINAL_MODELS.json',models);ledger.close()
 summary=[]
 for target,mode in [('AP','SIGNED_DYNAMIC'),('POWER_API','LOG_CORE9'),('POWER_API','LOG_DYNAMIC')]:
  for pool in ('ALL','OLD','M8','R21'):
   a=[r for r in results if r['target']==target and r['mode']==mode and (pool=='ALL' or r['pool']==pool or pool=='R21' and r['group'].startswith('M8_R21_'))];summary.append(dict(target=target,mode=mode,pool=pool,sessions=len(a),session_MAE=statistics.mean(r['MAE'] for r in a) if a else None,session_bias=statistics.mean(r['bias'] for r in a) if a else None))
 save(out/'REPAIR_RESULT.json',dict(status='PASS',meaning='DEVELOPMENT_REPAIR_FITS_COMPLETED_NOT_ADOPTED_OR_INDEPENDENTLY_VALIDATED',sessions=228,fits=fits,summary=summary,new_policy_environments=0,new_NN=0,primary_power_candidate='LOG_DYNAMIC fixed before fitting this lineage',primary_AP_candidate='SIGNED_DYNAMIC, not automatically replacing frozen AP',role='R21 was observed to diagnose parent failure; all R21-based fit/OOF is development. Original R21 heldout failure preserved.',negative_components='Signed effects under positive exp power, learned not hand chosen; observational interactions not identified hardware powers.'))
if __name__=='__main__':main(read(os.environ['S26_UNIFIED_OPERATION']))
