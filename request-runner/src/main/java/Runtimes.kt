package com.example.d1check.requestrunner

import android.content.Context
import android.os.SystemClock
import com.google.ai.edge.litert.Accelerator
import com.google.ai.edge.litert.CompiledModel
import com.google.ai.edge.litert.Environment
import com.google.ai.edge.litert.TensorBuffer
import java.io.File
import java.security.MessageDigest

/*
 * 출처:
 *   npu-runner/src/main/java/NpuBenchmarkEngine.kt (Environment + CompiledModel.Options(가속기 하나) + 버퍼 · 닫는 순서) — 사본 · 다출력 읽기로 바꿈
 *   npu-runner/src/main/java/NpuCompiledModelFacts.kt (NPU 하나 → native 에는 {NPU, CPU} 로 넘어간다는 사실 · 옵션 기록)
 *   feature/arrival-scheduling-20260923 @ d588323 benchmark-runner/src/modelProbe/.../ProbeTaskAdapter.kt 42~78행
 *     (요청마다: 이미지 SHA → canonical PNG → 디코드 → 크기 조정 → 텐서 → 추론 → 출력 SHA → 디코드 → 결과 맵)
 * 바꾼 것: 엔진 (Interpreter 1.4.2 → CompiledModel 2.2.0) · 출력을 "원소 수" 로 구분 (2.2.0 Kotlin API 에는 출력 이름 · shape 조회가 없다 —
 *   NpuBenchmarkEngine.kt 122~123행) · CPU 스레드는 CpuOptions(numThreads) (설정값일 뿐 — 실제 worker 수는 호스트 top -H 관측).
 */
enum class Backend { CPU, GPU, NPU }

data class RuntimeSpec(
    val key: String,
    val task: String,
    val backend: Backend,
    val modelPath: String,
    val modelSha256: String,
    val gpuPrecision: String? = null,
    val cpuThreads: Int? = null,
) {
    val lane: String get() = backend.name
    val modelId: String get() = File(modelPath).name.removeSuffix(".tflite")

    init {
        require(MixreqContract.laneOf(key) == backend.name) { "runtime key $key does not match backend $backend" }
        require(MixreqContract.taskOf(key) == task) { "runtime key $key does not match task $task" }
        require(modelSha256.matches(Regex("[a-f0-9]{64}"))) { "model_sha256 of $key" }
        require(gpuPrecision == null || backend == Backend.GPU) { "gpu_precision only with GPU ($key)" }
        require(cpuThreads == null || backend == Backend.CPU) { "cpu_threads only with CPU ($key)" }
    }

    /** NpuCompiledModelFacts.nativeAccelerators 와 같은 사실: litert-api 2.2.0 은 {NPU} 하나를 {NPU, CPU} 로 바꿔 넘긴다. */
    fun acceleratorsPassedToNative(): List<String> = when (backend) {
        Backend.NPU -> listOf("NPU", "CPU")
        Backend.CPU -> listOf("CPU")
        Backend.GPU -> listOf("GPU")
    }

    fun optionsRecord(): Map<String, Any?> = linkedMapOf(
        "api" to "CompiledModel.Options(Accelerator.${backend.name})",
        "accelerators_requested" to listOf(backend.name),
        "accelerators_passed_to_native" to acceleratorsPassedToNative(),
        "cpu_options" to (cpuThreads?.let { linkedMapOf("num_threads" to it) }),
        "gpu_options" to (gpuPrecision?.let { linkedMapOf("precision" to it) }),
        "environment_options" to listOf("DispatchLibraryDir=nativeLibraryDir", "CompilerPluginLibraryDir=nativeLibraryDir"),
        "compiler_cache" to true,
    )
}

/** 추론 백엔드. 운영 = CompiledModelRuntime · 시험 = 가짜 (서비스 시간만 흉내). */
interface InferenceRuntime : AutoCloseable {
    val spec: RuntimeSpec
    fun inputElementCount(): Int

    /** 1회 추론 = 입력 쓰기 → run → 모든 출력 읽기. 반환 = 출력 텐서 전부 (탐지는 2개). */
    fun run(input: FloatArray): List<FloatArray>

    /** 직전 run() 안의 CompiledModel.run() 만의 ns (write / read 제외). 모르면 null. */
    fun lastRunOnlyNs(): Long? = null

    fun initRecord(): Map<String, Any?>
}

