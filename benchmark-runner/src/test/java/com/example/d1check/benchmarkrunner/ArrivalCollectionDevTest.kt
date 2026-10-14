package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File

@RunWith(RobolectricTestRunner::class)
@Config(manifest = Config.NONE, sdk = [35])
class ArrivalCollectionDevTest {
    private var tick = 0L
    private val n = ArrivalPolicy.Ticket("normal", "detection", "normal", 0)
    private val u = ArrivalPolicy.Ticket("urgent", "classification", "urgent", 1)
    private val cells = listOf("classification", "detection").flatMap { t -> listOf("CPU", "GPU").flatMap { b ->
        listOf("normal", "urgent").map { p -> "${t}_${b}_$p" to ArrivalCollectionDev.Cell(listOf(10.0,20.0,30.0,10.0),
            listOf(if (p=="urgent") 30.0 else 60.0,70.0,60.0,40.0,10.0)) }
    } }.toMap()
    private fun collector(mode: String="strict_active", split: String="CPU", concurrency: Int=1, capacity: Int=128) =
        ArrivalCollectionDev({tick++},mode,split,concurrency,cells,"a".repeat(64),capacity).also { it.arrive(n,0);it.arrive(u,0) }
    private fun lanes(phase: ArrivalTimingDev.Phase=ArrivalTimingDev.Phase.AVAILABLE, since: Long=0, persist: Long?=null) = mapOf(
        "CPU" to ArrivalTimingDev.Lane("CPU",phase,if(phase==ArrivalTimingDev.Phase.AVAILABLE)null else n.id,
            if(phase==ArrivalTimingDev.Phase.AVAILABLE)null else n.task,since,persist),"GPU" to ArrivalTimingDev.Lane("GPU"))

    @Test fun activeStrictUsesFallbackAndCannotUseGpuWhenCpuBusy() {
        val c=collector();assertEquals("CPU",c.choose(listOf(u),lanes(),0).choice?.backend)
        assertNull(c.choose(listOf(u),lanes(ArrivalTimingDev.Phase.EXECUTING),25).choice)
    }
    @Test fun fixedShadowHasAnExplicitlyDifferentActualChoice() {
        val c=collector("fixed_shadow","SPLIT")
        assertEquals("GPU",c.choose(listOf(n),lanes(),0).choice?.backend)
        val record=(c.artifact(true)["records"] as List<*>).single() as Map<*,*>
        assertEquals("CPU",((record["shadow"] as Map<*,*>)["selected"] as Map<*,*>)["backend"])
    }
    @Test fun globalSerializationDiffersFromPerLaneOccupancy() {
        assertNull(collector("fixed_shadow","SPLIT",1).choose(listOf(n),lanes(ArrivalTimingDev.Phase.EXECUTING),1).choice)
        assertEquals("GPU",collector("fixed_shadow","SPLIT",2).choose(listOf(n),lanes(ArrivalTimingDev.Phase.EXECUTING),1).choice?.backend)
    }
    @Test fun outputReleaseAndOverrunNeverFreeBusyLane() {
        val c=collector()
        for (phase in listOf(ArrivalTimingDev.Phase.ASSIGNED,ArrivalTimingDev.Phase.EXECUTING,ArrivalTimingDev.Phase.OUTPUT_READY,ArrivalTimingDev.Phase.WORKER_RELEASED)) {
            assertNull(c.choose(listOf(u),lanes(phase,0,0),50).choice)
        }
    }
    @Test fun overflowStopsWithoutUnrecordedDispatch() {
        val c=collector(capacity=1);c.choose(emptyList(),lanes(),0)
        assertNull(c.choose(listOf(u),lanes(),1).choice);assertTrue(c.overflow)
        assertEquals(false,c.artifact(true)["complete"])
    }
    @Test fun timingRecorderKeepsOldNullBudgetsAndNewNamespace() {
        val c=collector();val budgets=listOf("classification_CPU","classification_GPU","detection_CPU","detection_GPU").associateWith { ArrivalTimingDev.Budget(null,null,null,null) }
        val r=ArrivalTimingDev.Recorder({tick++},budgets,"pending","synthetic",collection=c)
        val choice=r.choose(listOf(n,u)).first.choice!!;assertEquals(u,choice.ticket)
        r.mark("CPU",u,ArrivalTimingDev.Phase.ASSIGNED)
        assertNull(r.choose(listOf(n)).first.choice)
        assertEquals(ArrivalCollectionDev.PROTOCOL,r.artifact(false)["protocol"])
    }
    @Test fun futureArrivalIsRejected() {
        val c=collector();val late=ArrivalPolicy.Ticket("future","classification","urgent",2);c.arrive(late,100)
        assertThrows(IllegalArgumentException::class.java) { c.evaluate(listOf(late),lanes(),99) }
    }
    @Test fun exportRealKotlinSnapshotsForPythonParity() {
        val c=collector();val values=mutableListOf<Map<String,Any?>>()
        values.add(c.evaluate(listOf(n,u),lanes(),0))
        values.add(c.evaluate(emptyList(),lanes(),0))
        for (phase in listOf(ArrivalTimingDev.Phase.ASSIGNED,ArrivalTimingDev.Phase.EXECUTING,ArrivalTimingDev.Phase.OUTPUT_READY,ArrivalTimingDev.Phase.PERSISTED,ArrivalTimingDev.Phase.WORKER_RELEASED)) {
            values.add(c.evaluate(listOf(u),lanes(phase,0,0),5))
            values.add(c.evaluate(listOf(u),lanes(phase,0,0),50))
        }
        val path=System.getenv("D1_COLLECTION_PARITY_OUTPUT") ?: "build/collection-parity.json"
        File(path).apply { parentFile.mkdirs();writeText(ModelProbeArtifacts.json(values)) }
        assertEquals(12,values.size)
    }
}
