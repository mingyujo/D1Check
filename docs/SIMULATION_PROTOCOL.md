# PC 본 시뮬레이션 사전 계약

2026-09-22 / `pc-simulation-plan-v1` / 현재 작업 `SIM-PLAN-01` / **SIMULATION_PLAN_INCOMPLETE**.

이 버전은 확정된 범위와 필수 미해결 항목을 재현 가능하게 동결한다. 본 실험 실행 가능한 READY 계약이 아니다. 실측 입력의 `SIM-01_READY` 판정은 유지한다. 기존 formal v1, diagnostic v2, calibration, modelProbe, Telemetry v4, 이전 실험 원본·보고서·hash는 변경하지 않는다.

## 연구 질문과 증거 역할

> A24에서 측정한 session-level joint empirical distribution을 사용할 때, 앱 수준의 상태 기반 CPU/GPU 배정 정책이 CPU-only 및 정적 배정 정책에 비해 긴급 요청의 응답성과 deadline 준수를 개선하면서 일반 요청의 완료율, makespan, throughput, 메모리 및 열 제약의 손실을 사전 허용 범위 안에 유지할 수 있는가?

상충관계 존재 자체를 다시 발견하는 연구가 아니다. 어떤 정책이 어떤 조건에 적합한지 판별한다. 선행연구 비교와 비신규성은 [RELATED_WORK_GAP.md](RELATED_WORK_GAP.md)를 따른다. 실측은 현 기기 서비스·setup/active·resident dispatch·간섭·메모리/열의 calibration이며 새 ADB·실측을 이번에 수행하지 않는다.

사실: 30세션/480호출, solo 4 cell 각5, resident CPU serial/분류 CPU+탐지 GPU 5쌍이 동결됐다. 측정 warmup 240/timed 240이며 독립 표본 480개가 아니다. 긴급 P95 co-run−CPU 평균 약 −2,838.11ms, makespan +2,178.00ms, throughput 약 −0.87997req/s는 이전 **실측 관측**이다. 이번 정책 simulation 결과가 아니다. 정확한 재검증 집계는 외부 input_audit와 보고서에 둔다.

적용 범위: A24, exact APK/모델/canonical 단일 이미지, 현 CPU/GPU, resident runtime, thermal0, 관측 메모리 범위. 다른 기기·NPU·지속 throttling·동적 unload/reload·다른 작업·미측정 overlap에 일반화하지 않는다. 출력 동등성은 실제 task accuracy나 unseen-image 정확도와 다르다. EfficientDet exact license/NOTICE 미확인은 계속 비배포 연구 제한이다.

## 입력에서 확인되는 결정적인 한계

기존 [bounded 계약](BOUNDED_EMPIRICAL_PROTOCOL.md)과 [empirical 계약](EMPIRICAL_CALIBRATION_PROTOCOL.md)은 task/backend/priority/origin/요청 순서/overlap 호환성을 요구하고 미측정 overlap 외삽을 금지한다.

| 동결 family | 실제 지원 | 본 정책 비교에서 빠진 값 |
| --- | --- | --- |
| solo 4 cell | 한 runtime, 동일 이미지, normal, cold/early/settling/ordinal warm | 두 runtime resident에서 순서를 바꾼 직렬 서비스와 장시간 idle-resume |
| CPU resident serial | 두 CPU runtime, 분류 urgent/탐지 normal 교대, 각6 timed, offset0, 단일 lane | urgent-first로 재정렬한 요청열의 joint 서비스 분포 |
| CPU/GPU resident co-run | 분류 CPU urgent+탐지 GPU normal, 각6 timed, offset0, 두 lane | staggered 도착·다른 mix/priority·선택적 co-run 중단/시작의 간섭 |

추론: 고정 trace의 관측 응답을 다른 정책의 서비스시간으로 사용하는 것은 queue wait와 간섭을 이미 포함한 결과를 재사용하는 오류가 될 수 있다. active만 떼어 순서를 바꿔도 원래 session의 overlap/ordinal 관계가 유지된다는 보장이 없다. 전체 block을 선택하는 것만으로 이 문제가 해결되지 않는다.

