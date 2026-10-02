"""Descriptive ABBA measurement sensitivity, no fitted replacement model."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from tools import d1_arrival_plan as p
from tools import d1_online_policy_model as m
from tools import d1_online_power_diagnosis as diag


def paired_differences(rows):
    if [r['period_ms'] for r in rows]!=[1000,900,900,1000]:raise ValueError('not ABBA')
    result=[]
    for a,b in [(0,1),(3,2)]:
        result.append(dict(control=rows[a]['case'],dephased=rows[b]['case'],
            difference_900_minus_1000_j=rows[b]['observed_120s_j']-rows[a]['observed_120s_j'],
            future_difference_j=rows[b]['observed_35_120s_j']-rows[a]['observed_35_120s_j'],
            background_adjusted_difference_j=rows[b]['excess_35_120s_j']-rows[a]['excess_35_120s_j']))
    return result


def readout(planfile,output,model_freeze=None):
    planfile=Path(planfile);plan=p.read(planfile);root=Path(plan['output_root']);output=Path(output)
    receipt=p.read(root/'FINAL_RECEIPT.json')
    if receipt['status']!='completed_descriptive_only':raise ValueError('incomplete block; no completed comparison')
    bindings=[]
    if plan.get('imported_completed'):
        imported=plan['imported_completed']
        for f,digest in imported['files'].items():
            if p.digest(f)!=digest:raise ValueError('import changed')
        priorfile=Path(imported['plan']);prior=p.read(priorfile)
        bindings.extend((priorfile,prior,prior['entries'][i]) for i in imported['indices'])
    bindings.extend((planfile,plan,e) for e in plan['entries'])
    cases=[m.load_case(f,pl,e) for f,pl,e in bindings]
    rows=[];curves=[];phase_rows=[];model_rows=[];model_paths=[]
    frozen=p.read(model_freeze)['model'] if model_freeze else None
    for c,(file,source,e) in zip(cases,bindings):
        manifest=p.read(file.parent/e['manifest']);period=manifest['power_sample_period_ms']
        folder=Path(source['output_root'])/f"{e['index']:02d}_{e['session_id']}"
        events=m.logs.read_lines(folder/'artifacts/progress.jsonl')
        contracts=[x for x in events if x.get('kind')=='power_sampling_contract']
        if len(contracts)!=1 or contracts[0]['period_ms']!=period:raise ValueError('actual sampler contract absent/mismatch')
        ss=[s for s in c['power_samples'] if 0<=(s['mono_ns']-c['origin_ns'])/1e9<=120]
        tt=[(s['mono_ns']-c['origin_ns'])/1e9 for s in ss]
        phase=diag.phase_counts([t for t in tt if 35<=t<=80],2)
        phase_rows.extend(dict(case=c['id'],period_ms=period,bin=i,count=n) for i,n in enumerate(phase))
        rows.append(dict(case=c['id'],period_ms=period,requests=96,
            observed_120s_j=c['observed_120s_j'],observed_35_120s_j=m.energy_at(c,35,120),
            preload_w=c['preload_power_w'],post_idle_w=m.energy_at(c,90,120)/30,
            excess_35_120s_j=m.energy_at(c,35,120)-85*c['preload_power_w'],
            samples_120s=len(ss),max_sample_gap_s=max(np.diff(tt)),phase_bins=sum(n>0 for n in phase),
            sensor_read_elapsed_s=sum((s['sensor_read_end_ns']-s['snapshot_start_ns'])/1e9 for s in ss),
            parallel_s=sum(max(0,min(120,s['end_s'])-max(0,s['start_s'])) for s in c['inputs']['segments'] if '+' in s['state']),
            initial_ap_c=c['common_start_ap_c'],peak_post35_ap_c=max(c['observed_ap_c']),
            last_lane_s=c['last_lane_s']))
        for t in range(1,121):curves.append(dict(case=c['id'],period_ms=period,t=t,observed_j=m.energy_at(c,0,t)))
        if frozen is not None:
            initial=dict(preload=c['inputs']['preload'],preload_power_w=c['preload_power_w'])
            value=m.costs(c['inputs']['segments'],initial,c['inputs']['query_s'],frozen,c['inputs']['segments'][-1]['end_s'])
            model_rows.append(dict(case=c['id'],role='posthoc_protocol_transfer_not_training',period_ms=period,
                observed_j=c['observed_120s_j'],predicted_j=value['whole_120s_j'],signed_j=value['whole_120s_j']-c['observed_120s_j'],
                future_signed_j=value['prospective_35_120s_j']-m.energy_at(c,35,120),
                **m.common.score(c['observed_ap_c'],value['ap_path'])))
            model_paths.append(dict(case=c['id'],t=c['inputs']['query_s'],observed=c['observed_ap_c'],predicted=value['ap_path'],
                energy_residual=[v['predicted_j']-m.energy_at(c,0,v['common_s']) if v['common_s'] else 0. for v in value['energy_path']]))
    paired=paired_differences(rows)
    output.mkdir(parents=True,exist_ok=False)
    for name,data in [('sessions.csv',rows),('energy_paths.csv',curves),('phase_counts.csv',phase_rows),('paired_differences.csv',paired)]:
        with (output/name).open('w',newline='',encoding='utf8') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    summary=dict(plan_sha256=p.digest(planfile),receipt_sha256=p.digest(root/'FINAL_RECEIPT.json'),
        pairs=paired,fit_coefficients=0,independent_model_validation=False,experiment_ready=False,
        separate_blocks=bool(plan.get('imported_completed')),original_failed_session_preserved=bool(plan.get('imported_completed')),
        limits='Different query/record cost and session background/history remain; neither sampler is an absolute reference. No cause, corrected J, or accuracy PASS inferred.')
    if frozen is not None:
        summary['unchanged_model_sha256']=p.digest(model_freeze)
        with (output/'frozen_model_transfer.csv').open('w',newline='',encoding='utf8') as f:
            w=csv.DictWriter(f,fieldnames=list(model_rows[0]));w.writeheader();w.writerows(model_rows)
        (output/'frozen_model_paths.json').write_text(json.dumps(model_paths,indent=2)+'\n',encoding='utf8')
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(2,2,figsize=(12,8),constrained_layout=True)
    for i,c in enumerate(cases):
        label=f"{i+1}: {rows[i]['period_ms']} ms"
        v=[v for v in curves if v['case']==c['id']]
        axs[0,0].plot([v['t'] for v in v],[v['observed_j'] for v in v],label=label)
        axs[0,1].plot(c['inputs']['query_s'],c['observed_ap_c'],label=label)
        axs[1,0].plot(range(8),[v['count'] for v in phase_rows if v['case']==c['id']],marker='o',label=label)
    axs[1,1].bar(range(4),[r['observed_120s_j'] for r in rows]);axs[1,1].set_xticks(range(4),['1000','900','900','1000'])
    for ax,title in zip(axs.flat,['Observed cumulative J, 0..120s','Observed numeric AP, after35s','Sample phase of repeated 2s input cycle','Observed 120s J; ordered sessions']):
        ax.set_title(title);ax.grid(alpha=.2)
    axs[0,0].legend();fig.savefig(output/'sampling_comparison.svg');fig.savefig(output/'sampling_comparison.png',dpi=110);plt.close(fig)
    f=output/'sampling_comparison.svg';f.write_text('\n'.join(s.rstrip() for s in f.read_text(encoding='utf8').splitlines())+'\n',encoding='utf8')
    if model_paths:
        fig,axs=plt.subplots(4,2,figsize=(12,11),constrained_layout=True)
        for row,(c,axes) in enumerate(zip(model_paths,axs)):
            axes[0].plot(c['t'],c['observed'],label='observed');axes[0].plot(c['t'],c['predicted'],label='unchanged conditional model')
            axes[0].set_title(c['case']+' AP');axes[0].set_ylabel('Celsius');axes[0].legend(fontsize=7)
            axes[1].plot(range(121),c['energy_residual']);axes[1].axhline(0,color='grey');axes[1].set_title('Cumulative predicted - observed J')
            for ax in axes:ax.set_xlabel('common seconds');ax.grid(alpha=.2)
        fig.suptitle('Protocol-transfer diagnosis; actual schedule + pre35 inputs; no fit or accuracy PASS')
        fig.savefig(output/'frozen_model_transfer.svg');fig.savefig(output/'frozen_model_transfer.png',dpi=110);plt.close(fig)
        f=output/'frozen_model_transfer.svg';f.write_text('\n'.join(s.rstrip() for s in f.read_text(encoding='utf8').splitlines())+'\n',encoding='utf8')
    return summary


if __name__=='__main__':
    q=argparse.ArgumentParser();q.add_argument('--plan',required=True);q.add_argument('--output',required=True);q.add_argument('--model-freeze')
    a=q.parse_args();print(json.dumps(readout(a.plan,a.output,a.model_freeze),indent=2))
