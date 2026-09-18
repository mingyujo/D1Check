# D1Check CALIB-01A 종단간 calibration protocol

- 문서 버전: 5 — 기존 단일 MobileNet 계약의 적용 범위 표시; image-v3 및 측정/schema 계약은 유지
- 작성일: 2026-09-15
- 상태: CALIB-01B completed / `CALIB_01B_PASS`. FIX4 최종 감사와 전체 host 검증 완료. 과거 네트워크·Robolectric·signing lock 대기는 resolved history로 분리한다. SCOPE-02와 MODEL-02A 조건부 host gate를 마쳤고 프로젝트 현재 작업은 MODEL-02B-PREP다. 이 문서의 CALIB-01C-INPUT은 legacy 단일 모델 입력 준비로 보류/재계획하며 대표 이미지·라벨·thermal/cooling gate·strict GPU smoke 미완료 상태를 보존한다.
- 직접 실기기 적용 기기: Galaxy A24만 해당. Galaxy S26 새 calibration·설치·실행은 `OUT_OF_SCOPE_NON_BLOCKING`이며 기존 formal 80슬롯 보조자료만 유지한다.
- 절대 마감시간 상태: `calibration_pending`
- 목적: 실제 사용자 이미지 경로의 구성요소별 종단간 지연과 변동성을 측정해 기기별 절대 마감시간 및 혼합 워크로드 조건을 평가 전에 고정한다.

## 0. 개정 4.1 계획과 기존 구현의 적용 경계

프로젝트 목표는 [PROJECT_PLAN.md](PROJECT_PLAN.md) 개정 4.1, 새 두 작업의 측정·평가 설계는 [MULTITASK_EXPERIMENT_PROTOCOL.md](MULTITASK_EXPERIMENT_PROTOCOL.md)를 따른다. **아래 1~14절은 구현된 MobileNet 단일 모델 `calibration-v1`/schema 2 계약과 이력이다. 새 두 작업에 자동 적용하지 않는다.**

- CALIB-01B PASS와 기존 host 검증 결과는 보존한다. 새 모델 지원 또는 실기기 calibration 완료를 의미하지 않는다.
- 기존 1001행 label mapping 출처 미확인, 8장 입력 미준비, AP/PA/SKIN·cooling host 연결, strict GPU smoke는 해결된 것으로 기록하지 않는다. 기존 CALIB-01C를 재개하면 원래 사전조건을 충족해야 한다.
- 8절의 `N95 + U95`, `N95 + 3 × U95`와 9절의 단일 `C` 도착률 공식은 기존 단일 모델용이다. 서로 다른 두 작업의 사용자 deadline·workload로 전용하지 않는다.
- 새 모델별 tensor/labels/전처리와 별도 artifact 계약은 TASK-02에서 구현한다. 기존 `d1_calibration_cli.py`에 새 입력을 전달하거나 image-v3 hash를 새 모델에 재사용하지 않는다.
- 새 실험에서 AP/PA/SKIN을 진단 자료로 다루는 결정은 새 protocol에 한정된다. 기존 5절의 stricter gate를 완화한 PASS로 소급하지 않는다.

## 1. 범위와 비목표

- 긴급 요청은 사용자가 갤러리 사진 한 장을 선택하고 즉시 분류 결과를 요청하는 작업이다.
- 일반 요청은 여러 갤러리 사진을 백그라운드에서 분류·색인하는 작업이며, 개별 이미지 결과 저장을 요청 완료 경계로 삼는다.
- 1차 backend는 CPU와 GPU다. NPU는 capability와 실제 실행 proof가 있을 때만 별도 후보로 추가하며 CALIB-01의 필수조건이 아니다.
- A24에서만 새 종단간 calibration과 스케줄러 실기기 검증을 수행한다. 기존 S26 formal 80슬롯은 기기별 CPU/GPU 특성 차이를 보여주는 보조 사례이며 S26 종단간 검증 근거가 아니다.
- 이 calibration은 스케줄러 우수성, 에너지 절감 또는 GPU 내부 H2D/GPU/D2H·fence 시간을 입증하지 않는다.
- 기존 80슬롯의 tensor-only `Interpreter.run()` 지연을 이미지 종단간 지연으로 사용하지 않는다.

## 2. CALIB-01A 당시 구현 전 production 경로 감사

