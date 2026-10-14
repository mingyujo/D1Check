package com.example.d1check.requestrunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * M8 (계약표 v1 §0 · §2 · banks_m8.json): bank 4 식 · µs · 기한 0.8/2 · 같은 시각 8건 ordinal · 537.155 재계산 · SMOOTH 균등식 · uuid5 새 계보 == Python (2026-10-14 22:4x) ·
 * 실험 행 (index → arm · DEV/CONFIRM 대역) · SessionManifest.validate 의 M8 분기 (contract · 단계 60/90 · policy_args · prep · 블록 NONE) · 기존 표 · 상수 무변경.
 */
class M8PlanTest {
    private val C = MixreqContract

    @Test fun uuid5NewLineageMatchesPython() {
        assertEquals("e4abc988-c5f5-5657-b7d7-e3060cda0ac6", M8Plan.M8_NS.toString())
        assertEquals("e74fd67f-c716-5716-b0ce-f4a1afe628d8", M8Plan.sessionId(C.M8_FN_ID, 0))
        assertEquals("f8f8fb52-72a5-5670-9d83-f1b40dc11ece", M8Plan.sessionId(C.M8_L64_ID, 0))
        assertEquals("534fffe7-2485-5228-ab5c-989b39eb2fe8", M8Plan.sessionId(C.M8_L64_ID, 399))
        assertEquals("91f07d1d-0de6-5f19-a8f7-1ebc6ffa0f8f", M8Plan.sessionId(C.M8_M128_ID, 0))
        assertEquals("09f3d194-ec61-536c-b874-dc31d9010d5d", M8Plan.sessionId(C.M8_M128_ID, 999))
        assertEquals("db4555ad-59a3-534e-acbc-85a81e8a27dd", M8Plan.sessionId("S26-M8-M128-SMOKE", 0))
        assertEquals("ac71ad73-472b-5334-8cc2-0eb09f5feb85", M8Plan.sessionId(C.M8_IDLE_ID, 0))
        val sid = M8Plan.sessionId(C.M8_M128_ID, 0)
        assertEquals("8f95ef14-320c-563d-b257-32ea5a70e761", M8Plan.requestId(sid, 0))
        assertEquals("907ad989-87d1-5565-b9c9-d37302ae8b58", M8Plan.requestId(sid, 127))
        // 기존 계보 (NAMESPACE_URL 직접) 와 다르다
        assertFalse(M8Plan.sessionId(C.M8_M128_ID, 0) == RequestPlan.sessionId(C.M8_M128_ID, 0))
    }

    @Test fun banksMatchTheContract() {
        val l = M8Plan.slots(M8Plan.Bank.L64)
        assertEquals(64, l.size); assertEquals(35_000_000L, l.first().second); assertEquals(98_000_000L, l.last().second)
        assertTrue(l.withIndex().all { (i, s) -> s.first == (if (i % 2 == 0) "classification" else "detection") && s.second == 35_000_000L + 1_000_000L * i })
        val c = M8Plan.slots(M8Plan.Bank.C252)
        assertEquals(252, c.size); assertEquals(118_633_200L, c.last().second); assertTrue(c.all { it.first == "classification" }); assertEquals(35_333_200L, c[1].second)
        val m = M8Plan.slots(M8Plan.Bank.M128)
        assertEquals(128, m.size); assertEquals(96, m.count { it.first == "classification" }); assertEquals(32, m.count { it.first == "detection" })
        assertEquals(List(8) { 35_000_000L }, m.take(8).map { it.second })                       // 같은 시각 8건
        assertEquals("CCCDCCCD", m.take(8).joinToString("") { if (it.first == "classification") "C" else "D" })
        assertEquals(35_537_155L, m[8].second); assertEquals(43_057_325L, m.last().second)          // 537.155 ms × 15
        assertEquals(16, m.map { it.second }.distinct().size)
        val s = M8Plan.slots(M8Plan.Bank.SMOOTH128)
        assertEquals(128, s.size); assertEquals(m.map { it.first }, s.map { it.first })              // task 순서 유지
        assertEquals(35_000_000L, s.first().second); assertEquals(43_057_325L, s.last().second)     // 첫/마지막 유지
        assertEquals(35_063_444L, s[1].second); assertEquals(39_060_384L, s[64].second); assertEquals(42_993_881L, s[126].second)
        assertEquals(128, s.map { it.second }.distinct().size)
        assertTrue(s.map { it.second }.zipWithNext().all { (a, b) -> b - a in 63_443L..63_444L })
        assertEquals(537_155L, M8Plan.burstIntervalUs(73.5442, 241.7197))                          // burst_interval_recalc.json (M6 개발 P 6세션)
        assertEquals(536_336L, M8Plan.burstIntervalUs(73.6814, 241.3512))                          // M6 12세션 전체 → 다름 (기록)
        assertEquals(M8Plan.BURST_INTERVAL_US, M8Plan.burstIntervalUs(73.5442, 241.7197))
    }

