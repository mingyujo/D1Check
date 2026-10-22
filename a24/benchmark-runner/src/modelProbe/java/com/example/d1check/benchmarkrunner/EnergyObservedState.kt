package com.example.d1check.benchmarkrunner

import java.io.PrintWriter
import java.io.StringWriter
import java.util.concurrent.atomic.AtomicReference

/** One short lock protects only copies/references, never adapters, I/O or Android APIs. */
internal class EnergyObservedState<T>(private val clock: () -> Long) {
    private val lock = Any()
    private var currentPhase = "setup"
    private var version = 0L
    private var waiting: Int? = null
    private val active = linkedMapOf<String, String>()
    private val runtimes = linkedMapOf<String, T>()
    var phase: String
        get() = synchronized(lock) { currentPhase }
        set(value) = synchronized(lock) { currentPhase = value; version++ }
    fun addRuntime(key: String, runtime: T) = synchronized(lock) { runtimes[key] = runtime; version++ }
    fun runtime(key: String): T = synchronized(lock) { runtimes.getValue(key) }
    fun laneRuntimes(suffix: String): List<T> = synchronized(lock) {
        runtimes.filterKeys { it.endsWith(suffix) }.values.toList()
    }
    fun dispatch(key: String, id: String) = synchronized(lock) { active[key] = id; version++ }
    fun release(key: String) = synchronized(lock) { active.remove(key); version++ }
    /** Only the new arrival collector sets this; legacy fixed-work samples are unchanged. */
    fun setWaiting(count: Int) = synchronized(lock) { require(count >= 0); waiting = count; version++ }
    fun snapshot(): Map<String, Any?> = synchronized(lock) {
        mapOf("phase" to currentPhase, "active" to LinkedHashMap(active),
            "resident_keys" to runtimes.keys.sorted(), "state_version" to version,
            "state_snapshot_ns" to clock(), "observation_version" to "energy-state-snapshot-v1") +
            (waiting?.let { mapOf("waiting_requests" to it) } ?: emptyMap())
    }
}

internal object EnergyFailureEvidence {
    fun capture(error: Throwable, session: String, phase: String, stage: String, monoNs: Long): Map<String, Any?> {
        val stack = StringWriter().also { error.printStackTrace(PrintWriter(it)) }.toString()
        return mapOf("exception_class" to error.javaClass.name, "message" to error.message,
            "stack" to stack, "session_id" to session, "phase" to phase, "stage" to stage,
            "mono_ns" to monoNs, "thread_id" to Thread.currentThread().id,
            "thread_name" to Thread.currentThread().name)
    }
}

/** The Activity uses this exact tick path. Failure recording never samples shared maps. */
internal class EnergySamplerGuard(
    private val stop: AtomicReference<String?>,
    private val context: (Throwable) -> Map<String, Any?>,
    private val persist: (Map<String, Any?>) -> Unit
) {
    val failure = AtomicReference<Map<String, Any?>?>(null)
    val recordingFailure = AtomicReference<String?>(null)
    fun tick(sampleAndRecord: () -> Unit) {
        if (failure.get() != null) return
        try { sampleAndRecord() } catch (error: Throwable) {
            val record = context(error)
            if (failure.compareAndSet(null, record)) {
                // Publish detached evidence BEFORE stop lets the controller enter cleanup.
                stop.compareAndSet(null, "sample: $error")
                try { persist(record) } catch (writeError: Throwable) {
                    // Remains failed; cleanup receipt can preserve the first evidence and this error.
                    recordingFailure.set(StringWriter().also { writeError.printStackTrace(PrintWriter(it)) }.toString())
                }
            }
        }
    }
}
