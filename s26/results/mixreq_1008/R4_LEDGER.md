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
