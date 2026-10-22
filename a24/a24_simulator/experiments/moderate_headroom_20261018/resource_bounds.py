"""User-authorized independent simulator compute; no shared physical device.

Deterministic simulated clocks never use host wall time. Only this workspace
writes its outputs. A pinned sibling simulator/auditor may compute separately.
"""
from pathlib import Path
import hashlib,json,os,subprocess,time
HERE=Path(__file__).resolve().parent

def inspect(entry,minimum_free_bytes):
    spec=json.loads((HERE/'PARALLEL_ALLOWLIST_V2.json').read_text(encoding='utf-8'))
    command="[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); $o=Get-CimInstance Win32_OperatingSystem; $c=Get-CimInstance Win32_ComputerSystem; $p=@(Get-CimInstance Win32_Process -Filter \"Name = 'python.exe'\" | Select-Object ProcessId,ParentProcessId,CommandLine,WorkingSetSize); @{free_KiB=$o.FreePhysicalMemory;logical_processors=$c.NumberOfLogicalProcessors;python=$p}|ConvertTo-Json -Depth 4 -Compress"
    data=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',command],creationflags=0x08000000).decode('utf-8-sig'))
    rows=data['python'];rows=rows if isinstance(rows,list) else [rows]
    if len(rows)>3:raise RuntimeError('Temporary global Python3 resource limit')
    if data['logical_processors']<4 or data['free_KiB']*1024<minimum_free_bytes:raise RuntimeError('Temporary memory/core resource limit')
    for peer in spec['peers']:
        if hashlib.sha256(Path(peer['path']).read_bytes()).hexdigest()!=peer['sha256']:raise ValueError('Pinned independent peer source changed')
    own=0;others=[]
    for row in rows:
        if row['ProcessId']==os.getpid():own+=1;continue
        text=(row.get('CommandLine') or '').replace('\\','/').lower()
        if row['ProcessId']==25792 and '3d_cleanup/server.py' in text:role='Existing unrelated local server'
        else:
            allowed=next((p for p in spec['peers'] if str(Path(p['path'])).replace('\\','/').lower() in text or (p.get('command_token') and p['command_token'] in text)),None)
            if allowed is None:raise RuntimeError('Temporary unregistered Python peer')
            role=allowed['role']
        others.append(dict(process=row,role=role))
    if own!=1:raise RuntimeError('Actual producer PID binding')
    data.update(actual_pid=os.getpid(),entry=str(Path(entry).resolve()),minimum_free_bytes=minimum_free_bytes,global_limit=3,own_A24_limit=1,other_roles=others,private_mutex='runtime/a24_local_worker.lock',authority=spec['user_authority'])
    return data

def wait_resources(entry,minimum_free_bytes,deadline):
    while True:
        try:return inspect(entry,minimum_free_bytes)
        except RuntimeError as exc:
            if time.monotonic()>=deadline:raise
            print('PRE_START_RESOURCE_WAIT',str(exc),'minimum_MiB',round(minimum_free_bytes/1024**2),flush=True);time.sleep(5)
