package com.example.d1check.requestrunner

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File

/**
 * M5 Q1 (폰 없이): Q20 manifest 꼴 파싱 · 검증 (혼합 요청 설정만 받음) · 엔진이 Q20 결과 형식 (result.json · run0/run1 f32le · summary.json) 을 쓰는지 ·
 * png_check (요청 경로 TaskRuntime.execute) 가 텐서 입력 run0 과 나란히 적히는지. 가짜 runtime = 입력 합에 따라 바뀌는 고정 softmax (시험용 숫자).
 * 산출물은 build/q1-roundtrip/<case>/ 에 남겨 호스트 쪽 (statesplit_q1.py --selftest-dir) 이 q20_judge 형식으로 다시 읽는다.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class InputListEngineTest {
    private val root = File(File(".").absoluteFile, "build/q1-roundtrip")

    private class FakeRuntime(override val spec: RuntimeSpec) : InferenceRuntime {
        override fun inputElementCount() = 224 * 224 * 3
        override fun run(input: FloatArray): List<FloatArray> {
            require(input.size == inputElementCount())
            val s = input.sum()
            return listOf(FloatArray(1000) { i -> if (i == 518) 0.5f else 0.0005f + (i % 7) * 1e-5f + s * 1e-9f })
        }
        override fun initRecord(): Map<String, Any?> = mapOf("engine" to "fake")
        override fun close() {}
    }

    private val rgb = ByteArray(4 * 3 * 3) { (it * 7).toByte() }

    private fun fixture(case: String, withPng: Boolean, gpuPrecision: String = "FP32"): Pair<File, String> {
        val dir = File(root, case).apply { deleteRecursively(); mkdirs() }
        val inputs = File(dir, "_inputs").apply { mkdirs() }
        val model = File(inputs, "efficientnet_lite0.tflite").apply { writeBytes(byteArrayOf(1, 2, 3)) }
        val aot = File(inputs, "efficientnet_lite0_Samsung_E9965.tflite").apply { writeBytes(byteArrayOf(4, 5, 6)) }
        val tensor = ImageContract.tensorFor("classification", rgb, 4, 3)
        val samples = (0 until 20).map { i ->
            val id = "%016x".format(0x00575b9132bb3746L + i)
            val bytes = SessionEngine.floatBytes(if (i == 0) tensor else FloatArray(224 * 224 * 3) { (it % 13) * 0.01f + i })
            val f = File(inputs, "$id.f32le").apply { writeBytes(bytes) }
            JSONObject(mapOf("index" to i, "sample_id" to id, "input_path" to f.absolutePath, "input_bytes" to bytes.size,
                "input_sha256" to ImageContract.sha256(bytes)))
        }
        fun rt(b: String, path: File, extra: Map<String, Any>) = JSONObject(mapOf("key" to "classification_$b", "task" to "classification",
            "backend" to b, "model_path" to path.absolutePath, "model_sha256" to TaskRuntime.sha256(path)) + extra)
        val m = JSONObject()
        m.put("protocol", "s26-q20-manifest-v1"); m.put("input_elements", 150_528); m.put("input_bytes", 602_112)
        m.put("output_elements", 1000); m.put("runs_per_image", 2)
        m.put("runtimes", JSONObject(mapOf("CPU" to rt("CPU", model, mapOf("cpu_threads" to 1)),
            "GPU" to rt("GPU", model, mapOf("gpu_precision" to gpuPrecision)), "NPU" to rt("NPU", aot, emptyMap()))))
        m.put("samples", org.json.JSONArray(samples))
        if (withPng) {
            val png = File(inputs, "x.png").apply { writeBytes(SessionRoundTripTest.canonicalPng(4, 3, rgb)) }
            val labels = File(inputs, "labels.txt").apply { writeText((0 until 1000).joinToString("\n") { "c$it" } + "\n") }
            m.put("png_check", JSONObject(mapOf("sample_id" to "%016x".format(0x00575b9132bb3746L), "image_path" to png.absolutePath,
                "image_sha256" to TaskRuntime.sha256(png), "labels_path" to labels.absolutePath, "labels_sha256" to TaskRuntime.sha256(labels))))
        }
        return dir to m.toString()
    }

    private fun engine(dir: File, text: String, backend: String) = InputListEngine(
        manifest = InputListManifest.parse(text).also { it.validate() }, manifestBytes = text.toByteArray(), backend = backend, runId = "selftest",
        outRoot = File(dir, backend), runtimeFactory = { FakeRuntime(it) }, decodeImage = { DecodedImage(4, 3, rgb) }, now = System::nanoTime,
        identity = emptyMap(), log = {},
    )

    @Test fun writesQ20FormatAndPngCheck() {
        val (dir, text) = fixture("ok", withPng = true)
        for (b in listOf("CPU", "GPU", "NPU")) assertTrue(engine(dir, text, b).run())
        val out = File(dir, "NPU")
        val summary = JSONObject(File(out, "summary.json").readText())
        assertEquals("completed", summary.getString("status"))
        assertEquals("s26-q20-summary-v1", summary.getString("schema"))
        assertTrue(summary.getBoolean("runtime_created"))
        val r0 = JSONObject(File(out, "00_00575b9132bb3746.result.json").readText())
        assertEquals("s26-q20-image-result-v1", r0.getString("schema"))
        assertEquals(2, r0.getJSONArray("runs").length())
        assertTrue(r0.getBoolean("bit_identical_runs"))
        assertEquals(4000L, File(out, "00_00575b9132bb3746.run0.f32le").length())
        assertEquals(20, out.listFiles()!!.count { it.name.endsWith(".result.json") })
        val png = JSONObject(File(out, "png_check.json").readText())
        assertEquals("ok", png.getString("status"))
        assertTrue(png.getBoolean("input_tensor_equal"))
        assertTrue(png.getBoolean("output_equal"))
        assertFalse(File(out, "00_00575b9132bb3746.failure.json").exists())
    }

    @Test fun refusesSettingsOtherThanTheMixreqOnes() {
        val (_, fp16) = fixture("fp16", withPng = false, gpuPrecision = "FP16")
        assertThrows(IllegalArgumentException::class.java) { InputListManifest.parse(fp16).validate() }
        val (dir, text) = fixture("exists", withPng = false)
        File(dir, "CPU").mkdirs()
        assertThrows(IllegalStateException::class.java) { engine(dir, text, "CPU").run() }
    }
}