    @Test fun requestsCarryMicrosecondsAndDeadlines() {
        val sid = M8Plan.sessionId(C.M8_M128_ID, 0)
        val rows = M8Plan.requests(C.M8_M128_ID, 0, sid)
        assertEquals(128, rows.size)
        rows.forEachIndexed { i, q ->
            assertEquals(i, q.ordinal); assertEquals(q.offsetUs / 1_000L, q.offsetMs)
            if (q.task == "classification") { assertEquals("urgent", q.priority); assertEquals(800L, q.deadlineMs) } else { assertEquals("normal", q.priority); assertEquals(2_000L, q.deadlineMs) }
        }
        assertEquals(35_537L, rows[8].offsetMs); assertEquals(35_537_155L, rows[8].offsetUs)
        val bursts = M8Plan.burstIndexOf(rows)
        assertEquals(0, bursts.getValue(rows[7].id)); assertEquals(1, bursts.getValue(rows[8].id)); assertEquals(15, bursts.getValue(rows[127].id))
        // 기존 Request 생성 (offsetUs 기본값) 은 그대로: M6 표의 offsetUs = offsetMs × 1,000
        val m6 = M6Plan.requests("S26-M6-P", 0, RequestPlan.sessionId("S26-M6-P", 0))
        assertTrue(m6.all { it.offsetUs == it.offsetMs * 1_000L })
        assertEquals(M6Plan.requests("S26-M6-P", 0, RequestPlan.sessionId("S26-M6-P", 0)), m6)   // 같은 유도 → 같은 값 (equals 에 offsetUs 포함)
    }

    @Test fun armsAndBands() {
        assertEquals(listOf("C252_CPU", "C252_GPU", "C252_NPU", "M128_BASE", "M128_PAIR_G", "M128_PAIR_N"), M8Plan.arms(C.M8_FN_ID).map { it.name })
        assertEquals(8, M8Plan.arms(C.M8_M128_ID).size); assertEquals(2, M8Plan.arms(C.M8_L64_ID).size); assertEquals(6, M8Plan.arms(C.M8_RECENT_ID).size)
        assertEquals("M128_WAIT1000x12", M8Plan.armOf(C.M8_M128_ID, 15).name); assertEquals(1, M8Plan.repetitionOf(C.M8_M128_ID, 15))
        assertEquals(M8Plan.WAIT200X16, M8Plan.armOf(C.M8_M128_ID, 3).wait); assertEquals(null, M8Plan.armOf(C.M8_M128_ID, 0).wait)
        assertEquals(M8Plan.Prep.CPU60, M8Plan.armOf(C.M8_RECENT_ID, 2).prep); assertEquals(M8Plan.Prep.IDLE60, M8Plan.armOf(C.M8_RECENT_ID, 3).prep)
        assertEquals(C.BLOCK_NONE, M8Plan.armOf(C.M8_IDLE_ID, 0).block); assertEquals(C.POLICY_NO_RUNTIME, M8Plan.armOf(C.M8_IDLE_ID, 0).policy)
        assertEquals(C.BLOCK_M, M8Plan.armOf(C.M8_IDLE_ID, 1).block)
        assertEquals(500, M8Plan.devCount(C.M8_M128_ID)); assertEquals("dev", M8Plan.analysisSplitOf(C.M8_M128_ID, 499)); assertEquals("confirm", M8Plan.analysisSplitOf(C.M8_M128_ID, 500))
        assertEquals(50, M8Plan.devCount(C.M8_FN_ID)); assertEquals(100, M8Plan.devCount(C.M8_IDLE_ID))
        assertEquals(M8Plan.arms(C.M8_M128_ID), M8Plan.arms("S26-M8-M128-SMOKE"))   // 스모크 ID 도 같은 행
        assertThrows(IllegalArgumentException::class.java) { M8Plan.arms("S26-M6-P") }
    }

