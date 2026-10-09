package com.example.d1check.benchmarkrunner

import org.json.JSONObject

/** Separate bounded diagnostic. Legacy 1800s regimens are never extended. */
internal object EnergyTailObservation {
    const val VERSION = "tail-observation-regimen-v1"
    const val PROTOCOL = "energy-ap-tail-observation-v1"
    const val WATCHDOG_MS = 3_540_000L
    const val COOLING_SECONDS = 1920
    const val COMMON_SECONDS = 600
    fun blocks(profile: String): List<EnergyStateCalibration.Block> = when (profile) {
        "C0_LONG" -> listOf(EnergyStateCalibration.Block("registered_no_work", emptyList(), COMMON_SECONDS))
        "LOAD_A_LONG" -> EnergyResidentIdentification.blocks("DEV_A")
        else -> throw IllegalArgumentException("unregistered tail profile")
    }
    fun workCap(profile: String) = blocks(profile).sumOf { it.lanes.size * it.seconds * 4 }
    fun validate(m: JSONObject): String {
        val profile = m.getString("identification_profile")
        val expected = blocks(profile)
        require(!m.has("resident_identification_version") && m.getString("protocol") == PROTOCOL)
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
