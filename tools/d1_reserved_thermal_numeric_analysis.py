"""Offline paired analysis of the uniformly corrected 48-condition cohort."""
from __future__ import annotations
import html
import json
import statistics
import subprocess
from types import SimpleNamespace
from tools import d1_reserved_thermal_numeric_study as n
from tools import d1_reserved_thermal_pilot_analysis as a

s = n.s
NEW = n.r2.PUBLIC_POLICY
LABELS = dict(a.LABELS, EFT_REFERENCE='내부 EFT')
LABELS[NEW] = '기한 예약·열 분산 수정본'
BASES = ['BAND_HEFT_WHOLE_REQUEST_ADAPT_V1', 'SHARED_EFT', 'EFT_REFERENCE',
         'TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1']
EPS = s.rule.EPS


def pairs(rows):
    ours = {a.key(r): r for r in rows if r['policy']==NEW}
    result = []
    for b in rows:
        if b['policy']==NEW: continue
        r = ours[a.key(b)]
        full = r['completed']==r['planned'] and b['completed']==b['planned']
        service = full and r['urgent_service_failure']<=b['urgent_service_failure'] and \
            r['normal_service_failure']<=b['normal_service_failure'] and r['urgent_p95_ms']<=b['urgent_p95_ms']+EPS
        ap, j = a.delta(r['peak_ap_c'], b['peak_ap_c']), a.delta(r['energy_j'], b['energy_j'])
        eligible = service and ap is not None and j is not None
        result.append(dict(seed=r['seed'], family=r['family'], context=r['context'], baseline=b['policy'],
            service_preserved=service, cost_eligible=eligible, delta_peak_ap_c=ap, delta_energy_j=j,
            delta_urgent_p95_ms=a.delta(r['urgent_p95_ms'], b['urgent_p95_ms']),
            delta_normal_mean_ms=a.delta(r['normal_mean_ms'], b['normal_mean_ms']),
            delta_deadline_met=r['deadline_met']-b['deadline_met'], delta_completed=r['completed']-b['completed'],
            thermal_gain=eligible and ap < -EPS and j <= EPS,
            joint_gain=eligible and ap < -EPS and j < -EPS))
    assert len(result)==528
    return result


def diagnostics(item, row):
    records = item['records']; events = item['numeric_events']
    multiple_actions = multiple_request_backend = local_gain = local_j_gain = invalid = 0
    for record in records:
        admitted = [c for c in record['candidates'] if not c['reasons']]
        multiple_actions += len({tuple(c['effective_action']['signature']) for c in admitted}) > 1
        multiple_request_backend += len({(c['first_request_id'], c['first_backend']) for c in admitted}) > 1
        invalid += sum(c['effective_action']['kind']=='INVALID_BUSY_DISPATCH' for c in admitted)
        reference = record['candidates'][0]
        if not reference['reasons'] and reference['predicted_total_j'] is not None:
            local_gain += any(c['predicted_peak_ap_c'] < reference['predicted_peak_ap_c']-EPS
                and c['predicted_total_j'] <= reference['predicted_total_j']+EPS for c in admitted)
            local_j_gain += any(c['predicted_total_j'] < reference['predicted_total_j']-EPS
                and c['predicted_peak_ap_c'] <= reference['predicted_peak_ap_c']+EPS for c in admitted)
    corrections = [e for e in events if e['accepted'] and e['displacement_s'] > 0]
    rejected = [e for e in events if not e['accepted']]
    return dict(seed=row['seed'], family=row['family'], context=row['context'],
        scored_callbacks=len(records), decision_calls=len(item['result']['decisions']),
        multiple_effective_actions_callbacks=multiple_actions,
        multiple_first_request_backend_callbacks=multiple_request_backend,
        invalid_busy_admitted_actions=invalid, local_thermal_gain_callbacks=local_gain,
        local_joint_j_gain_callbacks=local_j_gain,
        corrected_placement_calls=len(corrections), rejected_placement_calls=len(rejected),
        max_accepted_shift_s=max((e['displacement_s'] for e in corrections), default=0),
        numeric_candidate_rejections=sum(any(reason.startswith('numeric_') for reason in c['reasons'])
            for record in records for c in record['candidates']),
        fallback_callbacks=sum(d['reason'] in ('reserved_no_admitted_calendar_EFT', 'reserved_observed_overrun_EFT')
            for d in item['result']['decisions']),
        observed_cap_violation_requests=row['observed_cap_violation_requests'],
        final_budget_satisfied=row['final_budget_satisfied'],
        decision_host_total_s=row['decision_host_total_s'], decision_host_max_ms=row['decision_host_max_ms'],
        projections=row['projections'])


