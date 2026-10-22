"""One finite Node supervisor under the existing local A24 Windows byte mutex."""
import json,msvcrt,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
WORKSPACE=HERE.parents[3]
LOCK=WORKSPACE/'D1Check/a24_simulator/runtime/worker.lock'
if len(sys.argv)<2 or sys.argv[1] not in ('tests','run','audit','all'):
    raise SystemExit('launcher.py tests|run|audit|all [--wait-a24]')
if '--wait-a24' in sys.argv:
    peer=WORKSPACE/'D1Check/a24_simulator/results/SUSTAINED_LOAD_20261017_01'
    deadline=time.monotonic()+1800
    print('WAITING_FOR_A24_PRODUCTION_AND_SAVED_AUDIT',flush=True)
    while not (peer/'AUDIT.json').exists() and not (peer/'FAILURE.json').exists():
        if time.monotonic()>deadline:raise SystemExit('A24 still owns shared workflow; no S26 environment started')
        time.sleep(2)
entries={'tests':['test.cjs'],'run':['run.cjs'],'audit':['audit.cjs'],
         'all':['test.cjs','register.cjs','run.cjs','audit.cjs','report.cjs']}[sys.argv[1]]
lock=LOCK.open('r+b')
try:
    lock.seek(0)
    msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    print(json.dumps(dict(status='LOCK_ACQUIRED',path=str(LOCK),mode=sys.argv[1])),flush=True)
    for entry in entries:
        stamp=str(time.time_ns())
        with (HERE/(entry+'.'+stamp+'.log')).open('x',encoding='utf-8') as log:
            child=subprocess.Popen(['node',str(HERE/entry)],cwd=HERE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8')
            for line in child.stdout:
                log.write(line);log.flush();print(line,end='',flush=True)
            status=child.wait()
        if status:raise SystemExit(status)
    raise SystemExit(0)
finally:
    lock.seek(0)
    try: msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
    except OSError: pass
    lock.close()
