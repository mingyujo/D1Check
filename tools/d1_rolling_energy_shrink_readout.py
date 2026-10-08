"""Read saved scalar-calibration results and render them; no re-fitting."""
import argparse
import csv
import html
from pathlib import Path
import numpy as np
from tools import d1_rolling_energy_shrink as s


def read(p):
    with Path(p).open(encoding='utf-8') as f:return list(csv.DictReader(f))


def plot(output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.family']='Malgun Gothic';plt.rcParams['axes.unicode_minus']=False
    out=Path(output);comparison=read(out/'comparison.csv');sessions=read(out/'session_errors.csv')
    methods=['FROZEN','FULL_CORRECTION','DEV_MAE_SHRINK'];colors=['#b94a40','#7e8693','#247f6b'];names=['원모형','전량 보정','개발에서 고정한 감쇠']
    fig,axes=plt.subplots(1,3,figsize=(15,4.6),constrained_layout=True)
    for ax,field,title in zip(axes,('mae_10s_j','net80_mae_j','max_absolute_10s_j'),('개별10초 평균절대오차','8회발행 합산80초 순오차','개별10초 최대절대오차')):
        highest=0.
        for i,method in enumerate(methods):
            values=[float(next(x for x in comparison if x['block']==b and x['role']==r and x['method']==method)[field]) for b,r in [('history','development'),('history','confirmation'),('sustained','evaluation')]]
            bars=ax.bar(np.arange(3)+(i-1)*.24,values,width=.24,color=colors[i],label=names[i]);highest=max(highest,max(values))
            for bar,value in zip(bars,values):ax.text(bar.get_x()+bar.get_width()/2,value,f'{value:.3f}',ha='center',va='bottom',fontsize=8)
        ax.set_xticks(range(3),['개발6','확인6','기존 지속8']);ax.set_ylim(0,highest*1.4);ax.set_ylabel('J');ax.set_title(title);ax.legend(fontsize=7,loc='upper center')
    fig.suptitle('같은 창·같은 평가 자료에서 비교 · 감쇠 계수는 개발에서만 추정 · 120초 전체 오차 아님')
    fig.savefig(out/'comparison.png',dpi=145);plt.close(fig)
    ids=list(dict.fromkeys(x['id'] for x in sessions if x['role']!='development'))
    fig,axes=plt.subplots(2,1,figsize=(13,7),constrained_layout=True)
    for ax,field,title in zip(axes,('mae_10s_j','absolute_net80_j'),('평가14세션의 개별10초 MAE','평가14세션의 갱신합산80초 절대순오차')):
        for method,color,label in zip(methods,colors,names):
            values=[float(next(x for x in sessions if x['id']==identity and x['method']==method)[field]) for identity in ids]
            ax.plot(range(len(ids)),values,marker='o',color=color,label=label,markersize=4)
        ax.set_xticks(range(len(ids)),[x.replace('confirmation_','확인_').replace('sustained_','지속_') for x in ids],rotation=35,ha='right',fontsize=8)
        ax.set_ylabel('J');ax.set_title(title);ax.legend(fontsize=8);ax.grid(alpha=.15)
    fig.savefig(out/'evaluation_sessions.png',dpi=145);plt.close(fig)
    summary=s.previous.h.m.read(out/'summary.json')
    cells=''.join('<tr>'+''.join('<td>'+html.escape(row[k])+'</td>' for k in ('block','role','method','n','mae_10s_j','net80_mae_j','local_worse_sessions','net_worse_sessions'))+'</tr>' for row in comparison)
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>에너지 보정 강도 평가</title>
    <style>body{font:17px/1.6 sans-serif;max-width:1200px;margin:30px auto;padding:20px}table{border-collapse:collapse}td,th{padding:8px;border:1px solid #ddd}img{max-width:100%}aside{background:#fff0cf;padding:18px}</style>
    <h1>에너지 잔차 반영 강도: 개발6 추정·평가14</h1><aside>후보alpha='''+str(summary['candidate_alpha'])+''' · 개발교차gate실패/선택alpha0(원모형유지).
    전량보정보다악화폭을줄였으나확인10초MAE0.870→0.922J·지속0.844→0.856J로원모형보다커졌다.
    합산80초오차는확인3.891→2.960J로줄었지만120초예측개선이아니며구간상쇄를포함한다.</aside>
    <p>모형계수/기한/보상/정책/AP·실측을변경하지않은별도PC에너지보정한구조다. 평가결과로alpha를다시고르지않았다. 이미본자료사후평가·정확도PASS/실제절감미검증.</p>
    <p><a href="README.md">범위·재현</a> · <a href="candidate_freeze.json">개발동결/교차평가</a> · <a href="session_errors.csv">20세션 악화</a> · <a href="window_errors.csv">480계산행</a></p>
    <table><tr><th>자료</th><th>역할</th><th>방식</th><th>세션</th><th>10초MAE J</th><th>합산80초MAE J</th><th>10초악화</th><th>합산악화</th></tr>'''+cells+'''</table><img src="comparison.png" alt="개별·합산·최대오차 비교"><img src="evaluation_sessions.png" alt="모든평가14세션 결과"></html>'''
    (out/'index.html').write_text(page,encoding='utf-8')
    print('Readout2 figures and 9 summary rows completed; no fit/device/RL run')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);plot(p.parse_args().output)
