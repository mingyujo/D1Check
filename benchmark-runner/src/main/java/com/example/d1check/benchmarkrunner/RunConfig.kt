package com.example.d1check.benchmarkrunner

enum class ResourceTarget {
    CPU4,
    GPU,
    NPU,
}

enum class ModelPrecision {
    FLOAT32,
    INT8,
}

enum class LimitMode {
    COUNT,
    DURATION,
}

enum class ExperimentMode {
    BASIC,
    DIAGNOSTIC,
}

data class RunConfig(
    val resource: ResourceTarget,
    val precision: ModelPrecision = ModelPrecision.FLOAT32,
    val limitMode: LimitMode,
    val inferenceCount: Int,
    val durationSeconds: Long,
    val warmupCount: Int,
    val experimentMode: ExperimentMode,
) {
    init {
        require(resource == ResourceTarget.CPU4 || resource == ResourceTarget.GPU)
        require(precision == ModelPrecision.FLOAT32)
        require(inferenceCount in 1..MAX_INFERENCE_COUNT) {
            "inferenceCount must be 1..$MAX_INFERENCE_COUNT"
        }
        require(durationSeconds in 1..MAX_DURATION_SECONDS) {
            "durationSeconds must be 1..$MAX_DURATION_SECONDS"
        }
        require(warmupCount in 0..MAX_WARMUP_COUNT) {
            "warmupCount must be 0..$MAX_WARMUP_COUNT"
        }
    }

    companion object {
        const val MAX_WARMUP_COUNT = 10_000
        const val MAX_INFERENCE_COUNT = 250_000
        const val MAX_DURATION_SECONDS = 3_600L
    }
}
