package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test
import java.util.concurrent.*

@org.junit.runner.RunWith(org.robolectric.RobolectricTestRunner::class)
@org.robolectric.annotation.Config(sdk = [35])
class ArrivalRuntimeSetupTest {
    private val keys = setOf("detection_GPU", "classification_CPU", "detection_CPU", "classification_GPU")

    @Test fun setupOnlyReturnsBeforeAnyCallAndPreservesOrder() {
        val created = mutableListOf<String>()
        var calls = 0
        fun run() {
            if (ArrivalRuntimeSetup.initialize(keys, true, 0, 0) { created += it }) return
            calls++
        }
        run()
        assertEquals(keys.sorted(), created); assertEquals(0, calls)
    }

    @Test fun malformedSetupCannotInitialize() {
        for (counts in listOf(1 to 0, 0 to 1)) {
            assertThrows(IllegalArgumentException::class.java) {
                ArrivalRuntimeSetup.initialize(keys, true, counts.first, counts.second) { error("must not create") }
            }
        }
    }

    @Test fun creationFailureStopsSequenceWithoutRetry() {
        val created = mutableListOf<String>()
        assertThrows(IllegalStateException::class.java) {
            ArrivalRuntimeSetup.initialize(keys, true, 0, 0) {
                created += it; if (created.size == 3) error("injected constructor")
            }
        }
        assertEquals(keys.sorted().take(3), created)
    }

    @Test fun stalledWorkerHasBoundedCloseAndRetainsThreadOwnership() {
        val lane=Executors.newSingleThreadExecutor(); val entered=CountDownLatch(1); val release=CountDownLatch(1)
        var worker=0L; var closer=0L
        try {
            lane.submit { worker=Thread.currentThread().id; entered.countDown(); release.await() }
            assertTrue(entered.await(2,TimeUnit.SECONDS))
            assertThrows(TimeoutException::class.java) {
                ArrivalRuntimeSetup.closeLane(lane,1,TimeUnit.MILLISECONDS) { closer=Thread.currentThread().id }
            }
            assertEquals(0L,closer) // timeout is not resource-release success
            release.countDown(); lane.submit {}.get(2,TimeUnit.SECONDS)
            assertEquals(worker,closer)
        } finally { release.countDown(); lane.shutdownNow() }
    }

    @Test fun legacyInitializationContinuesIntoCalls() {
        assertFalse(ArrivalRuntimeSetup.initialize(keys,false,8,4) {})
    }

    @Test fun firstWarmupContractRejectsExtraCallsAndOtherBackend() {
        assertTrue(ArrivalRuntimeSetup.firstWarmupOnly("first_warmup", listOf("classification_CPU"), 0))
        assertFalse(ArrivalRuntimeSetup.firstWarmupOnly("setup_only", emptyList(), 0))
        for (keys in listOf(emptyList(), listOf("classification_GPU"), listOf("classification_CPU", "classification_CPU"))) {
            assertThrows(IllegalArgumentException::class.java) { ArrivalRuntimeSetup.firstWarmupOnly("first_warmup", keys, 0) }
        }
        assertThrows(IllegalArgumentException::class.java) { ArrivalRuntimeSetup.firstWarmupOnly("first_warmup", listOf("classification_CPU"), 1) }
    }

    @Test fun firstWarmupRunsOnceOnExistingLaneAndReturnsBeforeRequests() {
        val lane=Executors.newSingleThreadExecutor(); val records=mutableListOf<String>();var calls=0
        val journal=ArrivalFailureJournal("00000000-0000-4000-8000-000000000001", "a".repeat(64), System::nanoTime, { records += it.toString(Charsets.UTF_8) })
        try {
            val owner=lane.submit<Long> { Thread.currentThread().id }.get()
            ArrivalRuntimeSetup.runFirstWarmup(lane,journal,"request") { assertEquals(owner,Thread.currentThread().id);calls++ }
            assertEquals(1,calls)
            assertEquals(5,records.size)
            assertTrue(records.last().contains("first_warmup"))
        } finally { lane.shutdownNow() }
    }

    @Test fun firstWarmupFailureDoesNotReportSuccess() {
        val lane=Executors.newSingleThreadExecutor(); val records=mutableListOf<String>()
        val journal=ArrivalFailureJournal("00000000-0000-4000-8000-000000000001", "a".repeat(64), System::nanoTime, { records += it.toString(Charsets.UTF_8) })
        try {
            assertThrows(ExecutionException::class.java) { ArrivalRuntimeSetup.runFirstWarmup(lane,journal,"request") { error("injected call") } }
            assertTrue(records.any { it.contains("failed") })
            assertFalse(records.any { it.contains("first_warmup") })
        } finally { lane.shutdownNow() }
    }

    @Test fun firstWarmupTimeoutPreservesIntentAndDoesNotRetry() {
        val lane=Executors.newSingleThreadExecutor(); val release=CountDownLatch(1)
        val records=java.util.Collections.synchronizedList(mutableListOf<String>())
        val journal=ArrivalFailureJournal("00000000-0000-4000-8000-000000000001", "a".repeat(64), System::nanoTime, { records += it.toString(Charsets.UTF_8) })
        try {
            assertThrows(TimeoutException::class.java) {
                ArrivalRuntimeSetup.runFirstWarmup(lane,journal,"request",50,TimeUnit.MILLISECONDS) { release.await() }
            }
            assertTrue(records.any { it.contains("timeout") })
            assertFalse(records.any { it.contains("first_warmup") })
        } finally { release.countDown();lane.shutdownNow();lane.awaitTermination(1,TimeUnit.SECONDS) }
    }
}
