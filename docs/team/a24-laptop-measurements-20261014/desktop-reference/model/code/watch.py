"""One-owner supervisor. Never retries a failed environment or hides an abort."""
import os,sys,time,subprocess,traceback,msvcrt,json
from common import OUT,save,read,stamp,WORK,append,sha

def active_workers():
    # Native process query avoids treating a recycled PID as an existing worker.
    query="Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python' } | Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress"
    result=subprocess.run(["powershell.exe","-NoProfile","-NonInteractive","-Command",query],capture_output=True,text=True,check=True)
    rows=json.loads(result.stdout or "[]")
    if isinstance(rows,dict):rows=[rows]
    found=[];prefix=str(WORK).replace("\\","/").lower()
    for item in rows:
        command=(item.get("CommandLine") or "").replace("\\","/").lower()
        if item["ProcessId"] not in (os.getpid(),os.getppid()) and prefix in command and (
                "/code/orchestrator.py" in command or "/code/watch.py" in command):found.append(item)
    return found

def audited_complete():
    if not all((OUT/name).exists() for name in ("COMPLETE.json","FINAL_AUDIT.json","FINAL_FREEZE.json","FINAL_SUMMARY.json")):return False
    complete=read(OUT/"COMPLETE.json");checked=read(OUT/"FINAL_AUDIT.json")
    return (checked.get("status")=="PASS" and complete.get("independent_audit",{}).get("status")=="PASS"
            and complete.get("freeze_sha")==sha(OUT/"FINAL_FREEZE.json")
            and complete.get("summary_sha")==sha(OUT/"FINAL_SUMMARY.json"))

def run():
    OUT.mkdir(parents=True,exist_ok=True)
    lock=(OUT/"worker.lock").open("a+b")
    if lock.seek(0,2)==0:lock.write(b"0");lock.flush()
    lock.seek(0)
    try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:raise RuntimeError("V2 supervisor already owns worker.lock")
    workers=active_workers()
    if workers:raise RuntimeError("V2 worker already active: "+str(workers))
    if audited_complete():
        save(OUT/"SUPERVISOR.json",dict(pid=os.getpid(),status="COMPLETE",unix=stamp(),already_complete=True));return
    if (OUT/"COMPLETE.json").exists():raise RuntimeError("Unverified COMPLETE marker requires audit investigation")
    save(OUT/"WORKER_OWNER.json",dict(pid=os.getpid(),unix=stamp(),worker_cap=1))
    save(OUT/"SUPERVISOR.json",dict(pid=os.getpid(),status="RUNNING",unix=stamp()))
    with (OUT/"RUN_stdout.log").open("a",encoding="utf-8") as stdout,(OUT/"RUN_stderr.log").open("a",encoding="utf-8") as stderr:
        argv=[sys.executable,"-X","utf8","-u",str(WORK/"code/orchestrator.py")]
        process=subprocess.Popen(argv,stdout=stdout,stderr=stderr)
        launch=dict(pid=process.pid,supervisor_pid=os.getpid(),unix=stamp(),own_heavy_workers=1,
            global_environment_cap=137712,no_device=True,no_external_send=True,autonomous_development=True,
            command=argv,supervisor_source_sha=sha(WORK/"code/watch.py"),recovery_origin=str(OUT/"recovery_20261014"))
        save(OUT/"AUTONOMOUS_STARTED.json",launch);append(OUT/"process_launches.jsonl",launch)
        exitcode=process.wait()
    complete=exitcode==0 and audited_complete()
    save(OUT/"SUPERVISOR.json",dict(pid=os.getpid(),status="COMPLETE" if complete else "ATTENTION",exit_code=exitcode,unix=stamp()))
    lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
    if not complete:raise RuntimeError("Worker stopped before audited completion; inspect preserved receipts/failure log")

if __name__=="__main__":
    try:run()
    except Exception:
        save(OUT/f"SUPERVISOR_FAILURE_{time.time_ns()}.json",dict(traceback=traceback.format_exc(),unix=stamp()))
        raise
