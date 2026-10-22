package com.example.d1check.benchmarkrunner

/** Explicit low-battery diagnostic; legacy arrival sessions retain their 20% gate. */
internal object ArrivalBatteryGate {
    const val VERSION = "model-v3-arrival-low-battery-v1"

    fun minimum(version: String?, requested: Int?): Int {
        if (version == null) {
            require(requested == null || requested == 20) { "arrival battery floor requires explicit diagnostic" }
            return 20
        }
        require(version == VERSION && requested == 6) { "unsupported arrival battery diagnostic/floor" }
        return 6
    }

    fun admitted(level: Int?, scale: Int?, minimum: Int): Boolean {
        require(minimum == 20 || minimum == 6) { "unsupported arrival battery floor" }
        return level != null && scale == 100 && level in minimum..100
    }
}
