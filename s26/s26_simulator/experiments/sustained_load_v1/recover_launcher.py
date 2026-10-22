"""Registered finite unstarted-only continuation; no failed identity retry."""
from pathlib import Path
import msvcrt,subprocess,time
HERE=Path(__file__).resolve().parent
lock=(HERE.parents[3]/'D1Check/a24_simulator/runtime/worker.lock').open('r+b')
try:
    lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    for entry in ['recover_unstarted.cjs','audit.cjs','report_v2.cjs']:
        with (HERE/(entry+'.'+str(time.time_ns())+'.log')).open('x',encoding='utf-8') as log:
            child=subprocess.Popen(['node',str(HERE/entry)],cwd=HERE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8')
            for line in child.stdout:
                log.write(line);log.flush();print(line,end='',flush=True)
            status=child.wait()
        if status:raise SystemExit(status)
finally:
    lock.seek(0)
    try:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
    except OSError:pass
    lock.close()
