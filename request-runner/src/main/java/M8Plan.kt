package com.example.d1check.requestrunner

import com.example.d1check.requestrunner.MixreqContract.Request
import java.util.UUID

/**
 * M8 요청표 · 실험 행 — d1sim/docs/M8_계약표_v2.md §0 · §1 · §2 · s26/results/m8_prep/contract_v2/{banks_m8,policies_m8}.json (2026-10-15 · 조민규 답 10/14 §3 + 10/15 01:5x 8항목).
 *   bank: L64 (C32/D32 교대 · 35 s 부터 1 s) · C252 (분류 252 · 333.2 ms) · M128 (C96/D32 · 8건 × 16 묶음 CCCDCCCD · 같은 시각 8건 · 묶음 간격 537.155 ms = 537,155,000 ns) ·
 *         SMOOTH128 (M128 과 같은 128건 · arrival_ns = 35,000,000,000 + floor(i × 15 × 537,155,000 / 127) · 첫 35.000 s · 마지막 43.057325 s · 절대기한 = 새 예정 도착 + C 0.8 s / D 2 s).
 *   시각 = ns 정수 (offset_ns · 조민규 #4) · offset_us = floor(ns / 1,000) · offset_ms = floor(us / 1,000) (표시용) · 기한 C 800 ms / D 2,000 ms (예정 도착부터) · jitter 0.
 *   ID: 새 계보 네임스페이스 M8_NS = uuid5(NAMESPACE_URL, "S26-M8-lineage-v1") · session = uuid5(M8_NS, "<실험 ID>/<index>") · request = uuid5(M8_NS, "<sid>/<ordinal>").
 *   실험 행: 실험 ID 마다 군 (arm) 목록 · index → arm = index % 군 수 · 반복 = index / 군 수 · DEV = index < (상한+1)/2 · CONFIRM = 나머지 (session/request ID 분리).
 *   정책 7 (FIFO/EDD × SERIAL/PAIR × CPU/CG/CN · WAIT 인자 = wait_ms · first_n_bursts · nominal_total_ms) · 블록 M (상주 5) 또는 NONE (runtime 0 · S26-M8-IDLE 만) · 준비 role (RECENT: CPU60 / IDLE60).
 * 호스트 s26/tools/mixreq/m8_common.py 가 같은 식으로 만들고, 앱은 manifest 의 표 · 정책 · 인자 · 준비가 이 식과 같은지 다시 확인한다 (fail closed).
 * 기존 M6/M7 행 (M6Plan · RequestPlan.requests · MixreqContract.validateRequests) 은 바꾸지 않는다.
 */
object M8Plan {
    val M8_NS: UUID = Uuid5.uuid5(Uuid5.NAMESPACE_URL, "S26-M8-lineage-v1")
    const val FIRST_OFFSET_US = 35_000_000L
    const val FIRST_OFFSET_NS = 35_000_000_000L
    const val URGENT_DEADLINE_MS = 800L
    const val NORMAL_DEADLINE_MS = 2_000L
    const val BURST_INTERVAL_US = 537_155L           // 조민규 값 (bank 고정) — burstIntervalUs(BURST_C_GPU_MEAN_MS, BURST_D_CPU_MEAN_MS) == 이 값 (M8PlanTest · burst_interval_recalc_v2.json)
    const val BURST_INTERVAL_NS = 537_155_000L
    const val BURST_COUNT = 16
    const val BURST_SIZE = 8
    const val BURST_PATTERN = "CCCDCCCD"
    /** 조민규 01:5x #3: 기존 동결 프로필 (SHA 아래 · 이쪽에 파일 없음 [D]) 의 평균 AVAILABLE — 합성 입력용 평균 기반 수치 · 새 M8 실측 성능 · 실제 이용률 90 % 보장 아님. */
    const val BURST_PROFILE_SHA256 = "bd8d55c14e531e8629c5fcc84289f167f7e69cee3e7cc9dd761a25f345d4cc39"
    const val BURST_C_GPU_MEAN_MS = 73.54419138
    const val BURST_D_CPU_MEAN_MS = 241.71965499333334
    const val BURST_INTERVAL_RAW_MS = 537.154788874      // 8 × max(96·C, 32·D) / (128 × 0.9) 올림 전 (조민규 537.154788874…)
    const val PREP_S = 60L
    const val PREP_GAP_S = 5L
    const val DEV_SEED = 20261014L
    const val CONFIRM_SEED = 20261022L

