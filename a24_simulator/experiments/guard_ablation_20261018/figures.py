"""Saved-only all-policy factorial plot; every mode/factor retained."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main(out):
    out=Path(out);rows=[r for r in json.loads((out/'EVALUATION.json').read_text())['rows'] if r['source']=='GUARD_ABLATION']
    fig,axes=plt.subplots(1,3,figsize=(14,4.5),layout='constrained');factors=[.5,1,1.5,2,3]
    for policy,color,marker in [('GUARD_ON_NN','#167d9a','o'),('GUARD_OFF_NN','#d45087','s'),('GUARD_ON_ZERO','#8c8c8c','^'),('GUARD_OFF_ZERO','#bf9d24','x')]:
        values=[[],[],[]]
        for factor in factors:
            g=[r for r in rows if r['policy']==policy and r['condition']['rate_multiplier']==factor]
            refs=[r for r in rows if r['policy']=='GUARD_ON_NN' and r['condition']['rate_multiplier']==factor]
            values[0].append(100*sum(r['original']['on_time'] for r in g)/sum(r['n'] for r in g))
            good=all(r['completion'] is not None for r in [*g,*refs])
            values[1].append(100*(1-sum(r['completion']['total_J_proxy'] for r in g)/sum(r['completion']['total_J_proxy'] for r in refs)) if good else float('nan'))
            values[2].append((sum(r['common']['mean_AP_c'] for r in refs)-sum(r['common']['mean_AP_c'] for r in g))/2)
        for i,ax in enumerate(axes):ax.plot(factors,values[i],marker=marker,color=color,label=policy,alpha=.9)
    for ax,title,y in zip(axes,['All-arrival on-time rate','Completion energy vs guard-on NN','Raw common-window temperature'],['On-time (%)','Saving (%)','Reduction vs guard-on NN (C)']):
        ax.set(title=title,xlabel='Workload density multiplier',ylabel=y,xticks=factors);ax.grid(alpha=.2);ax.axhline(0,linewidth=.6,color='#333')
    axes[0].legend(fontsize=7)
    fig.suptitle('Frozen neural policy: urgent-WAIT guard ON/OFF x learned/zero actor\nAll modes shown. SLA loss and common-window completion exclusions remain in the full table.',fontsize=11)
    fig.savefig(out/'GUARD_ABLATION.png',dpi=170);fig.savefig(out/'GUARD_ABLATION.svg');plt.close(fig)
