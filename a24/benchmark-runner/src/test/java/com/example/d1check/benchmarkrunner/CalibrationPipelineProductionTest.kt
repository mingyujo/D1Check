package com.example.d1check.benchmarkrunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.UUID

class CalibrationPipelineProductionTest {
    @get:Rule
    val temporary = TemporaryFolder()

    @Test
    fun productionPipelineExecutesActualDecodePreprocessUrgentAndDurableNormalBoundaries() {
        val fixture = Fixture(queueCapacity = 4)
        val urgent = fixture.request(CalibrationRequestType.URGENT)
        var outputReadyCalls = 0
        var urgentResult: CalibrationRequestResult? = null
        assertTrue(fixture.pipeline.submit(
            urgent,
            CalibrationOutputConsumer { request, output ->
                assertEquals(urgent.requestId, request.requestId)
                assertEquals(5, output.topIndices.size)
                outputReadyCalls++
            },
        ) { urgentResult = it }.accepted)
        assertTrue(fixture.pipeline.drainOne())

        val completedUrgent = checkNotNull(urgentResult)
        assertEquals(CalibrationTerminalStatus.SUCCEEDED, completedUrgent.terminalStatus)
        assertEquals(1, outputReadyCalls)
        assertNotNull(completedUrgent.timestamps.imageReadStartNs)
        assertNotNull(completedUrgent.timestamps.decodeStartNs)
        assertNotNull(completedUrgent.timestamps.preprocessingStartNs)
        assertNotNull(completedUrgent.timestamps.outputReadyNs)
        assertTrue(checkNotNull(completedUrgent.queueWaitNs) > 0L)
        assertTrue(checkNotNull(completedUrgent.endToEndNs) > checkNotNull(completedUrgent.queueWaitNs))
        assertEquals(fixture.inputTensorHash, completedUrgent.inputTensorSha256)

        val normal = fixture.request(CalibrationRequestType.NORMAL)
        var normalResult: CalibrationRequestResult? = null
        fixture.pipeline.submit(normal, completed = { normalResult = it })
        fixture.pipeline.drainOne()
        val completedNormal = checkNotNull(normalResult)
        assertEquals(CalibrationTerminalStatus.SUCCEEDED, completedNormal.terminalStatus)
        assertNotNull(completedNormal.timestamps.persistenceCompletedNs)
        assertEquals(null, completedNormal.timestamps.outputReadyNs)
        val stored = File(fixture.resultsRoot, "${normal.requestId}.json")
        assertTrue(stored.isFile)
        assertTrue(stored.readText().contains(CalibrationContract.DURABILITY))
        assertFalse(File(fixture.resultsRoot, ".${normal.requestId}.part").exists())
        fixture.pipeline.close()
        assertTrue(fixture.runtime.closed)
    }

    @Test
    fun interpreterTimerExcludesDecodePreprocessPostprocessChecksumAndPersistence() {
        val events = mutableListOf<String>()
        val fixture = Fixture(events = events)
        var result: CalibrationRequestResult? = null
        fixture.pipeline.submit(fixture.request(CalibrationRequestType.NORMAL), completed = { result = it })
        fixture.pipeline.drainOne()
        val timestamps = checkNotNull(result).timestamps
        assertTrue(checkNotNull(timestamps.preprocessingEndNs) <= checkNotNull(timestamps.interpreterRunStartNs))
        assertTrue(checkNotNull(timestamps.interpreterRunEndNs) <= checkNotNull(timestamps.postprocessingEndNs))
        assertTrue(checkNotNull(timestamps.postprocessingEndNs) <= checkNotNull(timestamps.persistenceStartNs))
        assertEquals(listOf("read", "decode", "preprocess", "prepare", "run", "postprocess", "persist"), events)
    }

