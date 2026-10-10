# R4 혼합 요청 v3 — 원장 (레포 사본, `D1_ondevice\sim\out_mixreq\freeze_mixreq.txt` 끝의 R4 절과 같은 내용)

> 작업 클론 `C:\Users\rhoyo\AndroidStudioProjects\D1Check_mixreq` · 브랜치 `s26-mixreq` · 시작 HEAD `344dd9f` = `origin/s26-mixreq` (R3 끝).
> 표기 [P] 실측 · [D] 인용 · [E] 추정 · `미확인`. 주소 · 시리얼은 `<IP:PORT>` · `<SERIAL>`. KPI 는 readout 전에 이 파일에 쓰지 않는다.
> 우선순위: 프롬프트 R4 > 등록 v3 (`45f151d3…`) > v2 (`8e8e1104…`) > v1 (`edf9e594…`) > R3 보고서 §10 > CLAUDE.md.

## 영훈 결정 — 결과 전 고정

1. **10/9 20:10**: "1, 2번 둘 다 진행 — 우리 측정을 (조민규와) 동일한 수준으로 맞춘다" → (C) v2 확인 블록 (`S26-MIXREQ-02C`, 역순 N → A) + (S) 지속 600 s (`S26-MIXREQ-03`, 3,000 요청 · 720 s 창).
2. **무조건 완주** (10/9 04:14 · 20:10): R3 프롬프트 표 그대로. 측정 전체를 그만두는 결정은 영훈만. 안전 비상은 그 세션만.
3. **10/9 19:4x**: "핸드폰은 세션 끝나도 화면 끄기 방지는 유지해" → 4부 원복에서 `screen_off_timeout` 은 86400000 유지 (프롬프트 "끝에 원래 값" 보다 영훈 직접 지시 우선 — 기록).
4. 결과 지위 = S26 부록 관측 (등록 v3 머리) · (S) 는 결과 뒤 설계 (등록 v3 머리 · 반대 해석 19).

## 0단계 (20:30 ~ 20:34) [P] — 상세 `results\S26_MIXREQ_R4\r4_preflight.txt` (git 밖)

- 폰 첫 명령: `screen_off_timeout` 은 이미 86400000 (Q20 2부 19:47 에 넣음 · 그 전 원래 값 600000 = R3 원복값) · 잠금 없음 · Awake. git HEAD `344dd9f` = origin · clean · R3 · Q20 프로세스 0 (Q20 감시의 고아 tail.exe 1개 — 정적 파일, adb 무관, 종료는 도구 정책이 거부).
- 등록 v3 SHA `45f151d3cac03236fd8f9d6f529efefbac43b54ba1c57933082957fe6f43d46b` ✔ · v1 `edf9e594…` ✔ · v2 `8e8e1104…` ✔ · git 밖 입력 7/7 ✔ · a24_handoff `d93e0978…` ✔ · v2 APK `591cae72…` ✔ · 디스크 free 15.6 GB · 폰 SOC 73 · plugged 0 · 밝기 127 · 비행기 1 · zen 1 · HAL SKIN 27.7 · AP 25.7 · BAT 25.3.

## 1-1 등록 v3 커밋 ① (20:33:31) [P]

- `d1sim/docs/혼합요청_사전등록_v3.md` ← OneDrive 바이트 그대로 (SHA `45f151d3…` · `git show HEAD:` 도 같음 · 57 줄).
- **커밋 ① `70c50f73c2e9d600a86deaa8a93f1b4dd02225a1`** (2026-10-09 20:33:31 +0900) "d1sim: 혼합 요청 사전 등록 v3 — (C) 확인 블록 · (S) 지속 600 s (v3 칸 전)" · 추가 줄 PAT 0 · 바이너리 0.

## 1-2 코드 v3 — R4 가 결과 전에 정함 (등록 v3 §0 · (C) · (S) 만) [P]

1. **앱 변경 범위** = `MixreqContract.kt` (실험 ID 표 `EXPERIMENTS`: -02 · -02C · -03 + 각 -SMOKE → 요청 수 192/192/3,000 · 공통창 120/120/720 s · index 0~15 · watchdog 600/600/1,260 s · `COMMON_NS` 는 `SessionManifest.validate()` 가 고른 표 행 · `WATCHDOG_MS` 는 표 최댓값 1,260 s — Activity 가 manifest 를 읽기 전에 거는 값이라 실험별로 못 건다; 세션별 상한은 호스트 (`session_cap_s`) · `validateRequests` 허용 수 = 표 ∪ {24}) + `SessionManifest.kt` (`experimentOf` fail-closed · 요청 수 · 공통창 · index 범위 = 표 행). `git diff e2bedf1 -- request-runner/src/main/java` = 2 파일 +30/−7 (아래 전문). 요청 처리 · 정책 · 전처리 · 디코드 · runtime · 표본기 · 경계 코드 변경 0 (SessionEngine · SessionActivity · Runtimes · Decoders · ImageContract · BatterySampler · EventLog · Json · PolicyStudy · RequestPlan · Uuid5 diff 0).
2. **(C) 순서** `SESSION_ORDER_C` = 블록 안 v2 거울 순서의 역순 (A: PAR · CPU · CPU · PAR · CPU · PAR · PAR · CPU / N: PAR-NPU · CPU · CPU · PAR-NPU · CPU · PAR-NPU · PAR-NPU · CPU) · index 번호는 그대로 (A 0~7 · N 8~15) · **실행 순서 = 드라이버 `-Block N` 먼저 → `-Block A`** (8 → 15 → 0 → 7). (S) 는 v2 순서 그대로 (`SESSION_ORDER`), 실행 N → 충전 → A.
3. **(C)-4 확인 판정** (`mixreq_readout.confirmation`): 블록 A → Q1 · 블록 N → Q3, `judgment` (꼬리표 포함한 readout 이름) 이 R3 `R3_readout/readout.json` 의 것과 같으면 "확인됨 (개발 · 확인 2블록 같은 판정)", 다르면 "확인 안 됨 — 개발 · 확인 판정 다름". `urgent · normal · thermal_skin · thermal_ap · service` 판정도 같은 방식으로 나란히 (Q 판정은 `judgment` 만 따른다). 두 블록 합산 없음. 판정기 · 허용치 = R3 `e2bedf1` 의 것 (재보정 없음 · 코드 변경은 실험 ID 분기뿐).
4. **(S)-6 정의** (`mixreq_readout`): ① SKIN ≥ 38.0 ℃ 시간 = 호스트 HAL 2 s 표본 (hal.csv, 공통창 안) 에서 표본 i 의 SKIN ≥ 38.0 이고 다음 표본까지 간격 ≤ 2.5 s 일 때 그 간격을 합산 (결측 · 지연 표본은 보간하지 않음) ② 처리 속도 저하 = lane 키 (task_backend) 별 서비스 시간 (execution_start → output_ready, ms) 의 **마지막 60 s 도착 (예정 offset ≥ 634.8 − 60 = 574.8 s) 중앙 ÷ 처음 60 s 도착 (offset < 35 + 60 = 95 s) 중앙** · 기술만 ③ 창 끝 SKIN · 시작 SKIN. (S)-7 판정: 최고 SKIN 1.0 ℃ 규칙 (주, v1 `thermal_direction`) · 38 ℃ 시간 60 s 규칙 (`time38_direction`: 전부 |Δ| < 60 → "기준 안 (60 s)" · 전부 ≥ +60 → "병행이 더 오래 38 ℃ 이상" · 전부 ≤ −60 → "덜 오래" · 그 밖 "엇갈림") · 긴급 응답 v1 §6 · n < 3 → "쌍 부족 — 기술만" 이 먼저. 꼬리표 우선순위 R3 와 같음.
5. **호스트 상수**: `session_cap_s` -03 = 180 + 60 + 30 + 720 + 30 + 60 + 240 = **1,320 s** (v2 · -02C 는 1,200 그대로) · 진행 폴링 `ls -l` **3 s** (-03) / 1 s · 유효성 규칙 3 창 = 실험 표의 공통창 (-03 720 s · 그 밖 120 s) · 규칙 5 는 v2 분기 (등록 버전 ≥ 2) · readout 은 plan 의 실험 ID 와 다른 세션을 건너뛴다 (섞지 않음, 기록) · v2 readout 출력은 바이트 동일 (회귀 아래).
6. **도구 보수 (R3 §11-4)**: `top -H` 파서 (Android 행 = TID USER PR NI … THREAD PROCESS; R2 정규식은 "PID TID" 를 기대해 0행) → 패키지 행 수 · `d1mix-*` 스레드 수 기록 · 0단계 화면 꺼짐 순서는 이 프롬프트 0단계 1 로 (이미 86400000) · 스모크 sid 는 실험 ID 네임스페이스라 다름.
7. **스모크 (S)**: 등록 v3 §0-2 "스모크 공통창 = 같은 실험의 값" → -03-SMOKE 는 24 요청 · 720 s 창 (S1 은 warmup_only 라 짧음 · S2 3개는 각 ≈ 17 분).

