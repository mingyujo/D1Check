package com.example.d1check.benchmarkrunner

/** Opt-in observation only; never chooses a backend or changes a coefficient. */
internal object ArrivalBackgroundObservation {
    const val VERSION = "background-activity-contrast-v1"
    const val CONTROL = "resident-control-pair-v1"
    fun validate(version: String, policy: String, role: String, scenario: String,
                 requests: List<ArrivalEnergyContract.Request>, control: String) {
        require(version == VERSION && role == "development")
        if (control.isNotEmpty()) {
            require(control == CONTROL && policy == ArrivalRecordedReplay.POLICY)
            ArrivalEnergyContract.validateSession(scenario, requests, control, "no_load_control")
        } else {
            require(policy in setOf(ArrivalPolicyStudy.CPU, ArrivalPolicyStudy.PARALLEL))
            // Same registered 48:48/350ms confirmation input, used here as new development.
            ArrivalPolicyStudy.validate(ArrivalPolicyStudy.VERSION, policy, "confirmation", scenario,
                requests, ArrivalPolicyStudy.SEPARATED_POWER)
        }
    }
}

/** Bounded past-only delivery. No file/sensor/inference operation under its lock. */
internal class ArrivalPastPowerWindow {
    data class Sample(val midpoint: Long, val ready: Long, val watts: Double?, val cpuMs: Long)
    private val samples = ArrayDeque<Sample>()
    @Synchronized fun add(sample: Sample) {
        require(sample.midpoint <= sample.ready && sample.cpuMs >= 0)
        require(samples.isEmpty() || (sample.midpoint > samples.last().midpoint && sample.ready >= samples.last().ready))
        if (samples.size == 128) samples.removeFirst()
        samples.addLast(sample)
    }
    @Synchronized private fun copy() = samples.toList()
    fun at(issue: Long): Map<String, Any?> {
        val eligible = copy().filter { it.ready <= issue }
        val last = eligible.lastOrNull()
        fun invalid(reason: String) = mapOf("issue_ns" to issue, "status" to reason,
            "mean_whole_device_w" to null, "self_cpu_fraction" to null,
            "future_ap_used" to false, "capacity" to 128)
        if (last == null || issue-last.ready > 3_000_000_000L) return invalid("missing_or_stale")
        val end = last.midpoint; val begin = end-10_000_000_000L
        val rows = eligible.filter { it.midpoint >= begin }.toMutableList()
        eligible.lastOrNull { it.midpoint < begin }?.let { rows.add(0,it) }
        if (rows.size < 2 || rows.first().midpoint > begin) return invalid("insufficient_past_window")
        if (rows.any { it.watts == null || !it.watts.isFinite() } ||
            rows.zipWithNext().any { (a,b) -> b.midpoint-a.midpoint > 2_500_000_000L || b.cpuMs < a.cpuMs })
            return invalid("invalid_or_gap")
        var joules = 0.0
        for ((a,b) in rows.zipWithNext()) {
            val left = maxOf(a.midpoint,begin); val fraction = (left-a.midpoint).toDouble()/(b.midpoint-a.midpoint)
            val wl = a.watts!! + (b.watts!!-a.watts)*fraction
            joules += (wl+b.watts!!)/2 * (b.midpoint-left)/1e9
        }
        val a=rows.first(); val b=rows[1]
        val cpuBegin=a.cpuMs+(b.cpuMs-a.cpuMs)*(begin-a.midpoint).toDouble()/(b.midpoint-a.midpoint)
        return mapOf("issue_ns" to issue, "window_start_ns" to begin, "window_end_ns" to end,
            "latest_ready_ns" to last.ready, "samples" to rows.size, "status" to "available",
            "mean_whole_device_w" to joules/10, "self_cpu_fraction" to (last.cpuMs-cpuBegin)/10000,
            "current_scale" to "raw_mA_conditional_not_absolute_certified", "future_ap_used" to false,
            "task_residual_w" to null, "task_residual_reason" to "requires_past_lane_exposure_join")
    }
}
