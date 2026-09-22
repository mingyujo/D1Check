# 지원 범위 한정 PC 시뮬레이션 계약

2026-09-22, 작업 `SIM-PLAN-02-SUPPORT`, version `support-constrained-simulation-v1`.
이 계약은 사용자가 명시적으로 채택한 제한 모형으로 이전 `11d1e89`의 미완료 항목을 해결한다. 이전 부분 계획과 실측 계약은 보존한다. READY는 실행 승인이 아니다. 이번에는 입력 변환·검증·합성 fixture 테스트만 수행한다.

## 연구 질문과 근거의 구분

A24에서 측정한 session-level joint empirical distribution과 아래 교환가능성 가정 아래, 앱 수준의 배치 시작 전 CPU/GPU 배정은 CPU-only 및 정적 정책에 비해 긴급 응답·deadline 준수와 일반 완료율·makespan·throughput 사이에서 어떤 Pareto 선택지를 제공하며, 사전 epsilon 조건별로 어떤 구성이 적합한가?

**사실:** 동결 30세션/480호출, solo 4cell×5 및 resident CPU serial/co-run 5쌍, 실패·재시도·대체·추가 0, thermal status 0. 출력 동등성·memory admission·cleanup은 기존 v4 gate 범위에서 통과했다. 관측 co-run−CPU 평균 urgent P95 −2,838.110815ms, makespan +2,178.003769ms, throughput −0.879968req/s는 calibration 관측이며 새 정책 결과가 아니다.

**가정:** warm 동일 task/backend/resident state의 dispatch gap과 dispatch→output-ready/persist/release 결합 tuple은 해당 세션 내에서 교환 가능하다. CPU urgent-first 재배열은 이 가정을 사용하며 task 내부 순서는 보존한다. 새 순서 효과를 추정하거나 전환 비용을 따로 더하지 않는다. gap을 tuple에 결합해 이동하는 것도 모델링 가정이다. 열·메모리 상태와 양 arm의 상관관계는 세션 pair 전체를 단위로 유지한다. 가정의 실제 타당성이 검증되었다고 주장하지 않는다.

**추론의 한계:** 실제 사용자 로그가 아닌 측정 서비스시간을 이용한 통제된 합성 혼합요청이다. 대기 중인 12요청의 유한 배치 연구이며 일반 온라인 스케줄러, 임의 도착률·task mix·긴 burst의 성능을 입증하지 않는다. 단일 정책이 지배하지 않거나 적응형 정책의 이득이 없다는 결과도 유효하다.

## 입력과 허용 action

- A24, 현재 APK·모델·입력·CPU/GPU backend, thermal0, resident runtime, non-preemptive로 제한한다. 원본 manifest와 기존 validator가 정확한 모델/input/APK hash·동등성·전처리 계약을 검증한다. 다른 기기·NPU·에너지/배터리 주장은 없다.
- `CPU_SOLO`, `GPU_SOLO`: 관측된 한 task의 normal 6요청/offset0, 같은 backend의 warm tuple만 사용한다. core의 독립 baseline이 아닌 capability·정적 배정 calibration이다.
- `CPU_FIFO`: 관측 A arm의 classification urgent/detection normal 교대 6+6, 두 CPU runtime resident 직렬. 원래 gap과 tuple을 순서대로 재생하므로 원 trace와 동일하다.
- `CPU_URGENT`: 같은 A block의 urgent 6개 후 normal 6개. task별 순서와 joint tuple을 유지한다. 교환가능성 가정에 의한 유일한 재배열이다.
- `PAIRED_CORUN`: B arm 전체의 classification CPU urgent + detection GPU normal timeline을 그대로 사용한다. lane를 독립 표집하거나 임의 시작시각으로 이동하지 않는다. 잔여 normal lane·workload tail을 모두 보존한다.

