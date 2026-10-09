package com.example.d1check.qualityrunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Test

/** Q2: manifest 검증 (fail-closed) — 정상은 통과, 어긋난 것은 하나하나 거부. */
class QualityManifestTest {
    @Suppress("UNCHECKED_CAST")
    private fun runtimes(m: MutableMap<String, Any?>) = m["runtimes"] as MutableMap<String, Any?>
    @Suppress("UNCHECKED_CAST")
    private fun runtime(m: MutableMap<String, Any?>, backend: String) = runtimes(m)[backend] as MutableMap<String, Any?>
    @Suppress("UNCHECKED_CAST")
    private fun samples(m: MutableMap<String, Any?>) = m["samples"] as MutableList<MutableMap<String, Any?>>

    private fun parsed(mutate: (MutableMap<String, Any?>) -> Unit = {}): QualityManifest =
        QualityManifest.parse(TestFixtures.build(mutate = mutate).manifestText)

    @Test fun validManifestParsesAndValidates() {
        val m = parsed()
        m.validate()
        assertEquals(20, m.samples.size)
        assertEquals(setOf("CPU", "GPU", "NPU"), m.runtimes.keys)
        assertEquals(1, m.runtimeFor("CPU").cpuThreads)
        assertEquals("FP32", m.runtimeFor("GPU").gpuPrecision)
        assertNull(m.runtimeFor("NPU").gpuPrecision)
        assertNull(m.runtimeFor("NPU").cpuThreads)
        assertEquals(listOf("NPU", "CPU"), m.runtimeFor("NPU").acceleratorsPassedToNative())
        assertEquals(listOf("GPU"), m.runtimeFor("GPU").acceleratorsPassedToNative())
        assertEquals("efficientnet_lite0_Samsung_E9965", m.runtimeFor("NPU").modelId)
        assertEquals(listOf("NPU"), m.runtimeFor("NPU").optionsRecord()["accelerators_requested"])
    }

    @Test fun rejectsEveryContractViolation() {
        fun rejected(label: String, mutate: (MutableMap<String, Any?>) -> Unit) {
            val thrown = runCatching { parsed(mutate).validate() }.exceptionOrNull()
            check(thrown is IllegalArgumentException || thrown is IllegalStateException || thrown is NoSuchElementException || thrown is NullPointerException) { "$label was not rejected: $thrown" }
        }
        rejected("protocol") { it["protocol"] = "other" }
        rejected("19 samples") { samples(it).removeAt(19) }
        rejected("duplicate id") { samples(it)[1]["sample_id"] = samples(it)[0]["sample_id"] }
        rejected("index order") { samples(it)[3]["index"] = 4L }
        rejected("input bytes") { samples(it)[0]["input_bytes"] = 602_111L }
        rejected("sha format") { samples(it)[0]["input_sha256"] = "zz" }
        rejected("runs 3") { it["runs_per_image"] = 3L }
        rejected("output 1001") { it["output_elements"] = 1001L }
        rejected("missing NPU") { runtimes(it).remove("NPU") }
        rejected("extra backend") { runtimes(it)["DSP"] = runtime(it, "CPU") }
        rejected("CPU threads 2") { runtime(it, "CPU")["cpu_threads"] = 2L }
        rejected("CPU threads absent") { runtime(it, "CPU").remove("cpu_threads") }
        rejected("GPU FP16") { runtime(it, "GPU")["gpu_precision"] = "FP16" }
        rejected("GPU precision absent") { runtime(it, "GPU").remove("gpu_precision") }
        rejected("NPU opens original") { runtime(it, "NPU")["model_path"] = runtime(it, "CPU")["model_path"] }
        rejected("CPU opens AOT") { runtime(it, "CPU")["model_path"] = runtime(it, "NPU")["model_path"] }
        rejected("GPU different model sha") { runtime(it, "GPU")["model_sha256"] = "1".repeat(64) }
        rejected("key/backend mismatch") { runtime(it, "GPU")["key"] = "classification_CPU" }
        rejected("task mismatch") { runtime(it, "GPU")["key"] = "detection_GPU"; runtime(it, "GPU")["task"] = "detection" }
        rejected("gpu_precision on CPU") { runtime(it, "CPU")["gpu_precision"] = "FP32" }
    }
}
