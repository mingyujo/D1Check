package com.example.d1check.benchmarkrunner

import org.junit.Assert.assertEquals
import org.junit.Test

class RunConfigTest {
    private fun config(warmup: Int) = RunConfig(
        resource = ResourceTarget.GPU,
        limit = RunLimit.Count(1),
        warmupCount = warmup,
        experimentMode = ExperimentMode.BASIC,
    )

    @Test(expected = IllegalArgumentException::class)
    fun warmupCountAboveLimitIsRejected() {
        config(RunConfig.MAX_WARMUP_COUNT + 1)
    }

    @Test
    fun cpu4LegacyAliasNormalizesToCpuFourWithoutAffinity() {
        val config = RunConfig(
            resource = ResourceTarget.CPU4,
            limit = RunLimit.Count(1),
            warmupCount = 0,
            experimentMode = ExperimentMode.BASIC,
        )

        assertEquals(ResourceTarget.CPU, config.normalizedResource)
        assertEquals(4, config.cpuThreads)
        assertEquals("CPU4", config.legacyResourceAlias)
    }
}
