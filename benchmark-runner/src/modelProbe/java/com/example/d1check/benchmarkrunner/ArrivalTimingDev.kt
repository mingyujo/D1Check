package com.example.d1check.benchmarkrunner

/** Development-only causal snapshots. No Android, file IO, or future outcomes in the policy. */
internal object ArrivalTimingDev {
    const val PROTOCOL = "arrival-timing-dev-v1"
    const val POLICY = "CONDITIONAL_TIMING_DEV_1"
    const val ESTIMATE_CONTRACT = "arrival-phase-budgets-v1"
    const val CALIBRATION_PROTOCOL = "arrival-timing-calibration-v1"
    const val CALIBRATION_POLICY = "CALIBRATION_FIXED_BACKEND_1"
    fun unfinishedWithArrival(planned: Map<String, Any?>, arrival: Map<String, Any?>?): Map<String, Any?> {
        // Arrival facts were copied before worker execution; never promote missing event evidence to success.
        require(planned["terminal_status"] == "unfinished")
        require(arrival == null || arrival["request_id"] == planned["request_id"])
        return arrival.orEmpty() + planned
    }
    fun calibrationChoice(queue: List<ArrivalPolicy.Ticket>, lanes: Map<String, Lane>, backend: String): Decision {
        require(backend in setOf("CPU", "GPU"))
        val ticket = ordered(queue).firstOrNull()
        val reason = when {
            ticket == null -> "wait_empty"
            lanes.values.any { it.phase != Phase.AVAILABLE } -> "wait_calibration_solo_busy"
            else -> "calibration_fixed_backend"
        }
        return Decision(if (reason == "calibration_fixed_backend") ArrivalPolicy.Choice(ticket!!, backend, reason) else null,
            reason, emptyList()) // No duration forecasts or adaptive comparisons in calibration.
    }
    /** Host API interval, including an exceptional return; observer work is outside that interval. */
    fun observeInvocation(clock: () -> Long, observer: (Long, Long) -> Unit, invoke: () -> Unit): Pair<Long, Long> {
        val start = clock()
        var end: Long
        try { invoke() } finally { end = clock(); observer(start, end) }
        return Pair(start, end)
    }
    enum class Phase { AVAILABLE, ASSIGNED, EXECUTING, OUTPUT_READY, PERSISTED, WORKER_RELEASED }
    data class Budget(val dispatchToStart: Long?, val service: Long?, val persist: Long?, val release: Long?,
                      val decisionToDispatch: Long? = null) {
        init { listOf(decisionToDispatch, dispatchToStart, service, persist, release).forEach { require(it == null || it in 0..20_000_000_000L) } }
        fun values() = listOf(dispatchToStart, service, persist, release)
        fun wire() = mapOf("decision_to_dispatch_ns" to decisionToDispatch, "dispatch_to_start_ns" to dispatchToStart, "start_to_output_ready_ns" to service,
            "output_ready_to_persist_ns" to persist, "persist_to_lane_available_ns" to release)
    }
    data class Lane(val backend: String, val phase: Phase = Phase.AVAILABLE, val requestId: String? = null,
                    val task: String? = null, val phaseSince: Long = 0, val persistSince: Long? = null)
    data class Remaining(val ns: Long?, val state: String)
    data class Candidate(val id: String, val cpuReply: Long?, val gpuReply: Long?, val reason: String) {
        fun wire() = mapOf("request_id" to id, "cpu_reply_ns" to cpuReply, "gpu_reply_ns" to gpuReply, "reason" to reason)
    }
    data class Decision(val choice: ArrivalPolicy.Choice?, val reason: String, val candidates: List<Candidate>)
    private fun sum(xs: List<Long?>): Long? = if (xs.any { it == null }) null else xs.sumOf { it!! }
    fun remaining(lane: Lane, now: Long, budget: Budget?): Remaining {
        require(lane.phaseSince <= now)
        if (lane.phase == Phase.AVAILABLE) return Remaining(0, "AVAILABLE")
        if (budget == null) return Remaining(null, "UNKNOWN_MISSING_BUDGET")
        val index = when (lane.phase) {
            Phase.ASSIGNED -> 0
            Phase.EXECUTING -> 1
            Phase.OUTPUT_READY -> 2
            else -> 3
        }
        val origin = if (index == 3) lane.persistSince else lane.phaseSince
        val duration = budget.values()[index]
        if (origin == null || duration == null) return Remaining(null, "UNKNOWN_MISSING_BUDGET")
        require(origin <= now)
        val left = duration - (now - origin)
        // Busy is never converted into availability; no invented overrun constant.
        if (left <= 0) return Remaining(null, "UNKNOWN_OVERRUN")
        val total = sum(listOf(left) + budget.values().drop(index + 1))
        return Remaining(total, if (total == null) "UNKNOWN_MISSING_BUDGET" else "ESTIMATED")
    }
    fun ordered(queue: List<ArrivalPolicy.Ticket>) = queue.sortedWith(
        compareBy<ArrivalPolicy.Ticket> { it.priority != "urgent" }.thenBy { it.ordinal }.thenBy { it.id })
    fun decide(queue: List<ArrivalPolicy.Ticket>, lanes: Map<String, Lane>, now: Long,
               budgets: Map<String, Budget>): Decision {
        val cpu = lanes.getValue("CPU"); val gpu = lanes.getValue("GPU")
        val freeCpu = cpu.phase == Phase.AVAILABLE; val freeGpu = gpu.phase == Phase.AVAILABLE
        val residual = remaining(cpu, now, budgets["${cpu.task}_CPU"]).ns
        var ahead: Long? = 0
        var selected: ArrivalPolicy.Choice? = null
        val candidates = ordered(queue).map { ticket ->
            val cb = budgets["${ticket.task}_CPU"]; val gb = budgets["${ticket.task}_GPU"]
            fun reply(b: Budget?) = b?.let { sum(listOf(it.decisionToDispatch) + it.values().take(if (ticket.priority == "urgent") 2 else 3)) }
            val c = sum(listOf(residual, ahead, reply(cb)))
            val g = if (freeGpu) reply(gb) else null
            val reason = when {
                !freeCpu && !freeGpu -> "wait_both_busy"
                c == null || (freeGpu && g == null) -> if (freeCpu) "fallback_cpu_unknown" else "wait_unknown"
                freeCpu && (!freeGpu || c <= g!!) -> "estimated_cpu_reply"
                freeGpu && g!! < c -> "estimated_gpu_reply"
                else -> "wait_estimated_cpu"
            }
            if (selected == null && reason in setOf("fallback_cpu_unknown", "estimated_cpu_reply", "estimated_gpu_reply"))
                selected = ArrivalPolicy.Choice(ticket, if (reason == "estimated_gpu_reply") "GPU" else "CPU", reason)
            ahead = sum(listOf(ahead, cb?.let { sum(listOf(it.decisionToDispatch) + it.values()) }))
            Candidate(ticket.id, c, g, reason)
        }
        return Decision(selected, selected?.reason ?: candidates.firstOrNull()?.reason ?: "wait_empty", candidates)
    }
    fun ticketWire(t: ArrivalPolicy.Ticket) = mapOf("id" to t.id, "task" to t.task, "priority" to t.priority, "ordinal" to t.ordinal)