| 필수 경로 | CALIB-01A 당시 상태 | 직접 확인한 코드와 의미 |
| --- | --- | --- |
| 1. 사용자가 이미지 선택 | 없음 | app과 benchmark-runner의 Activity에 Photo Picker, `ACTION_OPEN_DOCUMENT`, Activity Result 경로가 없다. |
| 2. 이미지 읽기 | 없음 | 실제 이미지 URI/bytes를 읽거나 decode하는 경로가 없다. `ModelLoader.map()`은 모델 asset mmap이며 이미지 I/O가 아니다. |
| 3. 모델 입력 전처리 | 실제 이미지 경로 없음 | `DeterministicInputSet.legacyTimedInput()`은 합성 FLOAT32 tensor를 만든다. accuracy preflight는 host-preprocessed tensor를 읽으며 기기에서 이미지 전처리를 수행하지 않는다. |
| 4. 요청 큐 진입 | 없음 | benchmark-runner의 단일 executor와 `BenchmarkExecutionGate`는 run 중복 방지 수단이며 긴급·일반 요청 큐가 아니다. |
| 5. backend CPU/GPU 선택 | run 단위로 존재 | benchmark-runner `MainActivity`, `AutomationIntentParser`, `RunConfig`, `GpuBenchmarkEngine`이 CPU/GPU를 선택한다. 요청별 동적 선택과 NPU 실행은 없다. |
| 6. Interpreter 초기화 및 `run()` | 존재 | `ModelLoader.map()`, `ProductionBenchmarkEngineDependencies.createRuntime()`, `OfficialInferenceCoordinator`가 초기화와 공식 `Interpreter.run()` 구간을 제공한다. 현재 입력은 synthetic tensor다. |
| 7. 후처리 | 사용자 분류 경로 없음 | diagnostic checksum/readback과 accuracy comparator는 있지만 label mapping을 이용한 사용자용 top-k 결과 생성은 없다. |
| 8. 긴급 결과 output-ready | 없음 | Activity는 전체 benchmark 완료 메시지만 표시한다. 이미지별 결과 제공 가능 시점과 callback이 없다. |
| 9. 일반 결과 영구 저장 완료 | 없음 | telemetry/accuracy artifact 저장은 존재하지만 분류 결과 index 저장소와 이미지별 transaction 완료 경계는 없다. |

추가 확인:

- 모델 asset과 SHA-256은 `ModelLoader` 및 `model-manifest.json`에 존재한다.
- runner의 `GpuTelemetry`는 `SystemClock.elapsedRealtimeNanos()` 기반 event와 `Interpreter.run()` span을 기록하고 run context를 검증한다.
- app의 `TelemetryForegroundService`는 같은 Android monotonic clock으로 battery temperature와 Android thermal status를 기록한다.
- 기존 host orchestrator는 APK·모델·입력 artifact SHA-256, 기기 상태, manifest와 결과 provenance를 다루는 코드를 재사용할 수 있다.
- 모델 label mapping asset은 현재 runner에 없다. 실제 분류 결과와 정확도 gate를 위해 검증된 label 파일 및 hash가 필요하다.

CALIB-01A 당시 결론: 당시 production은 tensor benchmark 경로뿐이어서 사용자 이미지 종단간 calibration을 실행할 수 없었다. CALIB-01B가 별도 opt-in production 경로를 추가했지만 기존 benchmark 명령은 여전히 synthetic tensor 측정이므로 종단간 calibration으로 대체 사용하지 않는다.

## 3. 측정 경계와 event 계약

모든 device-side timestamp는 `SystemClock.elapsedRealtimeNanos()` 하나만 사용하고 manifest에 boot ID와 clock 이름을 기록한다. wall clock은 파일 정렬·사람 확인용이며 지연 계산에 사용하지 않는다.

### 3.1 요청 수명주기

각 요청은 canonical UUID `request_id`, `session_id`, `request_type`, `image_id`, `backend_requested`, `backend_actual`, `terminal_status`, `deadline_outcome`을 갖는다. 정상 요청은 다음 단조 증가 timestamp를 기록한다.

