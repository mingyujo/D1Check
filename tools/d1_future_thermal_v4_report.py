"""Exact-cost speed preservation and future-scenario outcome reporting."""
import csv,gzip,html,json,statistics,time
from tools import d1_future_thermal_v4_study as s
from tools.d1_edd_ect_residual_report import compare
ROOT=s.ROOT;BUNDLE=s.BUNDLE;LOCAL=s.LOCAL;read=s.read;write=s.write
NEW=(s.fast.FAST,s.x.ROBUST,s.x.EMPIRICAL)
LABELS={s.BAND:'Band 요청 적용',s.TRITON:'Triton 고정 자원',s.EDD:'기한 우선 ECT',s.OLD:'기존 작업량 열 분산',s.fast.FAST:'같은 판단 경량화',s.x.ROBUST:'미래 최악 가정',s.x.EMPIRICAL:'미래 관측 빈도'}
RULES={s.BAND:'원 Band 요청 규칙',s.TRITON:'원 고정 자원 규칙',s.EDD:'원 EDD·ECT',s.OLD:'기존 도착큐 예측·작업량 허용',s.fast.FAST:'같은 전체 후보·원식 벡터화',s.x.ROBUST:'실제 Band/대기·관측 미래가정 최악 AP',s.x.EMPIRICAL:'같은 행동·서비스/J검사·관측 빈도 AP'}

def csv_write(path,rows):
    with path.open('w',encoding='utf8',newline='') as f:
        fields=list(dict.fromkeys(k for r in rows for k in r));w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
def load_items():
    receipts={r['identity']:r for r in s.events() if r['event']=='completed'};items={}
    for path in (LOCAL/'items').glob('*.gz'):
        item=json.loads(gzip.decompress(path.read_bytes()));identity=item['row']['identity'];assert receipts[identity]['artifact_sha256']==s.sha(path);items[identity]=item
    return items
def controlled_benchmark():
    if (BUNDLE/'controlled_benchmark.json').exists():return read(BUNDLE/'controlled_benchmark.json')
    from tools.test_d1_ie_dispatch import ticket,lanes
    frozen,_=s.fast.p.inputs(s.fast.p.BUNDLE);initial=read(BUNDLE/'inputs.json')['initial'];c=s.fast.prior.Controller(frozen,initial);c.observe(35e9,lanes())
    queue=[ticket('d0',0,'detection',35.,6.),ticket('c0',1),ticket('d1',2,'detection',35.,6.),ticket('c1',3)];action=dict(jobs=[])
    timings={'old':[],'fast':[]};max_error=0.
    for repeat in range(20):
        values={}
        for kind in (('old','fast') if repeat%2==0 else ('fast','old')):
            began=time.perf_counter();value=s.fast.old.Controller.forecast(c,queue,lanes(),35e9,action,'mean') if kind=='old' else s.fast.forecast(c,queue,lanes(),35e9,action,'mean')
            timings[kind].append(time.perf_counter()-began);values[kind]=value
        for key in ('peak_ap_c','global_peak_ap_c','remaining_increment_j','urgent_p95_ms'):max_error=max(max_error,abs(values['old'][key]-values['fast'][key]))
    assert max_error<1e-8
    answer=dict(repeated_pairs=20,old_median_ms=statistics.median(timings['old'])*1000,fast_median_ms=statistics.median(timings['fast'])*1000,
        speedup=statistics.median(timings['old'])/statistics.median(timings['fast']),maximum_numeric_difference=max_error,
        scope='same-process alternating order, same4-request pure forecast input; not native environments, independent traces, phone latency or energy',new_environment_starts=0,device_commands=0)
    write(BUNDLE/'controlled_benchmark.json',answer);return answer
