package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test

class ArrivalBatteryGateTest {
    @Test fun defaultSessionsKeepTwentyPercentFloor() {
        assertEquals(20, ArrivalBatteryGate.minimum(null, null))
        assertEquals(20, ArrivalBatteryGate.minimum(null, 20))
        assertTrue(ArrivalBatteryGate.admitted(20, 100, 20))
        assertFalse(ArrivalBatteryGate.admitted(19, 100, 20))
    }

    @Test fun sixPercentRequiresExactVersionAndExplicitFloor() {
        assertEquals(6, ArrivalBatteryGate.minimum(ArrivalBatteryGate.VERSION, 6))
        for ((version, requested) in listOf(null to 6, "" to 6, "unknown" to 6,
            ArrivalBatteryGate.VERSION to null, ArrivalBatteryGate.VERSION to 20,
            ArrivalBatteryGate.VERSION to 0, null to 0, null to 19)) {
            assertThrows(IllegalArgumentException::class.java) {
                ArrivalBatteryGate.minimum(version, requested)
            }
        }
    }

    @Test fun lowBatteryNeverRelaxesScaleLevelValidityOrStopBoundary() {
        assertTrue(ArrivalBatteryGate.admitted(19, 100, 6))
        assertTrue(ArrivalBatteryGate.admitted(6, 100, 6))
        assertTrue(ArrivalBatteryGate.admitted(100, 100, 6))
        for ((level, scale) in listOf(5 to 100, 0 to 100, -1 to 100, 101 to 100,
            null to 100, 19 to null, 19 to 99, 19 to 0)) {
            assertFalse(ArrivalBatteryGate.admitted(level, scale, 6))
        }
        assertThrows(IllegalArgumentException::class.java) {
            ArrivalBatteryGate.admitted(19, 100, 0)
        }
    }
}