1. `picker_result_received_ns` 또는 background batch의 `image_discovered_ns`
2. `queue_enter_ns` — URI가 정해진 즉시, 이미지 I/O 전에 기록
3. `image_read_start_ns`, `image_read_end_ns`
4. `preprocess_start_ns`, `preprocess_end_ns`
5. `scheduler_decision_start_ns`, `scheduler_decision_end_ns`
6. 필요 시 `backend_prepare_start_ns`, `backend_prepare_end_ns`
7. `inference_start_ns`, `inference_end_ns`
8. `postprocess_start_ns`, `postprocess_end_ns`
9. 긴급: `output_ready_ns`
10. 일반: `persist_start_ns`, `persist_commit_ns`
11. `terminal_ns`

사용자가 picker를 보고 선택하는 시간은 공식 긴급 응답시간에 포함하지 않는다. 공식 시작은 `queue_enter_ns`다. picker callback 시각은 선택 경로가 실제로 실행됐다는 provenance로만 남긴다.

### 3.2 파생 구간

- 이미지 I/O = `image_read_end_ns - image_read_start_ns`
- 전처리 = `preprocess_end_ns - preprocess_start_ns`
- 큐 대기 = 실제 service 시작 − `queue_enter_ns`. service 시작은 이미지 I/O가 worker에서 시작되는 시점이다.
- backend 결정 = `scheduler_decision_end_ns - scheduler_decision_start_ns`
- backend 준비·전환 = `backend_prepare_end_ns - backend_prepare_start_ns`
- 순수 추론 = `inference_end_ns - inference_start_ns`; 기존 공식 `Interpreter.run()` 경계를 유지한다.
- 후처리 = `postprocess_end_ns - postprocess_start_ns`
- 긴급 output-ready 응답시간 = `output_ready_ns - queue_enter_ns`
- 일반 영구 저장 완료시간 = `persist_commit_ns - queue_enter_ns`
- cold 초기화는 interpreter/delegate가 없는 상태의 `backend_prepare`로 기록하고, warm 요청 통계에 섞지 않는다.

일반 결과의 `persist_commit_ns`는 app-private 영구 저장소 transaction이 성공적으로 반환되고 같은 request ID의 결과가 다시 읽을 수 있는 시점이다. 이는 저장 장치 controller의 물리적 flush 완료를 주장하지 않는다.

### 3.3 terminal 상태와 deadline 결과

- `succeeded`: 긴급 output-ready 또는 일반 durable persist commit까지 완료. 마감 후 완료돼도 이 terminal 상태와 결과를 유지한다.
- `failed`: I/O, decode, preprocessing, backend, inference, postprocessing 또는 저장 오류.
- `rejected`: 큐 상한이나 정책에 의해 수락되지 않음.
- `expired`: deadline 때문에 실제 output-ready/persistence 완료 전에 실행되지 않은 요청에만 사용한다.

deadline 결과는 terminal 상태와 분리한다. deadline 미설정은 `not_set`/null, deadline 이전 완료는 `on_time`/true, deadline 후 완료는 `late`/false, deadline이 설정됐으나 완료되지 않은 요청은 `not_completed`/false다. `failed`, `rejected`, `expired`에는 output 및 persisted result가 없어야 한다. 늦게 완료된 `succeeded` 요청은 전체 완료율 분자에는 포함하고 기한 내 완료율 분자에는 포함하지 않는다. 전체 완료율은 `succeeded / 전체 도착`, 기한 내 완료율은 `on_time / deadline 설정 도착`, 위반율은 `(late + not_completed) / deadline 설정 도착`으로 계산한다.

모든 도착 요청은 정확히 하나의 terminal 상태를 갖는다. 실패·거절·만료는 전체 도착 분모에 남기고 짧은 가상 지연값을 대입하지 않는다.

## 4. 입력과 provenance

