"""Plot already evaluated J/AP errors; no refit or device work."""
import csv
import gzip
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'run_v1'


def main():
    with (OUT/'joint_errors.csv').open(encoding='utf8') as f:rows=list(csv.DictReader(f))
    plt.rcParams['font.family']='Malgun Gothic'
    plt.rcParams['axes.unicode_minus']=False
    fig,axes=plt.subplots(3,1,figsize=(12,16),constrained_layout=True,
                         gridspec_kw={'height_ratios':[3,10,2.5]})
    stages=('development_loso','archive_posthoc','seen_long_posthoc_energy')
    titles=('개발4: 세션 제외평가', '이미 본 과거29: 사후 전이 평가',
            '이미 본 장시간2: 사후 에너지 평가 (새 독립 확인 아님)')
    for ax,stage,title in zip(axes,stages,titles):
        r=[x for x in rows if x['stage']==stage];y=list(range(len(r)))
        ax.barh([i-.18 for i in y],[float(x['frozen_abs_J']) for x in r],.35,label='기존 에너지식',color='#d98c32')
        ax.barh([i+.18 for i in y],[float(x['candidate_abs_J']) for x in r],.35,label='기준전력＋4상태 후보',color='#287e75')
        ax.set_yticks(y,[x['session'] for x in r]);ax.invert_yaxis();ax.set_title(title)
        ax.set_xlabel('참고 공통창 [0,120] 에너지 절대오차 (J)');ax.legend();ax.grid(axis='x',alpha=.2)
        for label,row in zip(ax.get_yticklabels(),r):
            if row['energy_worse']=='True':label.set_color('#b91c1c')
    fig.suptitle('에너지 후보: 개선과 악화35세션 모두 보존 · 기본/RL 교체 없음',fontsize=14)
    fig.savefig(OUT/'session_energy_errors.png',dpi=125);plt.close(fig)
    with gzip.open(OUT/'energy_curves.csv.gz','rt',encoding='utf8') as f:paths=list(csv.DictReader(f))
    fig,axes=plt.subplots(3,1,figsize=(12,11),constrained_layout=True)
    ids=('confirmation_0_C0_LONG','confirmation_1_LOAD_A_LONG')
    for ax,identity in zip(axes[:2],ids):
        p=[x for x in paths if x['session']==identity and x['observed_j']]
        t=[float(x['t_s']) for x in p]
        ax.plot(t,[float(x['frozen_j'])-float(x['observed_j']) for x in p],label='기존식',color='#d98c32')
        ax.plot(t,[float(x['candidate_j'])-float(x['observed_j']) for x in p],label='에너지 후보',color='#287e75')
        ax.axvline(635,color='gray',ls='--',label='등록600초 종료');ax.axhline(0,color='black',lw=.7)
        ax.set_title(identity+' · 관측이 덮은 prefix만');ax.set_ylabel('예측 - 관측 누적 J');ax.set_xlabel('원 모형 시계 (초)');ax.legend()
    r=[x for x in rows if x['stage']=='seen_long_posthoc_energy'];y=[0,1]
    axes[2].bar([i-.18 for i in y],[float(x['frozen_AP_MAE_c']) for x in r],.35,label='기존 AP식',color='#d98c32')
    axes[2].bar([i+.18 for i in y],[float(x['candidate_AP_MAE_c']) for x in r],.35,label='이미 동결한 LOAD_SLOW',color='#287e75')
    axes[2].set_xticks(y,['C0','LOAD_A']);axes[2].set_ylabel('AP 경로 MAE (°C)');axes[2].legend()
    axes[2].set_title('AP는 이전 확인 결과 그대로 · 새 에너지 계수를 AP식에 넣지 않음')
    fig.suptitle('600초 개선과 긴 유휴 악화를 분리 · 전체 오차 개선/PASS 아님',fontsize=14)
    fig.savefig(OUT/'long_energy_AP_residuals.png',dpi=130);plt.close(fig)


if __name__=='__main__':main()
