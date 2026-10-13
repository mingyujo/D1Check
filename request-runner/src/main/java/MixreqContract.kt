package com.example.d1check.requestrunner

/*
 * S26 판 혼합 요청 계약 — A24 `SUSTAINED-CPU-PAR-CONFIRM-01` 의 상수와 요청열 검증을 그대로 옮긴다.
 * 출처:
 *   feature/arrival-scheduling-20260923 @ d588323
 *     benchmark-runner/src/modelProbe/.../ArrivalEnergyContract.kt (COMMON_NS · DRAIN · BASELINE · COOLING · SETUP · GATE · CALL)
 *     benchmark-runner/src/modelProbe/.../ArrivalPolicyStudy.kt (정책 이름 · validate 의 sustained 분기)
 *     tools/d1_sustained_protocol.py (192 · 짝/홀 · 35,000 + 400·i · 1,500 / 6,000)
 *   d1sim/docs/혼합요청_사전등록_v1.md §1 · §2 · §3 (S26 쪽 값: 블록 · 상주 runtime · 준비 상한 · 정지 규칙)
 * 의미를 바꾸지 않는다. A24 와 다른 값은 "A24 와 다름" 으로 주석에 적는다.
 * v2 (등록 v2 `d1sim/docs/혼합요청_사전등록_v2.md` #1 · #2, 2026-10-09): STEP_MS 400 → 200 · EXPERIMENT_ID -01 → -02 (스모크도). v1 = `03f271a`. 그 밖 무변경.
 * v3 (등록 v3 `d1sim/docs/혼합요청_사전등록_v3.md` §0-1 · §0-2, 2026-10-09): 실험 ID 표 EXPERIMENTS (-02 · -02C · -03 · 각 -SMOKE → 요청 수 · 공통창 · index 범위) ·
 *   COMMON_NS 는 SessionManifest.validate() 가 고른 표 행에서 · WATCHDOG_MS 는 표의 최댓값 · validateRequests 의 요청 수 허용 = 표. v2 = `e2bedf1`. 그 밖 무변경.
 * M6 (등록 `d1sim/docs/M6_동일APK_사전등록_v3.md` §1, 2026-10-12): M6_EXPERIMENTS (P · K) · 블록 M (키 5 · 정책 3 · 준비 상한 = N). M5 = `8bd3d76`. 그 밖 무변경.
 * M7 (등록 `d1sim/docs/M7_확대반복_사전등록_v2.md` 머리 단락, 2026-10-13): 실험 표 index 상한만 — S26-M6-P 11 → 51 · S26-M6-K 3 → 18 ·
 *   S26-MIXREQ-03 15 → 27 (M7 행 = M6Plan.ORDER 12..51 · S 16..27). M6 = `4f87d15` (APK 6a4da1ac…). 그 밖 무변경 (요청 수 · 창 · watchdog · 유도식 같음).
 */
object MixreqContract {
    const val PROTOCOL = "s26-mixreq-session-v1"
    const val EXPERIMENT_ID = "S26-MIXREQ-02"
    const val SMOKE_EXPERIMENT_ID = "S26-MIXREQ-02-SMOKE"
    const val SPLIT_CONFIRMATION = "confirmation"
    const val SPLIT_DIAGNOSTIC = "diagnostic"

    /** 등록 v3 §0-2 실험 ID 표 (앱 · 호스트 같은 표). 스모크 ID 는 같은 실험의 공통창을 쓰고 요청 수는 SMOKE_REQUEST_COUNT. 간격은 전부 STEP_MS. */
    data class ExperimentSpec(val id: String, val smokeId: String, val requestCount: Int, val commonS: Long, val sessionIndexMax: Int, val watchdogMs: Long)
    val EXPERIMENTS = listOf(
        ExperimentSpec("S26-MIXREQ-02", "S26-MIXREQ-02-SMOKE", 192, 120L, 15, 600_000L),
        ExperimentSpec("S26-MIXREQ-02C", "S26-MIXREQ-02C-SMOKE", 192, 120L, 15, 600_000L),
        // (S) 지속: 3,000 요청 (35.0 ~ 634.8 s) · 공통창 720 s · watchdog = 준비 180 + 게이트 60 + 기준 30 + 창 720 + drain 30 + 냉각 60 = 1,080 → 여유 1,260 s
        // M7: index 상한 15 → 27 (R4 (S) 0..15 · M7 S 16..27, 등록 M7 v2 §4-4). 그 밖 같음.
        ExperimentSpec("S26-MIXREQ-03", "S26-MIXREQ-03-SMOKE", 3_000, 720L, 27, 1_260_000L),
    )

