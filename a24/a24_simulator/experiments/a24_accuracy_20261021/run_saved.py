"""One bounded saved-data pass under the project's shared worker mutex."""
import ctypes, json, msvcrt, os, shutil, subprocess, sys, time, traceback
from pathlib import Path
from prepare import H,R,A,O,write

def main():
    if O.exists():raise RuntimeError('Existing identity is preserved; no automatic restart')
    lock=(A/'runtime/a24_local_worker.lock').open('r+b');owned=False
    try:
        for attempt in range(31):
            try:
                lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);owned=True;break
            except OSError:
                if attempt==30:raise RuntimeError('Shared lock busy; bounded wait ended')
                print(json.dumps({'state':'WAIT','reason':'shared worker lock busy','seconds':20}),flush=True);time.sleep(20)
        if shutil.disk_usage(R).free<8*1024**3:raise RuntimeError('Less than 8 GiB disk free')
        import prepare
        prepare.main()
        write(O/'START.json',{'kind':'SAVED_DATA_CONDITIONAL_PREDICTION_ONLY','started_unix':time.time(),'policy_environments':0,'fits':0,'phone_measurements':0})
        node=shutil.which('node');assert node
        for entry,cmd,timeout in [('replay',[node,str(H/'replay.cjs')],180),('analysis',[sys.executable,'-B','-X','utf8',str(H/'analyze.py')],300)]:
            with (O/(entry+'.log')).open('x',encoding='utf-8') as log:
                subprocess.run(cmd,cwd=R,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=timeout)
            print((O/(entry+'.log')).read_text(encoding='utf-8'),flush=True)
        write(O/'COMPLETE.json',{'status':'SAVED_PREDICTION_AND_ERRORS_COMPLETE','completed_unix':time.time(),'policy_environments':0,'fits':0,'phone_measurements':0,'empirical_accuracy_PASS':None})
    except BaseException as error:
        if O.exists():
            write(O/'FAILURE.json',{'error':repr(error),'traceback':traceback.format_exc(),'automatic_retry':False})
        raise
    finally:
        if owned:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()

if __name__=='__main__':main()
