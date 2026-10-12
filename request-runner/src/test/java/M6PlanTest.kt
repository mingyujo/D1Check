package com.example.d1check.requestrunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * M6 (d1sim/docs/M6_동일APK_사전등록_v3.md §1 · §3-2 · §3-5 · §4-1): 부하 L / B 식 · ORDER · uuid5 == Python · M6 표 2행 · 블록 M ·
 * SessionManifest.validate 의 M6 분기 · 기존 표 (EXPERIMENTS · M5) 무변경.
 * uuid5 기대값 = Python uuid.uuid5(NAMESPACE_URL, ...) (2026-10-12 23:5x).
 */
class M6PlanTest {
    private val p0 = RequestPlan.sessionId("S26-M6-P", 0)

    @Test fun uuid5MatchesPython() {
        assertEquals("89f44a8e-c543-5ac1-a184-9c2c3624cc38", p0)
        assertEquals("7fd3d8d3-fcd3-5c4f-a0ac-b4e72e05af9e", RequestPlan.sessionId("S26-M6-P", 11))
        assertEquals("23f345fa-ee79-595e-86aa-782e7ee01ef3", RequestPlan.sessionId("S26-M6-P-SMOKE", 3))
        assertEquals("9ce6bdc4-706e-591b-9f2b-f2ae3819ffe3", RequestPlan.sessionId("S26-M6-K", 0))
        assertEquals("9e2c584b-502b-50d9-badc-1e039c4d1522", RequestPlan.sessionId("S26-M6-K", 3))
        assertEquals("3ec2bf32-bc1e-515e-bbed-358c58db8652", RequestPlan.sessionId("S26-M6-K-SMOKE", 0))
        val rows = M6Plan.requests("S26-M6-P", 0, p0)
        assertEquals("064a4c21-eafc-5711-a279-fd638f01800e", rows.first().id)
        assertEquals("8df6aeef-4cdf-5e0a-a330-231cca2d50f0", rows.last().id)
    }

    @Test fun loadsMatchRegistration() {
        val l = M6Plan.loadRequests(p0, "L")
        assertEquals(100, l.size)
        assertEquals((0 until 100).map { 35_000L + 400L * it }, l.map { it.offsetMs })
        assertEquals(35_000L, l.first().offsetMs)
        assertEquals(74_600L, l.last().offsetMs)
        val b = M6Plan.loadRequests(p0, "B")
        assertEquals(100, b.size)
        assertEquals(35_000L, b.first().offsetMs)
        assertEquals(71_450L, b.last().offsetMs)   // 35,000 + 4,000 × 9 + 50 × 9
        assertEquals(listOf(35_000L, 35_050L, 35_100L), b.take(3).map { it.offsetMs })
        assertEquals(39_000L, b[10].offsetMs)
        for (rows in listOf(l, b)) {
            assertEquals(50, rows.count { it.task == "classification" })
            assertEquals(50, rows.count { it.task == "detection" })
            rows.forEachIndexed { i, q ->
                assertEquals(i, q.ordinal)
                val urgent = q.task == "classification"
                assertEquals(if (urgent) "urgent" else "normal", q.priority)
                assertEquals(if (urgent) 1_500L else 6_000L, q.deadlineMs)
            }
            assertTrue(rows.zipWithNext().all { (x, y) -> x.offsetMs < y.offsetMs })
        }
        // L: 짝 = 분류 · B: 버스트 안 j 짝 = 분류
        assertTrue(l.all { (it.ordinal % 2 == 0) == (it.task == "classification") })
        assertTrue(b.all { (it.ordinal % 10 % 2 == 0) == (it.task == "classification") })
    }

    @Test fun orderIsTheRegisteredMirror() {
        assertEquals(listOf("L-C", "B-G", "L-N", "B-C", "L-G", "B-N"), M6Plan.ORDER.take(6))
        assertEquals(listOf("B-N", "L-G", "B-C", "L-N", "B-G", "L-C"), M6Plan.ORDER.drop(6))
        assertEquals(M6Plan.ORDER.take(6).reversed(), M6Plan.ORDER.drop(6))
        assertEquals(MixreqContract.POLICY_CPU, M6Plan.policyOf(0))
        assertEquals(MixreqContract.POLICY_PAR, M6Plan.policyOf(1))
        assertEquals(MixreqContract.POLICY_PAR_NPU, M6Plan.policyOf(2))
        assertEquals("B", M6Plan.loadOf(3))
        // 같은 부하의 세 규칙: (ordinal · task · priority · offset · deadline) 같음 (id 만 sid 에서 다름)
        fun proj(i: Int) = M6Plan.requests("S26-M6-P", i, RequestPlan.sessionId("S26-M6-P", i)).map { listOf(it.ordinal, it.task, it.priority, it.offsetMs, it.deadlineMs) }
        assertEquals(proj(0), proj(2))
        assertEquals(proj(0), proj(4))
        assertEquals(proj(1), proj(3))
        assertEquals(proj(1), proj(5))
        assertFalse(proj(0) == proj(1))
        assertTrue(M6Plan.requests("S26-M6-K", 0, RequestPlan.sessionId("S26-M6-K", 0)).isEmpty())
    }

