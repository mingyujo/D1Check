# S26 request-runner APK ↔ source commit 연결표 (2026-10-12 · Cowork · GitHub 원격 기준)

> 조민규 10/12 요청 "문서 한 가지" 답. 근거: GitHub `mingyujo/D1Check` `s26-mixreq` `21cba44` · `s26-statesplit` `9c857f1` (git diff --numstat) + 세션 기록의 `apk_sha256` (progress.jsonl 첫 줄) + 작업결과 문서. 표기 [P] git · 세션 기록 · [D] 작업결과 문서.
> **빌드 재현은 아직 확인 안 함** — 각 커밋을 다시 빌드한 해시 비교는 PC 에서 (`프롬프트_M6A_개발측정_1012.md` 1단계). 그 전까지 대응은 "작업 기록 · 세션 기록상" 이다.

## 1. 해시 ↔ 커밋

| APK (request-runner) | 쓰인 자료 | 세션 기록 `apk_sha256` [P] | 빌드 커밋 [D] | 브랜치 · 시각 | 근거 문서 | 빌드 재현 [P 1012 PC] |
|---|---|---|---|---|---|---|
| `fb240791…` (v1) | R1 · R2 스모크 | — | `0ad7fac` | `s26-mixreq` 10-08 04:39 | `작업결과_1008_R1_혼합요청개발.md` | — (R1 · R2 스모크 · 대상 밖) |
| **`591cae72886aebe6a051d7b0fe311aa38b8127e21ba0b519851b7784229d986d`** (v2) | **R3** 16 | 16/16 | **`e2bedf1`** | `s26-mixreq` 10-09 04:40 | `작업결과_1009_R3_혼합요청v2.md` | **빌드 재현 확인** (`e2bedf1` 깨끗한 빌드 → `591cae72…` 바이트 같음 · dex 같음) |
| **`b97a97842471b0727dc36f4d3c7230108397c0e43cd7406e654c5f038c8b89b7`** (v3) | **R4C · R4S** | R4C 16/16 | **`c75d085`** | `s26-mixreq` 10-09 20:51 | `작업결과_1010_R4_혼합요청v3.md` §4 | **빌드 재현 확인** (`c75d085` → `b97a9784…` 같음 · dex 같음) |
| **`c2e78939b2b9a37427b2862734c185093ba6f84e454d191ac6603a67a6b8a39d`** (M5) | **SS · ABBA** | SS 12/12 | **`8bd3d76`** | `s26-statesplit` 10-12 02:28 | `작업결과_1012_M5_상태분리측정.md` | **빌드 재현 확인** (`8bd3d76` → `c2e78939…` 같음 · dex 같음) |
| **`6a4da1acc213b4a8c13fdbbd42bbbae3cdb5bb1b71557ff7995212c3e4bc1f3f`** (M6) | M6 E · K · P | (측정 뒤 기록) | **`4f87d15`** (커밋 ②) | `s26-m6` 10-13 00:25 | M6 등록 v3 §1 · `freeze_m6.txt` | 깨끗한 빌드 = `6a4da1ac…` (14,545,892 B · 서명 `6394e51f…` = 기존과 같음) |

- 세 묶음 모두 세션 기록 `litert_version` 2.2.0 · `sdk_int` 37 · `device_model` SM-S942N [P].
- `9c857f1` (M5 결과 나머지 파일) 은 앱 코드 변경 0 [P].
- **빌드 재현 (2026-10-12 23:4x · M6-A 1단계 · PC)** [P]: 세 커밋을 각각 `git worktree` 에서 `request-runner/build` 를 지운 뒤 `./gradlew :request-runner:assembleDebug` → 파일 SHA-256 이 세션 기록 `apk_sha256` 과 바이트 같음 **3/3** (`build_repro/compare_*.json`). 조건: 같은 PC · 같은 debug keystore · 레포 밖 입력 2개 = `local.properties` (sdk.dir) 와 `request-runner/src/main/jniLibs/arm64-v8a/libLiteRtDispatch_Samsung.so` (gitignore 라이선스물 · SHA-256 `f08656a6…` = 세 APK 안의 그 항목). 이 .so 없이 빌드하면 그 항목만 빠지고 (dex 같음), 증분 빌드는 zip 항목 순서만 달라진다 (내용 같음) — 깨끗한 빌드에서는 둘 다 없음.

