"""Frozen simulator, new bounded experiment; unique helper name avoids common imports."""
import sys
from pathlib import Path
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H.parent/'a24_s26_scale_20261022'))
from scale_common import *
H=Path(__file__).resolve().parent;O=A/'results/A24_S26_JOINT_20261022_01';V=A/'reviews/A24_S26_JOINT_20261022_01'
OLDH=A/'experiments/a24_s26_scale_20261022';OLDO=A/'results/A24_S26_SCALE_20261022_01'

def screen(rows):
    import math
    out=[]
    for sid in sorted({r['condition']['setting'] for r in rows}):
        rr=[r for r in rows if r['condition']['setting']==sid and r['condition']['role']=='DEV'];assert len(rr)==10
        bc=[r for r in rr if r['policy']==MODES[-1]];services=[];tests=[]
        for mix in [.5,.75]:
            b=next(r['metrics'] for r in bc if r['condition']['mix']==mix);services.append({'mix':mix,'all':b['service']['ALL']['on']/b['service']['ALL']['n'],'urgent':b['service']['U']['on']/b['service']['U']['n'],'missing':b['service']['ALL']['missing'],'incomplete':b['service']['ALL']['incomplete']})
            for p in MODES[:3]:
                a=next(r['metrics'] for r in rr if r['condition']['mix']==mix and r['policy']==p);tests.append({'mix':mix,'reference':p,'energy_saving_pct':100*(1-b['J']/a['J']),'AP_reduction_C':a['AP']-b['AP'],'on_change':b['service']['ALL']['on']/b['service']['ALL']['n']-a['service']['ALL']['on']/a['service']['ALL']['n']})
        gaps=[]
        for p in MODES[:3]:
            a=[r for r in rr if r['policy']==p];gaps.append({'reference':p,'all_gain_pp':100*(sum(r['metrics']['service']['ALL']['on'] for r in bc)/sum(r['metrics']['service']['ALL']['n'] for r in bc)-sum(r['metrics']['service']['ALL']['on'] for r in a)/sum(r['metrics']['service']['ALL']['n'] for r in a))})
        minU=min(s['urgent'] for s in services);allBC=sum(s['all'] for s in services)/2
        eligible=all(s['missing']==s['incomplete']==0 and s['all']>=.95 and s['urgent']>=.99 for s in services) and all(t['energy_saving_pct']>1e-9 and t['AP_reduction_C']>1e-9 and t['on_change']>=-1e-12 for t in tests) and all(g['all_gain_pp']>1e-9 for g in gaps)
        n=rr[0]['condition']['n'];tier=int(minU<1-1e-12);rank=[tier,-minU,-allBC,-min(g['all_gain_pp'] for g in gaps),-min(t['energy_saving_pct'] for t in tests),-min(t['AP_reduction_C'] for t in tests),-n,sid]
        out.append({'setting':sid,'n':n,'eligible':eligible,'service':services,'comparisons':tests,'aggregate_gaps':gaps,'rank':rank})
    return sorted(out,key=lambda x:(not x['eligible'],x['rank']))
