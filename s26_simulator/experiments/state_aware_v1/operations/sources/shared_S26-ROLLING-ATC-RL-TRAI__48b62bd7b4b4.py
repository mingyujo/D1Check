"""Visible shared Python owner of the registered Node forecast workflow.

This process supervises real reserved work. It imports no numerical/NN module.
Its actual PID/creation/command are verified by each child, and other A24/S26
guards can see its ownership while Node performs the event computations.
"""
import argparse
import ast
import datetime
import hashlib
import json
import msvcrt
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

W=Path(__file__).resolve().parent
PS=Path('C:/Users/chomg/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe')
NODE=Path('C:/Users/chomg/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')


def require(ok,text):
    if not ok: raise ValueError(text)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while block:=f.read(1024*1024):h.update(block)
    return h.hexdigest()


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path,value):
    with Path(path).open('x',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,allow_nan=False,indent=2);f.flush();os.fsync(f.fileno())


def verify(op):
    for key in ('source_hashes','input_hashes','protected_hashes'):
        for path,h in op.get(key,{}).items():require(sha(path)==h,'SHA '+path)


def processes():
    script="Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|pypy|powershell|pwsh' } | Select-Object ProcessId,ParentProcessId,CreationDate,Name,CommandLine | ConvertTo-Json -Compress -Depth 3"
    text=subprocess.check_output([str(PS),'-NoProfile','-Command',script],text=True,encoding='utf-8',timeout=30)
    value=json.loads(text or '[]');return [value] if isinstance(value,dict) else value


def guard():
    rows=processes();py=[r for r in rows if str(r['Name']).lower().startswith(('python','pypy'))]
    require(all(r['ProcessId']==os.getpid() for r in py),'Another actual Python owner; wait without changing it')
    for r in rows:
        command=(r.get('CommandLine') or '').lower()
        if not str(r['Name']).lower().startswith(('python','pypy')):
            require(' -file ' not in command or 'supervise_once.ps1' not in command,'Production supervisor has next shared slot')
    require(shutil.disk_usage(W.anchor).free>=8589934592,'8 GiB reserve')
    own=[r for r in rows if r['ProcessId']==os.getpid()]
    require(len(own)==1,'actual owner CIM evidence')
    return own[0]


def run_node(script,arguments,out,name):
    require(script.resolve().parent==W,'Only this registered workspace script')
    guard()
    with (out/(name+'.stdout.log')).open('x',encoding='utf-8') as stdout,(out/(name+'.stderr.log')).open('x',encoding='utf-8') as stderr:
        child=subprocess.Popen([str(NODE),'--max-old-space-size=3072',str(script),*arguments],cwd=W,stdout=stdout,stderr=stderr)
        save(out/(name+'_LAUNCH.json'),dict(pid=child.pid,parent_pid=os.getpid(),script=str(script),arguments=arguments,created_unix=time.time()))
        code=child.wait()
    save(out/(name+'_FINISHED.json'),dict(exit_code=code,finished_unix=time.time(),stdout_sha256=sha(out/(name+'.stdout.log')),stderr_sha256=sha(out/(name+'.stderr.log'))))
    require(code==0,'Registered Node step failed; preserve saved artifacts')


