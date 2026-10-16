"""Read-only-to-model reporting of the single frozen RL experiment."""
import argparse
import csv
import html
import json
import statistics
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from tools import d1_request_rl as rl


def report(folder):
    folder = Path(folder)
    summary = json.loads((folder/'summary.json').read_text(encoding='utf8'))
    rows = summary['results']
    with (folder/'comparison.csv').open(encoding='utf8',newline='') as f:
        csv_rows = list(csv.DictReader(f))
    if len(csv_rows)!=len(rows): raise ValueError('CSV denominator')
    for a,b in zip(rows,csv_rows):
        for key in ('energy_120s_j','deadline_met','planned','learned_decisions','unseen_fallbacks'):
            if float(a[key])!=float(b[key]): raise ValueError('CSV/JSON mismatch')
    if rl.p.digest(folder/'learned_table.json')!=summary['policy_sha256']:
        raise ValueError('policy hash mismatch')
    table = json.loads((folder/'learned_table.json').read_text(encoding='utf8'))['table']
    aggregate = []; differences = []
    for family in rl.FAMILIES:
        for policy in (*rl.BASELINES,rl.p.RL_POLICY):
            group=[r for r in rows if r['family']==family and r['policy']==policy]
            aggregate.append(dict(family=family,policy=policy,synthetic_conditions=len(group),
                distinct_arrival_traces=len({r['seed'] for r in group}),
                planned=sum(r['planned'] for r in group),completed=sum(r['completed'] for r in group),
                deadline_met=sum(r['deadline_met'] for r in group),
                mean_j=statistics.mean(r['energy_120s_j'] for r in group),
                mean_peak_ap_c=(statistics.mean(r['peak_ap_35_180_c'] for r in group)
                                if all(r['peak_ap_35_180_c'] is not None for r in group) else None),
                mean_urgent_p95_ms=statistics.mean(r['urgent_p95_ms'] for r in group)))
    for a in rows:
        if a['policy']!=rl.p.RL_POLICY: continue
        for baseline in rl.BASELINES:
            b=next(r for r in rows if (r['seed'],r['family'],r['scenario'],r['policy'])==
                   (a['seed'],a['family'],a['scenario'],baseline))
            both_complete=a['completed']==a['planned'] and b['completed']==b['planned']
            differences.append(dict(seed=a['seed'],family=a['family'],scenario=a['scenario'],baseline=baseline,
                equal_work_completed=both_complete,deadline_met_delta=a['deadline_met']-b['deadline_met'],
                energy_j_delta=a['energy_120s_j']-b['energy_120s_j'],
                peak_ap_delta=(a['peak_ap_35_180_c']-b['peak_ap_35_180_c']
                    if a['peak_ap_35_180_c'] is not None and b['peak_ap_35_180_c'] is not None else None),
                urgent_p95_ms_delta=a['urgent_p95_ms']-b['urgent_p95_ms']))
    rl.csv_write(folder/'aggregate.csv',aggregate);rl.csv_write(folder/'differences.csv',differences)
    ns=[r['n'] for actions in table.values() for r in actions.values()]
    diagnostics=dict(states=len(table),state_action_pairs=len(ns),
        states_only_one_action=sum(len(a)==1 for a in table.values()),
        state_action_visits_min=min(ns),state_action_visits_median=statistics.median(ns),
        state_action_visits_max=max(ns),
        learned_decisions=sum(r['learned_decisions'] for r in rows),
        unseen_fallbacks=sum(r['unseen_fallbacks'] for r in rows),
        wait_decisions=sum(r['wait_decisions'] for r in rows),
        visitation_is_not_convergence=True,independent_device_validation=False)
    rl.p.write(folder/'learning_diagnostics.json',diagnostics)
    # Aggregate matched differences: same traces and contexts; no confidence bars.
    eft=[r for r in differences if r['baseline']=='EFT_REFERENCE']
    fig,axes=plt.subplots(1,3,figsize=(12,4.1))
    for ax,key,title in zip(axes,['deadline_met_delta','energy_j_delta','peak_ap_delta'],
                           ['Deadline-met count: RL - EFT','120 s energy: RL - EFT (J)','Peak AP: RL - EFT (C)']):
        vals=[statistics.mean(r[key] for r in eft if r['family']==family) for family in rl.FAMILIES]
        ax.bar(rl.FAMILIES,vals,color=['#d95f02' if (x<0 if key=='deadline_met_delta' else x>0)
                                     else '#386cb0' for x in vals])
        ax.axhline(0,color='black',lw=.8);ax.set_title(title,fontsize=10);ax.tick_params(axis='x',rotation=25)
        for i,v in enumerate(vals):ax.annotate(f'{v:+.3f}',(i,v),xytext=(0,5 if v>=0 else -14),
                                              textcoords='offset points',ha='center',fontsize=9)
        ax.margins(y=.25)
        if key=='deadline_met_delta': ax.set_ylim(min(vals)-.5,max(vals)+.5)
    fig.suptitle('Frozen RL candidate: synthetic holdout, NOT measured effects',fontsize=12)
    fig.text(.5,.01,'Each family: 2 arrival traces x 3 service contexts. No confidence intervals; no accuracy PASS.',
             ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.06,1,.94));fig.savefig(folder/'rl_vs_eft.png',dpi=150)
    fig.savefig(folder/'rl_vs_eft.svg');plt.close(fig)
    svg=folder/'rl_vs_eft.svg';svg.write_text('\n'.join(x.rstrip() for x in svg.read_text(encoding='utf8').splitlines())+'\n',encoding='utf8')
    def table_html(records):
        return '<table><tr>'+''.join('<th>'+html.escape(k)+'</th>' for k in records[0])+'</tr>'+''.join(
            '<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in row.values())+'</tr>' for row in records)+'</table>'
    (folder/'index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8">
<title>요청별 강화학습 PC 비교</title><style>body{font:15px system-ui;margin:24px;color:#203040}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:6px}img{max-width:100%}.warning{background:#fff3d5;padding:16px}</style>
<h1>요청별 강화학습: 학습·동결·합성 입력 평가</h1>
<p class="warning">후보 미채택. 단일 표 기반 학습96회 이후 평가120회. 새 실측·모형 재보정·기본 정책 변경 없음.
기한 우선 학습 목표가 실제 기한 보장은 아닙니다. 같은 자료 기반 모형·같은 초기조건이며 실기기 독립 확인이 아닙니다.</p>
<p><a href="../README.md">계약·결과·한계·재현</a> · <a href="comparison.csv">전체120행</a> · <a href="differences.csv">대응 차이</a> · <a href="learning_diagnostics.json">방문 수</a></p>
<img src="rl_vs_eft.png" alt="모형상 RL-EFT 기한·에너지·AP 차이"><h2>입력별 기술 요약</h2>
<p>각 입력의6조건은2개 도착열×3개 처리시간 문맥입니다. 6개 독립 실측 반복이 아닙니다. J는0–120초, AP는35–180초입니다.
응답 P95 열은 조건별 P95의 평균이며 요청을 합친 P95가 아닙니다. 에너지·AP는 낮을수록, 기한 충족은 높을수록 좋습니다.</p>'''+table_html(aggregate)+
        '<h2>학습 상태 관측</h2><p>방문 상태에서 행동을 썼다는 사실은 충분한 탐색·수렴·인과적 이득의 증거가 아닙니다.</p>'+table_html([diagnostics])+'</html>',encoding='utf8')
    return aggregate,diagnostics


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True)
    args=parser.parse_args();print(report(args.folder))