- A24 pilot에 사용할 8개 실제 이미지 set을 고정한다. 최소 4개 class, class당 2개 이미지를 고정하고 각 원본 bytes의 SHA-256을 기록한다. 이 입력으로 S26 종단간 검증을 주장하지 않는다.
- 입력은 라이선스와 ground-truth를 확인한 뒤 고정한다. 이 작은 set은 pipeline·backend equivalence gate이며 일반적인 task accuracy를 주장하는 데이터셋이 아니다.
- Android production preprocessing은 versioned `android-mobilenet-v1-image-v3` 계약으로 기록한다. AndroidX `ExifInterface` 1.4.2로 실제 입력 bytes에 backed된 orientation 태그를 확인한다. 태그가 없으면 normal(1), 명시된 값은 1~8만 허용한다(명시된 0도 거부). orientation 1~8(미러 포함)을 먼저 적용한 뒤 중앙 0.875 square crop, Android bilinear 224×224 resize, RGB channel order, FLOAT32 `(value / 127.5) - 1`을 수행한다. 원본·EXIF 변환 후 크기와 orientation을 기록한다.
- Pillow host 검증은 이미지 bytes·magic MIME·원본 크기·EXIF·변환 후 크기를 검증하는 준비 gate다. Android Bitmap 전처리와 byte-identical하다고 주장하지 않는다.
- 모델 파일·model manifest·label mapping·전처리 configuration·각 이미지·각 APK의 크기와 SHA-256을 기록한다.
- Git HEAD, dirty diff 존재 여부와 diff hash, application ID/versionCode/versionName, device serial의 공개용 별칭, build fingerprint, OS/API, LiteRT version, boot ID를 기록한다.
- label mapping이 없거나 hash가 다르면 calibration을 시작하지 않는다.
- CPU와 GPU가 동일한 preprocessed input bytes를 사용했는지 input tensor SHA-256으로 확인한다.
- accuracy gate는 non-finite output 없음, CPU/GPU 출력 equivalence, label mapping 정합성과 고정 pilot set의 top-1/top-5 결과를 기록한다. 8개 이미지 결과로 전체 모델 정확도를 일반화하지 않는다.

## 5. 환경 계약

calibration mode는 `baseline_pilot`, `baseline_formal`, `thermal_stress`로 고정하며 누락·혼입을 거부한다. 각 session마다 다음을 기록한다.

- 고정된 물리적 위치와 가능한 경우 주변온도
- 충전 연결 여부, battery status와 SOC
- 화면 on/off, brightness와 orientation
- 앱 내부에서는 시작 battery temperature와 Android thermal status, timestamp가 있는 두 값의 원시 시계열과 최고값을 기록한다. timestamp는 `elapsedRealtimeNanos`다.
- AP/PA/SKIN은 앱 API에서 읽었다고 주장하지 않는다. A24에서는 host `dumpsys thermalservice` 수집으로 보완해야 한다.
- 시작·종료 wall clock과 monotonic bounds

`baseline_pilot`과 `baseline_formal`은 시작 Android thermal status가 1을 초과하면 시작 전에 거부한다. `baseline_formal`은 사전 고정된 battery temperature/stability policy와 그 canonical SHA-256을 요구하며 시작 battery temperature 상한을 앱에서 검사한다. `thermal_stress`는 baseline 집계에 합치지 않는다. 같은 기기 내 비교는 충전·화면 상태를 동일하게 유지한다.

A24 CALIB-01C 전에 host가 AP/PA/SKIN 시계열, cooling/stability window와 gate를 제공하고 app session ID/monotonic 시간과 연결해야 한다. 기존 `d1_logger_v4.py`에는 `dumpsys thermalservice`의 AP/SKIN/BAT/PA 수집과 coverage 검사가 있지만 calibration CLI/Activity와 자동 연결돼 있지 않다. 이 자동 연결과 사전 고정 policy는 실기기 baseline 실행의 외부 사전조건이며, 현재 앱 내부 battery 값으로 AP/PA/SKIN을 대체했다고 주장하지 않는다.

## 6. cold, warm과 backend 전환

- cold: 해당 backend의 interpreter/delegate 인스턴스가 없는 상태에서 모델 mmap, delegate 생성, interpreter 생성과 tensor allocation을 수행하는 첫 요청.
- warm: 동일 backend 인스턴스에서 고정된 3개 warm-up 요청을 완료한 이후의 요청. warm-up도 event는 남기되 latency 표본에서 제외한다.
- warm switch: CPU와 GPU 인스턴스가 모두 초기화된 상태에서 scheduler 결정부터 선택 backend의 inference 준비까지.
- cold switch: 대상 backend 인스턴스가 없어 선택 후 초기화가 필요한 전환.
- CPU→GPU와 GPU→CPU를 따로 기록한다. 인스턴스 재사용 여부와 메모리 상태를 manifest에 명시한다.

