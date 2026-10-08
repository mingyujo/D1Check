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
 */
object MixreqContract {
    const val PROTOCOL = "s26-mixreq-session-v1"
    const val EXPERIMENT_ID = "S26-MIXREQ-02"
    const val SMOKE_EXPERIMENT_ID = "S26-MIXREQ-02-SMOKE"
    const val SPLIT_CONFIRMATION = "confirmation"
    const val SPLIT_DIAGNOSTIC = "diagnostic"

    const val REQUEST_COUNT = 192
    const val SMOKE_REQUEST_COUNT = 24
    const val FIRST_OFFSET_MS = 35_000L
    const val STEP_MS = 200L
    const val URGENT_DEADLINE_MS = 1_500L
    const val NORMAL_DEADLINE_MS = 6_000L

    // A24 ArrivalEnergyContract (같은 값)
    const val COMMON_NS = 120_000_000_000L
    const val DRAIN_SECONDS = 30L
    const val BASELINE_SECONDS = 30L
    const val COOLING_SECONDS = 60L
    const val GATE_NS = 60_000_000_000L
    const val CALL_NS = 30_000_000_000L
    const val SETUP_NS_BLOCK_A = 150_000_000_000L
    /** A24 와 다름: 블록 N 은 상주 runtime 5 (NPU 추가) 라 준비 상한 180 s (등록 §3-2). */
    const val SETUP_NS_BLOCK_N = 180_000_000_000L
    /** A24 와 다름: A24 480 s (준비 150). 블록 N 준비 180 s + 게이트 60 + 기준 30 + 공통창 120 + drain 30 + 냉각 60 = 480 → 여유 600 s. */
    const val WATCHDOG_MS = 600_000L
    const val SAMPLE_PERIOD_MS = 900L
    const val WARMUPS_PER_KEY = 2

    const val POLICY_CPU = "CPU_URGENT_ONLINE_V1"
    const val POLICY_PAR = "B2_PARALLEL_ONLINE_V1"
    /** S26 전용 (등록 §2): 분류 → NPU lane (AOT) · 탐지 → CPU lane. 나머지는 PAR 과 같다. */
    const val POLICY_PAR_NPU = "S26_NPU_PARALLEL_V1"
    val POLICIES = setOf(POLICY_CPU, POLICY_PAR, POLICY_PAR_NPU)

    const val BLOCK_A = "A"
    const val BLOCK_N = "N"
    val KEYS_BLOCK_A = setOf("classification_CPU", "classification_GPU", "detection_CPU", "detection_GPU")
    val KEYS_BLOCK_N = KEYS_BLOCK_A + "classification_NPU"
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
        else -> error("unknown block $block")
    }

    fun policiesOf(block: String): Set<String> = when (block) {
        BLOCK_A -> setOf(POLICY_CPU, POLICY_PAR)
        BLOCK_N -> setOf(POLICY_CPU, POLICY_PAR_NPU)
        else -> error("unknown block $block")
    }

    fun setupNsOf(block: String): Long = if (block == BLOCK_N) SETUP_NS_BLOCK_N else SETUP_NS_BLOCK_A

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
     */
    fun validateRequests(requests: List<Request>, count: Int = REQUEST_COUNT) {
        require(count == REQUEST_COUNT || count == SMOKE_REQUEST_COUNT) { "request count must be 192 or 24" }
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
