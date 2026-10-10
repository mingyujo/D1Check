"""Completed same-data diagnosis, with matched-history snapshot evidence."""
import csv,gzip,html,json,statistics,subprocess
from collections import Counter
from datetime import datetime,timezone
from tools import d1_overnight_ie_reference_gap as d

def schedule(raw):return [(q['id'],q.get('backend'),q.get('dispatch_ns'),q.get('response_ns'),q.get('lane_available_ns')) for q in sorted(raw['result']['ledger'],key=lambda q:q['ordinal'])]

def run():
    done=d.read(d.LOCAL/'completion.json');assert done['status']=='completed';d.check();reg=d.read(d.LOCAL/'registration.json');rows=done['rows']
    data=d.read(d.LOCAL/'inputs.json');by={(q['condition'],q['policy']):q for q in rows};new_starts=[]
    for line in (d.LOCAL/'executions.jsonl').read_text(encoding='utf-8').splitlines():
        q=json.loads(line)
        if q.get('event'):new_starts[q['number']-1].update(q)
        else:new_starts.append(q)
    assert len(new_starts)==96 and all(q['status']=='completed' for q in new_starts)
    completed=planned=0
    for q in new_starts:
        path=d.LOCAL/'items'/(q['identity']+'.json.gz');assert d.sha(path)==q['sha256'];raw=json.loads(gzip.decompress(path.read_bytes()));d.native.prior.previous.audit(raw['result'],q['case']['tickets']);planned+=raw['row']['planned'];completed+=raw['row']['completed']
        assert all(q['source_request_id']=='same_overnight_'+q2['case']['context'] for q2 in [q] for q in raw['result']['ledger'])
    for q in data['controls']:
        raw=d.read_raw(q['identity']);d.native.prior.previous.audit(raw['result'],data['cases'][q['condition']]['tickets'])
    summaries=[];band={q['condition']:q for q in rows if q['policy']=='Band'}
    for role in d.ALL_ROLES:
        rs=[q for q in rows if q['policy']==role]
        assert len(rs)==48
        summaries.append(dict(policy=role,conditions=48,planned=sum(q['planned'] for q in rs),completed=sum(q['completed'] for q in rs),urgent_violation=sum(q['urgent_failure'] for q in rs),normal_violation=sum(q['normal_failure'] for q in rs),mean_condition_urgent_P95_ms=statistics.mean(q['urgent_p95_ms'] for q in rs),mean_energy_j=statistics.mean(q['energy_j'] for q in rs),mean_peak_AP_c=statistics.mean(q['peak_ap_c'] for q in rs),mean_delta_J=statistics.mean(q['energy_j']-band[q['condition']]['energy_j'] for q in rs),mean_delta_AP=statistics.mean(q['peak_ap_c']-band[q['condition']]['peak_ap_c'] for q in rs)))
    d.write(d.PUBLIC/'summary.json',summaries)
    with (d.PUBLIC/'comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=sorted({k for q in rows for k in q});out=csv.DictWriter(f,fieldnames=fields);out.writeheader();out.writerows(rows)
    first=d.read(d.PUBLIC/'first_divergence.json');focus=next(q for q in first if q['condition']==18);t=focus['first_difference_ns'];case=data['cases'][18]
    l0=d.read_raw(by[18,'L0']['identity']);b=d.read_raw(by[18,'Band']['identity']);base_snap=next(s for s in l0['snapshots'] if abs(s['now_ns']-t)<=1)
    common_dispatch={k:v for k,v in d.dispatches(l0).items() if k<t}=={k:v for k,v in d.dispatches(b).items() if k<t}
    common_phases=[q for q in l0['result']['transitions'] if q['at_ns']<=t]==[q for q in b['result']['transitions'] if q['at_ns']<=t]
    assert common_dispatch and common_phases
    new_snapshots={};input_equality={}
    for role in d.NEW_ROLES:
        raw=d.read_raw(by[18,role]['identity'],True);snap=next(s for s in raw['snapshots'] if abs(s['now_ns']-t)<=1)
        equal={key:snap[key]==base_snap[key] for key in ('state','candidates','physical_mask')};assert all(equal.values());input_equality[role]=equal
        new_snapshots[role]={k:snap[k] for k in ('state','candidates','physical_mask','mask','admissions','chosen','schema_id','forecasts','actions')}
    index=focus['candidate_matches'][0]['slot'];reference=base_snap['forecasts'][0];candidate=base_snap['forecasts'][index]
    qC=next(q for q in case['tickets'] if q['id'].endswith('/1'))
    board={q['id']:q for q in b['result']['ledger']};extra_cpu=[q for q in l0['result']['ledger'] if q['task']=='classification' and q.get('backend')=='CPU' and board[q['id']]['backend']=='GPU']
    extra_cpu_ns=sum(q['lane_available_ns']-q['dispatch_ns'] for q in extra_cpu)
    evidence=dict(condition=18,arrival_seed=case['seed'],family=case['family'],context=case['context'],time_ns=t,
        common_dispatch_history_before_t=common_dispatch,common_public_phase_callbacks_through_t=common_phases,
        same_L0_R1_Flex_full_state_candidates_physical_mask=input_equality,Band_56_feature_encoding_not_available=True,
        original_full_L0_snapshot={k:base_snap[k] for k in ('state','candidates','physical_mask','mask','admissions','chosen','schema_id','actions','forecasts')},
        R1_Flex_snapshots=new_snapshots,
        urgent_prediction=dict(L0_P95_ms=[q['urgent_p95_ms'] for q in reference],Band_like_bundle_P95_ms=[q['urgent_p95_ms'] for q in candidate],
            Bundle_C1_response_ms=[(q['responses'][qC['id']]-qC['arrival_ns']/1e9)*1000 for q in candidate],C1_deadline_ms=qC['deadline_offset_ns']/1e6,
            predicted_C1_meets_deadline_all3=all(q['responses'][qC['id']]<=d.flex.r.c.due(qC)/1e9 for q in candidate),
            current_urgent_population_note='one completed urgent+one currently queued urgent; nearest-rank P95 is maximum; this early L0 bound differs from final full-case Band comparison'),
        extra_classification_CPU_accounting=dict(request_ids=[q['id'] for q in extra_cpu],extra_busy_ns=extra_cpu_ns,
            meaning='after-episode resource accounting, never a policy input or mask recomputation'),
        interpretation='a matched-history legal Band-like bundle is present but filtered; R1 does not change urgent_response and Flex still blocks current observed P95. Not proof this is the only cause of all policy differences.')
    d.write(d.PUBLIC/'matched_history_focus.json',evidence)
    verification=dict(status='PASS',utc=datetime.now(timezone.utc).isoformat(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),new_native=96,new_learning=0,scheduled_requests=planned,completed_requests=completed,source_sha256=reg['source_sha256'],new96_raw_SHA_phase_lane_audited=True,reused480_raw_SHA_phase_lane_audited=True,
        matched_history_first_difference_proved=True,full_state_candidate_physical_mask_equal=input_equality,static_analysis_new_projection_calls=0,original_verdicts_changed=False,
        native_internal_forecasts='existing forecasts inside the 96 native executions; not additional environments',
        reused_confirmation_data=True,independent_new_confirmations=0,device_commands=0,model_fit_calls=0,automatic_adoption=False)
    d.write(d.PUBLIC/'verification.json',verification)
    counts=Counter(q.get('classification','same dispatches') for q in first)
    render=''.join('<tr>'+''.join(f'<td>{html.escape(str(q[k]) if k in ("policy","normal_violation","completed") else f"{q[k]:.6f}")}</td>' for k in ('policy','completed','normal_violation','mean_condition_urgent_P95_ms','mean_delta_J','mean_delta_AP'))+'</tr>' for q in summaries)
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><title>L0 학습 참조와 Band 비교군 격차</title><style>body{max-width:1200px;margin:35px auto;font:17px "Malgun Gothic",sans-serif;background:#f6f8fb;color:#183149}section{padding:24px;background:white;margin:20px 0}table{border-collapse:collapse;width:100%}th,td{padding:11px;border-bottom:1px solid #d7e1e9;text-align:left}.notice{background:#fff0cc;padding:20px}p{line-height:1.65}</style><h1>학습 참조 L0와 강한 비교군의 격차</h1><p class="notice">사후 같은자료 진단입니다. 새로운 독립 확인·새 정책 개발·새 본학습이 아니며 원 PPO/R1/Flex FAIL을 바꾸지 않았습니다. 새96환경·학습0·기기0·6336요청 전량 완료.</p><section><table><tr><th>고정 정책</th><th>완료</th><th>일반 기한 위반</th><th>조건별 긴급P95 평균ms</th><th>Band 대비 평균 ΔJ</th><th>평균 ΔAP °C</th></tr>'+render+'</table><p>완료는 정책별3168/3168입니다. 기한 위반은 늦은 완료이고 실행 오류가 아닙니다. 네 도착seed×세 민감도 문맥을48독립 실측으로 보지 않습니다.</p></section><section><h2>최초 동일 공개 상태의 반례</h2><p>seed827020102 · burst · 35.165216276초. 두 lane가AVAILABLE이고 C1분류와D2탐지가대기합니다. L0는C1_CPU, Band는C1_GPU+D2_CPU를 같은시각에배정했습니다.</p><p>Band 병행 후보는 원bank에 존재하고 물리적으로 허용되지만 urgent_response에서 차단됩니다. R1의동일상태/후보/물리mask는exact 같으며 Flex도 early P95가L0보다늘어같은후보를막습니다. 후보공간부재나GPU미지원문제가아닙니다.</p><p>D22는L0/PPO/NoWait 모두6.302997초, Band5.972564초(mean). 해당조건에서냉각/자원대기 선택은0입니다. CPU분류3 vs1건과추가CPU점유약330.433ms를사후회계로확인했습니다. 전체실패를냉각으로설명하면안됩니다.</p><p>학습의서비스cost는L0참조이므로L0와같은45건을더악화하지않아도Band42건의최종서비스기준은놓칠수있습니다. 이것은알고리즘미실행이나수렴완료의증거가아닙니다.</p></section><p><a href="comparison.csv">576논리행</a> · <a href="matched_history_focus.json">fulltensor·물리/예측mask</a> · <a href="first_divergence.json">전체첫차이48</a> · <a href="late_request_gap.json">같은D22세문맥</a> · <a href="verification.json">원장/SHA검증</a> · <a href="execution_contract.json">사전등록</a></p></html>'
    (d.PUBLIC/'index.html').write_text(page,encoding='utf-8')
    text=['# 학습 참조와 강한 비교군 격차의 사후 진단','','기존 RL 확인 seed827020101..104×4부하×3문맥48에 이미 동결한 R1/Flex만각1회새실행했다. 원 Band/Triton/L0/Rule/세PPO512/세NoWait 480행은 원 SHA를검사해재사용했고새소비로세지않았다. 새96/128환경·학습0·실패0·6336/6336완료, 원RL+진단2784≤3072이며 원05:54/새30분·저장5분clock을유지했다.','','새독립확인이나튜닝이아니고확인자료를다시사용한사후기전진단이다. 원일반45 vsBand42/유망0/원FAIL을보존한다. 기존앱기본은유지했고Band를우리정책기본으로채택하지않았다. 내부기본·복귀·학습참조는L0다.','','## 같은 자료 결과','','| 정책 | 일반 기한 위반 | 평균 ΔJ | 평균 Δ최고 AP °C |','|---|---:|---:|---:|']
    for q in summaries:text.append(f'| {q["policy"]} | {q["normal_violation"]} | {q["mean_delta_J"]:+.6f} | {q["mean_delta_AP"]:+.6f} |')
    text.extend(['','## 무엇을 확인했는가','','대표18의공통배정prefix와시각35.165216276초까지공개phase콜백이exact 같음을검사했다. 이후갈라진상태를같은상태처럼비교하지않았다. 원L0의상태56·후보8×28·물리mask·예측mask를보존했으며R1/Flex의같은시각상태/후보/물리mask도exact 같았다. 새마스크계산에실제미래완료나실현잔여시간을넣지않았고정적 진단의 추가 예측 호출0이다. 새96환경 내부에는 기존 예측을 그대로 사용했다.','','이상태에서C1_GPU+D2_CPU 후보가bank에있고물리허용인데urgent_response로차단됐다. C1이1.5초기한을지키는예측이어도원L0개별응답보다느리면막혔다. Flex는현재완료1+대기1인긴급두요청의P95가최댓값인초기상태여서current_observed_urgent_P95로여전히차단했다. 이것은현재한정상태의참조/제약설명이며전체정책차이의유일원인이라고주장하지않는다.','','동일요청D22(mean)의응답은L0/PPO/NoWait6.302997초vsBand5.972564초다. 이조건은대기선택0이며L0계열CPU분류3건vsBand1건이다. 추가CPU점유약330.433ms는전체종료후회계이며정책관측에주지않았다. cooling제거가추가실패를없앤다고전제할수없다.','','초기미관측대기를막은R1은다른확인48에서원Rule추가서비스손실을막았지만, 이번827자료는L0자체45 vsBand42이므로R1/Flex도45다. 학습참조와최종비교기준격차·현재허용마스크·순서/자원배정을분리해야한다. 해당 동일 상태·현재 허용 규칙에서는 학습량 추가로 마스크 밖 행동을 선택할 수 없다. 이전 행동으로 다른 상태에 도달할 개선 가능성까지 부정하지 않는다.','','## 적용과 다음 판단','','queue/burst압력에서늦은완료가존재하지만 모든42건이불가피한과부하라는최적/용량증명은없다. D22는같은입력에서Band가제때끝내므로L0의해당추가위반은전량불가능을뜻하지않는다. 원low/sustained절대기한·전량·모든조건서비스/J/AP원판정은완화하지않았다.','','후속ROI는새대규모학습보다현재참조·예측제약과원KPI의대응을명확히하고,지원범위/예측오차/온라인제어비용을먼저검토하는쪽이크다. 새로운목적/마스크변경은별도미래계약의문제이며이번실행에소급하지않는다.','','```powershell','python -B -X utf8 -m tools.d1_overnight_ie_reference_gap check','python -B -X utf8 -m tools.d1_overnight_ie_reference_gap_report','```','','위명령은원등록과local완료gz가있는현재작업공간의검증/후처리이다. 공유화면·CSV·fulltensor/마스크json은읽기전용으로열린다. 완료task등록/run을재호출해예산을초기화하지않는다. 새weights/source/default/NPU/기기/fit변경0이다.'])
    (d.PUBLIC/'README.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    return dict(summary=summaries,verification=verification,first_divergence_counts=dict(counts))

if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False),flush=True)
