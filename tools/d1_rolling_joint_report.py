"""Complete-work evaluation of bounded joint rolling plans and wait ablation."""
import csv,gzip,html,json,statistics
from tools import d1_rolling_joint_study as s
from tools.d1_edd_ect_residual_report import compare
ROOT=s.ROOT;BUNDLE=s.BUNDLE;LOCAL=s.LOCAL;read=s.read;write=s.write;NEW=s.NEW
LABELS={s.BAND:'Band 요청 적용',s.TRITON:'Triton 고정 자원',s.EDD:'기한 우선 ECT',s.CP:'기존 CP-SAT 첫 선택 필터',s.FAST:'기존 경량 열 분산',s.x.NOWAIT:'공동 계획 대기0',s.x.WAIT:'공동 계획0.25초'}
RULES={s.BAND:'원 Band 요청 순위·자원 배정',s.TRITON:'원 고정 자원 규칙',s.EDD:'기한 순서·5단계 ECT',s.CP:'현재4요청 J계획·첫 행동 AP필터',s.FAST:'단건/병행/대기·기존 경량 예측',s.x.NOWAIT:'과업내EDD·순서/자원 공동 계획·전체 J/AP검사',s.x.WAIT:'같은 공동 계획·일반 유휴1구간·누적0.25초'}

