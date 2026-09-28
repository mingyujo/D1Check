package com.example.d1check.npurunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class NpuRunMetadataTest {
    private val config = NpuRunConfig(
        limit = RunLimit.Duration(60),
        warmupCount = 20,
        experimentMode = ExperimentMode.BASIC,
        expectedRunId = "11111111-1111-4111-8111-111111111111",
        commandId = "22222222-2222-4222-8222-222222222222",
        dutyCyclePercent = 100,
    )
    private val outcome = NpuRunMetadata.LoadOutcome(
        terminationReason = TerminationReason.DURATION_COMPLETE,
        targetDurationNs = 60_000_000_000L,
        actualLoadDurationNs = 60_000_100_000L,
        durationOverrunNs = 100_000L,
        dutyMetrics = DutyCycleTracker(100, 10_000_000_000L, 0L, 60_000_000_000L)
            .metrics(60_000_100_000L),
        completedInferenceCount = 1234,
        runnerSessionId = "33333333-3333-4333-8333-333333333333",
        lifecycleEventCount = 30,
        experimentValid = true,
        invalidReason = null,
    )
    private val facts = NpuRunMetadata.NpuFacts(
        modelId = "mobilenet_v1_1.0_224_Samsung_E9965",
        modelSha256 = "1415b2c87d01b67a9380b8f912e2b4ef4561502105b06f313332c97c1c8cb5cf",
        modelSource = NpuRunConfig.DEFAULT_MODEL_ASSET,
        dispatchLibSha256 = "f08656a642c46e7b06b64fbe1e0800de9e73b0b69c1641b87995562b4a16840f",
        aotPartition = mapOf("dispatch_ops" to 1, "non_dispatch_ops" to 0),
        availableAccelerators = "NPU,GPU,CPU",
        envInitMs = 4.8, modelInitMs = 33.9, bufferInitMs = 0.3,
        inputSpec = NpuDeterministicInput.InputSpec.LCG_UNIT,
        inputElements = 150528,
        inputSha256 = "5dc1cb09d712429fa580bdb7976c01d3933956d77002a8c8ab3c82c40f3899f3",
    )
    private val pilot = PilotSafetyPolicy.evaluate(PilotSafetySnapshot(0, 0, 3, 80, 30.0))

    /** benchmark-runner GpuBenchmarkEngine outputConfig 의 키와 순서 (2026-09-24 기준). */
    private val benchmarkOutputConfigKeys = listOf(
        "precision", "limit_mode", "requested_inference_count", "requested_duration_s",
        "target_duration_ns", "actual_load_duration_ns", "duration_overrun_ns", "termination_reason",
        "warmup_count", "baseline_s", "experiment_mode", "perfetto_requested_by_runner",
        "completed_inference_count", "runner_session_id", "litert_version", "experiment_valid",
        "invalid_reason", "lifecycle_event_count", "resource_legacy_alias", "cpu_threads", "cpu_affinity",
        "gpu_delegate_profile", "auto_start", "expected_run_id", "command_id",
        "requested_duty_cycle_percent", "duty_cycle_period_ns", "duty_cycle_applied",
        "target_active_duration_ns", "actual_active_duration_ns", "actual_idle_duration_ns",
        "achieved_duty_cycle_percent", "completed_duty_cycle_count", "duty_cycle_active_overrun_ns",
        "accuracy_preflight", "energy_measurement",
        "gpu_compatibility_policy_id", "gpu_compatibility_list_supported",
        "gpu_compatibility_list_query_error", "gpu_compatibility_list_enforced",
    )

    @Test
    fun benchmarkRunnerKeysComeFirstInTheSameOrder() {
        val keys = NpuRunMetadata.build(config, outcome, pilot, facts).keys.toList()
        assertEquals(benchmarkOutputConfigKeys, keys.take(benchmarkOutputConfigKeys.size))
        assertTrue(keys.containsAll(pilot.metadata().keys))
    }

    @Test
    fun valueRulesFollowBenchmarkRunner() {
        val m = NpuRunMetadata.build(config, outcome, pilot, facts)
        assertEquals("DURATION", m["limit_mode"])
        assertEquals(60L, m["requested_duration_s"])
        assertEquals("duration_complete", m["termination_reason"])
        assertNull(m["cpu_threads"])
        assertEquals("NONE", m["cpu_affinity"])
        assertNull(m["gpu_delegate_profile"])
        assertEquals(true, m["auto_start"])
        assertEquals("BASIC", m["experiment_mode"])
        assertEquals(10_000_000_000L, m["duty_cycle_period_ns"])
        assertEquals(0L, m["actual_idle_duration_ns"])
        val accuracy = m["accuracy_preflight"] as Map<*, *>
        assertEquals("not_run", accuracy["status"])
        assertEquals("timed_run_does_not_execute_preflight", accuracy["validation_scope"])
        val energy = m["energy_measurement"] as Map<*, *>
        assertEquals("raw_unverified", energy["status"])
        assertEquals(false, energy["current_unit_verified"])
        assertEquals(false, energy["charge_counter_unit_verified"])
        assertEquals(false, energy["calculation_performed"])
        assertEquals(true, m["pilot_safety_pass"])
        assertEquals(true, m["formal_energy_eligible"])
    }

    @Test
    fun npuFieldsForFormalNpuValid() {
        val m = NpuRunMetadata.build(config, outcome, pilot, facts)
        assertEquals("2.2.0", m["litert_version"])
        assertEquals("litert-compiled-model", m["engine"])
        assertEquals(facts.dispatchLibSha256, m["npu_dispatch_lib_sha256"])
        assertEquals(mapOf("dispatch_ops" to 1, "non_dispatch_ops" to 0), m["npu_model_partition"])
        assertEquals("lcg-unit", m["npu_input_spec"])
        assertEquals(facts.inputSha256, m["npu_input_sha256"])
        // model_sha256 / model_id / resource 는 GpuTelemetry.flushAfterRun 이 인자로 넣는다 (config 에 두지 않는다)
        assertFalse(m.containsKey("model_sha256"))
        assertFalse(m.containsKey("resource"))
    }

    @Test
    fun failedRunWithoutFactsStillProducesAWellFormedRecord() {
        val failed = outcome.copy(
            terminationReason = TerminationReason.PILOT_SAFETY_REJECTED, dutyMetrics = null,
            experimentValid = false, invalidReason = "pilot_safety_rejected", completedInferenceCount = 0,
        )
        val m = NpuRunMetadata.build(config, failed, null, null)
        assertEquals("pilot_safety_rejected", m["termination_reason"])
        assertEquals(false, m["experiment_valid"])
        assertEquals("NONE", m["safety_policy_scope"])
        assertNull(m["npu_dispatch_lib_sha256"])
        assertEquals(NpuRunConfig.DEFAULT_MODEL_ASSET, m["npu_model_source"])
    }

    // ---- 2026-09-28 (GPU 가속기 · 추론 수 상한)

    private val newKeys = listOf(
        "compiled_model_options", "precision_record", "max_inference_spans",
        "max_inference_spans_buffer_bytes", "jvm_max_memory_bytes",
    )

    @Test
    fun defaultNpuAndCpuRunsCarryNoNewKeysAndTheSameValues() {
        for (cfg in listOf(config, config.copy(accelerator = TimedAccelerator.CPU))) {
            val m = NpuRunMetadata.build(cfg, outcome, pilot, facts.copy(jvmMaxMemoryBytes = 1L))
            for (key in newKeys) assertFalse(key, m.containsKey(key))
            assertEquals("aot", m["npu_compile_mode"])
            assertEquals("fp16(compiler-default)", m["npu_precision"])
        }
    }

    @Test
    fun gpuRunRecordsOptionsAndPrecisionFourItems() {
        val gpu = config.copy(accelerator = TimedAccelerator.GPU, modelAsset = "models/mobilenet_v1_1.0_224.tflite")
        val m = NpuRunMetadata.build(gpu, outcome, pilot, facts)
        assertEquals("GPU", m["npu_accelerator_requested"])
        assertEquals("gpu_compiled_model", m["npu_timed_resource_label"])
        val options = m["compiled_model_options"] as Map<*, *>
        assertEquals(listOf("GPU"), options["accelerators_passed_to_native"])
        assertEquals("not_set (LiteRT default)", options["gpu_options"])
        val record = m["precision_record"] as Map<*, *>
        assertEquals(listOf("schema", "storage", "io_dtype", "options", "internal_compute"), record.keys.toList())
        assertEquals("unknown", (record["internal_compute"] as Map<*, *>)["value"])
        // 키 자리는 benchmark-runner 순서 그대로
        assertEquals(benchmarkOutputConfigKeys, m.keys.toList().take(benchmarkOutputConfigKeys.size))
        val fp32 = NpuRunMetadata.build(gpu.copy(gpuPrecision = "FP32"), outcome, pilot, facts)
        assertEquals(mapOf("precision" to "FP32"), (fp32["compiled_model_options"] as Map<*, *>)["gpu_options"])
    }

    @Test
    fun nativeAcceleratorSetFollowsTheLiteRtKotlinLayer() {
        // litert-api 2.2.0 javap: 원소 하나인 {NPU} 만 {NPU, CPU} 로 바뀐다
        assertEquals(listOf("NPU", "CPU"), CompiledModelFacts.nativeAccelerators(TimedAccelerator.NPU))
        assertEquals(listOf("GPU"), CompiledModelFacts.nativeAccelerators(TimedAccelerator.GPU))
        assertEquals(listOf("CPU"), CompiledModelFacts.nativeAccelerators(TimedAccelerator.CPU))
    }

    @Test
    fun raisedSpanCapIsRecordedWithTheHeap() {
        val m = NpuRunMetadata.build(
            config.copy(maxInferenceSpans = 2_000_000), outcome, pilot, facts.copy(jvmMaxMemoryBytes = 536_870_912L),
        )
        assertEquals(2_000_000, m["max_inference_spans"])
        assertEquals(56_000_000L, m["max_inference_spans_buffer_bytes"])
        assertEquals(536_870_912L, m["jvm_max_memory_bytes"])
    }
}
