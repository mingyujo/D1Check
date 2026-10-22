package com.example.d1check.benchmarkrunner

/** One pre-load approval only; never interprets thermal status as numeric AP. */
internal object ArrivalStartApGate {
    const val VERSION = "numeric-ap-once-v1"
    const val DIAGNOSTIC_VERSION = "numeric-ap-observe-v2"
    const val WAIT_NS = 30_000_000_000L
    const val MAX_AGE_NS = 3_000_000_000L
    data class Reading(val before: Long, val after: Long, val ap: Double)
    fun parse(text: String, hash: String, ready: Long, mode: String = VERSION): Reading {
        require(mode == VERSION || mode == DIAGNOSTIC_VERSION) { "unknown AP gate mode" }
        val fields = text.trim().split(Regex("\\s+"))
        require(fields.size == 6 && fields[0] == hash && fields[1].toLong() == ready) { "AP approval identity" }
        val r = Reading(fields[2].toLong(), fields[3].toLong(), fields[4].toDouble())
        require(r.before >= ready && r.after >= r.before && fields[5] == "0") { "AP clock/thermal" }
        require(r.ap.isFinite() && (mode == DIAGNOSTIC_VERSION || r.ap in 32.5..34.0)) {
            "AP outside initial development support"
        }
        return r
    }
    fun atStart(r: Reading, start: Long) {
        require(start >= r.after && start - r.before <= MAX_AGE_NS) { "AP reading stale at actual start" }
    }
}