    @Test fun tablesAndBlockM() {
        assertEquals(listOf("S26-MIXREQ-02", "S26-MIXREQ-02C", "S26-MIXREQ-03"), MixreqContract.EXPERIMENTS.map { it.id })
        assertEquals(listOf("S26-STATESPLIT-01", "S26-SUSTAIN-ABBA-01"), MixreqContract.M5_EXPERIMENTS.map { it.id })
        assertEquals(1_260_000L, MixreqContract.WATCHDOG_MS)
        assertTrue(MixreqContract.WATCHDOG_MS >= 1_140_000L)   // K: 180 + 60 + 30 + 780 + 30 + 60
        val p = MixreqContract.experimentOf("S26-M6-P")
        assertEquals(listOf(100L, 120L, 11L), listOf(p.requestCount.toLong(), p.commonS, p.sessionIndexMax.toLong()))
        val k = MixreqContract.experimentOf("S26-M6-K-SMOKE")
        assertEquals(listOf(0L, 780L, 3L), listOf(k.requestCount.toLong(), k.commonS, k.sessionIndexMax.toLong()))
        assertTrue(MixreqContract.isM6("S26-M6-P-SMOKE"))
        assertFalse(MixreqContract.isM6("S26-STATESPLIT-01"))
        assertFalse(MixreqContract.isM6("S26-M6-E"))   // 게이지 진단은 세션 표 밖
        assertEquals(MixreqContract.KEYS_BLOCK_N, MixreqContract.keysOf("M"))
        assertEquals(5, MixreqContract.keysOf("M").size)
        assertEquals(setOf(MixreqContract.POLICY_CPU, MixreqContract.POLICY_PAR, MixreqContract.POLICY_PAR_NPU), MixreqContract.policiesOf("M"))
        assertEquals(MixreqContract.SETUP_NS_BLOCK_N, MixreqContract.setupNsOf("M"))
        // 기존 블록 무변경
        assertEquals(setOf(MixreqContract.POLICY_CPU, MixreqContract.POLICY_PAR), MixreqContract.policiesOf("A"))
        assertEquals(setOf(MixreqContract.POLICY_CPU, MixreqContract.POLICY_PAR_NPU), MixreqContract.policiesOf("N"))
        assertEquals(MixreqContract.SETUP_NS_BLOCK_A, MixreqContract.setupNsOf("A"))
        // 짝/홀 검증은 100 · 0 을 받지 않는다 (M6 요청표는 M6Plan 만)
        assertThrows(IllegalArgumentException::class.java) { MixreqContract.validateRequests(M6Plan.loadRequests(p0, "L"), 100) }
    }

    @Test fun validationRejectsTampering() {
        val rows = M6Plan.loadRequests(p0, "L")
        M6Plan.validateLoad(rows, "L")
        RequestPlan.requireDerived("S26-M6-P", 0, p0, rows)
        assertThrows(IllegalArgumentException::class.java) { M6Plan.validateLoad(rows, "B") }
        assertThrows(IllegalArgumentException::class.java) { M6Plan.validateLoad(rows.dropLast(1), "L") }
        assertThrows(IllegalArgumentException::class.java) { M6Plan.validateLoad(rows.mapIndexed { i, q -> if (i == 7) q.copy(offsetMs = q.offsetMs + 1) else q }, "L") }
        assertThrows(IllegalArgumentException::class.java) { M6Plan.validateLoad(rows.mapIndexed { i, q -> if (i == 8) q.copy(deadlineMs = 6_000L) else q }, "L") }
        // index 0 = L 인데 B 표를 주면 거부 (index 에서 부하를 유도)
        assertThrows(IllegalArgumentException::class.java) { RequestPlan.requireDerived("S26-M6-P", 0, p0, M6Plan.loadRequests(p0, "B")) }
        assertThrows(IllegalArgumentException::class.java) { RequestPlan.requireDerived("S26-M6-P", 1, p0, rows) }
    }

