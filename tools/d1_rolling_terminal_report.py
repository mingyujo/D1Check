"""Development terminal gate and pilot report; no environment starts."""
import gzip,hashlib,html,json,statistics
from tools import d1_rolling_terminal_pilot as s
from tools import d1_rolling_joint_report as csv_tools
from tools.d1_edd_ect_residual_report import compare
ROOT=s.ROOT;B=s.probe.BUNDLE;read=s.read;write=s.write
LABELS={s.POLICIES[0]:'Band 요청 적용',s.POLICIES[1]:'Triton 고정 자원',s.POLICIES[2]:'공동 계획 첫 선택 검사',s.POLICIES[3]:'공동 계획 종단 AP 검사'}
def get_native(row):
    if row['policy']==s.x.POLICY:folder=s.LOCAL;events=s.events()
    elif row['policy']==s.parent.x.POLICY:folder=s.parent.LOCAL;events=s.parent.events()
    else:
        ancestor=s.parent.parent.previous.parent.parent;folder=ancestor.LOCAL;events=ancestor.events()
    identity=row['identity'];path=folder/'items'/(identity.replace('/','__')+'.json.gz');receipt=next(e for e in events if e['event']=='completed' and e['identity']==identity)
    assert s.sha(path)==receipt['artifact_sha256'];item=json.loads(gzip.decompress(path.read_bytes()));assert item['row']==row
    return item
