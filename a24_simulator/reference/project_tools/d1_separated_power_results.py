"""Post-freeze diagnostics only; no fitting, device calls or sample exclusion."""
import argparse
import csv
from collections import defaultdict
from pathlib import Path
from tools import d1_online_policy_model as m
from tools import d1_online_policy_readout as shared


def export(root,output):
    root,output=Path(root),Path(output)
    frozen=m.p.read(root/'model_freeze.json');cases=m.p.read(root/'confirmation_cases.json')
    evaluations=m.p.read(root/'confirmation_evaluation.json')
    if len(cases)!=6 or len(evaluations)!=6:raise ValueError('complete independent block required')
    by_id={r['id']:r for r in evaluations};windows=[];residuals=[];context=[]
    for c in cases:
        evaluation=by_id[c['id']]
        segments=c['inputs']['segments'];pred=evaluation['outputs']['actual_schedule_conditional']
        durations=defaultdict(float)
        for s in segments:durations[s['state']]+=max(0,min(120,s['end_s'])-max(0,s['start_s']))
        context.append(dict(id=c['id'],initial_ap_c=c['common_start_ap_c'],preload_w=c['preload_power_w'],last_lane_s=c['last_lane_s'],
                            post_lane_w=m.energy_at(c,c['last_lane_s'],120)/(120-c['last_lane_s']),
                            overlap_seconds=sum(v for k,v in durations.items() if '+' in k),power_samples=len(c['power_samples']),
                            AP_samples=len(c['observed_ap_c'])))
        signed=[]
        for a in range(0,120,5):
            b=a+5;obs=m.energy_at(c,a,b)
            predicted=pred['energy_path'][b]['predicted_j']-pred['energy_path'][a]['predicted_j']
            states=sorted({s['state'] for s in segments if min(b,s['end_s'])>max(a,s['start_s'])})
            error=predicted-obs;signed.append(error)
            windows.append(dict(id=c['id'],start_s=a,end_s=b,states='|'.join(states),mixed=len(states)>1,
                                observed_j=obs,predicted_j=predicted,signed_error_j=error))
        total=sum(signed)
        if abs(total-evaluation['outputs']['actual_schedule_conditional']['energy_signed_error_j'])>1e-6:raise ValueError('energy partition closure')
        residuals.append(dict(id=c['id'],signed_error_j=total,positive_windows_j=sum(x for x in signed if x>0),
                              negative_windows_j=sum(x for x in signed if x<0),sum_absolute_window_error_j=sum(abs(x) for x in signed)))
    output.mkdir(parents=True,exist_ok=False)
    for name,rows in [('windows.csv',windows),('cancellation.csv',residuals),('initial_and_occupancy.csv',context)]:
        with (output/name).open('w',encoding='utf8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    shared.write(output/'scope.json',dict(source_freeze_sha256=m.p.digest(root/'model_freeze.json'),independent_confirmation_sessions=6,
        refits=0,exclusions=0,device_commands=0,experiment_ready=False,accuracy_pass=None,
        interpretation='Five-second arithmetic residuals, not causal device background attribution or per-request power identification'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,2,figsize=(12,8),constrained_layout=True)
    for c,ax in zip(cases,axes.flat):
        rows=[r for r in windows if r['id']==c['id']]
        ax.step([r['start_s'] for r in rows],[r['observed_j']/5 for r in rows],where='post',label='observed 5s mean W')
        ax.step([r['start_s'] for r in rows],[r['predicted_j']/5 for r in rows],where='post',label='frozen conditional W')
        ax.axvline(c['last_lane_s'],color='grey',linestyle=':',label='last lane release')
        ax.set(title=c['id'].replace('confirmation_',''),xlabel='Common seconds',ylabel='Whole-device W');ax.legend(fontsize=7)
    svg=output/'five_second_power.svg';fig.savefig(svg);plt.close(fig)
    svg.write_text('\n'.join(x.rstrip() for x in svg.read_text(encoding='utf8').splitlines())+'\n',encoding='utf8')
    return dict(output=str(output),windows=len(windows),device_commands=0)


if __name__=='__main__':
    q=argparse.ArgumentParser();q.add_argument('--root',required=True);q.add_argument('--output',required=True);a=q.parse_args()
    print(export(a.root,a.output))
