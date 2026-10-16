"""Read-only model accounting; write pilot review artifacts, never run an environment."""
from __future__ import annotations

import csv
import gzip
import html
import json
import math
import statistics
import subprocess
from types import SimpleNamespace

from tools import d1_reserved_thermal_study as s
from tools import d1_reserved_thermal_pilot_repair as repair

NEW = s.rule.PUBLIC_POLICY
EPS = 1e-9  # Numerical equality only, not model accuracy.
LABELS = {
    NEW:'기한 예약·열 분산', 'SHARED_EFT':'예상 완료 우선',
    'BAND_HEFT_WHOLE_REQUEST_ADAPT_V1':'Band 요청 대응',
    'TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1':'Triton 제한 해제',
    'TRITON_RATE_CAP1_EQUAL_REQUEST_ADAPT_V1':'Triton 동시1·동일',
    'TRITON_RATE_CAP2_EQUAL_REQUEST_ADAPT_V1':'Triton 동시2·동일',
    'TRITON_RATE_CAP1_CLASS_WEIGHT_REQUEST_ADAPT_V1':'Triton 동시1·분류 가중',
    'TRITON_RATE_CAP2_CLASS_WEIGHT_REQUEST_ADAPT_V1':'Triton 동시2·분류 가중',
    'ENERGY_AP_REQUEST_V1':'기존 에너지·열 규칙',
    'ARRIVED_QUEUE_J_PEAK_AREA_V1':'기존 큐 전체 규칙'}


def load(path):
    with gzip.open(path,'rt',encoding='utf8') as f:
        return json.load(f)


def typed(value):
    if value=='': return None
    if value in ('True','False'): return value=='True'
    try: return float(value) if any(c in value for c in '.eE') else int(value)
    except ValueError: return value


def key(row):
    return row['seed'],row['family'],row['context']


def delta(a,b):
    return a-b if a is not None and b is not None else None


def mean(values):
    values=[v for v in values if v is not None]
    return statistics.mean(values) if values else None


def comparisons(rows):
    ours={key(r):r for r in rows if r['policy']==NEW}
    pairs=[]
    for base in rows:
        if base['policy']==NEW: continue
        new=ours[key(base)]
        full=new['completed']==new['planned'] and base['completed']==base['planned']
        service=(full and new['urgent_service_failure']<=base['urgent_service_failure']
            and new['normal_service_failure']<=base['normal_service_failure']
            and new['urgent_p95_ms']<=base['urgent_p95_ms']+EPS)
        ap=delta(new['peak_ap_c'],base['peak_ap_c'])
        energy=delta(new['energy_j'],base['energy_j'])
        eligible=service and ap is not None and energy is not None
        pairs.append(dict(seed=new['seed'],family=new['family'],context=new['context'],
            baseline=base['policy'],both_full_work=full,service_preserved=service,
            all_new_deadlines_met=new['deadline_met']==new['planned'],cost_eligible=eligible,
            thermal_gain=eligible and ap < -EPS and energy <= EPS,
            joint_gain=eligible and ap < -EPS and energy < -EPS,
            delta_peak_ap_c=ap,delta_energy_j=energy,
            delta_urgent_p95_ms=delta(new['urgent_p95_ms'],base['urgent_p95_ms']),
            delta_normal_mean_ms=delta(new['normal_mean_ms'],base['normal_mean_ms']),
            delta_normal_p95_ms=delta(new['normal_p95_ms'],base['normal_p95_ms']),
            delta_completed=new['completed']-base['completed'],
            delta_deadline_met=new['deadline_met']-base['deadline_met'],
            new_incomplete=new['incomplete'],base_incomplete=base['incomplete']))
    assert len(pairs)==432
    return pairs