    enum class Bank(val count: Int) { L64(64), C252(252), M128(128), SMOOTH128(128), NONE(0) }
    enum class Prep { NONE, CPU60, IDLE60 }

    /**
     * WAIT 인자 (조민규 01:5x #2): 정책 ID 하나 (FIFO_WAIT_CG_V1) + manifest policy_args. nominal_total_ms = wait_ms × first_n_bursts (명목량 · 잘라 쓰는 상한이 아님 · 실제 dose 는 엔진이 따로 기록).
     * 묶음별 최초 eligible head 에서 한 번만 wait_ms · 그 뒤 묶음 (k ≥ first_n) 은 WAIT 0 · 타이머 중 도착 = enqueue 만.
     */
    data class WaitArgs(val waitMs: Long, val firstNBursts: Int, val nominalTotalMs: Long) {
        init { require(waitMs > 0 && firstNBursts > 0 && nominalTotalMs == waitMs * firstNBursts) { "wait args: nominal_total_ms must equal wait_ms × first_n_bursts" } }
        fun record(): Map<String, Any?> = linkedMapOf("wait_ms" to waitMs, "first_n_bursts" to firstNBursts, "nominal_total_ms" to nominalTotalMs)
    }

    /** 한 군 (arm): bank · 정책 · (WAIT 인자) · 블록 · 준비. */
    data class Arm(val name: String, val bank: Bank, val policy: String, val block: String = MixreqContract.BLOCK_M, val wait: WaitArgs? = null, val prep: Prep = Prep.NONE)

    val WAIT200X16 = WaitArgs(200, 16, 3_200)      // 핵심: 200 ms × 앞 16 묶음 · 명목 3.2 s
    val WAIT200X12 = WaitArgs(200, 12, 2_400)      // P2 대조: 200 ms × 앞 12 묶음 · 명목 2.4 s
    val WAIT1000X12 = WaitArgs(1_000, 12, 12_000)  // P2 긴 대기: 1,000 ms × 같은 앞 12 묶음 · 명목 12 s

    private val C = MixreqContract
    val ARMS: Map<String, List<Arm>> = mapOf(
        C.M8_FN_ID to listOf(
            Arm("C252_CPU", Bank.C252, C.POLICY_FIFO_SERIAL_CPU), Arm("C252_GPU", Bank.C252, C.POLICY_FIFO_SERIAL_CG), Arm("C252_NPU", Bank.C252, C.POLICY_FIFO_SERIAL_CN),
            Arm("M128_BASE", Bank.M128, C.POLICY_FIFO_SERIAL_CG), Arm("M128_PAIR_G", Bank.M128, C.POLICY_FIFO_PAIR_CG), Arm("M128_PAIR_N", Bank.M128, C.POLICY_FIFO_PAIR_CN),
        ),
        C.M8_L64_ID to listOf(Arm("L64_BASE", Bank.L64, C.POLICY_FIFO_SERIAL_CG), Arm("L64_PAIR_G", Bank.L64, C.POLICY_FIFO_PAIR_CG)),
        C.M8_C252_ID to listOf(Arm("C252_CPU", Bank.C252, C.POLICY_FIFO_SERIAL_CPU), Arm("C252_GPU", Bank.C252, C.POLICY_FIFO_SERIAL_CG), Arm("C252_NPU", Bank.C252, C.POLICY_FIFO_SERIAL_CN)),
        C.M8_M128_ID to listOf(
            Arm("M128_BASE", Bank.M128, C.POLICY_FIFO_SERIAL_CG), Arm("M128_ORDER", Bank.M128, C.POLICY_EDD_SERIAL_CG), Arm("M128_PAIR_G", Bank.M128, C.POLICY_FIFO_PAIR_CG),
            Arm("M128_WAIT200x16", Bank.M128, C.POLICY_FIFO_WAIT_CG, wait = WAIT200X16), Arm("M128_NPU_SERIAL", Bank.M128, C.POLICY_FIFO_SERIAL_CN),
            Arm("M128_PAIR_N", Bank.M128, C.POLICY_FIFO_PAIR_CN), Arm("M128_WAIT200x12", Bank.M128, C.POLICY_FIFO_WAIT_CG, wait = WAIT200X12),
            Arm("M128_WAIT1000x12", Bank.M128, C.POLICY_FIFO_WAIT_CG, wait = WAIT1000X12),
        ),
        C.M8_S128_ID to listOf(Arm("SMOOTH128_BASE", Bank.SMOOTH128, C.POLICY_FIFO_SERIAL_CG), Arm("SMOOTH128_ORDER", Bank.SMOOTH128, C.POLICY_EDD_SERIAL_CG), Arm("SMOOTH128_PAIR_G", Bank.SMOOTH128, C.POLICY_FIFO_PAIR_CG)),
        C.M8_RECENT_ID to listOf(
            Arm("RECENT_CPU60_C252_CPU", Bank.C252, C.POLICY_FIFO_SERIAL_CPU, prep = Prep.CPU60), Arm("RECENT_CPU60_C252_GPU", Bank.C252, C.POLICY_FIFO_SERIAL_CG, prep = Prep.CPU60),
            Arm("RECENT_CPU60_C252_NPU", Bank.C252, C.POLICY_FIFO_SERIAL_CN, prep = Prep.CPU60), Arm("RECENT_IDLE60_C252_CPU", Bank.C252, C.POLICY_FIFO_SERIAL_CPU, prep = Prep.IDLE60),
            Arm("RECENT_IDLE60_C252_GPU", Bank.C252, C.POLICY_FIFO_SERIAL_CG, prep = Prep.IDLE60), Arm("RECENT_IDLE60_C252_NPU", Bank.C252, C.POLICY_FIFO_SERIAL_CN, prep = Prep.IDLE60),
        ),
        C.M8_IDLE_ID to listOf(Arm("IDLE_NO_RUNTIME", Bank.NONE, C.POLICY_NO_RUNTIME, block = C.BLOCK_NONE), Arm("IDLE_RESIDENT", Bank.NONE, C.POLICY_FIFO_SERIAL_CPU)),
    )

