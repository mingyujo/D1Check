package com.example.d1check.npurunner

/*
 * 미러 원본: benchmark-runner/.../RunTermination.kt — 로직·wire name 무변경 (패키지만 다르다).
 * wire name 은 orchestrator 가 그대로 본다 (validate_result 의 duration_complete 등).
 */

internal enum class TerminationReason(val wireName: String) {
    COUNT_COMPLETE("count_complete"),
    DURATION_COMPLETE("duration_complete"),
    BUFFER_LIMIT("buffer_limit"),
    RUN_CONTEXT_MISMATCH("run_context_mismatch"),
    PILOT_SAFETY_REJECTED("pilot_safety_rejected"),
    RUN_ERROR("run_error"),
    SHUTDOWN_ERROR("shutdown_error"),
}

internal class RunTermination(
    private val limit: RunLimit,
    private val startedNs: Long,
) {
    val targetDurationNs: Long? = (limit as? RunLimit.Duration)
        ?.durationSeconds
        ?.times(NANOS_PER_SECOND)

    fun completionReason(nowNs: Long, inferenceCount: Long): TerminationReason? = when (limit) {
        is RunLimit.Count -> if (inferenceCount >= limit.inferenceCount) {
            TerminationReason.COUNT_COMPLETE
        } else {
            null
        }
        is RunLimit.Duration -> if (nowNs - startedNs >= checkNotNull(targetDurationNs)) {
            TerminationReason.DURATION_COMPLETE
        } else {
            null
        }
    }

    fun actualDurationNs(endedNs: Long): Long = (endedNs - startedNs).coerceAtLeast(0L)

    fun durationOverrunNs(endedNs: Long): Long? = targetDurationNs?.let {
        (actualDurationNs(endedNs) - it).coerceAtLeast(0L)
    }

    companion object {
        private const val NANOS_PER_SECOND = 1_000_000_000L
    }
}
