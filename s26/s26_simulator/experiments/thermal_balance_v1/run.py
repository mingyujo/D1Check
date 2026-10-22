"""Single Python owner; no other Python child, finite registered fits only."""
import datetime
import json
import msvcrt
import os
import shutil
import subprocess
import traceback
from pathlib import Path
for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):
    os.environ[key] = '1'
from calibrate import main, read, save, verify, sha

HERE = Path(__file__).resolve().parent
op = read(HERE/'OPERATION.json')
verify(op)
out = Path(op['output'])
assert not out.exists(), 'Consumed namespace; no automatic retry'
lock = Path(op['shared_byte_mutex']).open('r+b')
locked = False
try:
    lock.seek(0)
    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    locked = True
    assert shutil.disk_usage(HERE).free >= 8*1024**3
    census = subprocess.run(['powershell','-NoProfile','-Command',
        '[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); Get-CimInstance Win32_Process -Filter "Name = \'python.exe\' OR Name = \'python3.exe\'" | Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress'],
        capture_output=True, text=True, encoding='utf-8', check=True)
    processes = json.loads(census.stdout or '[]')
    if isinstance(processes, dict): processes = [processes]
    pids = {p['ProcessId'] for p in processes}
    parents = {p['ParentProcessId'] for p in processes}
    leaves = pids-parents
    assert len(leaves) <= 2, 'Global Python leaf cap'
    for p in processes:
        cmd = p.get('CommandLine') or ''
        if p['ProcessId'] != os.getpid() and ('a24_simulator' in cmd or 's26_simulator' in cmd):
            raise AssertionError('Other simulator Python owner is active')
    out.mkdir(parents=True)
    (out/'models').mkdir()
    save(out/'START.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),pid=os.getpid(),
        operation_sha256=sha(HERE/'OPERATION.json'),python_leaf_count=len(leaves),free_bytes=shutil.disk_usage(HERE).free,
        numpy_single_thread=True,shared_mutex_owned=True,new_policy_environments=0))
    tests = subprocess.run(['node', str(HERE/'test_rc.cjs')],capture_output=True,text=True,check=True)
    save(out/'PURE_TESTS.json',json.loads(tests.stdout))
    result = main(op)
    from audit import audit
    audit(op)
    print(json.dumps(dict(status='FINISHED',fits=result['fits'],adopted=False,output=str(out))),flush=True)
except BaseException:
    if out.exists() and not (out/'FAILURE.json').exists():
        save(out/'FAILURE.json',dict(status='FAILED_PRESERVED',traceback=traceback.format_exc()))
    raise
finally:
    if locked:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
    lock.close()
