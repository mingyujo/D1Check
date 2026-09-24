package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test
import java.util.concurrent.*

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
}
