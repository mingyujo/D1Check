# Empirical calibration protocol amendment v1

2026-09-21. 상태: **EMPIRICAL_CALIBRATION_PLAN_INCOMPLETE**. Host 설계·동결 산출물이며 기기 실행 승인이 아니다. `tools/d1_empirical_plan.py`는 ADB나 simulator 실행 기능이 없다.

## 목적과 이전 실패

기존 transition_mean은 독립 holdout coverage80.384615%로 사전90% 기준에 실패했다. MAE39.07ms/WAPE6.10%, cold 및 직후 coverage50%, 최초774.244ms와 두 번째381.316923ms의74.57%오차를 보존한다. 기존 모델·평가기·frozen threshold·보고서는 변경하지 않는다. 기존52 profile UUID(검증51세션559요청과 host실패9요청 시도), 과거 holdout 및 v4 smoke4세션18요청을 모두 consumed development로 등록한다. 새 승인용 자료로 가져오거나 UUID만 바꾸는 replay는 금지한다.

새 목표는 요청별 예측 정확도가 아니라 긴급 P95·deadline violation·일반 완료율·makespan·throughput·memory admission·thermal 적용 범위와 backend/순서 선택의 상대 성과를 평가할 수 있는 **관측 범위 내 공동 분포**다. Scheduler 인터페이스는 PI를 입력으로 받지 않는다. 따라서 이 새 empirical protocol의 SIM-01 gate에서 request-level PI90%를 제거한다. 이전 실패 기준을 완화하거나 통과로 바꾸는 것이 아니라 새 자료에만 적용되는 protocol amendment다. 향후 PI 기반 정책을 도입하면 별도 사전 검증 계약이 필요하다. 분포 검증·독립 세션 검증·품질·deadline gate는 제거하지 않는다.

## 입력 구조와 적용 범위

계획 `empirical-calibration-plan-v1`, 입력 block `joint-empirical-session-v1`, 원시 telemetry `task-profile-v4/schema1`을 구분한다. Block은 원래 manifest, 전체 event, 검증 receipt, terminal outcome, provenance SHA를 함께 가진다. setup/active/inference/worker occupancy/queue wait, memory snapshot/admission, thermal 및 두 worker의 overlap은 같은 session의 원래 시계열이다. 원본 artifact 재검증 후 전체 block을 선택한다. 개별 setup·active·메모리·slowdown을 독립 추출하거나 다른 session 값으로 교체하면 거부한다. Setup은 runtime당 한 번만 부과하며 요청별 중복 가산하지 않는다.

실측은 service block을 제공하고, 미래 simulator는 arrival/task mix/urgency/deadline/정책 결정을 만든다. 두 영역을 연결하려면 task/backend/priority/runtime origin/input/동시 실행 시작 상대 위치가 관측 block과 호환돼야 한다. 일치하는 block이 없으면 unsupported다. Co-run의 한 arm만 따로 뽑거나 겹침 길이를 임의로 늘리는 것은 허용하지 않는다. 따라서 현재 계획의 동시 offset0 pair만으로 임의 staggered overlap·burst·지속 부하를 검증했다고 할 수 없다. 새 도착을 생성해도 서비스 분포의 미측정 조건을 만들어서는 안 된다. CPU 동일 backend 병행도 지원하지 않는다.

메모리 gate 거절은 admission rejection 또는 deferred로 기록하고, deferred는 별도 terminal이 아니라 대기 상태다. drain 종료까지 미완료면 unfinished, deadline이 확정된 경우 만료 규칙에 따라 expired로 집계한다. 실패·거절·만료·미완료는 전체 도착 분모에서 빠지지 않는다. 성공 block만 지원 분포를 채우며 실패 ledger는 따로 계속 보존한다. Admission 실패 block을 성공 latency 표본으로 사용하지 않는다. 실패율·admission율은 전체 계획 시도 기준으로 함께 보고한다. Silent fallback·미지원 backend·미측정 thermal 생성 금지.

