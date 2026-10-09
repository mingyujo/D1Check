package com.example.d1check.qualityrunner

import java.io.File

/**
 * Q20 한 번 실행 = backend 하나 (증거 창을 섞지 않으려고 backend 마다 앱을 따로 띄운다 — 프롬프트 1-3).
 * 순서 (등록 §2): 모델 SHA 확인 → runtime 생성 (`runtime create_start/end`) → 이미지마다: 파일 SHA 확인 (manifest 와 다르면 그 이미지 실패) →
 * 602,112 B 그대로 FloatArray (LE) → run 2회 (같은 입력) → 출력 1000 float32 를 raw LE 파일 2개 + SHA · finite · 원소 수 · run() ns →
 * 결과 JSON (.part → fsync → rename) → summary.json. 실패해도 남은 이미지를 계속 하고 실패는 `.failure.json` 으로 보존한다.
 * Context 가 없다 — runtimeFactory 가 CompiledModelRuntime (폰) 또는 가짜 (JVM 시험) 를 만든다.
 */
class QualityEngine(
    private val manifest: QualityManifest,
    private val manifestBytes: ByteArray,
    private val backend: String,
    private val runId: String,
    private val outRoot: File,
    private val runtimeFactory: (RuntimeSpec) -> InferenceRuntime,
    private val now: () -> Long,
    private val wallClock: () -> String,
    private val identity: Map<String, Any?>,
    private val log: (String) -> Unit,
) {
    val spec: RuntimeSpec = manifest.runtimeFor(backend)
    private val store = ArtifactStore(outRoot)
    private val failures = ArrayList<Map<String, Any?>>()

    /** 반환 = 끝까지 돌았는가 (runtime 생성 실패도 summary 를 남기고 false). */
    fun run(): Boolean {
        require(backend in QualityContract.BACKENDS) { "backend $backend" }
        check(!outRoot.exists()) { "out dir exists: $outRoot" }
        check(outRoot.mkdirs()) { "cannot create $outRoot" }
        val startedAt = wallClock()
        val t0 = now()
        store.saveBytes("manifest.json", manifestBytes)
        val modelFile = File(spec.modelPath)
        val modelSha = runCatching { FileSha256.sha256(modelFile) }.getOrNull()
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
        if (runtime != null) {
            try {
                for (sample in manifest.samples) {
                    log("image_start idx=${sample.index} sample_id=${sample.sampleId}")
                    val good = runCatching { image(runtime, sample) }.fold(
                        onSuccess = { true },
                        onFailure = { e -> failure(sample, "image", e); false },
                    )
                    if (good) ok++
                    log("image_end idx=${sample.index} ok=$good")
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
            "schema" to QualityContract.SUMMARY_SCHEMA,
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
            "manifest_sha256" to FileSha256.sha256(manifestBytes),
            "manifest_source" to manifest.source,
            "started_at" to startedAt,
            "ended_at" to wallClock(),
            "elapsed_ns" to (now() - t0),
            "identity" to identity,
            "note" to "raw outputs are <idx>_<sample_id>.run<k>.f32le (LE float32, 1000); metrics and verdicts are computed only by the host judge (s26/tools/quality20/q20_judge.py, committed before the phone run)",
        ))
        return runtime != null
    }

    private fun image(runtime: InferenceRuntime, sample: QualityManifest.Sample) {
        val file = File(sample.inputPath)
        val bytes = file.readBytes()
        val actualSha = FileSha256.sha256(bytes)
        check(bytes.size == sample.inputBytes) { "input bytes ${bytes.size} != ${sample.inputBytes}" }
        check(actualSha == sample.inputSha256) { "input sha256 mismatch: expected ${sample.inputSha256} got $actualSha" }
        val input = F32le.toFloats(bytes, manifest.inputElements)
        val prefix = "%02d_%s".format(sample.index, sample.sampleId)
        val runs = ArrayList<Map<String, Any?>>()
        val outputShas = ArrayList<String>()
        for (k in 0 until manifest.runsPerImage) {
            val t0 = now()
            val outputs = runtime.run(input)
            val t1 = now()
            check(outputs.size == 1) { "output tensor count ${outputs.size} != 1" }
            val raw = outputs[0]
            val rawBytes = F32le.toBytes(raw)
            val name = "$prefix.run$k.f32le"
            store.saveBytes(name, rawBytes)
            val sha = FileSha256.sha256(rawBytes)
            outputShas += sha
            runs += linkedMapOf(
                "run" to k,
                "output_file" to name,
                "output_elements" to raw.size,
                "output_shape_expected" to listOf(1, manifest.outputElements),
                "output_elements_ok" to (raw.size == manifest.outputElements),
                "all_finite" to raw.all { it.isFinite() },
                "output_sha256" to sha,
                "run_only_ns" to runtime.lastRunOnlyNs(),
                "write_run_read_ns" to (t1 - t0),
            )
        }
        store.save("$prefix.result.json", linkedMapOf(
            "schema" to QualityContract.RESULT_SCHEMA,
            "index" to sample.index,
            "sample_id" to sample.sampleId,
            "backend" to backend,
            "runtime_key" to spec.key,
            "input_path" to sample.inputPath,
            "input_bytes" to bytes.size,
            "input_sha256_expected" to sample.inputSha256,
            "input_sha256_actual" to actualSha,
            "input_dtype" to "float32_le",
            "input_transform" to "none (bytes written to the tensor as-is)",
            "runs" to runs,
            "bit_identical_runs" to (outputShas.toSet().size == 1),
            "status" to "ok",
        ))
    }

    private fun failure(sample: QualityManifest.Sample, stage: String, e: Throwable) {
        val prefix = "%02d_%s".format(sample.index, sample.sampleId)
        val record = linkedMapOf<String, Any?>(
            "index" to sample.index, "sample_id" to sample.sampleId, "backend" to backend, "stage" to stage,
            "error" to e.toString(), "status" to "failed",
        )
        failures += record
        runCatching { store.save("$prefix.failure.json", record) }
        log("image_failure idx=${sample.index} error=${e.toString().replace('\n', ' ').take(200)}")
    }
}
