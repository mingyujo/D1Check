package com.example.d1check.contract

import org.junit.Assert.assertNotEquals
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
}
