package com.example.d1check.requestrunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File

/**
 * M5 왕복 (폰 없이): 상태 분리 스모크 ID (S26-STATESPLIT-01-SMOKE, diagnostic) 의 522 요청표를 실제 SessionEngine 으로 끝까지 —
 * C (블록 A 키 · CPU 직렬) · G (블록 A · 병행) · N (블록 N · NPU 병행). time_scale 4 (10 은 Windows sleep 정밀도 ≈ 15 ms 때문에 가짜 서비스가 늘어 과부하) · 가짜 서비스 시간 = R3 lane 중앙 크기의 1/4
 * (분류 CPU 52 · GPU 65 · NPU 60 · 탐지 CPU 240 ms → /4, 시험용 숫자 · 결과 아님). 산출물 build/statesplit-roundtrip/<case>/a1 은
 * s26/tools/mixreq/test_statesplit.py 가 statesplit_validate (--selftest) · statesplit_readout 으로 다시 읽는다.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class StatesplitRoundTripTest {
    private val moduleDir = File(".").absoluteFile
    private val root = File(moduleDir, "build/statesplit-roundtrip")
    private val inputs = File(root, "_inputs")
    private val rgb = byteArrayOf(10, 20, 30, 40, 50, 60)
    private val sha = HashMap<String, String>()

    private class FakeRuntime(override val spec: RuntimeSpec, private val latencyNs: Long, private val variant: Float) : InferenceRuntime {
        override fun inputElementCount() = if (spec.task == "classification") 224 * 224 * 3 else 320 * 320 * 3
        override fun run(input: FloatArray): List<FloatArray> {
            val until = System.nanoTime() + latencyNs
            if (latencyNs > 2_000_000L) Thread.sleep((latencyNs - 1_000_000L) / 1_000_000L)
            while (System.nanoTime() < until) Thread.onSpinWait()
            return if (spec.task == "classification") listOf(SessionRoundTripTest.classification(variant))
            else listOf(SessionRoundTripTest.detectionScores(variant), FloatArray(19_206 * 4))
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
        val realAot = File(moduleDir, "../npu-runner/src/main/assets/models/efficientnet_lite0_Samsung_E9965.tflite")
        if (realAot.isFile) put("efficientnet_lite0_Samsung_E9965.tflite", realAot.readBytes())
        else put("efficientnet_lite0_Samsung_E9965.tflite", "fake NPU AOT artifact".toByteArray())
    }

    private fun manifestBytes(block: String, policy: String, letter: String): ByteArray {
        val experimentId = MixreqContract.STATESPLIT_SMOKE_EXPERIMENT_ID
        val sid = RequestPlan.sessionId(experimentId, 0)
        val requests = StatesplitPlan.requests(sid).map { linkedMapOf("request_id" to it.id, "ordinal" to it.ordinal, "task_id" to it.task,
            "priority" to it.priority, "offset_ms" to it.offsetMs, "deadline_ms" to it.deadlineMs) }
        fun spec(key: String): Map<String, Any?> {
            val task = MixreqContract.taskOf(key); val lane = MixreqContract.laneOf(key)
            val model = when { lane == "NPU" -> "efficientnet_lite0_Samsung_E9965.tflite"; task == "classification" -> "efficientnet_lite0.tflite"; else -> "efficientdet_lite0.tflite" }
            return linkedMapOf("key" to key, "task" to task, "backend" to lane, "model_path" to File(inputs, model).path, "model_sha256" to sha.getValue(model),
                "gpu_precision" to (if (lane == "GPU") "FP32" else null), "cpu_threads" to (if (lane == "CPU") 1 else null))
        }
        val m = linkedMapOf<String, Any?>(
            "protocol" to MixreqContract.PROTOCOL, "experiment_id" to experimentId, "split" to MixreqContract.SPLIT_DIAGNOSTIC,
            "session_id" to sid, "session_index" to 0, "block" to block, "pair" to 0, "attempt" to 1, "policy" to policy,
            "runtimes" to MixreqContract.keysOf(block).sorted().map(::spec),
            "image" to linkedMapOf("path" to File(inputs, "image.png").path, "sha256" to sha.getValue("image.png"), "width" to 2, "height" to 1),
            "anchors" to linkedMapOf("path" to File(inputs, "anchors.json").path, "sha256" to sha.getValue("anchors.json")),
            "labels" to linkedMapOf("classification" to linkedMapOf("path" to File(inputs, "labels_without_background.txt").path, "sha256" to sha.getValue("labels_without_background.txt")),
                "detection" to linkedMapOf("path" to File(inputs, "labels.txt").path, "sha256" to sha.getValue("labels.txt"))),
            "requests" to requests,
            "phases" to linkedMapOf("setup_s" to (if (block == "N") 180 else 150), "gate_s" to 60, "baseline_s" to 30, "common_s" to 120, "drain_s" to 30, "cooling_s" to 60),
            "sample_period_ms" to 900, "time_scale" to TIME_SCALE, "warmup_gate" to true,
            "stop_rules" to linkedMapOf("battery_deci_c_max" to 420, "thermal_status_max" to 2, "soc_min" to 20),
            "start_check" to linkedMapOf("thermal_status_max" to 1), "statesplit_letter" to letter,
        )
        return Json.encode(m).toByteArray()
    }

    private fun latency(spec: RuntimeSpec): Long = when (spec.key) {
        "classification_CPU" -> 52_000_000L; "classification_GPU" -> 65_000_000L; "classification_NPU" -> 60_000_000L; else -> 240_000_000L
    } / TIME_SCALE

    private fun run(case: String, block: String, policy: String, letter: String) {
        writeInputs()
        val caseDir = File(root, case).apply { deleteRecursively(); mkdirs() }
        val bytes = manifestBytes(block, policy, letter)
        val manifest = SessionManifest.parse(String(bytes)).also { it.validate() }
        val sessionInputs = File(caseDir, "inputs").apply { mkdirs() }
        File(sessionInputs, "manifest.json").writeBytes(bytes)
        val out = File(caseDir, "a1")
        val snapshot = { linkedMapOf<String, Any?>("current_raw" to -523_000, "current_valid" to true, "voltage_mV" to 4_012, "charge_counter_raw" to 3_000_000,
            "charge_valid" to true, "plugged" to 0, "battery_temperature_deci_c" to 301, "battery_level" to 77, "battery_scale" to 100, "thermal_status" to 0,
            "interactive" to true, "snapshot_start_ns" to System.nanoTime(), "sensor_read_end_ns" to System.nanoTime()) }
        val engine = SessionEngine(manifest, bytes, sessionInputs, out,
            runtimeFactory = { spec -> FakeRuntime(spec, latency(spec), when (spec.backend) { Backend.CPU -> 0f; Backend.GPU -> 1e-5f; Backend.NPU -> 5e-4f }) },
            decodeImage = { DecodedImage(2, 1, rgb) }, snapshot = snapshot, now = System::nanoTime, identity = mapOf("pid" to 4242), log = { })
        val hash = ImageContract.sha256(bytes)
        val host = Thread {
            val ready = File(out, "warmup.ready.json"); val deadline = System.nanoTime() + 120_000_000_000L
            while (!ready.exists() && System.nanoTime() < deadline && engine.phase != "cleanup") Thread.sleep(20)
            if (ready.exists()) File(sessionInputs, "warmup.arm").writeText(hash)
        }.apply { isDaemon = true; start() }
        val completed = engine.run()
        host.join(1000)
        assertTrue("$case stop=${engine.stop.get()}", completed)
        val rows = (TestJson.parse(File(out, "requests.json").readText()) as List<*>).map { it as Map<*, *> }
        assertEquals(522, rows.size)
        assertTrue(rows.all { it["terminal_status"] == "succeeded" })
        assertTrue(rows.all { it["selected_backend"] == PolicyStudy.laneFor(policy, it["task_id"] as String) })
        assertEquals(522, out.listFiles()!!.count { it.name.endsWith(".result.json") })
    }

    @Test fun cpuSerial() = run("C", "A", MixreqContract.POLICY_CPU, "C")
    @Test fun gpuParallel() = run("G", "A", MixreqContract.POLICY_PAR, "G")
    @Test fun npuParallel() = run("N", "N", MixreqContract.POLICY_PAR_NPU, "N")

    companion object { const val TIME_SCALE = 4 }
}
