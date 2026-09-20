# SERVICE-MODEL-V2-DESIGN — 2026-09-20

판정은 **BLOCKED_MISSING_TELEMETRY**다. Host 설계/분석 구현과 simulation 승인 상태를 구분한다. 기존 transition_mean 실패는 보존하며 모든 기존 holdout을 consumed development로 등록한다. 새 ADB 측정·scheduling simulation·formal 실행은 없다. 신규 프로토콜의 파라미터나 승인된 simulation input은 아직 없다.

## 기존 실패와 선택

이전 holdout16세션/260요청의 MAE39.07ms, WAPE6.10%, coverage80.38%는 변경하지 않는다. classification CPU cold와 직후 coverage50%이며 cold 직후와 runtime 전환 직후를 pooling한 것이 구조적 오류다. 기존 두 번째381.316923ms의74.57%오차와 cold774.244ms는 별개 관측으로 유지한다. 작은 session 표본의 empirical Q05..Q95는 finite-sample 90% 보장이 아니다.

비교 A=task/backend 평균, B=origin별 first/early/warm 후보, C=B+setup/active 분리 및 co-run/완료경계 층, D=C+직전 task/backend 전체 setup matrix, E=C의 session-balanced joint empirical, G=warm cell mean×pooled origin multiplier. F는 E에 덧붙이는 session-level split-conformal 보조구간이며 별도 평균모델이 아니다. C/D의 point는 같은 행의 setup+active 평균으로 계산하므로 합산값만으로 분해의 인과적 타당성을 주장하지 않는다. 모든 비교는 개발용 leave-one-session-out이고 승인 검증이 아니다.

**선택 구조: C+E**. 현재 관측된 문맥별 `(setup, active, inference)` joint block을 같은 세션에서 함께 보존한다. session을 균등하게 선택하고 그 block의 호출 순서를 보존한다. 서로 다른 요청의 setup과 active를 독립 sampling해 가짜 조합을 만들지 않는다. 구현의 empirical_draw는 관측 조회만 하며 시간 진행/완료/정책 실행이 없다. 실제 다중 worker의 상관은 세션 전체 trace block으로 유지해야 하며 현재 state별 조회 함수를 scheduler에 바로 연결할 수 없다. 미관측 상태·idle 범위·동일 backend contention은 interpolation/fallback 없이 unsupported다.

D의 더 많은 parameter가 개발 MAE를 개선하지 않아 모델 복잡도를 늘리지 않는다. source task/backend는 trace에 계속 저장해 신규 설계에서 적합성 검증한다. G는 cold 비용의 task 차이를 과도하게 pooling한다. 계층적 random-effects 모델은 session별 추정 자유도에 비해 현재 sparse state 표본이 부족하며 추가 구현을 선택하지 않는다. 모델 비교의 support/MAE/WAPE 및 전체 fold는 외부 candidate_comparison.json에 있다.

## 타임라인 감사와 최소 계측 설계

| 경계 | task-profile-v3에서 확인 가능한 범위 | 최소 변경 설계 |
| --- | --- | --- |
| process/activity start | host wall-clock/context, logcat; 정확한 request monotonic 경계와 연결 불가 | probe process UUID, process-start 관측값의 출처, Activity.onCreate 최초 elapsedRealtimeNanos 기록; 실제 fork시각과 혼동 금지 |
| model loading/verification | 요청 이전 ProbeModelFile.open, summary에 제외 사실만 표시 | hash/open/map 시작·종료, label/anchor load 각각 span |
| runtime construction | prepare_ns aggregate | runtime UUID, owner worker, create begin/end, source/destination cell |
| delegate/interpreter/allocate | ProbeRawSession의 progress hook은 존재하나 ProbeTaskAdapter가 null로 호출 | 기존 ProbeProgress 연결 또는 가벼운 monotonic span sink; nested span parent ID |
| first/second/subsequent | worker별 key 변경 및 호출 ordinal 재구성 가능 | runtime UUID별 invocation ordinal, 첫 생성 origin과 recreate origin 분리 |
| invoke | inference_ns는 runForMultipleInputsOutputs 구간만 | 시작/종료 timestamp도 기록; output buffer 할당·readback 별도 |
| preprocess/decode/postprocess | service-prepare-inference 안에 혼합 | PNG read/hash/decode, resize/tensor, output decode/serialize span |
| warm steady | ordinal/idle/변동성으로 기술 가능; 인과적 안정화 증명 없음 | warmup 이벤트도 삭제 없이 보존; qualification protocol 별도 |
| backend transition | prepare_ns에 이전 close+새 create 혼합 | close와 create를 별도 span, source/destination task/backend, resident 여부 |
| runtime close | 최종 cleanup 수행은 확인, 시간 없음 | interpreter/delegate close begin/end 및 failure 기록 |
| completion/worker release | normal은 persist까지, urgent는 output_ready; terminal 뒤 event 저장과 gate release가 남음 | result completion, terminal write, worker-release/gate-release timestamp 구분 |

