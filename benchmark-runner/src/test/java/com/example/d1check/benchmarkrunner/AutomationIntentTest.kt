package com.example.d1check.benchmarkrunner

import android.content.Intent
import android.os.Bundle
import android.widget.TextView
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class AutomationIntentTest {
    private val runId = "11111111-1111-1111-1111-111111111111"
    private val commandId = "22222222-2222-2222-2222-222222222222"

    @Test
    fun cpu4LegacyRequestBecomesAutomatedDurationRun() {
        val request = AutomationIntentParser.parse(
            mapOf(
                AutomationIntentParser.EXTRA_AUTO_START to true,
                AutomationIntentParser.EXTRA_RESOURCE to "CPU4",
                AutomationIntentParser.EXTRA_DURATION_S to 60L,
                AutomationIntentParser.EXTRA_WARMUP_COUNT to 20,
                AutomationIntentParser.EXTRA_RUN_ID to runId,
                AutomationIntentParser.EXTRA_COMMAND_ID to commandId,
            )
        )

        val config = requireNotNull(request).config
        assertEquals(ResourceTarget.CPU, config.normalizedResource)
        assertEquals(4, config.cpuThreads)
        assertEquals("CPU4", config.legacyResourceAlias)
        assertEquals(RunLimit.Duration(60), config.limit)
        assertEquals(100, config.dutyCyclePercent)
        assertEquals(10.0, config.dutyCyclePeriodSeconds, 0.0)
    }

    @Test
    fun explicitCountRequestUsesOnlyCountLimit() {
        val request = AutomationIntentParser.parse(
            mapOf(
                AutomationIntentParser.EXTRA_AUTO_START to true,
                AutomationIntentParser.EXTRA_RESOURCE to "GPU",
                AutomationIntentParser.EXTRA_LIMIT_MODE to "COUNT",
                AutomationIntentParser.EXTRA_INFERENCE_COUNT to 123,
                AutomationIntentParser.EXTRA_RUN_ID to runId,
                AutomationIntentParser.EXTRA_COMMAND_ID to commandId,
            )
        )

        assertEquals(RunLimit.Count(123), requireNotNull(request).config.limit)
    }

    @Test
    fun absentAutoStartIsNotAnAutomationRequest() {
        assertNull(AutomationIntentParser.parse(emptyMap()))
    }

    @Test
    fun dutyCycleExtrasAreParsedForDurationRun() {
        val request = AutomationIntentParser.parse(
            mapOf(
                AutomationIntentParser.EXTRA_AUTO_START to true,
                AutomationIntentParser.EXTRA_RESOURCE to "GPU",
                AutomationIntentParser.EXTRA_DURATION_S to 60L,
                AutomationIntentParser.EXTRA_DUTY_CYCLE_PERCENT to 25,
                AutomationIntentParser.EXTRA_DUTY_CYCLE_PERIOD_S to 4.0f,
                AutomationIntentParser.EXTRA_GPU_PROFILE to "gpu-fp32-strict-v1",
                AutomationIntentParser.EXTRA_RUN_ID to runId,
                AutomationIntentParser.EXTRA_COMMAND_ID to commandId,
            )
        )

        assertEquals(25, requireNotNull(request).config.dutyCyclePercent)
        assertEquals(4.0, request.config.dutyCyclePeriodSeconds, 0.0)
        assertEquals(GpuDelegateProfile.FP32_STRICT, request.config.gpuDelegateProfile)
    }

    @Test(expected = IllegalArgumentException::class)
    fun gpuRejectsCpuThreadExtra() {
        AutomationIntentParser.parse(
            mapOf(
                AutomationIntentParser.EXTRA_AUTO_START to true,
                AutomationIntentParser.EXTRA_RESOURCE to "GPU",
                AutomationIntentParser.EXTRA_CPU_THREADS to 4,
                AutomationIntentParser.EXTRA_DURATION_S to 60L,
                AutomationIntentParser.EXTRA_RUN_ID to runId,
                AutomationIntentParser.EXTRA_COMMAND_ID to commandId,
            )
        )
    }

    @Test
    fun protocolV1RemainsDefaultAndHasNoDiagnosticSession() {
        val config = requireNotNull(AutomationIntentParser.parse(
            mapOf(
                AutomationIntentParser.EXTRA_AUTO_START to true,
                AutomationIntentParser.EXTRA_RESOURCE to "CPU",
                AutomationIntentParser.EXTRA_CPU_THREADS to 2,
                AutomationIntentParser.EXTRA_DURATION_S to 10L,
                AutomationIntentParser.EXTRA_RUN_ID to runId,
                AutomationIntentParser.EXTRA_COMMAND_ID to commandId,
            )
        )).config

        assertEquals(ProtocolVersion.V1, config.protocolVersion)
        assertNull(config.diagnosticSessionId)
        assertFalse(config.isDiagnosticV2)
    }

    @Test
    fun explicitDiagnosticV2ParsesProtocolAndSession() {
        val sessionId = "33333333-3333-3333-3333-333333333333"
        val config = requireNotNull(AutomationIntentParser.parse(
            mapOf(
                AutomationIntentParser.EXTRA_AUTO_START to true,
                AutomationIntentParser.EXTRA_RESOURCE to "GPU",
                AutomationIntentParser.EXTRA_DURATION_S to 10L,
                AutomationIntentParser.EXTRA_WARMUP_COUNT to 0,
                AutomationIntentParser.EXTRA_RUN_ID to runId,
                AutomationIntentParser.EXTRA_COMMAND_ID to commandId,
                AutomationIntentParser.EXTRA_EXPERIMENT_MODE to "DIAGNOSTIC",
                AutomationIntentParser.EXTRA_PROTOCOL_VERSION to 2,
                AutomationIntentParser.EXTRA_DIAGNOSTIC_SESSION_ID to sessionId,
                AutomationIntentParser.EXTRA_DIAGNOSTIC_PERFETTO to "off",
                AutomationIntentParser.EXTRA_DIAGNOSTIC_PERFETTO_STARTED to false,
            )
        )).config

        assertTrue(config.isDiagnosticV2)
        assertEquals(sessionId, config.diagnosticSessionId)
        assertEquals(ExperimentMode.DIAGNOSTIC, config.experimentMode)
        assertEquals(DiagnosticTraceMode.OFF, config.diagnosticTraceMode)
        assertFalse(config.diagnosticPerfettoEnabled)
    }

    @Test
    fun diagnosticPerfettoOnRequiresAndPreservesReadyTraceIdentity() {
        val sessionId = "33333333-3333-3333-3333-333333333333"
        val filename = "d1check-$sessionId.perfetto-trace"
        val config = requireNotNull(AutomationIntentParser.parse(
            mapOf(
                AutomationIntentParser.EXTRA_AUTO_START to true,
                AutomationIntentParser.EXTRA_RESOURCE to "GPU",
                AutomationIntentParser.EXTRA_DURATION_S to 10L,
                AutomationIntentParser.EXTRA_WARMUP_COUNT to 0,
                AutomationIntentParser.EXTRA_RUN_ID to runId,
                AutomationIntentParser.EXTRA_COMMAND_ID to commandId,
                AutomationIntentParser.EXTRA_EXPERIMENT_MODE to "DIAGNOSTIC",
                AutomationIntentParser.EXTRA_PROTOCOL_VERSION to 2,
                AutomationIntentParser.EXTRA_DIAGNOSTIC_SESSION_ID to sessionId,
                AutomationIntentParser.EXTRA_DIAGNOSTIC_PERFETTO to "on",
                AutomationIntentParser.EXTRA_DIAGNOSTIC_PERFETTO_STARTED to true,
                AutomationIntentParser.EXTRA_DIAGNOSTIC_TRACE_FILENAME to filename,
            )
        )).config

        assertTrue(config.diagnosticPerfettoEnabled)
        assertTrue(config.diagnosticPerfettoStarted)
        assertEquals(filename, config.diagnosticTraceFilename)
    }

    @Test(expected = IllegalArgumentException::class)
    fun diagnosticV2RequiresExplicitSessionId() {
        AutomationIntentParser.parse(
            mapOf(
                AutomationIntentParser.EXTRA_AUTO_START to true,
                AutomationIntentParser.EXTRA_RESOURCE to "GPU",
                AutomationIntentParser.EXTRA_DURATION_S to 10L,
                AutomationIntentParser.EXTRA_RUN_ID to runId,
                AutomationIntentParser.EXTRA_COMMAND_ID to commandId,
                AutomationIntentParser.EXTRA_EXPERIMENT_MODE to "DIAGNOSTIC",
                AutomationIntentParser.EXTRA_PROTOCOL_VERSION to 2,
                AutomationIntentParser.EXTRA_DIAGNOSTIC_PERFETTO to "off",
                AutomationIntentParser.EXTRA_DIAGNOSTIC_PERFETTO_STARTED to false,
            )
        )
    }

    private fun parseThroughActivityContract(incomingExtras: Map<String, Any?>): RunConfig =
        requireNotNull(
            AutomationIntentParser.parseFromSource(
                incomingExtras::containsKey,
                incomingExtras::get,
            )
        ).config

    private fun diagnosticActivityExtras(traceMode: String): MutableMap<String, Any?> {
        val sessionId = "33333333-3333-3333-3333-333333333333"
        return mutableMapOf<String, Any?>(
            AutomationIntentParser.EXTRA_AUTO_START to true,
            AutomationIntentParser.EXTRA_RESOURCE to "GPU",
            AutomationIntentParser.EXTRA_DURATION_S to 10L,
            AutomationIntentParser.EXTRA_WARMUP_COUNT to 0,
            AutomationIntentParser.EXTRA_RUN_ID to runId,
            AutomationIntentParser.EXTRA_COMMAND_ID to commandId,
            AutomationIntentParser.EXTRA_EXPERIMENT_MODE to "DIAGNOSTIC",
            AutomationIntentParser.EXTRA_PROTOCOL_VERSION to 2,
            AutomationIntentParser.EXTRA_DIAGNOSTIC_SESSION_ID to sessionId,
            AutomationIntentParser.EXTRA_DIAGNOSTIC_PERFETTO to traceMode,
            AutomationIntentParser.EXTRA_DIAGNOSTIC_PERFETTO_STARTED to (traceMode == "on"),
        ).also {
            if (traceMode == "on") {
                it[AutomationIntentParser.EXTRA_DIAGNOSTIC_TRACE_FILENAME] =
                    "d1check-$sessionId.perfetto-trace"
            }
        }
    }

    @Test
    fun activityContractPreservesCompleteTraceOffRequest() {
        val config = parseThroughActivityContract(diagnosticActivityExtras("off"))

        assertEquals(DiagnosticTraceMode.OFF, config.diagnosticTraceMode)
        assertFalse(config.diagnosticPerfettoStarted)
        assertNull(config.diagnosticTraceFilename)
    }

    @Test
    fun activityContractPreservesCompleteTraceOnRequest() {
        val config = parseThroughActivityContract(diagnosticActivityExtras("on"))

        assertEquals(DiagnosticTraceMode.ON, config.diagnosticTraceMode)
        assertTrue(config.diagnosticPerfettoStarted)
        assertEquals(
            "d1check-${config.diagnosticSessionId}.perfetto-trace",
            config.diagnosticTraceFilename,
        )
    }

    private fun diagnosticIntent(traceMode: String): Intent = Intent().apply {
        diagnosticActivityExtras(traceMode).forEach { (key, value) ->
            when (value) {
                is Boolean -> putExtra(key, value)
                is Int -> putExtra(key, value)
                is Long -> putExtra(key, value)
                is String -> putExtra(key, value)
                else -> error("unsupported fixture value")
            }
        }
    }

    @Test
    fun realIntentAndBundleDistinguishFilenameAbsenceFromEveryPresentValue() {
        val validOff = requireNotNull(AutomationIntentParser.parse(diagnosticIntent("off"))).config
        assertEquals(DiagnosticTraceMode.OFF, validOff.diagnosticTraceMode)
        assertNull(validOff.diagnosticTraceFilename)

        val invalidBundles = listOf(
            Bundle().apply { putString(AutomationIntentParser.EXTRA_DIAGNOSTIC_TRACE_FILENAME, null) },
            Bundle().apply { putString(AutomationIntentParser.EXTRA_DIAGNOSTIC_TRACE_FILENAME, "") },
            Bundle().apply { putInt(AutomationIntentParser.EXTRA_DIAGNOSTIC_TRACE_FILENAME, 7) },
            Bundle().apply { putBoolean(AutomationIntentParser.EXTRA_DIAGNOSTIC_TRACE_FILENAME, false) },
            Bundle().apply { putString(AutomationIntentParser.EXTRA_DIAGNOSTIC_TRACE_FILENAME, "arbitrary") },
        )
        invalidBundles.forEach { extras ->
            val intent = diagnosticIntent("off").putExtras(extras)
            try {
                AutomationIntentParser.parse(intent)
                throw AssertionError("present trace-off filename extra was accepted")
            } catch (_: IllegalArgumentException) {
                assertTrue(intent.hasExtra(AutomationIntentParser.EXTRA_DIAGNOSTIC_TRACE_FILENAME))
            }
        }
    }

    @Test
    fun realIntentRequiresBooleanStartedAndValidOnSessionFilename() {
        val validOn = requireNotNull(AutomationIntentParser.parse(diagnosticIntent("on"))).config
        assertTrue(validOn.diagnosticPerfettoStarted)
        assertEquals(
            "d1check-${validOn.diagnosticSessionId}.perfetto-trace",
            validOn.diagnosticTraceFilename,
        )

        val wrongStarted = diagnosticIntent("off").apply {
            removeExtra(AutomationIntentParser.EXTRA_DIAGNOSTIC_PERFETTO_STARTED)
            putExtra(AutomationIntentParser.EXTRA_DIAGNOSTIC_PERFETTO_STARTED, "false")
        }
        try {
            AutomationIntentParser.parse(wrongStarted)
            throw AssertionError("non-Boolean started extra was accepted")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }
    }

    @Test
    fun mainActivityAutomationEntryFailsClosedOnPresentNullOffFilename() {
        val intent = diagnosticIntent("off").apply {
            putExtras(Bundle().apply {
                putString(AutomationIntentParser.EXTRA_DIAGNOSTIC_TRACE_FILENAME, null)
            })
        }
        val activity = Robolectric.buildActivity(MainActivity::class.java, intent).setup().get()
        val field = MainActivity::class.java.getDeclaredField("statusView").apply {
            isAccessible = true
        }
        val status = (field.get(activity) as TextView).text.toString()
        assertTrue(status.startsWith("Invalid automation request:"))
    }

    @Test
    fun mainActivityValidTraceOffIntentReachesBenchmarkBoundaryOnce() {
        assertValidDiagnosticIntentStartsThroughActivity(
            "off",
            "44444444-4444-4444-4444-444444444444",
        )
    }

    @Test
    fun mainActivityValidTraceOnIntentReachesBenchmarkBoundaryOnce() {
        assertValidDiagnosticIntentStartsThroughActivity(
            "on",
            "55555555-5555-5555-5555-555555555555",
        )
    }

    private fun assertValidDiagnosticIntentStartsThroughActivity(
        traceMode: String,
        expectedCommandId: String,
    ) {
        val controller = Robolectric.buildActivity(MainActivity::class.java, Intent()).setup()
        val activity = controller.get()
        val observed = mutableListOf<RunConfig>()
        activity.benchmarkLauncher = BenchmarkLauncher { config, completed ->
            observed += config
            completed(BenchmarkResult(true, "fixture complete", null))
        }
        val incoming = diagnosticIntent(traceMode).apply {
            putExtra(AutomationIntentParser.EXTRA_COMMAND_ID, expectedCommandId)
        }

        try {
            controller.newIntent(incoming)

            assertEquals(1, observed.size)
            val config = observed.single()
            assertEquals(ProtocolVersion.DIAGNOSTIC_V2, config.protocolVersion)
            assertEquals("33333333-3333-3333-3333-333333333333", config.diagnosticSessionId)
            assertEquals(
                if (traceMode == "on") DiagnosticTraceMode.ON else DiagnosticTraceMode.OFF,
                config.diagnosticTraceMode,
            )
            assertEquals(traceMode == "on", config.diagnosticPerfettoStarted)
            assertEquals(
                if (traceMode == "on") {
                    "d1check-${config.diagnosticSessionId}.perfetto-trace"
                } else {
                    null
                },
                config.diagnosticTraceFilename,
            )
            assertEquals(ResourceTarget.GPU, config.resource)
            assertEquals(ResourceTarget.GPU, config.normalizedResource)
            assertEquals(RunLimit.Duration(10L), config.limit)
            assertEquals(0, config.warmupCount)
            assertEquals(ExperimentMode.DIAGNOSTIC, config.experimentMode)
            assertEquals(runId, config.expectedRunId)
            assertEquals(expectedCommandId, config.commandId)
            assertEquals(100, config.dutyCyclePercent)
            assertEquals(10.0, config.dutyCyclePeriodSeconds, 0.0)
            val status = MainActivity::class.java.getDeclaredField("statusView").let { field ->
                field.isAccessible = true
                (field.get(activity) as TextView).text.toString()
            }
            assertFalse(status.startsWith("Invalid automation request:"))
        } finally {
            controller.destroy()
        }
    }

    @Test
    fun activityContractFailsClosedForMissingWrongTypeAndInvalidMode() {
        val missing = diagnosticActivityExtras("off").apply {
            remove(AutomationIntentParser.EXTRA_DIAGNOSTIC_PERFETTO_STARTED)
        }
        val wrongType = diagnosticActivityExtras("off").apply {
            this[AutomationIntentParser.EXTRA_DIAGNOSTIC_PERFETTO_STARTED] = "false"
        }
        val invalidMode = diagnosticActivityExtras("off").apply {
            this[AutomationIntentParser.EXTRA_DIAGNOSTIC_PERFETTO] = "automatic"
        }
        val unsafeFilename = diagnosticActivityExtras("on").apply {
            this[AutomationIntentParser.EXTRA_DIAGNOSTIC_TRACE_FILENAME] =
                "../escape.perfetto-trace"
        }

        listOf(missing, wrongType, invalidMode, unsafeFilename).forEach { extras ->
            try {
                parseThroughActivityContract(extras)
                throw AssertionError("invalid Activity extra set was accepted")
            } catch (_: IllegalArgumentException) {
                // Expected: the same extraction path used by MainActivity fails closed.
            }
        }
    }

    @Test
    fun manualV1DiagnosticPreservesLegacyTraceMarkerPolicy() {
        val config = RunConfig(
            resource = ResourceTarget.GPU,
            limit = RunLimit.Duration(10),
            warmupCount = 0,
            experimentMode = ExperimentMode.DIAGNOSTIC,
        )

        assertEquals(ProtocolVersion.V1, config.protocolVersion)
        assertTrue(config.shouldEmitTraceMarkers)
        assertFalse(config.diagnosticPerfettoEnabled)
    }
}
