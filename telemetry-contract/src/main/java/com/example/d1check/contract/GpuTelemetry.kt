package com.example.d1check.contract

import android.content.Context
import android.net.Uri
import android.os.SystemClock
import android.util.Log
import org.json.JSONObject
import java.util.concurrent.atomic.AtomicLong

data class D1RunContext(
    val runId: String,
    val startedElapsedNs: Long,
    val startedWallMs: Long,
)

object D1RunContextClient {
    const val DEFAULT_AUTHORITY = "com.example.d1check.run"

    /** Query once at benchmark startup. Per-inference provider calls would perturb latency. */
    fun requireActive(context: Context, authority: String = DEFAULT_AUTHORITY): D1RunContext {
        val uri = Uri.parse("content://$authority/current")
        context.contentResolver.query(uri, null, null, null, null)?.use { cursor ->
            check(cursor.moveToFirst()) { "D1Check has no run. Start D1Check v4 first." }
            val active = cursor.getInt(cursor.getColumnIndexOrThrow("active")) == 1
            check(active) { "D1Check run is not active. Start a new run first." }
            return D1RunContext(
                runId = cursor.getString(cursor.getColumnIndexOrThrow("run_id")),
                startedElapsedNs = cursor.getLong(
                    cursor.getColumnIndexOrThrow("started_elapsed_ns")
                ),
                startedWallMs = cursor.getLong(cursor.getColumnIndexOrThrow("started_wall_ms")),
            )
        }
        error("D1Check run provider is unavailable: $uri")
    }
}

/**
 * Structured GPU benchmark logger. All timestamps use elapsedRealtimeNanos(), the same
 * boot-scoped monotonic clock as D1Check. Log after measuring so Logcat overhead is excluded.
 */
class GpuTelemetry(private val run: D1RunContext) {
    private val sequence = AtomicLong(0L)

    init {
        event(event = "benchmark_connected", phase = "setup", status = "ok")
    }

    fun event(
        event: String,
        phase: String,
        status: String = "ok",
        fields: Map<String, Any?> = emptyMap(),
    ) {
        emit(event, phase, status, SystemClock.elapsedRealtimeNanos(), null, fields)
    }

    fun <T> delegateInit(block: () -> T): T = measured("delegate_init", "delegate_init", block = block)

    fun <T> warmup(iteration: Long, block: () -> T): T = measured(
        operation = "warmup",
        phase = "warmup",
        fields = mapOf("iteration" to iteration),
        block = block,
    )

    fun <T> inference(inferenceIndex: Long, batchSize: Int = 1, block: () -> T): T = measured(
        operation = if (batchSize == 1) "inference" else "batch",
        phase = "run",
        fields = mapOf("inference_index" to inferenceIndex, "batch_size" to batchSize),
        block = block,
    )

    fun <T> shutdown(block: () -> T): T = measured("shutdown", "shutdown", block = block)

    fun <T> measured(
        operation: String,
        phase: String,
        fields: Map<String, Any?> = emptyMap(),
        block: () -> T,
    ): T {
        val startNs = SystemClock.elapsedRealtimeNanos()
        emit("${operation}_start", phase, "start", startNs, null, fields)
        return try {
            val result = block()
            val endNs = SystemClock.elapsedRealtimeNanos()
            emit("${operation}_end", phase, "ok", endNs, startNs, fields)
            result
        } catch (error: Throwable) {
            val endNs = SystemClock.elapsedRealtimeNanos()
            emit(
                "${operation}_error",
                phase,
                "error",
                endNs,
                startNs,
                fields + mapOf(
                    "error_type" to error.javaClass.name,
                    "message" to error.message,
                ),
            )
            throw error
        }
    }

    private fun emit(
        event: String,
        phase: String,
        status: String,
        endNs: Long,
        startNs: Long?,
        fields: Map<String, Any?>,
    ) {
        val json = JSONObject()
            .put("schema_version", 1)
            .put("source", "gpu")
            .put("event", event)
            .put("phase", phase)
            .put("status", status)
            .put("run_id", run.runId)
            .put("sequence", sequence.getAndIncrement())
            .put("mono_ns", endNs)
            .put("wall_ms", System.currentTimeMillis())
        if (startNs != null) {
            json.put("start_mono_ns", startNs)
            json.put("latency_ns", endNs - startNs)
            json.put("latency_ms", (endNs - startNs) / 1_000_000.0)
        }
        fields.forEach { (key, value) -> json.put(key, value ?: JSONObject.NULL) }
        Log.i(TAG, json.toString())
    }

    companion object {
        const val TAG = "D1GPU"

        fun connect(context: Context): GpuTelemetry =
            GpuTelemetry(D1RunContextClient.requireActive(context))
    }
}