`service_ns = prepare_ns + active_service_ns`로 기존 자료를 정확히 분해할 수 있다. active는 inference만이 아니라 IO/preprocess/postprocess/normal persistence를 포함한다. setup은 기존 close와 create가 합쳐진 관측값이며 순수 GPU 전환 penalty가 아니다. session preloading 비용은 별도 startup ledger로 보고하고 steady 요청에 다시 더하지 않는다. worker 점유시간은 urgent completion보다 길 수 있으므로 새로운 release 계측 없이 queue 응답을 정확히 재생할 수 없다.

새 telemetry 제안 버전은 task-profile-v4다. 기존 v3 parser/의미/원자료를 수정하지 않는다. span은 session/runtime/request/parent UUID, name, start_ns, end_ns, requested/actual backend, owner thread를 갖는다. 음수·역순·부모 범위 밖·겹치는 exclusive segment를 거부한다. host가 full delegate 로그를 확인하기 전 GPU actual을 확정하지 않는다. 실패·exception cleanup도 partial span과 terminal ledger에 남긴다. production source는 이번 단계에서 변경하지 않았다.

## 안정화 분석과 상태 계약

외부 stabilization.json은 모든 session/runtime episode의 호출번호별 total/setup/active/inference와 request ID를 보존한다. 최소6호출 episode에서 log(active)에 대해 k=0..5 초기호출별 자유평균+나머지 일정평균의 BIC를 비교한다. 이는 개발자료의 기술적 change-point이며 현재 요청 지연을 본 뒤 상태를 바꾸는 분류기가 아니다. 입력·priority·idle가 섞여 있고 transition episode는3호출뿐이므로 긴 tail 안정화를 입증하지 못한다.

- first 종료: 해당 runtime 첫 invocation의 실제 terminal/worker release. 새 runtime first와 process 첫 runtime을 구분한다.
- early: 일단 두 번째 호출을 별도 관측 상태로 고정한다. process-first 직후와 recreated 직후를 합치지 않는다.
- 3회차 이상은 **warm_candidate**, 검증된 warm으로 자동 승격하지 않는다. 개발 BIC가3~6 등으로 달라져 모든 cell에서2회 warmup이면 충분하다는 결론을 내리지 않는다.
- 신규 calibration에서 각 cell/origin별 10회 연속 동일 이미지·priority, 이어20 canonical 이미지의 순서고정 sweep을 분리한다. CPU→GPU→CPU의 각 segment도10회로 늘려 전환 후 안정화를 확인한다. 48요청/120초 bound 내에서 독립 세션으로 분리한다. 이는 다음 버전의 제안 workload이며 지금 실행하지 않는다.
- 종료규칙 후보는 개발 calibration에서 정한 K 이후 연속5호출의 median drift와 상대 spread가 같은 cell의 이미 안정된 tail 변동성 상한 이내인 최소 K다. K와 상한은 **새 holdout 전** 고정한다. 새 holdout 중 K를 늘리거나 실패 호출을 warmup으로 재분류하지 않는다. K를 찾지 못하면 해당 cell warm 미지원이다.
- 지금은 K와 idle-resume 허용범위를 확정할 telemetry/균일 trace가 부족하다. cell별 규칙 차이는 새 calibration에서 결정하며 기존 실패를 통과시키려는 사후 상태 세분화에 사용하지 않는다.

