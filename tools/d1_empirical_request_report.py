"""Small PC comparison artifacts from an existing run; never fit or resimulate."""
import argparse
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from tools import d1_empirical_request_policy as p


def save_csv(path, rows):
    with path.open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def save_svg(fig, path):
    fig.savefig(path)
    path.write_text('\n'.join(line.rstrip() for line in path.read_text(encoding='utf8').splitlines())+'\n',encoding='utf8')


def report(folder):
    folder=Path(folder)
    summary=json.loads((folder/'summary.json').read_text(encoding='utf8'))
    original=json.loads((folder/'local_decisions.json').read_text(encoding='utf8'))
    frozen,case=p.inputs(p.BUNDLE)
    rows=summary['results']; differences=[]
    for name in ('low','queue','burst','sustained'):
        for scenario in ('mean','short_context','long_context'):
            group={r['policy']:r for r in rows if r['workload']==name and r['service_scenario']==scenario}
            a=group['ENERGY_AP_REQUEST_V1']
            for baseline in ('CPU_REFERENCE','SPLIT_REFERENCE','EFT_REFERENCE'):
                b=group[baseline]
                differences.append(dict(workload=name,service_scenario=scenario,baseline=baseline,
                    candidate_minus_reference_j=a['energy_120s_j']-b['energy_120s_j'],
                    candidate_minus_reference_peak_ap_c=a['peak_ap_35_180_c']-b['peak_ap_35_180_c'],
                    candidate_minus_reference_urgent_p95_ms=a['urgent_p95_ms']-b['urgent_p95_ms'],
                    candidate_deadline_met=a['deadline_met'],reference_deadline_met=b['deadline_met'],
                    planned=a['planned'],candidate_all_deadlines=a['deadline_met']==a['planned'],
                    reference_all_deadlines=b['deadline_met']==b['planned'],
                    measured_policy_effect=False))
    save_csv(folder/'differences.csv',differences)
    ledgers=[];energy=[]; decisions=[]
    for run in original:
        name,policy=run['workload'],run['policy']
        for r in run['ledger']:
            ledgers.append(dict(workload=name,policy=policy,request_id=r['id'],task=r['task'],priority=r['priority'],
                backend=r.get('backend'),status=r['status'],arrival_s=r['arrival_ns']/1e9,
                dispatch_s=r.get('dispatch_ns',0)/1e9 if 'dispatch_ns' in r else None,
                output_ready_s=r.get('output_ready_ns',0)/1e9 if 'output_ready_ns' in r else None,
                persist_s=r.get('persist_complete_ns',0)/1e9 if 'persist_complete_ns' in r else None,
                worker_release_s=r.get('worker_release_ns',0)/1e9 if 'worker_release_ns' in r else None,
                lane_available_s=r.get('lane_available_ns',0)/1e9 if 'lane_available_ns' in r else None))
        _,costs,end=p.account(dict(ledger=run['ledger']),case['initial'],frozen)
        expected=next(r for r in rows if r['service_scenario']=='mean' and r['workload']==name and r['policy']==policy)
        if abs(costs['whole_120s_j']-expected['energy_120s_j'])>1e-9: raise ValueError('reproduction energy mismatch')
        energy.extend(dict(workload=name,policy=policy,t_s=x['common_s'],predicted_j=x['predicted_j']) for x in costs['energy_path'])
        if policy=='ENERGY_AP_REQUEST_V1':
            decisions.extend(dict(workload=name,now_s=d['now_ns']/1e9,head=d.get('head_request_id'),
                selected_request=None if d['selected'] is None else d['selected']['request_id'],
                selected_backend=None if d['selected'] is None else d['selected']['backend'],
                reason=d['reason'],chosen_delay_s=d.get('chosen_explicit_delay_s'),
                forecast_start_s=d.get('planned_start_s'),modeled_ap_c=d.get('modeled_ap_c')) for d in run['decisions'])
    save_csv(folder/'request_ledger.csv',ledgers);save_csv(folder/'predicted_energy.csv',energy)
    save_csv(folder/'decision_summary.csv',decisions)
    labels={'CPU_REFERENCE':'CPU','SPLIT_SERIAL_REFERENCE':'split serial','SPLIT_REFERENCE':'split parallel',
        'EFT_REFERENCE':'EFT','ENERGY_AP_REQUEST_V1':'J/AP candidate'}
    colors=dict(zip(p.POLICIES,('#777777','#bb9999','#2171b5','#2ca25f','#cc4c02')))
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    tags=dict(zip(p.POLICIES,('CPU','SS','SP','EFT','J/AP')))
    offsets=dict(zip(p.POLICIES,(-14,-14,2,16,8)))
    for ax,name in zip(axes.flat,('low','queue','burst','sustained')):
        for r in (r for r in rows if r['workload']==name and r['service_scenario']=='mean'):
            if r['peak_ap_35_180_c'] is None: continue
            ax.scatter(r['energy_120s_j'],r['peak_ap_35_180_c'],color=colors[r['policy']],s=65)
            ax.annotate(tags[r['policy']]+f" ({r['deadline_met']}/{r['planned']})",
                        (r['energy_120s_j'],r['peak_ap_35_180_c']),xytext=(4,offsets[r['policy']]),textcoords='offset points',fontsize=8)
        ax.set_title(name+' / complete-work model predictions');ax.set_xlabel('Predicted whole-device J, 0-120 s')
        ax.set_ylabel('Predicted AP peak, 35-180 s (C)');ax.margins(.30);ax.grid(alpha=.2)
    fig.suptitle('PC predictions only; labels = deadline counts; SS/SP = fixed split serial/parallel\nMeasured coefficients + service-transfer assumptions; no independently validated policy superiority',fontsize=11)
    fig.savefig(folder/'tradeoffs.png',dpi=150);save_svg(fig,folder/'tradeoffs.svg');plt.close(fig)
    fig,axes=plt.subplots(3,1,figsize=(12,9),layout='constrained')
    with (folder/'predicted_ap.csv').open(encoding='utf8') as f:aps=list(csv.DictReader(f))
    for policy in ('SPLIT_REFERENCE','EFT_REFERENCE','ENERGY_AP_REQUEST_V1'):
        er=[r for r in energy if r['workload']=='sustained' and r['policy']==policy]
        ar=[r for r in aps if r['workload']=='sustained' and r['policy']==policy]
        axes[0].plot([r['t_s'] for r in er],[r['predicted_j'] for r in er],label=labels[policy],color=colors[policy])
        axes[1].plot([float(r['t_s']) for r in ar],[float(r['predicted_ap_c']) for r in ar],label=labels[policy],color=colors[policy])
    for i,policy in enumerate(('EFT_REFERENCE','ENERGY_AP_REQUEST_V1')):
        for j,b in enumerate(('CPU','GPU')):
            jobs=[r for r in ledgers if r['workload']=='sustained' and r['policy']==policy and r['backend']==b and r['lane_available_s'] is not None]
            axes[2].broken_barh([(r['dispatch_s'],r['lane_available_s']-r['dispatch_s']) for r in jobs],(i*3+j,.8),facecolors=colors[policy])
    axes[2].set_yticks([0.4,1.4,3.4,4.4],['EFT CPU','EFT GPU','candidate CPU','candidate GPU'])
    axes[2].set_xlim(35,120);axes[2].set_xlabel('Common time (s), modeled dispatch through lane release')
    axes[0].set_ylabel('Cumulative J');axes[1].set_ylabel('AP (C)')
    for ax in axes[:2]:ax.legend();ax.grid(alpha=.2);ax.set_xlabel('Common time (s)')
    fig.suptitle('Sustained192: PC schedules and predictions only\nCandidate trades response delay for modeled J/AP; no new device observations')
    fig.savefig(folder/'sustained_paths.png',dpi=150);save_svg(fig,folder/'sustained_paths.svg');plt.close(fig)
    html=folder/'index.html';text=html.read_text(encoding='utf8')
    if '<!--PC_FIGURES-->' not in text:
        text=text.replace('<table>','<!--PC_FIGURES--><p><a href="differences.csv">기준선별 차이</a> · <a href="request_ledger.csv">요청별 일정</a> · <a href="decision_summary.csv">배정·대기 결정</a></p><p>그림은 PC 계산이며 새 관측 자료가 아닙니다. 괄호는 전체 예정 요청 중 기한 준수 수입니다. 미완료 split serial의 180초 AP는 공란입니다.</p><img src="tradeoffs.png" style="max-width:100%" alt="PC service and J AP tradeoffs"><img src="sustained_paths.png" style="max-width:100%" alt="PC predicted energy AP and lane schedules"><table>',1)
        html.write_text(text,encoding='utf8')
    return dict(comparisons=len(rows),differences=len(differences),ledger_rows=len(ledgers),
        decision_rows=len(decisions),energy_paths_reproduced=20,device_commands=0)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True)
    print(json.dumps(report(parser.parse_args().folder),indent=2))
