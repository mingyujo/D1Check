"""Report conditional retained-work results, explicit omitted work and wait scope."""
from __future__ import annotations
import csv,gzip,hashlib,html,json,statistics
from pathlib import Path
from tools import d1_busy_oracle_study as s
from tools.d1_edd_ect_residual_report import compare

BUNDLE=s.BUNDLE;LOCAL=s.LOCAL;ROOT=s.ROOT;read=s.read;write=s.write
LABELS={s.BAND:'Band 요청 규칙',s.TRITON:'Triton 고정 배정',s.EDD:'기한 우선 ECT',s.x.micro.SLACK:'응답 여유시간 ECT',s.x.micro.FLEX:'여유시간·CPU 보호',s.POLICIES[-2]:'열·에너지 리스트',s.POLICIES[-1]:'구간 계획·AP 필터','ORACLE':'오프라인 유한 일정'}
def csv_write(path,rows):
    with path.open('w',encoding='utf8',newline='') as f:
        fields=list(dict.fromkeys(k for r in rows for k in r));w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)


def load_items():
    done={r['identity']:r for r in s.entries() if r['event']=='completed'};items={}
    for path in (LOCAL/'items').glob('*.gz'):
        item=json.loads(gzip.decompress(path.read_bytes()));identity=item['row']['identity'];assert s.sha(path)==done[identity]['artifact_sha256'];items[identity]=item
    return items


def intentional_idle(case,item):
    ls=item['result']['ledger'];events=sorted({case['snapshot_ns']}|{r[k] for r in ls for k in ('arrival_ns','dispatch_ns','lane_available_ns') if r[k]>=case['snapshot_ns']})
    gaps=[]
    for a,b in zip(events,events[1:]):
        if b<=a:continue
        mid=(a+b)/2
        if not any(r['dispatch_ns']<=mid<r['lane_available_ns'] for r in ls) and any(r['id'] in case['variable_ids'] and r['arrival_ns']<=mid<r['dispatch_ns'] for r in ls):
            if gaps and gaps[-1][1]==a:gaps[-1][1]=b
            else:gaps.append([a,b])
    maximum=max([0.]+[(b-a)/1e9 for a,b in gaps])
    return dict(both_lanes_idle_with_arrived_work_s=sum((b-a)/1e9 for a,b in gaps),max_idle_gap_s=maximum,
        exceeds_current_cooling_credit=maximum>.25+1e-9,idle_intervals_ns=gaps,
        interpretation='sufficient mismatch if >0.25s with both lanes free and supported arrived work; not a full RL action reachability proof')


def conditional_energy_lower_bound(case,frozen,initial):
    """Relax future order/SLA/AP, retaining fixed prefix energy and overlap.

    Every variable GPU-class overlap needs one GPU-class and one CPU-detection
    time unit. Fixed future unpaired time is a further optimistic capacity.
    This relaxes timing, so cannot overstate the attainable energy improvement.
    """
    import itertools
    by={q['id']:q for q in case['tickets']};profile=s.x.p.profile(frozen,case['context']);model=s.x.micro.PulseModel(frozen,initial)
    fixed=[]
    for j in case['prefix_calendar']:
        q=by[j['request_id']];label=q['task']+'_'+j['backend'];start=j['start_ns'];end=start
        for d in profile[s.x.p.key(q,j['backend'])]:end+=d
        fixed.append(dict(label=label,start=round(start)/1e9,end=round(end)/1e9))
    cut=case['snapshot_ns']/1e9;cg=[j for j in fixed if j['label']=='classification_GPU'];dc=[j for j in fixed if j['label']=='detection_CPU']
    overlap=sum(max(0.,min(a['end'],b['end'])-max(a['start'],b['start'])) for a in cg for b in dc)
    future_overlap=sum(max(0.,min(a['end'],b['end'])-max(a['start'],b['start'],cut)) for a in cg for b in dc)
    free_cg=sum(max(0.,j['end']-max(j['start'],cut)) for j in cg)-future_overlap
    free_dc=sum(max(0.,j['end']-max(j['start'],cut)) for j in dc)-future_overlap
    fixed_cost=model.background+sum(model.watts[j['label']]*(j['end']-j['start']) for j in fixed)+model.corr_w*overlap
    qs=[by[i] for i in case['variable_ids']];values=[]
    for assignment in itertools.product(*(s.x.p.backends(q) for q in qs)):
        times=[sum(profile[s.x.p.key(q,b)])/1e9 for q,b in zip(qs,assignment)]
        energy=sum(model.watts[q['task']+'_'+b]*d for q,b,d in zip(qs,assignment,times))
        gpu=sum(d for q,b,d in zip(qs,assignment,times) if b=='GPU');cpu_d=sum(d for q,d in zip(qs,times) if q['task']=='detection')
        n=len(case['tickets']);rounding=(n+2*n*n)*1e-9*max(model.watts.values())
        values.append(fixed_cost+energy+min(0.,model.corr_w)*min(gpu+free_cg,cpu_d+free_dc)-rounding)
    return min(values)


