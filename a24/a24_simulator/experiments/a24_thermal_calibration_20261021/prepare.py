"""Freeze causal initial context and group splits before thermal fitting."""
import gzip,hashlib,json,subprocess
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[2];A=R/'a24_simulator';O=A/'results/A24_THERMAL_CALIBRATION_20261021_01'
OLD=A/'results/A24_ACCURACY_20261021_02'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pin(p):return {'path':p.relative_to(R).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}
def write(p,x):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def split(cases,n=5):
    groups=Counter(c['group'] for c in cases);bins=[[] for _ in range(min(n,len(groups)))];sizes=[0]*len(bins)
    for group in sorted(groups,key=lambda g:(-groups[g],hashlib.sha256(g.encode()).hexdigest())):
        k=min(range(len(bins)),key=lambda i:(sizes[i],i));bins[k].append(group);sizes[k]+=groups[group]
    return bins
def main():
    O.mkdir(exist_ok=False)
    old=read(OLD/'INPUTS.json');manifest=read(A/'data/CORE_MANIFEST.json');source=next(p for p in manifest if p['name']=='MODEL_INPUTS.json')
    raw=gzip.decompress((A/source['stored']).read_bytes());assert hashlib.sha256(raw).hexdigest()==source['sha256'];allinput=read(OLD/'REGISTRATION.json')
    ss={s['session_id']:s for s in json.loads(raw)['sessions']};cases=[]
    for c in old['cases']:
        s=ss[c['session']];pre=sorted([o for o in s['observations'] if o.get('channel')=='AP' and o.get('hi_s') is not None and o['hi_s']<=35 and 15<=o['t_s']<=35],key=lambda o:o['t_s'])
        assert len(pre)>=3
        ts=[o['t_s'] for o in pre];ys=[o['ap_c'] for o in pre];tm=sum(ts)/len(ts);ym=sum(ys)/len(ys)
        slope=sum((t-tm)*(y-ym) for t,y in zip(ts,ys))/sum((t-tm)**2 for t in ts)
        slope=max(-.05,min(.05,slope))
        group=('m8:'+s['cohort_id'].split(':')[-1]) if c['family']=='m8' else s['cohort_id']
        cases.append({**c,'pre_slope_C_s':slope,'pre_points':len(pre),'pre_latest_return_s':max(o['hi_s'] for o in pre),
            'group':group,'original_cohort':s['cohort_id'],'fit_window_s':[35,180] if c['family']=='m8' else [35,c['observations'][-1]['t']]})
    assert len(cases)==106
    config={'tau_fast_s':[10.,30.,90.],'tau_slow_s':[180.,600.,1800.],'ridge':1e-4,'level_weight':.75,'delta_weight':.25,
        'selection_delta_weight':.5,'coefficient_names':['background_offset_C','pre_trend_multiplier','fast_CC','fast_CG','fast_DC','fast_CG_DC','slow_CC','slow_CG','slow_DC','slow_CG_DC'],
        'lower_bounds':[-2.,0.,*([0.]*8)],'upper_bounds':[2.,2.,*([20.]*8)],'prior':[0.,1.,*([0.]*8)],
        'outer_folds':5,'inner_folds':3,'fit_limit':336,'fresh_confirmation':False,'posthoc_development':True}
    folds={family:split([c for c in cases if c['family']==family]) for family in ['m8','old']}
    write(O/'INPUTS.json',{'cases':cases,'config':config,'outer_groups':folds,'screening':old['screening'],'original_profile':old['profile']})
    paths=[*sorted(H.glob('*.py')),*sorted(H.glob('*.cjs')),H/'PROTOCOL.md',A/'data/CORE_MANIFEST.json',A/source['stored'],
        OLD/'INPUTS.json',OLD/'REGISTRATION.json',OLD/'PREDICTIONS.json.gz',OLD/'REGISTERED_WINDOW.json',OLD/'FINDINGS.json',R/'common_simulator/v1/profiles.cjs',
        A/'experiments/a24_s26_common_20261020/PROFILES.json']
    write(O/'REGISTRATION.json',{'utc':datetime.now(timezone.utc).isoformat(),'HEAD':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),
        'dirty_worktree':True,'sources':[pin(p) for p in dict.fromkeys(paths)],'inputs':pin(O/'INPUTS.json'),'source_decoded_sha256':source['sha256'],
        'folds':folds,'fit_limit':336,'policy_environments':0,'device_measurements':0,'fresh_confirmation':False})
    print(json.dumps({'status':'PREPARED','groups':{f:len({c['group'] for c in cases if c['family']==f}) for f in folds},'fold_sizes':{f:[sum(c['group'] in g for c in cases) for g in fold] for f,fold in folds.items()}},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
