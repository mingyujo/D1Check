package com.example.d1check.requestrunner

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Debug
import android.os.PowerManager
import android.os.SystemClock
import java.util.concurrent.atomic.AtomicLong

/*
 * 출처: feature/arrival-scheduling-20260923 @ d588323 benchmark-runner/src/modelProbe/.../ArrivalEnergyActivity.kt 99~128행 (snapshot)
 * 필드 이름을 그대로 둔다 (online-power-phase-audit-v1 과 같은 표본: current_raw · voltage_mV · charge_counter_raw · plugged ·
 * battery_temperature_deci_c · battery_level · thermal_status · interactive · snapshot_start_ns · sensor_read_end_ns).
 * 바꾼 것: V4Gate (A24 메모리 계약) 의 admission_reason 은 없다 · 멈춤 판정은 SessionEngine.stopReason (S26 규칙) 이 한다 ·
 *   S26 전류 단위 가설 (µA, 방전 음수) 을 필드로 적는다 (등록 §3-7).
 */
class BatterySampler(private val context: Context) {
    private val peak = AtomicLong(0)

    fun snapshot(): Map<String, Any?> {
        val start = SystemClock.elapsedRealtimeNanos()
        val am = context.getSystemService(ActivityManager::class.java)
        val memory = ActivityManager.MemoryInfo()
        am.getMemoryInfo(memory)
        val debug = Debug.MemoryInfo()
        Debug.getMemoryInfo(debug)
        peak.updateAndGet { maxOf(it, debug.totalPss.toLong() * 1024) }
        val battery = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val bm = context.getSystemService(BatteryManager::class.java)
        val pm = context.getSystemService(PowerManager::class.java)
        val current = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CURRENT_NOW)
        val charge = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CHARGE_COUNTER)
        val thermal = pm.currentThermalStatus
        return linkedMapOf(
            "current_raw" to current,
            "current_valid" to (current != Int.MIN_VALUE),
            "current_nominal_unit" to "uA_API_unverified_device_scale",
            "s26_current_unit_hypothesis" to "uA, discharge negative (등록 §3-7)",
            "voltage_mV" to battery?.getIntExtra(BatteryManager.EXTRA_VOLTAGE, -1),
            "charge_counter_raw" to charge,
            "charge_valid" to (charge != Int.MIN_VALUE),
            "charge_nominal_unit" to "uAh",
            "plugged" to battery?.getIntExtra(BatteryManager.EXTRA_PLUGGED, -1),
            "battery_temperature_deci_c" to battery?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1),
            "battery_level" to battery?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1),
            "battery_scale" to battery?.getIntExtra(BatteryManager.EXTRA_SCALE, -1),
            "thermal_status" to thermal,
            "interactive" to pm.isInteractive,
            "avail_bytes" to memory.availMem,
            "threshold_bytes" to memory.threshold,
            "low_memory" to memory.lowMemory,
            "peak_pss_bytes" to peak.get(),
            "snapshot_start_ns" to start,
            "sensor_read_end_ns" to SystemClock.elapsedRealtimeNanos(),
        )
    }
}
