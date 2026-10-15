"""Plot previously computed conditional energy; no device or analysis changes."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def render(run, destination):
    pairs=json.loads((run/'pairs.json').read_text(encoding='utf-8'))
    rows=[r for r in pairs if (r['window_start_s'],r['window_end_s'])==(0,180)]
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':11})
    fig,axes=plt.subplots(1,2,figsize=(14,6.8),gridspec_kw={'width_ratios':[1.25,1]})
    names={'GPU':'GPU 배정','PAIR_G':'병행 허용','ORDER':'납기순 EDD','WAIT200':'200ms 대기'}
    recipes={'C252':'분류252','L64':'저부하64','M128':'혼합128'}
    stages={'DEV':'개발','CONFIRM':'확인'}
    labels=[f"{stages[r['stage']]} · {recipes[r['recipe']]} · {names[r['treatment']]}" for r in rows]
    changes=[-r['reduction_pct'] for r in rows]
    colors=['#367bb3' if r['stage']=='DEV' else '#df8935' for r in rows]
    axes[0].barh(range(len(rows)),changes,color=colors)
    axes[0].set_yticks(range(len(rows)),labels);axes[0].invert_yaxis();axes[0].axvline(0,color='#333333',lw=1)
    axes[0].set_xlim(-4,4);axes[0].set_xlabel('기준 대비 추정 에너지 변화 (%)\n음수: 감소 · 양수: 증가')
    axes[0].set_title('같은 180초의 기기 전체 소비')
    for i,v in enumerate(changes):axes[0].text(v+(.08 if v>=0 else -.08),i,f'{v:+.2f}%',va='center',ha='left' if v>=0 else 'right',fontsize=10)
    windows=[(0,180),(0,35),(35,120),(120,180)]
    for i,stage in enumerate(('DEV','CONFIRM')):
        sub=[next(r for r in pairs if r['recipe']=='M128' and r['treatment']=='PAIR_G' and r['stage']==stage and (r['window_start_s'],r['window_end_s'])==w) for w in windows]
        axes[1].bar([j+(i-.5)*.36 for j in range(4)],[r['delta_J_mA_hypothesis'] for r in sub],width=.36,label=stages[stage],color=('#367bb3','#df8935')[i])
    axes[1].set_xticks(range(4),['전체\n0–180초','요청 전\n0–35초','35–120초','후반\n120–180초'])
    axes[1].axhline(0,color='#333333',lw=1);axes[1].set_ylabel('병행 - 직렬 추정 에너지 (J)');axes[1].legend()
    axes[1].set_title('혼합 부하: 구간을 바꾸면 무엇이 달라지나')
    fig.suptitle('A24 조건부 에너지 비교 — 전류 mA 가정',fontsize=17)
    fig.text(.5,.025,'개발·확인 각 1블록의 사후 분석 · 검증된 절감률 아님 · 준비/워밍업/냉각은 관측창 밖\n기한 준수·응답과 함께 해석하며, 후반 구간만 선택해 전체 절감으로 판정하지 않음',ha='center',fontsize=10)
    fig.tight_layout(rect=[0,.09,1,.94])
    for suffix in ('.png','.svg'):
        path=destination.with_suffix(suffix)
        if path.exists():raise FileExistsError(path)
        fig.savefig(path,dpi=160)
    plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('run',type=Path);parser.add_argument('destination',type=Path)
    args=parser.parse_args();render(args.run,args.destination)
