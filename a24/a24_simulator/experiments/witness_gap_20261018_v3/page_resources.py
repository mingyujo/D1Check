"""Bound physical and commit headroom; paging cannot change simulator clocks."""
import json,subprocess,time
from resources import inspect
def wait_resources(entry,minimum_free_bytes,deadline):
    demand=max(2*1024**3,minimum_free_bytes+1024**3)
    while True:
        try:
            status=inspect(entry,256*1024**2)
            script='Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory | Select-Object AvailableMBytes,CommittedBytes,CommitLimit | ConvertTo-Json -Compress'
            memory=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',script],creationflags=0x08000000).decode('utf-8-sig'))
            available=int(memory['CommitLimit'])-int(memory['CommittedBytes'])
            if available<demand:raise RuntimeError('Temporary commit headroom '+str(available)+' below '+str(demand))
            status.update(commit_memory=memory,required_commit_headroom=demand,physical_minimum=256*1024**2,paging_allowed=True,scientific_clock_uses_host_time=False)
            return status
        except RuntimeError as exc:
            if time.monotonic()>=deadline:raise
            print('PRE_START_RESOURCE_WAIT',str(exc),flush=True);time.sleep(5)
