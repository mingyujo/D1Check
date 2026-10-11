package com.example.d1check.requestrunner

import org.json.JSONObject
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

/*
 * M5 Q1 "입력 목록 실행" (d1sim/docs/상태분리_사전등록_v2.md §3 Q1) — 세션 경로와 따로 도는 진입점 (InputListActivity).
 * 혼합 요청 세션과 같은 것: RuntimeSpec (classification_CPU numThreads 1 · classification_GPU FP32 · classification_NPU AOT) ·
 *   CompiledModelRuntime (Runtimes.kt 그대로) · 분류 출력 = 그 runtime 의 readFloat() 그대로.
 * 입력: Q20 과 같은 canonical 텐서 (LE float32 NHWC [1,224,224,3] = 602,112 B, 받은 그대로) — 20장 중 canonical PNG 는 00575b… 하나뿐이라
 *   나머지는 요청 경로 전처리 (ImageContract) 를 다시 돌릴 수 없다. 대신 png_check 가 주어지면 그 한 장은 요청 경로 (TaskRuntime.execute:
 *   PNG → 디코드 → ImageContract.tensorFor → run) 로도 돌려 입력 텐서 SHA · 출력 SHA 를 텐서 입력 run0 과 나란히 적는다 (기록).
 * 산출물 형식 = quality-runner Q20 (s26-q20-image-result-v1 · s26-q20-summary-v1 · <idx>_<id>.run<k>.f32le) — 호스트 Q20 판정기를 import 만 해서 쓴다.
 * logcat 표시 = Q20 과 같은 꼴 (태그 D1Q1): activity_start · runtime create_start/end · image_start/end idx · activity_end.
 * SessionEngine · SessionManifest · 정책 · 계약 키는 건드리지 않는다.
 */