## 1-3 시험 (20:4x ~ 20:5x) [P]

| 시험 | 결과 |
|---|---|
| `gradlew :request-runner:testDebugUnitTest --offline --rerun-tasks` | **37 / 37** (32 + ExperimentTableTest 3 + K6 `confirmationExperiment02CRunsLikeV2` · `sustainedExperiment03…` (3,000 요청 · 창 72 s · 결과 파일 3,000) + manifest fail-closed 추가 조합 8) · round-trip `blockA_par_02C` · `blockN_parnpu_03` 생성 |
| `py -3 -m pytest s26/tools/mixreq` | **42 passed** (34 + v3 8: 표 · 3,000 요청표 · 규칙 3 창 720/120 · 38 ℃ 시간 · 저하 비 · 확인 판정 · sustained judge_block · plan_v3 + 드라이버 `-Experiment 02C -DryRun`) — 기존 `test_request_table…` 의 "모르는 ID" 예시를 -03 → -04 로 (−03 가 표에 들어갔으므로) |
| `e2e_selftest.py` | **E2E PASS** (v2 전 사례 + v3: -02C · -03 유효 · 창 [3.5, 72.0] · 다른 실험 세션 건너뜀 · (C) 확인 "확인 안 됨" (1세션 = 쌍 부족 ≠ 개발 판정) · (S) sustained 필드 · 정의 · 결론 틀) |
| v2 회귀: R3 16세션 + 스모크 4 재검증 (`V.validate`) | **20/20 동일** (절대 경로 문자열 `device_dir` · `host_dir` · `logcat` 만 다름 — R3 는 절대 경로로 호출) |
| v2 회귀: readout (`plan_v2` · R3 결과 · 같은 인자) | `inventory.csv` · `metrics.csv` · `files_inventory.csv` **바이트 동일** · `readout.json` 은 `skipped: ["readout"]` 한 항목만 다름 (R3 가 readout 폴더를 결과 루트 안에 만들었고 그 뒤에 폴더가 생김 — 코드 차이 아님, 판정 · 쌍 · 숫자 전부 동일) |
| plan_v2 재생성 (`mixreq_plan.py --experiment 02`) | **바이트 동일** (`cdf62732…`) |
| 회귀 `:npu-runner:testDebugUnitTest --rerun-tasks` | **61 / 61** |
| `git diff --stat 344dd9f -- npu-runner benchmark-runner app telemetry-contract tools gradle quality-runner` | **빈 diff** |
| 드라이버 `-Experiment 02C -Block N -DryRun` · 스모크 `--dry-run` (v3c · v3s) · 세션 `--dry-run` (v3s index 8, 3,000 요청 manifest) | 통과 (pytest 안 + 수동) |
| `py -m pytest tools` · `d1sim/tests` | (아래 1-5 에 기록) |

## 1-4 APK v3 · 계획 [P]

- **APK v3 `request-runner-debug.apk` 14,444,380 B · SHA-256 `b97a97842471b0727dc36f4d3c7230108397c0e43cd7406e654c5f038c8b89b7`** (20:48, `:request-runner:assembleDebug`, 모델 0 · dispatch `.so` 포함) → 사본 `local_inputs\apk\request-runner-debug_v3.apk` (git 밖). v2 APK `591cae72…` 는 그대로 보관.
- **plan_v3c** (`--experiment 02C`): `plan.json` SHA `dcae7acce70e01cdf8d9445d3877751b01275798a27888fcfe9cb65aeba797ba` · 16 + 스모크 4 · 실행 순서 [8..15, 0..7] · 등록 v3 `45f151d3…` (+ v2 · v1) · sid 0 = `4add7ebd-…` · 호출 3,216.
- **plan_v3s** (`--experiment 03`): `plan.json` SHA `66a719bd5b6e830b73056f464f14091e51e697e61a42cfa451fca2fb46519dff` · 3,000 요청 (끝 634,800 ms) · 공통창 720 s · 호출 48,144 · sid 0 = `2bf5048f-…` · 두 번 생성 바이트 동일 · 7.1 MB (manifests 16).
- 호스트 도구 SHA (커밋 ② 전): `mixreq_common.py` `e8f57d92…` · `mixreq_plan.py` `1972f83a…` · `mixreq_session.py` `f0175844…` · `mixreq_validate.py` `effa050e…` · `mixreq_readout.py` `4dc2ff08…` · `mixreq_driver.ps1` `5c2055e8…` · `mixreq_smoke.py` `706e358c…` · `mixreq_a24_compare.py` `c1e43ece…` (무변경).

### `git diff e2bedf1 -- request-runner/src/main/java` (커밋 ② 직전 · 전문)