    private fun manifest(experimentId: String, index: Int, block: String? = null, policy: String? = null, wait: M8Plan.WaitArgs? = null, prep: M8Plan.Prep? = null,
                         requests: List<MixreqContract.Request>? = null, contract: String = C.CONTRACT_M8, baselineS: Long = 60, coolingS: Long = 90,
                         split: String = C.SPLIT_CONFIRMATION, timeScale: Int = 1, sid: String? = null): SessionManifest {
        val arm = M8Plan.armOf(experimentId, index)
        val sha = "a".repeat(64)
        val blk = block ?: arm.block
        val runtimes = C.keysOf(blk).sorted().map { key ->
            val lane = C.laneOf(key)
            RuntimeSpec(key, C.taskOf(key), Backend.valueOf(lane), if (lane == "NPU") "/x/efficientnet_lite0_Samsung_E9965.tflite" else "/x/m.tflite", sha,
                gpuPrecision = if (lane == "GPU") "FP32" else null, cpuThreads = if (lane == "CPU") 1 else null)
        }
        val s = sid ?: M8Plan.sessionId(experimentId, index)
        return SessionManifest(
            protocol = C.PROTOCOL, experimentId = experimentId, split = split, sessionId = s, sessionIndex = index, block = blk, pair = 0, attempt = 1,
            policy = policy ?: arm.policy, runtimes = runtimes, image = SessionManifest.FileSpec("/x/i.png", sha), imageWidth = 1024, imageHeight = 683,
            anchors = SessionManifest.FileSpec("/x/a.json", sha),
            labels = mapOf("classification" to SessionManifest.FileSpec("/x/c.txt", sha), "detection" to SessionManifest.FileSpec("/x/d.txt", sha)),
            requests = requests ?: M8Plan.requests(experimentId, index, s),
            phases = SessionManifest.Phases(C.setupNsOf(blk) / 1_000_000_000L, 60, baselineS, 120, 30, coolingS),
            samplePeriodMs = 900, timeScale = timeScale, warmupGate = true, stopRules = SessionManifest.StopRules(420, 2, 20), startThermalStatusMax = 1,
            contract = contract, policyArgs = wait ?: arm.wait, prep = prep ?: arm.prep,
        )
    }

    private fun rejects(block: () -> Unit) {
        var threw = false
        try { block() } catch (_: IllegalArgumentException) { threw = true } catch (_: IllegalStateException) { threw = true }
        assertTrue("accepted", threw)
    }

    @Test fun manifestValidationM8Branch() {
        val saved = C.activeExperiment
        try {
            for (id in C.M8_EXPERIMENTS.map { it.id }) for (index in 0 until M8Plan.arms(id).size * 2) manifest(id, index).validate()   // 모든 arm · 반복 2
            manifest("S26-M8-M128-SMOKE", 3, split = C.SPLIT_DIAGNOSTIC, timeScale = 10).validate()
            assertEquals(120_000_000_000L, C.COMMON_NS)
            manifest(C.M8_M128_ID, 1000 - 1).validate()
            rejects { manifest(C.M8_M128_ID, 1000).validate() }                                                   // 상한 밖
            rejects { manifest(C.M8_M128_ID, 0, policy = C.POLICY_EDD_SERIAL_CG).validate() }                     // index 0 = BASE
            rejects { manifest(C.M8_M128_ID, 0, wait = M8Plan.WAIT200X16).validate() }                            // BASE 에 WAIT 인자
            rejects { manifest(C.M8_M128_ID, 3, wait = M8Plan.WAIT200X12).validate() }                            // 다른 인자
            rejects { manifest(C.M8_M128_ID, 3, policy = C.POLICY_FIFO_SERIAL_CG, wait = M8Plan.WAIT200X16).validate() }
            rejects { manifest(C.M8_RECENT_ID, 0, prep = M8Plan.Prep.IDLE60).validate() }                         // 준비 종류 다름
            rejects { manifest(C.M8_M128_ID, 0, prep = M8Plan.Prep.CPU60).validate() }                            // M128 에 준비
            rejects { manifest(C.M8_IDLE_ID, 0, block = C.BLOCK_M).validate() }                                   // NO_RUNTIME 행은 블록 NONE
            rejects { manifest(C.M8_IDLE_ID, 1, block = C.BLOCK_NONE, policy = C.POLICY_NO_RUNTIME).validate() }   // 상주 행은 블록 M
            rejects { manifest(C.M8_M128_ID, 0, block = C.BLOCK_A).validate() }
            rejects { manifest(C.M8_M128_ID, 0, baselineS = 30).validate() }                                      // M8 단계 = 60 / 90
            rejects { manifest(C.M8_M128_ID, 0, coolingS = 60).validate() }
            rejects { manifest(C.M8_M128_ID, 0, contract = C.CONTRACT_M6).validate() }                            // M8 실험 ↔ contract M6
            rejects { manifest(C.M8_M128_ID, 0, sid = RequestPlan.sessionId(C.M8_M128_ID, 0)).validate() }         // 옛 계보 uuid5
            rejects { manifest(C.M8_M128_ID, 0, policy = C.POLICY_PAR).validate() }                               // 기존 정책 ID
            val sid = M8Plan.sessionId(C.M8_M128_ID, 0)
            rejects { manifest(C.M8_M128_ID, 0, requests = M8Plan.requests(C.M8_M128_ID, 8, M8Plan.sessionId(C.M8_M128_ID, 8))).validate() }    // 같은 bank · 다른 세션 ID 의 요청 id
            rejects { manifest(C.M8_M128_ID, 0, requests = M8Plan.bankRequests(sid, M8Plan.Bank.SMOOTH128)).validate() }
            rejects { manifest(C.M8_M128_ID, 0, requests = M8Plan.requests(C.M8_M128_ID, 0, sid).mapIndexed { i, q -> if (i == 9) q.copy(offsetUs = q.offsetUs + 1) else q }).validate() }
            rejects { manifest(C.M8_M128_ID, 0, requests = M8Plan.requests(C.M8_M128_ID, 0, sid).mapIndexed { i, q -> if (i == 3) q.copy(deadlineMs = 6_000L) else q }).validate() }
            rejects { manifest(C.M8_M128_ID, 0, split = C.SPLIT_CONFIRMATION, timeScale = 10).validate() }
        } finally {
            C.activeExperiment = saved
        }
    }

