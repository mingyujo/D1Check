"""Standalone scientific figures from audited saved outcomes only."""
from pathlib import Path
import gzip
import hashlib
import json
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent


def read(path):
    b=path.read_bytes();return json.loads(gzip.decompress(b) if path.suffix=='.gz' else b)


def main():
    op=read(HERE/'OPERATION.json');out=ROOT/op['output_dir'];a=read(out/'ANALYSIS.json')
    r=read(out/'RESULT.json');audit=read(out/'AUDIT.json')
    if audit['result_sha256']!=hashlib.sha256((out/'RESULT.json').read_bytes()).hexdigest():raise ValueError('Audited bytes required')
    targets=[out/'POLICY_COMPARISON.png',out/'FIXED_HOT_CASE_GANTT.png']
    if any(p.exists() for p in targets):raise ValueError('Preserve completed figure outputs')
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'#ffffff'})
    names=[m['policy'] for m in a['means']];x=np.arange(len(names));colors=['#46546d' if not n.startswith('RL') else '#307dad' for n in names]
    fig,axes=plt.subplots(2,2,figsize=(13,9),constrained_layout=True)
    ax=axes[0,0]
    ax.bar(x,[m['mean_total_J_proxy'] for m in a['means']],color='#dbe3ed',label='Total')
    ax.bar(x,[m['mean_increment_J_proxy'] for m in a['means']],color=colors,label='Work increment')
    ax.set_ylabel('Conditional proxy J*');ax.set_title('Energy: same fixed window for every policy');ax.legend(frameon=False)
    ax=axes[0,1]
    for T,col in ((26,'#3889bd'),(39,'#d77c36')):
        values=[next(z for z in a['byTemperature'] if z['policy']==n and z['initial_T']==T)['mean_AP_c'] for n in names]
        ax.plot(x,values,'o-',color=col,label=f'Initial thermal proxy {T} C')
    ax.set_ylabel('Mean thermal proxy (C)');ax.set_title('Cool and hot conditions shown separately');ax.legend(frameon=False)
    ax=axes[1,0]
    rates=[100*m['on_time']/m['planned'] for m in a['means']]
    ax.bar(x,rates,color=colors);ax.set_ylim(0,105);ax.set_ylabel('On-time / ALL planned requests (%)')
    for i,(p,m) in enumerate(zip(rates,a['means'])):ax.text(i,p+1.5,f"{m['on_time']}/{m['planned']}",ha='center',fontsize=8)
    ax.set_title('Missing and late requests remain in the denominator')
    ax=axes[1,1];t=a['trajectories'];xx=np.arange(len(t));w=.25
    ax.bar(xx-w,[100*z['route_changed']/z['planned'] for z in t],w,label='Request route changed')
    ax.bar(xx,[100*z['dispatch_clock_changed']/z['planned'] for z in t],w,label='Dispatch time changed')
    ax.bar(xx+w,[100*z['same_state_differs_from_exact']/max(1,z['informative_decisions']) for z in t],w,label='Same-state action differs')
    ax.set_xticks(xx,[str(z['seed']) for z in t]);ax.set_ylim(0,105);ax.set_ylabel('Difference from EXACT without NN (%)')
    ax.set_title('Neural contribution: all three seeds');ax.legend(frameon=False,fontsize=8)
    for ax in axes.flat:
        ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    for ax in (axes[0,0],axes[0,1],axes[1,0]):ax.set_xticks(x,names,rotation=30,ha='right')
    fig.suptitle('Coupled 3/4/5 research model: 12 saved conditions, explicit thermal/power assumptions\nSimulation proxies; not calibrated A24 energy or physical superiority',fontsize=13)
    fig.savefig(targets[0],dpi=170);plt.close(fig)
    # Recipe chosen before outcomes: hot C50 clustered96, same latent potentials.
    chosen='FRESH_09';policies=['EDF','EXACT',a['selected_name']]
    fig,(ax,temperature)=plt.subplots(2,1,figsize=(14,7),gridspec_kw={'height_ratios':[2,1]},constrained_layout=True)
    ticks=[];ticklabels=[]
    for i,policy in enumerate(policies):
        row=next(z for z in r['rows'] if z['kind']=='FRESH' and z['case']==chosen and (z['policy']==policy or z['policy']=='RL' and policy=='RL_S'+z['label'].split('_S')[-1]))
        raw=read(out/(row['label']+'.raw.json.gz'));pred=raw['result']
        for lane,route in enumerate(('CPU','GPU')):
            y=2*i+lane;ticks.append(y);ticklabels.append(policy+' / '+route)
            for q in pred['requests']:
                if q['route']!=route or q['dispatch_ns'] is None:continue
                start=q['dispatch_ns']/1e9-35
                # A still-owned lane ends at the observed trace boundary;
                # never invent an AVAILABLE time for a censored request.
                end=(q['available_ns'] if q['available_ns'] is not None else pred['trace'][-1]['end_ns'])/1e9-35
                ax.broken_barh([(start,max(0,end-start))],(y-.32,.64),facecolors='#3889bd' if q['task']=='C' else '#da8a3e',edgecolors='white',linewidth=.2)
        t=[tr['start_ns']/1e9-35 for tr in pred['trace']];v=[tr['state']['temperature_c'] for tr in pred['trace']]
        temperature.plot(t,v,label=policy,lw=1.5)
    ax.set_yticks(ticks,ticklabels);ax.invert_yaxis();ax.set_xlabel('Seconds since first arrival');ax.grid(axis='x',alpha=.15)
    ax.set_title('Preselected hot C50 clustered96 recipe: classification blue, detection orange')
    temperature.set_xlabel('Seconds since first arrival');temperature.set_ylabel('Thermal proxy (C)');temperature.legend(frameon=False,ncol=3);temperature.grid(alpha=.15)
    fig.suptitle('Same input and latent work potentials; only the scheduling policy changes',fontsize=12)
    fig.savefig(targets[1],dpi=170);plt.close(fig)
    meta=dict(status='FIGURES_SAVED',new_environment_START=0,source_analysis_sha256=hashlib.sha256((out/'ANALYSIS.json').read_bytes()).hexdigest(),
        fixed_illustration_case='FRESH_09',case_selected_before_outcomes=True,
        files=[dict(path=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in targets])
    with (out/'FIGURES.json').open('x',encoding='utf-8') as f:json.dump(meta,f,indent=2)
    print(json.dumps(meta))


if __name__=='__main__':main()
