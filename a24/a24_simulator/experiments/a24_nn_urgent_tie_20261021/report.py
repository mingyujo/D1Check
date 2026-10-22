"""Saved-only final Korean comparison, limitations and inference contract."""
import hashlib,json
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[2];O=R/'a24_simulator/results/A24_NN_URGENT_TIE_20261021_01'
def read(n):return json.loads((O/n).read_text(encoding='utf8'))
def write(n,s):
    with (O/n).open('x',encoding='utf8',newline='\n') as f:f.write(s.rstrip()+'\n')
a,py,diag,result=read('ACCOUNTING.json'),read('AUDIT_PY.json'),read('DIAGNOSTICS.json'),read('RESULT.json');js,lab,fixed,rem,matched,cal=read('AUDIT_JS.json'),read('AUDIT_LABELS_JS.json'),read('FIXED_PREVIOUS_STATES.json'),read('REMAINING_ERROR_AUDIT.json'),read('MATCHED_REQUESTS.json'),read('RISK_CALIBRATION.json')
names={'FIFO_DYN':'FIFO','EDF_DYN':'EDF','RR_DYN':'RR','TEACHER_OLD':'최초 교사','BC_OLD':'최초 보완 BC','TEACHER_FAIR':'이전 교사(여유0)','COST_IMITATION':'이전 비용회귀 모방','BC_NEURAL_PREVIOUS':'NN03 BC(긴급932)','BC_NEURAL_MARGIN':'직전04B BC','TEACHER_RISK':'새 교사(오차여유)','BC_NEURAL_URGENT':'이번05 BC'}
def pct(s):return 100*s['on']/s['n']
def get(rate,policy):return next(x for x in a['aggregates'] if x['load']==rate and x['policy']==policy)
def table(rows,pattern=False):
    out=['|건/초|'+('패턴|' if pattern else '')+'정책|소비 J*|평균 AP ℃|전체 정시 %|일반 정시 %|긴급 정시 %|일반 P95 초|긴급 P95 초|미응답/미완료|','|---:|'+('---|' if pattern else '')+'---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for x in rows:
        s=x['service'];v=x['common'] if pattern else x
        out.append(f"|{x['load']}|"+(x['pattern']+'|' if pattern else '')+f"{names[x['policy']]}|{v['J']:.6f}|{v['AP']:.6f}|{pct(s['ALL']):.4f}|{pct(s['N']):.4f}|{pct(s['U']):.4f}|{s['N']['P95']:.6f}|{s['U']['P95']:.6f}|{s['ALL']['missing']}/{s['ALL']['incomplete']}|")
    return '\n'.join(out)
main=[x for x in a['aggregates'] if x['policy'] in ('FIFO_DYN','EDF_DYN','RR_DYN','TEACHER_FAIR','BC_NEURAL_PREVIOUS','BC_NEURAL_MARGIN','TEACHER_RISK','BC_NEURAL_URGENT')];other=[x for x in a['aggregates'] if x not in main];summary=[]
for rate in (1,4):
    x=get(rate,'BC_NEURAL_URGENT');old=get(rate,'BC_NEURAL_MARGIN');nn03=get(rate,'BC_NEURAL_PREVIOUS');t=get(rate,'TEACHER_RISK');e=get(rate,'EDF_DYN');s=x['service'];summary.append(f"{rate}건/초: 이번 BC 전체 {s['ALL']['on']}/{s['ALL']['n']}={pct(s['ALL']):.4f}%, 일반 {s['N']['on']}/{s['N']['n']}={pct(s['N']):.4f}%, 긴급 {s['U']['on']}/{s['U']['n']}={pct(s['U']):.4f}%. 직전04B 대비 전체 {s['ALL']['on']-old['service']['ALL']['on']:+d}/일반 {s['N']['on']-old['service']['N']['on']:+d}/긴급 {s['U']['on']-old['service']['U']['on']:+d}건·소비 {x['J']-old['J']:+.6f}J*·긴급P95 {s['U']['P95']-old['service']['U']['P95']:+.6f}초. NN03 긴급 {nn03['service']['U']['on']}건 대비 {s['U']['on']-nn03['service']['U']['on']:+d}건. 새 교사 대비 전체 {s['ALL']['on']-t['service']['ALL']['on']:+d}/일반 {s['N']['on']-t['service']['N']['on']:+d}/긴급 {s['U']['on']-t['service']['U']['on']:+d}건·소비 {x['J']-t['J']:+.6f}J*. EDF 대비 소비 {e['J']-x['J']:+.6f}J*/{100*(1-x['J']/e['J']):+.4f}% 절감·긴급P95 {s['U']['P95']-e['service']['U']['P95']:+.6f}초.")
ev=[x for x in py['cases'] if x['policy']=='BC_NEURAL_URGENT'];calls=sum(x['counts']['calls'] for x in ev);exact=sum(x['counts']['exact'] for x in ev);multi=sum(x['counts']['nontrivial'] for x in ev);mgood=sum(x['counts']['nontrivial_exact'] for x in ev);compatible=sum(x['counts']['cost_compatible'] for x in ev)
ft=['|고정11329상태 진단|정확 일치/선택|오류|기존79 중 정답|교사 선택 변경|','|---|---:|---:|---:|---:|']
for mode,title in (('old_mask_old_teacher','이전 서비스 마스크/이전 교사'),('new_mask_new_teacher','새 서비스 마스크/새 교사')):
    c={k:sum(r[mode].get(k,0) for r in fixed['cases']) for k in ('calls','exact','old_79_subset','old_79_now_exact','teacher_action_changed')};ft.append(f"|{title}|{c['exact']}/{c['calls']}|{c['calls']-c['exact']}|{c['old_79_now_exact']}/{c['old_79_subset']}|{c['teacher_action_changed']}|")
et=['|case|선택 수|정확 행동 %|복수 후보 수|복수 후보 정확 %|오류|최대 공개 비용 차|','|---|---:|---:|---:|---:|---:|---:|']
for x in ev:et.append(f"|{x['case']}|{x['counts']['calls']}|{100*x['exact_accuracy']:.4f}|{x['counts']['nontrivial']}|{100*x['nontrivial_accuracy']:.4f}|{x['counts']['calls']-x['counts']['exact']}|{x['max_teacher_regret']:.9g}|")
tr=['|학습 단계|TRAIN 상태|전체 정확 %|복수 후보 정확 %|epoch|Adam step|','|---|---:|---:|---:|---:|---:|']
for x in py['fits']:tr.append(f"|{x['stage']}|{x['final']['n']}|{100*x['final']['all']:.4f}|{100*x['final']['nontrivial']:.4f}|{x['epochs']}|{x['optimizer_steps']}|")
dt=['|건/초|비교대상|소비절감 J*|소비절감 %|전체정시차 %p|일반정시차 %p|긴급정시차 %p|긴급P95차 초|','|---:|---|---:|---:|---:|---:|---:|---:|']
for x in a['deltas']:
    if x['policy']=='BC_NEURAL_URGENT':dt.append(f"|{x['load']}|{names[x['reference']]}|{x['energy_saving_J']:+.6f}|{x['energy_saving_percent']:+.4f}|{x['all_on_change_pp']:+.4f}|{x['normal_on_change_pp']:+.4f}|{x['urgent_on_change_pp']:+.4f}|{x['urgent_P95_change_s']:+.6f}|")
write('REPORT_KO.md',f'''# 남은 모방오차·긴급 정시율 보완 후 같은 S26식 입력 비교

2026-10-21 · A24-NNBC-URGENT-05 · branch codex/a24-simulator-handoff-20261016 · HEAD ac3a5af569e04bc6be01f1ef976b9dd4eb6558cf + 로컬 미커밋/미게시.

{chr(10).join(summary)}

## 같은 요청 조건의 주표

{table(main)}

동일 SHA의 600초 공급/1·4건/초/균등·8묶음 네 입력이다. 저부하는 1200건(U312/N888), 고부하는4800건(U1177/N3623)의 두 패턴 합계다. 정시율은 모든 도착 분모, 미응답/미완료는 drain815초 기준, P95는 두 패턴의 응답 지연 합친 nearest rank다. J*/AP는 같은 case에서 11정책 모두 AVAILABLE인 완료시각(최소 공급종료)까지 공통창으로 적분한 두 패턴 평균이다. FIFO/EDF/RR의 동적 route/CPU3·GPU1 병행도 그대로다. S26의 요청 형식을 사용하고 A24의 물리/원 측정/명목 시간/열/경합 beta.25는 그대로다.

## 79회와 모방 정확도

직전04B의 79오류는 비용 순서 밖64/비용 허용차1e-8 안의 다른 행동15다. 기존 입력49는 요청 후보 위치였고 WAIT/route를 모두 관통하는 행동 나열 순서는 직접 제공하지 않았다. 이번에는 공개 후보 나열 index/35를49번에 주어 동점의 일관된 순서를 학습하게 했다. 이것은 정답 index/rank가 아니며 모든 후보마다 계산된다. 비용 차가 작아도 일률적으로 logit margin.5를 요구하던 손실 대신, 공개 비용 차에 따른 margin과 모든 오답 후보 pairwise hinge를 사용했다. 이 원인 설명은 설계 진단이며 두 수정과 데이터 추가 각각의 인과 효과를 분리한 ablation은 아니다.

새 동결 BC의 실제 새 궤적은 정확 행동 {exact}/{calls}={100*exact/calls:.4f}%, 복수 후보 {mgood}/{multi}={100*mgood/multi:.4f}%, 오류 {calls-exact}회다. 비용 호환 선택은 {compatible}/{calls}다. 교사가 바뀌고 방문 상태/분모도 바뀌었으므로 이를 단순히 이전79에서 뺀 값으로 해석하지 않는다.

{chr(10).join(et)}

이전11329개 전체 공개 상태에서 forward만 수행한 별도 진단은 다음과 같다. 이전 마스크 모드는 새 위험 여유 보호를 꺼서 이전 교사 정답에 대한 순수 모방을 확인하는 진단이며 실제 새 정책 실행이 아니다. 두 모드 모두 gradient/환경 실행/평가 모델 선택0이다.

{chr(10).join(ft)}

{chr(10).join(tr)}

최종 TRAIN 잔여오류 {len(rem['TRAIN_errors'])}회, 완전히 같은 float32입력+마스크의 상충 정답 그룹 {len(rem['contradictory_identical_float32_groups'])}개다. 평가 사례를 학습에 넣지 않았다. 최종 checkpoint {result['fits'][-1]['network_sha256']}는 fit2를 사전에 최종으로 지정한 결과이며 평가 성적으로 epoch/seed/모델을 고르지 않았다.

## 기존 참고 정책과 모든 차이

{table(other)}

소비절감은 비교대상−이번 BC, 정시/P95차는 이번 BC−대상이다. 음수 절감/정시 하락·양수 P95 증가는 손해다.

{chr(10).join(dt)}

## 검증과 해석 범위

TRAIN 잔차 추정1+TRAIN6+BC2fit+EVAL8=17 START/COMPLETE를 보존했다. 새 교사4/BC4만 평가했고 기존36행을 저장 재사용했다. 독립 JS {js['checks']:,}검사(물리 {js['independent_math_checks']:,}/결정 {js['decision_checks']:,}), TRAIN 라벨 JS {lab['labels']:,}상태/{lab['checks']:,}검사, 실제 Torch/NumPy NN {py['neural_frames']:,}선택/float64 argmax최대차 {py['Float64_argmax_max_regret']:.3g}, TRAIN출처 {py['TRAIN_source_bindings']:,}/요청 {py['request_bindings']:,}/잔차 {py['calibration_bindings']} 결합 PASS다. 원망/평가 checkpoint/optimizer/RNG 및 critic/PPO 카운터 불변, 원50특징 Net의 shape 유지다. 입력/마스크 ABI는 바뀌었으므로 [입력 계약](INFERENCE_CONTRACT.json)과 checkpoint를 함께 사용해야 한다.

이번 수정은 교사의 목적/안전 여유와 BC 학습을 함께 바꿨다. 성과를 BC 단독 효과, 교사 초월 최적화, 학습이 필요 없는 교사보다 연산 절약으로 주장하지 않는다. 공개 교사 비용/rolling 예측 자체는 여전히 계산한다. 알려진 benchmark를 본 뒤의 개발 평가이며 새 blind holdout/실기기 절감/통계적 일반화가 아니다. 가상 CPU3·미교정 J*·공통 원측정 세션·열/경합 가정·제어 계산 비용 누락을 유지한다. 새 실측/물리 fit/PPO/원 완료 재시작/자동 후속실험·채택/게시0이다.

[전체44행](ALL_ROWS_KO.md) · [원인/손해](INTERPRETATION_KO.md) · [고정상태79추적](FIXED_PREVIOUS_STATES.json) · [재개/봉인](CONTINUE_RUNNING.md).
''')
write('ALL_ROWS_KO.md','# 같은 S26식 입력 · 11정책 44행\n\n'+table(a['rows'],True)+'\n\n[22집계행/주표](REPORT_KO.md) · [기계 판독/공통창](ACCOUNTING.json). 과거 완료36행은 저장 재사용이고 새 환경 실행은8평가다.')
losses=[]
for x in a['deltas']:
    if x['policy']!='BC_NEURAL_URGENT':continue
    if x['energy_saving_J']<0 or x['all_on_change_pp']<0 or x['normal_on_change_pp']<0 or x['urgent_on_change_pp']<0 or x['urgent_P95_change_s']>0:losses.append(f"- {x['load']}건/초 vs {names[x['reference']]}: 소비절감 {x['energy_saving_J']:+.6f}J*, 전체/일반/긴급정시 {x['all_on_change_pp']:+.4f}/{x['normal_on_change_pp']:+.4f}/{x['urgent_on_change_pp']:+.4f}%p, 긴급P95 {x['urgent_P95_change_s']:+.6f}초.")
dr=['|case|정책|긴급 정시/전체|명목정시→실제지각|여유반영정시→실제지각|정확모방 오류|','|---|---|---:|---:|---:|---:|']
for r in diag['rows']:
    c=r['counts'];g=r['groups']['U'];dr.append(f"|{r['case']}|{names[r['policy']]}|{g['on']}/{g['n']}|{c.get('urgent_nominal_on_actual_late',0)}|{c.get('urgent_buffered_on_actual_late',0)}|{c['calls']-c['exact']}|")
write('INTERPRETATION_KO.md',f'''# 원인·보완·남은 손해

저장 요청의 대응 비교에서 직전04B의 긴급은 NN03보다 고부하 균등12건 감소/묶음4건 증가=순8건 감소였다. 전체 학습 규칙을 정확히 모방한다고 각 긴급 요청 정시가 자동 개선되지 않는다. 명목 예측상 정시인데 실제 모의 실행이 늦는 사례가 고부하56건이었다. 예: 균등 common-000233, 기한94.45초, dispatch시 명목94.438126초인데 실제94.525820초(교사와 동일 선택). 예측은 공개 명목시간과 EDF continuation/현재 관측 요청만 쓰며, 실제는 동결 private 시간·후속 도착·실제 정책 재선택에 따라 경합이 달라진다. 따라서 이를 순수 센서 오차나 물리 코드 버그로 단정하지 않는다. 저장 궤적의 정합/직전 선택을 추적한 것이며 단일 행동 치환 인과실험은 하지 않았다.

단순 `(긴급지각,전체지각)` 우선순위 교환은 저장 TRAIN/EVAL에서 개선후보0으로 확인해 채택하지 않았다. 대신 별도 TRAIN 긴급208 dispatch의 `실제 모의 응답−명목 예측` 잔차를 C94/D114로 나눠 90% nearest-rank 분위수를 추정했다. C {cal['task_margin_s']['C']:.9f}초, D {cal['task_margin_s']['D']:.9f}초다. 이는 실측 보정이 아니라 TRAIN 궤적을 이용한 정책 여유시간이다. 같은 hot 입력 반복/소표본/정책 의존성이 있으므로 이 수치가 미래 지각 확률10%를 보장하지 않는다.

새 교사는 `(여유 반영 긴급 지각,명목 전체 지각,명목 긴급 지각)`를 최소화한 후보 안에서 기존 일반 latest-start 보호와6공개 비용을 쓴다. 미래 도착/평가 응답/비공개 시간은 실행 입력이 아니다. 그 결과의 서비스/소비를 새 교사와 새 NN 각각 평가했다. 남는 지각에는 이미 대응이 늦은 요청, 명목과 private/실제 경합의 차이, 새 정책이 바꾼 경합, 모방오차가 섞인다. 단순히 새 NN의 모든 지각을 모방오차로 세지 않는다.

{chr(10).join(dr)}

79회 오차 보완은 신경망 구조를 바꾸지 않고 공개 행동순서를 입력49로 표현하고 비용차별 pairwise margin/자기방문 TRAIN6를 추가한 것이다. 입력의 상당 부분은 교사의 공개 예측이므로 이 BC가 새로운 산업공학 목표를 독립 발견했다는 주장은 하지 않는다. 기존79고정상태 추적과 새 궤적 오류를 [보고서](REPORT_KO.md)에 따로 적었다. 남은 실제 평가오류 {calls-exact}회/TRAIN {len(rem['TRAIN_errors'])}회는 보존했다. 비용 동점의 다른 실제 작업은 hidden private 시간이 다를 수 있어 비용호환과 정확행동 일치를 계속 분리한다.

모든 비교 중 하나라도 남는 손해는 다음과 같다. 정확한 정시 건수·AP·일반P95를 포함한 전체 값은 [주표](REPORT_KO.md)/[44행](ALL_ROWS_KO.md)에 있다.

{chr(10).join(losses)}

여유시간의 목적/공통 서비스 마스크·입력49·학습 손실·자료 추가가 함께 바뀌었으므로 각각의 기여를 분리한 대조실험이 아니다. 새 교사 대비 NN 차이는 학습 정책이 방문한 상태까지 포함한 전체 궤적 차이다. 근거 없이 ‘교사보다 높은 지능/최적’으로 해석하지 않는다. J*는 미교정 모형 소비이며 실기기 절감이 아니다. 현재 최종 결과를 보고 자동 튜닝/새 실험/채택하지 않았다.
''')
contract=dict(schema='A24_NEURAL_INFERENCE_CONTRACT_V4',checkpoint=result['fits'][-1]['checkpoint'],network_sha256=result['fits'][-1]['network_sha256'],original_Net='a24_atc_bc_20261019.learner.Net',shape=[36,50],preprocessing='a24_nn_urgent_tie_20261021.policy.Policy(risk=RISK_CALIBRATION.task_margin_s)',input28='eligible candidate public cost centered/scaled; float32; ineligible zero',input49='public action enumeration index/35, padded zero; not target action index',unchanged_other_features=48,mask='buffered urgent late / nominal total late / nominal urgent late, then critical normals',risk_calibration=dict(path=(O/'RISK_CALIBRATION.json').relative_to(R).as_posix(),sha256=hashlib.sha256((O/'RISK_CALIBRATION.json').read_bytes()).hexdigest()),teacher_public_cost_computed_at_runtime=True,selection='frozen learned neural logits argmax, first exact logit tie',post_NN_override=False,cost_regression=False,PPO=False,EVAL_model_selection=False,adopted=False,mobile_validated=False)
write('INFERENCE_CONTRACT.json',json.dumps(contract,ensure_ascii=False,indent=2))
write('CONTINUE_RUNNING.md',f'''# 완료 상태와 재개

A24-NNBC-URGENT-05의 유한17 START/COMPLETE17(CALIBRATION1/TRAIN6/BC2/EVAL8), FAIL/SKIP0 완료다. 결과는 [주표](REPORT_KO.md)/[44행](ALL_ROWS_KO.md)/[원인/손해](INTERPRETATION_KO.md)를 따른다. 같은 완료 identity를 다시 실행하지 않는다. 추가 과학실험은 새 사용자 범위/새 namespace/등록과 고유 영수증이 필요하다. 로컬 예약합산137962는 전호스트census가 아니다.

최종망 `{result['fits'][-1]['network_sha256']}`는 [fit2](NEURAL_BC_FIT_STAGE2.json)/해당 DATA·TRACE와 짝이다. 원50특징 Net shape는 같지만 입력49/마스크와 policy ABI가 다르다. [입력 계약](INFERENCE_CONTRACT.json)/[TRAIN 잔차 여유](RISK_CALIBRATION.json)/[정책](../../experiments/a24_nn_urgent_tie_20261021/policy.py)을 함께 사용한다. old checkpoint wrapper로 바꾸거나 교사 action을 NN 출력에 덮어쓰지 않는다.

과거 모든 완료/실패/초안/체크포인트를 보존했고 원 소스/input pin은 불변이다. [실제 영수증](receipts.jsonl)/[RESULT](RESULT.json), [Python검산](AUDIT_PY.json)/[JS검산](AUDIT_JS.json)/[TRAIN검산](AUDIT_LABELS_JS.json)/[고정이전상태](FIXED_PREVIOUS_STATES.json)/[대응요청](MATCHED_REQUESTS.json)/[잔여오차](REMAINING_ERROR_AUDIT.json) PASS다. 최종 [봉인](FINAL_PROOF.json)/[재검산](FINAL_RECHECK.json)은 자료와 네 상태 문서를 기록한다.

HEAD ac3a5af569e04bc6be01f1ef976b9dd4eb6558cf, branch codex/a24-simulator-handoff-20261016, 로컬 미커밋/미게시다. 과학 worker 종료/공유잠금 반환 후 봉인한다. 새 실측/물리fit/PPO/과거완료재시작/자동추가·재시도·채택/게시0이다. 다음은 결과/현재 diff 검토와 사용자 후속 지시 대응이다.
''')
print('REPORTS_WRITTEN',calls-exact,'EVAL errors',len(rem['TRAIN_errors']),'TRAIN errors')
for s in summary:print(s)
