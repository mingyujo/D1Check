"""Source-bound diagnosis, new confirmation and offline figures; no env starts."""
import gzip,html,json,math,statistics
from tools import d1_rolling_prefix_study as s
from tools import d1_rolling_joint_report as prior_report
from tools.d1_edd_ect_residual_report import compare
ROOT=s.ROOT;B=s.BUNDLE;D=s.diagnosis.BUNDLE;write=s.write;read=s.read
LABELS=dict(prior_report.LABELS);LABELS[s.x.POLICY]='공동 계획 첫 선택 검사'
def native_items(folder,receipts):
    receipts={e['identity']:e for e in receipts if e['event']=='completed'};items={}
    for p in (folder/'items').glob('*.gz'):
        item=json.loads(gzip.decompress(p.read_bytes()));identity=item['row']['identity'];assert s.sha(p)==receipts[identity]['artifact_sha256'];items[identity]=item
    return items
def guarded_pair(r,b,t):
    a,c=compare(r,b),compare(r,t)
    return dict(**a,service_preserved_both=a['service_preserved'] and c['service_preserved'],nonworse_both=a['nonworse'] and c['nonworse'],heat_gain_both=a['heat_gain'] and c['heat_gain'],joint_gain_both=a['joint_gain'] and c['joint_gain'],
        absolute_deadline_eligible_all=all(v['deadline_met']==v['planned'] for v in (r,b,t)))
def volume(item):
    v={}
    for segment in item['curves']['segments']:
        dt=max(0.,min(120.,segment['end_s'])-max(0.,segment['start_s']));label=segment['state']
        v[label]=v.get(label,0.)+dt
    return v
def explain(item,base,frozen,split):
    row=item['row'];old=base['row'];qold={r['id']:r for r in base['result']['ledger']};changes=[]
    for r in item['result']['ledger']:
        b=qold[r['id']]
        if r['dispatch_ns']!=b['dispatch_ns'] or r['backend']!=b['backend']:
            changes.append(dict(request_id=r['id'],priority=r['priority'],arrival_s=r['arrival_ns']/1e9,baseline_dispatch_s=b['dispatch_ns']/1e9,
                candidate_dispatch_s=r['dispatch_ns']/1e9,baseline_backend=b['backend'],candidate_backend=r['backend'],response_delta_ms=(r['response_ns']-b['response_ns'])/1e6))
    changes.sort(key=lambda r:min(r['baseline_dispatch_s'],r['candidate_dispatch_s']))
    v,w=volume(item),volume(base);parts={k:(v.get(k,0.)-w.get(k,0.))*frozen['energy_increment_w'].get(k,0.) for k in set(v)|set(w) if k!='idle'}
    assert abs(sum(parts.values())-(row['energy_j']-old['energy_j']))<1e-8
    peak_index=max(range(len(item['curves']['ap_path'])),key=lambda i:item['curves']['ap_path'][i]);peak_s=item['curves']['ap_times_s'][peak_index]
    import numpy as np
    slopes=frozen['ap']['parameters']['ap_slope_at_30_c_per_s'];heat={}
    for sign,obj in ((1,item),(-1,base)):
        for seg in obj['curves']['segments']:
            label=seg['state']
            if label=='idle':continue
            u=slopes[label]-slopes['resident_idle'];a=seg['start_s'];b=seg['end_s']
            delta=sign*u*float(s.parent.x.fast.kernel(frozen['ap'],np.array([max(0.,peak_s-a)]))[0]-s.parent.x.fast.kernel(frozen['ap'],np.array([max(0.,peak_s-b)]))[0])
            heat[label]=heat.get(label,0.)+delta
    ap_at_candidate_peak=item['curves']['ap_path'][peak_index]-base['curves']['ap_path'][peak_index]
    assert abs(sum(heat.values())-ap_at_candidate_peak)<1e-8
    alignment=base['curves']['ap_path'][peak_index]-old['peak_ap_c']
    assert abs(sum(heat.values())+alignment-(row['peak_ap_c']-old['peak_ap_c']))<1e-8
    future_arrivals=sorted({q['arrival_ns']/1e9 for q in item['result']['ledger'] if changes and q['arrival_ns']/1e9>changes[0]['baseline_dispatch_s']})
    return dict(split=split,seed=row['seed'],context=row['context'],policy=row['policy'],dispatch_or_backend_changed=len(changes),first_change=changes[0] if changes else None,
        hindsight_next_actual_arrival_s=future_arrivals[0] if future_arrivals else None,delta_energy_j=row['energy_j']-old['energy_j'],delta_peak_ap_c=row['peak_ap_c']-old['peak_ap_c'],
        delta_urgent_p95_ms=row['urgent_p95_ms']-old['urgent_p95_ms'],delta_normal_mean_ms=row['normal_mean_ms']-old['normal_mean_ms'],
        delta_overlap_s=row['overlap_s']-old['overlap_s'],delta_classification_gpu=row['classification_gpu']-old['classification_gpu'],
        energy_contributions_j=parts,temperature_contributions_at_candidate_peak_c=heat,peak_alignment_c=alignment,candidate_peak_s=peak_s,
        actual_future_is_hindsight_only=True)
