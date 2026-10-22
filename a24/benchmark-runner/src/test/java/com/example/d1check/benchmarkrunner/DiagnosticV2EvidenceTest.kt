package com.example.d1check.benchmarkrunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder

class DiagnosticV2EvidenceTest {
    @Test
    fun procStatParserHandlesThreadNameCpuTicksAndLastCpu() {
        val fields = MutableList(37) { "0" }
        fields[0] = "R" // field 3
        fields[11] = "100" // utime, field 14
        fields[12] = "25" // stime, field 15
        fields[36] = "6" // processor, field 39
        val sample = ProcTaskStatParser.parse(
            123,
            "123 (XNNPACK worker 0) ${fields.joinToString(" ")}",
        )

        assertEquals("XNNPACK worker 0", sample.name)
        assertEquals(125L, sample.cpuTimeTicks)
        assertEquals(6, sample.lastCpu)
    }

    @Test
    fun procStatParserHandlesNestedParenthesesAndSpacesInComm() {
        val fields = MutableList(37) { "0" }
        fields[0] = "S"
        fields[11] = "7"
        fields[12] = "8"
        fields[36] = "2"
        val sample = ProcTaskStatParser.parse(
            44,
            "44 (worker (pool) 1) ${fields.joinToString(" ")}",
        )

        assertEquals("worker (pool) 1", sample.name)
        assertEquals(15L, sample.cpuTimeTicks)
    }

    @Test
    fun threadDeltasDoNotGuessWorkerIdentityAndConvertTicks() {
        val before = ProcessThreadSnapshot(
            "ok", 1, 10, 100,
            listOf(ProcessThreadSample(7, "worker", 20, 2)), emptyList(),
        )
        val after = ProcessThreadSnapshot(
            "ok", 1, 20, 100,
            listOf(
                ProcessThreadSample(7, "worker", 45, 3),
                ProcessThreadSample(8, "new", 5, null),
            ), emptyList(),
        )

        val deltas = ProcTaskStatParser.deltas(before, after)
        assertEquals(25L, deltas[0]["cpu_time_delta_ticks"])
        assertEquals(250_000_000L, deltas[0]["cpu_time_delta_ns"])
        assertEquals(false, deltas[1]["present_before_load"])
        assertNull(deltas[1]["cpu_time_delta_ticks"])
    }

    @Test
    fun threadComparisonTreatsNameChangeAsPossibleTidReuse() {
        val before = ProcessThreadSnapshot(
            "partial", 1, 10, 100,
            listOf(ProcessThreadSample(7, "old worker", 20, 2)), listOf("tid=8 denied"), 2, 1,
        )
        val after = ProcessThreadSnapshot(
            "ok", 1, 20, 100,
            listOf(ProcessThreadSample(7, "new worker", 45, 3)), emptyList(), 1, 0,
        )

        val comparison = ProcTaskStatParser.comparison(before, after)
        val delta = (comparison["deltas"] as List<*>).single() as Map<*, *>
        assertEquals("incomplete", comparison["evidence_completeness"])
        assertEquals(true, delta["possible_tid_reuse"])
        assertNull(delta["cpu_time_delta_ticks"])
        assertEquals(listOf(7), comparison["tid_reuse_candidates"])
        assertEquals("incomplete", before.metadata()["completeness"])
        assertEquals(1, before.metadata()["failed_tid_count"])
    }

    @Test
    fun outputReadbackRunsOnlyAfterProvidedInterpreterEndBoundary() {
        val output = ByteBuffer.allocateDirect(12).order(ByteOrder.nativeOrder())
        output.putFloat(1.0f).putFloat(-2.0f).putFloat(3.0f)
        val times = ArrayDeque(listOf(101L, 105L))

        val evidence = OutputReadbackInspector.inspect(output, 4, 100L, 100L) {
            times.removeFirst()
        }

        assertEquals("passed", evidence.status)
        assertEquals(0, evidence.nonFiniteCount)
        assertEquals(101L, evidence.checkStartMonoNs)
        assertTrue(evidence.metadata()["performed_after_latency_timer"] as Boolean)
        assertTrue(evidence.metadata()["performed_after_load_end"] as Boolean)
        assertEquals(64, evidence.sha256?.length)
        assertEquals(
            "output_readiness_and_integrity_support_only",
            evidence.metadata()["evidence_scope"],
        )
        assertEquals(false, evidence.metadata()["cpu_gpu_accuracy_equivalence_claim"])
    }

