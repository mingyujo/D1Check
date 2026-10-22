package com.example.d1check.benchmarkrunner

import org.tensorflow.lite.gpu.GpuDelegateFactory
import java.security.MessageDigest

enum class GpuDelegateProfile(
    val profileId: String,
    val precisionLossAllowed: Boolean,
) {
    COMPAT_DEFAULT("gpu-compat-default-v1", true),
    FP32_STRICT("gpu-fp32-strict-v1", false),
    ;

    val quantizedModelsAllowed: Boolean = true
    val inferencePreferenceName: String = "FAST_SINGLE_ANSWER"
    val forceBackendName: String = "UNSET"
    val actualFp16Execution: String = "unknown_not_exposed_by_litert_api"

    val canonicalConfiguration: String
        get() = listOf(
            "profile_id=$profileId",
            "precision_loss_allowed=$precisionLossAllowed",
            "quantized_models_allowed=$quantizedModelsAllowed",
            "inference_preference=$inferencePreferenceName",
            "force_backend=$forceBackendName",
        ).joinToString("|")

    val configurationSha256: String
        get() = MessageDigest.getInstance("SHA-256")
            .digest(canonicalConfiguration.toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it) }

    fun options(): GpuDelegateFactory.Options = GpuDelegateFactory.Options()
        .setPrecisionLossAllowed(precisionLossAllowed)
        .setQuantizedModelsAllowed(quantizedModelsAllowed)
        .setInferencePreference(GpuDelegateFactory.Options.INFERENCE_PREFERENCE_FAST_SINGLE_ANSWER)
        .setForceBackend(GpuDelegateFactory.Options.GpuBackend.UNSET)

    fun metadata(): Map<String, Any?> = linkedMapOf(
        "profile_id" to profileId,
        "configuration_sha256" to configurationSha256,
        "precision_loss_allowed" to precisionLossAllowed,
        "quantized_models_allowed" to quantizedModelsAllowed,
        "inference_preference" to inferencePreferenceName,
        "force_backend" to forceBackendName,
        "actual_fp16_execution" to actualFp16Execution,
    )

    companion object {
        val DEFAULT = COMPAT_DEFAULT

        fun fromId(value: String): GpuDelegateProfile = entries.firstOrNull {
            it.profileId == value
        } ?: throw IllegalArgumentException("Unsupported GPU delegate profile: $value")
    }
}
