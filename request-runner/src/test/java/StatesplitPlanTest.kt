package com.example.d1check.requestrunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * M5 (d1sim/docs/상태분리_사전등록_v2.md §1 · 지속감속_확인_사전등록_v1.md §1): 상태 분리 요청열 522 · 구간 · uuid5 == Python ·
 * M5 표 2행 · 기존 표 (EXPERIMENTS) · 짝/홀 검증 무변경 · SessionManifest.validate 분기.
 * uuid5 기대값 = Python uuid.uuid5(NAMESPACE_URL, ...) (2026-10-12 02:0x).
 */
class StatesplitPlanTest {
    private val sid0 = RequestPlan.sessionId("S26-STATESPLIT-01", 0)

    @Test fun uuid5MatchesPython() {
        assertEquals("1474672c-faec-564d-8c0c-7ecb75f31227", sid0)
        assertEquals("0c96572b-ec5a-5026-b466-f9a68c480d25", RequestPlan.sessionId("S26-STATESPLIT-01", 11))
        assertEquals("e56a1e28-e366-5f79-8fef-28ca8cacd31c", RequestPlan.sessionId("S26-STATESPLIT-01-SMOKE", 0))
        assertEquals("91c1d227-2bdc-5aee-85c9-df6052166616", RequestPlan.sessionId("S26-SUSTAIN-ABBA-01", 0))
        assertEquals("c2c72aa2-2fb6-57e8-95b1-21d20db4787d", RequestPlan.sessionId("S26-SUSTAIN-ABBA-01", 3))
        val rows = StatesplitPlan.requests(sid0)
        assertEquals("8996b6cd-5924-59ba-9aaf-c5f2d9c5a333", rows.first().id)
        assertEquals("ab3f776b-7730-520b-838b-3f81fef2899f", rows.last().id)
    }

    @Test fun segmentsMatchRegistration() {
        val rows = StatesplitPlan.requests(sid0)
        assertEquals(522, rows.size)
        fun seg(lo: Long, hi: Long, task: String) = rows.filter { it.offsetMs in lo until hi && it.task == task }
        assertEquals(250, seg(35_000, 60_000, "classification").size)
        assertEquals(0, seg(35_000, 60_000, "detection").size)
        assertEquals(84, seg(65_000, 90_000, "detection").size)
        assertEquals(0, seg(65_000, 90_000, "classification").size)
        assertEquals(125, seg(95_000, 120_000, "classification").size)
        assertEquals(63, seg(95_000, 120_000, "detection").size)
        assertEquals(0, rows.count { it.offsetMs in 60_000 until 65_000 || it.offsetMs in 90_000 until 95_000 || it.offsetMs >= 120_000 })
        assertEquals(35_000L, rows.first().offsetMs)
        assertEquals(119_900L, rows.last().offsetMs)   // S3 탐지 마지막 95,100 + 400 × 62
        assertTrue(rows.zipWithNext().all { (a, b) -> a.offsetMs < b.offsetMs })
        rows.forEachIndexed { i, q ->
            assertEquals(i, q.ordinal)
            val urgent = q.task == "classification"
            assertEquals(if (urgent) "urgent" else "normal", q.priority)
            assertEquals(if (urgent) 1_500L else 6_000L, q.deadlineMs)
        }
        // S3: 분류 200 ms · 탐지 400 ms (+100 ms 어긋남)
        assertEquals(listOf(95_000L, 95_100L, 95_200L, 95_400L, 95_500L), rows.filter { it.offsetMs >= 95_000 }.take(5).map { it.offsetMs })
    }

    @Test fun validationRejectsTampering() {
        val rows = StatesplitPlan.requests(sid0)
        StatesplitPlan.validateRequests(rows)
        RequestPlan.requireDerived("S26-STATESPLIT-01", 0, sid0, rows)
        assertThrows(IllegalArgumentException::class.java) { StatesplitPlan.validateRequests(rows.dropLast(1)) }
        assertThrows(IllegalArgumentException::class.java) {
            StatesplitPlan.validateRequests(rows.mapIndexed { i, q -> if (i == 10) q.copy(offsetMs = q.offsetMs + 1) else q })
        }
        assertThrows(IllegalArgumentException::class.java) {
            StatesplitPlan.validateRequests(rows.mapIndexed { i, q -> if (i == 300) q.copy(deadlineMs = 1_500L) else q })
        }
        // 다른 sid 의 표 / 짝·홀 검증기 (기존) 는 상태 분리 표를 받지 않는다
        assertThrows(IllegalArgumentException::class.java) { RequestPlan.requireDerived("S26-STATESPLIT-01", 1, sid0, rows) }
        assertThrows(IllegalArgumentException::class.java) { MixreqContract.validateRequests(rows, rows.size) }
    }