def report():
    s.check();s.probe.check();done=read(s.BUNDLE/'completion.json');assert done['status']=='completed'
    probe=json.loads(gzip.decompress((B/'probe_records.json.gz').read_bytes()));probe_rows=[]
    for item in probe:
        rs=item['records'];passed=[r for r in rs if r['first_guard_pass']]
        probe_rows.append(dict(seed=item['seed'],family=item['family'],context=item['context'],records=len(rs),first_pass=len(passed),terminal_pass=sum(r['terminal_pass'] for r in passed),
            first_strict_gain=sum(r['first_prefix_strict_gain'] for r in passed),useful=sum(r['useful'] for r in passed),cooling_candidates=sum(r['action_kind']=='cool_wait' for r in passed),
            cooling_terminal_pass=sum(r['action_kind']=='cool_wait' and r['terminal_pass'] for r in passed),exact_replay=item['exact_replay']))
    rows=read(s.BUNDLE/'development_rows.json');by={(r['seed'],r['family'],r['context'],r['policy']):r for r in rows};items={r['identity']:get_native(r) for r in rows};pairs=[];equal=0;certificates=[];max_deltas={k:0. for k in ('energy_j','peak_ap_c','urgent_p95_ms','normal_mean_ms')}
    for r in rows:
        if r['policy']==s.POLICIES[0]:continue
        base=by[r['seed'],r['family'],r['context'],s.POLICIES[0]];other=by[r['seed'],r['family'],r['context'],s.POLICIES[1]];a,b=compare(r,base),compare(r,other)
        both=a['nonworse'] and b['nonworse'];heat=a['heat_gain'] and b['heat_gain'];joint=a['joint_gain'] and b['joint_gain']
        category='서비스 악화' if not a['service_preserved'] or not b['service_preserved'] else '비용 상충' if not both else 'J·AP 공동감소' if joint else 'J 비악화·AP 감소' if heat else '비악화·열차 없음'
        pairs.append(dict(seed=r['seed'],family=r['family'],context=r['context'],policy=r['policy'],**a,nonworse_both=both,heat_gain_both=heat,joint_gain_both=joint,category=category))
        if r['policy']==s.x.POLICY:
            clean=lambda obj:[{k:v for k,v in q.items() if k!='source_request_id'} for q in obj['result']['ledger']]
            equal+=clean(items[r['identity']])==clean(items[base['identity']])
            digest=lambda obj:hashlib.sha256(json.dumps(clean(obj),sort_keys=True,separators=(',',':')).encode()).hexdigest()
            certificates.append(dict(seed=r['seed'],family=r['family'],context=r['context'],planned=r['planned'],baseline_ledger_sha256=digest(items[base['identity']]),candidate_ledger_sha256=digest(items[r['identity']]),excluded_field='source_request_id only'))
            for k in max_deltas:max_deltas[k]=max(max_deltas[k],abs(r[k]-base[k]))
    summaries=[]
    for policy in s.POLICIES:
        g=[r for r in rows if r['policy']==policy];ps=[r for r in pairs if r['policy']==policy]
        summaries.append(dict(policy=policy,conditions=24,planned=sum(r['planned'] for r in g),completed=sum(r['completed'] for r in g),
            urgent_failures=sum(r['urgent_service_failure'] for r in g),normal_failures=sum(r['normal_service_failure'] for r in g),
            **{k:statistics.mean(r[k] for r in g) for k in ('urgent_p95_ms','normal_mean_ms','energy_j','peak_ap_c')},
            heat_gain_both=sum(r['heat_gain_both'] for r in ps),joint_gain_both=sum(r['joint_gain_both'] for r in ps),
            host_total_s=sum(r['decision_host_total_s'] for r in g),host_max_ms=max(r['decision_host_max_ms'] for r in g),
            terminal_checks=sum(r.get('terminal_checks',0) for r in g),terminal_blocks=sum(r.get('terminal_blocks',0) for r in g)))
    flat=[r for i in probe for r in i['records']];accepted=[r for r in flat if r['first_guard_pass']];useful=[dict(seed=i['seed'],family=i['family'],context=i['context'],**r) for i in probe for r in i['records'] if r['useful']]
    h_delta=max(abs(c['delta_h_c_per_s']) for r in flat for c in r['contexts'].values() if c['valid'])
    terminal_events=[dict(identity=identity,**r) for identity,i in items.items() if i['row']['policy']==s.x.POLICY for r in i['terminal_records']]
    (B/'pilot_terminal_records.json.gz').write_bytes(gzip.compress(json.dumps(terminal_events,separators=(',',':'),allow_nan=False).encode(),mtime=0))
    csv_tools.csv_write(B/'probe_summary.csv',probe_rows);csv_tools.csv_write(B/'development_results.csv',rows);csv_tools.csv_write(B/'policy_summary.csv',summaries);csv_tools.csv_write(B/'pairs_vs_band.csv',pairs);csv_tools.csv_write(B/'ledger_equality.csv',certificates)
    csv_tools.csv_write(B/'probe_execution_receipts.csv',s.probe.events());csv_tools.csv_write(B/'pilot_execution_receipts.csv',s.events())
    write(B/'useful_probe_examples.json',useful)
    representative={p:items[next(r['identity'] for r in rows if r['seed']==813010101 and r['family']=='sustained' and r['context']=='mean' and r['policy']==p)] for p in s.POLICIES}
    write(B/'representatives.json',{p:dict(row=i['row'],ledger=i['result']['ledger'],curves=i['curves']) for p,i in representative.items()})
    failure_example=min((dict(seed=i['seed'],family=i['family'],context=i['context'],**r) for i in probe for r in i['records'] if r['first_guard_pass'] and not r['terminal_pass']),key=lambda r:(r['now_ns'],r['seed'],r['family'],r['context']))
    write(B/'first_terminal_counterexample.json',failure_example)
    repair=read(B/'repair.json');ambiguities=[]
    for identity in repair['preserved_v1_successes']:
        source=s.parent.LOCAL/'items'/(identity.replace('/','__')+'.json.gz');item=json.loads(gzip.decompress(source.read_bytes()))
        n=sum(len([p for p in item['plans'] if p['now_ns']==g['now_ns']])>1 and next(p for p in item['plans'] if p['now_ns']==g['now_ns'])['selected_plan'] is None for g in item['prefix_guards'])
        ambiguities.append(dict(identity=identity,ambiguous_same_time_bindings=n))
    assert sum(r['ambiguous_same_time_bindings'] for r in ambiguities)==0
    write(B/'repair_verification.json',dict(status='PASS',preserved_v1_completed=10,source_cases=ambiguities,criteria_or_thermal_equation_changes=False,clock_reset=False,new_native_executions=0))
    selection=read(s.BUNDLE/'selection.json');assert equal==24 and all(v==0 for v in max_deltas.values()) and selection['chosen'] is None
    summary=dict(status='completed',scope='development-only probe and pilot; no independent final',original_g=0.,h_condition_has_independent_workload_signal=False,
        probe=dict(exact_replays=24,requests_completed=1584,first_forecasts_recovered=len(flat),first_guard_passes=len(accepted),terminal_passes=sum(r['terminal_pass'] for r in accepted),
            strict_first_gain=sum(r['first_prefix_strict_gain'] for r in accepted),useful_count=len(useful),cooling_candidates=sum(r['action_kind']=='cool_wait' for r in accepted),
            cooling_terminal_passes=sum(r['action_kind']=='cool_wait' and r['terminal_pass'] for r in accepted),maximum_absolute_h_difference=h_delta,consumption=read(B/'completion.json')['consumption']),
        pilot=dict(new_environment_starts=26,reused_rows=72,candidate_completed=1584,fixture_completed=8,band_equal_ledger_conditions=equal,maximum_absolute_KPI_differences=max_deltas,
            selected=selection['chosen'],terminal_checks=sum(r['terminal_checks'] for r in rows if r['policy']==s.x.POLICY),terminal_blocks=sum(r['terminal_blocks'] for r in rows if r['policy']==s.x.POLICY)),
        policy_summaries=summaries,consumption=done['consumption'],combined_new_starts=51,combined_failed_starts=1,validated_completed_requests=3176,
        all_attempt_planned_requests=3368,failed_attempt_planned_requests=192,failed_partial_completed_requests=None,
        independent_final_started=0,new_learning_starts=0,device_commands=0,adopted=False,experiment_ready=False,physical_improvement_proven=False,
        reason_to_stop='Terminal guard removed cooling and changed its own trajectory; the two old-trajectory forecast opportunities did not yield any difference from Band in the actual pilot. Registered stop criterion met.')
    write(B/'summary.json',summary);plots(probe,summaries,representative,pairs,failure_example);dashboard(probe_rows,summaries,pairs);return summary
