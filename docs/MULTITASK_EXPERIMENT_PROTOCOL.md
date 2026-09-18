# D1Check 두 작업 실험·평가 계약

- 버전: 1.3 / 설계일: 2026-09-18 / 상태: **planned, 미구현·미실측**
- 상위 계획: [PROJECT_PLAN.md](PROJECT_PLAN.md) 개정 4.3. [SCOPE_02_EVIDENCE.md](SCOPE_02_EVIDENCE.md)의 근거 조사와 [MODEL_02_INVENTORY.md](MODEL_02_INVENTORY.md)의 조건부 host artifact 검증을 수행했고 현재 작업은 `MODEL-02B-PREP`다.
- 예약 protocol ID: `multitask-v1`. 현재 `d1_calibration_cli.py`는 이 protocol을 처리하지 않는다. 이 문서는 존재하지 않는 실행 명령을 제시하지 않는다.
- legacy `calibration-v1`/schema 2/image-v3, formal v1, diagnostic v2는 [CALIBRATION_PROTOCOL.md](CALIBRATION_PROTOCOL.md)와 기존 코드 계약을 유지한다.
- 절대 deadline: `calibration_pending`. 효과·서비스·안전·최종 반복 수의 수치: `thresholds_pending`. 값이 비어 있는 formal 실행은 금지한다.

## 1. 측정 대상과 증거 수준

한 A24 앱 안에서 두 task adapter를 실행한다. 우선 검증할 작업은 이미지 분류와 객체탐지이며 각각 자체 모델, 입력/출력 tensor, 전·후처리, label mapping, 품질 기준을 갖는다. task와 요청 등급은 독립이다. 한 요청의 실제 작업을 다른 작업의 반복 또는 임의 지연으로 대체하지 않는다. 특정 사진 정리 기능은 대표 시연 후보이며 평가 조건 전체를 그 기능에 한정하지 않는다.

**실험 방법:** A24 실측에서는 사전 생성한 요청 시각·등급·작업·입력 기록을 재생하고 매 요청의 실제 모델과 I/O를 실행한다. “합성 요청 도착”은 “추론을 가상으로 계산”한다는 뜻이 아니다. 별도 이산사건 시뮬레이터에서는 실측 분포로 가상 완료 시각을 계산하며, 두 결과를 별도 experiment type과 artifact 집합으로 기록한다. 시연의 수동 클릭 결과는 독립된 정량 반복 표본으로 합치지 않는다.

| 단계 | 입증하는 것 | 입증하지 않는 것 |
| --- | --- | --- |
| Host 동작 테스트 | timestamp·queue·상태·artifact·정책 배선 | A24 지원·실제 모델 정확도·성능 |
| 모델 smoke | 특정 파일/런타임/A24에서 실제 output | 모든 사진 정확도·정책 우수성 |
| PROFILE-02 | 해당 입력·환경의 단독/전환/간섭·메모리 | 실사용 도착 빈도·다른 모델/기기 |
| EVAL-02 실기기 재생 | 고정한 혼합 도착 조건에서 기준정책 대비 효과 | 실제 이용 빈도·OS 전체·통역/게임/OCR 일반화 |
| 이산사건 시뮬레이션 | holdout으로 검증된 모델 범위의 조건 탐색 | 가상 실행 횟수를 실제 기기 표본 수로 계산 |

## 2. 모델·입력과 실행 경로 승인

[MODEL_02_INVENTORY.md](MODEL_02_INVENTORY.md)의 1차 결과처럼 MODEL-02 결과표에는 task/model ID, 원 배포 URL·버전, 라이선스 근거, 파일 byte count/SHA-256, tensor name/shape/type, labels의 실제 index·background 처리, metadata, 전처리·후처리 ID/hash, runtime/delegate version을 남긴다. URL이 `latest`이면 확보한 bytes/hash를 고정하고 자동 업데이트하지 않는다. 해시는 파일 동일성이고 출처·정확성의 독립 증명은 아니다.