원시 monotonic timestamp는 workload_start를 빼 정수 ns로 변환한다. dispatch부터 worker_release_end까지 lane 점유이며 output_ready와 normal persist_complete를 구별한다. urgent에는 존재하지 않는 persist를 만들지 않는다. setup과 6 warm-up은 resident 배치 이전이며 지표 시간에 포함하지 않고 provenance에 보존한다. runtime unload/reload와 setup 비용 최적화는 범위 밖이다.

`support`, `validate_catalog`, provenance 재생성은 임의 stagger/idle arrival, 다른 task/priority 순서·개수, thermal≠0, unknown option/action, mixed serial CPU/GPU, 반대 co-run 배정, 새 transition·reload를 `OUT_OF_SUPPORT`로 거부한다. 지원 밖 요청을 빠른 rejected 요청으로 계산하지 않고 전체 평가를 중단한다. 품질 gate를 통과하지 않은 backend는 입력에 들어올 수 없다.

## 정책 알고리즘

공통: resident layout은 setup 이전 1회 결정한다. non-preemptive, deadline은 soft이며 늦어도 취소/만료하지 않는다. arrival/입력 ordinal/request ID로 동률 처리한다. RNG에 의한 정책 동률 처리는 없다. GPU는 측정 B 전체 layout 외에는 core에서 거부한다.

| 정책 ID | 계산·queue·backend |
| --- | --- |
| FIFO_CPU | 모든 요청 CPU, 입력 ordinal FIFO. urgent 선점 없음 |
| URGENT_CPU | 모든 요청 CPU, urgent 우선/urgent deadline 오름차순/ordinal/ID, normal FIFO |
| STATIC | solo 각 session 6개 worker 점유시간 평균을 구한 뒤 5session 평균 최소 backend를 task별 선택, 동률 CPU. 현재 두 task 모두 CPU이므로 FIFO_CPU와 동일; 별개 효과로 세지 않음 |
| ALWAYS_CORUN | 허용된 B 전체 layout, lane별 관측 task FIFO, CPU urgent/GPU normal. 임의 lane 재배치 없음 |
| ADAPTIVE_0 | 아래 예측 epsilon=0 제약 안에서 CPU_URGENT/PAIRED_CORUN 중 선택 |
| ADAPTIVE_HALF, ADAPTIVE_1 | 같은 알고리즘의 사전 sensitivity epsilon=0.5/1 |

적응형의 상태는 고정 workload·deadline budget·admitted resident layout·calibration catalog다. 평가될 pair ticket을 보지 않고 training catalog에 대해 각 action 지표의 동일가중 기대값을 계산한다. CPU urgent를 기준 R, co-run C라고 할 때 손실 벡터는 `(makespan−R, R.throughput−throughput, R.normal_on_time−normal_on_time)`이다. 제약은 성분별 `loss ≤ epsilon × max(0, loss(C))`. feasible action 중 `(urgent miss, urgent P95, makespan, CPU 우선)` 사전식 최소를 택한다. 전부 동일하면 CPU다. 이 예측 계산은 **본 실행 시** 수행하며 계획 생성/dry-run에서는 호출하지 않는다.

Memory gate는 기존 `android-low-memory-resident-v1`: before_workload에서 thermal0, low_memory=false 및 `avail−threshold > max(threshold, observed_peak_PSS)`를 요구한다. 불통과하면 GPU fallback/강제 실행 없이 batch 전체 거절, 모든 도착을 분모에 남긴다. core는 관측된 admit snapshot만 사용한다. 압력/거절 확률을 생성하지 않으며 거절 처리는 합성 경계 테스트로만 검증한다. 관측 PSS는 true peak/미래 admission 보장이 아니다. 실행 중 메모리 변화와 실패 발생 모형은 없고 새로운 상태는 OUT_OF_SUPPORT다.

## 최소 workload·반복·deadline 설계

core 축은 실제 offset0 배치/urgent 비율1/2/classification:detection=1:1/12요청/초기 빈 queue에서 동시 투입/6warmup/관측 admission이다. 외부 부하율은 정의하지 않는다. measured burst 한 가지이며 장기 정상상태 warm-up이나 무한 drain은 없다. 마지막 release와 관측 tail까지 drain한다.

