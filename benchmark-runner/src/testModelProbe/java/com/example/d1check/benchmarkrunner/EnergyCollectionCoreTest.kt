package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test
import java.io.File
import java.nio.file.Files

class EnergyCollectionCoreTest {
    @Test fun serialCannotReuseBeforeActualRelease() {
        assertEquals(emptyList<Int>(), EnergyCollectionCore.selectable(listOf(0,192),setOf(0),false))
        assertEquals(listOf(1),EnergyCollectionCore.selectable(listOf(0,192),emptySet(),false))
    }
    @Test fun parallelTailRetainsOnlyUnfinishedLane() {
        assertEquals(listOf(0,1),EnergyCollectionCore.selectable(listOf(678,192),emptySet(),true))
        assertEquals(emptyList<Int>(),EnergyCollectionCore.selectable(listOf(0,0),setOf(1),true))
        assertEquals(listOf(1),EnergyCollectionCore.selectable(listOf(0,10),emptySet(),true))
    }
    @Test fun exactWorkAndPairIdentity() {
        assertEquals(870,EnergyCollectionCore.counts().values.sum())
        for (pair in listOf("CC_DG","CG_DC")) {
            val keys=EnergyCollectionCore.keys(pair)
            assertEquals(setOf("CPU","GPU"),keys.map { it.substringAfterLast('_') }.toSet())
        }
        try { EnergyCollectionCore.keys("CG_DG");fail() } catch(_: IllegalStateException) {}
    }
    @Test fun exactTimeoutBoundaryStops() {
        EnergyCollectionCore.requireTime(29,0,30)
        try { EnergyCollectionCore.requireTime(30,0,30);fail() } catch(_: IllegalStateException) {}
        assertEquals(5L,EnergyCollectionCore.remainingCall(145,0,150))
    }
    @Test fun progressSurvivesPartialEndAndFlush() {
        val file=Files.createTempDirectory("energy-test").resolve("progress.jsonl").toFile()
        val p=EnergyProgress(file);p.add("start");p.add("returned");p.add("next_start");p.flushBeforeGate()
        assertEquals(3,file.readLines().size);p.close()
        assertEquals(listOf("start","returned","next_start"),file.readLines())
        try { p.add("after_close");fail() } catch(_: IllegalStateException) {}
    }
    @Test fun writerFailureIsVisibleNotSuccess() {
        val parent=Files.createTempFile("energy-parent", ".file").toFile()
        val p=EnergyProgress(File(parent,"cannot_write"))
        try { p.close();fail() } catch(_: IllegalStateException) {}
        assertNotNull(p.failure.get())
    }
}