    /**
     * M5 (2026-10-12, d1sim/docs/상태분리_사전등록_v2.md · 지속감속_확인_사전등록_v1.md): 위 표 밖의 실험 2개. EXPERIMENTS 는 그대로
     * (WATCHDOG_MS · validateRequests 의 허용 수는 EXPERIMENTS 만 본다 — ABBA 3,000 · 1,260 s 는 -03 과 같은 값).
     * STATESPLIT 요청열은 짝/홀 꼴이 아니라 StatesplitPlan 이 유도 · 검증한다.
     */
    const val STATESPLIT_EXPERIMENT_ID = "S26-STATESPLIT-01"
    const val STATESPLIT_SMOKE_EXPERIMENT_ID = "S26-STATESPLIT-01-SMOKE"
    val M5_EXPERIMENTS = listOf(
        ExperimentSpec(STATESPLIT_EXPERIMENT_ID, STATESPLIT_SMOKE_EXPERIMENT_ID, 522, 120L, 11, 600_000L),
        ExperimentSpec("S26-SUSTAIN-ABBA-01", "S26-SUSTAIN-ABBA-01-SMOKE", 3_000, 720L, 3, 1_260_000L),
    )

    fun isStatesplit(experimentId: String): Boolean =
        experimentId == STATESPLIT_EXPERIMENT_ID || experimentId == STATESPLIT_SMOKE_EXPERIMENT_ID

    /**
     * M6 (2026-10-12, d1sim/docs/M6_동일APK_사전등록_v3.md §1 · §3 · §4): 위 두 표 밖의 실험 2개. EXPERIMENTS 는 그대로
     * (WATCHDOG_MS 1,260 s ≥ K 명목 180 + 60 + 30 + 780 + 30 + 60 = 1,140 s).
     *   S26-M6-P: 정책 대응 · 요청 100 (부하 L / B, M6Plan 이 index 로 유도) · 공통창 120 s · index 0..11 (개발 0..5 · 확인 6..11)
     *   S26-M6-K: 냉각 · 요청 0 · 공통창 780 s · index 0..3 (K1 · K2 개발 · K3 · K4 확인)
     *   M7 (등록 M7 v2 머리 단락): 같은 두 실험에 index 만 더함 — P 12..51 (M6Plan.ORDER 의 M7 행) · K 4..18 (세트 1~5 × 조건 자리). 0..11 · 0..3 은 M6 그대로.
     * 스모크 ID 는 본과 같은 요청 수 · 공통창. 두 실험 모두 블록 M 만.
     * S26-M6-E (게이지 진단) 는 세션이 아니라 GaugeDiagActivity 의 실행 ID 다 (세션 표에 넣지 않는다).
     */
    const val M6_P_EXPERIMENT_ID = "S26-M6-P"
    const val M6_P_SMOKE_EXPERIMENT_ID = "S26-M6-P-SMOKE"
    const val M6_K_EXPERIMENT_ID = "S26-M6-K"
    const val M6_K_SMOKE_EXPERIMENT_ID = "S26-M6-K-SMOKE"
    const val M6_E_EXPERIMENT_ID = "S26-M6-E"
    const val M6_E_SMOKE_EXPERIMENT_ID = "S26-M6-E-SMOKE"
    val M6_EXPERIMENTS = listOf(
        ExperimentSpec(M6_P_EXPERIMENT_ID, M6_P_SMOKE_EXPERIMENT_ID, 100, 120L, 51, 600_000L),   // M7: 11 → 51
        ExperimentSpec(M6_K_EXPERIMENT_ID, M6_K_SMOKE_EXPERIMENT_ID, 0, 780L, 18, 1_260_000L),   // M7: 3 → 18
    )

