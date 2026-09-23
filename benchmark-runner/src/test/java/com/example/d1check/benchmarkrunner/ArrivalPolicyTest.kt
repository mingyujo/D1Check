package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test

class ArrivalPolicyTest {
    private val estimates = mapOf("classification_CPU" to 100L, "classification_GPU" to 260L,
        "detection_CPU" to 550L, "detection_GPU" to 1000L)
    private val normal = ArrivalPolicy.Ticket("normal", "detection", "normal", 0)
    private val urgent = ArrivalPolicy.Ticket("urgent", "classification", "urgent", 1)

    @Test fun fifoKeepsArrivalOrderAndNeverPreempts() {
        assertNull(ArrivalPolicy.choose(ArrivalPolicy.FIFO, listOf(normal, urgent), false, true, 400, estimates))
        assertEquals(normal, ArrivalPolicy.choose(ArrivalPolicy.FIFO, listOf(normal, urgent), true, true, 0, estimates)?.ticket)
    }

    @Test fun priorityOnlyChangesNextSelection() {
        assertNull(ArrivalPolicy.choose(ArrivalPolicy.URGENT, listOf(normal, urgent), false, true, 400, estimates))
        assertEquals(urgent, ArrivalPolicy.choose(ArrivalPolicy.URGENT, listOf(normal, urgent), true, true, 0, estimates)?.ticket)
    }

    @Test fun conditionalUsesCurrentBusyTimeAndDoesNotSendToSlowerGpu() {
        val queue = listOf(urgent)
        assertNull(ArrivalPolicy.choose(ArrivalPolicy.CONDITIONAL, queue, false, true, 50, estimates))
        assertEquals("GPU", ArrivalPolicy.choose(ArrivalPolicy.CONDITIONAL, queue, false, true, 300, estimates)?.backend)
        assertEquals("CPU", ArrivalPolicy.choose(ArrivalPolicy.CONDITIONAL, queue, true, true, 0, estimates)?.backend)
    }

    @Test fun fixedSplitSeparatesPriorityFromBackendChoice() {
        assertEquals("GPU", ArrivalPolicy.choose(ArrivalPolicy.FIXED, listOf(normal), true, true, 0, estimates)?.backend)
        assertEquals("CPU", ArrivalPolicy.choose(ArrivalPolicy.FIXED, listOf(normal, urgent), true, true, 0, estimates)?.backend)
    }

    @Test fun fixedSplitNeverStealsIdleOtherLane() {
        assertNull(ArrivalPolicy.choose(ArrivalPolicy.FIXED, listOf(normal), true, false, 0, estimates))
        assertNull(ArrivalPolicy.choose(ArrivalPolicy.FIXED, listOf(urgent), false, true, 400, estimates))
        val choice = ArrivalPolicy.choose(ArrivalPolicy.FIXED, listOf(normal, urgent), false, true, 400, estimates)
        assertEquals(normal, choice?.ticket)
        assertEquals("GPU", choice?.backend)
        val reversedTask = urgent.copy(task = "detection")
        assertEquals("CPU", ArrivalPolicy.choose(ArrivalPolicy.FIXED, listOf(reversedTask), true, true, 0, estimates)?.backend)
    }

    @Test fun decisionsOnlySeeProvidedArrivalsAndDoNotMutateQueue() {
        val arrived = mutableListOf(normal)
        for (policy in listOf(ArrivalPolicy.URGENT, ArrivalPolicy.FIXED, ArrivalPolicy.CONDITIONAL)) {
            val choice = ArrivalPolicy.choose(policy, arrived, true, true, 0, estimates)
            assertEquals(normal, choice?.ticket)
            assertEquals(listOf(normal), arrived)
            assertNull(ArrivalPolicy.choose(policy, emptyList(), true, true, 0, estimates))
        }
    }

    @Test fun conditionalTieUsesCpuAndCannotPreemptBusyLanes() {
        val tie = estimates + ("classification_GPU" to 100L)
        assertEquals("CPU", ArrivalPolicy.choose(ArrivalPolicy.CONDITIONAL, listOf(urgent), true, true, 0, tie)?.backend)
        assertNull(ArrivalPolicy.choose(ArrivalPolicy.CONDITIONAL, listOf(normal, urgent), false, false, 400, estimates))
    }
}
