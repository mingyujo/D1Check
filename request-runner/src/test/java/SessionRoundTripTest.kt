package com.example.d1check.requestrunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.ByteArrayOutputStream
import java.io.DataOutputStream
import java.io.File
import java.nio.ByteBuffer
import java.util.zip.CRC32
import java.util.zip.Deflater

/**
 * K6: 세션 왕복 (폰 없이) — 실제 SessionEngine + 실제 기록 코드, 가짜 backend (서비스 시간만) · 가짜 표본 · 가짜 디코드.
 * time_scale 10 (등록 요청표 192 그대로 · offset/단계 길이만 1/10 → 세션 ≈ 25 s). 산출물은 build/mixreq-roundtrip/<case>/a1/ 에 남겨
 * tools 쪽 (s26/tools/mixreq/e2e_selftest.py → mixreq_validate.py → mixreq_readout.py) 이 등록 §4 9규칙으로 다시 검사한다.
 * 가짜 서비스 시간 = 시험용 숫자 (결과 아님): 분류 CPU 4.4 ms · GPU 2.0 ms · NPU 0.8 ms · 탐지 CPU 50 ms (짧게) / 300 ms (길게).
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class SessionRoundTripTest {
    private val moduleDir = File(".").absoluteFile
    private val root = File(moduleDir, "build/mixreq-roundtrip")
    private val inputs = File(root, "_inputs")

    private class FakeRuntime(override val spec: RuntimeSpec, private val latencyNs: Long, private val variant: Float,
                              private val failOnCreate: Boolean = false) : InferenceRuntime {
        init { if (failOnCreate) throw IllegalStateException("fake ${spec.key} creation failure (LiteRtException stand-in)") }
        override fun inputElementCount() = if (spec.task == "classification") 224 * 224 * 3 else 320 * 320 * 3
        override fun run(input: FloatArray): List<FloatArray> {
            require(input.size == inputElementCount())
            val until = System.nanoTime() + latencyNs
            if (latencyNs > 2_000_000L) Thread.sleep((latencyNs - 1_000_000L) / 1_000_000L)
            while (System.nanoTime() < until) Thread.onSpinWait()
            return if (spec.task == "classification") listOf(classification(variant))
            else listOf(detectionScores(variant), FloatArray(19_206 * 4))
        }
        override fun initRecord(): Map<String, Any?> = mapOf("engine" to "fake", "available_accelerators" to listOf("CPU", "GPU", "NPU"), "fake_latency_ns" to latencyNs)
        override fun close() {}
    }

    companion object {
        const val TIME_SCALE = 10
        fun classification(variant: Float): FloatArray = FloatArray(1000) { i ->
            val base = when (i) { 518 -> 0.2134f; 671 -> 0.1125f; 535 -> 0.0572f; 870 -> 0.0551f; 665 -> 0.0545f; else -> 0.0005f + (i % 7) * 0.00001f }
            base + variant * ((i % 3) - 1)
        }
        fun detectionScores(variant: Float): FloatArray = FloatArray(19_206 * 90).also {
            it[100 * 90 + 1] = 0.7f + variant
            it[15_000 * 90 + 3] = 0.6f + variant
        }
        fun canonicalPng(width: Int, height: Int, rgb: ByteArray): ByteArray {
            val raw = ByteArrayOutputStream()
            for (y in 0 until height) { raw.write(0); raw.write(rgb, y * width * 3, width * 3) }
            val deflater = Deflater().apply { setInput(raw.toByteArray()); finish() }
            val idat = ByteArrayOutputStream(); val buf = ByteArray(4096)
            while (!deflater.finished()) idat.write(buf, 0, deflater.deflate(buf))
            val stream = ByteArrayOutputStream(); val out = DataOutputStream(stream)
            out.write(byteArrayOf(-119, 80, 78, 71, 13, 10, 26, 10))
            fun chunk(type: String, data: ByteArray) {
                out.writeInt(data.size); val t = type.toByteArray(Charsets.US_ASCII); out.write(t); out.write(data)
                val crc = CRC32(); crc.update(t); crc.update(data); out.writeInt(crc.value.toInt())
            }
            chunk("IHDR", ByteBuffer.allocate(13).putInt(width).putInt(height).put(8).put(2).put(0).put(0).put(0).array())
            chunk("IDAT", idat.toByteArray()); chunk("IEND", ByteArray(0))
            return stream.toByteArray()
        }
    }

    private val rgb = byteArrayOf(10, 20, 30, 40, 50, 60)
    private lateinit var pngSha: String
    private lateinit var anchorsSha: String
    private lateinit var clsLabelsSha: String
    private lateinit var detLabelsSha: String
    private val modelSha = HashMap<String, String>()

    private fun writeInputs() {
        inputs.mkdirs()
        val png = canonicalPng(2, 1, rgb); File(inputs, "image.png").writeBytes(png); pngSha = ImageContract.sha256(png)
        val clsLabels = (0 until 1000).joinToString("\n") { "cls$it" } + "\n"
        File(inputs, "labels_without_background.txt").writeText(clsLabels); clsLabelsSha = ImageContract.sha256(clsLabels.toByteArray())
        val detLabels = (0 until 90).joinToString("\n") { if (it % 10 == 9) "???" else "det$it" } + "\n"
        File(inputs, "labels.txt").writeText(detLabels); detLabelsSha = ImageContract.sha256(detLabels.toByteArray())
        val anchors = StringBuilder("[")
        for (i in 0 until 19_206) { if (i > 0) anchors.append(','); anchors.append("[${(i % 139 + 0.5) / 139},${(i / 139 + 0.5) / 139},0.05,0.05]") }
        anchors.append(']'); File(inputs, "anchors.json").writeText(anchors.toString()); anchorsSha = ImageContract.sha256(anchors.toString().toByteArray())
        for ((name, body) in listOf("efficientnet_lite0.tflite" to "fake classification model", "efficientdet_lite0.tflite" to "fake detection model",
            "efficientnet_lite0_Samsung_E9965.tflite" to "fake NPU AOT artifact")) {
            File(inputs, name).writeBytes(body.toByteArray()); modelSha[name] = ImageContract.sha256(body.toByteArray())
        }
        // The host validator looks the NPU artifact up in the AOT table (tools/d1_logger_v4.py) by SHA-256: use the real AOT file when it is
        // on disk (git 밖, npu-runner assets) so the e2e self-test can exercise the npu-dispatch-evidence conditions; the fake backend ignores it.
        val realAot = File(moduleDir, "../npu-runner/src/main/assets/models/efficientnet_lite0_Samsung_E9965.tflite")
        if (realAot.isFile) {
            realAot.copyTo(File(inputs, "efficientnet_lite0_Samsung_E9965.tflite"), overwrite = true)
            modelSha["efficientnet_lite0_Samsung_E9965.tflite"] = TaskRuntime.sha256(realAot)
        }
    }

    private fun runtimeSpec(key: String): Map<String, Any?> {
        val task = MixreqContract.taskOf(key); val lane = MixreqContract.laneOf(key)
        val model = when { lane == "NPU" -> "efficientnet_lite0_Samsung_E9965.tflite"; task == "classification" -> "efficientnet_lite0.tflite"; else -> "efficientdet_lite0.tflite" }
        return linkedMapOf("key" to key, "task" to task, "backend" to lane, "model_path" to File(inputs, model).path, "model_sha256" to modelSha.getValue(model),
            "gpu_precision" to (if (lane == "GPU") "FP32" else null), "cpu_threads" to (if (lane == "CPU") 1 else null))
    }

    private fun manifestBytes(index: Int, block: String, policy: String, attempt: Int = 1): ByteArray {
        val sid = RequestPlan.sessionId(MixreqContract.EXPERIMENT_ID, index)
        val requests = RequestPlan.requests(sid).map { linkedMapOf("request_id" to it.id, "ordinal" to it.ordinal, "task_id" to it.task,
            "priority" to it.priority, "offset_ms" to it.offsetMs, "deadline_ms" to it.deadlineMs) }
        val m = linkedMapOf<String, Any?>(
            "protocol" to MixreqContract.PROTOCOL, "experiment_id" to MixreqContract.EXPERIMENT_ID, "split" to MixreqContract.SPLIT_DIAGNOSTIC,
            "session_id" to sid, "session_index" to index, "block" to block, "pair" to (if (block == "A") index / 2 else (index - 8) / 2), "attempt" to attempt,
            "policy" to policy, "runtimes" to MixreqContract.keysOf(block).sorted().map(::runtimeSpec),
            "image" to linkedMapOf("path" to File(inputs, "image.png").path, "sha256" to pngSha, "width" to 2, "height" to 1),
            "anchors" to linkedMapOf("path" to File(inputs, "anchors.json").path, "sha256" to anchorsSha),
            "labels" to linkedMapOf("classification" to linkedMapOf("path" to File(inputs, "labels_without_background.txt").path, "sha256" to clsLabelsSha),
                "detection" to linkedMapOf("path" to File(inputs, "labels.txt").path, "sha256" to detLabelsSha)),
            "requests" to requests,
            "phases" to linkedMapOf("setup_s" to (if (block == "N") 180 else 150), "gate_s" to 60, "baseline_s" to 30, "common_s" to 120, "drain_s" to 30, "cooling_s" to 60),
            "sample_period_ms" to 900, "time_scale" to TIME_SCALE, "warmup_gate" to true,
            "stop_rules" to linkedMapOf("battery_deci_c_max" to 420, "thermal_status_max" to 2, "soc_min" to 20),
            "start_check" to linkedMapOf("thermal_status_max" to 1),
        )
        return Json.encode(m).toByteArray()
    }

    private fun snapshot(plugged: Int = 0): Map<String, Any?> = linkedMapOf("current_raw" to -523_000, "current_valid" to true, "voltage_mV" to 4_012,
        "charge_counter_raw" to 3_000_000, "charge_valid" to true, "plugged" to plugged, "battery_temperature_deci_c" to 301, "battery_level" to 77,
        "battery_scale" to 100, "thermal_status" to 0, "interactive" to true, "snapshot_start_ns" to System.nanoTime(), "sensor_read_end_ns" to System.nanoTime())

    private fun latencyFor(spec: RuntimeSpec, longDetection: Boolean): Long = when (spec.key) {
        "classification_CPU" -> 4_400_000L; "classification_GPU" -> 2_000_000L; "classification_NPU" -> 800_000L
        else -> if (longDetection) 300_000_000L else 50_000_000L
    } / TIME_SCALE

    private fun runCase(case: String, index: Int, block: String, policy: String, plugged: Int = 0, npuFails: Boolean = false,
                        longDetection: Boolean = false, expectCompleted: Boolean): Pair<File, SessionEngine> {
        writeInputs()
        val caseDir = File(root, case).apply { deleteRecursively(); mkdirs() }
        val bytes = manifestBytes(index, block, policy)
        val manifest = SessionManifest.parse(String(bytes)).also { it.validate() }
        val sessionInputs = File(caseDir, "inputs").apply { mkdirs() }
        File(sessionInputs, "manifest.json").writeBytes(bytes)
        val out = File(caseDir, "a1")
        val engine = SessionEngine(manifest, bytes, sessionInputs, out,
            // fake output variants: GPU within the A24 tolerance (1e-5), NPU bit-different but cosine > 0.99 (5e-4) so the §4-N contract passes
            runtimeFactory = { spec -> FakeRuntime(spec, latencyFor(spec, longDetection), when (spec.backend) { Backend.CPU -> 0f; Backend.GPU -> 1e-5f; Backend.NPU -> 5e-4f }, failOnCreate = npuFails && spec.backend == Backend.NPU) },
            decodeImage = { DecodedImage(2, 1, rgb) }, snapshot = { snapshot(plugged) }, now = System::nanoTime,
            identity = mapOf("pid" to 4242, "device_model" to "robolectric"), log = { })
        // host stand-in: arm the warmup gate with the manifest SHA once warmup.ready.json appears
        val hash = ImageContract.sha256(bytes)
        val host = Thread {
            val ready = File(out, "warmup.ready.json"); val deadline = System.nanoTime() + 120_000_000_000L
            while (!ready.exists() && System.nanoTime() < deadline && engine.phase != "cleanup") Thread.sleep(20)
            if (ready.exists()) File(sessionInputs, "warmup.arm").writeText(hash)
        }.apply { isDaemon = true; start() }
        val completed = engine.run()
        host.join(1000)
        assertEquals("$case completed=$completed stop=${engine.stop.get()}", expectCompleted, completed)
        File(caseDir, "roundtrip.json").writeText(Json.encode(mapOf("case" to case, "session_index" to index, "block" to block, "policy" to policy,
            "time_scale" to TIME_SCALE, "expect_completed" to expectCompleted, "plugged" to plugged, "npu_fails" to npuFails, "long_detection" to longDetection,
            "stop_reason" to engine.stop.get(), "manifest_sha256" to hash)))
        return out to engine
    }

    private fun rows(out: File): List<Map<*, *>> = (TestJson.parse(File(out, "requests.json").readText()) as List<*>).map { it as Map<*, *> }
    private fun ns(row: Map<*, *>, key: String) = (row[key] as Number).toLong()

    private fun assertCompletedShape(out: File, policy: String, keys: Int) {
        val summary = TestJson.parse(File(out, "summary.json").readText()) as Map<*, *>
        assertEquals("completed", summary["status"]); assertEquals(192L, summary["planned"]); assertEquals(192L, summary["terminal"])
        val cleanup = TestJson.parse(File(out, "cleanup.json").readText()) as Map<*, *>
        assertEquals("completed", cleanup["status"])
        val rows = rows(out)
        assertEquals(192, rows.size)
        assertTrue(rows.all { it["terminal_status"] == "succeeded" })
        for (r in rows) {
            val order = listOf("scheduled_arrival_ns", "actual_arrival_ns", "queue_entry_ns", "dispatch_ns", "execution_start_ns", "host_inference_start_ns",
                "host_inference_return_ns", "output_ready_ns", "persist_complete_ns", "worker_release_ns", "lane_available_ns").map { ns(r, it) }
            assertEquals(r.toString(), order, order.sorted())
            assertEquals(PolicyStudy.laneFor(policy, r["task_id"] as String), r["selected_backend"])
        }
        assertEquals(192, out.listFiles()!!.count { it.name.endsWith(".result.json") })
        assertEquals(192, out.listFiles()!!.count { it.name.endsWith(".event.json") })
        assertEquals(0, out.listFiles()!!.count { it.name.endsWith(".part") })
        val warmups = TestJson.parse(File(out, "warmup.json").readText()) as List<*>
        assertEquals(keys * 2, warmups.size)
        assertTrue(warmups.map { it as Map<*, *> }.filter { (it["key"] as String).startsWith("classification") }.all { it["softmax_f32le_base64"] != null })
        val progress = File(out, "progress.jsonl").readLines()
        assertTrue(progress.size > 192 * 10)
        assertEquals(1, progress.count { it.contains("\"kind\":\"common_start\"") })
        assertTrue(progress.count { it.contains("\"kind\":\"power_sample\"") } > 10)
    }

    /** lane 겹침 초 = 그 정책의 두 lane 이 동시에 바쁜 시간 (busy = dispatch → lane_available). */
    private fun overlapNs(rows: List<Map<*, *>>, laneA: String, laneB: String): Long {
        fun intervals(lane: String) = rows.filter { it["selected_backend"] == lane }.map { ns(it, "dispatch_ns") to ns(it, "lane_available_ns") }.sortedBy { it.first }
        var total = 0L
        for ((a0, a1) in intervals(laneA)) for ((b0, b1) in intervals(laneB)) total += maxOf(0L, minOf(a1, b1) - maxOf(a0, b0))
        return total
    }

    @Test fun blockACpuCompletesSeriallyWithZeroOverlap() {
        val (out, _) = runCase("blockA_cpu", 0, "A", MixreqContract.POLICY_CPU, expectCompleted = true)
        assertCompletedShape(out, MixreqContract.POLICY_CPU, 4)
        assertEquals(0L, overlapNs(rows(out), "CPU", "GPU"))
        assertTrue(rows(out).all { it["selected_backend"] == "CPU" })
    }

    @Test fun blockAParOverlapsTheGpuAndCpuLanes() {
        val (out, _) = runCase("blockA_par", 1, "A", MixreqContract.POLICY_PAR, longDetection = true, expectCompleted = true)
        assertCompletedShape(out, MixreqContract.POLICY_PAR, 4)
        assertTrue(overlapNs(rows(out), "GPU", "CPU") > 0L)
        assertEquals(96, rows(out).count { it["selected_backend"] == "GPU" })
    }

    @Test fun blockNCpuKeepsFiveResidentRuntimesAndNeverUsesNpu() {
        val (out, _) = runCase("blockN_cpu", 8, "N", MixreqContract.POLICY_CPU, expectCompleted = true)
        assertCompletedShape(out, MixreqContract.POLICY_CPU, 5)
        assertEquals(0L, overlapNs(rows(out), "CPU", "NPU"))
    }

    @Test fun blockNParNpuOverlapsTheNpuAndCpuLanes() {
        val (out, _) = runCase("blockN_parnpu", 9, "N", MixreqContract.POLICY_PAR_NPU, longDetection = true, expectCompleted = true)
        assertCompletedShape(out, MixreqContract.POLICY_PAR_NPU, 5)
        assertTrue(overlapNs(rows(out), "NPU", "CPU") > 0L)
        assertEquals(96, rows(out).count { it["selected_backend"] == "NPU" })
        assertEquals(0, rows(out).count { it["selected_backend"] == "GPU" })
    }

    @Test fun npuCreationFailureInvalidatesTheBlockNSessionBeforeAnyRequest() {
        val (out, engine) = runCase("blockN_npu_create_fails", 10, "N", MixreqContract.POLICY_PAR_NPU, npuFails = true, expectCompleted = false)
        assertFalse(File(out, "summary.json").exists())
        assertFalse(File(out, "requests.json").exists())
        val cleanup = TestJson.parse(File(out, "cleanup.json").readText()) as Map<*, *>
        assertEquals("failed", cleanup["status"])
        assertTrue(cleanup["error"].toString().contains("creation failure"))
        val failure = TestJson.parse(File(out, "session_failure.json").readText()) as Map<*, *>
        assertEquals("runtime_setup", failure["phase"])
        assertTrue(engine.stop.get()!!.contains("creation failure"))
    }

    @Test fun pluggedDeviceStopsTheSessionInsideTheApp() {
        val (out, engine) = runCase("blockA_plugged", 2, "A", MixreqContract.POLICY_PAR, plugged = 1, expectCompleted = false)
        assertFalse(File(out, "summary.json").exists())
        assertEquals("environment/plugged_1", engine.stop.get())
        val cleanup = TestJson.parse(File(out, "cleanup.json").readText()) as Map<*, *>
        assertEquals("failed", cleanup["status"])
        assertEquals("environment/plugged_1", cleanup["stop_reason"])
    }

    @Test fun existingAttemptFolderRefusesToStart() {
        writeInputs()
        val bytes = manifestBytes(3, "A", MixreqContract.POLICY_CPU)
        val manifest = SessionManifest.parse(String(bytes)).also { it.validate() }
        val caseDir = File(root, "blockA_existing").apply { deleteRecursively(); mkdirs() }
        val out = File(caseDir, "a1").apply { mkdirs() }
        val engine = SessionEngine(manifest, bytes, caseDir, out, { error("never") }, { DecodedImage(2, 1, rgb) }, { snapshot() }, System::nanoTime)
        assertFalse(engine.run())
        assertTrue(engine.stop.get()!!.contains("attempt folder exists"))
        assertFalse(File(out, "progress.jsonl").exists())
    }

    @Test fun manifestValidationIsFailClosed() {
        writeInputs()
        fun parsed(mutate: (MutableMap<String, Any?>) -> Unit): SessionManifest {
            val m = TestJson.parse(String(manifestBytes(1, "A", MixreqContract.POLICY_PAR))) as Map<*, *>
            @Suppress("UNCHECKED_CAST") val mutable = LinkedHashMap(m as Map<String, Any?>)
            mutate(mutable)
            return SessionManifest.parse(Json.encode(mutable))
        }
        parsed { }.validate()
        for (mutate in listOf<(MutableMap<String, Any?>) -> Unit>(
            { it["policy"] = MixreqContract.POLICY_PAR_NPU },            // PAR-NPU is not a block A policy
            { it["block"] = "N" },                                           // block N needs 5 runtimes
            { it["split"] = MixreqContract.SPLIT_CONFIRMATION },             // confirmation forbids time_scale 10
            { it["session_index"] = 2 },                                     // sid is not uuid5(.../2)
            { it["sample_period_ms"] = 1000 },
            { (it["phases"] as Map<*, *>).let { p -> it["phases"] = LinkedHashMap(p as Map<String, Any?>).apply { this["common_s"] = 100 } } },
        )) {
            var threw = false
            try { parsed(mutate).validate() } catch (_: IllegalArgumentException) { threw = true } catch (_: IllegalStateException) { threw = true }
            assertTrue("mutation accepted", threw)
        }
    }
}