현재 지원 조건만 유지하면 STATIC 직렬 CPU/GPU와 URGENT_CPU의 변경 순서까지 비교할 공통 서비스 모형이 없다. STATIC을 ALWAYS_CORUN과 같게 정의해 다섯 정책이 준비됐다고 세거나, adaptive가 미래 선택 block의 완료값을 미리 읽어 layout을 고르는 oracle을 만들지 않는다. CPU+GPU 고정 layout 안에서 탐지 CPU로 전환하면 세 번째 runtime이 필요하며 허용되지 않는다.

따라서 `U1_SUPPORT`는 단순 구현 누락이 아니라 **반사실적 정책에 대한 서비스 모형 계약 누락**이다. 원자료를 더 분석해 지원 범위를 확인할 수 있지만 원자료에 없는 정책 효과를 만들어낼 수는 없다.

## 정책 정의와 동결 상태

새 namespace `SP1/*`를 사용한다. 개정4.4 B0/B1/B2/B3/P 및 이전 bounded baseline ID의 의미를 덮어쓰지 않는다. 아래 첫 네 정책의 논리 정의는 고정하며, 실측 입력에서 실행 가능하다는 뜻은 아니다. ADAPTIVE는 명시적 미완료 명세다.

| ID | 큐/우선순위·backend·동시성 | 실측 입력 적용 상태 |
| --- | --- | --- |
| SP1/FIFO_CPU | `(arrival, request_id)` 오름차순; 두 task CPU; 단일 lane | 기존 CPU trace 순서와 일치할 때만 원 trace 재생 가능 |
| SP1/URGENT_CPU | urgent 먼저, urgent 내 `(absolute_deadline, arrival, request_id)`; normal FIFO; CPU 단일 lane | 재정렬 서비스 연결 미확정 |
| SP1/STATIC | 분류 CPU/탐지 GPU 고정; 전역 FIFO; 전체 동시 실행1 | 상주 CPU/GPU 직렬 문맥 미측정 |
| SP1/ALWAYS_CORUN | 같은 고정 mapping; lane별 FIFO; 빈 lane에 즉시 시작; 최대2 | 동결 offset0/교대6+6와 일치하는 범위만 지원 |
| SP1/ADAPTIVE | 시작 전 현재 queue와 관측 환경만으로 CPU serial 또는 CPU/GPU layout 선택; 이후 해당 resident cell만 사용. urgent EDF/normal FIFO. 합법 후보를 feasibility→예상 urgent miss 수→지각량→완료시간 순으로 비교, 동률 CPU layout | 예상값 계산기와 일반 서비스 허용 손실 및 합법 dispatch 집합 미확정 (`U2_POLICY`); 완성 알고리즘/성능 주장 금지 |

공통: 요청 전체 비선점, CPU thread1, 최대 runtime2, workload 전 setup/각runtime6회 measured warmup, 끝까지 상주. 선택 후 unload/reload 금지. 동률은 arrival/request ID, backend/layout 동률은 CPU 우선. 정책은 난수를 소비하지 않는다. 미래 도착·실현 서비스시간을 볼 수 없다. 유한 batch에서 aging 없이 normal FIFO를 쓰는 정의이며 지속 도착에서 starvation 방지가 입증됐다고 하지 않는다. 지속 workload의 aging 규칙은 U4와 함께 미확정이다.

GPU 거부: 출력 gate 미통과, thermal≠0, memory admission 거절, nonresident cell, 미측정 schedule. memory 실패 시 요청 rejected를 남기고 새 dispatch latch를 닫는다. 이미 시작한 요청은 중단하지 않는다. CPU silent fallback 없음. 유효 서비스 블록이 없는 것은 정책 rejection 성능이 아니라 해당 scenario가 **unsupported**인 준비 실패다.

Deadline은 soft: 만료로 긴급 표본을 줄이지 않고 늦은 성공을 보존한다. deadline 경과만으로 취소하지 않는다. failed/rejected/expired/cancelled/unfinished 상태를 결과 계약에 모두 유지하며 expiry가 꺼진 실행에서는 expired=0이어야 한다. 실행 종료/drain 상한은 미해결이다.

