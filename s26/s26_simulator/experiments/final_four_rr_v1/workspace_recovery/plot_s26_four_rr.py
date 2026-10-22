from pathlib import Path
import csv,gzip,hashlib,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.ticker import FormatStrFormatter

W=Path(__file__).resolve().parents[1];H=W/'S26-D1Check/s26_simulator/experiments/final_four_rr_v1';O=H/'artifacts/G001';OUT=W/'output/S26_RR_20261019';OUT.mkdir(parents=True,exist_ok=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
D=read(O/'SUMMARY.json');RESULT=read(O/'RESULT.json');CASES=read(H/'INPUTS.json')['cases'];METHODS=['FIFO','EDF','RR','OURS'];NAMES=['FIFO','EDF','RR\n큐 순환','우리 정책'];COLORS=['#718096','#377BC1','#D48A35','#078A80'];MARKERS=['o','s','^','D']
font_manager.fontManager.addfont('C:/Windows/Fonts/malgun.ttf');font_manager.fontManager.addfont('C:/Windows/Fonts/malgunbd.ttf')
plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':12,'axes.titlesize':15,'axes.labelsize':12,'xtick.labelsize':11,'ytick.labelsize':10,'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none','figure.facecolor':'white','axes.spines.top':False,'axes.spines.right':False,'grid.color':'#E0E5EA','grid.linewidth':.7})
FOOT='명목 부하 85% · 동일 4입력 × 1,024요청 · CPU3 · 단일 모델 881087 · API-J / AP 모형 예측 (물리 정확도 gate FAIL)'
RR_NOTE='RR: 분류·탐지 큐를 한 건씩 순환하는 비선점 방식. FIFO·EDF·RR 경로 순서 GPU→NPU→CPU.'
series={m:{r['input']:r for r in RESULT['rows'] if r['method']==m} for m in METHODS}
figure_files=[]
def style(ax,ylabel,title,xlabel=True):
    ax.set_title(title,loc='left',fontweight='bold',pad=13);ax.set_ylabel(ylabel,labelpad=9);ax.set_axisbelow(True);ax.grid(axis='y');ax.set_xticks(np.arange(4),NAMES)
    if xlabel:ax.set_xlabel('스케줄링 방식',labelpad=9)
def finish(fig,name,pdf):
    fig.savefig(OUT/(name+'.png'),dpi=220,facecolor='white');fig.savefig(OUT/(name+'.svg'),facecolor='white');pdf.savefig(fig)
    figure_files.extend([OUT/(name+'.png'),OUT/(name+'.svg')]);plt.close(fig)

bundle=OUT/'S26_FIFO_EDF_RR_우리정책_비교그래프.pdf'
with PdfPages(bundle) as pdf:
    pdf.infodict().update(Title='S26 FIFO EDF queue RR and adopted policy comparison',Author='S26 result analysis',Subject=RR_NOTE)
    fig,axs=plt.subplots(2,2,figsize=(14.5,10.5));fig.subplots_adjust(left=.075,right=.96,top=.84,bottom=.19,hspace=.65,wspace=.27)
    fig.suptitle('FIFO · EDF · RR · 우리 정책  |  지표 절대값 비교',fontsize=21,fontweight='bold',y=.97)
    fig.text(.5,.915,'0부터 시작하는 에너지 막대와 확대 범위를 명시한 온도·정시율 점그래프',ha='center',fontsize=12,color='#455365')
    x=np.arange(4);energy=[D[m]['J'] for m in METHODS]
    ax=axs[0,0];ax.bar(x,energy,color=COLORS,width=.59);style(ax,'전체 API 소비 (API-J, 낮을수록 좋음)','A  전체 소비');ax.set_ylim(0,960)
    for i,v in enumerate(energy):ax.text(i,v+17,f'{v:.3f}',ha='center',fontweight='bold',fontsize=11)
    ax=axs[0,1];temps=[D[m]['AP_mean'] for m in METHODS]
    for i,v in enumerate(temps):ax.scatter(i,v,c=COLORS[i],marker=MARKERS[i],s=135,zorder=3);ax.annotate(f'{v:.3f}℃',(i,v),xytext=(0,13),textcoords='offset points',ha='center',fontsize=11,fontweight='bold')
    style(ax,'평균 AP 예측 온도 (℃, 낮을수록 좋음)','B  평균 AP  |  확대 축 38.3~39.8℃');ax.set_ylim(38.3,39.8);ax.set_yticks(np.arange(38.3,39.81,.3));ax.axhline(D['EDF']['AP_mean'],color=COLORS[1],ls=':',lw=1)
    ax=axs[1,0];ons=[D[m]['service']['all']['pooled_on_percent'] for m in METHODS]
    for i,v in enumerate(ons):ax.scatter(i,v,c=COLORS[i],marker=MARKERS[i],s=135,zorder=3);ax.annotate(f'{v:.3f}%',(i,v),xytext=(0,13),textcoords='offset points',ha='center',fontsize=11,fontweight='bold')
    style(ax,'전체 도착 기준 정시율 (%, 높을수록 좋음)','C  전체 정시율  |  확대 축 96.5~97.3%');ax.set_ylim(96.5,97.3);ax.set_yticks(np.arange(96.5,97.31,.2));ax.axhline(D['EDF']['service']['all']['pooled_on_percent'],color=COLORS[1],ls=':',lw=1)
    ax=axs[1,1];bw=.32;overall=[D[m]['service']['all']['mean_case_P95_s'] for m in METHODS];urgent=[D[m]['service']['urgent']['mean_case_P95_s'] for m in METHODS]
    a=ax.bar(x-bw/2,overall,bw,color='#64748B',label='전체 응답 P95');b=ax.bar(x+bw/2,urgent,bw,color='#D98A50',label='긴급 응답 P95')
    style(ax,'완료 응답 P95 회차 평균 (초, 낮을수록 좋음)','D  응답 지연  |  우리 정책의 긴급 지연은 증가');ax.set_ylim(0,2.05);ax.legend(frameon=False,fontsize=10,loc='upper right')
    for bars in [a,b]:
        for bar in bars:ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+.035,f'{bar.get_height():.3f}',ha='center',fontsize=9)
    fig.text(.075,.052,FOOT,fontsize=10,color='#455365');fig.text(.075,.027,RR_NOTE+'  확대 축은 점그래프에만 사용.',fontsize=10,color='#455365')
    finish(fig,'01_absolute_metrics',pdf)

    fig,axs=plt.subplots(3,1,figsize=(9,10.5));fig.subplots_adjust(left=.16,right=.95,top=.85,bottom=.16,hspace=.72)
    fig.suptitle('EDF 대비 차이  |  양수일수록 유리',fontsize=20,fontweight='bold',y=.97)
    fig.text(.5,.925,'막대는 방법별 평균끼리 비교 · 점은 같은 입력별 차이 4개 (신뢰구간 아님)',ha='center',fontsize=10.5,color='#455365')
    kinds=[('energy','전체 API 소비 감소율 (%)','A  에너지 감소',lambda a,b:100*(b['J']-a['J'])/b['J']),('AP','평균 AP 예측 감소 (℃)','B  평균 AP 감소',lambda a,b:b['AP_mean']-a['AP_mean']),('on','전체 정시율 변화 (%p)','C  전체 정시율 변화',lambda a,b:100*a['service']['all']['on_time']/a['service']['all']['planned']-100*b['service']['all']['on_time']/b['service']['all']['planned'])]
    for ax,(key,ylabel,title,func) in zip(axs,kinds):
        if key=='energy':vals=[100*(D['EDF']['J']-D[m]['J'])/D['EDF']['J'] for m in METHODS]
        elif key=='AP':vals=[D['EDF']['AP_mean']-D[m]['AP_mean'] for m in METHODS]
        else:vals=[D[m]['service']['all']['pooled_on_percent']-D['EDF']['service']['all']['pooled_on_percent'] for m in METHODS]
        ax.bar(x,vals,color=COLORS,width=.6,alpha=.85,zorder=2);allv=vals+[0]
        for i,m in enumerate(METHODS):
            dots=[func(series[m][c['id']],series['EDF'][c['id']]) for c in CASES];allv+=dots
            ax.scatter(i+np.array([-.15,-.05,.05,.15]),dots,s=28,facecolor='white',edgecolor='#263442',linewidth=.8,zorder=4)
        lo,hi=min(allv),max(allv);span=max(hi-lo,.3 if key=='on' else .1);ax.set_ylim(lo-span*.28,hi+span*.33)
        ax.axhline(0,color='#273342',lw=1.1,zorder=3);style(ax,ylabel,title);ax.set_xlim(-.55,3.55)
        for i,v in enumerate(vals):
            ax.text(i,.97,f'평균 {v:+.3f}',transform=ax.get_xaxis_transform(),ha='center',va='top',fontweight='bold',fontsize=10.5,color=COLORS[i])
    fig.text(.075,.045,'4입력은 고정 2템플릿 × 잠재 작업량 2개. 표본 수를 실기기 반복 수로 해석하지 않음.',fontsize=9,color='#455365')
    fig.text(.075,.023,'에너지·온도는 모형 예측. EDF=0 기준. 정시율 차이의 단위는 %p이며 상대 변화율 %와 구분.',fontsize=9,color='#455365')
    finish(fig,'02_gap_vs_EDF',pdf)

    fig,ax=plt.subplots(figsize=(14.5,6));fig.subplots_adjust(left=.085,right=.965,top=.80,bottom=.32)
    fig.suptitle('응답 지연의 교환 관계  |  납기 준수와 빠른 응답은 구분',fontsize=20,fontweight='bold',y=.96)
    groups=[('all','전체','#718096'),('urgent','긴급','#D98A50'),('normal','일반','#5A9F94')];bw=.23
    for j,(key,label,color) in enumerate(groups):
        vals=[D[m]['service'][key]['mean_case_P95_s'] for m in METHODS];bars=ax.bar(x+(j-1)*bw,vals,bw,label=label,color=color)
        for bar,v in zip(bars,vals):ax.text(bar.get_x()+bar.get_width()/2,v+.035,f'{v:.3f}',ha='center',fontsize=10)
    style(ax,'완료 응답 P95의 회차 평균 (초, 낮을수록 좋음)','긴급 정시율은 네 방식 모두 100% · 긴급 P95는 우리 정책이 더 큼');ax.set_ylim(0,2.18);ax.legend(title='요청군',ncol=3,frameon=False,loc='upper right')
    fig.text(.085,.09,FOOT,fontsize=10,color='#455365');fig.text(.085,.045,'P95는 각 회차의 95백분위 응답시간을 평균한 값. 전체 응답을 합친 P95가 아님. 미완료는 모든 방식 0.',fontsize=10,color='#455365')
    finish(fig,'03_response_P95',pdf)

    fig,axs=plt.subplots(2,2,figsize=(14.5,10.5));fig.subplots_adjust(left=.075,right=.97,top=.79,bottom=.16,hspace=.40,wspace=.2)
    fig.suptitle('같은 입력에서의 AP 예측 온도 궤적',fontsize=21,fontweight='bold',y=.97)
    fig.text(.5,.92,'35초부터 각 관측 종료까지 · 공통 Y축 · 점선 RR과 실선 FIFO가 겹치는 구간이 있음',ha='center',fontsize=12,color='#455365')
    for ax,c in zip(axs.flat,CASES):
        for m in ['FIFO','RR','EDF','OURS']:
            row=series[m][c['id']];raw=json.loads(gzip.decompress((O/(row['label']+'.raw.json.gz')).read_bytes()));curve=np.array(raw['curve']);curve=curve[curve[:,0]>=35]
            i=METHODS.index(m);ax.plot(curve[:,0],curve[:,1],color=COLORS[i],lw=2.2 if m=='OURS' else 1.25,ls='--' if m=='RR' else '-',label=NAMES[i].replace('\n',' '))
        ax.set_title(f"분류 비중 {c['mix']*100:.0f}% · 잠재 작업량 R{c['replicate']}",loc='left',fontweight='bold');ax.set_xlabel('관측 시간 (초)');ax.set_ylabel('AP 예측 온도 (℃)');ax.set_xlim(35,row['observation_s']);ax.set_ylim(30,49);ax.axhspan(46.6,49,color='#FCE3DF',alpha=.65);ax.axhline(46.6,color='#BD746B',ls=':',lw=1);ax.grid(alpha=.65)
    handles,labels=axs.flat[0].get_legend_handles_labels();fig.legend(handles,labels,ncol=4,loc='upper center',bbox_to_anchor=(.5,.89),frameon=False,fontsize=11)
    fig.text(.075,.065,'붉은 영역: AP 적격 실측 지원 상단 46.6℃ 밖의 외삽 구간. 온도 곡선은 실기기 측정이 아님.',fontsize=10,color='#455365');fig.text(.075,.031,RR_NOTE,fontsize=10,color='#455365')
    finish(fig,'04_AP_time_series',pdf)

