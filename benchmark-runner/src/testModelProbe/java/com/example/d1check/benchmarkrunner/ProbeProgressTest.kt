package com.example.d1check.benchmarkrunner

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File
import java.nio.file.Files

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class ProbeProgressTest {
    private val session = "00000000-0000-0000-0000-000000000001"

    @Test fun failedNativeCloseIsNeverRecordedAsFinished() {
        val root = Files.createTempDirectory("close-failure").toFile()
        try {
            val p = ProbeProgress(root, session, { 1L }, {})
            assertThrows(IllegalStateException::class.java) {
                closeProbeResource(p, "runtime_close") { error("native close failure") }
            }
            val rows = File(root, "model-probe-progress-v1/$session.jsonl").readLines().map(::JSONObject)
            assertEquals("failed", rows.last().getString("edge"))
        } finally { root.deleteRecursively() }
    }

    @Test fun cleanupStillRunsWhenDiagnosticClockFails() {
        val root = Files.createTempDirectory("progress").toFile()
        try {
            var clock = 2L
            val p = ProbeProgress(root, session, { clock }, {})
            p.mark("request_validation", "start")
            clock = 1
            var closed = false
            assertThrows(IllegalStateException::class.java) {
                closeProbeResource(p, "runtime_close") { closed = true }
            }
            assertTrue(closed)
        } finally { root.deleteRecursively() }
    }

    @Test fun rawCapturePersistsOnlyFirstInvocationWithExactHash() {
        val root = Files.createTempDirectory("capture").toFile()
        try {
            val p = ProbeProgress(root, session, { 1L }, {})
            p.bind("a".repeat(64))
            // IEEE float32 little endian 1.0.
            val bytes = byteArrayOf(0, 0, -128, 63)
            val digest = java.security.MessageDigest.getInstance("SHA-256").digest(bytes)
                .joinToString("") { "%02x".format(it) }
            val value = ProbeRawInvocation(0, "b".repeat(64), listOf(digest),
                listOf(floatArrayOf(1f)), 1L, ProbeBackend.CPU, "not_applicable_cpu")
            p.captureRaw(value)
            p.captureRaw(value)
            val capture = File(root, "model-probe-raw-v1/$session")
            assertArrayEquals(bytes, File(capture, "output_0.f32le").readBytes())
            assertEquals(2, capture.listFiles()!!.size)
            assertEquals(session, JSONObject(File(capture, "capture.json").readText()).getString("session_id"))
        } finally { root.deleteRecursively() }
    }

    @Test fun journalIsImmediatelyReadableBoundAndReplaySafe() {
        val root = Files.createTempDirectory("progress").toFile()
        try {
            var clock = 1L
            val p = ProbeProgress(root, session, { clock++ }, {})
            p.mark("request_validation", "start")
            p.bind("a".repeat(64))
            p.mark("interpreter_construction", "start")
            val file = File(root, "model-probe-progress-v1/$session.jsonl")
            val original = file.readText()
            val rows = file.readLines().map(::JSONObject)
            assertEquals(3, rows.size)
            assertEquals(2, rows.last().getInt("sequence"))
            assertEquals(3L, rows.last().getLong("mono_ns"))
            assertEquals("a".repeat(64), rows.last().getString("manifest_sha256"))
            assertEquals(session, rows.last().getString("session_id"))
            assertThrows(IllegalArgumentException::class.java) { ProbeProgress(root, session, { 4 }, {}) }
            assertEquals(original, file.readText())
        } finally { root.deleteRecursively() }
    }

    @Test fun clockRegressionAndInvalidBindingFailClosedWithoutAppending() {
        val root = Files.createTempDirectory("progress").toFile()
        try {
            var clock = 2L
            val p = ProbeProgress(root, session, { clock }, {})
            p.mark("request_validation", "start")
            clock = 1
            assertThrows(IllegalStateException::class.java) { p.mark("request_validation", "finish") }
            assertThrows(IllegalArgumentException::class.java) { p.bind("invalid") }
            assertEquals(1, File(root, "model-probe-progress-v1/$session.jsonl").readLines().size)
            assertThrows(IllegalArgumentException::class.java) { ProbeProgress(root, "../escape", { 1 }, {}) }
        } finally { root.deleteRecursively() }
    }
}
