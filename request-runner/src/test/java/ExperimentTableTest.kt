package com.example.d1check.requestrunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

/** K1b (v3, 등록 v3 §0-2): 실험 ID 표 — 요청 수 · 공통창 · index 범위 · watchdog · 요청표 검증 허용 수 · 모르는 ID 거부. */
class ExperimentTableTest {
    @Test fun tableMatchesRegistrationV3() {
        val ids = MixreqContract.EXPERIMENTS.map { it.id }
        assertEquals(listOf("S26-MIXREQ-02", "S26-MIXREQ-02C", "S26-MIXREQ-03"), ids)
        assertEquals(listOf("S26-MIXREQ-02-SMOKE", "S26-MIXREQ-02C-SMOKE", "S26-MIXREQ-03-SMOKE"), MixreqContract.EXPERIMENTS.map { it.smokeId })
        assertEquals(listOf(192, 192, 3_000), MixreqContract.EXPERIMENTS.map { it.requestCount })
        assertEquals(listOf(120L, 120L, 720L), MixreqContract.EXPERIMENTS.map { it.commonS })
        assertTrue(MixreqContract.EXPERIMENTS.all { it.sessionIndexMax == 15 })
        assertEquals(1_260_000L, MixreqContract.WATCHDOG_MS)   // 표의 최댓값 (-03: 180 + 60 + 30 + 720 + 30 + 60 = 1,080 s + 여유)
        assertEquals(600_000L, MixreqContract.experimentOf("S26-MIXREQ-02C").watchdogMs)
        assertEquals("S26-MIXREQ-03", MixreqContract.experimentOf("S26-MIXREQ-03-SMOKE").id)
        assertThrows(IllegalStateException::class.java) { MixreqContract.experimentOf("S26-MIXREQ-04") }
        assertThrows(IllegalStateException::class.java) { MixreqContract.experimentOf("S26-MIXREQ-01") }   // v1 id: v1 APK 가 받던 값, v3 APK 는 거부
    }

    @Test fun commonWindowFollowsTheActiveExperiment() {
        val saved = MixreqContract.activeExperiment
        try {
            MixreqContract.activeExperiment = MixreqContract.experimentOf("S26-MIXREQ-02C")
            assertEquals(120_000_000_000L, MixreqContract.COMMON_NS)
            MixreqContract.activeExperiment = MixreqContract.experimentOf("S26-MIXREQ-03")
            assertEquals(720_000_000_000L, MixreqContract.COMMON_NS)
        } finally {
            MixreqContract.activeExperiment = saved
        }
    }

    @Test fun requestTableAcceptsTheTableCountsOnly() {
        val sid = RequestPlan.sessionId("S26-MIXREQ-03", 0)
        val rows = RequestPlan.requests(sid, 3_000)
        assertEquals(3_000, rows.size)
        assertEquals(1_500, rows.count { it.task == "classification" && it.priority == "urgent" && it.deadlineMs == 1_500L })
        assertEquals(1_500, rows.count { it.task == "detection" && it.priority == "normal" && it.deadlineMs == 6_000L })
        assertEquals(634_800L, rows.last().offsetMs)   // 35,000 + 200 × 2,999 (등록 v3 (S)-2: 35.0 ~ 634.8 s)
        MixreqContract.validateRequests(rows, 3_000)
        RequestPlan.requireDerived("S26-MIXREQ-03", 0, sid, rows)
        assertThrows(IllegalArgumentException::class.java) { RequestPlan.requests(sid, 2_999) }
        assertThrows(IllegalArgumentException::class.java) { MixreqContract.validateRequests(rows.dropLast(1), 2_999) }
        assertThrows(IllegalArgumentException::class.java) { MixreqContract.validateRequests(rows, 192) }
        MixreqContract.validateRequests(RequestPlan.requests(RequestPlan.sessionId("S26-MIXREQ-03-SMOKE", 1), 24), 24)
    }
}