Deadline은 원본 `deadline_scenarios.json`의 classification urgent_warm/urgent_cold/urgent_early 각 6 budget과 normal 3 budget의 직교 조합 **54개**를 사용한다. 원래 측정분포 공식·수치는 audit에 결합된 원본에서 읽고 ns를 ceil한다. cold/early는 **deadline budget 출처 이름**일 뿐 모든 실행은 warm이다. 단일 사용자 SLA는 여전히 `calibration_pending`; 복수 engineering budget으로 비교하는 것이며 완료로 바꾸지 않는다. 반복된 수치도 원래 scenario ID를 보존한다.

seed=`2026092202`, SHA-256 canonical `[version, seed, purpose, scenario, ordinal]`로 요청 ID를 결정한다. pair_id는 별도 CRN key다. scenario 순서는 state(warm,cold,early), urgent index, normal index; pair는 ID 사전순; 정책 순서는 위 표 순서다. 데이터 크기는 독립 pair 5뿐이므로 무의미한 MC 복제를 하지 않는다. **replications=5, 모든 pair atom 동일가중 전수 평가**로 유한 empirical 기대값의 MC 오차를 0으로 만든다. 이는 모집단 추정오차가 0이라는 뜻이 아니다. 정책·scenario별 같은 pair/tuple을 쓰는 common random numbers의 결정적 전수 구현이다. 요청 독립 표집을 하지 않는다.

## 평가·불확실성·성공 판정

- 요청별 urgent output-ready response P50/P95/P99는 선형보간 empirical quantile. 6개 urgent의 P99는 population tail을 보장하지 않는다. urgent miss는 실패/거절 포함 전체 urgent 도착, normal on-time은 persist 기준 전체 normal 도착, completion은 전체 12도착 기준이다.
- makespan=workload 끝, throughput=완료수/makespan, waiting=dispatch−arrival, backend busy=release−dispatch, CPU/GPU 배정 비율·memory rejection·failed/rejected/expired/cancelled/unfinished 수를 함께 보존한다. 완료 조건부 latency와 전체도착 실패를 함께 보고한다. 모델 내 failure0은 실세계 failure 불가능 주장과 다르다.
- 주 결과는 각 scenario의 **pair별 지표 평균**에 대한 `(P95, miss, makespan, −throughput, −normal_on_time)` Pareto frontier다. 전체 완료율1인 정책만 frontier 후보며 한 성분 엄격 개선/나머지 비악화가 dominance다. 동률은 모두 표시하고 STATIC alias를 명시한다. scalar 종합점수·보편 winner를 만들지 않는다.
- 실제 결과의 epsilon feasible 집합도 동일 식으로 e=0/0.5/1 각각 표시한다. 이는 관측 trade-off 구간의 무손실/중간/전손실 sensitivity이지 UX가 허용한 손실 기준이 아니다. 적응형의 **선택**은 사전에 고정된 예측값만 사용하며 결과에 맞춰 바꾸지 않는다.
- 모든 정책과 4baseline 간 동일 pair difference를 ns/ms·요청/s·비율/percentage point 실제 단위로 보고한다. epsilon 제약과 frontier의 개선/동률/비지배 영역을 보고하며 실질적 가치가 검증됐다는 임의 threshold 판정은 하지 않는다. 정책 효과 없음·일부 deadline만 유리함도 그대로 보고한다.
- core CI: pair 전체를 replacement로 뽑는 **5^5=3125 ordered bootstrap 조합 전수**, 평균 paired difference의 2.5/97.5 선형보간 percentile. 알고리즘 재선택 없이 동결 정책 difference의 CI이며 adaptive policy-selection 불확실성은 아래 LOSO로 별도 평가한다. n=5의 탐색적 CI, 독립 holdout 아님. p-value/다중 유의성 성공 주장을 하지 않으므로 다중 검정 승자 선정 없음; 다수 CI는 simultaneous coverage가 아닌 marginal 기술 결과다.
- low/central/high: A+B 전체 worker 점유 합으로 pair rank(동률 pair ID)를 정하고 최저/중앙/최고 **실제 pair 전체**를 적용한다. component별 quantile 혼합/새 서비스 배율을 생성하지 않는다. 이것은 관측 세션 변동 민감도이며 교환가능성의 미관측 순서 비용을 검증하지 않는다.
- LOSO 5fold: pair 양 arm을 함께 제외, 남은 4pair로 적응형 예측을 다시 만들고 동일 4pair 전수 평가한다. 이는 leave-one-pair-out deletion robustness이며 held-out accuracy 평가가 아니다. static solo calibration은 유지한다. scenario를 pooling한 latency를 만들지 않는다. 필요 시 Pareto 등장 scenario 수의 기술 요약만 병기한다.