    @Test
    fun queueRejectExpireFailureAndSilentFallbackAreTerminalAndRecorded() {
        val full = Fixture(queueCapacity = 1)
        val accepted = full.pipeline.submit(full.request(CalibrationRequestType.URGENT))
        val rejected = full.pipeline.submit(full.request(CalibrationRequestType.URGENT))
        assertTrue(accepted.accepted)
        assertFalse(rejected.accepted)
        assertEquals(CalibrationTerminalStatus.REJECTED, rejected.terminalStatus)

        val expired = Fixture()
        var expiredResult: CalibrationRequestResult? = null
        val request = expired.request(CalibrationRequestType.URGENT).copy(
            deadlineNs = expired.clock.peek(),
        )
        expired.pipeline.submit(request, completed = { expiredResult = it })
        expired.pipeline.drainOne()
        assertEquals(CalibrationTerminalStatus.EXPIRED, checkNotNull(expiredResult).terminalStatus)
        assertEquals(null, checkNotNull(expiredResult).output)
        assertEquals(null, checkNotNull(expiredResult).persistedRelativePath)

        val invalid = Fixture(imageHashOverride = "0".repeat(64))
        var invalidResult: CalibrationRequestResult? = null
        invalid.pipeline.submit(invalid.request(CalibrationRequestType.URGENT), completed = {
            invalidResult = it
        })
        invalid.pipeline.drainOne()
        assertEquals(CalibrationTerminalStatus.FAILED, checkNotNull(invalidResult).terminalStatus)
        assertEquals(null, checkNotNull(invalidResult).output)
        assertTrue(checkNotNull(invalidResult).error.orEmpty().contains("SHA-256 mismatch"))

        val fallback = Fixture(fallbackStatus = CalibrationFallbackStatus.DETECTED)
        var fallbackResult: CalibrationRequestResult? = null
        fallback.pipeline.submit(fallback.request(CalibrationRequestType.URGENT), completed = {
            fallbackResult = it
        })
        fallback.pipeline.drainOne()
        assertEquals(CalibrationTerminalStatus.FAILED, checkNotNull(fallbackResult).terminalStatus)
        assertTrue(checkNotNull(fallbackResult).error.orEmpty().contains("fallback"))
    }

    @Test
    fun completedUrgentAndNormalRequestsSeparateTerminalStatusFromDeadlineOutcome() {
        fun run(type: CalibrationRequestType, deadlineDeltaNs: Long): CalibrationRequestResult {
            val fixture = Fixture()
            var result: CalibrationRequestResult? = null
            val request = fixture.request(type, deadlineNs = fixture.clock.peek() + deadlineDeltaNs)
            fixture.pipeline.submit(request, completed = { result = it })
            fixture.pipeline.drainOne()
            return checkNotNull(result)
        }

        val urgentOnTime = run(CalibrationRequestType.URGENT, 100_000L)
        assertEquals(CalibrationTerminalStatus.SUCCEEDED, urgentOnTime.terminalStatus)
        assertEquals(CalibrationDeadlineOutcome.ON_TIME, urgentOnTime.deadlineOutcome)
        assertEquals(true, urgentOnTime.deadlineMet)

        val urgentLate = run(CalibrationRequestType.URGENT, 5_000L)
        assertEquals(CalibrationTerminalStatus.SUCCEEDED, urgentLate.terminalStatus)
        assertEquals(CalibrationDeadlineOutcome.LATE, urgentLate.deadlineOutcome)
        assertEquals(false, urgentLate.deadlineMet)

        val normalOnTime = run(CalibrationRequestType.NORMAL, 100_000L)
        assertEquals(CalibrationTerminalStatus.SUCCEEDED, normalOnTime.terminalStatus)
        assertEquals(CalibrationDeadlineOutcome.ON_TIME, normalOnTime.deadlineOutcome)
        assertNotNull(normalOnTime.persistedRelativePath)

        val normalLate = run(CalibrationRequestType.NORMAL, 5_000L)
        assertEquals(CalibrationTerminalStatus.SUCCEEDED, normalLate.terminalStatus)
        assertEquals(CalibrationDeadlineOutcome.LATE, normalLate.deadlineOutcome)
        assertNotNull(normalLate.persistedRelativePath)
    }

