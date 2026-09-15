# D1Check CALIB-01A 종단간 calibration protocol

- 문서 버전: 1
- 작성일: 2026-09-15
- 상태: 설계 완료, CALIB-01B 구현 전 실행 불가
- 적용 기기: Galaxy A24, Galaxy S26
- 절대 마감시간 상태: `calibration_pending`
- 목적: 실제 사용자 이미지 경로의 구성요소별 종단간 지연과 변동성을 측정해 기기별 절대 마감시간 및 혼합 워크로드 조건을 평가 전에 고정한다.

## 1. 범위와 비목표

- 긴급 요청은 사용자가 갤러리 사진 한 장을 선택하고 즉시 분류 결과를 요청하는 작업이다.
- 일반 요청은 여러 갤러리 사진을 백그라운드에서 분류·색인하는 작업이며, 개별 이미지 결과 저장을 요청 완료 경계로 삼는다.
- 1차 backend는 CPU와 GPU다. NPU는 capability와 실제 실행 proof가 있을 때만 별도 후보로 추가하며 CALIB-01의 필수조건이 아니다.
- A24와 S26를 별도로 분석한다. 표본과 마감시간을 두 기기 사이에서 합치지 않는다.
- 이 calibration은 스케줄러 우수성, 에너지 절감 또는 GPU 내부 H2D/GPU/D2H·fence 시간을 입증하지 않는다.
- 기존 80슬롯의 tensor-only `Interpreter.run()` 지연을 이미지 종단간 지연으로 사용하지 않는다.

## 2. 현재 production 경로 감사

| 필수 경로 | 현재 상태 | 직접 확인한 코드와 의미 |
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

결론: 현재 production은 tensor benchmark 경로이며 이 프로토콜의 사용자 이미지 종단간 calibration을 실행할 수 없다. CALIB-01B가 아래 gap을 production 경로에 연결하기 전에는 기존 benchmark 명령으로 대체 측정하지 않는다.

## 3. 측정 경계와 event 계약

모든 device-side timestamp는 `SystemClock.elapsedRealtimeNanos()` 하나만 사용하고 manifest에 boot ID와 clock 이름을 기록한다. wall clock은 파일 정렬·사람 확인용이며 지연 계산에 사용하지 않는다.

### 3.1 요청 수명주기

각 요청은 canonical UUID `request_id`, `session_id`, `request_type`, `image_id`, `backend_requested`, `backend_actual`, `status`를 갖는다. 정상 요청은 다음 단조 증가 timestamp를 기록한다.

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

### 3.3 terminal 상태

- `success`: 긴급 output-ready 또는 일반 persist commit까지 완료.
- `failed`: I/O, decode, preprocessing, backend, inference, postprocessing 또는 저장 오류.
- `rejected`: 큐 상한이나 정책에 의해 수락되지 않음.
- `expired`: 절대 마감 전에 시작 또는 완료할 수 없어 만료 정책이 적용됨.

모든 도착 요청은 정확히 하나의 terminal 상태를 갖는다. 실패·거절·만료는 전체 도착 분모에 남기고 짧은 가상 지연값을 대입하지 않는다.

## 4. 입력과 provenance

- 동일한 8개 실제 이미지 pilot set을 두 기기에서 사용한다. 최소 4개 class, class당 2개 이미지를 고정하고 각 원본 bytes의 SHA-256을 기록한다.
- 입력은 라이선스와 ground-truth를 확인한 뒤 고정한다. 이 작은 set은 pipeline·backend equivalence gate이며 일반적인 task accuracy를 주장하는 데이터셋이 아니다.
- 중앙 crop 비율, resize algorithm, RGB channel order, FLOAT32 변환과 normalization을 canonical JSON으로 기록하고 SHA-256을 계산한다.
- 모델 파일·model manifest·label mapping·전처리 configuration·각 이미지·각 APK의 크기와 SHA-256을 기록한다.
- Git HEAD, dirty diff 존재 여부와 diff hash, application ID/versionCode/versionName, device serial의 공개용 별칭, build fingerprint, OS/API, LiteRT version, boot ID를 기록한다.
- label mapping이 없거나 hash가 다르면 calibration을 시작하지 않는다.
- CPU와 GPU가 동일한 preprocessed input bytes를 사용했는지 input tensor SHA-256으로 확인한다.
- accuracy gate는 non-finite output 없음, CPU/GPU 출력 equivalence, label mapping 정합성과 고정 pilot set의 top-1/top-5 결과를 기록한다. 8개 이미지 결과로 전체 모델 정확도를 일반화하지 않는다.

## 5. 환경 계약

각 session마다 다음을 기록한다.

- 고정된 물리적 위치와 가능한 경우 주변온도
- 충전 연결 여부, battery status와 SOC
- 화면 on/off, brightness와 orientation
- 시작 battery/AP/PA/SKIN 온도 중 기기에서 제공되는 값
- session 최고 온도와 Android thermal status 전체 시계열
- 시작·종료 wall clock과 monotonic bounds

같은 기기 내 비교는 충전·화면 상태를 동일하게 유지한다. 시작 Android thermal status가 1을 초과하거나 사전 고정한 시작 온도 범위를 벗어나면 측정하지 않고 cooling/retry 상태로 남긴다. A24와 S26의 센서 절대값을 직접 동등하게 취급하지 않는다.

## 6. cold, warm과 backend 전환

