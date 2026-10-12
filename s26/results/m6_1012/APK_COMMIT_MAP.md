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
| (M6 — 이번) | M6 E · K · P | — | M6 커밋 ② | `s26-m6` | M6 등록 v2 §1 | (M6 행 = §3 · 커밋 ② 뒤) |

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

- **전처리 · 디코드 · logger · worker/큐 · 정책 · runtime · power sampler 는 세 구간 모두 변경 0.** `request-runner/build.gradle.kts` · `gradle/` 변경 0 (LiteRT 버전 같음).
- 계약 상수 중 공통창 길이 · watchdog 은 엔진이 읽는 값이다 (R3 120 s · R4C 120 s · R4S 720 s · SS 120 s) — 코드 경로는 같고 값만 실험 표에서 온다.
- 블록 구성 (세 APK 같음): A = 상주 4 (`classification_CPU/GPU` · `detection_CPU/GPU`) · 정책 {CPU_URGENT, B2_PARALLEL} / N = 상주 5 (+ `classification_NPU`) · 정책 {CPU_URGENT, S26_NPU_PARALLEL}. 그래서 같은 APK 안에서도 상주 집합이 블록마다 다르다 — G 는 늘 4, N 은 늘 5, C 는 R3 · R4C 에서 블록 A 4 / 블록 N 5, SS 에서 전부 4 [P 세션 `summary.runtime_keys`]. M6 는 세 규칙 모두 5 (블록 `M`).
