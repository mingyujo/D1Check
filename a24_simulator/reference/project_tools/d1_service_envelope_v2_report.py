"""Final bounded V2 report, no additional environment or fitting."""
import csv,gzip,html,json,statistics
from collections import Counter
from datetime import datetime,timezone
from tools import d1_service_envelope_v2_run as d
def schedule(raw):return [(q['id'],q['backend'],q['dispatch_ns'],q['response_ns'],q['lane_available_ns']) for q in sorted(raw['result']['ledger'],key=lambda q:q['ordinal'])]
def run():
    reg=d.check();state=d.read(d.LOCAL/'WORKING_STATE.json');assert state['phase']=='completed'
    events=[]
    for line in (d.LOCAL/'executions.jsonl').read_text(encoding='utf-8').splitlines():
        q=json.loads(line)
        if q.get('event'):events[q['number']-1].update(q)
        else:events.append(q)
    assert len(events)==171 and all(q['status']=='completed' for q in events)
    planned=completed=0;counts=Counter();snapshot_counts=Counter();raws={};callbacks=[]
    for q in events:
        path=d.LOCAL/'items'/(q['identity']+'.json.gz');assert d.sha(path)==q['sha256'];raw=json.loads(gzip.decompress(path.read_bytes()));raws[q['identity']]=raw
        d.native.prior.previous.audit(raw['result'],q['case']['tickets']);planned+=raw['row']['planned'];completed+=raw['row']['completed']
        if q['role']!='CostV2' or q['phase']!='confirmation':continue
        counts['cooling_selections']+=raw['cooling_count'];counts['cooling_seconds']+=raw['total_extra_wait'];callbacks+=raw.get('callback_seconds',[])
        if raw['request_wait']:assert max(raw['request_wait'].values())<=.25+1e-8
        for s in raw['snapshots']:
            assert s['mask'][s['chosen']] and not any(a and not b for a,b in zip(s['mask'],s['physical_mask']))
            snapshot_counts['decisions']+=1;snapshot_counts['physical_slots']+=sum(s['physical_mask']);snapshot_counts['admitted_slots']+=sum(s['mask']);snapshot_counts['informative_slots']+=sum(s['mask'])>1;snapshot_counts['nonreference_choices']+=s['chosen']!=0;snapshot_counts['chosen_'+s['actions'][s['chosen']]['kind']]+=1
    rows=d.read(d.PUBLIC/'confirmation_comparison.json');band={q['condition']:q for q in rows if q['policy']=='Band'};summaries=[];differences=[]
    for role in d.ROLES:
        rr=[q for q in rows if q['policy']==role]
        summaries.append(dict(policy=role,conditions=48,planned=sum(q['planned'] for q in rr),completed=sum(q['completed'] for q in rr),urgent_violations=sum(q['urgent_failure'] for q in rr),normal_violations=sum(q['normal_failure'] for q in rr),mean_condition_P95_ms=statistics.mean(q['urgent_p95_ms'] for q in rr),mean_J=statistics.mean(q['energy_j'] for q in rr),mean_AP=statistics.mean(q['peak_ap_c'] for q in rr),mean_delta_J=statistics.mean(q['energy_j']-band[q['condition']]['energy_j'] for q in rr),mean_delta_AP=statistics.mean(q['peak_ap_c']-band[q['condition']]['peak_ap_c'] for q in rr),mean_delta_P95_ms=statistics.mean(q['urgent_p95_ms']-band[q['condition']]['urgent_p95_ms'] for q in rr)))
    for q in rows:
        if q['policy']!='CostV2':continue
        b=band[q['condition']];differences.append(dict(condition=q['condition'],seed=q['arrival_seed'],family=q['family'],context=q['context'],delta_normal_violations=q['normal_failure']-b['normal_failure'],delta_P95_ms=q['urgent_p95_ms']-b['urgent_p95_ms'],delta_J=q['energy_j']-b['energy_j'],delta_AP=q['peak_ap_c']-b['peak_ap_c']))
    gate=d.read(d.PUBLIC/'confirmation_verdict.json');groups={}
    for family in ('low','queue','burst','sustained'):
        ds=[q for q in gate['differences'] if q['family']==family];rr=[q for q in differences if q['family']==family]
        groups[family]=dict(conditions=len(rr),passes_against_Band=sum(q['passed'] for q in ds if q['baseline']=='Band'),passes_against_Triton=sum(q['passed'] for q in ds if q['baseline']=='Triton'),all_declared_conditions_pass=all(q['passed'] for q in ds),mean_delta_J=statistics.mean(q['delta_J'] for q in rr),mean_delta_AP=statistics.mean(q['delta_AP'] for q in rr),mean_delta_P95_ms=statistics.mean(q['delta_P95_ms'] for q in rr),normal_violation_delta=sum(q['delta_normal_violations'] for q in rr))
    rep=raws['representative_CostV2'];v1=d.ROOT/'output/service_envelope_20261011_v1/items/representative_Band.json.gz';baseline=json.loads(gzip.decompress(v1.read_bytes()));exact=schedule(rep)==schedule(baseline)
    representative=dict(predeclared96same35s350ms=True,original_Band_raw_sha256=d.sha(v1),exact_Band_schedule=exact,different_requests=sum(a!=b for a,b in zip(schedule(rep),schedule(baseline))),new_phone_sessions=0)
    verification=dict(status='PASS',utc=datetime.now(timezone.utc).isoformat(),registered_head=reg['head'],source_sha256=reg['source_sha256'],native_starts=171,native_cap=192,new_learning=0,scheduled_requests=planned,completed_requests=completed,failed=0,all_raw_SHA_phase_lane_audited=True,physical_mask_and_waitcap=True,unit_tests=3,gate2=True,development_service_count_losses=0,independent_new_confirmation_seed_set=True,final_gate_unchanged=True,device_commands=0,model_fit_calls=0,forecast_not_future_guarantee=True)
    d.write(d.PUBLIC/'summary.json',dict(summary=summaries,by_family=groups,selection_counts=counts,snapshot_counts=snapshot_counts,callback_seconds=sum(callbacks),phone_control_cost=None));d.write(d.PUBLIC/'condition_differences.json',differences);d.write(d.PUBLIC/'representative_receipt.json',representative);d.write(d.PUBLIC/'verification.json',verification)
    for name,rs in [('comparison.csv',rows),('condition_differences.csv',differences)]:
        with (d.PUBLIC/name).open('w',encoding='utf-8-sig',newline='') as f:fields=sorted({k for q in rs for k in q});w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rs)
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.family']='Malgun Gothic';plt.rcParams['axes.unicode_minus']=False
    folder=d.PUBLIC/'figures';folder.mkdir(exist_ok=True);fig,axes=plt.subplots(1,3,figsize=(12,4))
    for ax,k,label in zip(axes,('delta_P95_ms','delta_J','delta_AP'),('Band 대비 긴급P95 차이 (ms)','Band 대비 에너지 차이 (J)','Band 대비 최고 AP 차이 (°C)')):
        vv=[q[k] for q in differences];ax.bar(range(48),vv,color=['#cf8d68' if v>0 else '#418c80' for v in vv]);ax.axhline(0,color='#374958',lw=.8);ax.set_ylabel(label);ax.set_xlabel('새 고정 조건0..47')
    fig.suptitle('V2 새835확인 · 비용 감소와 서비스 손실을 함께 표시 · 전체 FAIL');fig.tight_layout();fig.savefig(folder/'01_비용과서비스상충.png',dpi=150);plt.close(fig)
    table='<table><tr><th>정책</th><th>완료</th><th>일반 기한 위반</th><th>조건별 P95 평균ms</th><th>평균 ΔJ</th><th>평균 ΔAP°C</th></tr>'
    for q in summaries:table+='<tr>'+''.join('<td>'+html.escape(str(q[k]) if k in ('policy','completed','normal_violations') else f'{q[k]:.6f}')+'</td>' for k in ('policy','completed','normal_violations','mean_condition_P95_ms','mean_delta_J','mean_delta_AP'))+'</tr>'
    table+='</table>'
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><title>서비스 Envelope V2</title><style>body{max-width:1180px;margin:30px auto;font:18px "Malgun Gothic",sans-serif;color:#17364d;background:#f5f8fb}section{padding:25px;background:white;margin:22px 0}table{width:100%;border-collapse:collapse}th,td{padding:13px;border-bottom:1px solid #dbe2e9;text-align:left}p{line-height:1.65}.warn{padding:23px;background:#fff0d0}img{width:100%}</style><h1>서비스 Envelope V2: 대안은 열렸고 전체 서비스는 지키지 못했다</h1><p class="warn">새171환경·학습0·전량 완료·실패0. 일반 기한 위반45 vs Band42/Triton39, 긴급P95도Band보다악화했다. 평균AP/J 감소를 전체 방법론 성공으로 표시하지 않는다.</p><section>'+table+'<p>각3168/3168 완료. P95 평균은 조건별 P95의 평균, 기한 위반은 늦은 완료다. 민감도3문맥은 독립 실측3회가 아니다.</p></section><section><h2>제거한 과제약과 남은 한계</h2><p>기한 내 일반 작업의 응답 시각까지 Joint 참조와 같아야 한다는 조건을 제거했다. 현재 위반/지각량·P95는 보호하고 .25초 누적 대기/물리 지원을 유지한다. 참조 순위는 P95를 전체 드레인ECT보다 먼저 보았다. 초기 표본 P95와 실제 전체 P95는 같지 않으므로 모든 guard를 최종KPI와 동일화한 것이 아니다.</p><p>확인 자료를 보고 V1 기준을 바꾸지 않았다. V1/기존RL은 보존하고 V2를 별도 사전등록하여 새835자료에서 평가했다. 공유 fallback/suffix는 V1의 유한 EDD·ECT근사이며 본정책을 재귀적으로 끝까지 실행한 rollout은 아니다.</p></section><section><img src="figures/01_비용과서비스상충.png"></section><p><a href="README.md">보고서</a> · <a href="comparison.csv">전체CSV</a> · <a href="summary.json">부하군/실제대기</a> · <a href="execution_contract.json">사전등록</a> · <a href="verification.json">원장검증</a> · <a href="confirmation_verdict.json">원strict 판정</a></p></html>'
    (d.PUBLIC/'index.html').write_text(page,encoding='utf-8')
    lines=['# 서비스 Envelope V2: 부분 개선과 전체 실패','',f'새171/192환경·학습0·오류0·{completed}/{planned}요청 완료. native gate2+개발24+새 확인48×3역할144+대표1을 보존했다. 개발 Band/Triton48행은 이전 완료 SHA로 재사용했고 새환경으로 세지 않았다.','', 'CPU-only 개별 응답 보호로만 탈락한273개 저장 슬롯이 개정 근거다. 반복 슬롯이지 독립 이득273회가 아니다. 일반 기한/위반/지각 기준은 유지하되 개별 응답 불변을 제거했고 참조 P95를 드레인 ECT 앞에 두었다. 이는 일부 과제약과 순위의 정렬이며 전체 미래 P95 보장을 뜻하지 않는다.','', '| 정책 | 일반 기한 위반 | 조건별 P95 평균ms | 평균 ΔJ | 평균 ΔAP°C |','|---|---:|---:|---:|---:|']
    for q in summaries:lines.append(f'| {q["policy"]} | {q["normal_violations"]} | {q["mean_condition_P95_ms"]:.6f} | {q["mean_delta_J"]:+.6f} | {q["mean_delta_AP"]:+.6f} |')
    lines.extend(['','**전체 원strict FAIL·유망0·최종 자동채택0**이다. 평균 비용 감소를 일반 추가 위반/P95 악화와 바꾸지 않는다. V1과 V2는 서로 다른 새 확인 seed이므로 표의42/45나AP평균을 직접 전후 개선으로 합치지 않는다.','', '## 부하군별 범위',''])
    for family,q in groups.items():lines.append(f'- {family}: Band 대비 통과{q["passes_against_Band"]}/12, Triton 대비 통과{q["passes_against_Triton"]}/12, ΔJ{q["mean_delta_J"]:+.6f}J/ΔAP{q["mean_delta_AP"]:+.6f}°C/ΔP95{q["mean_delta_P95_ms"]:+.6f}ms/일반위반차{q["normal_violation_delta"]:+d}.')
    lines.extend(['','사전 고정한 부하군의 조건부 결과는 전체 통과 판정을 대체하지 않는다. 정책에 미래 trace의 low/burst 이름을 넣어 유리한 경우만 실행하지 않았다. 현재 관측 도착 이력으로 미래 몰림을 보장할 수 없다.','',f'실제 냉각 선택{counts["cooling_selections"]}회/추가{counts["cooling_seconds"]:.6f}초, slot0 외 선택{snapshot_counts["nonreference_choices"]}회. 대표96은 Band exact='+str(exact)+'이며 새 기기 재생0이다. AP는 표면 온도가 아니고 작은모형차이는폰절감입증이아니다. 기존 실측4회/원PPO512/새V1학습을 보존했다.','', '[화면](index.html) · [CSV](comparison.csv) · [부하군/선택](summary.json) · [설정](execution_contract.json) · [기능/원장 검증](verification.json)','', '```powershell','python -B -X utf8 -m unittest tools.test_d1_service_envelope_v2_policy -v','python -B -X utf8 -m tools.d1_service_envelope_v2_run check','python -B -X utf8 -m tools.d1_service_envelope_v2_report','```','', '현재 workspace 원gz 후처리이며 새환경/학습/기기/fit0이다. 완료run/등록을 반복해예산을초기화하지않는다. 기존V1 actor를V2로재사용하지않는다.'])
    (d.PUBLIC/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return dict(verification=verification,summary=summaries,by_family=groups,selection=counts,representative=representative)
if __name__=='__main__':print(json.dumps(d.serial(run()),ensure_ascii=False),flush=True)
