"""Fail-closed fresh ownership census with an explicit by-PID self query.
At most3 pre-START inventory reads, no retry of simulation identities.
No process hiding, exclusions, guard removal, or production source changes.
"""
import datetime,json,os,shutil,subprocess,time
PS='C:/Users/chomg/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe'
def guard(proof_path):
 from pathlib import Path
 attempts=[]
 for attempt in range(3):
  command="$ErrorActionPreference='Stop'; $all=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|pypy|powershell|pwsh' } | Select-Object ProcessId,ParentProcessId,CreationDate,Name,CommandLine); $self=Get-CimInstance Win32_Process -Filter 'ProcessId="+str(os.getpid())+"' | Select-Object ProcessId,ParentProcessId,CreationDate,Name,CommandLine; @{all=$all;self=$self} | ConvertTo-Json -EscapeHandling EscapeNonAscii -Compress -Depth 5"
  text=subprocess.check_output([PS,'-NoProfile','-Command',command],encoding='utf-8',timeout=30);v=json.loads(text);py=[r for r in v['all'] if str(r['Name']).lower().startswith(('python','pypy'))];own=[r for r in v['all'] if r['ProcessId']==os.getpid()];self=v['self'];attempts.append(dict(attempt=attempt+1,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),inventory=v))
  if any(r['ProcessId']!=os.getpid() for r in py):raise ValueError('Another Python owner; fail closed')
  for r in v['all']:
   cmd=(r.get('CommandLine') or '').lower()
   if not str(r['Name']).lower().startswith(('python','pypy')) and ' -file ' in cmd and 'supervise_once.ps1' in cmd:raise ValueError('Production supervisor has next slot')
  if len(own)==1 and self and self['ProcessId']==os.getpid() and own[0]['CreationDate']==self['CreationDate'] and own[0]['CommandLine']==self['CommandLine']:
   assert shutil.disk_usage('C:/').free>=8589934592 and shutil.disk_usage('D:/').free>=8589934592
   with Path(proof_path).open('x',encoding='utf-8') as f:json.dump(dict(status='PASS',attempts=attempts,self=self,no_hidden_processes=True),f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
   return self
  time.sleep(.25)
 with Path(proof_path).open('x',encoding='utf-8') as f:json.dump(dict(status='FAILED_CLOSED',attempts=attempts),f,ensure_ascii=False)
 raise ValueError('Actual owner census missing/inconsistent after3 bounded pre-START reads')
