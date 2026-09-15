package com.example.d1check.benchmarkrunner

import android.os.Process
import android.system.Os
import android.system.OsConstants
import java.io.File
import java.nio.ByteBuffer
import java.security.MessageDigest

data class ProcessThreadSample(
    val tid: Int,
    val name: String,
    val cpuTimeTicks: Long,
    val lastCpu: Int?,
)

data class ProcessThreadSnapshot(
    val status: String,
    val processId: Int,
    val capturedMonoNs: Long,
    val clockTicksPerSecond: Long?,
    val threads: List<ProcessThreadSample>,
    val errors: List<String>,
    val attemptedTidCount: Int = threads.size + errors.count { it.startsWith("tid=") },
    val failedTidCount: Int = errors.count { it.startsWith("tid=") },
) {
    fun metadata(): Map<String, Any?> = linkedMapOf(
        "status" to status,
        "process_id" to processId,
        "captured_mono_ns" to capturedMonoNs,
        "clock_ticks_per_second" to clockTicksPerSecond,
        "thread_count" to threads.size,
        "successful_tid_count" to threads.size,
        "failed_tid_count" to failedTidCount,
        "attempted_tid_count" to attemptedTidCount,
        "completeness" to when (status) {
            "ok" -> "complete"
            "partial" -> "incomplete"
            else -> "unavailable"
        },
        "threads" to threads.map { thread ->
            linkedMapOf(
                "tid" to thread.tid,
                "name" to thread.name,
                "cpu_time_ticks" to thread.cpuTimeTicks,
                "last_cpu" to thread.lastCpu,
            )
        },
        "errors" to errors,
    )
}

object ProcTaskStatParser {
    fun parse(tid: Int, text: String): ProcessThreadSample {
        val open = text.indexOf('(')
        val close = text.lastIndexOf(')')
        require(open > 0 && close > open) { "malformed /proc task stat for tid=$tid" }
        val fieldsAfterComm = text.substring(close + 1).trim().split(Regex("\\s+"))
        // fieldsAfterComm[0] is field 3 (state); utime/stime are fields 14/15.
        require(fieldsAfterComm.size >= 13) { "truncated /proc task stat for tid=$tid" }
        val userTicks = fieldsAfterComm[11].toLong()
        val systemTicks = fieldsAfterComm[12].toLong()
        val lastCpu = fieldsAfterComm.getOrNull(36)?.toIntOrNull() // processor, field 39
        return ProcessThreadSample(
            tid = tid,
            name = text.substring(open + 1, close),
            cpuTimeTicks = Math.addExact(userTicks, systemTicks),
            lastCpu = lastCpu,
        )
    }

    fun deltas(
        before: ProcessThreadSnapshot?,
        after: ProcessThreadSnapshot?,
    ): List<Map<String, Any?>> {
        if (before == null || after == null) return emptyList()
        val previous = before.threads.associateBy { it.tid }
        return after.threads.sortedBy { it.tid }.map { current ->
            val initial = previous[current.tid]
            val sameIdentity = initial?.name == current.name
            val deltaTicks = initial?.takeIf { sameIdentity }?.let {
                (current.cpuTimeTicks - it.cpuTimeTicks).coerceAtLeast(0L)
            }
            val ticksPerSecond = after.clockTicksPerSecond?.takeIf { it > 0L }
            linkedMapOf(
                "tid" to current.tid,
                "name" to current.name,
                "name_before" to initial?.name,
                "thread_name_matches" to (initial != null && sameIdentity),
                "possible_tid_reuse" to (initial != null && !sameIdentity),
                "cpu_time_delta_ticks" to deltaTicks,
                "cpu_time_delta_ns" to if (deltaTicks != null && ticksPerSecond != null) {
                    deltaTicks * 1_000_000_000L / ticksPerSecond
                } else null,
                "last_cpu_before" to initial?.lastCpu,
                "last_cpu_after" to current.lastCpu,
                "present_before_load" to (initial != null),
            )
        }
    }