    fun mainId(experimentId: String): String = C.experimentOf(experimentId).id.also { require(C.isM8(experimentId)) { "not an M8 experiment $experimentId" } }
    fun arms(experimentId: String): List<Arm> = ARMS.getValue(mainId(experimentId))
    fun armOf(experimentId: String, index: Int): Arm = arms(experimentId).let { it[index % it.size] }
    fun repetitionOf(experimentId: String, index: Int): Int = index / arms(experimentId).size
    fun devCount(experimentId: String): Int = (C.experimentOf(experimentId).sessionIndexMax + 1) / 2
    fun analysisSplitOf(experimentId: String, index: Int): String = if (index < devCount(experimentId)) "dev" else "confirm"

    fun sessionId(experimentId: String, index: Int): String = Uuid5.uuid5(M8_NS, "$experimentId/$index").toString()
    fun requestId(sid: String, ordinal: Int): String = Uuid5.uuid5(M8_NS, "$sid/$ordinal").toString()

    /** 묶음 간격 식 (banks_m8.json · 조민규 #3): 8 × max(96·s_CGPU, 32·s_DCPU) / (128 × 0.9) (ms · 올림 전) · s = 동결 프로필 평균 AVAILABLE (ms). */
    fun burstIntervalRawMs(sCgpuMs: Double, sDcpuMs: Double): Double = 8.0 * maxOf(96.0 * sCgpuMs, 32.0 * sDcpuMs) / (128.0 * 0.9)

    /** 1 µs 올림 (µs). */
    fun burstIntervalUs(sCgpuMs: Double, sDcpuMs: Double): Long = Math.ceil(burstIntervalRawMs(sCgpuMs, sDcpuMs) * 1000.0).toLong()
    fun burstIntervalNs(sCgpuMs: Double, sDcpuMs: Double): Long = burstIntervalUs(sCgpuMs, sDcpuMs) * 1_000L

    /** (task, offset_ns) 슬롯 — ordinal 순서 (조민규 #4: 정수 ns 식). */
    fun slotsNs(bank: Bank): List<Pair<String, Long>> = when (bank) {
        Bank.L64 -> List(64) { i -> (if (i % 2 == 0) "classification" else "detection") to (FIRST_OFFSET_NS + 1_000_000_000L * i) }
        Bank.C252 -> List(252) { i -> "classification" to (FIRST_OFFSET_NS + 333_200_000L * i) }
        Bank.M128 -> List(BURST_COUNT * BURST_SIZE) { i ->
            val k = i / BURST_SIZE
            val j = i % BURST_SIZE
            (if (BURST_PATTERN[j] == 'C') "classification" else "detection") to (FIRST_OFFSET_NS + BURST_INTERVAL_NS * k)
        }
        Bank.SMOOTH128 -> slotsNs(Bank.M128).mapIndexed { i, (task, _) -> task to (FIRST_OFFSET_NS + i.toLong() * 15L * BURST_INTERVAL_NS / 127L) }   // floor (정수 나눗셈 · 음수 없음)
        Bank.NONE -> emptyList()
    }

