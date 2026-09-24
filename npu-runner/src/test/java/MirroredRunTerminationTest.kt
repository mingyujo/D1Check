// 미러 테스트: benchmark-runner/src/test/java/com/example/d1check/benchmarkrunner/RunTerminationTest.kt 를 패키지 줄만 바꿔 그대로 옮겼다.
// npu-runner 로 옮긴 DutyCycle/RunTermination/CommandReplay/PilotSafety 가 원본과 같은 동작임을 원본 테스트로 고정한다.
package com.example.d1check.npurunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class RunTerminationTest {
    @Test
    fun durationModeIgnoresInferenceCountAndStopsAtDeadline() {
        val termination = RunTermination(RunLimit.Duration(60), 1_000L)

        assertNull(termination.completionReason(59_000_001_000L, 1_000L))
        assertEquals(
            TerminationReason.DURATION_COMPLETE,
            termination.completionReason(60_000_001_000L, 50_000L),
        )
    }

    @Test
    fun countModeStopsAtRequestedCount() {
        val termination = RunTermination(RunLimit.Count(1_000), 100L)

        assertNull(termination.completionReason(Long.MAX_VALUE, 999L))
        assertEquals(
            TerminationReason.COUNT_COMPLETE,
            termination.completionReason(Long.MAX_VALUE, 1_000L),
        )
    }

    @Test
    fun durationOverrunIsRecorded() {
        val termination = RunTermination(RunLimit.Duration(60), 2_000L)

        assertEquals(25L, termination.durationOverrunNs(60_000_002_025L))
    }
}
