package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File
import java.nio.file.Files
import android.os.SystemClock
import org.json.JSONObject

/** Runs the actual Activity completion dispatch; native workers are not executed. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class EnergyTailWindowBoundaryTest {
    private fun field(a: EnergyCollectionActivity, name: String, value: Any) {
        EnergyCollectionActivity::class.java.getDeclaredField(name).apply { isAccessible=true;set(a,value) }
    }
    @Test fun actualC0CompletionRecordsPhaseEndAtFullWindow() {
        val a=EnergyCollectionActivity();val file=File(Files.createTempDirectory("tail-boundary").toFile(),"progress.jsonl")
        val progress=EnergyProgress(file);field(a,"progress",progress);field(a,"sid","fixture");field(a,"tailObservation",true)
        val common=600_000_000_000L;val start=SystemClock.elapsedRealtimeNanos()-common
        val method=EnergyCollectionActivity::class.java.getDeclaredMethod("finishCalibrationWindow",List::class.java,Long::class.javaPrimitiveType,Long::class.javaPrimitiveType)
        method.isAccessible=true
        method.invoke(a,EnergyTailObservation.blocks("C0_LONG"),start,common)
        progress.close();assertEquals("phase_end",JSONObject(file.readLines().single()).getString("kind"))
    }
    @Test fun actualLegacyAndLoadDispatchStillRejectMissingTail() {
        val a=EnergyCollectionActivity();val common=600_000_000_000L;val start=SystemClock.elapsedRealtimeNanos()-common
        val method=EnergyCollectionActivity::class.java.getDeclaredMethod("finishCalibrationWindow",List::class.java,Long::class.javaPrimitiveType,Long::class.javaPrimitiveType)
        method.isAccessible=true
        val legacy=assertThrows(java.lang.reflect.InvocationTargetException::class.java) {
            method.invoke(a,EnergyTailObservation.blocks("C0_LONG"),start,common)
        }
        assertEquals("no common-window tail reserve",legacy.cause?.message)
        field(a,"tailObservation",true)
        val load=assertThrows(java.lang.reflect.InvocationTargetException::class.java) {
            method.invoke(a,EnergyTailObservation.blocks("LOAD_A_LONG"),start,common)
        }
        assertEquals("no common-window tail reserve",load.cause?.message)
    }
    @Test fun earlyC0AndUnregisteredIdleCannotBypassBoundary() {
        val ns=600_000_000_000L
        assertThrows(IllegalStateException::class.java) { EnergyTailObservation.requireCommonEnd(EnergyTailObservation.blocks("C0_LONG"),ns-1,ns) }
        EnergyTailObservation.requireCommonEnd(EnergyTailObservation.blocks("C0_LONG"),ns,ns)
        EnergyTailObservation.requireCommonEnd(EnergyTailObservation.blocks("C0_LONG"),ns+100_000_000L,ns)
        assertThrows(IllegalArgumentException::class.java) { EnergyTailObservation.requireCommonEnd(listOf(EnergyStateCalibration.Block("not_registered",emptyList(),600)),ns,ns) }
        assertThrows(IllegalArgumentException::class.java) { EnergyTailObservation.requireCommonEnd(EnergyTailObservation.blocks("C0_LONG"),ns,ns+1) }
    }
}