    private fun manifest(experimentId: String, split: String, index: Int, requests: List<MixreqContract.Request>, block: String = "M",
                         policy: String, timeScale: Int = 1, commonS: Long = 120L): SessionManifest {
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

    @Test fun sessionManifestAcceptsM6AndKeepsOldChecks() {
        val saved = MixreqContract.activeExperiment
        try {
            for (i in 0..11) {
                val sid = RequestPlan.sessionId("S26-M6-P", i)
                manifest("S26-M6-P", "confirmation", i, M6Plan.requests("S26-M6-P", i, sid), policy = M6Plan.policyOf(i)).validate()
            }
            assertEquals(120_000_000_000L, MixreqContract.COMMON_NS)
            val smoke = RequestPlan.sessionId("S26-M6-P-SMOKE", 3)
            manifest("S26-M6-P-SMOKE", "diagnostic", 3, M6Plan.requests("S26-M6-P-SMOKE", 3, smoke), policy = MixreqContract.POLICY_CPU).validate()
            for (i in 0..3) manifest("S26-M6-K", "confirmation", i, emptyList(), policy = MixreqContract.POLICY_CPU, commonS = 780L).validate()
            assertEquals(780_000_000_000L, MixreqContract.COMMON_NS)
            manifest("S26-M6-K-SMOKE", "diagnostic", 0, emptyList(), policy = MixreqContract.POLICY_CPU, timeScale = 10, commonS = 780L).validate()
            // K: 요청이 있으면 · 다른 정책 표기 · 창 120 · index 4 → 거부
            val k0 = RequestPlan.sessionId("S26-M6-K", 0)
            assertThrows(IllegalArgumentException::class.java) {
                manifest("S26-M6-K", "confirmation", 0, M6Plan.loadRequests(k0, "L"), policy = MixreqContract.POLICY_CPU, commonS = 780L).validate()
            }
            assertThrows(IllegalArgumentException::class.java) {
                manifest("S26-M6-K", "confirmation", 0, emptyList(), policy = MixreqContract.POLICY_PAR, commonS = 780L).validate()
            }
            assertThrows(IllegalArgumentException::class.java) {
                manifest("S26-M6-K", "confirmation", 0, emptyList(), policy = MixreqContract.POLICY_CPU, commonS = 120L).validate()
            }
            assertThrows(IllegalArgumentException::class.java) {
                manifest("S26-M6-K", "confirmation", 4, emptyList(), policy = MixreqContract.POLICY_CPU, commonS = 780L).validate()
            }
            // P: index 의 규칙과 다른 정책 · 블록 A/N · index 12 → 거부
            val sid0 = RequestPlan.sessionId("S26-M6-P", 0)
            assertThrows(IllegalArgumentException::class.java) {
                manifest("S26-M6-P", "confirmation", 0, M6Plan.requests("S26-M6-P", 0, sid0), policy = MixreqContract.POLICY_PAR).validate()
            }
            assertThrows(IllegalArgumentException::class.java) {
                manifest("S26-M6-P", "confirmation", 0, M6Plan.requests("S26-M6-P", 0, sid0), block = "N", policy = MixreqContract.POLICY_CPU).validate()
            }
            assertThrows(IllegalArgumentException::class.java) {
                manifest("S26-M6-P", "confirmation", 0, M6Plan.requests("S26-M6-P", 0, sid0), block = "A", policy = MixreqContract.POLICY_CPU).validate()
            }
            val sid12 = RequestPlan.sessionId("S26-M6-P", 12)
            assertThrows(IllegalArgumentException::class.java) {
                manifest("S26-M6-P", "confirmation", 12, M6Plan.loadRequests(sid12, "L"), policy = MixreqContract.POLICY_CPU).validate()
            }
            // 블록 M 은 M6 밖에서 거부 · 기존 실험 무변경
            val old = RequestPlan.sessionId("S26-MIXREQ-02", 0)
            assertThrows(IllegalArgumentException::class.java) {
                manifest("S26-MIXREQ-02", "confirmation", 0, RequestPlan.requests(old, 192), block = "M", policy = MixreqContract.POLICY_CPU).validate()
            }
            manifest("S26-MIXREQ-02", "confirmation", 0, RequestPlan.requests(old, 192), block = "A", policy = MixreqContract.POLICY_CPU).validate()
            val ss = RequestPlan.sessionId("S26-STATESPLIT-01", 0)
            manifest("S26-STATESPLIT-01", "confirmation", 0, StatesplitPlan.requests(ss), block = "A", policy = MixreqContract.POLICY_CPU).validate()
        } finally {
            MixreqContract.activeExperiment = saved
        }
    }
}