## 2. 영역별 변경 (request-runner `src/main` + 빌드 설정) [P git diff --numstat]

영역 규칙 (파일 → 영역): 계약/검증 = `MixreqContract` · `SessionManifest` · `RequestPlan` · `StatesplitPlan` · `Uuid5` / 진단 진입점 (별도) = `InputListActivity` · `InputListEngine` · `AndroidManifest.xml` 의 activity / worker·큐·세션 엔진 = `SessionEngine` · `SessionActivity` / 정책 = `PolicyStudy` / runtime·엔진 = `Runtimes` / 전처리 = `ImageContract` / 디코드 = `Decoders` / logger = `EventLog` · `Json` / power sampler = `BatterySampler` / 빌드 = gradle 파일.

| 구간 | 계약/검증 | 진단 진입점 | 전처리 | 디코드 | logger | worker·큐·엔진 | 정책 | runtime | sampler | 빌드 |
|---|---|---|---|---|---|---|---|---|---|---|
| `0ad7fac` → `e2bedf1` (v1 → R3) | `MixreqContract` +4/−3 (STEP 400 → 200 · 실험 ID −01 → −02) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `e2bedf1` → `c75d085` (R3 → R4) | `MixreqContract` +23/−3 (실험 ID 표 · 표 행의 공통창 · watchdog) · `SessionManifest` +7/−4 (표 행으로 검증) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `c75d085` → `8bd3d76` (R4 → SS) | `MixreqContract` +16/−1 (M5 실험 2개) · `RequestPlan` +1/−1 · `SessionManifest` +2/−1 · `StatesplitPlan` +51 (새 · 요청표 유도/검증) | `InputListActivity` +104 · `InputListEngine` +274 · `AndroidManifest` +5 (Q1 입력 목록 · 세션 경로와 따로) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | `settings.gradle.kts` +4 (`:quality-runner` 모듈 포함만) |
| `9c857f1` → `4f87d15` (SS → M6) | `MixreqContract` +29/−2 (M6 표 P · K · 블록 M) · `RequestPlan` +3/−1 · `SessionManifest` +4/−1 · `M6Plan` +95 (새 · 요청표 유도/검증) | `GaugeDiagActivity` +453 (새 · E 게이지 진단) · `AndroidManifest` +5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

- **전처리 · 디코드 · logger · worker/큐 · 정책 · runtime · power sampler 는 세 구간 모두 변경 0.** `request-runner/build.gradle.kts` · `gradle/` 변경 0 (LiteRT 버전 같음).
- 계약 상수 중 공통창 길이 · watchdog 은 엔진이 읽는 값이다 (R3 120 s · R4C 120 s · R4S 720 s · SS 120 s) — 코드 경로는 같고 값만 실험 표에서 온다.
- 블록 구성 (세 APK 같음): A = 상주 4 (`classification_CPU/GPU` · `detection_CPU/GPU`) · 정책 {CPU_URGENT, B2_PARALLEL} / N = 상주 5 (+ `classification_NPU`) · 정책 {CPU_URGENT, S26_NPU_PARALLEL}. 그래서 같은 APK 안에서도 상주 집합이 블록마다 다르다 — G 는 늘 4, N 은 늘 5, C 는 R3 · R4C 에서 블록 A 4 / 블록 N 5, SS 에서 전부 4 [P 세션 `summary.runtime_keys`]. M6 는 세 규칙 모두 5 (블록 `M`).
- **M6 행 (2026-10-13 · M6-A 3단계)** [P git diff --numstat `9c857f1` `4f87d15`]: 전처리 · 디코드 · logger · worker/큐 · 정책 · runtime · sampler · 빌드 = 0 (영역 규칙 `area_rules.json` · `M6Plan` = 계약/검증 · `GaugeDiagActivity` = 진단 진입점, 등록 v3 §1-1). M6 는 세 규칙 모두 블록 M (상주 5).