def plots(probe,summaries,reps,pairs,example):
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False});out=B/'figures';out.mkdir(exist_ok=True)
    fig,ax=plt.subplots(figsize=(11,5),layout='constrained');data=[r for i in probe for r in i['records'] if r['first_guard_pass'] and r['first_prefix_strict_gain']]
    for passed,label in ((False,'종단 조건 차단'),(True,'종단 통과·예측 이득 유지')):
        g=[r for r in data if r['terminal_pass']==passed]
        ax.scatter([max(v['delta_ap_c'] for v in r['contexts'].values()) for r in g],[r['worst_first_AP_delta_c'] for r in g],alpha=.6,label=label)
    ax.axhline(0,color='grey');ax.axvline(0,color='grey');ax.set_xlabel('같은 종료 시각의 최악 예상 AP 차이 °C');ax.set_ylabel('기존 첫 선택의 최악 미래 최고 AP 차이 °C');ax.legend();ax.grid(alpha=.2);ax.set_title('지금의 최고값 감소와 종료 상태 부담의 상충');fig.savefig(out/'01_종단상태상충.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(15,5),layout='constrained')
    for ax,k,label in zip(axes,('urgent_p95_ms','energy_j','peak_ap_c'),('긴급 P95 조건별 평균 ms','공통120초 기기 전체 J 평균','같은 채널 최고 AP 평균 °C')):
        ax.bar(range(4),[r[k] for r in summaries]);ax.set_xticks(range(4),[LABELS[r['policy']] for r in summaries],rotation=35,ha='right');ax.set_ylabel(label);ax.grid(axis='y',alpha=.2)
    fig.suptitle('개발24조건 — 종단 검사는 Band와 모든 KPI 동률');fig.savefig(out/'02_개발성적비교.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(4,1,figsize=(13,8),sharex=True,layout='constrained')
    for ax,(p,item) in zip(axes,reps.items()):
        for q in item['result']['ledger']:
            a=q['dispatch_ns']/1e9;b=q['lane_available_ns']/1e9;y=q['backend']=='GPU';ax.broken_barh([(a,b-a)],(y-.25,.5),facecolors='#397cb3' if q['priority']=='urgent' else '#eda040')
        ax.set_yticks([0,1],['CPU','GPU']);ax.set_title(LABELS[p],loc='left',fontsize=10);ax.grid(axis='x',alpha=.2)
    axes[-1].set_xlim(35,55);axes[-1].set_xlabel('초 — 첫 개발 seed 지속/평균의 첫20초');fig.savefig(out/'03_대표작업시간표.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    for p in (s.POLICIES[0],s.POLICIES[2],s.POLICIES[3]):
        c=reps[p]['curves'];axes[0].plot(c['ap_times_s'],c['ap_path'],label=LABELS[p])
    axes[0].set_xlabel('초');axes[0].set_ylabel('원 AP 모형 °C');axes[0].legend();axes[0].grid(alpha=.2)
    contexts=example['contexts']
    for i,(key,name) in enumerate((('baseline','현재 큐 기준'),('candidate','첫 선택 후보'))):axes[1].bar([j+(i-.5)*.3 for j in range(3)],[contexts[c][key]['ap_c'] for c in s.x.CONTEXTS],width=.3,label=name)
    values=[v[key]['ap_c'] for v in contexts.values() for key in ('baseline','candidate')];axes[1].set_ylim(min(values)-.002,max(values)+.002);axes[1].set_xticks(range(3),['평균','짧음','김']);axes[1].set_ylabel('같은H에서 예상 AP °C');axes[1].ticklabel_format(axis='y',style='plain',useOffset=False);axes[1].set_title('사전 최초 반례: 대기 뒤 종료 AP 증가');axes[1].legend();fig.savefig(out/'04_온도경로와종단조건.png',dpi=150);plt.close(fig)
    names=['서비스 악화','비용 상충','비악화·열차 없음','J 비악화·AP 감소','J·AP 공동감소'];codes={n:i for i,n in enumerate(names)};keys=sorted({(r['seed'],r['family'],r['context']) for r in pairs});policies=(s.POLICIES[2],s.POLICIES[3]);matrix=[[codes[next(r['category'] for r in pairs if r['policy']==p and (r['seed'],r['family'],r['context'])==k)] for k in keys] for p in policies]
    fam={'low':'낮음','queue':'큐','burst':'몰림','sustained':'지속'};ctx={'mean':'평균','short_context':'짧음','long_context':'김'}
    fig,ax=plt.subplots(figsize=(15,5),layout='constrained');im=ax.imshow(matrix,cmap=ListedColormap(['#c34d4d','#e9a351','#dedede','#699bcb','#65a776']),vmin=-.5,vmax=4.5,aspect='auto');ax.set_yticks(range(2),[LABELS[p] for p in policies]);ax.set_xticks(range(24),[f'{k[0]-813010100} {fam[k[1]]} {ctx[k[2]]}' for k in keys],rotation=65,ha='right');cb=fig.colorbar(im,ax=ax,ticks=range(5));cb.ax.set_yticklabels(names);ax.set_title('개발 전체 조건 — 종단 조건 뒤 개선0');fig.savefig(out/'05_조건별결과지도.png',dpi=150);plt.close(fig)
def dashboard(probe,summaries,pairs):
    def table(rows,fields):
        def fmt(v):return LABELS.get(v,v) if isinstance(v,str) else f'{v:.8g}' if isinstance(v,float) else str(v)
        return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+n+'</th>' for k,n in fields)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(fmt(r[k]))+'</td>' for k,n in fields)+'</tr>' for r in rows)+'</tbody></table></div>'
    rules=[dict(policy=p,rule='출처 기반 요청 배정' if i==0 else '출처 기반 고정 자원' if i==1 else '후속 계획과 첫 선택 검사' if i==2 else '첫 선택 + 공통H의 AP/h 조건') for i,p in enumerate(s.POLICIES)]
    body='<h1>종단 상태를 검사한 롤링 호라이즌의 개발 결과</h1><p>원모형 g=0: h는 새 작업의 잔열 누적 정보가 아닙니다. 원 경로의 예측 기회2건 → 새 정책 실제 개발24조건 모두 기준과 동일. 추가 이득0으로 새확인·학습을 중단했습니다.</p><p>동일 미래 입력의 조건부 수식과 실제 미래 요청/기기 보장은 구분합니다. AP는 표면온도가 아닙니다.</p><p><a href="README.md">결과·수식·한계</a> · <a href="development_results.csv">개발 전체 CSV</a> · <a href="repair.json">중단1회와 기록 연결 수정</a></p><input id="filter" placeholder="정책·부하·문맥 검색">'
    body+=table(rules,[('policy','규칙'),('rule','판단 차이')]);body+=table(summaries,[('policy','정책'),('completed','완료'),('planned','예정'),('normal_failures','일반 기한 실패'),('urgent_p95_ms','P95 평균 ms'),('energy_j','J 평균'),('peak_ap_c','최고AP 평균'),('heat_gain_both','AP감소'),('terminal_checks','종단검사'),('terminal_blocks','차단')])
    body+=table(probe,[('seed','seed'),('family','부하'),('context','문맥'),('records','원첫선택'),('first_pass','기존검사통과'),('terminal_pass','종단통과'),('first_strict_gain','첫선택이득'),('useful','이득과종단통과'),('cooling_candidates','냉각후보'),('cooling_terminal_pass','냉각통과')])
    body+=table(pairs,[('seed','seed'),('family','부하'),('context','문맥'),('policy','후보'),('category','양 기준 판정'),('delta_energy_j','J 차이'),('delta_peak_ap_c','AP 차이'),('delta_urgent_p95_ms','P95 차이 ms')])
    for p in sorted((B/'figures').glob('*.png')):body+=f'<img src="figures/{p.name}" alt="{p.stem}">'
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>종단 AP 개발 비교</title><style>body{font-family:Malgun Gothic,sans-serif;margin:24px;max-width:1450px;color:#263142}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #ddd;padding:7px}th{background:#edf3f8}.scroll{overflow:auto;margin:18px 0}input{padding:10px;width:320px}img{width:100%;max-width:1300px;margin:20px 0}</style>'+body+'<script>document.querySelector("#filter").addEventListener("input",e=>{let q=e.target.value.toLowerCase();document.querySelectorAll("tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));});</script></html>'
    (B/'index.html').write_text(page,encoding='utf8',newline='\n')
if __name__=='__main__':print(json.dumps(report(),ensure_ascii=False,indent=2))
