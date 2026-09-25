package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicReference

class EnergyObservedStateTest {
    @Test fun originalSnapshotConversionThrowsAfterLastEntryRemoval() {
        val sized = CountDownLatch(1); val removed = CountDownLatch(1)
        val original = object : ConcurrentHashMap<String, String>() {
            override val size: Int get() {
                val n = super.size
                sized.countDown(); check(removed.await(2,TimeUnit.SECONDS))
                return n
            }
        }
        original["classification_CPU"]="load-0-644"
        val writer=Thread { check(sized.await(2,TimeUnit.SECONDS)); original.remove("classification_CPU"); removed.countDown() }
        writer.start()
        // Exact old Activity expression, actual Kotlin stdlib, forced size=1 -> empty iterator.
        try { original.toMap(); fail("old sampler expression unexpectedly succeeded") }
        catch (e: NoSuchElementException) { assertTrue(e.stackTrace.any { it.className.contains("Collections") || it.className.contains("Maps") }) }
        finally { writer.join(2000); assertFalse(writer.isAlive) }
    }

    @Test fun capturedFieldsAndMapAreOneDetachedState() {
        val state=EnergyObservedState<String> { 42L }
        state.addRuntime("classification_CPU","adapter"); state.phase="load"
        state.dispatch("classification_CPU","first")
        val captured=state.snapshot()
        state.release("classification_CPU"); state.phase="cleanup"
        assertEquals(mapOf("classification_CPU" to "first"),captured["active"])
        assertEquals(listOf("classification_CPU"),captured["resident_keys"])
        assertEquals("load",captured["phase"]); assertEquals(42L,captured["state_snapshot_ns"])
        assertEquals(emptyMap<String,String>(),state.snapshot()["active"])
        assertEquals(listOf("adapter"),state.laneRuntimes("_CPU"))
    }

    @Test fun removalCannotInterleaveWithSnapshotCopy() {
        val entered=CountDownLatch(1);val release=CountDownLatch(1);val attempting=CountDownLatch(1)
        val state=EnergyObservedState<String> { entered.countDown(); check(release.await(2,TimeUnit.SECONDS)); 1L }
        state.addRuntime("classification_CPU","adapter");state.dispatch("classification_CPU","request")
        val pool=Executors.newFixedThreadPool(2)
        try {
            val sample=pool.submit<Map<String,Any?>> { state.snapshot() }
            assertTrue(entered.await(2,TimeUnit.SECONDS))
            val remove=pool.submit { attempting.countDown(); state.release("classification_CPU") }
            assertTrue(attempting.await(2,TimeUnit.SECONDS)); assertFalse(remove.isDone)
            release.countDown()
            assertEquals(mapOf("classification_CPU" to "request"),sample.get(2,TimeUnit.SECONDS)["active"])
            remove.get(2,TimeUnit.SECONDS)
            assertEquals(emptyMap<String,String>(),state.snapshot()["active"])
        } finally { release.countDown();pool.shutdownNow() }
    }

    @Test fun runtimeUseAndCloseAreOutsideStateLock() {
        val state=EnergyObservedState<String> { 1L };state.addRuntime("detection_GPU","adapter")
        val refs=state.laneRuntimes("_GPU")
        val pool=Executors.newSingleThreadExecutor()
        try { assertEquals("adapter",refs.single());pool.submit { state.snapshot() }.get(1,TimeUnit.SECONDS) }
        finally { pool.shutdownNow() }
    }

    @Test fun actualSamplerGuardPreservesFailureAndStopsWithoutFakeSample() {
        val stop=AtomicReference<String?>(null);val records=mutableListOf<Map<String,Any?>>()
        val guard=EnergySamplerGuard(stop,{EnergyFailureEvidence.capture(it,"s","load","sampler",9)}, { records.add(it) })
        guard.tick { throw NoSuchElementException("controlled") }
        guard.tick { fail("sampler must not resume") }
        val record=records.single()
        assertEquals("java.util.NoSuchElementException",record["exception_class"])
        assertEquals("controlled",record["message"]);assertEquals("load",record["phase"])
        assertEquals(9L,record["mono_ns"]);assertEquals(Thread.currentThread().id,record["thread_id"])
        assertTrue(record["stack"].toString().contains("actualSamplerGuard"));assertNotNull(stop.get())
    }

    @Test fun failedEvidenceWriteStillLeavesStopAndCleanupEvidence() {
        val stop=AtomicReference<String?>(null)
        val guard=EnergySamplerGuard(stop,{EnergyFailureEvidence.capture(it,"s","load","sampler",1)}, { error("disk full") })
        guard.tick { throw NoSuchElementException("original") }
        assertNotNull(stop.get());assertEquals("original",guard.failure.get()!!["message"])
        assertTrue(guard.recordingFailure.get()!!.contains("disk full"))
        // Cleanup can serialize these detached values without traversing active/runtime maps.
        assertTrue(guard.failure.get()!!["stack"].toString().contains("NoSuchElementException"))
    }

    @Test fun lifecycleStopIsNotErasedBySamplerFailure() {
        val stop=AtomicReference<String?>("lifecycle_cancelled")
        val guard=EnergySamplerGuard(stop,{EnergyFailureEvidence.capture(it,"s","cleanup","sampler",1)}, {})
        guard.tick { error("cancelled writer") }
        assertEquals("lifecycle_cancelled",stop.get());assertNotNull(guard.failure.get())
    }

    @Test fun stopPublishesEvidenceBeforeBlockedFailureIo() {
        val stop=AtomicReference<String?>(null);val writing=CountDownLatch(1);val finish=CountDownLatch(1)
        val guard=EnergySamplerGuard(stop,{EnergyFailureEvidence.capture(it,"s","load","sampler",1)}, {
            writing.countDown();check(finish.await(2,TimeUnit.SECONDS))
        })
        val worker=Thread { guard.tick { error("first") } }
        worker.start()
        try {
            assertTrue(writing.await(2,TimeUnit.SECONDS));assertNotNull(stop.get())
            assertEquals("first",guard.failure.get()!!["message"])
        } finally { finish.countDown();worker.join(2000);assertFalse(worker.isAlive) }
    }
}
