"""Visualize frozen evaluation tables; no model fitting or new simulation."""
import argparse
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parent


def rows(path):
    with Path(path).open(encoding='utf8',newline='') as f:return list(csv.DictReader(f))


def plot(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':11})
    energy=rows(ROOT/'run_v1/energy_errors.csv');curve=rows(ROOT/'run_v1/energy_curves.csv')
    ap=rows(ROOT/'run_v1/AP_errors.csv');pairs=rows(ROOT/'run_v1/paired_errors.csv')
    APcurves=rows(ROOT.parent/'ap_tail_observation_run_05/run_v6/curves.csv')
    fig,axes=plt.subplots(2,2,figsize=(14,9))
    for col,(sid,profile) in enumerate([('confirmation_0_C0_LONG','C0_LONG'),('confirmation_1_LOAD_A_LONG','LOAD_A_LONG')]):
        use=[r for r in curve if r['session']==sid and r['observed_j']]
        times=[float(r['t_s']) for r in use]
        for key,label in [('frozen_j','원식'),('previous_offset_j','이전 상수보정'),('candidate_j','이번 δ0/p4 후보')]:
            axes[0,col].plot(times,[float(r[key])-float(r['observed_j']) for r in use],label=label)
        axes[0,col].axhline(0,color='black',linewidth=.6);axes[0,col].axvline(635,color='#777',ls='--',linewidth=.7)
        axes[0,col].set_title(profile+' / 누적 에너지 잔차');axes[0,col].set_ylabel('예측 - 관측 (J)')
        raw=[r for r in APcurves if r['session']==profile]
        t=[float(r['t_s']) for r in raw]
        for key,label in [('observed_c','관측'),('FROZEN','원식'),('LOAD_SLOW','고정 AP 후보')]:
            axes[1,col].plot(t,[float(r[key]) for r in raw],label=label)
        axes[1,col].set_ylabel('AP (°C)');axes[1,col].set_xlabel('동일 원점 시각 (초)')
        axes[1,col].axvline(635,color='#777',ls='--',linewidth=.7)
        for row in range(2):axes[row,col].legend(fontsize=9)
    fig.suptitle('기존 장시간 자료 사후 평가 · 에너지5fit / AP재추정0 · 끝 결측 유지')
    fig.tight_layout();fig.savefig(out/'long_joint_paths.png',dpi=140);plt.close(fig)
    use=[r for r in energy if r['phase']=='reference120'];fig,axes=plt.subplots(3,1,figsize=(15,10))
    for ax,stage,title in zip(axes,('development_loso','archive_posthoc','seen_long_posthoc'),('개발4: 에너지 세션 제외 평가','이미 본 과거29: 사후 전이 평가','이미 본 긴2: 사후 에너지 평가')):
        part=[r for r in use if r['stage']==stage];x=np.arange(len(part))
        ax.bar(x-.18,[float(r['frozen_absolute_j']) for r in part],.36,label='원식')
        ax.bar(x+.18,[float(r['candidate_absolute_j']) for r in part],.36,label='δ0/p4 후보')
        ax.set_xticks(x,[r['session'] for r in part],rotation=65,ha='right',fontsize=8)
        ax.set_ylabel('참고120초 절대J');ax.set_title(title);ax.legend(fontsize=9)
    fig.tight_layout();fig.savefig(out/'all_session_energy.png',dpi=140);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(14,5))
    use=[r for r in pairs if r['mode']=='A_conditional'];x=np.arange(4)
    for i,(key,label) in enumerate([('observed_delta_j','관측'),('frozen_predicted_delta_j','원식'),('candidate_predicted_delta_j','δ0/p4 후보')]):
        axes[0].bar(x+(i-1)*.24,[float(r[key]) for r in use],.24,label=label)
    axes[0].axhline(0,color='black',linewidth=.6);axes[0].set_xticks(x,['짝0','짝1','짝2','짝3'])
    axes[0].set_ylabel('PAR - CPU 긴급우선 (J)');axes[0].set_title('같은120초 정책 차이: 부호2/4 미해결');axes[0].legend(fontsize=9)
    phases=['registered600','work_present','recovery_covered_prefix','matched_AP_power']
    use=[next(r for r in energy if r['session']=='confirmation_1_LOAD_A_LONG' and r['phase']==p) for p in phases];x=np.arange(len(use))
    for i,(key,label) in enumerate([('frozen_signed_j','원식'),('candidate_signed_j','δ0/p4 후보')]):axes[1].bar(x+(i-.5)*.32,[float(r[key]) for r in use],.32,label=label)
    axes[1].axhline(0,color='black',linewidth=.6);axes[1].set_xticks(x,['600초','작업존재','덮인회복','J/AP공통'])
    axes[1].set_ylabel('예측 - 관측 (J)');axes[1].set_title('LOAD: 구간별 상쇄를 함께 공개');axes[1].legend(fontsize=9)
    fig.tight_layout();fig.savefig(out/'policy_and_interval_errors.png',dpi=140);plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();plot(a.output)
