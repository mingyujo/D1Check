"""Plot stored results; oracle panels are marked evaluation-only, not forecasts."""
import argparse
import csv
import sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tools import d1_ap_conditioned_power as m


def save(fig,out,name):
    for suffix in ('png','svg'):
        p=out/(name+'.'+suffix);fig.savefig(p,dpi=150,bbox_inches='tight')
        if suffix=='svg':p.write_text('\n'.join(x.rstrip() for x in p.read_text(encoding='utf8').splitlines())+'\n',encoding='utf8',newline='\n')
    plt.close(fig)


def plot(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':10})
    source=m.BUNDLE/'run_v1';E=m.table(source/'energy_errors.csv');curves=m.table(source/'energy_curves.csv')
    labels=[p['id'] for p in m.old.old.read(source/'pre_features.json')];x=np.arange(12)
    methods=m.METHODS;names=('원식 P50','이전 전체CPU','동일창 CPU','CPU＋AP 후보');colors=('#999','#0369a1','#0f766e','#ea580c')
    fig,axs=plt.subplots(2,1,figsize=(13,8),sharex=True)
    for j,(method,name,color) in enumerate(zip(methods,names,colors)):
        y=[]
        for identity in labels:
            value=next(r['signed_J'] for r in E if r['session']==identity and r['head']=='original_frozen' and r['phase']=='reference120' and r['method']==method)
            y.append(float(value) if value else np.nan)
        for ax,values in zip(axs,(y,np.abs(y))):ax.bar(x+(j-1.5)*.19,values,width=.19,label=name,color=color)
    for ax in axs:ax.axvline(5.5,color='black',ls='--',lw=.7);ax.grid(axis='y',alpha=.2)
    axs[0].axhline(0,color='black',lw=.6);axs[0].legend(ncol=4,fontsize=9);axs[0].set_ylabel('예측 - 관측 J');axs[1].set_ylabel('절대오차 J')
    axs[0].set_title('원4전력계수 유지·같은120초 / 개발: 반대회복시간 추정 / 확인: 이미 본 사후 평가')
    axs[1].set_xticks(x,[s.replace('development','개발').replace('confirmation','확인') for s in labels],rotation=55,ha='right')
    fig.tight_layout();save(fig,out,'all_session_energy_errors')

    baseline=m.table(source/'baseline_paths.csv');cases={c['id']:c for c in m.old.old.history()}
    fig,axs=plt.subplots(2,2,figsize=(12,9))
    for row,identity in enumerate(('confirmation_180_C0','confirmation_30_C0')):
        use=[r for r in baseline if r['session']==identity];c=cases[identity]
        axs[row,0].plot([float(r['t_s']) for r in use],[float(r['idle_AP_counterfactual_c']) for r in use],label='작업없는 AP 모형 경로',color='#ea580c')
        observed=[(t,v) for t,v in zip(c['q'],c['ap']) if 35<=t<=120]
        axs[row,0].plot([t for t,v in observed],[v for t,v in observed],'.-',label='실측: 평가에만 사용',color='#0369a1')
        axs[row,0].axhline(float(use[0]['pre_matched_mean_AP_c']),ls='--',label='시작 전 전체 AP 평균',color='gray')
        axs[row,0].set(title=identity+' / AP',xlabel='공통창 s',ylabel='AP °C');axs[row,0].legend(fontsize=8)
        use=[r for r in curves if r['session']==identity and r['head']=='original_frozen']
        for method,name,color in zip(('P50','MATCH_CPU','CPU_AP'),('원식 P50','동일창 CPU','CPU＋AP'),('#999','#0f766e','#ea580c')):
            axs[row,1].plot([float(r['t_s']) for r in use],[float(r[method+'_J'])-float(r['observed_J']) if r[method+'_J'] and r['observed_J'] else np.nan for r in use],label=name,color=color)
        axs[row,1].axvline(35,color='gray',ls='--');axs[row,1].axhline(0,color='black',lw=.6)
        axs[row,1].set(title=identity+' / 누적 에너지 잔차',xlabel='공통창 s',ylabel='예측 - 관측 J');axs[row,1].legend(fontsize=8)
        for ax in axs[row]:ax.grid(alpha=.2)
    fig.suptitle('AP가 시작 후 냉각돼도 시작 전 평균보다 높을 수 있음 / AP 초기경로 오차와 전력 연결을 구분')
    fig.tight_layout();save(fig,out,'C0_AP_energy_paths')

    oracle=m.table(m.BUNDLE/'readout_v1/C0_oracle_attribution.csv');x=np.arange(4)
    fig,ax=plt.subplots(figsize=(11,5))
    for j,(key,name,color) in enumerate((('CPU_AP_future_signed_error_J','CPU＋AP 예측','#ea580c'),('oracle_AP_future_signed_error_J','진단전용: 미래 실측 AP 대입','#6366f1'))):
        ax.bar(x+(j-.5)*.32,[float(r[key]) for r in oracle],width=.32,label=name,color=color)
    ax.axhline(0,lw=.6,color='black');ax.grid(axis='y',alpha=.2)
    ax.set_xticks(x,[r['session'].replace('development','개발').replace('confirmation','확인') for r in oracle],rotation=20,ha='right')
    ax.set(title='4개 C0·같은35..120초 / 미래 실측 AP 대입은 사용 가능한 예측이 아님',ylabel='부호 있는 에너지 오차 J');ax.legend(fontsize=9)
    fig.tight_layout();save(fig,out,'C0_oracle_AP_attribution')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();plot(a.output)
