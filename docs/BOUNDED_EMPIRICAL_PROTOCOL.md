# Bounded descriptive empirical protocol v1

2026-09-21. **계획 READY는 측정 완료나 SIM-01_READY가 아니다.** 이전160/280세션 계획은 채택하지 않는다. 사용자 지정 총30세션으로 관측 경험분포와 제한된 정책 상대비교를 준비한다. 기존 계획·동결hash·보고서는 그대로 보존한다.

## 범위와 방법 변경

Galaxy A24 SM-A245N, 현재 EfficientNet-Lite0 분류/ EfficientDet-Lite0 탐지, Telemetry v4, thermal status0, 검증된 CPU/GPU cell에 한정한다. 모든 스마트폰/온디바이스AI 일반화·정확한 모집단 cold P95·개별요청90%예측 보장·GPU 보편 우월성을 주장하지 않는다. 관측 P95나 작은 표본 bootstrap은 descriptive다.

이전 transition_mean 독립 holdout coverage80.38%<90% 실패, 74.57%오차, cold774.244ms, consumed holdout, 검증51세션559요청, 별도실패9요청, v4 smoke4세션, 기존 formal80슬롯은 그대로다. 새 protocol 성공으로 재해석하지 않는다. 기존52 profile session과 smoke4는 consumed registry로 차단하며 calibration 입력으로 재사용하지 않는다. 이전 predictive/분포precision 계획의 결과는 역사적 상태로 남기고 이 새 버전에 소급 적용하지 않는다.

160/280세션은 정밀도/분포 승인 목표에 맞춘 탐색 후보였으며 대학생 프로젝트의 제한적 운영성과 비교에는 과도했다. 이번에는 그 통계적 보증을 주장 범위에서 제거하므로 독립holdout80·cold population P95 rank gate·CI폭 gate를 요구하지 않는다. LOSO는 독립 holdout이 아니다. 실패 예측모델을 통과시키기 위한 threshold 변경이 아니라 새 목적·scope의 명시적 개정이다.

## 정확한 30세션

| Family | 독립 session | session당 호출 |
| --- | ---: | ---: |
| classification CPU | 5 | 12 |
| classification GPU | 5 | 12 |
| detection CPU | 5 | 12 |
| detection GPU | 5 | 12 |
| resident CPU serial | 5 | 24 |
| resident CPU/GPU co-run | 5 | 24 |

총30session/480호출, 별도 holdout0. Solo20 + paired5쌍10이다. Seed2026092102, UUIDv5(namespace에 새 protocol 포함), session별 새 output root. 같은 seed로 재생성하면 같은 UUID가 되므로 이는 **재실행 허용이 아니다**. 실행시 frozen bundle에 exclusive execution.claim을 먼저 생성해 다른 output root로도 다시 실행하지 못하게 한다.

각 runtime의 고정 순서는 호출1 cold-first,2 early-after-cold,3~6 settling,7~12 warm_observed다. Native manifest는6 warmup+6 timed active이며 warmup event에도 실제 cold/early 값과 output-equivalence를 보존한다. Warm은 고정6호출 이후의 관측 상태이지 정적 분포가 보장됐다는 뜻이 아니다. Setup/active·queue/dispatch·worker-release·memory·thermal·terminal은 v4 그대로 수집한다. Input은 기존 golden의 canonical image00575b9132bb3746 반복으로 고정하며 unseen-image 정확도를 주장하지 않는다.

한 replicate마다 solo4의 순서를 seed로 섞고 paired 두 arm은 연속 실행한다. Pair 순서는 AB,BA,AB,BA,AB로3:2다(5쌍이라 완전1:1 균형 불가). A=두 CPU runtime 단일lane, B=classificationCPU+detectionGPU 각owner lane. 두runtime을 사전 생성·상주, 각6warmup, timed6+6요청은 task 교대로 offset0 arrival, 동일seed/task mix/input/전처리/model/count/thermal0/deadline null이다. 우선순위는 classification urgent/detection normal. 일반성을 늘리는 다른 mix/priority reversal은 후속 측정이며 이5쌍에서 검증한 것으로 쓰지 않는다.

## 실행 상한·실패

