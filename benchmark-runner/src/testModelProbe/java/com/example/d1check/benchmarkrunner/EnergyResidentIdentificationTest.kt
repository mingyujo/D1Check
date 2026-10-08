package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test

class EnergyResidentIdentificationTest {
    @Test fun budgetsAndFourResidentDefinitions() {
        assertEquals(600,EnergyResidentIdentification.commonSeconds("DEV_A"))
        assertEquals(600,EnergyResidentIdentification.commonSeconds("DEV_B"))
        assertEquals(480,EnergyResidentIdentification.commonSeconds("CONF_A"))
        assertEquals(210,EnergyResidentIdentification.commonSeconds("CONF_MIX_A"))
        assertEquals(1200,EnergyResidentIdentification.workCap("DEV_A"))
        assertEquals(600,EnergyResidentIdentification.workCap("CONF_A"))
        assertEquals(352,EnergyResidentIdentification.workCap("CONF_MIX_A"))
        assertEquals(4,EnergyResidentIdentification.KEYS.size)
    }
    @Test fun exactProfileAndCapRequired() {
        val b=EnergyResidentIdentification.blocks("DEV_A")
        EnergyResidentIdentification.validate(EnergyResidentIdentification.VERSION,"DEV_A",b,1200)
        for (bad in listOf(b.reversed(),b.dropLast(1),b.map { it.copy(lanes=listOf(0,2)) })) {
            try { EnergyResidentIdentification.validate(EnergyResidentIdentification.VERSION,"DEV_A",bad,1200);fail() }
            catch (_: IllegalArgumentException) {}
        }
        try { EnergyResidentIdentification.validate(EnergyResidentIdentification.VERSION,"DEV_A",b,1201);fail() }
        catch (_: IllegalArgumentException) {}
    }
    @Test fun fixedTimesRejectMissedWindowAndExtraCalls() {
        assertFalse(EnergyResidentIdentification.canStart(9,10,20,0,4))
        assertTrue(EnergyResidentIdentification.canStart(10,10,20,0,4))
        assertFalse(EnergyResidentIdentification.canStart(20,10,20,0,4))
        assertFalse(EnergyResidentIdentification.canStart(19,10,20,4,4))
    }
    @Test fun previousContractsAreUnchanged() {
        EnergyStateCalibration.validate(EnergyStateCalibration.blocks(false))
        EnergyStateCalibration.validate(EnergyStateCalibration.shortTransitionBlocks())
        assertEquals(1680,EnergyStateCalibration.MAX_WORK_CALLS)
        assertEquals(120_000_000_000L,ArrivalEnergyContract.COMMON_NS)
    }
}
