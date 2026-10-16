"""Registered visible owner. No numerical imports before guards and shared mutex."""
import ast, datetime, hashlib, importlib.util, json, msvcrt, os
from pathlib import Path
import runpy, shutil, subprocess, sys, time, traceback
W=Path(__file__).resolve().parent
U=Path("C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/work/S26-INTEGRATED-MODEL-20261016/shared_S26-ROLLING-ATC-RL-TRAIN-20261016_forecast_owner.py")
spec=importlib.util.spec_from_file_location('shared_owner_util',U);u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)
sys.path.insert(0,"C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/work/S26-UNIFIED-DYNAMICS-20261016")
def ascii_processes():
    script="Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|pypy|powershell|pwsh' } | Select-Object ProcessId,ParentProcessId,CreationDate,Name,CommandLine | ConvertTo-Json -EscapeHandling EscapeNonAscii -Compress -Depth 3"
    data=subprocess.check_output([str(u.PS),'-NoProfile','-Command',script],timeout=30)
    value=json.loads(data.decode('ascii') or '[]')
    return [value] if isinstance(value,dict) else value
u.processes=ascii_processes

def main():
 op_path=Path(sys.argv[1]).resolve();op=u.read(op_path)
 assert op['schema']=='S26_UNIFIED_STAGE_OPERATION_V1'
 u.verify(op);own=u.guard()
 for drive in op['volumes']:assert shutil.disk_usage(drive).free>=8589934592,'8GiB reserve '+drive
 assert op['source_hashes'].get(str(Path(__file__).resolve()))==u.sha(__file__)
 out=Path(op['runtime_dir']);assert not out.exists(),'Consumed operation runtime; inspect, no automatic retry'
 mutex=op['shared_byte_mutex'];assert u.sha(mutex['path'])==mutex['sha256']
 with open(mutex['path'],'r+b') as handle:
  handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
  try:
   own=u.guard();out.mkdir()
   u.save(out/'WORKER_OWNER.json',dict(pid=os.getpid(),parent_pid=own['ParentProcessId'],creation_date=own['CreationDate'],command_line=own['CommandLine'],operation=str(op_path),operation_sha256=u.sha(op_path),stage=op['stage'],source_sha256=u.sha(__file__)))
   u.save(out/'START.json',dict(stage=op['stage'],unix=time.time(),consumed=True,new_policy_environments=0))
   for p in op['source_hashes']:
    if p.endswith('.py'):ast.parse(Path(p).read_text(encoding='utf-8-sig'))
   if op['stage']=='EXTRACT':
    subprocess.run([str(u.NODE),'--max-old-space-size=2048',op['entry'],str(op_path)],cwd=W,check=True)
   else:
    os.environ['S26_UNIFIED_OPERATION']=str(op_path)
    runpy.run_path(op['entry'],run_name='__main__')
   u.verify(op)
   result=u.read(op['result_path']);assert result['status']=='PASS'
   u.save(out/'FINISHED.json',dict(status='PASS',unix=time.time(),result_path=op['result_path'],result_sha256=u.sha(op['result_path']),new_policy_environments=op.get('new_policy_environments',0)))
  except BaseException:
   if out.exists():u.save(out/'FAILED.json',dict(status='FAILED_PRESERVED_NO_RETRY',unix=time.time(),traceback=traceback.format_exc()))
   raise
  finally:
   handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
 assert u.sha(mutex['path'])==mutex['sha256']
if __name__=='__main__':main()
