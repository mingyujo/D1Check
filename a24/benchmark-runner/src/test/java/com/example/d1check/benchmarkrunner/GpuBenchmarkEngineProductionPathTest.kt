package com.example.d1check.benchmarkrunner

import com.example.d1check.contract.GpuFlushResult
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.atomic.AtomicReference

class GpuBenchmarkEngineProductionPathTest {
    @Test
    fun executeRunsOfficialLoopFreezesMetricsThenChecksOutputAndCleansResources() {
        val fixture = EngineFixture(normalClock())

        val result = execute(fixture)

        assertTrue(result.success)
        assertEquals(1, fixture.runtime.inferenceCalls)
        assertEquals(listOf(110L, 140L, 0L, 1L), fixture.telemetry.recordedInference)
        val frozen = checkNotNull(fixture.frozenAtPostLoad)
        assertEquals(1L, frozen.completedInferenceCount)
        assertEquals(1_000_000_020L, frozen.actualLoadDurationNs)
        assertNotNull(frozen.dutyMetrics)
        assertEquals(frozen, fixture.frozenAfterChecksum)
        assertNotNull(fixture.postLoadResult?.outputReadback?.sha256)
        assertTrue(fixture.order.indexOf("inference_recorded") < fixture.order.indexOf("load_end"))
        assertTrue(fixture.order.indexOf("load_end") < fixture.order.indexOf("post_load_checksum"))
        assertTrue(fixture.order.indexOf("post_load_checksum") < fixture.order.indexOf("interpreter_close"))
        assertTrue(fixture.runtime.interpreterClosed)
        assertTrue(fixture.runtime.delegateClosed)
        assertEquals(1_000_000_020L, fixture.telemetry.flushedConfig["actual_load_duration_ns"])
        assertEquals(1, fixture.telemetry.flushedConfig["completed_inference_count"])
        assertEquals(
            frozen.dutyMetrics?.actualActiveDurationNs,
            fixture.telemetry.flushedConfig["actual_active_duration_ns"],
        )
        assertEquals(
            frozen.dutyMetrics?.actualIdleDurationNs,
            fixture.telemetry.flushedConfig["actual_idle_duration_ns"],
        )
    }

    @Test
    fun executeInferenceFailureStillRunsActualFinallyCleanup() {
        val fixture = EngineFixture(
            ArrayDeque(listOf(10L, 100L, 101L, 110L, 120L)),
            inferenceFailure = IllegalStateException("inference failed"),
        )

        val result = execute(fixture)

        assertFalse(result.success)
        assertEquals(1, fixture.runtime.inferenceCalls)
        assertTrue(fixture.runtime.interpreterClosed)
        assertTrue(fixture.runtime.delegateClosed)
        assertFalse(fixture.order.contains("post_load_checksum"))
    }

    @Test
    fun executePostLoadFailureStillRunsActualFinallyCleanup() {
        val fixture = EngineFixture(normalClock(), failPostLoad = true)

        val result = execute(fixture)

        assertFalse(result.success)
        assertEquals(1, fixture.runtime.inferenceCalls)
        assertTrue(fixture.order.contains("post_load_checksum"))
        assertTrue(fixture.runtime.interpreterClosed)
        assertTrue(fixture.runtime.delegateClosed)
    }

    @Test
    fun executeDelegateCleanupRunsWhenInterpreterCloseFails() {
        val fixture = EngineFixture(normalClock(), failInterpreterClose = true)

        val result = execute(fixture)

        assertFalse(result.success)
        assertTrue(fixture.runtime.interpreterClosed)
        assertTrue(fixture.runtime.delegateClosed)
        assertEquals(
            listOf("interpreter_close", "delegate_close"),
            fixture.order.filter { it.endsWith("_close") },
        )
    }

    private fun execute(fixture: EngineFixture): BenchmarkResult {
        val result = AtomicReference<BenchmarkResult>()
        val failure = AtomicReference<Throwable>()
        val thread = Thread({
            try {
                result.set(GpuBenchmarkEngine(fixture).execute(diagnosticConfig()))
            } catch (error: Throwable) {
                failure.set(error)
            }
        }, GpuBenchmarkEngine.THREAD_NAME)
        thread.start()
        thread.join(5_000)
        assertFalse("engine execution did not terminate", thread.isAlive)
        failure.get()?.let { throw AssertionError("engine execution escaped", it) }
        return checkNotNull(result.get())
    }

    private fun diagnosticConfig() = RunConfig(
        resource = ResourceTarget.GPU,
        limit = RunLimit.Duration(1),
        warmupCount = 0,
        experimentMode = ExperimentMode.DIAGNOSTIC,
        expectedRunId = RUN_ID,
        commandId = COMMAND_ID,
        dutyCyclePercent = 50,
        dutyCyclePeriodSeconds = 1.0,
        protocolVersion = ProtocolVersion.DIAGNOSTIC_V2,
        diagnosticSessionId = DIAGNOSTIC_ID,
        diagnosticTraceMode = DiagnosticTraceMode.ON,
        diagnosticPerfettoStarted = true,
        diagnosticTraceFilename = "d1check-$DIAGNOSTIC_ID.perfetto-trace",
    )