## 승인 지표와 표본 수

시뮬레이터의 목적은 분포 sampling이므로 주 지표는 독립 session별 mean/median/P95 오차, cell/origin/context별 Wasserstein(기준 mean으로 정규화), training P95 초과 tail probability다. KS는 효과크기로만 보고하며 상관된 request를 iid로 놓은 p-value는 사용하지 않는다. setup/active의 joint 분포와 직렬상관도 유지한다. session block bootstrap으로 불확실성을 보고하며 bootstrap seed도 사전 고정한다.

긴급 P95에는 tail quantile 오차가 직접 영향을 준다. deadline miss에는 frozen deadline에서 CDF/tail probability 오차가 중요하다. 일반 완료율에는 mean/service capacity뿐 아니라 failed/rejected/expired 및 queue 점유시간이 중요하므로 완료요청 latency만으로 승인하지 않는다. 서비스분포 적합성만으로 전체 scheduler queueing 품질 보장을 주장하지 않는다.

Scheduler가 PI를 사용하면 **90% 기준 유지**: 고정 fit predictor에 대해 독립 calibration session마다 계획된 모든 요청의 최대 정규화 절대잔차를 하나 계산한다. rank=ceil((m+1)×.9), rank>m이면 infinite/unsupported로 처리하며 임의 유한구간을 만들지 않는다. exchangeable session이라는 가정 아래 session block의 marginal 보장이지 cell별 conditional 보장이 아니다. family별 적용 시 각 family에서 독립 score가 필요하다. 고정 predictor를 score fitting에 다시 학습시키지 않는다. m≥9는 단지 유한 가능 최소, m=99는 rank resolution≤1%일 뿐 정확성 보장이 아니다. calibration 범위 밖 무한/무익한 interval은 승인하지 않으며 폭의 허용값은 deadline 의사결정 목적과 함께 사전 고정해야 한다. [finite-sample 근거](https://arxiv.org/abs/2107.07511).

PI를 사용하지 않는 empirical simulator에서도 이번90% 실패 기록을 삭제하지 않는다. 외부 uncertainty_analysis.json의 nested session split F 결과는 개발 민감도이며 protocol 이질성·미지원 group 때문에 통계적 보장이나 새 holdout PASS로 해석하지 않는다.

기존 MAE≤432.808616ms/WAPE≤43.191436%를 느슨하게 바꾸지 않는다. 다만 이 넓은 기준만으로 긴급 P95나 deadline 차이를 구별할 수 없으므로 충분한 승인조건으로 사용하지 않는다. 최종 분포 equivalence margin/PI width는 **calibration_pending**: 공통 urgent P95 효과크기·허용 miss-rate 차이·일반 완료율 하한이 먼저 고정되어야 한다. 기존10%/2%p는 계획의 미승인 참고값이며 자동 SLA로 승격하지 않는다.

표본수 산출은 sample_size.json에 공식·입력·결과를 남긴다. 8 family=4 solo cell+2 task transition+2 co-run orientation. 다음 숫자는 실행 승인/최소 측정 요구가 아니라 엄격한 통계 보장의 비용을 보여주는 계획 상한이다.

1. 성공=session의 모든 계획 요청이 PI에 포함됨. H0 p≤.9, 대립 p=.95(가정), power≥.8, familywise alpha=.05/8의 정확 binomial 설계: family당322세션,303성공 이상; power≈.8105. 이 simultaneous-session 기준은 기존 request90%보다 강하며 둘을 같은 지표로 바꾸지 않는다.
2. session 평균 request coverage를±5%로 추정하는 distribution-free Hoeffding 동시 bound: ceil(log(2×8/.05)/(2×.05²))=1154/family. 이는 보수적 충분조건이지 통계적으로 최적인 최소값이 아니다.
3. 기존 session별 cell/state 평균의 CV와 동일 alpha, 상대mean precision5%를 이용한 정규근사 n=(z×CV/.05)²도 계산한다. 작은·이질적인 기존표본이므로 새 프로토콜의 보장으로 쓰지 않는다. 상태별 session 수가 JSON에 있다.
4. 위 보장들을 모두 요구하면 max=1154/family, 총9232 완료세션. 기존 host 실패2/23의 단측95% Clopper–Pearson 상한≈24.925%를 보수적 dropout 계획값으로 사용하면 기대 완수 기준1538시도/family다. 이것은 높은 확률의 완수 보장이 아니며 무제한 retry를 허용하지 않는다. 실제 device 실패와 전송 복구는 따로 기록한다.

이 규모를 단순히16으로 줄여 충분하다고 할 수 없다. 연구 일정에 과도하므로 지금 수천 세션을 실행하도록 계획을 승인하지 않는다. 다음 bounded instrumentation calibration으로 exchangeability/family pooling 가능성 및 session 분산을 확인하고, 사용자 서비스 목적에 필요한 정밀도를 먼저 정해야 한다. 그 후 한 번만 sample-size/design을 승인 holdout 전에 재동결한다. 이번 결과에 맞춰90%를80%로 낮추는 방법은 허용하지 않는다. 독립성은 session 단위지만 동일 기기 연속 실행의 drift가 사라지는 것은 아니므로 block/time 기록과 gate를 유지한다.

## 공정한 paired CPU 대조

CPU-only는 CPU classification+CPU detection 두 runtime을 **상주**시키고 global permit1로 직렬 dispatch한다. co-run은 CPU classification+GPU detection 두 runtime을 동일 방식으로 사전 생성하고 permit2로 허용한다. runtime slot 수와 concurrency를 분리해야 하므로 기존v3 runner로는 실행할 수 없다. GPU owner-thread 원칙을 유지하며 CPU 동시실행은 허용하지 않는다. 반대 task orientation은 별도 pair다.

양쪽 model bytes/residency, runtime별 warmup K, image/hash/priority/task mix, seed, 요청수, 예정 도착기록, deadline 후보, 초기 thermal0, 전경/화면/충전/background 관측 조건, 출력 검증 및 artifact 회수 절차를 같게 한다. setup/initial warmup은 모두 ledger로 별도 보고하며 한쪽에만 비용을 청구하지 않는다. background 다른 앱에 접근하지 않고 프로젝트 상태와 공개 system pressure만 기록한다. system noise가 같다고 가정하지 않는다.

pair를 한 block으로 하며 seed20260921로 block별 AB/BA를 균형 배정한다. 양 arm 사이 thermal0와 memory gate를 다시 확인하고, gate 실패는 missing pair/실패 ledger로 남긴다. 정확한 UUID는 실제 실행계획 생성 시 새UUID로 할당하고 output root 재사용을 거부한다. arrival schedule의 hash는 pair에서 동일해야 한다. 비교는 pair차이의 urgent P50/P95, normal 평균/마지막 완료, makespan, throughput, deadline violations, sampled PSS/thermal 및 모든 terminal state다. 전체와 warm segment를 따로 보고한다.

기존n2 대조는 runtime residency 혼입 때문에 새 paired-effect variance의 신뢰 가능한 입력이 아니다. paired control의 확정 표본수는 새 공정한 pilot pair차이 분산과 사전 최소효과/precision에서 산출한다. 현재는 정확한 누락 조건으로 남기며 n2의 효과크기를 power계산에 전용하지 않는다. 기존 양쪽 완료율100%, GPU 이점/무익함 확정 없음, A24 CPU-solo-dominant 및 네cell PASS_EQ는 유지한다.

## Memory admission / thermal / 품질

318,364kB는500ms **sampled** PSS 최대다. 현재 Activity snapshot은 Debug.MemoryInfo만 사용한다. ActivityManager.MemoryInfo의 availMem/threshold/lowMemory와 memoryClass/largeMemoryClass는 새 probe에서 수집 가능하나 기존 artifact에는 동기화된 값이 없다. memoryClass는 Java heap 특성으로 전체 native/GPU PSS 상한에 대입하면 안 된다. [공식 MemoryInfo](https://developer.android.com/reference/android/app/ActivityManager.MemoryInfo), [공식 메모리 관리](https://developer.android.com/topic/performance/memory/manage-app-memory).

제안 gate는 요청 admit 전 동일 monotonic timestamp에서 thermal==0, !lowMemory, fresh snapshot을 확인하고 `availMem-threshold > incremental_PSS_upper + pressure_reserve` 및 `javaMax-javaUsed > java_increment_upper+java_reserve`, 현재PSS≤calibrated resident envelope를 모두 요구한다. 이미 상주한 runtime은 두 번 더하지 않는다. 별도 setup 동시성 비용·작업 중 증가량과 snapshot 간 압력 하락량을 새 calibration에서 기록해 upper/reserve를 정한다. upper는 관측/통계 envelope이며 OOM 불가능 보장이 아니다. 미계측·stale·미검증 estimate면 fail closed다. monitor가 gate를 잃으면 신규 admit 중단, 실행 중 native 호출은 강제 중단하지 않고 bound 종료와 terminal 기록을 유지한다. 범위는 A24 thermal0·동결 residency/workload뿐이다.

thermal0를 throttling 부재나 다른 thermal 상태/장시간/에너지로 일반화하지 않는다. backend numerical, decoded equivalence, 실제task accuracy, scheduling quality preservation을 분리한다. 기존20장 동등성은 accuracy GT가 아니다. 네 검증cell만 사용, raw1e-4+1e-3×abs(reference), decoded score.001/box2px/label-order 동일 유지, silent fallback 금지. 같은 backend contention은 미승인이다. failed/rejected/expired/cancelled/unfinished도 전체 도착 분모에 남긴다. 다섯 baseline은 향후 같은 input hash를 사용한다.

## 사전 동결 순서와 다음 명령

1. 최소v4 계측·resident CPU serial gate 구현 후 JVM/build/lint 및 schema/span tests. 새APK hash를 승인 계약에 결합한다. 이번 Android source/APK는 변경하지 않았다.
2. 새 bounded instrumentation calibration을 별도UUID/output으로 수행할 계획을 먼저 확정한다. 위 구조·state qualification·paired 조건·seed·quality·thermal/memory 수집을 적용한다. 기존52 profile session은 전부 consumed registry로 금지한다.
3. 새 calibration에서 K/idle 범위/parameter estimator/joint distribution/score split/PI폭·분포 acceptance margin·정확session 수·workload·task balance·paired count·memory bound/deadline 상태를 확정한다. fit/score/holdout session은 완전 분리한다. script/schema/APK/model/input hash와 timestamp를 Git checkpoint에 결합한 뒤에만 새로운 untouched holdout을 생성한다. 판정 실패 시 모델·기준 수정 없이 실패 보존한다.

현재 실행 가능한 명령은 host-only `python -m tools.d1_service_v2 analyze --bundle <기존service_model_v1> --final <FINAL-CALIB root> --output <새V2 root>`와 `validate/no-op/dry-run --output <V2 root> --expected-sha256 <design hash>`다. **다음 실기기 명령은 아직 발급 불가**: 현APK/runner는v4 span·resident CPU 대조·memory gate를 구현하지 않아 기존 profile_device.py 명령으로 목표를 충족할 수 없다. 없는 옵션/runner의 ADB 명령을 재현 명령으로 꾸미지 않는다. 다음 행동은 위1번이며 이후 구현된 runner의 정확한 bounded 명령과 새hash를 동결해야 한다.
