"""Saved-only scientific brackets; an upper bound is not an achieved gain."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main(out):
    out=Path(out);data=json.loads((out/'EVALUATION.json').read_text(encoding='utf-8'));rows=data['rows'];bounds=data['bounds']
    ids=list(dict.fromkeys(r['case'] for r in rows));fig,axes=plt.subplots(2,2,figsize=(12,7),layout='constrained')
    for col,tier in enumerate(('EDF','STRONG')):
        achievedE=[];achievedT=[];upperE=[];upperT=[];labels=[]
        for cid in ids:
            local=[r for r in rows if r['case']==cid and r['source']!='P0'];ref=next(r for r in local if r['source']=='ORIGINAL' and r['policy']=='EDF')
            be=next(b for b in bounds if b['case']==cid and b['tier']==tier and b['kind']=='energy')
            bt=next(b for b in bounds if b['case']==cid and b['tier']==tier and b['kind']=='temperature')
            eligible=[r for r in local if r['completion'] is not None and r['original']['incomplete']==r['original']['response_missing']==0 and all(r['original'][k]>=v for k,v in be['targets'].items())]
            same=[r for r in eligible if r['same_work_common_eligible']]
            achievedE.append(100*(1-min(r['completion']['total_J_proxy'] for r in eligible)/ref['completion']['total_J_proxy']))
            achievedT.append(ref['common']['mean_AP_c']-min(r['common']['mean_AP_c'] for r in same))
            upperE.append(be['maximum_reduction']);upperT.append(bt['maximum_reduction'])
            labels.append(str(ref['condition']['rate_multiplier'])+('D' if ref['condition']['pattern']=='staggered_wave' else 'C'))
        for ax,a,b,title,y in [(axes[0,col],achievedE,upperE,'Completion energy','Saving vs EDF (%)'),(axes[1,col],achievedT,upperT,'Same-work common-window temperature','Reduction vs EDF (C)')]:
            ax.plot(range(10),b,'o--',color='#7d8792',label='Optimistic upper bound')
            ax.plot(range(10),a,'s-',color='#1b9e77',label='Best found feasible schedule')
            ax.set(title=title+' - '+tier+' SLA',ylabel=y,xticks=range(10),xticklabels=labels);ax.axhline(0,color='#444',linewidth=.6);ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('A24 frozen-model headroom: found gains and conservative limits\nD: dispersed, C: clustered. STRONG preserves both EDF and RL on-time counts.',fontsize=12)
    fig.savefig(out/'HEADROOM.png',dpi=170);fig.savefig(out/'HEADROOM.svg');plt.close(fig)
    print('SAVED_HEADROOM_FIGURES',flush=True)
