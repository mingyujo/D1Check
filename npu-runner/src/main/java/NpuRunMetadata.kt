package com.example.d1check.npurunner

/*
 * timed run 의 run_metadata config 맵. GpuTelemetry.flushAfterRun(config=) 에 그대로 넘긴다.
 * 미러 원본: benchmark-runner/.../GpuBenchmarkEngine.kt 의 outputConfig + GpuCompatibilityPolicy
 * .notEvaluatedMetadata() + PilotSafetyCheck.metadata(). 키 이름·순서·값 규칙은 원본과 같고,
 * NPU 전용 필드는 맨 뒤에 붙인다 (tools/d1_logger_v4.py formal_npu_valid 가 읽는 것).
 * Android 의존이 없어 JVM 단위 테스트로 고정한다.
 */
internal object NpuRunMetadata {
    const val LITERT_VERSION = "2.2.0" // gradle/libs.versions.toml litertNext 와 같아야 한다
    const val ENGINE = "litert-compiled-model"
    const val BASELINE_S = 60L
    const val DISPATCH_LIB_FILE = "libLiteRtDispatch_Samsung.so"
    const val DISPATCH_LIB_SOURCE = "LiteRT main@9380426b, Bazel 7.7.0, NDK r27c (s26/npu/artifacts/litert_samsung_arm64/README.md)"
    // benchmark-runner s26/GpuCompatibilityPolicy.POLICY_ID. NPU 는 GPU 호환 목록을 평가하지 않는다.
    private const val GPU_COMPAT_POLICY_ID = "s26-compat-list-advisory-v1"

    /** 모델·dispatch·입력에 대한 사실. 타이밍 루프 밖에서 한 번 계산한다. */
    data class NpuFacts(
        val modelId: String,
        val modelSha256: String,
        val modelSource: String,
        val dispatchLibSha256: String?,
        /** aot_manifest.json 에서 이 모델 SHA 의 출력 항목. 없으면 null (formal_npu_valid 4번에서 걸린다). */
        val aotPartition: Map<String, Any?>?,
        val availableAccelerators: String?,
        val envInitMs: Double?,
        val modelInitMs: Double?,
        val bufferInitMs: Double?,
        val inputSpec: NpuDeterministicInput.InputSpec,
        val inputElements: Int?,
        val inputSha256: String?,
        val modelSizeBytes: Long? = null,
        /** Runtime.maxMemory() (2026-09-28 추가). 상한 옵션을 쓴 런에만 기록한다. */
        val jvmMaxMemoryBytes: Long? = null,
    )

    data class LoadOutcome(
        val terminationReason: TerminationReason?,
        val targetDurationNs: Long?,
        val actualLoadDurationNs: Long?,
        val durationOverrunNs: Long?,
        val dutyMetrics: DutyCycleMetrics?,
        val completedInferenceCount: Int,
        val runnerSessionId: String,
        val lifecycleEventCount: Int,
        val experimentValid: Boolean,
        val invalidReason: String?,
    )

