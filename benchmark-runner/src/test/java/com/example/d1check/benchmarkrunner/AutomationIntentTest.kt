package com.example.d1check.benchmarkrunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

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
}
