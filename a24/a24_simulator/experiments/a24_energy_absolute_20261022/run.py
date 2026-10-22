import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import time,msvcrt,traceback
from common import *
def main():
    assert not O.exists(),'Consumed identity; never restart'
    lock=(A/'runtime/a24_local_worker.lock').open('r+b');owned=False;begun=time.time()
    try:
        for attempt in range(31):
            try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);owned=True;break
            except OSError:
                if attempt==30:write(V/f'WAIT_EXPIRED_{int(begun)}.json',{'fit_START':0,'result_exists':O.exists(),'elapsed_s':time.time()-begun});return
                print(json.dumps({'state':'WAIT_SHARED_BYTE_LOCK','elapsed_s':time.time()-begun}),flush=True);time.sleep(20)
        res=resources(True)
        import prepare;prepare.main();write(O/'START.json',{'unix':time.time(),'resources':res,'fit_limit':600})
        import fit;fit.main();write(O/'COMPLETE.json',{'unix':time.time(),'state':'FINITE_FITS_COMPLETE','saved_validation_pending':True})
    except BaseException as e:
        write((O if O.exists() else V)/f'FAILURE_{int(time.time())}.json',{'error':repr(e),'traceback':traceback.format_exc(),'automatic_retry':False});raise
    finally:
        if owned:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()
        if owned:write(V/f'LOCK_RELEASED_{int(begun)}.json',{'owned_lock_returned':True,'unix':time.time()})
if __name__=='__main__':main()