Numerical equivalence, decoded equivalence, 실제 task accuracy, scheduling quality preservation은 별개다. 기존 golden 허용오차를 그대로 사용하고 임의 정확도를 생성하지 않는다. 이번 최소 입력은 canonical 이미지00575b9132bb3746 반복에 한정된다. 20장 정확도나 unseen-image 일반화가 아니다. Cold/early 측정은 normal 완료경계이며 urgent cold로 무조건 전용하지 않는다. 동일 trace의 output_ready/worker release 양 경계를 사용하는 추가 호환성 검증 전에는 해당 urgent cold 조건이 unsupported다.

## 상태·workload와 정확한 누락

| Family | 개수 | session 내부 설계 |
| --- | ---: | --- |
| Solo task/backend | 4 | runtime1개, 총12호출 |
| Task별 CPU→GPU/GPU→CPU | 4 | 같은 process/session에서 source12호출→release/close→target construction/setup→target12호출 |
| Resident CPU serial / CPU+GPU | 2 | 두 runtime 사전 생성, 각6 warmup+6 active, 총24호출 |

호출1 cold_first,2 early_after_cold,3~6 stabilization,7~12 warm_candidate다. 기존 trace의 안정화 시작2~6 분산에 따라6회를 관측 구간으로 두었으며 7회부터 자동 warm 승인하지 않는다. 각 cell/origin에서 calibration session-bootstrap으로 median(10~12)/median(7~9)의95% CI 전체가[0.9,1.1]에 들어가야 warm을 지원한다. 아니면 ordinal 상태만 유지하고 warm 계약은 incomplete다. 결과를 보고 K를 탐색하거나 늘리지 않는다. Origin은 process-first와 transition-after-setup을 구분한다.

**현재 APK는 lifecycle/resident_cpu_serial/resident_corun만 허용한다.** 같은 session 내 close/recreate 전환 실행경로와 대응 validator는 없다. resident 선택 변경이나 두 session 접합으로 전환 계측을 대체하지 않는다. 전환4 family는 논리 계획으로만 생성하고 execution_supported=false다. 필요한 최소 변경은 v4의 명시적 transition 구성, source-release/close 이후 target-create/ready 및 phase별 workload 경계, 원래 session identity 보존, host validator와 bounded smoke다. 기존 APK hash가 고정돼 있으므로 구현 후 새 APK/hash를 포함한 새 amendment를 **신규 empirical 자료 전에** 동결해야 한다. 이번에는 Android 코드를 바꾸지 않았다.

지원6 family에는 native v4 manifest catalog를 생성한다. 새 UUID는 seed/phase/family/replicate로 결정되는 UUIDv5이며 consumed registry와 대조한다. 결정적 재생성이 같은 UUID를 만든다는 것은 재실행 허용이 아니다. 실제 실행 ledger에 한 번 들어간 UUID는 다시 실행할 수 없다. output root는 sessions/UUID, session120초, 총48요청 상한, 동일 APK/model/전처리/decoder/이미지, 시작thermal0와 매 admission memory gate를 유지한다. 실행 후 artifact hash 검증과 project force-stop/프로세스 종료 확인이 필수다.

## 표본 수와 bounded 예산

기존51세션559요청에서 cell/state별 **session 통계**를 사용한다. 최악 CV=.456488(분류CPU process-first early,16session), cold CV=.269911(19), warm CV=.040806(16)이다. 이질적 과거 설계를 새 v4의 분산 보장으로 쓰지 않는다. 새 smoke는 setup/active 구조를 확인한4session뿐이고 공정한 pair는1개라 paired variance 추정 불가다. 기존2대조는 runtime 재생성 혼입 때문에 효과크기/power 근거로 사용하지 않는다.

평균의 탐색적 상대 반폭 h에 대한 정규근사 ceil((1.96×CV/h)^2)를 AB/BA 균형을 위해 짝수로 올림한다. h=.35이면8회, h=.25이면14회/family/phase다. 이는 평균 근사이고 P50/P95 보장이 아니다. 후보는 다음과 같다.

| 설계 | calibration | independent validation | 전체 |
| --- | ---: | ---: | ---: |
| 최소·선택된 탐색 계획 | 8×10=80 | 8×10=80 | 160 |
| 권장 변동성 탐색 | 14×10=140 | 14×10=140 | 280 |

