package com.example.d1check.benchmarkrunner

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class EnergyTailObservationTest {
    private fun manifest(profile: String): JSONObject = JSONObject().apply {
        put("protocol",EnergyTailObservation.PROTOCOL);put("tail_observation_version",EnergyTailObservation.VERSION)
        put("calibration_version",EnergyTailObservation.VERSION);put("identification_profile",profile)
        put("state_model_calibration",true);put("operational_only",true);put("autonomous_diagnostic_only",true)
        put("experiment_ready",false);put("session_control",EnergySessionControl.DEVICE_AFTER_PROBE);put("mode","calibration")
        put("maximum_duration_ms",EnergyTailObservation.WATCHDOG_MS);put("baseline_seconds",120)
        put("common_work_seconds",600);put("cooling_seconds",1920);put("cadence_ms",250)
        put("work_call_cap",EnergyTailObservation.workCap(profile));put("power_sample_period_ms",900)
        put("start_ap_gate",ArrivalStartApGate.DIAGNOSTIC_VERSION)
        put("blocks",JSONArray().apply { EnergyTailObservation.blocks(profile).forEach {
            put(JSONObject().put("id",it.id).put("seconds",it.seconds).put("lane_indices",JSONArray(it.lanes)))
        } })
    }
    @Test fun registeredC0IsCompleteIdleNotMissingWork() {
        assertEquals("C0_LONG",EnergyTailObservation.validate(manifest("C0_LONG")))
        assertEquals(0,EnergyTailObservation.workCap("C0_LONG"))
        assertEquals(600,EnergyTailObservation.blocks("C0_LONG").single().seconds)
        val bad=manifest("C0_LONG").put("blocks",JSONArray())
        assertThrows(IllegalArgumentException::class.java) { EnergyTailObservation.validate(bad) }
    }
    @Test fun loadPreservesDevALanesAndCadenceCap() {
        assertEquals(EnergyResidentIdentification.blocks("DEV_A"),EnergyTailObservation.blocks("LOAD_A_LONG"))
        assertEquals(1200,EnergyTailObservation.workCap("LOAD_A_LONG"))
        EnergyTailObservation.validate(manifest("LOAD_A_LONG"))
        assertThrows(IllegalArgumentException::class.java) { EnergyTailObservation.validate(manifest("LOAD_A_LONG").put("work_call_cap",0)) }
    }
    @Test fun extensionIsNeverImplicitOrLegacyCompatible() {
        for (key in listOf("maximum_duration_ms","cooling_seconds","power_sample_period_ms","cadence_ms")) {
            assertThrows(IllegalArgumentException::class.java) { EnergyTailObservation.validate(manifest("C0_LONG").put(key,1)) }
        }
        assertThrows(IllegalArgumentException::class.java) { EnergyTailObservation.validate(manifest("C0_LONG").put("resident_identification_version",EnergyResidentIdentification.VERSION)) }
        assertThrows(IllegalArgumentException::class.java) { EnergyTailObservation.blocks("C0") }
        assertEquals(1_800_000L,EnergyResidentIdentification.WATCHDOG_MS)
        assertEquals(1_800_000L,EnergyStateCalibration.WATCHDOG_MS)
    }
    @Test fun watchdogContainsRegisteredStageTimeoutsAndCleanup() {
        val bound=150+60+30+60+30+360+120+30+600+1920+45
        assertEquals(3405,bound)
        assertTrue(bound*1000L<EnergyTailObservation.WATCHDOG_MS)
    }
    @Test fun lowBatteryRequiresExplicitProtocolAndExactFloor() {
        val old=manifest("C0_LONG")
        assertEquals(20,EnergyTailObservation.batteryMinimum(old))
        val low=manifest("C0_LONG").put("protocol",EnergyTailObservation.LOW_BATTERY_PROTOCOL)
            .put("tail_battery_gate_version",EnergyTailObservation.LOW_BATTERY_GATE)
            .put("battery_min_percent",6).put("battery_stop_at_percent",5)
        EnergyTailObservation.validate(low)
        assertEquals(6,EnergyTailObservation.batteryMinimum(low))
        assertThrows(IllegalArgumentException::class.java) { EnergyTailObservation.validate(low.put("battery_min_percent",0)) }
        assertThrows(IllegalArgumentException::class.java) { EnergyTailObservation.validate(old.put("tail_battery_gate_version","unknown")) }
    }
    @Test fun nineteenIsOptInAndFiveStopsWithoutRelaxingValidity() {
        assertFalse(EnergyTailObservation.batteryAdmitted(19,100,20))
        assertTrue(EnergyTailObservation.batteryAdmitted(19,100,6))
        assertTrue(EnergyTailObservation.batteryAdmitted(6,100,6))
        assertFalse(EnergyTailObservation.batteryAdmitted(5,100,6))
        assertFalse(EnergyTailObservation.batteryAdmitted(null,100,6))
        assertFalse(EnergyTailObservation.batteryAdmitted(19,null,6))
        assertFalse(EnergyTailObservation.batteryAdmitted(19,99,6))
        assertFalse(EnergyTailObservation.batteryAdmitted(101,100,6))
    }
}