    fun isM6(experimentId: String): Boolean = M6_EXPERIMENTS.any { it.id == experimentId || it.smokeId == experimentId }

    fun experimentOf(experimentId: String): ExperimentSpec =
        (EXPERIMENTS + M5_EXPERIMENTS + M6_EXPERIMENTS).firstOrNull { it.id == experimentId || it.smokeId == experimentId } ?: error("unknown experiment_id $experimentId")

    /** SessionManifest.validate() 가 정한다 (한 프로세스 = 한 세션 = 실험 하나). 엔진은 COMMON_NS 를 이 표 행에서 읽는다. */
    @Volatile var activeExperiment: ExperimentSpec = EXPERIMENTS[0]

    const val REQUEST_COUNT = 192
    const val SMOKE_REQUEST_COUNT = 24
    const val FIRST_OFFSET_MS = 35_000L
    const val STEP_MS = 200L
    const val URGENT_DEADLINE_MS = 1_500L
    const val NORMAL_DEADLINE_MS = 6_000L

    // A24 ArrivalEnergyContract (같은 값)
    /** v3: 실험 ID 표의 공통창 (-02 · -02C 120 s = A24 값 · -03 720 s). 값은 SessionManifest.validate() 가 고른 표 행. */
    val COMMON_NS: Long get() = activeExperiment.commonS * 1_000_000_000L
    const val DRAIN_SECONDS = 30L
    const val BASELINE_SECONDS = 30L
    const val COOLING_SECONDS = 60L
    const val GATE_NS = 60_000_000_000L
    const val CALL_NS = 30_000_000_000L
    const val SETUP_NS_BLOCK_A = 150_000_000_000L
    /** A24 와 다름: 블록 N 은 상주 runtime 5 (NPU 추가) 라 준비 상한 180 s (등록 §3-2). */
    const val SETUP_NS_BLOCK_N = 180_000_000_000L
    /** A24 와 다름: A24 480 s (준비 150). 블록 N 준비 180 s + 게이트 60 + 기준 30 + 공통창 120 + drain 30 + 냉각 60 = 480 → 여유 600 s. */
    /** v3: Activity 가 manifest 를 읽기 전에 거는 값이라 실험 ID 표의 최댓값 (-03 1,260 s). 세션별 상한은 호스트 (mixreq_session.py) 가 실험 ID 로 건다. */
    val WATCHDOG_MS: Long get() = EXPERIMENTS.maxOf { it.watchdogMs }
    const val SAMPLE_PERIOD_MS = 900L
    const val WARMUPS_PER_KEY = 2

    const val POLICY_CPU = "CPU_URGENT_ONLINE_V1"
    const val POLICY_PAR = "B2_PARALLEL_ONLINE_V1"
    /** S26 전용 (등록 §2): 분류 → NPU lane (AOT) · 탐지 → CPU lane. 나머지는 PAR 과 같다. */
    const val POLICY_PAR_NPU = "S26_NPU_PARALLEL_V1"
    val POLICIES = setOf(POLICY_CPU, POLICY_PAR, POLICY_PAR_NPU)

    const val BLOCK_A = "A"
    const val BLOCK_N = "N"
    /** M6 등록 v3 §1-1 · §3-1: 세 규칙 모두 같은 준비 — 키 = 블록 N 의 5개 · 정책 3개 · 준비 상한 = 블록 N 값. */
    const val BLOCK_M = "M"
    val KEYS_BLOCK_A = setOf("classification_CPU", "classification_GPU", "detection_CPU", "detection_GPU")
    val KEYS_BLOCK_N = KEYS_BLOCK_A + "classification_NPU"
    val KEYS_BLOCK_M = KEYS_BLOCK_N
    val LANES = listOf("CPU", "GPU", "NPU")

