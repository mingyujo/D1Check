"""Plot recovered information and observed associations, no fit or device commands."""
import argparse,csv,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
ROOT=Path(__file__).resolve().parent


def rows(file):
    with Path(file).open(encoding='utf8',newline='') as f:return list(csv.DictReader(f))


def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':11})
    metrics=rows(ROOT/'run_v1/AP_metrics.csv');paths=rows(ROOT/'run_v1/AP_paths.csv')
    choice=rows(ROOT/'run_v1/preonly_choice.csv');pre=json.loads((ROOT/'run_v1/expanded_pre.json').read_text(encoding='utf8'))
    fig,axes=plt.subplots(2,1,figsize=(14,8))
    for ax,role,label in zip(axes,('development','confirmation'),('기존 개발6','이미 본 확인6 / 사후 분석')):
        ids=[r['session'] for r in choice if r['role']==role];x=np.arange(len(ids))
        for i,(variant,name) in enumerate([('existing_short_pre','기존 약60초 초기화'),('registered_idle_pre','등록 유휴기록 전체')]):
            values=[float(next(r for r in metrics if r['session']==identity and r['variant']==variant)['mae_c']) for identity in ids]
            ax.bar(x+(i-1)*.25,values,.25,label=name)
        ax.bar(x+.25,[float(next(r for r in choice if r['session']==identity)['mae_c']) for identity in ids],.25,label='부하 전 1표본 선택')
        ax.set_xticks(x,ids,rotation=25,ha='right',fontsize=9);ax.set_ylabel('AP 경로 MAE (°C)');ax.set_title(label);ax.legend(fontsize=9)
    fig.suptitle('계수·최종 초기AP 불변 / 추가 과거정보 효과와 악화 동시 공개')
    fig.tight_layout();fig.savefig(out/'all_history_initialization.png',dpi=140);plt.close(fig)
    identity='confirmation_180_C0';initial=next(r['expanded_pre'] for r in pre if r['id']==identity)
    old=[r for r in paths if r['session']==identity and r['variant']=='existing_short_pre'];new=[r for r in paths if r['session']==identity and r['variant']=='registered_idle_pre']
    fig,ax=plt.subplots(figsize=(12,5))
    ax.plot([r['t'] for r in initial],[r['ap'] for r in initial],color='#1d3557',label='복원한 부하 전 AP')
    ax.plot([float(r['t_s']) for r in old],[float(r['observed_c']) for r in old],color='black',label='실제 이후 AP')
    ax.plot([float(r['t_s']) for r in old],[float(r['predicted_c']) for r in old],label='기존 초기화')
    ax.plot([float(r['t_s']) for r in new],[float(r['predicted_c']) for r in new],label='전체 등록유휴 초기화')
    ax.axvspan(-30,35,color='#ddd',alpha=.45,label='기존 초기화 입력 구간');ax.axvline(35,color='#555',ls='--')
    ax.set_xlabel('동일 Android 원점 기준 초');ax.set_ylabel('AP (°C)');ax.legend(fontsize=9)
    ax.set_title('동일 마지막 AP·시각 / 과거정보만 확장: C0 확인 MAE0.339→0.068°C')
    fig.tight_layout();fig.savefig(out/'C0_initial_information.png',dpi=140);plt.close(fig)
    data=rows(ROOT/'run_v1/matched_C0_CPU_context.csv')
    selected=[next(r for r in data if r['session']==s and r['phase']==phase) for s in ('development_30_C0','confirmation_30_C0') for phase in ('pre50','future85_idle')]
    x=np.arange(4);fig,axes=plt.subplots(1,2,figsize=(12,5))
    axes[0].bar(x,[float(r['mean_device_power_W']) for r in selected]);axes[0].set_ylabel('기기 전체 평균 전력 (W)')
    axes[1].bar(x,[float(r['other_cpu_seconds'])/float(r['seconds']) for r in selected]);axes[1].set_ylabel('other 분류 CPU seconds / wall second')
    for ax in axes:ax.set_xticks(x,['개발 pre50','개발 이후85','확인 pre50','확인 이후85'],rotation=15);ax.set_ylim(bottom=0)
    fig.suptitle('같은 C0·30초회복: pre구간의 추가 활동 / 이후는 유사 · 인과J 귀속은 아님')
    fig.tight_layout();fig.savefig(out/'C0_baseline_CPU_association.png',dpi=140);plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();run(a.output)
