"""Run the finite calibration once, under the existing shared mutex."""
import json,msvcrt,os,shutil,sys,time,traceback
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from prepare import H,R,A,O,write
def main():
    if O.exists():raise RuntimeError('Consumed identity; preserve prior results')
    lock=(A/'runtime/a24_local_worker.lock').open('r+b');owned=False
    try:
        for attempt in range(31):
            try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);owned=True;break
            except OSError:
                if attempt==30:raise RuntimeError('Bounded lock wait ended')
                print(json.dumps({'state':'WAIT','reason':'shared worker lock busy','seconds':20}),flush=True);time.sleep(20)
        assert shutil.disk_usage(R).free>=8*1024**3,'Disk guard'
        import prepare
        prepare.main();write(O/'START.json',{'unix':time.time(),'fit_limit':336,'policy_environments':0,'device_measurements':0})
        import fit
        fit.main();write(O/'COMPLETE.json',{'unix':time.time(),'status':'FINITE_CALIBRATION_COMPLETE','fits':336,'policy_environments':0,'device_measurements':0})
    except BaseException as error:
        if O.exists():write(O/'FAILURE.json',{'error':repr(error),'traceback':traceback.format_exc(),'automatic_retry':False})
        raise
    finally:
        if owned:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()
if __name__=='__main__':main()
