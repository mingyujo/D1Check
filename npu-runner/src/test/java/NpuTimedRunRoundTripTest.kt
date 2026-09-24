package com.example.d1check.npurunner

import android.content.ContentProvider
import android.content.ContentValues
import android.database.Cursor
import android.database.MatrixCursor
import android.net.Uri
import android.os.SystemClock
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowSystemClock
import java.io.File
import java.io.FileInputStream
import java.time.Duration

/**
 * 기기↔호스트 계약 라운드트립 (폰 없이).
 *
 * npu-runner 의 실제 NpuTimedRunEngine + telemetry-contract 의 실제 GpuTelemetry 직렬화로 timed run 을
 * 돌리고, 나온 JSONL 을 build/npu-roundtrip/<case>/ 에 떨군다. 호스트 쪽 검사는
 * tools/test_npu_runner_roundtrip.py 가 그 파일을 d1_logger_v4.analyze → validate_result(formal) 에 넣는다.
 *
 * NPU 대신 가짜 백엔드가 Robolectric 시계만 진행시킨다. 모델·dispatch SHA 와 AOT 파티션은 레포의
 * 실제 파일에서 계산한다 (그래서 formal_npu_valid 4·5번이 실값으로 판정된다).
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class NpuTimedRunRoundTripTest {

    class FakeRunProvider : ContentProvider() {
        override fun onCreate() = true
        override fun query(
            uri: Uri, projection: Array<out String>?, selection: String?,
            selectionArgs: Array<out String>?, sortOrder: String?,
        ): Cursor = MatrixCursor(
            arrayOf("run_id", "active", "started_elapsed_ns", "started_wall_ms", "boot_id")
        ).apply { addRow(arrayOf<Any>(runId, 1, startedElapsedNs, 1_790_000_000_000L, "boot-fixture")) }

        override fun getType(uri: Uri): String? = null
        override fun insert(uri: Uri, values: ContentValues?): Uri? = null
        override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?) = 0
        override fun update(
            uri: Uri, values: ContentValues?, selection: String?, selectionArgs: Array<out String>?,
        ) = 0

        companion object {
            var runId = ""
            var startedElapsedNs = 0L
        }
    }

    private class FakeBackend(private val latencyNs: Long) : NpuTimedBackend {
        var closed = false
        override fun init() = NpuBackendInit(4_806_000L, 10_930_000L, 270_000L, "NPU,GPU,CPU")
        override fun inputElementCount() = 224 * 224 * 3
        override fun infer(input: FloatArray) {
            ShadowSystemClock.advanceBy(Duration.ofNanos(latencyNs))
        }
        override fun close() {
            closed = true
        }
    }

    private val moduleDir = File(".").absoluteFile
    private val modelFile = File(moduleDir, "src/main/assets/models/mobilenet_v1_1.0_224_Samsung_E9965.tflite")
    private val dispatchFile = File(moduleDir, "src/main/jniLibs/arm64-v8a/libLiteRtDispatch_Samsung.so")
    private val manifestFile = File(moduleDir, "src/main/assets/models/aot_manifest.json")
    private val outRoot = File(moduleDir, "build/npu-roundtrip")

    @Before
    fun registerRunProvider() {
        Robolectric.setupContentProvider(FakeRunProvider::class.java, "com.example.d1check.run")
    }

    private fun realArtifacts(): NpuArtifacts {
        val modelSha = FileInputStream(modelFile).use(NpuArtifacts::sha256)
        return NpuArtifacts(
            modelId = NpuArtifacts.modelIdOf(modelFile.name),
            modelSha256 = modelSha,
            dispatchLibSha256 = FileInputStream(dispatchFile).use(NpuArtifacts::sha256),
            aotPartition = NpuArtifacts.aotPartitionFor(manifestFile.readText(), modelSha),
        )
    }

    private fun runCase(
        case: String,
        runId: String,
        commandId: String,
        dutyPercent: Int,
        periodSeconds: Double,
        safety: PilotSafetyCheck,
        expectValid: Boolean,
    ): NpuTimedRunResult {
        FakeRunProvider.runId = runId
        FakeRunProvider.startedElapsedNs = SystemClock.elapsedRealtimeNanos()
        ShadowSystemClock.advanceBy(Duration.ofMillis(1))
        val backend = FakeBackend(latencyNs = 2_000_000L)
        val config = NpuRunConfig(
            limit = RunLimit.Duration(DURATION_S),
            warmupCount = WARMUP,
            experimentMode = ExperimentMode.BASIC,
            expectedRunId = runId,
            commandId = commandId,
            dutyCyclePercent = dutyPercent,
            dutyCyclePeriodSeconds = periodSeconds,
        )
        val engine = NpuTimedRunEngine(
            context = RuntimeEnvironment.getApplication(),
            backendFactory = { backend },
            baselineMs = 0L,
            idle = { nanos -> ShadowSystemClock.advanceBy(Duration.ofNanos(nanos)) },
            safety = { safety },
            artifacts = { realArtifacts() },
        )
        var result: NpuTimedRunResult? = null
        var failure: Throwable? = null
        val thread = Thread({
            try {
                result = engine.execute(config)
            } catch (error: Throwable) {
                failure = error
            }
        }, NpuTimedRunEngine.THREAD_NAME)
        thread.start()
        thread.join()
        failure?.let { throw it }
        val done = checkNotNull(result)
        assertEquals(done.message, expectValid, done.success)
        if (expectValid) assertTrue(backend.closed)

        // 호스트 테스트가 읽을 자리에 떨군다 (고정 이름으로 덮어쓴다)
        val file = checkNotNull(done.flushResult).file
        val caseDir = File(outRoot, case).apply { mkdirs() }
        file.copyTo(File(caseDir, "runner.jsonl"), overwrite = true)
        File(caseDir, "roundtrip.json").writeText(
            JSONObject()
                .put("case", case)
                .put("run_id", runId)
                .put("command_id", commandId)
                .put("runner_session_id", done.flushResult.runnerSessionId)
                .put("runner_file_name", file.name)
                .put("duration_s", DURATION_S)
                .put("warmup", WARMUP)
                .put("duty_cycle_percent", dutyPercent)
                .put("duty_cycle_period_s", periodSeconds)
                .put("expect_valid", expectValid)
                .toString(2)
        )
        return done
    }

    private fun records(result: NpuTimedRunResult): List<JSONObject> =
        checkNotNull(result.flushResult).file.readLines().map { JSONObject(it) }

    @Test
    fun continuousLoadProducesAHostReadableFile() {
        val result = runCase(
            "npu-d100", "aaaaaaaa-1111-4111-8111-111111111111", "bbbbbbbb-2222-4222-8222-222222222222",
            100, 10.0, PASSING_SAFETY, expectValid = true,
        )
        val records = records(result)
        val metadata = records.first()
        val footer = records.last()
        assertEquals("run_metadata", metadata.getString("event"))
        assertEquals("NPU", metadata.getString("resource"))
        assertEquals(MOBILENET_AOT_SHA, metadata.getString("model_sha256"))
        assertEquals(DISPATCH_SHA, metadata.getString("npu_dispatch_lib_sha256"))
        assertEquals("2.2.0", metadata.getString("litert_version"))
        assertEquals("duration_complete", metadata.getString("termination_reason"))
        assertTrue(metadata.getBoolean("experiment_valid"))
        assertEquals(1, metadata.getJSONObject("npu_model_partition").getInt("dispatch_ops"))
        assertEquals(0L, metadata.getLong("actual_idle_duration_ns"))
        assertEquals("file_summary", footer.getString("event"))
        assertEquals(records.size, footer.getInt("file_event_count"))
        assertEquals((records.indices).toList(), records.map { it.getInt("sequence") })
        val inferences = records.count { it.getString("event") == "inference" }
        assertEquals(metadata.getInt("completed_inference_count"), inferences)
        assertTrue(inferences > 0)
        assertEquals(WARMUP, records.count { it.getString("event") == "warmup" })
    }

    @Test
    fun halfDutyRecordsIdleTime() {
        val result = runCase(
            "npu-d050", "cccccccc-3333-4333-8333-333333333333", "dddddddd-4444-4444-8444-444444444444",
            50, 0.5, PASSING_SAFETY, expectValid = true,
        )
        val metadata = records(result).first()
        val idle = metadata.getLong("actual_idle_duration_ns")
        val active = metadata.getLong("actual_active_duration_ns")
        assertTrue(idle > 0L)
        assertEquals(metadata.getLong("actual_load_duration_ns"), idle + active)
    }

    @Test
    fun pluggedDeviceIsRejectedBeforeLoad() {
        val plugged = PilotSafetyPolicy.evaluate(PilotSafetySnapshot(0, 2, 2, 90, 30.0))
        val result = runCase(
            "npu-plugged", "eeeeeeee-5555-4555-8555-555555555555", "ffffffff-6666-4666-8666-666666666666",
            100, 10.0, plugged, expectValid = false,
        )
        val records = records(result)
        val metadata = records.first()
        assertFalse(metadata.getBoolean("experiment_valid"))
        assertEquals("pilot_safety_rejected", metadata.getString("termination_reason"))
        assertTrue(records.any { it.getString("event") == "pilot_safety_rejected" })
        assertEquals(0, records.count { it.getString("event") == "inference" })
    }

    companion object {
        const val DURATION_S = 2L
        const val WARMUP = 3
        const val MOBILENET_AOT_SHA = "1415b2c87d01b67a9380b8f912e2b4ef4561502105b06f313332c97c1c8cb5cf"
        const val DISPATCH_SHA = "f08656a642c46e7b06b64fbe1e0800de9e73b0b69c1641b87995562b4a16840f"
        internal val PASSING_SAFETY: PilotSafetyCheck =
            PilotSafetyPolicy.evaluate(PilotSafetySnapshot(0, 0, 3, 80, 30.0))
    }
}
