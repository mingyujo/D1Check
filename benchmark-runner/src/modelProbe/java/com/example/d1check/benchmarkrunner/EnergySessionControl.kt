package com.example.d1check.benchmarkrunner

/** Session-local continuation is deliberately diagnostic: host AP/quality evidence remains required. */
internal object EnergySessionControl {
    const val HOST_GATED = "host-gated-v1"
    const val DEVICE_AFTER_PROBE = "device-after-probe-diagnostic-v1"

    fun validate(value: String, calibration: Boolean, diagnosticOnly: Boolean): String {
        require(value == HOST_GATED || value == DEVICE_AFTER_PROBE) { "unsupported session control" }
        require(value != DEVICE_AFTER_PROBE || (calibration && diagnosticOnly)) {
            "device continuation requires state-calibration diagnostic manifest"
        }
        return value
    }

    fun hostArmRequired(value: String, gate: String): Boolean {
        require(gate in setOf("warmup", "serial_probe", "probe", "baseline"))
        return value == HOST_GATED || gate != "baseline"
    }
}
