package com.example.d1check.benchmarkrunner

/** Opt-in causal three-policy study. No recorded future dispatch is accepted. */
internal object ArrivalPolicyStudy {
    const val VERSION = "online-policy-model-study-v1"
    const val CPU = "CPU_URGENT_ONLINE_V1"
    const val PARALLEL = "B2_PARALLEL_ONLINE_V1"
    const val SERIAL = "B2_SERIAL_ONLINE_V1"
    val POLICIES = setOf(CPU, PARALLEL, SERIAL)
    const val COUNT = 96

    /** Separate measurement protocol; legacy timing cannot change implicitly. */
    fun samplePeriodMs(studyVersion: String, samplingVersion: String, requestedMs: Long): Long {
        if (samplingVersion.isEmpty()) {
            require(requestedMs == 1000L)
            return 1000L
        }
        require(studyVersion == VERSION && samplingVersion == "online-power-phase-audit-v1")
        require(requestedMs == 900L || requestedMs == 1000L)
        return requestedMs
    }

    fun validate(version: String, policy: String, role: String, scenario: String,
                 requests: List<ArrivalEnergyContract.Request>) {
        require(version == VERSION && policy in POLICIES && scenario == "sustained_mixed")
        require(role in setOf("development", "confirmation"))
        val interval = if (role == "development") 500L else 550L
        require(requests.size == COUNT && requests.map { it.id }.toSet().size == COUNT)
        requests.forEachIndexed { i, q ->
            val urgent = i % 4 == 1
            require(q.ordinal == i && q.offsetMs == 35_000L + i * interval)
            require(q.task == (if (urgent) "classification" else "detection"))
            require(q.priority == (if (urgent) "urgent" else "normal"))
            require(q.deadlineMs == (if (urgent) 1500L else 6000L))
        }
    }

    fun choose(policy: String, waiting: List<ArrivalPolicy.Ticket>, freeCpu: Boolean,
               freeGpu: Boolean): ArrivalPolicy.Choice? {
        require(policy in POLICIES)
        if ((policy == CPU || policy == SERIAL) && (!freeCpu || !freeGpu)) return null
        val ordered = waiting.sortedWith(compareBy<ArrivalPolicy.Ticket> { it.priority != "urgent" }
            .thenBy { it.ordinal }.thenBy { it.id })
        for (q in ordered) {
            val lane = if (policy == CPU || q.task == "detection") "CPU" else "GPU"
            if ((lane == "CPU" && freeCpu) || (lane == "GPU" && freeGpu))
                return ArrivalPolicy.Choice(q, lane, "online_arrived_priority_then_ordinal")
        }
        return null
    }
}
