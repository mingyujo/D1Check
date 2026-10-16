"""Figures from saved electrical diagnostics and fixed30 candidate outputs only."""
import argparse
import html
from pathlib import Path
import numpy as np
from tools import d1_energy_memory30 as m


def plot():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.family']='Malgun Gothic';plt.rcParams['axes.unicode_minus']=False
    diag=m.diagnostic.BUNDLE;out=m.BUNDLE;groups=m.diagnostic.csv_rows(diag/'groups.csv');telemetry=m.diagnostic.csv_rows(diag/'telemetry.csv')
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),constrained_layout=True)
    for ax,fields,title in zip(axes,[('mean_past10_sd_w','mean_past30_sd_w'),('descriptive_past10_future_corr','descriptive_past30_future_corr')],['과거 잔차의 세션 내 표준편차 평균','과거 잔차와 다음 10초 잔차의 기술적 상관']):
        for i,(field,label,color) in enumerate(zip(fields,['과거10초','과거30초'],['#bd554a','#237969'])):
            values=[float(x[field]) for x in groups];bars=ax.bar(np.arange(3)+(i-.5)*.3,values,width=.3,color=color,label=label)
            for bar,v in zip(bars,values):ax.text(bar.get_x()+bar.get_width()/2,v,f'{v:.3f}',ha='center',va='bottom',fontsize=9)
        ax.set_xticks(range(3),['개발6','확인6','지속8']);ax.set_title(title);ax.legend(fontsize=8);ax.margins(y=.35)
    axes[0].set_ylabel('W');fig.suptitle('평균 기간 30초는 사전 고정 · 상관은 물리 원인이나 독립 표본의 증명 아님')
    fig.savefig(diag/'structure.png',dpi=145);plt.close(fig)
    comparison=m.diagnostic.csv_rows(out/'comparison.csv');methods=['FROZEN','FULL10','SHRINK10_FIXED','MEMORY30'];labels=['원모형','기존10초전량','기존10초감쇠','고정30초 후보'];colors=['#bc4a40','#858d96','#b29649','#247b69']
    fig,axes=plt.subplots(1,3,figsize=(15,4.6),constrained_layout=True)
    for ax,field,title in zip(axes,['mae_10s_j','net80_mae_j','maximum_10s_j'],['개별 10초 평균 절대오차','8회 발행 합산 80초 순오차','개별 10초 최대 절대오차']):
        highest=0.
        for i,method in enumerate(methods):
            values=[float(next(x for x in comparison if x['block']==b and x['role']==r and x['method']==method)[field]) for b,r in [('history','development'),('history','confirmation'),('sustained','evaluation')]]
            bars=ax.bar(np.arange(3)+(i-1.5)*.2,values,width=.2,label=labels[i],color=colors[i]);highest=max(highest,max(values))
            for bar,v in zip(bars,values):ax.text(bar.get_x()+bar.get_width()/2,v,f'{v:.3f}',ha='center',va='bottom',fontsize=7)
        ax.set_ylim(0,highest*1.4);ax.set_xticks(range(3),['개발6','확인6','지속8']);ax.set_ylabel('J');ax.set_title(title);ax.legend(fontsize=7,ncol=2,loc='upper center')
    fig.suptitle('동일한 10초 창과 자료 · 후보 계수는 개발 6세션에서 고정 · 120초 전체 예측 아님')
    fig.savefig(out/'comparison.png',dpi=145);plt.close(fig)
    cells=''.join('<tr>'+''.join('<td>'+html.escape(row[k])+'</td>' for k in ('block','role','method','n','mae_10s_j','net80_mae_j','local_worse_sessions','net_worse_sessions'))+'</tr>' for row in comparison)
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>전력 잔차 구조와30초 후보</title><style>body{font:17px/1.6 sans-serif;max-width:1200px;margin:30px auto;padding:20px}img{max-width:100%}td,th{padding:8px;border:1px solid #ddd}table{border-collapse:collapse}aside{padding:18px;background:#fff2d6}</style>
    <h1>전력 잔차의 변동과 지속 편향: 고정 30초 후보</h1><aside>전류값 반복은 드물고 기록 간격은 약 0.9초다. 30초 잔차 평균은 변동을 줄이고 다음 10초와의 상관을 높였다.
    alpha 0.519 후보는 확인 자료의 개별 10초 MAE를 0.870→0.848J, 합산 80초 순오차를 3.891→2.150J로 줄였다.
    그러나 지속 자료의 개별 오차는 0.844→0.854J로 커졌고 개발 교차 선택 기준을 충족하지 못했다. 특정 조건에서 개선했으며 일반 적용은 보류한다.</aside>
    <p>잔차의 통계적 시간 규모를 비교한 결과다. 센서 잡음·백그라운드·상태 비용의 물리 원인을 식별한 것은 아니다.
    센서 내부 갱신 주기는 미확인이고 개별 요청 전력도 식별되지 않았다. 모든 자료는 이미 열람한 사후 평가이며 정확도 합격이나 정책 우월성을 판정하지 않는다.</p>
    <p>실제 미래 lane 일정이 주어진 조건부 계산이다. 예측 입력의 전력 관측은 각 발행 시점 이전에 가용했던 것만 사용한다.
    합산 80초는 35–115초의 8개 순차 예측을 합친 값이며, 한 번에 만든 전체 창 예측과 구분한다. AP·기본 모형·RL·strict·experiment_ready=false는 유지한다.</p>
    <p><a href="README.md">판독·재현</a> · <a href="candidate_freeze.json">개발 동결</a> · <a href="session_errors.csv">전체 20세션</a> · <a href="../power_residual_structure_01/telemetry.csv">전류·전압 기록 통계</a></p>
    <img src="../power_residual_structure_01/structure.png" alt="10초/30초변동과상관"><img src="comparison.png" alt="평균/합산/최대오차">
    <table><tr><th>자료</th><th>역할</th><th>방식</th><th>세션</th><th>10초MAE J</th><th>합산80초MAE J</th><th>개별악화</th><th>합산악화</th></tr>'''+cells+'</table></html>'
    (out/'index.html').write_text(page,encoding='utf-8')
    print('Saved2 figures and12 group rows; no fit/device/policy execution')


if __name__=='__main__':plot()
