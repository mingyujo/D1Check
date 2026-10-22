package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test

class ArrivalHistoryControlTest {
    private fun requests(prefix: String) = (0 until 96).map { i ->
        val c=i%2==0
        ArrivalEnergyContract.Request("$prefix-$i",i,if(c) "classification" else "detection",
            if(c) "urgent" else "normal",35000L+i*350L,if(c)1500L else 6000L)
    }
    @Test fun validatesSeparateBudgetsAndLegacyWatchdog() {
        for (gap in listOf(30L,180L)) for (role in listOf("development","confirmation")) {
            ArrivalHistoryControl.validate(ArrivalHistoryControl.VERSION,gap,role,ArrivalPolicyStudy.PARALLEL,requests("c"),requests("t"))
            ArrivalHistoryControl.validate(ArrivalHistoryControl.VERSION,gap,role,"C0",requests("c"),emptyList())
        }
        assertEquals(480000L,ArrivalHistoryControl.watchdog(""))
        assertEquals(900000L,ArrivalHistoryControl.watchdog(ArrivalHistoryControl.VERSION))
    }
    @Test fun rejectsDuplicateRequestsAndUnregisteredGap() {
        assertThrows(IllegalArgumentException::class.java) {
            ArrivalHistoryControl.validate(ArrivalHistoryControl.VERSION,30,"development",ArrivalPolicyStudy.CPU,requests("x"),requests("x"))
        }
        assertThrows(IllegalArgumentException::class.java) {
            ArrivalHistoryControl.validate(ArrivalHistoryControl.VERSION,31,"development","C0",requests("c"),emptyList())
        }
    }
    @Test fun sameEntryOrchestrationStopsBeforeTargetOnCancellation() {
        val events=mutableListOf<String>(); var stopped=false
        assertThrows(IllegalStateException::class.java) {
            ArrivalHistoryControl.execute({check(!stopped)}, {events.add("conditioning")},
                {events.add("recovery");stopped=true},{events.add("target")})
        }
        assertEquals(listOf("conditioning","recovery"),events)
    }
    @Test fun failurePreservedAndEachPhaseRunsOnce() {
        val events=mutableListOf<String>()
        ArrivalHistoryControl.execute({}, {events.add("conditioning")},{events.add("recovery")},{events.add("target")})
        assertEquals(listOf("conditioning","recovery","target"),events)
        val error=IllegalStateException("lane not released")
        val got=assertThrows(IllegalStateException::class.java) { ArrivalHistoryControl.execute({}, {throw error},{fail()},{fail()}) }
        assertSame(error,got)
    }
}
