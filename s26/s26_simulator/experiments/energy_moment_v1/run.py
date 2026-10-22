"""Second bounded physical repair: match session-integrated energy as well as points.
28 power fits plus56 thermal fits; no new measurements or policy environments.
"""
import datetime,hashlib,importlib.util,json,msvcrt,os,sys,time,traceback
from pathlib import Path
for k in('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];WORK=HERE.parents[3]
sys.path.insert(0,str(WORK/'recovery'));from s26_resources import wait_ready
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
 with Path(p).open('x',encoding='utf-8')as f:json.dump(x,f,ensure_ascii=False,allow_nan=False,indent=2)
def load(name,p):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def main(op,out):
 import numpy as np
 started=time.monotonic();sys.path.insert(0,str(ROOT/'experiments/capacity_power_v1'));sys.path.insert(0,str(ROOT/'experiments/thermal_balance_v1'));power=load('anchor_parent_power_run',ROOT/'experiments/capacity_power_v1/run.py')
 original_fit=power.P.fit;power_op=read(HERE/'POWER_OPERATION.json');old_rows=power.read(power_op['inputs']['old_OOF']['path']);old_rows=[r for r in old_rows if r['target']=='POWER_API'];session_rows=power.read(power_op['inputs']['sessions']['path']);session_by={s.get('session_uid',s['id']):s for s in session_rows};fit_index=0
 def fit_anchor(X,y,w):
  nonlocal fit_index
  group=(power_op['groups']+[None])[fit_index];fit_index+=1;train=[r for r in old_rows if group is None or r['group']!=group];counts={}
  for r in train:
   cohort=session_by[r['id']]['cohort'];counts[cohort]=counts.get(cohort,0)+1
  ex=[];ey=[];ew=[];offset=0
  for r in train:
   times=np.asarray(r['times']);n=len(times);assert np.array_equal(y[offset:offset+n],np.asarray(r['observed']));duration=times[-1]-times[0];assert duration>0
   weights=np.zeros(n);dt=np.diff(times);weights[:-1]+=dt/2;weights[1:]+=dt/2;weights/=duration;ex.append(weights@X[offset:offset+n]);ey.append(float(weights@y[offset:offset+n]));ew.append(1/(len(counts)*counts[session_by[r['id']]['cohort']]));offset+=n
  assert offset==len(y);m=original_fit(np.vstack([X,np.asarray(ex)]),np.r_[y,ey],np.r_[.5*w,.5*np.asarray(ew)]);m.update(mode='CAPACITY_POWER_WITH_SESSION_ENERGY_MOMENT',point_MSE_weight=.5,session_mean_power_MSE_weight=.5,held_group_energy_not_used=True);return m
 power.P.fit=fit_anchor;po=read(HERE/'POWER_OPERATION.json');Path(po['output']).mkdir();(Path(po['output'])/'models').mkdir();power.main(po)
 old=read(ROOT/'experiments/pipeline_thermal_v1/OPERATION.json');old['schema']='ENERGY_MOMENT_PASSIVE_THERMAL_V1';old['output']=str(out/'THERMAL');old['source']=[dict(path=str(p),sha256=sha(p))for p in[Path(__file__),WORK/'recovery/s26_resources.py',ROOT/'experiments/pipeline_thermal_v1/run.py',ROOT/'experiments/pipeline_thermal_v1/basis.py',ROOT/'experiments/thermal_balance_v2/run.py',ROOT/'experiments/capacity_power_v1/power.py']];old['inputs']['previous_conditional']=dict(path=str(out/'POWER/CONDITIONAL_AP_ROWS.json.gz'),sha256=sha(out/'POWER/CONDITIONAL_AP_ROWS.json.gz'));old['power_models']={g:dict(path=str(out/'POWER/models'/(g+'.json')),sha256=sha(out/'POWER/models'/(g+'.json')))for g in old['power_models']};save(HERE/'THERMAL_OPERATION.json',old);Path(old['output']).mkdir();(Path(old['output'])/'models').mkdir()
 sys.path.insert(0,str(ROOT/'experiments/pipeline_thermal_v1'));thermal=load('anchor_parent_thermal_run',ROOT/'experiments/pipeline_thermal_v1/run.py');thermal.main(old)
 pr=read(out/'POWER/RESULT.json');tr=read(out/'THERMAL/RESULT.json');pg=all(r['MAE_API_W']<=r['parent_MAE_API_W']and r['median_abs_relative_J_error']<=r['parent_median_abs_relative_J_error']for r in pr['power_summary']);tg=all(r['pipeline_MAE_C']<=r['parent_MAE_C']for r in tr['summary'])
 for x in op['pins']:assert sha(x['path'])==x['sha256']
 result=dict(status='ENERGY_MOMENT_REPAIR_EVALUATED',fit_START=pr['fit_START']+tr['fit_START'],fit_COMPLETE=pr['fit_COMPLETE']+tr['fit_COMPLETE'],fit_FAIL=pr['fit_FAIL']+tr['fit_FAIL'],power_gate_pass=pg,thermal_gate_pass=tg,all_accuracy_gates_pass=pg and tg,power_summary=pr['power_summary'],thermal_summary=tr['summary'],elapsed_s=time.monotonic()-started,adopted=False,physical_constants_identified=False,new_environment=0,new_measurements=0,new_RL=0,scope='Development group-out validation on previously seen existing data; no new independent final validation; policy repair study keeps prior frozen models regardless of this result.');save(out/'RESULT.json',result);save(out/'FINAL_PROOF.json',dict(status='COMPLETED_EXISTING_DATA_SESSION_ENERGY_MOMENT_TEST',result_sha256=sha(out/'RESULT.json'),operation_sha256=sha(HERE/'OPERATION.json'),physical_validation=False,adopted=False));print(json.dumps(result),flush=True)
if __name__=='__main__':
 op=read(HERE/'OPERATION.json');out=HERE/'artifacts/G001';assert not out.exists();lock=Path(op['shared_mutex']).open('r+b');locked=False
 try:
  lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True;resource=wait_ready();out.mkdir(parents=True);save(out/'START.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),pid=os.getpid(),resource=resource))
  try:main(op,out)
  except BaseException:save(out/'FAILURE.json',dict(traceback=traceback.format_exc(),automatic_retry=False));raise
 finally:
  if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
  lock.close()
