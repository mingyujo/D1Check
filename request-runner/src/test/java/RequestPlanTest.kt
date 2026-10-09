package com.example.d1check.requestrunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

/** K1: 192 요청 · 짝/홀 · offset · 기한 · uuid5 == Python uuid.uuid5 (값은 py -3 -c 'import uuid; ...' 로 생성, 2026-10-08 · v2 네임스페이스 2026-10-09). */
class RequestPlanTest {
    @Test fun uuid5MatchesPythonForNamespaceUrl() {
        // v2 namespace S26-MIXREQ-02 (등록 v2 #2) — Python uuid.uuid5(NAMESPACE_URL, "S26-MIXREQ-02/<i>"), 2026-10-09 04:2x
        assertEquals("25a97307-6261-5c0a-b608-fa7a0566bca3", RequestPlan.sessionId(MixreqContract.EXPERIMENT_ID, 0))
        assertEquals("57796f65-279c-5995-8a6a-e3291f80177a", RequestPlan.sessionId(MixreqContract.EXPERIMENT_ID, 1))
        assertEquals("56cd63e1-2777-5202-9ad9-ccfd0c0db61b", RequestPlan.sessionId(MixreqContract.EXPERIMENT_ID, 7))
        assertEquals("c4fe0a73-7aca-5684-9b06-67cc120373b1", RequestPlan.sessionId(MixreqContract.EXPERIMENT_ID, 8))
        assertEquals("7b3badf4-aae4-5011-84f8-64e34692e10e", RequestPlan.sessionId(MixreqContract.EXPERIMENT_ID, 15))
        assertEquals("f6d1ec00-ce61-52a4-a14b-a4face78e590", RequestPlan.sessionId(MixreqContract.SMOKE_EXPERIMENT_ID, 0))
        // v1 namespace (S26-MIXREQ-01, 03f271a) for the record: the derivation itself did not change
        assertEquals("20b64aab-fe48-54ea-b5c8-476ec1972d7d", RequestPlan.sessionId("S26-MIXREQ-01", 0))
        assertEquals("ae211423-4bed-5e7f-a38c-0b981a9a89eb", RequestPlan.sessionId("S26-MIXREQ-01-SMOKE", 0))
        // v3 namespaces (등록 v3 §0-2: -02C 확인 블록 · -03 지속) — Python uuid.uuid5(NAMESPACE_URL, ...), 2026-10-09 20:3x
        assertEquals("4add7ebd-7f7a-5216-af5a-3f1498caa11e", RequestPlan.sessionId("S26-MIXREQ-02C", 0))
        assertEquals("31cc7655-bdff-5aa0-9f69-af4b566418a6", RequestPlan.sessionId("S26-MIXREQ-02C", 8))
        assertEquals("3ece6174-87cc-5de1-bbc0-7a6591aa438f", RequestPlan.sessionId("S26-MIXREQ-02C", 15))
        assertEquals("d9ef7388-bc3d-5081-abc2-389e741209c4", RequestPlan.sessionId("S26-MIXREQ-02C-SMOKE", 0))
        assertEquals("2bf5048f-4ac1-5e15-afc7-7ed43ca567ff", RequestPlan.sessionId("S26-MIXREQ-03", 0))
        assertEquals("88daaebf-efc4-5c0a-9b13-ca31d350a47c", RequestPlan.sessionId("S26-MIXREQ-03", 8))
        assertEquals("0880c952-2502-5521-9c54-a838f5e213e7", RequestPlan.sessionId("S26-MIXREQ-03", 15))
        assertEquals("4e6fec0a-b5da-50e8-b29a-94b5e713755a", RequestPlan.sessionId("S26-MIXREQ-03-SMOKE", 0))
        val sid03 = RequestPlan.sessionId("S26-MIXREQ-03", 0)
        assertEquals("1f3daad3-6e83-534f-b7cc-604c45331528", RequestPlan.requestId(sid03, 0))
        assertEquals("85804c92-baac-543c-8831-460940033f6f", RequestPlan.requestId(sid03, 2999))
        val sid02c = RequestPlan.sessionId("S26-MIXREQ-02C", 8)
        assertEquals("6058feb9-5410-5cab-9ac7-c289df55700b", RequestPlan.requestId(sid02c, 0))
        // A24 namespace string, for the record (tools/d1_sustained_plan.py NAME)
        assertEquals("fd107fbf-b077-5cfb-9112-88a09ad3f838", Uuid5.uuid5(Uuid5.NAMESPACE_URL, "SUSTAINED-CPU-PAR-CONFIRM-01/0").toString())
        val sid0 = RequestPlan.sessionId(MixreqContract.EXPERIMENT_ID, 0)
        assertEquals("4f44b70a-91c7-5ef2-9e65-d90506486a80", RequestPlan.requestId(sid0, 0))
        assertEquals("2cfd0921-4b30-54c1-b755-9ca4060f2b46", RequestPlan.requestId(sid0, 191))
        val sid15 = RequestPlan.sessionId(MixreqContract.EXPERIMENT_ID, 15)
        assertEquals("2f6f7125-800d-5115-826f-2da94a94fa31", RequestPlan.requestId(sid15, 0))
        assertEquals("f053a06a-516b-5ced-9663-e03a123a5490", RequestPlan.requestId(sid15, 191))
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
            assertEquals(35_000L + 200L * i, q.offsetMs)  // v2: step 200 ms (등록 v2 #1); v1 was 400 ms
            assertEquals(if (i % 2 == 0) "classification" else "detection", q.task)
        }
        assertEquals(73_200L, rows.last().offsetMs)  // 35,000 + 200 * 191
        MixreqContract.validateRequests(rows)
        RequestPlan.requireDerived(MixreqContract.EXPERIMENT_ID, 3, sid, rows)
    }

    @Test fun smokeTableIsTheFirst24RequestsOfTheSmokeNamespace() {
        val sid = RequestPlan.sessionId(MixreqContract.SMOKE_EXPERIMENT_ID, 1)
        val rows = RequestPlan.requests(sid, 24)
        assertEquals(24, rows.size)
        assertEquals(35_000L + 200L * 23, rows.last().offsetMs)
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
