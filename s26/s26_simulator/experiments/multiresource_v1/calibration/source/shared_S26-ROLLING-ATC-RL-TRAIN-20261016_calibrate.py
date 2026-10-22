"""Registered measurement-only calibration, not a policy environment or RL training.
Fixed ridge1; positive additive power and nonnegative activity heating coefficients.
All initial-history nuisance effects remain signed, and all measurements keep their eligibility.
"""
import ast,datetime,hashlib,importlib.util,json,math,msvcrt,os,shutil,sys,traceback
from pathlib import Path
import numpy as np
from repair_dynamic_cost_v2 import load_old,materialize
W=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
 with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,allow_nan=False);f.flush();os.fsync(f.fileno())
def features(ep,target,old):
 ts=ep['times'];segments=ep['segments'];start=ep['history_start_s']
 if target=='POWER_API':
  cols=[np.ones(len(ts)),np.full(len(ts),ep['baseline_api_w'])];labels=['intercept','past_baseline_API_W']
  cols.extend(old.windowed_activity(x,ts,.5,start) for x in segments);labels.extend('box05:'+str(j) for j in range(9))
  for tau in (1,10,60):cols.extend(old.filtered_activity(x,ts,1/tau,start) for x in segments);labels.extend('tail'+str(tau)+':'+str(j) for j in range(9))
  return np.column_stack(cols),labels,38
 cols=[];labels=[]
 for tau in (1/.06,60):
  for j,x in enumerate(segments):cols.append(old.filtered_activity(x,ts,1/tau,start)-old.filtered_activity(x,np.array([ep['anchor_s']]),1/tau,start)[0]);labels.append('APtau'+str(tau)+':'+str(j))
 for tau in (20,120):
  z=-np.expm1(-(ts-ep['anchor_s'])/tau)
  for j,v in enumerate(np.r_[1,ep['history']]):cols.append(z*v);labels.append('initial_history'+str(tau)+':'+str(j))
 return np.column_stack(cols),labels,18
def constrained_ridge(X,y,w,scale,positive,ridge):
 Z=X/scale;H=Z.T@(w[:,None]*Z)+(ridge/X.shape[1])*np.eye(X.shape[1]);b=Z.T@(w*y);c=np.linalg.solve(H,b);c[:positive]=np.maximum(0,c[:positive])
 for iteration in range(20000):
  before=c.copy()
  for j in range(len(c)):
   value=c[j]+(b[j]-H[j]@c)/H[j,j];c[j]=max(0,value) if j<positive else value
  if np.max(np.abs(c-before))<1e-11:
   gradient=H@c-b;free=np.r_[c[:positive]>1e-9,np.ones(len(c)-positive,dtype=bool)];error=max(float(np.max(abs(gradient[free]))) if np.any(free) else 0,float(max(0,-min(gradient[:positive]))));assert error<1e-7,'KKT residual';return c,iteration+1,error
 raise ValueError('Coordinate descent did not converge; preserve incomplete fit')
