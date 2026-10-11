package com.example.d1check.qualityrunner

import java.io.File
import java.nio.file.Files

/** JVM 시험 공용: 임시 입력 20장 (602,112 B, 결정적 바이트) · 가짜 모델 파일 · manifest JSON. 실제 참조 출력은 쓰지 않는다 (판정기 커밋 전 열람 금지). */
object TestFixtures {
    const val ORIGINAL_MODEL = "efficientnet_lite0.tflite"
    const val AOT_MODEL = "efficientnet_lite0_Samsung_E9965.tflite"

    class Built(val root: File, val manifestFile: File, val manifestText: String, val samples: List<QualityManifest.Sample>, val modelSha: Map<String, String>)

    fun inputBytes(index: Int): ByteArray = ByteArray(QualityContract.INPUT_BYTES) { i -> ((i * 31 + index * 7) and 0xFF).toByte() }

    fun build(count: Int = 20, corruptSha: Set<Int> = emptySet(), mutate: (MutableMap<String, Any?>) -> Unit = {}): Built {
        val root = Files.createTempDirectory("d1q20").toFile()
        val models = File(root, "models").apply { mkdirs() }
        val modelSha = HashMap<String, String>()
        for ((name, seed) in listOf(ORIGINAL_MODEL to 1, AOT_MODEL to 2)) {
            val bytes = ByteArray(4096) { i -> ((i * seed + 3) and 0xFF).toByte() }
            File(models, name).writeBytes(bytes)
            modelSha[name] = FileSha256.sha256(bytes)
        }
        val samples = (0 until count).map { i ->
            val id = "%016x".format(0x1000_0000_0000_0000L + i * 7919L)
            val dir = File(root, "inputs/$id").apply { mkdirs() }
            val bytes = inputBytes(i)
            File(dir, "input.f32le").writeBytes(bytes)
            val sha = if (i in corruptSha) "0".repeat(64) else FileSha256.sha256(bytes)
            QualityManifest.Sample(i, id, File(dir, "input.f32le").absolutePath, bytes.size, sha)
        }
        fun runtime(backend: String, model: String, extra: Map<String, Any?>) = linkedMapOf<String, Any?>(
            "key" to "classification_$backend", "task" to "classification", "backend" to backend,
            "model_path" to File(models, model).absolutePath, "model_sha256" to modelSha.getValue(model),
        ).also { it.putAll(extra) }
        val m = linkedMapOf<String, Any?>(
            "protocol" to QualityContract.PROTOCOL,
            "input_shape" to listOf(1, 224, 224, 3),
            "input_elements" to QualityContract.INPUT_ELEMENTS,
            "input_bytes" to QualityContract.INPUT_BYTES,
            "output_elements" to QualityContract.OUTPUT_ELEMENTS,
            "runs_per_image" to QualityContract.RUNS_PER_IMAGE,
            "runtimes" to linkedMapOf(
                "CPU" to runtime("CPU", ORIGINAL_MODEL, mapOf("cpu_threads" to 1)),
                "GPU" to runtime("GPU", ORIGINAL_MODEL, mapOf("gpu_precision" to "FP32")),
                "NPU" to runtime("NPU", AOT_MODEL, emptyMap()),
            ),
            "samples" to samples.map { s ->
                linkedMapOf("index" to s.index, "sample_id" to s.sampleId, "input_path" to s.inputPath, "input_bytes" to s.inputBytes, "input_sha256" to s.inputSha256)
            },
            "source" to linkedMapOf("zip_sha256" to "test", "note" to "JVM fixture"),
        )
        mutate(m)
        val text = Json.encode(m)
        val file = File(root, "q20_manifest.json").apply { writeText(text) }
        return Built(root, file, text, samples, modelSha)
    }
}

/** 가짜 backend: 입력 바이트에서 결정적으로 Softmax 1000 을 만든다 (서비스 시간 흉내 없음). variant 로 2회 차이 · 비유한 · 원소 수 오류를 흉내낸다. */
class FakeRuntime(
    override val spec: RuntimeSpec,
    private val elements: Int = QualityContract.OUTPUT_ELEMENTS,
    private val nanAt: Int? = null,
    private val driftSecondRun: Boolean = false,
    private val failOnCreate: Boolean = false,
    private val failRunAt: Int? = null,
) : InferenceRuntime {
    init { if (failOnCreate) throw IllegalStateException("fake ${spec.key} creation failure") }
    var runs = 0
    var closed = false
    override fun inputElementCount(): Int = QualityContract.INPUT_ELEMENTS
    override fun run(input: FloatArray): List<FloatArray> {
        require(input.size == QualityContract.INPUT_ELEMENTS)
        runs++
        if (failRunAt != null && runs == failRunAt) throw IllegalStateException("fake run failure #$runs")
        val seed = input[0] + input[1234] + input[input.size - 1]
        val out = FloatArray(elements) { i -> 1e-3f + (((i * 13 + seed.toRawBits()) and 0xFF) / 255f) * 1e-3f }
        if (driftSecondRun && runs % 2 == 0) out[0] += 1e-6f
        if (nanAt != null) out[nanAt] = Float.NaN
        return listOf(out)
    }
    override fun lastRunOnlyNs(): Long = 1_000L * runs
    override fun initRecord(): Map<String, Any?> = mapOf("engine" to "fake", "available_accelerators" to listOf("CPU", "GPU", "NPU"))
    override fun close() { closed = true }
}
