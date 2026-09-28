package com.example.d1check.npurunner

import java.util.Locale
import java.util.UUID

/*
 * timed-run 설정과 d1_* Intent 파서.
 * 미러 원본: benchmark-runner/src/main/java/com/example/d1check/benchmarkrunner/RunConfig.kt,
 *           AutomationIntent.kt
 * 달라지는 것: resource 는 NPU 하나, cpu_threads·gpu_profile 은 받지 않는다, 모델 선택 extra 가 있다.
 * benchmark-runner 를 import 하지 않는 이유: 모듈 의존을 만들면 LiteRT 1.4.2 가 이 모듈 classpath 로
 * 들어와 LiteRT Next 2.2.0 과 충돌한다 (NPU_RUNNER_SPEC §7).
 */

internal sealed interface RunLimit {
    val modeName: String

    data class Count(val inferenceCount: Int) : RunLimit {
        override val modeName: String = "COUNT"
    }

    data class Duration(val durationSeconds: Long) : RunLimit {
        override val modeName: String = "DURATION"
    }
}

/**
 * timed run 이 CompiledModel 에 넘기는 **단 하나의** 가속기. 폴백 목록이 아니다 —
 * CPU 는 "NPU 실패 시 CPU 로 떨어지는 경로"가 아니라 처음부터 CPU 만 지정하는 별도 런이다 (엔진 대조 C5).
 * 기본값 NPU = 기존 동작 그대로.
 */
internal enum class TimedAccelerator(val wireName: String, val resourceLabel: String) {
    NPU("NPU", "npu"),
    CPU("CPU", "cpu_compiled_model"),
    // 2026-09-28 추가: CompiledModel GPU 단독 (원본 FP32 모델). NPU 폴백이 아니다
    GPU("GPU", "gpu_compiled_model");

    companion object {
        fun fromWire(value: String?): TimedAccelerator? =
            if (value == null) NPU else entries.firstOrNull { it.wireName == value.uppercase(Locale.ROOT) }
    }
}

internal enum class ExperimentMode {
    BASIC,
    DIAGNOSTIC,
}

