package com.example.d1check.benchmarkrunner

/** CAL03 strict PC policy port plus explicitly separate fixed-assignment collection.
 * No forecast releases a lane; no future requests/outcomes enter evaluate(). */
internal class ArrivalCollectionDev(
    private val clock: () -> Long, val mode: String, val assignment: String, val concurrency: Int,
    private val cells: Map<String, Cell>, val configHash: String, private val capacity: Int = 128
) {
    companion object {
        const val PROTOCOL = "arrival-collection-dev-v1"
        const val POLICY = "COLLECTION_DISPATCH_DEV_1"
        const val STRICT = "CAL03_SOLO_CONDITIONAL_PC_DEV_1"
    }
    data class Cell(val phase: List<Double>, val joint: List<Double>) {
        init { require(phase.size == 4 && joint.size == 5 && (phase + joint).all { it.isFinite() && it >= 0 }) }
    }
    private val arrived = mutableMapOf<String, Pair<ArrivalPolicy.Ticket, Long>>()
    private val records = mutableListOf<Map<String, Any?>>()
    var overflow = false; private set
    init {
        require(mode in setOf("strict_active", "fixed_shadow") && assignment in setOf("CPU", "SPLIT"))
        require(concurrency in 1..2 && (mode != "strict_active" || concurrency == 1 && assignment == "CPU"))
        require(capacity > 0 && configHash.matches(Regex("[a-f0-9]{64}")))
        require(cells.keys == setOf("classification", "detection").flatMap { t ->
            listOf("CPU", "GPU").flatMap { b -> listOf("urgent", "normal").map { p -> "${t}_${b}_$p" } }
        }.toSet())
    }
    fun arrive(ticket: ArrivalPolicy.Ticket, actual: Long) {
        check(!arrived.containsKey(ticket.id)); arrived[ticket.id] = ticket to actual
    }
    fun evaluate(queue: List<ArrivalPolicy.Ticket>, lanes: Map<String, ArrivalTimingDev.Lane>, now: Long): Map<String, Any?> {
        val ordered = ArrivalTimingDev.ordered(queue)
        require(ordered.all { arrived.getValue(it.id).second <= now })
        val snapshots = lanes.mapValues { (backend, lane) ->
            val priority = lane.requestId?.let { arrived.getValue(it).first.priority }
            mapOf("phase" to lane.phase.name, "request_id" to lane.requestId, "task" to lane.task,
                "priority" to priority, "phase_since_ns" to lane.phaseSince, "persist_since_ns" to lane.persistSince)
        }
        val residuals = lanes.mapValues { (backend, lane) ->
            if (lane.phase == ArrivalTimingDev.Phase.AVAILABLE) mapOf("ns" to 0, "state" to "AVAILABLE") else {
                val p = arrived.getValue(lane.requestId!!).first.priority
                val cell = cells.getValue("${lane.task}_${backend}_$p")
                val index = when (lane.phase) {
                    ArrivalTimingDev.Phase.ASSIGNED -> 0
                    ArrivalTimingDev.Phase.EXECUTING -> 1
                    ArrivalTimingDev.Phase.OUTPUT_READY -> 2
                    else -> 3
                }
                val origin = if (index == 3) lane.persistSince else lane.phaseSince
                val elapsed = origin?.let { require(it <= now); now - it }
                val left = elapsed?.let { cell.joint[index + 1] - it }
                val state = if (elapsed == null) "UNKNOWN_MISSING_ORIGIN" else if (elapsed >= cell.phase[index] || left!! <= 0)
                    "UNKNOWN_OVERRUN" else "ESTIMATED_POINT"
                mapOf("ns" to if (state == "ESTIMATED_POINT") left else null, "state" to state)
            }
        }
        val candidates = ordered.map { t -> mapOf("request_id" to t.id, "predictions" to listOf("CPU", "GPU").associateWith { b ->
            val cell = cells.getValue("${t.task}_${b}_${t.priority}")
            mapOf("dispatch_to_response_ns" to cell.joint[0], "dispatch_to_lane_ns" to cell.joint[1], "decision_to_response_ns" to null)
        }) }
        val reason = when {
            ordered.isEmpty() -> "wait_empty"
            lanes.values.any { it.phase != ArrivalTimingDev.Phase.AVAILABLE } -> "wait_solo_scope_busy"
            else -> "fallback_cpu_missing_adaptive_cost"
        }
        return mapOf("policy" to STRICT, "now_ns" to now, "queue" to ordered.map {
            ArrivalTimingDev.ticketWire(it) + ("arrival_ns" to arrived.getValue(it.id).second)
        }, "lanes" to snapshots, "residuals" to residuals, "candidates" to candidates,
            "selected" to if (reason == "fallback_cpu_missing_adaptive_cost") mapOf("request_id" to ordered.first().id, "backend" to "CPU") else null,
            "reason" to reason, "assumed_common_decision_ns" to null, "experiment_ready" to false)
    }
    fun choose(queue: List<ArrivalPolicy.Ticket>, lanes: Map<String, ArrivalTimingDev.Lane>, now: Long): ArrivalTimingDev.Decision {
        if (records.size >= capacity) { overflow = true; return ArrivalTimingDev.Decision(null, "collection_overflow_stop", emptyList()) }
        val begin = clock()
        val shadow = evaluate(queue, lanes, now)
        val computeEnd = clock()
        val actual = if (mode == "strict_active") {
            if (shadow["selected"] == null) null else ArrivalPolicy.Choice(ArrivalTimingDev.ordered(queue).first(), "CPU", shadow["reason"] as String)
        } else {
            val candidate = if (concurrency == 1 && lanes.values.any { it.phase != ArrivalTimingDev.Phase.AVAILABLE }) null
                else ArrivalTimingDev.ordered(queue).firstOrNull { t ->
                    val b = if (assignment == "CPU" || t.priority == "urgent") "CPU" else "GPU"
                    lanes.getValue(b).phase == ArrivalTimingDev.Phase.AVAILABLE
                }
            candidate?.let { ArrivalPolicy.Choice(it, if (assignment == "CPU" || it.priority == "urgent") "CPU" else "GPU", "collection_fixed_assignment") }
        }
        val selectionEnd = clock()
        val reason = actual?.reason ?: if (mode == "strict_active") shadow["reason"] as String else if (queue.isEmpty()) "wait_empty" else "wait_collection_busy"
        val record = linkedMapOf<String, Any?>("seq" to records.size, "snapshot_ns" to now, "compute_start_ns" to begin,
            "compute_end_ns" to computeEnd, "selection_end_ns" to selectionEnd, "shadow" to shadow,
            "actual_selected" to actual?.let { mapOf("request_id" to it.ticket.id, "backend" to it.backend) }, "actual_reason" to reason)
        records.add(record)
        record["record_end_ns"] = clock() // in-memory construction/append; final assignment itself excluded
        return ArrivalTimingDev.Decision(actual, reason, emptyList())
    }
    fun artifact(complete: Boolean) = mapOf("protocol" to PROTOCOL, "policy" to POLICY, "mode" to mode,
        "assignment" to assignment, "maximum_concurrency" to concurrency, "config_sha256" to configHash,
        "capacity" to capacity, "overflow" to overflow, "complete" to (complete && !overflow), "records" to records.toList(),
        "cost_contract" to "snapshot->compute_start; compute; actual_selection; in_memory_record; outer_trace_and_dispatch separate", "experiment_ready" to false)
}