```diff
diff --git a/request-runner/src/main/java/MixreqContract.kt b/request-runner/src/main/java/MixreqContract.kt
index 8797d7ae..d8df0d43 100644
--- a/request-runner/src/main/java/MixreqContract.kt
+++ b/request-runner/src/main/java/MixreqContract.kt
@@ -10,6 +10,8 @@ package com.example.d1check.requestrunner
  *   d1sim/docs/혼합요청_사전등록_v1.md §1 · §2 · §3 (S26 쪽 값: 블록 · 상주 runtime · 준비 상한 · 정지 규칙)
  * 의미를 바꾸지 않는다. A24 와 다른 값은 "A24 와 다름" 으로 주석에 적는다.
  * v2 (등록 v2 `d1sim/docs/혼합요청_사전등록_v2.md` #1 · #2, 2026-10-09): STEP_MS 400 → 200 · EXPERIMENT_ID -01 → -02 (스모크도). v1 = `03f271a`. 그 밖 무변경.
+ * v3 (등록 v3 `d1sim/docs/혼합요청_사전등록_v3.md` §0-1 · §0-2, 2026-10-09): 실험 ID 표 EXPERIMENTS (-02 · -02C · -03 · 각 -SMOKE → 요청 수 · 공통창 · index 범위) ·
+ *   COMMON_NS 는 SessionManifest.validate() 가 고른 표 행에서 · WATCHDOG_MS 는 표의 최댓값 · validateRequests 의 요청 수 허용 = 표. v2 = `e2bedf1`. 그 밖 무변경.
  */
 object MixreqContract {
     const val PROTOCOL = "s26-mixreq-session-v1"
@@ -18,6 +20,21 @@ object MixreqContract {
     const val SPLIT_CONFIRMATION = "confirmation"
     const val SPLIT_DIAGNOSTIC = "diagnostic"
 
+    /** 등록 v3 §0-2 실험 ID 표 (앱 · 호스트 같은 표). 스모크 ID 는 같은 실험의 공통창을 쓰고 요청 수는 SMOKE_REQUEST_COUNT. 간격은 전부 STEP_MS. */
+    data class ExperimentSpec(val id: String, val smokeId: String, val requestCount: Int, val commonS: Long, val sessionIndexMax: Int, val watchdogMs: Long)
+    val EXPERIMENTS = listOf(
+        ExperimentSpec("S26-MIXREQ-02", "S26-MIXREQ-02-SMOKE", 192, 120L, 15, 600_000L),
+        ExperimentSpec("S26-MIXREQ-02C", "S26-MIXREQ-02C-SMOKE", 192, 120L, 15, 600_000L),
+        // (S) 지속: 3,000 요청 (35.0 ~ 634.8 s) · 공통창 720 s · watchdog = 준비 180 + 게이트 60 + 기준 30 + 창 720 + drain 30 + 냉각 60 = 1,080 → 여유 1,260 s
+        ExperimentSpec("S26-MIXREQ-03", "S26-MIXREQ-03-SMOKE", 3_000, 720L, 15, 1_260_000L),
+    )
+
+    fun experimentOf(experimentId: String): ExperimentSpec =
+        EXPERIMENTS.firstOrNull { it.id == experimentId || it.smokeId == experimentId } ?: error("unknown experiment_id $experimentId")
+
+    /** SessionManifest.validate() 가 정한다 (한 프로세스 = 한 세션 = 실험 하나). 엔진은 COMMON_NS 를 이 표 행에서 읽는다. */
+    @Volatile var activeExperiment: ExperimentSpec = EXPERIMENTS[0]
+
     const val REQUEST_COUNT = 192
     const val SMOKE_REQUEST_COUNT = 24
     const val FIRST_OFFSET_MS = 35_000L
@@ -26,7 +43,8 @@ object MixreqContract {
     const val NORMAL_DEADLINE_MS = 6_000L
 
     // A24 ArrivalEnergyContract (같은 값)
-    const val COMMON_NS = 120_000_000_000L
+    /** v3: 실험 ID 표의 공통창 (-02 · -02C 120 s = A24 값 · -03 720 s). 값은 SessionManifest.validate() 가 고른 표 행. */
+    val COMMON_NS: Long get() = activeExperiment.commonS * 1_000_000_000L
     const val DRAIN_SECONDS = 30L
     const val BASELINE_SECONDS = 30L
     const val COOLING_SECONDS = 60L
@@ -36,7 +54,8 @@ object MixreqContract {
     /** A24 와 다름: 블록 N 은 상주 runtime 5 (NPU 추가) 라 준비 상한 180 s (등록 §3-2). */
     const val SETUP_NS_BLOCK_N = 180_000_000_000L
     /** A24 와 다름: A24 480 s (준비 150). 블록 N 준비 180 s + 게이트 60 + 기준 30 + 공통창 120 + drain 30 + 냉각 60 = 480 → 여유 600 s. */
-    const val WATCHDOG_MS = 600_000L
+    /** v3: Activity 가 manifest 를 읽기 전에 거는 값이라 실험 ID 표의 최댓값 (-03 1,260 s). 세션별 상한은 호스트 (mixreq_session.py) 가 실험 ID 로 건다. */
+    val WATCHDOG_MS: Long get() = EXPERIMENTS.maxOf { it.watchdogMs }
     const val SAMPLE_PERIOD_MS = 900L
     const val WARMUPS_PER_KEY = 2
 
@@ -100,9 +119,10 @@ object MixreqContract {
      * A24 ArrivalPolicyStudy.validate 의 sustained-confirmation-v1 분기 그대로:
      * 짝수 = 분류 urgent 1,500 ms · 홀수 = 탐지 normal 6,000 ms · offset = 35,000 + 400·i · ID 유일.
      * count 192 = 본 세션 · 24 = 스모크 (앞 24요청 판, 등록 §3-8).
+     * v3: count 는 실험 ID 표의 요청 수 (192 · 3,000) 또는 24 (등록 v3 §0-2).
      */
     fun validateRequests(requests: List<Request>, count: Int = REQUEST_COUNT) {
-        require(count == REQUEST_COUNT || count == SMOKE_REQUEST_COUNT) { "request count must be 192 or 24" }
+        require(count == SMOKE_REQUEST_COUNT || EXPERIMENTS.any { it.requestCount == count }) { "request count must be in the experiment table (192, 3000) or 24" }
         require(requests.size == count && requests.map { it.id }.toSet().size == count) { "request count/id" }
         requests.forEachIndexed { i, q ->
             val urgent = i % 2 == 0
diff --git a/request-runner/src/main/java/SessionManifest.kt b/request-runner/src/main/java/SessionManifest.kt
index 1342d550..2a008fbf 100644
--- a/request-runner/src/main/java/SessionManifest.kt
+++ b/request-runner/src/main/java/SessionManifest.kt
@@ -48,11 +48,14 @@ class SessionManifest(
     fun validate() {
         require(protocol == MixreqContract.PROTOCOL) { "protocol $protocol" }
         require(split == MixreqContract.SPLIT_CONFIRMATION || split == MixreqContract.SPLIT_DIAGNOSTIC) { "split $split" }
+        // v3 (등록 v3 §0-1 · §0-2): 실험 ID 는 표에 있어야 하고 (fail closed), 요청 수 · 공통창 · index 범위는 그 표 행의 값이어야 한다.
+        val experiment = MixreqContract.experimentOf(experimentId)
+        MixreqContract.activeExperiment = experiment
         require(Uuid5.isCanonical(sessionId)) { "session_id" }
         require(block == MixreqContract.BLOCK_A || block == MixreqContract.BLOCK_N) { "block $block" }
         require(policy in MixreqContract.policiesOf(block)) { "policy $policy is not allowed in block $block" }
         require(attempt in 1..2) { "attempt $attempt" }
-        require(sessionIndex in 0..15 && pair in 0..3) { "session_index/pair" }
+        require(sessionIndex in 0..experiment.sessionIndexMax && pair in 0..3) { "session_index/pair" }
         val keys = runtimes.map { it.key }
         require(keys.toSet() == MixreqContract.keysOf(block) && keys.size == keys.toSet().size) {
             "runtimes $keys != block $block keys"
@@ -67,14 +70,14 @@ class SessionManifest(
         MixreqContract.validateRequests(requests, requests.size)
         RequestPlan.requireDerived(experimentId, sessionIndex, sessionId, requests)
         if (split == MixreqContract.SPLIT_CONFIRMATION) {
-            require(experimentId == MixreqContract.EXPERIMENT_ID) { "confirmation experiment_id" }
-            require(requests.size == MixreqContract.REQUEST_COUNT) { "confirmation needs 192 requests" }
+            require(experimentId == experiment.id) { "confirmation experiment_id" }
+            require(requests.size == experiment.requestCount) { "confirmation needs ${experiment.requestCount} requests" }
             require(timeScale == 1) { "confirmation needs time_scale 1" }
             require(!warmupOnly) { "confirmation cannot be warmup_only" }
         } else {
             require(timeScale in 1..100) { "time_scale" }
         }
-        require(phases.commonS == 120L && phases.baselineS == MixreqContract.BASELINE_SECONDS &&
+        require(phases.commonS == experiment.commonS && phases.baselineS == MixreqContract.BASELINE_SECONDS &&
             phases.drainS == MixreqContract.DRAIN_SECONDS && phases.coolingS == MixreqContract.COOLING_SECONDS &&
             phases.gateS == MixreqContract.GATE_NS / 1_000_000_000L) { "phase lengths must equal the contract" }
         require(phases.setupS * 1_000_000_000L == MixreqContract.setupNsOf(block)) { "setup_s for block $block" }
```

