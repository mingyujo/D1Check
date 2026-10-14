package com.example.d1check.requestrunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.assertThrows
import org.junit.Test

/**
 * M8 정책 규칙표 (s26/results/m8_prep/contract/policies_m8.json test_cases · 계약표 v1 §1) 를 그대로 돈다: FIFO strict head (추월 없음) · (예정 도착 → ordinal → id) ·
 * SERIAL 전역 1 · PAIR 허용 조합 · 같은 lane 1 · 상한 2 · EDD 절대기한 · 동점 FIFO · CPU 직렬 FIFO (urgent 우선 없음) · 120 s 경계 · WAIT 시작/안 함/cap 잘림.
 * 기존 PolicyStudy.choose 사례 (PolicyStudyTest) 는 그대로 — chooseM8 은 기존 정책 ID 를 받지 않는다.
 */
class PolicyStudyM8Test {
    private val C = MixreqContract
    private val S = 1_000_000_000L
    private fun t(id: String, task: String, ordinal: Int, arrivalS: Double, deadlineS: Double) =
        PolicyStudy.TicketM8(id, task, if (task == "classification") "urgent" else "normal", ordinal, (arrivalS * S).toLong(), (deadlineS * S).toLong())
    private fun c(id: String, ordinal: Int, arrivalS: Double) = t(id, "classification", ordinal, arrivalS, arrivalS + 0.8)
    private fun d(id: String, ordinal: Int, arrivalS: Double) = t(id, "detection", ordinal, arrivalS, arrivalS + 2.0)
    private val now = 36 * S
    private val end = 120 * S

    @Test fun fifoStrictHeadNoOvertaking() {
        // head C0 의 GPU busy → D1 (CPU 비어 있음) 추월 안 함
        assertNull(PolicyStudy.chooseM8(C.POLICY_FIFO_PAIR_CG, listOf(c("C0", 0, 35.0), d("D1", 1, 35.0)), listOf("classification_GPU"), now, end))
        // 같은 조건에서 running 이 비면 head C0 → GPU
        val ch = PolicyStudy.chooseM8(C.POLICY_FIFO_PAIR_CG, listOf(d("D1", 1, 35.0), c("C0", 0, 35.0)), emptyList(), now, end)!!
        assertEquals("C0", ch.ticket.id); assertEquals("GPU", ch.backend); assertEquals("classification_GPU", ch.key); assertEquals(PolicyStudy.REASON_M8_FIFO, ch.reason)
    }

    @Test fun fifoOrderIsArrivalThenOrdinalThenId() {
        val w = listOf(d("D5", 5, 35.537), c("C2", 2, 35.0), c("C1", 1, 35.0))
        assertEquals("C1", PolicyStudy.chooseM8(C.POLICY_FIFO_SERIAL_CG, w, emptyList(), now, end)!!.ticket.id)
        val same = listOf(c("b", 7, 35.0), c("a", 7, 35.0))
        assertEquals("a", PolicyStudy.chooseM8(C.POLICY_FIFO_SERIAL_CG, same, emptyList(), now, end)!!.ticket.id)
    }

    @Test fun serialIsGloballyOne() {
        assertNull(PolicyStudy.chooseM8(C.POLICY_FIFO_SERIAL_CG, listOf(d("D3", 3, 35.0)), listOf("classification_GPU"), now, end))
        assertNull(PolicyStudy.chooseM8(C.POLICY_FIFO_SERIAL_CN, listOf(c("C3", 3, 35.0)), listOf("detection_CPU"), now, end))
        assertEquals("CPU", PolicyStudy.chooseM8(C.POLICY_FIFO_SERIAL_CG, listOf(d("D3", 3, 35.0)), emptyList(), now, end)!!.backend)
    }

    @Test fun pairAllowsTheAllowedCombinationUpToTwo() {
        assertEquals("D3", PolicyStudy.chooseM8(C.POLICY_FIFO_PAIR_CG, listOf(d("D3", 3, 35.0)), listOf("classification_GPU"), now, end)!!.ticket.id)
        assertNull(PolicyStudy.chooseM8(C.POLICY_FIFO_PAIR_CG, listOf(c("C4", 4, 35.0)), listOf("classification_GPU"), now, end))           // 같은 lane 1
        assertNull(PolicyStudy.chooseM8(C.POLICY_FIFO_PAIR_CN, listOf(c("C8", 8, 35.537)), listOf("classification_NPU", "detection_CPU"), now, end))   // 상한 2
        assertEquals("NPU", PolicyStudy.chooseM8(C.POLICY_FIFO_PAIR_CN, listOf(c("C0", 0, 35.0)), emptyList(), now, end)!!.backend)       // PAIR_N 는 GPU 를 쓰지 않음
        assertEquals(setOf("classification_GPU", "detection_CPU"), PolicyStudy.allowedPairOf(C.POLICY_FIFO_PAIR_CG))
        assertNull(PolicyStudy.allowedPairOf(C.POLICY_FIFO_SERIAL_CG))
    }

