package com.example.d1check.requestrunner

/*
 * 출처: feature/arrival-scheduling-20260923 @ d588323
 *   benchmark-runner/src/modelProbe/java/com/example/d1check/benchmarkrunner/ArrivalPolicyStudy.kt 50~62행 (choose)
 *   benchmark-runner/src/modelProbe/java/com/example/d1check/benchmarkrunner/ArrivalPolicy.kt 10~11행 (Ticket · Choice)
 * 바꾼 것: lane 에 NPU 를 추가하고 정책 S26_NPU_PARALLEL_V1 (분류 → NPU · 탐지 → CPU) 을 넣었다 (등록 §2).
 * CPU · PAR 의 선택 규칙은 원문 그대로다: 비선점 · 큐에 든 것만 · urgent 먼저 → ordinal → id ·
 * CPU 정책은 CPU · GPU lane 이 둘 다 비었을 때만 고른다 (사실상 CPU lane 하나 직렬).
 */
object PolicyStudy {
    const val REASON = "online_arrived_priority_then_ordinal"

    data class Ticket(val id: String, val task: String, val priority: String, val ordinal: Int)
    data class Choice(val ticket: Ticket, val backend: String, val reason: String)

    fun choose(
        policy: String,
        waiting: List<Ticket>,
        freeCpu: Boolean,
        freeGpu: Boolean,
        freeNpu: Boolean = true,
    ): Choice? {
        require(policy in MixreqContract.POLICIES) { "unknown policy $policy" }
        // A24: if ((policy == CPU || policy == SERIAL) && (!freeCpu || !freeGpu)) return null
        if (policy == MixreqContract.POLICY_CPU && (!freeCpu || !freeGpu)) return null
        val ordered = waiting.sortedWith(
            compareBy<Ticket> { it.priority != "urgent" }.thenBy { it.ordinal }.thenBy { it.id },
        )
        for (q in ordered) {
            val lane = laneFor(policy, q.task)
            val free = when (lane) {
                "CPU" -> freeCpu
                "GPU" -> freeGpu
                else -> freeNpu
            }
            if (free) return Choice(q, lane, REASON)
        }
        return null
    }

    /** 등록 §2 배정: CPU 정책 → 전부 CPU · PAR → 분류 GPU / 탐지 CPU · PAR-NPU → 분류 NPU / 탐지 CPU. */
    fun laneFor(policy: String, task: String): String = when {
        policy == MixreqContract.POLICY_CPU || task == "detection" -> "CPU"
        policy == MixreqContract.POLICY_PAR -> "GPU"
        policy == MixreqContract.POLICY_PAR_NPU -> "NPU"
        else -> error("unknown policy $policy")
    }

    // ------------------------------------------------------------------ M8 (2026-10-14 · s26/results/m8_prep/contract/policies_m8.json · 계약표 v1 §1)
    // 기존 choose() · laneFor() 는 한 줄도 바꾸지 않는다. M8 행 (SessionEngineM8) 만 아래를 쓴다.
    const val REASON_M8_FIFO = "m8_fifo_strict_head"
    const val REASON_M8_EDD = "m8_edd_strict_head"

    /** M8 ready 요청 (도착한 것만). scheduledArrivalNs · deadlineNs = 절대 시각 (같은 시계). */
    data class TicketM8(val id: String, val task: String, val priority: String, val ordinal: Int, val scheduledArrivalNs: Long, val deadlineNs: Long)
    data class ChoiceM8(val ticket: TicketM8, val backend: String, val key: String, val reason: String)

    fun selectionOf(policy: String): String = when (policy) {
        MixreqContract.POLICY_EDD_SERIAL_CG -> "EDD"
        in MixreqContract.M8_POLICIES -> "FIFO"
        else -> error("unknown M8 policy $policy")
    }

    fun concurrencyOf(policy: String): String = when (policy) {
        MixreqContract.POLICY_FIFO_PAIR_CG, MixreqContract.POLICY_FIFO_PAIR_CN -> "PAIR"
        in MixreqContract.M8_POLICIES -> "SERIAL"
        else -> error("unknown M8 policy $policy")
    }

    /** 허용 병행 조합 (PAIR 만): 그 정책이 쓰는 두 runtime 키. SERIAL 은 null. */
    fun allowedPairOf(policy: String): Set<String>? = if (concurrencyOf(policy) == "PAIR") MixreqContract.usedKeysM8(policy) else null

