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

internal interface BenchmarkEngineTelemetry {
    val runId: String
    val inferenceCount: Int
    val hasInferenceCapacity: Boolean
    val lifecycleCount: Int
    val runnerSessionId: String

    fun instant(event: String, phase: String, status: String = "ok", detail: String? = null)
    fun liveInstant(event: String, phase: String, status: String = "ok", detail: String? = null)
    fun <T> measured(
        event: String,
        phase: String,
        index: Long = -1L,
        batchSize: Int = 0,
        block: () -> T,
    ): T
    fun recordInference(startNs: Long, endNs: Long, inferenceIndex: Long, batchSize: Int): Boolean
    fun flush(
        resource: String,
        modelId: String,
        modelSha256: String,
        config: Map<String, Any?>,
    ): GpuFlushResult?
}

internal interface BenchmarkEngineRuntime {
    val input: ByteBuffer
    val output: ByteBuffer
    fun runInference()
    fun closeInterpreter()
    fun closeDelegate()
}

internal interface BenchmarkEngineDependencies {
    fun connectTelemetry(config: RunConfig): BenchmarkEngineTelemetry
    fun evaluatePilotSafety(): PilotSafetyCheck
    fun sleepBaseline()
    fun createRuntime(
        config: RunConfig,
        telemetry: BenchmarkEngineTelemetry,
    ): BenchmarkEngineRuntime
    fun monotonicNanos(): Long
    fun parkNanos(nanos: Long)
    fun captureThreadSnapshot(monoNs: Long): ProcessThreadSnapshot
    fun revalidate(telemetry: BenchmarkEngineTelemetry, checkpoint: String)
    fun capturePostLoad(
        frozenMetrics: FrozenLoadMetrics,
        output: ByteBuffer,
    ): DiagnosticPostLoadResult
}

private class ProductionBenchmarkTelemetry(
    private val context: Context,
    private val telemetry: GpuTelemetry,
) : BenchmarkEngineTelemetry {
    val runContext get() = telemetry.run
    override val runId: String get() = telemetry.run.runId
    override val inferenceCount: Int get() = telemetry.inferenceCount
    override val hasInferenceCapacity: Boolean get() = telemetry.hasInferenceCapacity
    override val lifecycleCount: Int get() = telemetry.lifecycleCount
    override val runnerSessionId: String get() = telemetry.runnerSessionId

    override fun instant(event: String, phase: String, status: String, detail: String?) =
        telemetry.instant(event, phase, status, detail)

    override fun liveInstant(event: String, phase: String, status: String, detail: String?) =
        telemetry.liveInstant(event, phase, status, detail)

    override fun <T> measured(
        event: String,
        phase: String,
        index: Long,
        batchSize: Int,
        block: () -> T,
    ): T = telemetry.measured(event, phase, index, batchSize, block)

    override fun recordInference(
        startNs: Long,
        endNs: Long,
        inferenceIndex: Long,
        batchSize: Int,
    ): Boolean = telemetry.recordInference(startNs, endNs, inferenceIndex, batchSize)

    override fun flush(
        resource: String,
        modelId: String,
        modelSha256: String,
        config: Map<String, Any?>,
    ): GpuFlushResult = telemetry.flushAfterRun(context, resource, modelId, modelSha256, config)
}

private class ProductionBenchmarkRuntime(
    private val interpreter: Interpreter,
    private val delegate: GpuDelegate?,
    override val input: ByteBuffer,
    override val output: ByteBuffer,
) : BenchmarkEngineRuntime {
    override fun runInference() = interpreter.run(input, output)
    override fun closeInterpreter() = interpreter.close()
    override fun closeDelegate() = delegate?.close() ?: Unit
}

