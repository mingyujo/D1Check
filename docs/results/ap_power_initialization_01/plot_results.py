"""Plot the frozen finite comparison; no fit, device or gain selection."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
BUNDLE=Path(__file__).resolve().parent


def table(p):
    with Path(p).open(encoding='utf8',newline='') as f:return list(csv.DictReader(f))


def save(fig,out,name):
    for suffix in ('png','svg'):
        p=out/(name+'.'+suffix);fig.savefig(p,dpi=150,bbox_inches='tight')
        if suffix=='svg':p.write_text('\n'.join(line.rstrip() for line in p.read_text(encoding='utf8').splitlines())+'\n',encoding='utf8',newline='\n')
    plt.close(fig)


def plot(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':10})
    E=table(BUNDLE/'run_v1/AP_errors.csv');paths=table(BUNDLE/'run_v1/AP_paths.csv')
    labels=[p['id'] for p in json.loads((BUNDLE/'run_v1/pre_inputs.json').read_text(encoding='utf8'))];x=np.arange(12)
    fig,axs=plt.subplots(2,1,figsize=(13,8),sharex=True)
    for ax,phase,title in zip(axs,('common85','full_AP'),('35..120초 관측 표본','35..180초 관측 표본')):
        for j,(variant,name,color) in enumerate((('registered_idle_control','고정 LOAD_SLOW·등록유휴 초기화','#0369a1'),('pre_power_forcing','pre 전력 입력 후보','#ea580c'))):
            values=[float(next(r['MAE_c'] for r in E if r['session']==s and r['phase']==phase and r['variant']==variant)) for s in labels]
            ax.bar(x+(j-.5)*.32,values,width=.32,label=name,color=color)
        ax.axvline(5.5,color='black',ls='--',lw=.7);ax.grid(axis='y',alpha=.2);ax.set(title=title,ylabel='AP MAE °C');ax.legend(fontsize=9)
    axs[-1].set_xticks(x,[s.replace('development','개발').replace('confirmation','확인') for s in labels],rotation=55,ha='right')
    fig.suptitle('고정 계수·같은 마지막 초기AP/시각 / 개발: 반대 회복시간 gain / 확인: 이미 본 사후 평가')
    fig.tight_layout();save(fig,out,'all_session_AP_errors')

    fig,axs=plt.subplots(1,2,figsize=(12,5))
    identity='confirmation_30_C0'
    for variant,name,color in (('registered_idle_control','기존 초기화','#0369a1'),('pre_power_forcing','전력 입력 초기화','#ea580c')):
        rows=[r for r in paths if r['session']==identity and r['variant']==variant]
        axs[0].plot([float(r['t_s']) for r in rows],[float(r['predicted_c']) for r in rows],label=name,color=color)
        if variant=='registered_idle_control':axs[0].plot([float(r['t_s']) for r in rows],[float(r['observed_c']) for r in rows],'.-',label='관측: 평가에만 사용',color='#111')
    axs[0].set(title='회복30 C0: 가열 방향 오류가 남음',xlabel='공통창 s',ylabel='AP °C');axs[0].grid(alpha=.2);axs[0].legend(fontsize=8)
    models=[json.loads((BUNDLE/('run_v1/candidate_'+key+'.json')).read_text(encoding='utf8')) for key in ('30','180','final')]
    positions=np.arange(3)
    for i,m in enumerate(models):
        value=m['gain_C_per_J'];lo,hi=m['constrained_gain_rounding_interval']
        axs[1].errorbar(i,value,yerr=[[value-lo],[hi-value]],fmt='o',capsize=5,color='#0369a1')
    axs[1].axhline(.6587592370628114,color='#dc2626',ls='--',label='회복30 방향전환 필요 gain (적용0)')
    axs[1].set_xticks(positions,['회복30 제외','회복180 제외','개발6 최종'])
    axs[1].set(title='가정한 ±0.05°C 반올림 변동: 신뢰구간 아님',ylabel='gain °C/J');axs[1].grid(alpha=.2);axs[1].legend(fontsize=8)
    fig.tight_layout();save(fig,out,'C0_direction_and_gain_identification')

    rows=table(BUNDLE/'readout_v1/energy_link_summary.csv')
    fig,ax=plt.subplots(figsize=(10,5))
    for j,(variant,name,color) in enumerate((('registered_idle_control','기존 AP 초기화','#0369a1'),('pre_power_forcing','전력 입력 AP 초기화','#ea580c'))):
        values=[float(next(r['mean_abs_J'] for r in rows if r['role']=='confirmation' and r['head']==head and r['phase']=='reference120' and r['variant']==variant)) for head in ('original_frozen','zero_offset')]
        ax.bar(np.arange(2)+(j-.5)*.3,values,width=.3,label=name,color=color)
    ax.set_xticks([0,1],['원4계수＋미채택 전력관계','δ=0 4계수＋미채택 전력관계'])
    ax.set(title='연결 단계 진단: 이전 미채택 관계식 고정 / 원 전력모형 교체·재적합0',ylabel='확인6·120초 평균 절대J');ax.legend();ax.grid(axis='y',alpha=.2)
    fig.tight_layout();save(fig,out,'fixed_energy_relation_link')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();plot(a.output)
