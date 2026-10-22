import hashlib,json,csv,subprocess
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;R=H.parents[2];A=R/'a24_simulator';O=A/'results/A24_THERMAL_TAIL_20261022_01';V=A/'reviews/A24_THERMAL_TAIL_20261022_01'
PREV=A/'results/A24_THERMAL_DIRECTION_20261021_02';FIRST=A/'results/A24_THERMAL_DIRECTION_20261021_01';CAL=A/'results/A24_THERMAL_CALIBRATION_20261021_01';OLD=A/'results/A24_ACCURACY_20261021_02'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pin(p):return {'path':p.relative_to(R).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size}
def write(p,x):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,ensure_ascii=False,allow_nan=False,separators=(',',':'))
def split(cases,n=3):
    groups=Counter(c['group'] for c in cases);bins=[[] for _ in range(min(n,len(groups)))];sizes=[0]*len(bins)
    for g in sorted(groups,key=lambda g:(-groups[g],hashlib.sha256(g.encode()).hexdigest())):
        k=min(range(len(bins)),key=lambda k:(sizes[k],k));bins[k].append(g);sizes[k]+=groups[g]
    return bins
def main():
    O.mkdir(exist_ok=False);data=read(PREV/'INPUTS.json')
    for p in read(PREV/'REGISTRATION.json')['sources']:assert sha(R/p['path'])==p['sha256']
    data['tail_config']={'middle_s':[30.,60.],'robust_delta_C':[0.,.15],'hinge_strength':[0.,2.],'fit_limit':336,'context_reference_C':28.,'posthoc_development':True}
    data['inherited']={f:{str(k):read(PREV/f'{f}_OUTER_{k}.json')['model'] for k in range(5)} for f in ['m8','old']}
    for f in ['m8','old']:data['inherited'][f]['deployment']=read(PREV/f'{f}_DEPLOYMENT_MODEL.json')
    write(O/'INPUTS.json',data)
    rows=list(csv.DictReader((PREV/'DIRECTION_PAIRED_WINDOWS.csv').open(encoding='utf-8-sig')))
    # Column names are asserted by the caller before preparation.
    fixed=read(PREV/'FINDINGS.json')['worsening'];fixed=[r for r in fixed if r['family']=='m8']
    write(O/'FIXED_TARGETS.json',{'sessions':fixed,'previous_window_rows':rows,'selection_uses_these_subsets':False})
    paths=[*sorted(H.glob('*.*')),PREV/'INPUTS.json',PREV/'REGISTRATION.json',PREV/'FINDINGS.json',PREV/'OOF_PREDICTIONS.json',PREV/'DIRECTION_PAIRED_WINDOWS.csv',PREV/'FIT_LEDGER.jsonl',FIRST/'FIT_LEDGER.jsonl',CAL/'OOF_PREDICTIONS.json',OLD/'PREDICTIONS.json.gz',*sorted(PREV.glob('*_OUTER_*.json')),*sorted(PREV.glob('*_DEPLOYMENT_MODEL.json')),
        H.parent/'a24_thermal_calibration_20261021/thermal_model.py',H.parent/'a24_thermal_direction_v2_20261021/thermal_model.py',H.parent/'a24_thermal_direction_v2_20261021/calibrated_profile.cjs',H.parent/'a24_thermal_calibration_20261021/calibrated_profile.cjs',R/'common_simulator/v1/profiles.cjs']
    write(O/'REGISTRATION.json',{'utc':datetime.now(timezone.utc).isoformat(),'HEAD':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'dirty_worktree':True,'sources':[pin(p) for p in dict.fromkeys(paths)],'inputs':pin(O/'INPUTS.json'),'fit_limit':336,'new_measurements':0,'policy_environments':0,'fresh_confirmation':False})
    print(json.dumps({'status':'PREPARED','cases':len(data['cases']),'fit_limit':336}),flush=True)
if __name__=='__main__':main()