def diagnostics(items):
    result=[]
    for item in items:
        row=item['row']; ds=item['result']['decisions']; records=item['records']
        search=sum(d.get('reason')=='reserved_no_admitted_calendar_EFT' for d in ds)
        overrun=sum(d.get('reason')=='reserved_observed_overrun_EFT' for d in ds)
        assert search==row['fallback_callbacks']
        diversity=better=0
        for record in records:
            admitted=[v for v in record['candidates'] if not v['reasons']]
            scores={(round(v['predicted_peak_ap_c'],9),round(v['predicted_total_j'],9))
                for v in admitted}
            diversity+=len(scores)>1
            reference=record['candidates'][0]
            refap=reference['predicted_peak_ap_c']
            better+=refap is not None and any(v['predicted_peak_ap_c']<refap-EPS for v in admitted)
        result.append(dict(seed=row['seed'],family=row['family'],context=row['context'],
            search_fallback_callbacks=search,overrun_fallback_callbacks=overrun,
            all_fallback_callbacks=search+overrun,
            scored_callbacks=len(records),decision_calls=len(ds),
            retained_selected_callbacks=sum(r.get('selected_origin')=='retained' for r in records),
            search_selected_callbacks=sum(r.get('selected_origin')=='search' for r in records),
            reference_selected_callbacks=sum(r.get('selected_origin')=='reference' for r in records),
            score_diverse_admitted_callbacks=diversity,
            thermal_better_than_current_reference_callbacks=better,
            admitted_candidates=sum(r['admitted'] for r in records),
            expansion_limit_callbacks=row['expansion_limit_callbacks'],
            maximum_depth_reached=row['maximum_depth_reached'],
            observed_cap_violation_requests=row['observed_cap_violation_requests'],
            pending_reservations=row['pending_reservations'],
            final_budget_margin_j=row['final_budget_margin_j'],
            final_budget_satisfied=row['final_budget_satisfied'],
            full_work=row['final_full_work'],decision_host_total_s=row['decision_host_total_s'],
            decision_host_max_ms=row['decision_host_max_ms'],projections=row['projections'],
            projection_host_s=row['projection_host_s']))
    return result


def representatives(items, inputs):
    selected={}
    policies={NEW,'SHARED_EFT','BAND_HEFT_WHOLE_REQUEST_ADAPT_V1',
              'TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1'}
    def wanted(row):
        return (row['seed']==610810001 and row['family'] in ('queue','sustained')
            and row['context']=='mean' and row['policy'] in policies
            and row['scope']=='resource' and row['environment']=='immediate_allow')
    for item in items:
        if wanted(item['row']):
            selected[(item['row']['family'],NEW)]=dict(row=item['row'],ledger=item['result']['ledger'],
                decisions=item['result']['decisions'],**item['curves'])
    old_paths=list((s.ROOT/'output/external_rules_20261007_v2/items').glob('*.gz'))
    old_paths+=list((s.existing.LOCAL/'comparison/items').glob('*.gz'))
    hashes={}
    for path in old_paths:
        item=load(path)
        if wanted(item['row']):
            row=item['row']; ident=(row['family'],row['policy'])
            assert ident not in selected
            selected[ident]=item
            hashes[path.relative_to(s.ROOT).as_posix()]=s.digest(path)
    assert len(selected)==8,'representative raw evidence missing'
    tickets={w['family']:w['tickets'] for w in inputs['workloads'] if w['seed']==610810001}
    ledger_rows=[]
    for (family,policy),item in selected.items():
        s.existing.audit(dict(ledger=item['ledger'],decisions=item['decisions']),tickets[family])
        ledger_rows += [dict(family=family,policy=policy,**r) for r in item['ledger']]
    s.existing.csv_write(s.BUNDLE/'pilot_representative_ledger.csv',ledger_rows)
    s.write(s.BUNDLE/'pilot_representatives.json',
        [dict(family=k[0],policy=k[1],**v) for k,v in selected.items()])
    return selected,hashes


