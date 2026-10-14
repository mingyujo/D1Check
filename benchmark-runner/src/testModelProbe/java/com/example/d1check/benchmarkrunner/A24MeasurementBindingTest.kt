package com.example.d1check.benchmarkrunner

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[34])
class A24MeasurementBindingTest {
    private fun manifest(extra: String = ""): A24PreparationManifest {
        val root = JSONObject("""{"protocol":"a24-laptop-measurement-v1","session_id":"12086e3c-817f-520f-88b0-53340522ad79","service_cutoff_ns":120000000000,"sensor_end_ns":210000000000,"recipe":"IDLE","order":"FIFO","route":"C_GPU_D_CPU","concurrency":"SERIAL","wait_ms":0,"requests":[],"plan_sha256":"${"1".repeat(64)}"$extra}""")
        return A24PreparationManifest.parse(root)
    }
    @Test fun planAndManifestDigestAreDistinctBoundaries() {
        val m = manifest()
        assertEquals("1".repeat(64), m.exactPlanSha256())
        assertNotEquals(ProbeTaskAdapter.digest(m.json.toString().toByteArray()), m.exactPlanSha256())
    }
    @Test fun legacyMinimumIsPreservedWhileUserTenIsExplicit() {
        assertEquals(20, manifest().minimumBatteryPercent())
        assertEquals(10, manifest(""", "soc_contract":"USER_SOC_GE10_20261015", "minimum_battery_percent":10""").minimumBatteryPercent())
        val user = manifest(""", "soc_contract":"USER_SOC_GE10_20261015", "minimum_battery_percent":10""")
        assertTrue(user.batteryAdmitted(10,100))
        assertFalse(user.batteryAdmitted(9,100))
        assertFalse(user.batteryAdmitted(null,100))
        assertFalse(user.batteryAdmitted(10,0))
        assertFalse(manifest().batteryAdmitted(19,100))
    }
    @Test fun invalidOverrideCannotDisableBatteryFloor() {
        try { manifest(""", "soc_contract":"USER_SOC_GE10_20261015", "minimum_battery_percent":0""").minimumBatteryPercent(); fail() }
        catch (_: IllegalArgumentException) { }
    }
}
