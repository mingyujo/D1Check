package com.example.d1check

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class RunSessionPolicyTest {
    private fun active(id: String, boot: String) =
        RunContext(id, true, 10L, 20L, boot, RunSessionPolicy.STATUS_ACTIVE)

    @Test
    fun staleActiveRunIsReplacedByNewRunId() {
        val decision = RunSessionPolicy.startNew(active("stale", "boot:1"), "boot:1", "fresh", 30L, 40L)
        assertEquals("stale", decision.abortedRunId)
        assertEquals("fresh", decision.run.runId)
        assertNotEquals("stale", decision.run.runId)
        assertTrue(decision.run.active)
    }

    @Test
    fun bootIdentifierChangeNeverReusesMonotonicOrigin() {
        val decision = RunSessionPolicy.startNew(active("old", "boot:1"), "boot:2", "new", 3L, 50L)
        assertEquals("old", decision.abortedRunId)
        assertEquals("boot:2", decision.run.bootId)
        assertEquals(3L, decision.run.startedElapsedNs)
    }
}
