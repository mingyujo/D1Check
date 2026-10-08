"""Visualize frozen-vs-preload estimators; no candidate search or policy ranking."""
import argparse
import csv
import html
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from tools import d1_preload_dynamics_refinement as d
from tools.d1_joint_model_report import save


def rows(path):
    with path.open(encoding='utf8') as f:return list(csv.DictReader(f))


def run(output):
    data=rows(output/'session_errors.csv');paths=rows(output/'paths.csv');summary=d.j.m.read(output/'summary.json')
    cases,_=d.j.panel();by={c['id']:c for c in cases};ids=[r['id'] for r in data if r['role']!='development' and r['mode']=='A_conditional' and r['candidate']=='FROZEN']
    fig,axes=plt.subplots(2,1,figsize=(14,8),sharex=True)
    for ax,field,candidate,label in [(axes[0],'abs_j','E_PRE_TRANSIENT','Whole120 energy absolute error J'),(axes[1],'mae_c','AP_FREE_INITIAL','AP path MAE C; actual post35 samples')]:
        for shift,name,color in [(-.18,'FROZEN','#2563eb'),(.18,candidate,'#db7d35')]:
            values=[float(next(r for r in data if r['id']==i and r['mode']=='A_conditional' and r['candidate']==name)[field]) for i in ids]
            ax.bar(np.arange(20)+shift,values,.36,label=name,color=color)
        ax.set_ylabel(label);ax.legend();ax.grid(axis='y',alpha=.2)
    axes[-1].set_xticks(range(20),ids,rotation=70,ha='right',fontsize=8)
    fig.suptitle('Preload-only estimators / all20 archived evaluation sessions / posthoc');fig.tight_layout();save(fig,output/'session_errors')
    fig,axes=plt.subplots(5,4,figsize=(16,16))
    for ax,identity in zip(axes.flat,ids):
        for name,color in [('FROZEN','#2563eb'),('AP_FREE_INITIAL','#db7d35')]:
            use=[r for r in paths if r['id']==identity and r['candidate']==name and r['observed_ap_c']!='']
            ax.plot([float(r['t_s']) for r in use],[float(r['predicted_ap_c']) for r in use],label=name,color=color)
            if name=='FROZEN':ax.plot([float(r['t_s']) for r in use],[float(r['observed_ap_c']) for r in use],label='Observed',color='black')
        ax.set_title(identity,fontsize=9);ax.set_xlabel('s');ax.set_ylabel('AP C');ax.grid(alpha=.2);ax.axvspan(35,by[identity]['last_lane_s'],alpha=.1,color='red')
    axes.flat[0].legend(fontsize=7);fig.suptitle('Absolute AP at observed sample times; load span shaded / latest preload AP anchor unchanged');fig.tight_layout();save(fig,output/'ap_paths')
    fig,axes=plt.subplots(3,2,figsize=(13,10))
    for axrow,identity in zip(axes,['confirmation_5','confirmation_30_C0','sustained_5']):
        for ax,candidate,field,title in [(axrow[0],'E_PRE_TRANSIENT','signed_j','Cumulative J residual, whole0..120s'),(axrow[1],'AP_FREE_INITIAL','signed_ap_c','Signed AP residual, actual sensor window')]:
            for name,color in [('FROZEN','#2563eb'),(candidate,'#db7d35')]:
                use=[r for r in paths if r['id']==identity and r['candidate']==name and r[field]!='']
                ax.plot([float(r['t_s']) for r in use],[float(r[field]) for r in use],label=name,color=color)
            ax.axhline(0,color='black',lw=.7);ax.grid(alpha=.2);ax.legend(fontsize=8);ax.set_title(identity+' / '+title,fontsize=9);ax.set_xlabel('s')
            ax.axvspan(35,by[identity]['last_lane_s'],alpha=.1,color='red')
    fig.tight_layout();save(fig,output/'residual_paths')
    def table(use,keys):
        return '<table><tr>'+''.join('<th>'+html.escape(k)+'</th>' for k in keys)+'</tr>'+''.join('<tr>'+''.join('<td>'+html.escape(str(r.get(k,'')))+'</td>' for k in keys)+'</tr>' for r in use)+'</table>'
    text='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>에너지·AP 예측 모형 보완</title>
    <style>body{font:16px/1.7 system-ui;max-width:1200px;margin:30px auto;padding:16px}img{max-width:100%}table{border-collapse:collapse;font-size:12px}td,th{border:1px solid #ddd;padding:6px}.scroll{overflow:auto}.notice{background:#fff2dc;padding:20px}</style>
    <h1>부하전 초기화 변경: AP 일부 개선·에너지 후보 제외</h1><div class="notice">AP 초기화 후보는 지속8 평균오차를0.381→0.335°C·최대오차1.277→1.165°C로 줄였습니다. 새확인6은0.260→0.268°C로 악화했고 지속8에서도4개는 평균오차가 커졌습니다. 개발 선택 기준을 통과하지 못해 기본 모형을 유지합니다. 전력 준비 추세 외삽은 악화해 제외합니다.</div>
    <p>이 화면은 실제 일정 조건부 에너지/AP 예측 오차를 비교합니다. 정책 순위 화면이 아닙니다. 새로운 기기 측정·물리계수 적합·RL 환경 변경은0회입니다. 기존 동결본과 계수는 보존했습니다.</p>
    <p>J는0–120초 공통창, AP는 각 세션의 실제 post35 표본창입니다. B는 기존 예정도착 예측 일정에 적용한 별도 비용이며 새로운 일정/응답 정확도 개선을 뜻하지 않습니다. 표본 시각과 전체/부분 경계를 CSV에 표시했습니다.</p>
    <p>후보는 부하전 관측만 사용합니다. 자유 초기화의 유효 유휴 R와 잠재H는 추정값이며 주변온도나 내부온도 실측이 아닙니다. 에너지30초 감소상수는 기존 가설을 고정한 것으로 새 물리적 식별이 아닙니다. 이미 본 자료의 사후 평가·strict/experiment_ready=false 유지.</p>
    <p><a href="../README.md">재현·계약·별도 후보</a> · <a href="../../../PRELOAD_DYNAMICS_REFINEMENT_RESULTS_20261008.md">한국어 보고서</a> · <a href="session_errors.csv">172개 A/B·개발/평가</a> · <a href="initial_states.csv">부하전 추정값</a> · <a href="windows.csv">구간 오차</a></p>'''
    text+='<h2>같은 조건의 원모형·후보 비교</h2><div class="scroll">'+table(summary['comparison'],['block','role','mode','candidate','n','energy_n','ap_n','energy_mae_j','energy_max_j','ap_mae_c','ap_max_c','opposite_cooling'])+'</div>'
    for name,title in [('session_errors','모든 평가 세션의 평균오차'),('ap_paths','관측·원모형·초기화 후보 AP'),('residual_paths','누적 에너지·가열/냉각 잔차')]:text+=f'<h2>{title}</h2><img src="{name}.png" alt="{title}">'
    text+='<h2>전체 세션과 악화</h2><div class="scroll">'+table(data,['id','role','mode','candidate','signed_j','abs_j','load_signed_j','post_signed_j','mae_c','max_absolute_error_c','peak_signed_error_c','delta_mae_c','ap_start_s','ap_end_s'])+'</div></html>'
    (output/'index.html').write_text(text,encoding='utf8')
    print('3 figures / all20 AP paths / 172 rows published')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);run(Path(p.parse_args().output))
