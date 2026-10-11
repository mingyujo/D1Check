package com.example.d1check.qualityrunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** M5 Q2: specOverride (GPU 정밀도만 바꾼 spec) 가 runtime 에 그대로 가고 summary 의 compiled_model_options 에 적힌다 · 없으면 Q20 그대로. */
class Q2PrecisionOverrideTest {
    @Suppress("UNCHECKED_CAST")
    private fun json(f: File) = MiniJson.parse(f.readText()) as Map<String, Any?>

    private fun run(built: TestFixtures.Built, case: String, override: RuntimeSpec?): Pair<RuntimeSpec, Map<String, Any?>> {
        val out = File(built.root, "out/q2_$case/GPU")
        var seen: RuntimeSpec? = null
        var clock = 0L
        val ok = QualityEngine(
            manifest = QualityManifest.parse(built.manifestText).also { it.validate() }, manifestBytes = built.manifestFile.readBytes(),
            backend = "GPU", runId = "q2_$case", outRoot = out, runtimeFactory = { spec -> seen = spec; FakeRuntime(spec) },
            now = { clock += 1_000; clock }, wallClock = { "2026-10-12T00:00:00.000+09:00" }, identity = emptyMap(), log = {},
            specOverride = override,
        ).run()
        assertTrue(ok)
        @Suppress("UNCHECKED_CAST")
        return seen!! to (json(File(out, "summary.json"))["compiled_model_options"] as Map<String, Any?>)
    }

    @Test fun overrideReachesTheRuntimeAndTheSummary() {
        val built = TestFixtures.build()
        val base = QualityManifest.parse(built.manifestText).runtimeFor("GPU")
        val (q20, q20Options) = run(built, "default", null)
        assertEquals("FP32", q20.gpuPrecision)
        @Suppress("UNCHECKED_CAST")
        assertEquals("FP32", (q20Options["gpu_options"] as Map<String, Any?>)["precision"])
        val (none, noneOptions) = run(built, "none", base.copy(gpuPrecision = null))
        assertNull(none.gpuPrecision)
        assertNull(noneOptions["gpu_options"])
        val (fp16, fp16Options) = run(built, "fp16", base.copy(gpuPrecision = "FP16"))
        assertEquals("FP16", fp16.gpuPrecision)
        @Suppress("UNCHECKED_CAST")
        assertEquals("FP16", (fp16Options["gpu_options"] as Map<String, Any?>)["precision"])
        assertEquals(base.modelSha256, fp16.modelSha256)
    }
}