def report():
    assert read(BUNDLE/'completion.json')['status']=='completed';s.check();items=load_items();rows=read(BUNDLE/'final_rows.json');dev=read(BUNDLE/'development_rows.json');assert len(rows)==168 and len(dev)==144
    by={(r['seed'],r['family'],r['context'],r['policy']):r for r in rows};pairs=[];summaries=[];speed=[];diagnostics=[]
    for row in rows:
        if row['policy']==s.BAND:continue
        refs=[by[row['seed'],row['family'],row['context'],p] for p in (s.BAND,s.TRITON)];b,t=[compare(row,r) for r in refs]
        both=b['nonworse'] and t['nonworse'];heat=b['heat_gain'] and t['heat_gain'];joint=b['joint_gain'] and t['joint_gain']
        category='서비스 악화' if not b['service_preserved'] or not t['service_preserved'] else '비용 상충' if not both else 'J·AP 공동감소' if joint else 'J 비악화·열감소' if heat else '비악화·열차 없음'
        pairs.append(dict(seed=row['seed'],family=row['family'],context=row['context'],policy=row['policy'],primary=row['family'] in ('low','sustained'),**b,nonworse_both=both,heat_gain_both=heat,joint_gain_both=joint,category=category))
    for policy in s.POLICIES:
        group=[r for r in rows if r['policy']==policy];pp=[r for r in pairs if r['policy']==policy]
        summaries.append(dict(policy=policy,conditions=24,planned=sum(r['planned'] for r in group),completed=sum(r['completed'] for r in group),urgent_failures=sum(r['urgent_service_failure'] for r in group),normal_failures=sum(r['normal_service_failure'] for r in group),
            urgent_p95_ms=statistics.mean(r['urgent_p95_ms'] for r in group),normal_mean_ms=statistics.mean(r['normal_mean_ms'] for r in group),energy_j=statistics.mean(r['energy_j'] for r in group),peak_ap_c=statistics.mean(r['peak_ap_c'] for r in group),
            nonworse_both=sum(r['nonworse_both'] for r in pp),heat_gain_both=sum(r['heat_gain_both'] for r in pp),joint_gain_both=sum(r['joint_gain_both'] for r in pp),decision_host_total_s=sum(r['decision_host_total_s'] for r in group),decision_host_max_ms=max(r['decision_host_max_ms'] for r in group)))
    for case in read(BUNDLE/'inputs.json')['cases']['final']:
        old=by[case['seed'],case['family'],case['context'],s.OLD];fast=by[case['seed'],case['family'],case['context'],s.fast.FAST]
        equal=s.physical(items[old['identity']]['result'])==s.physical(items[fast['identity']]['result']);assert equal,'fresh fast policy semantic drift'
        speed.append(dict(seed=case['seed'],family=case['family'],context=case['context'],ledger_equal=equal,old_decision_s=old['decision_host_total_s'],fast_decision_s=fast['decision_host_total_s'],speedup=old['decision_host_total_s']/fast['decision_host_total_s']))
    for identity,item in items.items():
        if not identity.startswith('final/') or item['row']['policy'] not in NEW:continue
        diagnostics.append(dict(identity=identity,policy=item['row']['policy'],seed=item['row']['seed'],family=item['row']['family'],context=item['row']['context'],cool_wait_choices=item['row']['cool_wait_choices'],projection_calls=item['row']['projection_calls'],future_scenario_batches=item['row']['future_scenario_batches']))
    selection=read(BUNDLE/'selection.json');first=min(e['utc'] for e in s.events() if e['event']=='start' and e['identity'].startswith('final/'));assert selection['utc']<first
    chosen=selection['chosen'];cp=[p for p in pairs if p['policy']==chosen]
    summary=dict(status='completed',selected_before_final=chosen,selected_final_accepted=bool(chosen and all(p['nonworse_both'] for p in cp) and all(any(p['heat_gain_both'] and p['primary'] and p['seed']==seed for p in cp) for seed in (814020101,814020102))),
        development_rows=144,development_reused_rows=96,final_rows=168,final_planned=sum(r['planned'] for r in rows),final_completed=sum(r['completed'] for r in rows),
        original_engine_successes=len(items),total_planned=sum(i['row']['planned'] for i in items.values()),total_completed=sum(i['row']['completed'] for i in items.values()),consumption=read(BUNDLE/'completion.json')['consumption'],
        old_fast_preservation_equal=8,old_fast_fresh_equal=sum(r['ledger_equal'] for r in speed),paired_old_decision_s=sum(r['old_decision_s'] for r in speed),paired_fast_decision_s=sum(r['fast_decision_s'] for r in speed),
        paired_host_speedup=sum(r['old_decision_s'] for r in speed)/sum(r['fast_decision_s'] for r in speed),
        new_heat_gain_both={p:sum(r['heat_gain_both'] for r in pairs if r['policy']==p) for p in NEW},new_joint_gain_both={p:sum(r['joint_gain_both'] for r in pairs if r['policy']==p) for p in NEW},
        new_service_regression_vs_Band={p:sum(not r['service_preserved'] for r in pairs if r['policy']==p) for p in NEW},no_policy_default_change=True,experiment_ready=False,new_training=0,physical_improvement_proven=False,
        scope='fresh whole-arrival PC traces; fixed original measurement-based model; synthetic future only in forecasts; fast same-rule parity distinguished from future narrower action pool',controlled_benchmark=controlled_benchmark())
    csv_write(BUNDLE/'policy_summary.csv',summaries);csv_write(BUNDLE/'pairs_vs_band.csv',pairs);csv_write(BUNDLE/'speed_pairs.csv',speed);csv_write(BUNDLE/'decision_diagnostics.csv',diagnostics)
    csv_write(BUNDLE/'development_results.csv',dev);csv_write(BUNDLE/'final_results.csv',rows);csv_write(BUNDLE/'execution_receipts.csv',[{k:e.get(k) for k in ('event','utc','number','identity','kind','source_sha256','error')} for e in s.events()]);write(BUNDLE/'summary.json',summary)
    representative=read(BUNDLE/'registration.json')['representative'];reps={p:items[next(r['identity'] for r in rows if r['policy']==p and all(r[k]==v for k,v in representative.items()))] for p in s.POLICIES}
    write(BUNDLE/'representatives.json',{p:dict(row=i['row'],ledger=i['result']['ledger'],curves=i['curves']) for p,i in reps.items()});plots(pairs,summaries,reps);dashboard(pairs,summaries,summary);return summary
