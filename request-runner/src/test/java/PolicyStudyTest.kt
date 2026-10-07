package com.example.d1check.requestrunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Test
import java.io.File

/**
 * K2: A24 ArrivalPolicyStudyTest.onlineDecisionHasOnlyArrivedQueueAndActualAvailability 를 이식 (SERIAL 은 없다) +
 * PAR 사례의 GPU lane 을 NPU lane 으로만 바꾼 PAR-NPU 사례 + 무작위 1,000 사례에서 Kotlin choose == Python policy_ref.choose
 * (fixture = src/test/resources/policy_cases_v1.json, s26/tools/mixreq/make_test_fixtures.py 가 생성).
 */
class PolicyStudyTest {
    private val normal = PolicyStudy.Ticket("normal", "detection", "normal", 0)
    private val urgent = PolicyStudy.Ticket("urgent", "classification", "urgent", 1)
    private val queue = listOf(normal, urgent)

    @Test fun a24CasesPortedCpuAndPar() {
        for (policy in listOf(MixreqContract.POLICY_CPU, MixreqContract.POLICY_PAR)) {
            assertEquals("urgent", PolicyStudy.choose(policy, queue, true, true)!!.ticket.id)
            assertNull(PolicyStudy.choose(policy, emptyList(), true, true))
            assertNull(PolicyStudy.choose(policy, queue, false, false))
        }
        assertEquals("CPU", PolicyStudy.choose(MixreqContract.POLICY_CPU, queue, true, true)!!.backend)
        assertEquals("GPU", PolicyStudy.choose(MixreqContract.POLICY_PAR, queue, false, true)!!.backend)
        assertNull(PolicyStudy.choose(MixreqContract.POLICY_CPU, queue, false, true))
        assertEquals("normal", PolicyStudy.choose(MixreqContract.POLICY_PAR, listOf(normal), true, false)!!.ticket.id)
        assertEquals(PolicyStudy.REASON, PolicyStudy.choose(MixreqContract.POLICY_PAR, queue, true, true)!!.reason)
    }

    @Test fun parNpuIsParWithTheClassificationLaneOnNpu() {
        val p = MixreqContract.POLICY_PAR_NPU
        assertEquals("urgent", PolicyStudy.choose(p, queue, true, true, true)!!.ticket.id)
        assertEquals("NPU", PolicyStudy.choose(p, queue, false, false, true)!!.backend)
        assertEquals("urgent", PolicyStudy.choose(p, queue, false, false, true)!!.ticket.id)
        // NPU busy, CPU free -> the detection request goes first (same as PAR with GPU busy)
        val onlyCpu = PolicyStudy.choose(p, queue, true, true, false)!!
        assertEquals("normal", onlyCpu.ticket.id)
        assertEquals("CPU", onlyCpu.backend)
        assertNull(PolicyStudy.choose(p, queue, false, true, false))
        assertNull(PolicyStudy.choose(p, emptyList(), true, true, true))
        // the GPU lane is never used by PAR-NPU
        assertEquals("NPU", PolicyStudy.choose(p, listOf(urgent), false, true, true)!!.backend)
        // same ordering as PAR: urgent first, then ordinal, then id
        val many = listOf(
            PolicyStudy.Ticket("b", "detection", "normal", 2), PolicyStudy.Ticket("a", "detection", "normal", 2),
            PolicyStudy.Ticket("z", "classification", "urgent", 9),
        )
        assertEquals("z", PolicyStudy.choose(p, many, true, true, true)!!.ticket.id)
        assertEquals("a", PolicyStudy.choose(p, many, true, true, false)!!.ticket.id)
        assertEquals("a", PolicyStudy.choose(MixreqContract.POLICY_PAR, many, true, false, true)!!.ticket.id)
    }

    @Test fun cpuPolicyNeverUsesTheNpuLaneAndUnknownPolicyFails() {
        assertEquals("CPU", PolicyStudy.choose(MixreqContract.POLICY_CPU, listOf(urgent), true, true, false)!!.backend)
        assertThrows(IllegalArgumentException::class.java) { PolicyStudy.choose("B2_SERIAL_ONLINE_V1", queue, true, true) }
        assertEquals("CPU", PolicyStudy.laneFor(MixreqContract.POLICY_CPU, "classification"))
        assertEquals("GPU", PolicyStudy.laneFor(MixreqContract.POLICY_PAR, "classification"))
        assertEquals("NPU", PolicyStudy.laneFor(MixreqContract.POLICY_PAR_NPU, "classification"))
        assertEquals("CPU", PolicyStudy.laneFor(MixreqContract.POLICY_PAR_NPU, "detection"))
    }

    @Test fun thousandRandomCasesAgreeWithThePythonReference() {
        val text = javaClass.classLoader!!.getResource("policy_cases_v1.json")?.readText()
            ?: File("src/test/resources/policy_cases_v1.json").readText()
        val cases = (TestJson.parse(text) as Map<*, *>)["cases"] as List<*>
        assertEquals(1000, cases.size)
        var nonNull = 0
        for (raw in cases) {
            val case = raw as Map<*, *>
            val free = case["free"] as Map<*, *>
            val waiting = (case["waiting"] as List<*>).map { w ->
                w as Map<*, *>
                PolicyStudy.Ticket(w["id"] as String, w["task"] as String, w["priority"] as String, (w["ordinal"] as Number).toInt())
            }
            val choice = PolicyStudy.choose(case["policy"] as String, waiting, free["CPU"] as Boolean, free["GPU"] as Boolean, free["NPU"] as Boolean)
            val expected = case["expected"] as Map<*, *>?
            if (expected == null) assertNull(case.toString(), choice)
            else {
                nonNull++
                assertEquals(case.toString(), expected["id"], choice!!.ticket.id)
                assertEquals(case.toString(), expected["backend"], choice.backend)
            }
        }
        assert(nonNull > 300) { "fixture is degenerate: $nonNull non-null" }
    }
}
