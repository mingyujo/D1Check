package com.example.d1check.npurunner

import android.content.Context
import android.os.SystemClock
import com.example.d1check.contract.D1RunContextClient
import com.example.d1check.contract.GpuTelemetry
import com.example.d1check.contract.RunContextMismatchException
import org.json.JSONObject
import java.security.MessageDigest
import java.util.Base64
import java.util.concurrent.locks.LockSupport

/*
 * 연쇄 모드 (2026-09-28 추가, P2 2단계). 한 슬롯 = 구간 목록을 한 프로세스에서 이어 실행한다.
 *   baseline 60 s (슬롯에 한 번) → 구간 0 준비·warmup → load_start
 *   → [구간 0] → (전환 1: 필요하면 모델 교체 + warmup) → [구간 1] → … → load_end
 * 구간 사이에 baseline · force-stop · 냉각 · 안전 게이트 재검사가 없다. 텔레메트리(D1Check run)는 끊기지 않는다.
 * 경계는 러너 JSONL 에 instant 로 남긴다: segment_start / segment_end, chain_transition_start / _end.
 * load_start / load_end 는 한 번씩만 낸다 — d1_logger_v4.analyze 가 정확히 하나씩을 요구한다 (d1_logger_v4.py:1057-1060).
 * 호스트 쪽 보존 검사는 tools/npu_chain.py (Σ 구간 + Σ 전환 = load 창, Σ 구간 추론 = 전체 …).
 * 이 경로는 기존 단일 구간 timed run(NpuTimedRunEngine) 과 코드를 나누지 않는다 — 기본 경로는 그대로다.
 */

internal enum class ChainModelPrepare(val wireName: String) {
    /** 가속기·모델이 바뀌는 구간 경계에서 앞 모델을 닫고 새 모델을 만든다 (전환 구간에 init 이 들어간다). */
    PER_SEGMENT("per_segment"),

    /** 슬롯 시작 때(load_start 전) 서로 다른 모델을 전부 만들어 둔다 (전환 구간에는 warmup 만 남는다). */
    UPFRONT("upfront");

    companion object {
        fun fromWire(value: String): ChainModelPrepare? = entries.firstOrNull { it.wireName == value }
    }
}

internal data class NpuChainSegment(
    val index: Int,
    val label: String?,
    val accelerator: TimedAccelerator,
    val modelAsset: String?,
    val modelPath: String?,
    val inputSpec: NpuDeterministicInput.InputSpec,
    val dutyCyclePercent: Int,
    val durationSeconds: Long,
    /** null = 슬롯의 d1_warmup_count. */
    val warmupCount: Int?,
    val gpuPrecision: String?,
) {
    val modelSource: String get() = modelPath ?: checkNotNull(modelAsset)

    /** 같은 key 면 같은 CompiledModel 을 이어 쓴다 (전환이 아니다). */
    val backendKey: String get() = "${accelerator.wireName}|$modelSource|${gpuPrecision ?: "-"}"

    fun warmup(defaultWarmup: Int): Int = warmupCount ?: defaultWarmup

    /** NpuArtifacts.read 에 넘기는 모양 (SHA·크기·AOT 파티션 계산용). */
    fun artifactConfig(): NpuRunConfig = NpuRunConfig(
        limit = RunLimit.Duration(durationSeconds),
        warmupCount = 0,
        experimentMode = ExperimentMode.BASIC,
        modelAsset = modelAsset ?: NpuRunConfig.DEFAULT_MODEL_ASSET,
        modelPath = modelPath,
    )
}

