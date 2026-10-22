"""One shared-slot, saved-only audit/report sequence; no simulator execution."""
import importlib,msvcrt,os,shutil,subprocess,sys,traceback
from pathlib import Path
entry=Path(sys.argv[1]).resolve();sys.path.insert(0,str(entry))
from run import read,save,sha,processes,now
op=read(entry/'OPERATION.json');out=Path(op['output'])
assert(out/'COMPLETE.json').exists() and not(out/'FINAL_PROOF.json').exists()
lock=Path(op['shared_mutex']).open('r+b');locked=False
try:
    lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
    ps=processes();assert len({p['ProcessId'] for p in ps}-{p['ParentProcessId'] for p in ps})<=2
    assert not any(p['ProcessId']!=os.getpid() and any(t in(p.get('CommandLine')or'')for t in('a24_simulator','s26_simulator'))for p in ps)
    assert shutil.disk_usage(entry).free>=8*1024**3 and shutil.disk_usage('D:/').free>=8*1024**3
    save(entry/'POSTRUN_OPERATION.json',dict(utc=now(),scope='New saved comparison arithmetic only',new_environment=0,new_training_data=0,pins=[dict(path=str(p),sha256=sha(p))for p in(Path(__file__),entry/'audit_saved.cjs',entry/'audit_nn.py',entry/'report.cjs',entry/'OPERATION.json',out/'RESULT.json')]))
    try:
        assert not(entry/'AUDIT_OPERATION.json').exists() and not(entry/'NN_AUDIT_OPERATION.json').exists()
        subprocess.run(['node',str(entry/'audit_saved.cjs')],check=True)
        importlib.import_module('audit_nn').main(op,out)
        subprocess.run(['node',str(entry/'report.cjs')],check=True)
        print('SAVED_ONLY_AUDITS_AND_REPORT_COMPLETE',flush=True)
    except BaseException:
        save(out/'POSTRUN_FAILURE.json',dict(utc=now(),traceback=traceback.format_exc(),new_environment=0,automatic_retry=False));raise
finally:
    if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
    lock.close()