    /** policies_m8.json route: C → 정책의 분류 lane · D → CPU. */
    fun laneForM8(policy: String, task: String): String = when {
        task == "detection" -> "CPU"
        policy == MixreqContract.POLICY_FIFO_SERIAL_CPU -> "CPU"
        policy == MixreqContract.POLICY_FIFO_SERIAL_CN || policy == MixreqContract.POLICY_FIFO_PAIR_CN -> "NPU"
        policy in MixreqContract.M8_POLICIES -> "GPU"
        else -> error("unknown M8 policy $policy")
    }

    /** FIFO = (예정 도착 → ordinal → id) · EDD = (절대기한 → 예정 도착 → ordinal → id). head 하나만 본다. */
    fun orderedM8(policy: String, waiting: List<TicketM8>): List<TicketM8> = when (selectionOf(policy)) {
        "EDD" -> waiting.sortedWith(compareBy<TicketM8> { it.deadlineNs }.thenBy { it.scheduledArrivalNs }.thenBy { it.ordinal }.thenBy { it.id })
        else -> waiting.sortedWith(compareBy<TicketM8> { it.scheduledArrivalNs }.thenBy { it.ordinal }.thenBy { it.id })
    }

    /**
     * M8 선택: strict head (head 의 lane 이 busy 면 null · 추월 없음) · SERIAL = running 이 하나라도 있으면 null · PAIR = running ∪ {후보} ⊆ 허용 조합 · |running| < 2 · 같은 lane 1 ·
     * 서비스 120 s 경계 (nowNs ≥ windowEndNs) 뒤엔 null. running = 지금 dispatch 된 뒤 lane_available 전인 runtime 키 (실제 시각으로 유지하는 집합).
     */
    fun chooseM8(policy: String, waiting: List<TicketM8>, running: Collection<String>, nowNs: Long, windowEndNs: Long): ChoiceM8? {
        require(policy in MixreqContract.M8_POLICIES) { "unknown M8 policy $policy" }
        if (nowNs >= windowEndNs || waiting.isEmpty()) return null
        val head = orderedM8(policy, waiting).first()
        val lane = laneForM8(policy, head.task)
        val key = "${head.task}_$lane"
        if (running.any { MixreqContract.laneOf(it) == lane }) return null
        when (concurrencyOf(policy)) {
            "SERIAL" -> if (running.isNotEmpty()) return null
            "PAIR" -> {
                val allowed = allowedPairOf(policy)!!
                if (running.size >= 2 || key !in allowed || running.any { it !in allowed }) return null
            }
        }
        return ChoiceM8(head, lane, key, if (selectionOf(policy) == "EDD") REASON_M8_EDD else REASON_M8_FIFO)
    }

    /**
     * WAIT (policies_m8.json wait_rules): 묶음 k 의 첫 dispatch 직전에만 · ready head 있음 ∧ running 0 (관련 owner 전부 실제 AVAILABLE) ∧ k < first_n ∧ 그 묶음 처음 ∧ 누적 < cap.
     * 반환 = 계획 dose ms (cap 에 걸리면 남은 cap 만큼) · null = 의도 WAIT 아님 (busy · 요청 없음 · n 밖 · 같은 묶음 두 번째 · cap 소진).
     */
    fun plannedWaitMs(args: M8Plan.WaitArgs, burstIndex: Int, burstsWaited: Set<Int>, cumulativeMs: Long, runningCount: Int, hasReadyHead: Boolean): Long? {
        // v2 (조민규 01:5x #2): 묶음 k 의 최초 eligible head (ready head ∧ running 0) 에서 한 번만 wait_ms · k ≥ first_n 또는 같은 묶음 두 번째 = WAIT 0 (null).
        // nominal_total_ms = wait_ms × first_n 은 명목량 (잘라 쓰는 상한이 아님) · 누적 계획은 구조상 명목을 넘지 않는다 (검산) · 실제 dose/잘림/초과는 엔진이 따로 기록.
        if (!hasReadyHead || runningCount > 0 || burstIndex >= args.firstNBursts || burstIndex in burstsWaited) return null
        check(cumulativeMs + args.waitMs <= args.nominalTotalMs) { "WAIT cumulative planned ${cumulativeMs + args.waitMs} > nominal_total_ms ${args.nominalTotalMs}" }
        return args.waitMs
    }
}
