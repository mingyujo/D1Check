"""Read-only diagnosis of saved runs. No environment, fitting or policy update."""
import datetime,gc,gzip,hashlib,io,json,math,msvcrt,os,shutil,subprocess,time,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
def read(p):
 p=Path(p);return json.loads((gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes()).decode('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
 with Path(p).open('x',encoding='utf-8')as f:json.dump(x,f,ensure_ascii=False,allow_nan=False,indent=2)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def main(op,out):
 import numpy as np,torch
 torch.set_num_threads(1);begin=time.monotonic()
 def q(a,p):return float(np.quantile(a,p)) if a else None
 def stats(a):return dict(n=len(a),mean=float(np.mean(a)) if a else None,p50=q(a,.5),p95=q(a,.95),max=max(a) if a else None)
 def pt(p):return torch.load(io.BytesIO(gzip.decompress(Path(p).read_bytes())),map_location='cpu',weights_only=False)
 final=read(ROOT/'experiments/a24_static_controls_v1/artifacts/G001/COMPARISON_SUMMARY.json');rows=[];frame_groups=[]
 for i,row in enumerate(final['rows']):
  O=ROOT/('experiments/a24_load_margin_v1/artifacts/G001' if row['label'].startswith('MARGIN_') else 'experiments/a24_static_controls_v1/artifacts/G001');raw=read(O/(row['label']+'.raw.json.gz'));ready={x['ordinal']:x['readyAt']for x in raw['planned_requests']};by={x['ordinal']:x for x in raw['requests']};grants={};wall={}
  for x in raw['cpu_intervals']:grants.setdefault((x['ordinal'],x['phase']),[]).append(x)
  for x in raw['phase_trace']:
   if x['event']=='ENTER':wall[(x['ordinal'],x['phase'])]=x
  groups={}
  for priority in ('urgent','normal'):
   qs=[x for x in raw['requests']if x['priority']==priority];queue=[];admit=[];post=[];infer=[];detect_block=[]
   for x in qs:
    if x['times'] is None:continue
    t=x['times'];queue.append(t['dispatch']-ready[x['ordinal']]);admit.append(max(0.,t['host_inference_start']-t['execution_start']-wall[(x['ordinal'],'ADMISSION')]['wall_duration_s']))
    post.append(max(0.,x['available']-t['output_ready']-wall[(x['ordinal'],'POST')]['wall_duration_s']))
    if x['route'].endswith('CPU'):infer.append(max(0.,t['host_inference_return']-t['host_inference_start']-sum(v['end']-v['start']for v in grants.get((x['ordinal'],'INFER'),[]))))
    ad=grants.get((x['ordinal'],'ADMISSION'),[]);end=ad[-1]['end']if ad else t['execution_start'];detect_block.append(sum(max(0.,min(end,v['end'])-max(t['execution_start'],v['start']))for v in raw['cpu_intervals']if v['route']=='detection_CPU'and v['phase']=='INFER'))
   groups[priority]=dict(queue_s=stats(queue),admission_CPU_wait_s=stats(admit),post_CPU_wait_s=stats(post),CPU_infer_wait_s=stats(infer),detection_infer_block_before_admission_CPU_completion_s=stats(detect_block))
  detail=dict(input=row['input'],policy=row['policy_name'],load=row['nominal_load_ratio'],mix=row['mix'],service=row['service'],routes=row['routes'],API_J=row['full_API_J'],mean_AP=row['AP_mean'],peak_AP=row['AP_peak'],max_ready_queue=raw['max_ready_queue'],shared_CPU_wait_sum_s=raw['shared_cpu_wait_s'],groups=groups);rows.append(detail)
  if row['policy']=='RL':
   data=pt(O/(row['label']+'.frames.pt.gz'));errors=[];under=[];coverage=[];choice_prob=[];minimum_score=wait_cheaper=hidden_savable=frames_with_hidden=chosen_forecast_late=0;Xs=[]
   for f,d in zip(data['frames'],raw['policy_decisions']):
    actions=f['candidate_actions'];mask=f['mask'];ix=f['index'];scores=np.asarray(f['scores']);valid=np.flatnonzero(mask);coverage.append(f['forecast_ready']/max(1,f['ready_total']));choice_prob.append(math.exp(f['old_logp']));minimum_score+=int(ix==int(valid[np.argmin(scores[valid])]))
    wait=[j for j,a in enumerate(actions)if a['kind']=='WAIT'];dispatch=[j for j,a in enumerate(actions)if a['kind']=='DISPATCH'];wait_cheaper+=int(bool(wait)and min(scores[wait])<min(scores[dispatch]));chosen=f['nominal_forecasts'][ix];actual=by[f['action']['ordinal']]['response'];pred=chosen['candidate_response']
    if pred is not None and actual is not None:errors.append(pred-actual);under.append(max(0.,actual-pred));chosen_forecast_late+=int(pred>by[f['action']['ordinal']]['deadline'])
    public=d['public_observation'];candidates={a['ordinal']for a in actions if a['kind']=='DISPATCH'};hidden=[x for x in public['ready']if x['ordinal']not in candidates];frames_with_hidden+=int(bool(hidden));hidden_savable+=int(any(x['priority']=='normal'and x['deadline']-public['time']>.2264312379001616 for x in hidden)and not any(x['ordinal']in candidates and x['priority']=='normal'and x['deadline']-public['time']>.2264312379001616 for x in public['ready']))
    Xs.append(f['x'][mask])
   xx=np.concatenate(Xs);np.savez_compressed(out/(row['label']+'.feature_stats.npz'),minimum=xx.min(0),maximum=xx.max(0),mean=xx.mean(0),count=len(xx));frame_groups.append(dict(input=row['input'],policy=row['policy_name'],load=row['nominal_load_ratio'],frames=len(data['frames']),coverage=stats(coverage),chosen_argmax_probability=stats(choice_prob),chosen_minimum_forecast_score=minimum_score,WAIT_strictly_cheaper_forecast_frames=wait_cheaper,frames_with_hidden_requests=frames_with_hidden,frames_with_only_hidden_potentially_timely_normal=hidden_savable,nominal_first_response_error_s=stats(errors),nominal_first_response_underestimate_s=stats(under),chosen_nominal_late=chosen_forecast_late))
   del data,Xs,xx;gc.collect()
  del raw;gc.collect()
  if(i+1)%16==0:print('SAVED_DIAGNOSIS',i+1,flush=True)
 parent=ROOT/'experiments/a24_unprotected_v3/artifacts/G001';training=read(parent/'RESULT.json')['rows'];train_min=np.full(32,np.inf);train_max=np.full(32,-np.inf);train_frames=train_actions=0;diagnostics=[]
 for r in training:
  if r['kind']!='TRAIN':continue
  data=pt(parent/(r['label']+'.frames.pt.gz'));xx=np.concatenate([f['x'][f['mask']]for f in data['frames']]);train_min=np.minimum(train_min,xx.min(0));train_max=np.maximum(train_max,xx.max(0));train_frames+=len(data['frames']);train_actions+=len(xx);del data,xx
 for g in frame_groups:
  a=np.load(out/(next(r['label']for r in final['rows']if r['input']==g['input']and r['policy_name']==g['policy'])+'.feature_stats.npz'));diagnostics.append(dict(input=g['input'],policy=g['policy'],features_outside_training_envelope=np.flatnonzero((a['minimum']<train_min-1e-6)|(a['maximum']>train_max+1e-6)).tolist()))
 physical={}
 for name in ('capacity_power_v1','pipeline_thermal_v1'):
  result=read(ROOT/f'experiments/{name}/artifacts/G001/RESULT.json');physical[name]=result
 result=dict(status='SAVED_MULTIFACTOR_DIAGNOSIS_COMPLETE',utc=now(),rows=rows,neural_decision_diagnostics=frame_groups,training_feature_envelope=dict(frames=train_frames,valid_action_rows=train_actions,minimum=train_min.tolist(),maximum=train_max.tolist(),evaluation_outside=diagnostics),physical_validation_history=physical,limitations=['First-action nominal error includes later online recourse and future arrivals; not an isolated forecast calibration test.','Potentially timely normal uses optimistic C0 duration only; not a deadline-feasibility guarantee.','Admission wait subtracts frozen phase wall duration; independent CPU grant overlap is separately reported.'],new_environment=0,new_training=0,new_physical_fit=0,elapsed_s=time.monotonic()-begin)
 for p in op['pins']:assert sha(p['path'])==p['sha256'],'Changed diagnostic input'
 save(out/'RESULT.json',result);save(out/'COMPLETE.json',dict(utc=now(),status=result['status'],result_sha256=sha(out/'RESULT.json'),new_environment=0,new_training=0));print(result['status'],round(result['elapsed_s'],2),flush=True)
if __name__=='__main__':
 op=read(HERE/'OPERATION.json');out=HERE/'artifacts/G001';assert not out.exists();lock=Path(op['shared_mutex']).open('r+b');locked=False
 try:
  lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
  ps=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command','Get-CimInstance Win32_Process -Filter "Name = \'python.exe\'" | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress'],text=True)or'[]');ps=[ps]if isinstance(ps,dict)else ps;assert len(ps)<=2 and not any(p['ProcessId']!=os.getpid()and any(s in(p.get('CommandLine')or'')for s in('a24_simulator','s26_simulator'))for p in ps)
  assert shutil.disk_usage(HERE).free>=8*1024**3;out.mkdir(parents=True);save(out/'START.json',dict(utc=now(),pid=os.getpid(),operation_sha256=sha(HERE/'OPERATION.json')))
  try:main(op,out)
  except BaseException:save(out/'FAILURE.json',dict(utc=now(),traceback=traceback.format_exc(),new_environment=0));raise
 finally:
  if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
  lock.close()
