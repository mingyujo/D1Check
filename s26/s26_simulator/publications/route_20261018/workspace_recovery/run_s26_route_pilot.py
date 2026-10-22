"""Authorized brief resource supplement, never alter the live parent's science."""
import datetime,hashlib,json,msvcrt,os,subprocess
from pathlib import Path
import psutil
W=Path(__file__).resolve().parent.parent;H=W/'S26-D1Check/s26_simulator/experiments/route_witness_pilot_v1';P=H.parent/'route_energy_v1'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2)
op=read(H/'OPERATION_BASE.json');assert not (H/'OPERATION.json').exists()
parent=psutil.Process(op['parent_pid']);assert parent.is_running() and any('route_energy_v1' in arg and 'run.py' in arg for arg in parent.cmdline())
assert sha(P/'OPERATION.json')==op['parent_operation_sha256'];assert psutil.cpu_count()>=8 and psutil.virtual_memory().available>=2*1024**3
python=[p.info for p in psutil.process_iter(['pid','name','cmdline']) if (p.info['name'] or '').lower() in ['python.exe','python3.exe']]
assert len(python)<=3 and all(p['pid'] in [os.getpid(),parent.pid] for p in python),'No unrelated heavy peer for brief parallel pilot'
lock=Path(op['shared_mutex']).open('r+b');locked=False
try:
    try:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:pass
    else:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);raise RuntimeError('Expected live parent outer shared exclusion')
    lock.seek(1);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
    op['resource_snapshot']=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),logical_cores=psutil.cpu_count(),free_bytes=psutil.virtual_memory().available,python=python,outer_byte0_held_by_verified_parent=True,pilot_byte1_exclusive=True,own_max_two_temporarily=True)
    op['pins'].append(dict(path=str(Path(__file__)),sha256=sha(__file__)));save(H/'OPERATION.json',op)
    run=subprocess.run(['node',str(H/'run.cjs')],creationflags=0x08000000)
    if run.returncode:raise RuntimeError('Pilot failed; preserve consumed namespace, no retry')
finally:
    if locked:lock.seek(1);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
    lock.close()
