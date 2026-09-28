package com.example.d1check.npurunner

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.os.Handler
import android.os.HandlerThread
import android.os.Looper
import android.util.Log
import android.view.Gravity
import android.widget.ScrollView
import android.widget.TextView
import com.google.ai.edge.litert.Accelerator
import com.google.ai.edge.litert.CompiledModel
import java.io.File
import java.io.PrintWriter
import java.io.StringWriter

/**
 * G3/G4 — S26 NPU 첫 추론.
 *
 * 셸 바이너리(`run_model`)로는 binder 스레드 풀이 없어 ENN `MediumInterface initialization failed`
 * 가 났다. 앱 프로세스에는 그 제약이 없다. 이 Activity 가 그 차이를 확인하는 최소 실행기다.
 *
 * 수동:   앱 아이콘 실행 (기본값 = NPU / FP32 컴파일 모델 / 50회)
 * 자동:   adb shell am start -n com.example.d1check.npurunner/.NpuRunnerActivity \
 *           --es accelerator NPU --es dtype float --ei iterations 50 --ez autofinish true
 *
 * 결과는 logcat 태그 `D1NPU` 와 앱 전용 저장소의 summary.json 양쪽에 남는다.
 * logcat 에만 의존해도 되도록 JSON 전문을 청크로 나눠 출력한다 (run-as 불필요).
 */
class NpuRunnerActivity : Activity() {

    private lateinit var text: TextView
    private val ui = Handler(Looper.getMainLooper())
    private var worker: HandlerThread? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        text = TextView(this).apply {
            setPadding(24, 24, 24, 24)
            textSize = 11f
            setTextColor(Color.BLACK)
            gravity = Gravity.TOP or Gravity.START
            typeface = android.graphics.Typeface.MONOSPACE
        }
        setContentView(ScrollView(this).apply { addView(text) })
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        commandReplayStore = CommandReplayStore(this)

        // d1_auto_start 가 있으면 orchestrator 의 timed run. 없으면 아래 스모크/게이트 경로 (G4 그대로).
        if (handleAutomationIntent(intent)) return

        val cfg = Config.from(intent)
        append("D1 NPU Runner\n$cfg\n\nrunning...\n")

