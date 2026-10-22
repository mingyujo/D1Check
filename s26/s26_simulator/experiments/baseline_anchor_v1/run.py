"""One existing-data physical repair: idle prediction equals observed baseline.
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
 def fit_anchor(X,y,w):
  A=X[:,2:];res=y-X[:,1];scale=np.maximum(np.sqrt(np.sum(w[:,None]*A**2,axis=0)),1e-6);Z=A/scale;H=Z.T@(w[:,None]*Z)+np.eye(20)/22;b=Z.T@(w*res);c=np.maximum(0,np.linalg.solve(H,b))
  for iteration in range(20000):
   old=c.copy()
   for j in range(len(c)):c[j]=max(0,c[j]+(b[j]-H[j]@c)/H[j,j])
   if max(abs(c-old))<1e-11:
    grad=H@c-b;free=c>1e-9;kkt=max(float(max(abs(grad[free])))if any(free)else 0.,float(max(0.,-min(grad))));assert kkt<1e-7
    return dict(mode='OBSERVED_IDLE_BASELINE_PLUS_NONNEGATIVE_ACTIVITY',coef=[0.,1.]+c.tolist(),scale=[1.,1.]+scale.tolist(),ridge=1.,iterations=iteration+1,KKT=kkt,core_utilization_identified=False,absolute_W_verified=False,idle_baseline_identity=True)
  save(out/'FAILED_POWER_PARAMETERS.json',dict(coef=c.tolist(),scale=scale.tolist(),iterations=20000));raise ValueError('Anchored coordinate fit nonconvergence; no retry')
 power.P.fit=fit_anchor;po=read(HERE/'POWER_OPERATION.json');Path(po['output']).mkdir();(Path(po['output'])/'models').mkdir();power.main(po)
 old=read(ROOT/'experiments/pipeline_thermal_v1/OPERATION.json');old['schema']='BASELINE_ANCHOR_PASSIVE_THERMAL_V1';old['output']=str(out/'THERMAL');old['source']=[dict(path=str(p),sha256=sha(p))for p in[Path(__file__),WORK/'recovery/s26_resources.py',ROOT/'experiments/pipeline_thermal_v1/run.py',ROOT/'experiments/pipeline_thermal_v1/basis.py',ROOT/'experiments/thermal_balance_v2/run.py',ROOT/'experiments/capacity_power_v1/power.py']];old['inputs']['previous_conditional']=dict(path=str(out/'POWER/CONDITIONAL_AP_ROWS.json.gz'),sha256=sha(out/'POWER/CONDITIONAL_AP_ROWS.json.gz'));old['power_models']={g:dict(path=str(out/'POWER/models'/(g+'.json')),sha256=sha(out/'POWER/models'/(g+'.json')))for g in old['power_models']};save(HERE/'THERMAL_OPERATION.json',old);Path(old['output']).mkdir();(Path(old['output'])/'models').mkdir()
 sys.path.insert(0,str(ROOT/'experiments/pipeline_thermal_v1'));thermal=load('anchor_parent_thermal_run',ROOT/'experiments/pipeline_thermal_v1/run.py');thermal.main(old)
 pr=read(out/'POWER/RESULT.json');tr=read(out/'THERMAL/RESULT.json');pg=all(r['MAE_API_W']<=r['parent_MAE_API_W']and r['median_abs_relative_J_error']<=r['parent_median_abs_relative_J_error']for r in pr['power_summary']);tg=all(r['pipeline_MAE_C']<=r['parent_MAE_C']for r in tr['summary'])
 for x in op['pins']:assert sha(x['path'])==x['sha256']
 result=dict(status='BASELINE_IDENTITY_REPAIR_EVALUATED',fit_START=pr['fit_START']+tr['fit_START'],fit_COMPLETE=pr['fit_COMPLETE']+tr['fit_COMPLETE'],fit_FAIL=pr['fit_FAIL']+tr['fit_FAIL'],power_gate_pass=pg,thermal_gate_pass=tg,all_accuracy_gates_pass=pg and tg,power_summary=pr['power_summary'],thermal_summary=tr['summary'],elapsed_s=time.monotonic()-started,adopted=False,physical_constants_identified=False,new_environment=0,new_measurements=0,new_RL=0,scope='Development group-out validation on previously seen existing data; no new independent final validation; policy repair study keeps prior frozen models regardless of this result.');save(out/'RESULT.json',result);save(out/'FINAL_PROOF.json',dict(status='COMPLETED_EXISTING_DATA_BASELINE_IDENTITY_TEST',result_sha256=sha(out/'RESULT.json'),operation_sha256=sha(HERE/'OPERATION.json'),physical_validation=False,adopted=False));print(json.dumps(result),flush=True)
if __name__=='__main__':
 op=read(HERE/'OPERATION.json');out=HERE/'artifacts/G001';assert not out.exists();lock=Path(op['shared_mutex']).open('r+b');locked=False
 try:
  lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True;resource=wait_ready();out.mkdir(parents=True);save(out/'START.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),pid=os.getpid(),resource=resource))
  try:main(op,out)
  except BaseException:save(out/'FAILURE.json',dict(traceback=traceback.format_exc(),automatic_retry=False));raise
 finally:
  if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
  lock.close()
