package com.example.d1check.benchmarkrunner

import java.util.Locale
import java.util.UUID

internal data class AutomationRequest(val config: RunConfig)

internal object AutomationIntentParser {
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

    val knownExtras = setOf(
        EXTRA_AUTO_START,
        EXTRA_RESOURCE,
        EXTRA_CPU_THREADS,
        EXTRA_LIMIT_MODE,
        EXTRA_INFERENCE_COUNT,
        EXTRA_DURATION_S,
        EXTRA_WARMUP_COUNT,
        EXTRA_RUN_ID,
        EXTRA_COMMAND_ID,
        EXTRA_EXPERIMENT_MODE,
    )

    fun parse(extras: Map<String, Any?>): AutomationRequest? {
        if (extras[EXTRA_AUTO_START] != true) return null

        val resourceValue = requiredString(extras, EXTRA_RESOURCE).uppercase(Locale.ROOT)
        val resource = when (resourceValue) {
            "CPU" -> ResourceTarget.CPU
            "CPU4" -> ResourceTarget.CPU4
            "GPU" -> ResourceTarget.GPU
            else -> throw IllegalArgumentException("Unsupported d1_resource: $resourceValue")
        }
        val cpuThreads = when (resource) {
            ResourceTarget.CPU -> requiredInt(extras, EXTRA_CPU_THREADS)
            ResourceTarget.CPU4 -> {
                val supplied = optionalInt(extras, EXTRA_CPU_THREADS)
                require(supplied == null || supplied == 4) {
                    "CPU4 requires d1_cpu_threads=4"
                }
                4
            }
            ResourceTarget.GPU -> {
                require(extras[EXTRA_CPU_THREADS] == null) {
                    "d1_cpu_threads must be omitted for GPU"
                }
                null
            }
            ResourceTarget.NPU -> error("unreachable")
        }
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
        return AutomationRequest(
            RunConfig(
                resource = resource,
                cpuThreads = cpuThreads,
                limit = limit,
                warmupCount = optionalInt(extras, EXTRA_WARMUP_COUNT) ?: 20,
                experimentMode = experimentMode,
                expectedRunId = runId,
                commandId = commandId,
            )
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
}
