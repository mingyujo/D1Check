package com.example.d1check.benchmarkrunner

import java.util.UUID

internal enum class AccuracyCheckType(val wireName: String) {
    SYNTHETIC("synthetic"),
    REPRESENTATIVE("representative"),
    ;

    companion object {
        fun fromWireName(value: String): AccuracyCheckType = entries.firstOrNull {
            it.wireName == value.lowercase()
        } ?: throw IllegalArgumentException("Unsupported accuracy check type: $value")
    }
}

internal data class AccuracyPreflightConfig(
    val commandId: String,
    val checkType: AccuracyCheckType = AccuracyCheckType.SYNTHETIC,
    val inputCount: Int = 32,
    val seed: Long = DeterministicInputSet.DEFAULT_SEED,
    val cpuThreads: Int = 4,
    val tolerance: ComparatorTolerance = ComparatorTolerance(
        atol = 1e-4,
        rtol = 1e-3,
        relativeErrorEpsilon = 1e-6,
    ),
    val representativeTensorSetPath: String? = null,
    val expectedTensorSetContainerSha256: String? = null,
    val expectedPreprocessingConfigurationSha256: String? = null,
    val gpuDelegateProfile: GpuDelegateProfile = GpuDelegateProfile.DEFAULT,
) {
    init {
        require(inputCount in 1..MAX_INPUT_COUNT)
        require(cpuThreads in 1..RunConfig.MAX_CPU_THREADS)
        UUID.fromString(commandId)
        require((checkType == AccuracyCheckType.REPRESENTATIVE) ==
            !representativeTensorSetPath.isNullOrBlank()) {
            "representative check requires exactly one tensor-set path"
        }
        require((checkType == AccuracyCheckType.REPRESENTATIVE) ==
            !expectedTensorSetContainerSha256.isNullOrBlank()) {
            "representative check requires the expected container SHA-256"
        }
        require((checkType == AccuracyCheckType.REPRESENTATIVE) ==
            !expectedPreprocessingConfigurationSha256.isNullOrBlank()) {
            "representative check requires the expected preprocessing configuration SHA-256"
        }
        expectedTensorSetContainerSha256?.let {
            require(it.matches(Regex("[0-9a-fA-F]{64}"))) { "invalid tensor-set SHA-256" }
        }
        expectedPreprocessingConfigurationSha256?.let {
            require(it.matches(Regex("[0-9a-fA-F]{64}"))) {
                "invalid preprocessing configuration SHA-256"
            }
        }
    }

    companion object {
        const val MAX_INPUT_COUNT = 256
    }
}

internal object AccuracyPreflightIntentParser {
    const val EXTRA_ENABLED = "d1_accuracy_preflight"
    const val EXTRA_COMMAND_ID = AutomationIntentParser.EXTRA_COMMAND_ID
    const val EXTRA_INPUT_COUNT = "d1_accuracy_input_count"
    const val EXTRA_SEED = "d1_accuracy_seed"
    const val EXTRA_CPU_THREADS = "d1_accuracy_cpu_threads"
    const val EXTRA_ATOL = "d1_accuracy_atol"
    const val EXTRA_RTOL = "d1_accuracy_rtol"
    const val EXTRA_RELATIVE_EPSILON = "d1_accuracy_relative_epsilon"
    const val EXTRA_CHECK_TYPE = "d1_accuracy_check_type"
    const val EXTRA_TENSOR_SET_PATH = "d1_accuracy_tensor_set_path"
    const val EXTRA_TENSOR_SET_SHA256 = "d1_accuracy_tensor_set_sha256"
    const val EXTRA_PREPROCESSING_SHA256 = "d1_accuracy_preprocessing_sha256"
    const val EXTRA_GPU_PROFILE = "d1_gpu_profile"

    fun parse(extras: Map<String, Any?>): AccuracyPreflightConfig? {
        if (extras[EXTRA_ENABLED] != true) return null
        val commandId = (extras[EXTRA_COMMAND_ID] as? String)?.let {
            try {
                UUID.fromString(it).toString()
            } catch (error: IllegalArgumentException) {
                throw IllegalArgumentException("Invalid UUID for $EXTRA_COMMAND_ID: $it", error)
            }
        } ?: throw IllegalArgumentException("Missing $EXTRA_COMMAND_ID")
        val checkType = (extras[EXTRA_CHECK_TYPE] as? String)?.let(
            AccuracyCheckType::fromWireName
        ) ?: AccuracyCheckType.SYNTHETIC
        return AccuracyPreflightConfig(
            commandId = commandId,
            checkType = checkType,
            inputCount = number(extras, EXTRA_INPUT_COUNT)?.toInt() ?: 32,
            seed = number(extras, EXTRA_SEED)?.toLong() ?: DeterministicInputSet.DEFAULT_SEED,
            cpuThreads = number(extras, EXTRA_CPU_THREADS)?.toInt() ?: 4,
            tolerance = ComparatorTolerance(
                atol = decimal(extras, EXTRA_ATOL) ?: 1e-4,
                rtol = decimal(extras, EXTRA_RTOL) ?: 1e-3,
                relativeErrorEpsilon = decimal(extras, EXTRA_RELATIVE_EPSILON) ?: 1e-6,
            ),
            representativeTensorSetPath = extras[EXTRA_TENSOR_SET_PATH] as? String,
            expectedTensorSetContainerSha256 = extras[EXTRA_TENSOR_SET_SHA256] as? String,
            expectedPreprocessingConfigurationSha256 =
                extras[EXTRA_PREPROCESSING_SHA256] as? String,
            gpuDelegateProfile = (extras[EXTRA_GPU_PROFILE] as? String)?.let(
                GpuDelegateProfile::fromId
            ) ?: GpuDelegateProfile.DEFAULT,
        )
    }

    private fun number(extras: Map<String, Any?>, key: String): Number? =
        when (val value = extras[key]) {
            null -> null
            is Number -> value
            else -> throw IllegalArgumentException("$key must be numeric")
        }

    private fun decimal(extras: Map<String, Any?>, key: String): Double? =
        when (val value = extras[key]) {
            null -> null
            is Number -> value.toDouble()
            is String -> value.toDoubleOrNull()
                ?: throw IllegalArgumentException("$key must be a decimal string")
            else -> throw IllegalArgumentException("$key must be numeric")
        }
}
