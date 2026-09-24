# D1Check 결정 기록

이 문서는 방향 변경을 날짜순으로 기록한다. 각 항목에 제안 / 채택 / 대체됨 상태를 표시한다. 아래 초기 항목은 이전 계획에서 이관한 작업 방향이며, 개별 수치·실험 조건 확정을 의미하지 않는다. 이번 개정은 사용자 요청에 따른 문서 보강이다.

> 현재 계획은 개정4.4에 날짜별 후속 결정을 적용한다. S26·NPU 범위는 [2026-09-24 협업 결정](#s26-npu-20260924)을 우선한다. 과거 결정은 이력으로 보존한다. 새 시나리오·모델 후보·효과 수치는 아래에 명시한 검증/미확정 상태를 유지한다.

## 2026-09-15 — 프로젝트 목표 재정의

- 단일 Android 앱의 긴급·일반 AI 요청 스케줄링 문제로 범위를 고정한다.
- 운영체제 전체의 자원 스케줄러는 범위에 포함하지 않는다.
- 초기 주목적은 긴급 요청 P95 응답시간 감소로 두었다. DEFINE-01에서 안전·정확도와 긴급 마감 위반을 P95보다 앞선 사전적 우선순위로 구체화했다.
- 근거: 기기별 CPU/GPU 성능 차이는 확인했지만 동적 정책의 추가 효과는 아직 확인되지 않았다.

## 2026-09-15 — 초기 구현 범위

- 현재 모델, CPU/GPU, 긴급·일반 두 요청 종류, 비선점 실행을 초기 범위로 한다.
- CPU와 GPU의 동시 실행은 간섭을 별도로 확인하기 전에는 사용하지 않는다.
- NPU와 강화학습은 초기 완성의 필수 조건에서 제외한다.

## 2026-09-15 — 비교정책과 평가 원칙

- B0: 기기별 최속 고정 backend + FIFO.
- B1: 기기별 최속 고정 backend + 긴급 우선.
- B2: CPU/GPU 고정 후보에 긴급 우선·단순 열 대응을 적용하고 개발 자료로 선정. 짧은 단독 추론 최속값만으로 고정하지 않는다.
- P: 큐·마감·열 상태를 함께 사용하는 제안정책.
- 같은 요청 도착 기록, 입력, 마감시간, 만료·거절 규칙과 종료 규칙으로 비교한다.
- 전체 도착 요청을 분모로 사용하며 실패와 미완료를 제외해 P95를 유리하게 만들지 않는다.

## 2026-09-15 — 증거 분리

- A24/S26 formal, diagnostic v2 trace-off/on, 새 혼합 요청 실험을 서로 합치지 않는다.
- 원시 자료는 불변으로 보존하고 파생 분석은 새 경로와 입력 해시를 갖는다.
- 온도 차이를 에너지 차이로 표현하지 않는다.

## 2026-09-15 — 문서 개정 2

- 상태: 채택 — 사용자가 검토사항을 반영한 수정을 요청함.
- 내용: 선택적 읽기, 단계별 체크포인트, 읽기 전용 예외, 증거 버전 연결, 조건부 P95와 전체 서비스율 분리, B2 후보 선정 보강.
- 미확정: 36세션, 개선 10%, 허용 감소 2%p, 실제 마감·열 기준. 개발 결과와 사용 요구를 근거로 평가 전에 고정한다.
- 영향: AGENTS, STATUS, PLAN, 설치 안내. 구현·실기기 실행을 수행했다는 뜻은 아니다.

## 2026-09-15 — DEFINE-01 공식 사용·평가 계약

- 상태: 채택 — 사용자가 프로젝트의 공식 정의로 명시함.
- 범위: D1Check는 Android 운영체제 전체가 아니라 하나의 온디바이스 AI 앱 내부에서 CPU/GPU/NPU 후보를 선택하고 긴급·일반 요청 큐를 관리하는 애플리케이션 수준 스케줄러다.
- 사용자 시나리오: 긴급 요청은 사용자가 갤러리 사진 한 장의 즉시 분류 결과를 요구하는 대화형 작업이고, 일반 요청은 여러 갤러리 사진을 백그라운드에서 분류·색인하는 일괄 작업이다.
- 완료 시점: 긴급 응답은 앱 큐 진입부터 결과가 사용자에게 제공 가능한 시점까지, 일반 요청은 큐 진입부터 해당 이미지 결과 저장까지다. 순수 `Interpreter.run()` 지연과 종단간 지연을 분리한다.
- 일반 작업 처리 후보: 현재 일반 이미지 완료 후 긴급 실행, 다음 이미지 경계에서 일반 batch 중단, 다른 가용 자원 동시 실행을 비교한다. `Interpreter.run()` 중간 강제 중단은 가정하지 않는다.
- 자원: 1차 구현은 CPU/GPU다. NPU는 capability detection과 실제 실행 검증을 통과한 기기에서만 활성화하며, 미지원·접근 실패 시 CPU/GPU로 정상 동작한다. S26의 현재 NNAPI 노출은 `nnapi-reference` CPU뿐이며 NPU 지원은 성공 필수조건이 아니다.
- KPI: 긴급 output-ready 응답시간 P95, 긴급 마감 위반율, 일반 기한 내 완료율, 전체 도착 대비 완료율, 처리량, 최고 온도 또는 Android thermal status, CPU/GPU 실제 사용 비율, 정확도 검증 통과 여부를 각각 보고한다. 실패·거절·만료는 전체 도착 분모에서 제외하지 않는다.
- 목적함수: 안전·정확도 제약, 긴급 마감 위반 최소화, 긴급 P95 최소화, 일반 기한 내 완료율 최대화, 처리량 최대화, 온도·전환 비용 최소화의 사전적 순서를 사용한다. 가중합은 아직 채택하지 않는다.
- 마감시간: 상태는 `calibration_pending`이다. 기존 80슬롯은 순수 추론 중심이므로 CALIB-01의 실제 이미지 종단간 측정 후 평가 전에 절대값을 사전 고정한다.
- 연구 근거: A24에서는 CPU 중앙 약 41.2 ms 대 GPU 약 131.6 ms(GPU/CPU 약 3.196), S26에서는 GPU가 pooled CPU보다 duty별 약 1.062~1.201배 빨랐다. 자원 우열이 기기마다 달라 기기별 calibration이 필요하다.
- S26 공시: 20개 block-duty 대응 비교 모두 GPU가 더 빠르고 AP 온도 상승도 더 낮았으며, 모든 GPU run은 31/31 노드 full delegation과 fallback 없음이 확인됐다. `gpu_compatibility_list_supported=false`, `formal_gpu_compat_list_override=true`를 결과에 반드시 공시한다.
- 남은 제한: A24 위치 변경, 실제 FP32/FP16 하드웨어 실행 여부 unknown, 미검증 에너지 단위, GPU 내부 H2D/GPU/D2H·fence timing 부재, S26 dataset manifest 문구 수정 필요, 설치 APK와 Git 소스의 완전한 cryptographic binding 부족, S26 재시도 raw run 하나의 불완전한 failure 기록.
- 영향: PROJECT_PLAN 개정 3, PROJECT_STATUS의 DEFINE-01 완료 및 CALIB-01 전환. production 코드·테스트·실험 데이터는 변경하지 않는다.

## 2026-09-15 — CALIB-01A 종단간 calibration 설계

- 상태: 채택 — 측정 실행 전 구현·검증해야 할 calibration protocol로 사용한다. 절대 마감시간 값은 여전히 `calibration_pending`이다.
- 코드 감사: 현재 production에는 run 단위 CPU/GPU 선택과 tensor-only Interpreter 초기화·run, telemetry/provenance는 있지만 photo picker, 실제 이미지 I/O·전처리, 긴급·일반 큐, 사용자 후처리/output-ready와 분류 결과 영구 저장 경로는 없다.
- 결정: 기존 tensor benchmark를 종단간 calibration으로 사용하지 않고 CALIB-01B에서 누락 경로를 실제 production 흐름에 연결한 뒤 측정한다.
- 시계·상태: 모든 device timestamp는 `SystemClock.elapsedRealtimeNanos()`를 사용하고 성공·실패·거절·만료를 전체 도착 분모에 남긴다.
- pilot: 기기·backend별 독립 session 5개로 시작하고 사전 변동성 기준을 만족하지 못하면 2개씩 최대 9개까지 확장한다. 9개에서도 불안정하면 deadline을 고정하지 않는다.
- deadline: 기기별 fastest validated warm backend를 reference로 삼고 일반 이미지 한 건의 비선점 완료와 긴급 처리 비용에서 urgent deadline을, 긴급 3건 burst 허용에서 normal deadline을 사전 공식으로 계산한다. 정책 평가 후 변경하지 않는다.
- workload: reference warm 일반 처리능력에 대한 0.4/0.9 utilization과 0.6 일반 + 3건 urgent burst 조건을 기기별로 생성하며 동일 기기 정책 간 arrival trace를 고정한다. 실제 사용자 로그가 없는 synthetic 조건임을 공시한다.
- 영향: `docs/CALIBRATION_PROTOCOL.md`, PROJECT_PLAN의 CALIB-01A/01B 연결, PROJECT_STATUS의 다음 작업 CALIB-01B. production 코드·테스트·실기기와 기존 자료는 이 단계에서 변경하지 않는다.

## 2026-09-16 — CALIB-01B 모듈 경계와 영구 저장 완료 의미

- 상태: 채택 — CALIB-01A의 후보를 현재 production 소유권에 맞춰 최소 구현함.
- 결정: 실제 이미지 calibration production 경로는 모델 asset, LiteRT, GPU delegate를 소유한 `benchmark-runner`에 둔다. telemetry-only app의 기존 사용자 `MainActivity`와 formal/diagnostic v1/v2 경로는 변경하지 않는다.
- 영구 저장 완료: app-private external-files session의 임시 파일에 write/flush하고 `FileDescriptor.sync()`한 뒤 동일 디렉터리 최종 파일로 atomic rename하고 byte-for-byte readback에 성공한 시점이다. 저장장치 controller의 물리 flush 완료는 주장하지 않는다.
- backend: CPU/GPU는 요청 전에 고정한다. backend별 Interpreter를 한 worker에서 재사용하며 GPU 실패를 CPU로 조용히 대체하지 않는다. Java API로 GPU full delegation을 증명할 수 없으면 `unverified_requires_host_delegate_log`를 기록하고 host 증거 전에는 해당 GPU cell을 정식 결과로 승인하지 않는다.
- artifact: `calibration-v1`/schema 1을 기존 v1/v2와 분리하고 canonical session/request UUID, 고정 경로, exact artifact set, byte count와 SHA-256을 production/host 양쪽에서 fail-closed 검증한다.
- 영향: benchmark-runner calibration production/test, 별도 host CLI/test, CALIBRATION_PROTOCOL/PLAN/STATUS. 동적 scheduler, mixed arrival generator, ADB 실행은 포함하지 않는다.
- 마감시간: 전체 검증과 A24 pilot 전까지 `calibration_pending`을 유지한다.

## 2026-09-16 — CALIB-01B-FIX2-A24 범위·deadline·thermal·EXIF 계약

- 상태: 채택.
- 직접 실기기 범위: CALIB-01C와 최종 스케줄러의 새 실기기 검증은 Galaxy A24만 수행한다. S26 formal 80슬롯은 기기별 CPU/GPU 특성 차이의 보조 자료로 유지하며 S26 end-to-end calibration·스케줄러 검증을 주장하지 않는다.
- GPU: strict `CompatibilityList` gate와 silent CPU fallback 금지를 유지한다. S26 compatibility override나 기기 모델 우회는 구현하지 않는다. A24 GPU 진입 가능 여부는 후속 smoke에서 확인한다.
- 완료와 deadline: output-ready 또는 durable persistence가 완료되면 늦었더라도 `terminal_status=succeeded`다. `deadline_outcome`은 `not_set`, `on_time`, `late`, `not_completed`로 분리한다. `expired`는 deadline 때문에 실제 완료되지 못한 요청에만 사용하며 failed/rejected/expired에는 결과 artifact가 없어야 한다.
- 집계: 늦은 성공은 전체 완료율에는 포함하고 기한 내 완료율에는 포함하지 않는다. 실패·거절·만료를 전체 도착 분모에서 제외하지 않는다.
- thermal: `baseline_pilot`, `baseline_formal`, `thermal_stress`를 분리한다. baseline 시작 thermal status는 0/1만 허용하고 formal은 사전 고정 temperature/stability policy와 hash를 요구한다. stress는 baseline에 합치지 않는다.
- 관측 경계: 앱은 battery temperature와 Android thermal status의 monotonic 원시 시계열을 기록한다. AP/PA/SKIN은 앱에서 측정했다고 주장하지 않으며 A24 baseline 전에 host logger의 시계열·cooling/stability gate와 calibration session 자동 연결이 필요하다.
- 입력: minSdk 24의 Android framework `ExifInterface`로 orientation 1~8을 적용한 뒤 versioned Android preprocessing 계약을 실행한다. 자체 EXIF parser는 만들지 않는다. Pillow host 검증과 Android preprocessing이 byte-identical하다고 주장하지 않는다. input bundle은 실제 파일 크기·SHA-256·magic MIME·크기·EXIF·label/APK 및 exact file set을 fail-closed 검증한다.

## 2026-09-17 — CALIB-01B-FIX3 EXIF/decode/Matrix 수정

- 상태: 채택. FIX2의 framework EXIF/preprocessing-v2 선택을 대체한다.
- 근거: EXIF 없는 정상 PNG의 합성 orientation 0, Robolectric decode RuntimeException, transformed bitmap backing 부재가 재현됐다는 사용자 확인.
- 결정: AndroidX ExifInterface 1.4.2를 사용한다. 원본 byte offset이 있는 명시 orientation은 1~8만 허용하고 태그 부재는 normal(1)로 처리한다. 명시 0/9 등은 거부한다. 자체 EXIF parser를 추가하지 않는다.
- 전처리 계약: `android-mobilenet-v1-image-v3`, canonical SHA-256 `03e507dea1d4111681b6c1120fab7729967a19e49712ccc05d2e72e4f7762cf5`. host CLI와 Android를 함께 갱신하며 Pillow byte-identical 주장은 하지 않는다.
- decode: RuntimeException만 cause 보존 IllegalArgumentException으로 변환한다. Error/OOM은 잡지 않는다.
- 검증: production Matrix 좌표로 1~8/미러 의미를 검사하고 실제 EXIF JPEG reader→decoder를 유지한다. Shadow bitmap의 getPixels에 의존하지 않는다. 테스트 수 3개·기존 inference timer·v1/v2·artifact/provenance·A24-only 범위는 유지한다.

## 2026-09-17 — 대회 목표에 맞춘 두 작업·강한 비교 중심 계획 개정

- 상태: 채택 — 사용자의 “우리의 계획을 수상 가능성을 높여서 더 나은 방향으로 발전” 요청에 따른 계획 개정. 코드/실기기 완료 또는 수상 가능성의 정량 입증이 아니다.
- 유지: A24-only, 단일 앱 수준 제어, 비선점, 전체 도착 분모, 품질·일반 서비스·열/메모리 제약, 기존 80슬롯/v1/v2/calibration-v1 보존. NPU·강화학습은 선택적 확장이다.
- 변경: 단일 분류 모델의 긴급/일반 시나리오에서 서로 다른 두 실제 AI 작업으로 주평가를 확장한다. 초기 직렬 경로 이후 실측으로 검증된 조합만 최대 두 건 병행한다. 09-15 초기 범위/DEFINE-01의 단일 모델 한정은 새 주평가에 대해 대체하며 기존 구현 계약에는 소급하지 않는다.
- 우선 검증할 사용 가설: 오프라인 사진 정리 중 백그라운드 분류·색인과 선택 사진의 대화형 객체탐지. 현장 수요·최종 모델 선정은 SCOPE-02/MODEL-02에서 검증한다. 통역/OCR/게임은 구현 사실이나 필수 범위가 아니다.
- 모델 후보: 분류 EfficientNet-Lite0 FLOAT32, 탐지 EfficientDet-Lite0 FLOAT32(부적합 시 SSD MobileNetV2 FLOAT32 검토). 최신성 대신 출처/labels/license·A24 호환성·품질·메모리·측정 가능성으로 선택한다. 후보는 배포 파일을 검증하기 전 승인 모델이 아니다.
- 기존 MobileNet V1과 1001행 라벨 미확인 문제를 보존한다. CALIB-01B PASS는 유지, CALIB-01C-INPUT은 legacy 입력 준비로 보류/재계획한다. 라벨을 임의 생성하거나 새 모델 라벨을 기존 출력에 붙이지 않는다. 새 모델도 독립적인 label provenance gate를 통과해야 한다.
- 비교: 개정 4의 B2는 task별 고정 배정·직렬/허용 병행·단순 열 대응 중 개발자료로 고른 강한 정책이다. B3(단독 프로파일 기반 EDF/earliest-finish)를 추가한다. P는 실측 간섭과 준비 비용으로 시작/대기·경로를 결정한다. 구 B2 결과는 개정 없이 재사용하지 않는다.
- 지표: 새 주평가는 예정 도착→완료, enqueue→완료도 병기한다. 긴급 기한 내 서비스율과 조건부 P95, 일반 기한 내 완료율/aging·backlog를 함께 보고한다. 일반 하한·허용차·실질 개선 수치는 evaluation 전에 freeze한다.
- 열: 스로틀링 유도는 필수조건이 아니다. 새 실험의 기본 안전/비교 조건은 검증 가능한 system thermal/battery·cooling policy로 집행하고 AP/PA/SKIN은 가능한 진단 자료로 결합한다. 구 calibration-v1의 AP/PA/SKIN 외부 gate를 완료 처리하거나 삭제하지 않는다. 센서 부재는 기록하며 열 인과·에너지 절감 주장을 제한한다.
- 프로토콜: 기존 image-v3와 schema 2 유지. `multitask-v1`은 새 계획용 예약 ID이며 별도 구현·validator가 필요하다. 기존 CLI에서 새 manifest가 실행된다고 주장하지 않는다.
- 미확정: 구체 모델 파일/hash·runtime, 실제 사용자 deadline, 일반 서비스 하한, 안전 온도/stability 값, 튜닝 예산·최종 반복 수. 상태는 `calibration_pending`/`thresholds_pending`이다.
- 영향: AGENTS, PROJECT_PLAN/STATUS/DECISIONS, CALIBRATION_PROTOCOL의 적용 범위 표시, 신규 MULTITASK_EXPERIMENT_PROTOCOL. production·입력·APK·기존 데이터는 변경하지 않는다.

## 2026-09-17 — 개정 4.1: 사용 사례와 혼합 요청 주평가 분리

- 상태: 채택 — 사용자가 한 사용 상황으로 연구를 한정하지 않는 방향의 수정을 요청했다.
- 연구 범위는 한 앱의 제한된 CPU/GPU를 공유하는 여러 AI 요청의 순서·경로·병행 결정이다. 사진 정리는 대표 시연 후보이며 필수 사용 상황이나 앱 기능으로 고정하지 않는다.
- 두 실제 작업의 초기 후보와 A24-only, 비선점·최대 두 건 병행·기존 데이터/계약 보존은 유지한다. task ID와 요청 등급을 독립시키고 task별 등급 배치 변경을 사전 지정 보조 조건으로 검증한다.
- 주평가는 일반 backlog 중 긴급 burst와 지속 혼합 요청이다. 저부하·동일 등급 경합은 overhead·공정성·적용 범위를 확인하는 보조 조건이며 primary 판정을 대체하지 않는다.
- 실기기 실험은 요청 도착만 합성·재생하고 모델·전후처리·I/O는 실제로 실행한다. 별도 이산사건 시뮬레이션은 실측 서비스·준비·간섭으로 보정하고 독립 실기기 자료에서 검증한 뒤 조건을 탐색한다. 두 방법의 표본·결과·provenance를 분리한다.
- 수동 시연·합성 도착 재생·가상 시뮬레이션을 구분한다. 모델 실행을 sleep으로 대체하거나 미측정 통역/OCR/게임의 성능을 검증했다고 주장하지 않는다. 가상 온도·에너지 효과도 검증된 모형 없이 만들지 않는다.
- 사용 패턴의 현실 근거는 조사하되 특정 사진 앱의 수요 인터뷰를 모든 개발의 선행 조건으로 만들지 않는다. 미확인 패턴은 합성 가정으로 공시한다.
- 현재 작업 SCOPE-02, deadline/thresholds 미확정 상태와 개발→동결→독립 평가 원칙을 유지한다. 이 결정은 새 구현·실측 PASS가 아니다.

## 2026-09-17 — SCOPE-02 근거 경계와 MODEL-02 분리

- 상태: 채택 — [SCOPE_02_EVIDENCE.md](SCOPE_02_EVIDENCE.md)에 확인 사실·추론·합성 가정을 분리해 기록하고 다음 작업을 `MODEL-02A`로 전환한다.
- 기존 작업: A24/S26 80슬롯, diagnostic v2, CALIB-01B는 폐기하지 않는다. 자원 우열의 기기 의존성, 측정·provenance, production 측정 경계의 근거로 유지한다. legacy MobileNet 8장/1001행 라벨은 새 두 작업의 필수 입력에서 제외하고 재현 과제로 보류한다.
- workload: W-burst와 W-sustain을 primary, W-low·W-peer·task/priority swap을 supporting으로 유지한다. 실제 사용자 도착 로그가 없으므로 arrival trace는 합성 조건이라고 명시하고 모델·전후처리·I/O는 A24에서 실제 실행한다.
- 작업 후보: EfficientNet-Lite0 FLOAT32와 EfficientDet-Lite0 FLOAT32를 유지한다. 공식 안내와 label 후보 구조만 확인했으며 exact artifact/license/hash·metadata/tensor 결합·A24 지원은 승인하지 않았다. 탐지의 공식 label map은 90 index row 중 10 placeholder로 80 object class를 표현하므로 dense 80행으로 가정하지 않는다.
- 차별성: Band·Sung et al.·Pantheon·CoDL 등 모바일 multi-DNN/이종 실행 연구가 이미 있으므로 최초성을 주장하지 않는다. A24 한 앱의 whole-request 비선점 배정, 서비스 제약, co-run 간섭, 강한 정적·단순 동적 기준정책 대비 재현 실증으로 범위를 좁힌다.
- 중복 조사: 공개 공식 대회 목록과 접근 가능한 프로그램에서 동일 제목은 확인하지 못했으나 최근 3개년 전체 출품작 감사가 아니므로 중복 없음은 미확정이다. 제출 전 `RELATED-02`에서 다시 확인한다.
- MODEL-02 분리: `MODEL-02A`는 host artifact/source/license/tensor/label/golden output, `MODEL-02B`는 승인 bundle의 A24 CPU/GPU·delegation·품질·메모리 smoke다. SCOPE-02 완료는 모델 승인·앱 구현·실기기 PASS나 정책 효과를 뜻하지 않는다.

## 2026-09-17 — MODEL-02A host 판정과 탐지 license gate

- 상태: 부분 대체됨 — host 판정은 유지하고, 무조건 A24 반입 보류는 2026-09-18 조건부 결정으로 대체한다.
- EfficientNet-Lite0 FLOAT32 v1은 공식 version URL, byte count/SHA-256, 내장 1000 labels, `[1,224,224,3] -> [1,1000]`, metadata의 Apache-2.0, deterministic raw CPU output을 확인해 MODEL-02B 후보로 승인한다. 이 승인은 A24/GPU/품질/성능 PASS가 아니다.
- EfficientDet-Lite0 FLOAT32 v1은 공식 source, 90행 sparse labels, raw tensor와 host CPU 실행을 확인했으나 exact binary metadata의 license가 null이다. 안내 문서 footer나 sample source license를 binary license로 대신하지 않는다.
- 사전 지정 대안 SSD MobileNetV2 FLOAT32 v1도 한 번 검사했다. 91행 background 포함 label과 tensor·raw CPU 실행은 확인했지만 license가 동일하게 비어 있어 대안 승인하지 않는다. 후보를 계속 바꾸지 않는다.
- 당시 다음 작업은 `MODEL-02A-LICENSE`였다. exact license 연결은 확보하지 못했지만 decoded golden을 완료했고, 2026-09-18 결정에서 비배포 연구 probe만 조건부 허용했다.
- 모델 binary·golden 산출물은 이번 문서 PR에 넣지 않는다. deadline과 threshold는 계속 pending이며 host latency를 A24 수치로 사용하지 않는다.

## 2026-09-18 — EfficientDet 비배포 연구 평가 조건부 승인

- 상태: 채택 — `MODEL-02A_CONDITIONAL_PASS`. 이전의 무조건 A24 반입 보류를 비배포 연구 probe에 한해 완화한다.
- 확인 사실: Google 공식 Object Detector 안내는 EfficientDet-Lite0 FLOAT32를 권장하고 모델을 내려받아 프로젝트에 저장하도록 안내한다. 공식 Apache-2.0 sample은 exact v1 GCS URL을 직접 사용한다. 동일 exact binary는 source/hash/tensor/label/raw output과 MediaPipe Tasks decoded output이 host에서 결정적으로 확인됐다.
- 미확인: exact GCS binary metadata와 bucket에는 license/NOTICE가 없으며, Apache-2.0인 TensorFlow/Kaggle EfficientDet TFLite variants는 byte·dtype·출력 계약이 달라 exact binary의 라이선스 증거가 아니다. 이 결정은 법률 자문이나 재배포 승인으로 해석하지 않는다.
- 결정: version URL, byte count, SHA-256을 고정한 A24 내부 연구 평가만 허용한다. binary를 Git 저장소·PR·APK·팀 공유 ZIP·제출물에 포함하지 않는다. A24 probe는 외부 다운로드 검증 후 app-private storage로 전달하고 실험 종료 후 cleanup·provenance를 기록한다.
- 배포 gate: 시연 APK나 재현 bundle에 모델을 넣기 전 exact license/NOTICE를 확보한다. 확보하지 못하면 명시적으로 라이선스된 artifact로 교체하고 MODEL-02A/B를 다시 통과한다.
- 다음 작업: `MODEL-02B-PREP`. 외부 manifest와 비번들 A24 CPU/GPU 최소 probe 계약을 먼저 확정한다. host latency는 deadline·simulation service time·A24 성능으로 사용하지 않는다.

## 2026-09-18 — MODEL-02B debug-only 외부 probe 구조

- 상태: 채택 — [MODEL_02B_PROBE.md](MODEL_02B_PROBE.md)의 manifest·staging·비교·cleanup·판정 계약을 구현 기준으로 사용한다.
- 코드 감사: 현재 `ModelLoader`와 calibration runtime은 APK MobileNet asset 및 고정 tensor에 묶여 있어 새 model 파일 복사만으로 재사용할 수 없다. 기존 계약을 일반화한 것처럼 바꾸지 않는다.
- 구현 경계: 새 loader·component·Tasks dependency는 debug source/dependency에 격리하고 release·formal v1·diagnostic v2·calibration-v1에 연결하지 않는다. model/sample bytes는 어느 variant에도 bundle하지 않는다.
- 실행 계층: 두 모델의 raw LiteRT CPU/GPU tensor·수치 검증과 EfficientDet Tasks decoded 검증을 분리한다. Tasks API 전체 시간은 `tasks_detect_ns`이며 내부 inference 시간으로 부르지 않는다.
- GPU 판정: delegate 생성만으로 PASS하지 않는다. full-delegation host evidence, 수치 gate, no-fallback가 모두 있어야 verified GPU cell이다.
- 범위 판정: 두 task CPU와 두 GPU가 모두 통과하면 FULL, 두 CPU와 최소 한 GPU만 통과하면 REDUCED, 그보다 좁거나 dependency/배포 gate를 충족하지 못하면 SCOPE-03로 보낸다.
- 현재 작업: `MODEL-02B-SEAM`. host tests와 dry-run을 통과하기 전 A24 설치·실행을 시작하지 않는다.

## 2026-09-18 — A24 주평가와 추가 Android 기기 무재튜닝 재현

- 상태: 채택 — 사용자의 “다른 핸드폰에도 실측해야 하는 것까지 고려” 지시를 반영한다.
- 기기 역할: A24는 개발·full profile·정책 튜닝·주평가 기기다. A24에서 모델·입력·정책·분석을 동결한 뒤 최소 한 대의 다른 Android 기기에서 같은 runner의 축소 profile과 재현평가를 수행한다. 세 번째 기기는 일정과 접근성이 허용할 때만 추가한다.
- 구현: MODEL-02B seam과 host 도구는 model name/serial별 코드 분기 없이 device manifest와 runtime capability로 동작해야 한다. 추가 기기의 GPU unsupported/unverified는 실패를 숨기지 않고 CPU/queue-only 축소 범위로 남긴다. compatibility override와 silent CPU fallback은 허용하지 않는다.
- 비교: `absolute-SLA`는 같은 millisecond deadline과 byte-identical arrival trace로 실제 사용자 경험 차이를 보고, `capacity-normalized`는 기기별 사전 solo capacity로 부하를 스케일해 정책 구조의 재현성을 본다. 원시 latency를 기기 사이에서 pooling하지 않는다.
- 무재튜닝: P/B3의 알고리즘·hyperparameter·quality/tolerance는 A24에서 고정한다. B2는 사전 정의된 기기별 profile 선택 규칙만 적용한다. 추가 기기 결과를 본 뒤 정책이나 임계값을 바꾸면 외부검증이 아니라 새 개발 버전으로 되돌린다.
- 증거 한계: A24와 추가 기기 한 대의 일치만으로 Android 전체 모집단 일반화를 주장하지 않는다. `device × policy` 차이와 미지원 cell도 결과다. 기존 S26 80슬롯은 동기 자료이며 새 두 작업 재현평가를 대체하지 않는다. S26을 쓰려면 새 계약으로 다시 실행한다.
- 라이선스: EfficientDet exact binary는 각 승인 기기 실행자가 고정 원 URL에서 직접 확보하고 hash 검증하는 비배포 연구 사용으로만 확장한다. binary를 기기 간 전달하거나 Git·PR·APK·팀 ZIP·제출물에 넣지 않는다.
- 이전 결정 관계: 2026-09-16 CALIB-01B-FIX2의 A24-only는 legacy `calibration-v1`에 그대로 적용한다. 2026-09-17 개정 4/4.1의 새 주평가 A24-only 부분은 `multitask-v1`에 한해 이 결정으로 대체한다.
- 영향: PLAN 개정 4.4, STATUS, MODEL-02 inventory/probe, SCOPE evidence, MULTITASK protocol. 현재 production 구현·실기기 PASS를 뜻하지 않는다.

## 2026-09-19 — 비정상 종료 복구와 probe APK 격리

- 상태: 채택 — 사용자가 feature/pre-simulation-ready-20260919의 미커밋 작업 보존·복구 및 최소 A24 smoke를 명시적으로 요청했다. push/PR/merge는 하지 않는다.
- 결정: 09-18 debug 전용 seam을 opt-in modelProbe variant와 별도 applicationId로 좁힌다. 일반 debug/release와 legacy production 경로를 보존한다. 전용 테스트만 testModelProbe에 둔다.
- 결과 저장 완료와 모델/기기 PASS를 분리한다. manifest schema 1과 legacy v1/v2/calibration은 유지하고, 결과 binding 강화는 artifact_contract_version=2로 명시한다. 과거 artifact는 보존하고 새 계약을 소급 적용해 수정하지 않는다.
- 미커밋 sample 교체는 bytes/source 확인만 완료했다. 새 sample에 기존 golden·정확도 판정을 전용하지 않는다. 새 decoded golden과 raw CPU/GPU 수치 gate는 미완료다.
- SIM-01 준비는 MODEL-02B 및 TASK-02/PROFILE-02의 실제 완료 경계를 충족해야 한다. probe 호출시간을 사용자 요청 service distribution으로 승격하지 않는다. deadline/threshold/repetition pending은 그대로 유지한다.

## 2026-09-20 — GPU 진행 증거·raw 수치와 실제 task 승인 분리

- 상태: 채택 — 사용자의 GPU 진단부터 SIM-01 준비까지 자율 진행 지시를 반영했다. 본 simulation·formal·push/merge는 실행하지 않았다.
- 결정: 기존 8-file probe와 공식 timer를 유지하고 UUID/manifest/monotonic 순서에 묶인 별도 durable progress와 raw f32 sidecar를 사용한다. cleanup 실패는 진단 저장 오류와 구분한다. 세부 실패를 성공으로 바꾸지 않는다.
- 증거: 첫 GPU 진단과 raw 12세션이 120초 이내 완료됐고 두 task×CPU/GPU는 seed 0/1/2의 raw 수치 gate를 통과했다. 이전 timeout의 exact phase는 미확정이다. 새 성공으로 과거 원인이 수정됐다고 선언하지 않는다.
- 제한: Tasks decoded GPU는 완료했지만 Android CPU와 고정 label/box/score gate가 실패했고 actual delegate 이름은 unknown이다. host 새 golden과 Android CPU도 한 score 기준이 실패했다. raw full GPU 증거를 Tasks wrapper에 전용하지 않는다.
- 다음 판단: 탐지 GPU를 현재의 실제 task/profile 후보에서 제외한다. 탐지 CPU와 분류 GPU 조합은 과학적으로 가능한 축소 후보이나 탐지 CPU golden/품질·adapter 검증 전에는 REDUCED_PASS로 채택하지 않는다. tolerance 완화·CPU fallback·모델 교체는 결정하지 않았다.
- 준비 범위: 별도 draft simulation schema·validator·seed·no-op·정책 인터페이스·host KPI 계약을 구현하되 TASK-02 production 완성이나 PROFILE-02 실측으로 표시하지 않는다. 실제 service/transition/co-run·품질 입력·holdout·deadline/반복은 열린 gate다.
- 근거: `C:/Users/LG/Documents/D1Check_GPU_Diag/run_20260920/device_evidence_summary.json`, `decoded_comparison.json`, [SIM_01_PREPARATION.md](SIM_01_PREPARATION.md).

## 2026-09-20 — 명시적 image task 계약과 증거 경계

- 상태: 채택 — 사용자의 decoded 원인 조사·adapter 구현·bounded 실측 승인 범위.
- 결정: 같은 원본의 RGB PNG와 Q16 resize를 입력 계약으로 고정하고 `explicit-image-task-v1`에서 LiteRT raw 출력과 metadata 기반 decoder를 직접 연결한다. 기존 모델 ID와 기존 Tasks artifact는 유지하며 새 task-profile-v1 결과를 별도 root에 저장한다.
- 근거: host/A24 CPU JPEG decode 차이를 같은 RGB ablation으로 확인했다. 같은 tensor에서는 CPU/GPU raw 및 decoded가 기존 tolerance를 통과했다. Tasks GPU는 추가 2회 timeout으로 실제 task/profile 후보에서 제외한다. [상세 근거](DECODE_RESOLUTION_20260920.md).
- 모델: exact float32 license/NOTICE는 아직 미확인이다. 기존 실행자 직접 확보·비배포 연구 probe 한정으로 유지한다. 확보한 공식 uint8 대안은 다른 모델이며 결과를 섞거나 교체 완료로 기록하지 않는다. 배포 전 라이선스 입증/교체 gate를 유지한다.
- 품질: Open Images 공식 주석 20장으로 실제 탐지 품질을 관측하되 host equivalence와 분리한다. 낮은/불확실한 품질 관측을 감추거나 gate 통과를 위해 threshold/tolerance를 바꾸지 않는다.
- 준비: B0/B1 순수 결정 함수를 추가한다. 고정 mapping·aging 값은 caller가 명시해야 하며 아직 평가용 동결값은 없다. 호출 테스트는 simulation·정책 비교가 아니다. 절대 deadline과 holdout 오차 허용값은 pending을 유지한다.

## 2026-09-20 — 색상 canonical 계약과 외부 연결 장애

- 상태: 채택(구현/host 검증), 기기 최종 검증 보류.
- 근거: 실제 10-image 실행의 한 PNG에서 iCCP에 따른 input tensor 차이가 확인됐다. host ICC→sRGB 변환 후 metadata 없는 RGB PNG를 고정한다. 모델/resize/decoder threshold/tolerance는 유지한다.
- 최종 버전: canonical-srgb-q16-stretch-v2, explicit-image-task-v2, task-profile-v3. 기존 입력과 v1/v2 결과는 보존한다. 요청 journal과 bounded Activity 가시성을 보강했다.
- 제한: 최종 APK 전송 중 A24 offline. 네 cell은 최종 계약에서 unverified이며 기존 raw 성공을 task 승인으로 전용하지 않는다. 본 simulation·formal은 미실행.
- 판정: BLOCKED_EXTERNAL_INPUT. STATUS와 외부 FINAL_REPORT에 재연결·정리 대상 UUID·최종 APK hash를 기록한다. 임의 deadline·품질 하한·holdout 오차를 채우지 않는다.

## 2026-09-20 — A24 최종 색상 계약 네 cell 검증

- 상태: 채택 — 사용자 재연결·bounded 최종 검증 지시. 최신 APK 원격 hash 확인 후 새 UUID 8 session을 실행했다.
- 결정: explicit-image-task-v2의 classification/detection CPU/GPU 네 cell을 20-image backend equivalence 범위에서 PASS_EQ로 인정한다. 기존 Tasks 실패에 따른 GPU 제외를 새 명시적 adapter에 적용하지 않는다. 품질 승인 또는 formal 안정성으로 확대하지 않는다.
- 근거: [재개 검증](A24_RESUME_20260920.md). host와 같은 tensor, decoded 및 CPU↔GPU 직접 비교 40쌍 통과. session/PID full GPU 확인. tolerance/fallback 변경 없음.
- 추가 수정: 이전 외부 분류 golden의 manifest/파일 경로 혼용을 검출했다. 실제 bytes/hash 결합 generator와 회귀 테스트를 추가하고 잘못된 golden/실패 판정을 보존했다.
- 다음: 통과 cell의 bounded solo/transition/co-run/holdout을 관측한다. deadline·품질·안정성·오차 수용값은 근거 없이 동결하지 않는다.

## 2026-09-20 — bounded profile 관측과 SIM-01 동결 보류

- 상태: 채택 — 사용자의 본 simulation/formal 제외 및 시뮬레이션 직전 준비 지시.
- 결정: 네 cell을 실제 지원하는 것으로 유지하되, 현재 두 작업 모두 solo CPU가 빠르다는 관측을 받아들인다. heterogeneous 배정 이득을 전제하거나 GPU를 유리하게 보이도록 기준을 바꾸지 않는다.
- 근거: 새31개 실기기 session, bounded solo/전환/두 co-run/별도 holdout, thermal/PSS·모든 requested/actual backend 검증. [상세 결과](A24_RESUME_20260920.md).
- 제한: 분류 CPU의 첫 non-cold 요청381ms와 warm 예측 오차74.57%를 보존한다. 추가 warmup 진단은 초기 호출 상태 영향의 근거지만 기존 holdout을 대체하는 confirmatory 결과가 아니다. cold boolean만으로 안정적인 warm service를 가정하지 않는다.
- 판정: SIM-01_INCOMPLETE. 측정값과 준비 입력을 provenance로 연결하고 no-op만 실행한다. 품질 수용·초기 호출 서비스 모델·안정성·holdout 오차·공통 제약/반복/평가 freeze 없이 READY나 절대 deadline을 만들지 않는다.
- 연결 복구 시 완료 artifact 회수는 재실행과 구분한다. host 명령 실패를 보존하고 device monotonic 실행 bound·hash·decoded·delegate를 검증한 경우에만 완료로 인정한다.

## 2026-09-20 — SERVICE-MODEL-FREEZE의 독립성·품질 보존 계약

- 상태: 채택 — 사용자의 기존233요청/31 session 분석·6후보 비교·누수 방지·no-op 지시.
- 결정: 이미 결과를 확인한4개 holdout과 사후1개 진단은 retrospective로만 유지한다. calibration24개 LOSO로 선택한 초기 상태 분리 모델은 임시 후보이며, 포함률82.52%<90% 및 untouched holdout 부재로 동결하지 않는다. 과거74.57% 오차를 제거하거나 새로운 진단으로 덮어쓰지 않는다.
- 근거: [SERVICE-MODEL-FREEZE](SERVICE_MODEL_FREEZE_20260920.md), 외부 최종 bundle의 split/acceptance/model comparison/source hash closure. 새 기준은 calibration 변동성으로 산출한 prospective engineering 기준이며 과거 holdout을 사전 승인으로 소급하지 않는다.
- 품질: numerical/decoded 동등성과 실제 task accuracy를 분리한다. 정확도를 임의 생성하지 않고 검증 cell·동일 모델/입력/전처리/decoder·기존 허용오차를 정책 공통 quality-preservation 제약으로 사용한다. 이는 모델 배포 라이선스 승인이나 실제 정확도 개선 주장이 아니다.
- 공통 경계: fallback 금지·thermal0·serial만 준비 승인, co-run/메모리 limit·deadline은 독립 검증 전 pending. GPU는 solo에서 느리지만 CPU-only 직렬 대조가 없으므로 모든 조건에서 지배당한다고 단정하거나 제외하지 않는다.
- 상태: SIM-01_INCOMPLETE 유지. 작은 추가 calibration과 새 holdout/control 설계를 명시했으며 본 simulation/formal을 실행하지 않았다. 기존 정책 ID·증거 의미는 변경하지 않는다.

## 2026-09-20 — FINAL-CALIB 사전 동결

- 상태: 채택 — 사용자 승인 A4 calibration/B16 독립 holdout/C2 CPU-only bounded 대조. 본 simulation/formal 금지 유지.
- calibration24+신규4만으로 전환을 cold와 분리한 `transition_mean`을 독립 평가 후보로 고정했다. 기존 PI Q05..Q95, coverage90%, MAE432.808616ms/WAPE43.191436% 기준을 완화하지 않았다. calibration coverage80.65% 미달도 보존한다. 후보 고정은 SIM-01 승인과 다르다.
- 2026-09-20T13:11:32.713690Z 고정 hash는 [receipt](SERVICE_MODEL_FINAL_FREEZE_20260920.json), 원자료/상세는 `C:/Users/LG/Documents/D1Check_Service_Model_Final/run_20260920T130139Z`. B16은 이 시각/commit 이후 새 UUID로 실행하고 모델을 read-only 평가한다.
- 첫 host 종료기록 변수 오류 시도는 진단 원자료로 보존하고 새 UUID로 대체했다. CPU-only 직렬 대조는 기존 단일-worker runtime 교체 비용이 포함돼 warm 두 모델 상주 대조가 아니다. sampled memory/미확정 deadline을 임의 승인하지 않는다.

## 2026-09-20 — FINAL-CALIB 독립 holdout 실패 보존

- 상태: 확정 — A4/B16/C2 실행과 동결 모델 read-only 평가 완료. Holdout coverage80.384615%<90%, 상태/분포 기준 실패로 SIM-01_INCOMPLETE다. 전체 MAE39.07ms/WAPE6.10%만으로 승인하지 않는다.
- 근거: [최종 calibration](SERVICE_MODEL_FINAL_CALIB_20260920.md), 외부 frozen contract/260개 request 예측/16개 session 평가/두 CPU 대조 및 memory·thermal 원자료.
- 모델·PI·기준을 holdout 이후 변경하지 않는다. Cold직후와 전환직후 pooling 실패는 새 버전의 calibration 설계 근거로만 사용하며 이번16개를 독립 holdout으로 재사용하지 않는다.
- CPU/GPU co-run의 긴급 응답 개선 관측은 CPU직렬 runtime 재생성과2개 warm runtime 유지의 비대칭을 포함한 n2 진단이다. GPU 자체의 우월성·전체 완료율 개선을 주장하지 않는다. Memory admission 미검증·deadline pending도 유지한다.
- Host 실패2건을 보존했다. 첫 시도는 새UUID로 대체, 다른 한 건은 이미 완료된 기기 artifact 전송만 복구했으며 Activity 재실행·실패상태 수정 없음. 본 simulation/formal·push/merge/rebase 없음.

### 2026-09-20 — SERVICE-MODEL-V2 개발 재설계와 telemetry blocker

- 상태: 채택(개발 설계); 서비스 모델 승인/실기기 실행은 아님.
- 사용자 SERVICE-MODEL-V2-DESIGN 지시에 따라 기존 calibration 및 consumed holdout 모두 개발 근거로 전환한다. 기존 실패·74.57%오차·cold774.244ms를 보존하며 새 독립 holdout으로 재사용하지 않는다.
- C setup/active 분리+E joint session empirical를 최소 구조로 선택하고, origin/cell/co-run/완료경계를 유지한다. D full sequence matrix·G pooled multiplier는 추가 복잡도/오차 근거상 선택하지 않는다. F session-conformal은90%를 유지하되 exchangeability/유한표본 한계와 분포 목적을 분리한다.
- warm3회차 자동 승인 금지. lifecycle/worker-release·MemoryInfo·두 resident CPU runtime 직렬 대조가 없어 BLOCKED_MISSING_TELEMETRY다. Android 변경/새 ADB/본 simulation/formal은 이번에 수행하지 않는다.
- [V2 설계](SERVICE_MODEL_V2_DESIGN.md)의 sample-size 계산은 계획 bound이며 수천세션 실행 승인이 아니다. 목표 precision/분포margin·공정한 paired variance가 미확정이므로 새 calibration 이후, 새 holdout 이전에 정확 프로토콜을 동결한다.
- 이전 transition_mean frozen artifact/hash/평가기 코드는 수정하지 않는다. V2 host 도구는 새 파일로 분리한다.

### 2026-09-21 — Telemetry v4와 resident control의 별도 실행경로

- 상태: 구현·host 검증 완료, **BLOCKED_DEVICE_CONNECTION**. 사용자는 새 calibration/holdout/formal/simulation을 금지하고 최소4개 lifecycle/resident smoke만 승인했다. ADB devices와mDNS 모두비어 설치/Activity/smoke는0회이며 READY_FOR_CALIBRATION을선언하지않는다.
- task-profile-v4/schema1을 modelProbe 전용 Activity/adapter로 분리해 기존 v3/공식 timer/decoder/legacy artifact를 보존한다. 캡처한 invocation timestamp를 호출 종료 후 기록하고 내부 logger 시간을 inference에 넣지 않는다.
- 두 CPU runtime을 같은 lane에 상주시켜 serial control의 runtime 재생성 혼입을 제거한다. Co-run도 같은 사전생성/warmup 원칙을 사용한다. Paired 비교는 같은 workload hash와 두 성공 receipt가 필요하다.
- 고정 headroom 대신 android-low-memory-resident-v1의 system threshold+관측 PSS reserve를 적용한다. sampled peak나 baseline guard를 실제 최대/안전보장으로 주장하지 않는다. [세부 계약](TELEMETRY_V4_GATE.md).
- v4 warm label은 ordinal이고 qualified=false다. 이번 smoke는 서비스모델 calibration/holdout으로 승격하지 않는다. 기존 consumed registry와 PI 실패를 유지한다.

### 2026-09-21 — Telemetry v4 실기기 smoke gate 통과

- 상태: 채택. 사용자의 연결 복구 후 smoke 재개 지시 범위에서만 실행했다.
- 근거: `C:/Users/LG/Documents/D1Check_Telemetry_V4/resume_20260920T160724Z/FINAL_REPORT.md`, smoke_ledger/post_validation/paired_smoke_contract. 새4세션18요청, schema/semantic validator·출력 동등성·memory admission·runtime/worker release 모두 PASS. 기존 소스/APK/원자료 불변.
- 결정: TELEMETRY_V4_READY_FOR_CALIBRATION. 서비스모델 승인이나 GPU 우월성 증거로 승격하지 않는다. Ordinal warm은 qualified=false, deadline pending, 기존 holdout consumed 유지.
- 다음: 별도 승인된 calibration 계획 동결. 이번 단계에서는 추가 calibration/holdout/simulation/formal 없음. 이전 BLOCKED_DEVICE_CONNECTION은 이번 gate에 한해 해소됐다.

### 2026-09-21 — Prediction gate에서 joint empirical 입력 검증으로 protocol amendment

- 상태: 새 방법 채택, 실행 계획은 INCOMPLETE. 사용자 EMPIRICAL-CALIBRATION-PLAN 지시를 따른다.
- PI를 scheduler가 사용하지 않으므로 새 protocol의 request PI90% 필수 gate를 제거한다. 이는 운영 성과 비교 목적과 입력 모델의 정렬이며 기존 threshold 사후 완화가 아니다. transition_mean80.38% 실패와 이전 hash/원자료는 불변이다.
- 기존52 profile 및 smoke4는 consumed development, 승인 입력은 신규 v4 자료에 한정한다. setup/active/memory/thermal/interference는 session block으로 결합하고 임의 field 재조합을 거부한다.
- [계약](EMPIRICAL_CALIBRATION_PROTOCOL.md)에 최소160/권장280 탐색세션·사전 criteria·deadline 계산 규칙을 고정했다. n8로 cold P95 정밀도를 보장하지 않으며 fair paired variance도 없다. 같은-session 전환경로가 현재 APK에 없으므로 전체 계획의 A24 실행 명령을 발행하지 않는다.
- 이번 ADB·실측·calibration·holdout·simulation/formal 없음. Android/APK 불변. 최신 외부 증거는 C:/Users/LG/Documents/D1Check_Empirical_Calibration_Plan/plan_20260921_v1/FINAL_REPORT.md.

### 2026-09-21 — 최대30세션 descriptive resident-only protocol 채택

- 상태: 계획채택, 측정미실행. 사용자 BOUNDED-EMPIRICAL-PLAN의고정수량·제한된주장을우선한다. 160/280계획은실행하지않고이전동결artifact/실패결과를보존한다.
- A24/현분류탐지/thermal0/v4의관측경험분포로정책상대비교한다. dynamic unload/reload transition과cold populationP95 precision은simulation v1필수gate에서제외한다. Setup/queue/dispatch는남긴다.
- 정확30=solo4×5+resident5pair×2. device retry0/대체0/총시작≤30; 실패시자료보존·중단·incomplete. 독립holdout없이completeness/quality/safety·sessionbootstrap/LOSO·wholeblock sensitivity/CRN을사용한다. 통계적보편우월성주장금지.
- [계약](BOUNDED_EMPIRICAL_PROTOCOL.md), 외부 `C:/Users/LG/Documents/D1Check_Bounded_Empirical_Plan/plan_20260921_v1/FINAL_REPORT.md`. 다음실행명령을제공하되이번에는ADB/측정/simulation/formal을호출하지않았다. Deadline pending·SIM-01_INCOMPLETE유지.

### 2026-09-21 — 30세션 descriptive empirical 입력 동결

- 상태: SIM-01_READY(현재사용자기준의resident-only/A24/thermal0/관측입력범위). 본simulation/formal은실행하지않음.
- 정확30/480 completed, 추가/retry/대체/실패0. Nativemanifest·순서·seed·480호출·criterion·memory/thermal·deadline공식은동결계획과동일하다. Atomic fsync/rename journal·exclusivehostlock·completed 재실행금지·완전artifact만복구하는별도관리계층을추가했다.
- Joint input SHA `4eeae6f6f8e9954d153b010767ba5a84307e5b8d0a971e7a478b0255413c0fc5`, `C:/Users/LG/Documents/D1Check_Bounded_Empirical_Run/run_20260921_atomic_v1/FINAL_REPORT.md`.
- 5pair의GPUcorun은urgentP95 개선과makespan/throughput 악화가동시에관측됐다. 5쌍bootstrap·wholeblock sensitivity로방향과불확실성만보고하고보편우월성/인과일반화는주장하지않는다.
- 기존coverage80.38%예측실패/consumedholdout/51session559요청/v4smoke/formal80원본은보존한다. 새READY는이전prediction모델의PASS전환이아니며coldP95/요청90%예측/다기기·다른thermal보장이아니다.
- 다음은동일input/CRN/복수deadline을쓰는별도승인simulation단계이며새실기기재실행은없다.

### 2026-09-22 — PC 계획의 입력 READY와 정책 READY 분리

- 상태: 채택 — 사용자의 동결 A24 입력만 사용하는 PC 계획 확정 요청. 본 simulation·추가 실기기 금지.
- 결정: 연구 질문·calibration 역할·선행연구와 비신규성을 [PC 계약](SIMULATION_PROTOCOL.md)과 [문헌 비교](RELATED_WORK_GAP.md)에 명시한다. 새 SP1 policy namespace, epsilon-constraint/lexicographic 구조, seed2026092201 및 부분 계약 hash를 사용한다. 기존 정책/telemetry/원본 의미를 바꾸지 않는다.
- 확인: 고정 offset0·분류 urgent6/탐지 normal6 co-run과 CPU 교대 serial만 측정돼 있다. 요청 순서와 overlap을 바꾸는 서비스 모형이 없는데 전체block resampling만으로 동적 정책 성능을 계산할 수 있다고 가정하지 않는다.
- 판정: SIMULATION_PLAN_INCOMPLETE. adaptive estimator·합법 action, 서비스 모형 지원, 실질효과/일반 허용 손실, workload·replication/drain, simulator version/hash는 null로 보존한다. 과거10%/2%p를 승인값으로 승격하지 않는다. 기존 SIM-01_READY는 입력 준비 판정으로 유효하다.
- 동결: 계획/schema/validator·원본 hash/consumed registry·no-op과 문서. validator PASS는 연구 READY가 아니다. 새 원자료·새 simulation 결과 생성 없이 별도 외부 root에 저장한다.
- 다음: SIM-PLAN-02-SUPPORT-DECISION에서 반사실적 모형의 가정과 기존 외삽 금지의 관계를 결정한다. 가정 미합의 시 고정 trace 기술 분석으로 연구 질문을 명시적으로 축소하는 대안을 제시하며 임의 변경하지 않는다.

### 2026-09-22 — 사용자 승인 support-constrained 모델 채택

- 상태: 채택. 최신 사용자 지시의 warm 교환가능성·허용 action·Pareto·epsilon 제한을 반영한다. 새 실측과 본 simulation은 금지한다.
- 결정: A24 thermal0/resident/non-preemptive, 같은 task/backend/state joint tuple의 제한 가정으로 CPU urgent 재배열을 허용한다. 전체 paired co-run 외의 overlap/transition은 OUT_OF_SUPPORT. 기존 empirical/v4 계약을 수정하지 않고 새 simulator namespace에서 가정과 관측을 분리한다.
- 최소 설계: 고정12요청/54budget/5pair 전수/seed2026092202. conditional MC 오차0이므로 임의 복제 수를 도입하지 않는다. 모집단 오차는 남으며 exact bootstrap3125·wholepair rank sensitivity·5LOSO deletion으로 기술한다.
- 정책·평가: FIFO/urgent/static/always-corun/adaptive, STATIC은 FIFO alias. adaptive는 시작 전 기대값의 epsilon 제약 후 miss/P95/makespan 사전식 선택, epsilon0 primary와0.5/1 sensitivity. 주 결과 Pareto, 보편승자·실질가치 threshold 없음. 상세 알고리즘과 적용 한계는 SUPPORT_SIMULATION_PROTOCOL.md에 고정한다.
- 대체: 이전 SIM-PLAN-01의 필수 null은 이 축소 계약에서 해결한다. 과거 부분 계획·hash·실패 모델은 보존한다. absolute user SLA calibration_pending은 복수 budget과 구분한다. 현재 교환가능성은 검증된 사실이 아니다.
- 다음: 검증 후 checkpoint, 별도 실행 승인 전에는 본 simulation/기기 작업0. 실행 후 선택 정책의 소규모 A24 확인은 후속 단계다.

### 2026-09-23 — 동결 시뮬레이션과 분리된 비동시 도착 확장

- 상태: 채택. 2026-09-23 사용자가 정확19세션·평가130·warmup152·총시도≤19·retry0 개발 pilot 예산을 승인했다. 실행 전 A24 연결 부재로 설치·실측0에서 중단했으며 연결 복구 시 같은 frozen plan으로 재개한다.
- 사용자 지시: A24의 검증된 분류/탐지·resident·non-preemptive를 재사용하고 완료 독립 도착, CPU FIFO/긴급 우선/조건부 CPU-GPU를 같은 workload로 비교한다. 기존 동결·원본·실패 기록을 보존한다.
- 결정: `ARRIVAL-EXT-01`/`arrival-scheduler-v1` 별도 Activity·manifest·출력 root. 네 runtime을 전 정책에 상주시켜 시작 조건을 맞추고 CPU thread1·동시2로 제한한다. 19세션/130평가요청·retry0 개발 계획과 100ms 도착 지연·120초 drain·thermal0/paired 시작온도 1°C 조건은 [확장 계약](ARRIVAL_SCHEDULING_EXTENSION_20260923.md)에 기록한다.
- 이유·근거: 기존 offset0 12요청 제한 시뮬레이션에는 staggered arrival의 실제 정책 순위/paired 효과 검증이 없다. 새 결과를 기존 동결 결과로 소급 해석하지 않는다. 네 runtime memory admission·실제 GPU delegation과 성능 이득은 아직 실기기 미검증이다.
- 미확정: UX SLA, 최소 의미 효과·일반 허용손실·독립 평가 최대 예산. 개발 결과를 본 뒤 과거 10%/2%p 참고값을 자동 승인값으로 만들지 않는다.
- 영향을 받는 범위: 새 modelProbe Activity·host 계획/실행/분석 도구와 PLAN/STATUS. formal v1/v2, task-profile-v3/v4, support-constrained freeze, 과거 APK/원본은 변경하지 않는다.

### 2026-09-23 — ARRIVAL-EXT-01 개발 pilot 완료와 독립 평가 제안

- 상태: **pilot 증거 채택 / 독립 평가 제안 미승인**.
- 실행: 고정 SHA plan/APK로 A24 19/19세션·평가130·warmup152, 총시도19/retry0. 오류·실패·거절·만료·미완료·늦은 성공0, arrival/thermal/paired온도/memory/GPU delegation/cleanup gate 통과.
- 관측: 주 3 paired block에서 `CPU_URGENT−CPU_FIFO` urgent P95 `-1217.5±15.8ms`, normal 평균응답 `+104.1±5.4ms`; `CONDITIONAL−CPU_URGENT` urgent P95 `-11.2±6.7ms`, normal 평균응답 `-630.4±27.9ms`, makespan `-1.245±0.024s`. 개발용 소표본으로 우수성을 선언하지 않는다.
- 제안: 순서 균형 주6블록+보조3블록, 27세션/198평가/216warmup/retry0, 예상65분·예약120분. 종전 참고값인 urgent P95 10% 최소효과, normal 평균응답 10% 손실 및 on-time·완료율 2%p 손실을 결과 전 동결하는 안이다. 2초/8초 deadline은 UX SLA가 아닌 설명 지표로 유지한다.
- 근거: `C:/Users/LG/Documents/D1Check_Arrival_Extension/pilot_analysis_v3/FINAL_REPORT.md`; 제안 plan SHA `9e826188a25ecc9ca33404995cc1e45238f00f539fbb3c41eabfcdb8295cf3c3`.
- 영향: 기존 formal v1/v2, support-constrained simulation freeze와 과거 원본·APK를 변경하지 않는다. 독립 평가·새 본 시뮬레이션은 별도 승인 전 실행하지 않는다.

### 2026-09-23 — ARRIVAL-EXT-01 독립 평가 완료와 동결 판정 유지

- 상태: 채택. 사용자가 정확27세션·평가198·warmup216·retry/대체/추가0 예산과 사전 gate를 승인했다.
- 실행: plan SHA `9e826188a25ecc9ca33404995cc1e45238f00f539fbb3c41eabfcdb8295cf3c3`, 고정 APK SHA `1a8448abe1c78432870f1848676de61faefa83f64c9a6a3732d79f7a121f3612`, 동일 A24 fingerprint로 27/27세션을 완료했다. 성공198, 실패·거절·만료·미완료·늦은 성공0, retry·대체·추가0이다.
- 결정: `CPU_URGENT−CPU_FIFO`는 urgent 10% 최소효과와 normal 10% 손실 기준을 통과했다. `CONDITIONAL−CPU_URGENT`는 normal 기준을 통과했지만 urgent 상대개선 `-3.48%`, 95% CI `[-5.02%,-1.95%]`로 10% 최소효과를 실패했다. 결과를 본 뒤 threshold를 완화하지 않으며 조건부 정책의 주 결합 판정은 `FAIL`로 유지한다.
- 해석: CPU 긴급 우선 대비 FIFO 차이는 우선순위 효과다. 조건부 정책의 normal 응답·makespan·throughput 개선은 주로 GPU 보조 병행 효과이며 긴급 추가 개선은 작다. deadline 2초/8초는 포화된 설명 지표이며 UX SLA 또는 2%p 비열등성 입증으로 승격하지 않는다.
- 증거: `C:/Users/LG/Documents/D1Check_Arrival_Extension/independent_evaluation_run_v1`, `C:/Users/LG/Documents/D1Check_Arrival_Extension/independent_evaluation_analysis_v2/FINAL_REPORT.md`. 독립 block n=6, 세션당 urgent2, A24 thermal0·단일 canonical 입력 범위다.
- 미완료: 새 staggered workload의 simulation 예측을 평가 전에 동결하지 않았으므로 simulation 정책 순위·paired 개선량 일치 검증은 하지 못했다. 이번 평가로 simulator를 보정한 뒤 같은 평가로 검증하지 않는다. 추가 simulation·holdout·다기기는 별도 계획과 승인 대상이다.
- 영향: 기존 formal v1/v2, support-constrained simulation freeze, pilot·과거 APK·원본을 변경하지 않는다.

### 2026-09-23 — 독립 평가 PC 재현과 확장 시뮬레이션 plan-only 경계

- 상태: 채택. 사용자 지시에 따라 추가 실측 없이 기존 원본·판정의 재현 검증, 시각화와 탐색적 simulation 적합성만 수행한다.
- 재현 결정: 세션당 urgent2건 nearest-rank P95의 평균과 모든 요청 pooled P95를 별도 추정량으로 유지한다. paired t CI 단위는 6개 workload block이며 요청 수를 독립 표본 수로 쓰지 않는다. 기존 JSON과 semantic equality, 원본694 hash를 통과했고 joint primary `FAIL`은 변하지 않았다.
- 시각화 결정: 첫 primary paired block `replicate=0`의 세 정책 전부를 대표 간트로 사용한다. metric 기반 선택을 금지하고 PNG+SVG와 그래프 CSV를 함께 보존한다.
- simulation 결정: `arrival-extension-exploratory-simulation-plan-v1`은 기존 support-constrained freeze와 별도다. 응답시간을 서비스시간으로 쓰지 않고 execution-start→worker-release 점유, completion 경계, queue wait, residual, overlap, policy cost를 분리한다. 이번에는 plan 생성과 dry-run만 허용하고 성공 기준·본 실행은 없다.
- 한계: classification/GPU arrival cell0, detection/GPU15 전부 overlap·조건부 선택 표본이다. fixed split 우월성, overlap 인과 penalty, 임의 부하·순서, 독립 simulator 검증은 현재 자료로 지지하지 않는다. 평가 공개 후 fit은 적합도 확인이다.
- 근거: [PC 후처리 계약](ARRIVAL_EXTENSION_POST_ANALYSIS_20260923.md), 외부 `independent_evaluation_post_analysis_v2`, `arrival_extension_simulation_plan_v2`.
- 영향: formal v1/v2, support-constrained simulation freeze, pilot·독립 평가 원본·기존 분석은 변경하지 않는다.

## 새 결정 작성 형식

### YYYY-MM-DD — 결정 제목

- 상태: 제안 / 채택 / 대체됨
- 사용자 지시 또는 합의 근거:
- 결정:
- 이유와 근거:
- 영향을 받는 계획·코드·실험:
- 폐기하거나 대체한 이전 결정:


## 2026-09-23 — ARRIVAL-FIXED-01 고정 분리 대조군 준비

- 확정(사용자 작업 범위): 기존27세션 주 결합 FAIL과 모든 동결 계약/결과를 보존한다. 새 같은 기간 paired 측정 후보는 CPU_URGENT/FIXED_SPLIT/CONDITIONAL, 기존 burst·low·queue와 모델/입력/앱 정책/APK를 재사용한다. 과거 conditional과 새 fixed만을 주 비교하지 않는다.
- 구현 감사: fixed는 priority 기준 urgent CPU/normal GPU, 해당 lane busy이면 대체 배정 없음. 조건부는 기존 개발 추정97/250/558/1063ms와 도착한 큐만 사용한다. 네 runtime resident 및 각2warmup은 세 정책에서 동일하다.
- PC 준비 완료: 새 plan protocol과 기존 runner 확장, 품질 gate/cleanup 중단 결함 수정, 새 고유 manifest와16 Python/7 JVM 관련 테스트·두 안 dry-run. 기존 앱 inference 경계/정책/공식 v1/v2 변경 없음.
- 제안/승인 대기: 최소27 또는 정밀54세션 중 하나, 추가/retry/대체0. 주 비교 burst C−F urgent 세션 max·normal 평균의 상대차 Bonferroni CI. 동등성/비열등성 margin 없는 추정안 권장; 새 PASS 기준이나 실측 예산 승인으로 승격하지 않는다.
- 근거·실제 명령: [별도 계약](ARRIVAL_FIXED_SPLIT_COMPARISON_20260923.md), 외부 `fixed_split_preparation_v1/FINAL_REPORT.md`. 본 simulation/추가 모델·기기·역할반전·열부하 실행은 이번 범위 밖이다.

## 2026-09-23 — ARRIVAL-FIXED-01 최소안 실행 승인 및 시작 전 gate

- 확정: 사용자가 권장 최소안을 “승인할게”로 승인했다. 27세션/162평가요청/216warmup, retry·대체·추가0, host150분+cleanup45초 상한. plan SHA `9812ce6ec8d04c43e9a072bf15d712a222304ca96e2a0033d564748decaa213f`; 정밀54세션안은 미승인이다. 승인 receipt는 외부 `minimum_approval.json`에 보존한다.
- gate: 동일 A24 serial/fingerprint, thermal0·28.8°C·충전 없음·프로세스 부재를 확인했으나 배터리39%로 동결 시작55% 기준에 미달했다. 기준을 완화하지 않고 설치·측정 시작 전 중단했다. session attempt0/27, 평가0, warmup0이며 예산 재승인은 필요 없다.
- 동일 기기의 IP/mDNS 중복 연결은 serial/fingerprint를 먼저 대조한 후 IP 연결만 해제했다. 앱/기기 설정·원본 변경 없음. 충전 후 분리·cooling 및 gate 재확인으로 같은 승인된 명령을 시작한다. 원래 실제 실행 중 실패의 retry0 규칙은 그대로 유지한다.


## 2026-09-23 — ARRIVAL-FIXED-01 기술적 중단 및 부분 결과 보존

- 사실: 동일 기기와 승인 gate 확인 후 한 번 실행해23세션 완료. 24번째 시도의 실행 전 thermal 확인에서 ADB 연결 단절, cleanup도 첫 시도 실패. 24/27시도·142/162평가요청·184/216warmup; retry/대체/추가0. 재연결 후 원본 확인·cleanup만 수행했다.
- 확정된 규칙 적용: 사용자 재연결은 retry0·첫 기술 실패 종료 규칙을 변경하지 않는다. 남은3세션을 이어 실행하거나 실패 FIXED_SPLIT을 대체하지 않는다. 별도 복구 receipt를 남기며 원래 오류를 보존한다.
- 해석: burst 완전2pair와 low2pair는 계획n3 미달로 주/해당 CI 미산출. queue3pair의 사전 보조95% CI는 탐색으로만 표시한다. C−F는 관측된 모든 완전pair에서 urgent 비용과 normal 이득이 함께 나타났다. 전체 평가 완료·전면 우월성·동등성·비열등성을 주장하지 않고 기존 FAIL 유지.
- 산출물: [결과·재현 명령](ARRIVAL_FIXED_SPLIT_RESULTS_20260923.md), 외부 analysis_v3/FINAL_REPORT.md와 recovery_v1/recovery_receipt.json. 새 raw566파일·기존758파일 보존. 추가 측정은 별도 전향적 계획/예산 판단 대상이며 이번 작업에서 실행하지 않는다.

## 2026-09-24 — ARRIVAL-TIMING-DEV-01 시간 계약 보완

- 상태: 채택(사용자 승인 설계·코드·PC 범위). 기존 CONDITIONAL의 dispatch 기준 잔여 소진·누락 snapshot 문제를 시간 경계/재현 보완으로 다룬다. 간섭 보정 P의 우수성 근거로 확대하지 않는다.
- 새 protocol `arrival-timing-dev-v1` / ID `CONDITIONAL_TIMING_DEV_1`에만 phase 추정·판단 기록을 적용한다. 기존 ArrivalPolicy/old protocol/원자료·분석·198요청 FAIL·fixed-split 부분 결과·동결 simulation은 의미와 재현 경로를 유지한다.
- 판단→dispatch, dispatch→execution, execution→output, output→persist, persist→실제 scheduler callback의 5구간을 분리한다. worker_release는 기존 event 저장 전 경계를 유지하고 lane_available을 별도로 기록한다. host inference는 API 호출 구간이며 kernel 계측으로 부르지 않는다.
- 추정 소진/필수값 미정은 UNKNOWN으로 기록하고 busy를 가용으로 전환하지 않는다. 미확정 비교는 CPU idle 진단 fallback/CPU busy 대기다. 20값 모두 null인 출처 포함 설정을 제공하며 과거 단독 수치를 새 경계에 전용하지 않는다. 실험 READY 승격·새 성공 기준·실측 예산 확정 없음.
- 모든 선택/대기 호출·phase를512개 bounded RAM snapshot으로 저장하고 종료 때 flush한다. overflow는 이후 배정 중지·trace 무효이며 강제 종료의 기록 소실은 성공으로 취급하지 않는다. 새 PC 검증은 당시 입력 재생·경계/분모/누락 검사이고 전체 GPU/품질 gate가 아니다.
- 근거·검증·한계·후속 질문: [별도 계약](ARRIVAL_TIMING_DEV_20260924.md). 구현/관련 PC 통과와 실기기 미검증을 구분한다. 폐기한 기존 결정 없음; 완료·중단 실측을 재개하지 않는다.

## 2026-09-24 — ARRIVAL-TIMING-CAL-01 단독 진단 준비

- 상태: 설계·코드·PC 준비 채택 / **16세션 실기기 예산은 제안·미승인**. 직전12개 변경은 사용자 지시대로2904165에 선택적으로 checkpoint했다.
- 채택: 기존 실행기를 재사용하는 별도 `arrival-timing-calibration-v1`/`CALIBRATION_FIXED_BACKEND_1`, 지정 backend·global concurrency1·독립0/5/10/15초 도착. 모든 추정값 null이며 일반 experiment_ready gate의 예외를 만들지 않는다. 도착 시 아직 busy인 경우와 환경/계측 실패에 새 배정을 중단한다.
- 계약: 기존20 budget/조건부 ID 의미 유지. 새 `arrival-phase-observations-v2`는 task/backend/priority8조건×5구간을 구분한다. urgent도 저장하므로 저장이 응답 예측에 N/A인 것과 lane 점유 및 실제 관측은 다르다. 미측정을0/N/A로 대체하지 않는다. 단독 고정 정책 판단 비용은 적응형 비용으로 전용하지 않는다.
- 보존: worker event가 미완료일 때도 calibration의 실제 도착/queue 사실을 immutable snapshot으로 남기되 status는 unfinished다. warmup start/end를 별도 기록한다. 기존 arrival-v1·timing-dev-v1의 실패 해석/출력은 조용히 바꾸지 않는다.
- 제안 근거: 조건당 개발1+확인1의16세션·64요청·128warmup은 최소 수집 가능성/초기 중앙값 확인용이다. 동결 뒤 확인 자료로 재적합하지 않는다. 정밀도·검정력·안정된 tail 보장 없음. 예상45~60분·host/cleanup 상한121.5분, retry/대체/추가0. 과거27세션 잔여 예산과 독립이다.
- 구현: 별도 build root에 APK를 보존하고 APK Android/Gradle 입력 및 host plan/tool hash를 분리해 결합한다. phase 소비 registry는 출력 경로를 바꾼 재실행도 막고, 중단 뒤 회수/cleanup만 허용한다. 모델/원본/APK/동결 계약 덮어쓰기·ADB·실측·simulation·push/merge 없음.
- 근거·실제 명령·판정 경계: [진단 준비 계약](ARRIVAL_TIMING_CALIBRATION_20260924.md). 기존 FAIL과 부분 결과를 대체하는 결정은 없다.

## 2026-09-24 — APK 서명 복구 및 CAL-02 후보

후속 승인/종료: 사용자가16/64/128·retry/대체/추가0·121.5분을 승인했다. 동일성/기기 gate·서명 preflight 후 설치1회 성공, 실제 package/version/APK hash·서명을 확인했다. 첫 세션(index0)의 필수 trace/ledger/warmup/environment가 없어서 동결 중단 규칙을 적용했다. 세션시도1·완료0·실패1·미시도15, 확인 phase 미소비, fit 없음. 실제 진단/warmup 호출 수는 누락 기록 때문에 미확인(해당 세션 상한4/8)으로 남기며0이나성공으로 대체하지 않는다. cleanup 완료. 이는 서명 문제 해결과 별개의 계측/초기화 실패이며 GPU hang 등 원인은 미확정이다. [CAL-02 종료 보고](ARRIVAL_TIMING_CAL02_RESULTS_20260924.md). 남은 세션 자동 재개·재시도·새 측정 없음.

- 채택: 현재 설치본/성공 보관본은 프로젝트 기존 debug 키b253…7565, 실패 APK는 전역 debug 키35ce…18f3임을 apksigner로 확인했다. 격리 출력 경로 자체가 키를 생성한 것으로 단정하지 않는다. 패키징 경로가 기존 ANDROID_USER_HOME 조건을 보장하지 않았고 설치 전 signer gate도 없었다.
- 기존 APK 정확한 바이너리를 기존 프로젝트 키로 새 경로에 재서명했다. ZIP909개 중 서명3개 외 동일, Android source/의존성/variant/manifest 불변. 키/비밀번호/개인 설정은 저장소에 추가하지 않는다. 앱 삭제·데이터 초기화·applicationId 변경·설치 재시도 없음.
- 새 CAL-02에만 parent 중단/hash 연결·새 UUID/registry·서명 preflight를 결합한다. 설치본 읽기 검사 실패는 phase/install/session0인 별도 receipt, 설치 실패는 claim 이후이므로 소비·중단이다. CAL-01 소비 상태를 소급 변경하지 않는다.
- PC10 및 실제 읽기 전용 A24 서명 비교 통과는 설치/추론 성공과 다르다. 후보16/64/128·retry/대체/추가0·개발8→동결→확인8·121.5분은 **승인 대기**이며 이번에 실행하지 않는다. [전체 근거·명령](APK_SIGNING_RECOVERY_20260924.md).

## 2026-09-24 — ARRIVAL-FAILURE-DIAG-PC-01 기록 보존 보완

- 채택: runtime 정지 원인과 기록 누락을 분리한다. CAL-02 마지막 GPU 로그/과거 crash를 원인으로 확정하지 않는다.125초 host poll 소진·finally/RAM 의존 기록 구조는 코드와 원본으로 확인했다. 진단0~4/warmup0~8 미확인 및 세션1/16 중단을 유지한다.
- 명시적 `arrival-failure-journal-v1`/performance_excluded 진단에만 session·runtime·호출 의도/반환·timeout/cancel/부분 cleanup을 append+fsync로 보존한다. 비용이 계측을 바꾸므로 calibration fit 입력을 차단한다. setup_only는 동일4runtime 생성·warmup/추론0이며 기존 정책/manifest 의미를 바꾸지 않는다. 저장 오류/128record 한도 초과 시 후속 호출 차단, native crash/강제 종료의 finally나 마지막 저장은 보장하지 않는다.
- host 실패 단계·회수 실패를 앱 실패와 분리하고 기존 phase 예산 안에서 pre-cleanup 증거5초+partial5초 후 기존 bounded cleanup을 수행한다. 기존 계획 hash/consumed를 갱신하지 않는다. PC 검증 완료는 실기기 GPU 초기화 복구 증명이 아니다.
- 제안(미승인): 새로운 setup_only 최대1시도·생성4·warmup/추론0·retry/대체/추가0·총600초. 기존30/120/125초 timeout 및 환경 gate는 유지한다. 새 실행 준비/승인이 필요하며 이번에 APK/실행 plan을 생성하거나 실측하지 않았다.16세션 보정·간섭·정책 비교로 확대하지 않는다. [근거·검증·한계](ARRIVAL_FAILURE_DIAGNOSIS_20260924.md).

## 2026-09-24 — ARRIVAL-TIMING-CAL-01 bound_v2 실행 승인

- 사용자 명시 승인 채택: 개발8→기록 검토·추정값/규칙/지원 범위 동결→확인8, 총16시도·64진단요청·128warmup, retry/대체/추가0, 실행+cleanup 합상한7290초. 별도 smoke/과거 fixed-split 잔여 실행 없음.
- 승인 대상은 plan SHA `a340a6c61e4eb4a85591ce226965495627ebd6751c3db4075b7b558a9d0553a2`, APK SHA `7bf84ce9997ed1fc0866ed89c38c84a78f37d5589a04eedef28ff65f16ae11e5`, HEAD `660532f`. 동결 plan의 역사적 proposed 상태를 고치지 않고 별도 승인 receipt에 결합했다.
- 최초 preflight의 동일 기기/연결·배터리·thermal·초기 상태 확인 후 승인된 개발 명령을 한 번 시작했다. 원자료/receipt: 외부 `timing_calibration_execution_20260924T105336` 및 `timing_calibration_development_run_v1`.
- 필수 기록 불완전·추정 근거 부족이면 확인 예산을 소모하지 않는다. 확인 자료 재적합·tail/간섭/정책 우수성 주장·일반 experiment_ready 승격은 승인에 포함하지 않는다.

- 실행 결과/동결 중단 규칙 적용: 개발 phase의 `install -r`에서 기존 설치본과 새 APK의 서명 불일치로 실패했다. session attempt0이어도 phase 소비/실패이므로 같은 실험 ID의 재실행과 확인 단계는 금지한다. 설치 시도1, Activity0, 세션0/16, 진단0/64, warmup0/128; 자동 uninstall/clear/재서명/재설치 없음. cleanup 완료·해당 앱 전체 프로세스 부재·thermal0. 상세: 외부 `timing_calibration_execution_20260924T105336/FINAL_REPORT.md`.

<a id="s26-npu-20260924"></a>

## 2026-09-24 — S26-NPU-COLLAB-01: 추가 기기와 NPU 개발 채택

**상태: 사용자 지시로 개발 방향 채택. 기기 identity·NPU 실행 장치·품질·성능은 검증 대기.** 문서화 시작은 `744cd75`, 작업 브랜치 `feature/arrival-scheduling-20260923`, clean이었다. 이번 변경은 문서/협업 정리이며 모듈 구현·기기 실행·평가 기준 수치 확정을 하지 않는다. 이전 NPU 제외/추가 기기 기능 제한은 아래 범위에서 대체하며 과거 기록은 보존한다.

### 채택 범위

- **S26을 XDEV-02 추가 검증 기기로 선정**한다. 정확한 모델명·SoC·fingerprint는 새 기기 manifest로 확인한다. 확인 전 S26 identity는 팀원 보고 정보이며 모델번호/SoC를 추정해 채우지 않는다.
- 팀원이 별도 **`npu-runner` 모듈·CompiledModel 엔진으로 NPU 확장 개발**을 진행한다. A24 작업과 병행하되 A24의 기존 `benchmark-runner` 런타임을 이 작업 때문에 교체하지 않는다. 이 로컬 체크포인트의 settings에는 npu-runner가 없고 팀원 측 최신 소스는 아직 검토하지 않았다. 채택은 현재 저장소 구현 완료 선언이 아니다.
- **S26 CPU/GPU 재현**은 검증된 두 모델과 동결 정책의 축소 재현평가이며, **NPU 확장**은 별도 엔진/모델 경로의 개발·동결·평가다. model-probe-v1 계열 실행 확인은 전자의 필요 자료일 뿐 XDEV-02 완료가 아니다. 기존 S26 80런은 보조 자료로 유지하고 새 두 모델·엔진·정책 검증을 대체하지 않는다.
- 모델별 지원·실제 실행 증거·출력 품질을 모두 통과한 NPU 경로만 배정 후보에 넣는다. 한 모델만 지원하면 해당 모델만 허용한다. 기기별 지원 경로/합법적 병행 조합을 정책 입력으로 다루는 구조는 개발 후 고정하고 새 자료로 평가한다. 현재 CONDITIONAL/시간 경계 개발 버전이3자원을 지원하거나 완전한 B3/P라고 기록하지 않는다.
- CPU/GPU/NPU 각각의 지원과3건 동시 실행 지원은 별개다. 검증되지 않은 병행 조합은 허용하지 않는다. 과거 기기의 열 상수·전환비용을 새 모델·엔진에 그대로 적용하지 않는다.

### 실행·품질 판정 원칙

| 항목 | 채택한 원칙 | 확보할 증거/미확정 사항 |
|---|---|---|
| 경로 이름 | `npu_full`/`npu_partial`은 후보 이름이며 자동 PASS가 아니다. 모델별 위임·실행 근거로 구분하며 근거 부족 시 미확정 | 원 모델 연산/partition→변환/AOT graph→컴파일 매핑, CPU 잔여 연산과 실패 시 fallback(거절/명시적 CPU 재시도/엔진 내부 대체)의 실제 의미·로그. silent fallback을 NPU 성공으로 세지 않음 |
| 식별 | engine, runtime와 compiler 버전, 원본 모델 SHA-256과 AOT 모델 SHA-256을 별도 기록 | 정밀도·변환 옵션·컴파일 target·device manifest·입출력 dtype/shape/layout·전후처리/labels/threshold. 같은 이름의 모델을 동일 artifact로 가정하지 않음 |
| DispatchDelegate | `1/1`이 변환 후 graph의 노드 집계인지 먼저 확인 | 원 모델 partition/compile mapping과 실제 실행 근거 없이 원 모델 전체 NPU 실행으로 확정하지 않음 |
| 장치와 품질 | 실행 장치 검증과 출력 품질 검증을 독립 gate로 둠 | `bit_identical_to_cpu`는 관찰값. true/false 어느 쪽도 NPU 실행 또는 품질의 PASS/FAIL 조건이 아님. 비트 비동일은 NPU 실행 증명이 아니며 비트 동일도 실패 조건이 아님 |
| FP16 등 변환 | 기존 FP32 경로와 동일 산출물 비교라고 부르지 않음 | 엔진·정밀도 변경 효과 공개, 공통 task 품질 요구를 사전에 고정. 속도 차이를 전부 배정 정책 효과로 해석하지 않음 |
| 분류 품질 | 대표 이미지와 적절한 출력/품질 기준으로 확인 | 입력 출처/hash·전처리·label 대응·출력 허용오차 및 task 품질 기준/표본을 결과 열람 전에 고정. 숫자는 이번 문서에서 임의 확정하지 않음 |
| 탐지 품질 | box/class/score와 필요한 task 품질 기준을 분리해 확인 | 좌표계·NMS/score threshold·매칭 규칙·적절한 task 품질 지표/하한을 결과 전에 고정. tensor 유사성만으로 정확도 PASS를 선언하지 않음 |

새 모델의 품질 기준은 해당 검증 결과를 보기 전에 고정한다. 이미 공개한 결과로 기준을 만들면 개발 자료 사용임을 밝히고 별도 확인 자료를 확보한다. 기존 합성 입력 결과를 대표 이미지 품질 검증으로 승격하지 않는다. 온도 관측을 에너지 절감으로 해석하지 않는다.

### 현재 근거와 보존

- **계약 모델 미검증:** EfficientNet-Lite0 / EfficientDet-Lite0의 NPU 지원·품질·성능은 확인 전까지 미검증이다. 아래 MobileNet 보고로 대체하지 않는다. 이 명시는 2026-09-24 팀 공유 동기화에서 기존 채택/검증 구분을 명확히 한 것이며 새 검증 결과가 아니다.
- **팀원 보고/미검토:** MobileNet V1 NPU 성공, 합성 입력32개 결과, manifest 수정 원인. 현재 전달 내용만 기록한다. 원본·해당 commit·변경 diff·사전 기준을 확인하지 않아 프로젝트의 독립 검증 완료로 표시하지 않는다. 특히 manifest 수정의 구체 원인·타당성을 여기서 추정하지 않는다.
- A24 두 모델 실측·198요청 독립 평가의 `conditional_joint_primary_pass=false`, fixed-split24시도/23완료 부분 종료, CAL-02 실패/미확인 소비량, 원본·동결 APK/계획·중단 registry는 그대로다. NPU 채택으로 기존 FAIL을 대체하지 않는다.
- EfficientDet exact binary의 비배포 경계는 유지한다. 원본뿐 아니라 이를 포함/파생한 AOT artifact도 배포 권한을 별도 확인하기 전 저장소·PR·APK·팀 공유 bundle에 넣지 않는다. 승인된 실행자가 고정 원 URL에서 직접 확보하는 기존 절차를 따른다.
- 이 결정은 **NPU 개발 채택**이다. NPU 품질·속도·에너지 절감·정책 이식성 검증 완료가 아니다. 새 기기 실행 예산/명령, 모델별 품질 수치, 지원 경로/병행 조합 freeze는 별도 근거가 필요하다.
- 팀 전달 최소 자료와 읽는 순서는 [팀 안내](team/README.md)에 있다. 이번 작업은 문서 diff/상대 링크/추적 파일·push 대상 점검만 하고 기존 테스트·빌드·실측을 반복하지 않는다. 작업 브랜치만 origin에 정상 push하며 master/타인 브랜치를 변경하지 않는다.

## 2026-09-24 — ARRIVAL-INIT-DIAG-01 단일 초기화 후보

- 채택/PC 준비: 사용자 요청에 따라 별도1세션·생성≤4·warmup/명시적추론0·retry/대체/추가0·전체600초의 실행 후보를 준비한다. 실행은 아직 미승인이다. 기존 CAL-02의source/입력/순서/CPU·GPU worker 소유권/대기 구조를 유지하고, 단계 기록과0호출 차단/검증만 보완했다. 생성자의 앱 추론 호출은 없으나 library prepare 내부 연산까지0이라고 주장하지 않는다.
- 단일 host monotonic T0+600 deadline에서 work cutoff545·회수10·cleanup45초를 예약한다. runtime30초/앱120초/host125초·cooling120초·환경 gate 유지. close는 같은worker에 제출하되5초까지만 기다린다. signature subprocess·host cleanup도 절대 deadline을 넘겨 새 예산을 시작하지 않는다. gate/여유 미달이면 Activity를 시작하지 않는다.
- 새로운 execution claim은 preflight 전에 소비하고 재진입을 막는다. install/session attempt는 각각 명령 직전에 별도 기록한다. runtime start 의도와 반환 증거/미확인 범위를 구분한다. preflight/설치 실패는 session0일 수 있으나 claim 이후 같은 계획 재실행은 금지한다. 기존 소비/중단 상태는 불변이다.
- 프로젝트 기존 인증서로 격리 APK를 빌드하고 PC 검증했다. 새plan/source/manifest/APK identity를 묶고 runtime_initialization 전용 root/registry를 쓴다. 동기 기록이 포함되어 성능 보정/평가에 사용하지 않는다. 결과가 완전해도 `complete_not_cause_resolved`; 불완전하면 마지막 확인 단계/회수 오류와 앱 실패를 구분하고 원인을 추측하지 않는다.
- 검증: 관련Kotlin5/Python15·compile/assemble·dry-run PASS, 실제ADB/설치/기기생성0. 새1회 실행 승인과 실제 설치본·기기/환경 gate가 남았다. 기존FAIL·부분 결과·20null/experiment_ready=false 및 S26 협업 결정은 유지한다. [후보 경로·실제 명령·한계](ARRIVAL_INITIALIZATION_DIAGNOSTIC_20260924.md).

## 2026-09-24 — ARRIVAL-WARMUP-DIAG-01 준비 범위

- 채택은 PC 준비 범위다. 네 생성 성공 뒤 아직 관측하지 않은 첫 classification_CPU warmup 전이를1회만 확인하는 새 scope를 추가한다. 원래 CAL-02 순서/worker를 유지하고 나머지7warmup/4요청은 시작하지 않는다. setup_only 단순 반복·16세션 보정 재개 대신 미관측구간을최소확장한다. 과거원인을고친다는추측성수정은하지않는다.
- 앱명시적inference 상한1은warmup1에포함되며추가호출이아니다. 입력준비/host API/출력단계와Future대기를기록하되성능보정에는쓰지않는다. 공식inference timer 내부경계는유지한다. 새실행예산은1세션/600초제안·미승인, timeout/gate는기존값유지.
- 과거RawAdapter의Git blob과원working-tree byte hash 대응미확인은별도공시한다. 새후보source/build/APK/plan mandatory검사에는예외를두지않는다. 기존FAIL·부분결과·두종료계획·20null/experiment_ready=false 불변. [비교와판독기준](ARRIVAL_WARMUP_DIAGNOSTIC_20260924.md).

## 2026-09-24 — ARRIVAL-WARMUP-REQUEST-DIAG-01 통합 준비 채택

- 첫 warmup 성공 후 두 번째 호출만 확인하는 진단을 반복하는 대신, 원 순서8warmup과 첫 정규 classification/urgent/GPU1건의 전이를 한 세션에 관측하는 PC 준비를 채택했다. 정규1건은 dispatcher·저장·lane callback 경계 확인용이며 평가가 아니다. 설치/세션1·생성4·warmup8+요청1=명시적추론9·600초·retry/대체/추가0은 **제안 예산/미승인**이다.
- 구체적 공백인 전체 warmup의 제출/내부 단계, 정규 요청의 durable 저장/callback 기록을 새scope에서 보완한다. journal 정상 예상약191개에 근거해 새scope만256, 기존scope128 유지. 기존 worker_release 의미를 물리적 lane 해제로 바꾸지 않고 event저장과 scheduler AVAILABLE을 별도 기록한다. 환경/timeout 완화나 간섭 정책은 추가하지 않는다.
- 동기 기록의 성능자료 제외,20null/experiment_ready=false,과거FAIL/부분결과/소비registry와RawAdapter 대응미확인 유지. 성공은 보정 준비로 넘어갈 조건이며 과거원인치료·8조건 보정·반복안정성의 검증이 아니다. 후속 조건은 새 보정 개발/확인 계획에서 함께 다루고 구체적 장애 없이 작은 진단을 계속 증설하지 않는다.
- PC Kotlin19/Python24·컴파일/서명/계획검사 통과와 실기기미검증을 구분한다. [근거·파일·판독·남은검증](ARRIVAL_WARMUP_REQUEST_DIAGNOSTIC_20260924.md).

### 2026-09-24 실행 결과 반영

위 제안은 이후 사용자가 같은예산으로 승인했고1회실행후중단됐다. 설치1성공/세션1실패·311.344초, CPU분류runtime1반환과GPU분류Interpreter시작만확인, 이후호출수미확인이다. 회수·host cleanup완료, 앱정상close미확인. 같은계획재시도는하지않는다. 이번결과로보정준비/과거원인해결을선언하지않고PC에서Future30/main watchdog120의무기록조건을검토한다. 상세는 [실행결과](ARRIVAL_WARMUP_REQUEST_DIAGNOSTIC_20260924.md)와외부원본을따른다. 새실측예산이나timeout완화결정은없다.


## 2026-09-24 ARRIVAL-STALL-OBS-DIAG-01: host 독립 관측 채택

- 확정: GPU worker/setup Future/main watchdog 구조는 유지한다. 원인이 확인되지 않은 앱/런타임 수정 대신 기존 통합 APK 재사용과 host125초 안5/35/105초 read-only snapshot을 추가한다. 앱/API source identity 동일성을 PC검사하고 새 host source·계획·session·registry를 고정한다. [근거·계약](ARRIVAL_STALL_OBSERVATION_DIAGNOSTIC_20260924.md).
- 증거: 통합 실패는 CPU반환/GPU interpreter 시작 이후 무기록, Future30/watchdog120도 무기록이다. journal fd.sync 지연과 OS/VM/scheduling 정지는 가능한 가설이나 현재 확정 원인은 아니다. invisible은 성공setup에도 있었으므로 단독 인과근거가 아니다. Handler uptime과host125초를 같은clock으로 취급하지 않는다.
- 범위: 사용자 승인1계획/1설치/1세션/runtime4/warmup8/정규1/추론9, 평가0/retry0,600초(545/10/45). 신규observer는 각8초·명령2초, signal/debugger/root 없음. 접근불가stack은미확인. PC검증20건은 native복구 입증이 아니다. 종료계획/기존FAIL/미확인소비량/20null/experiment_ready=false 유지.


### 2026-09-24 실행 판독 및 CAL-03 제안 분리

- 진단1회성공: runtime4/warmup8/정규1,209.390초, 앱/hostcleanup. Dozing/top-sleeping과isFrozen=false를한시점관측했으나전체실행은성공했다. 원인해결·반복안정성·성능보정을선언하지않는다. stack권한거부와native_gpu_verified=false보존.
- 확정개발변경: 새CAL-03 provenance/unique ID·registry·sync journal없음·awake/interactive read-only 시작gate·host poll125절대deadline 지원. 이는sleep환경을보정지원조건에서분리하는새수집조건이며과거gate를소급변경하지않는다. 화면조작없음.
- 제안/미승인: [CAL-03](ARRIVAL_TIMING_CAL03_PREPARATION_20260924.md)의16세션·64진단·128warmup/121.5분. 기존규칙으로개발8→동결→확인8, 관련PC15건과dry-run통과. 실행승인과측정품질PASS는아니다. 기존20null과experiment_ready=false유지.


## 2026-09-24 CAL-03 실행·동결·확인 판정

- 사용자 승인16세션/64진단/128warmup·retry/대체/추가0·합121.5분 범위를 유지했다. 결과 열람 전에 화면상태10초 host 관측, settings 전후 확인, 작업deadline의 회수10초 예약을 보완해 v3 source/계획을 고정했다. v1/v2는 미실행 보존, APK/모델/순서/통계량 변경 없음. [사전 규칙과 결과](ARRIVAL_CAL03_EXECUTION_20260924.md).
- 개발8개 모두 적격한 뒤40슬롯 median/min/max·원자료/환경 hash를 동결하고 확인8을 수집했다. 설치2·진단64·warmup128, 실패·미시도·대체·retry0, 앱/host cleanup16/16. 화면96표본/후속lane재사용48쌍 확인. 약43.43분의 이번 자료로 과거 정지 원인을 확정하지 않는다.
- 자료 적격성은 통과했으나 수치 정확도 허용폭은 원 계약에 없으며 performance_pass=null을 유지한다. 확인 자료로 재보정하지 않았다. S→O 최대 절대오차32.270ms, 탐지/GPU/긴급의 중앙값 초과4/4를 포함한 모든 오차를 보존한다. median은 상한/초과 잔여시간 분포가 아니다.
- 확정 범위: A24·고정 입력·resident4·CPUthread1·단독·관측된 awake/thermal 조건의 초기 구간 관측. 40슬롯을 기존20개 설정에 자동 복사하지 않는다. adaptive D→A·priority별 적용·UNKNOWN_OVERRUN·병행 부하 미검증을 유지하고 experiment_ready=false다. 다음은 해당 경계를 정리하는 PC 작업이며 새 정책 실측이나 추가 기기 진단 승인이 아니다.


## 2026-09-24 — ARRIVAL-CAL03-CONNECT-01: priority·공동 구간 PC 연결

- 채택/PC 검증 완료: 동결40값을 task×backend×priority로 보존하는 새 설정과 PC 개발 정책을 사용한다. 기존20필드/정책ID/Android 경로에 대입하지 않는다. 개발자료에서 각 요청의 A→응답/A·S·O·P→L 차를 먼저 계산한 중앙값을 파생 설정에 두며, phase 중앙값의 합을 전체 구간 중앙값이라고 해석하지 않는다. 확인 자료는 변환/튜닝에 사용하지 않는다.
- 고정 경로 D→A는 적응형 비용이 아니므로 missing/null 유지. 엄격 모드는 CPU fallback/단독busy 대기, 공통 비용을 명시한 PC 가정 모드에서만 후보 최소 응답 선택. 이는 보수적 개발 제한이며 성능 보장·새 P 기여가 아니다. UNKNOWN_OVERRUN 유지·실제L callback 전busy, W에서 P→L 시계 재시작 금지.
- 새 이벤트 엔진은 기존 동결 simulator/옛 탐색 계획과 분리한다. CPU/GPU overlap은 미지원으로 차단하고, 다른 도착/순서에 단독 벡터를 쓰는 전이는 미검증 가정으로 표시한다. policy 예상과 engine 실현을 분리하며 예정도착·전체분모·미완료를 보존한다. PC21시험/8요청 엔진 점검은 기기 검증·독립 예측 검증이 아니다.
- experiment_ready=false: adaptive 비용/부하 의존 지연/병행 간섭/정확도 기준/새 앱 연결·독립평가가 미충족이다. 기존10% 판정·FAIL/부분결과·CAL-03 performance_pass=null·동결값·종료계획 불변. 상한/허용폭/실측 예산을 새로 확정하지 않는다. [범위·구현·검증·다음 조건](ARRIVAL_CAL03_CONNECTION_20260924.md).

## 2026-09-24 — ARRIVAL-COLLECT-01: 통합 개발 수집 경로 준비

- 채택/PC 구현: 기존 정책을 바꾸지 않고 새 collection namespace에서 PC 엄격 정책의 실제 배정과 고정 배정+shadow를 분리한다. strict는 현재 CPU fallback·전체직렬이고, fixed는 urgentCPU/normalGPU이며 global1과per-lane2를 구분한다. snapshot/후보/초과잔여/선택없음·계산/메모리기록/dispatch 시간 경계를 보존한다. 동기 journal 없이 버퍼를 종료 시 저장하며 유실을0호출로 바꾸지 않는다.
- 근거: 공통 판단비용은 backend 순위에서 상쇄된다. 이번 목적은 완전한P 개발이 아니라 실제 목표 경로의 절대시간과큐/병행 지원 범위를 식별할 최소 자료다. 한정 병행은 탐지normalGPU+분류urgentCPU만, 단계별앞5조건검증/cleanup 뒤 허용한다. F를마지막에두는 안전조건의순서교란, overlap과큐전이혼재, 조건당독립세션1개의한계를명시한다.
- 제안/실측 미승인: 개발6→회수hash재검사/조건별기술통계동결→확인6,12세션/48진단/96warmup/설치2·retry/대체/추가0·상한91.5분. 새로운 실측 승인 전에는 실행하지 않는다. 단계claim/preflight/설치/세션/Activity소비를 분리하고 어떤실패든전체계획종료·재개금지. 확인자료재보정·CI/tail/정확도/우월성PASS없음.
- 검증: Kotlin28/기존timing Python9·최종collection Python13/실제Kotlin-PC snapshot12, APK빌드/PC서명/dry-run통과. 실기기병행·환경·성능 미검증. host동결검사보완으로planv2, 기존v1/APK보존. [상세 계약·실제 명령](ARRIVAL_INTEGRATED_COLLECTION_20260924.md).
- 유지: 기존40값/20null/FAIL/부분결과/종료계획·experiment_ready=false. 강한B2/B3/P·기존시스템 비교와 축소 기준은불변. 이수집성공만으로최종비교완료/새성공기준을부여하지않는다.

### 2026-09-24 ARRIVAL-COLLECT-01 승인 실행 중단 판정

- 승인12세션/48진단/96warmup·2설치·retry/대체/추가0·91.5분 범위에서planv2를변경없이1회호출했다. 설치전identity/서명/환경gate통과 뒤 install-r가120초timeout. 설치1·세션0·명시적추론0, 미시도12다. 원래중단규칙대로전체종료, 미소비세션을재개/대체하지않는다.
- hostcleanup/프로세스부재확인, 이후비파괴조회에서이전설치APK해시유지. 서명불일치가아니며전송/패키지처리원인은미확정. 앱실행전실패이므로GPU/CAL-02원인에새결론을부여하지않는다. 화면설정변경없음.
- 새적격자료가없어동결/확인/PC연결은수행하지않는다. 기존설정과experiment_ready=false유지. 다음은설치timeout부분출력·단계시간보존을갖춘새진단의PC준비이며지금추가기기작업을승인하거나실행하지않는다. [원본·소비량·판독](ARRIVAL_INTEGRATED_COLLECTION_20260924.md).

## 2026-09-24 — 설치 복구와 COLLECT-02 분리 준비

- 채택/PC구현: 새 복구 전용 host 기록으로 명령 시작/종료·부분 stdout/stderr·timeout·client tree 종료·설치 후 조회 실패를 남긴다. 기존install-r 스트리밍 추정 대신 명시적 push/hash→pm install-r로 분리한다. 방식·추가 staging 비용이 달라지며 이전 방법과 동일 실험이라고 하지 않는다. 설치timeout120초 유지, 기존증거의전송/패키지처리원인은미확정.
- 복구와 수집의 namespace/소비/출력을 분리한다. exact APK/package/version/signer 확인 시 재설치생략 가능, 아니면 복구단계만 설치최대1. 성공receipt·증거hash·cleanup 확인 후 새 수집, 각 단계 설치본 재검사, 수집내설치0. 기존중단계획·미시도분재사용금지.
- 미승인예산: 복구600초+기존설계수집5490초=6090초, 개발6→동결→확인6/48진단/96warmup/명시적144, retry·대체·추가0. 한 번의 향후 승인으로 gate 충족 시 자동 진행하는 스크립트 준비. 이번에는 기기 작업0.
- PC28건·서명/해시/manifest/dry-run 확인. Android/APK변경없어재빌드없음. 기존40값/20null/FAIL/부분결과/experiment_ready=false 보존. [상세 근거·예산·명령](ARRIVAL_INSTALL_RECOVERY_20260924.md).

### 2026-09-24 승인 실행의 배터리 gate 중단

- bceec84에서동결된복구/수집계획을승인실행했다. 서명/기기조회후배터리50%가시작55%를충족하지못해원래규칙대로종료. 후보push/install0, 수집phase/세션/명시적추론0, retry/대체/추가0. 단순로그부재가아니라기록된명령과설치전제어흐름을근거로0을판정한다.
- hostcleanup/프로세스부재·기존설치본유지확인. 복구91.156초/workflow92.297초, 새비용표본없음. 현복구/workflow소비기록보존·재개금지, PC연결/병행허용확대없음. 다음은충전/비충전조건준비후새식별자의계획준비이며추가기기실행을자동승인하지않는다. [원본·소비량](ARRIVAL_INSTALL_RECOVERY_20260924.md).
