"""Tables, matched schedules and offline scientific figures from finished runs."""
import argparse,csv,gzip,html,json,math,statistics
from collections import defaultdict
from pathlib import Path

NAMES={'EDD':'기한 우선＋ECT','MST':'최소 여유＋ECT','CR':'임계비율＋ECT','ATC':'ATC＋ECT',
       'PROTECT':'최소 여유＋CPU 보호','L0':'기존 기한 리스트','Band':'Band 요청 단위 적용',
       'Triton':'Triton 요청 단위 적용','TailRule':'전체 큐 비용 규칙'}
FAMILY={'low':'낮은 부하','queue':'큐 몰림','burst':'순간 몰림','sustained':'지속 부하'}
PHOTOS=('01_판단_규칙.png','02_응답과_기한.png','03_에너지와_AP.png','04_조건별_차이.png','05_실행_시간표.png','06_AP_경로.png')
KPI=('incomplete','urgent_failure','normal_failure','urgent_p95_ms','energy_j','peak_ap_c')
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def csv_write(p,rows):
    if not rows:return
    with Path(p).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def raw(run,identity):return json.loads(gzip.decompress((run/'items'/(identity+'.json.gz')).read_bytes()))
def finite(v):return isinstance(v,(int,float)) and math.isfinite(v)

