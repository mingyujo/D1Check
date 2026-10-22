package com.example.d1check.contract

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import java.nio.file.Files

@RunWith(RobolectricTestRunner::class)
class GpuTelemetryProductionPathTest {
    private val runId = "11111111-1111-1111-1111-111111111111"
    private val sessionId = "22222222-2222-2222-2222-222222222222"
    private val diagnosticId = "33333333-3333-3333-3333-333333333333"

    @Test
    fun liveLifecycleErrorLoadInferenceAndFlushUseProductionSerialization() {
        val telemetry = GpuTelemetry.connectForTest(
            D1RunContext(runId, true, 1L, 2L, "boot"),
            sessionId,
            protocolVersion = 2,
            diagnosticSessionId = diagnosticId,
            requestedTraceMode = "on",
        )
        telemetry.liveInstant("diagnostic_trace_start", "diagnostic")
        telemetry.instant("load_start", "run")
        try {
            telemetry.measured("interpreter_init", "setup") {
                throw IllegalStateException("fixture failure")
            }
        } catch (_: IllegalStateException) {
            // The production error serialization is asserted below.
        }
        assertTrue(telemetry.recordInference(20L, 30L, 0L, 1))
        telemetry.instant("load_end", "run")

        var outputFile: java.io.File? = null
        try {
            val result = telemetry.flushAfterRun(
                RuntimeEnvironment.getApplication(),
                "GPU",
                "fixture-model",
                "fixture-sha",
                mapOf("completed_inference_count" to 1L),
            )
            outputFile = result.file
            val records = result.file.readLines().map { JSONObject(it) }
            assertEquals("run_metadata", records.first().getString("event"))
            assertEquals("file_summary", records.last().getString("event"))
            assertTrue(records.any { it.getString("event") == "diagnostic_trace_start" })
            assertTrue(records.any { it.getString("event") == "load_start" })
            assertTrue(records.any { it.getString("event") == "inference" })
            assertTrue(records.any {
                it.getString("event") == "interpreter_init" && it.getString("status") == "error"
            })
            records.forEach { record ->
                assertEquals(runId, record.getString("run_id"))
                assertEquals(sessionId, record.getString("runner_session_id"))
                assertEquals(2, record.getInt("protocol_version"))
                assertEquals(diagnosticId, record.getString("diagnostic_session_id"))
                assertEquals("on", record.getString("requested_trace_mode"))
            }
        } finally {
            outputFile?.delete()
        }
    }

    @Test
    fun invalidV2RunContextAndSessionFailBeforeOutputRootExists() {
        val parent = Files.createTempDirectory("gpu-invalid-context").toFile()
        try {
            val output = parent.resolve("diagnostics-v2")
            listOf(
                "../run" to sessionId,
                runId to "../session",
            ).forEach { (badRun, badSession) ->
                try {
                    GpuTelemetry.connectForTest(
                        D1RunContext(badRun, true, 1L, 2L, "boot"),
                        badSession,
                        protocolVersion = 2,
                        diagnosticSessionId = diagnosticId,
                        requestedTraceMode = "off",
                    )
                    throw AssertionError("unsafe identity was accepted")
                } catch (_: IllegalArgumentException) {
                    assertFalse(output.exists())
                    assertTrue(parent.listFiles()?.isEmpty() == true)
                }
            }
        } finally {
            parent.deleteRecursively()
        }
    }
}
