"""All moderate conditions; fixed plotting, no result selection."""
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family']='Malgun Gothic'
plt.rcParams['axes.unicode_minus']=False

def main(out):
    rows=json.loads((out/'WORK_METRICS.json').read_text(encoding='utf-8'))['rows']
    fig,axes=plt.subplots(3,2,figsize=(12,11),layout='constrained')
    for j,duration in enumerate((60,120)):
        for policy in ('EDF','ATC','GUARD_ON_NN','GUARD_OFF_NN'):
            values=[]
            for factor in (.6,.75,.9,1.05,1.2):
                group=[r for r in rows if r['policy']==policy and r['condition']['supply_s']==duration and r['condition']['rate_multiplier']==factor]
                refs=[next(b for b in rows if b['case']==r['case'] and b['policy']=='EDF') for r in group]
                energy=None if any(r['completion'] is None for r in group+refs) else 100*(1-sum(r['completion']['total_J_proxy'] for r in group)/sum(r['completion']['total_J_proxy'] for r in refs))
                values.append((factor,100*sum(r['original']['on_time'] for r in group)/sum(r['n'] for r in group),energy,sum(b['common']['mean_AP_c']-r['common']['mean_AP_c'] for b,r in zip(refs,group))/2))
            for i in range(3):axes[i,j].plot([v[0] for v in values],[v[i+1] for v in values],marker='o',label=policy)
        for i,label in enumerate(('전체 도착 정시율 (%)','자기완료 총소비 절감 vs EDF (%)','공통창 평균 AP 감소 vs EDF (℃)')):
            axes[i,j].set(xlabel='도착률 배수',ylabel=label,title=f'공급 {duration}초 · 두 파형 모두 포함');axes[i,j].grid(alpha=.25)
        axes[0,j].legend(fontsize=8)
    fig.suptitle('중간 부하: 납기보호 ON/OFF · 원모형/고정 NN\n가설모형 기술값; 납기/온도창 적격성은 전수표 비고 참조')
    fig.savefig(out/'MODERATE.png',dpi=150);fig.savefig(out/'MODERATE.svg');plt.close(fig)