    @Test fun existingTablesAndConstantsUnchanged() {
        assertEquals(listOf("S26-MIXREQ-02", "S26-MIXREQ-02C", "S26-MIXREQ-03"), C.EXPERIMENTS.map { it.id })
        assertEquals(listOf("S26-STATESPLIT-01", "S26-SUSTAIN-ABBA-01"), C.M5_EXPERIMENTS.map { it.id })
        assertEquals(listOf("S26-M6-P", "S26-M6-K"), C.M6_EXPERIMENTS.map { it.id })
        assertTrue((C.EXPERIMENTS + C.M5_EXPERIMENTS + C.M6_EXPERIMENTS).all { it.contract == C.CONTRACT_M6 })
        assertTrue(C.M8_EXPERIMENTS.all { it.contract == C.CONTRACT_M8 && it.requestCount == C.M8_REQUESTS_PER_ROW && it.commonS == 120L })
        assertEquals(listOf(99, 399, 399, 999, 399, 399, 199), C.M8_EXPERIMENTS.map { it.sessionIndexMax })
        assertEquals(60L, C.COOLING_SECONDS); assertEquals(30L, C.BASELINE_SECONDS); assertEquals(1_500L, C.URGENT_DEADLINE_MS); assertEquals(6_000L, C.NORMAL_DEADLINE_MS)
        assertEquals(90L, C.M8_COOLING_SECONDS); assertEquals(60L, C.M8_BASELINE_SECONDS); assertEquals(1_260_000L, C.WATCHDOG_MS)
        assertEquals(setOf(C.POLICY_CPU, C.POLICY_PAR, C.POLICY_PAR_NPU), C.policiesOf("M"))   // 기존 블록 정책 표 무변경
        assertEquals(emptySet<String>(), C.keysOf(C.BLOCK_NONE)); assertEquals(emptySet<String>(), C.usedKeysM8(C.POLICY_NO_RUNTIME))
        assertTrue(C.isM8("S26-M8-RECENT-SMOKE")); assertFalse(C.isM8("S26-M6-P")); assertFalse(C.isM6("S26-M8-FN"))
        // 기존 M6 매니페스트 (contract 기본값 M6) 는 그대로 통과 · contract 를 M8 로 적으면 거부
        val saved = C.activeExperiment
        try {
            val sha = "a".repeat(64)
            val sid = RequestPlan.sessionId("S26-M6-P", 0)
            fun m6(contract: String) = SessionManifest(
                protocol = C.PROTOCOL, experimentId = "S26-M6-P", split = C.SPLIT_CONFIRMATION, sessionId = sid, sessionIndex = 0, block = "M", pair = 0, attempt = 1,
                policy = M6Plan.policyOf(0), runtimes = C.keysOf("M").sorted().map { key ->
                    val lane = C.laneOf(key)
                    RuntimeSpec(key, C.taskOf(key), Backend.valueOf(lane), if (lane == "NPU") "/x/efficientnet_lite0_Samsung_E9965.tflite" else "/x/m.tflite", sha,
                        gpuPrecision = if (lane == "GPU") "FP32" else null, cpuThreads = if (lane == "CPU") 1 else null)
                }, image = SessionManifest.FileSpec("/x/i.png", sha), imageWidth = 1024, imageHeight = 683, anchors = SessionManifest.FileSpec("/x/a.json", sha),
                labels = mapOf("classification" to SessionManifest.FileSpec("/x/c.txt", sha), "detection" to SessionManifest.FileSpec("/x/d.txt", sha)),
                requests = M6Plan.requests("S26-M6-P", 0, sid), phases = SessionManifest.Phases(180, 60, 30, 120, 30, 60), samplePeriodMs = 900, timeScale = 1,
                warmupGate = true, stopRules = SessionManifest.StopRules(420, 2, 20), startThermalStatusMax = 1, contract = contract)
            m6(C.CONTRACT_M6).validate()
            assertFalse(m6(C.CONTRACT_M6).isM8)
            rejects { m6(C.CONTRACT_M8).validate() }
        } finally {
            C.activeExperiment = saved
        }
    }
}