    fun build(
        config: NpuRunConfig,
        outcome: LoadOutcome,
        pilotSafety: PilotSafetyCheck?,
        facts: NpuFacts?,
    ): LinkedHashMap<String, Any?> {
        val accuracyPreflight = linkedMapOf<String, Any?>(
            "schema_version" to 2,
            "validation_scope" to "timed_run_does_not_execute_preflight",
            "status" to "not_run",
            "synthetic_numerical_check" to mapOf("status" to "not_run"),
            "representative_input_equivalence" to mapOf("status" to "not_run"),
            "task_accuracy_check" to mapOf("status" to "not_run"),
            "formal_gate_result" to mapOf("status" to "not_run"),
            "note" to "experiment-level preflight is attached by the host; timed loop is isolated",
        )
        val energyMeasurement = linkedMapOf<String, Any?>(
            "status" to "raw_unverified",
            "current_raw_policy" to "raw_unscaled_unit_unverified",
            "voltage_available" to null,
            "current_unit_verified" to false,
            "charge_counter_unit_verified" to false,
            "calculation_performed" to false,
            "note" to "no J or mWh result is produced before unit calibration",
        )
        val dutyMetrics = outcome.dutyMetrics
        val values = linkedMapOf<String, Any?>(
            "precision" to config.precision,
            "limit_mode" to config.limit.modeName,
            "requested_inference_count" to (config.limit as? RunLimit.Count)?.inferenceCount,
            "requested_duration_s" to (config.limit as? RunLimit.Duration)?.durationSeconds,
            "target_duration_ns" to outcome.targetDurationNs,
            "actual_load_duration_ns" to outcome.actualLoadDurationNs,
            "duration_overrun_ns" to outcome.durationOverrunNs,
            "termination_reason" to
                (outcome.terminationReason ?: TerminationReason.RUN_ERROR).wireName,
            "warmup_count" to config.warmupCount,
            "baseline_s" to BASELINE_S,
            "experiment_mode" to config.experimentMode.name,
            "perfetto_requested_by_runner" to (config.experimentMode == ExperimentMode.DIAGNOSTIC),
            "completed_inference_count" to outcome.completedInferenceCount,
            "runner_session_id" to outcome.runnerSessionId,
            "litert_version" to LITERT_VERSION,
            "experiment_valid" to outcome.experimentValid,
            "invalid_reason" to outcome.invalidReason,
            "lifecycle_event_count" to outcome.lifecycleEventCount,
            "resource_legacy_alias" to null,
            "cpu_threads" to null,
            "cpu_affinity" to "NONE",
            "gpu_delegate_profile" to null,
            "auto_start" to config.isAutomated,
            "expected_run_id" to config.expectedRunId,
            "command_id" to config.commandId,
            "requested_duty_cycle_percent" to config.dutyCyclePercent,
            "duty_cycle_period_ns" to DutyCycleTracker.periodNanos(config.dutyCyclePeriodSeconds),
            "duty_cycle_applied" to (config.limit is RunLimit.Duration),
            "target_active_duration_ns" to dutyMetrics?.targetActiveDurationNs,
            "actual_active_duration_ns" to dutyMetrics?.actualActiveDurationNs,
            "actual_idle_duration_ns" to dutyMetrics?.actualIdleDurationNs,
            "achieved_duty_cycle_percent" to dutyMetrics?.achievedPercent,
            "completed_duty_cycle_count" to dutyMetrics?.completedCycleCount,
            "duty_cycle_active_overrun_ns" to dutyMetrics?.activeOverrunNs,
            "accuracy_preflight" to accuracyPreflight,
            "energy_measurement" to energyMeasurement,
            // GpuCompatibilityPolicy.notEvaluatedMetadata() — CPU run 과 같은 "평가 안 함" 값
            "gpu_compatibility_policy_id" to GPU_COMPAT_POLICY_ID,
            "gpu_compatibility_list_supported" to null,
            "gpu_compatibility_list_query_error" to null,
            "gpu_compatibility_list_enforced" to false,
        )
        values.putAll(
            pilotSafety?.metadata() ?: mapOf(
                "safety_policy_scope" to "NONE",
                "pilot_safety_pass" to null,
                "formal_safety_limits_applied" to false,
                "matched_start_limits_applied" to false,
            )
        )
        // ---- NPU 전용 (NPU_RUNNER_SPEC §4). CPU/GPU 파일에는 없는 키다.
        values.putAll(linkedMapOf(
            "engine" to ENGINE,
            "npu_accelerator_requested" to config.accelerator.wireName,
            "npu_available_accelerators" to facts?.availableAccelerators,
            "npu_model_source" to (facts?.modelSource ?: config.modelSource),
            "npu_model_partition" to facts?.aotPartition,
            "npu_compile_mode" to "aot",
            "npu_precision" to "fp16(compiler-default)",
            "npu_dispatch_lib_sha256" to facts?.dispatchLibSha256,
            "npu_dispatch_lib_source" to DISPATCH_LIB_SOURCE,
            "npu_env_init_ms" to facts?.envInitMs,
            "npu_model_init_ms" to facts?.modelInitMs,
            "npu_buffer_init_ms" to facts?.bufferInitMs,
            "npu_input_spec" to config.inputSpec.wireName,
            "npu_input_generator" to config.inputSpec.generator,
            "npu_input_normalization" to config.inputSpec.normalization,
            "npu_input_elements" to facts?.inputElements,
            "npu_input_sha256" to facts?.inputSha256,
            // latency_ms 는 write + run + read (Interpreter.run() 의 복사 포함 의미와 맞춘다, SPEC §4)
            "npu_latency_boundary" to "writeFloat+run+readFloat",
        ))
        // 2026-09-26 추가 키 — 기본 설정(기본 모델·NPU·run-only 기록 안 함)에서는 붙지 않아 기존 출력과 같다
        if (config.accelerator != TimedAccelerator.NPU) {
            values["npu_timed_resource_label"] = config.accelerator.resourceLabel
        }
        if (config.recordRunOnly) {
            values["npu_run_only_span"] = "run_only_summary event (CompiledModel.run() only)"
        }
        if (config.modelPath != null || config.modelAsset != NpuRunConfig.DEFAULT_MODEL_ASSET) {
            values["npu_model_size_bytes"] = facts?.modelSizeBytes
        }
        // 2026-09-28 추가 키 — GPU 가속기·상한 옵션일 때만 붙는다 (기본 NPU·CPU 런 출력은 그대로)
        if (config.accelerator == TimedAccelerator.GPU) {
            // 아래 두 키는 NPU AOT 전제의 값이라 GPU 런에서는 사실대로 바꿔 적는다 (자리는 그대로)
            values["npu_compile_mode"] = "not_aot (original model, compiled on device by the GPU accelerator)"
            values["npu_precision"] = "not_applicable (GPU run; see precision_record)"
            values["compiled_model_options"] = CompiledModelFacts.optionsRecord(config.accelerator, config.gpuPrecision)
            values["precision_record"] = CompiledModelFacts.precisionRecord(config.accelerator, config.gpuPrecision)
        }
        if (config.maxInferenceSpans != NpuRunConfig.DEFAULT_MAX_INFERENCE_SPANS) {
            values["max_inference_spans"] = config.maxInferenceSpans
            values["max_inference_spans_buffer_bytes"] = config.maxInferenceSpans * NpuRunConfig.SPAN_BUFFER_BYTES
            values["jvm_max_memory_bytes"] = facts?.jvmMaxMemoryBytes
        }
        return values
    }
}
