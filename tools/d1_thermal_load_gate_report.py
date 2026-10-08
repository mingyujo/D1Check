"""Complete-arrival thermal-slack pilot, original-unit gates and offline figures."""
from __future__ import annotations
import csv,gzip,html,json,statistics
from tools import d1_thermal_load_gate_study as s
from tools.d1_edd_ect_residual_report import compare
BUNDLE=s.BUNDLE;LOCAL=s.LOCAL;ROOT=s.ROOT;read=s.read;write=s.write
LABELS={s.x.POLICY:'관측 작업량·기한 여유 열 분산',s.BAND:'Band 요청 적용',s.TRITON:'Triton 고정 자원',s.EDD:'기한 우선 ECT',s.LIST:'기존 열·에너지 리스트',s.parent.x.SHORT:'허용 장치 없는0.25초 열 분산'}

def csv_write(path,rows):
    with path.open('w',encoding='utf8',newline='') as f:
        fields=list(dict.fromkeys(k for row in rows for k in row));w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
def load_items():
    done={r['identity']:r for r in s.events() if r['event']=='completed'};items={}
    for path in (LOCAL/'items').glob('*.gz'):
        item=json.loads(gzip.decompress(path.read_bytes()));identity=item['row']['identity'];assert s.sha(path)==done[identity]['artifact_sha256'];items[identity]=item
    return items
def mean(values):
    values=list(values);return statistics.mean(values) if values and all(v is not None for v in values) else None
def ledger(item):return [{k:v for k,v in r.items() if k!='source_request_id'} for r in item['result']['ledger']]

