package com.example.d1check.npurunner

import android.content.Context
import android.os.SystemClock
import com.example.d1check.contract.D1RunContextClient
import com.example.d1check.contract.GpuFlushResult
import com.example.d1check.contract.GpuTelemetry
import com.example.d1check.contract.RunContextMismatchException
import com.google.ai.edge.litert.Accelerator
import com.google.ai.edge.litert.CompiledModel
import org.json.JSONObject
import java.io.File
import java.io.InputStream
import java.security.MessageDigest
import java.util.concurrent.locks.LockSupport

/*
 * timed run (d1_auto_start) 실행기.
 * 미러 원본: benchmark-runner/.../GpuBenchmarkEngine.kt execute() — 단계·이벤트 이름·실패 분류가 같다:
 *   run context 확인 → pilot safety → baseline 60 s → 초기화 → warmup → load_start → duty 루프
 *   → load_end → shutdown → flushAfterRun (run_metadata 첫 줄 … file_summary 끝 줄, logcat D1GPU)
 * 달라지는 것: 엔진(Interpreter → CompiledModel, NPU 단독), 초기화 이벤트 이름(compiled_model_init),
 *   NPU 사실(모델·dispatch SHA, AOT 파티션, init span)을 run_metadata 에 추가.
 * JSONL 직렬화는 telemetry-contract 의 GpuTelemetry 를 그대로 쓴다 (수정 없이 의존, SPEC §2.1).
 */

/** 추론 백엔드. 운영은 CompiledModel(NPU 단독), 라운드트립 테스트는 가짜로 바꿔 끼운다. */
internal interface NpuTimedBackend : AutoCloseable {
    /** Environment + CompiledModel + 버퍼. 예외는 그대로 던진다 (폴백 없음). */
    fun init(): NpuBackendInit

    fun inputElementCount(): Int

    /** 1회 추론 = write + run + read. 이 호출 전체가 inference span 이다. */
    fun infer(input: FloatArray)

    /**
     * 직전 infer() 안의 CompiledModel.run() 만의 ns (write/read 제외). 모르면 null.
     * 2026-09-26 추가 — 기본 구현이 null 이라 기존 백엔드·테스트 가짜는 그대로 컴파일된다.
     */
    fun lastRunOnlyNs(): Long? = null
}

internal data class NpuBackendInit(
    val envInitNs: Long,
    val modelInitNs: Long,
    val bufferInitNs: Long,
    val availableAccelerators: String,
)

/**
 * 운영 백엔드: NpuBenchmarkEngine(CompiledModel.Options(<가속기 하나>)) 한 겹.
 * 가속기는 config.accelerator 하나뿐이다 — 기본 NPU. CPU 는 폴백이 아니라 처음부터 CPU 단독인 별도 런 (C5).
 */
internal class NpuCompiledModelBackend(
    context: Context,
    accelerator: TimedAccelerator,
    modelAsset: String?,
    modelPath: String?,
    gpuPrecision: String? = null,
) : NpuTimedBackend {
    /** 기존 단일 구간 timed run 경로 (기본값이면 2026-09-26 판과 같은 엔진 인자). */
    constructor(context: Context, config: NpuRunConfig) : this(
        context = context,
        accelerator = config.accelerator,
        modelAsset = config.modelAsset.takeIf { config.modelPath == null },
        modelPath = config.modelPath,
        gpuPrecision = config.gpuPrecision,
    )

    private var runOnlyNs: Long? = null
    private val engine = NpuBenchmarkEngine(
        context = context,
        accelerator = when (accelerator) {
            TimedAccelerator.NPU -> Accelerator.NPU
            TimedAccelerator.CPU -> Accelerator.CPU
            TimedAccelerator.GPU -> Accelerator.GPU
        },
        modelAssetPath = modelAsset,
        modelFilePath = modelPath,
        gpuPrecision = gpuPrecision?.let { CompiledModel.GpuOptions.Precision.valueOf(it) },
    )

    override fun init(): NpuBackendInit {
        val spans = engine.init()
        return NpuBackendInit(
            envInitNs = spans.envInitNs,
            modelInitNs = spans.modelInitNs,
            bufferInitNs = spans.bufferInitNs,
            availableAccelerators = spans.availableAccelerators.joinToString(",") { it.name },
        )
    }

    override fun inputElementCount(): Int = engine.inputElementCount(useFloat = true)

    override fun infer(input: FloatArray) {
        runOnlyNs = engine.runFloat(input).first.runOnlyNs
    }

    override fun lastRunOnlyNs(): Long? = runOnlyNs

    override fun close() = engine.close()
}

