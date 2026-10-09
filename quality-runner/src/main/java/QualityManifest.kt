package com.example.d1check.qualityrunner

/**
 * 호스트 (s26/tools/quality20/q20_run.py) 가 만드는 Q20 manifest. 앱은 값을 믿지 않고 계약과 다시 대조한다 (fail closed):
 * 표본 20 · sample_id 유일 · input_bytes = 602,112 · SHA 형식 · runtime 셋 = CPU/GPU/NPU 정확히 · NPU 만 AOT 산출물 (`_Samsung_E9965`) ·
 * GPU 정밀도 FP32 · CPU 스레드 1 (R2 와 같은 설정). 폴백 나열 없음 (RuntimeSpec 이 가속기 하나만 받는다).
 */
class QualityManifest(
    val protocol: String,
    val inputElements: Int,
    val inputBytes: Int,
    val outputElements: Int,
    val runsPerImage: Int,
    val runtimes: Map<String, RuntimeSpec>,
    val samples: List<Sample>,
    val source: Map<String, Any?>,
) {
    data class Sample(val index: Int, val sampleId: String, val inputPath: String, val inputBytes: Int, val inputSha256: String) {
        init {
            require(inputSha256.matches(Regex("[a-f0-9]{64}"))) { "input_sha256 of $sampleId" }
            require(sampleId.matches(Regex("[a-f0-9]{16}"))) { "sample_id $sampleId" }
        }
    }

    fun runtimeFor(backend: String): RuntimeSpec = requireNotNull(runtimes[backend]) { "no runtime for backend $backend" }

    fun validate() {
        require(protocol == QualityContract.PROTOCOL) { "protocol $protocol" }
        require(inputElements == QualityContract.INPUT_ELEMENTS && inputBytes == QualityContract.INPUT_BYTES) { "input geometry" }
        require(outputElements == QualityContract.OUTPUT_ELEMENTS) { "output_elements $outputElements" }
        require(runsPerImage == QualityContract.RUNS_PER_IMAGE) { "runs_per_image $runsPerImage" }
        require(runtimes.keys == QualityContract.BACKENDS.toSet()) { "runtimes ${runtimes.keys}" }
        runtimes.forEach { (backend, spec) ->
            require(spec.backend.name == backend && spec.key == QualityContract.keyOf(backend) && spec.task == QualityContract.TASK) { "runtime $backend key" }
            if (spec.backend == Backend.NPU) require(spec.modelId.endsWith("_Samsung_E9965")) { "NPU runtime must open an AOT artifact" }
            else require(!spec.modelId.endsWith("_Samsung_E9965")) { "AOT artifact is NPU-only (${spec.key})" }
            if (spec.backend == Backend.GPU) require(spec.gpuPrecision == "FP32") { "GPU precision must be FP32" }
            if (spec.backend == Backend.CPU) require(spec.cpuThreads == 1) { "CPU threads must be 1 (R2 와 같은 설정)" }
        }
        require(runtimes.getValue("CPU").modelSha256 == runtimes.getValue("GPU").modelSha256) { "CPU and GPU must open the same original model" }
        require(samples.size == QualityContract.SAMPLE_COUNT) { "samples ${samples.size}" }
        require(samples.map { it.sampleId }.toSet().size == samples.size) { "duplicate sample_id" }
        samples.forEachIndexed { i, s ->
            require(s.index == i) { "sample index $i" }
            require(s.inputBytes == QualityContract.INPUT_BYTES) { "input_bytes of ${s.sampleId}" }
            require(s.inputPath.isNotBlank()) { "input_path of ${s.sampleId}" }
        }
    }

    companion object {
        @Suppress("UNCHECKED_CAST")
        fun parse(text: String): QualityManifest {
            val m = MiniJson.parse(text) as Map<String, Any?>
            fun str(o: Map<String, Any?>, k: String): String = o[k] as? String ?: error("missing string $k")
            fun int(o: Map<String, Any?>, k: String): Int = (o[k] as? Long)?.toInt() ?: error("missing int $k")
            val runtimes = (m["runtimes"] as? Map<String, Any?> ?: error("missing runtimes")).map { (backend, v) ->
                val r = v as Map<String, Any?>
                backend to RuntimeSpec(
                    key = str(r, "key"),
                    task = str(r, "task"),
                    backend = Backend.valueOf(str(r, "backend")),
                    modelPath = str(r, "model_path"),
                    modelSha256 = str(r, "model_sha256"),
                    gpuPrecision = (r["gpu_precision"] as? String)?.ifEmpty { null },
                    cpuThreads = (r["cpu_threads"] as? Long)?.toInt(),
                )
            }.toMap()
            val samples = (m["samples"] as? List<Any?> ?: error("missing samples")).map { v ->
                val s = v as Map<String, Any?>
                Sample(int(s, "index"), str(s, "sample_id"), str(s, "input_path"), int(s, "input_bytes"), str(s, "input_sha256"))
            }
            return QualityManifest(
                protocol = str(m, "protocol"),
                inputElements = int(m, "input_elements"),
                inputBytes = int(m, "input_bytes"),
                outputElements = int(m, "output_elements"),
                runsPerImage = int(m, "runs_per_image"),
                runtimes = runtimes,
                samples = samples,
                source = (m["source"] as? Map<String, Any?>) ?: emptyMap(),
            )
        }
    }
}
