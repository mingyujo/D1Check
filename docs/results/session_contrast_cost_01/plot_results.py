"""All retained methods and frozen choice, saved measured targets only."""
import argparse
from pathlib import Path
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parent


def read(path):
    with Path(path).open(encoding='utf8',newline='') as f:return list(csv.DictReader(f))


def run(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':11})
    E=read(ROOT/'run_v1/energy_errors.csv');AP=read(ROOT/'run_v1/AP_errors.csv');curves=read(ROOT/'run_v1/AP_curves.csv')
    prior_AP=read(ROOT.parent/'ap_tail_observation_run_05/run_v6/curves.csv')
    fig,axes=plt.subplots(1,2,figsize=(14,5));x=np.arange(3);phases=['registered600','matched_AP_power','recovery_covered_prefix']
    for i,(method,label) in enumerate([('previous','직전 별도 후보'),('UNCENTERED','일반13'),('CENTERED','중심화13')]):
        subset=[next(r for r in E if r['session']=='confirmation_1_LOAD_A_LONG' and r['phase']==p and r['method']==('UNCENTERED' if method=='previous' else method)) for p in phases]
        values=[float(r['prior_zero_offset_j'])-float(r['observed_j']) if method=='previous' else float(r['candidate_signed_j']) for r in subset]
        axes[0].bar(x+(i-1)*.24,values,.24,label=label)
        subset=[next(r for r in AP if r['session']=='confirmation_1_LOAD_A_LONG' and r['phase']==p and r['method']==('UNCENTERED' if method=='previous' else method)) for p in phases]
        axes[1].bar(x+(i-1)*.24,[float(r['prior_AP_MAE_c'] if method=='previous' else r['mae_c']) for r in subset],.24,label=label)
    for ax in axes:ax.set_xticks(x,['등록600초','동일J/AP관측창','덮인회복']);ax.legend(fontsize=9)
    axes[0].axhline(0,color='black',lw=.6);axes[0].set_ylabel('예측 - 관측 에너지 (J)');axes[1].set_ylabel('AP MAE (°C)')
    fig.suptitle('LOAD: 개발에서 전력=일반 / AP=중심화 선택 · 모든 결과 공개')
    fig.tight_layout();fig.savefig(out/'LOAD_phase_comparison.png',dpi=140);plt.close(fig)
    for role,label in [('seen_archival_evaluation','추정에 쓰지 않은 과거20 / 이미 열람한 사후 평가'),('seen_long_evaluation','긴2 / 이미 열람한 사후 평가')]:
        fig,axes=plt.subplots(2,1,figsize=(14,8))
        energies=[r for r in E if r['role']==role and r['phase']=='reference120' and r['method']=='UNCENTERED']
        sid=[r['session'] for r in energies];x=np.arange(len(sid))
        axes[0].bar(x-.16,[float(r['prior_abs_j']) for r in energies],.32,label='직전 후보')
        axes[0].bar(x+.16,[float(r['candidate_abs_j']) for r in energies],.32,label='개발선택 전력=일반13')
        values=[next(r for r in AP if r['session']==s and r['role']==role and r['phase']=='matched_AP_power' and r['method']=='CENTERED') for s in sid]
        axes[1].bar(x-.16,[float(r['prior_AP_MAE_c']) for r in values],.32,label='직전 LOAD_SLOW')
        axes[1].bar(x+.16,[float(r['mae_c']) for r in values],.32,label='개발선택 AP=중심화13')
        for ax in axes:ax.set_xticks(x,sid,rotation=55,ha='right',fontsize=8);ax.legend(fontsize=9)
        axes[0].set_ylabel('참고120초 절대J');axes[1].set_ylabel('J/AP공통창 AP MAE (°C)')
        fig.suptitle(label+' · 서로 다른 J/AP 창의 평균을 합치지 않음')
        fig.tight_layout();fig.savefig(out/(role+'.png'),dpi=140);plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(13,7),sharex=True)
    old=[r for r in prior_AP if r['session']=='LOAD_A_LONG']
    new=[r for r in curves if r['session']=='confirmation_1_LOAD_A_LONG' and r['method']=='CENTERED']
    t=[float(r['t_s']) for r in old]
    for field,label in [('observed_c','관측'),('LOAD_SLOW','직전 고정 AP')]:axes[0].plot(t,[float(r[field]) for r in old],label=label)
    axes[0].plot([float(r['t_s']) for r in new],[float(r['predicted_ap_c']) for r in new],label='새 AP중심화')
    axes[1].plot(t,[float(r['LOAD_SLOW'])-float(r['observed_c']) for r in old],label='직전잔차')
    axes[1].plot([float(r['t_s']) for r in new],[float(r['predicted_ap_c'])-float(r['observed_ap_c']) for r in new],label='새잔차')
    for ax in axes:ax.axvline(635,color='#666',ls='--',lw=.7);ax.legend()
    axes[0].set_ylabel('AP (°C)');axes[1].set_ylabel('예측 - 관측 (°C)');axes[1].set_xlabel('동일 원점 시각 (초)');axes[1].axhline(0,color='black',lw=.6)
    fig.suptitle('LOAD AP 추가 개선과 냉각 변화량 악화를 함께 판독')
    fig.tight_layout();fig.savefig(out/'LOAD_AP_path.png',dpi=140);plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();run(a.output)