총 device 시작 최대30, session당 시작1회, **실기기 retry0·대체session0**. 30성공을 얻기 위해 실패를 빼고31회째 실행하지 않는다. ADB/host/artifact/thermal/memory/cleanup 실패 시 원자료·ledger를 보존하고 중단, DATA_INCOMPLETE다. Host 전송 복구와 Activity 재실행은 구분되지만 제공 실행기는 자동 복구/retry하지 않는다. 이미 실행한 session을 재사용하지 않는다. 후속 원자료 read-only 회수는 별도 기록된 작업이며 새 inferencing을 뜻하지 않는다.

각 session 기존120초 watchdog/host bound, 전후thermal/battery, requested/actual backend/full delegation, artifact SHA/provenance, output equivalence, force-stop 및 PID부재를 확인한다. 기존데이터 삭제·pm clear·uninstall·reboot·다른앱 제어 없음. 필요한 모델은 기존 로컬 검증 파일만 복사하며 저장소/APK에 포함하지 않는다. 기기 실행30회 최악60분에 설치·복사·쿨다운 시간이 별도 추가된다. 이는 실제 완료시간 보장이 아니다.

## Resident-only simulation v1

필요 runtime은 workload 전에 생성한다. Memory admission 통과한 runtime만 resident하고 workload 끝까지 유지한다. 요청은 해당 resident backend에만 배정한다. 동적 unload/reload·CPU→GPU 재생성 transition은 지원하지 않으며 필수 gate에서 제거한다. 미지원 전환 계획/manifest를 validator가 거절한다. Workload 전 setup과 resident backend 사이 dispatch/queue 영향은 남긴다. Admission 실패 backend는 사용 불가이며 unsupported/거절을 CPU silent fallback으로 바꾸지 않는다.

동적 gate는 기존 android-low-memory-resident-v1:

`thermal==0 && !lowMemory && availMem-threshold > max(threshold, observed_peak_process_PSS)`.

availMem/threshold/lowMemory/process PSS/resident0·1·2 PSS/sampled peak/decision/reason을 block에서 함께 보존한다. 326,254KiB는 sampled peak이지 절대 최대나 safe headroom이 아니다. 미관측 pressure·thermal 상태를 생성하지 않는다. Memory 실패는 reject/defer(대기는 terminal 아님), horizon/drain 종료까지 미완료면 unfinished다. 실패·거절·만료·미완료를 전체도착 분모에서 제외하지 않는다.

## Joint block·CRN·sensitivity

`bounded-descriptive-empirical-v1` plan/schema와 기존 `joint-empirical-session-v1` raw-source importer를 사용한다. 원래 session의 setup/cold/early/settling/warm/memory/thermal/terminal/interference 전체를 하나의 block으로 읽고 provenance를 검증한다. 파생 receipt 값도 raw event에서 재계산해 cross-session 필드 재조합을 거절한다. 두arm은 pair단위로 함께 추출한다. Setup은 runtime당 한 번, readback/decode/release는 공식 inference timer 밖이다.

Common random number ticket은 protocol/seed/replicate/scenario로만 결정하며 policy명과 policy 호출순서를 넣지 않는다. 각 정책은 같은 workload/arrival/deadline과 사전에 materialize한 같은 family별 block catalog, 같은pair ticket을 받는다. 정책이 다른 cell을 선택할 때 같은 숫자 latency를 강제하지 않고 동일 난수의 rank로 해당 호환 cell 경험분포를 선택한다. adaptive가 더 많은 난수를 소비해 뒤의서비스표본을 바꾸는 방식은 금지한다.

Low/central/high는 총worker occupancy가 최소/중앙/최대인 **실제 전체block**이다. Cold-stress는 cold+early active 합이 최대인 실제block이다. Pair는 두arm 합을 기준으로 전체pair를 선택한다. Setup최대와 active최대와 memory최대를 서로 다른session에서 조립하거나 임의배수를 cold값에 곱하지 않는다. 관측 support 안의 민감도이며 미관측 극단위험의 상한을 보장하지 않는다. 모든 정책에 같은시나리오를 적용하고 유리한 한시나리오만 보고하지 않는다.

관측 minimum/median/maximum, session-median bootstrap95%CI(2000회), leave-one-session-out 요약을 낸다. Pair metric은5개corun-minus-CPU 대응차·평균차·pair-bootstrap95%CI를 기록한다. 폭/부호가 불확실하면 inconclusive, CI가0을 벗어나도 관측방향일 뿐 보편우월성이 아니다. n5 CI의 불안정성을 공시하며 GPU 사용정책과 CPU-only를 모두 남긴다. 분포나 KPI 계산·simulator 실행은 이번 계획 단계에서 하지 않는다(합성 unit fixture 검증 제외).

