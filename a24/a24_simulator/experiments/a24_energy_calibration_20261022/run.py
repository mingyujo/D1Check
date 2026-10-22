import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import time,json,msvcrt,traceback
from common import A,O,V,write,resources
def main():
    assert not O.exists(),'Consumed identity; do not restart'
    lock=(A/'runtime/a24_local_worker.lock').open('r+b');owned=False;begun=time.time()
    try:
        for attempt in range(31):
            try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);owned=True;break
            except OSError:
                if attempt==30:
                    write(V/f'LOCK_WAIT_{int(begun)}.json',{'state':'BOUNDED_WAIT_EXPIRED','wait_s':time.time()-begun,'scientific_fits_started':0,'result_directory_exists':O.exists(),'another_shared_worker_may_be_running':True});return
                print(json.dumps({'state':'WAIT_SHARED_BYTE_LOCK','elapsed_s':time.time()-begun}),flush=True);time.sleep(20)
        r=resources(True)
        import prepare;prepare.main();write(O/'START.json',{'unix':time.time(),'resources':r,'fit_limit':300,'new_measurements':0,'policy_environments':0})
        import fit;fit.main();write(O/'COMPLETE.json',{'state':'ENERGY_FITS_COMPLETE','unix':time.time(),'requires_saved_validation':True})
    except BaseException as e:
        target=O if O.exists() else V;write(target/f'FAILURE_{int(time.time())}.json',{'error':repr(e),'traceback':traceback.format_exc(),'automatic_retry':False});raise
    finally:
        if owned:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()
        if owned:write(V/f'LOCK_RELEASED_{int(begun)}.json',{'unix':time.time(),'owned_byte_lock_returned':True,'fits_exist':(O/'FIT_COMPLETE.json').exists()})
if __name__=='__main__':main()