def representatives(items, inputs):
    # Inherited pre-result selection, not a favorable-result search.
    reps = {(v['family'], v['policy']): v for v in s.read(s.BUNDLE/'pilot_representatives.json')}
    for item, (work, ctx) in zip(items, n.reuse()[1]):
        if work['seed']==610810001 and work['family'] in ('queue', 'sustained') and ctx=='mean':
            reps[(work['family'], NEW)] = dict(ledger=item['result']['ledger'], decisions=item['result']['decisions'],
                                            **item['curves'])
    hashes = {}
    for path in (s.existing.LOCAL/'comparison/items').glob('*.gz'):
        item = a.load(path); row = item['row']
        if row['policy']=='EFT_REFERENCE' and row['seed']==610810001 and row['family'] in ('queue', 'sustained') \
            and row['context']=='mean' and row['scope']=='resource' and row['environment']=='immediate_allow':
            reps[(row['family'], 'EFT_REFERENCE')] = item
            hashes[path.relative_to(s.ROOT).as_posix()] = s.digest(path)
    assert all((f, p) in reps for f in ('queue', 'sustained') for p in [NEW]+BASES)
    ledgers = [dict(family=f, policy=p, **r) for (f,p),v in reps.items() for r in v['ledger']]
    s.existing.csv_write(n.BUNDLE/'representative_ledger.csv', ledgers)
    s.write(n.BUNDLE/'representatives.json', [dict(v, family=f, policy=p) for (f,p),v in reps.items()])
    return reps, hashes


