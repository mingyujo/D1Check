package com.example.d1check.benchmarkrunner

import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Build
import android.os.PowerManager

internal data class PilotSafetySnapshot(
    val androidThermalStatus: Int,
    val plugged: Int,
    val batteryStatus: Int,
    val batteryLevelPercent: Int,
    val batteryTemperatureC: Double,
)

internal data class PilotSafetyCheck(
    val snapshot: PilotSafetySnapshot,
    val rejectionReasons: List<String>,
) {
    val passed: Boolean get() = rejectionReasons.isEmpty()
    val formalEnergyEligible: Boolean
        get() = passed && snapshot.batteryLevelPercent in
            PilotSafetyPolicy.FORMAL_ENERGY_MIN_BATTERY_PERCENT..
            PilotSafetyPolicy.FORMAL_ENERGY_MAX_BATTERY_PERCENT

    fun metadata(): Map<String, Any?> = linkedMapOf(
        "safety_policy_scope" to "PILOT_START_ONLY",
        "pilot_safety_policy_version" to 1,
        "pilot_max_android_thermal_status" to PilotSafetyPolicy.MAX_ANDROID_THERMAL_STATUS,
        "pilot_require_unplugged" to true,
        "pilot_required_battery_status" to PilotSafetyPolicy.REQUIRED_BATTERY_STATUS,
        "pilot_min_battery_pct" to PilotSafetyPolicy.MIN_BATTERY_PERCENT,
        "pilot_max_battery_pct" to PilotSafetyPolicy.MAX_BATTERY_PERCENT,
        "pilot_max_battery_temp_C" to PilotSafetyPolicy.MAX_BATTERY_TEMPERATURE_C,
        "pilot_android_thermal_status" to snapshot.androidThermalStatus,
        "pilot_plugged" to snapshot.plugged,
        "pilot_battery_status" to snapshot.batteryStatus,
        "pilot_battery_pct" to snapshot.batteryLevelPercent,
        "pilot_battery_temp_C" to snapshot.batteryTemperatureC,
        "pilot_safety_pass" to passed,
        "pilot_safety_rejection_reasons" to rejectionReasons.joinToString(","),
        "formal_energy_recommended_min_battery_pct" to
            PilotSafetyPolicy.FORMAL_ENERGY_MIN_BATTERY_PERCENT,
        "formal_energy_recommended_max_battery_pct" to
            PilotSafetyPolicy.FORMAL_ENERGY_MAX_BATTERY_PERCENT,
        "formal_energy_eligible" to formalEnergyEligible,
        "formal_safety_limits_applied" to false,
        "matched_start_limits_applied" to false,
    )
}

internal object PilotSafetyPolicy {
    const val MAX_ANDROID_THERMAL_STATUS = 1 // PowerManager.THERMAL_STATUS_LIGHT
    const val REQUIRED_BATTERY_STATUS = 3 // BatteryManager.BATTERY_STATUS_DISCHARGING
    const val MIN_BATTERY_PERCENT = 30
    const val MAX_BATTERY_PERCENT = 100
    const val FORMAL_ENERGY_MIN_BATTERY_PERCENT = 30
    const val FORMAL_ENERGY_MAX_BATTERY_PERCENT = 90
    const val MAX_BATTERY_TEMPERATURE_C = 35.0

    fun evaluate(snapshot: PilotSafetySnapshot): PilotSafetyCheck {
        val reasons = buildList {
            if (snapshot.androidThermalStatus !in 0..MAX_ANDROID_THERMAL_STATUS) {
                add("android_thermal_status")
            }
            if (snapshot.plugged != 0) add("device_plugged")
            if (snapshot.batteryStatus != REQUIRED_BATTERY_STATUS) add("not_discharging")
            if (snapshot.batteryLevelPercent !in MIN_BATTERY_PERCENT..MAX_BATTERY_PERCENT) {
                add("battery_level")
            }
            if (!snapshot.batteryTemperatureC.isFinite() ||
                snapshot.batteryTemperatureC < 0.0 ||
                snapshot.batteryTemperatureC > MAX_BATTERY_TEMPERATURE_C
            ) {
                add("battery_temperature")
            }
        }
        return PilotSafetyCheck(snapshot, reasons)
    }

    fun readAndEvaluate(context: Context): PilotSafetyCheck {
        val battery = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
            ?: return evaluate(PilotSafetySnapshot(-1, -1, -1, -1, Double.NaN))
        val level = battery.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
        val scale = battery.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
        val levelPercent = if (level >= 0 && scale > 0) level * 100 / scale else -1
        val thermalStatus = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            context.getSystemService(PowerManager::class.java).currentThermalStatus
        } else {
            -1
        }
        return evaluate(
            PilotSafetySnapshot(
                androidThermalStatus = thermalStatus,
                plugged = battery.getIntExtra(BatteryManager.EXTRA_PLUGGED, -1),
                batteryStatus = battery.getIntExtra(BatteryManager.EXTRA_STATUS, -1),
                batteryLevelPercent = levelPercent,
                batteryTemperatureC =
                    battery.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1) / 10.0,
            )
        )
    }
}

internal class PilotSafetyException(message: String) : IllegalStateException(message)
