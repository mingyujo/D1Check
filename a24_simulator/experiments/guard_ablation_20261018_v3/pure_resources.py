"""User-authorized relaxation for read-only snapshot/AST checks only.

Never used by a native runner, training, timing restoration or LP producer.
"""
from pathlib import Path
import json,os,subprocess

def inspect(entry):
    command="[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); $o=Get-CimInstance Win32_OperatingSystem; $c=Get-CimInstance Win32_ComputerSystem; $p=@(Get-CimInstance Win32_Process -Filter \"Name = 'python.exe'\" | Select-Object ProcessId,ParentProcessId,CommandLine); @{free_KiB=$o.FreePhysicalMemory;logical_processors=$c.NumberOfLogicalProcessors;python=$p}|ConvertTo-Json -Depth 4 -Compress"
    # Dedicated invocation; no environment entry point or shared lock claimed.
    data=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',command],creationflags=0x08000000).decode('utf-8-sig'))
    rows=data['python'];rows=rows if isinstance(rows,list) else [rows]
    if len(rows)>3 or data['logical_processors']<4 or data['free_KiB']<1024**2:raise RuntimeError('Read-only preflight resource allowance unavailable')
    if not any(r['ProcessId']==os.getpid() for r in rows):raise RuntimeError('Actual pure process absent')
    data.update(utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),actual_pid=os.getpid(),entry=str(Path(entry).resolve()),scope='Read-only AST/import/synthetic snapshot tests only; no environments/training/model restoration/LP',pure_global_Python_limit=3,native_global_limit=3,user_authority='2026-10-18 constraints may be relaxed with logical grounds',one_own_pure_process=True)
    return data
