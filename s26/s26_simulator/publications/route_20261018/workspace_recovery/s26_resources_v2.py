"""Independent registered A24 peers, verified from their immutable operation pins."""
import datetime,hashlib,json,os,re,shutil,subprocess,time
from pathlib import Path
WORK=Path(__file__).resolve().parent.parent
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
   m=re.search(r'a24_simulator/experiments/([a-z0-9_]+)/([a-z0-9_]+\.py)',text)
   if not m:raise RuntimeError('Unknown Python peer; wait')
   entry=(WORK/'D1Check/a24_simulator/experiments'/m[1]/m[2]).resolve();expected=(WORK/'D1Check/a24_simulator/experiments').resolve();assert expected in entry.parents
   digest=hashlib.sha256(entry.read_bytes()).hexdigest();registration=None
   for file in sorted(entry.parent.glob('OPERATION*.json')):
    op=json.loads(file.read_text(encoding='utf-8-sig'));pins=op.get('sources',op.get('source',op.get('pins',[])))
    if isinstance(pins,list)and op.get('global_Python_limit',0)>=3 and any(isinstance(x,dict)and str(Path(x.get('path','')).resolve()).lower()==str(entry).lower()and x.get('sha256')==digest for x in pins):registration=dict(path=str(file),sha256=hashlib.sha256(file.read_bytes()).hexdigest());break
   if registration is None:raise RuntimeError('Unregistered or modified A24 peer source; wait')
   role='Separate registered deterministic A24 computation';p={**p,'entry':str(entry),'entry_sha256':digest,'registration':registration}
  others.append(dict(role=role,process=p))
 for volume in(WORK,Path('D:/')):
  if shutil.disk_usage(volume).free<8*1024**3:raise RuntimeError('Disk headroom below8GiB')
 return dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),actual_PID=os.getpid(),global_Python_limit=3,own_S26_limit=1,min_free_MiB=min_free_MiB,other_roles=others,**s)
def wait_ready(timeout_s=7200,min_free_MiB=2048):
 end=time.monotonic()+timeout_s
 while True:
  try:return inspect(min_free_MiB)
  except RuntimeError as e:
   if time.monotonic()>=end:raise
   print('RESOURCE_WAIT_V2',str(e),flush=True);time.sleep(5)
