"""Compare all registered alternatives, accounting and host cost; never run a device."""
import argparse
import html
import json
from pathlib import Path
import statistics as stat
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from tools import d1_scheduler_alternatives as a
from tools import d1_request_ppo_report as prior


def compare(rows):
    rows=[r for r in rows if r['stage']=='test']
    index={(r['trace_seed'],r['family'],r['scenario'],r['policy']):r for r in rows}
    result=[]
    for r in rows:
        ref=index[(r['trace_seed'],r['family'],r['scenario'],'EFT_REFERENCE')]
        complete=r['completed']==r['planned']
        thermal=r['thermal_degree_seconds'] is not None and ref['thermal_degree_seconds'] is not None
        service=complete and all(r[k]<=ref[k] for k in ('urgent_service_failure','normal_service_failure'))
        energy=r['energy_j']<=ref['energy_j']+1e-8
        heat=thermal and r['thermal_degree_seconds']<=ref['thermal_degree_seconds']+1e-8 and r['peak_ap_c']<=ref['peak_ap_c']+1e-8
        result.append(dict(trace_seed=r['trace_seed'],family=r['family'],scenario=r['scenario'],policy=r['policy'],
            delta_j=r['energy_j']-ref['energy_j'],
            delta_ap_area=r['thermal_degree_seconds']-ref['thermal_degree_seconds'] if thermal else None,
            delta_peak=r['peak_ap_c']-ref['peak_ap_c'] if thermal else None,
            delta_p95=r['urgent_p95_ms']-ref['urgent_p95_ms'] if r['urgent_p95_ms'] is not None and ref['urgent_p95_ms'] is not None else None,
            deadline_gain=r['deadline_met']-ref['deadline_met'],service_not_worse=service,
            j_not_worse=energy,heat_not_worse=heat,all_guard=service and energy and heat,
            strict_model_improvement=service and energy and heat and (r['energy_j']<ref['energy_j']-1e-8 or
                (thermal and r['thermal_degree_seconds']<ref['thermal_degree_seconds']-1e-8) or r['deadline_met']>ref['deadline_met']),
            eft_gap_to_relaxation_j=ref['gap_to_relaxed_bound_j'],candidate_gap_to_relaxation_j=r['gap_to_relaxed_bound_j']))
    return result


def summarize(rows,differences):
    result=[]
    for family in [*a.old.FAMILIES,'all']:
        for policy in dict.fromkeys(r['policy'] for r in rows if r['stage']=='test'):
            rr=[r for r in rows if r['stage']=='test' and r['policy']==policy and (family=='all' or r['family']==family)]
            ds=[r for r in differences if r['policy']==policy and (family=='all' or r['family']==family)]
            def avg(data,k):return stat.mean(x[k] for x in data) if all(x[k] is not None for x in data) else None
            result.append(dict(family=family,policy=policy,conditions=len(rr),arrival_seeds=len({r['trace_seed'] for r in rr}),
                planned=sum(r['planned'] for r in rr),completed=sum(r['completed'] for r in rr),deadline_met=sum(r['deadline_met'] for r in rr),
                delta_j=avg(ds,'delta_j'),delta_ap_area=avg(ds,'delta_ap_area'),delta_peak=avg(ds,'delta_peak'),delta_p95=avg(ds,'delta_p95'),
                service_worse=sum(not x['service_not_worse'] for x in ds),j_worse=sum(not x['j_not_worse'] for x in ds),
                heat_worse=sum(not x['heat_not_worse'] for x in ds),all_guard=sum(x['all_guard'] for x in ds),
                strict_model_improvement=sum(x['strict_model_improvement'] for x in ds),
                eft_improvement_ceiling_j=avg(ds,'eft_gap_to_relaxation_j'),
                candidate_gap_to_bound_j=avg(ds,'candidate_gap_to_relaxation_j'),
                host_callback_total_s=sum(r['decision_host_total_s'] for r in rr) if all(r.get('decision_host_total_s') is not None for r in rr) else None,
                mean_host_callback_p95_ms=avg(rr,'decision_host_p95_ms') if all('decision_host_p95_ms' in r for r in rr) else None,
                max_host_callback_ms=max(r['decision_host_max_ms'] for r in rr) if all(r.get('decision_host_max_ms') is not None for r in rr) else None))
    return result