    /** One short monitor serializes worker observations and immutable decision inputs. No disk IO here. */
    class Recorder(private val clock: () -> Long, budgets: Map<String, Budget>, val version: String,
                   val provenance: String, private val capacity: Int = 512, private val calibrationBackend: String? = null) {
        val budgets = budgets.toMap()
        private val lanes = mutableMapOf("CPU" to Lane("CPU"), "GPU" to Lane("GPU"))
        private val records = mutableListOf<Map<String, Any?>>()
        @Volatile var overflow = false; private set
        private var dropped = 0
        init {
            require(capacity > 0 && version.isNotBlank() && provenance.isNotBlank())
            require(calibrationBackend == null || calibrationBackend in setOf("CPU", "GPU") &&
                budgets.values.all { it.values().all { value -> value == null } && it.decisionToDispatch == null })
        }
        @Synchronized fun isIdle(observedAt: Long? = null) = lanes.values.all {
            it.phase == Phase.AVAILABLE && (observedAt == null || it.phaseSince <= observedAt)
        }
        private fun append(value: Map<String, Any?>) {
            if (records.size >= capacity) { overflow = true; dropped++; return }
            records.add(value + ("seq" to records.size))
        }
        @Synchronized fun mark(backend: String, ticket: ArrivalPolicy.Ticket, phase: Phase): Long {
            val old = lanes.getValue(backend)
            check(if (phase == Phase.ASSIGNED) old.phase == Phase.AVAILABLE else old.requestId == ticket.id)
            check(phase == Phase.ASSIGNED || phase == Phase.WORKER_RELEASED ||
                phase == Phase.AVAILABLE && old.phase == Phase.WORKER_RELEASED || phase.ordinal == old.phase.ordinal + 1)
            val time = clock()
            check(time >= old.phaseSince)
            val lane = Lane(backend, phase, if (phase == Phase.AVAILABLE) null else ticket.id,
                if (phase == Phase.AVAILABLE) null else ticket.task, time,
                if (phase == Phase.PERSISTED) time else if (phase in setOf(Phase.ASSIGNED, Phase.AVAILABLE)) null else old.persistSince)
            lanes[backend] = lane
            append(mapOf("kind" to "phase", "mono_ns" to time, "backend" to backend,
                "request_id" to ticket.id, "phase" to phase.name))
            return time
        }
        @Synchronized fun choose(queue: List<ArrivalPolicy.Ticket>): Pair<Decision, Long> {
            val time = clock()
            val snapshot = lanes.toMap()
            val ordered = ordered(queue).toList()
            val decision = if (overflow) Decision(null, "trace_overflow_stop", emptyList())
                else if (calibrationBackend != null) calibrationChoice(ordered, snapshot, calibrationBackend)
                else decide(ordered, snapshot, time, budgets)
            val end = clock()
            append(mapOf("kind" to "decision", "mono_ns" to time, "decision_end_ns" to end,
                "queue" to ordered.map(::ticketWire), "estimate_version" to version,
                "lanes" to snapshot.mapValues { (_, lane) ->
                    val residual = remaining(lane, time, budgets["${lane.task}_${lane.backend}"])
                    mapOf("phase" to lane.phase.name, "request_id" to lane.requestId, "task" to lane.task,
                        "phase_since_ns" to lane.phaseSince, "persist_since_ns" to lane.persistSince,
                        "remaining_ns" to residual.ns, "remaining_state" to residual.state)
                }, "candidates" to decision.candidates.map { it.wire() }, "reason" to decision.reason,
                "selected" to decision.choice?.let { mapOf("request_id" to it.ticket.id, "backend" to it.backend) }))
            // If this append overflowed, do not dispatch an unrecorded decision.
            return Pair(if (overflow) Decision(null, "trace_overflow_stop", emptyList()) else decision, end - time)
        }
        @Synchronized fun artifact(complete: Boolean): Map<String, Any?> = mapOf(
            "protocol" to if (calibrationBackend == null) PROTOCOL else CALIBRATION_PROTOCOL,
            "policy" to if (calibrationBackend == null) POLICY else CALIBRATION_POLICY, "estimate_contract" to ESTIMATE_CONTRACT,
            "estimate_version" to version, "estimate_provenance" to provenance,
            "budgets" to budgets.mapValues { it.value.wire() }, "capacity" to capacity,
            "clock" to "elapsedRealtimeNanos", "overflow" to overflow, "dropped_records" to dropped,
            "complete" to (complete && !overflow), "records" to records.toList(),
            "experiment_ready" to false) + (calibrationBackend?.let { mapOf("calibration_backend" to it) } ?: emptyMap())
    }
}