경진대회에는160회 상한의 탐색 계획을 선택하되 현재 **실행 승인/승인 검증에 충분하다는 판정은 보류**한다. 각 phase에8개 fair pair를 포함한다. 기존 host문제2/23의 단측95%상한.249249를 보수적 dropout proxy로 사용해 ceil(8/(1-p))=11시도/family/phase, 전체220 UUID를 예약한다. 자동 retry는 없고, reserve 사용 전 실패 사유와 새 ID 선택을 기록하는 실행기 규칙이 필요하다. Pair 한쪽 실패면 pair 승인 거부, 성공 arm도 비교에서 단독 재사용하지 않는다. 현재 coverage validator는 reserve 대체 승격을 지원하지 않으므로 reserve는 미실행 예약이며 자동 성공 채우기가 아니다.

160×120초=5시간20분의 device 상한, host overhead30초/회는 **가정**으로 더하면6시간40분, reserve 포함220회는9시간10분이다. 쿨다운은 별도이며 gate 미충족 시 무한 대기하지 않고 중단한다. 권장280회는 overhead 포함11시간40분이다. 실제 추정시간은 v4의3~6요청 smoke를12~24요청으로 단순 선형 외삽해 보장하지 않는다.

Cold처럼 session당 한 표본이면 population P95 위에 표본 최대가 올 확률95%에만도 n≥ceil(log(.05)/log(.95))=59가 필요하다. 이것도 양측 CI폭 보장이 아니다. n8의 해당 확률은 약33.7%, n14는51.2%다. 수천 회로 보장하려 하지 않으며 표본이 적은 cold P95를 확정값으로 승인하지 않는다. 따라서 bounded 계획만으로 모든 P95 승인 요구를 충족한다고 선언할 수 없다. `legacy_uncertainty.json`은 seed 고정2000회 session bootstrap, session별 quantile 평균과 equal-session mixture quantile을 명확히 구분해 기록한다. request 수를 독립 n으로 세지 않는다.

## 신규 자료 이전에 고정한 승인 규칙

아래 값은 기존 실패 coverage를 통과시키기 위한 조정값이 아니라 **새 프로토콜의 engineering tolerances**다. 정책 효과가 이 오차보다 작으면 순위 확정 근거가 되지 않는다. 오류 누적이 비선형인 queue에서 service-level 기준이 운영 KPI 정확도를 자동 보장하지 않으므로 추후 독립 trace/KPI 검증도 필요하다.

- Artifact/provenance/필수event/출력 동등성100%, 모든 계획 cell/state 지원, 두 arm 완전한 pair, memory gate 재계산 일치 및 thermal0.
- Calibration/validation UUID·request/runtime identity 겹침0. calibration만으로 empirical catalog/deadline/state qualification 동결 후 validation 시작. 결과를 보기 전 timestamp/commit/hash/실행 ledger로 순서를 입증한다. validation은 재학습이나 K 선택에 쓰지 않는다.
- Equal-session mixture median 상대 drift≤10%, P95≤20%, calibration median으로 나눈1-Wasserstein≤10%, 사전 deadline 후보에서 CDF 절대차≤5%p. KS는 descriptive이며 request-iid 유의확률을 제시하지 않는다.
- 2000회 session-cluster percentile bootstrap95% CI의 full width/point: median≤20%, P95≤40%. Pair contrast는 pair단위 bootstrap. 모든 cell/origin/완료경계를 별도 평가하고 missing/작은 n/zero denominator면 incomplete다. 유한 cold P95 rank evidence도 별도 표시한다. CI를 계산할 수 있다는 이유로 tail이 식별됐다고 승인하지 않는다.
- PI90% 및 기존 MAE/WAPE를 새 필수 gate로 사용하지 않는다. 기존 평가 결과는 그대로 실패다. 새 기준의 실패를 숨기거나 새 validation 결과를 본 뒤 tolerance·interval폭·표본 수를 바꾸지 않는다.
- Median/점유시간은 makespan/throughput/일반 완료율, P95는 긴급 tail, CDF는 deadline violation과 연결된다. 메모리 거절·실패 accounting은 완료율 분모를 보존한다. Paired 효과 CI가0을 포함하면 우월성 미입증. 다중 비교 exploratory 성격을 공시하며 유리한 task/조건만 보고하지 않는다.