class CompiledModelRuntime(context: Context, override val spec: RuntimeSpec) : InferenceRuntime {
    private val env: Environment
    private val model: CompiledModel
    private val inputs: List<TensorBuffer>
    private val outputs: List<TensorBuffer>
    private val elements: Int
    private val record: LinkedHashMap<String, Any?>
    private var runOnlyNs: Long? = null

    init {
        val libDir = context.applicationInfo.nativeLibraryDir
        val t0 = SystemClock.elapsedRealtimeNanos()
        env = Environment.create(
            context,
            mapOf(
                Environment.Option.DispatchLibraryDir to libDir,
                Environment.Option.CompilerPluginLibraryDir to libDir,
            ),
            /* enableCompilerCache = */ true,
        )
        val t1 = SystemClock.elapsedRealtimeNanos()
        val available = runCatching { env.getAvailableAccelerators().map { it.name }.sorted() }.getOrDefault(emptyList())
        val accelerator = when (spec.backend) {
            Backend.CPU -> Accelerator.CPU
            Backend.GPU -> Accelerator.GPU
            Backend.NPU -> Accelerator.NPU
        }
        // 가속기 하나만. 폴백 목록을 만들지 않는다 (NPU_RUNNER_SPEC §7 · 등록 §3-1)
        val options = CompiledModel.Options(accelerator)
        if (spec.cpuThreads != null) options.cpuOptions = CompiledModel.CpuOptions(numThreads = spec.cpuThreads)
        if (spec.gpuPrecision != null) {
            options.gpuOptions = CompiledModel.GpuOptions(precision = CompiledModel.GpuOptions.Precision.valueOf(spec.gpuPrecision))
        }
        model = CompiledModel.create(spec.modelPath, options, env)
        val t2 = SystemClock.elapsedRealtimeNanos()
        inputs = model.createInputBuffers()
        outputs = model.createOutputBuffers()
        val t3 = SystemClock.elapsedRealtimeNanos()
        check(inputs.size == 1) { "${spec.key}: expected one input tensor, got ${inputs.size}" }
        // 원소 수는 버퍼를 한 번 읽어 잰다 (NpuBenchmarkEngine.inputElementCount) — 타이밍 밖, 생성 때 한 번
        elements = inputs[0].readFloat().size
        val expected = if (spec.task == "classification") 224 * 224 * 3 else 320 * 320 * 3
        check(elements == expected) { "${spec.key}: input elements $elements != $expected" }
        val libFiles = runCatching { File(libDir).listFiles()?.map { it.name }?.sorted() }.getOrNull() ?: emptyList()
        record = linkedMapOf(
            "engine" to MixreqContract.ENGINE,
            "litert_version" to MixreqContract.LITERT_VERSION,
            "env_init_ns" to (t1 - t0),
            "model_init_ns" to (t2 - t1),
            "buffer_init_ns" to (t3 - t2),
            "available_accelerators" to available,
            "native_lib_dir" to libDir,
            "native_lib_files" to libFiles,
            "dispatch_so_present" to libFiles.contains("libLiteRtDispatch_Samsung.so"),
            "input_count" to inputs.size,
            "output_count" to outputs.size,
            "input_elements" to elements,
            "compiled_model_options" to spec.optionsRecord(),
        )
    }

    override fun inputElementCount(): Int = elements

    override fun run(input: FloatArray): List<FloatArray> {
        inputs[0].writeFloat(input)
        val r0 = SystemClock.elapsedRealtimeNanos()
        model.run(inputs, outputs)
        runOnlyNs = SystemClock.elapsedRealtimeNanos() - r0
        return outputs.map { it.readFloat() }
    }

    override fun lastRunOnlyNs(): Long? = runOnlyNs

    override fun initRecord(): Map<String, Any?> = record

    /** 닫는 순서: 버퍼 → 모델 → 환경 (NpuBenchmarkEngine.close). */
    override fun close() {
        inputs.forEach { runCatching { it.close() } }
        outputs.forEach { runCatching { it.close() } }
        runCatching { model.close() }
        runCatching { env.close() }
    }
}