`Interpreter.run()` 중간 중단은 시도하지 않는다. 일반 batch 중단은 현재 이미지 결과를 terminal 상태로 만든 뒤 다음 이미지 경계에서만 수행한다.

## 7. 소규모 pilot과 변동성 중단 규칙

### 7.1 최초 규모

A24의 CPU/GPU backend 조합마다 독립 `baseline_pilot` session 5개로 시작한다. session 순서는 무작위화한다.

각 session은 다음을 포함한다.

1. cold 긴급 요청 1개.
2. warm-up 요청 3개.
3. 고정 8이미지 각각의 warm 긴급 요청 8개.
4. 같은 8이미지의 일반 batch 1개와 이미지별 저장 완료 8개.
5. session 묶음 전체에서 CPU→GPU 및 GPU→CPU warm/cold 전환을 방향별 최소 5회 확보.

urgent와 normal 측정 순서는 session마다 교대한다. OS page cache와 decode cache 여부를 기록하고 warm 통계와 cold 통계를 분리한다.

### 7.2 확장·중단 규칙

기기·backend·요청 유형별로 session-level median과 session-level empirical P95를 계산한다. 최초 5 session에서 다음 조건을 모두 만족하면 해당 cell의 calibration을 중단한다.

- session median의 robust CV(`1.4826 × MAD / median`)가 10% 이하.
- 현재 `n` session 집계와 직전 `n-2` session 집계의 median 및 empirical P95 변화가 각각 5% 이하.
- unexplained failure·rejection·expiration이 0개이고 accuracy gate가 모두 통과.
- 허용 thermal start 범위를 벗어난 session이 분석에 포함되지 않음.

하나라도 실패하면 독립 session을 2개 추가해 7개에서 다시 계산하고, 필요하면 최대 9개까지 늘린다. 9개에서도 안정 조건을 만족하지 못하면 표본을 임의로 계속 늘리거나 마감시간을 고정하지 않는다. 원인을 `unstable_calibration`으로 기록하고 입력·열·I/O·backend 변동 원인을 조사한다.

P95는 nearest-rank empirical quantile로 계산하고 요청 표본 수와 독립 session 수를 함께 보고한다. 여러 요청을 독립 session처럼 취급하지 않는다.

## 8. 절대 마감시간 사전 결정 규칙

마감시간은 기기별로 별도 계산한 실제 millisecond 상수이며 정책 평가 결과를 본 뒤 바꾸지 않는다.

1. accuracy gate를 통과한 CPU/GPU 중 warm 긴급 output-ready median이 더 낮은 backend를 기기의 reference backend `B*`로 정한다. 기존 80슬롯 우열을 자동 적용하지 않는다.
2. 안정 조건을 통과한 각 session에서 warm 긴급 output-ready P95 `U95_s`와 일반 이미지 persist-complete P95 `N95_s`를 구한다.
3. `U95 = max(U95_s)`, `N95 = max(N95_s)`로 session 간 보수적 값을 사용한다.
4. 긴급 deadline은 `ceil_10ms(N95 + U95)`로 정한다. 이는 이미 실행 중인 일반 이미지 한 건은 중단하지 않고 완료한 뒤 긴급 한 건을 처리하는 reference contract다.
5. 일반 deadline은 `ceil_10ms(N95 + 3 × U95)`로 정한다. 혼합 burst 조건의 긴급 3건이 앞서 처리되는 경우까지 허용한다.
6. cold 첫 요청은 별도 `cold_output_ready` 분포로 보고하고 위 warm scheduler deadline에 섞지 않는다. 제품 첫 실행 SLA가 필요하면 별도 결정한다.
7. CPU/GPU 전환 비용과 동시 실행 간섭은 위 deadline 안에서 정책이 감당해야 하며 deadline에 사후 가산하지 않는다.

`ceil_10ms(x)`는 x 이상인 가장 작은 10 ms 단위 값이다. 계산 입력, 계산 코드와 결과 JSON의 hash를 보존한다. 어떤 cell이라도 안정·정확도 gate를 통과하지 못하면 deadline 상태는 `calibration_pending`으로 유지한다.

## 9. 혼합 워크로드 조건 결정 규칙

reference backend `B*`의 warm 일반 per-image persist-complete median을 `N50`이라 하고 기기별 기준 처리능력을 `C = 1 / N50` images/s로 둔다. 이는 workload 생성용 capacity이며 최종 throughput 결과가 아니다.