    @Test
    fun failureAfterDurableWriteRollsBackResultBeforeFailedTelemetry() {
        val fixture = Fixture(clockFailureAt = 18)
        val request = fixture.request(CalibrationRequestType.NORMAL)
        var result: CalibrationRequestResult? = null
        fixture.pipeline.submit(request, completed = { result = it })
        fixture.pipeline.drainOne()
        val failed = checkNotNull(result)
        assertEquals(CalibrationTerminalStatus.FAILED, failed.terminalStatus)
        assertEquals(null, failed.output)
        assertEquals(null, failed.persistedRelativePath)
        assertFalse(File(fixture.resultsRoot, "${request.requestId}.json").exists())
    }

    @Test
    fun coldWarmAndBidirectionalBackendSwitchAreObservedByProductionPipeline() {
        val fixture = Fixture(mode = CalibrationMode.TRANSITION_PROBE)
        val results = mutableListOf<CalibrationRequestResult>()
        fun run(backend: CalibrationBackend, warmup: Boolean = false) {
            fixture.pipeline.submit(
                fixture.request(CalibrationRequestType.URGENT, backend, warmup),
                completed = results::add,
            )
            fixture.pipeline.drainOne()
        }
        run(CalibrationBackend.CPU)
        run(CalibrationBackend.CPU, warmup = true)
        run(CalibrationBackend.CPU)
        run(CalibrationBackend.GPU)
        run(CalibrationBackend.CPU)
        assertEquals(CalibrationThermalClass.COLD, results[0].executionClass)
        assertEquals(CalibrationThermalClass.WARMUP, results[1].executionClass)
        assertEquals(CalibrationThermalClass.WARM, results[2].executionClass)
        assertEquals("CPU->GPU", results[3].transition)
        assertEquals("GPU->CPU", results[4].transition)
        assertEquals(results.map { it.request.requestedBackend }, results.map { it.actualBackend })
    }

    private inner class Fixture(
        queueCapacity: Int = 8,
        mode: CalibrationMode = CalibrationMode.FIXED,
        events: MutableList<String> = mutableListOf(),
        fallbackStatus: CalibrationFallbackStatus = CalibrationFallbackStatus.NOT_APPLICABLE,
        imageHashOverride: String? = null,
        clockFailureAt: Int? = null,
    ) {
        val clock = StepClock(clockFailureAt)
        private val png = "explicit-test-fixture-not-representative-data".toByteArray()
        private val imageSpec = CalibrationImageSpec(
            "fixture", "images/fixture.png",
            imageHashOverride ?: CalibrationContract.sha256(png), png.size.toLong(),
            0, "fixture-label", 8, 8, 1, 8, 8, "image/png",
        )
        private val manifest = manifest(imageSpec, queueCapacity, mode)
        val runtime = FakeRuntime(fallbackStatus, events)
        private val pool = FakePool(runtime, events)
        val resultsRoot: File = temporary.newFolder(UUID.randomUUID().toString())
        var inputTensorHash: String? = null
        val pipeline = CalibrationPipeline(
            manifest,
            clock,
            object : CalibrationImageReader {
                override fun read(uri: String): CalibrationImageBytes {
                    events += "read"
                    return CalibrationImageBytes(
                        png, CalibrationContract.sha256(png), "image/png", png.size.toLong(), 1
                    )
                }
            },
            object : CalibrationImageDecoder {
                override fun decode(image: CalibrationImageBytes): CalibrationDecodedImage {
                    events += "decode"
                    return object : CalibrationDecodedImage {
                        override val rawWidth = 8
                        override val rawHeight = 8
                        override val exifOrientation = 1
                        override val width = 8
                        override val height = 8
                        override fun close() = Unit
                    }
                }
            },
            CalibrationPreprocessor {
                events += "preprocess"
                val buffer = ByteBuffer.allocateDirect(16).order(ByteOrder.nativeOrder())
                repeat(4) { buffer.putFloat(it.toFloat()) }
                val bytes = ByteArray(16)
                buffer.duplicate().apply { flip() }.get(bytes)
                buffer.rewind()
                CalibrationInputTensor(buffer, CalibrationContract.sha256(bytes)).also { tensor ->
                    inputTensorHash = tensor.sha256
                }
            },
            pool,
            CalibrationPostprocessor { output ->
                events += "postprocess"
                val bytes = ByteBuffer.allocate(output.size * 4).order(ByteOrder.nativeOrder())
                output.forEach(bytes::putFloat)
                ClassificationOutput(
                    listOf(1000, 999, 998, 997, 996),
                    listOf("1000", "999", "998", "997", "996"),
                    CalibrationContract.sha256(bytes.array()),
                    output.count { !it.isFinite() },
                )
            },
            CalibrationResultStore { request, output ->
                events += "persist"
                val file = File(resultsRoot, "${request.requestId}.json")
                file.writeText("${CalibrationContract.DURABILITY}:${output.outputSha256}")
                CalibrationPersistenceReceipt("results/${file.name}") {
                    check(!file.exists() || file.delete())
                }
            },
            CalibrationResultRecorder { },
        )

        fun request(
            type: CalibrationRequestType,
            backend: CalibrationBackend = CalibrationBackend.CPU,
            warmup: Boolean = false,
            deadlineNs: Long? = null,
        ): CalibrationRequest {
            val accepted = clock.monotonicNanos()
            return CalibrationRequest(
                UUID.randomUUID().toString(), type, imageSpec, "test-fixture://image",
                backend, if (type == CalibrationRequestType.URGENT) accepted else null,
                accepted, deadlineNs, warmup,
            )
        }
    }