EfficientDet-Lite0 exact binary는 비배포 A24 연구 probe에만 조건부 승인됐다. 외부 manifest로 URL·bytes·SHA-256을 검증하고 app-private storage에 전달하며 저장소·PR·APK·팀 공유물에 포함하지 않는다. 이 조건은 exact license/NOTICE를 증명하지 않으며, 배포 단계에서는 근거 확보 또는 명시적으로 라이선스된 artifact 교체가 필요하다.

기존 MobileNet의 1001행 계약을 새 모델에 강요하지 않는다. 공식 분류 안내의 1000개 class 설명과 실제 출력 차원을 동일시하지 않고, 각 바이너리와 associated labels를 검사한다. 기존 WNID 앞에 임의 background를 붙이는 방식은 계속 금지한다. verified labels가 없는 후보는 보류한다.

입력은 smoke용 소수 이미지와 개발/최종 평가용 입력을 분리한다. 품질 평가는 라이선스·ground truth가 확인된 공개 validation subset 또는 직접 확인한 표본으로 한다. task별 최소 20개 서로 다른 이미지/여러 class를 확보하는 것을 준비 목표로 하되 이는 정확도 일반화의 충분 표본 수가 아니다. 개발·평가 중복, 인물/개인정보, provenance 제한을 기록한다. 같은 사진 반복은 latency 표본을 늘릴 수 있지만 독립 이미지·독립 session 수를 늘리지 않는다.

CPU와 가속 경로에는 같은 원본·전처리 계약을 적용하고 가능한 경우 동일 input tensor hash를 확인한다. 분류는 top-k/수치 tolerance, 탐지는 box/label/score 매칭 기준과 task accuracy를 CPU reference와 대조한다. tolerance·매칭 규칙은 정책 비교 전에 고정한다. 오류·non-finite·미완료 output은 성공이 아니다. 정책은 모델/해상도/정밀도/threshold를 바꾸지 않는다.

새 protocol의 실행 경로는 다음처럼 구별한다. 이는 기존 strict formal/calibration GPU gate를 바꾸는 것이 아니다.

- `cpu`: CPU runtime과 고정 thread 예산.
- `gpu_full`: 해당 모델 graph의 full delegation 근거가 있는 구성. CPU 전·후처리까지 GPU 실행이라고 부르지 않는다.
- `gpu_assisted`: graph의 GPU/CPU 분할이 확인된 명시적 혼합 구성. 모델별 CPU 잔여 연산과 delegate 로그를 기록하고 전체 서비스시간으로 평가한다. full GPU와 별도 cell이며 “순수 GPU 속도”로 표기하지 않는다.
- `unverified`/`unsupported`: primary 성능 cell에서 제외. 요청만 GPU인데 실제 CPU fallback인 결과를 GPU로 승인하지 않는다.

기존 CompatibilityList 우회나 S26 override는 도입하지 않는다. 새 모델에서도 지원 gate를 통과해야 하며 GPU 초기화 실패는 실패로 남긴다. 알려진 `gpu_assisted` 경로와 실패 시 자동 CPU 재실행은 다른 개념이다. wrapper가 내부 backend를 확인할 수 없으면 CPU/GPU 배정 효과의 주평가에 쓰지 않는다.

## 3. 구현 및 자원 제약

기존 raw Interpreter timer와 새 wrapper API timer는 별도 metric 이름을 사용한다. 새 adapter가 raw Interpreter를 쓰면 buffer reset 후 첫 clock -> run 반환 직후 두 번째 clock을 유지한다. API 내부를 볼 수 없으면 API-call latency만 기록한다. 공식 KPI는 두 경우 모두 실제 service/output 경계의 end-to-end다.

