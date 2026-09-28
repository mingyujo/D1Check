package com.example.d1check.npurunner

/*
 * CompiledModel 실행 설정에 대한 정적 사실과 정밀도 4항목 기록 (MEASUREMENT_DEFINITION §11-3).
 * 2026-09-28 추가. GPU·연쇄 런의 run_metadata 에만 붙는다 — 기본 NPU·CPU 런 출력은 그대로다.
 * Android·LiteRT 의존이 없어 JVM 단위 테스트로 고정한다.
 */
internal object CompiledModelFacts {
    /**
     * litert-api 2.2.0 classes.jar 를 javap -c 로 읽은 결과 (2026-09-28):
     * CompiledModel$Companion.createFromAsset / createFromFile 은 accelerators 가 원소 하나이고 그것이 NPU 면
     * setOf(NPU, CPU) 로 바꿔 native 에 넘긴다. 다른 집합(GPU 하나, CPU 하나)은 그대로 넘긴다.
     */
    const val ACCELERATOR_BASIS =
        "litert-api 2.2.0 javap: CompiledModel\$Companion.createFromAsset/createFromFile replace a lone {NPU} " +
            "with {NPU,CPU} before the native call; other sets are passed unchanged"

    fun nativeAccelerators(accelerator: TimedAccelerator): List<String> = when (accelerator) {
        TimedAccelerator.NPU -> listOf("NPU", "CPU")
        TimedAccelerator.CPU -> listOf("CPU")
        TimedAccelerator.GPU -> listOf("GPU")
    }

    /** ③ 설정한 실행 옵션. NpuBenchmarkEngine.init 이 실제로 넘기는 값과 같아야 한다. */
    fun optionsRecord(accelerator: TimedAccelerator, gpuPrecision: String?): LinkedHashMap<String, Any?> =
        linkedMapOf(
            "api" to "CompiledModel.Options(Accelerator.${accelerator.wireName})",
            "accelerators_requested" to listOf(accelerator.wireName),
            "accelerators_passed_to_native" to nativeAccelerators(accelerator),
            "accelerators_basis" to ACCELERATOR_BASIS,
            "gpu_options" to (
                if (gpuPrecision != null) linkedMapOf("precision" to gpuPrecision)
                else if (accelerator == TimedAccelerator.GPU) "not_set (LiteRT default)"
                else null
                ),
            "environment_options" to listOf(
                "DispatchLibraryDir=nativeLibraryDir", "CompilerPluginLibraryDir=nativeLibraryDir",
            ),
            "compiler_cache" to true,
        )

    /** 정밀도 4항목. 러너가 확인할 수 없는 칸은 unknown + 이유 (추정값을 ④ 로 쓰지 않는다). */
    fun precisionRecord(accelerator: TimedAccelerator, gpuPrecision: String?): LinkedHashMap<String, Any?> =
        linkedMapOf(
            "schema" to "precision-4-v1",
            "storage" to linkedMapOf(
                "value" to "unknown_in_runner",
                "reason" to "the runner does not parse the .tflite; the host reads tensor types from the model " +
                    "file whose SHA-256 is model_sha256 (tools/compiled_model_evidence.py)",
            ),
            "io_dtype" to linkedMapOf(
                "value" to "FLOAT32 written and read (TensorBuffer.writeFloat/readFloat)",
                "reason" to "runner calls only; the dtype stored in the file is read by the host",
            ),
            "options" to optionsRecord(accelerator, gpuPrecision),
            "internal_compute" to linkedMapOf(
                "value" to "unknown",
                "reason" to "LiteRT 2.2.0 exposes no executed or accumulation precision; a set " +
                    "GpuOptions.precision is a request, not execution evidence",
            ),
        )
}
