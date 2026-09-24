package com.example.d1check.npurunner

import kotlin.math.roundToLong

/*
 * 미러 원본: benchmark-runner/.../DutyCycle.kt — 로직 무변경 (패키지만 다르다).
 * duty 의미가 CPU/GPU 와 같아야 validate_result 의 duty_* 검사를 같은 식으로 통과한다.
 */

internal data class DutyCycleMetrics(
    val requestedPercent: Int,
    val periodNs: Long,
    val targetActiveDurationNs: Long,
    val actualActiveDurationNs: Long,
    val actualIdleDurationNs: Long,
    val achievedPercent: Double,
    val completedCycleCount: Long,
    val activeOverrunNs: Long,
)

/** Monotonic duty schedule anchored at load_start. COUNT runs do not instantiate this class. */
internal class DutyCycleTracker(
    val requestedPercent: Int,
    val periodNs: Long,
    private val startedNs: Long,
    private val targetDurationNs: Long,
) {
    init {
        require(requestedPercent in 1..100)
        require(periodNs > 0L)
        require(targetDurationNs > 0L)
    }

    private val activeWindowNs: Long = if (requestedPercent == 100) {
        periodNs
    } else {
        percentageOf(periodNs, requestedPercent).coerceAtLeast(1L)
    }
    private var idleDurationNs = 0L
    private var activeOverrunNs = 0L

    fun nanosUntilActive(nowNs: Long): Long {
        if (requestedPercent == 100) return 0L
        val elapsed = (nowNs - startedNs).coerceAtLeast(0L)
        if (elapsed >= targetDurationNs) return 0L
        val phase = elapsed % periodNs
        return if (phase < activeWindowNs) 0L else periodNs - phase
    }

    fun recordIdle(startNs: Long, endNs: Long) {
        idleDurationNs += (endNs - startNs).coerceAtLeast(0L)
    }

    fun recordInference(startNs: Long, endNs: Long) {
        if (requestedPercent == 100 || endNs <= startNs) return
        val elapsedAtStart = (startNs - startedNs).coerceAtLeast(0L)
        val phase = elapsedAtStart % periodNs
        if (phase < activeWindowNs) {
            val elapsedAtEnd = (endNs - startedNs).coerceAtLeast(elapsedAtStart)
            val activeOverlapNs = scheduledActiveDuration(elapsedAtEnd) -
                scheduledActiveDuration(elapsedAtStart)
            activeOverrunNs += ((endNs - startNs) - activeOverlapNs).coerceAtLeast(0L)
        }
    }

    fun metrics(endedNs: Long): DutyCycleMetrics {
        val actualDurationNs = (endedNs - startedNs).coerceAtLeast(0L)
        val actualIdleNs = idleDurationNs.coerceIn(0L, actualDurationNs)
        val actualActiveNs = actualDurationNs - actualIdleNs
        return DutyCycleMetrics(
            requestedPercent = requestedPercent,
            periodNs = periodNs,
            targetActiveDurationNs = scheduledActiveDuration(targetDurationNs),
            actualActiveDurationNs = actualActiveNs,
            actualIdleDurationNs = actualIdleNs,
            achievedPercent = if (actualDurationNs == 0L) {
                0.0
            } else {
                actualActiveNs * 100.0 / actualDurationNs
            },
            completedCycleCount = actualDurationNs / periodNs,
            activeOverrunNs = activeOverrunNs,
        )
    }

    private fun scheduledActiveDuration(durationNs: Long): Long {
        if (requestedPercent == 100) return durationNs
        val completePeriods = durationNs / periodNs
        val remainder = durationNs % periodNs
        return completePeriods * activeWindowNs + minOf(remainder, activeWindowNs)
    }

    companion object {
        fun periodNanos(seconds: Double): Long {
            require(seconds.isFinite() && seconds > 0.0)
            return (seconds * NANOS_PER_SECOND).roundToLong().coerceAtLeast(1L)
        }

        private const val NANOS_PER_SECOND = 1_000_000_000.0

        private fun percentageOf(value: Long, percent: Int): Long =
            (value / 100L) * percent + (value % 100L) * percent / 100L
    }
}