    const val CANONICAL_INPUT_CONTRACT = "canonical-srgb-png-v2"
    const val ADAPTER_CONTRACT = "explicit-image-task-v2"
    const val ADAPTER_PORT = "s26-request-runner-compiledmodel-v1"
    const val ENGINE = "litert-compiled-model"
    const val LITERT_VERSION = "2.2.0"
    /** logcat 태그. 호스트가 러너 PID 와 위임 증거 구간을 이것으로 자른다 (등록 §4-7). */
    const val LOG_TAG = "D1MIX"

    data class Request(
        val id: String,
        val ordinal: Int,
        val task: String,
        val priority: String,
        val offsetMs: Long,
        val deadlineMs: Long,
    )

    fun keysOf(block: String): Set<String> = when (block) {
        BLOCK_A -> KEYS_BLOCK_A
        BLOCK_N -> KEYS_BLOCK_N
        BLOCK_M -> KEYS_BLOCK_M
        else -> error("unknown block $block")
    }

    fun policiesOf(block: String): Set<String> = when (block) {
        BLOCK_A -> setOf(POLICY_CPU, POLICY_PAR)
        BLOCK_N -> setOf(POLICY_CPU, POLICY_PAR_NPU)
        BLOCK_M -> setOf(POLICY_CPU, POLICY_PAR, POLICY_PAR_NPU)
        else -> error("unknown block $block")
    }

    fun setupNsOf(block: String): Long = if (block == BLOCK_N || block == BLOCK_M) SETUP_NS_BLOCK_N else SETUP_NS_BLOCK_A

    /** "classification_GPU" -> "GPU". lane 이름 = runtime 키의 마지막 토큰. */
    fun laneOf(key: String): String = key.substringAfterLast('_').also { require(it in LANES) { "unknown lane in $key" } }

    fun taskOf(key: String): String = key.substringBeforeLast('_')

    /** 그 정책이 실제로 쓰는 runtime 키 (등록 §2 배정). 상주만 하는 runtime 은 포함하지 않는다. */
    fun usedKeys(policy: String): Set<String> = when (policy) {
        POLICY_CPU -> setOf("classification_CPU", "detection_CPU")
        POLICY_PAR -> setOf("classification_GPU", "detection_CPU")
        POLICY_PAR_NPU -> setOf("classification_NPU", "detection_CPU")
        else -> error("unknown policy $policy")
    }

    /**
     * A24 ArrivalPolicyStudy.validate 의 sustained-confirmation-v1 분기 그대로:
     * 짝수 = 분류 urgent 1,500 ms · 홀수 = 탐지 normal 6,000 ms · offset = 35,000 + 400·i · ID 유일.
     * count 192 = 본 세션 · 24 = 스모크 (앞 24요청 판, 등록 §3-8).
     * v3: count 는 실험 ID 표의 요청 수 (192 · 3,000) 또는 24 (등록 v3 §0-2).
     */
    fun validateRequests(requests: List<Request>, count: Int = REQUEST_COUNT) {
        require(count == SMOKE_REQUEST_COUNT || EXPERIMENTS.any { it.requestCount == count }) { "request count must be in the experiment table (192, 3000) or 24" }
        require(requests.size == count && requests.map { it.id }.toSet().size == count) { "request count/id" }
        requests.forEachIndexed { i, q ->
            val urgent = i % 2 == 0
            require(q.ordinal == i && q.offsetMs == FIRST_OFFSET_MS + i * STEP_MS) { "request $i ordinal/offset" }
            require(q.task == (if (urgent) "classification" else "detection")) { "request $i task" }
            require(q.priority == (if (urgent) "urgent" else "normal")) { "request $i priority" }
            require(q.deadlineMs == (if (urgent) URGENT_DEADLINE_MS else NORMAL_DEADLINE_MS)) { "request $i deadline" }
        }
    }
}
