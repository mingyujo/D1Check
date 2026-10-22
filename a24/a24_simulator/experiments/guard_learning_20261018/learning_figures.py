import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family']='Malgun Gothic';plt.rcParams['axes.unicode_minus']=False

def main(out):
    data=json.loads((out/'POLICY_COMPARISON.json').read_text(encoding='utf-8'))['rows']
    fig,axes=plt.subplots(3,2,figsize=(12,11),layout='constrained')
    for j,duration in enumerate((60,120)):
        for policy in ('FT_ON_NN','FT_OFF_NN','REPAIR_OFF_NN'):
            rates=sorted({r['condition']['rate_multiplier'] for r in data if r['condition']['supply_s']==duration})
            values=[]
            for rate in rates:
                group=[r for r in data if r['policy']==policy and r['condition']['supply_s']==duration and r['condition']['rate_multiplier']==rate]
                J=None if any(r['completion_J_proxy'] is None for r in group) else 100*(1-sum(r['completion_J_proxy'] for r in group)/sum(r['EDF_completion_J_proxy'] for r in group))
                values.append((100*sum(r['on_time'] for r in group)/sum(r['n'] for r in group),J,sum(r['temperature_reduction_c'] for r in group)/len(group)))
            for i in range(3):axes[i,j].plot(rates,[r[i] for r in values],marker='o',label=policy)
        for i,label in enumerate(('전체 도착 정시율 (%)','완료 총소비 절감 vs EDF (%)','평균 AP 감소 vs EDF (℃)')):
            axes[i,j].set(xlabel='도착률 배수',ylabel=label,title=f'공급 {duration}초');axes[i,j].grid(alpha=.25)
        axes[0,j].legend(fontsize=8)
    fig.suptitle('같은 초기 NN · 각32학습 · 최종 EP32 고정\n모든 조건 표시; 납기/온도창 적격성은 전수표 비고 참조')
    fig.savefig(out/'LEARNING.png',dpi=150);fig.savefig(out/'LEARNING.svg');plt.close(fig)
