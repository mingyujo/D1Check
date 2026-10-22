"""Continue only unstarted work from original target source and saved checkpoints.

The target path is a real positional argument and remains the scientific source.
Only manager initialization, acknowledged identical checkpoints and skip-completed
bookkeeping change. No simulate/physics/policy/learner source is edited.
"""
import datetime,difflib,gzip,hashlib,json,msvcrt,os,sys,time,traceback
from pathlib import Path
for key in('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[key]='1'
WORK=Path(__file__).resolve().parent.parent;TARGET=Path(sys.argv[1]).resolve();H=TARGET.parent;OUT=H/'artifacts/G001';sys.path.insert(0,str(H))
from s26_resources_v2 import wait_ready
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,x):
 with Path(p).open('x',encoding='utf-8')as f:json.dump(x,f,ensure_ascii=False,allow_nan=False,indent=2)
def transformed(source):
 s=source.split("if __name__=='__main__':")[0];s=s.replace('count=0;rows=[]','count=resume_count;rows=resume_rows.copy()').replace('nets={};updates=[]','nets={};updates=resume_updates.copy()').replace("out/'ENGINE_STDERR.txt'","out/'ENGINE_STDERR_RESUME_V2.txt'")
 s=s.replace(' def pt(p,x):\n  b=io.BytesIO();torch.save(x,b)',' def pt(p,x):\n  if Path(p).exists():resume_same(load(p),x);return\n  b=io.BytesIO();torch.save(x,b)')
 anchor='    learner=Learner(seed);learner.net.load_state_dict(snapshot[\'network\']);';line=next(x for x in s.splitlines()if x.startswith(anchor));new=line+"\n    completed=resume_completed.get((variant,seed),[])\n    if completed:learner.restore(load(out/f'{variant}_S{seed}_EP{max(completed):03d}_after.pt.gz'))"
 s=s.replace(line,new).replace("    for ep,j in enumerate(order,1):\n", "    for ep,j in enumerate(order,1):\n     if ep in resume_completed.get((variant,seed),[]):continue\n")
 if 'count=resume_count'not in s or 'if ep in resume_completed'not in s:raise ValueError('Manager transform missing')
 return s
def main():
 op=read(H/'OPERATION.json');control=read(H/'OPERATION_RESOURCE_RESUME_V2.json');assert control['original_run_sha256']==sha(TARGET)
 for p in control['pins']:assert sha(p['path'])==p['sha256']
 receipts=[json.loads(x)for x in(OUT/'receipts.jsonl').read_text(encoding='utf-8').splitlines()if x];starts=[x for x in receipts if x['event']=='START'];complete=[x for x in receipts if x['event']=='COMPLETE'];assert len(starts)==len(complete)==control['prior_START']and not any(x['event']=='FAIL'for x in receipts)
 lock=Path(op['shared_mutex']).open('r+b');locked=False
 try:
  lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True;resource=wait_ready();import numpy as np,torch
  def same(a,b):
   if torch.is_tensor(a):assert torch.equal(a,b),'Resume checkpoint tensor'
   elif isinstance(a,np.ndarray):assert np.array_equal(a,b),'Resume checkpoint array'
   elif isinstance(a,dict):
    assert a.keys()==b.keys()
    for k in a:same(a[k],b[k])
   elif isinstance(a,(list,tuple)):
    assert len(a)==len(b)
    for x,y in zip(a,b):same(x,y)
   else:assert a==b,'Resume checkpoint scalar'
  def load(p):return torch.load(__import__('io').BytesIO(gzip.decompress(Path(p).read_bytes())),map_location='cpu',weights_only=False)
  rows=[read(OUT/(r['label']+'.json'))for r in complete];done={};updates=[]
  for row in rows:
   if row['kind']!='TRAIN':raise ValueError('This registered resume point is training-only')
   ep=int(row['label'].rsplit('EP',1)[1]);done.setdefault((row['variant'],row['seed']),[]).append(ep);prefix=f'{row["variant"]}_S{row["seed"]}_EP{ep:03d}';before=load(OUT/(prefix+'_before.pt.gz'));after=load(OUT/(prefix+'_after.pt.gz'))
   if after['updates']>before['updates']:updates.append(dict(variant=row['variant'],seed=row['seed'],episode=ep,update=after['updates'],before=before['network_sha256'],after=after['network_sha256']))
  source=TARGET.read_text(encoding='utf-8-sig');code=transformed(source);assert hashlib.sha256(code.encode()).hexdigest()==control['transformed_source_sha256'];namespace=dict(__file__=str(TARGET),__name__='s26_registered_checkpoint_resume',resume_count=len(starts),resume_rows=rows,resume_updates=updates,resume_completed=done,resume_same=same);exec(compile(code,str(TARGET)+'[registered-manager-resume-v2]','exec'),namespace);namespace['wait_ready']=wait_ready;original_save=namespace['save']
  def acknowledged_save(p,x):
   if Path(p).exists()and Path(p).name.endswith('_CASE_ORDER.json'):same(read(p),x);return
   return original_save(p,x)
  namespace['save']=acknowledged_save;combined={**op,'pins':op['pins']+control['pins'],'wall_cap_s':control['remaining_wall_cap_s']};save(OUT/'RESUME_START_V2.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),pid=os.getpid(),prior_START=len(starts),prior_COMPLETE=len(complete),new_unstarted=512-len(starts),original_operation_sha256=sha(H/'OPERATION.json'),resume_operation_sha256=sha(H/'OPERATION_RESOURCE_RESUME_V2.json'),resource=resource,source_manager_only=True,policy_physics_learner_inputs_unchanged=True));namespace['main'](combined,OUT)
  for p in control['pins']:assert sha(p['path'])==p['sha256']
 except BaseException:
  save(OUT/'RESUME_FAILURE_V2.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),traceback=traceback.format_exc(),automatic_retry=False));raise
 finally:
  if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
  lock.close()
if __name__=='__main__':main()