def figures(rows,pairs,reps,summary):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':['Malgun Gothic','DejaVu Sans'],'axes.unicode_minus':False,'font.size':10})
    folder=s.BUNDLE/'pilot_figures';folder.mkdir(exist_ok=True)
    def save(fig,name):
        fig.tight_layout();fig.savefig(folder/(name+'.png'),dpi=160,bbox_inches='tight')
        fig.savefig(folder/(name+'.svg'),bbox_inches='tight');plt.close(fig)
    policies=list(LABELS)
    fig,axes=plt.subplots(1,2,figsize=(14,5))
    for ax,field,title in zip(axes,('incomplete','planned'),('미완료 요청 / 전체48조건','기한 실패 요청 / 전체48조건')):
        values=[sum((r['incomplete'] if field=='incomplete' else r['planned']-r['deadline_met'])
            for r in rows if r['policy']==p) for p in policies]
        ax.barh([LABELS[p] for p in policies],values,color=['#276E91']+['#8A9DA5']*9)
        for i,value in enumerate(values):
            ax.text(value+max(values)*.012,i,str(value),va='center',fontsize=9)
        ax.set_xlim(0,max(values)*1.12)
        ax.set_title(title);ax.set_xlabel('요청 수');ax.invert_yaxis()
    save(fig,'01_전체요청_완료와기한')
    baselines=['BAND_HEFT_WHOLE_REQUEST_ADAPT_V1','TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1','SHARED_EFT']
    fig,axes=plt.subplots(1,3,figsize=(13,4.4))
    for ax,base in zip(axes,baselines):
        valid=[r for r in pairs if r['baseline']==base and r['delta_peak_ap_c'] is not None]
        for eligible,color,marker,label in ((True,'#276E91','o','서비스 유지'),(False,'#B66060','x','서비스 손실/미완료')):
            xs=[r for r in valid if r['cost_eligible']==eligible]
            ax.scatter([r['delta_energy_j'] for r in xs],[r['delta_peak_ap_c'] for r in xs],c=color,marker=marker,label=label)
        ax.axhline(0,color='#999',lw=.7);ax.axvline(0,color='#999',lw=.7)
        ax.set_title(LABELS[base]);ax.set_xlabel('신규−기준 에너지 (J)');ax.set_ylabel('신규−기준 AP 최고값 (°C)')
        ax.legend(fontsize=8)
    save(fig,'02_동일조건_열에너지차이')
    fig,axes=plt.subplots(2,4,figsize=(16,6),sharex='row')
    for ri,family in enumerate(('queue','sustained')):
        for ci,policy in enumerate((NEW,'SHARED_EFT','BAND_HEFT_WHOLE_REQUEST_ADAPT_V1','TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1')):
            ax=axes[ri,ci];item=reps[(family,policy)]
            for r in item['ledger']:
                if 'dispatch_ns' not in r:continue
                start=r['dispatch_ns']/1e9;end=r.get('lane_available_ns',120e9)/1e9
                lane=0 if r['backend']=='CPU' else 1
                ax.broken_barh([(start,end-start)],(lane-.32,.64),facecolors='#276E91' if r['priority']=='urgent' else '#D39342')
            ax.set_yticks([0,1],['CPU','GPU']);ax.set_xlim(35,120)
            ax.set_title(LABELS[policy]+' · '+family);ax.set_xlabel('시각 (초)')
    fig.suptitle('사전 지정 seed610810001·mean / lane 실제 반환까지 점유',y=.99)
    save(fig,'03_대표요청_실행시간표')
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for ax,family in zip(axes,('queue','sustained')):
        for policy in (NEW,'SHARED_EFT','BAND_HEFT_WHOLE_REQUEST_ADAPT_V1','TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1'):
            item=reps[(family,policy)]
            ax.plot(item['ap_times_s'],item['ap_path'],label=LABELS[policy])
        ax.set_title('사전 지정 '+family);ax.set_xlabel('시각 (초)');ax.set_ylabel('모형 AP (°C)');ax.legend(fontsize=8)
    save(fig,'04_대표조건_AP경로')
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch
    conditions=sorted({(r['seed'],r['family'],r['context']) for r in pairs})
    bases=list(dict.fromkeys(r['baseline'] for r in pairs))
    by={(r['seed'],r['family'],r['context'],r['baseline']):r for r in pairs}
    matrix=[]
    for condition in conditions:
        row=[]
        for baseline in bases:
            r=by[condition+(baseline,)]
            row.append(0 if not r['cost_eligible'] else 1 if r['thermal_gain'] else
                2 if r['delta_peak_ap_c'] < -EPS and r['delta_energy_j'] > EPS else 3)
        matrix.append(row)
    colors=['#BE6D6D','#328773','#DBAA55','#D9E0E4']
    fig,ax=plt.subplots(figsize=(13,14))
    ax.imshow(matrix,aspect='auto',interpolation='nearest',cmap=ListedColormap(colors),vmin=0,vmax=3)
    ax.set_xticks(range(len(bases)),[LABELS[b] for b in bases],rotation=35,ha='right')
    ax.set_yticks(range(len(conditions)),[f'{seed-610810000:02d} / {family} / {context}' for seed,family,context in conditions],fontsize=8)
    ax.set_title('신규 규칙 - 기준별 조건 지도 / 48조건 모두 표시')
    ax.legend(handles=[Patch(color=c,label=label) for c,label in zip(colors,
        ['서비스 유지 불충족/비용 부적격','AP 감소·J 비증가','AP 감소·J 증가','그 밖의 적격 결과'])],
        loc='lower center',bbox_to_anchor=(.5,-.19),ncol=2)
    save(fig,'05_전체조건_결과지도')