class InputListManifest(
    val protocol: String,
    val inputElements: Int,
    val inputBytes: Int,
    val outputElements: Int,
    val runsPerImage: Int,
    val runtimes: Map<String, RuntimeSpec>,
    val samples: List<Sample>,
    val pngCheck: PngCheck?,
) {
    data class Sample(val index: Int, val sampleId: String, val inputPath: String, val inputBytes: Int, val inputSha256: String)
    data class PngCheck(val sampleId: String, val imagePath: String, val imageSha256: String, val labelsPath: String, val labelsSha256: String)

    fun runtimeFor(backend: String): RuntimeSpec = requireNotNull(runtimes[backend]) { "no runtime for backend $backend" }

    fun validate() {
        require(protocol == PROTOCOL) { "protocol $protocol" }
        require(inputElements == INPUT_ELEMENTS && inputBytes == INPUT_ELEMENTS * 4) { "input geometry" }
        require(outputElements == OUTPUT_ELEMENTS && runsPerImage == RUNS_PER_IMAGE) { "output_elements / runs_per_image" }
        require(runtimes.keys == BACKENDS.toSet()) { "runtimes ${runtimes.keys}" }
        runtimes.forEach { (backend, spec) ->
            require(spec.backend.name == backend && spec.key == "classification_$backend" && spec.task == "classification") { "runtime $backend key" }
            // 혼합 요청 manifest 와 같은 설정 (SessionManifest.validate · mixreq_plan.runtime_specs)
            if (spec.backend == Backend.NPU) require(spec.modelId.endsWith("_Samsung_E9965")) { "NPU runtime must open an AOT artifact" }
            else require(!spec.modelId.endsWith("_Samsung_E9965")) { "AOT artifact is NPU-only (${spec.key})" }
            if (spec.backend == Backend.GPU) require(spec.gpuPrecision == "FP32") { "GPU precision must be FP32 (mixreq setting)" }
            if (spec.backend == Backend.CPU) require(spec.cpuThreads == 1) { "CPU threads must be 1 (mixreq setting)" }
        }
        require(samples.size == SAMPLE_COUNT && samples.map { it.sampleId }.toSet().size == SAMPLE_COUNT) { "samples" }
        samples.forEachIndexed { i, s ->
            require(s.index == i && s.inputBytes == inputBytes && s.inputPath.isNotBlank()) { "sample $i" }
            require(s.inputSha256.matches(SHA_RE) && s.sampleId.matches(Regex("[a-f0-9]{16}"))) { "sample $i ids" }
        }
        pngCheck?.let { p ->
            require(samples.any { it.sampleId == p.sampleId }) { "png_check sample not in list" }
            require(p.imageSha256.matches(SHA_RE) && p.labelsSha256.matches(SHA_RE)) { "png_check sha" }
        }
    }

    companion object {
        /** Q20 manifest 와 같은 protocol (같은 입력 계약 · 같은 파일 · s26/tools/quality20/q20_common.build_app_manifest). */
        const val PROTOCOL = "s26-q20-manifest-v1"
        const val INPUT_ELEMENTS = 224 * 224 * 3
        const val OUTPUT_ELEMENTS = 1000
        const val RUNS_PER_IMAGE = 2
        const val SAMPLE_COUNT = 20
        val BACKENDS = listOf("CPU", "GPU", "NPU")
        private val SHA_RE = Regex("[a-f0-9]{64}")

        fun parse(text: String): InputListManifest {
            val m = JSONObject(text)
            val r = m.getJSONObject("runtimes")
            val runtimes = r.keys().asSequence().associateWith { backend ->
                val o = r.getJSONObject(backend)
                RuntimeSpec(
                    key = o.getString("key"),
                    task = o.getString("task"),
                    backend = Backend.valueOf(o.getString("backend")),
                    modelPath = o.getString("model_path"),
                    modelSha256 = o.getString("model_sha256"),
                    gpuPrecision = if (o.has("gpu_precision") && !o.isNull("gpu_precision")) o.getString("gpu_precision").ifEmpty { null } else null,
                    cpuThreads = if (o.has("cpu_threads") && !o.isNull("cpu_threads")) o.getInt("cpu_threads") else null,
                )
            }
            val s = m.getJSONArray("samples")
            val samples = (0 until s.length()).map { i ->
                val o = s.getJSONObject(i)
                Sample(o.getInt("index"), o.getString("sample_id"), o.getString("input_path"), o.getInt("input_bytes"), o.getString("input_sha256"))
            }
            val png = if (m.has("png_check") && !m.isNull("png_check")) m.getJSONObject("png_check").let {
                PngCheck(it.getString("sample_id"), it.getString("image_path"), it.getString("image_sha256"), it.getString("labels_path"), it.getString("labels_sha256"))
            } else null
            return InputListManifest(
                protocol = m.getString("protocol"),
                inputElements = m.getInt("input_elements"),
                inputBytes = m.getInt("input_bytes"),
                outputElements = m.getInt("output_elements"),
                runsPerImage = m.getInt("runs_per_image"),
                runtimes = runtimes,
                samples = samples,
                pngCheck = png,
            )
        }
    }
}

