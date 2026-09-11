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
import java.util.concurrent.locks.LockSupport

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
        var loadStartedNs: Long? = null
        var loadEndedNs: Long? = null
        var runTermination: RunTermination? = null
        var terminationReason: TerminationReason? = null
        var pilotSafety: PilotSafetyCheck? = null
        var dutyCycleTracker: DutyCycleTracker? = null

        try {
            config.expectedRunId?.let { expectedRunId ->
                if (telemetry.run.runId != expectedRunId) {
                    throw RunContextMismatchException(
                        "run_context_mismatch checkpoint=automation_start " +
                            "expected_run=$expectedRunId actual_run=${telemetry.run.runId}"
                    )
                }
            }
            if (config.isAutomated) {
                pilotSafety = PilotSafetyPolicy.readAndEvaluate(context)
                if (!checkNotNull(pilotSafety).passed) {
                    throw PilotSafetyException(
                        "pilot_safety_rejected: " +
                            checkNotNull(pilotSafety).rejectionReasons.joinToString(",")
                    )
                }
            }
            revalidate(telemetry, "before_baseline")
            telemetry.instant("baseline_start", "baseline")
            Thread.sleep(BASELINE_MS)
            telemetry.instant("baseline_end", "baseline")

            val options = Interpreter.Options()
            when (config.normalizedResource) {
                ResourceTarget.CPU -> options.setNumThreads(checkNotNull(config.cpuThreads))
                ResourceTarget.GPU -> {
                    gpuDelegate = telemetry.measured("delegate_init", "setup") {
                        val compatibility = CompatibilityList()
                        check(compatibility.isDelegateSupportedOnThisDevice) {
                            "GPU delegate is not supported; GPU experiment cannot start"
                        }
                        GpuDelegate(config.gpuDelegateProfile.options())
                    }
                    options.addDelegate(checkNotNull(gpuDelegate))
                }
                ResourceTarget.CPU4 -> error("CPU4 must be normalized before execution")
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
                resetTensorBuffers(input, output)
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
            loadStartedNs = runStartedNs
            runTermination = RunTermination(config.limit, runStartedNs)
            if (config.limit is RunLimit.Duration) {
                dutyCycleTracker = DutyCycleTracker(
                    requestedPercent = config.dutyCyclePercent,
                    periodNs = DutyCycleTracker.periodNanos(config.dutyCyclePeriodSeconds),
                    startedNs = runStartedNs,
                    targetDurationNs = checkNotNull(runTermination.targetDurationNs),
                )
            }
            var inferenceIndex = 0L
            while (true) {
                val loopNowNs = SystemClock.elapsedRealtimeNanos()
                val completed = checkNotNull(runTermination).completionReason(
                    loopNowNs,
                    inferenceIndex,
                )
                if (completed != null) {
                    terminationReason = completed
                    break
                }
                if (!telemetry.hasInferenceCapacity) {
                    success = false
                    message = "buffer_limit"
                    invalidReason = "buffer_limit"
                    terminationReason = TerminationReason.BUFFER_LIMIT
                    telemetry.instant("buffer_limit", "run", "error",
                        "max=${GpuTelemetry.DEFAULT_MAX_INFERENCE_SPANS}")
                    break
                }

                dutyCycleTracker?.let { tracker ->
                    val requestedIdleNs = tracker.nanosUntilActive(loopNowNs)
                    if (requestedIdleNs > 0L) {
                        val remainingDurationNs = (
                            checkNotNull(runTermination.targetDurationNs) -
                                (loopNowNs - runStartedNs)
                            ).coerceAtLeast(0L)
                        val idleStartedNs = SystemClock.elapsedRealtimeNanos()
                        LockSupport.parkNanos(minOf(requestedIdleNs, remainingDurationNs))
                        val idleEndedNs = SystemClock.elapsedRealtimeNanos()
                        tracker.recordIdle(idleStartedNs, idleEndedNs)
                        continue
                    }
                }

                resetTensorBuffers(input, output)
                val startNs = SystemClock.elapsedRealtimeNanos()
                activeInterpreter.run(input, output)
                val endNs = SystemClock.elapsedRealtimeNanos()
                dutyCycleTracker?.recordInference(startNs, endNs)
                check(telemetry.recordInference(startNs, endNs, inferenceIndex, 1))
                inferenceIndex++
            }
            loadEndedNs = SystemClock.elapsedRealtimeNanos()
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
                terminationReason = TerminationReason.RUN_CONTEXT_MISMATCH
                telemetry.instant("run_context_mismatch", "validation", "error", message)
            } else if (error is PilotSafetyException) {
                invalidReason = "pilot_safety_rejected"
                terminationReason = TerminationReason.PILOT_SAFETY_REJECTED
                telemetry.instant("pilot_safety_rejected", "validation", "error", message)
            } else {
                invalidReason = invalidReason ?: "run_error"
                terminationReason = terminationReason ?: TerminationReason.RUN_ERROR
                telemetry.instant("run_error", "run", "error", message)
            }
            if (loadStarted && !loadEnded) {
                loadEndedNs = SystemClock.elapsedRealtimeNanos()
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
                invalidReason = invalidReason ?: "shutdown_error"
                terminationReason = terminationReason ?: TerminationReason.SHUTDOWN_ERROR
            }
        }

        try {
            revalidate(telemetry, "before_file_flush")
        } catch (error: RunContextMismatchException) {
            success = false
            invalidReason = "run_context_mismatch"
            terminationReason = TerminationReason.RUN_CONTEXT_MISMATCH
            message = "${error.javaClass.simpleName}: ${error.message ?: ""}"
            telemetry.instant("run_context_mismatch", "validation", "error", message)
        }

        val requestedInferenceCount = (config.limit as? RunLimit.Count)?.inferenceCount
        val requestedDurationSeconds = (config.limit as? RunLimit.Duration)?.durationSeconds
        val actualLoadDurationNs = if (loadStartedNs != null && loadEndedNs != null) {
            checkNotNull(runTermination).actualDurationNs(checkNotNull(loadEndedNs))
        } else {
            null
        }
        val dutyMetrics = if (loadEndedNs != null) {
            dutyCycleTracker?.metrics(checkNotNull(loadEndedNs))
        } else {
            null
        }
        val accuracyPreflight = linkedMapOf<String, Any?>(
            "schema_version" to 2,
            "validation_scope" to "timed_run_does_not_execute_preflight",
            "status" to "not_run",
            "synthetic_numerical_check" to mapOf("status" to "not_run"),
            "representative_input_equivalence" to mapOf("status" to "not_run"),
            "task_accuracy_check" to mapOf("status" to "not_run"),
            "formal_gate_result" to mapOf("status" to "not_run"),
            "note" to "experiment-level preflight is attached by the host; timed loop is isolated",
        )
        val energyMeasurement = linkedMapOf<String, Any?>(
            "status" to "raw_unverified",
            "current_raw_policy" to "raw_unscaled_unit_unverified",
            "voltage_available" to null,
            "current_unit_verified" to false,
            "charge_counter_unit_verified" to false,
            "calculation_performed" to false,
            "note" to "no J or mWh result is produced before unit calibration",
        )
        val outputConfig = linkedMapOf<String, Any?>(
            "precision" to config.precision.name,
            "limit_mode" to config.limit.modeName,
            "requested_inference_count" to requestedInferenceCount,
            "requested_duration_s" to requestedDurationSeconds,
            "target_duration_ns" to runTermination?.targetDurationNs,
            "actual_load_duration_ns" to actualLoadDurationNs,
            "duration_overrun_ns" to loadEndedNs?.let { runTermination?.durationOverrunNs(it) },
            "termination_reason" to (terminationReason ?: TerminationReason.RUN_ERROR).wireName,
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
            "resource_legacy_alias" to config.legacyResourceAlias,
            "cpu_threads" to config.cpuThreads,
            "cpu_affinity" to "NONE",
            "gpu_delegate_profile" to if (config.normalizedResource == ResourceTarget.GPU) {
                config.gpuDelegateProfile.metadata()
            } else {
                null
            },
            "auto_start" to config.isAutomated,
            "expected_run_id" to config.expectedRunId,
            "command_id" to config.commandId,
            "requested_duty_cycle_percent" to config.dutyCyclePercent,
            "duty_cycle_period_ns" to DutyCycleTracker.periodNanos(
                config.dutyCyclePeriodSeconds
            ),
            "duty_cycle_applied" to (config.limit is RunLimit.Duration),
            "target_active_duration_ns" to dutyMetrics?.targetActiveDurationNs,
            "actual_active_duration_ns" to dutyMetrics?.actualActiveDurationNs,
            "actual_idle_duration_ns" to dutyMetrics?.actualIdleDurationNs,
            "achieved_duty_cycle_percent" to dutyMetrics?.achievedPercent,
            "completed_duty_cycle_count" to dutyMetrics?.completedCycleCount,
            "duty_cycle_active_overrun_ns" to dutyMetrics?.activeOverrunNs,
            "accuracy_preflight" to accuracyPreflight,
            "energy_measurement" to energyMeasurement,
        )
        outputConfig.putAll(
            pilotSafety?.metadata() ?: mapOf(
                "safety_policy_scope" to "NONE",
                "pilot_safety_pass" to null,
                "formal_safety_limits_applied" to false,
                "matched_start_limits_applied" to false,
            )
        )
        val flush = telemetry.flushAfterRun(
            context = context,
            resource = config.normalizedResource.name,
            modelId = ModelLoader.MODEL_ID,
            modelSha256 = ModelLoader.MODEL_SHA256,
            config = outputConfig,
        )
        return BenchmarkResult(success, message, flush)
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
        return DeterministicInputSet.legacyTimedInput(interpreter.getInputTensor(0).numBytes())
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