    @Test fun eddUsesAbsoluteDeadlineWithFifoTies() {
        val w = listOf(d("D0", 0, 35.0), c("C1", 1, 35.0))      // D0 dl 37.0 · C1 dl 35.8
        assertEquals("C1", PolicyStudy.chooseM8(C.POLICY_EDD_SERIAL_CG, w, emptyList(), now, end)!!.ticket.id)
        assertEquals("D0", PolicyStudy.chooseM8(C.POLICY_FIFO_SERIAL_CG, w, emptyList(), now, end)!!.ticket.id)   // FIFO 였으면 D0
        val tie = listOf(c("C9", 9, 35.537), c("C2", 2, 35.0), c("C1", 1, 35.0))
        assertEquals("C1", PolicyStudy.chooseM8(C.POLICY_EDD_SERIAL_CG, tie, emptyList(), now, end)!!.ticket.id)
        assertNull(PolicyStudy.chooseM8(C.POLICY_EDD_SERIAL_CG, listOf(c("C1", 1, 35.0), d("D0", 0, 35.0)), listOf("detection_CPU"), now, end))   // strict · SERIAL
        assertEquals(PolicyStudy.REASON_M8_EDD, PolicyStudy.chooseM8(C.POLICY_EDD_SERIAL_CG, tie, emptyList(), now, end)!!.reason)
    }

    @Test fun cpuSerialIsFifoWithoutUrgentFirst() {
        val w = listOf(c("C1", 1, 35.4), d("D0", 0, 35.0))
        val m8 = PolicyStudy.chooseM8(C.POLICY_FIFO_SERIAL_CPU, w, emptyList(), now, end)!!
        assertEquals("D0", m8.ticket.id); assertEquals("CPU", m8.backend)
        // 기존 CPU_URGENT 는 urgent 먼저 (보존 · 비교용)
        val old = PolicyStudy.choose(C.POLICY_CPU, listOf(PolicyStudy.Ticket("C1", "classification", "urgent", 1), PolicyStudy.Ticket("D0", "detection", "normal", 0)), true, true)!!
        assertEquals("C1", old.ticket.id)
    }

    @Test fun noReadyAndWindowEnd() {
        assertNull(PolicyStudy.chooseM8(C.POLICY_FIFO_SERIAL_CG, emptyList(), emptyList(), now, end))
        assertNull(PolicyStudy.chooseM8(C.POLICY_FIFO_SERIAL_CG, listOf(c("C100", 100, 119.9)), emptyList(), (120.001 * S).toLong(), end))
        assertEquals("C100", PolicyStudy.chooseM8(C.POLICY_FIFO_SERIAL_CG, listOf(c("C100", 100, 119.9)), emptyList(), (119.999 * S).toLong(), end)!!.ticket.id)
    }

    @Test fun waitRules() {
        val a = M8Plan.WAIT200X16
        assertEquals(200L, PolicyStudy.plannedWaitMs(a, 1, setOf(0), 200, 0, true))                 // 시작 조건: ready head · running 0 · 묶음 1 처음
        assertNull(PolicyStudy.plannedWaitMs(a, 1, setOf(0), 200, 1, true))                          // running 있음 = 의도 WAIT 아님 (owner 전부 AVAILABLE 때만)
        assertNull(PolicyStudy.plannedWaitMs(a, 1, setOf(0, 1), 400, 0, true))                       // 같은 묶음 두 번째 head = WAIT 0
        assertNull(PolicyStudy.plannedWaitMs(M8Plan.WAIT200X12, 12, (0..11).toSet(), 2_400, 0, true))   // 첫 n 밖 = WAIT 0
        assertNull(PolicyStudy.plannedWaitMs(a, 0, emptySet(), 0, 0, false))                         // ready 없음
        assertEquals(1_000L, PolicyStudy.plannedWaitMs(M8Plan.WAIT1000X12, 11, (0..10).toSet(), 11_000, 0, true))   // 마지막 허용 묶음도 전량 (잘라 쓰지 않음)
    }

