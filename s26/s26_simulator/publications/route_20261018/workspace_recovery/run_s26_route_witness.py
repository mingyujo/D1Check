"""One-process counted witness driver; independent parent sources stay frozen."""
import datetime,json,hashlib,msvcrt,os,subprocess,time
from pathlib import Path
W=Path(__file__).resolve().parent.parent;H=W/'S26-D1Check/s26_simulator/experiments/route_witness_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2)
P=H.parent/'route_energy_v1';pilot=H.parent/'route_witness_pilot_v1'
if not (pilot/'artifacts/G001/FINAL_PROOF.json').exists():
    saved_audit=subprocess.run(['node',str(pilot/'audit_summary.cjs')],creationflags=0x08000000)
    if saved_audit.returncode:raise RuntimeError('Saved TRAIN pilot audit failed; no environment replay')
op=json.loads((H/'OPERATION_BASE.json').read_text(encoding='utf-8'));op['pins']+=[dict(path=str(p),sha256=sha(p)) for p in [Path(__file__),H/'run.cjs',H/'audit_report.cjs',P/'artifacts/G001/RESULT.json',P/'artifacts/G001/NN_AUDIT.json',pilot/'artifacts/G001/FINAL_PROOF.json']]
lock=Path(op['shared_mutex']).open('r+b');locked=False
try:
    lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
    import psutil
    deadline=time.monotonic()+3600
    while psutil.virtual_memory().available<1536*1024**2 or sum(p.name().lower() in ['python.exe','python3.exe'] for p in psutil.process_iter())>3:
        if time.monotonic()>=deadline:raise RuntimeError('Finite pre-START witness resource wait')
        time.sleep(5)
    op['resource']=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),free_bytes=psutil.virtual_memory().available,Python_cap=3,initial_min_free_MiB=1536,Node_only_scientific_worker=True,heavy_S26_limit=1)
    write(H/'OPERATION.json',op)
    result=subprocess.run(['node',str(H/'run.cjs')],creationflags=0x08000000)
    if result.returncode:raise RuntimeError('Witness calculation failed; preserve namespace; no retry')
    result=subprocess.run(['node',str(H/'audit_report.cjs')],creationflags=0x08000000)
    if result.returncode:raise RuntimeError('Saved witness audit/report failed; no environment retry')
finally:
    if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
    lock.close()
