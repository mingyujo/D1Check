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

    private class FakeBackend(
        private val latencyNs: Long,
        private val runOnlyNs: Long? = null,
    ) : NpuTimedBackend {
        var closed = false
        override fun init() = NpuBackendInit(4_806_000L, 10_930_000L, 270_000L, "NPU,GPU,CPU")
        override fun inputElementCount() = 224 * 224 * 3
        override fun infer(input: FloatArray) {
            ShadowSystemClock.advanceBy(Duration.ofNanos(latencyNs))
        }
        override fun lastRunOnlyNs(): Long? = runOnlyNs
        override fun close() {
            closed = true
        }
    }

    private val moduleDir = File(".").absoluteFile
    private val modelFile = File(moduleDir, "src/main/assets/models/mobilenet_v1_1.0_224_Samsung_E9965.tflite")
    private val originalModelFile = File(moduleDir, "../benchmark-runner/src/main/assets/models/mobilenet_v1_1.0_224.tflite")
    private val dispatchFile = File(moduleDir, "src/main/jniLibs/arm64-v8a/libLiteRtDispatch_Samsung.so")
    private val manifestFile = File(moduleDir, "src/main/assets/models/aot_manifest.json")
    private val outRoot = File(moduleDir, "build/npu-roundtrip")

    @Before
    fun registerRunProvider() {
        Robolectric.setupContentProvider(FakeRunProvider::class.java, "com.example.d1check.run")
    }

    private fun realArtifacts(file: File = modelFile): NpuArtifacts {
        val modelSha = FileInputStream(file).use(NpuArtifacts::sha256)
        return NpuArtifacts(
            modelId = NpuArtifacts.modelIdOf(file.name),
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
        accelerator: TimedAccelerator = TimedAccelerator.NPU,
        recordRunOnly: Boolean = false,
        expectFormalNpuValid: Boolean = expectValid,
        gpuPrecision: String? = null,
        maxInferenceSpans: Int = NpuRunConfig.DEFAULT_MAX_INFERENCE_SPANS,
        exportForHost: Boolean = true,
    ): NpuTimedRunResult {
        FakeRunProvider.runId = runId
        FakeRunProvider.startedElapsedNs = SystemClock.elapsedRealtimeNanos()
        ShadowSystemClock.advanceBy(Duration.ofMillis(1))
        val backend = FakeBackend(latencyNs = 2_000_000L, runOnlyNs = if (recordRunOnly) 1_500_000L else null)
        val config = NpuRunConfig(
            limit = RunLimit.Duration(DURATION_S),
            warmupCount = WARMUP,
            experimentMode = ExperimentMode.BASIC,
            expectedRunId = runId,
            commandId = commandId,
            dutyCyclePercent = dutyPercent,
            dutyCyclePeriodSeconds = periodSeconds,
            accelerator = accelerator,
            recordRunOnly = recordRunOnly,
            gpuPrecision = gpuPrecision,
            maxInferenceSpans = maxInferenceSpans,
        )
        // GPU 는 원본 FP32 모델을 연다 (AOT 는 NPU 전용)
        val artifactFile = if (accelerator == TimedAccelerator.GPU) originalModelFile else modelFile
        val engine = NpuTimedRunEngine(
            context = RuntimeEnvironment.getApplication(),
            backendFactory = { backend },
            baselineMs = 0L,
            idle = { nanos -> ShadowSystemClock.advanceBy(Duration.ofNanos(nanos)) },
            safety = { safety },
            artifacts = { realArtifacts(artifactFile) },
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
        if (!exportForHost) return done

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
                .put("expect_formal_npu_valid", expectFormalNpuValid)
                .put("timed_accelerator", accelerator.wireName)
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
        // 기본 설정 = 2026-09-26 이전과 같은 출력: 새 키·새 이벤트가 없다
        assertEquals("NPU", metadata.getString("npu_accelerator_requested"))
        for (key in listOf("npu_timed_resource_label", "npu_run_only_span", "npu_model_size_bytes")) {
            assertFalse(key, metadata.has(key))
        }
        assertEquals(0, records.count { it.getString("event") == "run_only_summary" })
    }

    @Test
    fun runOnlySpanIsOptInAndSummarisesTheLoad() {
        val result = runCase(
            "npu-d100-runonly", "12121212-1111-4111-8111-111111111111", "34343434-2222-4222-8222-222222222222",
            100, 10.0, PASSING_SAFETY, expectValid = true, recordRunOnly = true,
        )
        val records = records(result)
        val metadata = records.first()
        val summaries = records.filter { it.getString("event") == "run_only_summary" }
        assertEquals(1, summaries.size)
        val detail = JSONObject(summaries.single().getString("detail"))
        val inferences = records.count { it.getString("event") == "inference" }
        assertEquals(inferences, detail.getInt("count"))
        assertEquals(0, detail.getInt("missing"))
        assertEquals(1_500_000L, detail.getLong("median_ns"))
        // 기존 inference latency 의미(write+run+read)는 그대로다
        assertEquals("writeFloat+run+readFloat", metadata.getString("npu_latency_boundary"))
        assertTrue(metadata.has("npu_run_only_span"))
    }

    @Test
    fun cpuOnlyCompiledModelRunIsLabelledAndNeverAnNpuRun() {
        val result = runCase(
            "cpu-compiled-d100", "56565656-1111-4111-8111-111111111111", "78787878-2222-4222-8222-222222222222",
            100, 10.0, PASSING_SAFETY, expectValid = true, accelerator = TimedAccelerator.CPU,
            expectFormalNpuValid = false,
        )
        val metadata = records(result).first()
        assertEquals("CPU", metadata.getString("npu_accelerator_requested"))
        assertEquals("cpu_compiled_model", metadata.getString("npu_timed_resource_label"))
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

    // ------------------------------------------------------------------ 2026-09-28

    @Test
    fun gpuCompiledModelRunIsLabelledWithPrecisionRecordAndNeverAnNpuRun() {
        val result = runCase(
            "gpu-compiled-d100", "9a9a9a9a-1111-4111-8111-111111111111", "9b9b9b9b-2222-4222-8222-222222222222",
            100, 10.0, PASSING_SAFETY, expectValid = true, accelerator = TimedAccelerator.GPU,
            expectFormalNpuValid = false, gpuPrecision = "FP32",
        )
        val metadata = records(result).first()
        assertEquals("GPU", metadata.getString("npu_accelerator_requested"))
        assertEquals("gpu_compiled_model", metadata.getString("npu_timed_resource_label"))
        assertEquals(ORIGINAL_SHA, metadata.getString("model_sha256"))
        val options = metadata.getJSONObject("compiled_model_options")
        assertEquals("FP32", options.getJSONObject("gpu_options").getString("precision"))
        assertEquals("GPU", options.getJSONArray("accelerators_passed_to_native").getString(0))
        assertEquals(1, options.getJSONArray("accelerators_passed_to_native").length())
        assertTrue(metadata.getJSONObject("precision_record").has("internal_compute"))
    }

    @Test
    fun raisedSpanCapIsHonouredAndLoweredCapStillFailsClosed() {
        // 상한을 낮추면 기존과 같은 buffer_limit 실패 (detail 은 설정값) — 상한 옵션이 실제로 connect 에 들어간다는 증거
        val result = runCase(
            "npu-cap-small", "5a5a5a5a-1111-4111-8111-111111111111", "5b5b5b5b-2222-4222-8222-222222222222",
            100, 10.0, PASSING_SAFETY, expectValid = false, maxInferenceSpans = 100, exportForHost = false,
        )
        val records = records(result)
        val metadata = records.first()
        assertEquals("buffer_limit", metadata.getString("termination_reason"))
        assertEquals(100, metadata.getInt("completed_inference_count"))
        assertEquals("max=100", records.single { it.getString("event") == "buffer_limit" }.getString("detail"))
        assertEquals(100, metadata.getInt("max_inference_spans"))
    }

    private fun backendFor(segment: NpuChainSegment, opened: MutableList<String>): NpuTimedBackend {
        opened += segment.backendKey
        return FakeBackend(
            latencyNs = when (segment.accelerator) {
                TimedAccelerator.GPU -> 3_000_000L
                TimedAccelerator.NPU -> 1_000_000L
                TimedAccelerator.CPU -> 5_000_000L
            },
        )
    }

    private fun runChainCase(case: String, runId: String, commandId: String, chainJson: String): Pair<NpuTimedRunResult, List<String>> {
        FakeRunProvider.runId = runId
        FakeRunProvider.startedElapsedNs = SystemClock.elapsedRealtimeNanos()
        ShadowSystemClock.advanceBy(Duration.ofMillis(1))
        val sha = java.security.MessageDigest.getInstance("SHA-256").digest(chainJson.toByteArray())
            .joinToString("") { "%02x".format(it) }
        val spec = NpuChainSpec.parse(chainJson, sha)
        val config = NpuRunConfig(
            limit = RunLimit.Duration(spec.totalDurationSeconds),
            warmupCount = WARMUP,
            experimentMode = ExperimentMode.BASIC,
            expectedRunId = runId,
            commandId = commandId,
            dutyCyclePeriodSeconds = CHAIN_PERIOD_S,
            chain = spec,
        )
        val opened = mutableListOf<String>()
        val engine = NpuChainRunEngine(
            context = RuntimeEnvironment.getApplication(),
            backendFactory = { segment -> backendFor(segment, opened) },
            baselineMs = 0L,
            idle = { nanos -> ShadowSystemClock.advanceBy(Duration.ofNanos(nanos)) },
            safety = { PASSING_SAFETY },
            artifacts = { segment ->
                realArtifacts(if (segment.accelerator == TimedAccelerator.NPU) modelFile else originalModelFile)
            },
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
        assertTrue(done.message, done.success)
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
                .put("duration_s", spec.totalDurationSeconds)
                .put("warmup", WARMUP)
                .put("duty_cycle_percent", 100)
                .put("duty_cycle_period_s", CHAIN_PERIOD_S)
                .put("expect_valid", true)
                .put("expect_formal_npu_valid", false)
                .put("timed_accelerator", "CHAIN")
                .put("chain_json", chainJson)
                .put("chain_sha256", sha)
                .toString(2)
        )
        return done to opened
    }

    private fun chainJson(prepare: String, vararg segments: String): String =
        "{\"schema\":\"d1-npu-chain-v1\",\"chain_id\":\"roundtrip_$prepare\",\"model_prepare\":\"$prepare\"," +
            "\"segments\":[${segments.joinToString(",")}]}"

    private fun seg(accelerator: String, duty: Int, seconds: Int, label: String): String {
        val model = if (accelerator == "NPU") "models/mobilenet_v1_1.0_224_Samsung_E9965.tflite"
        else "models/mobilenet_v1_1.0_224.tflite"
        return "{\"accelerator\":\"$accelerator\",\"model\":\"$model\",\"input_spec\":\"lcg-unit\"," +
            "\"duty\":$duty,\"duration_s\":$seconds,\"label\":\"$label\"}"
    }

    @Test
    fun chainKeepsOneBackendWhileTheAcceleratorStaysTheSame() {
        // M1 모양: GPU d10 → GPU d100 → GPU d10. 같은 모델을 이어 쓰므로 init 1번, 전환 창엔 warmup 만
        val json = chainJson("per_segment", seg("GPU", 10, 1, "cold_d10"), seg("GPU", 100, 2, "heat"),
            seg("GPU", 10, 1, "probe_d10"))
        val (result, opened) = runChainCase(
            "chain-m1-same-backend", "c1c1c1c1-1111-4111-8111-111111111111",
            "c2c2c2c2-2222-4222-8222-222222222222", json,
        )
        assertEquals(1, opened.size)
        val records = records(result)
        val metadata = records.first()
        assertEquals(1, records.count { it.getString("event") == "load_start" })
        assertEquals(1, records.count { it.getString("event") == "load_end" })
        assertEquals(3, records.count { it.getString("event") == "segment_start" })
        assertEquals(3, records.count { it.getString("event") == "segment_end" })
        assertEquals(2, records.count { it.getString("event") == "chain_transition_end" })
        assertEquals(1, records.count { it.getString("event") == "chain_model_init" })
        assertTrue(metadata.getBoolean("chain_mode"))
        assertEquals("chain_compiled_model", metadata.getString("npu_timed_resource_label"))
        val segments = metadata.getJSONArray("chain_segments")
        var sum = 0
        for (i in 0 until segments.length()) sum += segments.getJSONObject(i).getInt("inference_count")
        assertEquals(metadata.getInt("completed_inference_count"), sum)
        assertEquals(sum, records.count { it.getString("event") == "inference" })
        assertEquals(JSONObject(json).toString(), metadata.getJSONObject("chain_spec").toString())
    }

    @Test
    fun chainSwitchingAcceleratorsRecordsInitInsideTheTransition() {
        // M2 모양 (per_segment): GPU d100 → NPU d100 → CPU d50
        val json = chainJson("per_segment", seg("GPU", 100, 2, "heat_gpu"), seg("NPU", 100, 1, "victim_npu"),
            seg("CPU", 50, 1, "victim_cpu"))
        val (result, opened) = runChainCase(
            "chain-m2-per-segment", "d1d1d1d1-1111-4111-8111-111111111111",
            "d2d2d2d2-2222-4222-8222-222222222222", json,
        )
        assertEquals(3, opened.size)
        val metadata = records(result).first()
        val transitions = metadata.getJSONArray("chain_transitions")
        assertEquals(2, transitions.length())
        for (i in 0 until transitions.length()) {
            val t = transitions.getJSONObject(i)
            assertTrue(t.getBoolean("backend_switch"))
            assertTrue(t.getBoolean("model_initialized"))
            assertTrue(t.has("model_init_ns"))
        }
        val native = metadata.getJSONArray("chain_segments").getJSONObject(1)
            .getJSONObject("compiled_model_options").getJSONArray("accelerators_passed_to_native")
        assertEquals(listOf("NPU", "CPU"), (0 until native.length()).map { native.getString(it) })
    }

    @Test
    fun chainUpfrontPreparesEveryModelBeforeLoadStart() {
        val json = chainJson("upfront", seg("GPU", 100, 1, "control_gpu"), seg("NPU", 100, 1, "victim_npu"))
        val (result, opened) = runChainCase(
            "chain-m2-upfront", "e1e1e1e1-1111-4111-8111-111111111111",
            "e2e2e2e2-2222-4222-8222-222222222222", json,
        )
        assertEquals(2, opened.size)
        val records = records(result)
        val loadStart = records.single { it.getString("event") == "load_start" }.getLong("mono_ns")
        val inits = records.filter { it.getString("event") == "chain_model_init" }
        assertEquals(2, inits.size)
        assertTrue(inits.all { it.getLong("mono_ns") <= loadStart })
        val transition = records.first().getJSONArray("chain_transitions").getJSONObject(0)
        assertFalse(transition.getBoolean("model_initialized"))
    }

    companion object {
        const val DURATION_S = 2L
        const val WARMUP = 3
        const val CHAIN_PERIOD_S = 0.5
        const val ORIGINAL_SHA = "d95b3c5ea86750cef882fa867ca357dfe4d265d0b80b67e83277a0bda310cfbb"
        const val MOBILENET_AOT_SHA = "1415b2c87d01b67a9380b8f912e2b4ef4561502105b06f313332c97c1c8cb5cf"
        const val DISPATCH_SHA = "f08656a642c46e7b06b64fbe1e0800de9e73b0b69c1641b87995562b4a16840f"
        internal val PASSING_SAFETY: PilotSafetyCheck =
            PilotSafetyPolicy.evaluate(PilotSafetySnapshot(0, 0, 3, 80, 30.0))
    }
}
