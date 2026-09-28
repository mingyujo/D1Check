package com.example.d1check.npurunner

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.security.MessageDigest
import java.util.Base64

/** 연쇄 구간 목록 파서 (org.json 이 필요해 Robolectric). 2026-09-28 추가. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class NpuChainSpecTest {
    private val original = "models/mobilenet_v1_1.0_224.tflite"
    private val aot = "models/mobilenet_v1_1.0_224_Samsung_E9965.tflite"

    private fun segment(accelerator: String, model: String, duty: Int, seconds: Int) = JSONObject()
        .put("accelerator", accelerator).put("model", model).put("input_spec", "lcg-unit")
        .put("duty", duty).put("duration_s", seconds)

    private fun chain(vararg segments: JSONObject, prepare: String = "per_segment") = JSONObject()
        .put("schema", NpuChainSpec.SCHEMA).put("chain_id", "M2_heated_gpu_npu")
        .put("model_prepare", prepare).put("segments", JSONArray(segments.toList()))

    private fun sha(text: String): String =
        MessageDigest.getInstance("SHA-256").digest(text.toByteArray()).joinToString("") { "%02x".format(it) }

    private fun rejected(json: String): Boolean = try {
        NpuChainSpec.parse(json, sha(json))
        false
    } catch (expected: IllegalArgumentException) {
        true
    } catch (expected: org.json.JSONException) {
        true
    }

    @Test
    fun validChainParsesInOrderWithSums() {
        val json = chain(
            segment("GPU", original, 100, 30).put("label", "heat").put("gpu_precision", "FP32"),
            segment("NPU", aot, 100, 60).put("warmup", 5),
        ).toString()
        val spec = NpuChainSpec.parse(json, sha(json))
        assertEquals("M2_heated_gpu_npu", spec.chainId)
        assertEquals(ChainModelPrepare.PER_SEGMENT, spec.modelPrepare)
        assertEquals(listOf(TimedAccelerator.GPU, TimedAccelerator.NPU), spec.segments.map { it.accelerator })
        assertEquals(90L, spec.totalDurationSeconds)
        assertEquals("FP32", spec.segments[0].gpuPrecision)
        assertEquals(5, spec.segments[1].warmup(20))
        assertEquals(20, spec.segments[0].warmup(20))
        assertEquals(json, spec.json)
    }

    @Test
    fun base64TransportChecksTheSha() {
        val json = chain(segment("GPU", original, 10, 60), prepare = "upfront").toString()
        val b64 = Base64.getEncoder().encodeToString(json.toByteArray())
        val spec = NpuChainSpec.decode(b64, sha(json))
        assertEquals(ChainModelPrepare.UPFRONT, spec.modelPrepare)
        assertEquals(sha(json), spec.sha256)
        assertTrue(runCatching { NpuChainSpec.decode(b64, "0".repeat(64)) }.isFailure)
        assertTrue(runCatching { NpuChainSpec.decode("not base64!", sha(json)) }.isFailure)
    }

    @Test
    fun malformedChainsFailClosed() {
        val good = segment("GPU", original, 100, 30)
        val cases = mapOf(
            "AOT on GPU" to chain(segment("GPU", aot, 100, 30)),
            "original on NPU" to chain(segment("NPU", original, 100, 30)),
            "unknown segment key" to chain(segment("GPU", original, 100, 30).put("dutty", 50)),
            "unknown top key" to chain(good).put("extra", 1),
            "no model_prepare" to chain(good).apply { remove("model_prepare") },
            "bad model_prepare" to chain(good, prepare = "lazy"),
            "wrong schema" to chain(good).put("schema", "d1-npu-chain-v0"),
            "duty 0" to chain(segment("GPU", original, 0, 30)),
            "string duty" to chain(segment("GPU", original, 100, 30).put("duty", "100")),
            "both model and path" to chain(segment("GPU", original, 100, 30).put("model_path", "/data/local/tmp/x.tflite")),
            "precision on NPU" to chain(segment("NPU", aot, 100, 30).put("gpu_precision", "FP32")),
            "bad input spec" to chain(segment("GPU", original, 100, 30).put("input_spec", "rgb")),
            "sum over 3600 s" to chain(segment("GPU", original, 100, 3000), segment("GPU", original, 10, 601)),
            "no segments" to chain(),
            "fallback list" to chain(segment("NPU,CPU", aot, 100, 30)),
        )
        for ((name, value) in cases) assertTrue(name, rejected(value.toString()))
    }

    @Test
    fun parserTiesTheChainToTheSlotDuration() {
        val json = chain(segment("GPU", original, 10, 60), segment("GPU", original, 100, 240)).toString()
        fun extras(duration: Long, duty: Int = 100) = mutableMapOf<String, Any?>(
            "d1_auto_start" to true, "d1_resource" to "NPU",
            "d1_npu_model_asset" to NpuRunConfig.DEFAULT_MODEL_ASSET,
            "d1_limit_mode" to "DURATION", "d1_duration_s" to duration, "d1_warmup_count" to 20,
            "d1_run_id" to "11111111-1111-4111-8111-111111111111",
            "d1_command_id" to "22222222-2222-4222-8222-222222222222",
            "d1_experiment_mode" to "BASIC", "d1_duty_cycle_percent" to duty, "d1_duty_cycle_period_s" to 10.0f,
            "d1_npu_chain_b64" to Base64.getEncoder().encodeToString(json.toByteArray()),
            "d1_npu_chain_sha256" to sha(json),
        )
        val config = checkNotNull(NpuAutomationIntentParser.parse(extras(300L)))
        assertEquals(2, checkNotNull(config.chain).segments.size)
        // 슬롯 길이 ≠ Σ 구간, 슬롯 duty ≠ 100, 단일 구간 옵션과 섞기 → 거부
        for (bad in listOf(
            extras(301L), extras(300L, duty = 50),
            extras(300L).apply { put("d1_npu_accelerator", "GPU") },
            extras(300L).apply { put("d1_npu_run_only_span", true) },
            extras(300L).apply { put("d1_npu_input_spec", "lcg-rgb-127-128") },
        )) {
            assertTrue(runCatching { NpuAutomationIntentParser.parse(bad) }.isFailure)
        }
    }
}
