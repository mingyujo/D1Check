package com.example.d1check.benchmarkrunner

/** Opt-in causal three-policy study. No recorded future dispatch is accepted. */
internal object ArrivalPolicyStudy {
    const val VERSION = "online-policy-model-study-v1"
    const val CPU = "CPU_URGENT_ONLINE_V1"
    const val PARALLEL = "B2_PARALLEL_ONLINE_V1"
    const val SERIAL = "B2_SERIAL_ONLINE_V1"
    val POLICIES = setOf(CPU, PARALLEL, SERIAL)
    const val COUNT = 96
    const val SEPARATED_POWER = "separated-power-input-v1"
    const val SUSTAINED_CONFIRMATION = "sustained-confirmation-v1"

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
                 requests: List<ArrivalEnergyContract.Request>, inputVersion: String = "") {
        require(version == VERSION && policy in POLICIES)
        require(inputVersion in setOf("", SEPARATED_POWER, SUSTAINED_CONFIRMATION))
        require(scenario == if (inputVersion.isEmpty()) "sustained_mixed" else "separated_power")
        require(role in setOf("development", "confirmation"))
        val interval = if (role == "development") 500L else 550L
        val sustained = inputVersion == SUSTAINED_CONFIRMATION
        if (sustained) require(role == "confirmation" && policy in setOf(CPU, PARALLEL))
        val count = if (sustained) 192 else COUNT
        require(requests.size == count && requests.map { it.id }.toSet().size == count)
        requests.forEachIndexed { i, q ->
            val separated = inputVersion == SEPARATED_POWER
            val urgent = if (sustained) i % 2 == 0 else if (!separated) i % 4 == 1 else if (role == "development")
                i < 32 || (i >= 64 && i % 2 == 0) else i % 2 == 0
            val offset = if (sustained) 35_000L + i * 400L else if (!separated) 35_000L + i * interval else if (role == "development")
                (if (i < 32) 35_000L else if (i < 64) 55_000L else 85_000L) + (i % 32) * 100L
                else 35_000L + i * 350L
            require(q.ordinal == i && q.offsetMs == offset)
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
