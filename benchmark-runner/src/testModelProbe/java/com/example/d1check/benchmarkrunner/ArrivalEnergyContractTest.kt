package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test

class ArrivalEnergyContractTest {
    @Test fun fixedTraceAndDistinctScheduledArrivals() {
        for (scenario in listOf("low", "queue", "burst")) {
            val requests = (0 until 24).map { i ->
                val urgent = i % 4 == 1
                ArrivalEnergyContract.Request("request-$i", i,
                    if (urgent) "classification" else "detection",
                    if (urgent) "urgent" else "normal",
                    ArrivalEnergyContract.offset(scenario, i), if (urgent) 1500 else 6000)
            }
            ArrivalEnergyContract.validate(scenario, requests)
            assertEquals(6, requests.count { it.priority == "urgent" })
            assertTrue(requests.zipWithNext().all { it.first.offsetMs < it.second.offsetMs })
            try { ArrivalEnergyContract.validate(scenario, requests.dropLast(1)); fail("missing request accepted") }
            catch (_: IllegalArgumentException) { }
            try { ArrivalEnergyContract.validate(scenario, requests.toMutableList().apply {
                this[1] = this[1].copy(offsetMs = this[1].offsetMs + 1)
            }); fail("changed time accepted") } catch (_: IllegalArgumentException) { }
        }
    }

    @Test fun arrivalPolicyActuallyChangesResourceUse() {
        // queue trace after the last 4.6s arrival: same 24 online-visible tickets.
        val waiting = (0 until 24).map { i -> ArrivalPolicy.Ticket("request-$i",
            if (i%4==1) "classification" else "detection",
            if (i%4==1) "urgent" else "normal",i) }
        assertEquals("CPU", ArrivalPolicy.choose(ArrivalPolicy.URGENT, waiting, true, true, 0, emptyMap())!!.backend)
        assertEquals("CPU", ArrivalPolicy.choose(ArrivalPolicy.FIXED, waiting, true, true, 0, emptyMap())!!.backend)
        assertEquals("GPU", ArrivalPolicy.choose(ArrivalPolicy.FIXED, waiting, false, true, 0, emptyMap())!!.backend)
        assertNull(ArrivalPolicy.choose(ArrivalPolicy.URGENT, waiting, false, true, 0, emptyMap()))
    }
}
