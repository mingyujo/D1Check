package com.example.d1check.benchmarkrunner

/** Separate opt-in protocol: one resident owner, two registered windows. */
internal object ArrivalHistoryControl {
    const val VERSION = "registered-history-control-v1"
    const val WATCHDOG_MS = 900_000L
    fun validate(version: String, gap: Long, role: String, policy: String,
                 conditioning: List<ArrivalEnergyContract.Request>, target: List<ArrivalEnergyContract.Request>) {
        require(version == VERSION && gap in setOf(30L,180L))
        require(role in setOf("development","confirmation"))
        require(policy in setOf("C0",ArrivalPolicyStudy.CPU,ArrivalPolicyStudy.PARALLEL))
        ArrivalPolicyStudy.validate(ArrivalPolicyStudy.VERSION,ArrivalPolicyStudy.CPU,"confirmation",
            "separated_power",conditioning,ArrivalPolicyStudy.SEPARATED_POWER)
        if (policy == "C0") require(target.isEmpty()) else
            ArrivalPolicyStudy.validate(ArrivalPolicyStudy.VERSION,policy,"confirmation",
                "separated_power",target,ArrivalPolicyStudy.SEPARATED_POWER)
        require((conditioning+target).map { it.id }.toSet().size == conditioning.size+target.size)
    }
    fun watchdog(version: String) = if (version.isEmpty()) ArrivalEnergyContract.WATCHDOG_MS
        else { require(version == VERSION); WATCHDOG_MS }

    fun execute(healthy: () -> Unit, conditioning: () -> Unit, recoveryAndBaseline: () -> Unit,
                target: () -> Unit) {
        healthy(); conditioning(); healthy(); recoveryAndBaseline(); healthy(); target(); healthy()
    }
}
