"""Full-denominator final rule-only comparison; no plant executions or tuning."""
from __future__ import annotations
import html
import json
import statistics
import subprocess
from types import SimpleNamespace
from tools import d1_reserved_thermal_final_study as f
from tools import d1_reserved_thermal_numeric_analysis as a

s,n=f.s,f.n
NEW=n.r2.PUBLIC_POLICY
BASES=a.BASES
LABELS=a.LABELS
EPS=s.rule.EPS


def comparison(rows):
    by={a.a.key(r):r for r in rows if r['policy']==NEW};out=[]
    for b in rows:
        if b['policy']==NEW:continue
        r=by[a.a.key(b)]
        full=r['completed']==r['planned'] and b['completed']==b['planned']
        service=full and r['urgent_service_failure']<=b['urgent_service_failure'] and \
            r['normal_service_failure']<=b['normal_service_failure'] and r['urgent_p95_ms']<=b['urgent_p95_ms']+EPS
        ap=a.a.delta(r['peak_ap_c'],b['peak_ap_c']);j=a.a.delta(r['energy_j'],b['energy_j'])
        eligible=service and ap is not None and j is not None
        out.append(dict(seed=r['seed'],family=r['family'],context=r['context'],baseline=b['policy'],
            service_preserved=service,cost_eligible=eligible,delta_peak_ap_c=ap,delta_energy_j=j,
            delta_urgent_p95_ms=r['urgent_p95_ms']-b['urgent_p95_ms'],
            delta_normal_mean_ms=a.a.delta(r['normal_mean_ms'],b['normal_mean_ms']),
            delta_deadline_met=r['deadline_met']-b['deadline_met'],delta_completed=r['completed']-b['completed'],
            thermal_gain=eligible and ap < -EPS and j <= EPS,joint_gain=eligible and ap < -EPS and j < -EPS))
    assert len(out)==1920
    return out


