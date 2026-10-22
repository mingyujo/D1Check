"""New stable-stage saved checks; no fits or environments."""
import ast,msvcrt,subprocess,sys,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent;entry=Path(sys.argv[1]).resolve();sys.path.insert(0,str(HERE));sys.path.insert(0,str(entry))
from s26_resources_v2 import wait_ready
from run import read,save,sha,now
op=read(entry/'OPERATION.json');out=Path(op['output']);assert(out/'COMPLETE.json').exists()and not(out/'FINAL_PROOF.json').exists()
lock=Path(op['shared_mutex']).open('r+b');locked=False
try:
 lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True;resource=wait_ready()
 for p in(entry/'audit_nn.py',entry/'figure.py'):ast.parse(p.read_text(encoding='utf-8-sig'))
 pins=[Path(__file__),HERE/'s26_resources_v2.py',entry/'audit_nn.py',entry/'audit_saved.cjs',entry/'audit_bank.cjs',entry/'model_family.cjs',entry/'report.cjs',entry/'figure.py',entry/'OPERATION.json',entry/'RESOURCE_MANAGER_V2.json',out/'RESULT.json'];save(entry/'POSTRUN_OPERATION.json',dict(utc=now(),new_environment=0,new_training=0,resource=resource,pins=[dict(path=str(p),sha256=sha(p))for p in pins]))
 try:
  subprocess.run(['node',str(entry/'audit_saved.cjs')],check=True)
  import audit_nn;audit_nn.main(op,out)
  subprocess.run(['node',str(entry/'audit_bank.cjs')],check=True)
  subprocess.run(['node',str(entry/'model_family.cjs')],check=True)
  subprocess.run(['node',str(entry/'report.cjs')],check=True)
  import figure;figure.main(out)
  report=read(out/'REPORT_PROOF.json');fig=read(out/'FIGURE_PROOF.json')
  for p in pins:assert sha(p)==next(x['sha256']for x in read(entry/'POSTRUN_OPERATION.json')['pins']if x['path']==str(p))
  save(out/'FINAL_PROOF.json',dict(status='PASS_CONDITIONAL_STABLE_STAGE_AND_INDEPENDENT_AUDITS',utc=now(),START=256,COMPLETE=256,FAIL=0,report=report['report'],figure=fig,summary_sha256=sha(out/'COMPARISON_SUMMARY.json'),operation_sha256=sha(entry/'OPERATION.json'),PPO_updates=48,new_environment_reexecutions=0,new_measurements=0,new_fit=0,physical_validation=False,adopted=False))
  print('STABLE_STAGE_AUDITS_AND_REPORT_COMPLETE',flush=True)
 except BaseException:save(out/'POSTRUN_FAILURE.json',dict(utc=now(),traceback=traceback.format_exc(),new_environment=0,automatic_retry=False));raise
finally:
 if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
 lock.close()