def report():
    done=read(BUNDLE/'completion.json');assert done['status']=='completed';s.check();items=load_items();rows=read(BUNDLE/'final_rows.json');dev=read(BUNDLE/'development_rows.json');assert len(rows)==len(dev)==168
    by={(r['seed'],r['family'],r['context'],r['policy']):r for r in rows};pairs=[];summaries=[];diagnostics=[];ablations=[]
    for row in rows:
        if row['policy']==s.BAND:continue
        b,t=[compare(row,by[row['seed'],row['family'],row['context'],p]) for p in (s.BAND,s.TRITON)]
        both=b['nonworse'] and t['nonworse'];heat=b['heat_gain'] and t['heat_gain'];joint=b['joint_gain'] and t['joint_gain']
        category='서비스 악화' if not b['service_preserved'] or not t['service_preserved'] else '비용 상충' if not both else 'J·AP 공동감소' if joint else 'J 비악화·열감소' if heat else '비악화·열차 없음'
        pairs.append(dict(seed=row['seed'],family=row['family'],context=row['context'],policy=row['policy'],primary=row['family'] in ('low','sustained'),**b,service_preserved_both=b['service_preserved'] and t['service_preserved'],nonworse_both=both,heat_gain_both=heat,joint_gain_both=joint,category=category))
    for policy in s.POLICIES:
        group=[r for r in rows if r['policy']==policy];ps=[r for r in pairs if r['policy']==policy]
        summaries.append(dict(policy=policy,conditions=24,planned=sum(r['planned'] for r in group),completed=sum(r['completed'] for r in group),urgent_failures=sum(r['urgent_service_failure'] for r in group),normal_failures=sum(r['normal_service_failure'] for r in group),urgent_p95_ms=statistics.mean(r['urgent_p95_ms'] for r in group),normal_mean_ms=statistics.mean(r['normal_mean_ms'] for r in group),energy_j=statistics.mean(r['energy_j'] for r in group),peak_ap_c=statistics.mean(r['peak_ap_c'] for r in group),
            nonworse_both=sum(r['nonworse_both'] for r in ps),heat_gain_both=sum(r['heat_gain_both'] for r in ps),joint_gain_both=sum(r['joint_gain_both'] for r in ps),decision_host_total_s=sum(r['decision_host_total_s'] for r in group),decision_host_max_ms=max(r['decision_host_max_ms'] for r in group)))
    equality={}
    for policy in NEW:
        equality[policy]=sum([{k:v for k,v in q.items() if k!='source_request_id'} for q in items[r['identity']]['result']['ledger']]==[{k:v for k,v in q.items() if k!='source_request_id'} for q in items[by[r['seed'],r['family'],r['context'],s.BAND]['identity']]['result']['ledger']] for r in rows if r['policy']==policy)
    selected_records=[]
    for identity,item in items.items():
        if not identity.startswith(('development/','final/')) or item['row']['policy'] not in NEW:continue
        records=item['plans'];selected=[r for r in records if r['selected_plan']]
        diagnostics.append(dict(identity=identity,split=identity.split('/')[0],seed=item['row']['seed'],family=item['row']['family'],context=item['row']['context'],policy=item['row']['policy'],planning_calls=len(records),selected_forecast_plans=len(selected),mean_screen_plan_evaluations=sum(r['candidate_count'] for r in records),full_plan_evaluations=sum(r['full_plan_count'] for r in records),
            cool_wait_actions=sum(d.get('action_kind')=='cool_wait' for d in item['result']['decisions']),resource_wait_calls=sum(d.get('reason')=='rolling_selected_resource_wait' for d in item['result']['decisions']),bundle_commit_calls=sum(d.get('action_kind')=='bundle_commit' for d in item['result']['decisions'])))
        for record in selected:
            selected_records.append(dict(identity=identity,**record))
    for r in (r for r in rows if r['policy']==s.x.WAIT):
        base=by[r['seed'],r['family'],r['context'],s.x.NOWAIT];ablations.append(dict(seed=r['seed'],family=r['family'],context=r['context'],**compare(r,base)))
    selection=read(BUNDLE/'selection.json');first=min(r['utc'] for r in s.events() if r['event']=='start' and r['identity'].startswith('final/'));assert selection['utc']<first
    chosen=selection['chosen'];chosen_pairs=[r for r in pairs if r['policy']==chosen]
    summary=dict(status='completed',selected_before_final=chosen,selected_final_accepted=bool(chosen and all(r['nonworse_both'] for r in chosen_pairs) and all(any(r['heat_gain_both'] and r['primary'] and r['seed']==seed for r in chosen_pairs) for seed in (815020101,815020102))),
        development_rows=168,development_reused_rows=72,final_rows=168,final_planned=sum(r['planned'] for r in rows),final_completed=sum(r['completed'] for r in rows),original_engine_successes=len(items),total_planned=sum(i['row']['planned'] for i in items.values()),total_completed=sum(i['row']['completed'] for i in items.values()),consumption=done['consumption'],
        Band_ledger_equal_conditions=equality,new_heat_gain_both={p:sum(r['heat_gain_both'] for r in pairs if r['policy']==p) for p in NEW},new_joint_gain_both={p:sum(r['joint_gain_both'] for r in pairs if r['policy']==p) for p in NEW},new_service_regression_vs_Band={p:sum(not r['service_preserved'] for r in pairs if r['policy']==p) for p in NEW},
        final_planning={p:{k:sum(d[k] for d in diagnostics if d['split']=='final' and d['policy']==p) for k in ('planning_calls','selected_forecast_plans','mean_screen_plan_evaluations','full_plan_evaluations','cool_wait_actions','resource_wait_calls','bundle_commit_calls')} for p in NEW},
        no_policy_default_change=True,experiment_ready=False,new_training=0,physical_improvement_proven=False,scope='EDD-list-restricted window4 joint prefix with mean shortlist8 and full arrived-queue3-context guard; not global/continuous optimum or future/physical SLA guarantee')
    csv_write(BUNDLE/'development_results.csv',dev);csv_write(BUNDLE/'final_results.csv',rows);csv_write(BUNDLE/'policy_summary.csv',summaries);csv_write(BUNDLE/'pairs_vs_band.csv',pairs);csv_write(BUNDLE/'planning_diagnostics.csv',diagnostics);csv_write(BUNDLE/'wait_ablation.csv',ablations)
    csv_write(BUNDLE/'execution_receipts.csv',[{k:r.get(k) for k in ('event','utc','number','identity','kind','source_shared_sha256','error')} for r in s.events()]);write(BUNDLE/'selected_forecast_plans.json',selected_records);write(BUNDLE/'summary.json',summary)
    rep=read(BUNDLE/'registration.json')['representative'];reps={p:items[next(r['identity'] for r in rows if r['policy']==p and all(r[k]==v for k,v in rep.items()))] for p in s.POLICIES}
    write(BUNDLE/'representatives.json',{p:dict(row=i['row'],ledger=i['result']['ledger'],curves=i['curves'],selected_plans=[r for r in i['plans'] if r['selected_plan']]) for p,i in reps.items()})
    plots(pairs,summaries,reps);dashboard(pairs,summaries,summary);return summary
def csv_write(path,rows):
    with path.open('w',encoding='utf8',newline='') as f:
        fields=list(dict.fromkeys(k for r in rows for k in r));w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)