    @Test fun m5TableDoesNotTouchTheExistingTable() {
        assertEquals(listOf("S26-MIXREQ-02", "S26-MIXREQ-02C", "S26-MIXREQ-03"), MixreqContract.EXPERIMENTS.map { it.id })
        assertEquals(1_260_000L, MixreqContract.WATCHDOG_MS)
        val ss = MixreqContract.experimentOf("S26-STATESPLIT-01")
        assertEquals(listOf(522, 11), listOf(ss.requestCount, ss.sessionIndexMax))
        assertEquals(120L, ss.commonS)
        assertEquals("S26-STATESPLIT-01", MixreqContract.experimentOf("S26-STATESPLIT-01-SMOKE").id)
        val abba = MixreqContract.experimentOf("S26-SUSTAIN-ABBA-01")
        assertEquals(listOf(3_000L, 720L, 3L, 1_260_000L), listOf(abba.requestCount.toLong(), abba.commonS, abba.sessionIndexMax.toLong(), abba.watchdogMs))
        assertTrue(MixreqContract.isStatesplit("S26-STATESPLIT-01-SMOKE"))
        assertFalse(MixreqContract.isStatesplit("S26-SUSTAIN-ABBA-01"))
        assertFalse(MixreqContract.isStatesplit("S26-MIXREQ-02"))
        // 짝/홀 검증의 허용 수는 기존 표만 (522 는 짝/홀 꼴로 받지 않는다)
        assertThrows(IllegalArgumentException::class.java) { RequestPlan.requests(RequestPlan.sessionId("S26-MIXREQ-02", 0), 522) }
        // ABBA = -03 과 같은 짝/홀 3,000 요청열 (sid 만 새 네임스페이스)
        val abbaSid = RequestPlan.sessionId("S26-SUSTAIN-ABBA-01", 2)
        val abbaRows = RequestPlan.requests(abbaSid, 3_000)
        RequestPlan.requireDerived("S26-SUSTAIN-ABBA-01", 2, abbaSid, abbaRows)
        assertEquals(634_800L, abbaRows.last().offsetMs)
    }

    private fun manifest(experimentId: String, split: String, index: Int, requests: List<MixreqContract.Request>, block: String = "A",
                         policy: String = MixreqContract.POLICY_CPU, timeScale: Int = 1, commonS: Long = 120L): SessionManifest {
        val sha = "a".repeat(64)
        val runtimes = MixreqContract.keysOf(block).sorted().map { key ->
            val lane = MixreqContract.laneOf(key)
            val npu = lane == "NPU"
            RuntimeSpec(key, MixreqContract.taskOf(key), Backend.valueOf(lane),
                if (npu) "/x/efficientnet_lite0_Samsung_E9965.tflite" else "/x/m.tflite", sha,
                gpuPrecision = if (lane == "GPU") "FP32" else null, cpuThreads = if (lane == "CPU") 1 else null)
        }
        return SessionManifest(
            protocol = MixreqContract.PROTOCOL, experimentId = experimentId, split = split,
            sessionId = RequestPlan.sessionId(experimentId, index), sessionIndex = index, block = block, pair = 0, attempt = 1,
            policy = policy, runtimes = runtimes, image = SessionManifest.FileSpec("/x/i.png", sha), imageWidth = 1024, imageHeight = 683,
            anchors = SessionManifest.FileSpec("/x/a.json", sha),
            labels = mapOf("classification" to SessionManifest.FileSpec("/x/c.txt", sha), "detection" to SessionManifest.FileSpec("/x/d.txt", sha)),
            requests = requests,
            phases = SessionManifest.Phases(MixreqContract.setupNsOf(block) / 1_000_000_000L, 60, 30, commonS, 30, 60),
            samplePeriodMs = 900, timeScale = timeScale, warmupGate = true, stopRules = SessionManifest.StopRules(420, 2, 20),
            startThermalStatusMax = 1,
        )
    }

    @Test fun sessionManifestAcceptsStatesplitAndKeepsOldChecks() {
        val saved = MixreqContract.activeExperiment
        try {
            val sid11 = RequestPlan.sessionId("S26-STATESPLIT-01", 11)
            manifest("S26-STATESPLIT-01", "confirmation", 11, StatesplitPlan.requests(sid11), block = "N", policy = MixreqContract.POLICY_PAR_NPU).validate()
            assertEquals(120_000_000_000L, MixreqContract.COMMON_NS)
            val smokeSid = RequestPlan.sessionId("S26-STATESPLIT-01-SMOKE", 0)
            manifest("S26-STATESPLIT-01-SMOKE", "diagnostic", 0, StatesplitPlan.requests(smokeSid)).validate()
            // index 12 is outside the M5 table (0..11)
            val sid12 = RequestPlan.sessionId("S26-STATESPLIT-01", 12)
            assertThrows(IllegalArgumentException::class.java) { manifest("S26-STATESPLIT-01", "confirmation", 12, StatesplitPlan.requests(sid12)).validate() }
            // a statesplit id with an alternating table is refused, and an old id with the statesplit table is refused
            val sid0 = RequestPlan.sessionId("S26-STATESPLIT-01", 0)
            assertThrows(IllegalArgumentException::class.java) { manifest("S26-STATESPLIT-01", "confirmation", 0, RequestPlan.requests(sid0, 192)).validate() }
            val old = RequestPlan.sessionId("S26-MIXREQ-02", 0)
            assertThrows(IllegalArgumentException::class.java) { manifest("S26-MIXREQ-02", "confirmation", 0, StatesplitPlan.requests(old)).validate() }
            // old experiment unchanged
            manifest("S26-MIXREQ-02", "confirmation", 0, RequestPlan.requests(old, 192)).validate()
            // ABBA: 3,000 · 720 s · index 0..3
            val abba = RequestPlan.sessionId("S26-SUSTAIN-ABBA-01", 3)
            manifest("S26-SUSTAIN-ABBA-01", "confirmation", 3, RequestPlan.requests(abba, 3_000), policy = MixreqContract.POLICY_PAR, commonS = 720L).validate()
            assertEquals(720_000_000_000L, MixreqContract.COMMON_NS)
            val abba4 = RequestPlan.sessionId("S26-SUSTAIN-ABBA-01", 4)
            assertThrows(IllegalArgumentException::class.java) {
                manifest("S26-SUSTAIN-ABBA-01", "confirmation", 4, RequestPlan.requests(abba4, 3_000), commonS = 720L).validate()
            }
        } finally {
            MixreqContract.activeExperiment = saved
        }
    }
}