def report():
    assert read(BUNDLE/'completion.json')['status']=='completed';s.check();items=load_items();cases=[read(p) for p in sorted(BUNDLE.glob('case_*.json'))]
    data=read(BUNDLE/'inputs.json');frozen,_=s.x.p.inputs(s.x.p.BUNDLE)
    write(BUNDLE/'analysis_contract.json',dict(scope='post-registration diagnostics only; no outcome/selection/domain/gate change',
        energy_bound='fixed prefix energy/overlap plus variable solo energy and optimistic min(total future GPU-class,CPU-detection) overlap with unpaired future prefix time; ns rounding allowance; relax SLA/AP/timing',
        idle='intervals >=snapshot where both lanes empty and selected arrived job waits; max gap > original0.25s credit is sufficient mismatch, not full action proof',
        history_normal_guard='normal mean nonworsening additional diagnosis, not adoption gate retrofit',independent_holdout=False))
    rows=[];paired=[];proofs=[];waits=[];summaries=[]
    for i,r in enumerate(cases):
        case=r['case'];base=r['baselines'][s.BAND];ref=[r['baselines'][k] for k in (s.BAND,s.TRITON)]
        for policy,row in r['baselines'].items():
            rows.append(row)
            if policy!=s.BAND:paired.append(dict(case=i,source_index=case['source_index'],family=case['family'],context=case['context'],policy=policy,**compare(row,base)))
        min_j=r['verified']['min_J'];min_ap=r['verified']['min_AP'];pair=compare(min_ap,base);pair['native_joint_gain']=pair.pop('joint_gain')
        comparisons=[compare(min_ap,rr) for rr in ref];bound=conditional_energy_lower_bound(case,frozen,data['initial'])
        assert bound<=base['energy_j']+1e-9 and bound<=min_j['energy_j']+1e-9,'invalid lower bound'
        proofs.append(dict(case=i,source_index=case['source_index'],seed=case['seed'],family=case['family'],context=case['context'],snapshot_s=case['snapshot_ns']/1e9,
            retained=len(case['tickets']),original=case['original_requests'],omitted=len(case['omitted_ids']),prefix=len(case['prefix_calendar']),active=len(case['active_ids']),original_waiting=case['waiting_original'],
            **r['oracle']['counts'],min_j=min_j['energy_j'],min_ap=min_ap['peak_ap_c'],band_j=base['energy_j'],band_ap=base['peak_ap_c'],
            delta_min_j=min_j['energy_j']-base['energy_j'],**pair,nonworse_both=all(a['nonworse'] for a in comparisons),heat_gain_both=all(a['heat_gain'] for a in comparisons),
            normal_mean_preserved_both=all(min_ap['normal_mean_ms']<=rr['normal_mean_ms']+1e-9 for rr in ref),
            conditional_relaxed_lower_bound_j=bound,band_above_bound_j=base['energy_j']-bound,oracle_wall_s=r['oracle']['host_wall_s']))
        wait=dict(case=i,source_index=case['source_index'],**intentional_idle(case,items[min_ap['identity']]));waits.append(wait)
    for policy in s.POLICIES:
        group=[r for r in rows if r['policy']==policy]
        summaries.append(dict(policy=policy,conditions=len(group),planned=sum(r['planned'] for r in group),completed=sum(r['completed'] for r in group),urgent_failures=sum(r['urgent_service_failure'] for r in group),normal_failures=sum(r['normal_service_failure'] for r in group),
            urgent_p95_ms=statistics.mean(r['urgent_p95_ms'] for r in group),normal_mean_ms=statistics.mean(r['normal_mean_ms'] for r in group),energy_j=statistics.mean(r['energy_j'] for r in group),peak_ap_c=statistics.mean(r['peak_ap_c'] for r in group),
            decision_host_total_s=sum(r['decision_host_total_s'] for r in group),host_environment_wall_s=sum(r['host_wall_s'] for r in group)))
    robust=[dict(nominal_case=r['nominal_case'],role=r['role'],context=r['actual_context'],planned=r['row']['planned'],completed=r['row']['completed'],urgent_failures=r['row']['urgent_service_failure'],normal_failures=r['row']['normal_service_failure'],**compare(r['row'],r['reference'])) for r in read(BUNDLE/'robustness.json')]
    protection=sum(d.get('reason')=='protect_arrived_cpu_only_deadline' for item in items.values() for d in item['result']['decisions'])
    summary=dict(status='completed',screened=48,eligible=4,excluded=44,distinct_consumed_source_traces=2,cases=4,retained_requests_per_case=15,variable_requests_per_case=4,
        raw_calendars=sum(p['raw'] for p in proofs),safe_pruned=sum(p['pruned'] for p in proofs),visited_calendars=sum(p['visited'] for p in proofs),service_valid=sum(p['service_valid'] for p in proofs),joint_gain_calendars=sum(p['joint_gain'] for p in proofs),
        offline_heat_gain_conditions=sum(p['heat_gain_both'] for p in proofs),selected_min_ap_heat_gain_with_normal_mean_preserved=sum(p['heat_gain_both'] and p['normal_mean_preserved_both'] for p in proofs),
        offline_heat_change_c=[min(p['delta_peak_ap_c'] for p in proofs),max(p['delta_peak_ap_c'] for p in proofs)],normal_mean_change_ms=[min(p['delta_normal_mean_ms'] for p in proofs),max(p['delta_normal_mean_ms'] for p in proofs)],
        maximum_energy_gain_j=max(-p['delta_min_j'] for p in proofs),band_above_relaxed_bound_j=[min(p['band_above_bound_j'] for p in proofs),max(p['band_above_bound_j'] for p in proofs)],
        offline_exceeds_current_RL_credit=sum(w['exceeds_current_cooling_credit'] for w in waits),offline_idle_gap_s=[min(w['max_idle_gap_s'] for w in waits),max(w['max_idle_gap_s'] for w in waits)],protection_calls=protection,
        robust_replays=len(robust),robust_distinct_plans_and_contexts=2,robust_nonworse=sum(r['nonworse'] for r in robust),robust_service_preserved=sum(r['service_preserved'] for r in robust),
        robust_max_p95_regression_ms=max(r['delta_urgent_p95_ms'] for r in robust),total_planned=sum(i['row']['planned'] for i in items.values()),total_completed=sum(i['row']['completed'] for i in items.values()),
        original_engine_successes=len(items),consumption=read(BUNDLE/'completion.json')['consumption'],no_new_training=True,no_policy_promotion=True,
        recommendation='retain prior full-trace Band-adapted baseline; no new RL training based on this diagnostic; thermal-spacing upper-bound signal requires separately specified online action/objective and full-arrival evaluation',
        caveats='consumed conditional subset; exact finite space only; numerical AP estimate not surface or physical heat reduction; missing threshold and APK control energy; no thermal/service coupling invented')
    csv_write(BUNDLE/'screening.csv',data['screening']);csv_write(BUNDLE/'policy_results.csv',rows);csv_write(BUNDLE/'policy_summary.csv',summaries);csv_write(BUNDLE/'pairs_vs_band.csv',paired)
    csv_write(BUNDLE/'oracle_certificates.csv',proofs);csv_write(BUNDLE/'robustness_results.csv',robust);write(BUNDLE/'wait_scope.json',waits)
    csv_write(BUNDLE/'execution_receipts.csv',[{k:e.get(k) for k in ('event','utc','number','identity','kind','error')} for e in s.entries()]);write(BUNDLE/'summary.json',summary)
    rep=next(r for r in cases if r['case']['source_index']==6);reps={p:next(i for i in items.values() if i['row']['policy']==p and i['row']['identity'].startswith('base/0/')) for p in s.POLICIES}
    reps['ORACLE']=items[rep['verified']['min_AP']['identity']];write(BUNDLE/'representatives.json',reps)
    plots(proofs,paired,reps,waits);dashboard(proofs,summaries,robust,summary);return summary