    /** 조민규 01:5x #2: 세 처방 (200×16 · 200×12 · 1000×12) — ID 하나 FIFO_WAIT_CG_V1 + 인자 (wait_ms · first_n_bursts · nominal_total_ms) · 묶음별 최초 eligible head 한 번 · 그 뒤 WAIT 0 · 명목 = wait × n. */
    private fun simulateBursts(args: M8Plan.WaitArgs): List<Long?> {
        val waited = mutableSetOf<Int>()
        var cumulative = 0L
        return (0 until M8Plan.BURST_COUNT).map { k ->
            val planned = PolicyStudy.plannedWaitMs(args, k, waited, cumulative, 0, true)
            if (planned != null) { waited += k; cumulative += planned }
            // 같은 묶음의 두 번째 · 세 번째 head: 항상 WAIT 0
            assertNull(PolicyStudy.plannedWaitMs(args, k, waited, cumulative, 0, true))
            planned
        }
    }

    @Test fun wait200x16Core() {
        val p = simulateBursts(M8Plan.WAIT200X16)
        assertEquals(List(16) { 200L }, p)
        assertEquals(3_200L, p.filterNotNull().sum()); assertEquals(3_200L, M8Plan.WAIT200X16.nominalTotalMs)
        assertEquals(listOf("wait_ms", "first_n_bursts", "nominal_total_ms"), M8Plan.WAIT200X16.record().keys.toList()); assertEquals("{wait_ms=200, first_n_bursts=16, nominal_total_ms=3200}", M8Plan.WAIT200X16.record().toString())
    }

    @Test fun wait200x12Contrast() {
        val p = simulateBursts(M8Plan.WAIT200X12)
        assertEquals(List(12) { 200L } + List(4) { null }, p)
        assertEquals(2_400L, p.filterNotNull().sum()); assertEquals(2_400L, M8Plan.WAIT200X12.nominalTotalMs)
    }

    @Test fun wait1000x12Long() {
        val p = simulateBursts(M8Plan.WAIT1000X12)
        assertEquals(List(12) { 1_000L } + List(4) { null }, p)
        assertEquals(12_000L, p.filterNotNull().sum()); assertEquals(12_000L, M8Plan.WAIT1000X12.nominalTotalMs)
        assertThrows(IllegalArgumentException::class.java) { M8Plan.WaitArgs(200, 16, 3_000) }       // nominal ≠ wait × n → 거부
        assertEquals(setOf("M128_WAIT200x16", "M128_WAIT200x12", "M128_WAIT1000x12"), M8Plan.arms(C.M8_M128_ID).filter { it.wait != null }.map { it.name }.toSet())
        assertTrue(M8Plan.arms(C.M8_M128_ID).filter { it.wait != null }.all { it.policy == C.POLICY_FIFO_WAIT_CG })   // ID 하나 · 인자로 구분
    }

    @Test fun tablesAndOldPoliciesRejected() {
        assertEquals("FIFO", PolicyStudy.selectionOf(C.POLICY_FIFO_WAIT_CG)); assertEquals("EDD", PolicyStudy.selectionOf(C.POLICY_EDD_SERIAL_CG))
        assertEquals("PAIR", PolicyStudy.concurrencyOf(C.POLICY_FIFO_PAIR_CN)); assertEquals("SERIAL", PolicyStudy.concurrencyOf(C.POLICY_FIFO_WAIT_CG))
        assertEquals("GPU", PolicyStudy.laneForM8(C.POLICY_FIFO_WAIT_CG, "classification")); assertEquals("CPU", PolicyStudy.laneForM8(C.POLICY_FIFO_WAIT_CG, "detection"))
        assertEquals("NPU", PolicyStudy.laneForM8(C.POLICY_FIFO_SERIAL_CN, "classification")); assertEquals("CPU", PolicyStudy.laneForM8(C.POLICY_FIFO_SERIAL_CPU, "classification"))
        assertThrows(IllegalArgumentException::class.java) { PolicyStudy.chooseM8(C.POLICY_CPU, listOf(c("C0", 0, 35.0)), emptyList(), now, end) }
        assertThrows(IllegalArgumentException::class.java) { PolicyStudy.choose(C.POLICY_FIFO_SERIAL_CG, emptyList(), true, true) }   // 기존 choose 는 M8 ID 를 받지 않는다
        assertEquals(7, C.M8_POLICIES.size)
        assertEquals(setOf(C.POLICY_CPU, C.POLICY_PAR, C.POLICY_PAR_NPU), C.POLICIES)   // 기존 집합 무변경
    }
}