        worker = HandlerThread("npu-runner").also { it.start() }
        Handler(worker!!.looper).post { runAll(cfg) }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleAutomationIntent(intent)
    }

    override fun onDestroy() {
        worker?.quitSafely()
        timedExecutor.shutdownNow()
        super.onDestroy()
    }

    // ------------------------------------------------------------- timed run

    private lateinit var commandReplayStore: CommandReplayStore
    private val timedExecutor = java.util.concurrent.Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, NpuTimedRunEngine.THREAD_NAME)
    }

    /**
     * benchmark-runner MainActivity.handleAutomationIntent 미러 (accuracy preflight 분기는 없다 —
     * NPU 품질 게이트는 스모크 경로의 quality_n 으로 돈다). d1 요청이면 true.
     */
    private fun handleAutomationIntent(intent: Intent): Boolean {
        val values = buildMap<String, Any?> {
            if (intent.hasExtra(NpuAutomationIntentParser.EXTRA_AUTO_START)) {
                put(
                    NpuAutomationIntentParser.EXTRA_AUTO_START,
                    intent.getBooleanExtra(NpuAutomationIntentParser.EXTRA_AUTO_START, false),
                )
            }
            NpuAutomationIntentParser.stringExtras.forEach { key ->
                if (intent.hasExtra(key)) put(key, intent.getStringExtra(key))
            }
            NpuAutomationIntentParser.intExtras.forEach { key ->
                if (intent.hasExtra(key)) put(key, intent.getIntExtra(key, Int.MIN_VALUE))
            }
            NpuAutomationIntentParser.booleanExtras.forEach { key ->
                if (intent.hasExtra(key)) put(key, intent.getBooleanExtra(key, false))
            }
            if (intent.hasExtra(NpuAutomationIntentParser.EXTRA_DURATION_S)) {
                put(
                    NpuAutomationIntentParser.EXTRA_DURATION_S,
                    intent.getLongExtra(NpuAutomationIntentParser.EXTRA_DURATION_S, Long.MIN_VALUE),
                )
            }
            if (intent.hasExtra(NpuAutomationIntentParser.EXTRA_DUTY_CYCLE_PERIOD_S)) {
                put(
                    NpuAutomationIntentParser.EXTRA_DUTY_CYCLE_PERIOD_S,
                    intent.getFloatExtra(NpuAutomationIntentParser.EXTRA_DUTY_CYCLE_PERIOD_S, Float.NaN),
                )
            }
        }
        if (values[NpuAutomationIntentParser.EXTRA_AUTO_START] != true) return false
        val config = try {
            NpuAutomationIntentParser.parse(values)
        } catch (error: IllegalArgumentException) {
            append("Invalid automation request: ${error.message}\n")
            return true
        } ?: return false

        if (NpuExecutionGate.isRunning) {
            append("Automation request ignored: a benchmark is already running.\n")
            return true
        }
        val commandId = checkNotNull(config.commandId)
        if (!commandReplayStore.claim(commandId)) {
            append("Automation replay ignored: command_id=$commandId\n")
            return true
        }
        startTimedRun(config)
        return true
    }

    private fun startTimedRun(config: NpuRunConfig) {
        if (!NpuExecutionGate.tryAcquire()) {
            append("A benchmark is already running.\n")
            return
        }
        append("D1 NPU timed run\n$config\nBaseline 60 seconds. No NPU load has started yet.\n")
        timedExecutor.execute {
            val result = try {
                // 연쇄 모드(d1_npu_chain_b64)만 별도 실행기로 간다. 그 밖에는 기존 실행기 그대로
                if (config.chain != null) NpuChainRunEngine(applicationContext).execute(config)
                else NpuTimedRunEngine(applicationContext).execute(config)
            } catch (error: Throwable) {
                NpuTimedRunResult(false, "${error.javaClass.simpleName}: ${error.message}", null)
            }
            NpuExecutionGate.release()
            append(
                buildString {
                    append(if (result.success) "Complete" else "Failed")
                    append("\n").append(result.message)
                    result.flushResult?.let {
                        append("\nevents=").append(it.eventCount)
                        append("\nfile=").append(it.file.absolutePath)
                    }
                    append("\n")
                },
            )
        }
    }

    // ------------------------------------------------------------------ config

    data class Config(
        val accelerator: Accelerator,
        val modelAsset: String?,
        val modelPath: String?,
        val dtype: String,
        val iterations: Int,
        val warmup: Int,
        val elements: Int,
        val runId: String,
        val autofinish: Boolean,
        /** 품질 게이트 샘플 수. 0 이면 끔. NPU 판정에는 32 (NpuQualityGate). */
        val qualityN: Int,
        /** 품질 게이트의 CPU 기준 모델 (원본 FP32, benchmark-runner assets 공유). */
        val referenceAsset: String,
        /**
         * `--es ref_model_path` (2026-09-26 추가). 주면 CPU 기준 모델을 기기 파일에서 연다 —
         * APK 에 없는 원본(EfficientNet-Lite0 FP32 `6c7ab0a6…`)용. 없으면 referenceAsset (기존과 같음).
         */
        val referencePath: String? = null,
        /** `--es input_spec`. null = 기본 lcg-unit (MobileNet, 9/24 G4 게이트와 같은 입력). */
        val inputSpecName: String?,
        /**
         * `--es gpu_precision` (2026-09-28 추가). GPU 후보의 CompiledModel.GpuOptions.precision — timed run 의
         * d1_npu_gpu_precision 과 같은 설정으로 품질 게이트를 돌리기 위함. 없으면 설정 안 함 (기존과 같음).
         */
        val gpuPrecision: String? = null,
    ) {
        companion object {
            const val DEFAULT_ASSET_FP32 = "models/mobilenet_v1_1.0_224_Samsung_E9965.tflite"
            const val DEFAULT_REFERENCE_ASSET = "models/mobilenet_v1_1.0_224.tflite"

            fun from(i: Intent): Config {
                val accName = i.getStringExtra("accelerator") ?: "NPU"
                val acc = when (accName.uppercase()) {
                    "CPU" -> Accelerator.CPU
                    "GPU" -> Accelerator.GPU
                    "NPU" -> Accelerator.NPU
                    else -> Accelerator.NPU
                }
                val path = i.getStringExtra("model_path")
                val asset = i.getStringExtra("model_asset")
                    ?: if (path == null) DEFAULT_ASSET_FP32 else null
                return Config(
                    accelerator = acc,
                    modelAsset = asset,
                    modelPath = path,
                    dtype = (i.getStringExtra("dtype") ?: "float").lowercase(),
                    iterations = i.getIntExtra("iterations", 50).coerceIn(1, 250_000),
                    warmup = i.getIntExtra("warmup", 5).coerceIn(0, 10_000),
                    // 0 이하 = 입력 텐서에서 읽는다. 주면 텐서와 일치해야 한다 (불일치면 FAILED)
                    elements = i.getIntExtra("elements", 0),
                    runId = i.getStringExtra("run_id") ?: "manual-${System.currentTimeMillis()}",
                    autofinish = i.getBooleanExtra("autofinish", false),
                    qualityN = i.getIntExtra("quality_n", 0).coerceIn(0, 256),
                    referenceAsset = i.getStringExtra("ref_model_asset") ?: DEFAULT_REFERENCE_ASSET,
                    referencePath = i.getStringExtra("ref_model_path")?.takeIf { it.isNotBlank() },
                    inputSpecName = i.getStringExtra("input_spec"),
                    gpuPrecision = i.getStringExtra("gpu_precision")?.uppercase(),
                )
            }
        }

        override fun toString(): String =
            "accelerator=$accelerator dtype=$dtype iterations=$iterations warmup=$warmup " +
                "model=${modelPath ?: modelAsset} run_id=$runId quality_n=$qualityN " +
                "input_spec=${inputSpecName ?: "lcg-unit"}"
    }

    // ------------------------------------------------------------------- run

    private fun runAll(cfg: Config) {
        val j = StringBuilder()
        j.append("{")
        j.append(kv("schema", "npu-runner-smoke-v1")).append(",")
        j.append(kv("run_id", cfg.runId)).append(",")
        j.append(kv("engine", "litert-compiled-model")).append(",")
        j.append(kv("accelerator_requested", cfg.accelerator.name)).append(",")
        // 설정했을 때만 적는다 (기본 요약 JSON 은 기존과 바이트 동일)
        cfg.gpuPrecision?.let { j.append(kv("gpu_precision", it)).append(",") }
        j.append(kv("model", cfg.modelPath ?: cfg.modelAsset ?: "")).append(",")
        j.append(kv("dtype", cfg.dtype)).append(",")
        val spec = NpuDeterministicInput.InputSpec.fromWire(cfg.inputSpecName)
        j.append(kv("input_generator", spec?.generator ?: "unknown")).append(",")
        j.append(kv("input_normalization", spec?.normalization ?: "unknown")).append(",")
        j.append(kv("input_spec", spec?.wireName ?: cfg.inputSpecName.orEmpty())).append(",")
        j.append("\"iterations\":${cfg.iterations},\"warmup\":${cfg.warmup},")
        j.append("\"device_model\":\"${android.os.Build.MODEL}\",")
        j.append("\"android_sdk\":${android.os.Build.VERSION.SDK_INT},")
        j.append("\"build_fingerprint\":\"${android.os.Build.FINGERPRINT}\",")

        var engine: NpuBenchmarkEngine? = null
        try {
            val gpuPrecision = cfg.gpuPrecision?.let {
                require(cfg.accelerator == Accelerator.GPU && it in NpuRunConfig.GPU_PRECISIONS) {
                    "gpu_precision $it needs accelerator GPU and one of ${NpuRunConfig.GPU_PRECISIONS}"
                }
                CompiledModel.GpuOptions.Precision.valueOf(it)
            }
            engine = NpuBenchmarkEngine(
                context = this,
                accelerator = cfg.accelerator,
                modelAssetPath = cfg.modelAsset,
                modelFilePath = cfg.modelPath,
                gpuPrecision = gpuPrecision,
            )

            append("creating Environment / CompiledModel...\n")
            val spans = engine.init()
            val accList = spans.availableAccelerators.joinToString(",") { it.name }
            j.append(kv("available_accelerators", accList)).append(",")
            j.append("\"env_init_ms\":${ms(spans.envInitNs)},")
            j.append("\"model_init_ms\":${ms(spans.modelInitNs)},")
            j.append("\"buffer_init_ms\":${ms(spans.bufferInitNs)},")
            j.append("\"input_buffers\":${spans.inputCount},\"output_buffers\":${spans.outputCount},")
            j.append(kv("native_lib_dir", spans.nativeLibDir)).append(",")
            j.append(kv("native_lib_files", spans.nativeLibFiles.joinToString(","))).append(",")
            val hasDispatch = spans.nativeLibFiles.any { it.startsWith("libLiteRtDispatch") }
            j.append("\"dispatch_so_present\":$hasDispatch,")
            // 실행한 모델 파일의 SHA-256 — orchestrator 품질 preflight 와 d1_logger_v4 formal_npu_valid 가
            // aot_manifest.json 의 출력 SHA 와 대조한다. 타이밍 루프 밖에서 한 번만 읽는다.
            j.append(kv("model_sha256", modelSha256(cfg))).append(",")

            append(
                "init OK\n" +
                    "  available = [$accList]\n" +
                    "  env    ${ms(spans.envInitNs)} ms\n" +
                    "  model  ${ms(spans.modelInitNs)} ms   <- idle->${cfg.accelerator} switch cost\n" +
                    "  buffer ${ms(spans.bufferInitNs)} ms\n" +
                    "  nativeLibDir = ${spans.nativeLibDir}\n" +
                    "  libs = ${spans.nativeLibFiles}\n" +
                    "  dispatch .so present = ${spans.nativeLibFiles.any { it.startsWith("libLiteRtDispatch") }}\n\n",
            )

            val useFloat = cfg.dtype != "uint8" && cfg.dtype != "int8"
            requireNotNull(spec) { "unknown input_spec: ${cfg.inputSpecName}" }
            require(useFloat || spec == NpuDeterministicInput.InputSpec.LCG_UNIT) {
                "input_spec ${spec.wireName} is float-only (uint8 smoke uses lcg-unit)"
            }
            // 입력 원소 수는 모델마다 다르다 → 텐서에서 읽는다. --ei elements 를 주면 대조만 한다
            val elements = engine.inputElementCount(useFloat)
            require(cfg.elements <= 0 || cfg.elements == elements) {
                "--ei elements ${cfg.elements} != input tensor $elements"
            }
            j.append("\"input_elements\":$elements,")
            val inputF = if (useFloat) NpuDeterministicInput.inputSet(spec, 1, elements)[0] else FloatArray(0)
            val inputB = if (useFloat) ByteArray(0) else NpuDeterministicInput.uint8Bytes(elements)
            j.append(
                kv(
                    "input_sha256",
                    if (useFloat) NpuDeterministicInput.sha256(inputF)
                    else NpuDeterministicInput.sha256(inputB),
                ),
            ).append(",")

            // warm-up (기록에서 제외)
            repeat(cfg.warmup) {
                if (useFloat) engine.runFloat(inputF) else engine.runInt8(inputB)
            }

            val totals = DoubleArray(cfg.iterations)
            val runOnly = DoubleArray(cfg.iterations)
            var lastFloat: FloatArray? = null
            var lastBytes: ByteArray? = null

            for (n in 0 until cfg.iterations) {
                if (useFloat) {
                    val (s, out) = engine.runFloat(inputF)
                    totals[n] = ms(s.totalNs); runOnly[n] = ms(s.runOnlyNs); lastFloat = out
                } else {
                    val (s, outF, outB) = engine.runInt8(inputB)
                    totals[n] = ms(s.totalNs); runOnly[n] = ms(s.runOnlyNs)
                    lastFloat = outF; lastBytes = outB
                }
                if (n == 0) append("first inference OK: ${totals[0]} ms\n")
            }

            j.append(stats("latency_ms", totals)).append(",")
            j.append(stats("run_only_ms", runOnly)).append(",")

            // 출력 요약 — CPU 대조의 기준값
            val scores: FloatArray? = lastFloat
                ?: lastBytes?.let { b -> FloatArray(b.size) { (b[it].toInt() and 0xFF).toFloat() } }
            if (scores != null) {
                j.append("\"output_length\":${scores.size},")
                j.append(kv("output_sha256", NpuDeterministicInput.sha256(scores))).append(",")
                val top = scores.indices.sortedByDescending { scores[it] }.take(5)
                j.append("\"argmax\":${top.firstOrNull() ?: -1},")
                j.append("\"top5\":[")
                top.forEachIndexed { k, idx ->
                    if (k > 0) j.append(",")
                    j.append("{\"index\":$idx,\"score\":${scores[idx]}}")
                }
                j.append("],")
                append(
                    "\nresult\n" +
                        "  latency  median ${median(totals)} ms  p95 ${p95(totals)} ms\n" +
                        "  run() only median ${median(runOnly)} ms\n" +
                        "  argmax   ${top.firstOrNull()}\n" +
                        "  top5     ${top.joinToString(", ") { "$it(${"%.4f".format(scores[it])})" }}\n",
                )
            } else {
                j.append("\"output_length\":0,")
            }

            // 품질 게이트 — 타이밍 루프가 끝난 뒤에 돌리므로 latency 에 섞이지 않는다
            if (cfg.qualityN > 0) {
                j.append(runQualityGate(cfg, engine, useFloat, spec, elements, spans.outputCount)).append(",")
            }

            j.append(kv("status", "OK")).append(",").append(kv("error", ""))
            append("\n=== OK ===\n")
        } catch (t: Throwable) {
            val sw = StringWriter()
            t.printStackTrace(PrintWriter(sw))
            val trace = sw.toString()
            j.append(kv("status", "FAILED")).append(",")
            j.append(kv("error_class", t.javaClass.name)).append(",")
            j.append(kv("error", t.message ?: "")).append(",")
            j.append(kv("stacktrace", trace))
            Log.e(TAG, "run failed", t)
            append("\n=== FAILED ===\n${t.javaClass.name}: ${t.message}\n\n$trace\n")
        } finally {
            runCatching { engine?.close() }
        }
        j.append("}")

        val json = j.toString()
        writeSummary(cfg.runId, json)
        logChunks(json)

        if (cfg.autofinish) ui.postDelayed({ finish() }, 1500)
    }

    /**
     * 같은 n 개 입력을 후보(설정된 가속기·모델)와 CPU 기준(원본 FP32 모델)에 넣고 NpuQualityGate 로 판정.
     * CPU 기준도 같은 엔진(CompiledModel)이다. 판정 기준은 NpuQualityGate 에 고정돼 있다.
     */
    private fun runQualityGate(
        cfg: Config,
        candidate: NpuBenchmarkEngine,
        useFloat: Boolean,
        spec: NpuDeterministicInput.InputSpec,
        elements: Int,
        outputCount: Int,
    ): String {
        if (!useFloat) {
            // uint8 AOT 모델과 짝이 맞는 CPU 기준(원본 quant 모델)이 assets 에 없다
            append("quality gate: NOT_APPLICABLE (uint8)\n")
            return "\"quality_gate\":{\"version\":\"${NpuQualityGate.VERSION}\"," +
                "\"verdict\":\"NOT_APPLICABLE\",\"reason\":\"uint8 has no matching CPU reference model\"}"
        }
        if (outputCount != 1) {
            // 이 게이트는 단일 출력 벡터(분류) 전제다. 검출 모델(출력 2개 이상)을 outputs[0] 만으로
            // PASS 시키지 않도록 막는다. 검출 게이트 설계: measure/s26/npu/runner/NPU_DETECTOR_GATE_NOTE.md
            append("quality gate: NOT_APPLICABLE (outputs=$outputCount)\n")
            return "\"quality_gate\":{\"version\":\"${NpuQualityGate.VERSION}\"," +
                "\"verdict\":\"NOT_APPLICABLE\",\"reason\":\"multi-output model ($outputCount); " +
                "detector gate not implemented\"}"
        }
        append("quality gate: n=${cfg.qualityN} candidate=${cfg.accelerator} reference=CPU input=${spec.wireName}\n")
        val inputs = NpuDeterministicInput.inputSet(spec, cfg.qualityN, elements)
        val candidateOut = inputs.map { candidate.runFloat(it).second }
        val referenceOut = NpuBenchmarkEngine(
            context = this,
            accelerator = Accelerator.CPU,
            modelAssetPath = cfg.referenceAsset.takeIf { cfg.referencePath == null },
            modelFilePath = cfg.referencePath,
        ).use { cpu ->
            cpu.init()
            inputs.map { cpu.runFloat(it).second }
        }
        val result = NpuQualityGate.evaluate(referenceOut, candidateOut)
        append(
            "quality gate: ${if (result.pass) "PASS" else "FAIL"}  " +
                "bit_identical_to_cpu=${result.bitIdenticalToCpu} (${result.bitIdenticalCount}/${result.n})  " +
                "argmax=${result.argmaxAgreement}/${result.n}  cosine_min=${result.cosineMin}\n",
        )
        val referenceName = cfg.referencePath ?: cfg.referenceAsset
        val json = result.toJson(referenceName, "${cfg.accelerator}:${cfg.modelPath ?: cfg.modelAsset}")
        // 파일 기준일 때만 기준 모델 SHA 를 덧붙인다 (asset 기준 출력은 기존과 바이트 동일)
        return cfg.referencePath?.let { path ->
            json.removeSuffix("}") + ",\"reference_model_sha256\":\"${fileSha256(File(path))}\"}"
        } ?: json
    }

    // --------------------------------------------------------------- helpers

    private fun fileSha256(file: File): String {
        val digest = java.security.MessageDigest.getInstance("SHA-256")
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

    private fun modelSha256(cfg: Config): String {
        val digest = java.security.MessageDigest.getInstance("SHA-256")
        val stream = cfg.modelPath?.let { File(it).inputStream() }
            ?: assets.open(requireNotNull(cfg.modelAsset))
        stream.use { input ->
            val buffer = ByteArray(1 shl 16)
            while (true) {
                val n = input.read(buffer)
                if (n < 0) break
                digest.update(buffer, 0, n)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    private fun writeSummary(runId: String, json: String) {
        try {
            val dir = File(filesDir, "npu-runner-v1").apply { mkdirs() }
            File(dir, "summary-$runId.json").writeText(json)
            File(dir, "summary-latest.json").writeText(json)
        } catch (e: Throwable) {
            Log.w(TAG, "summary write failed: ${e.message}")
        }
    }

    /** logcat 은 긴 줄을 자른다. run-as 없이도 전문을 회수할 수 있도록 청크로 나눈다. */
    private fun logChunks(json: String) {
        val size = 2500
        val total = (json.length + size - 1) / size
        Log.i(TAG, "SUMMARY_BEGIN chunks=$total bytes=${json.length}")
        for (i in 0 until total) {
            val part = json.substring(i * size, minOf((i + 1) * size, json.length))
            Log.i(TAG, "SUMMARY[$i/$total] $part")
        }
        Log.i(TAG, "SUMMARY_END")
    }

    private fun append(s: String) {
        Log.i(TAG, s.trimEnd())
        ui.post { text.append(s) }
    }

    private fun kv(k: String, v: String): String = "\"$k\":\"${esc(v)}\""

    private fun esc(s: String): String = s
        .replace("\\", "\\\\").replace("\"", "\\\"")
        .replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")

    private fun ms(ns: Long): Double = Math.round(ns / 1_000.0) / 1000.0

    private fun median(a: DoubleArray): Double {
        val s = a.sortedArray()
        return if (s.isEmpty()) 0.0
        else if (s.size % 2 == 1) s[s.size / 2]
        else (s[s.size / 2 - 1] + s[s.size / 2]) / 2.0
    }

    private fun p95(a: DoubleArray): Double {
        if (a.isEmpty()) return 0.0
        val s = a.sortedArray()
        // nearest-rank (조민규 계약과 동일)
        val rank = Math.ceil(0.95 * s.size).toInt().coerceIn(1, s.size)
        return s[rank - 1]
    }

    private fun stats(name: String, a: DoubleArray): String {
        if (a.isEmpty()) return "\"$name\":null"
        val s = a.sortedArray()
        val mean = a.average()
        return "\"$name\":{\"count\":${a.size},\"mean\":${r(mean)},\"median\":${r(median(a))}," +
            "\"p95\":${r(p95(a))},\"min\":${r(s.first())},\"max\":${r(s.last())}}"
    }

    private fun r(v: Double): Double = Math.round(v * 1000.0) / 1000.0

    companion object {
        const val TAG = "D1NPU"
    }
}