    private class StepClock(
        private val failureAt: Int? = null,
    ) : CalibrationClock {
        private var value = 1_000_000L
        private var calls = 0
        override fun monotonicNanos(): Long {
            calls++
            if (calls == failureAt) error("clock fixture failure")
            return value.also { value += 1_000L }
        }
        fun peek(): Long = value
    }

    private class FakeRuntime(
        override val fallbackStatus: CalibrationFallbackStatus,
        private val events: MutableList<String>,
    ) : CalibrationBackendRuntime {
        override var actualBackend = CalibrationBackend.CPU
        var closed = false
        override fun run(input: ByteBuffer, clock: CalibrationClock): CalibrationRawOutput {
            events += "run"
            val start = clock.monotonicNanos()
            val output = FloatArray(1001) { it.toFloat() }
            val end = clock.monotonicNanos()
            return CalibrationRawOutput(output, start, end)
        }
        override fun close() { closed = true }
    }

    private class FakePool(
        private val runtime: FakeRuntime,
        private val events: MutableList<String>,
    ) : CalibrationRuntimePool {
        private val seen = mutableSetOf<CalibrationBackend>()
        private var previous: CalibrationBackend? = null
        override fun prepare(backend: CalibrationBackend): PreparedCalibrationBackend {
            events += "prepare"
            runtime.actualBackend = backend
            val transition = previous?.takeIf { it != backend }?.let { "${it.wireName}->${backend.wireName}" }
            previous = backend
            return PreparedCalibrationBackend(runtime, seen.add(backend), transition)
        }
        override fun close() = runtime.close()
    }

    private fun manifest(
        image: CalibrationImageSpec,
        queueCapacity: Int,
        mode: CalibrationMode,
    ) = CalibrationInputManifest(
        UUID.randomUUID().toString(), CalibrationSessionMode.BASELINE_PILOT, mode,
        if (mode == CalibrationMode.FIXED) CalibrationBackend.CPU else null,
        1, queueCapacity, 0,
        ModelLoader.MODEL_SHA256.lowercase(), "1".repeat(64),
        MobileNetCalibrationPreprocessor.configurationSha256,
        MobileNetCalibrationPreprocessor.CONTRACT_ID, "2".repeat(64), null,
        CalibrationEnvironmentPlan("test", null, false, true),
        listOf(image), "3".repeat(64),
    )

}