def publish(run,out):
    run,out=Path(run),Path(out);out.mkdir(parents=True,exist_ok=True)
    stages={stage:read(run/(stage+'_results.json')) for stage in ('development','confirmation') if (run/(stage+'_results.json')).exists()}
    flat=[];paired=[];identical=[]
    for stage,data in stages.items():
        refs={r['condition']:r for r in data['rows'] if r['policy']=='EDD'}
        for r in data['rows']:
            ctl=r['controller'];times=sorted(ctl['decision_seconds']);result=raw(run,r['identity'])['result'];ledger=result['ledger']
            lanes={b:[q for q in ledger if q.get('backend')==b and 'dispatch_ns' in q] for b in ('CPU','GPU')}
            end=lambda q:q.get('lane_available_ns',120e9)
            overlap=sum(max(0,min(end(a),end(b))-max(a['dispatch_ns'],b['dispatch_ns']))/1e9 for a in lanes['CPU'] for b in lanes['GPU'])
            flat.append(dict(stage=stage,condition=r['condition'],arrival_seed=r['case']['seed'],family=r['case']['family'],context=r['case']['context'],
                policy=r['policy'],planned=r['planned'],completed=r['completed'],incomplete=r['incomplete'],
                urgent_failure=r['urgent_failure'],urgent_scheduled=r['urgent_scheduled'],urgent_p95_ms=r['urgent_p95_ms'],
                normal_failure=r['normal_failure'],normal_scheduled=r['normal_scheduled'],normal_mean_ms=r['normal_mean_ms'],
                normal_timely_rate=(r['normal_scheduled']-r['normal_failure'])/r['normal_scheduled'] if r['normal_scheduled'] else None,
                energy_j=r['energy_j'],peak_ap_c=r['peak_ap_c'],surface_temperature_c=None,AP_limit_exceedance_s=None,phone_control_J=None,
                scheduler_PC_p95_ms=times[math.ceil(.95*len(times))-1]*1000 if times else None,scheduler_PC_total_s=sum(times),
                timer_measurement='candidate decisions only' if r['policy'] in ('L0','TailRule') else 'provider callbacks including busy/empty',
                native_seconds=r['native_seconds'],CPU_protect_decisions=ctl['CPU_protect_decisions'],voluntary_wait_s=ctl['voluntary_wait_s'],
                classification_CPU=sum(q['task']=='classification' and q.get('backend')=='CPU' for q in ledger),
                classification_GPU=sum(q['task']=='classification' and q.get('backend')=='GPU' for q in ledger),
                CPU_lane_s=sum(end(q)-q['dispatch_ns'] for q in lanes['CPU'])/1e9,
                GPU_lane_s=sum(end(q)-q['dispatch_ns'] for q in lanes['GPU'])/1e9,parallel_lane_s=overlap,identity=r['identity']))
            if r['policy']=='EDD':continue
            b=refs[r['condition']];baseline=raw(run,b['identity'])['result']
            delta={k:r[k]-b[k] if finite(r[k]) and finite(b[k]) else None for k in KPI}
            nonworse=r['completed']==r['planned']==b['completed']==b['planned'] and all(v is not None and v<=0 for v in delta.values())
            paired.append(dict(stage=stage,policy=r['policy'],condition=r['condition'],arrival_seed=r['case']['seed'],family=r['case']['family'],
                context=r['case']['context'],all_KPI_nonworse=nonworse,service_nonworse=all(delta[k] is not None and delta[k]<=0 for k in KPI[:4]),
                **{'delta_'+k:v for k,v in delta.items()}))
            identical.append(dict(stage=stage,policy=r['policy'],condition=r['condition'],ledger_EDD_exact=result['ledger']==baseline['ledger'],
                transitions_EDD_exact=result['transitions']==baseline['transitions']))
    groups=defaultdict(list)
    for r in flat:groups[(r['stage'],r['policy'])].append(r)
    summary=[]
    for (stage,policy),rows in groups.items():
        average=lambda key:statistics.mean(r[key] for r in rows if finite(r[key])) if any(finite(r[key]) for r in rows) else None
        summary.append(dict(stage=stage,policy=policy,conditions=len(rows),planned=sum(r['planned'] for r in rows),completed=sum(r['completed'] for r in rows),
            incomplete=sum(r['incomplete'] for r in rows),urgent_failure=sum(r['urgent_failure'] for r in rows),normal_failure=sum(r['normal_failure'] for r in rows),
            urgent_p95_mean_ms=average('urgent_p95_ms'),normal_mean_ms=average('normal_mean_ms'),energy_mean_j=average('energy_j'),AP_mean_c=average('peak_ap_c'),
            CPU_protect_decisions=sum(r['CPU_protect_decisions'] for r in rows),PC_p95_condition_mean_ms=average('scheduler_PC_p95_ms')))
    csv_write(out/'evaluation.csv',flat);csv_write(out/'policy_summary.csv',summary);csv_write(out/'EDD_paired_differences.csv',paired);csv_write(out/'schedule_identity.csv',identical)
    reg=read(run/'registration.json')
    gates={stage:{role:{k:v for k,v in g.items() if k!='differences'} for role,g in data['gates'].items()} for stage,data in stages.items()}
    report=dict(task='IE-PRIORITY-COMPARE-02',status='completed_analysis',consumption=read(run/'confirmation_completion.json')['consumption'],latest_shared_consumption=read(run/'progress.json')['consumption'],rows=len(flat),summary=summary,gates=gates,
        EDD_comparison={stage:{role:dict(nonworse=sum(r['all_KPI_nonworse'] for r in paired if r['stage']==stage and r['policy']==role),
            service_nonworse=sum(r['service_nonworse'] for r in paired if r['stage']==stage and r['policy']==role),
            identical_schedule=sum(r['ledger_EDD_exact'] and r['transitions_EDD_exact'] for r in identical if r['stage']==stage and r['policy']==role))
            for role in NAMES if role!='EDD'} for stage in stages},
        selected_policy=[role for role,g in gates.get('confirmation',{}).items() if g['promising']],physical_improvement_claim=False,
        new_learning=0,device_commands=0,tuning_trials=0,scope='fixed A24 coefficients; two fresh arrival seeds confirmatory pilot; no convergence/physical/global optimality claim')
    write(out/'summary.json',report)
    for name in ('registration.json','gate_verification.json'):
        if (run/name).exists():(out/name).write_bytes((run/name).read_bytes())
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    font=Path('C:/Windows/Fonts/malgun.ttf')
    if font.exists():plt.rcParams['font.family']=FontProperties(fname=str(font)).get_name()
    plt.rcParams['axes.unicode_minus']=False
    fig,ax=plt.subplots(figsize=(14,4));ax.axis('off')
    rule_rows=[['기한 우선','절대 기한','원 ECT','기존 기준'],['최소 여유','기한 - 예상 응답','같은 ECT','자원 대기 포함'],
        ['임계비율','남은 기한÷응답 lead','같은 ECT','비율이 작을수록 우선'],['ATC','점유 길이＋기한 긴박함','같은 ECT','k=2 · w=1 고정'],
        ['최소 여유＋CPU 보호','최소 여유','조건부 GPU 변경','도착 탐지 위반 감소/C 기한 유지']]
    table=ax.table(cellText=rule_rows,colLabels=['방법','작업 선택','자원 배정','특징/제한'],loc='center',cellLoc='center',colWidths=[.18,.26,.20,.36])
    table.auto_set_font_size(False);table.set_fontsize(11);table.scale(1,2.1)
    ax.set_title('제조 스케줄링 개념을 앱 응답·실제 lane 반환으로 제한 적용',pad=12);fig.tight_layout();fig.savefig(out/PHOTOS[0],dpi=160);plt.close(fig)
    final='confirmation' if 'confirmation' in stages else 'development';aggregates=[r for r in summary if r['stage']==final];labels=[NAMES[r['policy']] for r in aggregates]
    baseline=next(r for r in aggregates if r['policy']=='EDD')
    for filename,keys,titles in ((PHOTOS[1],('normal_failure','urgent_p95_mean_ms'),('일반 기한 위반 합','조건별 긴급 P95 평균 (ms)')),
        (PHOTOS[2],('energy_mean_j','AP_mean_c'),('EDD 대비 공통120초 에너지 차이 (J)','EDD 대비 최고 AP 차이 (°C)'))):
        fig,axes=plt.subplots(1,2,figsize=(15,5))
        for ax,key,title in zip(axes,keys,titles):
            offset=baseline[key] if filename==PHOTOS[2] else 0.
            ax.bar(range(len(aggregates)),[r[key]-offset if finite(r[key]) else float('nan') for r in aggregates],color=['#2b7a78' if r['policy'] in ('MST','CR','ATC','PROTECT') else '#8191a2' for r in aggregates])
            ax.set_xticks(range(len(aggregates)),labels,rotation=45,ha='right',fontsize=9);ax.set_title(title)
            if filename==PHOTOS[2]:ax.axhline(0,color='black',lw=.6)
        fig.suptitle(('새 확인24조건' if final=='confirmation' else '개발24조건')+' · 같은 예정 요청·기한·모형');fig.tight_layout();fig.savefig(out/filename,dpi=160);plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(13,7),sharex=True)
    for role in ('MST','CR','ATC','PROTECT'):
        rr=[r for r in paired if r['stage']==final and r['policy']==role]
        for ax,key,title in zip(axes.flat,('urgent_p95_ms','normal_failure','energy_j','peak_ap_c'),('긴급 P95 차이 (ms)','일반 기한 위반 차이','에너지 차이 (J)','최고 AP 차이 (°C)')):
            ax.plot([r['condition'] for r in rr],[r['delta_'+key] if finite(r['delta_'+key]) else float('nan') for r in rr],label=NAMES[role]);ax.set_title('EDD 대비 '+title)
    for ax in axes.flat:ax.axhline(0,color='black',lw=.6);ax.set_xlabel('고정 조건 번호')
    axes[0,0].legend(fontsize=8);fig.tight_layout();fig.savefig(out/PHOTOS[3],dpi=160);plt.close(fig)
    condition=reg['representative']['condition'];lo,hi=reg['representative']['window_s'];examples=[]
    for role in ('EDD','MST','ATC','PROTECT'):
        rr=next(r for r in flat if r['stage']==final and r['policy']==role and r['condition']==condition)
        examples.append((role,raw(run,rr['identity'])))
    fig,axes=plt.subplots(4,1,figsize=(13,7),sharex=True)
    for ax,(role,content) in zip(axes,examples):
        for q in content['result']['ledger']:
            if 'dispatch_ns' not in q:continue
            a,b=max(lo,q['dispatch_ns']/1e9),min(hi,q.get('lane_available_ns',120e9)/1e9)
            if b>a:
                y=0 if q['backend']=='CPU' else 1
                ax.broken_barh([(a,b-a)],(y-.3,.6),facecolors='#377eb8' if q['task']=='classification' else '#4daf4a')
                response=(q['arrival_ns']+q.get('response_ns',0))/1e9
                if lo<=response<=hi:ax.plot(response,y,'k.',ms=3)
        ax.set_title(NAMES[role],loc='left');ax.set_yticks([0,1],['CPU','GPU']);ax.set_xlim(lo,hi)
    axes[-1].set_xlabel('같은 대표 trace의 시각 (초)')
    fig.suptitle('실제 lane 점유 · 파랑 분류/초록 탐지/점 응답');fig.tight_layout();fig.savefig(out/PHOTOS[4],dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(13,4))
    for role,content in examples:ax.plot([p[0] for p in content['curve']],[p[1] for p in content['curve']],label=NAMES[role])
    ax.set_xlabel('시각 (초)');ax.set_ylabel('모형 AP (°C)');ax.set_title('사전 고정 대표 조건 · AP35~180초');ax.legend();fig.tight_layout();fig.savefig(out/PHOTOS[5],dpi=160);plt.close(fig)
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><title>산업공학 우선순위 비교</title><style>body{font:15px system-ui;margin:24px;max-width:1600px}img{max-width:100%}table{border-collapse:collapse}th,td{border:1px solid #ddd;padding:6px}th{background:#eee}p{line-height:1.6}</style><h1>산업공학 우선순위·CPU 보호 비교</h1>'
    page+='<p>같은 실측 기반 계수·CPU/GPU·요청·기한. 학습/기기0회. 새 확인은2개 도착 seed의 작은 파일럿이며 실제 휴대폰 우위가 아니다. ATC k=2/w=1은 이번 고정 설정이다.</p>'
    page+='<p>최종 기존 서비스/J/AP 판정 적격: '+(' / '.join(NAMES[r] for r in report['selected_policy']) if report['selected_policy'] else '없음 · 기존 기준 유지')+'.</p><p><a href="README.md">결과·재현</a> · <a href="evaluation.csv">전체 CSV</a> · <a href="EDD_paired_differences.csv">EDD 대비 모든 조건</a></p>'
    if (out/'expert_meeting.md').exists():page+='<p><a href="expert_meeting.md">세 전문가 토론·응답 경계 보완의 개발 결과</a> · <a href="response_development.csv">보완 후보24조건</a></p>'
    page+=''.join('<img alt="'+name+'" src="'+name+'">' for name in PHOTOS)
    page+='<p>필터 <input id="filter" aria-label="조건 필터" placeholder="임계비율 / 새 확인 / 지속"></p><table><thead><tr>'+''.join('<th>'+s+'</th>' for s in ('자료','정책','조건','부하','문맥','완료','긴급 위반','일반 위반','긴급 P95 ms','J120','최고 AP °C'))+'</tr></thead><tbody id="results">'
    columns=('stage','policy','condition','family','context','completed','urgent_failure','normal_failure','urgent_p95_ms','energy_j','peak_ap_c')
    for row in flat:
        def label(k):
            v=row[k]
            return ('새 확인' if v=='confirmation' else '개발') if k=='stage' else NAMES[v] if k=='policy' else FAMILY[v] if k=='family' else '계산 불가' if v is None else f'{v:.4f}' if isinstance(v,float) else str(v)
        page+='<tr>'+''.join('<td>'+html.escape(label(k))+'</td>' for k in columns)+'</tr>'
    page+="</tbody></table><script>document.querySelector('#filter').oninput=function(){let q=this.value.toLowerCase();document.querySelectorAll('#results tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))}</script></html>"
    (out/'index.html').write_text(page,encoding='utf-8',newline='\n')
    (out/'README.md').write_text('# 산업공학 우선순위·CPU 보호 비교\n\n[상세 보고서](../../IE_PRIORITY_COMPARE_20261010.md) · [오프라인 화면](index.html) · [전체 CSV](evaluation.csv) · [EDD 대비 차이](EDD_paired_differences.csv)\n\n원 모형·입력·기한·CPU/GPU 지원·기존 정책 보존. 학습/기기0회. 개발24＋새 확인24×9정책, 작은 고정 설정 비교이며 규칙 계열의 보편 우위를 주장하지 않는다.\n\n재현: `python -B -X utf8 -m tools.d1_ie_priority_compare_report --run output/ie_priority_compare_20261010_v1 --output docs/results/ie_priority_compare_02`\n',encoding='utf-8',newline='\n')
    return dict(status='PASS',rows=len(flat),summary=summary,consumption=report['consumption'],gates=gates)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--run',required=True);a.add_argument('--output',required=True);x=a.parse_args();print(json.dumps(publish(x.run,x.output),ensure_ascii=False,indent=2))