    fun comparison(
        before: ProcessThreadSnapshot?,
        after: ProcessThreadSnapshot?,
    ): Map<String, Any?> {
        if (before == null || after == null) {
            return linkedMapOf(
                "status" to "unavailable",
                "evidence_completeness" to "incomplete",
                "deltas" to emptyList<Map<String, Any?>>(),
                "created_threads" to emptyList<Map<String, Any?>>(),
                "terminated_threads" to emptyList<Map<String, Any?>>(),
                "tid_reuse_candidates" to emptyList<Int>(),
            )
        }
        val beforeByTid = before.threads.associateBy { it.tid }
        val afterByTid = after.threads.associateBy { it.tid }
        val created = after.threads.filter { beforeByTid[it.tid] == null }.map {
            mapOf("tid" to it.tid, "name" to it.name)
        }
        val terminated = before.threads.filter { afterByTid[it.tid] == null }.map {
            mapOf("tid" to it.tid, "name" to it.name)
        }
        val reused = after.threads.filter { current ->
            beforeByTid[current.tid]?.name?.let { it != current.name } == true
        }.map { it.tid }
        val complete = before.status == "ok" && after.status == "ok"
        return linkedMapOf(
            "status" to if (complete) "ok" else "partial",
            "evidence_completeness" to if (complete) "complete" else "incomplete",
            "deltas" to deltas(before, after),
            "created_threads" to created,
            "terminated_threads" to terminated,
            "tid_reuse_candidates" to reused,
            "identity_policy" to "tid_and_thread_name_must_match",
            "lifecycle_caveat" to
                "created_or_terminated_threads_and_tid_reuse_may_hide_cpu_time",
        )
    }
}

object ProcessThreadSnapshotCollector {
    fun capture(monoNs: Long): ProcessThreadSnapshot {
        val errors = mutableListOf<String>()
        val taskRoot = File("/proc/self/task")
        val tasks = taskRoot.listFiles()
        if (tasks == null) errors += "task_directory unavailable"
        var attemptedTidCount = 0
        var failedTidCount = 0
        val samples = tasks.orEmpty().mapNotNull { task ->
            val tid = task.name.toIntOrNull() ?: return@mapNotNull null
            attemptedTidCount++
            try {
                ProcTaskStatParser.parse(tid, File(task, "stat").readText())
            } catch (error: Throwable) {
                failedTidCount++
                errors += "tid=$tid ${error.javaClass.simpleName}: ${error.message ?: ""}"
                null
            }
        }.sortedBy { it.tid }
        val ticks = try {
            Os.sysconf(OsConstants._SC_CLK_TCK)
        } catch (error: Throwable) {
            errors += "clock_ticks ${error.javaClass.simpleName}: ${error.message ?: ""}"
            null
        }
        return ProcessThreadSnapshot(
            status = when {
                samples.isEmpty() -> "unavailable"
                errors.isNotEmpty() -> "partial"
                else -> "ok"
            },
            processId = Process.myPid(),
            capturedMonoNs = monoNs,
            clockTicksPerSecond = ticks,
            threads = samples,
            errors = errors,
            attemptedTidCount = attemptedTidCount,
            failedTidCount = failedTidCount,
        )
    }
}

data class OutputReadbackEvidence(
    val status: String,
    val inferenceIndex: Long,
    val interpreterRunEndMonoNs: Long,
    val loadEndedMonoNs: Long,
    val checkStartMonoNs: Long,
    val checkEndMonoNs: Long,
    val byteCount: Int,
    val sha256: String?,
    val nonFiniteCount: Int?,
    val error: String?,
) {
    fun metadata(): Map<String, Any?> = linkedMapOf(
        "status" to status,
        "inference_index" to inferenceIndex,
        "interpreter_run_end_mono_ns" to interpreterRunEndMonoNs,
        "load_ended_mono_ns" to loadEndedMonoNs,
        "check_start_mono_ns" to checkStartMonoNs,
        "check_end_mono_ns" to checkEndMonoNs,
        "performed_after_latency_timer" to (checkStartMonoNs >= interpreterRunEndMonoNs),
        "performed_after_load_end" to (checkStartMonoNs >= loadEndedMonoNs),
        "output_byte_count" to byteCount,
        "output_sha256" to sha256,
        "non_finite_count" to nonFiniteCount,
        "output_readable_after_run" to (status != "error"),
        "evidence_scope" to "output_readiness_and_integrity_support_only",
        "cpu_gpu_accuracy_equivalence_claim" to false,
        "source_output" to "duplicate_of_last_completed_official_inference_output",
        "error" to error,
    )
}

