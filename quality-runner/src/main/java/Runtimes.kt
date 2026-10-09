package com.example.d1check.qualityrunner

/*
 * ★ 사본 — request-runner/src/main/java/Runtimes.kt (s26-mixreq e2bedf1 · blob 7f9ba0a7aa8aab22259e3cb940f727cc0546c893) 의
 *   Backend · RuntimeSpec · InferenceRuntime · CompiledModelRuntime 을 package 줄만 바꾸고 그대로 가져왔다 (코드 무변경).
 *   TaskRuntime (canonical PNG 디코드 · 탐지 디코더) 은 Q20 에 없으므로 복사하지 않았다 — 그 companion 의 sha256(File) 만
 *   FileSha256.kt 에 같은 코드로 옮겼다. MixreqContract 참조 (laneOf · taskOf · ENGINE · LITERT_VERSION) 는 MixreqContractSubset.kt 가
 *   같은 이름 · 같은 코드로 제공한다.
 *   근거: d1sim/docs/품질20장_사전등록_v1.md §2 (CPU CompiledModel 2.2.0 XNNPACK · GPU OpenCL FP32 요청 · NPU DispatchDelegate AOT).
 */
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