def load_items():
    receipts={r['identity']:r for r in s.events() if r['event']=='completed'};items={}
    for path in (LOCAL/'items').glob('*.gz'):
        item=json.loads(gzip.decompress(path.read_bytes()));identity=item['row']['identity'];assert receipts[identity]['artifact_sha256']==s.sha(path);items[identity]=item
    return items

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
    axes[-1].set_xlim(35,45);axes[-1].set_xlabel('공통 시간 초 — 첫10초 고정 확대');fig.suptitle('사전 대표 첫 확인 seed·몰림·평균의 실제 lane 점유');fig.savefig(out/'03_대표작업시간표.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(14,5),layout='constrained')
    for p in (s.BAND,s.CP,s.FAST,s.x.NOWAIT,s.x.WAIT):
        c=reps[p]['curves'];axes[0].plot(c['ap_times_s'],c['ap_path'],label=LABELS[p])
    axes[0].set_xlabel('초');axes[0].set_ylabel('동일 AP 모형 °C');axes[0].legend(fontsize=9);axes[0].grid(alpha=.2)
    axes[1].bar(range(len(s.POLICIES)),[r['energy_j'] for r in summaries]);axes[1].set_xticks(range(len(s.POLICIES)),[LABELS[r['policy']] for r in summaries],rotation=35,ha='right');axes[1].set_ylabel('공통120초 기기 전체 J 평균');fig.suptitle('원계수·초기 상태 보존 — 실제 표면온도/절감과 구분');fig.savefig(out/'04_온도경로와에너지.png',dpi=150);plt.close(fig)
    policies=list(NEW);keys=sorted({(r['seed'],r['family'],r['context']) for r in pairs});names=['서비스 악화','비용 상충','비악화·열차 없음','J 비악화·열감소','J·AP 공동감소'];codes={n:i for i,n in enumerate(names)}
    matrix=[[codes[next(r['category'] for r in pairs if r['policy']==p and (r['seed'],r['family'],r['context'])==k)] for k in keys] for p in policies]
    fig,ax=plt.subplots(figsize=(15,5),layout='constrained');im=ax.imshow(matrix,cmap=ListedColormap(['#c34d4d','#e9a351','#dedede','#699bcb','#65a776']),vmin=-.5,vmax=4.5,aspect='auto')
    ax.set_yticks(range(len(policies)),[LABELS[p] for p in policies]);ax.set_xticks(range(24),[f'{k[0]-815020100} {k[1]} {k[2].split("_")[0]}' for k in keys],rotation=65,ha='right',fontsize=8);cb=fig.colorbar(im,ax=ax,ticks=range(5));cb.ax.set_yticklabels(names);ax.set_title('사전 고정 모든 확인 조건 — Band/Triton 양쪽 제약');fig.savefig(out/'05_조건별결과지도.png',dpi=150);plt.close(fig)

def dashboard(pairs,summaries,summary):
    def table(rows,fields):
        body=''
        for row in rows:
            body+='<tr>'+''.join('<td>'+html.escape(LABELS.get(row[k],row[k]) if isinstance(row[k],str) else f'{row[k]:.8g}' if isinstance(row[k],float) else str(row[k]))+'</td>' for k,_ in fields)+'</tr>'
        return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+v+'</th>' for _,v in fields)+'</tr></thead><tbody>'+body+'</tbody></table></div>'
    rules=[dict(policy=p,rule=RULES[p]) for p in s.POLICIES]
    body='<h1>순서·자원·대기를 함께 계획하는 롤링 호라이즌</h1><p>현재 도착 창4 · 과업내 EDD·호환성 · 최대72계획 중8선별 · 전체 현재큐의 J/AP·서비스검사 · 첫 선택 실행 후 재계획.</p>'
    body+=f'<p>개발 선택: {html.escape(str(LABELS.get(summary["selected_before_final"],summary["selected_before_final"])))}, 확인 적격: {summary["selected_final_accepted"]}. 물리적 절감이나 실제 표면온도 우위가 아닙니다.</p>'
    body+='<p><a href="README.md">설계·판정·한계</a> · <a href="final_results.csv">전체 확인 CSV</a> · <a href="planning_diagnostics.csv">계획·실제 선택</a> · <a href="wait_ablation.csv">대기 제거</a></p><input id="filter" placeholder="정책·부하·문맥 검색">'

    body+=table(rules,[('policy','규칙'),('rule','판단 차이')]);body+=table(summaries,[('policy','정책'),('completed','완료'),('planned','예정'),('urgent_failures','긴급 실패'),('normal_failures','일반 실패'),('urgent_p95_ms','P95 평균 ms'),('energy_j','J 평균'),('peak_ap_c','AP 평균'),('heat_gain_both','양 기준 대비 열감소'),('joint_gain_both','공동감소')])
    body+=table(pairs,[('seed','seed'),('family','부하'),('context','문맥'),('policy','후보'),('category','판정'),('delta_energy_j','Band J 차이'),('delta_peak_ap_c','AP 차이'),('delta_urgent_p95_ms','P95 차이 ms'),('delta_normal_mean_ms','일반 지연 ms')])
    for p in sorted((BUNDLE/'figures').glob('*.png')):body+=f'<img src="figures/{p.name}" alt="{p.stem}">'
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>온라인 열 분산 비교</title><style>body{font-family:Malgun Gothic,sans-serif;margin:24px;max-width:1450px;color:#263142}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #ddd;padding:7px}th{background:#edf3f8}.scroll{overflow:auto;margin:18px 0}input{padding:10px;width:320px}img{width:100%;max-width:1300px;margin:20px 0}</style>'+body+'<script>document.querySelector("#filter").addEventListener("input",e=>{let q=e.target.value.toLowerCase();document.querySelectorAll("tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));});</script></html>'
    (BUNDLE/'index.html').write_text(page,encoding='utf8',newline='\n')

if __name__=='__main__':print(json.dumps(report(),ensure_ascii=False,indent=2))