정책 비교 전에 다음 synthetic arrival trace를 생성하고 seed와 전체 trace SHA-256을 고정한다.

- 낮은 부하: 총 평균 도착률 `0.4 × C`, 긴급 비율 10%, burst 없음.
- 지속 부하: 총 평균 도착률 `0.9 × C`, 긴급 비율 20%, burst 없음.
- 긴급 burst: 일반 평균 `0.6 × C`를 유지하면서 긴급 3건 burst를 `3 / (0.2 × C)`초마다 주입해 전체 장기 평균이 `0.8 × C`가 되게 한다.

도착은 scheduler 처리속도와 독립된 monotonic schedule로 생성한다. A24의 모든 정책에 byte-identical arrival trace를 사용한다. 실제 사용자 arrival log가 없으므로 이 조건은 synthetic임을 명시한다. S26용 새 arrival trace나 종단간 결과는 만들지 않는다.

혼합 실행 전에 reference backend로 짧은 admission probe를 수행한다. 낮은 부하에서 불필요한 queue 증가가 있거나 지속 부하가 즉시 안전 한계를 넘으면 workload를 실행하지 않고 capacity 계산·환경 조건을 재검토한다. 정책 결과를 본 뒤 특정 정책에 유리하게 도착률을 조정하지 않는다.

## 10. 산출물과 수용 기준

필수 산출물:

- immutable session manifest와 event JSONL
- 이미지·모델·전처리·label·APK provenance 및 SHA-256
- request별 timestamp, component duration, backend와 terminal 상태
- 환경·thermal 시계열
- 기기별 cold/warm/transition 표와 session-level 변동성
- deadline 계산 입력·출력과 workload arrival trace
- 제외·retry·failure 원기록

CALIB-01 실행 수용 기준:

- 모든 성공 요청 timestamp가 같은 monotonic domain에서 단조 증가함.
- component 합과 종단간 경계가 일치하고 누락·중복 request ID가 없음.
- 모든 도착 요청에 terminal 상태가 정확히 하나 있음.
- provenance hash가 실제 artifact와 일치함.
- deadline stability와 accuracy gate를 통과하거나 `calibration_pending` 상태를 명확히 유지함.

## 11. 재사용 부분과 CALIB-01B 구현 상태

CALIB-01B는 2026-09-17 최종 읽기 전용 감사에서 `CALIB_01B_PASS`로 종료했다. 로컬 JDK 17의 전체 `testDebugUnitTest lintDebug assembleDebug --rerun-tasks`가 성공했고 최신 XML/SARIF 직접 집계는 Kotlin/JVM 119건·failure/error/skip 0, lint error 0/warning 76이다. Python 전체 195건·failure/error 0/기존 skip 1, compileall·logger self-test·assembleDebug도 PASS다. 이는 host 구현 검증이며 A24 이미지 calibration 또는 정확도 실측 완료를 의미하지 않는다. 최신 APK·전처리 hash와 resolved history는 [PROJECT_STATUS.md](PROJECT_STATUS.md)에 기록한다.

재사용 가능:

- `ModelLoader`: 모델 asset mmap과 고정 모델 identity/hash.
- `RunConfig`, `AutomationIntentParser`, `GpuBenchmarkEngine`: run-level CPU/GPU 설정과 interpreter/delegate 생성·정리.
- `OfficialInferenceCoordinator`: 공식 `Interpreter.run()` timing 경계.
- `GpuTelemetry`와 app telemetry service: monotonic event, run context, thermal/battery 기록과 JSONL flush.
- host orchestrator/logger: device 선택, 안전 snapshot, artifact hash, manifest/provenance, bounded process 제어.
- accuracy preflight comparator: 동일 preprocessed tensor의 CPU/GPU 수치 동등성 검사.

CALIB-01B에서 구현한 경로:

