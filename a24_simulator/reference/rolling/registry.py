"""Separate durable identities and guards; no predecessor mutation/recollection."""
from pathlib import Path
import collections,gzip,hashlib,json,os,shutil,subprocess,time
B=Path('C:/Users/chomg/Documents/Codex/2026-10-11/dkfo')
W=B/'work/A24-INTEGRATED-SIM-20261016-G002'
O=B/'outputs/A24-INTEGRATED-SIM-20261016-G002'
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(canonical(x)).hexdigest()
def atomic(path,data):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 if path.exists():raise RuntimeError('Immutable artifact exists: '+str(path))
 tmp=path.with_name(path.name+'.part')
 with tmp.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)
def save(path,data):atomic(path,canonical(data))
def append(path,row):
 Path(path).parent.mkdir(parents=True,exist_ok=True)
 with Path(path).open('ab') as f:f.write(canonical(row)+b'\n');f.flush();os.fsync(f.fileno())
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def events(path):return [json.loads(line) for line in Path(path).open(encoding='utf-8')] if Path(path).exists() else []
def process_guard():
 code="Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python(w)?\\.exe$' } | Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress"
 p=subprocess.run(['powershell','-NoProfile','-Command',code],capture_output=True,check=True,creationflags=0x08000000)
 text=p.stdout.decode('utf-8',errors='replace').strip();rows=json.loads(text) if text else []
 if isinstance(rows,dict):rows=[rows]
 parents={r['ParentProcessId'] for r in rows};leaves=[r for r in rows if r['ProcessId'] not in parents]
 tokens=['A24-INTEGRATED-SIM-20261016','S26-ROLLING-ATC-RL-TRAIN-20261016','continue_independent_models.py','ROLLING-ATC-RL-37-V2']
 own=[r for r in leaves if any(t in (r.get('CommandLine') or '') for t in tokens)]
 if len(leaves)>2 or len(own)>1:raise RuntimeError('own heavy1/global Python leaves2 guard')
 return {'global_python_leaves':len(leaves),'own_python_leaves':len(own),'pids':[r['ProcessId'] for r in leaves]}
def guard(generation):
 reg=read(O/'REGISTRATION.json');gen=read(W/'source_generations'/generation/'GENERATION.json')
 if gen['generation']!=generation or gen['registration_sha256']!=sha(O/'REGISTRATION.json'):raise RuntimeError('generation/registration binding')
 for p,h in {**reg['protected'],**gen['source_hashes']}.items():
  if sha(p)!=h:raise RuntimeError('Immutable SHA changed: '+p)
 free=shutil.disk_usage(O).free
 if free<8*1024**3:raise RuntimeError('Disk8GiB guard')
 existing=events(O/'receipts.jsonl');own=sum(x['event']=='START' for x in existing)
 if own>=reg['budget']['new_environment_cap']:raise RuntimeError('new environment cap')
 shared=reg['shared_reservation'];parent_path=Path(shared['predecessor_receipts_path']).resolve()
 if parent_path!=(B/'outputs/A24-INTEGRATED-SIM-20261016/receipts.jsonl').resolve():raise RuntimeError('fixed predecessor ledger path')
 parent_bytes=parent_path.read_bytes()
 if hashlib.sha256(parent_bytes).hexdigest()!=shared['predecessor_receipts_sha256']:raise RuntimeError('predecessor receipts SHA')
 parent_events=[json.loads(line) for line in parent_bytes.decode('utf-8-sig').splitlines() if line.strip()]
 parent_starts=sum(x.get('event')=='START' for x in parent_events)
 if shared['pool_cap']!=2048 or shared['remaining_child_cap']!=2047 or shared['predecessor_consumed_START']!=1 or parent_starts!=1:raise RuntimeError('shared reservation contract')
 if reg['budget']['new_environment_cap']!=shared['remaining_child_cap'] or own>=shared['remaining_child_cap'] or parent_starts+own>=shared['pool_cap']:raise RuntimeError('parent plus child shared2048 cap')
 ledgers=[Path(p).resolve() for p in reg['prior_ledgers']]
 if len({str(p).casefold() for p in ledgers})!=len(ledgers) or parent_path not in ledgers:raise RuntimeError('prior ledgers canonical duplicates/missing predecessor')
 old=sum(parent_starts if p==parent_path else sum(x.get('event')=='START' for x in events(p)) for p in ledgers)
 if own+old>=137712:raise RuntimeError('global137712 cap')
 return {'free_bytes':free,'old_starts':old,'new_starts':own,'predecessor_starts':parent_starts,'shared_starts_before_START':parent_starts+own,'shared_cap':shared['pool_cap'],'predecessor_receipts_sha256':shared['predecessor_receipts_sha256'],**process_guard()}
class Journal:
 def __init__(self,generation):self.generation=generation;self.gen=read(W/'source_generations'/generation/'GENERATION.json')
 def run(self,label,config,callback,extra_writer=None):
  identity=digest([self.generation,label,config])[:28]
  if any(x.get('identity')==identity or x.get('manifest',{}).get('label')==label for x in events(O/'receipts.jsonl')):raise RuntimeError('Consumed identity/label; exact prepared recovery only '+identity)
  guards=guard(self.generation)
  manifest={'identity':identity,'label':label,'generation':self.generation,'config':config,'source_hashes':self.gen['source_hashes'],
   'registration_sha256':sha(O/'REGISTRATION.json'),'generation_sha256':sha(W/'source_generations'/self.generation/'GENERATION.json')}
  append(O/'receipts.jsonl',{'event':'START','identity':identity,'manifest':manifest,'guards':guards,'pid':os.getpid(),'unix':time.time()})
  try:
   result,aux=callback(manifest)
   raw=O/'raw'/self.generation/(identity+'.json.gz');atomic(raw,gzip.compress(canonical(result),mtime=0))
   extras=extra_writer(identity,aux) if extra_writer else {}
   row={'identity':identity,'label':label,'config':config,'raw_path':str(raw),'raw_sha256':sha(raw),
    'metrics':result['metrics'],'cost_metrics':result['cost']['metrics'],'manifest':manifest,**extras}
   prep=O/'prepared'/(identity+'.json');save(prep,row)
   append(O/'receipts.jsonl',{'event':'PREPARED','identity':identity,'prepared_sha256':sha(prep),'raw_sha256':sha(raw)})
   append(O/'rows.jsonl',row)
   append(O/'receipts.jsonl',{'event':'COMPLETE','identity':identity,'raw_sha256':sha(raw),'unix':time.time()})
   return result,aux,row
  except BaseException as error:
   append(O/'receipts.jsonl',{'event':'FAIL','identity':identity,'error':str(error),'type':type(error).__name__,'unix':time.time()});raise

def progress(phase,**fields):
 obj={'phase':phase,'pid':os.getpid(),'unix':time.time(),**fields}
 tmp=O/'PROGRESS.json.part'
 with tmp.open('wb') as f:f.write(canonical(obj));f.flush();os.fsync(f.fileno())
 os.replace(tmp,O/'PROGRESS.json')

def owner_lock():
 import msvcrt
 lock=(O/'worker.lock').open('a+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
 return lock