with (OUT/'comparison_data.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.writer(f);writer.writerow(['method','energy_API_J','mean_AP_C','overall_on_time_percent','urgent_on_time_percent','normal_on_time_percent_pooled','overall_P95_mean_s','urgent_P95_mean_s','normal_P95_mean_s','unfinished','energy_saving_vs_EDF_percent','AP_reduction_vs_EDF_C','on_time_change_vs_EDF_pp'])
    for m in METHODS:
        q=D[m];s=q['service'];writer.writerow([m,q['J'],q['AP_mean'],s['all']['pooled_on_percent'],s['urgent']['pooled_on_percent'],s['normal']['pooled_on_percent'],s['all']['mean_case_P95_s'],s['urgent']['mean_case_P95_s'],s['normal']['mean_case_P95_s'],q['unfinished'],-q['versus_EDF']['energy_percent'],-q['versus_EDF']['AP_C'],q['versus_EDF']['on_pp']])
meta={'status':'GENERATED_PENDING_VISUAL_QA','RR_definition':RR_NOTE,'methods':METHODS,'selected_model_seed':881087,'source_summary':str(O/'SUMMARY.json'),'source_summary_sha256':sha(O/'SUMMARY.json'),'result_sha256':sha(O/'RESULT.json'),'plot_code_sha256':sha(Path(__file__)),'expanded_axes_only_for_points':True,'energy_bar_starts_zero':True,'uncertainty_bars':False,'paired_dots':'4 fixed-input differences, not confidence intervals','outputs':[dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)) for p in figure_files+[bundle,OUT/'comparison_data.csv']]}
(OUT/'FIGURE_PROVENANCE.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
print(json.dumps({'figures':4,'PNG':4,'SVG':4,'PDF_pages':4,'RR_mean_API_J':D['RR']['J'],'RR_on_time_percent':D['RR']['service']['all']['pooled_on_percent']},ensure_ascii=False))
