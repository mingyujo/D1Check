package com.example.d1check.npurunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class NpuAutomationIntentParserTest {
    private val runId = "11111111-1111-4111-8111-111111111111"
    private val commandId = "22222222-2222-4222-8222-222222222222"

    /**
     * tools/d1_experiment_orchestrator.py runner_intent_arguments("NPU", ...) 가 보내는 extra 와 같은 타입
     * (--ez / --es / --el / --ei / --ef). Activity 는 이 타입대로 getXxxExtra 로 읽어 파서에 넘긴다.
     */
    private fun orchestratorExtras(): MutableMap<String, Any?> = mutableMapOf(
        "d1_auto_start" to true,
        "d1_resource" to "NPU",
        "d1_npu_model_asset" to "models/mobilenet_v1_1.0_224_Samsung_E9965.tflite",
        "d1_limit_mode" to "DURATION",
        "d1_duration_s" to 600L,
        "d1_warmup_count" to 20,
        "d1_run_id" to runId,
        "d1_command_id" to commandId,
        "d1_experiment_mode" to "BASIC",
        "d1_duty_cycle_percent" to 50,
        "d1_duty_cycle_period_s" to 10.0f,
    )

    @Test
    fun orchestratorNpuIntentParses() {
        val config = requireNotNull(NpuAutomationIntentParser.parse(orchestratorExtras()))
        assertEquals(RunLimit.Duration(600L), config.limit)
        assertEquals(20, config.warmupCount)
        assertEquals(ExperimentMode.BASIC, config.experimentMode)
        assertEquals(runId, config.expectedRunId)
        assertEquals(commandId, config.commandId)
        assertEquals(50, config.dutyCyclePercent)
        assertEquals(10.0, config.dutyCyclePeriodSeconds, 0.0)
        assertEquals("NPU", config.resource)
        assertTrue(config.isAutomated)
        assertEquals(NpuDeterministicInput.InputSpec.LCG_UNIT, config.inputSpec)
    }

    @Test
    fun withoutAutoStartTheSmokePathKeepsTheIntent() {
        assertNull(NpuAutomationIntentParser.parse(mapOf("accelerator" to "NPU", "quality_n" to 32)))
        assertNull(NpuAutomationIntentParser.parse(orchestratorExtras().apply { put("d1_auto_start", false) }))
    }

    @Test
    fun defaultsMatchBenchmarkRunner() {
        val extras = orchestratorExtras().apply {
            remove("d1_limit_mode"); remove("d1_warmup_count"); remove("d1_experiment_mode")
            remove("d1_duty_cycle_percent"); remove("d1_duty_cycle_period_s"); remove("d1_npu_model_asset")
        }
        val config = requireNotNull(NpuAutomationIntentParser.parse(extras))
        assertEquals(RunLimit.Duration(600L), config.limit)
        assertEquals(20, config.warmupCount)
        assertEquals(100, config.dutyCyclePercent)
        assertEquals(10.0, config.dutyCyclePeriodSeconds, 0.0)
        assertEquals(NpuRunConfig.DEFAULT_MODEL_ASSET, config.modelAsset)
    }

    @Test
    fun countModeAndModelPath() {
        val extras = orchestratorExtras().apply {
            put("d1_limit_mode", "COUNT"); put("d1_inference_count", 1000)
            put("d1_npu_model_path", "/data/local/tmp/efficientdet_lite0_Samsung_E9965.tflite")
            put("d1_npu_input_spec", "lcg-rgb-127.5-127.5")
        }
        val config = requireNotNull(NpuAutomationIntentParser.parse(extras))
        assertEquals(RunLimit.Count(1000), config.limit)
        assertEquals("/data/local/tmp/efficientdet_lite0_Samsung_E9965.tflite", config.modelSource)
        assertEquals(NpuDeterministicInput.InputSpec.LCG_RGB_1275_1275, config.inputSpec)
    }

    @Test
    fun cpuGpuAndMalformedRequestsAreRejected() {
        val cases = listOf(
            orchestratorExtras().apply { put("d1_resource", "GPU") },
            orchestratorExtras().apply { put("d1_resource", "CPU") },
            orchestratorExtras().apply { put("d1_cpu_threads", 4) },
            orchestratorExtras().apply { put("d1_gpu_profile", "gpu-compat-default-v1") },
            orchestratorExtras().apply { put("d1_run_id", "not-a-uuid") },
            orchestratorExtras().apply { remove("d1_command_id") },
            orchestratorExtras().apply { put("d1_limit_mode", "FOREVER") },
            orchestratorExtras().apply { put("d1_duty_cycle_percent", 0) },
            orchestratorExtras().apply { put("d1_npu_input_spec", "rgb") },
            orchestratorExtras().apply { put("d1_duration_s", 0L) },
        )
        for (extras in cases) {
            try {
                NpuAutomationIntentParser.parse(extras)
                throw AssertionError("accepted: $extras")
            } catch (expected: IllegalArgumentException) {
                // fail closed
            }
        }
    }
}
