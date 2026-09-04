package com.example.d1check.benchmarkrunner

import android.content.Context
import android.os.SystemClock
import com.example.d1check.contract.GpuFlushResult
import com.example.d1check.contract.GpuTelemetry
import com.example.d1check.contract.D1RunContextClient
import com.example.d1check.contract.RunContextMismatchException
import org.tensorflow.lite.DataType
import org.tensorflow.lite.Interpreter
import org.tensorflow.lite.gpu.CompatibilityList
import org.tensorflow.lite.gpu.GpuDelegate
import java.nio.ByteBuffer
import java.nio.ByteOrder

data class BenchmarkResult(
    val success: Boolean,
    val message: String,
    val flushResult: GpuFlushResult?,
)

class GpuBenchmarkEngine(private val context: Context) {
    fun execute(config: RunConfig): BenchmarkResult {
        check(Thread.currentThread().name == THREAD_NAME) {
            "Benchmark must run on the dedicated $THREAD_NAME thread"
        }
        val telemetry = GpuTelemetry.connect(context)
        var interpreter: Interpreter? = null
        var gpuDelegate: GpuDelegate? = null
        var success = true
        var message = "ok"
        var invalidReason: String? = null
        var loadStarted = false
        var loadEnded = false

        try {
            revalidate(telemetry, "before_baseline")
            telemetry.instant("baseline_start", "baseline")
            Thread.sleep(BASELINE_MS)
            telemetry.instant("baseline_end", "baseline")

            val options = Interpreter.Options()
            when (config.resource) {
                ResourceTarget.CPU4 -> options.setNumThreads(4)
                ResourceTarget.GPU -> {
                    gpuDelegate = telemetry.measured("delegate_init", "setup") {
                        val compatibility = CompatibilityList()
                        check(compatibility.isDelegateSupportedOnThisDevice) {
                            "GPU delegate is not supported; GPU experiment cannot start"
                        }
                        GpuDelegate(compatibility.bestOptionsForThisDevice)
                    }
                    options.addDelegate(checkNotNull(gpuDelegate))
                }
                ResourceTarget.NPU -> error("NPU is reserved for a future version")
            }

            interpreter = telemetry.measured("interpreter_init", "setup") {
                Interpreter(ModelLoader.map(context), options).also { it.allocateTensors() }
            }
            val activeInterpreter = checkNotNull(interpreter)
            validateModel(activeInterpreter)
            val input = createInput(activeInterpreter)
            val output = createOutput(activeInterpreter)

            revalidate(telemetry, "before_warmup")
            repeat(config.warmupCount) { index ->
                telemetry.measured("warmup", "warmup", index.toLong(), 1) {
                    activeInterpreter.run(input, output)
                }
            }

            revalidate(telemetry, "before_gpu_load")
            if (config.experimentMode == ExperimentMode.DIAGNOSTIC) {
                telemetry.liveInstant("diagnostic_trace_start", "diagnostic")
            }
            telemetry.instant("load_start", "run")
            loadStarted = true
            val runStartedNs = SystemClock.elapsedRealtimeNanos()
            var inferenceIndex = 0L
            while (shouldContinue(config, inferenceIndex, runStartedNs)) {
                if (!telemetry.hasInferenceCapacity) {
                    success = false
                    message = "buffer_limit"
                    telemetry.instant("buffer_limit", "run", "error",
                        "max=${GpuTelemetry.DEFAULT_MAX_INFERENCE_SPANS}")
                    break
                }

                val startNs = SystemClock.elapsedRealtimeNanos()
                activeInterpreter.run(input, output)
                val endNs = SystemClock.elapsedRealtimeNanos()
                check(telemetry.recordInference(startNs, endNs, inferenceIndex, 1))
                inferenceIndex++
            }
            telemetry.instant("load_end", "run", if (success) "ok" else "error")
            loadEnded = true
            if (config.experimentMode == ExperimentMode.DIAGNOSTIC) {
                telemetry.liveInstant("diagnostic_trace_stop", "diagnostic")
            }
            revalidate(telemetry, "after_gpu_load")
        } catch (error: Throwable) {
            success = false
            message = "${error.javaClass.simpleName}: ${error.message ?: ""}"
            if (error is RunContextMismatchException) {
                invalidReason = "run_context_mismatch"
                telemetry.instant("run_context_mismatch", "validation", "error", message)
            } else {
                telemetry.instant("run_error", "run", "error", message)
            }
            if (loadStarted && !loadEnded) {
                telemetry.instant("load_end", "run", "error")
                loadEnded = true
                if (config.experimentMode == ExperimentMode.DIAGNOSTIC) {
                    telemetry.liveInstant("diagnostic_trace_stop", "diagnostic", "error")
                }
            }
        } finally {
            try {
                telemetry.measured("shutdown", "shutdown") {
                    interpreter?.close()
                    gpuDelegate?.close()
                }
            } catch (error: Throwable) {
                success = false
                message = "shutdown ${error.javaClass.simpleName}: ${error.message ?: ""}"
            }
        }

        try {
            revalidate(telemetry, "before_file_flush")
        } catch (error: RunContextMismatchException) {
            success = false
            invalidReason = "run_context_mismatch"
            message = "${error.javaClass.simpleName}: ${error.message ?: ""}"
            telemetry.instant("run_context_mismatch", "validation", "error", message)
        }

        val flush = telemetry.flushAfterRun(
            context = context,
            resource = config.resource.name,
            modelId = ModelLoader.MODEL_ID,
            modelSha256 = ModelLoader.MODEL_SHA256,
            config = linkedMapOf(
                "precision" to config.precision.name,
                "limit_mode" to config.limitMode.name,
                "requested_inference_count" to config.inferenceCount,
                "requested_duration_s" to config.durationSeconds,
                "warmup_count" to config.warmupCount,
                "baseline_s" to BASELINE_MS / 1000L,
                "experiment_mode" to config.experimentMode.name,
                "perfetto_requested_by_runner" to
                    (config.experimentMode == ExperimentMode.DIAGNOSTIC),
                "completed_inference_count" to telemetry.inferenceCount,
                "runner_session_id" to telemetry.runnerSessionId,
                "litert_version" to LITERT_VERSION,
                "experiment_valid" to (success && invalidReason == null),
                "invalid_reason" to invalidReason,
                "lifecycle_event_count" to telemetry.lifecycleCount,
            ),
        )
        return BenchmarkResult(success, message, flush)
    }

