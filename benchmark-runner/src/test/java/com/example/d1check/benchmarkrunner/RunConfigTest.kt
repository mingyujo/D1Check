package com.example.d1check.benchmarkrunner

import org.junit.Test

class RunConfigTest {
    private fun config(warmup: Int) = RunConfig(
        resource = ResourceTarget.GPU,
        limitMode = LimitMode.COUNT,
        inferenceCount = 1,
        durationSeconds = 1,
        warmupCount = warmup,
        experimentMode = ExperimentMode.BASIC,
    )

    @Test(expected = IllegalArgumentException::class)
    fun warmupCountAboveLimitIsRejected() {
        config(RunConfig.MAX_WARMUP_COUNT + 1)
    }
}