/** runtime 하나 + 이미지 파이프라인 + 디코더 = A24 ProbeTaskAdapter 에 해당. */
class TaskRuntime(
    val spec: RuntimeSpec,
    private val runtime: InferenceRuntime,
    private val labels: List<String>,
    private val anchors: List<DoubleArray>,
    private val decodeImage: (File) -> DecodedImage,
    private val now: () -> Long,
) : AutoCloseable {
    class Outcome(val record: LinkedHashMap<String, Any?>, val softmax: FloatArray?)

    init {
        if (spec.task == "classification") {
            require(labels.size == 1000) { "${spec.key}: classification labels ${labels.size}" }
        } else {
            require(labels.size == 90 && anchors.size == 19_206) { "${spec.key}: detection labels/anchors" }
        }
    }

    val initRecord: Map<String, Any?> get() = runtime.initRecord()

    /**
     * A24 ProbeTaskAdapter.execute 그대로의 순서: 이미지 SHA → canonical PNG 검사 → 디코드 → 크기 조정 → 텐서 → 추론 →
     * 출력 유한성 · SHA → 디코드. recordDecodedRgb = 디코드된 RGB 의 SHA 도 적는다 (warmup 에서만 — A24 는 요청마다 적지 않는다).
     */
    fun execute(image: File, imageSha256: String, recordDecodedRgb: Boolean = false): Outcome {
        val bytes = image.readBytes()
        require(ImageContract.sha256(bytes) == imageSha256) { "image SHA-256 mismatch" }
        ImageContract.requireCanonicalPng(bytes)
        val decoded = decodeImage(image)
        val tensor = ImageContract.tensorFor(spec.task, decoded.rgb, decoded.width, decoded.height)
        val inputSha = ImageContract.sha256(tensor)
        val t0 = now()
        val raw = runtime.run(tensor)
        val t1 = now()
        check(raw.all { output -> output.all { it.isFinite() } }) { "${spec.key}: non-finite output" }
        val outputSha = raw.map { ImageContract.sha256(it) }
        val results: List<Map<String, Any?>>
        var softmax: FloatArray? = null
        if (spec.task == "classification") {
            check(raw.size == 1 && raw[0].size == labels.size) { "${spec.key}: classification output shape ${raw.map { it.size }}" }
            softmax = raw[0]
            results = ClassificationDecoder.toMaps(ClassificationDecoder.top5(raw[0], labels))
        } else {
            check(raw.size == 2) { "${spec.key}: detection output count ${raw.size}" }
            val scores = raw.singleOrNull { it.size == anchors.size * labels.size }
            val boxes = raw.singleOrNull { it.size == anchors.size * 4 }
            check(scores != null && boxes != null && scores !== boxes) { "${spec.key}: detection output sizes ${raw.map { it.size }}" }
            results = DetectionDecoder.toMaps(
                DetectionDecoder.decode(scores, boxes, anchors, labels, decoded.width, decoded.height),
            )
        }
        val record = linkedMapOf<String, Any?>(
            "task_id" to spec.task,
            "runtime_key" to spec.key,
            "model_id" to spec.modelId,
            "model_sha256" to spec.modelSha256,
            "image_sha256" to imageSha256,
            "image_size" to listOf(decoded.width, decoded.height),
            "input_tensor_sha256" to inputSha,
            "raw_output_sha256" to outputSha,
            "raw_output_elements" to raw.map { it.size },
            "results" to results,
            "inference_ns" to (runtime.lastRunOnlyNs() ?: (t1 - t0)),
            "write_run_read_ns" to (t1 - t0),
            "requested_backend" to spec.backend.name,
            "actual_backend" to if (spec.backend == Backend.CPU) "CPU" else "unverified_requires_host_delegate_log",
            "adapter_contract" to MixreqContract.ADAPTER_CONTRACT,
            "adapter_port" to MixreqContract.ADAPTER_PORT,
            "canonical_input_contract" to MixreqContract.CANONICAL_INPUT_CONTRACT,
            "engine" to MixreqContract.ENGINE,
            "litert_version" to MixreqContract.LITERT_VERSION,
        )
        if (recordDecodedRgb) record["decoded_rgb_sha256"] = ImageContract.sha256(decoded.rgb)
        return Outcome(record, softmax)
    }

    override fun close() = runtime.close()

    companion object {
        fun sha256(file: File): String {
            val digest = MessageDigest.getInstance("SHA-256")
            file.inputStream().use { input ->
                val buffer = ByteArray(1 shl 16)
                while (true) {
                    val n = input.read(buffer)
                    if (n < 0) break
                    digest.update(buffer, 0, n)
                }
            }
            return digest.digest().joinToString("") { "%02x".format(it) }
        }

        /** Python splitlines 와 같은 뜻: 마지막 개행 뒤의 빈 조각만 버리고 안쪽 빈 줄은 유지한다 (labels.txt 는 빈자리가 있을 수 있다). */
        fun labelLines(text: String): List<String> {
            val normalized = text.replace("\r\n", "\n")
            val parts = normalized.split("\n")
            return if (normalized.endsWith("\n")) parts.dropLast(1) else parts
        }
    }
}
