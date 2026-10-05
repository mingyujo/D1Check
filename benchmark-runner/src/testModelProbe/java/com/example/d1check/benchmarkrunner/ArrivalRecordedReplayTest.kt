package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test

class ArrivalRecordedReplayTest {
    @Test fun comparisonRequiresExplicitVersionAndExactSourceAllocation() {
        val req=requests()
        val cpu=entries().map { it.copy(backend="CPU") }
        ArrivalRecordedReplay.validate(cpu,req,ArrivalRecordedReplay.COMPARISON_VERSION,"CPU_URGENT")
        ArrivalRecordedReplay.validate(entries(),req,ArrivalRecordedReplay.COMPARISON_VERSION,"B2_PC")
        for (policy in listOf("B2_PC","B3_SOLO_EFT_PC")) {
            try { ArrivalRecordedReplay.validate(cpu,req,ArrivalRecordedReplay.COMPARISON_VERSION,policy);fail("wrong policy") }
            catch (_: IllegalArgumentException) {}
        }
        try { ArrivalRecordedReplay.validate(cpu,req);fail("legacy broadened") }
        catch (_: IllegalArgumentException) {}
        val waiting=req.map { ArrivalPolicy.Ticket(it.id,it.task,it.priority,it.ordinal) }
        assertNull(ArrivalRecordedReplay.choose(waiting,cpu.associateBy { it.id },1_000_000_000,false,true))
        assertEquals("CPU",ArrivalRecordedReplay.choose(waiting,cpu.associateBy { it.id },1_000_000_000,true,true)!!.backend)
    }
    @Test fun delayedBurstReleasePassesActualContractsButShiftedArrivalFails() {
        val req = (0 until 24).map { i ->
            val urgent = i % 4 == 1
            ArrivalEnergyContract.Request("burst-$i", i,
                if (urgent) "classification" else "detection",
                if (urgent) "urgent" else "normal",
                ArrivalEnergyContract.offset("burst", i), if (urgent) 1500L else 6000L)
        }
        val entries = req.map { r -> ArrivalRecordedReplay.Entry(r.id, r.ordinal,
            r.task, r.offsetMs * 1_000_000L, 35_000_300_000L + r.offsetMs * 1_000_000L,
            if (r.task == "classification") "GPU" else "CPU", "source/${r.ordinal}") }
        ArrivalEnergyContract.validate("burst", req)
        ArrivalRecordedReplay.validate(entries, req)
        val waiting = req.map { ArrivalPolicy.Ticket(it.id, it.task, it.priority, it.ordinal) }
        assertNull(ArrivalRecordedReplay.choose(waiting, entries.associateBy { it.id },
            35_000_299_999L, true, true))
        assertEquals("burst-0", ArrivalRecordedReplay.choose(waiting, entries.associateBy { it.id },
            35_000_300_000L, true, true)!!.ticket.id)
        try {
            ArrivalEnergyContract.validate("burst", req.map { it.copy(offsetMs = it.offsetMs + 35_000L) })
            fail("unsupported shifted arrival grid accepted")
        } catch (_: IllegalArgumentException) {}
    }

    private fun requests() = (0 until 24).map { i ->
        val urgent = i % 4 == 1
        ArrivalEnergyContract.Request("id-$i", i,
            if (urgent) "classification" else "detection",
            if (urgent) "urgent" else "normal", i * 200L,
            if (urgent) 1500 else 6000)
    }
    private fun entries() = requests().map { r ->
        ArrivalRecordedReplay.Entry(r.id, r.ordinal, r.task, r.offsetMs*1_000_000L,
            r.offsetMs*1_000_000L+300_000L,
            if (r.task == "classification") "GPU" else "CPU", "source/${r.ordinal}")
    }

    @Test fun rejectsEarlyOrWrongRecordedAssignment() {
        val req=requests();val entries=entries()
        ArrivalRecordedReplay.validate(entries,req)
        for (bad in listOf(entries.toMutableList().apply { set(1,get(1).copy(releaseNs=0)) },
                           entries.toMutableList().apply { set(1,get(1).copy(backend="CPU")) })) {
            try { ArrivalRecordedReplay.validate(bad,req);fail("invalid replay accepted") }
            catch (_: IllegalArgumentException) {}
        }
    }

    @Test fun obeysReleaseGateBusyLaneAndDeterministicTie() {
        val entries=entries().associateBy { it.id }
        val waiting=listOf(ArrivalPolicy.Ticket("id-0","detection","normal",0),
            ArrivalPolicy.Ticket("id-1","classification","urgent",1),
            ArrivalPolicy.Ticket("id-2","detection","normal",2))
        assertNull(ArrivalRecordedReplay.choose(waiting,entries,0,true,true))
        assertEquals("id-0",ArrivalRecordedReplay.choose(waiting,entries,300_000,true,true)!!.ticket.id)
        assertNull(ArrivalRecordedReplay.choose(waiting,entries,200_300_000,false,false))
        assertEquals("id-1",ArrivalRecordedReplay.choose(waiting,entries,200_300_000,false,true)!!.ticket.id)
        assertEquals("id-2",ArrivalRecordedReplay.choose(waiting.drop(1),entries,400_300_000,true,false)!!.ticket.id)
        val tied=entries.toMutableMap().apply { put("id-0",getValue("id-0").copy(releaseNs=400_300_000)) }
        assertEquals("id-0",ArrivalRecordedReplay.choose(waiting,tied,400_300_000,true,false)!!.ticket.id)
    }
}