def figure_outputs(rows,pp,reps):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch
    plt.rcParams.update({'font.family':['Malgun Gothic','DejaVu Sans'],'axes.unicode_minus':False,'font.size':10})
    folder=f.BUNDLE/'figures';folder.mkdir(exist_ok=True)
    def save(fig,name):
        fig.tight_layout();fig.savefig(folder/(name+'.png'),dpi=150,bbox_inches='tight')
        fig.savefig(folder/(name+'.svg'),bbox_inches='tight');plt.close(fig)
    policies=f.POLICIES
    fig,axes=plt.subplots(2,2,figsize=(15,11))
    for ax,field,title in zip(axes.ravel(),('incomplete','deadline','urgent_p95_ms','normal_mean_ms'),
        ('전체192조건 미완료','전체192조건 기한 실패','조건별 긴급 응답P95 평균','조건별 일반 완료시간 평균')):
        timing=field in ('urgent_p95_ms','normal_mean_ms')
        values=[sum(r['incomplete'] if field=='incomplete' else r['planned']-r['deadline_met']
            for r in rows if r['policy']==p) if not timing else
            statistics.mean(r[field] for r in rows if r['policy']==p) for p in policies]
        ax.barh([LABELS[p] for p in policies],values,color=['#276E91' if p==NEW else '#9AA8AF' for p in policies])
        ax.invert_yaxis();ax.set_title(title);ax.set_xlabel('ms / 완료 응답의 조건별 요약 평균' if timing else '요청 수')
        ax.set_xlim(0,max(values)*1.2 if max(values)>0 else 1)
        for i,v in enumerate(values):ax.text(v,i,f' {v:.2f}' if timing else f' {v}',va='center',fontsize=8)
    save(fig,'01_전체요청_완료와응답')
    fig,axes=plt.subplots(1,4,figsize=(17,4.7))
    for ax,p in zip(axes,BASES):
        for eligible,color,marker,label in ((True,'#276E91','o','서비스 유지'),(False,'#B55E5E','x','서비스 손실')):
            rr=[r for r in pp if r['baseline']==p and r['cost_eligible']==eligible and r['delta_peak_ap_c'] is not None]
            ax.scatter([r['delta_energy_j'] for r in rr],[r['delta_peak_ap_c'] for r in rr],c=color,marker=marker,label=label,s=16)
        ax.axhline(0,color='#888',lw=.6);ax.axvline(0,color='#888',lw=.6)
        ax.set_title(LABELS[p]);ax.set_xlabel('수정규칙−기준 J');ax.set_ylabel('수정규칙−기준 AP 최고값(°C)');ax.legend(fontsize=8)
    save(fig,'02_기준별_열에너지차이')
    fig,axes=plt.subplots(2,5,figsize=(18,6))
    for ri,family in enumerate(('queue','sustained')):
        for ci,p in enumerate([NEW]+BASES):
            ax=axes[ri,ci]
            for r in reps[(family,p)]['result']['ledger']:
                if 'dispatch_ns' not in r:continue
                lo=r['dispatch_ns']/1e9;hi=r.get('lane_available_ns',120e9)/1e9
                ax.broken_barh([(lo,hi-lo)],(int(r['backend']=='GPU')-.3,.6),
                    facecolors='#276E91' if r['priority']=='urgent' else '#D39342')
            ax.set_yticks([0,1],['CPU','GPU']);ax.set_xlim(35,120);ax.set_xlabel('시각(초)')
            ax.set_title(LABELS[p]+' · '+family,fontsize=9)
    fig.suptitle('사전 지정 seed610880001·mean / 실제 lane 반환까지 점유',y=.99)
    save(fig,'03_대표요청_실행시간표')
    fig,axes=plt.subplots(1,2,figsize=(13,4.5))
    for ax,family in zip(axes,('queue','sustained')):
        for p in [NEW]+BASES:
            v=reps[(family,p)]['curves'];ax.plot(v['ap_times_s'],v['ap_path'],label=LABELS[p])
        ax.set_title('사전 지정 '+family);ax.set_xlabel('시각(초)');ax.set_ylabel('모형 AP(°C)');ax.legend(fontsize=8)
    save(fig,'04_대표조건_AP경로')
    colors=['#BE6D6D','#328773','#DBAA55','#D9E0E4'];by={(a.a.key(r),r['baseline']):r for r in pp}
    fig,axes=plt.subplots(1,4,figsize=(17,13))
    for ax,family in zip(axes,('low','queue','burst','sustained')):
        conditions=sorted({a.a.key(r) for r in pp if r['family']==family});matrix=[]
        for cond in conditions:
            line=[]
            for p in BASES:
                r=by[(cond,p)];line.append(0 if not r['cost_eligible'] else 1 if r['thermal_gain'] else
                    2 if r['delta_peak_ap_c'] < -EPS and r['delta_energy_j'] > EPS else 3)
            matrix.append(line)
        ax.imshow(matrix,aspect='auto',cmap=ListedColormap(colors),vmin=0,vmax=3)
        ax.set_xticks(range(4),[LABELS[p] for p in BASES],rotation=55,ha='right',fontsize=8)
        ax.set_yticks(range(48),[f'{seed-610880000:02d}/{ctx.replace("_context","")}' for seed,_,ctx in conditions],fontsize=7)
        ax.set_title(family)
    fig.suptitle('새192조건 전수 지도 / AP 감소·J 비증가를 서비스 통과 뒤 판정',y=.999)
    fig.legend(handles=[Patch(color=c,label=l) for c,l in zip(colors,
        ['서비스/비용 부적격','AP 감소·J 비증가','AP 감소·J 증가','그 밖의 적격'])],
        loc='lower center',bbox_to_anchor=(.5,-.025),ncol=4)
    save(fig,'05_전체192조건_결과지도')