def report():
    s.check();s.diagnosis.check();assert read(B/'completion.json')['status']=='completed'
    diagnosis=read(D/'diagnosis.json');diag_rows=[]
    for r in diagnosis:
        p=r['prefixes'];ss=r['shortlist_snapshots'];bad=[q for q in p if not q['actual_prefix_guard_pass']]
        diag_rows.append(dict(split=r['split'],seed=r['seed'],context=r['context'],policy=r['policy'],exact_replay=r['exact_replay'],selected_plans=len(p),prefix_guard_failures=len(bad),shortlist_snapshots=len(ss),omitted_better=sum(q['omitted_improving_plan'] for q in ss),first_prefix_failure_s=bad[0]['now_ns']/1e9 if bad else None))
    prior_report.csv_write(D/'diagnosis_summary.csv',diag_rows)
    (D/'diagnosis_details.json.gz').write_bytes(gzip.compress(json.dumps(diagnosis,separators=(',',':'),allow_nan=False).encode(),mtime=0))
    write(D/'summary.json',dict(status='completed',exact_native_replays=24,consumption=read(D/'completion.json')['consumption'],
        groups={split:{p:dict(selected_plans=sum(r['selected_plans'] for r in diag_rows if r['split']==split and r['policy']==p),prefix_guard_failures=sum(r['prefix_guard_failures'] for r in diag_rows if r['split']==split and r['policy']==p),shortlist_snapshots=sum(r['shortlist_snapshots'] for r in diag_rows if r['split']==split and r['policy']==p),omitted_better=sum(r['omitted_better'] for r in diag_rows if r['split']==split and r['policy']==p)) for p in s.parent.NEW} for split in ('development','final')},
        no_claim_of_exhaustive_decision_sampling=True,previous_final_hindsight_not_new_validation=True))
    rows=read(B/'final_rows.json');dev=read(B/'development_rows.json');by={(r['seed'],r['family'],r['context'],r['policy']):r for r in rows};pairs=[]
    for r in rows:
        if r['policy']==s.parent.BAND:continue
        d=guarded_pair(r,by[r['seed'],r['family'],r['context'],s.parent.BAND],by[r['seed'],r['family'],r['context'],s.parent.TRITON])
        category='서비스 악화' if not d['service_preserved_both'] else '비용 상충' if not d['nonworse_both'] else 'J·AP 공동감소' if d['joint_gain_both'] else 'J 비악화·AP 감소' if d['heat_gain_both'] else '비악화·열차 없음'
        pairs.append(dict(seed=r['seed'],family=r['family'],context=r['context'],policy=r['policy'],**d,category=category))
    sums=[]
    for p in s.POLICIES:
        g=[r for r in rows if r['policy']==p];ps=[r for r in pairs if r['policy']==p]
        sums.append(dict(policy=p,conditions=24,planned=sum(r['planned'] for r in g),completed=sum(r['completed'] for r in g),urgent_failures=sum(r['urgent_service_failure'] for r in g),normal_failures=sum(r['normal_service_failure'] for r in g),
            **{k:statistics.mean(r[k] for r in g) for k in ('urgent_p95_ms','normal_mean_ms','energy_j','peak_ap_c')},
            nonworse_both=sum(r['nonworse_both'] for r in ps),heat_gain_both=sum(r['heat_gain_both'] for r in ps),absolute_heat_gain=sum(r['heat_gain_both'] and r['absolute_deadline_eligible_all'] for r in ps),joint_gain_both=sum(r['joint_gain_both'] for r in ps),service_regressions_vs_band=sum(not r['service_preserved'] for r in ps),
            decision_host_total_s=sum(r['decision_host_total_s'] for r in g),decision_host_max_ms=max(r['decision_host_max_ms'] for r in g),prefix_checks=sum(r.get('prefix_checks',0) for r in g),prefix_blocks=sum(r.get('prefix_blocked_calls',0) for r in g)))
    items=native_items(s.LOCAL,s.events());olditems=native_items(s.parent.LOCAL,s.parent.events());ancestor=s.parent.previous.parent.parent
    # The joint study reused its development Band rows; their native ledgers
    # belong to the ancestor study, rather than the joint study's item folder.
    ancestor_items=native_items(ancestor.LOCAL,ancestor.events())
    for identity,item in ancestor_items.items():
        if identity.startswith('development/') and item['row']['policy']==s.parent.BAND:
            expected=next(r for r in read(s.parent.BUNDLE/'development_rows.json') if r['identity']==identity)
            assert item['row']==expected;olditems[identity]=item
    frozen,_=s.parent.x.p.inputs(s.parent.x.p.BUNDLE)
    explanations=[]
    for source,split in ((olditems,'old_development'),(olditems,'old_final'),(items,'fresh_final')):
        chosen_split='development' if split=='old_development' else 'final'
        for item in source.values():
            row=item['row']
            if row['family']!='sustained' or row['policy'] not in (*s.parent.NEW,s.x.POLICY) or not row['identity'].startswith(chosen_split+'/'):continue
            baseline=next(o for o in source.values() if o['row']['policy']==s.parent.BAND and o['row']['seed']==row['seed'] and o['row']['family']=='sustained' and o['row']['context']==row['context'])
            explanations.append(explain(item,baseline,frozen,split))
    write(D/'native_first_changes.json',explanations);guards=[dict(identity=i['row']['identity'],**g) for i in items.values() for g in i['prefix_guards']]
    (B/'prefix_guard_events.json.gz').write_bytes(gzip.compress(json.dumps(guards,separators=(',',':'),allow_nan=False).encode(),mtime=0))
    equality={}
    for p in (*s.parent.NEW,s.x.POLICY):
        n=0
        for row in rows:
            if row['policy']!=p:continue
            b=by[row['seed'],row['family'],row['context'],s.parent.BAND]
            clean=lambda item:[{k:v for k,v in q.items() if k!='source_request_id'} for q in item['result']['ledger']]
            n+=clean(items[row['identity']])==clean(items[b['identity']])
        equality[p]=n
    new=[r for r in rows if r['policy']==s.x.POLICY];old=[by[r['seed'],r['family'],r['context'],s.parent.x.WAIT] for r in new]
    ablation=[dict(seed=r['seed'],family=r['family'],context=r['context'],**compare(r,o)) for r,o in zip(new,old)]
    chosen=read(B/'selection.json')['chosen'];summary=dict(status='completed',selected_before_final=chosen,adopted=False,final_rows=len(rows),final_planned=sum(r['planned'] for r in rows),final_completed=sum(r['completed'] for r in rows),
        original_native_successes=len(items),new_native_requests=sum(i['row']['planned'] for i in items.values()),diagnostic_replay_requests=4608,combined_new_environment_starts=170,combined_new_requests=4608+sum(i['row']['planned'] for i in items.values()),
        consumption=read(B/'completion.json')['consumption'],policy_summaries=sums,Band_ledger_equal_ignoring_source_label=equality,
        original_joint_vs_guarded=dict(conditions=24,energy_equal_within_1e_8=all(abs(r['energy_j']-o['energy_j'])<1e-8 for r,o in zip(new,old)),p95_changed=sum(abs(r['urgent_p95_ms']-o['urgent_p95_ms'])>1e-8 for r,o in zip(new,old)),
            ledger_changed=sum(items[r['identity']]['result']['ledger']!=items[o['identity']]['result']['ledger'] for r,o in zip(new,old))),
        no_further_tuning=True,experiment_ready=False,physical_improvement_proven=False,
        preparation_issue=dict(count=1,scope='before native environments',cause='prepare and run were mistakenly launched concurrently; atomic inputs temporary file was in use on Windows',
            resolution='prepare failed; the run-created registration and input/source hashes were checked before all native environments; one frozen registration, no re-registration or changes to criteria',environment_starts=0))
    write(B/'summary.json',summary);prior_report.csv_write(B/'development_results.csv',dev);prior_report.csv_write(B/'final_results.csv',rows);prior_report.csv_write(B/'policy_summary.csv',sums);prior_report.csv_write(B/'pairs_vs_band.csv',pairs);prior_report.csv_write(B/'guard_ablation.csv',ablation)
    for folder,events in ((D,s.diagnosis.events()),(B,s.events())):prior_report.csv_write(folder/'execution_receipts.csv',events)
    rep=read(B/'registration.json')['representative'];reps={p:items[next(r['identity'] for r in rows if r['policy']==p and all(r[k]==v for k,v in rep.items()))] for p in s.POLICIES}
    write(B/'representatives.json',{p:dict(row=i['row'],ledger=i['result']['ledger'],curves=i['curves']) for p,i in reps.items()})
    plots(pairs,sums,reps,diagnosis);dashboard(pairs,sums,diag_rows,summary)
    return summary