    private fun shouldContinue(config: RunConfig, count: Long, startedNs: Long): Boolean =
        when (config.limitMode) {
            LimitMode.COUNT -> count < config.inferenceCount
            LimitMode.DURATION ->
                SystemClock.elapsedRealtimeNanos() - startedNs < config.durationSeconds * 1_000_000_000L
        }

    private fun revalidate(telemetry: GpuTelemetry, checkpoint: String) {
        D1RunContextClient.revalidate(context, telemetry.run, checkpoint)
    }

    private fun validateModel(interpreter: Interpreter) {
        val input = interpreter.getInputTensor(0)
        val output = interpreter.getOutputTensor(0)
        check(input.dataType() == DataType.FLOAT32 && input.shape().contentEquals(INPUT_SHAPE)) {
            "Unexpected input tensor: ${input.dataType()} ${input.shape().contentToString()}"
        }
        check(output.dataType() == DataType.FLOAT32 && output.shape().contentEquals(OUTPUT_SHAPE)) {
            "Unexpected output tensor: ${output.dataType()} ${output.shape().contentToString()}"
        }
    }

    private fun createInput(interpreter: Interpreter): ByteBuffer {
        val buffer = ByteBuffer.allocateDirect(interpreter.getInputTensor(0).numBytes())
            .order(ByteOrder.nativeOrder())
        var state = 0x12345678
        while (buffer.remaining() >= Float.SIZE_BYTES) {
            state = state * 1664525 + 1013904223
            buffer.putFloat(((state ushr 8) and 0xFFFFFF) / 16777215.0f)
        }
        return buffer.rewind() as ByteBuffer
    }

    private fun createOutput(interpreter: Interpreter): ByteBuffer =
        ByteBuffer.allocateDirect(interpreter.getOutputTensor(0).numBytes())
            .order(ByteOrder.nativeOrder())

    companion object {
        const val THREAD_NAME = "d1-benchmark-runner"
        const val BASELINE_MS = 60_000L
        const val LITERT_VERSION = "1.4.2"
        private val INPUT_SHAPE = intArrayOf(1, 224, 224, 3)
        private val OUTPUT_SHAPE = intArrayOf(1, 1001)
    }
}