def dashboard(summary,pp,ds):
    def table(title,rows):
        keys=list(rows[0]);out='<h2>'+html.escape(title)+'</h2><table><thead><tr>'
        out+=''.join('<th>'+html.escape(k)+'</th>' for k in keys)+'</tr></thead><tbody>'
        out+=''.join('<tr>'+''.join('<td>'+html.escape(f'{r[k]:.6g}' if isinstance(r[k],float) else str(r[k]))+'</td>' for k in keys)+'</tr>' for r in rows)
        return out+'</tbody></table>'
    rules=[{'규칙':LABELS[p],'제어':control,'실제 판단':text} for p,control,text in
        [(NEW,'배정·순서·대기','완료예약·누적J·AP 우선; 위반 시 내부EFT 복귀'),
         ('EFT_REFERENCE','배정·대기','곧 비는 자원을 고려한 예측 응답 최소'),
         ('SHARED_EFT','배정','공개 원 adapter의 예상 완료 기준'),
         (BASES[0],'요청 배정','Band HEFT의 전체 요청 단위 제한적 대응'),
         (BASES[3],'자원 허가·고정배정','Triton rate-limit을 전체 요청으로 대응')]]
    tables=table('가져온 규칙과 우리 규칙의 판단 차이',rules)
    scorecard=[{'정책':LABELS[r['policy']], '코드':r['policy'], '예정 요청':r['planned'],
        '완료 요청':r['completed'], '미완료':r['incomplete'], '긴급 기한 실패':r['urgent_service_failure'],
        '일반 기한 실패':r['normal_service_failure'], '주96 전량 기한통과 조건':r['main_all_deadlines_conditions'],
        '일반 기한위반율(%)':r['normal_failure_rate_pct'], '일반 완료시간 요약평균(ms)':r['mean_condition_normal_ms'],
        '주96 AP 유효조건':r['main_ap_available_conditions'],
        '주96 평균 J(부분작업 포함)':r['main_mean_j'], '주96 유효 AP 최고값 평균(°C)':r['main_mean_peak_ap_c']}
        for r in summary['policy_summary']]
    paired=[{'기준':LABELS[r['baseline']], '전체 서비스 유지/192':r['service_preserved'],
        '전체 공동 감소/192':r['joint_gain'], '주96 서비스 유지':r['main_service_preserved'],
        '주96 공동 감소':r['main_joint_gain'], '주96 비용 적격조건':r['main_cost_eligible'],
        '적격조건 AP 차이(°C)':r['main_eligible_mean_delta_ap_c'],
        '적격조건 J 차이':r['main_eligible_mean_delta_j']} for r in summary['baseline_summary']]
    tables+=table('전체192조건 정책 성적표',scorecard)
    tables+=table('기준별 전체/주평가96조건 집계',paired)
    tables+=table('수정규칙192조건 진단',ds)+table('전체1,920개 짝비교',pp)
    images=''.join('<figure><img src="figures/'+html.escape(p.name)+'"><figcaption>'+html.escape(p.stem)+'</figcaption></figure>'
        for p in sorted((f.BUNDLE/'figures').glob('*.png')))
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>D1Check 최종 모형 비교</title>
<style>body{font:15px system-ui;color:#19313e;margin:28px}p{max-width:1100px;line-height:1.7}table{display:block;overflow:auto;border-collapse:collapse;font-size:12px;margin:22px 0}td,th{border:1px solid #ccd5da;padding:7px;white-space:nowrap}th{background:#e9f0f4}img{max-width:100%;height:auto}figure{margin:28px 0}input{padding:10px;width:320px}</style>
<h1>온디바이스 AI 자원 스케줄링: 최종 모형 비교</h1>
<p>새 합성192조건 × 11정책 = 2,112행. low/sustained96은 주평가, queue/burst96은 과부하 진단이다. 완료 요구와 기한·긴급 응답을 먼저 확인한다. AP는 표면 온도가 아니며 이 비교는 실측 계수·처리문맥 전이 가정의 A24 모형에 한정된다. 작은 차이는 기기 개선이나 실제 제품 우월성을 입증하지 않는다. RL 본학습0.</p>
<p>미완료 정책의 J 평균에는 부분작업이 포함되어 절감 성과로 해석할 수 없다. AP는 전량 완료 조건에서만 유효하며 그 조건 수를 표시한다. 기준별 비용 차이 평균은 서비스·완료를 모두 통과한 동일 조건 쌍에서만 계산한다.</p>
<p><a href="REPORT.md">최종 보고서</a> · <a href="results.csv">전체 CSV</a> · <a href="pairs.csv">짝비교 CSV</a> · <a href="diagnostics.csv">진단 CSV</a> · <a href="../numeric_r2/index.html">48조건 수정 검증</a></p>
<label>표 검색 <input id="filter" placeholder="Band, EFT, sustained 등"></label>'''
    page+=tables+images+'''<script>document.getElementById('filter').addEventListener('input',e=>{let q=e.target.value.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))})</script></html>'''
    (f.BUNDLE/'index.html').write_text(page,encoding='utf8')


def main():
    before=s.consumption();reg=f.prepare();completion=s.read(f.BUNDLE/'completion.json');assert completion['status']=='completed'
    assert s.digest(a.a.__file__)==s.read(s.BUNDLE/'pilot_verification.json')['analysis_source_sha256']
    assert s.digest(a.__file__)==s.read(n.BUNDLE/'verification.json')['analysis_source_sha256']
    rows=n.csv_read(f.BUNDLE/'results.csv');assert len(rows)==2112 and len({a.a.key(r)+(r['policy'],) for r in rows})==2112
    inputs=s.read(f.LOCAL/'inputs.json');tickets={(w['seed'],w['family']):w['tickets'] for w in inputs['workloads']}
    frozen,_=s.rule.P.inputs(s.rule.P.BUNDLE);ds=[];reps={};maxerror=0.;items_hashes={}
    journal=[json.loads(line) for line in (s.LOCAL/'executions.jsonl').read_text(encoding='utf8').splitlines()]
    receipts={e['name']:e for e in journal if e['event']=='completed' and e.get('kind')=='evaluation'}
    for path in sorted((f.LOCAL/'items').glob('*.gz')):
        item=a.a.load(path);r=item['row']
        assert item['binding']==completion['binding']
        assert item['identity']==f"final_rule/{r['seed']}/{r['family']}/{r['context']}/{r['policy']}"
        assert receipts[item['identity']]['item_sha256']==s.digest(path)
        s.existing.audit(item['result'],tickets[(r['seed'],r['family'])])
        calc,_=s.existing.metrics(item['result'],SimpleNamespace(),inputs['initial'],frozen)
        for field in ('planned','completed','deadline_met','urgent_p95_ms','energy_j','peak_ap_c','normal_service_failure'):
            assert r[field]==calc[field],field
        independent=120*inputs['initial']['preload_power_w']+sum(max(0,min(120,v['end_s'])-v['start_s'])*
            (0 if v['state']=='idle' else frozen['energy_increment_w'][v['state']]) for v in item['curves']['segments'])
        maxerror=max(maxerror,abs(independent-r['energy_j']));assert abs(independent-r['energy_j'])<1e-8
        if r['policy']==NEW:
            d=a.diagnostics(item,r);assert d['max_accepted_shift_s']<=EPS and d['invalid_busy_admitted_actions']==0;ds.append(d)
        if r['seed']==reg['representative']['seed'] and r['family'] in reg['representative']['families'] \
            and r['context']=='mean' and r['policy'] in [NEW]+BASES:
            reps[(r['family'],r['policy'])]=item
        items_hashes[path.name]=s.digest(path)
    assert len(items_hashes)==2112 and len(ds)==192 and len(reps)==10
    pp=comparison(rows);baselines=[]
    for p in f.POLICIES[:-1]:
        rr=[r for r in pp if r['baseline']==p];main=[r for r in rr if r['family'] in ('low','sustained')]
        baselines.append(dict(baseline=p,conditions=192,service_preserved=sum(r['service_preserved'] for r in rr),
            thermal_gain=sum(r['thermal_gain'] for r in rr),joint_gain=sum(r['joint_gain'] for r in rr),
            main_conditions=96,main_service_preserved=sum(r['service_preserved'] for r in main),
            main_thermal_gain=sum(r['thermal_gain'] for r in main),main_joint_gain=sum(r['joint_gain'] for r in main),
            main_cost_eligible=sum(r['cost_eligible'] for r in main),
            main_eligible_mean_delta_ap_c=a.a.mean([r['delta_peak_ap_c'] for r in main if r['cost_eligible']]),
            main_eligible_mean_delta_j=a.a.mean([r['delta_energy_j'] for r in main if r['cost_eligible']]),
            main_mean_delta_ap_c=a.a.mean([r['delta_peak_ap_c'] for r in main]),
            main_mean_delta_j=a.a.mean([r['delta_energy_j'] for r in main])))
    policy_summary=[]
    for p in f.POLICIES:
        rr=[r for r in rows if r['policy']==p]
        policy_summary.append(dict(policy=p,conditions=192,planned=sum(r['planned'] for r in rr),completed=sum(r['completed'] for r in rr),
            incomplete=sum(r['incomplete'] for r in rr),deadline_met=sum(r['deadline_met'] for r in rr),
            urgent_service_failure=sum(r['urgent_service_failure'] for r in rr),normal_service_failure=sum(r['normal_service_failure'] for r in rr),
            normal_n=sum(r['normal_n'] for r in rr),urgent_n=sum(r['urgent_n'] for r in rr),
            normal_failure_rate_pct=100*sum(r['normal_service_failure'] for r in rr)/sum(r['normal_n'] for r in rr),
            mean_condition_normal_ms=a.a.mean([r['normal_mean_ms'] for r in rr]),
            main_all_deadlines_conditions=sum(r['planned']==r['deadline_met'] for r in rr if r['family'] in ('low','sustained')),
            main_ap_available_conditions=sum(r['peak_ap_c'] is not None for r in rr if r['family'] in ('low','sustained')),
            main_mean_j=a.a.mean([r['energy_j'] for r in rr if r['family'] in ('low','sustained')]),
            main_mean_peak_ap_c=a.a.mean([r['peak_ap_c'] for r in rr if r['family'] in ('low','sustained')]),
            mean_overlap_s=a.a.mean([r['overlap_s'] for r in rr]),mean_cpu_occupied_s=a.a.mean([r['cpu_occupied_s'] for r in rr]),
            mean_gpu_occupied_s=a.a.mean([r['gpu_occupied_s'] for r in rr])))
    totals={k:sum(r[k] for r in ds) for k in ('scored_callbacks','decision_calls','multiple_effective_actions_callbacks',
        'multiple_first_request_backend_callbacks','numeric_candidate_rejections','corrected_placement_calls',
        'rejected_placement_calls','fallback_callbacks','observed_cap_violation_requests','projections')}
    summary=dict(version='final-rule-only-analysis-v1',utc=s.utc(),conditions=192,policies=11,logical_rows=2112,
        policy_summary=policy_summary,baseline_summary=baselines,diagnostic_totals=totals,
        max_accepted_shift_s=max(r['max_accepted_shift_s'] for r in ds),
        budget_satisfied_conditions=sum(r['final_budget_satisfied'] is True for r in ds),
        budget_violated_conditions=sum(r['final_budget_satisfied'] is False for r in ds),
        callback_host_total_s=sum(r['decision_host_total_s'] for r in ds),callback_host_max_ms=max(r['decision_host_max_ms'] for r in ds),
        independent_energy_max_error_j=maxerror,consumption=before,training_episodes=0,device_commands=0,
        strict_supported=False,experiment_ready=False,scope='fresh synthetic seed test; model context transfer, not device validation')
    s.existing.csv_write(f.BUNDLE/'pairs.csv',pp);s.existing.csv_write(f.BUNDLE/'diagnostics.csv',ds)
    s.existing.csv_write(f.BUNDLE/'policy_summary.csv',policy_summary);s.write(f.BUNDLE/'summary.json',summary)
    s.existing.csv_write(f.BUNDLE/'representative_ledger.csv',[dict(family=family,policy=p,**r)
        for (family,p),item in reps.items() for r in item['result']['ledger']])
    s.write(f.BUNDLE/'representatives.json',[dict(family=family,policy=p,row=item['row'],ledger=item['result']['ledger'],
        decisions=item['result']['decisions'],curves=item['curves']) for (family,p),item in reps.items()])
    figure_outputs(rows,pp,reps);dashboard(summary,pp,ds);assert before==s.consumption()
    s.write(f.BUNDLE/'verification.json',dict(utc=s.utc(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,
        command='MKL_THREADING_LAYER=SEQUENTIAL; python -B -m tools.d1_reserved_thermal_final_analysis',
        source_hashes=f.sources(),analysis_source_sha256=s.digest(__file__),
        analysis_dependency_hashes={p:s.digest(s.ROOT/p) for p in
            ('tools/d1_reserved_thermal_numeric_analysis.py','tools/d1_reserved_thermal_pilot_analysis.py')},
        checks=dict(rows=2112,unique_rows=2112,conditions=192,audited_items=2112,pairs=1920,
            numeric_shift_bounded=True,no_busy_lane_dispatch=True,independent_energy_max_error_j=maxerror),
        local_item_hashes=items_hashes,outputs={p.relative_to(f.BUNDLE).as_posix():s.digest(p) for p in f.BUNDLE.rglob('*')
            if p.is_file() and p.name not in ('verification.json','browser_verification.json','REPORT.md','final_review.json')},
        consumption=before,added_environment_starts=0))
    print(json.dumps(dict(rows=2112,diagnostic_totals=totals,consumption=before),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
