"""Static scientific plots from audited saved metrics; no new environment."""
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main(out):
    rows=json.loads((out/'WORK_METRICS.json').read_text(encoding='utf8'))['rows'];primary=[r for r in rows if r['family']=='THROTTLE'];levels=sorted({r['k'] for r in primary});policies=['EDF','FIFO','PACKING_PUBLIC','FROZEN_EVENT_JOINT'];names=['EDF','FIFO','Public rule','Frozen RL'];fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
    for policy,name in zip(policies,names):
        data=[]
        for k in levels:
            a=[r for r in primary if r['policy']==policy and r['k']==k];refs=[next(q for q in primary if q['scenario']==r['scenario'] and q['case']==r['case'] and q['policy']=='EDF') for r in a];n=sum(r['n'] for r in a);u=sum(r['original']['urgent_planned'] for r in a)
            E=100*(1-sum(r['completion']['total_J_proxy'] for r in a)/sum(r['completion']['total_J_proxy'] for r in refs)) if all(r['completion'] is not None for r in a+refs) else float('nan')
            data.append((100*sum(r['original']['on_time'] for r in a)/n,100*sum(r['original']['urgent_on_time'] for r in a)/u,E,sum(r['common']['mean_AP_c']-b['common']['mean_AP_c'] for r,b in zip(a,refs))/len(a)))
        for ax,i in zip(axes.flat,range(4)):ax.plot(levels,[v[i] for v in data],marker='o',label=name)
    for ax,title in zip(axes.flat,['On-time / all planned (%)','Urgent on-time / urgent planned (%)','Completion energy saving vs EDF (%)','Mean AP minus EDF (C)']):
        ax.set(xscale='log',xlabel='Throttle slope multiplier k',ylabel=title);ax.set_xticks(levels,[str(k) for k in levels]);ax.grid(alpha=.25)
    axes[1,0].axhline(0,color='black',lw=.6);axes[1,1].axhline(0,color='black',lw=.6);axes[0,0].legend(fontsize=8);fig.suptitle('Virtual thermal sensitivity: fixed 30 workloads and fixed NN\nk=1 is the original A24 hypothesis; energy/AP are model proxies',fontsize=12)
    fig.savefig(out/'THERMAL_SENSITIVITY.png',dpi=160);fig.savefig(out/'THERMAL_SENSITIVITY.svg');plt.close(fig)
