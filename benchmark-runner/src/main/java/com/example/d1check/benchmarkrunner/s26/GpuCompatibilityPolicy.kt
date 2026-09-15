package com.example.d1check.benchmarkrunner.s26

import android.util.Log
import org.tensorflow.lite.gpu.CompatibilityList

/**
 * S26 measurement policy for the LiteRT GPU device compatibility list.
 *
 * LiteRT 1.4.2 embeds a binary allow list of GPU-capable devices that predates
 * the Exynos 2600, so on the Galaxy S26 it reports "not supported" even though
 * the device exposes libOpenCL.so and libOpenCL_samsung.so. The list is a
 * heuristic for app developers, not a statement of hardware capability.
 *
 * The original runner treated a negative verdict as fatal, which made every GPU
 * run fail in the setup phase before GpuDelegate() was constructed. This policy
 * records the verdict instead and lets the delegate constructor decide.
 *
 * Actual GPU execution remains verified downstream by delegate_evidence
 * (TfLiteGpuDelegateV2 creation, kernel count, replaced-node count in logcat)
 * and by the CPU/GPU output equivalence preflight. Those checks are stronger
 * than the allow list, not weaker.
 *
 * On devices present in the list (e.g. Galaxy A24 / Mali-G57) the verdict is
 * true and behaviour is identical to before; only metadata is added.
 */
internal object GpuCompatibilityPolicy {

    const val TAG = "D1GPUCOMPAT"
    const val POLICY_ID = "s26-compat-list-advisory-v1"

    data class Verdict(
        val listSupported: Boolean?,
        val queryError: String?,
    ) {
        fun metadata(): Map<String, Any?> = linkedMapOf(
            "gpu_compatibility_policy_id" to POLICY_ID,
            "gpu_compatibility_list_supported" to listSupported,
            "gpu_compatibility_list_query_error" to queryError,
            "gpu_compatibility_list_enforced" to false,
        )
    }

    fun notEvaluatedMetadata(): Map<String, Any?> = linkedMapOf(
        "gpu_compatibility_policy_id" to POLICY_ID,
        "gpu_compatibility_list_supported" to null,
        "gpu_compatibility_list_query_error" to null,
        "gpu_compatibility_list_enforced" to false,
    )

    fun evaluate(): Verdict {
        val verdict = try {
            val list = CompatibilityList()
            Verdict(list.isDelegateSupportedOnThisDevice, null)
        } catch (error: Throwable) {
            Verdict(null, "${error.javaClass.simpleName}: ${error.message ?: ""}")
        }
        Log.i(
            TAG,
            "policy=" + POLICY_ID +
                " list_supported=" + verdict.listSupported +
                " query_error=" + verdict.queryError +
                " enforced=false",
        )
        return verdict
    }
}
