package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test

class ArrivalPolicyStudyTest {
    private fun requests(role: String) = (0 until 96).map { i ->
        val urgent = i % 4 == 1
        ArrivalEnergyContract.Request("q$i", i, if (urgent) "classification" else "detection",
            if (urgent) "urgent" else "normal", 35000L + i * (if (role == "development") 500L else 550L),
            if (urgent) 1500L else 6000L)
    }
    @Test fun exactCountIndependentArrivalAndSeparateConfirmationTrace() {
        for (role in listOf("development", "confirmation"))
            for (policy in ArrivalPolicyStudy.POLICIES)
                ArrivalPolicyStudy.validate(ArrivalPolicyStudy.VERSION,policy,role,"sustained_mixed",requests(role))
        for (bad in listOf(requests("development").dropLast(1),
            requests("development").map { it.copy(offsetMs=it.offsetMs+1) }, requests("confirmation"))) {
            try { ArrivalPolicyStudy.validate(ArrivalPolicyStudy.VERSION,ArrivalPolicyStudy.CPU,
                "development","sustained_mixed",bad);fail("invalid trace") } catch (_: IllegalArgumentException) {}
        }
        try { ArrivalEnergyContract.validate("queue",requests("development"));fail("legacy widened") }
        catch (_: IllegalArgumentException) {}
    }
    @Test fun onlineDecisionHasOnlyArrivedQueueAndActualAvailability() {
        val normal=ArrivalPolicy.Ticket("normal","detection","normal",0)
        val urgent=ArrivalPolicy.Ticket("urgent","classification","urgent",1)
        val queue=listOf(normal,urgent)
        for (policy in ArrivalPolicyStudy.POLICIES) {
            assertEquals("urgent",ArrivalPolicyStudy.choose(policy,queue,true,true)!!.ticket.id)
            assertNull(ArrivalPolicyStudy.choose(policy,emptyList(),true,true))
            assertNull(ArrivalPolicyStudy.choose(policy,queue,false,false))
        }
        assertEquals("CPU",ArrivalPolicyStudy.choose(ArrivalPolicyStudy.CPU,queue,true,true)!!.backend)
        assertEquals("GPU",ArrivalPolicyStudy.choose(ArrivalPolicyStudy.PARALLEL,queue,false,true)!!.backend)
        assertNull(ArrivalPolicyStudy.choose(ArrivalPolicyStudy.SERIAL,queue,false,true))
        assertNull(ArrivalPolicyStudy.choose(ArrivalPolicyStudy.CPU,queue,false,true))
        assertEquals("normal",ArrivalPolicyStudy.choose(ArrivalPolicyStudy.PARALLEL,listOf(normal),true,false)!!.ticket.id)
    }
}
