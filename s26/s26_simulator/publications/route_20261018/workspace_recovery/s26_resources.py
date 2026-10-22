"""User-authorized independent deterministic computation with bounded resources.

No simulated time or physics depends on host runtime. Each task owns its data.
Keep one S26 Python, at most three total Python (including the idle local server),
one CPU thread per numerical library, at least4 cores and2GiB free before start.
"""
import datetime,hashlib,json,os,shutil,subprocess,time
from pathlib import Path
WORK=Path(__file__).resolve().parent.parent
PEERS=[WORK/'D1Check/a24_simulator/experiments'/d/n for d,n in [('moderate_load_20261018','run_moderate.py'),('moderate_headroom_20261018','run.py'),('guard_learning_20261018','run.py'),('guard_ablation_20261018_v3','run.py')]]
def snapshot():
 cmd='[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); $o=Get-CimInstance Win32_OperatingSystem; $c=Get-CimInstance Win32_ComputerSystem; $p=@(Get-CimInstance Win32_Process -Filter "Name = \'python.exe\' OR Name = \'python3.exe\'" | Select-Object ProcessId,ParentProcessId,CommandLine,WorkingSetSize); @{free_KiB=$o.FreePhysicalMemory;cores=$c.NumberOfLogicalProcessors;python=$p}|ConvertTo-Json -Depth 4 -Compress'
 return json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',cmd],creationflags=0x08000000).decode('utf-8-sig'))
def inspect(min_free_MiB=2048):
 s=snapshot();ps=s['python'];ps=[ps]if isinstance(ps,dict)else ps
 if len(ps)>3 or s['cores']<4 or s['free_KiB']<min_free_MiB*1024:raise RuntimeError('Temporary process/core/memory limit')
 others=[]
 for p in ps:
  if p['ProcessId']==os.getpid():continue
  text=(p.get('CommandLine')or'').replace('\\','/').lower()
  if p['ProcessId']==25792 and '3d_cleanup/server.py'in text:role='Existing unrelated idle server'
  else:
   peer=next((x for x in PEERS if ('a24_simulator/experiments/'+x.parent.name+'/'+x.name).lower()in text),None)
   if peer is None:raise RuntimeError('Unregistered Python peer; wait')
   role='Separate pinned A24 deterministic simulator'
   p={**p,'source':str(peer),'source_sha256':hashlib.sha256(peer.read_bytes()).hexdigest()}
  others.append(dict(role=role,process=p))
 for volume in (WORK,Path('D:/')):
  if shutil.disk_usage(volume).free<8*1024**3:raise RuntimeError('Disk headroom below8GiB')
 return dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),actual_PID=os.getpid(),global_Python_limit=3,own_S26_limit=1,min_free_MiB=min_free_MiB,other_roles=others,**s)
def wait_ready(timeout_s=7200,min_free_MiB=2048):
 end=time.monotonic()+timeout_s
 while True:
  try:return inspect(min_free_MiB)
  except RuntimeError as e:
   if time.monotonic()>=end:raise
   print('RESOURCE_WAIT',str(e),flush=True);time.sleep(5)