def report(folder):
    folder=Path(folder);rows=prior.read_csv(folder/'results.csv');summary=json.loads((folder/'summary.json').read_text())
    freeze=json.loads((folder/'freeze_before_test.json').read_text());reg=json.loads((folder/'preregistered.json').read_text())
    assert len(rows)==1440 and sum(r['stage']=='test' for r in rows)==1056
    assert reg['utc']<freeze['utc'] and summary['selected_for_followup']==freeze['selected']
    ds=compare(rows);groups=summarize(rows,ds)
    a.old.csv_write(folder/'paired_vs_eft.csv',ds);a.old.csv_write(folder/'aggregate.csv',groups)
    rawstats=dict(conditions=1056,complete_cases=sum(r['completed']==r['planned'] for r in rows if r['stage']=='test'),
        selected_before_test=freeze['selected'],simulation_is_not_device_validation=True,
        selected_summary=next(r for r in groups if r['family']=='all' and r['policy']==freeze['selected']))
    a.p.write(folder/'decision.json',rawstats)
    policies=[*a.p.ALTERNATIVE_POLICIES,'PPO_seed11','PPO_seed23','PPO_seed37']
    short=['ECO EDF','LLF EFT','Backfill','Energy MPC','Thermal MPC','PPO11','PPO23','PPO37']
    fig,axes=plt.subplots(1,3,figsize=(15,5))
    for ax,metric,title in zip(axes,['delta_j','delta_ap_area','delta_p95'],['J: policy - EFT','AP burden (C s): policy - EFT','Urgent P95 (ms): policy - EFT']):
        vals=[next(r for r in groups if r['family']=='all' and r['policy']==p)[metric] for p in policies]
        ax.barh(short,vals);ax.axvline(0,color='black',lw=.8);ax.set_title(title,fontsize=10);ax.grid(axis='x',alpha=.2)
    fig.suptitle('Frozen-model exploration: 96 test conditions; averages do not guarantee per-case constraints')
    fig.tight_layout(rect=(0,0,1,.94));prior.figure_save(fig,folder,'policy_tradeoffs')
    fig,ax=plt.subplots(figsize=(10,5));width=.25;x=np.arange(len(policies))
    for offset,key,label in [(-1,'service_worse','Service worse'),(0,'heat_worse','Heat worse'),(1,'j_worse','J worse')]:
        ax.bar(x+offset*width,[next(r for r in groups if r['family']=='all' and r['policy']==p)[key] for p in policies],width,label=label)
    ax.set_xticks(x,short,rotation=20);ax.set_ylabel('Conditions out of 96');ax.legend();ax.grid(axis='y',alpha=.2)
    ax.set_title('Per-case violations vs EFT (model comparison, not accuracy certification)')
    fig.tight_layout();prior.figure_save(fig,folder,'constraint_cases')
    fig,axes=plt.subplots(1,2,figsize=(12,4.8))
    for policy,label in zip(policies[:5],short[:5]):
        vals=[next(r for r in groups if r['family']==f and r['policy']==policy)['delta_j'] for f in a.old.FAMILIES]
        axes[0].plot(a.old.FAMILIES,vals,marker='o',label=label)
    axes[0].axhline(0,color='black',lw=.8);axes[0].legend(fontsize=8);axes[0].set_title('J change by workload; no favorable subset removed')
    bound=[next(r for r in groups if r['family']==f and r['policy']=='EFT_REFERENCE')['eft_improvement_ceiling_j'] for f in a.old.FAMILIES]
    axes[1].bar(a.old.FAMILIES,bound);axes[1].set_title('EFT J - relaxed energy lower bound');axes[1].set_ylabel('J: optimistic improvement ceiling, NOT achievable saving')
    fig.tight_layout();prior.figure_save(fig,folder,'workload_and_ceiling')
    cols=['family','policy','conditions','deadline_met','planned','delta_j','delta_ap_area','delta_peak','delta_p95','service_worse','heat_worse','j_worse','all_guard','mean_host_callback_p95_ms']
    def table(rs):
        return '<table><tr>'+''.join('<th>'+k+'</th>' for k in cols)+'</tr>'+''.join('<tr>'+''.join('<td>'+html.escape(str(r[k]))+'</td>' for k in cols)+'</tr>' for r in rs)+'</table>'
    text='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>비RL 스케줄링 비교</title><style>body{font:15px system-ui;margin:24px;color:#234}img{max-width:100%}table{border-collapse:collapse;font-size:12px}td,th{border:1px solid #bbb;padding:5px}.scroll{overflow:auto}.note{padding:16px;background:#fff0d0}</style><h1>강화학습 외 스케줄링5종: 개발 후 동결·별도 PC 평가</h1><p class="note">실측 모형과 공통 처리시간 전이 가정에 따른 계산입니다. 새 실기기 절감이나 정확도 PASS가 아닙니다. 기한 충족과 완료, 에너지와 열 상충, 평균과 조건별 손해를 나눠 읽습니다. 계산비용은 PC callback wall time이며 시뮬레이터의 추가 정책 비용0 가정 밖입니다.</p><p><a href="../README.md">설계·결론·재현</a> · <a href="results.csv">개발/시험1440행</a> · <a href="paired_vs_eft.csv">대응차이</a> · <a href="freeze_before_test.json">시험 전 선정</a></p>'''
    text+='<p>개발에서 고정한 후속후보: <b>'+html.escape(freeze['selected'])+'</b>. 최종평가를 본 뒤 다른 후보로 갈아타거나 재조정하지 않았습니다.</p>'
    for name in ('policy_tradeoffs','constraint_cases','workload_and_ceiling'):text+=f'<img src="{name}.png" alt="{name}">'
    text+='<h2>전체 조건</h2><div class="scroll">'+table([r for r in groups if r['family']=='all'])+'</div><h2>입력별 결과</h2><div class="scroll">'+table([r for r in groups if r['family']!='all'])+'</div></html>'
    capacities=prior.read_csv(folder/'capacity_bounds.csv')
    capacity_summary=[]
    for family in a.old.FAMILIES:
        cs=[r for r in capacities if r['stage']=='test' and r['family']==family]
        capacity_summary.append(dict(family=family,conditions=len(cs),infeasible_count=sum(float(r['excess_s'])>1e-9 for r in cs),max_excess_s=max(float(r['excess_s']) for r in cs)))
    a.p.write(folder/'capacity_summary.json',capacity_summary)
    capacity_html='<h2>사후 원인 판독: 탐지 CPU의 기한 창 수요</h2><p>분류 작업과 응답 후 점유를 제거한 낙관적 필요조건입니다. 초과하면 현재 고정 처리시간 모형에서 모든 기한을 지킬 수 없습니다. 미초과는 가능성 증명이 아니며 실제 기기 용량 인증도 아닙니다. 이 분석으로 입력/계수/정책을 변경하지 않았습니다.</p><p><a href="capacity_bounds.csv">모든 시간창 위반 근거</a></p><table><tr><th>입력</th><th>모형상 불가능 조건</th><th>최대 CPU 수요 초과 s</th></tr>'
    for c in capacity_summary:capacity_html+=f'<tr><td>{c["family"]}</td><td>{c["infeasible_count"]}/{c["conditions"]}</td><td>{c["max_excess_s"]:.6f}</td></tr>'
    text=text.replace('</html>',capacity_html+'</table></html>')
    (folder/'index.html').write_text(text,encoding='utf8');return rawstats


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True);args=parser.parse_args();print(report(args.folder))