## 1-5 회귀 · 커밋 ② · push (20:5x) [P]

- `py -m pytest tools` **243 passed · 1 failed** (= 기준: `test_d1_representative_tensors … canonical_bytes_and_hash_golden`, CRLF fixture) · `d1sim/tests` **93 passed**.
- **커밋 ② `c75d0855edb44e38d064a93f192f37efdfe2a50b`** (2026-10-09 20:51:36 +0900) "request-runner · s26/tools/mixreq: v3 (실험 ID 표 · 지속 3,000 · 720 s · 확인 순서) + 계획 v3c · v3s (v3 칸 전)" — 61 파일 +909/−72 (앱 2 · 시험 3 · 호스트 9 · plan_v3c 21 · plan_v3s 21 · 원장) · 추가 줄 PAT 0 · 바이너리 0 → **push `344dd9fa..c75d0855` · origin = HEAD**.

## 2-1 (C) 폰 준비 (20:51) [P]

- adb `device` · SOC 71 · plugged 0 · `screen_off_timeout` 86400000 ✔ · 잠금 없음 · 밝기 모드 0 · `screen_brightness 0` put → 폰이 1 로 되돌림 (v2 #7 허용) · 비행기 1 · zen 1 · HAL AP 27.0 · BAT 25.2 · SKIN 27.7.
- **APK v3 설치** (`adb install -r`, Success) · 기기 `pm path` sha256sum = **`b97a9784…` = 1-4 값** ✔ · `npurunner` `5ac485e3…` 무접촉.

## 2-2 (C) 스모크 · A24 대조 (20:52:23 ~ 21:09:04, `results\S26_MIXREQ_SMOKE_R4C`, APK v3 · plan_v3c) [P] — 기록만 (v2 #3 · #5)

- S1 (warmup_only 블록 N, 20:52:23 ~ 20:52:47): 게이트 즉시 PASS (SKIN 27.9 · AP 26.0 · BAT 25.4 · SOC 71) · 5 runtime · warmup 10 · 텐서 `603328d0…` ✔ · RGB `ca6c2e2b…` ✔ · CPU top-5 = PC 참조 ✔ · 탐지 CPU = PC 참조 (A24 허용) ✔ · GPU vs CPU §4-6 ✔ ×2 · `detection_GPU` 생성 ✔ · GPU 증거 PASS ×2 · NPU 증거 FAIL = `no_dispatch_failure_in_common_window` (warmup_only 에 공통창 없음 — R2 · R3 와 같은 검증기 한계) · **NPU 계약 첫 값 PASS (top-1 518 · cosine 0.9999935 ×2 = R3 와 같은 값)** · **`top -H` 파서 보수 확인: 패키지 스레드 행 31 · `d1mix-*` 3** (R3 는 0행).
- S2: CPU rc 0 유효 · 겹침 0 (21:54:14 ~ 20:58:06, 게이트 28.0 · 26.0 · 25.5) / PAR rc 0 유효 · **겹침 0.437 s** (20:59:36 ~ 21:03:28) / PAR-NPU rc 0 유효 · **겹침 0.420 s** · NPU 계약 PASS (21:04:59 ~ 21:08:51, SOC 70) · (a)~(d) 셋 다 통과 · decisions [] · observations [] (v3 기록만).
- **A24 대조 (`mixreq_a24_compare.py` `c1e43ece…` 무변경) PASS**: 탐지 warmup 0 · 1 각각 라벨 같음 · |Δscore| 0.0 · box ≤ 4.4e-5 px · 입력 텐서 = A24 ✔ · 분류 top-5 5/5 |Δscore| ≤ 3.6e-7 · raw ≠ (엔진 다름, 기록만) → `a24_compare.json`.
- 재시도 0 · 비상 0 · 잠금 0 · adb 끊김 0 · 밝기 설정값 1 (허용) · 화면 86400000 유지.

## 2-3 (C) 블록 N 시작 (21:1x) — 드라이버 `mixreq_driver.ps1 -Block N -Experiment 02C` (index 8 → 15: PAR-NPU · CPU · CPU · PAR-NPU · CPU · PAR-NPU · PAR-NPU · CPU) → 끝나면 `-Block A` (0 → 7). 결과 지위 = S26 부록 관측 (조민규 확인 없음).

## 2-3 (C) 블록 N 진행 (21:09:51 ~) [P] — 세션 사용 한도로 Claude 세션 중단 (21:2x)

- index 8 PAR-NPU rc 0 (21:09:51 ~ 21:13:47) · 9 CPU rc 0 (~21:19:09) · 10 CPU rc 0 (~21:24:35) · 11 PAR-NPU 실행 중 (21:24:35 ~). 재시도 0 · 비상 0. 드라이버 (pid `driver_pid_blockN.txt`) 는 detached 로 계속 돈다 — index 15 까지 혼자 끝낸다 (`driver_log_blockN.txt` 의 `DRIVER END` 줄).
- **남은 것 (새 Claude 세션이 이어서)**: ① 블록 N `DRIVER END` 확인 → `mixreq_driver.ps1 -Block A -Experiment 02C` (0 → 7) ② (C) readout: `mixreq_readout.py --plan s26\results\mixreq_1008\plan_v3c\plan.json --results results\S26_MIXREQ_R4C --out results\S26_MIXREQ_R4C\readout --a24-compare results\S26_MIXREQ_SMOKE_R4C\a24_compare.json --apk-sha256 b97a9784… --source-commit c75d0855… --reference-readout s26\results\mixreq_1008\R3_readout\readout.json` → 결과 사본 `R4C_*` · 커밋 ③ · push ③ 3부 (S): 충전 SOC 90 → 스모크 `mixreq_smoke.py --plan plan_v3s --results results\S26_MIXREQ_SMOKE_R4S --allow-settings-mismatch --reference-pc …` → `mixreq_driver.ps1 -Block N -Experiment 03` → 충전 → `-Block A -Experiment 03` ④ 4부 (S) readout (`--plan plan_v3s\plan.json --results results\S26_MIXREQ_R4S …`) · `sim\혼합요청_결과_v3.md` · `작업결과_1010_R4_혼합요청v3.md` · 커밋 ④ · push · CLAUDE.md 블록. 원복: 화면 86400000 유지 (영훈) · 밝기 127.

## 2-3 (C) 블록 N 끝 (21:09:51 ~ 21:51:29) [P]: **8/8 유효** (index 8 ~ 15 전부 rc 0) · 재시도 0 · invalid_twice 0 · 연결 사고 0 · 비상 0 · 블록 안 충전 0 · `DRIVER END block=N reason=completed`. Claude 세션은 21:2x ~ 22:45 사용 한도로 비어 있었고 그동안 드라이버가 혼자 끝냈다 (설계대로). 22:45 폰 SOC 62 · 잠금 없음 · 프로세스 0.
## 2-3 (C) 블록 A 시작 22:46 — `-Block A -Experiment 02C` (index 0 → 7: PAR · CPU · CPU · PAR · CPU · PAR · PAR · CPU). SOC 62 ≥ 40 → 충전 없이.

## 2-3 (C) 블록 A 끝 (22:46:03 ~ 23:27:45) [P]: **8/8 유효** (index 0 ~ 7 rc 0) · 재시도 0 · 비상 0 · 블록 안 충전 0 · 게이트 대기 0 s (SKIN 26.8 ~ 30.3) · `DRIVER END block=A reason=completed`. **(C) 16/16 유효** · NPU 계약 4/4 PASS · 실행 순서 8 → 15 → 0 → 7 (등록 (C)-2).

## 2-4 (C) readout · 확인 판정 (23:28 · 23:3x) [P]

- `mixreq_readout.py --plan plan_v3c --results results\S26_MIXREQ_R4C --a24-compare …R4C\a24_compare.json --apk-sha256 b97a9784… --source-commit c75d0855… --reference-readout R3_readout\readout.json` → 16세션 · slots valid 16 · 꼬리표 0 · A24 대조 PASS.
- **확인 판정 (등록 (C)-4)**: **Q1 (블록 A) = "확인됨 (개발 · 확인 2블록 같은 판정)"** — 개발 R3 · 확인 R4 둘 다 "병행이 긴급 응답을 줄였다" (R4 4쌍 Δ긴급 P95 −28.9 · −35.9 · −34.4 · −38.4 ms · CPU 107.5 ~ 114.0 → PAR 74.9 ~ 78.6) · **Q3 (블록 N) = "확인됨"** — 둘 다 "NPU 병행이 긴급 응답을 줄였다" (R4 −38.6 · −42.5 · −57.1 · −45.0 ms · CPU 109.8 ~ 124.2 → PAR-NPU 67.2 ~ 71.1 · NPU 계약 4/4). 서비스 "두 정책 모두 기한 충족" ×2 (16 × 192/192) 같음 · 일반 P95 판정 같음 (A "엇갈림" / N "같은 방향 · 일부 작음").
- **다른 판정 (나란히 · Q 판정은 `judgment` 만 따른다)**: 블록 A 최고 SKIN — 개발 "열 차이 기준 안 (1.0 ℃)" vs 확인 **"엇갈림"** (R4 Δ −1.1 · −0.2 · −0.2 · −0.1 — 쌍 A0 한 쌍이 −1.1 ℃, 시작 SKIN 첫 세션 29.5 ℃ 로 가장 낮음) · 블록 A 최고 AP — 개발 "엇갈림" vs 확인 **"병행이 덜 뜨거웠다"** (Δ −3.1 · −1.0 · −1.1 · −1.1 — 전부 ≤ −1.0) · 블록 N 6 항목 전부 같음 (SKIN "기준 안" Δ −0.9 · −0.1 · −0.3 · −0.4 · AP "엇갈림" Δ −2.0 · −0.8 · −1.3 · −1.4).
- 겹침 PAR 4.22 ~ 4.50 s · PAR-NPU 4.26 ~ 4.51 s (R3 4.45 ~ 4.77 / 4.46 ~ 4.67) · J (µA 해석 · 기술만) ΔA −22.8 · −33.9 · −13.8 · −25.3 · ΔN −29.7 · −0.3 · −28.6 · −50.2 · SOC 71 → 56.
- **결과 뒤 라벨 수정 1건 (기록)**: 첫 readout (`readout_c/`, 사본 `R4C_readout_first/`) 의 Q2 표 제목이 v1 문구 (`reg_version == 2` 조건) 였다 → `>= 2` 로 고쳐 다시 실행 (`readout/`, 사본 `R4C_readout/`). 두 readout 은 `q2_table` (제목 · note) 과 `skipped` 만 다르고 판정 · 쌍 · KPI · CSV 3개 바이트 동일. 판정 · 허용치 변경 0.
- 결과 사본 (`git add -f`): `R4C_smoke/` (S1 + S2 ×3 · smoke_report · a24_compare, logcat 제외) · `R4C_blocks/` (16세션 device + host (logcat 제외) + validated + npu_contract · 드라이버 로그 · state · keepawake) · `R4C_readout/` · `R4C_readout_first/`.

## 3-1 (S) 충전 대기 → 생략 (23:28 ~ 00:30) [P] — 프롬프트와 다르게 한 것

- 23:28 "케이블 꽂으세요 (SOC 90)" → 60 분 동안 plugged 0 (SOC 56 → 54, 영훈 응답 없음). 영훈 10/9 지시 "중간에 내 답을 기다리지 말고 무조건 완주 규칙대로" 에 따라 **SOC 54 에서 (S) 스모크 → 블록 N 을 충전 없이 시작** (R3 프롬프트 표: SOC < 30 → 드라이버 `CHARGE NEEDED` 멈춤 → 충전 → `-StartIndex` 로 이어서). 게이트 (SOC 30 ~ 100) 가 세션 시작을 막으므로 앱 안 SOC < 20 멈춤은 나지 않는다. 세션 중 케이블이 꽂히면 그 세션은 앱 안 멈춤 (plugged) → 재시도 1회.
- (S) 스모크 시작 00:30 (`results\S26_MIXREQ_SMOKE_R4S`, plan_v3s · 24 요청 · 공통창 720 s = 등록 표).

## 3-2 (S) 스모크 (00:30:04 ~ 01:16:25, `results\S26_MIXREQ_SMOKE_R4S`, APK v3 · plan_v3s · 24 요청 · 공통창 720 s) [P] — 기록만

- S1 (warmup_only 블록 N): 5 runtime · warmup 10 · 텐서 · RGB · PC 참조 ✔ · GPU 증거 PASS ×2 · NPU 증거 FAIL = warmup_only 공통창 조건 (검증기 한계, R2 · R3 · (C) 와 같음) · NPU 계약 PASS · `top -H` 패키지 스레드 30 · `d1mix-*` 3.
- S2 (각 ≈ 15 분 = 720 s 창 실기기 첫 통과): CPU rc 0 유효 · 겹침 0 (00:31:55 ~ 00:45:40, 게이트 26.8 · 24.4 · 24.1) / PAR rc 0 유효 · **겹침 0.480 s** (00:47:10 ~ 01:00:56, 27.5 · 25.5) / PAR-NPU rc 0 유효 · **겹침 0.493 s** · NPU 계약 PASS (01:02:26 ~ 01:16:11, 27.6 · 25.6 · 25.1). (a)~(d) 셋 다 통과 · decisions [] · observations [] · 재시도 0 · 비상 0 · SOC 54 → 50.

## 3-3 (S) 블록 N 시작 01:16:44 — `-Block N -Experiment 03` (CPU · PAR-NPU · PAR-NPU · CPU · PAR-NPU · CPU · CPU · PAR-NPU) · SOC 50 · 충전 없이 (3-1) · `CHARGE NEEDED` 가 뜨면 영훈에게 "케이블 꽂으세요".

## 3-3 (S) 블록 N 1차 (01:16:44 ~ 02:47:07) [P]: index 8 · 9 · 10 · 11 · 12 **유효 5/8** (각 ≈ 15 분 · 게이트 대기 0 ~ 120 s · SKIN 27.9 ~ 30.8) · 재시도 0 · 비상 0 · SOC 50 → < 30 → index 13 게이트 `GATE_BLOCKED_NONTHERMAL` → rc 6 → **`DRIVER END reason=CHARGE NEEDED at index 13`** (02:47). 영훈에게 "케이블 꽂으세요 (SOC 90)". 재개 = `-Block N -Experiment 03 -StartIndex 13` (index 13 a1 호스트 폴더는 폰에 닿기 전 rc 6 라 `_pre1_charge` 로 옆에 둔 뒤 — 드라이버 pre-start 규칙과 같은 운영 처리).
- **(S) readout 전 수정 1건 (02:5x, 코드 — 판정 규칙 아님)**: (S) 세션의 호스트 HAL 표본 간격이 ≈ 3.2 s (`listing_period_s` 3 s 때문; v2 · (C) 는 ≈ 2.3 s) 로, `time_above()` 의 gap 상한 2.5 s 로는 모든 구간이 빠져 38 ℃ 시간이 늘 0 이 된다 — 5 세션 산출물의 **필드 존재만 확인하는 파이프라인 점검** (스크래치, KPI 미열람 · 미기록) 중 표본 간격으로 발견. `TIME38_MAX_GAP_S` 2.5 → **5.0 s** (실측 최대 3.68 s 포함 · adb 끊김 ≥ 60 s 는 여전히 제외) · 정의 문구 갱신 · 시험 추가. 60 s 판정 규칙 · 그 밖 지표 무변경. 커밋 ④ 에 포함 (블록 도는 중 git 0).
- 충전: 02:47 요청 → **08:24 케이블 연결** (SOC 14 — 5시간 37분 대기, 그동안 화면 켜짐 유지로 SOC 26 → 14) → 10:16 SOC 90 → "뽑으세요" → **10:37 분리 (SOC 98)** → 10:38 `-Block N -Experiment 03 -StartIndex 13` 재개.
- **index 13 (CPU) attempt 1 무효 (11:16 ~ 11:30)** [P 진단 · KPI 아님]: 게이트 38 분 대기 뒤 31.3 · 30.0 · 29.8 로 시작 (충전 직후 · 1차 세션들보다 3 ℃ 높음) → 앱 안 `post-window drain incomplete` (요청 2,800 / 3,000 완료 · 창 끝 720 s + drain 30 s 안에 CPU lane 이 못 따라감 · 마지막 lane_available 750 s · 탐지 CPU 서비스 시간 중앙 238 → 506 ms (유효한 index 8 은 236 → 365 ms · 마지막 656.6 s) · 창 끝 SKIN 38.9 · AP 41.6). 규칙 0 · 1 · 9 로 무효 → 드라이버 재시도 1회 (600 s 쉼 + 게이트). 두 번째도 무효면 `invalid_twice` → 다음 index (쌍 N2 소실 · 남은 쌍 3 ≥ 3). 설계 · 규칙 변경 0.
- **index 13 attempt 2 무효 (11:52 ~ 12:07)** [P]: 게이트 12 분 대기 뒤 31.4 · 30.1 · 30.0 시작 → 같은 원인 `post-window drain incomplete` (2,830 / 3,000 · 마지막 lane_available 750.4 s · 창 끝 SKIN 38.2 · AP 40.5) → **`INVALID_TWICE` index 13 → 다음 index (등록 v2 #6)**. 쌍 N2 (12 · 13) 소실. index 14 (CPU) 도 같은 조건이면 쌍 N3 소실 → 블록 N 쌍 2 < 3 → "쌍 부족 — 기술만" 이 될 수 있다 (규칙 그대로 둔다 · 기록만).
- **index 14 (CPU) attempt 1 무효 (12:24 ~ 12:39)** [P]: 시작 31.4 · 30.0 · 29.9 → 같은 원인 `post-window drain incomplete` (완료 수 · 창 끝 SKIN 은 레포 사본 `R4S_blocks/`) → 600 s 쉼 + 게이트 뒤 attempt 2. 오후 (실내 · 폰 모두 더 따뜻한 상태 · 게이트 통과 직후 SKIN 31.4) 의 CPU 직렬은 600 s 를 못 버틴다 — 새벽 1차 (index 8 · 11, 27.9 ~ 30.8 시작) 는 유효. 규칙 변경 0.
- **index 14 attempt 2 무효 (12:59 ~ 13:14)** [P]: 같은 원인 → **`INVALID_TWICE` index 14**. 블록 N 유효 = 8 · 9 · 10 · 11 · 12 (+ 15 진행) → 쌍 N0 (8 · 9) · N1 (10 · 11) 만 완전 → **n = 2 < 3 → 블록 N 판정 "쌍 부족 — 기술만"** 이 확정 (등록 (S)-7). 무효 4세션 (13 ×2 · 14 ×2) 의 "CPU 직렬이 600 s 를 못 따라감 (2,800 ~ 2,840 / 3,000 · 창 끝 SKIN 38 ~ 39)" 은 결과 문서에 기술 (유효 세션 아님 · KPI 아님).

## 운영 중단 (영훈 지시 10/10 13:28 "지금 R4 측정 중단해. 인터넷이 곧 바뀐다") — 13:29:33 [P]

- ① 프로세스 정지: 드라이버 (pid 15832, `-Block N -Experiment 03 -StartIndex 13`) · 세션 py/python (8324 · 29060, index 15 attempt 1) · 게이트 python (24180) · keepawake (30464) → Stop-Process 전부 성공 · `keepawake.stop` 기록 · 남은 프로세스 0.
- ② adb 붙어 있음 (`device`) → `am force-stop com.example.d1check.requestrunner` (앱은 떠 있지 않았음 — 게이트 대기 중) · `npurunner` · `qualityrunner` 무접촉. SOC 80.
- ③ 진행 중이던 시도: **블록 N · index 15 (PAR-NPU) · attempt 1** — 13:14:33 세션 시작 → 간격 85 s 대기 → 13:15:59 게이트 폴링 중 (SKIN/BAT 기준 미달로 대기, 앱 미시작 · manifest 미push · 기기 폴더 없음 [P]) → **시도 소모 없음 (운영 중단)**. 호스트 폴더 → `S26_MIXREQ_15_S26_NPU_PARALLEL_V1_a1_abort_133009`. 재개 = `mixreq_driver.ps1 -Block N -Experiment 03 -StartIndex 15` (attempt 1 부터).
- 남은 칸: (S) 블록 N index **15** (미시도) · (S) 블록 A index **0 ~ 7** (전부 미시도, 충전 뒤) · (S) readout · 4부 보고 · CLAUDE.md 블록 · 커밋 ④. 완료: (C) 16/16 (커밋 ③ push 완료) · (S) 스모크 · (S) 블록 N 유효 8 · 9 · 10 · 11 · 12 · invalid_twice 13 · 14.
- ④ git 커밋 · push 없음 (지시). 작업 트리 미커밋 변경 = `mixreq_readout.py` (38 ℃ 시간 gap 상한 5 s · 라벨) · `test_mixreq.py` · `R4_LEDGER.md` — 다음 세션이 커밋 ④ 에 포함.
- ⑤ 폰: `screen_off_timeout` 86400000 그대로 · 밝기 1 (수동) · 비행기 · 방해 금지 그대로 · 케이블 없음 · APK v3 설치된 채 · `/data/local/tmp/mixreq` 보존.
- 인터넷 (학교망) 이 바뀌면 무선 디버깅 주소가 바뀐다 → 재개 시 `adb devices -l` · 폰 무선 디버깅 화면으로 새 `<IP:PORT>` 확인 (R3 9-3 과 같은 절차).

## R4 재개 (10/10 15:1x ~, 프롬프트 `프롬프트_R4재개_1010.md`) — 0단계 · 1단계 [P]

- **0단계 (15:15)**: R4 프로세스 (`mixreq_driver` · `mixreq_session` · `keepawake_block` · `phone_watch` · `skin_watch`) **0**. `git status -sb`: HEAD `3ab3d706` = `origin/s26-mixreq` · 미커밋 3 파일 = `R4_LEDGER.md` · `mixreq_readout.py` (38 ℃ gap 5 s) · `test_mixreq.py` (운영 중단 ④ 그대로, 건드리지 않음 · 커밋 ④ 에 포함). 디스크 free 12 GB (> 10 GB). 측정 코드 변경 0.
- **재개 전 상태 (원장 · `driver_state_blockN.json` (resume13 실행분: 13 · 14 `invalid_twice` · retries 2) · `results\S26_MIXREQ_R4S\` 폴더 · `validated.json` `eligible` · `reasons` 로 확정)**:

| index | 정책 | 시도 폴더 | 판정 (validated `reasons`) |
|---|---|---|---|
| 8 | CPU | a1 | **valid** (reasons []) |
| 9 | PAR-NPU | a1 | **valid** |
| 10 | PAR-NPU | a1 | **valid** |
| 11 | CPU | a1 | **valid** |
| 12 | PAR-NPU | a1 | **valid** |
| 13 | CPU | `a1_pre1_charge` (rc 6 · 폰 미접촉 · 미소모) · a1 · a2 | **invalid_twice** (a1 · a2 모두 reasons 0 · 1 · 2 · 3 · 4 · 5 · 9 = drain incomplete) |
| 14 | CPU | a1 · a2 | **invalid_twice** (같은 reasons) |
| 15 | PAR-NPU | `a1_abort_133009` (운영 중단 · 게이트 대기 중 · 앱 미시작 · `host/session_log.txt` 만) | **미시도 → 여기서 재개 (attempt 1)** |
| A 0 ~ 7 | CPU · PAR · PAR · CPU · PAR · CPU · CPU · PAR | 없음 | **미시도** (블록 N 뒤 · 충전 뒤) |

- **운영 중단 시도 처리 (0단계 4, 결과 · KPI 를 보지 않고 정한 운영 규칙)**: 블록 N index 15 attempt 1 (13:14:33 시작 · 13:15:59 ~ 13:29 게이트 폴링 중 중단) 은 폰에 닿지 않았다 (manifest 미push · 기기 폴더 없음 · 앱 미시작) → 폴더는 이미 `S26_MIXREQ_15_S26_NPU_PARALLEL_V1_a1_abort_133009` 로 옆에 있고 **시도를 소모하지 않는다** (R3 원장 1-2 ③ "연결 문제 · 시도 소모 안 함" 과 같은 처리 — 측정 실패 아님). 재개 = index 15 attempt 1 부터.
- **1단계 연결 (15:15 ~ 15:19)**: `adb devices -l` 비어 있음 → 영훈이 준 새 망 주소 (`192.0.0.x` 대역 · 포트) 로 `adb connect` → **timeout (10060)**. PC 는 핫스팟 망 (IPv4 /28, 게이트웨이 1개) 에 붙어 있고, 그 대역 포트 스캔 · 게이트웨이 IPv4 · IPv6 전부 거부 (10061). `adb mdns services` 가 폰 서비스 (`adb-<SERIAL>-…  _adb-tls-connect._tcp :<PORT>`) 를 **주소 없이** 찾음 → mDNS 이름으로 `adb connect` 는 거부 → IPv6 all-nodes ping 으로 Wi-Fi 링크의 이웃을 열거 → 게이트웨이가 아닌 IPv6 링크로컬 이웃 1개 → **`adb connect [<IPv6 링크로컬>%<if>]:<PORT>` 성공 (15:19, `device`, SM-S942N)**. `$env:ANDROID_SERIAL` = 그 문자열 (세션 도구 · 드라이버는 `<SERIAL>` 로 가림 · PAT 정규식에 IPv6 링크로컬 접두가 포함이라 원장 · 커밋에 안 쓴다). [E] 영훈이 읽은 주소는 폰의 clat464 (464XLAT) 주소로 보이며 PC 에서 닿지 않는다 — 이 망에서는 IPv6 링크로컬로 붙는다 (링크로컬은 폰의 무작위 MAC 에서 나오므로 같은 망이면 유지 [E]). `kill-server` · `start-server` 안 씀 (adb 데몬은 `devices` 가 자동 시작).
- **폰 상태 (15:20, 첫 명령 = `settings put system screen_off_timeout 86400000` — 이미 86400000)**: 잠금 없음 (`isKeyguardShowing=false` · Awake) · **SOC 77 · plugged 0** (status 3 방전 · 케이블 없음 ✔) · 밝기 1 (모드 0) → **0 put → 0 유지** · 비행기 1 · zen 1 · HAL **SKIN 29.7 · AP 34.7 / 26.6 · BAT 25.3 / 26.3** (중단 13:28 SKIN 32.1 → 식음) · 설치본 APK `b97a9784…` = v3 ✔ (재설치 없음).
- **2단계 드라이버 재개 15:20:59**: `mixreq_driver.ps1 -Block N -Experiment 03 -StartIndex 15` (기본 plan `plan_v3s` · 결과 root `results\S26_MIXREQ_R4S` — R4 와 같음) · pid `driver_pid_blockN_resume15.txt` · stdout/stderr `driver_stdout_blockN_resume15.txt` · keepawake 새 pid. **index 15 (PAR-NPU) attempt 1: 게이트 즉시 PASS (대기 0 s · SKIN 28.4 · AP 26.6 · BAT 26.2 · SOC 77 · 직전 쉼 = 13:14 세션 끝 뒤 2 h 7 min)** → 15:21:03 `am start` → warmup 게이트 ARM. 블록 도는 동안 git 0.

## 3-3 (S) 블록 N 끝 (15:20:59 ~ 15:36:21) [P]: index 15 (PAR-NPU) attempt 1 **유효** (rc 0 · `eligible` · reasons [] · 3,000/3,000 성공 · NPU 계약 PASS · 호스트 HAL 표본 250 행) · 게이트 즉시 PASS (대기 0 s · 28.4 · 26.6 · 26.2 · SOC 77) · 직전 쉼 2 h 7 min (13:14 → 15:21, 중단 포함) · SOC 77 → 73 · `DRIVER END block=N reason=completed retries=0 invalid_twice=[]` (resume15 실행분의 state — 13 · 14 의 invalid_twice 는 resume13 실행분 state · 원장 · 폴더로 남음).

**블록 N 합계**: 유효 6 (8 · 9 · 10 · 11 · 12 · 15) · invalid_twice 2 (13 · 14, CPU 직렬 drain incomplete ×4) · 완전 쌍 2 (N0 = 8 · 9, N1 = 10 · 11) · N2 (12 · 13) · N3 (14 · 15) 는 CPU 쪽 소실 → **n = 2 < 3 → "쌍 부족 — 기술만"** (readout 이 확정) · 재시도 2 · 운영 중단 1 (시도 미소모) · 충전 멈춤 1 (`_pre1_charge`) · 비상 0 · 연결 사고 0.

## 3-3 (S) 블록 A 시작 15:37:49 — 충전 없이 (프롬프트와 다르게 한 것 · 운영 규칙) [P]

- 등록 v3 (S)-4 · R4 프롬프트 3부 = "블록 N → 충전 (SOC 90) → 블록 A". **SOC 73 (케이블 없음) 에서 충전 없이 시작**한 이유 (결과 · KPI 를 보지 않고 정함): ① 영훈 10/9 지시 "중간에 내 답을 기다리지 말고 무조건 완주 규칙대로" (R4 3-1 과 같은 처리 — 그때는 60 분 응답 없음 뒤 SOC 54 에서 시작) ② (C) 의 블록 사이 기준 "SOC < 40 이면 충전" 을 넘는다 (73) — 8세션 ≈ 2 %p 씩 [E] 이면 끝 ≈ 57 · 게이트 SOC 30 까지 여유 ③ R4 3-3 의 관측: 충전 직후 (SOC 98 · 따뜻한 폰) 재개한 CPU 직렬 4시도가 모두 drain incomplete 무효 — 지금 식은 상태 (게이트 28.4 통과) 를 충전으로 버리지 않는다 (프롬프트 머리 "충전 직후 따뜻하면 … 무효가 되기 쉽다" 와 같은 방향). SOC < 30 이면 드라이버 `CHARGE NEEDED` → 영훈에게 "케이블 꽂으세요 (SOC 90)" → `-StartIndex` 로 이어서 ("블록 안 충전").
- `mixreq_driver.ps1 -Block A -Experiment 03` (plan_v3s · `results\S26_MIXREQ_R4S` · 같은 root) · pid `driver_pid_blockA.txt` · stdout `driver_stdout_blockA.txt` · 순서 index 0 → 7 = CPU · PAR · PAR · CPU · PAR · CPU · CPU · PAR. 블록 도는 동안 git 0.

## 3-3 (S) 블록 A (15:37:49 ~ 18:51:07) [P]: **8/8 유효** · 재시도 0 · invalid_twice 0 · 연결 사고 0 · 비상 0 · 블록 안 충전 0 · `DRIVER END block=A reason=completed`

| idx | 쌍 | 정책 | 세션 시작 (RUN) | 게이트 PASS (am start) | 게이트 대기 s | 게이트 SKIN · AP · BAT | 게이트 첫 판 SKIN · AP · BAT | SOC | 판정 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | A0 | CPU | 15:37:49 | 15:43:53 | 361 | 31.0 · 29.6 · 29.4 | 33.5 · 32.6 · 32.1 | 72 | valid (reasons []) |
| 1 | A0 | PAR | 15:59:10 | 16:08:39 | 481 | 31.3 · 29.9 · 29.8 | 34.2 · 33.3 · 33.0 | 68 | valid |
| 2 | A1 | PAR | 16:24:12 | 16:31:40 | 361 | 31.5 · 30.1 · 30.0 | 34.0 · 33.1 · 32.7 | 63 | valid |
| 3 | A1 | CPU | 16:47:01 | 16:56:27 | 481 | 31.3 · 29.9 · 29.7 | 33.8 · 32.9 · 32.6 | 59 | valid |
| 4 | A2 | PAR | 17:12:00 | 17:21:29 | 481 | 31.0 · 29.7 · 29.5 | 34.0 · 33.0 · 32.7 | 54 | valid |
| 5 | A2 | CPU | 17:36:47 | 17:46:15 | 481 | 31.2 · 29.9 · 29.6 | 34.1 · 33.2 · 32.8 | 49 | valid |
| 6 | A3 | CPU | 18:01:33 | 18:11:02 | 481 | 31.5 · 30.1 · 30.0 | 34.4 · 33.7 · 33.2 | 45 | valid |
| 7 | A3 | PAR | 18:26:20 | 18:35:48 | 481 | 31.4 · 30.0 · 29.9 | 34.2 · 33.4 · 33.1 | 40 | valid |

- 직전 쉼 = 세션 간격 85 s + 게이트 대기 (361 ~ 481 s) — 앞 세션 끝 SKIN 33.5 ~ 34.4 에서 게이트 기준 (SKIN ≤ 32 · AP ≤ 32 · BAT ≤ 30) 까지 6 ~ 8 분. 4쌍 전부 완전 (A0 ~ A3) · CPU 직렬 4세션 전부 유효 (블록 N 오후의 drain incomplete 와 달리 게이트 통과 직후 SKIN 31.0 ~ 31.5 로 시작 — 같은 오후 · 충전 없음). SOC 73 → 40 (8세션 ≈ 4 %p 씩 [P]) · 밝기 설정값 0 (이번 재개부터 0 유지) · `screen_off_timeout` 86400000 · 잠금 0 · adb 끊김 0.
- **(S) 16칸 전부 시도 끝 (18:51)**: 유효 14 (N 6 + A 8) · invalid_twice 2 (N 13 · 14) · 재시도 2 · 운영 중단 1 (미소모) · 충전 멈춤 1 · 비상 0.

## 4-1 원복 (20:18) [P]

- 프로세스 0 (keepawake stop 18:51:12) · 앱 미실행 · adb `device` · **SOC 32 · plugged 0** (18:51 뒤 화면 켜진 채 대기로 40 → 32) · `screen_off_timeout` **86400000 유지** (영훈 10/9 19:4x) · **밝기 0 → 127** · 비행기 1 · zen 1 그대로 · HAL SKIN 28.0 · BAT 25.7 · `/data/local/tmp/mixreq` 보존 · APK v3 설치된 채.
- 커밋 ④ 전 시험: `py -3 -m pytest s26/tools/mixreq` **42 passed** (38 ℃ gap 5 s 시험 포함).

## 4-2 (S) readout 한 번 (20:19:25 ~ 20:35:01, `results\S26_MIXREQ_R4S\readout`) [P]

- `mixreq_readout.py --plan plan_v3s\plan.json --results results\S26_MIXREQ_R4S --out …\readout --apk-sha256 b97a9784… --source-commit 3ab3d706…` (readout 코드 = HEAD + 미커밋 gap 5 s 수정 → 커밋 ④). 세션 18 (유효 14 · 무효 4) · skipped 2 (`_pre1_charge` · `_abort_133009`, validated.json 없음) · slots valid 14 / invalid_twice 2 / not_attempted 0 · 다른 실험 세션 0 · A24 식 대조 18/18 match · files_inventory 107,032 파일 (해시 16 분).
- **블록 A (Q-S1, n = 4, 꼬리표 0)**: 주 지표 최고 SKIN **"열 차이 기준 안 (1.0 ℃)"** (Δ 0.0 · 0.0 · 0.0 · 0.0 — **14 유효 세션 전부 최고 SKIN 38.1 ℃**) · 38 ℃ 시간 **"엇갈림"** (Δ −65.7 · −25.2 · −25.8 · −26.2 s — 전부 음수지만 3쌍 < 60 s) · 최고 AP "열 차이 기준 안" (−0.3 · −0.2 · −0.9 · +0.6) · 긴급 응답 **"병행이 긴급 응답을 줄였다"** (Δ −324.2 · −328.1 · −324.5 · −330.0 ms · CPU 424.6 ~ 431.7 → PAR 100.4 ~ 102.6) · 일반 P95 같은 이름 (Δ −42.9 · −38.2 · −43.7 · −58.5 **s**) · 서비스 **"기한 미충족 있음"** (CPU 일반 기한 706 ~ 740 / 1,500 · PAR 1,007 ~ 1,334 / 1,500 · 긴급은 둘 다 1,500/1,500) · 저하 비 · J 기술만.
- **블록 N (Q-S3, n = 2)**: **"쌍 부족 — 기술만"** (tags) · NPU 계약 4/4 PASS · 서비스 "기한 미충족 있음" (CPU 일반 1,066 · 816 / 1,500 · PAR-NPU 4세션 전부 3,000/3,000) · 기술: Δ긴급 −306.2 · −322.6 ms · 최고 SKIN 38.1 ×6 · Δ38 ℃ 시간 +41.1 · +27.1 s · Δ시작 SKIN +2.8 (N0: index 8 새벽 첫 세션 28.6 vs 9 31.4) · 0.0.
- 결과 뒤 코드 변경 0 (readout 은 3-3 의 gap 5 s 수정이 들어간 코드로 한 번) · 판정 규칙 변경 0 · 두 번째 readout 없음.
- 진단 (무효 4세션, KPI 아님 — `device/session_failure.json` `post-window drain incomplete` · 창 시작 SKIN 32.1 ~ 32.2 (게이트 31.3 ~ 31.4) · 완료 2,800 · 2,830 · 2,839 · 2,842 / 3,000 · 마지막 worker_release +750.2 ~ 750.4 s = drain 한계 · 창 끝 (720 s) SKIN 38.1 ~ 38.9 · AP 40.2 ~ 41.2 · 창 안 최고 SKIN 38.2 ~ 38.9 · 탐지 CPU 서비스 (execution_start→output_ready) 처음 60 s 중앙 295 ~ 298 ms → 300 ~ 360 s 459 ~ 506 ms · 마지막 60 s 도착분 처리 0). 유효 CPU 직렬 (블록 A) 도 마지막 lane_available 695.9 ~ 707.7 s 로 750 s 직전.
- 결과 사본 (`git add -f`, logcat 제외): `R4S_blocks/` (18 세션 + `_pre1_charge` + `_abort_133009` + 드라이버 로그 · state · stdout/stderr · pid · keepawake · gate log · 107,032 파일 · 163 MB) · `R4S_readout/` (readout.json · inventory · metrics · files_inventory) · `R4S_smoke/` (S1 + S2 ×3 · smoke_report, 230 파일) · `R4S_reports/` (보고 2 사본).