/** backend 하나 · 이미지 20장 × 2회. Android 의존 (런타임 · 디코드 · 시계) 은 주입 → JVM 시험에서 가짜로 돌린다. */
class InputListEngine(
    private val manifest: InputListManifest,
    private val manifestBytes: ByteArray,
    private val backend: String,
    private val runId: String,
    private val outRoot: File,
    private val runtimeFactory: (RuntimeSpec) -> InferenceRuntime,
    private val decodeImage: (File) -> DecodedImage,
    private val now: () -> Long,
    private val identity: Map<String, Any?>,
    private val log: (String) -> Unit,
) {
    val spec: RuntimeSpec = manifest.runtimeFor(backend)
    private val failures = ArrayList<Map<String, Any?>>()
    private val run0Sha = HashMap<String, String>()

    fun run(): Boolean {
        require(backend in InputListManifest.BACKENDS) { "backend $backend" }
        check(!outRoot.exists() && outRoot.mkdirs()) { "out dir exists or not creatable: $outRoot" }
        val store = ArtifactStore(outRoot)
        val t0 = now()
        store.saveBytes("manifest.json", manifestBytes)
        val modelSha = runCatching { TaskRuntime.sha256(File(spec.modelPath)) }.getOrNull()
        val modelOk = modelSha == spec.modelSha256
        var runtime: InferenceRuntime? = null
        var createError: String? = null
        var createNs: Long? = null
        if (modelOk) {
            log("runtime create_start key=${spec.key} backend=$backend model_sha256=${spec.modelSha256}")
            val c0 = now()
            try {
                runtime = runtimeFactory(spec)
                check(runtime.inputElementCount() == manifest.inputElements) { "input elements ${runtime.inputElementCount()}" }
            } catch (e: Throwable) {
                createError = e.toString()
                runCatching { runtime?.close() }
                runtime = null
            }
            createNs = now() - c0
            log("runtime create_end key=${spec.key} ok=${runtime != null}")
        } else {
            createError = "model sha256 mismatch: expected ${spec.modelSha256} got $modelSha"
            log("runtime create_skipped key=${spec.key} reason=model_sha_mismatch")
        }
        var ok = 0
        var pngRecord: Map<String, Any?>? = null
        if (runtime != null) {
            try {
                for (sample in manifest.samples) {
                    log("image_start idx=${sample.index} sample_id=${sample.sampleId}")
                    val good = runCatching { image(store, runtime, sample) }.fold(
                        onSuccess = { true },
                        onFailure = { e -> failure(store, sample, e); false },
                    )
                    if (good) ok++
                    log("image_end idx=${sample.index} ok=$good")
                }
                manifest.pngCheck?.let { p ->
                    pngRecord = runCatching { pngCheck(runtime, p) }.getOrElse { e -> linkedMapOf("status" to "failed", "error" to e.toString()) }
                    store.save("png_check.json", pngRecord)
                }
            } finally {
                runCatching { runtime.close() }
            }
        }
        val status = when {
            !modelOk -> "model_sha_mismatch"
            runtime == null -> "runtime_create_failed"
            ok == manifest.samples.size -> "completed"
            else -> "completed_with_failures"
        }
        store.save("summary.json", linkedMapOf(
            "schema" to "s26-q20-summary-v1",
            "run_id" to runId,
            "backend" to backend,
            "runtime_key" to spec.key,
            "status" to status,
            "model_path" to spec.modelPath,
            "model_sha256_expected" to spec.modelSha256,
            "model_sha256_actual" to modelSha,
            "model_sha_ok" to modelOk,
            "runtime_created" to (runtime != null),
            "runtime_create_error" to createError,
            "runtime_create_ns" to createNs,
            "runtime_init" to runtime?.initRecord(),
            "compiled_model_options" to spec.optionsRecord(),
            "engine" to MixreqContract.ENGINE,
            "litert_version" to MixreqContract.LITERT_VERSION,
            "runs_per_image" to manifest.runsPerImage,
            "images_total" to manifest.samples.size,
            "images_ok" to ok,
            "failures" to failures,
            "manifest_sha256" to ImageContract.sha256(manifestBytes),
            "png_check_status" to pngRecord?.get("status"),
            "elapsed_ns" to (now() - t0),
            "identity" to identity,
            "path" to "request-runner input-list mode (M5 Q1): RuntimeSpec + CompiledModelRuntime as SessionEngine; canonical tensor written as-is",
        ))
        return runtime != null
    }

    private fun image(store: ArtifactStore, runtime: InferenceRuntime, sample: InputListManifest.Sample) {
        val bytes = File(sample.inputPath).readBytes()
        val actualSha = ImageContract.sha256(bytes)
        check(bytes.size == sample.inputBytes) { "input bytes ${bytes.size} != ${sample.inputBytes}" }
        check(actualSha == sample.inputSha256) { "input sha256 mismatch: expected ${sample.inputSha256} got $actualSha" }
        val input = FloatArray(manifest.inputElements)
        ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(input)
        val prefix = "%02d_%s".format(sample.index, sample.sampleId)
        val runs = ArrayList<Map<String, Any?>>()
        val shas = ArrayList<String>()
        for (k in 0 until manifest.runsPerImage) {
            val t0 = now()
            val outputs = runtime.run(input)
            val t1 = now()
            check(outputs.size == 1) { "output tensor count ${outputs.size} != 1" }
            val raw = outputs[0]
            val rawBytes = SessionEngine.floatBytes(raw)
            val name = "$prefix.run$k.f32le"
            store.saveBytes(name, rawBytes)
            val sha = ImageContract.sha256(rawBytes)
            shas += sha
            runs += linkedMapOf(
                "run" to k, "output_file" to name, "output_elements" to raw.size,
                "output_shape_expected" to listOf(1, manifest.outputElements), "output_elements_ok" to (raw.size == manifest.outputElements),
                "all_finite" to raw.all { it.isFinite() }, "output_sha256" to sha,
                "run_only_ns" to runtime.lastRunOnlyNs(), "write_run_read_ns" to (t1 - t0),
            )
        }
        run0Sha[sample.sampleId] = shas[0]
        store.save("$prefix.result.json", linkedMapOf(
            "schema" to "s26-q20-image-result-v1",
            "index" to sample.index, "sample_id" to sample.sampleId, "backend" to backend, "runtime_key" to spec.key,
            "input_path" to sample.inputPath, "input_bytes" to bytes.size,
            "input_sha256_expected" to sample.inputSha256, "input_sha256_actual" to actualSha,
            "input_dtype" to "float32_le", "input_transform" to "none (bytes written to the tensor as-is)",
            "runs" to runs, "bit_identical_runs" to (shas.toSet().size == 1), "status" to "ok",
            "path" to "request-runner CompiledModelRuntime",
        ))
    }

    /** 요청 경로 그대로 (TaskRuntime.execute — 세션의 warmup · 요청과 같은 함수) 한 장: 입력 텐서 SHA · 출력 SHA 를 텐서 입력 run0 과 나란히. */
    private fun pngCheck(runtime: InferenceRuntime, p: InputListManifest.PngCheck): Map<String, Any?> {
        val labelsFile = File(p.labelsPath)
        check(TaskRuntime.sha256(labelsFile) == p.labelsSha256) { "labels SHA-256 mismatch" }
        val task = TaskRuntime(spec, runtime, TaskRuntime.labelLines(labelsFile.readText(Charsets.UTF_8)), emptyList(), decodeImage, now)
        val outcome = task.execute(File(p.imagePath), p.imageSha256, recordDecodedRgb = true)
        val outputSha = (outcome.record["raw_output_sha256"] as List<*>).single() as String
        val sample = manifest.samples.first { it.sampleId == p.sampleId }
        return linkedMapOf(
            "status" to "ok", "sample_id" to p.sampleId, "image_path" to p.imagePath, "image_sha256" to p.imageSha256,
            "request_path_input_tensor_sha256" to outcome.record["input_tensor_sha256"],
            "canonical_tensor_sha256" to sample.inputSha256,
            "input_tensor_equal" to (outcome.record["input_tensor_sha256"] == sample.inputSha256),
            "request_path_output_sha256" to outputSha, "tensor_input_run0_output_sha256" to run0Sha[p.sampleId],
            "output_equal" to (outputSha == run0Sha[p.sampleId]),
            "request_path_record" to outcome.record,
        )
    }

    private fun failure(store: ArtifactStore, sample: InputListManifest.Sample, e: Throwable) {
        val prefix = "%02d_%s".format(sample.index, sample.sampleId)
        val record = linkedMapOf<String, Any?>("index" to sample.index, "sample_id" to sample.sampleId, "backend" to backend,
            "stage" to "image", "error" to e.toString(), "status" to "failed")
        failures += record
        runCatching { store.save("$prefix.failure.json", record) }
        log("image_failure idx=${sample.index} error=${e.toString().replace('\n', ' ').take(200)}")
    }
}