    /** (task, offset_us) = floor(ns / 1,000) — 표시 · 호스트 µs 열과 대조용. */
    fun slots(bank: Bank): List<Pair<String, Long>> = slotsNs(bank).map { (t, ns) -> t to ns / 1_000L }

    fun bankRequests(sid: String, bank: Bank): List<Request> = slotsNs(bank).mapIndexed { ordinal, (task, offsetNs) ->
        val urgent = task == "classification"
        Request(
            id = requestId(sid, ordinal), ordinal = ordinal, task = task, priority = if (urgent) "urgent" else "normal",
            offsetMs = offsetNs / 1_000_000L, deadlineMs = if (urgent) URGENT_DEADLINE_MS else NORMAL_DEADLINE_MS, offsetUs = offsetNs / 1_000L, offsetNs = offsetNs,
        )
    }.also { validateBank(it, bank) }

    fun requests(experimentId: String, index: Int, sid: String): List<Request> = bankRequests(sid, armOf(experimentId, index).bank)

    /** 요청 수 · ID 유일 · ordinal 순서 · (task, offset_ns) 가 bank 식과 같음 · offset 단조 비감소 (M128 은 같은 시각 8건) · offset_us/ms = floor · 우선순위 · 상대기한 (절대기한은 엔진이 새 예정 도착 + 상대기한으로 계산). */
    fun validateBank(requests: List<Request>, bank: Bank) {
        val expected = slotsNs(bank)
        require(requests.size == bank.count && requests.map { it.id }.toSet().size == bank.count) { "m8 request count/id ($bank)" }
        require(expected.map { it.second }.zipWithNext().all { (a, b) -> a <= b }) { "m8 offsets must not decrease" }
        requests.forEachIndexed { i, q ->
            val urgent = q.task == "classification"
            require(q.ordinal == i && q.task == expected[i].first && q.offsetNs == expected[i].second) { "m8 request $i task/offset_ns" }
            require(q.offsetUs == q.offsetNs / 1_000L) { "m8 request $i offset_us must be floor(offset_ns / 1000)" }
            require(q.offsetMs == q.offsetUs / 1_000L) { "m8 request $i offset_ms must be floor(offset_us / 1000)" }
            require(q.priority == (if (urgent) "urgent" else "normal")) { "m8 request $i priority" }
            require(q.deadlineMs == (if (urgent) URGENT_DEADLINE_MS else NORMAL_DEADLINE_MS)) { "m8 request $i deadline" }
        }
    }

    /** SessionManifest.validate 의 M8 분기: 행 (index) 이 정한 블록 · 정책 · WAIT 인자 · 준비 · 요청표와 같은지 (fail closed). */
    fun validateSession(experimentId: String, index: Int, block: String, policy: String, wait: WaitArgs?, prep: Prep, requests: List<Request>) {
        val spec = C.experimentOf(experimentId)
        require(index in 0..spec.sessionIndexMax) { "m8 index $index out of 0..${spec.sessionIndexMax} ($experimentId)" }
        val arm = armOf(experimentId, index)
        require(block == arm.block) { "m8 index $index (${arm.name}) runs in block ${arm.block}, manifest block $block" }
        require(policy == arm.policy) { "m8 index $index is ${arm.name} (policy ${arm.policy}), manifest policy $policy" }
        require(wait == arm.wait) { "m8 index $index wait args ${arm.wait?.record()} != manifest ${wait?.record()}" }
        require((policy == C.POLICY_FIFO_WAIT_CG) == (wait != null)) { "WAIT policy needs policy_args; other policies must not carry them" }
        require(prep == arm.prep) { "m8 index $index prep ${arm.prep} != manifest $prep" }
        validateBank(requests, arm.bank)
    }

    /** 묶음 index (WAIT 용): 같은 예정 도착 (ns) = 같은 묶음 · 도착 시각 오름차순 번호. */
    fun burstIndexOf(requests: List<Request>): Map<String, Int> {
        val times = requests.map { it.offsetNs }.distinct().sorted()
        val of = times.withIndex().associate { (k, t) -> t to k }
        return requests.associate { it.id to of.getValue(it.offsetNs) }
    }
}