def plots(pairs,summaries,reps):
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False});out=BUNDLE/'figures';out.mkdir(exist_ok=True)
    fig,ax=plt.subplots(figsize=(11,6),layout='constrained')
    for p in NEW:
        group=[r for r in pairs if r['policy']==p];good=[r for r in group if r['service_preserved']];bad=[r for r in group if not r['service_preserved']]
        ax.scatter([r['delta_energy_j'] for r in good],[r['delta_peak_ap_c'] for r in good],label=LABELS[p],alpha=.65)
        if bad:ax.scatter([r['delta_energy_j'] for r in bad],[r['delta_peak_ap_c'] for r in bad],marker='x',label=LABELS[p]+' 서비스 악화',alpha=.65)
    ax.axhline(0,color='grey');ax.axvline(0,color='grey');ax.set_xlabel('같은 조건 Band 대비 J 차이');ax.set_ylabel('같은 조건 Band 대비 AP 최고 차이 °C');ax.legend(fontsize=9);ax.grid(alpha=.2);ax.set_title('전체 도착열의 열·에너지 상충 — 서비스와 함께 해석');fig.savefig(out/'01_열에너지상충.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(14,5),layout='constrained')
    for ax,key,label in zip(axes,('urgent_p95_ms','normal_failures'),('조건별 긴급 P95 평균 ms','일반 기한 실패 건')):
        ax.bar(range(len(s.POLICIES)),[r[key] for r in summaries]);ax.set_xticks(range(len(s.POLICIES)),[LABELS[r['policy']] for r in summaries],rotation=35,ha='right');ax.set_ylabel(label);ax.grid(axis='y',alpha=.2)
    fig.suptitle('확인24조건의 서비스 — 전체 요청을 분모에 포함');fig.savefig(out/'02_응답과기한완료.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(len(s.POLICIES),1,figsize=(13,11),sharex=True,layout='constrained')
    for ax,(policy,item) in zip(axes,reps.items()):
        for r in item['result']['ledger']:
            if r.get('dispatch_ns') is None:continue
            a=r['dispatch_ns']/1e9;b=r.get('lane_available_ns',120e9)/1e9;y=0 if r['backend']=='CPU' else 1
            ax.broken_barh([(a,b-a)],(y-.28,.56),facecolors='#397cb3' if r['priority']=='urgent' else '#eda040')
        ax.set_yticks([0,1],['CPU','GPU']);ax.set_title(LABELS[policy],loc='left',fontsize=10);ax.grid(axis='x',alpha=.2)
    axes[-1].set_xlim(35,50);axes[-1].set_xlabel('공통 시간 초 — 첫15초 고정 확대');fig.suptitle('사전 대표 첫 확인 seed·낮은 부하·평균의 실제 lane 점유');fig.savefig(out/'03_대표작업시간표.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(14,5),layout='constrained')
    for p in (s.BAND,s.OLD,s.fast.FAST,s.x.ROBUST,s.x.EMPIRICAL):
        c=reps[p]['curves'];axes[0].plot(c['ap_times_s'],c['ap_path'],label=LABELS[p])
    axes[0].set_xlabel('초');axes[0].set_ylabel('동일 AP 모형 °C');axes[0].legend(fontsize=9);axes[0].grid(alpha=.2)
    axes[1].bar(range(len(s.POLICIES)),[r['energy_j'] for r in summaries]);axes[1].set_xticks(range(len(s.POLICIES)),[LABELS[r['policy']] for r in summaries],rotation=35,ha='right');axes[1].set_ylabel('공통120초 기기 전체 J 평균');fig.suptitle('원계수·초기 상태 보존 — 실제 표면온도/절감과 구분');fig.savefig(out/'04_온도경로와에너지.png',dpi=150);plt.close(fig)
    policies=list(NEW);keys=sorted({(r['seed'],r['family'],r['context']) for r in pairs});names=['서비스 악화','비용 상충','비악화·열차 없음','J 비악화·열감소','J·AP 공동감소'];codes={n:i for i,n in enumerate(names)}
    matrix=[[codes[next(r['category'] for r in pairs if r['policy']==p and (r['seed'],r['family'],r['context'])==k)] for k in keys] for p in policies]
    fig,ax=plt.subplots(figsize=(15,5),layout='constrained');im=ax.imshow(matrix,cmap=ListedColormap(['#c34d4d','#e9a351','#dedede','#699bcb','#65a776']),vmin=-.5,vmax=4.5,aspect='auto')
    ax.set_yticks(range(len(policies)),[LABELS[p] for p in policies]);ax.set_xticks(range(24),[f'{k[0]-813030100} {k[1]} {k[2].split("_")[0]}' for k in keys],rotation=65,ha='right',fontsize=8);cb=fig.colorbar(im,ax=ax,ticks=range(5));cb.ax.set_yticklabels(names);ax.set_title('사전 고정 모든 확인 조건 — Band/Triton 양쪽 제약');fig.savefig(out/'05_조건별결과지도.png',dpi=150);plt.close(fig)

def dashboard(pairs,summaries,summary):
    def table(rows,fields):
        body=''
        for row in rows:
            body+='<tr>'+''.join('<td>'+html.escape(LABELS.get(row[k],row[k]) if isinstance(row[k],str) else f'{row[k]:.8g}' if isinstance(row[k],float) else str(row[k]))+'</td>' for k,_ in fields)+'</tr>'
        return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+v+'</th>' for _,v in fields)+'</tr></thead><tbody>'+body+'</tbody></table></div>'
    rules=[dict(policy=p,rule=RULES[p]) for p in s.POLICIES]
    body='<h1>관측 이력의 미래 열부하와 경량 예측</h1><p>전체 도착 요청 · 개발24조건 뒤 선택 동결 · 새 확인24조건 · 7역할. 실제 미래는 정책에 전달하지 않으며 가상 요청은 예측에만 사용합니다.</p>'
    body+=f'<p>개발 선택: {html.escape(str(LABELS.get(summary["selected_before_final"],summary["selected_before_final"])))}, 확인 적격: {summary["selected_final_accepted"]}. 물리적 절감이나 실제 표면온도 우위가 아닙니다.</p>'
    body+='<p><a href="README.md">설계·판정·한계</a> · <a href="final_results.csv">전체 확인 CSV</a> · <a href="speed_pairs.csv">동일 판단 속도 비교</a></p><input id="filter" placeholder="정책·부하·문맥 검색">'
    body+=table(rules,[('policy','규칙'),('rule','판단 차이')]);body+=table(summaries,[('policy','정책'),('completed','완료'),('planned','예정'),('urgent_failures','긴급 실패'),('normal_failures','일반 실패'),('urgent_p95_ms','P95 평균 ms'),('energy_j','J 평균'),('peak_ap_c','AP 평균'),('heat_gain_both','양 기준 대비 열감소'),('joint_gain_both','공동감소')])
    body+=table(pairs,[('seed','seed'),('family','부하'),('context','문맥'),('policy','후보'),('category','판정'),('delta_energy_j','Band J 차이'),('delta_peak_ap_c','AP 차이'),('delta_urgent_p95_ms','P95 차이 ms'),('delta_normal_mean_ms','일반 지연 ms')])
    for p in sorted((BUNDLE/'figures').glob('*.png')):body+=f'<img src="figures/{p.name}" alt="{p.stem}">'
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>온라인 열 분산 비교</title><style>body{font-family:Malgun Gothic,sans-serif;margin:24px;max-width:1450px;color:#263142}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #ddd;padding:7px}th{background:#edf3f8}.scroll{overflow:auto;margin:18px 0}input{padding:10px;width:320px}img{width:100%;max-width:1300px;margin:20px 0}</style>'+body+'<script>document.querySelector("#filter").addEventListener("input",e=>{let q=e.target.value.toLowerCase();document.querySelectorAll("tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));});</script></html>'
    (BUNDLE/'index.html').write_text(page,encoding='utf8',newline='\n')

if __name__=='__main__':print(json.dumps(report(),ensure_ascii=False,indent=2))
