"""Render stored results only: no fit, simulation, device or outcome selection."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BUNDLE=Path(__file__).resolve().parent


def table(name):
    with (BUNDLE/'run_v1'/name).open(encoding='utf8',newline='') as f:return list(csv.DictReader(f))


def render(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':10})
    errors=table('energy_errors.csv');features=table('pre_features.csv');bins=table('pre_bins.csv');curves=table('energy_curves.csv')
    labels=[r['session'] for r in features];x=np.arange(len(labels));variants=('original_frozen','fixed_zero_offset','CPU_prebaseline')
    fig,axs=plt.subplots(2,1,figsize=(13,8),sharex=True)
    for j,(variant,label,color) in enumerate(zip(variants,('동결 원식','기존 δ=0 보완식','CPU 초기화 후보'),('#999999','#0369a1','#ea580c'))):
        values=[float(next(r['signed_J'] for r in errors if r['session']==s and r['phase']=='reference120' and r['variant']==variant)) for s in labels]
        axs[0].bar(x+(j-1)*.24,values,width=.24,label=label,color=color)
        axs[1].bar(x+(j-1)*.24,np.abs(values),width=.24,label=label,color=color)
    axs[0].axhline(0,color='black',lw=.6);axs[0].set_ylabel('예측 - 관측 J');axs[1].set_ylabel('절대오차 J')
    for ax in axs:ax.axvline(5.5,color='black',ls='--',lw=1);ax.grid(axis='y',alpha=.2)
    axs[0].legend(ncol=3);axs[0].set_title('같은 0..120초·전체 12세션 / 개발은 다른 회복시간 블록으로 추정 / 확인은 이미 열람한 사후 평가')
    axs[1].set_xticks(x,[s.replace('development','개발').replace('confirmation','확인') for s in labels],rotation=55,ha='right')
    fig.tight_layout();save(fig,output,'all_session_errors')

    fig,axs=plt.subplots(2,2,figsize=(12,8),sharex=True)
    for ax,s in zip(axs.ravel(),[s for s in labels if s.endswith('_C0')]):
        use=[r for r in bins if r['session']==s];f=next(r for r in features if r['session']==s)
        t=[(float(r['lo_s'])+float(r['hi_s']))/2 for r in use]
        ax.plot(t,[float(r['other_rate_core_s_per_s']) for r in use],'-o',label='other CPU',color='#7c3aed')
        ax.axhline(float(f['pre50_other_rate']),ls='--',lw=1,color='#7c3aed',label='pre50 평균')
        ax.axvspan(10,30,alpha=.10,color='#fb923c');ax.set_ylabel('CPU core seconds / wall second');ax.set_title(s)
        twin=ax.twinx();twin.plot(t,[float(r['mean_power_W']) for r in use],'-s',color='#15803d',label='전체전력');twin.set_ylabel('기기 전체 W')
        ax.grid(alpha=.2)
    axs[0,0].legend(loc='upper left',fontsize=8);axs[1,0].set_xlabel('본 작업 예정 원점 기준 s');axs[1,1].set_xlabel('본 작업 예정 원점 기준 s')
    fig.suptitle('예측에 사용한 시작 전 정보만 표시: 음영은 고정 late20 / CPU 시간은 인과적 J 계수가 아님')
    fig.tight_layout();save(fig,output,'C0_pre_CPU_power')

    fig,axs=plt.subplots(1,2,figsize=(12,5))
    for ax,s in zip(axs,('confirmation_180_C0','confirmation_30_C0')):
        use=[r for r in curves if r['session']==s]
        ax.plot([float(r['t_s']) for r in use],[float(r['baseline_residual_J']) for r in use],label='기존 δ=0 보완식')
        ax.plot([float(r['t_s']) for r in use],[float(r['CPU_residual_J']) for r in use],label='CPU 초기화 후보')
        ax.axhline(0,lw=.7,color='black');ax.axvline(35,color='gray',ls='--',label='정보 경계35초')
        ax.set(title=s,xlabel='공통창 s',ylabel='누적 예측 - 관측 J');ax.grid(alpha=.2);ax.legend(fontsize=9)
    fig.suptitle('확인 C0 반례: 직전 CPU가 늘어난 뒤 감소 / pre CPU가 거의 일정한 뒤 감소')
    fig.tight_layout();save(fig,output,'C0_cumulative_residual')


def save(fig,out,name):
    for suffix in ('png','svg'):
        path=out/(name+'.'+suffix);fig.savefig(path,dpi=150,bbox_inches='tight')
        if suffix=='svg':
            path.write_text('\n'.join(line.rstrip() for line in path.read_text(encoding='utf8').splitlines())+'\n',encoding='utf8',newline='\n')
    plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();render(a.output)
