package com.example.d1check.requestrunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File

/**
 * 회귀 (프롬프트 M8 B-2 3): 기존 행 (S26-MIXREQ-02 B2 · S26-M6-P L-C · S26-M6-K) 이 기준 커밋 aaa7b87f 의 SessionEngine 과 같은 이벤트 종류 · 단계 순서 · 요청 행 키를 내는지.
 * 기준 목록은 aaa7b87f 의 엔진 (SessionEngine.kt · M8 에서 diff 0) 에서 적은 것 — M8 전용 키 (readback_* · response_ns · wait_* · burst_index · offset_us · undispatched) 가 기존 행에 없어야 한다.
 * SessionRoundTripTest · M6RoundTripTest 는 그대로 돈다 (이 시험은 그 위에 모양 검사만 더한다).
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class M6RegressionShapeTest {
    private val moduleDir = File(".").absoluteFile
    private val root = File(moduleDir, "build/m6-regression")
    private val inputs = File(root, "_inputs")
    private val rgb = byteArrayOf(10, 20, 30, 40, 50, 60)
    private val sha = HashMap<String, String>()

    companion object {
        /** aaa7b87f SessionEngine 이 내는 progress.jsonl kind (lifecycle 제외 · 시험 경로). */
        val BASE_EVENT_KINDS = setOf("session_start", "phase_start", "phase_end", "runtime_submit", "runtime_start", "admission", "runtime_return", "warmup_submit", "warmup_start",
            "warmup_return", "host_gate_accepted", "common_start", "decision", "arrival", "queue_entry", "dispatch", "request_start", "host_inference_start", "host_inference_return",
            "output_ready", "persist_complete", "worker_release", "lane_available", "common_end", "app_cleanup", "power_sample")
        /** aaa7b87f requests.json 행 키 (완료 요청). */
        val BASE_ROW_KEYS = setOf("request_id", "ordinal", "task_id", "priority", "scheduled_arrival_ns", "actual_arrival_ns", "deadline_ns", "terminal_status", "queue_entry_ns",
            "selected_backend", "decision_reason", "dispatch_ns", "execution_start_ns", "host_inference_start_ns", "host_inference_return_ns", "output_ready_ns", "persist_complete_ns",
            "worker_release_ns", "lane_available_ns")
        val BASE_PHASES = listOf("runtime_setup", "warmup", "resident_baseline", "common_start", "common_end", "post_window_drain", "resident_cooling")
        val M8_ONLY_KEYS = setOf("readback_start_ns", "readback_end_ns", "readback_ok", "readback_sha256", "readback_skipped", "response_ns", "response_boundary", "wait_burst_index",
            "wait_dose_ms", "burst_index", "offset_us", "undispatched_reason")
        val M8_ONLY_EVENTS = setOf("wait_start", "wait_end", "readback", "dispatch_closed", "prep_end", "prep_call_start", "prep_call_end")
    }

    private class FakeRuntime(override val spec: RuntimeSpec, private val latencyNs: Long) : InferenceRuntime {
        override fun inputElementCount() = if (spec.task == "classification") 224 * 224 * 3 else 320 * 320 * 3
        override fun run(input: FloatArray): List<FloatArray> {
            val until = System.nanoTime() + latencyNs
            if (latencyNs > 2_000_000L) Thread.sleep((latencyNs - 1_000_000L) / 1_000_000L)
            while (System.nanoTime() < until) Thread.onSpinWait()
            return if (spec.task == "classification") listOf(SessionRoundTripTest.classification(if (spec.backend == Backend.CPU) 0f else 1e-5f))
            else listOf(SessionRoundTripTest.detectionScores(0f), FloatArray(19_206 * 4))
        }
        override fun initRecord(): Map<String, Any?> = mapOf("engine" to "fake")
        override fun close() {}
    }

    private fun writeInputs() {
        inputs.mkdirs()
        fun put(name: String, bytes: ByteArray) { File(inputs, name).writeBytes(bytes); sha[name] = ImageContract.sha256(bytes) }
        put("image.png", SessionRoundTripTest.canonicalPng(2, 1, rgb))
        put("labels_without_background.txt", ((0 until 1000).joinToString("\n") { "cls$it" } + "\n").toByteArray())
        put("labels.txt", ((0 until 90).joinToString("\n") { "det$it" } + "\n").toByteArray())
        val anchors = StringBuilder("[")
        for (i in 0 until 19_206) { if (i > 0) anchors.append(','); anchors.append("[${(i % 139 + 0.5) / 139},${(i / 139 + 0.5) / 139},0.05,0.05]") }
        put("anchors.json", anchors.append(']').toString().toByteArray())
        put("efficientnet_lite0.tflite", "fake classification model".toByteArray())
        put("efficientdet_lite0.tflite", "fake detection model".toByteArray())
        put("efficientnet_lite0_Samsung_E9965.tflite", "fake NPU AOT artifact".toByteArray())
    }

    private fun manifestBytes(experimentId: String, index: Int, block: String, policy: String, timeScale: Int, requests: List<MixreqContract.Request>): ByteArray {
        val sid = RequestPlan.sessionId(experimentId, index)
        fun spec(key: String): Map<String, Any?> {
            val task = MixreqContract.taskOf(key); val lane = MixreqContract.laneOf(key)
            val model = when { lane == "NPU" -> "efficientnet_lite0_Samsung_E9965.tflite"; task == "classification" -> "efficientnet_lite0.tflite"; else -> "efficientdet_lite0.tflite" }
            return linkedMapOf("key" to key, "task" to task, "backend" to lane, "model_path" to File(inputs, model).path, "model_sha256" to sha.getValue(model),
                "gpu_precision" to (if (lane == "GPU") "FP32" else null), "cpu_threads" to (if (lane == "CPU") 1 else null))
        }
        val m = linkedMapOf<String, Any?>(
            "protocol" to MixreqContract.PROTOCOL, "experiment_id" to experimentId, "split" to MixreqContract.SPLIT_DIAGNOSTIC,
            "session_id" to sid, "session_index" to index, "block" to block, "pair" to 0, "attempt" to 1, "policy" to policy,
            "runtimes" to MixreqContract.keysOf(block).sorted().map(::spec),
            "image" to linkedMapOf("path" to File(inputs, "image.png").path, "sha256" to sha.getValue("image.png"), "width" to 2, "height" to 1),
            "anchors" to linkedMapOf("path" to File(inputs, "anchors.json").path, "sha256" to sha.getValue("anchors.json")),
            "labels" to linkedMapOf("classification" to linkedMapOf("path" to File(inputs, "labels_without_background.txt").path, "sha256" to sha.getValue("labels_without_background.txt")),
                "detection" to linkedMapOf("path" to File(inputs, "labels.txt").path, "sha256" to sha.getValue("labels.txt"))),
            "requests" to requests.map { linkedMapOf("request_id" to it.id, "ordinal" to it.ordinal, "task_id" to it.task, "priority" to it.priority, "offset_ms" to it.offsetMs, "deadline_ms" to it.deadlineMs) },
            "phases" to linkedMapOf("setup_s" to (if (block == "A") 150 else 180), "gate_s" to 60, "baseline_s" to 30, "common_s" to MixreqContract.experimentOf(experimentId).commonS, "drain_s" to 30, "cooling_s" to 60),
            "sample_period_ms" to 900, "time_scale" to timeScale, "warmup_gate" to true,
            "stop_rules" to linkedMapOf("battery_deci_c_max" to 420, "thermal_status_max" to 2, "soc_min" to 20),
            "start_check" to linkedMapOf("thermal_status_max" to 1),
        )
        return Json.encode(m).toByteArray()
    }

    private fun run(case: String, experimentId: String, index: Int, block: String, policy: String, timeScale: Int, requests: List<MixreqContract.Request>): File {
        writeInputs()
        val caseDir = File(root, case).apply { deleteRecursively(); mkdirs() }
        val bytes = manifestBytes(experimentId, index, block, policy, timeScale, requests)
        val manifest = SessionManifest.parse(String(bytes)).also { it.validate() }
        assertEquals(MixreqContract.CONTRACT_M6, manifest.contract)
        val sessionInputs = File(caseDir, "inputs").apply { mkdirs() }
        File(sessionInputs, "manifest.json").writeBytes(bytes)
        val out = File(caseDir, "a1")
        val snapshot = { linkedMapOf<String, Any?>("current_raw" to -523_000, "current_valid" to true, "voltage_mV" to 4_012, "charge_counter_raw" to 3_000_000,
            "charge_valid" to true, "plugged" to 0, "battery_temperature_deci_c" to 301, "battery_level" to 77, "battery_scale" to 100, "thermal_status" to 0,
            "interactive" to true, "snapshot_start_ns" to System.nanoTime(), "sensor_read_end_ns" to System.nanoTime()) }
        val engine = SessionEngine(manifest, bytes, sessionInputs, out,
            runtimeFactory = { spec -> FakeRuntime(spec, (if (spec.task == "classification") 50L else 240L) * 1_000_000L / timeScale) },
            decodeImage = { DecodedImage(2, 1, rgb) }, snapshot = snapshot, now = System::nanoTime, identity = mapOf("pid" to 4242), log = { })
        val hash = ImageContract.sha256(bytes)
        val host = Thread {
            val ready = File(out, "warmup.ready.json"); val deadline = System.nanoTime() + 120_000_000_000L
            while (!ready.exists() && System.nanoTime() < deadline && engine.phase != "cleanup") Thread.sleep(20)
            if (ready.exists()) File(sessionInputs, "warmup.arm").writeText(hash)
        }.apply { isDaemon = true; start() }
        assertTrue("$case stop=${engine.stop.get()}", engine.run())
        host.join(1000)
        return out
    }

    /** 요청 0 (K) 행은 요청 단위 이벤트 (decision · arrival · … · lane_available) 가 없다 — 기준 엔진에서도 같다. */
    private val REQUEST_EVENT_KINDS = setOf("decision", "arrival", "queue_entry", "dispatch", "request_start", "host_inference_start", "host_inference_return", "output_ready",
        "persist_complete", "worker_release", "lane_available")

    private fun checkShape(out: File, requestCount: Int) {
        val kinds = File(out, "progress.jsonl").readLines().map { (TestJson.parse(it) as Map<*, *>)["kind"] as String }
        assertEquals(if (requestCount > 0) BASE_EVENT_KINDS else BASE_EVENT_KINDS - REQUEST_EVENT_KINDS, kinds.toSet())
        assertTrue(kinds.none { it in M8_ONLY_EVENTS })
        val phases = File(out, "progress.jsonl").readLines().map { TestJson.parse(it) as Map<*, *> }
            .filter { (it["kind"] == "phase_start" && it["phase"] in BASE_PHASES) || it["kind"] in setOf("common_start", "common_end") }
            .map { if (it["kind"] == "phase_start") it["phase"] as String else it["kind"] as String }
        assertEquals(BASE_PHASES, phases)
        val rows = (TestJson.parse(File(out, "requests.json").readText()) as List<*>).map { it as Map<*, *> }
        assertEquals(requestCount, rows.size)
        for (r in rows) {
            assertEquals(BASE_ROW_KEYS, r.keys.map { it as String }.toSet())
            assertTrue(r.keys.none { it in M8_ONLY_KEYS })
        }
        val summary = TestJson.parse(File(out, "summary.json").readText()) as Map<*, *>
        assertTrue("summary must not carry M8 keys", summary.keys.none { it in setOf("contract", "wait", "readback", "response_boundary", "prep", "undispatched") })
        assertEquals(60L, (summary.let { File(out, "manifest.json").readText() }.let { (TestJson.parse(it) as Map<*, *>)["phases"] as Map<*, *> }["cooling_s"] as Number).toLong())
    }

    @Test fun mixreqB2RowKeepsTheBaseShape() {
        val sid = RequestPlan.sessionId("S26-MIXREQ-02-SMOKE", 1)
        val out = run("B2", "S26-MIXREQ-02-SMOKE", 1, "A", MixreqContract.POLICY_PAR, 10, RequestPlan.requests(sid, 24))
        checkShape(out, 24)
    }

    @Test fun m6LowCpuRowKeepsTheBaseShape() {
        val sid = RequestPlan.sessionId("S26-M6-P-SMOKE", 0)
        val out = run("M6_L-C", "S26-M6-P-SMOKE", 0, "M", MixreqContract.POLICY_CPU, 4, M6Plan.requests("S26-M6-P-SMOKE", 0, sid))
        checkShape(out, 100)
    }

    @Test fun m6CoolingRowKeepsTheBaseShape() {
        val out = run("M6_K", "S26-M6-K-SMOKE", 0, "M", MixreqContract.POLICY_CPU, 100, emptyList())
        checkShape(out, 0)
    }
}
