"""Visible owner for offline assembly/browser QA, no policy/NN/physics environment."""
import importlib.util,json,msvcrt,os,subprocess,sys,time,traceback
from pathlib import Path
opPath=Path(sys.argv[1]);op=json.loads(opPath.read_text(encoding='utf-8-sig'));s=importlib.util.spec_from_file_location('owner',op['owner_source']);owner=importlib.util.module_from_spec(s);s.loader.exec_module(owner);owner.verify(op);census=owner.Census();handle=None;locked=False;runtime=Path(op['runtime_dir']);child=None
try:
 own=census.get();handle=Path(op['shared_byte_mutex']['path']).open('r+b');handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1);locked=True;runtime.mkdir();owner.save(runtime/'OWNER.json',dict(actual=own['self'],operation_sha256=owner.sha(opPath),new_policy_environments=0));child=subprocess.Popen([op['node_path'],op['entry'],str(opPath)],creationflags=subprocess.CREATE_NO_WINDOW,stdout=(runtime/"node.stdout.log").open("w",encoding="utf-8"),stderr=(runtime/"node.stderr.log").open("w",encoding="utf-8"));owner.save(runtime/'NODE_LAUNCH.json',dict(pid=child.pid,parent=os.getpid(),unix=time.time(),entry=op['entry']));code=child.wait();assert code==0,'Node assembly/QA failure preserved';owner.verify(op);owner.save(runtime/'RESULT.json',dict(status='PASS',new_policy_environments=0,new_cost_replay=0,new_fit=0))
except BaseException:
 if runtime.exists():owner.save(runtime/'FAILURE.json',dict(status='FAILED_PRESERVED',traceback=traceback.format_exc()))
 raise
finally:
 if handle:
  if locked:handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
  handle.close()
 census.close()
