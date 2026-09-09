package com.example.d1check.benchmarkrunner

enum class ResourceTarget {
    CPU,
    CPU4,
    GPU,
    NPU,
}

enum class ModelPrecision {
    FLOAT32,
    INT8,
}

sealed interface RunLimit {
    val modeName: String

    data class Count(val inferenceCount: Int) : RunLimit {
        override val modeName: String = "COUNT"
    }

    data class Duration(val durationSeconds: Long) : RunLimit {
        override val modeName: String = "DURATION"
    }
}

enum class ExperimentMode {
    BASIC,
    DIAGNOSTIC,
}

data class RunConfig(
    val resource: ResourceTarget,
    val precision: ModelPrecision = ModelPrecision.FLOAT32,
    val cpuThreads: Int? = if (resource == ResourceTarget.CPU4) 4 else null,
    val limit: RunLimit,
    val warmupCount: Int,
    val experimentMode: ExperimentMode,
    val expectedRunId: String? = null,
    val commandId: String? = null,
    val dutyCyclePercent: Int = 100,
    val dutyCyclePeriodSeconds: Double = 10.0,
) {
    init {
        require(
            resource == ResourceTarget.CPU ||
                resource == ResourceTarget.CPU4 ||
                resource == ResourceTarget.GPU
        )
        require(precision == ModelPrecision.FLOAT32)
        when (limit) {
            is RunLimit.Count -> require(limit.inferenceCount in 1..MAX_INFERENCE_COUNT) {
                "inferenceCount must be 1..$MAX_INFERENCE_COUNT"
            }
            is RunLimit.Duration -> require(limit.durationSeconds in 1..MAX_DURATION_SECONDS) {
                "durationSeconds must be 1..$MAX_DURATION_SECONDS"
            }
        }
        if (resource == ResourceTarget.CPU || resource == ResourceTarget.CPU4) {
            require(cpuThreads in 1..MAX_CPU_THREADS) {
                "cpuThreads must be 1..$MAX_CPU_THREADS for CPU"
            }
        } else {
            require(cpuThreads == null) { "cpuThreads is only valid for CPU" }
        }
        require(resource != ResourceTarget.CPU4 || cpuThreads == 4) {
            "CPU4 legacy alias requires exactly 4 CPU threads"
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
    }

    val normalizedResource: ResourceTarget
        get() = if (resource == ResourceTarget.CPU4) ResourceTarget.CPU else resource

    val legacyResourceAlias: String?
        get() = ResourceTarget.CPU4.name.takeIf { resource == ResourceTarget.CPU4 }

    val isAutomated: Boolean get() = commandId != null

    companion object {
        const val MAX_WARMUP_COUNT = 10_000
        const val MAX_INFERENCE_COUNT = 250_000
        const val MAX_DURATION_SECONDS = 3_600L
        const val MAX_CPU_THREADS = 16
    }
}