internal data class NpuRunConfig(
    val limit: RunLimit,
    val warmupCount: Int,
    val experimentMode: ExperimentMode,
    val expectedRunId: String? = null,
    val commandId: String? = null,
    val dutyCyclePercent: Int = 100,
    val dutyCyclePeriodSeconds: Double = 10.0,
    /** assets 안 경로. modelPath 가 있으면 무시 (EfficientDet 처럼 APK 에 넣을 수 없는 모델용). */
    val modelAsset: String = DEFAULT_MODEL_ASSET,
    val modelPath: String? = null,
    /** timed 입력 규칙. 기본값은 benchmark-runner legacyTimedInput 과 비트 동일한 lcg-unit. */
    val inputSpec: NpuDeterministicInput.InputSpec = NpuDeterministicInput.InputSpec.LCG_UNIT,
    /** CompiledModel 에 넘기는 유일한 가속기. 기본 NPU (기존과 같음). */
    val accelerator: TimedAccelerator = TimedAccelerator.NPU,
    /** true 면 load 구간 run() 전용 시간 요약을 run_only_summary 이벤트로 남긴다 (opt-in, 기본 false). */
    val recordRunOnly: Boolean = false,
    // ---- 2026-09-28 추가 (셋 다 기본값이면 기존과 같은 동작)
    /** GPU 가속기의 CompiledModel.GpuOptions.precision 이름. null = GpuOptions 를 설정하지 않음 (LiteRT 기본). */
    val gpuPrecision: String? = null,
    /** GpuTelemetry.connect(maxInferenceSpans). 기본 = telemetry-contract 기본값 250,000. */
    val maxInferenceSpans: Int = DEFAULT_MAX_INFERENCE_SPANS,
    /** 연쇄 모드 구간 목록. null = 기존 단일 구간 timed run. */
    val chain: NpuChainSpec? = null,
) {
    init {
        when (limit) {
            is RunLimit.Count -> require(limit.inferenceCount in 1..MAX_INFERENCE_COUNT) {
                "inferenceCount must be 1..$MAX_INFERENCE_COUNT"
            }
            is RunLimit.Duration -> require(limit.durationSeconds in 1..MAX_DURATION_SECONDS) {
                "durationSeconds must be 1..$MAX_DURATION_SECONDS"
            }
        }
        require(warmupCount in 0..MAX_WARMUP_COUNT) {
            "warmupCount must be 0..$MAX_WARMUP_COUNT"
        }
        require((expectedRunId == null) == (commandId == null)) {
            "expectedRunId and commandId must both be present for automation"
        }
        require(dutyCyclePercent in 1..100) {
            "dutyCyclePercent must be 1..100"
        }
        require(dutyCyclePeriodSeconds.isFinite() && dutyCyclePeriodSeconds > 0.0) {
            "dutyCyclePeriodSeconds must be finite and positive"
        }
        require(modelAsset.isNotBlank() || modelPath != null) { "a model asset or path is required" }
        require(gpuPrecision == null || accelerator == TimedAccelerator.GPU) {
            "gpuPrecision is only valid with the GPU accelerator"
        }
        require(gpuPrecision == null || gpuPrecision in GPU_PRECISIONS) {
            "gpuPrecision must be one of $GPU_PRECISIONS"
        }
        require(maxInferenceSpans in 1..MAX_INFERENCE_SPANS_LIMIT) {
            "maxInferenceSpans must be 1..$MAX_INFERENCE_SPANS_LIMIT"
        }
        if (chain != null) {
            // 연쇄 모드는 구간이 가속기·모델·입력·duty·길이를 정한다. 단일 구간 옵션과 섞지 않는다 (fail closed)
            require(limit is RunLimit.Duration && limit.durationSeconds == chain.totalDurationSeconds) {
                "chain requires DURATION equal to the sum of segment durations (${chain.totalDurationSeconds} s)"
            }
            require(dutyCyclePercent == 100) { "chain sets duty per segment; d1_duty_cycle_percent must be 100" }
            require(accelerator == TimedAccelerator.NPU && gpuPrecision == null && modelPath == null) {
                "chain sets accelerator, model and GPU precision per segment"
            }
            require(inputSpec == NpuDeterministicInput.InputSpec.LCG_UNIT) { "chain sets input_spec per segment" }
            require(!recordRunOnly) { "run-only span is not supported in chain mode" }
        }
    }

    /** benchmark-runner 의 resource 자리. NPU 만 받는다. */
    val resource: String get() = RESOURCE

    /** 입력 dtype. AOT 산출물은 FP32 입력이어도 가중치가 FP16 이다 (npu_precision 에 따로 적는다). */
    val precision: String get() = "FLOAT32"

    val isAutomated: Boolean get() = commandId != null

    val modelSource: String get() = modelPath ?: modelAsset

    companion object {
        const val RESOURCE = "NPU"
        const val DEFAULT_MODEL_ASSET = "models/mobilenet_v1_1.0_224_Samsung_E9965.tflite"
        const val MAX_WARMUP_COUNT = 10_000
        const val MAX_INFERENCE_COUNT = 250_000
        const val MAX_DURATION_SECONDS = 3_600L
        /** telemetry-contract GpuTelemetry.DEFAULT_MAX_INFERENCE_SPANS 와 같은 값 (테스트로 고정). */
        const val DEFAULT_MAX_INFERENCE_SPANS = 250_000
        /**
         * 상한 옵션의 최대값. GpuEventBuffer 가 span 마다 LongArray 3 + IntArray 1 = 28 B 를 미리 잡는다
         * (telemetry-contract GpuEventBuffer.kt:19-22) → 3,000,000 × 28 B = 84 MB. 실제 허용은 기기 힙으로 한 번 더 막는다.
         */
        const val MAX_INFERENCE_SPANS_LIMIT = 3_000_000
        const val SPAN_BUFFER_BYTES = 28L
        /** CompiledModel.GpuOptions.Precision 이름 (litert-api 2.2.0 javap: DEFAULT, FP16, FP32, FP16_WITH_FP32_ACCUM). */
        val GPU_PRECISIONS = listOf("DEFAULT", "FP16", "FP32", "FP16_WITH_FP32_ACCUM")

        /** 미리 잡는 span 버퍼가 JVM 최대 힙의 40 % 를 넘으면 거부한다 (부하 중 OOM 대신 시작 전에 막는다). */
        fun spanBufferFits(maxInferenceSpans: Int, jvmMaxMemoryBytes: Long): Boolean =
            maxInferenceSpans.toLong() * SPAN_BUFFER_BYTES <= jvmMaxMemoryBytes * 4 / 10
    }
}