internal data class NpuTimedRunResult(
    val success: Boolean,
    val message: String,
    val flushResult: GpuFlushResult?,
)

internal class NpuTimedRunEngine(
    private val context: Context,
    private val backendFactory: (NpuRunConfig) -> NpuTimedBackend =
        { config -> NpuCompiledModelBackend(context, config) },
    private val baselineMs: Long = BASELINE_MS,
    private val idle: (Long) -> Unit = { nanos -> LockSupport.parkNanos(nanos) },
    private val safety: (Context) -> PilotSafetyCheck = PilotSafetyPolicy::readAndEvaluate,
    private val artifacts: (NpuRunConfig) -> NpuArtifacts = { config -> NpuArtifacts.read(context, config) },
) {
    fun execute(config: NpuRunConfig): NpuTimedRunResult {
        check(Thread.currentThread().name == THREAD_NAME) {
            "Benchmark must run on the dedicated $THREAD_NAME thread"
        }
        // maxInferenceSpans 기본값 = GpuTelemetry.DEFAULT_MAX_INFERENCE_SPANS (기존 connect(context) 와 같음)
        val telemetry = GpuTelemetry.connect(context, config.maxInferenceSpans)
        var backend: NpuTimedBackend? = null
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
        var artifactFacts: NpuArtifacts? = null
        var backendInit: NpuBackendInit? = null
        var inputElements: Int? = null
        var inputSha256: String? = null

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
                pilotSafety = safety(context)
                if (!checkNotNull(pilotSafety).passed) {
                    throw PilotSafetyException(
                        "pilot_safety_rejected: " +
                            checkNotNull(pilotSafety).rejectionReasons.joinToString(",")
                    )
                }
            }
            revalidate(telemetry, "before_baseline")
            telemetry.instant("baseline_start", "baseline")
            Thread.sleep(baselineMs)
            telemetry.instant("baseline_end", "baseline")

            // 모델·dispatch SHA 와 AOT 파티션: 부하 전, 한 번만 (benchmark-runner 는 ModelLoader 상수)
            artifactFacts = telemetry.measured("npu_artifact_hash", "setup") { artifacts(config) }
            // 먼저 만들어 backend 에 담아야 init 이 실패해도 finally 의 shutdown 이 close 한다
            val activeBackend = backendFactory(config)
            backend = activeBackend
            backendInit = telemetry.measured("compiled_model_init", "setup") { activeBackend.init() }
            inputElements = activeBackend.inputElementCount()
            val input = NpuDeterministicInput.inputSet(config.inputSpec, 1, checkNotNull(inputElements))[0]
            inputSha256 = NpuDeterministicInput.sha256(input)

            revalidate(telemetry, "before_warmup")
            repeat(config.warmupCount) { index ->
                telemetry.measured("warmup", "warmup", index.toLong(), 1) {
                    activeBackend.infer(input)
                }
            }

            revalidate(telemetry, "before_npu_load")
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
            // opt-in: run() 전용 시간. 측정 창(startNs..endNs) 밖에서 저장만 한다
            val runOnly = if (config.recordRunOnly) RunOnlyRecorder() else null
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
                        "max=${config.maxInferenceSpans}")
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
                        idle(minOf(requestedIdleNs, remainingDurationNs))
                        val idleEndedNs = SystemClock.elapsedRealtimeNanos()
                        tracker.recordIdle(idleStartedNs, idleEndedNs)
                        continue
                    }
                }

                val startNs = SystemClock.elapsedRealtimeNanos()
                activeBackend.infer(input)
                val endNs = SystemClock.elapsedRealtimeNanos()
                dutyCycleTracker?.recordInference(startNs, endNs)
                check(telemetry.recordInference(startNs, endNs, inferenceIndex, 1))
                runOnly?.add(activeBackend.lastRunOnlyNs())
                inferenceIndex++
            }
            loadEndedNs = SystemClock.elapsedRealtimeNanos()
            telemetry.instant("load_end", "run", if (success) "ok" else "error")
            loadEnded = true
            runOnly?.let { telemetry.instant("run_only_summary", "run", "ok", it.detailJson()) }
            if (config.experimentMode == ExperimentMode.DIAGNOSTIC) {
                telemetry.liveInstant("diagnostic_trace_stop", "diagnostic")
            }
            revalidate(telemetry, "after_npu_load")
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
                    backend?.close()
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

        val facts = artifactFacts
        val metadata = NpuRunMetadata.build(
            config = config,
            outcome = NpuRunMetadata.LoadOutcome(
                terminationReason = terminationReason,
                targetDurationNs = runTermination?.targetDurationNs,
                actualLoadDurationNs = if (loadStartedNs != null && loadEndedNs != null) {
                    checkNotNull(runTermination).actualDurationNs(checkNotNull(loadEndedNs))
                } else {
                    null
                },
                durationOverrunNs = loadEndedNs?.let { runTermination?.durationOverrunNs(it) },
                dutyMetrics = loadEndedNs?.let { dutyCycleTracker?.metrics(it) },
                completedInferenceCount = telemetry.inferenceCount,
                runnerSessionId = telemetry.runnerSessionId,
                lifecycleEventCount = telemetry.lifecycleCount,
                experimentValid = success && invalidReason == null,
                invalidReason = invalidReason,
            ),
            pilotSafety = pilotSafety,
            facts = NpuRunMetadata.NpuFacts(
                modelId = facts?.modelId ?: NpuArtifacts.modelIdOf(config.modelSource),
                modelSha256 = facts?.modelSha256 ?: UNAVAILABLE,
                modelSource = config.modelSource,
                dispatchLibSha256 = facts?.dispatchLibSha256,
                aotPartition = facts?.aotPartition,
                availableAccelerators = backendInit?.availableAccelerators,
                envInitMs = backendInit?.envInitNs?.let(::nanosToMs),
                modelInitMs = backendInit?.modelInitNs?.let(::nanosToMs),
                bufferInitMs = backendInit?.bufferInitNs?.let(::nanosToMs),
                inputSpec = config.inputSpec,
                inputElements = inputElements,
                inputSha256 = inputSha256,
                modelSizeBytes = facts?.modelSizeBytes,
                jvmMaxMemoryBytes = Runtime.getRuntime().maxMemory(),
            ),
        )
        val flush = telemetry.flushAfterRun(
            context = context,
            resource = config.resource,
            modelId = facts?.modelId ?: NpuArtifacts.modelIdOf(config.modelSource),
            modelSha256 = facts?.modelSha256 ?: UNAVAILABLE,
            config = metadata,
        )
        return NpuTimedRunResult(success, message, flush)
    }

    private fun revalidate(telemetry: GpuTelemetry, checkpoint: String) {
        D1RunContextClient.revalidate(context, telemetry.run, checkpoint)
    }

    companion object {
        const val THREAD_NAME = "d1-npu-runner"
        const val BASELINE_MS = 60_000L
        const val UNAVAILABLE = "unavailable"

        private fun nanosToMs(ns: Long): Double = Math.round(ns / 1_000.0) / 1_000.0
    }
}

