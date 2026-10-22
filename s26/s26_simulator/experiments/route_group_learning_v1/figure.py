"""Saved scientific primary85% figure; CPU3 assumption stated explicitly."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
H=Path(__file__).resolve().parent;O=H/'artifacts/G001';summary=json.loads((O/'COMPARISON_SUMMARY.json').read_text(encoding='utf-8'));data={g['method']:g for g in summary['groups'] if g['load']==.85}
font=Path('C:/Windows/Fonts/malgun.ttf')
if font.exists():font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(font)).get_name()
plt.rcParams['axes.unicode_minus']=False
methods=['EDF_GPU_FIRST','ATC','ATC_SALVAGE','OLD_RL','BC_FROZEN','EVENT_PPO'];names=['EDF','ATC','보완 ATC','기존 RL','교사학습\n후 고정','보완 RL\n3seed 평균'];colors=['#7b8792','#4b87b4','#44937b','#a78cb3','#b3a66c','#dc8c4d']
fig,axes=plt.subplots(1,3,figsize=(14,5),layout='constrained')
for ax,(key,title) in zip(axes,[('on_percent','납기 준수율 (%)'),('mean_API_J','전체 에너지 (API-J, 모형)'),('mean_AP_C','평균 AP 온도 (℃, 예측)')]):
    values=[data[m][key] for m in methods];bars=ax.bar(range(6),values,color=colors);ax.set_xticks(range(6),names,fontsize=9);ax.set_title(title);ax.set_ylim(0,max(values)*1.14);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);ax.spines[['top','right']].set_visible(False)
    for b,v in zip(bars,values):ax.text(b.get_x()+b.get_width()/2,b.get_height()+max(values)*.025,f'{v:.2f}',ha='center',fontsize=9)
fig.suptitle('S26 · 명목 부하85% · CPU 서비스 최대3개 병렬 가정\n동일 입력 비교 / 전력·열 예측 정확도 미검증 / 실제 기기 절감 인증 아님',fontsize=13)
fig.savefig(O/'PRIMARY85_EVENT_COMPARISON.png',dpi=160);print('EVENT_FIGURE_SAVED')
