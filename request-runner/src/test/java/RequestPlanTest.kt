package com.example.d1check.requestrunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

/** K1: 192 요청 · 짝/홀 · offset · 기한 · uuid5 == Python uuid.uuid5 (값은 py -3 -c 'import uuid; ...' 로 생성, 2026-10-08). */
class RequestPlanTest {
    @Test fun uuid5MatchesPythonForNamespaceUrl() {
        assertEquals("20b64aab-fe48-54ea-b5c8-476ec1972d7d", RequestPlan.sessionId(MixreqContract.EXPERIMENT_ID, 0))
        assertEquals("74855171-414c-56cb-8096-e2315d480937", RequestPlan.sessionId(MixreqContract.EXPERIMENT_ID, 1))
        assertEquals("e3c32bd0-1235-593d-8503-d30c0ca43e43", RequestPlan.sessionId(MixreqContract.EXPERIMENT_ID, 7))
        assertEquals("27de62f3-eedd-561c-b06d-12e0fd55214e", RequestPlan.sessionId(MixreqContract.EXPERIMENT_ID, 8))
        assertEquals("f59209d8-3a86-53c6-aafa-825ea8eb2c25", RequestPlan.sessionId(MixreqContract.EXPERIMENT_ID, 15))
        assertEquals("ae211423-4bed-5e7f-a38c-0b981a9a89eb", RequestPlan.sessionId(MixreqContract.SMOKE_EXPERIMENT_ID, 0))
        // A24 namespace string, for the record (tools/d1_sustained_plan.py NAME)
        assertEquals("fd107fbf-b077-5cfb-9112-88a09ad3f838", Uuid5.uuid5(Uuid5.NAMESPACE_URL, "SUSTAINED-CPU-PAR-CONFIRM-01/0").toString())
        val sid0 = RequestPlan.sessionId(MixreqContract.EXPERIMENT_ID, 0)
        assertEquals("aab496ba-5456-50de-8472-6ee42998c6cb", RequestPlan.requestId(sid0, 0))
        assertEquals("538200cc-58a0-5fbd-a00b-456462c781f6", RequestPlan.requestId(sid0, 191))
        val sid15 = RequestPlan.sessionId(MixreqContract.EXPERIMENT_ID, 15)
        assertEquals("e9370679-bc4e-554a-a082-cb26a0cde277", RequestPlan.requestId(sid15, 0))
        assertEquals("bb9f95ba-4579-5c20-ba9a-f89baf6de69c", RequestPlan.requestId(sid15, 191))
        assertTrue(Uuid5.isCanonical(sid0))
        assertEquals(5, java.util.UUID.fromString(sid0).version())
        assertEquals(2, java.util.UUID.fromString(sid0).variant())
    }

    @Test fun tableHas192AlternatingRequestsWithFixedOffsetsAndDeadlines() {
        val sid = RequestPlan.sessionId(MixreqContract.EXPERIMENT_ID, 3)
        val rows = RequestPlan.requests(sid)
        assertEquals(192, rows.size)
        assertEquals(192, rows.map { it.id }.toSet().size)
        assertEquals(96, rows.count { it.task == "classification" && it.priority == "urgent" && it.deadlineMs == 1500L })
        assertEquals(96, rows.count { it.task == "detection" && it.priority == "normal" && it.deadlineMs == 6000L })
        rows.forEachIndexed { i, q ->
            assertEquals(i, q.ordinal)
            assertEquals(35_000L + 400L * i, q.offsetMs)
            assertEquals(if (i % 2 == 0) "classification" else "detection", q.task)
        }
        assertEquals(111_400L, rows.last().offsetMs)
        MixreqContract.validateRequests(rows)
        RequestPlan.requireDerived(MixreqContract.EXPERIMENT_ID, 3, sid, rows)
    }

    @Test fun smokeTableIsTheFirst24RequestsOfTheSmokeNamespace() {
        val sid = RequestPlan.sessionId(MixreqContract.SMOKE_EXPERIMENT_ID, 1)
        val rows = RequestPlan.requests(sid, 24)
        assertEquals(24, rows.size)
        assertEquals(35_000L + 400L * 23, rows.last().offsetMs)
        MixreqContract.validateRequests(rows, 24)
    }

    @Test fun validationRejectsShiftedOffsetsWrongTasksDuplicateIdsAndOtherCounts() {
        val sid = RequestPlan.sessionId(MixreqContract.EXPERIMENT_ID, 0)
        val rows = RequestPlan.requests(sid)
        assertThrows(IllegalArgumentException::class.java) { MixreqContract.validateRequests(rows.map { it.copy(offsetMs = it.offsetMs + 1) }) }
        assertThrows(IllegalArgumentException::class.java) { MixreqContract.validateRequests(rows.map { it.copy(id = "same") }) }
        assertThrows(IllegalArgumentException::class.java) { MixreqContract.validateRequests(rows.dropLast(1)) }
        assertThrows(IllegalArgumentException::class.java) { MixreqContract.validateRequests(rows, 96) }
        assertThrows(IllegalArgumentException::class.java) {
            MixreqContract.validateRequests(rows.mapIndexed { i, q -> if (i == 5) q.copy(task = "classification", priority = "urgent", deadlineMs = 1500) else q })
        }
        assertThrows(IllegalArgumentException::class.java) { RequestPlan.requireDerived(MixreqContract.EXPERIMENT_ID, 1, sid, rows) }
        assertThrows(IllegalArgumentException::class.java) {
            RequestPlan.requireDerived(MixreqContract.EXPERIMENT_ID, 0, sid, rows.mapIndexed { i, q -> if (i == 7) q.copy(id = RequestPlan.requestId(sid, 8)) else q })
        }
    }
}
