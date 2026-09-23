package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test

class ArrivalTimingDevTest {
    private val normal = ArrivalPolicy.Ticket("n", "detection", "normal", 0)
    private val urgent = ArrivalPolicy.Ticket("u", "classification", "urgent", 1)
    private val budget = ArrivalTimingDev.Budget(40, 100, 10, 5, 2) // synthetic nanoseconds, NOT fitted data
    private val budgets = listOf("classification", "detection").flatMap { task ->
        listOf("CPU", "GPU").map { "${task}_$it" to if (it == "CPU") budget else ArrivalTimingDev.Budget(40, 250, 10, 5, 2) }
    }.toMap()
    private fun lane(phase: ArrivalTimingDev.Phase, since: Long, persist: Long? = null) =
        ArrivalTimingDev.Lane("CPU", phase, "active", "detection", since, persist)
    private fun choose(cpu: ArrivalTimingDev.Lane, time: Long, gpu: ArrivalTimingDev.Lane = ArrivalTimingDev.Lane("GPU")) =
        ArrivalTimingDev.decide(listOf(urgent), mapOf("CPU" to cpu, "GPU" to gpu), time, budgets)

    @Test fun delayedStartKeepsPreparationSeparateFromService() {
        val assigned = lane(ArrivalTimingDev.Phase.ASSIGNED, 0)
        assertEquals(125L, ArrivalTimingDev.remaining(assigned, 30, budget).ns)
        assertEquals("UNKNOWN_OVERRUN", ArrivalTimingDev.remaining(assigned, 50, budget).state)
        val executing = lane(ArrivalTimingDev.Phase.EXECUTING, 60)
        assertEquals(105L, ArrivalTimingDev.remaining(executing, 70, budget).ns)
    }
    @Test fun busyOverrunIsUnknownAndCannotBecomeFreeOrAnInfinityPenalty() {
        val executing = lane(ArrivalTimingDev.Phase.EXECUTING, 60)
        val remaining = ArrivalTimingDev.remaining(executing, 161, budget)
        assertNull(remaining.ns); assertEquals("UNKNOWN_OVERRUN", remaining.state)
        assertNull(choose(executing, 161).choice)
        assertEquals("wait_unknown", choose(executing, 161).reason)
    }
    @Test fun outputAndWorkerReleaseAreNotSchedulerAvailability() {
        assertEquals(12L, ArrivalTimingDev.remaining(lane(ArrivalTimingDev.Phase.OUTPUT_READY, 100), 103, budget).ns)
        val release = lane(ArrivalTimingDev.Phase.WORKER_RELEASED, 112, 110)
        assertEquals(2L, ArrivalTimingDev.remaining(release, 113, budget).ns)
        assertNull(choose(release, 113).choice)
        assertEquals("UNKNOWN_OVERRUN", ArrivalTimingDev.remaining(release, 116, budget).state)
        assertEquals("CPU", choose(ArrivalTimingDev.Lane("CPU"), 116).choice?.backend)
    }
    @Test fun bothBusyAndEmptyQueueCallsAreRecorded() {
        var time = 1L
        val recorder = ArrivalTimingDev.Recorder({ time++ }, budgets, "synthetic", "PC unit test")
        recorder.mark("CPU", normal, ArrivalTimingDev.Phase.ASSIGNED)
        recorder.mark("GPU", urgent, ArrivalTimingDev.Phase.ASSIGNED)
        assertEquals("wait_both_busy", recorder.choose(listOf(normal)).first.reason)
        assertEquals("wait_empty", recorder.choose(emptyList()).first.reason)
        assertEquals(4, (recorder.artifact(false)["records"] as List<*>).size)
    }
    @Test fun unknownBudgetsUseExplicitCpuDiagnosticFallback() {
        val result = ArrivalTimingDev.decide(listOf(normal, urgent), mapOf("CPU" to ArrivalTimingDev.Lane("CPU"),
            "GPU" to ArrivalTimingDev.Lane("GPU")), 1, emptyMap())
        assertEquals(urgent, result.choice?.ticket)
        assertEquals("fallback_cpu_unknown", result.reason)
        assertTrue(result.candidates.all { it.cpuReply == null && it.gpuReply == null })
    }
    @Test fun completionAndArrivalOrdersDoNotReleaseTheWrongRequest() {
        for (arrivalFirst in listOf(true, false)) {
            var t = 1L
            val recorder = ArrivalTimingDev.Recorder({ t++ }, budgets, "test", "synthetic")
            recorder.mark("CPU", normal, ArrivalTimingDev.Phase.ASSIGNED)
            recorder.mark("CPU", normal, ArrivalTimingDev.Phase.WORKER_RELEASED) // rejection/failure also releases
            if (arrivalFirst) assertNull(recorder.choose(listOf(urgent)).first.choice)
            recorder.mark("CPU", normal, ArrivalTimingDev.Phase.AVAILABLE)
            assertEquals(urgent, recorder.choose(listOf(urgent)).first.choice?.ticket)
            recorder.mark("CPU", urgent, ArrivalTimingDev.Phase.ASSIGNED)
            assertThrows(IllegalStateException::class.java) { recorder.mark("CPU", normal, ArrivalTimingDev.Phase.AVAILABLE) }
        }
    }
    @Suppress("UNCHECKED_CAST")
    @Test fun recordedInputsReplayDecisionWithoutActualFutureOutcome() {
        var t = 1L
        val recorder = ArrivalTimingDev.Recorder({ t++ }, budgets, "test", "synthetic")
        val observed = recorder.choose(listOf(normal, urgent)).first
        val snapshot = ((recorder.artifact(false)["records"] as List<Map<String, Any?>>).single())
        val queue = (snapshot["queue"] as List<Map<String, Any>>).map {
            ArrivalPolicy.Ticket(it["id"] as String, it["task"] as String, it["priority"] as String, it["ordinal"] as Int)
        }
        val lanes = (snapshot["lanes"] as Map<String, Map<String, Any?>>).mapValues { (backend, v) ->
            ArrivalTimingDev.Lane(backend, ArrivalTimingDev.Phase.valueOf(v["phase"] as String), v["request_id"] as String?,
                v["task"] as String?, v["phase_since_ns"] as Long, v["persist_since_ns"] as Long?)
        }
        recorder.mark("CPU", urgent, ArrivalTimingDev.Phase.ASSIGNED)
        t = 1000 // later facts do not mutate the earlier snapshot
        recorder.mark("CPU", urgent, ArrivalTimingDev.Phase.WORKER_RELEASED)
        val replay = ArrivalTimingDev.decide(queue, lanes, snapshot["mono_ns"] as Long, budgets)
        assertEquals(observed, replay)
        assertFalse(snapshot.containsKey("actual_completion_ns"))
        assertEquals("AVAILABLE", (snapshot["lanes"] as Map<String, Map<String, Any?>>).getValue("CPU")["phase"])
    }
    @Test fun recordingOverflowStopsUnloggedDispatchAndInvalidatesReceipt() {
        val recorder = ArrivalTimingDev.Recorder({ 1L }, budgets, "test", "synthetic", 1)
        recorder.choose(emptyList())
        assertNull(recorder.choose(listOf(urgent)).first.choice)
        assertTrue(recorder.overflow)
        assertEquals(false, recorder.artifact(true)["complete"])
        assertEquals(1, recorder.artifact(true)["dropped_records"])
    }
    @Test fun remainingBudgetIncludesPersistenceAndRelease() {
        val partial = budget.copy(release = null)
        assertNull(ArrivalTimingDev.remaining(lane(ArrivalTimingDev.Phase.EXECUTING, 1), 10, partial).ns)
        assertEquals("UNKNOWN_MISSING_BUDGET", ArrivalTimingDev.remaining(lane(ArrivalTimingDev.Phase.EXECUTING, 1), 10, partial).state)
    }
    @Test fun responseForecastIncludesDecisionPreparationAndNormalPersistence() {
        val lanes = mapOf("CPU" to ArrivalTimingDev.Lane("CPU"), "GPU" to ArrivalTimingDev.Lane("GPU"))
        val result = ArrivalTimingDev.decide(listOf(normal, urgent), lanes, 1, budgets)
        assertEquals(142L, result.candidates[0].cpuReply)
        assertEquals(292L, result.candidates[0].gpuReply)
        // Ahead urgent occupies decision+preparation+service+persist+release = 157 ns.
        assertEquals(309L, result.candidates[1].cpuReply)
        val unknownCost = budgets + ("classification_CPU" to budget.copy(decisionToDispatch = null))
        assertEquals("fallback_cpu_unknown", ArrivalTimingDev.decide(listOf(urgent), lanes, 1, unknownCost).reason)
    }
    @Suppress("UNCHECKED_CAST")
    @Test fun newAssignmentDoesNotInheritOldPersistenceOrigin() {
        var time = 1L
        val recorder = ArrivalTimingDev.Recorder({ time++ }, budgets, "test", "synthetic")
        recorder.mark("CPU", normal, ArrivalTimingDev.Phase.ASSIGNED)
        recorder.mark("CPU", normal, ArrivalTimingDev.Phase.EXECUTING)
        recorder.mark("CPU", normal, ArrivalTimingDev.Phase.OUTPUT_READY)
        recorder.mark("CPU", normal, ArrivalTimingDev.Phase.PERSISTED)
        recorder.mark("CPU", normal, ArrivalTimingDev.Phase.WORKER_RELEASED)
        recorder.mark("CPU", normal, ArrivalTimingDev.Phase.AVAILABLE)
        recorder.mark("CPU", urgent, ArrivalTimingDev.Phase.ASSIGNED)
        recorder.choose(emptyList())
        val last = (recorder.artifact(false)["records"] as List<Map<String, Any?>>).last()
        val cpu = (last["lanes"] as Map<String, Map<String, Any?>>).getValue("CPU")
        assertNull(cpu["persist_since_ns"])
        assertEquals("u", cpu["request_id"])
    }
    @Test fun legacyPolicyStillUsesItsOwnRulesAndRejectsNewId() {
        val old = mapOf("classification_CPU" to 97L, "classification_GPU" to 250L,
            "detection_CPU" to 558L, "detection_GPU" to 1063L)
        assertNull(ArrivalPolicy.choose(ArrivalPolicy.CONDITIONAL, listOf(urgent), false, true, 0, old))
        assertThrows(IllegalArgumentException::class.java) {
            ArrivalPolicy.choose(ArrivalTimingDev.POLICY, listOf(urgent), true, true, 0, old)
        }
    }
    @Test fun invocationBoundsExcludeObserverAndCoverExceptionalReturn() {
        for (fails in listOf(false, true)) {
            var time = 10L
            var observed: Pair<Long, Long>? = null
            val observer: (Long, Long) -> Unit = { start, end -> observed = Pair(start, end); time += 90 }
            val invoke = { time += 20; if (fails) error("synthetic failure") }
            if (fails) assertThrows(IllegalStateException::class.java) {
                ArrivalTimingDev.observeInvocation({ time }, observer, invoke)
            } else assertEquals(Pair(10L, 30L), ArrivalTimingDev.observeInvocation({ time }, observer, invoke))
            assertEquals(Pair(10L, 30L), observed)
            assertEquals(120L, time)
        }
    }
}