def report():
    done=read(BUNDLE/'completion.json');assert done['status']=='completed';s.check();items=load_items()
    final=read(BUNDLE/'final_rows.json');development=read(BUNDLE/'development_rows.json');assert len(final)==len(development)==144
    grouped={(r['seed'],r['family'],r['context'],r['policy']):r for r in final};pairs=[];summaries=[];diagnostics=[]
    for row in final:
        if row['policy']==s.BAND:continue
        base=grouped[row['seed'],row['family'],row['context'],s.BAND];triton=grouped[row['seed'],row['family'],row['context'],s.TRITON]
        b,t=compare(row,base),compare(row,triton)
        nonworse=b['nonworse'] and t['nonworse'];heat=b['heat_gain'] and t['heat_gain'];joint=b['joint_gain'] and t['joint_gain']
        if not b['service_preserved'] or not t['service_preserved']:category='서비스 악화'
        elif not nonworse:category='비용 상충'
        elif joint:category='J·AP 공동감소'
        elif heat:category='J 비악화·열감소'
        else:category='비악화·열차 없음'
        pairs.append(dict(seed=row['seed'],family=row['family'],context=row['context'],policy=row['policy'],primary=row['family'] in ('low','sustained'),
            **b,service_preserved_both=b['service_preserved'] and t['service_preserved'],nonworse_both=nonworse,heat_gain_both=heat,joint_gain_both=joint,normal_mean_nonworse=row['normal_mean_ms']<=base['normal_mean_ms']+1e-9,
            category=category,planned=row['planned'],completed=row['completed'],urgent_failures=row['urgent_service_failure'],normal_failures=row['normal_service_failure']))
    for policy in s.POLICIES:
        group=[r for r in final if r['policy']==policy];pp=[r for r in pairs if r['policy']==policy]
        summaries.append(dict(policy=policy,conditions=24,planned=sum(r['planned'] for r in group),completed=sum(r['completed'] for r in group),
            urgent_failures=sum(r['urgent_service_failure'] for r in group),normal_failures=sum(r['normal_service_failure'] for r in group),
            urgent_p95_ms=mean(r['urgent_p95_ms'] for r in group),normal_mean_ms=mean(r['normal_mean_ms'] for r in group),energy_j=mean(r['energy_j'] for r in group),
            peak_ap_c=mean(r['peak_ap_c'] for r in group),ap_full_work_conditions=sum(r['peak_ap_c'] is not None for r in group),
            nonworse_both=sum(r['nonworse_both'] for r in pp),heat_gain_both=sum(r['heat_gain_both'] for r in pp),joint_gain_both=sum(r['joint_gain_both'] for r in pp),
            host_environment_wall_s=sum(r['host_wall_s'] for r in group),decision_host_total_s=sum(r['decision_host_total_s'] for r in group),decision_host_max_ms=max(r['decision_host_max_ms'] for r in group)))
    for identity,item in items.items():
        if not identity.startswith(('development/','final/')) or item['row']['policy'] not in s.NEW:continue
        choices=item['choices'];waits=[d for d in item['result']['decisions'] if d.get('action_kind')=='cool_wait']
        diagnostics.append(dict(identity=identity,split=identity.split('/')[0],seed=item['row']['seed'],family=item['row']['family'],context=item['row']['context'],policy=item['row']['policy'],
            recorded_decisions=len(choices),nonbase=sum(not d['chosen_base'] for d in choices),wait_choices=len(waits),
            maximum_requested_wait_s=max([0.]+[(d['wait_until_ns']-d['now_ns'])/1e9 for d in waits]),projection_calls=item['row'].get('projection_calls'),gate_allowed=item['row'].get('gate_allowed'),gate_blocked=item['row'].get('gate_blocked')))
    equality={}
    for policy in s.NEW:
        equality[policy]=sum(ledger(items[r['identity']])==ledger(items[grouped[r['seed'],r['family'],r['context'],s.BAND]['identity']]) for r in final if r['policy']==policy)
    selection=read(BUNDLE/'selection.json');chosen=selection['chosen'];selected_pairs=[p for p in pairs if p['policy']==chosen]
    first_final=min(e['utc'] for e in s.events() if e['event']=='start' and e['identity'].startswith('final/'));assert selection['utc']<first_final
    primary={policy:dict(conditions=12,nonworse_both=sum(r['nonworse_both'] for r in pairs if r['policy']==policy and r['primary']),heat_gain_both=sum(r['heat_gain_both'] for r in pairs if r['policy']==policy and r['primary']),
        mean_delta_energy_j=mean(r['delta_energy_j'] for r in pairs if r['policy']==policy and r['primary']),mean_delta_ap_c=mean(r['delta_peak_ap_c'] for r in pairs if r['policy']==policy and r['primary'])) for policy in s.NEW}
    ablations=[]
    for row in (r for r in final if r['policy']==s.x.POLICY):
        base=grouped[row['seed'],row['family'],row['context'],s.parent.x.SHORT]
        ablations.append(dict(seed=row['seed'],family=row['family'],context=row['context'],policy=row['policy'],**compare(row,base)))
    summary=dict(status='completed',development_conditions=24,final_conditions=24,development_rows=144,development_reused_rows=120,final_rows=144,selected_before_final=chosen,
        selection_frozen_before_first_final=True,selected_final_accepted=bool(chosen and all(p['nonworse_both'] for p in selected_pairs) and all(any(p['heat_gain_both'] and p['primary'] and p['seed']==seed for p in selected_pairs) for seed in (813030101,813030102))),
        final_planned=sum(r['planned'] for r in final),final_completed=sum(r['completed'] for r in final),
        all_successful_environment_planned=sum(i['row']['planned'] for i in items.values()),all_successful_environment_completed=sum(i['row']['completed'] for i in items.values()),
        total_environment_successes=len(items),consumption=done['consumption'],primary=primary,Band_ledger_equal_conditions=equality,
        new_heat_gain_both={p:sum(r['heat_gain_both'] for r in pairs if r['policy']==p) for p in s.NEW},new_joint_gain_both={p:sum(r['joint_gain_both'] for r in pairs if r['policy']==p) for p in s.NEW},
        new_service_regression_vs_Band={p:sum(not r['service_preserved'] for r in pairs if r['policy']==p) for p in s.NEW},
        new_service_regression_vs_both={p:sum(not r['service_preserved_both'] for r in pairs if r['policy']==p) for p in s.NEW},
        new_nonworse_vs_Band={p:sum(r['nonworse'] for r in pairs if r['policy']==p) for p in s.NEW},
        no_new_training=True,no_policy_default_change=True,experiment_ready=False,AP_surface_temperature=False,physical_improvement_proven=False,
        measured_thermal_service_coupling=False,control_energy_j=None,thermal_safety_limit=None,
        scope='all planned requests in four arrival families, two fresh development and two final seeds, three phase contexts; model-transfer PC pilot, not physical/independent model verification')
    csv_write(BUNDLE/'development_results.csv',development);csv_write(BUNDLE/'final_results.csv',final);csv_write(BUNDLE/'policy_summary.csv',summaries);csv_write(BUNDLE/'pairs_vs_band.csv',pairs)
    csv_write(BUNDLE/'wait_ablation.csv',ablations);csv_write(BUNDLE/'decision_diagnostics.csv',diagnostics);write(BUNDLE/'summary.json',summary)
    csv_write(BUNDLE/'execution_receipts.csv',[{k:e.get(k) for k in ('event','utc','number','identity','kind','error')} for e in s.events()])
    representative=read(BUNDLE/'registration.json')['representative'];reps={p:items[next(r['identity'] for r in final if r['policy']==p and all(r[k]==v for k,v in representative.items()))] for p in s.POLICIES}
    # Shared representative omits bulky hypothetical choice logs, preserves full actual request ledger and curves.
    write(BUNDLE/'representatives.json',{p:dict(row=i['row'],ledger=i['result']['ledger'],curves=i['curves']) for p,i in reps.items()})
    plots(pairs,summaries,reps);dashboard(pairs,summaries,summary);return summary

