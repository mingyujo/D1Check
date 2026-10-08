"""Publish the bounded saved-schedule sensitivity; no refit or policy execution."""
import argparse
import html
import json
from pathlib import Path
from collections import Counter
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from tools import d1_policy_coefficient_sensitivity as s
from tools.d1_joint_model_report import save

LABEL={s.TARGETS[0]:'R2',s.TARGETS[1]:'EDD',s.BASELINES[0]:'Shared EFT',s.BASELINES[1]:'Head EFT',s.BASELINES[2]:'Band adapted',s.BASELINES[3]:'Triton adapted'}
STATUS=['joint_direction_all_five','sign_sensitive','heat_energy_tradeoff_all_five','energy_heat_tradeoff_all_five','heat_down_energy_nonincrease','no_joint_direction','numerical_tie','deadline_ineligible','service_ineligible','unavailable']
COLORS=['#20875a','#d58b21','#855b9c','#c46371','#50a5a3','#9caaac','#d8e1e5','#bf7074','#a1494d','#444']


def run(output):
    guarded=s.csv_rows(output/'direction_guard.csv');summary=s.j.m.read(output/'summary.json');data=s.j.m.read(s.BUNDLE/'inputs.json.gz')
    identifiers=[(f,c) for f in s.FAMILIES for c in s.CONTEXTS]
    fig,axes=plt.subplots(2,3,figsize=(15,9),sharex=True)
    for col,baseline in enumerate([s.BASELINES[3],s.BASELINES[0],s.BASELINES[2]]):
        use=[r for r in guarded if r['policy']==s.TARGETS[0] and r['baseline']==baseline]
        for row,(field,lo,hi,label) in enumerate([('frozen_delta_energy_j','energy_min_j','energy_max_j','Delta whole120 energy J'),('frozen_delta_peak_ap_c','ap_min_c','ap_max_c','Delta peak AP C, 35..180s')]):
            vals=[next(r for r in use if (r['family'],r['context'])==k) for k in identifiers]
            y=np.array([float(r[field]) for r in vals]);a=np.array([float(r[lo]) for r in vals]);b=np.array([float(r[hi]) for r in vals])
            axes[row,col].errorbar(range(12),y,yerr=np.array([y-a,b-y]),fmt='o',color='#2563eb',ecolor='#70889d',capsize=3)
            axes[row,col].axhline(0,color='black',lw=.8);axes[row,col].grid(alpha=.2);axes[row,col].set_title('R2 - '+LABEL[baseline]);axes[row,col].set_ylabel(label)
            axes[row,col].set_xticks(range(12),[f+' / '+c.replace('_context','') for f,c in identifiers],rotation=65,ha='right',fontsize=8)
    fig.suptitle('Dot: frozen model / span: five fixed development coefficient variants\nNot a confidence interval; all schedules held fixed');fig.tight_layout();save(fig,output/'coefficient_spans')
    from matplotlib.colors import ListedColormap
    fig,ax=plt.subplots(figsize=(14,6));values=[];labels=[]
    for target in s.TARGETS:
        for baseline in s.BASELINES:
            use=[r for r in guarded if r['policy']==target and r['baseline']==baseline]
            values.append([STATUS.index(next(r for r in use if (r['family'],r['context'])==k)['status']) for k in identifiers])
            labels.append(LABEL[target]+' - '+LABEL[baseline])
    ax.imshow(values,aspect='auto',cmap=ListedColormap(COLORS),vmin=-.5,vmax=len(STATUS)-.5)
    ax.set_yticks(range(8),labels);ax.set_xticks(range(12),[f+' / '+c.replace('_context','') for f,c in identifiers],rotation=45,ha='right')
    ax.set_title('Direction guard: includes full deadlines and urgent-P95 preservation')
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=COLORS[i],label=state) for i,state in enumerate(STATUS) if i in {x for row in values for x in row}],loc='upper center',bbox_to_anchor=(.5,-.37),ncol=3,fontsize=8)
    fig.tight_layout();save(fig,output/'direction_guard')
    fig,axes=plt.subplots(6,1,figsize=(14,10),sharex=True)
    for ax,policy in zip(axes,s.POLICIES):
        c=next(c for c in data['cases'] if c['family']=='sustained' and c['context']=='mean' and c['policy']==policy)
        for r in c['ledger']:
            y=0 if r['backend']=='CPU' else 1;color='#c57637' if r['task']=='detection' else '#547fb3'
            ax.broken_barh([(r['dispatch_ns']/1e9,(r['lane_available_ns']-r['dispatch_ns'])/1e9)],(y-.3,.6),facecolors=color)
        ax.set_yticks([0,1],['CPU','GPU']);ax.set_ylabel(LABEL[policy]);ax.grid(axis='x',alpha=.2);ax.set_ylim(-.6,1.6)
    axes[-1].set_xlabel('Common-window seconds / dispatch to lane_available');axes[-1].set_xlim(35,120)
    fig.suptitle('Archived sustained / mean / first seed; orange=detection, blue=classification\nOriginal schedule unchanged for every coefficient setting');fig.tight_layout();save(fig,output/'saved_lanes')
    status=Counter(r['status'] for r in guarded)
    s.j.m.table(output/'summary.csv',[dict(scope=r['scope'],policy=r['policy'],baseline=r['baseline'],comparisons=r['comparisons'],
                                            full_deadline_service=r['full_deadline_service'],original_joint=r['original_full_deadline_joint'],direction_all_five=r['joint_direction_all_five'],
                                            statuses=json.dumps(r['status_counts'],ensure_ascii=False)) for r in summary['summary']])
    def table(rows,keys):
        return '<table><tr>'+''.join('<th>'+html.escape(k)+'</th>' for k in keys)+'</tr>'+''.join('<tr>'+''.join('<td>'+html.escape(str(r.get(k,'')))+'</td>' for k in keys)+'</tr>' for r in rows)+'</table>'
    body='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>정책 계수 민감도</title>
    <style>body{font:16px/1.7 system-ui;max-width:1250px;margin:30px auto;padding:16px}img{max-width:100%}table{border-collapse:collapse;font-size:12px}td,th{border:1px solid #ddd;padding:6px;overflow-wrap:anywhere}.scroll{overflow:auto}.note{background:#fff2dc;padding:18px}</style>
    <h1>저장 정책 일정의 계수 민감도</h1><div class="note">R2·EDD는 주평가 6조건에서 Triton 대응 기준 대비 에너지·최고 AP 감소 방향을 다섯 계수 설정 모두 유지했습니다. 공용 EFT·Band 대비로는 공동 감소가 없고, 지속 부하 에너지 차이 부호가 바뀝니다. 이는 첫 seed의 저장 일정 민감도이며 실제 절감·전체 정책 우월성·독립 확인이 아닙니다.</div>
    <p>입력→정책 일정 생성은 기존 B 결과입니다. 이번에는 그 PC 일정을 고정한 조건부 비용만 다시 계산했습니다. 계수가 바뀌었을 때 정책이 다시 선택한 일정은 아닙니다. 새 정책 환경·학습·적합·기기 명령 0회, 기본 모형·RL·strict 유지.</p>
    <p>다섯 설정은 원모형＋공동개발9＋개발묶음제외3입니다. 네 재추정 변형은 미채택 후보입니다. 범위는 개발 묶음 민감도이며 확률적 신뢰구간이나 모든 오차를 포함하는 범위가 아닙니다. 서비스 부적격·기한 위반 사례는 비용 감소 성공으로 처리하지 않습니다.</p>
    <p>에너지 0–120초, 최고 AP/면적 35–180초 1초 격자. 면적은 각 설정의 부하전 유효 유휴 기준 R 초과분이며 R는 주변 온도 실측이 아닙니다. AP 센서 관측 곡선이나 실기기 안전 온도가 아닙니다.</p>
    <p><a href="../README.md">재현·계약</a> · <a href="../../../POLICY_COEFFICIENT_SENSITIVITY_RESULTS_20261008.md">한국어 보고서</a> · <a href="direction_guard.csv">96개 판독</a> · <a href="paired_variants.csv">480개 비용 차이</a> · <a href="state_exposure.csv">상태 점유</a></p>'''
    body+='<h2>범위별 집계</h2><div class="scroll">'+table(summary['summary'],['scope','policy','baseline','comparisons','full_deadline_service','original_full_deadline_joint','joint_direction_all_five','status_counts'])+'</div>'
    for name,title in [('coefficient_spans','고정 일정의 계수 변동 범위'),('direction_guard','기한·서비스·방향 판독'),('saved_lanes','대표 실제 PC lane 일정')]:body+=f'<h2>{title}</h2><img src="{name}.png" alt="{title}">'
    body+='<h2>96개 비교 전체</h2><div class="scroll">'+table(guarded,['family','context','policy','baseline','status','service_preserved','both_all_deadlines','policy_deadline_failures','baseline_deadline_failures','frozen_delta_energy_j','energy_min_j','energy_max_j','frozen_delta_peak_ap_c','ap_min_c','ap_max_c'])+'</div></html>'
    (output/'index.html').write_text(body,encoding='utf8')
    print(json.dumps(dict(figures=3,guarded_rows=96,status_counts=dict(status))))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);run(Path(p.parse_args().output))