동결 plan에 수치와 계산법을 저장했다. 현재 도구는 계획/원본 block·coverage validator, 불확실성 분석 및 stratum별 distribution_gate(median/P95/Wasserstein/CDF/CI폭)를 구현했다. 신규 자료 ingestion에서 source 검증·state별 grouping·전환경로·reserve 사용 ledger와 최종 승인 orchestration은 아직 연결되지 않았다. 운영 KPI evaluator는 본 simulator 구현 전 별도 검증 대상이다. 이를 모두 완료한 것처럼 READY로 표시하지 않는다.

## 공정한 pair·memory·thermal

Pair 두 arm은 동일 seed/task mix/offset0 arrival/요청 수/이미지/warmup/thermal0/deadline null, setup 밖 active, 두 runtime residency 원칙을 사용한다. CPU serial 한 lane과 CPU+GPU 두 lane만 다르다. 매 pair AB/BA를 사전 균형 배치하고 두 arm은 연속 실행, 시작 gate 재검사·배터리 온도 drift·background 조건을 기록한다. 다른 앱을 제어하지 않으며 background 변화는 관측 confound다. CPU solo 우세를 반영하지만 GPU 이익은 새 fair pair로만 판단한다. 한 쌍이나 이 탐색 계획만으로 통계적 power를 주장하지 않는다.

동적 gate는 기존 `android-low-memory-resident-v1`: thermal0 && !lowMemory && availMem-threshold > max(threshold, observed_peak_process_PSS). availMem/threshold/lowMemory/process PSS/runtime0·1·2 PSS/sampled peak/decision/reason을 같은 block에서 읽는다. Simulator는 관측 footprint/결과를 사용하며 미래 압력 시계열을 임의 생성하거나 runtime footprint를 독립 합산하지 않는다. gate 실패는 reject/defer, 미측정 headroom은 생성하지 않는다. 326,254KiB는 sampled peak이지 절대 최대·안전 상한이 아니다. Thermal 적용은 status0뿐이다.

## Deadline 규칙

계속 calibration_pending이다. Calibration equal-session weighted quantile로 task/context별 urgent Q50/Q75/Q90/Q95, normal Q90/Q95/Q99 후보를 계산한다. 주값은 urgent Q90/normal Q95지만 전 후보를 공개하고 validation에서 유리한 값을 선택하지 않는다. Cold를 포함하며 cold-start scenario는 setup을 runtime당 한 번 더한다. urgent output-ready와 normal persistence/worker occupancy를 혼합하지 않는다. Q99는 관측 경험 quantile일 뿐 population99 보장이 아니다.

민감도는 각 후보×{.75,1,1.25}로 고정한다. Calibration matched arm에서 적어도 한 후보의 CDF가(.1,.9)에 있어야 discrimination 가능 후보로 인정한다. 그렇지 않으면 pending을 유지하며 범위를 임의 확대하지 않는다. 모든 deadline을 service보다 크게 보장하지 않는다. 이것은 사용자 SLA가 아니라 engineering sensitivity다. 미래 큐/arrival까지 포함한 절대 운영 SLA 승인은 별도다.

## 재현과 정확한 다음 행동

`python -m tools.d1_empirical_plan generate --development <V2 artifacts> --smoke <v4 resume root> --output <새 root>`

`python -m tools.d1_empirical_plan dry-run --output <동결 root> --expected-sha256 <freeze.json SHA256>`

`freeze.json`은 계획·consumed registry·manifest catalog·분산분석·no-op hash를 고정하고 analysis/schema hash도 결합한다. 두 독립 output root에서 동일 bytes를 확인한다. 문서와 Git checkpoint는 외부 최종 provenance에 연결한다. 기존 데이터·APK hash를 재검사하며 본 ADB/측정/시뮬레이션은 없다.

**현재 유효한 다음 A24 실행 명령은 없다.** Smoke 실행기를 calibration용으로 다시 실행하지 않는다. 먼저 같은-session transition 및 native manifest/분리 실행 ledger, validation 통계 실행기와 tail scope를 완성하고 새 APK/계약을 freeze해야 한다. 그 이후 별도 승인된 bounded instrumentation smoke→calibration 명령을 제공한다. 현재 실행 가능한 명령은 위 host dry-run뿐이다.
