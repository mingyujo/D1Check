# D1Check 결정 기록

이 문서는 방향 변경을 날짜순으로 기록한다. 각 항목에 제안 / 채택 / 대체됨 상태를 표시한다. 아래 초기 항목은 이전 계획에서 이관한 작업 방향이며, 개별 수치·실험 조건 확정을 의미하지 않는다. 이번 개정은 사용자 요청에 따른 문서 보강이다.

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

## 새 결정 작성 형식

### YYYY-MM-DD — 결정 제목

- 상태: 제안 / 채택 / 대체됨
- 사용자 지시 또는 합의 근거:
- 결정:
- 이유와 근거:
- 영향을 받는 계획·코드·실험:
- 폐기하거나 대체한 이전 결정:
