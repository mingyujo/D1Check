package com.example.d1check.benchmarkrunner

/** Opt-in same-four-resident identification; legacy two-key regimens stay unchanged. */
internal object EnergyResidentIdentification {
    const val VERSION = "resident-identification-regimen-v1"
    const val PROTOCOL = "energy-ap-resident-identification-v1"
    const val CADENCE_NS = 250_000_000L
    const val WATCHDOG_MS = 1_800_000L
    val KEYS = listOf("classification_CPU", "classification_GPU", "detection_CPU", "detection_GPU")
    fun blocks(profile: String): List<EnergyStateCalibration.Block> {
        if (profile in setOf("CONF_MIX_A", "CONF_MIX_B")) return (0 until 4).flatMap { cycle ->
            val singles = if (profile=="CONF_MIX_A") listOf(0,1,2) else listOf(2,1,0)
            singles.flatMap { key -> listOf(EnergyStateCalibration.Block("cycle${cycle}_solo$key",listOf(key),if (key==2) 4 else 3),
                EnergyStateCalibration.Block("cycle${cycle}_idle$key",emptyList(),2)) } +
                listOf(EnergyStateCalibration.Block("cycle${cycle}_pair",listOf(1,2),6),EnergyStateCalibration.Block("cycle${cycle}_tail",emptyList(),8))
        }
        val order = when (profile) {
            "DEV_A" -> listOf(listOf(0), listOf(2), listOf(1), listOf(1,2))
            "DEV_B" -> listOf(listOf(1,2), listOf(1), listOf(2), listOf(0))
            "CONF_A" -> listOf(listOf(1), listOf(0), listOf(1,2), listOf(2))
            "CONF_B" -> listOf(listOf(2), listOf(1,2), listOf(0), listOf(1))
            else -> error("unknown identification profile")
        }
        val duration = if (profile.startsWith("DEV_")) 60 else 30
        return order.flatMapIndexed { i, lanes -> listOf(EnergyStateCalibration.Block("state_$i",lanes,duration)) +
            if (i<3) listOf(EnergyStateCalibration.Block("idle_$i",emptyList(),90)) else emptyList() }
    }
    fun commonSeconds(profile: String) = blocks(profile).sumOf { it.seconds }+90
    fun workCap(profile: String) = blocks(profile).sumOf { it.lanes.size*it.seconds*4 }
    fun validate(version: String, profile: String, specified: List<EnergyStateCalibration.Block>, cap: Int) {
        require(version==VERSION && specified==blocks(profile) && cap==workCap(profile))
        require(specified.all { it.seconds>0 && (it.lanes.isEmpty() || it.lanes in listOf(listOf(0),listOf(1),listOf(2),listOf(1,2))) })
    }
    fun canStart(nowNs: Long, plannedStartNs: Long, plannedEndNs: Long, calls: Int, cap: Int): Boolean {
        require(plannedEndNs>plannedStartNs && calls in 0..cap)
        return nowNs in plannedStartNs until plannedEndNs && calls<cap
    }
}