policy 목록과 모든 config를 canonical UTF-8 JSON SHA-256으로 결합한다. 미해결 null도 hash의 일부다. 채우려면 새 버전·새 freeze가 필요하며 결과를 본 뒤 조정할 수 없다. 강화학습은 제외한다.

## 목적함수·성공 기준

기존 사전적 우선순위를 유지하면서 **epsilon-constraint 후 lexicographic**을 선택한다. 먼저 지원·품질·memory/thermal 및 일반 서비스 손실 제약을 만족시킨 뒤 urgent deadline miss, urgent P95 순으로 비교한다. 단일 가중합은 임의 효용 환산을 요구하므로 쓰지 않는다.

필수 성공 형태: 강한 CPU urgent-priority 및 정적 대조 각각 대비 실질적 urgent 개선, normal deadline completion/전체 completion/makespan/throughput의 사전 허용 손실 이내, memory/출력/지원 위반0. FIFO 하나만 이기면 adaptive 기여 성공이 아니다. 특정 scenario만 유리하면 그 영역만 보고한다. 모든 정책이 불충족이면 불충족으로 남긴다.

`U3_CRITERIA`: practical urgent 효과와 허용 손실은 아직 null이다. 기존 10%/2%p는 미승인 참고값이며 자동 채택하지 않는다. 5쌍에서 관측된 GPU 손실만큼 허용치를 설정하면 후보를 통과시키기 위한 기준이 되므로 금지한다. CPU 측정 변동성은 측정 잡음의 근거일 뿐 사용자가 받아들일 서비스 손실의 근거가 아니다. zero-loss dominance를 별도 엄격 sensitivity로 검토할 수 있지만 그것을 사용자가 요청한 허용 손실 계약의 대체로 채택하지 않았다. 기준 미확정 상태에서는 정책 성공을 출력할 수 없다.

## KPI와 결과 schema 초안

결과 schema는 문서 초안이며 본 simulator 구현 전에 기계 validator가 필요하다. 요청마다 `scenario_id, replication, policy_id, config_sha256, input_sha256, pair_id, source_session_id, source_request_id, request_id, task, priority, arrival_ns, enqueue_ns, dispatch_ns, output_ready_ns, persist_complete_ns, worker_release_ns, deadline_ns, requested_backend, actual_backend, terminal, reason`을 기록한다. 시뮬레이션 ID와 실측 source ID를 분리한다. 파일에는 `experiment_type=empirical_simulation`을 명시한다.

| 지표 | 정의·분모 |
| --- | --- |
| urgent P50/P95/P99 | 성공 urgent의 output-ready−예정도착; linear empirical quantile. 성공 수/전체 urgent 수 함께 제시. 성공0이면 null |
| urgent deadline miss rate | 1−기한 내 성공 urgent/전체 urgent. 실패·거절·만료·미완료 포함 |
| normal deadline completion | 기한 내 persistence 성공 normal/전체 normal |
| 전체 completion | 성공 요청/전체 예정 도착; 늦은 성공 포함 |
| makespan | 첫 예정도착부터 마지막 terminal/공통 horizon까지; incomplete면 censored 표기. 성공한 요청만으로 짧게 만들지 않음 |
| throughput | 성공 수/공통 정의 실행 구간 초; urgent/normal도 별도 |
| queue waiting | dispatch−enqueue 및 enqueue−예정도착을 분리, dispatch된 수 병기; 미실행 대기 censoring 별도 |
| CPU/GPU busy time | lane dispatch→worker release 구간 합집합; hardware utilization이라고 부르지 않음 |
| rejection·실패 | admission rejection, failed/rejected/expired/cancelled/unfinished 전부 별도 수 및 전체도착 비율 |
| 배정 비율 | CPU/GPU 시작 수/전체도착, 미배정 수 병기; dispatch 조건부 비율도 보조 |

동일 request terminal 정확1개, 사건 시각 단조, resident cell만 dispatch, busy interval 중복 위반0, output이 worker release보다 빠르더라도 lane 조기 해제 금지, setup은 runtime당1회, 원 trace queue wait를 새 queue wait에 이중 가산 금지. 온도는 에너지 KPI가 아니다.

## Workload·deadline·seed·반복

실측 서비스시간을 사용하는 **통제된 합성 혼합요청**이다. 실제 사용자 로그가 아니다.