def main():
    p=argparse.ArgumentParser();p.add_argument('--operation',required=True);a=p.parse_args()
    operation_path=Path(a.operation).resolve();op=read(operation_path)
    require(op['schema']=='S26_FORECAST_CONFORMANCE_RECOVERY_OPERATION_v2','recovery/visible-owner operation schema')
    verify(op);own=guard()
    require(str(Path(__file__).resolve()) in op['source_hashes'] and sha(__file__)==op['source_hashes'][str(Path(__file__).resolve())],'registered actual owner source')
    ast.parse(Path(__file__).read_text(encoding='utf-8'))
    out=Path(op['runtime_output_dir']);require(not out.exists(),'Inspect prior owner outputs; do not restart this owner operation')
    shared=op['shared_byte_mutex'];shared_path=Path(shared['path']).resolve()
    require(shared['bytes_modified']==0 and shared['offset']==0 and shared['length']==1,'Existing shared byte mutex contract')
    require(sha(shared_path)==shared['sha256'],'Existing shared mutex bytes changed')
    shared_handle=shared_path.open('r+b');shared_acquired=False;fd=None
    lock=out.parent/'FORECAST_VISIBLE_OWNER.lock'
    try:
        shared_handle.seek(0);msvcrt.locking(shared_handle.fileno(),msvcrt.LK_NBLCK,1);shared_acquired=True
        own=guard()
        out.mkdir(parents=True)
        fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        os.write(fd,str(os.getpid()).encode());os.fsync(fd)
        created=datetime.datetime.fromisoformat(own['CreationDate'].replace('Z','+00:00')).astimezone(datetime.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
        receipt=dict(schema='S26_FORECAST_RUNTIME_OWNER_v1',pid=os.getpid(),creation_date_utc=created,
            command_line=own['CommandLine'],wrapper_source_path=str(Path(__file__).resolve()),wrapper_source_sha256=sha(__file__),
            operation_path=str(operation_path),operation_sha256=sha(operation_path),actual_parent_pid=own['ParentProcessId'],
            child_work='Registered Node forecast conformance and browser QA',shared_byte_mutex=shared,new_NN=0,new_fit=0,new_CostState=0)
        owner_path=Path(op['runtime_owner_path']);save(owner_path,receipt)
        os.environ['S26_FORECAST_OWNER_RECEIPT']=str(owner_path)
        script=W/'forecast_conformance_recovery_v2.cjs'
        require(op['source_hashes'].get(str(script))==sha(script),'bound recovery script')
        run_node(script,['--operation',str(operation_path),'--execute'],out,'STEP0_RECOVERY')
        verify(op)
        if op.get('auto_register_fixed_UI') is True:
            for name in ('register_forecast_ui_operation_v1.cjs','assemble_forecast_view.cjs','forecast_browser_qa.cjs'):
                require(op['source_hashes'].get(str(W/name))==sha(W/name),'Pre-bound downstream UI source '+name)
            run_node(W/'register_forecast_ui_operation_v1.cjs',[],out,'STEP1_UI_REGISTRATION')
            ui_path=out.parent/'FORECAST_UI_OPERATION_V1.json';ui=read(ui_path);verify(ui)
            require(ui['runtime_owner_contract']['operation_sha256_arg']==sha(operation_path),'Automatically registered UI parent binding')
            for p,h in ui['source_hashes'].items():require(op['source_hashes'].get(p)==h,'No unregistered downstream source '+p)
            run_node(W/'assemble_forecast_view.cjs',['--operation',str(ui_path)],out,'STEP2_UI_ASSEMBLY')
            assembly=out.parent/'FORECAST_VIEW_ASSEMBLY_V1.json'
            run_node(W/'forecast_browser_qa.cjs',['--operation',str(ui_path),'--assembly',str(assembly)],out,'STEP3_BROWSER')
            verify(ui);verify(op)
            save(out/'OWNER_FINISHED.json',dict(status='REGISTERED_FORECAST_STEPS_FINISHED_PENDING_FINAL_DOCUMENT_AUDIT',pid=os.getpid(),finished_unix=time.time(),owner_receipt_sha256=sha(owner_path),new_fit=0,new_NN=0,new_CostState=0))
            return
        save(out/'WAITING_FOR_REGISTERED_UI_STEP.json',dict(status='WAITING',parent_pid=os.getpid(),created_unix=time.time(),timeout_s=900))
        queue=Path(op['runtime_queue_dir']);queue.mkdir(parents=True,exist_ok=True)
        limit=time.monotonic()+900;done=False
        while time.monotonic()<limit:
            step=queue/'STEP1_UI.json'
            if step.exists():
                request=read(step);require(request['schema']=='S26_FORECAST_OWNED_UI_STEP_v1','sealed UI step request')
                ui_path=Path(request['operation_path']).resolve();require(sha(ui_path)==request['operation_sha256'],'UI step operation SHA')
                ui=read(ui_path);require(ui['schema']=='S26_RULE_FORECAST_UI_OPERATION_v1','registered UI operation')
                require(Path(ui['runtime_owner_path']).resolve()==owner_path.resolve(),'same visible owner receipt')
                require(ui['runtime_owner_contract']['operation_sha256_arg']==sha(operation_path),'UI binds actual owner operation')
                verify(ui);script=W/'forecast_browser_qa.cjs';require(ui['source_hashes'].get(str(script))==sha(script),'bound browser QA source')
                assembly=Path(request['assembly_path']).resolve();require(sha(assembly)==request['assembly_sha256'],'assembly SHA')
                run_node(script,['--operation',str(ui_path),'--assembly',str(assembly)],out,'STEP1_BROWSER')
                verify(ui);done=True;break
            time.sleep(1)
        require(done,'Registered UI handoff not received within the bounded owner interval')
        save(out/'OWNER_FINISHED.json',dict(status='REGISTERED_FORECAST_STEPS_FINISHED_PENDING_FINAL_DOCUMENT_AUDIT',pid=os.getpid(),finished_unix=time.time(),owner_receipt_sha256=sha(owner_path),new_fit=0,new_NN=0,new_CostState=0))
    except BaseException:
        if out.exists():save(out/'OWNER_FAILURE.json',dict(pid=os.getpid(),failed_unix=time.time(),traceback=traceback.format_exc()))
        raise
    finally:
        if fd is not None:os.close(fd)
        if fd is not None and lock.exists() and lock.read_text()==str(os.getpid()):lock.unlink()
        if shared_acquired:
            shared_handle.seek(0);msvcrt.locking(shared_handle.fileno(),msvcrt.LK_UNLCK,1)
        shared_handle.close()
        require(sha(shared_path)==shared['sha256'],'Shared mutex bytes must remain unchanged')


if __name__=='__main__':main()