def plots(pairs,sums,reps,diagnosis):
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False});out=B/'figures';out.mkdir(exist_ok=True)
    fig,ax=plt.subplots(figsize=(11,6),layout='constrained')
    for p in (s.parent.x.WAIT,s.x.POLICY):
        g=[r for r in pairs if r['policy']==p]
        for good,marker in ((True,'o'),(False,'x')):
            part=[r for r in g if r['service_preserved']==good]
            ax.scatter([r['delta_energy_j'] for r in part],[r['delta_peak_ap_c'] for r in part],marker=marker,alpha=.6,label=LABELS[p]+(' 서비스 악화' if not good else ''))
    ax.axhline(0,color='grey');ax.axvline(0,color='grey');ax.set_xlabel('같은 입력 Band 대비 기기 전체 J 차이');ax.set_ylabel('최고 AP 모형값 차이 °C');ax.legend();ax.grid(alpha=.2);ax.set_title('첫 선택 검사 후에도 남은 열·에너지 상충');fig.savefig(out/'01_열에너지상충.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    for ax,k,label in zip(axes,('urgent_p95_ms','normal_failures'),('조건별 긴급 P95 평균 ms','일반 기한 실패 건')):
        ax.bar(range(5),[r[k] for r in sums]);ax.set_xticks(range(5),[LABELS[r['policy']] for r in sums],rotation=30,ha='right');ax.set_ylabel(label);ax.grid(axis='y',alpha=.2)
    fig.suptitle('새 확인24조건 — 완료량을 유지한 서비스 비교');fig.savefig(out/'02_응답과기한완료.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(5,1,figsize=(13,8),sharex=True,layout='constrained')
    for ax,(p,item) in zip(axes,reps.items()):
        for q in item['result']['ledger']:
            a=q['dispatch_ns']/1e9;b=q['lane_available_ns']/1e9;y=q['backend']=='GPU'
            ax.broken_barh([(a,b-a)],(y-.25,.5),facecolors='#397cb3' if q['priority']=='urgent' else '#eda040')
        ax.set_yticks([0,1],['CPU','GPU']);ax.set_title(LABELS[p],loc='left',fontsize=10);ax.grid(axis='x',alpha=.2)
    axes[-1].set_xlim(35,55);axes[-1].set_xlabel('초 — 사전 대표 지속/평균의 첫20초');fig.savefig(out/'03_대표작업시간표.png',dpi=150);plt.close(fig)
    bad=next(q for r in diagnosis if r['split']=='development' and r['policy']==s.parent.x.WAIT for q in r['prefixes'] if not q['actual_prefix_guard_pass'])
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    for p in (s.parent.BAND,s.parent.x.WAIT,s.x.POLICY):
        c=reps[p]['curves'];axes[0].plot(c['ap_times_s'],c['ap_path'],label=LABELS[p])
    axes[0].set_xlabel('초');axes[0].set_ylabel('동일 AP 모형 °C');axes[0].legend();axes[0].grid(alpha=.2)
    for i,(key,name) in enumerate((('references','Band 예측'),('full','후속 전체 계획'),('first','첫 선택+Band'))):
        axes[1].bar([j+(i-1)*.25 for j in range(3)],[bad[key][c]['global_peak_ap_c'] for c in s.parent.x.core.CONTEXTS],width=.25,label=name)
    values=[bad[k][c]['global_peak_ap_c'] for k in ('references','full','first') for c in s.parent.x.core.CONTEXTS]
    axes[1].set_ylim(min(values)-.003,max(values)+.003);axes[1].set_xticks(range(3),['평균','짧은 실행','긴 실행']);axes[1].set_ylabel('현재 도착큐의 예상 최고 AP °C');axes[1].legend(fontsize=9);axes[1].set_title('사전 개발 첫 반례: 후속 냉각 이득을 첫 선택에 전용');fig.savefig(out/'04_온도경로와계획차이.png',dpi=150);plt.close(fig)
    keys=sorted({(r['seed'],r['family'],r['context']) for r in pairs});ps=(s.parent.x.WAIT,s.x.POLICY);names=['서비스 악화','비용 상충','비악화·열차 없음','J 비악화·AP 감소','J·AP 공동감소'];codes={n:i for i,n in enumerate(names)}
    matrix=[[codes[next(r['category'] for r in pairs if r['policy']==p and (r['seed'],r['family'],r['context'])==k)] for k in keys] for p in ps]
    family={'low':'낮음','queue':'큐','burst':'몰림','sustained':'지속'};ctx={'mean':'평균','short_context':'짧음','long_context':'김'}
    fig,ax=plt.subplots(figsize=(15,5),layout='constrained');im=ax.imshow(matrix,cmap=ListedColormap(['#c34d4d','#e9a351','#dedede','#699bcb','#65a776']),vmin=-.5,vmax=4.5,aspect='auto')
    ax.set_yticks(range(2),[LABELS[p] for p in ps]);ax.set_xticks(range(24),[f'{k[0]-815030100} {family[k[1]]} {ctx[k[2]]}' for k in keys],rotation=65,ha='right');cb=fig.colorbar(im,ax=ax,ticks=range(5));cb.ax.set_yticklabels(names);ax.set_title('새 확인 전체 — 양 기준 비악화와 서비스 악화 구분');fig.savefig(out/'05_조건별결과지도.png',dpi=150);plt.close(fig)
def dashboard(pairs,sums,diag,summary):
    def table(rows,fields):
        def fmt(v):return LABELS.get(v,v) if isinstance(v,str) else f'{v:.8g}' if isinstance(v,float) else str(v)
        return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+name+'</th>' for key,name in fields)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(fmt(r[k]))+'</td>' for k,n in fields)+'</tr>' for r in rows)+'</tbody></table></div>'
    rules=[dict(policy=p,rule='원 재현 규칙' if p in s.POLICIES[:2] else '원 공동 계획' if p in s.POLICIES[2:4] else '같은 공동 계획 + 실제 첫 선택3문맥 비악화 검사') for p in s.POLICIES]
    body='<h1>후속 계획과 실제 첫 선택을 분리한 롤링 호라이즌</h1><p>개발 진단: 큰 창24개 선별 손실0, 선택527개 중 첫 선택AP 위반12개. 새 확인은 별도 seed·24조건·5정책입니다.</p><p>개발 적격 없음으로 동결, 전체 정책 미채택. AP 모형값은 표면온도가 아니며 실제 폰 절감을 입증하지 않습니다.</p><p><a href="README.md">결과·한계</a> · <a href="final_results.csv">전체 확인 CSV</a> · <a href="../rolling_diagnosis_01/README.md">원인 진단</a> · <a href="guard_ablation.csv">첫 선택 검사 제거 비교</a></p><input id="filter" placeholder="정책·부하·문맥 검색">'
    body+=table(rules,[('policy','규칙'),('rule','판단 차이')]);body+=table(sums,[('policy','정책'),('completed','완료'),('planned','예정'),('urgent_failures','긴급 실패'),('normal_failures','일반 실패'),('urgent_p95_ms','P95 평균 ms'),('energy_j','J 평균'),('peak_ap_c','최고 AP 평균'),('heat_gain_both','양 기준 AP 감소'),('prefix_blocks','첫 선택 차단')])
    body+=table(diag,[('split','원자료'),('seed','seed'),('context','문맥'),('policy','원후보'),('selected_plans','선택계획'),('prefix_guard_failures','첫 선택 위반'),('shortlist_snapshots','큰 창 진단'),('omitted_better','놓친 더 좋은 계획')])
    body+=table(pairs,[('seed','seed'),('family','부하'),('context','문맥'),('policy','후보'),('category','양 기준 판정'),('delta_energy_j','Band J 차이'),('delta_peak_ap_c','Band AP 차이'),('delta_urgent_p95_ms','Band P95 차이 ms')])
    for p in sorted((B/'figures').glob('*.png')):body+=f'<img src="figures/{p.name}" alt="{p.stem}">'
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>첫 선택 검사 롤링 비교</title><style>body{font-family:Malgun Gothic,sans-serif;margin:24px;max-width:1450px;color:#263142}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #ddd;padding:7px}th{background:#edf3f8}.scroll{overflow:auto;margin:18px 0}input{padding:10px;width:320px}img{width:100%;max-width:1300px;margin:20px 0}</style>'+body+'<script>document.querySelector("#filter").addEventListener("input",e=>{let q=e.target.value.toLowerCase();document.querySelectorAll("tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));});</script></html>'
    (B/'index.html').write_text(page,encoding='utf8',newline='\n')
if __name__=='__main__':print(json.dumps(report(),ensure_ascii=False,indent=2))
