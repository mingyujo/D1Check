package com.example.d1check.contract

import android.content.Context
import android.net.Uri
import android.os.SystemClock
import android.util.Log
import org.json.JSONObject
import java.io.BufferedWriter
import java.io.File
import java.io.FileOutputStream
import java.io.OutputStreamWriter
import java.nio.charset.StandardCharsets
import java.util.UUID

data class D1RunContext(
    val runId: String,
    val active: Boolean,
    val startedElapsedNs: Long,
    val startedWallMs: Long,
    val bootId: String,
)

class RunContextMismatchException(message: String) : IllegalStateException(message)

object RunContextValidator {
    fun requireSame(initial: D1RunContext, current: D1RunContext, checkpoint: String) {
        if (!current.active || current.runId != initial.runId || current.bootId != initial.bootId) {
            throw RunContextMismatchException(
                "run_context_mismatch checkpoint=$checkpoint expected_run=${initial.runId} " +
                    "actual_run=${current.runId} expected_boot=${initial.bootId} " +
                    "actual_boot=${current.bootId} active=${current.active}"
            )
        }
    }
}

object D1RunContextClient {
    const val DEFAULT_AUTHORITY = "com.example.d1check.run"

    fun read(context: Context, authority: String = DEFAULT_AUTHORITY): D1RunContext {
        val uri = Uri.parse("content://$authority/current")
        context.contentResolver.query(uri, null, null, null, null)?.use { cursor ->
            check(cursor.moveToFirst()) { "D1Check has no run. Start D1Check v4 first." }
            return D1RunContext(
                runId = cursor.getString(cursor.getColumnIndexOrThrow("run_id")),
                active = cursor.getInt(cursor.getColumnIndexOrThrow("active")) == 1,
                startedElapsedNs = cursor.getLong(
                    cursor.getColumnIndexOrThrow("started_elapsed_ns")
                ),
                startedWallMs = cursor.getLong(cursor.getColumnIndexOrThrow("started_wall_ms")),
                bootId = cursor.getString(cursor.getColumnIndexOrThrow("boot_id")),
            )
        }
        error("D1Check run provider is unavailable: $uri")
    }

    fun requireActive(context: Context, authority: String = DEFAULT_AUTHORITY): D1RunContext =
        read(context, authority).also {
            check(it.active) { "D1Check run is not active. Start a new run first." }
        }

    fun revalidate(
        context: Context,
        initial: D1RunContext,
        checkpoint: String,
        authority: String = DEFAULT_AUTHORITY,
    ) {
        val current = try {
            read(context, authority)
        } catch (error: Throwable) {
            throw RunContextMismatchException(
                "run_context_mismatch checkpoint=$checkpoint provider_error=${error.message}"
            )
        }
        RunContextValidator.requireSame(initial, current, checkpoint)
    }
}

data class GpuFlushResult(
    val file: File,
    val eventCount: Int,
    val lastSequence: Long,
    val runnerSessionId: String,
)

