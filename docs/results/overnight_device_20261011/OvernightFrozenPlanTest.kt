package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test

class OvernightFrozenPlanTest {
    private fun requests() = (0 until 96).map { i ->
        val urgent = i % 2 == 0
        ArrivalEnergyContract.Request("id-$i",i,if (urgent) "classification" else "detection",
            if (urgent) "urgent" else "normal",35_000L+i*350L,if (urgent) 1500L else 6000L)
    }
    private fun entries() = requests().map { q -> ArrivalRecordedReplay.Entry(q.id,q.ordinal,q.task,
        q.offsetMs*1_000_000L,q.offsetMs*1_000_000L+250_000_000L,
        if (q.task=="detection" || q.ordinal%4==0) "CPU" else "GPU","source/${q.ordinal}") }
    @Test fun acceptsOnlyExactNewTraceAndSupportedResources() {
        val req=requests(); val rows=entries()
        ArrivalRecordedReplay.validateFrozenRequests("frozen_plan_periodic96",req)
        ArrivalRecordedReplay.validate(rows,req,ArrivalRecordedReplay.FROZEN_PLAN_VERSION,"IE_FROZEN")
        for (bad in listOf(rows.map { it.copy(backend="NPU") }, rows.map { if (it.task=="detection") it.copy(backend="GPU") else it })) {
            try { ArrivalRecordedReplay.validate(bad,req,ArrivalRecordedReplay.FROZEN_PLAN_VERSION,"IE_FROZEN"); fail("unsupported") }
            catch (_: IllegalArgumentException) {}
        }
        try { ArrivalRecordedReplay.validateFrozenRequests("frozen_plan_periodic96",req.map { it.copy(offsetMs=it.offsetMs+1) }); fail("shifted") }
        catch (_: IllegalArgumentException) {}
        try { ArrivalRecordedReplay.validate(rows,req); fail("legacy broadened") }
        catch (_: IllegalArgumentException) {}
    }
    @Test fun busyLaneAndReleasePreserveRequest() {
        val rows=entries().associateBy { it.id }
        val waiting=requests().take(2).map { ArrivalPolicy.Ticket(it.id,it.task,it.priority,it.ordinal) }
        assertNull(ArrivalRecordedReplay.choose(waiting,rows,35_249_999_999L,true,true))
        assertNull(ArrivalRecordedReplay.choose(waiting,rows,35_900_000_000L,false,true))
        assertEquals("id-0",ArrivalRecordedReplay.choose(waiting,rows,35_900_000_000L,true,true)!!.ticket.id)
        assertEquals(2,waiting.size)
        assertEquals("id-1",ArrivalRecordedReplay.choose(waiting.drop(1),rows,35_900_000_000L,true,true)!!.ticket.id)
    }
    @Test fun lateActualReleaseCannotCreateUnmeasuredClassCpuGpuPair() {
        val rows=entries().associateBy { it.id }
        val waiting=requests().take(3).map { ArrivalPolicy.Ticket(it.id,it.task,it.priority,it.ordinal) }
        val version=ArrivalRecordedReplay.FROZEN_PLAN_VERSION
        assertNull(ArrivalRecordedReplay.choose(waiting.take(1),rows,36_000_000_000L,true,false,mapOf("GPU" to "classification"),version))
        assertEquals("id-1",ArrivalRecordedReplay.choose(waiting,rows,36_000_000_000L,true,false,mapOf("GPU" to "classification"),version)!!.ticket.id)
        assertNull(ArrivalRecordedReplay.choose(waiting.drop(2),rows,36_000_000_000L,false,true,mapOf("CPU" to "classification"),version))
        assertEquals("id-2",ArrivalRecordedReplay.choose(waiting.drop(2),rows,36_000_000_000L,false,true,mapOf("CPU" to "detection"),version)!!.ticket.id)
        assertEquals(3,waiting.size)
    }
}