각 interpreter는 전용 worker에서 생성·실행·정리한다. GPU thread/context 계약을 지킨다. 같은 interpreter를 두 thread에서 동시에 호출하지 않는다. 최초 버전은 GPU worker 1개, CPU worker 1개, 전체 in-flight 최대 2건이다. CPU+CPU/GPU+GPU 동시 실행은 이번 범위에서 제외한다. GPU 경로의 CPU 전·후처리는 CPU task와 간섭할 수 있다.

직렬 정책도 두 작업의 모델을 동일한 공통 메모리 예산 안에서 준비할 수 있다. warm 인스턴스 수·캐시/eviction 규칙·thread 수·image cache 정책은 전 정책에 동일하게 적용한다. P만 모든 모델을 preload하고 기준정책만 재생성하는 비교를 금지한다. peak PSS/RSS 등 실제로 확보 가능한 memory metric, OOM/프로세스 종료, scheduler/telemetry 비용을 기록한다. per-process 측정으로 기기 전체 memory 사용량을 주장하지 않는다.

## 4. 요청 ledger와 완료 경계

필드: session/boot/protocol/config hash, request ID, task/model/input ID, priority, planned arrival, enqueue, service start, read/decode/preprocess, backend decision/prepare, inference 또는 API-call, postprocess, output-ready/persist-complete, terminal, requested/observed backend, co-run request IDs, cold/warm, 실패 사유.

device clock은 `SystemClock.elapsedRealtimeNanos()`로 통일한다. host wall clock을 빼서 device latency를 계산하지 않는다. host thermal을 결합할 때 동기화 오차와 offset/bounds를 기록한다.

- `C_i`: 긴급은 표시 가능한 결과 객체 완성 시각, 일반은 write/flush/fsync -> 같은 디렉터리 atomic rename -> readback 성공 시각. storage controller 물리 flush는 주장하지 않는다.
- 주응답 `R_i = C_i - a_i`(예정 도착). 보조 `R_enqueue_i = C_i - e_i`, 발생기 지연 `e_i - a_i`, 큐 대기 `service_start_i - e_i`.
- 문서 선택 UI에서 사진을 고르는 사용자 시간은 service latency에서 제외한다. 별도 사용자 시연에서는 입력 결정/요청 버튼 이후 화면 표시까지도 측정하고 output-ready와 구분한다.
- `succeeded`는 늦어도 결과를 보존한다. 새 protocol의 deadline 충족은 `C_i <= d_i`; 늦으면 `late`. 실패/거절/미완료와 완료 후 late를 섞지 않는다.
- rejected/expired/failed/cancelled/종료 시 unfinished까지 예정 도착 ledger에 한 행을 남긴다. 이미지 read 실패, enqueue 미발생, 프로세스 종료로 event가 빠지면 host가 ledger와 대조해 미완료로 남긴다.

## 5. 환경·열 관측과 안전

충전 여부, SOC, 고정 장소, 화면/밝기, OS/background 상태, warm-up, model cache, Wi-Fi/ADB 방식과 가능한 주변온도를 기록한다. 비교 block은 같은 시작 조건 범위를 만족해야 한다. 충전/화면을 정책마다 바꾸지 않는다.

새 protocol의 baseline은 실행 전 고정한 battery temperature 범위·cooling stability window와 Android thermal status 0/1을 모두 검사한다. runtime에는 지원되는 thermal 상태·battery 시계열, stop/pacing 기준과 실제 작동을 기록한다. 값이 누락되거나 필요한 gate를 평가할 수 없으면 formal 시작을 거부한다. 안전 기준은 정책 공통이며 안전 중단된 요청도 분모에 남긴다. 특정 정책에서 열이 올라 중단됐다는 이유로 그 세션만 제외하지 않는다.

