package com.example.d1check.contract

import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.nio.file.Files

class RunnerFileNamingTest {
    @Test
    fun twoSessionsForSameRunUseDifferentFiles() {
        val directory = Files.createTempDirectory("runner-files").toFile()
        try {
            val first = GpuTelemetry.createOutputFile(directory, "run", "session-a")
            val second = GpuTelemetry.createOutputFile(directory, "run", "session-b")
            assertNotEquals(first.name, second.name)
            assertTrue(first.exists())
            assertTrue(second.exists())
        } finally {
            directory.deleteRecursively()
        }
    }

    @Test(expected = IllegalStateException::class)
    fun existingSessionFileCannotBeOverwritten() {
        val directory = Files.createTempDirectory("runner-create-new").toFile()
        GpuTelemetry.createOutputFile(directory, "run", "session")
        GpuTelemetry.createOutputFile(directory, "run", "session")
    }

    @Test
    fun diagnosticIdsAreRejectedBeforeAnyDirectoryOrFileCreation() {
        val parent = Files.createTempDirectory("runner-unsafe-parent").toFile()
        try {
            val output = parent.resolve("diagnostics-v2")
            val valid = "11111111-1111-1111-1111-111111111111"
            listOf(
                "../escape" to valid,
                "C:\\escape" to valid,
                valid to "../../session",
                valid to "11111111-1111-1111-1111-111111111111/child",
            ).forEach { (runId, sessionId) ->
                try {
                    GpuTelemetry.createOutputFile(
                        output,
                        runId,
                        sessionId,
                        requireCanonicalIds = true,
                    )
                    throw AssertionError("unsafe diagnostic identity was accepted")
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
