package com.example.d1check.benchmarkrunner

import android.os.SystemClock
import java.util.UUID

/** Captured invocation timestamps are merged after execution, never logged inside the timer. */
internal class V4Telemetry(val sessionId: String, private val clock: () -> Long = SystemClock::elapsedRealtimeNanos) {
    private val events = mutableListOf<Map<String, Any?>>()
    private var previousDirect = -1L
    init { require(UUID.fromString(sessionId).toString() == sessionId) }
    @Synchronized fun emit(name: String, scope: V4Scope? = null, state: String = "running",
                           at: Long? = null, data: Map<String, Any?> = emptyMap()) {
        val captured = at ?: clock().also { check(it >= previousDirect) { "Monotonic clock regressed" }; previousDirect = it }
        require(captured >= 0 && name.matches(Regex("[a-z_]+")))
        events.add(linkedMapOf("protocol" to "task-profile-v4", "schema_version" to 1,
            "session_id" to sessionId, "request_id" to scope?.requestId,
            "runtime_id" to scope?.runtimeId, "worker_id" to scope?.worker,
            "task" to (scope?.task ?: "not_applicable"),
            "requested_backend" to (scope?.backend ?: "not_applicable"),
            "actual_backend" to (scope?.let { if (it.backend == "GPU") "GPU_unverified" else "CPU" } ?: "not_applicable"),
            "clock_domain" to "elapsedRealtimeNanos", "mono_ns" to captured,
            "event" to name, "terminal_state" to state, "data" to data))
    }
    @Synchronized fun snapshot(): List<Map<String, Any?>> = events.sortedBy { it["mono_ns"] as Long }
        .mapIndexed { index, row -> row + ("sequence" to index) }
}

internal class V4Scope(val trace: V4Telemetry, val runtimeId: String, val task: String,
                       val backend: String, val worker: Int) {
    var requestId: String? = null // owner-thread confined; emit snapshots the value immediately
    fun mark(phase: String, edge: String) = trace.emit(phase + "_" + if (edge == "finish") "end" else edge, this)
    fun at(name: String, timestamp: Long) = trace.emit(name, this, at = timestamp)
}

internal fun closeV4Resource(scope: V4Scope?, phase: String, close: () -> Unit) {
    var first: Throwable? = null
    var success = false
    listOf<() -> Unit>({ scope?.mark(phase, "start") }, { close(); success = true },
        { scope?.mark(phase, if (success) "finish" else "failed") }).forEach {
        try { it() } catch (e: Throwable) { if (first == null) first = e else first?.addSuppressed(e) }
    }
    first?.let { throw it }
}

internal object V4Gate {
    const val CONTRACT = "android-low-memory-resident-v1"
    /** Dynamic conservative smoke gate, NOT an OOM guarantee or calibrated peak bound. */
    fun reason(avail: Long, threshold: Long, low: Boolean, residentPss: Long, thermal: Int): String = when {
        avail < 0 || threshold <= 0 || residentPss <= 0 -> "missing_memory_evidence"
        thermal != 0 -> "thermal_outside_zero"
        low -> "android_low_memory"
        avail <= threshold || avail - threshold <= maxOf(threshold, residentPss) -> "insufficient_dynamic_reserve"
        else -> "admit"
    }
    fun worker(configuration: String, slot: Int): Int = if (configuration == "resident_cpu_serial") 0 else slot
}