def main(op_path):
 op=read(op_path);spec=importlib.util.spec_from_file_location('shared_owner',Path(op['owner_source']));owner=importlib.util.module_from_spec(spec);spec.loader.exec_module(owner);owner.verify(op);census=owner.Census();handle=None;locked=False;out=Path(op['output_dir']);fits=0
 try:
  own=census.get();
  for drive in op['volumes']:assert shutil.disk_usage(drive).free>=8589934592,'8GiB guard'
  for f in W.glob('*.py'):ast.parse(f.read_text(encoding='utf-8-sig'),filename=str(f))
  handle=Path(op['shared_byte_mutex']['path']).open('r+b');handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1);locked=True;out.mkdir();save(out/'OWNER.json',own['self']);old=load_old(op['old_math_source']);sessions=materialize(op,old);r21={s['session_id']:s for s in read(op['r21_sessions_path'])};usage=[];entries={};models={};rows=[]
  save(out/'MATERIALIZED_SESSIONS.json',sessions)
  for target in ('AP','POWER_API'):
   entries[target]=[]
   for s in sessions:
    try:
     if target=='POWER_API' and s['id'] in r21 and not r21[s['id']]['energy_eligible']:raise ValueError('R21 registered unit-ratio ineligible; do not promote missing J')
     ep=old.prepare_session(s,target)
     if not old.activity_available(ep,9):raise ValueError('Unknown9-channel activity/horizon')
     if target=='POWER_API':
      mask=ep['observed']>0;ep['times']=ep['times'][mask];ep['observed']=ep['observed'][mask]
      if len(ep['observed'])<3:raise ValueError('Insufficient positive API W')
     X,labels,positive=features(ep,target,old);y=ep['observed'] if target=='POWER_API' else ep['observed']-ep['anchor_AP_c'];entries[target].append((ep,X,y,labels,positive));usage.append(dict(id=ep['id'],target=target,status='INCLUDED',pool=ep['source_pool'],group=ep['cv_group'],points=len(y),actual_window_s=ep['actual_window_s']))
    except ValueError as e:usage.append(dict(id=old.uid(s),target=target,status='EXCLUDED',reason=str(e)))
  save(out/'USE_LEDGER.json',usage)
  for target in ('AP','POWER_API'):
   es=entries[target];groups=sorted({e[0]['cv_group'] for e in es});assert len(groups)>=3
   for group in groups+[None]:
    owner.verify(op);census.get();
    for drive in op['volumes']:assert shutil.disk_usage(drive).free>=8589934592,'8GiB guard'
    identity=target+'_'+(group or 'FULL');assert fits<op['fit_cap'];owner.append(out/'FIT_RECEIPTS.jsonl',dict(event='START',id=identity));fits+=1
    train=[e for e in es if group is None or e[0]['cv_group']!=group];tests=[e for e in es if e[0]['cv_group']==group] if group else [];sw=old.session_weights([e[0] for e in train]);X=np.vstack([e[1] for e in train]);y=np.concatenate([e[2] for e in train]);w=np.concatenate([np.full(len(e[2]),sw[i]/len(e[2])) for i,e in enumerate(train)]);w/=w.sum();scale=np.maximum(np.sqrt(np.sum(w[:,None]*X**2,axis=0)),1e-6);scale[0]=1 if target=='POWER_API' else scale[0]
    c,iterations,kkt=constrained_ridge(X,y,w,scale,es[0][4],1);model=dict(target=target,mode='POSITIVE_ADDITIVE' if target=='POWER_API' else 'POSITIVE_ACTIVITY_DYNAMIC',labels=es[0][3],mean=[0]*len(c),scale=scale.tolist(),coef=c.tolist(),positive_coefficients=es[0][4],ridge=1,iterations=iterations,KKT_residual=kkt,training_ids=[e[0]['id'] for e in train],training_groups=sorted({e[0]['cv_group'] for e in train}),scope='All-seen development including previously observed R21; group OOF only, not fresh phone accuracy',power_link='Positive additive in API units' if target=='POWER_API' else None,initial_AP_anchor_preserved=target=='AP',hardware_components_identified=False)
    save(out/(identity+'.json'),model)
    for ep,Xt,yt,_,_ in tests:
     pred=Xt/scale@c+(ep['anchor_AP_c'] if target=='AP' else 0);assert np.isfinite(pred).all();
     if target=='POWER_API':assert np.min(pred)>0
     obs=ep['observed'];areaP=float(np.trapezoid(pred,ep['times']));areaY=float(np.trapezoid(obs,ep['times']));rows.append(dict(id=ep['id'],group=group,pool=ep['source_pool'],target=target,MAE=float(np.mean(abs(pred-obs))),bias=float(np.mean(pred-obs)),predicted_area=areaP,observed_area=areaY,relative_area_error=(areaP-areaY)/areaY if target=='POWER_API' else None,points=len(pred),times=ep['times'].tolist(),observed=obs.tolist(),predicted=pred.tolist(),training_model=identity))
    owner.append(out/'FIT_RECEIPTS.jsonl',dict(event='COMPLETE',id=identity,model_sha256=sha(out/(identity+'.json')),train_sessions=len(train),heldout_sessions=len(tests),KKT_residual=kkt))
    if group is None:models[target]=model
    print(json.dumps(dict(fits=fits,id=identity,iterations=iterations)),flush=True)
  save(out/'FINAL_MODELS.json',models);save(out/'OOF_ROWS.json',rows);summary=[]
  for target in ('AP','POWER_API'):
   for pool in ('ALL','OLD','M8','R21'):
    rs=[r for r in rows if r['target']==target and (pool=='ALL' or r['pool']==pool or pool=='R21' and r['group'].startswith('M8_R21_'))];summary.append(dict(target=target,pool=pool,sessions=len(rs),session_MAE=float(np.mean([r['MAE'] for r in rs])) if rs else None,session_bias=float(np.mean([r['bias'] for r in rs])) if rs else None,median_abs_relative_area_error=float(np.median([abs(r['relative_area_error']) for r in rs])) if target=='POWER_API' and rs else None))
  owner.verify(op);save(out/'RESULT.json',dict(status='CALIBRATION_COMPLETED_PENDING_INDEPENDENT_AUDIT',sessions_inventory=len(sessions),included={t:len(es) for t,es in entries.items()},fits=fits,summary=summary,new_policy_environments=0,new_RL=0,new_measurements=0,component_identifiability='Nonnegative associative model, not identified per-chip hardware power or causal heating',scope='No synthetic policy outcomes used as fit targets; fixed ridge1 and architecture registered before fitting; all OOF are developmental'))
 except BaseException:
  if out.exists():save(out/'FAILURE.json',dict(status='FAILED_PRESERVED',fits=fits,traceback=traceback.format_exc()))
  raise
 finally:
  if handle:
   if locked:handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
   handle.close()
  census.close()
if __name__=='__main__':main(Path(sys.argv[1]))