internal data class NpuChainSpec(
    val chainId: String,
    val modelPrepare: ChainModelPrepare,
    val segments: List<NpuChainSegment>,
    /** 받은 JSON 문자열 그대로 (호스트가 보낸 바이트의 UTF-8 해석). */
    val json: String,
    val sha256: String,
) {
    val totalDurationSeconds: Long get() = segments.sumOf { it.durationSeconds }

    companion object {
        const val SCHEMA = "d1-npu-chain-v1"
        const val MAX_SEGMENTS = 32
        private val ID_RE = Regex("[A-Za-z0-9_.-]{1,64}")
        private val LABEL_RE = Regex("[A-Za-z0-9_.-]{0,64}")
        private val TOP_KEYS = setOf("schema", "chain_id", "model_prepare", "segments")
        private val SEGMENT_KEYS = setOf(
            "accelerator", "model", "model_path", "input_spec", "duty", "duration_s", "warmup",
            "gpu_precision", "label",
        )
        private const val AOT_MARKER = "_Samsung_E9965"

        /** d1_npu_chain_b64 (표준 Base64, UTF-8 JSON) + d1_npu_chain_sha256 (그 바이트의 SHA-256). */
        fun decode(b64: String, sha256: String): NpuChainSpec {
            val bytes = try {
                Base64.getDecoder().decode(b64)
            } catch (error: IllegalArgumentException) {
                throw IllegalArgumentException("d1_npu_chain_b64 is not Base64", error)
            }
            val actual = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
            require(actual.equals(sha256, ignoreCase = true)) {
                "d1_npu_chain_sha256 mismatch: sent=$sha256 decoded=$actual"
            }
            return parse(String(bytes, Charsets.UTF_8), actual)
        }

        fun parse(json: String, sha256: String): NpuChainSpec {
            val root = JSONObject(json)
            unknownKeys(root, TOP_KEYS, "chain")
            require(root.optString("schema") == SCHEMA) { "chain schema must be $SCHEMA" }
            val chainId = root.optString("chain_id")
            require(ID_RE.matches(chainId)) { "chain_id must match ${ID_RE.pattern}" }
            val prepare = requireNotNull(ChainModelPrepare.fromWire(root.optString("model_prepare"))) {
                "model_prepare must be per_segment or upfront (it is recorded; no default)"
            }
            val array = root.optJSONArray("segments") ?: throw IllegalArgumentException("segments missing")
            require(array.length() in 1..MAX_SEGMENTS) { "segments must be 1..$MAX_SEGMENTS" }
            val segments = (0 until array.length()).map { index -> segment(index, array.getJSONObject(index)) }
            val total = segments.sumOf { it.durationSeconds }
            require(total in 1..NpuRunConfig.MAX_DURATION_SECONDS) {
                "sum of segment durations must be 1..${NpuRunConfig.MAX_DURATION_SECONDS} s (got $total)"
            }
            return NpuChainSpec(chainId, prepare, segments, json, sha256.lowercase())
        }

        private fun segment(index: Int, value: JSONObject): NpuChainSegment {
            unknownKeys(value, SEGMENT_KEYS, "segment $index")
            val accelerator = requireNotNull(
                TimedAccelerator.entries.firstOrNull { it.wireName == value.optString("accelerator") }
            ) { "segment $index accelerator must be NPU, CPU or GPU" }
            val asset = value.optString("model").takeIf { value.has("model") }
            val path = value.optString("model_path").takeIf { value.has("model_path") }
            require((asset == null) != (path == null)) { "segment $index needs exactly one of model / model_path" }
            asset?.let { require(it.startsWith("models/") && it.endsWith(".tflite")) { "segment $index model: $it" } }
            path?.let { require(it.startsWith("/") && it.endsWith(".tflite")) { "segment $index model_path: $it" } }
            val source = checkNotNull(path ?: asset)
            // AOT 산출물은 NPU 전용, NPU 는 AOT 산출물만 (CLAUDE.md §1-4: AOT 를 CPU/GPU 로 열지 않는다)
            require((AOT_MARKER in source) == (accelerator == TimedAccelerator.NPU)) {
                "segment $index: AOT (*$AOT_MARKER*) models are NPU-only and NPU needs an AOT model ($source)"
            }
            val spec = requireNotNull(NpuDeterministicInput.InputSpec.fromWire(value.optString("input_spec"))) {
                "segment $index input_spec"
            }
            val duty = integer(value, "duty", index)
            require(duty in 1..100) { "segment $index duty must be 1..100" }
            val duration = integer(value, "duration_s", index).toLong()
            require(duration in 1..NpuRunConfig.MAX_DURATION_SECONDS) { "segment $index duration_s" }
            val warmup = if (value.has("warmup")) integer(value, "warmup", index) else null
            require(warmup == null || warmup in 0..NpuRunConfig.MAX_WARMUP_COUNT) { "segment $index warmup" }
            val precision = value.optString("gpu_precision").takeIf { value.has("gpu_precision") }
            require(precision == null || (accelerator == TimedAccelerator.GPU && precision in NpuRunConfig.GPU_PRECISIONS)) {
                "segment $index gpu_precision is GPU-only, one of ${NpuRunConfig.GPU_PRECISIONS}"
            }
            val label = value.optString("label").takeIf { value.has("label") }
            require(label == null || LABEL_RE.matches(label)) { "segment $index label" }
            return NpuChainSegment(index, label, accelerator, asset, path, spec, duty, duration, warmup, precision)
        }

        private fun integer(value: JSONObject, key: String, index: Int): Int {
            val raw = value.opt(key)
            require(raw is Int || (raw is Long && raw in Int.MIN_VALUE..Int.MAX_VALUE)) {
                "segment $index $key must be an integer"
            }
            return (raw as Number).toInt()
        }

        private fun unknownKeys(value: JSONObject, allowed: Set<String>, where: String) {
            val unknown = value.keys().asSequence().filterNot { it in allowed }.toList()
            require(unknown.isEmpty()) { "$where has unknown keys $unknown (fail closed)" }
        }
    }
}

