package com.example.d1check.npurunner

import android.content.Context
import android.os.SystemClock
import com.google.ai.edge.litert.Accelerator
import com.google.ai.edge.litert.CompiledModel
import com.google.ai.edge.litert.Environment
import com.google.ai.edge.litert.TensorBuffer

/**
 * LiteRT Next `CompiledModel` 을 쓰는 실행 엔진.
 *
 * benchmark-runner 의 `Interpreter.run()` 과는 **엔진 자체가 다르다**. 그래서 기록 필드 이름도
 * 분리한다 (`engine = "litert-compiled-model"`). 측정 경계만 CPU/GPU 와 맞춘다:
 * `latency_ms` = write + run + read (사용자 체감 1회 추론), `run_only_ms` = run() 만.
 *
 * API 는 LiteRT main @ 9380426b (우리가 dispatch .so 를 빌드한 그 커밋) 의 Kotlin 소스로 확인했다.
 *   Environment.create(context, Map<Option,String>, enableCompilerCache)
 *   Environment.getAvailableAccelerators(): Set<Accelerator>
 *   CompiledModel.create(assetManager, assetName, Options(vararg Accelerator), env)
 *   CompiledModel.create(filePath, Options, env)
 *   CompiledModel.createInputBuffers() / createOutputBuffers() / run(inputs, outputs)
 *   TensorBuffer.writeFloat / readFloat / writeInt8 / readInt8
 */
class NpuBenchmarkEngine(
    private val context: Context,
    private val accelerator: Accelerator,
    /** assets 안의 경로. modelFilePath 가 주어지면 무시된다. */
    private val modelAssetPath: String?,
    /** 파일 경로로 열 때 사용. 리빌드 없이 모델을 바꿔 끼우는 용도. */
    private val modelFilePath: String?,
) : AutoCloseable {

    data class InitSpans(
        val envInitNs: Long,
        val modelInitNs: Long,
        val bufferInitNs: Long,
        val availableAccelerators: Set<Accelerator>,
        val inputCount: Int,
        val outputCount: Int,
        /** dispatch .so 가 여기 실제 파일로 있어야 한다. 비어 있으면 packaging 문제다. */
        val nativeLibDir: String,
        val nativeLibFiles: List<String>,
    )

    data class RunSpans(val totalNs: Long, val runOnlyNs: Long)

    private var env: Environment? = null
    private var model: CompiledModel? = null
    private var inputs: List<TensorBuffer> = emptyList()
    private var outputs: List<TensorBuffer> = emptyList()

    /**
     * 준비 비용 = idle -> 해당 자원 전환비용. 예외는 그대로 던진다.
     * **조용한 폴백을 만들지 않는다** — Accelerator 를 하나만 지정하는 이유가 그것이다 (SPEC §7).
     */
    fun init(): InitSpans {
        val libDir = context.applicationInfo.nativeLibraryDir

        val t0 = SystemClock.elapsedRealtimeNanos()
        val environment = Environment.create(
            context,
            mapOf(
                Environment.Option.DispatchLibraryDir to libDir,
                Environment.Option.CompilerPluginLibraryDir to libDir,
            ),
            /* enableCompilerCache = */ true,
        )
        env = environment
        val t1 = SystemClock.elapsedRealtimeNanos()

        // 진단용. NPU 가 여기 없으면 ENN 문제가 아니라 런타임/dispatch 짝이 안 맞는 것이다.
        val available = try {
            environment.getAvailableAccelerators()
        } catch (e: Throwable) {
            emptySet()
        }

        val libFiles = try {
            java.io.File(libDir).listFiles()?.map { it.name }?.sorted() ?: emptyList()
        } catch (e: Throwable) {
            emptyList()
        }

        val options = CompiledModel.Options(accelerator)
        val compiled = when {
            modelFilePath != null -> CompiledModel.create(modelFilePath, options, environment)
            modelAssetPath != null ->
                CompiledModel.create(context.assets, modelAssetPath, options, environment)
            else -> error("modelAssetPath or modelFilePath must be provided")
        }
        model = compiled
        val t2 = SystemClock.elapsedRealtimeNanos()

        inputs = compiled.createInputBuffers()
        outputs = compiled.createOutputBuffers()
        val t3 = SystemClock.elapsedRealtimeNanos()

        return InitSpans(
            envInitNs = t1 - t0,
            modelInitNs = t2 - t1,
            bufferInitNs = t3 - t2,
            availableAccelerators = available,
            inputCount = inputs.size,
            outputCount = outputs.size,
            nativeLibDir = libDir,
            nativeLibFiles = libFiles,
        )
    }

    /**
     * 입력 텐서의 원소 수를 텐서에서 읽는다 (MobileNet/EfficientNet 224, EfficientDet 320 으로 모델마다 다르다).
     * 2.2.0 Kotlin API 에는 텐서 이름 없이 shape 를 묻는 함수가 없어서, 만들어 둔 입력 버퍼를 한 번 읽어 잰다.
     * init() 직후 타이밍 루프 밖에서만 부를 것. uint8 텐서를 readFloat 로 읽으면 안 된다 (runInt8 주석 참조).
     */
    fun inputElementCount(useFloat: Boolean): Int {
        check(inputs.isNotEmpty()) { "call init() first" }
        return if (useFloat) inputs[0].readFloat().size else inputs[0].readInt8().size
    }

    /** FLOAT32 입력 1회 추론. */
    fun runFloat(input: FloatArray): Pair<RunSpans, FloatArray> {
        val m = model ?: error("call init() first")
        val t0 = SystemClock.elapsedRealtimeNanos()
        inputs[0].writeFloat(input)
        val r0 = SystemClock.elapsedRealtimeNanos()
        m.run(inputs, outputs)
        val r1 = SystemClock.elapsedRealtimeNanos()
        val result = outputs[0].readFloat()
        val t1 = SystemClock.elapsedRealtimeNanos()
        return RunSpans(totalNs = t1 - t0, runOnlyNs = r1 - r0) to result
    }

    /**
     * uint8 입력 1회 추론. 출력은 readInt8 을 먼저 읽고, 안 되면 readFloat 로 떨어진다.
     * 순서 주의: readFloat 는 uint8 텐서에서도 예외 없이 바이트를 float 로 재해석해 쓰레기를 준다
     * (2026-09-24 실측: top5 점수 9.4e-38 등, results/G4_summary_*_NPU_U8.json).
     */
    fun runInt8(input: ByteArray): Triple<RunSpans, FloatArray?, ByteArray?> {
        val m = model ?: error("call init() first")
        val t0 = SystemClock.elapsedRealtimeNanos()
        inputs[0].writeInt8(input)
        val r0 = SystemClock.elapsedRealtimeNanos()
        m.run(inputs, outputs)
        val r1 = SystemClock.elapsedRealtimeNanos()
        var asFloat: FloatArray? = null
        var asBytes: ByteArray? = null
        try {
            asBytes = outputs[0].readInt8()
        } catch (e: Throwable) {
            asFloat = outputs[0].readFloat()
        }
        val t1 = SystemClock.elapsedRealtimeNanos()
        return Triple(RunSpans(totalNs = t1 - t0, runOnlyNs = r1 - r0), asFloat, asBytes)
    }

    /** 닫는 순서: 버퍼 -> 모델 -> 환경 (SPEC §3). */
    override fun close() {
        inputs.forEach { runCatching { it.close() } }
        outputs.forEach { runCatching { it.close() } }
        runCatching { model?.close() }
        runCatching { env?.close() }
        inputs = emptyList()
        outputs = emptyList()
        model = null
        env = null
    }
}