## 3. M7 행 (2026-10-13 21:3x · M7-A · 영훈 · Cowork 결정 20:5x "M7-apk 로 전환") [P]

| APK (request-runner) | 쓰인 자료 | 세션 기록 `apk_sha256` [P] | 빌드 커밋 | 브랜치 · 시각 | 근거 문서 | 빌드 재현 |
|---|---|---|---|---|---|---|
| **`878b10b7bc05300ddddc60fac0b2fb40eb020870841e473a8775827ef92bf092`** (M7) | M7 K 15 · 준비 P 10 · P 30 · S 12 (+ S7 회귀 · M6 재현 스모크) | (측정 뒤 기록) | **`7ad2b18f27d97b5f40d84343fe9cecd616128bf5`** | `s26-m6` 10-13 21:30:53 | 등록 M7 v2 (`c3da26cc…`) 머리 단락 · `sim\out_m7\freeze_m7.txt` | 깨끗한 빌드 2회 (21:12 작업 트리 · 21:4x 커밋 뒤) 모두 `878b10b7…` (14,547,256 B · 서명 `6394e51f…` = M6 와 같음) |

- **영역별 변경 `4f87d15` (M6 APK) → `7ad2b18` (M7 APK)** [P git diff --numstat `request-runner/src/main` + 빌드 설정]: 계약/검증 = `MixreqContract` +7/−3 (실험 표 index 상한만: `S26-M6-P` 11 → 51 · `S26-M6-K` 3 → 18 · `S26-MIXREQ-03` 15 → 27 · 주석) · `M6Plan` +25/−2 (index → 부하·규칙 순서표에 M7 행: 12 ~ 41 = 등록 §2-3 · 42 ~ 51 = 준비 L-C/L-N · `S_ORDER` 표 · 상수) / 진단 진입점 · 전처리 · 디코드 · logger · worker·큐·엔진 · 정책 · runtime · sampler · 빌드 = **0**. 요청 유도식 (L · B) · uuid5 · 블록 M · 단계 상수 · watchdog 무변경 → L 투영 SHA `ad29e819…` · B `9fc5ef9f…` 그대로 (plan_m7p · plan_m7prep 자동 검사 PASS).
- APK 항목 비교 (`m6_apk_compare.py` M6 `6a4da1ac…` ↔ M7): 다른 항목 = `classes3.dex` 1개 · META-INF 차이 0 · 나머지 항목 (리소스 · `libLiteRtDispatch_Samsung.so` · classes.dex · classes2.dex) 같음 (`results\m7_build\compare_m6_m7.json`, 커밋 안 함).
- 시험: request-runner 단위 61 중 60 통과 (새 `M6PlanTest.m7RowsMatchRegistrationV2` · `ExperimentTableTest` 상한 15/15/27 포함) · 남은 실패 1 = `SessionRoundTripTest.sustainedExperiment03…` (M6-A 원장과 같은 기존 실패 · 기준 `9c857f1` 에서도 실패 · 이 PC time_scale 10 타이밍) · `StatesplitRoundTripTest` 3개는 1차 (빌드와 다른 작업이 겹칠 때) 실패 → 유휴 재실행 3/3 통과. 호스트 pytest 86/86 (`test_m7` 11 포함).
- index 자리: M6 (P 0 ~ 11 · K 0 ~ 3) · R4 (S 0 ~ 15) 가 쓴 session_id 는 그대로 두고 **뒤에 잇는다** (앱이 session_id = uuid5(실험 ID/index) 를 강제 · 기기에 a1 폴더 있음). 같은 APK 전제는 M7 안에서만 — M6 12세션은 `6a4da1ac…` (`cycle = m6` 병기).