/** 연쇄 실행기. 단계·실패 분류·flush 는 NpuTimedRunEngine.execute 와 같고, load 루프만 구간 목록을 돈다. */
internal class NpuChainRunEngine(
    private val context: Context,
    private val backendFactory: (NpuChainSegment) -> NpuTimedBackend = { segment ->
        NpuCompiledModelBackend(context, segment.accelerator, segment.modelAsset, segment.modelPath, segment.gpuPrecision)
    },
    private val baselineMs: Long = NpuTimedRunEngine.BASELINE_MS,
    private val idle: (Long) -> Unit = { nanos -> LockSupport.parkNanos(nanos) },
    private val safety: (Context) -> PilotSafetyCheck = PilotSafetyPolicy::readAndEvaluate,
    private val artifacts: (NpuChainSegment) -> NpuArtifacts = { segment ->
        NpuArtifacts.read(context, segment.artifactConfig())
    },
) {
    private class Prepared(val backend: NpuTimedBackend, val init: NpuBackendInit, val inputElements: Int)

    fun execute(config: NpuRunConfig): NpuTimedRunResult {
        check(Thread.currentThread().name == NpuTimedRunEngine.THREAD_NAME) {
            "Benchmark must run on the dedicated ${NpuTimedRunEngine.THREAD_NAME} thread"
        }
        val chain = checkNotNull(config.chain) { "NpuChainRunEngine needs config.chain" }
        val segments = chain.segments
        val telemetry = GpuTelemetry.connect(context, config.maxInferenceSpans)
        val prepared = LinkedHashMap<String, Prepared>()
        val artifactFacts = LinkedHashMap<String, NpuArtifacts>()
        val segmentRecords = ArrayList<LinkedHashMap<String, Any?>>()
        val transitionRecords = ArrayList<LinkedHashMap<String, Any?>>()
        val inputs = HashMap<Int, Pair<FloatArray, String>>()
        var success = true
        var message = "ok"
        var invalidReason: String? = null
        var terminationReason: TerminationReason? = null
        var pilotSafety: PilotSafetyCheck? = null
        var loadStarted = false
        var loadEnded = false
        var loadStartedNs: Long? = null
        var loadEndedNs: Long? = null
        val periodNs = DutyCycleTracker.periodNanos(config.dutyCyclePeriodSeconds)

        fun prepare(segment: NpuChainSegment, stage: String): Prepared {
            prepared[segment.backendKey]?.let { return it }
            val backend = backendFactory(segment)
            // 먼저 등록해야 init 이 실패해도 finally 에서 close 한다
            val placeholder = Prepared(backend, NpuBackendInit(0, 0, 0, ""), 0)
            prepared[segment.backendKey] = placeholder
            val init = telemetry.measured("chain_model_init", stage, segment.index.toLong()) { backend.init() }
            val ready = Prepared(backend, init, backend.inputElementCount())
            prepared[segment.backendKey] = ready
            return ready
        }

        fun release(key: String) {
            prepared.remove(key)?.let { old ->
                telemetry.measured("chain_model_close", "chain") { old.backend.close() }
            }
        }

        fun input(segment: NpuChainSegment, ready: Prepared): FloatArray =
            inputs.getOrPut(segment.index) {
                val value = NpuDeterministicInput.inputSet(segment.inputSpec, 1, ready.inputElements)[0]
                value to NpuDeterministicInput.sha256(value)
            }.first

        fun warmup(segment: NpuChainSegment, ready: Prepared) {
            val data = input(segment, ready)
            repeat(segment.warmup(config.warmupCount)) { index ->
                telemetry.measured("warmup", "warmup", index.toLong(), 1) { ready.backend.infer(data) }
            }
        }

        try {
            config.expectedRunId?.let { expectedRunId ->
                if (telemetry.run.runId != expectedRunId) {
                    throw RunContextMismatchException(
                        "run_context_mismatch checkpoint=automation_start " +
                            "expected_run=$expectedRunId actual_run=${telemetry.run.runId}"
                    )
                }
            }
            // 안전 게이트는 슬롯 시작 때 한 번만 (구간 사이에 BAT 35 ℃ 시작 게이트가 걸리지 않는다)
            if (config.isAutomated) {
                pilotSafety = safety(context)
                if (!checkNotNull(pilotSafety).passed) {
                    throw PilotSafetyException(
                        "pilot_safety_rejected: " + checkNotNull(pilotSafety).rejectionReasons.joinToString(",")
                    )
                }
            }
            revalidate(telemetry, "before_baseline")
            telemetry.instant("baseline_start", "baseline")
            Thread.sleep(baselineMs)
            telemetry.instant("baseline_end", "baseline")

            for (segment in segments) {
                if (segment.modelSource !in artifactFacts) {
                    artifactFacts[segment.modelSource] =
                        telemetry.measured("npu_artifact_hash", "setup") { artifacts(segment) }
                }
            }
            if (chain.modelPrepare == ChainModelPrepare.UPFRONT) {
                for (segment in segments) prepare(segment, "setup")
            }
            // 구간 0 준비·warmup 은 load_start 전 (단일 구간 timed run 의 init → warmup → load_start 와 같다)
            val first = prepare(segments[0], "setup")
            warmup(segments[0], first)

            revalidate(telemetry, "before_npu_load")
            telemetry.instant("load_start", "run")
            loadStarted = true
            loadStartedNs = SystemClock.elapsedRealtimeNanos()
            var inferenceIndex = 0L

            for (segment in segments) {
                if (segment.index > 0) {
                    val previous = segments[segment.index - 1]
                    val transitionStartNs = SystemClock.elapsedRealtimeNanos()
                    val switching = previous.backendKey != segment.backendKey
                    telemetry.instant(
                        "chain_transition_start", "chain", "ok",
                        JSONObject()
                            .put("to_segment", segment.index)
                            .put("from_accelerator", previous.accelerator.wireName)
                            .put("to_accelerator", segment.accelerator.wireName)
                            .put("backend_switch", switching)
                            .put("model_prepare", chain.modelPrepare.wireName)
                            .put("start_ns", transitionStartNs)
                            .toString(),
                    )
                    // D1Check run 확인도 전환 창 안에서 한다 (구간 창 사이에 셈하지 않는 틈을 만들지 않는다)
                    revalidate(telemetry, "before_segment_${segment.index}")
                    var initialized = false
                    if (switching && chain.modelPrepare == ChainModelPrepare.PER_SEGMENT) {
                        release(previous.backendKey)
                        initialized = true
                    }
                    val ready = prepare(segment, "chain")
                    warmup(segment, ready)
                    val transitionEndNs = SystemClock.elapsedRealtimeNanos()
                    val record = linkedMapOf<String, Any?>(
                        "to_segment" to segment.index,
                        "from_accelerator" to previous.accelerator.wireName,
                        "to_accelerator" to segment.accelerator.wireName,
                        "backend_switch" to switching,
                        "model_initialized" to initialized,
                        "warmup_count" to segment.warmup(config.warmupCount),
                        "start_ns" to transitionStartNs,
                        "end_ns" to transitionEndNs,
                        "duration_ns" to (transitionEndNs - transitionStartNs),
                    )
                    if (initialized) {
                        record["env_init_ns"] = ready.init.envInitNs
                        record["model_init_ns"] = ready.init.modelInitNs
                        record["buffer_init_ns"] = ready.init.bufferInitNs
                    }
                    transitionRecords += record
                    telemetry.instant("chain_transition_end", "chain", "ok", JSONObject(record as Map<*, *>).toString())
                }

                val ready = checkNotNull(prepared[segment.backendKey])
                val data = input(segment, ready)
                val firstIndex = inferenceIndex
                val segmentStartNs = SystemClock.elapsedRealtimeNanos()
                telemetry.instant(
                    "segment_start", "chain", "ok",
                    JSONObject()
                        .put("index", segment.index)
                        .put("label", segment.label ?: JSONObject.NULL)
                        .put("accelerator", segment.accelerator.wireName)
                        .put("model", segment.modelSource)
                        .put("input_spec", segment.inputSpec.wireName)
                        .put("duty", segment.dutyCyclePercent)
                        .put("duration_s", segment.durationSeconds)
                        .put("first_inference_index", firstIndex)
                        .put("start_ns", segmentStartNs)
                        .toString(),
                )
                val termination = RunTermination(RunLimit.Duration(segment.durationSeconds), segmentStartNs)
                val targetNs = checkNotNull(termination.targetDurationNs)
                val tracker = DutyCycleTracker(segment.dutyCyclePercent, periodNs, segmentStartNs, targetNs)
                var segmentReason: TerminationReason? = null
                while (true) {
                    val loopNowNs = SystemClock.elapsedRealtimeNanos()
                    val completed = termination.completionReason(loopNowNs, inferenceIndex - firstIndex)
                    if (completed != null) {
                        segmentReason = completed
                        break
                    }
                    if (!telemetry.hasInferenceCapacity) {
                        success = false
                        message = "buffer_limit"
                        invalidReason = "buffer_limit"
                        segmentReason = TerminationReason.BUFFER_LIMIT
                        telemetry.instant("buffer_limit", "run", "error", "max=${config.maxInferenceSpans}")
                        break
                    }
                    val requestedIdleNs = tracker.nanosUntilActive(loopNowNs)
                    if (requestedIdleNs > 0L) {
                        val remainingNs = (targetNs - (loopNowNs - segmentStartNs)).coerceAtLeast(0L)
                        val idleStartedNs = SystemClock.elapsedRealtimeNanos()
                        idle(minOf(requestedIdleNs, remainingNs))
                        tracker.recordIdle(idleStartedNs, SystemClock.elapsedRealtimeNanos())
                        continue
                    }
                    val startNs = SystemClock.elapsedRealtimeNanos()
                    ready.backend.infer(data)
                    val endNs = SystemClock.elapsedRealtimeNanos()
                    tracker.recordInference(startNs, endNs)
                    check(telemetry.recordInference(startNs, endNs, inferenceIndex, 1))
                    inferenceIndex++
                }
                val segmentEndNs = SystemClock.elapsedRealtimeNanos()
                val duty = tracker.metrics(segmentEndNs)
                val record = linkedMapOf<String, Any?>(
                    "index" to segment.index,
                    "label" to segment.label,
                    "accelerator" to segment.accelerator.wireName,
                    "model" to segment.modelSource,
                    "model_sha256" to artifactFacts[segment.modelSource]?.modelSha256,
                    "input_spec" to segment.inputSpec.wireName,
                    "input_elements" to ready.inputElements,
                    "input_sha256" to inputs[segment.index]?.second,
                    "gpu_precision" to segment.gpuPrecision,
                    "requested_duty_cycle_percent" to segment.dutyCyclePercent,
                    "requested_duration_s" to segment.durationSeconds,
                    "warmup_count" to segment.warmup(config.warmupCount),
                    "start_ns" to segmentStartNs,
                    "end_ns" to segmentEndNs,
                    "target_duration_ns" to targetNs,
                    "actual_duration_ns" to termination.actualDurationNs(segmentEndNs),
                    "duration_overrun_ns" to termination.durationOverrunNs(segmentEndNs),
                    "first_inference_index" to firstIndex,
                    "inference_count" to (inferenceIndex - firstIndex),
                    "target_active_duration_ns" to duty.targetActiveDurationNs,
                    "actual_active_duration_ns" to duty.actualActiveDurationNs,
                    "actual_idle_duration_ns" to duty.actualIdleDurationNs,
                    "achieved_duty_cycle_percent" to duty.achievedPercent,
                    "completed_duty_cycle_count" to duty.completedCycleCount,
                    "duty_cycle_active_overrun_ns" to duty.activeOverrunNs,
                    "termination_reason" to checkNotNull(segmentReason).wireName,
                    "compiled_model_options" to CompiledModelFacts.optionsRecord(segment.accelerator, segment.gpuPrecision),
                    "env_init_ns" to ready.init.envInitNs,
                    "model_init_ns" to ready.init.modelInitNs,
                    "buffer_init_ns" to ready.init.bufferInitNs,
                    "available_accelerators" to ready.init.availableAccelerators,
                )
                segmentRecords += record
                telemetry.instant(
                    "segment_end", "chain", if (segmentReason == TerminationReason.DURATION_COMPLETE) "ok" else "error",
                    JSONObject(record.filterKeys { it != "compiled_model_options" } as Map<*, *>).toString(),
                )
                if (segmentReason != TerminationReason.DURATION_COMPLETE) {
                    terminationReason = segmentReason
                    break
                }
            }
            if (terminationReason == null) terminationReason = TerminationReason.DURATION_COMPLETE
            loadEndedNs = SystemClock.elapsedRealtimeNanos()
            telemetry.instant("load_end", "run", if (success) "ok" else "error")
            loadEnded = true
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
            }
        } finally {
            try {
                telemetry.measured("shutdown", "shutdown") {
                    prepared.values.forEach { it.backend.close() }
                    prepared.clear()
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

        val firstSegment = segments[0]
        val firstFacts = artifactFacts[firstSegment.modelSource]
        val firstPrepared = segmentRecords.firstOrNull()
        val metadata = NpuRunMetadata.build(
            config = config,
            outcome = NpuRunMetadata.LoadOutcome(
                terminationReason = terminationReason,
                targetDurationNs = chain.totalDurationSeconds * 1_000_000_000L,
                actualLoadDurationNs = if (loadStartedNs != null && loadEndedNs != null) {
                    (checkNotNull(loadEndedNs) - checkNotNull(loadStartedNs)).coerceAtLeast(0L)
                } else {
                    null
                },
                durationOverrunNs = if (segmentRecords.isEmpty()) null
                else segmentRecords.sumOf { (it["duration_overrun_ns"] as Long?) ?: 0L },
                dutyMetrics = null,
                completedInferenceCount = telemetry.inferenceCount,
                runnerSessionId = telemetry.runnerSessionId,
                lifecycleEventCount = telemetry.lifecycleCount,
                experimentValid = success && invalidReason == null,
                invalidReason = invalidReason,
            ),
            pilotSafety = pilotSafety,
            facts = NpuRunMetadata.NpuFacts(
                modelId = firstFacts?.modelId ?: NpuArtifacts.modelIdOf(firstSegment.modelSource),
                modelSha256 = firstFacts?.modelSha256 ?: NpuTimedRunEngine.UNAVAILABLE,
                modelSource = firstSegment.modelSource,
                dispatchLibSha256 = firstFacts?.dispatchLibSha256,
                aotPartition = firstFacts?.aotPartition,
                availableAccelerators = firstPrepared?.get("available_accelerators") as String?,
                envInitMs = null,
                modelInitMs = null,
                bufferInitMs = null,
                inputSpec = firstSegment.inputSpec,
                inputElements = firstPrepared?.get("input_elements") as Int?,
                inputSha256 = firstPrepared?.get("input_sha256") as String?,
                modelSizeBytes = firstFacts?.modelSizeBytes,
                jvmMaxMemoryBytes = Runtime.getRuntime().maxMemory(),
            ),
        )
        NpuChainMetadata.apply(
            metadata, chain, segmentRecords, transitionRecords, artifactFacts,
            loadStartedNs, loadEndedNs,
        )
        val flush = telemetry.flushAfterRun(
            context = context,
            resource = config.resource,
            modelId = firstFacts?.modelId ?: NpuArtifacts.modelIdOf(firstSegment.modelSource),
            modelSha256 = firstFacts?.modelSha256 ?: NpuTimedRunEngine.UNAVAILABLE,
            config = metadata,
        )
        return NpuTimedRunResult(success, message, flush)
    }

    private fun revalidate(telemetry: GpuTelemetry, checkpoint: String) {
        D1RunContextClient.revalidate(context, telemetry.run, checkpoint)
    }
}

/** 연쇄 런의 run_metadata 덧붙이기. 순수 함수라 JVM 테스트로 고정한다. */
internal object NpuChainMetadata {
    const val RESOURCE_LABEL = "chain_compiled_model"

    fun apply(
        metadata: LinkedHashMap<String, Any?>,
        chain: NpuChainSpec,
        segments: List<Map<String, Any?>>,
        transitions: List<Map<String, Any?>>,
        artifacts: Map<String, NpuArtifacts>,
        loadStartedNs: Long?,
        loadEndedNs: Long?,
    ) {
        // 단일 구간 전제의 키는 사실대로 다시 적는다 (자리는 그대로, 값은 구간별 → chain_segments)
        metadata["requested_duty_cycle_percent"] = null
        fun sum(key: String): Long? = if (segments.isEmpty()) null else segments.sumOf { (it[key] as Number).toLong() }
        metadata["target_active_duration_ns"] = sum("target_active_duration_ns")
        metadata["actual_active_duration_ns"] = sum("actual_active_duration_ns")
        metadata["actual_idle_duration_ns"] = sum("actual_idle_duration_ns")
        val segmentNs = sum("actual_duration_ns")
        val active = metadata["actual_active_duration_ns"] as Long?
        metadata["achieved_duty_cycle_percent"] =
            if (segmentNs == null || active == null || segmentNs == 0L) null else active * 100.0 / segmentNs
        metadata["completed_duty_cycle_count"] = sum("completed_duty_cycle_count")
        metadata["duty_cycle_active_overrun_ns"] = sum("duty_cycle_active_overrun_ns")
        metadata["npu_accelerator_requested"] = "PER_SEGMENT"
        metadata["npu_compile_mode"] = "per_segment (see chain_segments)"
        metadata["npu_precision"] = "per_segment (see chain_segments[].precision_record)"
        metadata["npu_input_spec"] = "per_segment"
        metadata["npu_timed_resource_label"] = RESOURCE_LABEL
        val transitionNs = transitions.sumOf { (it["duration_ns"] as Number).toLong() }
        metadata.putAll(linkedMapOf(
            "chain_mode" to true,
            "chain_schema" to NpuChainSpec.SCHEMA,
            "chain_id" to chain.chainId,
            "chain_sha256" to chain.sha256,
            "chain_spec" to JSONObject(chain.json),
            "chain_model_prepare" to chain.modelPrepare.wireName,
            "chain_segment_count" to chain.segments.size,
            "chain_segments_completed" to segments.size,
            "chain_requested_duration_s" to chain.totalDurationSeconds,
            "chain_load_window_ns" to if (loadStartedNs != null && loadEndedNs != null) loadEndedNs - loadStartedNs else null,
            "chain_segment_total_ns" to segmentNs,
            "chain_transition_total_ns" to transitionNs,
            "chain_duty_scope" to "duty keys above are sums over segment windows; per-segment values in chain_segments",
            "chain_segments" to segments.map { record ->
                val index = (record["index"] as Number).toInt()
                val segment = chain.segments[index]
                LinkedHashMap(record).apply {
                    put("model_partition", artifacts[segment.modelSource]?.aotPartition)
                    put("precision_record", CompiledModelFacts.precisionRecord(segment.accelerator, segment.gpuPrecision))
                }
            },
            "chain_transitions" to transitions,
            "chain_safety_gate" to "slot start only (no pilot safety re-check between segments)",
        ))
    }
}