    @Test
    fun outputReadbackReportsNonFiniteWithoutChangingBufferPosition() {
        val output = ByteBuffer.allocateDirect(8).order(ByteOrder.nativeOrder())
        output.putFloat(Float.NaN).putFloat(Float.POSITIVE_INFINITY)
        val originalPosition = output.position()
        var now = 10L

        val evidence = OutputReadbackInspector.inspect(output, 0, 9L, 9L) { now++ }

        assertEquals(2, evidence.nonFiniteCount)
        assertEquals("failed", evidence.status)
        assertEquals(true, evidence.metadata()["output_readable_after_run"])
        assertEquals(originalPosition, output.position())
    }

    @Test
    fun postLoadChecksumCannotChangeFrozenLoadMetrics() {
        val tracker = DutyCycleTracker(
            requestedPercent = 50,
            periodNs = 100L,
            startedNs = 0L,
            targetDurationNs = 200L,
        )
        tracker.recordIdle(50L, 100L)
        val frozenBeforeReadback = tracker.metrics(200L)
        val output = ByteBuffer.allocateDirect(8).order(ByteOrder.nativeOrder())
        output.putFloat(1.0f).putFloat(2.0f)
        val times = ArrayDeque(listOf(10_000L, 90_000L))

        OutputReadbackInspector.inspect(output, 9L, 190L, 200L) { times.removeFirst() }

        assertEquals(frozenBeforeReadback, tracker.metrics(200L))
        assertEquals(200L, frozenBeforeReadback.actualActiveDurationNs +
            frozenBeforeReadback.actualIdleDurationNs)
    }

    @Test
    fun postLoadCoordinatorRunsReadbackAfterFrozenMetricsWithoutMutation() {
        val duty = DutyCycleMetrics(
            requestedPercent = 50,
            periodNs = 100L,
            targetActiveDurationNs = 100L,
            actualActiveDurationNs = 100L,
            actualIdleDurationNs = 100L,
            achievedPercent = 50.0,
            completedCycleCount = 2L,
            activeOverrunNs = 0L,
        )
        val frozen = FrozenLoadMetrics(200L, 200L, duty, 10L, 190L)
        val output = ByteBuffer.allocateDirect(8).order(ByteOrder.nativeOrder())
        output.putFloat(1.0f).putFloat(2.0f)
        val times = ArrayDeque(listOf(201L, 205L))

        val result = ProductionPostLoadCoordinator.capture(frozen, output) {
            times.removeFirst()
        }

        assertEquals(frozen, result.frozenMetrics)
        assertEquals(10L, result.frozenMetrics.completedInferenceCount)
        assertEquals(200L, result.frozenMetrics.actualLoadDurationNs)
        assertEquals(duty, result.frozenMetrics.dutyMetrics)
        assertTrue(result.outputReadback.checkStartMonoNs >= frozen.loadEndedMonoNs)
    }

    @Test
    fun officialInferenceCoordinatorPreservesInterpreterBoundaryAndChecksumOrder() {
        val order = mutableListOf<String>()
        val clock = ArrayDeque(listOf(100L, 140L))
        var recorded: List<Long>? = null

        val result = OfficialInferenceCoordinator.execute(
            inferenceIndex = 7L,
            monotonicNanos = {
                order += "clock"
                clock.removeFirst()
            },
            interpreterRun = { order += "interpreter" },
            recordInference = { start, end, index, batch ->
                order += "telemetry"
                recorded = listOf(start, end, index, batch.toLong())
                true
            },
        )

        assertEquals(listOf("clock", "interpreter", "clock", "telemetry"), order)
        assertEquals(100L, result.startedMonoNs)
        assertEquals(140L, result.endedMonoNs)
        assertEquals(listOf(100L, 140L, 7L, 1L), recorded)

        val output = ByteBuffer.allocateDirect(4).order(ByteOrder.nativeOrder())
        output.putFloat(1.0f)
        val frozen = FrozenLoadMetrics(150L, 50L, null, 8L, result.endedMonoNs)
        val postLoadClock = ArrayDeque(listOf(151L, 152L))
        val postLoad = ProductionPostLoadCoordinator.capture(
            frozen, output, { postLoadClock.removeFirst() }
        )
        assertEquals(frozen, postLoad.frozenMetrics)
        assertTrue(postLoad.outputReadback.checkStartMonoNs > result.endedMonoNs)
    }

    @Test
    fun delegateCleanupStillRunsWhenInterpreterCleanupFails() {
        val calls = mutableListOf<String>()
        try {
            IndependentResourceCleanup.close(
                {
                    calls += "interpreter"
                    throw IllegalStateException("interpreter close failed")
                },
                { calls += "delegate" },
            )
            throw AssertionError("cleanup failure was not propagated")
        } catch (_: IllegalStateException) {
            assertEquals(listOf("interpreter", "delegate"), calls)
        }
    }
}