object OutputReadbackInspector {
    fun inspect(
        output: ByteBuffer,
        inferenceIndex: Long,
        interpreterRunEndMonoNs: Long,
        loadEndedMonoNs: Long,
        monotonicNanos: () -> Long,
    ): OutputReadbackEvidence {
        val started = monotonicNanos()
        return try {
            val bytes = output.duplicate().apply { clear() }
            val digest = MessageDigest.getInstance("SHA-256")
            val chunk = ByteArray(minOf(8192, bytes.remaining()))
            while (bytes.hasRemaining()) {
                val count = minOf(chunk.size, bytes.remaining())
                bytes.get(chunk, 0, count)
                digest.update(chunk, 0, count)
            }
            val floats = output.duplicate().order(output.order()).apply { clear() }.asFloatBuffer()
            var nonFinite = 0
            while (floats.hasRemaining()) if (!floats.get().isFinite()) nonFinite++
            OutputReadbackEvidence(
                if (nonFinite == 0) "passed" else "failed",
                inferenceIndex, interpreterRunEndMonoNs, loadEndedMonoNs, started,
                monotonicNanos(), output.capacity(),
                digest.digest().joinToString("") { "%02x".format(it) }, nonFinite, null,
            )
        } catch (error: Throwable) {
            OutputReadbackEvidence(
                "error", inferenceIndex, interpreterRunEndMonoNs, loadEndedMonoNs, started,
                monotonicNanos(), output.capacity(), null, null,
                "${error.javaClass.simpleName}: ${error.message ?: ""}",
            )
        }
    }
}

internal data class FrozenLoadMetrics(
    val loadEndedMonoNs: Long,
    val actualLoadDurationNs: Long,
    val dutyMetrics: DutyCycleMetrics?,
    val completedInferenceCount: Long,
    val lastInferenceEndedMonoNs: Long,
)

internal data class OfficialInferenceResult(
    val startedMonoNs: Long,
    val endedMonoNs: Long,
)

internal object OfficialInferenceCoordinator {
    fun execute(
        inferenceIndex: Long,
        monotonicNanos: () -> Long,
        interpreterRun: () -> Unit,
        recordInference: (Long, Long, Long, Int) -> Boolean,
    ): OfficialInferenceResult {
        val started = monotonicNanos()
        interpreterRun()
        val ended = monotonicNanos()
        check(recordInference(started, ended, inferenceIndex, 1))
        return OfficialInferenceResult(started, ended)
    }
}

internal data class DiagnosticPostLoadResult(
    val frozenMetrics: FrozenLoadMetrics,
    val outputReadback: OutputReadbackEvidence,
)

internal object ProductionPostLoadCoordinator {
    fun capture(
        frozenMetrics: FrozenLoadMetrics,
        output: ByteBuffer,
        monotonicNanos: () -> Long,
    ): DiagnosticPostLoadResult {
        require(frozenMetrics.completedInferenceCount > 0L)
        val readback = OutputReadbackInspector.inspect(
            output,
            frozenMetrics.completedInferenceCount - 1L,
            frozenMetrics.lastInferenceEndedMonoNs,
            frozenMetrics.loadEndedMonoNs,
            monotonicNanos,
        )
        check(readback.checkStartMonoNs >= frozenMetrics.loadEndedMonoNs) {
            "diagnostic readback started before load metrics were frozen"
        }
        return DiagnosticPostLoadResult(frozenMetrics, readback)
    }
}

internal object DiagnosticPostLoadEvidence {
    fun capture(
        frozenMetrics: FrozenLoadMetrics,
        output: ByteBuffer,
        monotonicNanos: () -> Long,
    ): DiagnosticPostLoadResult = ProductionPostLoadCoordinator.capture(
        frozenMetrics, output, monotonicNanos
    )
}

internal object IndependentResourceCleanup {
    fun close(interpreterClose: () -> Unit, delegateClose: () -> Unit) {
        var failure: Throwable? = null
        try {
            interpreterClose()
        } catch (error: Throwable) {
            failure = error
        }
        try {
            delegateClose()
        } catch (error: Throwable) {
            if (failure == null) failure = error else failure.addSuppressed(error)
        }
        failure?.let { throw it }
    }
}
