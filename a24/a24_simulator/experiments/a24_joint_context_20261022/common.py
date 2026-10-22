import json,hashlib,csv,subprocess,ctypes,shutil,os
from pathlib import Path
from collections import Counter
H=Path(__file__).resolve().parent;R=H.parents[2];A=R/'a24_simulator'
O=A/'results/A24_JOINT_CONTEXT_20261022_01';V=A/'reviews/A24_JOINT_CONTEXT_20261022_01'
PREV=A/'results/A24_ENERGY_CALIBRATION_20261022_01';PH=A/'experiments/a24_energy_calibration_20261022'
ENERGY=A/'results/A24_ENERGY_ABSOLUTE_20261022_01';EH=A/'experiments/a24_energy_absolute_20261022'
THERMAL=A/'results/A24_THERMAL_DIRECTION_20261021_02';TH=A/'experiments/a24_thermal_direction_v2_20261021'
FIRST=A/'results/A24_THERMAL_DIRECTION_20261021_01'
OLD=A/'results/A24_ACCURACY_20261021_02';CAL=A/'results/A24_THERMAL_CALIBRATION_20261021_01'
CONTROL=[R/'docs/PROJECT_STATUS.md',R/'docs/PROJECT_PLAN.md',R/'docs/DECISIONS.md',A/'docs/LATEST_EXECUTION_FILES.md']
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pin(p):return {'path':p.relative_to(R).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size}
def write(p,x):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,ensure_ascii=False,allow_nan=False,separators=(',',':'))
def csvwrite(p,rows):
    if not rows:return
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def split(cases,n=3):
    counts=Counter(c['group'] for c in cases);bins=[[] for _ in range(min(n,len(counts)))];size=[0]*len(bins)
    for g in sorted(counts,key=lambda g:(-counts[g],hashlib.sha256(g.encode()).hexdigest())):
        k=min(range(len(bins)),key=lambda k:(size[k],k));bins[k].append(g);size[k]+=counts[g]
    return bins
class Memory(ctypes.Structure):
    _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong),('totalPhys',ctypes.c_ulonglong),('availPhys',ctypes.c_ulonglong),('totalPage',ctypes.c_ulonglong),('availPage',ctypes.c_ulonglong),('totalVirtual',ctypes.c_ulonglong),('availVirtual',ctypes.c_ulonglong),('availExtended',ctypes.c_ulonglong)]
def resources(start=False):
    m=Memory();m.length=ctypes.sizeof(m);assert ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m));assert m.availPhys>=1024**3,'RAM below1GiB'
    free=shutil.disk_usage(R).free;assert free>=(8 if start else 4)*1024**3,'Insufficient disk'
    import psutil
    pp=[p.info for p in psutil.process_iter(['pid','name']) if (p.info['name'] or '').lower() in ('python.exe','python3.exe','python3.11.exe')]
    assert len(pp)<=3,pp
    return {'free_disk_bytes':free,'available_RAM_bytes':m.availPhys,'python_processes':pp,'math_threads':{k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')}}
def check_sources(reg):
    for p in [reg['inputs'],reg['feature_inputs'],*reg['sources']]:assert sha(R/p['path'])==p['sha256'],p['path']