- cold: 해당 backend의 interpreter/delegate 인스턴스가 없는 상태에서 모델 mmap, delegate 생성, interpreter 생성과 tensor allocation을 수행하는 첫 요청.
- warm: 동일 backend 인스턴스에서 고정된 3개 warm-up 요청을 완료한 이후의 요청. warm-up도 event는 남기되 latency 표본에서 제외한다.
- warm switch: CPU와 GPU 인스턴스가 모두 초기화된 상태에서 scheduler 결정부터 선택 backend의 inference 준비까지.
- cold switch: 대상 backend 인스턴스가 없어 선택 후 초기화가 필요한 전환.
- CPU→GPU와 GPU→CPU를 따로 기록한다. 인스턴스 재사용 여부와 메모리 상태를 manifest에 명시한다.

`Interpreter.run()` 중간 중단은 시도하지 않는다. 일반 batch 중단은 현재 이미지 결과를 terminal 상태로 만든 뒤 다음 이미지 경계에서만 수행한다.

## 7. 소규모 pilot과 변동성 중단 규칙

### 7.1 최초 규모

각 기기와 CPU/GPU backend 조합마다 독립 session 5개로 시작한다. session 순서는 기기별로 무작위화한다.

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

도착은 scheduler 처리속도와 독립된 monotonic schedule로 생성한다. 같은 기기에서는 모든 정책에 byte-identical arrival trace를 사용한다. 기기별 C가 다르므로 A24와 S26 trace는 별도이며 결과를 하나의 표본으로 합치지 않는다. 실제 사용자 arrival log가 없으므로 이 조건은 synthetic임을 명시한다.

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

## 11. 재사용 가능 부분과 구현 gap

재사용 가능:

- `ModelLoader`: 모델 asset mmap과 고정 모델 identity/hash.
- `RunConfig`, `AutomationIntentParser`, `GpuBenchmarkEngine`: run-level CPU/GPU 설정과 interpreter/delegate 생성·정리.
- `OfficialInferenceCoordinator`: 공식 `Interpreter.run()` timing 경계.
- `GpuTelemetry`와 app telemetry service: monotonic event, run context, thermal/battery 기록과 JSONL flush.
- host orchestrator/logger: device 선택, 안전 snapshot, artifact hash, manifest/provenance, bounded process 제어.
- accuracy preflight comparator: 동일 preprocessed tensor의 CPU/GPU 수치 동등성 검사.

구현 gap:

1. 실제 system photo picker와 batch image URI 선택·권한 유지.
2. URI bytes 읽기·decode와 입력 bytes SHA-256.
3. MobileNet용 on-device crop/resize/RGB/FLOAT32 normalization 및 configuration hash.
4. 긴급·일반 요청 model, bounded queue, terminal-state machine과 요청별 backend 결정.
5. label mapping 기반 top-k 후처리와 긴급 output-ready callback/UI.
6. 일반 이미지 결과 index의 transaction commit 및 readback 경계.
7. request-level event schema, cold/warm/transition 상태와 정확도 gate.
8. calibration 전용 host manifest, arrival trace 생성·검증과 resume/fail-closed 처리.

## 12. CALIB-01B 변경 허용 후보

다음은 구현 승인 전 후보 목록이며 이 문서가 수정 권한을 부여하지 않는다.

기존 파일 후보:

- `benchmark-runner/src/main/java/com/example/d1check/benchmarkrunner/MainActivity.kt`
- `benchmark-runner/src/main/java/com/example/d1check/benchmarkrunner/GpuBenchmarkEngine.kt`
- `benchmark-runner/src/main/java/com/example/d1check/benchmarkrunner/RunConfig.kt`
- `benchmark-runner/src/main/AndroidManifest.xml`
- `benchmark-runner/build.gradle.kts` — 새 의존성이 실제로 필요할 때만
- `telemetry-contract/src/main/java/com/example/d1check/contract/GpuTelemetry.kt`
- `tools/d1_experiment_orchestrator.py` 또는 별도 calibration orchestrator와 관련 테스트

신규 파일 후보:

- `CalibrationRequest.kt`, `CalibrationRequestQueue.kt`, `CalibrationEventRecorder.kt`
- `ImageInputLoader.kt`, `MobileNetImagePreprocessor.kt`, `ClassificationPostprocessor.kt`
- `ClassificationResultStore.kt`, verified label mapping asset, preprocessing manifest
- 각 production class의 JVM/Robolectric 테스트와 host Python 테스트

기존 `app/src/main/java/com/example/d1check/MainActivity.kt`에는 사용자 변경이 있으므로 기본 후보에서 제외한다. benchmark-runner 안에 실제 이미지 경로를 구현하고 기존 telemetry app과 provider 계약을 재사용하는 방안을 우선한다.

## 13. 제안 명령 상태

현재 CLI/parser에는 CALIB-01 image request 명령이 없으므로 실행 가능한 실기기 calibration 명령을 제시할 수 없다. 기존 diagnostic/benchmark 명령을 사용하면 synthetic tensor만 측정하므로 금지한다.

CALIB-01B는 구현 후 실제 `--help`에 다음 의미의 명시적 인터페이스를 제공해야 한다.

```text
<calibration-cli> prepare --device <alias> --input-manifest <path>
<calibration-cli> run --device <alias> --backend <CPU|GPU> --session-manifest <path>
<calibration-cli> validate --session-root <path>
```

위 표기는 인터페이스 제안일 뿐 현재 존재하는 명령이나 option 이름이 아니다. 실제 명령은 구현된 parser와 `--help`를 읽어 확정하며, CALIB-01A에서는 ADB·APK 설치·앱·실기기 명령을 실행하지 않는다.