    private fun normalClock() = ArrayDeque(
        listOf(
            10L,
            100L,
            101L,
            110L,
            140L,
            1_000_000_101L,
            1_000_000_120L,
            1_000_000_130L,
            1_000_000_140L,
            1_000_000_150L,
        )
    )

    private class FakeTelemetry(private val order: MutableList<String>) : BenchmarkEngineTelemetry {
        override val runId = RUN_ID
        override var inferenceCount = 0
        override val hasInferenceCapacity get() = true
        override var lifecycleCount = 0
        override val runnerSessionId = RUNNER_SESSION_ID
        var recordedInference: List<Long>? = null
        var flushedConfig: Map<String, Any?> = emptyMap()

        override fun instant(event: String, phase: String, status: String, detail: String?) {
            lifecycleCount++
            if (event == "load_end") order += "load_end"
        }

        override fun liveInstant(event: String, phase: String, status: String, detail: String?) {
            lifecycleCount++
        }

        override fun <T> measured(
            event: String,
            phase: String,
            index: Long,
            batchSize: Int,
            block: () -> T,
        ): T = block()

        override fun recordInference(
            startNs: Long,
            endNs: Long,
            inferenceIndex: Long,
            batchSize: Int,
        ): Boolean {
            recordedInference = listOf(startNs, endNs, inferenceIndex, batchSize.toLong())
            inferenceCount++
            order += "inference_recorded"
            return true
        }

        override fun flush(
            resource: String,
            modelId: String,
            modelSha256: String,
            config: Map<String, Any?>,
        ): GpuFlushResult? {
            flushedConfig = config.toMap()
            order += "flush"
            return null
        }
    }

    private class FakeRuntime(
        private val order: MutableList<String>,
        private val inferenceFailure: Throwable?,
        private val failInterpreterClose: Boolean,
    ) : BenchmarkEngineRuntime {
        override val input: ByteBuffer = ByteBuffer.allocateDirect(4).order(ByteOrder.nativeOrder())
        override val output: ByteBuffer = ByteBuffer.allocateDirect(4).order(ByteOrder.nativeOrder())
            .apply { putFloat(1.0f) }
        var inferenceCalls = 0
        var interpreterClosed = false
        var delegateClosed = false

        override fun runInference() {
            inferenceCalls++
            order += "interpreter_run"
            inferenceFailure?.let { throw it }
        }

        override fun closeInterpreter() {
            interpreterClosed = true
            order += "interpreter_close"
            if (failInterpreterClose) throw IllegalStateException("interpreter close failed")
        }

        override fun closeDelegate() {
            delegateClosed = true
            order += "delegate_close"
        }
    }

    private class EngineFixture(
        private val clock: ArrayDeque<Long>,
        inferenceFailure: Throwable? = null,
        private val failPostLoad: Boolean = false,
        failInterpreterClose: Boolean = false,
    ) : BenchmarkEngineDependencies {
        val order = mutableListOf<String>()
        val telemetry = FakeTelemetry(order)
        val runtime = FakeRuntime(order, inferenceFailure, failInterpreterClose)
        var frozenAtPostLoad: FrozenLoadMetrics? = null
        var frozenAfterChecksum: FrozenLoadMetrics? = null
        var postLoadResult: DiagnosticPostLoadResult? = null

        override fun connectTelemetry(config: RunConfig): BenchmarkEngineTelemetry = telemetry

        override fun evaluatePilotSafety() = PilotSafetyCheck(
            PilotSafetySnapshot(0, 0, 3, 50, 25.0),
            emptyList(),
        )

        override fun sleepBaseline() = Unit

        override fun createRuntime(
            config: RunConfig,
            telemetry: BenchmarkEngineTelemetry,
        ): BenchmarkEngineRuntime = runtime

        override fun monotonicNanos(): Long = clock.removeFirst()
        override fun parkNanos(nanos: Long) = error("fixture must remain in the active duty window")
        override fun captureThreadSnapshot(monoNs: Long) = ProcessThreadSnapshot(
            "ok", 1, monoNs, 100L, emptyList(), emptyList(), 0, 0,
        )

        override fun revalidate(telemetry: BenchmarkEngineTelemetry, checkpoint: String) = Unit

        override fun capturePostLoad(
            frozenMetrics: FrozenLoadMetrics,
            output: ByteBuffer,
        ): DiagnosticPostLoadResult {
            order += "post_load_checksum"
            frozenAtPostLoad = frozenMetrics
            if (failPostLoad) throw IllegalStateException("post-load failed")
            return ProductionPostLoadCoordinator.capture(
                frozenMetrics,
                output,
                ::monotonicNanos,
            ).also {
                postLoadResult = it
                frozenAfterChecksum = it.frozenMetrics
            }
        }
    }

    companion object {
        private const val RUN_ID = "11111111-1111-1111-1111-111111111111"
        private const val COMMAND_ID = "22222222-2222-2222-2222-222222222222"
        private const val RUNNER_SESSION_ID = "33333333-3333-3333-3333-333333333333"
        private const val DIAGNOSTIC_ID = "44444444-4444-4444-4444-444444444444"
    }
}
