"""Stored CSV visualization; no fit, device, tuning or missing-to-zero conversion."""
import argparse
import csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
BUNDLE=Path(__file__).resolve().parent


def table(path):
    with Path(path).open(encoding='utf8',newline='') as f:return list(csv.DictReader(f))


def save(fig,out,name):
    for suffix in ('png','svg'):
        p=out/(name+'.'+suffix);fig.savefig(p,dpi=150,bbox_inches='tight')
        if suffix=='svg':p.write_text('\n'.join(x.rstrip() for x in p.read_text(encoding='utf8').splitlines())+'\n',encoding='utf8',newline='\n')
    plt.close(fig)


def plot(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':10})
    errors=table(BUNDLE/'run_v1/energy_errors.csv');availability=table(BUNDLE/'run_v1/availability.csv');curves=table(BUNDLE/'run_v1/energy_curves.csv')
    labels=[r['session'] for r in availability];x=np.arange(12)
    methods=('FROZEN','ZERO','FULL_MEAN','FULL_CPU')
    legends=('동결 원식','기존 δ=0','전체 pre 평균','전체 pre＋CPU 후보')
    colors=('#999999','#0369a1','#0f766e','#ea580c')
    fig,axs=plt.subplots(2,1,figsize=(13,8),sharex=True)
    for j,(method,label,color) in enumerate(zip(methods,legends,colors)):
        y=[float(next(r['signed_J'] for r in errors if r['session']==s and r['method']==method and r['phase']=='reference120')) for s in labels]
        for ax,v in zip(axs,(y,np.abs(y))):ax.bar(x+(j-1.5)*.19,v,width=.19,color=color,label=label)
    axs[0].set_ylabel('예측 - 관측 J');axs[1].set_ylabel('절대오차 J');axs[0].axhline(0,color='black',lw=.6)
    axs[0].legend(ncol=4,fontsize=9);axs[0].set_title('같은 0..120초·전체12 / 개발: 반대 회복시간 계수 / 확인: 이미 본 사후 평가')
    for ax in axs:ax.axvline(5.5,color='black',ls='--',lw=.8);ax.grid(axis='y',alpha=.2)
    axs[1].set_xticks(x,[s.replace('development','개발').replace('confirmation','확인') for s in labels],rotation=55,ha='right')
    fig.tight_layout();save(fig,out,'all_session_energy_errors')

    fig,axs=plt.subplots(1,2,figsize=(12,5))
    for ax,identity in zip(axs,('confirmation_30_C0','confirmation_180_C0')):
        use=[r for r in curves if r['session']==identity];t=[float(r['t_s']) for r in use]
        for method,label,color in zip(('ZERO','FULL_MEAN','FULL_CPU'),legends[1:],colors[1:]):
            y=[float(r[method+'_J'])-float(r['observed_J']) for r in use]
            ax.plot(t,y,label=label,color=color)
        ax.axhline(0,lw=.6,color='black');ax.axvline(35,ls='--',color='gray');ax.grid(alpha=.2)
        ax.set(title=identity,xlabel='공통창 s',ylabel='누적 예측 - 관측 J');ax.legend(fontsize=9)
    fig.suptitle('C0 기준전력: 회복30 개선에는 초기/미래 오차 상쇄, 회복180은 악화')
    fig.tight_layout();save(fig,out,'C0_energy_residual_paths')

    pairs=table(BUNDLE/'readout_v1/policy_difference_errors.csv')
    fig,axs=plt.subplots(1,2,figsize=(11,5),sharey=True)
    for ax,head,title in zip(axs,('original_frozen','existing_zero_offset'),('원 동결4전력계수','기존 δ=0의4전력계수')):
        for j,(base,label,color) in enumerate(zip(('P50','FULL_MEAN','FULL_CPU'),('P50','전체 평균','전체＋CPU'),colors[1:])):
            y=[float(next(r['signed_difference_error_J'] for r in pairs if r['head']==head and r['initializer']==base and r['role']=='confirmation' and r['gap']==str(gap))) for gap in (30,180)]
            ax.bar(np.arange(2)+(j-1)*.23,y,width=.23,label=label,color=color)
        ax.axhline(0,color='black',lw=.6);ax.grid(axis='y',alpha=.2);ax.set_xticks([0,1],['확인 회복30','확인 회복180'])
        ax.set(title=title,ylabel='CPU - PAR 차이의 예측 오차 J');ax.legend(fontsize=9)
    fig.suptitle('후속 사후 분해: 동일 초기조건의 정책 효과 아님 / 원계수2종 모두 공개·선택0')
    fig.tight_layout();save(fig,out,'policy_difference_errors')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();plot(a.output)