def plots(pairs,summaries,reps):
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False});out=BUNDLE/'figures';out.mkdir(exist_ok=True)
    fig,ax=plt.subplots(figsize=(11,6),layout='constrained')
    for p in s.NEW:
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
    axes[-1].set_xlim(35,50);axes[-1].set_xlabel('공통 시간 초 — 첫15초 고정 확대');fig.suptitle('사전 대표 첫 확인 seed·지속·평균의 실제 lane 점유');fig.savefig(out/'03_대표작업시간표.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(14,5),layout='constrained')
    for p in (s.BAND,s.EDD,s.parent.x.SHORT,s.x.POLICY):
        c=reps[p]['curves'];axes[0].plot(c['ap_times_s'],c['ap_path'],label=LABELS[p])
    axes[0].set_xlabel('초');axes[0].set_ylabel('동일 AP 모형 °C');axes[0].legend(fontsize=9);axes[0].grid(alpha=.2)
    axes[1].bar(range(len(s.POLICIES)),[r['energy_j'] for r in summaries]);axes[1].set_xticks(range(len(s.POLICIES)),[LABELS[r['policy']] for r in summaries],rotation=35,ha='right');axes[1].set_ylabel('공통120초 기기 전체 J 평균');fig.suptitle('원계수·초기 상태 보존 — 실제 표면온도/절감과 구분');fig.savefig(out/'04_온도경로와에너지.png',dpi=150);plt.close(fig)
    policies=list(s.NEW);keys=sorted({(r['seed'],r['family'],r['context']) for r in pairs});names=['서비스 악화','비용 상충','비악화·열차 없음','J 비악화·열감소','J·AP 공동감소'];codes={n:i for i,n in enumerate(names)}
    matrix=[[codes[next(r['category'] for r in pairs if r['policy']==p and (r['seed'],r['family'],r['context'])==k)] for k in keys] for p in policies]
    fig,ax=plt.subplots(figsize=(15,5),layout='constrained');im=ax.imshow(matrix,cmap=ListedColormap(['#c34d4d','#e9a351','#dedede','#699bcb','#65a776']),vmin=-.5,vmax=4.5,aspect='auto')
    ax.set_yticks(range(len(policies)),[LABELS[p] for p in policies]);ax.set_xticks(range(24),[f'{k[0]-813030100} {k[1]} {k[2].split("_")[0]}' for k in keys],rotation=65,ha='right',fontsize=8);cb=fig.colorbar(im,ax=ax,ticks=range(5));cb.ax.set_yticklabels(names);ax.set_title('사전 고정 모든 확인 조건 — Band/Triton 양쪽 제약');fig.savefig(out/'05_조건별결과지도.png',dpi=150);plt.close(fig)

def dashboard(pairs,summaries,summary):
    def table(rows,fields):
        body=''
        for row in rows:
            body+='<tr>'+''.join('<td>'+html.escape(LABELS.get(row[k],row[k]) if isinstance(row[k],str) else f'{row[k]:.8g}' if isinstance(row[k],float) else str(row[k]))+'</td>' for k,_ in fields)+'</tr>'
        return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+v+'</th>' for _,v in fields)+'</tr></thead><tbody>'+body+'</tbody></table></div>'
    rules=[dict(policy=p,rule=d) for p,d in zip(s.POLICIES,('원 Band 요청 규칙','원 Triton 고정 자원 규칙','기한 순서·5단계 ECT','기존 EDD suffix·J/AP 리스트','허용 장치 없는0.25초 열 분산','관측 도착 간격 대비 작업량+credit 적합·현재큐 기한가능·0.25초 열 분산'))]
    body='<h1>관측 작업량으로 대기를 제한하는 열 분산</h1><p>전체 도착 요청 · 개발24조건 뒤 선택 동결 · 새 확인24조건 · 6규칙. 산업공학 요소는 EDD·응답 여유·잔여 작업량·호환성·재계획입니다.</p>'
    body+=f'<p>개발 선택: {html.escape(str(LABELS.get(summary["selected_before_final"],summary["selected_before_final"])))}, 확인 적격: {summary["selected_final_accepted"]}. 물리적 절감이나 실제 표면온도 우위가 아닙니다.</p>'
    body+='<p><a href="README.md">설계·판정·한계</a> · <a href="final_results.csv">전체 확인 CSV</a> · <a href="wait_ablation.csv">대기 허용 장치 제거 비교</a></p><input id="filter" placeholder="정책·부하·문맥 검색">'
    body+=table(rules,[('policy','규칙'),('rule','판단 차이')]);body+=table(summaries,[('policy','정책'),('completed','완료'),('planned','예정'),('urgent_failures','긴급 실패'),('normal_failures','일반 실패'),('urgent_p95_ms','P95 평균 ms'),('energy_j','J 평균'),('peak_ap_c','AP 평균'),('heat_gain_both','양 기준 대비 열감소'),('joint_gain_both','공동감소')])
    body+=table(pairs,[('seed','seed'),('family','부하'),('context','문맥'),('policy','후보'),('category','판정'),('delta_energy_j','Band J 차이'),('delta_peak_ap_c','AP 차이'),('delta_urgent_p95_ms','P95 차이 ms'),('delta_normal_mean_ms','일반 지연 ms')])
    for p in sorted((BUNDLE/'figures').glob('*.png')):body+=f'<img src="figures/{p.name}" alt="{p.stem}">'
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>온라인 열 분산 비교</title><style>body{font-family:Malgun Gothic,sans-serif;margin:24px;max-width:1450px;color:#263142}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #ddd;padding:7px}th{background:#edf3f8}.scroll{overflow:auto;margin:18px 0}input{padding:10px;width:320px}img{width:100%;max-width:1300px;margin:20px 0}</style>'+body+'<script>document.querySelector("#filter").addEventListener("input",e=>{let q=e.target.value.toLowerCase();document.querySelectorAll("tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));});</script></html>'
    (BUNDLE/'index.html').write_text(page,encoding='utf8',newline='\n')

if __name__=='__main__':print(json.dumps(report(),ensure_ascii=False,indent=2))
