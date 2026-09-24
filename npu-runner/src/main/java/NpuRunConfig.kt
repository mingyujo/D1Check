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

    val stringExtras = listOf(
        EXTRA_RESOURCE, EXTRA_LIMIT_MODE, EXTRA_RUN_ID, EXTRA_COMMAND_ID, EXTRA_EXPERIMENT_MODE,
        EXTRA_GPU_PROFILE, EXTRA_NPU_MODEL_ASSET, EXTRA_NPU_MODEL_PATH, EXTRA_NPU_INPUT_SPEC,
    )
    val intExtras = listOf(
        EXTRA_CPU_THREADS, EXTRA_INFERENCE_COUNT, EXTRA_WARMUP_COUNT, EXTRA_DUTY_CYCLE_PERCENT,
    )

    fun parse(extras: Map<String, Any?>): NpuRunConfig? {
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