## 재현·구현·결과 계약

`tools/d1_support_simulation.py`는 별도 namespace다. `generate`는 기존 raw validator·hash·registry를 재검증하고 catalog/plan/audit/registry/freeze만 쓴다. `validate`와 `dry-run`은 같은 read-only 경로이며 RNG·policy choose·time advancement·결과 writer를 호출하지 않는다. schema와 exact semantic regeneration을 함께 검증한다. 상대 path 탈출·replay·consumed registry 변조·미지원 action은 거부한다. `freeze.json`은 모든 Python/schema dependency와 이 문서·관련 문헌 문서 hash를 묶는다. configuration SHA는 계산식·seed·scenario·정책 의미를 source/protocol hash와 함께 고정한다. 실제 숫자와 모든 입력 SHA는 외부 plan/catalog/audit에 있다.

미래 simulator API는 `evaluate(catalog, scenarios)`이며 입력 freeze 검증 후 별도 승인된 실행 wrapper에서만 호출한다. 이번 CLI에는 run 명령이 없다. 반환 result는 protocol/experiment_type/results/interpretation이며 scenario별 9variant(core,low,central,high,5LOSO), policy/pair별 requests·metrics, means·pareto·paired_differences·epsilon_feasible를 포함한다. 요청 schema는 원 tuple+request_id/source_session/terminal/reason이다. `validate_result`가 terminal 단일성·시간 순서·lane 비중첩·전체도착 결합을 강제한다. unknown terminal/실패모형은 거부하고 조용히 누락하지 않는다. 결과 파일 schema 초안은 이 반환 구조와 validator이고 본 실행 wrapper/원자적 저장·소비 실행 registry는 별도 실행 작업에서 승인 후 결합한다.

정확한 동결 경로·SHA·검증 명령은 `SUPPORT_SIMULATION_FREEZE_20260922.json` 및 외부 FINAL_REPORT를 따른다. 사후 변경은 version/config hash 변경과 새 계획 승인 없이는 금지한다.

## 선행연구·다음 단계

[6편 1차 자료 비교](RELATED_WORK_GAP.md)의 알려진 GPU 비우월성·경합·latency/throughput 상충·priority/deadline scheduling을 새로운 발견으로 주장하지 않는다. D1Check 후보 차이는 상용 Android black-box app의 기기별 calibration, 실행 가능한 admission 범위, Pareto 선택 규칙 및 provenance 재현 계약이다. 이 작은 범위에서 새 정책 성능 우월성/학술적 신규성은 아직 미입증이다.

다음 `SIM-RUN-01-SUPPORT`는 별도 승인과 실행 프롬프트 후 동결 입력 검증→원자적 결과 저장 wrapper→본 평가다. 이어 `SIM-DEVICE-CONFIRM-01`에서 선택된 정책/CPU 대조를 A24의 같은 입력·resident·thermal0로 소규모 paired 확인한다. 세션 수·정확한 기기 실행은 결과와 별도 승인 후 사전계획하며 현재 추가 측정은 없다. 다른 기기 재현은 장기 프로젝트 목표로 남되 이 계약에 일반화하지 않는다.
