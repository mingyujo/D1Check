"""New positive conditional-mean power model. Gamma log-link deviance avoids
confusing exp(E[log W]) with E[W]. Physical units are unchanged.
"""
import collections,hashlib,json,math,os,statistics
from pathlib import Path
import numpy as np
from timing_model import read,save
from repair_dynamic_cost_v2 import load_old,materialize,features

def history(session):
 a=session.get('targets',{}).get('AP',{}).get('anchor') or {};v=[a.get('AP_c',a.get('AP')),a.get('SKIN_c',a.get('SKIN')),a.get('BAT_c',a.get('BAT')),a.get('pre20_AP_slope_c_s',a.get('pre20_AP_slope'))]
 known=all(isinstance(x,(int,float)) and math.isfinite(x) for x in v) and a.get('available_upper_s',a.get('completion_upper_s',1))<=0
 return v+[0.] if known else [0.,0.,0.,0.,1.]
def objective(c,X,y,w,penalty):
 eta=X@c
 if not np.isfinite(eta).all() or max(abs(eta))>600:return math.inf
 return float(np.sum(w*(y*np.exp(-eta)+eta))+.5*penalty*(c@c))
def gamma_fit(X,y,w,penalty):
 c=np.linalg.solve(X.T@(w[:,None]*X)+penalty*np.eye(X.shape[1]),X.T@(w*np.log(y)))
 for iteration in range(80):
  ratio=y*np.exp(-(X@c));g=X.T@(w*(1-ratio))+penalty*c;H=X.T@((w*ratio)[:,None]*X)+penalty*np.eye(X.shape[1]);step=np.linalg.solve(H,g);v=objective(c,X,y,w,penalty);scale=1.
  while scale>1e-8 and objective(c-scale*step,X,y,w,penalty)>v+1e-12:scale/=2
  if scale<=1e-8:raise ValueError('Gamma line search failed, preserve')
  c=c-scale*step
  if np.max(abs(scale*step))<1e-9:return c,iteration+1
 raise ValueError('Gamma nonconvergence, preserve')
def main(op):
 out=Path(op['output_dir']);out.mkdir();old=load_old(op['old_math_source']);ss=materialize(op,old);by={old.uid(s):s for s in ss};eps=[];excluded=[]
 for s in ss:
  try:
   ep=old.prepare_session(s,'POWER_API')
   if not old.activity_available(ep,9):raise ValueError('Unknown activity/horizon')
   mask=ep['observed']>0;ep['times']=ep['times'][mask];ep['observed']=ep['observed'][mask]
   if len(ep['observed'])<3:raise ValueError('Insufficient positive raw API W')
   eps.append(ep)
  except ValueError as e:excluded.append({'id':old.uid(s),'reason':str(e)})
 receipt=(out/'FIT_RECEIPTS.jsonl').open('x',encoding='utf-8');fits=0;rows=[];full={}
 def record(x):receipt.write(json.dumps(x)+'\n');receipt.flush();os.fsync(receipt.fileno())
 # Numerical score/Hessian check is a pure derivative calculation, not a fit.
 X=np.array([[1.,.2],[1.,-.3],[1.,.7]]);c=np.array([.2,-.1]);y=np.array([1.,2.,4.]);w=np.array([.2,.3,.5]);penalty=.1;g=X.T@(w*(1-y*np.exp(-(X@c))))+penalty*c
 for j in range(2):
  d=np.zeros(2);d[j]=1e-5;assert abs((objective(c+d,X,y,w,penalty)-objective(c-d,X,y,w,penalty))/2e-5-g[j])<1e-8
 save(out/'GAMMA_DERIVATIVE_TEST.json',{'status':'PASS','checks':2,'new_fit':0})
 for mode in ('GAMMA_DYNAMIC','GAMMA_HISTORY'):
  entries=[]
  for ep in eps:
   X,labels=features(ep,'POWER_API','LOG_DYNAMIC',old)
   if mode=='GAMMA_HISTORY':X=np.column_stack([X,np.tile(history(by[ep['id']]),(len(X),1))]);labels=labels+['initial_AP','initial_SKIN','initial_BAT','initial_AP_slope','initial_joint_HAL_missing']
   entries.append((ep,X))
  for group in sorted(set(ep['cv_group'] for ep in eps))+[None]:
   identity='POWER_API_'+mode+'_'+(group or 'FULL');assert fits<op['fit_cap'];record({'id':identity,'event':'START'});fits+=1
   train=[e for e in entries if group is None or e[0]['cv_group']!=group];test=[e for e in entries if e[0]['cv_group']==group] if group else [];sw=old.session_weights([e[0] for e in train]);X=np.vstack([e[1] for e in train]);y=np.concatenate([e[0]['observed'] for e in train]);w=np.concatenate([np.full(len(e[1]),sw[i]/len(e[1])) for i,e in enumerate(train)]);mean=np.sum(w[:,None]*X,axis=0)/sum(w);scale=np.maximum(np.sqrt(np.sum(w[:,None]*(X-mean)**2,axis=0)/sum(w)),1e-6);mean[0]=0;scale[0]=1;Z=(X-mean)/scale;c,n=gamma_fit(Z,y,w,op['ridge']/len(labels));model=dict(target='POWER_API',mode=mode,labels=labels,mean=mean.tolist(),scale=scale.tolist(),coef=c.tolist(),training_ids=[e[0]['id'] for e in train],training_groups=sorted(set(e[0]['cv_group'] for e in train)),scope='SEEN_DEVELOPMENT_AFTER_R21_NEGATIVE_VALIDATION',power_link='Gamma log-link conditional mean, exp positive',ridge=op['ridge'],iterations=n,unknown_joint_HAL='Missing flag plus zero nuisance design entries, never physical0C')
   save(out/(identity+'.json'),model)
   for ep,Xt in test:
    pred=np.exp((Xt-mean)/scale@c);err=pred-ep['observed'];rows.append(dict(id=ep['id'],group=group,pool=ep['source_pool'],target='POWER_API',mode=mode,MAE=float(np.mean(abs(err))),bias=float(np.mean(err)),times=ep['times'].tolist(),observed=ep['observed'].tolist(),predicted=pred.tolist()))
   record({'id':identity,'event':'COMPLETE','iterations':n,'model_sha256':hashlib.sha256((out/(identity+'.json')).read_bytes()).hexdigest()})
   if group is None:full[mode]=model
 receipt.close();save(out/'OOF_ROWS.json',rows);save(out/'FINAL_MODELS.json',full);summary=[]
 for mode in full:
  for pool in ('ALL','OLD','M8','R21'):
   rs=[r for r in rows if r['mode']==mode and(pool=='ALL' or r['pool']==pool or pool=='R21' and r['group'].startswith('M8_R21_'))];summary.append(dict(mode=mode,pool=pool,n=len(rs),MAE=statistics.mean(r['MAE'] for r in rs),bias=statistics.mean(r['bias'] for r in rs)))
 save(out/'RESULT.json',dict(status='PASS',meaning='DEVELOPMENT_FIT_EXECUTED_NOT_ACCEPTANCE',fits=fits,fit_cap=op['fit_cap'],summary=summary,excluded=excluded,inventory=228,new_policy_environments=0,new_NN=0,primary='GAMMA_HISTORY fixed before this fit; signed AP V3 retained as separate candidate',R21_role='Already seen development, not a second independent confirmation'))
if __name__=='__main__':main(read(os.environ['S26_UNIFIED_OPERATION']))