def figures(rows, comparisons, reps):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch
    plt.rcParams.update({'font.family':['Malgun Gothic','DejaVu Sans'], 'axes.unicode_minus':False, 'font.size':10})
    folder = n.BUNDLE/'figures'; folder.mkdir(exist_ok=True)
    def save(fig, name):
        fig.tight_layout(); fig.savefig(folder/(name+'.png'), dpi=150, bbox_inches='tight')
        fig.savefig(folder/(name+'.svg'), bbox_inches='tight'); plt.close(fig)
    policies = [NEW]+BASES+[s.rule.PUBLIC_POLICY]
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))
    for ax, field, title in zip(axes, ('incomplete', 'deadline', 'urgent_p95_ms'),
        ('전체 미완료 요청', '전체 기한 실패 요청', '조건별 긴급 응답P95 평균')):
        values = [sum(r['incomplete'] if field=='incomplete' else r['planned']-r['deadline_met']
            for r in rows if r['policy']==p) if field!='urgent_p95_ms' else
            statistics.mean(r[field] for r in rows if r['policy']==p) for p in policies]
        ax.barh([LABELS[p] for p in policies], values, color=['#276E91']+['#9AA8AF']*5)
        ax.invert_yaxis(); ax.set_title(title); ax.set_xlabel('ms (P95의 재계산 아님)' if field=='urgent_p95_ms' else '요청 수')
        for i,v in enumerate(values): ax.text(v, i, f' {v:.2f}' if field=='urgent_p95_ms' else f' {v}', va='center')
        ax.set_xlim(0, max(values)*1.18 if max(values)>0 else 1)
    save(fig, '01_전체완료와응답')
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.5))
    for ax,p in zip(axes,BASES):
        for eligible,color,marker,label in ((True,'#276E91','o','서비스 유지'), (False,'#B55E5E','x','서비스 손실')):
            pp = [r for r in comparisons if r['baseline']==p and r['cost_eligible']==eligible and r['delta_peak_ap_c'] is not None]
            ax.scatter([r['delta_energy_j'] for r in pp], [r['delta_peak_ap_c'] for r in pp], c=color, marker=marker, label=label)
        ax.axhline(0, color='#888', lw=.6); ax.axvline(0, color='#888', lw=.6)
        ax.set_title(LABELS[p]); ax.set_xlabel('수정본−기준 에너지(J)'); ax.set_ylabel('수정본−기준 AP 최고값(°C)')
        ax.legend(fontsize=8)
    save(fig, '02_동일조건_열에너지차이')
    fig, axes = plt.subplots(2, 5, figsize=(18, 6))
    for ri,f in enumerate(('queue','sustained')):
        for ci,p in enumerate([NEW]+BASES):
            ax = axes[ri,ci]
            for r in reps[(f,p)]['ledger']:
                if 'dispatch_ns' not in r: continue
                lo = r['dispatch_ns']/1e9; hi = r.get('lane_available_ns',120e9)/1e9
                lane = int(r['backend']=='GPU')
                ax.broken_barh([(lo,hi-lo)], (lane-.3,.6), facecolors='#276E91' if r['priority']=='urgent' else '#D39342')
            ax.set_yticks([0,1], ['CPU','GPU']); ax.set_xlim(35,120); ax.set_xlabel('시각(초)')
            ax.set_title(LABELS[p]+' · '+f, fontsize=9)
    fig.suptitle('사전 지정 seed610810001·mean / 실제 lane 반환까지 점유', y=.99)
    save(fig, '03_대표요청_실행시간표')
    fig,axes = plt.subplots(1,2,figsize=(13,4.5))
    for ax,f in zip(axes,('queue','sustained')):
        for p in [NEW]+BASES:
            v = reps[(f,p)]; ax.plot(v['ap_times_s'],v['ap_path'],label=LABELS[p])
        ax.set_title('사전 지정 '+f); ax.set_xlabel('시각(초)'); ax.set_ylabel('모형 AP(°C)'); ax.legend(fontsize=8)
    save(fig, '04_대표조건_AP경로')
    conditions = sorted({a.key(r) for r in comparisons})
    by = {(a.key(r),r['baseline']):r for r in comparisons}; matrix = []
    for cond in conditions:
        line=[]
        for p in BASES:
            r = by[(cond,p)]
            line.append(0 if not r['cost_eligible'] else 1 if r['thermal_gain'] else
                2 if r['delta_peak_ap_c'] < -EPS and r['delta_energy_j'] > EPS else 3)
        matrix.append(line)
    colors=['#BE6D6D','#328773','#DBAA55','#D9E0E4']
    fig,ax=plt.subplots(figsize=(9,13))
    ax.imshow(matrix,aspect='auto',cmap=ListedColormap(colors),vmin=0,vmax=3)
    ax.set_xticks(range(4),[LABELS[p] for p in BASES],rotation=15,ha='right')
    ax.set_yticks(range(48),[f'{seed-610810000:02d} / {f} / {ctx}' for seed,f,ctx in conditions],fontsize=8)
    ax.set_title('수정본 대비 기준별 전체48조건 / 수치 EPS는 모형 정확도 아님')
    ax.legend(handles=[Patch(color=c,label=l) for c,l in zip(colors,
        ['서비스/비용 부적격','AP 감소·J 비증가','AP 감소·J 증가','그 밖의 적격'])],loc='lower center',bbox_to_anchor=(.5,-.12),ncol=2)
    save(fig,'05_전체조건_결과지도')