/** GPU events remain in memory until [flushAfterRun]. */
class GpuTelemetry private constructor(
    val run: D1RunContext,
    maxInferenceSpans: Int,
    maxLifecycleEvents: Int,
    val runnerSessionId: String,
) {
    private val buffer = GpuEventBuffer(maxInferenceSpans, maxLifecycleEvents)

    val inferenceCount: Int get() = buffer.inferenceCount
    val hasInferenceCapacity: Boolean get() = buffer.hasInferenceCapacity
    val lifecycleCount: Int get() = buffer.lifecycleCount

    fun instant(event: String, phase: String, status: String = "ok", detail: String? = null) {
        recordInstant(event, phase, status, detail, emitNow = false)
    }

    /** Control marker for the host diagnostic capture; never call inside the inference loop. */
    fun liveInstant(event: String, phase: String, status: String = "ok", detail: String? = null) {
        recordInstant(event, phase, status, detail, emitNow = true)
    }

    private fun recordInstant(
        event: String,
        phase: String,
        status: String,
        detail: String?,
        emitNow: Boolean,
    ) {
        val monoNs = SystemClock.elapsedRealtimeNanos()
        buffer.recordLifecycle(
            BufferedGpuRecord(event, phase, status, monoNs, monoNs, -1L, 0, detail)
        )
        if (emitNow) {
            Log.i(TAG, encode(linkedMapOf(
                "schema_version" to SCHEMA_VERSION,
                "source" to "gpu",
                "event" to event,
                "phase" to phase,
                "status" to status,
                "run_id" to run.runId,
                "runner_session_id" to runnerSessionId,
                "boot_id" to run.bootId,
                "mono_ns" to monoNs,
                "detail" to detail,
            )))
        }
    }

    fun <T> measured(
        event: String,
        phase: String,
        index: Long = -1L,
        batchSize: Int = 0,
        block: () -> T,
    ): T {
        val startNs = SystemClock.elapsedRealtimeNanos()
        return try {
            val value = block()
            val endNs = SystemClock.elapsedRealtimeNanos()
            buffer.recordLifecycle(
                BufferedGpuRecord(event, phase, "ok", startNs, endNs, index, batchSize, null)
            )
            value
        } catch (error: Throwable) {
            val endNs = SystemClock.elapsedRealtimeNanos()
            buffer.recordLifecycle(
                BufferedGpuRecord(
                    event, phase, "error", startNs, endNs, index, batchSize,
                    "${error.javaClass.name}: ${error.message ?: ""}",
                )
            )
            throw error
        }
    }

    /** Called only after interpreter.run() and endNs have completed. No allocation is performed. */
    fun recordInference(startNs: Long, endNs: Long, inferenceIndex: Long, batchSize: Int): Boolean =
        buffer.recordInference(startNs, endNs, inferenceIndex, batchSize)

    /** JSON creation, file I/O, Logcat, and wall-time derivation happen only after GPU load ends. */
    fun flushAfterRun(
        context: Context,
        resource: String,
        modelId: String,
        modelSha256: String,
        config: Map<String, Any?>,
    ): GpuFlushResult {
        val lifecycle = buffer.lifecycleRecordsAfterRun()
        val directory = context.getExternalFilesDir("runs") ?: File(context.filesDir, "runs")
        check(directory.exists() || directory.mkdirs()) { "Cannot create runner log directory" }
        val file = createOutputFile(directory, run.runId, runnerSessionId)
        val eventCount = lifecycle.size + buffer.inferenceCount + 2
        var sequence = 0L

        val metadata = linkedMapOf<String, Any?>(
            "schema_version" to SCHEMA_VERSION,
            "source" to "gpu",
            "event" to "run_metadata",
            "phase" to "setup",
            "status" to "ok",
            "run_id" to run.runId,
            "runner_session_id" to runnerSessionId,
            "boot_id" to run.bootId,
            "sequence" to sequence++,
            "mono_ns" to run.startedElapsedNs,
            "wall_ms" to run.startedWallMs,
            "resource" to resource,
            "model_id" to modelId,
            "model_sha256" to modelSha256,
        )
        metadata.putAll(config)
        BufferedWriter(OutputStreamWriter(FileOutputStream(file), StandardCharsets.UTF_8)).use { writer ->
            writer.writeLine(encode(metadata))
            for (record in lifecycle) {
                writer.writeLine(encode(linkedMapOf(
                    "schema_version" to SCHEMA_VERSION,
                    "source" to "gpu",
                    "event" to record.event,
                    "phase" to record.phase,
                    "status" to record.status,
                    "run_id" to run.runId,
                    "runner_session_id" to runnerSessionId,
                    "sequence" to sequence++,
                    "start_mono_ns" to record.startNs,
                    "mono_ns" to record.endNs,
                    "latency_ns" to (record.endNs - record.startNs),
                    "latency_ms" to ((record.endNs - record.startNs) / 1_000_000.0),
                    "inference_index" to record.index.takeIf { it >= 0 },
                    "batch_size" to record.batchSize.takeIf { it > 0 },
                    "detail" to record.detail,
                    "wall_ms" to wallMs(record.endNs),
                )))
            }
            for (position in 0 until buffer.inferenceCount) {
                val startNs = buffer.inferenceStartAt(position)
                val endNs = buffer.inferenceEndAt(position)
                val batchSize = buffer.inferenceBatchSizeAt(position)
                writer.writeLine(encode(linkedMapOf(
                    "schema_version" to SCHEMA_VERSION,
                    "source" to "gpu",
                    "event" to if (batchSize == 1) "inference" else "batch",
                    "phase" to "run",
                    "status" to "ok",
                    "run_id" to run.runId,
                    "runner_session_id" to runnerSessionId,
                    "sequence" to sequence++,
                    "start_mono_ns" to startNs,
                    "mono_ns" to endNs,
                    "latency_ns" to (endNs - startNs),
                    "latency_ms" to ((endNs - startNs) / 1_000_000.0),
                    "inference_index" to buffer.inferenceIndexAt(position),
                    "batch_size" to batchSize,
                    "wall_ms" to wallMs(endNs),
                )))
            }
            val lastMonoNs = maxOf(
                lifecycle.maxOfOrNull { it.endNs } ?: run.startedElapsedNs,
                if (buffer.inferenceCount > 0) {
                    buffer.inferenceEndAt(buffer.inferenceCount - 1)
                } else {
                    run.startedElapsedNs
                },
            )
            val footer = linkedMapOf<String, Any?>(
                "schema_version" to SCHEMA_VERSION,
                "source" to "gpu",
                "event" to "file_summary",
                "phase" to "flush",
                "status" to "ok",
                "run_id" to run.runId,
                "runner_session_id" to runnerSessionId,
                "sequence" to sequence,
                "mono_ns" to lastMonoNs,
                "wall_ms" to wallMs(lastMonoNs),
                "file_event_count" to eventCount,
                "sequence_first" to 0,
                "sequence_last" to sequence,
                "inference_span_count" to buffer.inferenceCount,
                "file_path" to file.absolutePath,
            )
            listOf(
                "requested_duty_cycle_percent",
                "duty_cycle_period_ns",
                "target_active_duration_ns",
                "actual_active_duration_ns",
                "actual_idle_duration_ns",
                "achieved_duty_cycle_percent",
                "completed_duty_cycle_count",
                "duty_cycle_active_overrun_ns",
                "completed_inference_count",
                "termination_reason",
                "accuracy_preflight",
                "energy_measurement",
            ).forEach { key -> footer[key] = config[key] }
            writer.writeLine(encode(footer))
        }
        file.useLines { lines -> lines.forEach { Log.i(TAG, it) } }
        return GpuFlushResult(file, eventCount, sequence, runnerSessionId)
    }

    private fun wallMs(monoNs: Long): Long =
        run.startedWallMs + (monoNs - run.startedElapsedNs) / 1_000_000L

    private fun encode(values: Map<String, Any?>): String {
        val json = JSONObject()
        values.forEach { (key, value) -> json.put(key, jsonValue(value)) }
        return json.toString()
    }

    private fun jsonValue(value: Any?): Any = when (value) {
        null -> JSONObject.NULL
        is Map<*, *> -> JSONObject().apply {
            value.forEach { (key, nested) -> put(key.toString(), jsonValue(nested)) }
        }
        is Iterable<*> -> org.json.JSONArray().apply {
            value.forEach { nested -> put(jsonValue(nested)) }
        }
        else -> value
    }

    private fun BufferedWriter.writeLine(line: String) {
        append(line)
        newLine()
    }

    companion object {
        const val TAG = "D1GPU"
        const val SCHEMA_VERSION = 2
        const val DEFAULT_MAX_INFERENCE_SPANS = 250_000
        const val DEFAULT_MAX_LIFECYCLE_EVENTS = 20_000

        fun fileName(runId: String, runnerSessionId: String): String =
            "gpu-events-$runId-$runnerSessionId.jsonl"

        fun createOutputFile(directory: File, runId: String, runnerSessionId: String): File {
            check(directory.exists() || directory.mkdirs()) { "Cannot create runner log directory" }
            return File(directory, fileName(runId, runnerSessionId)).also {
                check(it.createNewFile()) { "runner output already exists: ${it.absolutePath}" }
            }
        }

        fun connect(
            context: Context,
            maxInferenceSpans: Int = DEFAULT_MAX_INFERENCE_SPANS,
            maxLifecycleEvents: Int = DEFAULT_MAX_LIFECYCLE_EVENTS,
            runnerSessionId: String = UUID.randomUUID().toString(),
        ): GpuTelemetry = GpuTelemetry(
            D1RunContextClient.requireActive(context),
            maxInferenceSpans,
            maxLifecycleEvents,
            runnerSessionId,
        )
    }
}