1. benchmark-runner의 `CalibrationActivity`가 platform `ACTION_OPEN_DOCUMENT`로 manifest, label mapping, 긴급 단일 이미지와 일반 batch 이미지를 선택한다. 사람의 선택 시간은 표본에서 제외하고 picker callback 뒤 수락 시각부터 기록한다.
2. `AndroidCalibrationImageReader`와 `AndroidCalibrationImageDecoder`가 URI bytes를 bounded read하고 SHA-256·magic MIME·EXIF orientation을 확인한 뒤 Android `BitmapFactory`로 decode하고 orientation 1~8 변환을 적용한다.
3. `MobileNetCalibrationPreprocessor`가 EXIF 변환 후 중앙 0.875 crop, bilinear 224×224 resize, RGB FLOAT32 `(value / 127.5) - 1`을 수행한다. contract ID는 `android-mobilenet-v1-image-v3`, canonical configuration SHA-256은 `03e507dea1d4111681b6c1120fab7729967a19e49712ccc05d2e72e4f7762cf5`다. Kotlin/host CLI는 같은 configuration을 사용하며 이전 계약 manifest를 조용히 재해석하지 않는다.
4. `CalibrationPipeline`이 bounded FIFO, succeeded/failed/rejected/expired terminal 상태와 분리된 deadline 결과, fixed CPU/GPU 및 전환 probe, cold/warm/warm-up 구분을 제공한다. Interpreter 한 개를 동시에 여러 thread에서 호출하지 않는다.
5. `LiteRtCalibrationRuntimePool`이 backend별 Interpreter/delegate를 초기화하고 재사용하며 CPU와 GPU를 조용히 상호 fallback하지 않는다. GPU full-delegation 여부는 LiteRT Java API만으로 증명할 수 없어 `unverified_requires_host_delegate_log`로 명시하며, host full-delegation 증거 전에는 GPU accuracy/backend gate 통과로 간주하지 않는다.
6. `MobileNetCalibrationPostprocessor`가 non-finite 수와 output SHA-256을 `Interpreter.run()` timer 밖에서 계산하고 verified external label mapping으로 top-5를 만든다. 긴급 결과는 callback 가능한 객체가 완성된 `output_ready_ns`에서 완료된다.
7. 일반 결과는 app-private external-files session 아래 `results/<request UUID>.json`에 기록한다. 완료 의미는 임시 파일 write/flush, `FileDescriptor.sync()`, 동일 디렉터리 atomic rename, byte-for-byte readback 성공이다. 저장장치 controller의 물리 flush를 주장하지 않는다.
8. `CalibrationSessionArtifacts`가 session metadata, request JSONL, raw `thermal_samples.jsonl`, summary, result files와 provenance를 생성하고 exact artifact set, canonical 상대경로, regular-file/symlink containment, byte count, SHA-256, session/mode/protocol identity, terminal/deadline count를 재검증한다.
9. `tools/d1_calibration_cli.py`가 고정 input bundle의 실제 이미지, 1001행 label mapping, APK와 결과를 fail-closed 검증하고 side-effect 없는 `plan --dry-run`을 제공한다.

남은 실행 gap:

- 저장소에는 대표 이미지와 verified 1001-line label mapping이 없다. 임의 fixture를 대표 데이터로 승격하지 않으며 실제 A24 calibration은 이 두 입력을 별도로 확정하기 전에는 시작할 수 없다.
- GPU 결과는 기존 logger 방식의 full-delegation/fallback 증거와 결합해야 정식 calibration cell로 사용할 수 있다.
- A24의 strict `CompatibilityList` gate를 유지한다. GPU 진입 가능 여부는 후속 smoke test에서 확인하며 실패 시 CPU로 조용히 fallback하지 않는다. S26 compatibility override나 기기 모델 우회는 구현하지 않는다.
- A24 baseline의 AP/PA/SKIN 시계열 및 cooling/stability gate는 기존 host logger와 calibration session의 자동 결합이 남은 사전조건이다.
- mixed-workload arrival trace 생성·resume은 최종 scheduler 단계의 범위이며 이 vertical slice에는 포함하지 않았다.

## 12. CALIB-01B 실제 변경 범위

기존 파일:

- `benchmark-runner/src/main/java/com/example/d1check/benchmarkrunner/MainActivity.kt`
- `benchmark-runner/src/main/AndroidManifest.xml`
- `docs/PROJECT_PLAN.md`, `docs/PROJECT_STATUS.md`, `docs/DECISIONS.md`, 이 문서

신규 production/test 파일:

