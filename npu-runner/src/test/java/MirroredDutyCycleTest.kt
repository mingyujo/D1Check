// 미러 테스트: benchmark-runner/src/test/java/com/example/d1check/benchmarkrunner/DutyCycleTest.kt 를 패키지 줄만 바꿔 그대로 옮겼다.
// npu-runner 로 옮긴 DutyCycle/RunTermination/CommandReplay/PilotSafety 가 원본과 같은 동작임을 원본 테스트로 고정한다.
package com.example.d1check.npurunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DutyCycleTest {
    @Test
    fun hundredPercentPreservesContinuousDurationLoad() {
        val tracker = DutyCycleTracker(100, 10_000L, 1_000L, 40_000L)

        assertEquals(0L, tracker.nanosUntilActive(1_000L))
        assertEquals(0L, tracker.nanosUntilActive(40_999L))
        val metrics = tracker.metrics(41_000L)
        assertEquals(40_000L, metrics.targetActiveDurationNs)
        assertEquals(40_000L, metrics.actualActiveDurationNs)
        assertEquals(0L, metrics.actualIdleDurationNs)
        assertEquals(100.0, metrics.achievedPercent, 0.0)
        assertEquals(0L, metrics.activeOverrunNs)
    }

    @Test
    fun quarterHalfAndThreeQuarterSchedulesExplainActivePlusIdle() {
        for (percent in listOf(25, 50, 75)) {
            val period = 10_000L
            val duration = 40_000L
            val tracker = DutyCycleTracker(percent, period, 0L, duration)
            val activePerPeriod = period * percent / 100
            val idlePerPeriod = period - activePerPeriod
            repeat(4) { cycle ->
                val idleStart = cycle * period + activePerPeriod
                tracker.recordIdle(idleStart, idleStart + idlePerPeriod)
            }

            val metrics = tracker.metrics(duration)
            assertEquals(duration * percent / 100, metrics.targetActiveDurationNs)
            assertEquals(duration * percent / 100, metrics.actualActiveDurationNs)
            assertEquals(duration * (100 - percent) / 100, metrics.actualIdleDurationNs)
            assertEquals(duration, metrics.actualActiveDurationNs + metrics.actualIdleDurationNs)
            assertEquals(percent.toDouble(), metrics.achievedPercent, 0.0)
            assertEquals(4L, metrics.completedCycleCount)
            assertEquals(idlePerPeriod, tracker.nanosUntilActive(activePerPeriod))
        }
    }

    @Test
    fun inferenceCrossingActiveBoundaryAccumulatesOnlyIdleIntrusion() {
        val tracker = DutyCycleTracker(25, 10_000L, 0L, 20_000L)

        tracker.recordInference(2_400L, 2_700L)
        tracker.recordInference(12_450L, 20_500L)

        assertEquals(7_700L, tracker.metrics(20_500L).activeOverrunNs)
    }

    @Test
    fun durationTerminationStillUsesWholeElapsedTimeDuringIdle() {
        val termination = RunTermination(RunLimit.Duration(1), 5_000L)
        val tracker = DutyCycleTracker(25, 1_000_000_000L, 5_000L, 1_000_000_000L)

        assertTrue(tracker.nanosUntilActive(250_005_000L) > 0L)
        assertEquals(
            TerminationReason.DURATION_COMPLETE,
            termination.completionReason(1_000_005_000L, 1L),
        )
    }
}
