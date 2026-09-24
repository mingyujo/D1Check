// 미러 테스트: benchmark-runner/src/test/java/com/example/d1check/benchmarkrunner/AutomationPolicyTest.kt 를 패키지 줄만 바꿔 그대로 옮겼다.
// npu-runner 로 옮긴 DutyCycle/RunTermination/CommandReplay/PilotSafety 가 원본과 같은 동작임을 원본 테스트로 고정한다.
package com.example.d1check.npurunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AutomationPolicyTest {
    @Test
    fun replayedCommandIdIsRejected() {
        assertNull(CommandReplayPolicy.append(listOf("command-a"), "command-a"))
    }

    @Test
    fun commandHistoryIsBounded() {
        val history = (0 until CommandReplayPolicy.MAX_HISTORY).map { "command-$it" }
        val updated = requireNotNull(CommandReplayPolicy.append(history, "new-command"))

        assertEquals(CommandReplayPolicy.MAX_HISTORY, updated.size)
        assertFalse("command-0" in updated)
        assertTrue("new-command" in updated)
    }

    @Test
    fun conservativePilotSafetyThresholdsPass() {
        val check = PilotSafetyPolicy.evaluate(
            PilotSafetySnapshot(1, 0, 3, 60, 34.9)
        )

        assertTrue(check.passed)
        assertTrue(check.formalEnergyEligible)
    }

    @Test
    fun fullBatteryPassesPilotButIsNotFormalEnergyEligible() {
        val check = PilotSafetyPolicy.evaluate(
            PilotSafetySnapshot(1, 0, 3, 100, 30.3)
        )

        assertTrue(check.passed)
        assertFalse(check.formalEnergyEligible)
        assertEquals(false, check.metadata()["formal_energy_eligible"])
    }

    @Test
    fun batteryBelowThirtyFailsPilotSafety() {
        val check = PilotSafetyPolicy.evaluate(
            PilotSafetySnapshot(1, 0, 3, 29, 30.3)
        )

        assertFalse(check.passed)
        assertEquals(listOf("battery_level"), check.rejectionReasons)
        assertFalse(check.formalEnergyEligible)
    }

    @Test
    fun pilotSafetySeparatelyRejectsThermalChargingLevelAndTemperature() {
        val check = PilotSafetyPolicy.evaluate(
            PilotSafetySnapshot(2, 1, 2, 20, 36.0)
        )

        assertEquals(
            listOf(
                "android_thermal_status",
                "device_plugged",
                "not_discharging",
                "battery_level",
                "battery_temperature",
            ),
            check.rejectionReasons,
        )
        assertFalse(check.passed)
        assertEquals(false, check.metadata()["formal_safety_limits_applied"])
        assertEquals(false, check.metadata()["matched_start_limits_applied"])
    }
}