/** d1_* extras → NpuRunConfig. d1_auto_start 가 true 가 아니면 null (스모크/게이트 경로로 간다). */
internal object NpuAutomationIntentParser {
    const val EXTRA_AUTO_START = "d1_auto_start"
    const val EXTRA_RESOURCE = "d1_resource"
    const val EXTRA_CPU_THREADS = "d1_cpu_threads"
    const val EXTRA_LIMIT_MODE = "d1_limit_mode"
    const val EXTRA_INFERENCE_COUNT = "d1_inference_count"
    const val EXTRA_DURATION_S = "d1_duration_s"
    const val EXTRA_WARMUP_COUNT = "d1_warmup_count"
    const val EXTRA_RUN_ID = "d1_run_id"
    const val EXTRA_COMMAND_ID = "d1_command_id"
    const val EXTRA_EXPERIMENT_MODE = "d1_experiment_mode"
    const val EXTRA_DUTY_CYCLE_PERCENT = "d1_duty_cycle_percent"
    const val EXTRA_DUTY_CYCLE_PERIOD_S = "d1_duty_cycle_period_s"
    const val EXTRA_GPU_PROFILE = "d1_gpu_profile"
    // NPU 전용 (orchestrator 가 NPU 슬롯에 붙이는 것 + 선택 항목)
    const val EXTRA_NPU_MODEL_ASSET = "d1_npu_model_asset"
    const val EXTRA_NPU_MODEL_PATH = "d1_npu_model_path"
    const val EXTRA_NPU_INPUT_SPEC = "d1_npu_input_spec"
    // 2026-09-26 추가 (둘 다 없으면 기존과 같은 동작)
    const val EXTRA_NPU_ACCELERATOR = "d1_npu_accelerator"
    const val EXTRA_NPU_RUN_ONLY_SPAN = "d1_npu_run_only_span"
    // 2026-09-28 추가 (없으면 기존과 같은 동작)
    const val EXTRA_NPU_GPU_PRECISION = "d1_npu_gpu_precision"
    const val EXTRA_MAX_INFERENCE_SPANS = "d1_max_inference_spans"
    const val EXTRA_NPU_CHAIN_B64 = "d1_npu_chain_b64"
    const val EXTRA_NPU_CHAIN_SHA256 = "d1_npu_chain_sha256"

    val stringExtras = listOf(
        EXTRA_RESOURCE, EXTRA_LIMIT_MODE, EXTRA_RUN_ID, EXTRA_COMMAND_ID, EXTRA_EXPERIMENT_MODE,
        EXTRA_GPU_PROFILE, EXTRA_NPU_MODEL_ASSET, EXTRA_NPU_MODEL_PATH, EXTRA_NPU_INPUT_SPEC,
        EXTRA_NPU_ACCELERATOR, EXTRA_NPU_GPU_PRECISION, EXTRA_NPU_CHAIN_B64, EXTRA_NPU_CHAIN_SHA256,
    )
    val booleanExtras = listOf(EXTRA_NPU_RUN_ONLY_SPAN)
    val intExtras = listOf(
        EXTRA_CPU_THREADS, EXTRA_INFERENCE_COUNT, EXTRA_WARMUP_COUNT, EXTRA_DUTY_CYCLE_PERCENT,
        EXTRA_MAX_INFERENCE_SPANS,
    )

