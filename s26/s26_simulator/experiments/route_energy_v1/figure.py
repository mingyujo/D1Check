"""Static scientific comparison of the saved primary85% condition."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
H=Path(__file__).resolve().parent;O=H/'artifacts/G001';s=json.loads((O/'COMPARISON_SUMMARY.json').read_text(encoding='utf-8'))
font=Path('C:/Windows/Fonts/malgun.ttf')
if font.exists():font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(font)).get_name()
plt.rcParams['axes.unicode_minus']=False
order=['EDF_GPU_FIRST','ATC','ATC_SALVAGE','FROZEN_RL','BALANCED_RL','ENERGY_ONLY']
names=['EDF','ATC','보완 ATC','기존 RL','보완 RL\n3seed 평균','에너지 전용\n진단']
colors=['#74838b','#4c87ba','#43917a','#a18bb1','#df9351','#cc6661']
fig,axes=plt.subplots(3,2,figsize=(13,11),layout='constrained')
for col,model in enumerate(['CENTRAL','CPU3']):
    data={r['method']:r for r in s['groups'] if r['model']==model and r['load']==.85}
    for row,(key,label) in enumerate([('on_percent','납기 준수율 (%)'),('mean_API_J','전체 에너지 (API-J, 모형)'),('mean_AP_C','평균 AP 온도 (℃, 예측)')]):
        ax=axes[row,col];values=[data[m][key] for m in order];bars=ax.bar(range(6),values,color=colors)
        ax.set_xticks(range(6),names,fontsize=9);ax.set_ylabel(label);ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
        if row==0:ax.set_ylim(0,110)
        else:ax.set_ylim(0,max(values)*1.16)
        for b,v in zip(bars,values):ax.text(b.get_x()+b.get_width()/2,b.get_height()+max(values)*.02,f'{v:.2f}',ha='center',fontsize=9)
        if row==0:ax.set_title('기존 CPU 서비스1개' if model=='CENTRAL' else 'CPU 서비스 최대3개 병렬 가정')
fig.suptitle('S26 · 명목 부하85% · 같은 CPU 가정 안에서 정책 비교\n미완료·납기 손해가 있는 소비 감소는 동등 서비스 절감으로 인정하지 않음',fontsize=14)
fig.savefig(O/'PRIMARY85_COMPARISON.png',dpi=160)
print('FIGURE_SAVED',str(O/'PRIMARY85_COMPARISON.png'))