현재 사실로 지원되는 최소 reference는 offset0, 분류 urgent6/탐지 normal6, 1:1 mix, 초기 실행0·대기12, admission 통과·thermal0, 사전 setup/warmup 후 timed6/runtime이다. 전5쌍을 사용한다. 이 reference는 본 정책 simulation 핵심 설계로 승격하지 않고 지원 범위 점검용이다.

필수 축은 도착률/부하, urgent 비율, task mix, deadline, burst, 초기 queue, memory 상태다. 첫 세 축·burst·초기 queue를 달리할 서비스 모형이 없으므로 수치 grid는 null(`U4_DESIGN`). 압력 거절은 validator synthetic fixture로만 확인하며 실측 admission 실패 분포를 생성하지 않는다. low/central/high/cold-stress와 LOSO는 기존 전체block 지원 안의 별도 sensitivity다. 장시간 warm block 반복은 무한 정상상태를 보장하지 않아 채택하지 않는다.

deadline source는 동결 `deadline_scenarios.json` 전부다. CPU output-ready의 warm Q50/Q90×{.75,1,1.5}, 같은 runtime setup+first 또는 early도 각각 별도6후보. normal은 `max(0,H−(a−first_arrival))+m×D_cpu`, m∈{.75,1,1.5}; D_cpu는 고정 CPU solo central block의 공통 task sequence 수요 합이다. 기존 offset0 normal 후보 약3000.740078/4000.986771/6001.480157ms. 기존 floating ns 값은 원본 그대로 보존하며 미래 integer ns deadline 적용은 ceil로 늦지 않게 반올림한다. state→quantile→multiplier→normal multiplier 사전 순서를 사용하고 후보를 성과에 따라 삭제하지 않는다.

이는 engineering scenario이며 절대 사용자 SLA는 계속 `calibration_pending`이다. cold/early deadline 예산을 warm timed 요청에 sensitivity로 적용하는 것과 cold-start workload 전체를 실행하는 것은 다르다. 새 workload의 normal D_cpu를 기존12요청 값으로 무조건 재사용하지 않는다.

master seed **2026092201**. namespace `pc-simulation-plan-v1`; canonical UTF-8 JSON `[version,master,scenario_id,replication,purpose]` SHA-256 첫8 byte unsigned big-endian. purpose=workload/joint_pair/bootstrap; policy명/실행순서 제외. 같은 시나리오와 반복의 workload/deadline/block ticket은 모든 정책에 공유한다. session 전체를 선택하고 pair는 두arm을 함께 선택한다. 다른 cell의 시간을 같은 숫자로 강제하지 않는다. 실제 난수 sampling·선택표 materialization은 미래 실행 때만 허용한다.

본 replication 수·요청 수·horizon/drain·scenario 전체 순서는 미확정이며 30 calibration session 또는 과거30 CRN ticket을 replication 수로 전용하지 않는다. 정확한 scenario/replication/pair 키와 version을 확정한 새 freeze 전 실행 금지. 알고리즘 이름만 있고 simulator/version/hash가 없는 상태도 `U5_ENGINE`로 남긴다.

## 통계 분석

기본 비교는 scenario/replication/동일 pair ticket에서 후보−각 baseline 대응차다. urgent 중앙/tail, deadline 비율, normal/전체 완료율, makespan/throughput을 모두 보고한다. scenario별 결과가 먼저이며 aggregate는 scenario에 동일 가중치를 주는 별도 요약이다. 요청을 모아 pooled P95 하나로 영역별 실패를 숨기지 않는다.

원자료 불확실성은 session 전체 또는 paired 두arm을 묶은 cluster percentile bootstrap **2000회·95%**로 보고한다(기존 descriptive 계약 유지). 가상 replication의 Monte Carlo 오차와 실측 5쌍 불확실성을 구분한다. simulation 반복을 늘려 기기 독립표본이 많아졌다고 하지 않는다. LOSO는 pair 두arm을 함께 빼는5회와 solo family별1세션 제외이며 독립 holdout이 아니다. 최종 각 fold에서 해당 제외 session을 predictor·평가 표본 모두에서 제거해야 한다.