서비스 block의 input/priority/runtime origin/overlap 조건과 호환되지 않는 dispatch는 unsupported다. Offset0 pair를 임의 staggered overlap에 외삽하거나 co-run arm을 독립 solo표본처럼 쓰지 않는다. Cold는 pre-workload 관측이라 warm steady 운영결과와 cold-start 전체비용 scenario를 분리한다. Simulator는 이 범위에서 arrival·urgency·policy를 만들 수 있으며 지원범위를 넘는 정책 action을 조용히 합성하지 않는다.

## Deadline와 baseline

Deadline=calibration_pending. 측정 후 CPU solo 참조경험분포를 task별로 고정해 모든정책이 공유한다. Urgent warm 후보는 Q50/Q90×{.75,1,1.5}. Cold 후보는 같은session의 setup+first(또는 early)service 합의 Q50/Q90×같은multiplier를 별도scenario로 만든다. cold/warm 필드를 독립 합성하지 않는다. Quantile은 관측 경험 quantile이며 population quantile 보장이 아니다.

Normal relative deadline은 `max(0,H-(arrival-first_arrival))+m*D_cpu`, m∈{.75,1,1.5}. H=공통workload의 마지막-첫도착, D_cpu=공통task sequence에 대한 고정CPU solo central block의 service demand 합이다. 정책실행결과로 D를 다시 계산하지 않는다. 모든deadline scenario를 사용해 deadline별 sensitivity를 보고하며 결과를 보고 범위/주deadline을 선택하지 않는다. 느슨한deadline만 만들어 성공을 보장하지 않는다.

새 baseline ID는 과거 B0~B3 의미와 혼합하지 않는다:

| ID | 정의 |
| --- | --- |
| FIFO_CPU | resident CPU-only, arrival순 단일lane |
| EDF_CPU | 같은CPU resident·단일lane, earliest absolute deadline; tie arrival/requestID |
| fixed_feasible_backend | 사전고정 feasible backend, FIFO; 혼합두task는 측정된CPU resident serial 기본 |
| static_task_backend | classificationCPU/detectionGPU resident 매핑; 관측co-run 범위만 병행 |
| adaptive | 같은resident capability/메모리/품질/비선점조건에서 합법action 선택; PI입력 없음 |

Fixed GPU는 solo 검증cell의 제한 대조군으로 가능하지만 **두GPU runtime residency/간섭은 측정하지 않았으므로 mixed fixed-GPU를 지원한 척하지 않는다**. Adaptive도 양모델×양backend4runtime 동시상주를 가정하지 않는다. Workload 시작 전에CPUserial 또는측정된CPU+GPU resident 구성을 선택하고, workload중에는 그구성의 resident cell만 사용할 수 있다. Solo GPU가 느리다고 GPU-use 대조군을 삭제하지 않는다. 정책 성능/본simulation은 후속단계다.

## 승인과 실행 명령

계획 승인: 정확30·cell5·pair5·사전manifest/hash/seed·retry0·joint identity·CRN·no-op 및 host테스트 통과. **데이터 승인:** 각solo5성공과완전5pair,artifact completeness100%,schema/identity/setup-active/quality/memory/thermal/cleanup/provenance 통과. 폭이좁은CI나populationP95·prediction90%·독립holdout을 요구하지 않는다. 실패한세션/partialpair가하나라도 있으면 데이터승인 미완료. 모든raw와실패ledger 보존.

재현: `python -m tools.d1_bounded_empirical generate --previous <이전 frozen root> --smoke <v4 resume root> --output <새 bundle>`.

Host확인: `python -m tools.d1_bounded_empirical dry-run --output <bundle> --expected-sha256 <freeze SHA>`.

**후속 별도승인 후 A24 실행:** `python -m tools.d1_bounded_empirical execute --bundle <bundle> --expected-sha256 <freeze SHA> --output <새 측정 root>`.

실행기는 기존 smoke검증 실행기를 exact문자열 검사로 조정한 source를 사전에compile하고runner_preview.json에동결한다. 4smoke→30descriptive,새registry·purpose,PID종료확인,최종joint completeness를추가했다. 기존실행기는바꾸지않는다. Nativeprotocol/Android/APK는그대로다. 실행중단시claim을삭제해재실행하지않는다. 이번단계에서는 execute/ADB를호출하지않았다.