AP/PA/SKIN은 확보 가능하면 수집해 해석을 보강하되, 새 주평가를 센서 세 개의 필수 획득에 종속시키지 않는다. 미지원은 missing 사유로 남기며 다른 센서를 같은 값처럼 대체하지 않는다. thermal headroom은 지원 여부와 공식 호출 간격 제한을 확인한다. status 0만으로 실제 스로틀링이 없다고 확정하지 않는다. 열 인과를 주장하려면 추가 근거가 필요하다. [Android Thermal API](https://developer.android.com/games/optimize/adpf/thermal)

baseline과 선택적 thermal_stress는 다른 조건이다. stress를 반드시 발생시키거나 게임·충전·외부 가열로 의도적으로 유발하지 않는다. “긴급 응답 향상”과 “열 스로틀링 완화”는 독립된 주장이다. 미검증 전류/charge-counter로 에너지 절감률을 계산하지 않는다.

legacy CALIB-01C의 AP/PA/SKIN·host 연결 필수조건은 그대로 남는다. 위 조건은 별도 구현할 multitask protocol에 한정한 개정 결정이다.

## 6. PROFILE-02: 단독·전환·간섭 측정

실제 task×승인 backend별로 읽기부터 해당 완료 경계까지 측정한다. inference timer만으로 예상 서비스를 만들지 않는다. cold 모델 초기화, warm 재사용, CPU↔GPU 및 모델 전환, peak memory를 분리한다. warm-up은 instance별 동일 개수로 고정하고 도착 ledger에서 warm-up role을 표시해 주평가 표본과 구분한다.

1. 단독: task별 CPU와 승인 GPU 구성을 독립 session 5개부터 측정하는 계획을 세운다. session당 서로 다른 입력과 반복 순서를 균형화한다. 표본 목표·최대 추가 session 수·불안정 판정은 시작 전 고정한다.
2. 간섭: 분류 CPU+탐지 GPU, 분류 GPU+탐지 CPU 중 승인된 조합을 같은 입력·환경의 단독과 대응 비교한다. 동시 시작 및 일부 겹치는 시작 offset을 고정해 한 조합의 한 시점만 측정하지 않는다.
3. 결과: task별 slowdown, combined completion/throughput, 긴급 tail, memory, 실패·열 상태를 기록한다. `slowdown = co-run service / comparable solo service`를 방향별 계산한다. aggregate speedup만으로 urgent가 빨라졌다고 하지 않는다.
4. 후보 승인: 품질/메모리/안전 조건과 정해진 표본·coverage를 통과한 cell만 합법적 병행 조합에 넣는다. 결과가 나쁘면 그 조합을 제외하고 직렬 대안을 남긴다.

부족한 cell을 0 지연이나 “간섭 없음”으로 채우지 않는다. 측정한 service distribution, 표본 수, 상태 범위, 잔차/불확실성을 versioned profile로 저장한다. session median의 robust CV와 변화량 같은 안정성 기준은 개발 프로파일 규칙에 명시하고, 작은 표본의 P95를 안정적이라고 선언하지 않는다.

## 7. Deadline·도착 조건 동결

사용자 과업에서 원하는 응답시간과 측정 가능한 수준을 분리한다. 충분한 사용 근거가 있으면 원하는 절대 deadline을 정하고 A24가 충족 가능한지 평가한다. 충족하지 못하면 불가능으로 기록한다. 사용자 근거가 없으면 task별 engineering deadline임을 명시한다. 단독 service quantile·허용 대기예산·출처를 별도로 남겨 어떤 SLA를 가정했는지 설명한다.

새 두 작업에는 legacy `N95+U95`, `N95+3U95`를 자동 적용하지 않는다. `d_i = a_i + D_(task,priority)`를 사용하고 enqueue 지연으로 deadline이 늘어나지 않게 한다. 긴급/일반 D, cold first-use 처리, allowed lateness, aging/최대 대기, 큐 상한과 admission·expiry·drain horizon은 개발 뒤 평가 전에 고정한다. 실행 중 추론의 강제 중단은 없다.

task k와 등급 p 조합의 solo reference service mean을 `s*_(k,p)`, 도착률을 `lambda_(k,p)`라 할 때 명목 부하는 `rho_ref = sum_k sum_p lambda_(k,p) * s*_(k,p)`로 기록한다. 모든 정책에 동일한 사전 고정 reference 구성과 시간 단위를 사용한다. 등급별 완료 경계의 저장 비용 차이도 포함하므로 task와 priority를 같은 축으로 취급하지 않는다. 이는 직렬 reference로 정규화한 제시 부하이고 실제 CPU/GPU 이용률 또는 동시 처리능력이 아니다. 단일 분류 속도를 모든 작업의 capacity로 사용하지 않는다.

| 조건 | 주된 질문 | 고정할 도착 기록 |
| --- | --- | --- |
| W-low | 불필요한 제어 overhead가 생기는가 | 낮은 명목 부하, burst 없음 |
| W-burst(primary 후보) | 누적 일반 작업이 있을 때 대화형 요청을 보호하는가 | 같은 크기의 일반 backlog + 정해진 시각의 urgent burst |
| W-peer(보조) | 같은 등급의 여러 작업이 경합할 때 효율·공정성은 어떤가 | 두 task의 동시/근접 도착, 같은 등급·고정한 task 비율 |
| W-sustain(primary 후보) | 서비스 하한과 대기 누적을 지키는가 | 독립 주기의 일반/긴급 도착, 지속 혼합 부하 |
| W-stress(선택) | 관측 열 상태 변화에서 정책이 유지되는가 | 별도 승인된 지속 부하 설정, baseline과 분리 |

W-peer에서는 task별 응답 분포·기한 내 완료율, 전체 완료량, 최대 대기·backlog를 보고한다. urgent가 없는 조건에 긴급 P95를 만들지 않는다. W-burst/W-sustain의 task 혼합 비율과 등급 비율은 별개로 고정하고, 사전 지정한 보조 조건에서 task별 등급 배치를 바꿔 특정 모델 효과와 우선순위 효과를 구분한다. W-peer나 시연 결과로 primary 판정을 사후 교체하지 않는다.

W-low의 rho_ref 0.4, W-sustain의 0.8~0.9, urgent 3건 burst는 개발용 시작 후보이며 공식 고정값이 아니다. 사람이 그 속도로 클릭한다는 주장과 구분한다. 가능하면 실제 사용 관찰에서 얻은 낮은 빈도의 시나리오도 재생한다. stress/synthetic arrival의 현실성을 과장하지 않는다.

arrival generator는 worker와 분리하고 시작 전에 ID·task·priority·입력·a_i·d_i 전체를 생성해 hash를 고정한다. 실행이 느려도 새 요청 도착을 늦추지 않는다. 발생기 지연 허용값과 logger loss의 처리 기준은 평가 전에 고정한다. 정책 부하 때문에 발생기까지 늦어진 결과는 정책 overhead이며 편의상 무효화하지 않는다. 외부 계측 고장만 별도 사유와 원본을 남기고 전체 대응 block의 처리 규칙을 적용한다.

## 8. 개발·독립 평가·통계

개발 단계는 다섯 정책 B0/B1/B2/B3/P × 두 경합 조건 × 두 독립 block의 짧은 탐색(20세션)을 출발안으로 한다. 이 단계는 feasibility 확인용이며 수상용 통계적 우수성 증거가 아니다. B2 후보 선정과 P/B3 튜닝은 같은 개발 입력·관측 정보·사전 계산 예산을 사용한다.

주평가는 개발에서 선택한 B2, B3, P × W-burst/W-sustain × 독립 block 5개(30세션)를 출발안으로 잡는다. 실제 block 수 5~9와 공통 session 길이는 개발 분산·목표 효과·시간 예산으로 평가 전에 결정한다. 최종 결과가 아슬아슬하다는 이유로 반복을 추가하거나 유리한 때 중단하지 않는다. W-low는 overhead, W-peer와 등급 배치 변경 조건은 공정성·일반성의 보조 비교로 포함한다. 각 보조 조건의 정책·길이·독립 block 수와 총 실행 예산도 평가 전에 고정하며, 위 30세션 출발안에 포함된 것으로 세지 않는다. B0/B1은 최소 독립 sanity block을 남긴다. 제안 개수가 통계적 충분성을 보장하지 않는다.

- 독립 block마다 같은 도착 trace를 정책에 재생하고 순서를 무작위화/균형화한다. 시작 온도·SOC 범위를 맞추며 cooldown은 기록한다.
- seed와 실행 session은 개발/평가에서 분리한다. freeze 후 모델·deadline·queue·정책 parameter를 변경하면 새 실험 버전으로 개발부터 재검증한다.
- session별 조건부 P95는 nearest-rank로 계산한다. 완료 긴급 표본 수·전체 긴급 도착 수를 병기한다. 완료 표본 100개를 안정성 점검의 개발 목표로 삼되, 미달 시 불확실성을 밝히고 부족하면 P95 우수성 판정을 보류한다. 결과를 본 뒤 해당 정책만 더 오래 실행하지 않는다.
- 긴급 기한 내 서비스율 = 기한 내 완료 긴급 수 / 예정 긴급 도착 수. 일반 기한 내 완료율도 같은 분모 원칙을 쓴다. terminal 실패와 late, unfinished를 별도 표로 낸다.
- 일반 목표는 절대 기한 내 서비스 하한 및 B2/B3 대비 허용 악화폭으로 고정한다. 일반 최대 대기/oldest age·종료 backlog·완료 수를 같이 본다. 과부하 조건은 서비스 보장이 불가능할 수 있으며 별도 resilience 결과로 구분한다.
- 세션 대응 차이를 기본으로 효과크기와 95% 신뢰구간을 계산한다. bootstrap을 사용하면 요청별 IID가 아니라 독립 block 단위로 재표집하고 분석 seed를 남긴다. 적은 block의 불확실성을 공시한다.
- primary 조건·metric pair·비교대상(B2/B3)와 다중 비교 처리(예: Holm 또는 사전 순차 gate)는 freeze에 기록한다. 나머지 load/민감도/구성요소 제거 결과는 탐색적으로 구분한다.
- 성공은 미리 정한 서비스 제약과 효과 기준을 함께 충족해야 한다. 긴급 P95 10%, 일반 감소 2%p는 이전 제안값이며 자동 채택하지 않는다. 기한 위반율 허용차·일반 절대 하한·CI 판정까지 동결해야 한다.

기한 민감도는 D의 0.8/1.0/1.2배처럼 개발 때 정한 보조 범위에서 보고할 수 있다. 1.0배 primary가 실패했는데 유리한 배수만 선택해 성공으로 바꾸지 않는다. 품질·메모리·열 안전 위반을 latency 이득으로 상쇄하지 않는다.

## 9. 실측 기반 시뮬레이션의 역할과 순서

1. **실측 프로파일 확보:** 실제 두 task의 단독·준비/전환·승인 co-run 서비스시간과 변동성, 실패·메모리·열 상태를 측정한다. 서비스시간은 input read부터 task 완료까지이며 같은 비용을 별도 overhead와 중복 합산하지 않는다.
2. **이산사건 모델 작성:** 요청 도착, 큐, CPU/GPU 점유, 비선점 실행, 준비/전환, 완료/거절/만료와 공통 제약을 모형화한다. 실측 상태에 맞는 분포와 간섭을 사용한다. 상관·시간 변화가 관측되면 단순 IID 샘플링 대신 블록 재생 또는 조건부 모델을 검토하고 사용 가정을 기록한다.
3. **별도 검증:** 모형 보정에 사용하지 않은 A24 session으로 응답 분포·throughput·backlog와 정책 순위가 재현되는지 확인한다. 허용 오차는 결과를 보기 전에 고정한다. 이 검증 자료와 최종 정책 평가 자료는 구분하며 최종 평가 결과로 모형을 재보정하지 않는다.
4. **조건 확장:** 검증된 범위의 도착 빈도·burst·task/등급 비율을 넓혀 민감도와 정책 적용 영역을 탐색한다. 검증 범위 밖은 외삽 가정으로 표시한다. 시뮬레이션에서 발견한 개선이나 설정을 채택하려면 개발 자료로 취급하고 새 독립 실기기 평가 전에 설정을 다시 고정한다.

실기기 재생과 가상 시뮬레이션은 원본·CSV·그림에 구별해 표시한다. simulated run 수를 실기기 session 수와 합산하거나, 시뮬레이션에서만 나온 개선률을 A24 실측 개선률로 쓰지 않는다. 가상 반복의 난수 오차와 원래 실측 프로파일의 불확실성도 별개다. 반복을 늘리는 것만으로 프로파일의 작은 표본 문제가 해결되지는 않는다.

열 동역학·실제 energy·장치 전체 memory를 검증하지 않았다면 가상 온도·스로틀링·전력 절감 결과를 만들지 않는다. 수집한 열 상태를 조건으로 사용하는 경우 관측된 범위로 한정한다. 미측정 OCR/통역/게임은 명시적 가정의 toy 사례로만 사용할 수 있으며 새 작업의 실제 성능·지원 근거가 아니다.

모형이 정책 순위나 주요 지표를 재현하지 못하면 원인을 기록하고 시뮬레이션을 정책 채택 근거에서 제외한다. 일정이 부족하면 보조 시뮬레이션 범위를 줄이고 실제 모델을 사용하는 A24 주비교를 완료한다. 미래 도착을 아는 작은 offline oracle을 추가할 경우 현실 정책이 아니라 예측 모형 안의 참고 상한으로 표시한다.

## 10. 필수 산출물과 실행 전 gate

MODEL-02: `model/input inventory`(파일명은 후속 구현에서 고정), 품질/지원/메모리 표 및 제외 이유. PROFILE-02: solo/transition/co-run 원시 event와 profile. SCHED-02: 정책 버전·parameter·decision log와 freeze 문서. EVAL-02: request_results.csv, session_summary.csv, thermal/memory 시계열, 대응 분석, 실패·제외 ledger. 모두 task/model/backend/config·입력·APK·Git·dirty diff hash로 묶는다.

실기기 재생/보조 시뮬레이션/사용자 시연의 구분 필드는 TASK-02에서 schema에 명시한다. 시뮬레이션 산출물은 service profile hash·보정/검증 session 목록·도착 trace hash·policy/model version·seed·가정·검증 오차를 별도 provenance로 연결한다. 아직 해당 실행기·CLI·schema는 구현되지 않았다.

TASK-02는 새 schema의 exact allowed artifact set과 root-only provenance self-exclusion, UUID·path containment·regular-file·hash·count 검증을 production/host 양쪽에 구현한다. 새 산출물을 legacy validator에 억지로 통과시키지 않는다.

formal 전 완료해야 할 항목:

1. 모델·labels·입력·품질·실제 backend 및 task adapter 승인.
2. arrival/terminal/deadline·persistence·cleanup·provenance production 경로 검증.
3. 공통 메모리·thread·thermal/cooling·admission/expiry/drain 값 동결.
4. solo/co-run profile과 허용 병행 집합, B2/B3/P 튜닝 및 정책 freeze.
5. 독립 평가 trace/반복 수/표본/분석법·일반 서비스 하한·성공 기준 동결.

이번 계획 개정은 위 항목의 PASS가 아니다. 실기기 설치·실행은 해당 작업에 대한 사용자 요청과 환경 권한 범위에서 수행한다.