def dashboard(summary,pairs,diagnostic):
    tables=[]
    baseline_display=[{'기준 규칙':LABELS[r['baseline']],'서비스 유지/48':r['service_preserved'],
        '열 감소·J 비증가/48':r['thermal_gain'],'공동 감소/48':r['joint_gain'],
        '주평가 서비스 유지/24':r['low_sustained_service_preserved'],
        '주평가 AP 차이(°C)':r['low_sustained_eligible_mean_delta_ap_c'],
        '주평가 J 차이':r['low_sustained_eligible_mean_delta_energy_j']}
        for r in summary['baseline_summary']]
    diagnostic_display=[{'seed':r['seed'],'부하':r['family'],'문맥':r['context'],
        '전체 fallback':r['all_fallback_callbacks'],'탐색 실패':r['search_fallback_callbacks'],
        'overrun':r['overrun_fallback_callbacks'],'저장 계획 선택':r['retained_selected_callbacks'],
        '새 탐색 선택':r['search_selected_callbacks'],'내부 cap 초과':r['observed_cap_violation_requests'],
        '최종 J 잔액':r['final_budget_margin_j'],'최대 판단(ms)':r['decision_host_max_ms']}
        for r in diagnostic]
    pair_display=[{'seed':r['seed'],'부하':r['family'],'문맥':r['context'],
        '기준 규칙':LABELS[r['baseline']],'서비스 유지':r['service_preserved'],
        '공동 감소':r['joint_gain'],'AP 차이(°C)':r['delta_peak_ap_c'],'J 차이':r['delta_energy_j'],
        '긴급 P95 차이(ms)':r['delta_urgent_p95_ms'],'일반 평균 차이(ms)':r['delta_normal_mean_ms']}
        for r in pairs]
    for title,data in [('기준별 전체48조건 비교',baseline_display),('신규48조건 진단',diagnostic_display),('전체432쌍 비교',pair_display)]:
        columns=list(data[0])
        head=''.join('<th>'+html.escape(k)+'</th>' for k in columns)
        body=''.join('<tr>'+''.join('<td>'+html.escape('계산 불가' if r.get(k) is None else
            f'{r[k]:.6g}' if isinstance(r.get(k),float) else str(r.get(k)))+'</td>' for k in columns)+'</tr>' for r in data)
        tables.append('<h2>'+title+'</h2><div class="scroll"><table><thead><tr>'+head+'</tr></thead><tbody>'+body+'</tbody></table></div>')
    images=''.join('<figure><img src="pilot_figures/'+p.name+'"><figcaption>'+html.escape(p.stem)+'</figcaption></figure>'
                  for p in sorted((s.BUNDLE/'pilot_figures').glob('*.png')))
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>기한 예약·열 분산 pilot</title>
<style>body{font:16px system-ui,sans-serif;margin:28px;color:#22343c;background:#f5f7f8}h1{font-size:28px}h2{font-size:21px;margin-top:36px}.scroll{overflow:auto;background:white;border:1px solid #ccd5d9;max-height:500px}table{border-collapse:collapse;font-size:12px}td,th{padding:8px;white-space:nowrap;border-bottom:1px solid #ddd;text-align:right}th{position:sticky;top:0;background:#dce9ef}img{width:100%;max-width:1500px}figure{margin:30px 0}input{padding:10px;width:300px}</style>
<h1>기한 예약·열 분산 pilot</h1><p>48신규 환경 + 432재사용 = 480행 · 기존 공개 개발 자료 · 실측 기반 모형 결과</p>
<p><strong>3,168요청 전량 완료. 주평가24조건에서 강한 Triton 대응 대비 공동 개선24조건, Band/EFT 대비0조건.</strong></p>
<p>전체 일반 기한 실패는 신규53건, Band/EFT/강한 Triton 각각36건입니다. 전체 우위로 판정하지 않습니다. 완료량·기한·긴급P95를 먼저 비교합니다. AP는 표면온도가 아니며 작은 차이는 실제 개선 증거가 아닙니다. partial 비용과 계산 불가는 원본 CSV에서 구분합니다.</p>
<p><a href="PILOT_REPORT.md">한국어 보고서</a> · <a href="pilot_results.csv">전체480행</a> · <a href="pilot_pairs.csv">432쌍 비교</a> · <a href="pilot_diagnostics.csv">판단 진단</a></p>
<input id="filter" placeholder="표 검색: 정책·seed·부하·문맥">'''+''.join(tables)+images+'''
<script>document.querySelector('#filter').addEventListener('input',e=>{const q=e.target.value.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));});</script></html>'''
    (s.BUNDLE/'pilot_index.html').write_text(page,encoding='utf8')


def main():
    before=s.consumption();s.check();s.require_review();repair.register()
    completion=s.read(s.BUNDLE/'pilot_completion.json')
    assert completion['status']=='completed'
    inputs,jobs,reused,evidence=s.reference_rows()
    frozen,_=s.rule.P.inputs(s.rule.P.BUNDLE)
    items=[load(p) for p in sorted((s.LOCAL/'pilot_items').glob('*.gz'))]
    assert len(items)==48
    accounting_max=0.
    for item,(work,ctx) in zip(items,jobs):
        assert key(item['row'])==(work['seed'],work['family'],ctx)
        s.existing.audit(item['result'],work['tickets'])
        row,_=s.existing.metrics(item['result'],SimpleNamespace(),inputs['initial'],frozen)
        for field in ('planned','completed','deadline_met','urgent_service_failure','normal_service_failure','energy_j','peak_ap_c','urgent_p95_ms'):
            assert row[field]==item['row'][field],field
        segments=item['curves']['segments']
        independent=120*inputs['initial']['preload_power_w']+sum(
            max(0.,min(120.,v['end_s'])-v['start_s'])*
            (0. if v['state']=='idle' else frozen['energy_increment_w'][v['state']]) for v in segments)
        error=abs(independent-row['energy_j']);accounting_max=max(accounting_max,error)
        assert error<1e-8
    rows=reused+[x['row'] for x in items]
    with (s.BUNDLE/'pilot_results.csv').open(encoding='utf8',newline='') as f:
        saved=[{k:typed(v) for k,v in r.items()} for r in csv.DictReader(f)]
    assert len(saved)==480 and len({key(r)+(r['policy'],) for r in saved})==480
    for actual,stored in zip(rows,saved):
        for k,v in actual.items():assert stored[k]==v,(k,v,stored[k])
    pairs=comparisons(rows);ds=diagnostics(items)
    base_summary=[]
    for baseline in evidence['policies']:
        pp=[r for r in pairs if r['baseline']==baseline]
        valid=[r for r in pp if r['cost_eligible']]
        main=[r for r in pp if r['family'] in ('low','sustained')]
        main_valid=[r for r in main if r['cost_eligible']]
        base_summary.append(dict(baseline=baseline,conditions=len(pp),service_preserved=sum(r['service_preserved'] for r in pp),
            thermal_gain=sum(r['thermal_gain'] for r in pp),joint_gain=sum(r['joint_gain'] for r in pp),
            eligible_mean_delta_ap_c=mean([r['delta_peak_ap_c'] for r in valid]),
            eligible_mean_delta_energy_j=mean([r['delta_energy_j'] for r in valid]),
            low_sustained_service_preserved=sum(r['service_preserved'] for r in main),
            low_sustained_thermal_gain=sum(r['thermal_gain'] for r in main),
            low_sustained_joint_gain=sum(r['joint_gain'] for r in main),
            low_sustained_eligible_mean_delta_ap_c=mean([r['delta_peak_ap_c'] for r in main_valid]),
            low_sustained_eligible_mean_delta_energy_j=mean([r['delta_energy_j'] for r in main_valid])))
    policy_summary=[]
    for policy in [NEW]+evidence['policies']:
        rr=[r for r in rows if r['policy']==policy]
        policy_summary.append(dict(policy=policy,conditions=len(rr),planned=sum(r['planned'] for r in rr),
            completed=sum(r['completed'] for r in rr),incomplete=sum(r['incomplete'] for r in rr),
            deadline_met=sum(r['deadline_met'] for r in rr),
            urgent_service_failure=sum(r['urgent_service_failure'] for r in rr),
            normal_service_failure=sum(r['normal_service_failure'] for r in rr),
            full_conditions=sum(r['completed']==r['planned'] for r in rr)))
    summary=dict(version='reserved-thermal-pilot-analysis-v1',utc=s.utc(),
        new_conditions=48,reused_rows=432,logical_rows=480,baseline_summary=base_summary,policy_summary=policy_summary,
        consumption=s.consumption(),scope='existing development/ regression model pilot; no independent holdout',
        diagnostic_totals={k:sum(r[k] for r in ds) for k in
            ('search_fallback_callbacks','overrun_fallback_callbacks','all_fallback_callbacks',
             'scored_callbacks','decision_calls','retained_selected_callbacks','search_selected_callbacks',
             'reference_selected_callbacks','score_diverse_admitted_callbacks',
             'thermal_better_than_current_reference_callbacks','observed_cap_violation_requests','projections')},
        budget_satisfied_conditions=sum(r['final_budget_satisfied'] is True for r in ds),
        budget_violated_conditions=sum(r['final_budget_satisfied'] is False for r in ds),
        callback_host_total_s=sum(r['decision_host_total_s'] for r in ds),
        callback_host_max_ms=max(r['decision_host_max_ms'] for r in ds),
        cost_recalculation_max_error_j=accounting_max)
    s.existing.csv_write(s.BUNDLE/'pilot_pairs.csv',pairs)
    s.existing.csv_write(s.BUNDLE/'pilot_diagnostics.csv',ds)
    s.existing.csv_write(s.BUNDLE/'pilot_policy_summary.csv',policy_summary)
    s.write(s.BUNDLE/'pilot_summary.json',summary)
    reps,reference_hashes=representatives(items,inputs)
    figures(rows,pairs,reps,summary);dashboard(summary,pairs,ds)
    assert s.consumption()==before
    outputs=[p for pattern in ('pilot_*.csv','pilot_*.json','pilot_index.html','pilot_figures/*')
             for p in s.BUNDLE.glob(pattern) if p.is_file() and p.name!='pilot_verification.json']
    verification=dict(utc=s.utc(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,
        command='MKL_THREADING_LAYER=SEQUENTIAL; python -B -m tools.d1_reserved_thermal_pilot_analysis',
        source_hashes=s.source_hashes(),runtime_hashes=repair.runtime_hashes(),
        analysis_source_sha256=s.digest(__file__),review_sha256=s.digest(s.BUNDLE/'astra_review.json'),
        pilot_manifest_sha256=s.digest(s.BUNDLE/'pilot_manifest.json'),reuse_manifest_sha256=s.digest(s.BUNDLE/'reuse_manifest.json'),
        checks=dict(saved_items=48,unique_csv_rows=480,pair_rows=432,diagnostic_rows=48,
            original_4_items_preserved=True,new_rows_recalculated=48,lane_request_online_audits=48,
            independent_energy_max_error_j=accounting_max),
        reference_representative_files=reference_hashes,
        outputs={p.relative_to(s.BUNDLE).as_posix():s.digest(p) for p in outputs},consumption=before,
        analysis_environment_starts=0,training_episodes=0,device_commands=0)
    s.write(s.BUNDLE/'pilot_verification.json',verification)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