private class ProductionBenchmarkEngineDependencies(
    private val context: Context,
) : BenchmarkEngineDependencies {
    override fun connectTelemetry(
        config: RunConfig,
    ): BenchmarkEngineTelemetry = ProductionBenchmarkTelemetry(
        context,
        GpuTelemetry.connect(
            context,
            outputDirectoryName = if (config.isDiagnosticV2) "diagnostics-v2" else "runs",
            protocolVersion = config.protocolVersion.wireValue.takeIf { config.isDiagnosticV2 },
            diagnosticSessionId = config.diagnosticSessionId,
            requestedTraceMode = config.diagnosticTraceMode.wireValue.takeIf {
                config.isDiagnosticV2
            },
        )
    )

    override fun evaluatePilotSafety(): PilotSafetyCheck =
        PilotSafetyPolicy.readAndEvaluate(context)

    override fun sleepBaseline() = Thread.sleep(GpuBenchmarkEngine.BASELINE_MS)

    override fun createRuntime(
        config: RunConfig,
        telemetry: BenchmarkEngineTelemetry,
    ): BenchmarkEngineRuntime {
        var delegate: GpuDelegate? = null
        var interpreter: Interpreter? = null
        try {
            val options = Interpreter.Options()
            when (config.normalizedResource) {
                ResourceTarget.CPU -> {
                    options.setNumThreads(checkNotNull(config.cpuThreads))
                    if (config.isDiagnosticV2) options.setUseXNNPACK(true)
                }
                ResourceTarget.GPU -> {
                    delegate = telemetry.measured("delegate_init", "setup") {
                        val compatibility = CompatibilityList()
                        check(compatibility.isDelegateSupportedOnThisDevice) {
                            "GPU delegate is not supported; GPU experiment cannot start"
                        }
                        GpuDelegate(config.gpuDelegateProfile.options())
                    }
                    options.addDelegate(checkNotNull(delegate))
                }
                ResourceTarget.CPU4 -> error("CPU4 must be normalized before execution")
                ResourceTarget.NPU -> error("NPU is reserved for a future version")
            }
            interpreter = telemetry.measured("interpreter_init", "setup") {
                Interpreter(ModelLoader.map(context), options).also { it.allocateTensors() }
            }
            val activeInterpreter = checkNotNull(interpreter)
            val inputTensor = activeInterpreter.getInputTensor(0)
            val outputTensor = activeInterpreter.getOutputTensor(0)
            check(
                inputTensor.dataType() == DataType.FLOAT32 &&
                    inputTensor.shape().contentEquals(GpuBenchmarkEngine.INPUT_SHAPE)
            ) {
                "Unexpected input tensor: ${inputTensor.dataType()} " +
                    inputTensor.shape().contentToString()
            }
            check(
                outputTensor.dataType() == DataType.FLOAT32 &&
                    outputTensor.shape().contentEquals(GpuBenchmarkEngine.OUTPUT_SHAPE)
            ) {
                "Unexpected output tensor: ${outputTensor.dataType()} " +
                    outputTensor.shape().contentToString()
            }
            val input = DeterministicInputSet.legacyTimedInput(inputTensor.numBytes())
            val output = ByteBuffer.allocateDirect(outputTensor.numBytes())
                .order(ByteOrder.nativeOrder())
            return ProductionBenchmarkRuntime(activeInterpreter, delegate, input, output)
        } catch (error: Throwable) {
            try {
                IndependentResourceCleanup.close(
                    { interpreter?.close() },
                    { delegate?.close() },
                )
            } catch (cleanupError: Throwable) {
                error.addSuppressed(cleanupError)
            }
            throw error
        }
    }

    override fun monotonicNanos(): Long = SystemClock.elapsedRealtimeNanos()
    override fun parkNanos(nanos: Long) = LockSupport.parkNanos(nanos)
    override fun captureThreadSnapshot(monoNs: Long): ProcessThreadSnapshot =
        ProcessThreadSnapshotCollector.capture(monoNs)

    override fun revalidate(
        telemetry: BenchmarkEngineTelemetry,
        checkpoint: String,
    ) {
        val productionTelemetry = telemetry as ProductionBenchmarkTelemetry
        D1RunContextClient.revalidate(context, productionTelemetry.runContext, checkpoint)
    }

    override fun capturePostLoad(
        frozenMetrics: FrozenLoadMetrics,
        output: ByteBuffer,
    ): DiagnosticPostLoadResult = ProductionPostLoadCoordinator.capture(
        frozenMetrics,
        output,
        SystemClock::elapsedRealtimeNanos,
    )

}

