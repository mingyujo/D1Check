"""Plot only closed public C8 analyses. No device, model, or private inputs."""
import argparse,csv,hashlib,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('report',type=Path);args=parser.parse_args()
base=args.report
with (base/'closed_results.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
by_arm={r['arm']:r for r in rows};arms=[a for a in ['BASE','WAIT200','PAIR_G'] if a in by_arm]
names={'BASE':'직렬 기본\n(BASE)','WAIT200':'200ms 대기\n(WAIT)','PAIR_G':'병행 실행\n(PAIR)'}
analyses=[json.loads((base/'new_closed_analysis'/(by_arm[a]['session_id']+'.analysis.json')).read_text(encoding='utf-8')) for a in arms]
assert len(analyses)==3 and all(x['trace']['completed_in_service']==128 and x['decoded_quality']['failures']==0 for x in analyses)
assert all(x['thermal']['status']=='READOUT_WINDOW_COVERED' for x in analyses)
plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':10})
fig,axs=plt.subplots(1,3,figsize=(14,4.6));xx=np.arange(len(arms));width=.34
for key,offset,color,label in [('C',-width/2,'#2563eb','긴급 분류'),('D',width/2,'#14b8a6','일반 탐지')]:
    services=[a['service'][key] for a in analyses];ys=[100*s['on_time']/s['planned'] for s in services]
    axs[0].bar(xx+offset,ys,width,color=color,label=label)
    for i,(y,s) in enumerate(zip(ys,services)):axs[0].text(i+offset,y+2,f"{s['on_time']}/{s['planned']}",ha='center',fontsize=9)
axs[0].set_ylim(0,115);axs[0].set_ylabel('기한 내 완료율 (%)');axs[0].set_title('기한을 지킨 요청');axs[0].legend(loc='upper left',fontsize=9)
p95=[a['service']['C']['response_P95_ms_service_successes']/1000 for a in analyses]
axs[1].bar(xx,p95,color=['#64748b','#f59e0b','#14b8a6'][:len(arms)])
for i,y in enumerate(p95):axs[1].text(i,y+.25,f'{y:.2f}초',ha='center')
axs[1].set_ylim(0,max(p95)*1.22);axs[1].set_ylabel('P95 응답시간 (초)');axs[1].set_title('긴급 응답 — 낮을수록 빠름')
mean=[a['thermal']['mean_reported_AP_c'] for a in analyses];peak=[a['thermal']['highest_observed_AP_c'] for a in analyses]
axs[2].plot(xx,mean,'o-',color='#2563eb',label='공통창 AP 평균');axs[2].plot(xx,peak,'s--',color='#ef4444',label='관측 최고 AP')
for i,(m,p) in enumerate(zip(mean,peak)):
    axs[2].annotate(f'{m:.2f}℃',(i,m),xytext=(0,-17),textcoords='offset points',ha='center',fontsize=9)
    axs[2].annotate(f'{p:.1f}℃',(i,p),xytext=(0,8),textcoords='offset points',ha='center',fontsize=9)
axs[2].set_ylim(28.6,31.4);axs[2].set_ylabel('보고된 HAL AP (℃)');axs[2].set_title('열 절감은 확인되지 않음');axs[2].legend(loc='upper left',fontsize=9)
for ax in axs:
    ax.set_xticks(xx,[names[a] for a in arms]);ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
fig.suptitle('A24 혼합 요청 128건 × 3조건 — 같은 입력·공통 기준 28.4℃',fontsize=14,fontweight='bold')
fig.text(.5,.015,'각 조건 128건 전량 완료·출력 오류 0 | ORDER 미실행 | J 미판정 · AP는 실제 표면온도 검증값이 아님 · 이번 1개 묶음의 결과',ha='center',fontsize=9)
fig.tight_layout(rect=[0,.05,1,.92]);dest=base/'service_AP_comparison.png';fig.savefig(dest,dpi=160);plt.close(fig)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
(base/'PLOT_PROVENANCE.json').write_text(json.dumps({'matplotlib_version':matplotlib.__version__,
    'code_sha256':sha(Path(__file__)),'closed_results_csv_sha256':sha(base/'closed_results.csv'),
    'figure_sha256':sha(dest),'closed_conditions':len(analyses),'new_device_commands':0,'new_inferences':0},indent=2)+'\n',encoding='utf-8')
print('FIGURE_READY',dest.as_posix())
