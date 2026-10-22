package com.example.d1check.benchmarkrunner

import android.content.Intent
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
    const val EXTRA_DUTY_CYCLE_PERCENT = "d1_duty_cycle_percent"
    const val EXTRA_DUTY_CYCLE_PERIOD_S = "d1_duty_cycle_period_s"
    const val EXTRA_GPU_PROFILE = "d1_gpu_profile"
    const val EXTRA_PROTOCOL_VERSION = "d1_protocol_version"
    const val EXTRA_DIAGNOSTIC_SESSION_ID = "d1_diagnostic_session_id"
    const val EXTRA_DIAGNOSTIC_PERFETTO = "d1_diagnostic_perfetto"
    const val EXTRA_DIAGNOSTIC_PERFETTO_STARTED = "d1_diagnostic_perfetto_started"
    const val EXTRA_DIAGNOSTIC_TRACE_FILENAME = "d1_diagnostic_trace_filename"

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
        EXTRA_DUTY_CYCLE_PERCENT,
        EXTRA_DUTY_CYCLE_PERIOD_S,
        EXTRA_GPU_PROFILE,
        EXTRA_PROTOCOL_VERSION,
        EXTRA_DIAGNOSTIC_SESSION_ID,
        EXTRA_DIAGNOSTIC_PERFETTO,
        EXTRA_DIAGNOSTIC_PERFETTO_STARTED,
        EXTRA_DIAGNOSTIC_TRACE_FILENAME,
    )

    fun parseFromSource(
        contains: (String) -> Boolean,
        value: (String) -> Any?,
    ): AutomationRequest? = parse(
        buildMap {
            knownExtras.forEach { key ->
                if (contains(key)) put(key, value(key))
            }
        }
    )

    fun parse(intent: Intent): AutomationRequest? = parseFromSource(
        intent::hasExtra,
        { key -> intent.extras?.get(key) },
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
        val gpuProfile = if (resource == ResourceTarget.GPU) {
            (extras[EXTRA_GPU_PROFILE] as? String)?.let(GpuDelegateProfile::fromId)
                ?: GpuDelegateProfile.DEFAULT
        } else {
            require(extras[EXTRA_GPU_PROFILE] == null) {
                "d1_gpu_profile is only valid for GPU"
            }
            GpuDelegateProfile.DEFAULT
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
        val protocolVersion = when (optionalInt(extras, EXTRA_PROTOCOL_VERSION) ?: 1) {
            1 -> ProtocolVersion.V1
            2 -> ProtocolVersion.DIAGNOSTIC_V2
            else -> throw IllegalArgumentException("d1_protocol_version must be 1 or 2")
        }
        val diagnosticSessionId = if (protocolVersion == ProtocolVersion.DIAGNOSTIC_V2) {
            requiredUuid(extras, EXTRA_DIAGNOSTIC_SESSION_ID)
        } else {
            require(!extras.containsKey(EXTRA_DIAGNOSTIC_SESSION_ID)) {
                "d1_diagnostic_session_id is only valid for protocol v2"
            }
            null
        }
        val diagnosticTraceMode = if (protocolVersion == ProtocolVersion.DIAGNOSTIC_V2) {
            when (requiredString(extras, EXTRA_DIAGNOSTIC_PERFETTO).lowercase(Locale.ROOT)) {
                "off" -> DiagnosticTraceMode.OFF
                "on" -> DiagnosticTraceMode.ON
                else -> throw IllegalArgumentException("d1_diagnostic_perfetto must be off or on")
            }
        } else {
            require(!extras.containsKey(EXTRA_DIAGNOSTIC_PERFETTO)) {
                "d1_diagnostic_perfetto is only valid for protocol v2"
            }
            DiagnosticTraceMode.OFF
        }
        val diagnosticPerfettoStarted = if (protocolVersion == ProtocolVersion.DIAGNOSTIC_V2) {
            requiredBoolean(extras, EXTRA_DIAGNOSTIC_PERFETTO_STARTED)
        } else {
            require(!extras.containsKey(EXTRA_DIAGNOSTIC_PERFETTO_STARTED)) {
                "d1_diagnostic_perfetto_started is only valid for protocol v2"
            }
            false
        }
        val diagnosticTraceFilename = if (protocolVersion == ProtocolVersion.DIAGNOSTIC_V2) {
            when (diagnosticTraceMode) {
                DiagnosticTraceMode.OFF -> {
                    require(!extras.containsKey(EXTRA_DIAGNOSTIC_TRACE_FILENAME)) {
                        "d1_diagnostic_trace_filename must be absent for trace-off"
                    }
                    require(!diagnosticPerfettoStarted) {
                        "trace-off requires d1_diagnostic_perfetto_started=false"
                    }
                    null
                }
                DiagnosticTraceMode.ON -> {
                    require(diagnosticPerfettoStarted) {
                        "trace-on requires d1_diagnostic_perfetto_started=true"
                    }
                    requiredString(extras, EXTRA_DIAGNOSTIC_TRACE_FILENAME)
                }
            }
        } else {
            require(!extras.containsKey(EXTRA_DIAGNOSTIC_TRACE_FILENAME)) {
                "d1_diagnostic_trace_filename is only valid for protocol v2"
            }
            null
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
                dutyCyclePercent = optionalInt(extras, EXTRA_DUTY_CYCLE_PERCENT) ?: 100,
                dutyCyclePeriodSeconds =
                    optionalDouble(extras, EXTRA_DUTY_CYCLE_PERIOD_S) ?: 10.0,
                gpuDelegateProfile = gpuProfile,
                protocolVersion = protocolVersion,
                diagnosticSessionId = diagnosticSessionId,
                diagnosticTraceMode = diagnosticTraceMode,
                diagnosticPerfettoStarted = diagnosticPerfettoStarted,
                diagnosticTraceFilename = diagnosticTraceFilename,
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

    private fun requiredBoolean(extras: Map<String, Any?>, key: String): Boolean =
        extras[key] as? Boolean ?: throw IllegalArgumentException("Missing or invalid $key")

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
