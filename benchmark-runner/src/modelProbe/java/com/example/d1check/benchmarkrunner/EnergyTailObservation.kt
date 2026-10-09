package com.example.d1check.benchmarkrunner

import org.json.JSONObject

/** Separate bounded diagnostic. Legacy 1800s regimens are never extended. */
internal object EnergyTailObservation {
    const val VERSION = "tail-observation-regimen-v1"
    const val PROTOCOL = "energy-ap-tail-observation-v1"
    const val LOW_BATTERY_PROTOCOL = "energy-ap-tail-observation-low-battery-v1"
    const val LOW_BATTERY_GATE = "tail-battery-stop5-v1"
    fun lowBattery(m: JSONObject) = m.optString("tail_battery_gate_version", "") == LOW_BATTERY_GATE
    fun protocol(m: JSONObject) = if (lowBattery(m)) LOW_BATTERY_PROTOCOL else PROTOCOL
    fun batteryMinimum(m: JSONObject): Int {
        if (!m.has("tail_battery_gate_version")) return 20
        require(lowBattery(m) && m.getInt("battery_min_percent") == 6 && m.getInt("battery_stop_at_percent") == 5)
        return 6 // 6% admitted, <=5% stops. Separate user-authorized protocol.
    }
    fun batteryAdmitted(level: Int?, scale: Int?, minimum: Int): Boolean {
        require(minimum == 20 || minimum == 6)
        return level != null && scale == 100 && level in minimum..100
    }
    const val WATCHDOG_MS = 3_540_000L
    const val COOLING_SECONDS = 1920
    const val COMMON_SECONDS = 600
    fun blocks(profile: String): List<EnergyStateCalibration.Block> = when (profile) {
        "C0_LONG" -> listOf(EnergyStateCalibration.Block("registered_no_work", emptyList(), COMMON_SECONDS))
        "LOAD_A_LONG" -> EnergyResidentIdentification.blocks("DEV_A")
        else -> throw IllegalArgumentException("unregistered tail profile")
    }
    fun workCap(profile: String) = blocks(profile).sumOf { it.lanes.size * it.seconds * 4 }
    fun requireCommonEnd(specified: List<EnergyStateCalibration.Block>, elapsedNs: Long, commonNs: Long) {
        require(commonNs == COMMON_SECONDS * 1_000_000_000L && elapsedNs >= 0)
        if (specified == blocks("C0_LONG")) {
            // C0 intentionally fills the entire common window: there is no work
            // completion tail to reserve. Whole watchdog/health checks still apply.
            check(elapsedNs >= commonNs) { "registered C0 window unfinished" }
        } else {
            require(specified == blocks("LOAD_A_LONG"))
            check(elapsedNs < commonNs) { "no common-window tail reserve" }
        }
    }
    fun validate(m: JSONObject): String {
        val profile = m.getString("identification_profile")
        val expected = blocks(profile)
        require(!m.has("resident_identification_version") && m.getString("protocol") == protocol(m))
        batteryMinimum(m)
        require(m.getString("tail_observation_version") == VERSION && m.getString("calibration_version") == VERSION)
        require(m.getBoolean("state_model_calibration") && m.getBoolean("operational_only") &&
            m.getBoolean("autonomous_diagnostic_only") && !m.getBoolean("experiment_ready"))
        require(m.getString("session_control") == EnergySessionControl.DEVICE_AFTER_PROBE && m.getString("mode") == "calibration")
        require(m.getLong("maximum_duration_ms") == WATCHDOG_MS && m.getInt("cooling_seconds") == COOLING_SECONDS &&
            m.getInt("common_work_seconds") == COMMON_SECONDS && m.getInt("baseline_seconds") == 120)
        require(m.getInt("work_call_cap") == workCap(profile) && m.getInt("cadence_ms") == 250 &&
            m.getInt("power_sample_period_ms") == 900 && m.getString("start_ap_gate") == ArrivalStartApGate.DIAGNOSTIC_VERSION)
        val specified = m.getJSONArray("blocks")
        require(specified.length() == expected.size && expected.indices.all { i ->
            val row = specified.getJSONObject(i); val lanes = row.getJSONArray("lane_indices")
            row.getString("id") == expected[i].id && row.getInt("seconds") == expected[i].seconds &&
                (0 until lanes.length()).map(lanes::getInt) == expected[i].lanes
        })
        return profile
    }
}
