"""Freeze exactly the prior input, folds and train-only thermal constants."""
import hashlib,json,subprocess,csv
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[2];A=R/'a24_simulator';O=A/'results/A24_THERMAL_DIRECTION_20261021_01'
PREV=A/'results/A24_THERMAL_CALIBRATION_20261021_01';OLD=A/'results/A24_ACCURACY_20261021_02'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pin(p):return {'path':p.relative_to(R).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size}
def write(p,x):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def split(cases,n=3):
    groups=Counter(c['group'] for c in cases);bins=[[] for _ in range(min(n,len(groups)))];sizes=[0]*len(bins)
    for group in sorted(groups,key=lambda g:(-groups[g],hashlib.sha256(g.encode()).hexdigest())):
        k=min(range(len(bins)),key=lambda i:(sizes[i],i));bins[k].append(group);sizes[k]+=groups[group]
    return bins
def main():
    O.mkdir(exist_ok=False);data=read(PREV/'INPUTS.json')
    for p in read(PREV/'REGISTRATION.json')['sources']:assert sha(R/p['path'])==p['sha256']
    data['direction_config']={'transport_s':[0.,5.,15.],'hinge_strength':[0.,2.,8.],'hinge_margin_C':.02,'threshold_C':.2,
        'MAE_allowance_C':.05,'delta_MAE_allowance_C':.05,'stable_accuracy_allowance_pp':5.,'fit_limit':360,
        'optimizer':{'method':'L-BFGS-B','maxiter':1000,'ftol':1e-13,'gtol':1e-8,'maxls':50}}
    data['frozen_tau']={family:{str(k):[read(PREV/f'{family}_OUTER_{k}.json')['model'][field] for field in ['tau_fast_s','tau_slow_s']] for k in range(5)} for family in ['m8','old']}
    data['deployment_tau']={family:[read(PREV/f'{family}_DEPLOYMENT_MODEL.json')[field] for field in ['tau_fast_s','tau_slow_s']] for family in ['m8','old']}
    write(O/'INPUTS.json',data)
    paths=[H/'PROTOCOL.md',*sorted(H.glob('*.py')),*sorted(H.glob('*.cjs')),PREV/'INPUTS.json',PREV/'REGISTRATION.json',PREV/'OOF_PREDICTIONS.json',PREV/'FINDINGS.json',PREV/'AP_WINDOWS.csv',
        *sorted(PREV.glob('*_OUTER_*.json')),*sorted(PREV.glob('*_DEPLOYMENT_MODEL.json')),OLD/'PREDICTIONS.json.gz',
        H.parent/'a24_thermal_calibration_20261021/thermal_model.py',H.parent/'a24_thermal_calibration_20261021/calibrated_profile.cjs',R/'common_simulator/v1/profiles.cjs']
    write(O/'REGISTRATION.json',{'utc':datetime.now(timezone.utc).isoformat(),'HEAD':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),
        'dirty_worktree':True,'sources':[pin(p) for p in dict.fromkeys(paths)],'inputs':pin(O/'INPUTS.json'),'fit_limit':360,'new_measurements':0,'policy_environments':0,'fresh_confirmation':False})
    print(json.dumps({'status':'PREPARED','cases':len(data['cases']),'candidates':9,'fit_limit':360},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