/**
 * load 구간 run()-only ns 요약 (C4). 기존 inference 이벤트의 latency 는 그대로 write+run+read 다.
 * telemetry-contract 의 inference 레코드에는 추가 필드를 넣을 수 없어 요약 1개 이벤트로 남긴다.
 */
internal class RunOnlyRecorder {
    private var values = LongArray(1024)
    private var size = 0
    private var missing = 0L

    fun add(value: Long?) {
        if (value == null) {
            missing++
            return
        }
        if (size == values.size) values = values.copyOf(values.size * 2)
        values[size++] = value
    }

    fun detailJson(): String {
        val sorted = values.copyOf(size).also { it.sort() }
        fun rank(q: Double): Long? =
            if (size == 0) null else sorted[(Math.ceil(q * size).toInt() - 1).coerceIn(0, size - 1)]
        val mean = if (size == 0) null else sorted.sum().toDouble() / size
        return "{\"span\":\"CompiledModel.run() only (excludes writeFloat/readFloat)\"," +
            "\"count\":$size,\"missing\":$missing,\"median_ns\":${rank(0.5)},\"p95_ns\":${rank(0.95)}," +
            "\"min_ns\":${sorted.firstOrNull()},\"max_ns\":${sorted.lastOrNull()},\"mean_ns\":$mean}"
    }
}