def plots(proofs,paired,reps,waits):
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False});out=BUNDLE/'figures';out.mkdir(exist_ok=True)
    fig,axes=plt.subplots(1,3,figsize=(14,4),layout='constrained')
    for ax,key,label in zip(axes,('delta_min_j','delta_peak_ap_c','delta_normal_mean_ms'),('최소 에너지 차이 J','최소 AP 차이 °C','일반 평균 지연 차이 ms')):
        ax.bar(range(4),[p[key] for p in proofs]);ax.set_ylabel(label);ax.set_xticks(range(4),['몰림 평균','몰림 짧음','몰림 길음','큐 길음']);ax.axhline(0,color='grey');ax.grid(axis='y',alpha=.2)
    fig.suptitle('Band 대비 오프라인 여지 — J 동률, AP 감소, 일반 완료 지연');fig.savefig(out/'01_열감소와지연상충.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(8,1,figsize=(13,12),sharex=True,layout='constrained')
    for ax,(policy,item) in zip(axes,reps.items()):
        ax.axvline(proofs[0]['snapshot_s'],color='black',linestyle='--',alpha=.6)
        for r in item['result']['ledger']:
            start=r['dispatch_ns']/1e9;end=r['lane_available_ns']/1e9;y=0 if r['backend']=='CPU' else 1
            ax.broken_barh([(start,end-start)],(y-.28,.56),facecolors='#4677b5' if r['priority']=='urgent' else '#e6a744')
        ax.set_yticks([0,1],['CPU','GPU']);ax.set_title(LABELS[policy],loc='left',fontsize=10);ax.grid(axis='x',alpha=.2)
    axes[-1].set_xlim(37,43);axes[-1].set_xlabel('공통 시간 초 — 세로선 이전 실행 이력 고정');fig.suptitle('사전 대표 812020001/몰림/평균 — 5단계 lane 점유');fig.savefig(out/'02_대표실행시간표.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(14,5),layout='constrained')
    for policy in (s.BAND,s.EDD,'ORACLE'):
        item=reps[policy];curve=item['curves'];axes[0].plot(curve['ap_times_s'],curve['ap_path'],label=LABELS[policy])
    axes[0].set_xlabel('초');axes[0].set_ylabel('AP 모형 °C');axes[0].legend();axes[0].grid(alpha=.2)
    axes[1].bar(range(4),[w['max_idle_gap_s'] for w in waits]);axes[1].axhline(.25,color='red',linestyle='--',label='현재 RL 냉각 credit0.25초');axes[1].set_ylabel('대기 요청 존재·양 lane 유휴 최장 초');axes[1].set_xlabel('조건 번호');axes[1].legend();fig.suptitle('열 이력 보존과 대기 행동 범위');fig.savefig(out/'03_온도경로와대기범위.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(14,5),layout='constrained')
    policies=list(s.POLICIES)[1:];matrix=[]
    for policy in policies:matrix.append([next(r for r in paired if r['policy']==policy and r['case']==i)['delta_peak_ap_c'] for i in range(4)])
    im=axes[0].imshow(matrix,cmap='coolwarm',aspect='auto');axes[0].set_yticks(range(6),[LABELS[p] for p in policies]);axes[0].set_xticks(range(4),['몰림 평균','몰림 짧음','몰림 길음','큐 길음']);fig.colorbar(im,ax=axes[0],label='Band 대비 AP 차이 °C')
    axes[1].bar(range(4),[p['band_above_bound_j'] for p in proofs]);axes[1].set_ylabel('Band와 낙관적 조건부 J 하한 차이');axes[1].set_xlabel('조건 번호');axes[1].ticklabel_format(axis='y',style='sci',scilimits=(0,0));fig.suptitle('조건별 선택 차이와 원 모형의 에너지 여지');fig.savefig(out/'04_조건지도와에너지여지.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(14,5),layout='constrained');policies=list(s.POLICIES)
    for key,ax,label in zip(('urgent_p95_ms','normal_mean_ms'),axes,('긴급 응답 P95 ms','일반 완료 평균 ms')):
        ax.bar(range(7),[statistics.mean(r['baselines'][p][key] for r in [read(f) for f in sorted(BUNDLE.glob('case_*.json'))]) for p in policies]);ax.set_xticks(range(7),[LABELS[p] for p in policies],rotation=35,ha='right');ax.set_ylabel(label);ax.grid(axis='y',alpha=.2)
    fig.suptitle('공통 유지 요청 전량 완료·기한 위반0 — 조건별 지표 평균');fig.savefig(out/'05_응답과완료비교.png',dpi=150);plt.close(fig)


def dashboard(proofs,summaries,robust,summary):
    def table(rows,fields):
        body=''
        for row in rows:
            body+='<tr>'+''.join('<td>'+html.escape(str(LABELS.get(row[k],row[k])) if isinstance(row[k],str) else f'{row[k]:.9g}' if isinstance(row[k],float) else str(row[k]))+'</td>' for k,_ in fields)+'</tr>'
        return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+v+'</th>' for _,v in fields)+'</tr></thead><tbody>'+body+'</tbody></table></div>'
    rules=[dict(policy=p,decision=d) for p,d in zip(s.POLICIES,('원 HEFT whole-request 순위·worker 선택·완료 EMA','원 fixed instance·rate off + 외부 prefix 점유 guard','EDD 우선·5단계 lane ECT','due - 예상 응답·lane ECT','여유시간 + 이미 도착한 CPU 전용 요청 보호','원3문맥 J/AP/서비스 필터·제한 대기','현재4요청 CP-SAT J 계획·첫 행동 AP 필터'))]
    body='<h1>실행 중 작업·대기열이 있는 조건부 비교</h1><p>48조건 중 구조 적격4 · 요청15건씩 유지 · 다른9건 제외. 전체 원 trace 우위나 독립 평가가 아닙니다.</p><p>전수 공간에서 공동 J/AP 감소0. J 동률로 AP 모형0.020~0.040°C 감소하는 오프라인 일정은4조건, 일반 평균98~181ms 지연. 실제 표면온도나 폰 절감이 아닙니다.</p><p><a href="README.md">보고서·계약·명령</a> · <a href="screening.csv">전체 선별 목록</a> · <a href="oracle_certificates.csv">전수 CSV</a></p><input id="filter" placeholder="정책·조건 검색">'
    body+=table(rules,[('policy','규칙'),('decision','판단 차이')])
    body+=table(summaries,[('policy','규칙'),('completed','완료/60'),('urgent_failures','긴급 실패'),('normal_failures','일반 실패'),('urgent_p95_ms','긴급 P95 ms'),('normal_mean_ms','일반 평균 ms'),('energy_j','J 평균'),('peak_ap_c','AP 평균')])
    body+=table(proofs,[('case','조건'),('family','부하'),('context','문맥'),('raw','선언 공간'),('visited','방문'),('joint_gain','공동감소'),('delta_peak_ap_c','참고 AP 차이'),('delta_normal_mean_ms','일반 지연 ms')])
    body+=table(robust,[('role','목적'),('context','실행 문맥'),('service_preserved','서비스 유지'),('nonworse','J/AP 비악화'),('delta_energy_j','J 차이'),('delta_peak_ap_c','AP 차이'),('delta_urgent_p95_ms','P95 차이 ms')])
    for p in sorted((BUNDLE/'figures').glob('*.png')):body+=f'<img src="figures/{p.name}" alt="{p.stem}">'
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>조건부 대기열 비교</title><style>body{font-family:Malgun Gothic,sans-serif;margin:24px;max-width:1450px;color:#263142}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #ddd;padding:7px}th{background:#edf3f8}.scroll{overflow:auto;margin:18px 0}input{padding:10px;width:300px}img{width:100%;max-width:1300px;margin:20px 0}</style>'+body+'<script>document.querySelector("#filter").addEventListener("input",e=>{let q=e.target.value.toLowerCase();document.querySelectorAll("tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));});</script></html>'
    (BUNDLE/'index.html').write_text(page,encoding='utf8',newline='\n')


if __name__=='__main__':print(json.dumps(report(),ensure_ascii=False,indent=2))
