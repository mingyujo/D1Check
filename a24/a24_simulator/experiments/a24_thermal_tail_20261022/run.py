import os,json,msvcrt,time,shutil,traceback
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from prepare import A,R,O,write
def main():
    if O.exists():raise RuntimeError('Consumed identity; no automatic restart')
    lock=(A/'runtime/a24_local_worker.lock').open('r+b');owned=False
    try:
        for attempt in range(31):
            try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);owned=True;break
            except OSError:
                if attempt==30:raise RuntimeError('Bounded shared lock wait expired')
                print(json.dumps({'state':'WAIT','reason':'shared worker lock busy','seconds':20}),flush=True);time.sleep(20)
        assert shutil.disk_usage(R).free>=8*1024**3
        from fit import resources
        resources()
        import prepare;prepare.main();write(O/'START.json',{'unix':time.time(),'fit_limit':336,'policy_environments':0,'new_measurements':0})
        import fit;fit.main();write(O/'COMPLETE.json',{'status':'THERMAL_TAIL_COMPLETE','unix':time.time()})
    except BaseException as e:
        if O.exists():write(O/'FAILURE.json',{'error':repr(e),'traceback':traceback.format_exc(),'automatic_retry':False})
        raise
    finally:
        if owned:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()
if __name__=='__main__':main()