/** 실행한 모델·dispatch 의 SHA 와 AOT 파티션. formal_npu_valid 4·5·6번이 이 값을 대조한다. */
internal data class NpuArtifacts(
    val modelId: String,
    val modelSha256: String,
    val dispatchLibSha256: String?,
    val aotPartition: Map<String, Any?>?,
    /** 모델 파일 바이트 수 (2026-09-26 추가, 기본값 null 이라 기존 생성 코드는 그대로). */
    val modelSizeBytes: Long? = null,
) {
    companion object {
        const val AOT_MANIFEST_ASSET = "models/aot_manifest.json"

        fun read(context: Context, config: NpuRunConfig): NpuArtifacts {
            val modelSha = (config.modelPath?.let { File(it).inputStream() }
                ?: context.assets.open(config.modelAsset)).use(::sha256)
            val modelSize = (config.modelPath?.let { File(it).inputStream() }
                ?: context.assets.open(config.modelAsset)).use { input ->
                val buffer = ByteArray(1 shl 16)
                var total = 0L
                while (true) {
                    val n = input.read(buffer)
                    if (n < 0) break
                    total += n
                }
                total
            }
            val dispatch = File(context.applicationInfo.nativeLibraryDir, NpuRunMetadata.DISPATCH_LIB_FILE)
            val manifest = runCatching {
                context.assets.open(AOT_MANIFEST_ASSET).bufferedReader().use { it.readText() }
            }.getOrNull()
            return NpuArtifacts(
                modelId = modelIdOf(config.modelSource),
                modelSha256 = modelSha,
                dispatchLibSha256 = dispatch.takeIf { it.isFile }?.inputStream()?.use(::sha256),
                aotPartition = manifest?.let { aotPartitionFor(it, modelSha) },
                modelSizeBytes = modelSize,
            )
        }

        fun modelIdOf(source: String): String = File(source).name.removeSuffix(".tflite")

        fun sha256(input: InputStream): String {
            val digest = MessageDigest.getInstance("SHA-256")
            val buffer = ByteArray(1 shl 16)
            while (true) {
                val n = input.read(buffer)
                if (n < 0) break
                digest.update(buffer, 0, n)
            }
            return digest.digest().joinToString("") { "%02x".format(it) }
        }

        /** 병합 manifest(npu-runner-aot-manifest-merged-v1)에서 출력 SHA 가 같은 항목을 찾는다. */
        fun aotPartitionFor(manifestJson: String, modelSha256: String): Map<String, Any?>? {
            val models = JSONObject(manifestJson).optJSONArray("models") ?: return null
            for (m in 0 until models.length()) {
                val model = models.getJSONObject(m)
                val outputs = model.optJSONArray("outputs") ?: continue
                for (o in 0 until outputs.length()) {
                    val output = outputs.getJSONObject(o)
                    if (output.optString("sha256").equals(modelSha256, ignoreCase = true)) {
                        return linkedMapOf(
                            "dispatch_ops" to output.optInt("dispatch_ops"),
                            "non_dispatch_ops" to output.optInt("non_dispatch_ops"),
                            "verdict" to output.optString("verdict"),
                            "compile_batch" to model.optString("compile_batch").ifEmpty { null },
                            "ai_edge_litert" to model.optString("ai_edge_litert").ifEmpty { null },
                        )
                    }
                }
            }
            return null
        }
    }
}