    /**
     * @param jvmMaxMemoryBytes 상한 옵션 검사용 (기본 = 이 프로세스의 Runtime.maxMemory()). 테스트가 바꿔 끼운다.
     */
    fun parse(
        extras: Map<String, Any?>,
        jvmMaxMemoryBytes: Long = Runtime.getRuntime().maxMemory(),
    ): NpuRunConfig? {
        if (extras[EXTRA_AUTO_START] != true) return null

        val resourceValue = requiredString(extras, EXTRA_RESOURCE).uppercase(Locale.ROOT)
        require(resourceValue == NpuRunConfig.RESOURCE) {
            "Unsupported d1_resource for npu-runner: $resourceValue"
        }
        require(extras[EXTRA_CPU_THREADS] == null) { "d1_cpu_threads must be omitted for NPU" }
        require(extras[EXTRA_GPU_PROFILE] == null) { "d1_gpu_profile is only valid for GPU" }
        val limitMode = (extras[EXTRA_LIMIT_MODE] as? String)
            ?.uppercase(Locale.ROOT)
            ?: "DURATION"
        val limit = when (limitMode) {
            "COUNT" -> RunLimit.Count(requiredInt(extras, EXTRA_INFERENCE_COUNT))
            "DURATION" -> RunLimit.Duration(requiredLong(extras, EXTRA_DURATION_S))
            else -> throw IllegalArgumentException("Unsupported d1_limit_mode: $limitMode")
        }
        val runId = requiredUuid(extras, EXTRA_RUN_ID)
        val commandId = requiredUuid(extras, EXTRA_COMMAND_ID)
        val experimentMode = when (
            (extras[EXTRA_EXPERIMENT_MODE] as? String)?.uppercase(Locale.ROOT) ?: "BASIC"
        ) {
            "BASIC" -> ExperimentMode.BASIC
            "DIAGNOSTIC" -> ExperimentMode.DIAGNOSTIC
            else -> throw IllegalArgumentException(
                "Unsupported d1_experiment_mode: ${extras[EXTRA_EXPERIMENT_MODE]}"
            )
        }
        val inputSpecName = extras[EXTRA_NPU_INPUT_SPEC] as? String
        val inputSpec = requireNotNull(NpuDeterministicInput.InputSpec.fromWire(inputSpecName)) {
            "Unsupported d1_npu_input_spec: $inputSpecName"
        }
        val acceleratorName = extras[EXTRA_NPU_ACCELERATOR] as? String
        val accelerator = requireNotNull(TimedAccelerator.fromWire(acceleratorName)) {
            "Unsupported d1_npu_accelerator: $acceleratorName (NPU, CPU or GPU, one accelerator only)"
        }
        val recordRunOnly = when (val value = extras[EXTRA_NPU_RUN_ONLY_SPAN]) {
            null -> false
            is Boolean -> value
            else -> throw IllegalArgumentException("$EXTRA_NPU_RUN_ONLY_SPAN must be a Boolean")
        }
        val gpuPrecision = (extras[EXTRA_NPU_GPU_PRECISION] as? String)?.uppercase(Locale.ROOT)
        val maxInferenceSpans = optionalInt(extras, EXTRA_MAX_INFERENCE_SPANS)
            ?: NpuRunConfig.DEFAULT_MAX_INFERENCE_SPANS
        require(
            extras[EXTRA_MAX_INFERENCE_SPANS] == null ||
                NpuRunConfig.spanBufferFits(maxInferenceSpans, jvmMaxMemoryBytes)
        ) {
            "d1_max_inference_spans $maxInferenceSpans x ${NpuRunConfig.SPAN_BUFFER_BYTES} B exceeds 40 % of " +
                "the JVM max heap ($jvmMaxMemoryBytes B)"
        }
        val chainB64 = extras[EXTRA_NPU_CHAIN_B64] as? String
        val chainSha = extras[EXTRA_NPU_CHAIN_SHA256] as? String
        require((chainB64 == null) == (chainSha == null)) {
            "$EXTRA_NPU_CHAIN_B64 and $EXTRA_NPU_CHAIN_SHA256 must be sent together"
        }
        val chain = chainB64?.let { NpuChainSpec.decode(it, checkNotNull(chainSha)) }
        return NpuRunConfig(
            limit = limit,
            warmupCount = optionalInt(extras, EXTRA_WARMUP_COUNT) ?: 20,
            experimentMode = experimentMode,
            expectedRunId = runId,
            commandId = commandId,
            dutyCyclePercent = optionalInt(extras, EXTRA_DUTY_CYCLE_PERCENT) ?: 100,
            dutyCyclePeriodSeconds = optionalDouble(extras, EXTRA_DUTY_CYCLE_PERIOD_S) ?: 10.0,
            modelAsset = (extras[EXTRA_NPU_MODEL_ASSET] as? String)?.takeIf { it.isNotBlank() }
                ?: NpuRunConfig.DEFAULT_MODEL_ASSET,
            modelPath = (extras[EXTRA_NPU_MODEL_PATH] as? String)?.takeIf { it.isNotBlank() },
            inputSpec = inputSpec,
            accelerator = accelerator,
            recordRunOnly = recordRunOnly,
            gpuPrecision = gpuPrecision,
            maxInferenceSpans = maxInferenceSpans,
            chain = chain,
        )
    }

    private fun requiredString(extras: Map<String, Any?>, key: String): String =
        (extras[key] as? String)?.takeIf { it.isNotBlank() }
            ?: throw IllegalArgumentException("Missing or invalid $key")

    private fun requiredUuid(extras: Map<String, Any?>, key: String): String {
        val value = requiredString(extras, key)
        return try {
            UUID.fromString(value).toString()
        } catch (error: IllegalArgumentException) {
            throw IllegalArgumentException("Invalid UUID for $key: $value", error)
        }
    }

    private fun optionalInt(extras: Map<String, Any?>, key: String): Int? = when (val value = extras[key]) {
        null -> null
        is Int -> value
        else -> throw IllegalArgumentException("$key must be an Int")
    }

    private fun requiredInt(extras: Map<String, Any?>, key: String): Int =
        optionalInt(extras, key) ?: throw IllegalArgumentException("Missing $key")

    private fun requiredLong(extras: Map<String, Any?>, key: String): Long = when (val value = extras[key]) {
        is Long -> value
        is Int -> value.toLong()
        else -> throw IllegalArgumentException("Missing or invalid $key")
    }

    private fun optionalDouble(extras: Map<String, Any?>, key: String): Double? =
        when (val value = extras[key]) {
            null -> null
            is Double -> value
            is Float -> value.toDouble()
            is Int -> value.toDouble()
            is Long -> value.toDouble()
            else -> throw IllegalArgumentException("$key must be numeric")
        }
}