다중 비교: 이번 단계는 descriptive이며 95% 주변 CI를 가족 단위95% 보장으로 부르지 않는다. 모든 baseline/scenario/metric을 공개하고 p-value 유의성이나 CI0 제외만으로 성공하지 않는다. confirmatory 다중비교 판정은 primary family·실질 기준 동결 전 사용할 수 없다. sensitivity에서 유리한 값으로 primary를 바꾸지 않는다. 기준 null 또는 지원 부족이면 inconclusive/incomplete다.

## 재현 도구·동결 산출물

`tools/d1_simulation_plan.py`는 기존 `d1_empirical_plan.validate_block`, Telemetry v4 semantic validator, paired validator, atomic journal reader를 재사용한다. CLI는 generate/validate/dry-run만 있다. 실행·ADB·모델 호출·시간 진행·random sample·가상 완료 경로는 없다. 기존 `d1_sim_prepare` draft/정책 함수를 simulation 완성품으로 재명명하지 않는다.

새 외부 bundle: plan.json, input_registry.json, input_audit.json, no_op.json, freeze.json. 원본 전체 파일 SHA, 30 UUID/요청/trace fingerprint, 과거 consumed registry, configuration/policies, tools Python/schema·본 두 문서 hash를 결합한다. 같은 입력으로 다른 output root에서 byte-identical 생성한다. 기존 root 덮어쓰기와 source 내부 생성 금지. validate/dry-run은 파일을 쓰지 않는다. schema 검증 PASS와 연구 READY 판정을 구분한다.

```powershell
python -B -m tools.d1_simulation_plan generate --source C:/Users/LG/Documents/D1Check_Bounded_Empirical_Run/run_20260921_atomic_v1 --output <새_외부_폴더>
python -B -m tools.d1_simulation_plan dry-run --output <동결_외부_폴더> --expected-sha256 <freeze.json_SHA256>
python -B -m unittest tools.test_d1_simulation_plan -v
```

정확한 이번 bundle 경로·hash·시작/종료 HEAD·테스트 집계는 `docs/SIMULATION_PLAN_FREEZE_20260922.json`과 외부 FINAL_REPORT에 기록한다. 이 문서 자체에 자신의 hash를 넣는 순환은 만들지 않는다. 현재 본 simulation 실행 명령은 없으며 만들어진 것처럼 제시하지 않는다.

## 다음 단계와 대안 비교

다음 ID `SIM-PLAN-02-SUPPORT-DECISION`. 새 실기기 측정 없이 먼저 연구 목적과 허용 모형의 관계를 결정해야 한다.

| 대안 | 가능한 것 | 대가·판정 |
| --- | --- | --- |
| 고정 trace의 전체 pair 재생만 유지 | 강한 provenance, 기존 5쌍·deadline별 기술 분석 | 이미 관측한 A/B 비교를 반복할 뿐 5정책·적응형 연구 질문은 답하지 못함 |
| 명시적 반사실적 서비스 모형 amendment | 일정 범위의 도착/순서/간섭 가정을 적어 PC 비교 설계 가능 | 현재 금지한 외삽과 충돌; 가정·검증 한계·적용 범위를 먼저 합의해야 함. 근거 없이 계수/분포를 만들면 안 됨 |
| 새로운 실측으로 support 확장 | 실제 변경 순서/overlap 식별에 도움 | 이번 작업 금지이며 현재 동결 입력 한정 목표의 해결책으로 실행하지 않음 |

추천은 **두 번째 대안의 타당성·허용 범위를 PC 설계 단계에서 먼저 결정**하는 것이다. 현재 권한으로 원본 계약의 미측정 overlap 금지를 조용히 해제하지 않는다. 합의가 성립하지 않으면 첫 대안으로 연구 질문을 명시적으로 축소해야 하며 READY로 이름만 바꾸지 않는다.

본 simulation 이후에는 정책과 성공 기준을 고정한 상태로 A24의 작은 독립 세션에서 예측한 유리/불리 영역을 확인하고, 최소 한 추가 Android에서 기기별 calibration을 거친 축소 재현을 계획한다. 구체 수량·조건은 simulator의 지원 영역이 확정된 뒤 별도 실행계획으로 사전 동결한다. 이번에는 어느 실기기 명령도 실행하지 않는다.