class GpuBenchmarkEngine private constructor(
    private val dependencies: BenchmarkEngineDependencies,
    @Suppress("UNUSED_PARAMETER") constructorMarker: Unit,
) {
    constructor(context: Context) : this(ProductionBenchmarkEngineDependencies(context), Unit)

    internal constructor(
        dependencies: BenchmarkEngineDependencies,
    ) : this(dependencies, Unit)

    fun execute(config: RunConfig): BenchmarkResult {
        check(Thread.currentThread().name == THREAD_NAME) {
            "Benchmark must run on the dedicated $THREAD_NAME thread"
        }
        val telemetry = dependencies.connectTelemetry(config)
        var runtime: BenchmarkEngineRuntime? = null
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
        var threadSnapshotBefore: ProcessThreadSnapshot? = null
        var threadSnapshotAfter: ProcessThreadSnapshot? = null
        var outputReadback: OutputReadbackEvidence? = null
        var completedWarmupCount = 0
        var actualLoadDurationNs: Long? = null
        var dutyMetrics: DutyCycleMetrics? = null
        var completedInferenceCount = 0L
        var lastInferenceEndedNs: Long? = null

        try {
            config.expectedRunId?.let { expectedRunId ->
                if (telemetry.runId != expectedRunId) {
                    throw RunContextMismatchException(
                        "run_context_mismatch checkpoint=automation_start " +
                            "expected_run=$expectedRunId actual_run=${telemetry.runId}"
                    )
                }
            }
            if (config.isAutomated) {
                pilotSafety = dependencies.evaluatePilotSafety()
                if (!checkNotNull(pilotSafety).passed) {
                    throw PilotSafetyException(
                        "pilot_safety_rejected: " +
                            checkNotNull(pilotSafety).rejectionReasons.joinToString(",")
                    )
                }
            }
            dependencies.revalidate(telemetry, "before_baseline")
            telemetry.instant("baseline_start", "baseline")
            dependencies.sleepBaseline()
            telemetry.instant("baseline_end", "baseline")

            runtime = dependencies.createRuntime(config, telemetry)
            val activeRuntime = checkNotNull(runtime)
            val input = activeRuntime.input
            val output = activeRuntime.output

            dependencies.revalidate(telemetry, "before_warmup")
            if (config.isDiagnosticV2) {
                telemetry.instant("diagnostic_warmup_start", "warmup", detail =
                    "requested_warmup_count=${config.warmupCount}")
            }
            repeat(config.warmupCount) { index ->
                resetTensorBuffers(input, output)
                telemetry.measured("warmup", "warmup", index.toLong(), 1) {
                    activeRuntime.runInference()
                }
                completedWarmupCount++
            }
            if (config.isDiagnosticV2) {
                telemetry.instant("diagnostic_warmup_end", "warmup", detail =
                    "completed_warmup_count=${config.warmupCount}")
                threadSnapshotBefore = dependencies.captureThreadSnapshot(
                    dependencies.monotonicNanos()
                )
                telemetry.instant("diagnostic_thread_snapshot_before_load", "diagnostic")
            }

            dependencies.revalidate(telemetry, "before_gpu_load")
            if (config.shouldEmitTraceMarkers) {
                telemetry.liveInstant("diagnostic_trace_start", "diagnostic")
            }
            telemetry.instant("load_start", "run")
            loadStarted = true
            val runStartedNs = dependencies.monotonicNanos()
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
                val loopNowNs = dependencies.monotonicNanos()
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
                        val idleStartedNs = dependencies.monotonicNanos()
                        dependencies.parkNanos(minOf(requestedIdleNs, remainingDurationNs))
                        val idleEndedNs = dependencies.monotonicNanos()
                        tracker.recordIdle(idleStartedNs, idleEndedNs)
                        continue
                    }
                }

                resetTensorBuffers(input, output)
                val inference = OfficialInferenceCoordinator.execute(
                    inferenceIndex,
                    dependencies::monotonicNanos,
                    activeRuntime::runInference,
                    telemetry::recordInference,
                )
                lastInferenceEndedNs = inference.endedMonoNs
                dutyCycleTracker?.recordInference(
                    inference.startedMonoNs, inference.endedMonoNs
                )
                inferenceIndex++
            }
            loadEndedNs = dependencies.monotonicNanos()
            actualLoadDurationNs = checkNotNull(runTermination).actualDurationNs(
                checkNotNull(loadEndedNs)
            )
            dutyMetrics = dutyCycleTracker?.metrics(checkNotNull(loadEndedNs))
            completedInferenceCount = inferenceIndex
            check(telemetry.inferenceCount.toLong() == completedInferenceCount) {
                "completed inference count mismatch before diagnostic readback"
            }
            telemetry.instant("load_end", "run", if (success) "ok" else "error")
            loadEnded = true
            if (config.shouldEmitTraceMarkers) {
                telemetry.liveInstant("diagnostic_trace_stop", "diagnostic")
            }
            if (config.isDiagnosticV2) {
                threadSnapshotAfter = dependencies.captureThreadSnapshot(
                    dependencies.monotonicNanos()
                )
                telemetry.instant("diagnostic_thread_snapshot_after_load", "diagnostic")
            }
            if (config.isDiagnosticV2 && completedInferenceCount > 0L) {
                outputReadback = dependencies.capturePostLoad(
                    FrozenLoadMetrics(
                        loadEndedMonoNs = checkNotNull(loadEndedNs),
                        actualLoadDurationNs = checkNotNull(actualLoadDurationNs),
                        dutyMetrics = dutyMetrics,
                        completedInferenceCount = completedInferenceCount,
                        lastInferenceEndedMonoNs = checkNotNull(lastInferenceEndedNs),
                    ),
                    output,
                ).outputReadback
            }
            dependencies.revalidate(telemetry, "after_gpu_load")
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
                loadEndedNs = dependencies.monotonicNanos()
                telemetry.instant("load_end", "run", "error")
                loadEnded = true
                actualLoadDurationNs = runTermination?.actualDurationNs(checkNotNull(loadEndedNs))
                dutyMetrics = dutyCycleTracker?.metrics(checkNotNull(loadEndedNs))
                completedInferenceCount = telemetry.inferenceCount.toLong()
                if (config.shouldEmitTraceMarkers) {
                    telemetry.liveInstant("diagnostic_trace_stop", "diagnostic", "error")
                }
            }
        } finally {
            try {
                telemetry.measured("shutdown", "shutdown") {
                    IndependentResourceCleanup.close(
                        { runtime?.closeInterpreter() },
                        { runtime?.closeDelegate() },
                    )
                }
            } catch (error: Throwable) {
                success = false
                message = "shutdown ${error.javaClass.simpleName}: ${error.message ?: ""}"
                invalidReason = invalidReason ?: "shutdown_error"
                terminationReason = terminationReason ?: TerminationReason.SHUTDOWN_ERROR
            }
        }

        try {
            dependencies.revalidate(telemetry, "before_file_flush")
        } catch (error: RunContextMismatchException) {
            success = false
            invalidReason = "run_context_mismatch"
            terminationReason = TerminationReason.RUN_CONTEXT_MISMATCH
            message = "${error.javaClass.simpleName}: ${error.message ?: ""}"
            telemetry.instant("run_context_mismatch", "validation", "error", message)
        }

        val requestedInferenceCount = (config.limit as? RunLimit.Count)?.inferenceCount
        val requestedDurationSeconds = (config.limit as? RunLimit.Duration)?.durationSeconds
        if (actualLoadDurationNs == null && loadStartedNs != null && loadEndedNs != null) {
            actualLoadDurationNs = checkNotNull(runTermination).actualDurationNs(
                checkNotNull(loadEndedNs)
            )
        }
        if (dutyMetrics == null && loadEndedNs != null) {
            dutyMetrics = dutyCycleTracker?.metrics(checkNotNull(loadEndedNs))
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
            "perfetto_requested_by_runner" to config.shouldEmitTraceMarkers,
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
        if (config.isDiagnosticV2) {
            outputConfig["protocol_version"] = config.protocolVersion.wireValue
            outputConfig["diagnostic_session_id"] = config.diagnosticSessionId
            outputConfig["diagnostic_perfetto_enabled"] = config.diagnosticPerfettoEnabled
            outputConfig["requested_trace_mode"] = config.diagnosticTraceMode.wireValue
            outputConfig["diagnostic_perfetto_started"] = config.diagnosticPerfettoStarted
            outputConfig["diagnostic_trace_filename"] = config.diagnosticTraceFilename
            outputConfig["diagnostic_trace_session_id"] = config.diagnosticSessionId
            outputConfig["diagnostic_trace_size_bytes"] = null
            outputConfig["diagnostic_trace_sha256"] = null
            outputConfig["diagnostic_trace_finalization"] = "host_logger_after_runner_flush"
            outputConfig["diagnostic_output_scope"] = "separate_external_files_diagnostics_v2"
            outputConfig["warmup_lifecycle"] = linkedMapOf(
                "requested_count" to config.warmupCount,
                "completed_count" to completedWarmupCount,
                "per_warmup_events_recorded" to true,
            )
            outputConfig["cpu_execution_profile"] = if (
                config.normalizedResource == ResourceTarget.CPU
            ) linkedMapOf(
                "requested_num_threads" to config.cpuThreads,
                "interpreter_options_set_num_threads_applied" to true,
                "xnnpack_requested" to true,
                "xnnpack_configuration_source" to "Interpreter.Options.setUseXNNPACK(true)",
                "xnnpack_runtime_enabled_observation" to "not_exposed_by_litert_java_api",
                "worker_identification" to "unknown",
                "worker_identification_reason" to
                    "public LiteRT Java API does not identify XNNPACK worker tids",
                "cpu_affinity" to "NONE",
            ) else null
            outputConfig["thread_diagnostics"] = linkedMapOf(
                "collection_scope" to "before_and_after_load_only_not_per_inference",
                "before_load" to threadSnapshotBefore?.metadata(),
                "after_load" to threadSnapshotAfter?.metadata(),
                "deltas" to ProcTaskStatParser.deltas(threadSnapshotBefore, threadSnapshotAfter),
                "comparison" to ProcTaskStatParser.comparison(
                    threadSnapshotBefore, threadSnapshotAfter
                ),
                "cpu_worker_evidence_completeness" to if (
                    threadSnapshotBefore?.status == "ok" && threadSnapshotAfter?.status == "ok"
                ) "complete" else "incomplete",
                "partial_snapshot_means_inference_failure" to false,
                "xnnpack_worker_classification" to "unknown",
            )
            outputConfig["output_readback_evidence"] = outputReadback?.metadata()
                ?: mapOf("status" to "not_observed", "reason" to "no completed inference")
            outputConfig["application_visible_timing"] = linkedMapOf(
                "clock" to "android_elapsed_realtime_nanos",
                "boundary" to "immediately_before_Interpreter.run_to_immediately_after_return",
                "checksum_in_latency" to false,
                "checksum_in_active_duration" to false,
                "checksum_in_idle_duration" to false,
                "checksum_in_achieved_duty" to false,
                "checksum_in_inference_count" to false,
                "file_io_in_latency" to false,
                "thread_snapshot_in_latency" to false,
                "component_breakdown" to "unsupported",
                "component_breakdown_reason" to
                    "LiteRT Java Interpreter.run does not expose H2D/GPU/D2H timestamps",
            )
            outputConfig["gpu_diagnostic_capabilities"] = if (
                config.normalizedResource == ResourceTarget.GPU
            ) linkedMapOf(
                "profile_id" to config.gpuDelegateProfile.profileId,
                "configuration_sha256" to config.gpuDelegateProfile.configurationSha256,
                "precision_loss_allowed" to config.gpuDelegateProfile.precisionLossAllowed,
                "force_backend" to config.gpuDelegateProfile.forceBackendName,
                "force_backend_request" to config.gpuDelegateProfile.forceBackendName,
                "actual_backend_observed" to "unknown",
                "backend_observation_source" to "host_preserved_LiteRT_logs",
                "gpu_timestamp" to "unsupported_by_public_litert_java_api",
                "gpu_fence" to "unsupported_by_public_litert_java_api",
                "gpu_utilization" to "not_collected_vendor_specific_or_privileged",
                "gpu_frequency" to
                    "host_perfetto_power_gpu_frequency_requested_device_support_required",
                "actual_fp16_execution" to "unknown_not_exposed_by_litert_api",
            ) else null
        }
        outputConfig.putAll(
            pilotSafety?.metadata() ?: mapOf(
                "safety_policy_scope" to "NONE",
                "pilot_safety_pass" to null,
                "formal_safety_limits_applied" to false,
                "matched_start_limits_applied" to false,
            )
        )
        val flush = telemetry.flush(
            resource = config.normalizedResource.name,
            modelId = ModelLoader.MODEL_ID,
            modelSha256 = ModelLoader.MODEL_SHA256,
            config = outputConfig,
        )
        return BenchmarkResult(success, message, flush)
    }

    companion object {
        const val THREAD_NAME = "d1-benchmark-runner"
        const val BASELINE_MS = 60_000L
        const val LITERT_VERSION = "1.4.2"
        internal val INPUT_SHAPE = intArrayOf(1, 224, 224, 3)
        internal val OUTPUT_SHAPE = intArrayOf(1, 1001)
    }
}
