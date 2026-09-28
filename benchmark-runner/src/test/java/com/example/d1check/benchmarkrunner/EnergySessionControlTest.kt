package com.example.d1check.benchmarkrunner

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class EnergySessionControlTest {
    @Test fun legacyGatesRemainHostOwned() {
        val mode = EnergySessionControl.validate(EnergySessionControl.HOST_GATED, false, false)
        listOf("warmup", "serial_probe", "probe", "baseline").forEach {
            assertTrue(EnergySessionControl.hostArmRequired(mode, it))
        }
    }

    @Test fun onlyDiagnosticCalibrationCanContinueAfterProbe() {
        val mode = EnergySessionControl.validate(EnergySessionControl.DEVICE_AFTER_PROBE, true, true)
        listOf("warmup", "serial_probe", "probe").forEach {
            assertTrue(EnergySessionControl.hostArmRequired(mode, it))
        }
        assertFalse(EnergySessionControl.hostArmRequired(mode, "baseline"))
        for (calibration in listOf(false, true)) for (diagnostic in listOf(false, true)) {
            if (calibration && diagnostic) continue
            try {
                EnergySessionControl.validate(EnergySessionControl.DEVICE_AFTER_PROBE, calibration, diagnostic)
                error("accepted non-diagnostic autonomous collection")
            } catch (_: IllegalArgumentException) { }
        }
    }
}