- `CalibrationContract.kt`, `CalibrationPipeline.kt`, `CalibrationAndroid.kt`, `CalibrationArtifacts.kt`, `CalibrationActivity.kt`
- `CalibrationPipelineProductionTest.kt`, `AndroidCalibrationImageIntegrationTest.kt`, `CalibrationArtifactValidatorTest.kt`, `CalibrationActivityEntryTest.kt`
- `tools/d1_calibration_cli.py`, `tools/test_d1_calibration_cli.py`

기존 `app/src/main/java/com/example/d1check/MainActivity.kt`, telemetry-contract, `GpuBenchmarkEngine`, diagnostic v1/v2 parser/schema는 수정하지 않았다. FIX3은 PNG/JPEG/WebP의 EXIF 처리 및 lint 권고를 위해 runner에 `androidx.exifinterface:exifinterface:1.4.2` 의존성을 추가한다([공식 릴리스](https://developer.android.com/jetpack/androidx/releases/exifinterface)). inference timer, calibration schema 2, artifact/provenance 구조와 저장 경로는 유지한다. `BitmapFactory`의 RuntimeException은 cause를 보존한 `IllegalArgumentException("Android image decode failed", cause)`로 변환하고 null도 명확히 실패한다. decode에서 Error/OutOfMemoryError는 잡지 않는다. `applyExifOrientation()`은 production `exifOrientationMatrix()`를 사용하며 테스트는 그 Matrix의 실제 좌표 변환으로 1~8/미러 의미를 확인하고 실제 EXIF JPEG reader→decoder의 크기 검증도 유지한다.

## 13. 실제 host CLI와 실행 절차

현재 구현된 parser의 입력·dry-run 명령은 다음과 같다. 이 명령은 ADB를 호출하거나 manifest/result를 쓰지 않는다.

```text
python tools/d1_calibration_cli.py validate-input --input-root <input-bundle> --manifest <input-bundle/input_manifest.json> --labels <input-bundle/label_mapping.txt> --apk <benchmark-runner-debug.apk>
python tools/d1_calibration_cli.py plan --input-root <input-bundle> --manifest <input-bundle/input_manifest.json> --labels <input-bundle/label_mapping.txt> --apk <benchmark-runner-debug.apk> --dry-run
python tools/d1_calibration_cli.py validate-result --root <pulled-session-root>
```

승인된 별도 설치 후에는 Benchmark Runner의 기존 launcher를 열고 `Open image calibration`을 선택한다. 이어서 검증된 manifest, 1001-line label mapping, manifest 순서의 이미지를 선택한다. 이번 구현·검증 작업에서는 ADB, 설치, 앱·실기기 실행을 하지 않았다.

## 14. calibration-v1 schema와 저장 경로

- protocol: `calibration-v1`, schema version: `2`, deadline state: `calibration_pending`.
- opt-in device root: `Android/data/com.example.d1check.benchmarkrunner/files/calibration-v1/<canonical session UUID>/`.
- 고정 session artifact: `input_manifest.json`, `label_mapping.txt`, `metadata.json`, `requests.jsonl`, `thermal_samples.jsonl`, `summary.json`, `provenance.json`.
- 일반 결과: `results/<canonical request UUID>.json`.
- self-hash 방지를 위해 세션 루트 상대경로 `provenance.json`만 `artifact_set`에서 제외한다. `results/provenance.json`, `nested/path/provenance.json` 등 중첩된 동명 파일은 허용되지 않은 추가 artifact로 거부하며 오류에 상대경로를 표시한다.
- `requests.jsonl`은 요청마다 protocol/session/request/image identity, requested/actual backend, fallback 상태, warm-up/cold/warm/transition, terminal 상태, 모든 component timestamp, queue wait, scenario end-to-end, tensor/output hash, non-finite count, top-1/top-5 및 persistence 경계를 기록한다.
- device timestamp는 모두 `SystemClock.elapsedRealtimeNanos()`다. runtime은 input rewind와 output buffer clear를 먼저 수행한 뒤 `Interpreter.run()` 직전에 start, 직후에 end를 읽는다. decode, 전처리, 후처리, checksum, telemetry와 파일 I/O는 이 timer 밖이다.
- provenance가 생기기 전 중단된 session은 partial이며 성공 artifact로 사용하지 않는다. finalized session도 production validator와 host validator를 모두 통과해야 사용할 수 있다.