def dashboard(summary, comparisons, ds):
    def table(title, rows):
        keys=list(rows[0]); result='<h2>'+html.escape(title)+'</h2><table><thead><tr>'
        result+=''.join('<th>'+html.escape(k)+'</th>' for k in keys)+'</tr></thead><tbody>'
        for r in rows:
            result+='<tr>'+''.join('<td>'+html.escape(f'{r[k]:.6g}' if isinstance(r[k],float) else str(r[k]))+'</td>' for k in keys)+'</tr>'
        return result+'</tbody></table>'
    rules=[{'규칙':LABELS[p], '제어':control, '판단 차이':behavior} for p,control,behavior in
        [(NEW,'배정·순서·대기','기존 완료 cap·signed J를 유지, AP 우선, 이동량≤1ns'),
         ('EFT_REFERENCE','배정·대기','현재 큐의 예측 응답 최소; 곧 비는 CPU도 고려'),
         ('SHARED_EFT','배정','공개 원 adapter의 예상 완료 기준'),
         (BASES[0],'요청 단위 제한적 배정','Band subgraph 배정을 전체 요청으로 대응'),
         (BASES[3],'허가·고정 자원','Triton rate-limit 논리를 요청 단위로 대응')]]
    tables=table('실행한 판단 규칙과 비교 범위',rules)
    tables+=table('기준별 전체/주평가 집계',summary['baseline_summary'])
    tables+=table('수정본48조건 실행 진단',ds)+table('전체528개 짝비교',comparisons)
    images=''.join('<figure><img src="figures/'+html.escape(p.name)+'"><figcaption>'+html.escape(p.stem)+'</figcaption></figure>'
        for p in sorted((n.BUNDLE/'figures').glob('*.png')))
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>D1Check 수치 보완 비교</title>
<style>body{font:15px system-ui;margin:28px;color:#19313e}h1{font-size:26px}table{border-collapse:collapse;font-size:12px;margin:20px 0;display:block;overflow:auto}td,th{border:1px solid #ccd5da;padding:7px;white-space:nowrap}th{background:#e9f0f4}img{max-width:100%;height:auto}figure{margin:28px 0}input{padding:10px;width:320px}p{max-width:1050px;line-height:1.7}</style>
<h1>기한 예약·열 분산 규칙: 수치 수정과 동일 조건 비교</h1>
<p>48개 개발 조건 × 12정책 = 576행. 원48행을 보존하고 수정본48행을 추가했다. 실측 계수와 처리문맥 전이 가정에 기반한 A24 모형 비교이며 실제 제품·기기 전체의 우월성 검증이 아니다. AP는 표면 온도가 아니다. 미완료는 비용 이득으로 해석하지 않는다.</p>
<p><a href="REPORT.md">최종 보고서</a> · <a href="results.csv">전체 결과 CSV</a> · <a href="pairs.csv">짝비교</a> · <a href="diagnostics.csv">선택·수치 진단</a></p>
<label>표 검색 <input id="filter" placeholder="Band, EFT, sustained 등"></label>'''
    page+=tables+images+'''<script>document.getElementById('filter').addEventListener('input',e=>{let q=e.target.value.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))})</script></html>'''
    (n.BUNDLE/'index.html').write_text(page,encoding='utf8')


def main():
    before=s.consumption(); registration=n.register(); inputs,jobs,_,_=n.reuse()
    rows=n.csv_read(n.BUNDLE/'results.csv'); completion=s.read(n.BUNDLE/'completion.json')
    assert completion['status']=='completed' and len(rows)==576
    assert len({a.key(r)+(r['policy'],) for r in rows})==576
    items=[a.load(p) for p in sorted((n.LOCAL/'pilot_items').glob('*.gz'))]; assert len(items)==48
    frozen,_=s.rule.P.inputs(s.rule.P.BUNDLE); ds=[]; accounting_max=0
    for item,(work,ctx) in zip(items,jobs):
        name=f"numeric_r2/pilot/{work['seed']}/{work['family']}/{ctx}"
        assert item['identity']==name
        r=next(r for r in rows if r['policy']==NEW and a.key(r)==(work['seed'],work['family'],ctx))
        s.existing.audit(item['result'],work['tickets'])
        calc,_=s.existing.metrics(item['result'],SimpleNamespace(),inputs['initial'],frozen)
        for field in ('planned','completed','deadline_met','urgent_service_failure','normal_service_failure','energy_j','peak_ap_c','urgent_p95_ms'):
            assert calc[field]==r[field],field
        independent=120*inputs['initial']['preload_power_w']+sum(max(0,min(120,v['end_s'])-v['start_s'])*
            (0 if v['state']=='idle' else frozen['energy_increment_w'][v['state']]) for v in item['curves']['segments'])
        accounting_max=max(accounting_max,abs(independent-r['energy_j']))
        assert abs(independent-r['energy_j']) < 1e-8
        d=diagnostics(item,r); assert d['max_accepted_shift_s']<=EPS and d['invalid_busy_admitted_actions']==0
        ds.append(d)
    pp=pairs(rows); baselines=[]
    for p in dict.fromkeys(r['baseline'] for r in pp):
        rr=[r for r in pp if r['baseline']==p]; main=[r for r in rr if r['family'] in ('low','sustained')]
        baselines.append(dict(baseline=p,service_preserved=sum(r['service_preserved'] for r in rr),
            thermal_gain=sum(r['thermal_gain'] for r in rr),joint_gain=sum(r['joint_gain'] for r in rr),
            main_service_preserved=sum(r['service_preserved'] for r in main),
            main_thermal_gain=sum(r['thermal_gain'] for r in main),main_joint_gain=sum(r['joint_gain'] for r in main),
            main_mean_delta_ap_c=a.mean([r['delta_peak_ap_c'] for r in main]),
            main_mean_delta_j=a.mean([r['delta_energy_j'] for r in main])))
    policy_summary=[dict(policy=p,conditions=len(rr),planned=sum(r['planned'] for r in rr),
        completed=sum(r['completed'] for r in rr),incomplete=sum(r['incomplete'] for r in rr),
        deadline_met=sum(r['deadline_met'] for r in rr),
        urgent_service_failure=sum(r['urgent_service_failure'] for r in rr),
        normal_service_failure=sum(r['normal_service_failure'] for r in rr))
        for p in dict.fromkeys(r['policy'] for r in rows) for rr in [[r for r in rows if r['policy']==p]]]
    totals={k:sum(r[k] for r in ds) for k in ('scored_callbacks','decision_calls',
        'multiple_effective_actions_callbacks','multiple_first_request_backend_callbacks','invalid_busy_admitted_actions',
        'local_thermal_gain_callbacks','local_joint_j_gain_callbacks','corrected_placement_calls',
        'rejected_placement_calls','numeric_candidate_rejections','fallback_callbacks','observed_cap_violation_requests','projections')}
    summary=dict(version='numeric-r2-analysis-v1',utc=s.utc(),conditions=48,logical_rows=576,
        baseline_summary=baselines,policy_summary=policy_summary,diagnostic_totals=totals,
        max_accepted_shift_s=max(r['max_accepted_shift_s'] for r in ds),
        callback_host_total_s=sum(r['decision_host_total_s'] for r in ds),
        callback_host_max_ms=max(r['decision_host_max_ms'] for r in ds),
        budget_satisfied_conditions=sum(r['final_budget_satisfied'] is True for r in ds),
        budget_violated_conditions=sum(r['final_budget_satisfied'] is False for r in ds),
        independent_energy_max_error_j=accounting_max,consumption=before,
        training_episodes=0,device_commands=0,strict_supported=False,experiment_ready=False)
    s.existing.csv_write(n.BUNDLE/'pairs.csv',pp);s.existing.csv_write(n.BUNDLE/'diagnostics.csv',ds)
    s.existing.csv_write(n.BUNDLE/'policy_summary.csv',policy_summary);s.write(n.BUNDLE/'summary.json',summary)
    reps,hashes=representatives(items,inputs);figures(rows,pp,reps);dashboard(summary,pp,ds)
    assert before==s.consumption()
    outputs={p.relative_to(n.BUNDLE).as_posix():s.digest(p) for p in n.BUNDLE.rglob('*') if p.is_file()
             and p.name not in ('verification.json','browser_verification.json','REPORT.md','final_review.json')}
    s.write(n.BUNDLE/'verification.json',dict(utc=s.utc(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        dirty=True,command='MKL_THREADING_LAYER=SEQUENTIAL; python -B -m tools.d1_reserved_thermal_numeric_analysis',
        checks=dict(rows=576,pairs=528,unique_rows=576,audited_conditions=48,
            numerical_shift_bounded=True,no_busy_lane_dispatch=True,independent_energy_max_error_j=accounting_max),
        outputs=outputs,reference_representative_hashes=hashes,runtime_hashes=n.sources(),
        analysis_source_sha256=s.digest(__file__),consumption=before,added_environment_starts=0))
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
