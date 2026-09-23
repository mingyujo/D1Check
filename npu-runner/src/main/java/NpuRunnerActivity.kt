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

        val cfg = Config.from(intent)
        append("D1 NPU Runner\n$cfg\n\nrunning...\n")

        worker = HandlerThread("npu-runner").also { it.start() }
        Handler(worker!!.looper).post { runAll(cfg) }
    }

    override fun onDestroy() {
        worker?.quitSafely()
        super.onDestroy()
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
                    elements = i.getIntExtra("elements", NpuDeterministicInput.DEFAULT_ELEMENT_COUNT),
                    runId = i.getStringExtra("run_id") ?: "manual-${System.currentTimeMillis()}",
                    autofinish = i.getBooleanExtra("autofinish", false),
                    qualityN = i.getIntExtra("quality_n", 0).coerceIn(0, 256),
                    referenceAsset = i.getStringExtra("ref_model_asset") ?: DEFAULT_REFERENCE_ASSET,
                )
            }
        }

        override fun toString(): String =
            "accelerator=$accelerator dtype=$dtype iterations=$iterations warmup=$warmup " +
                "model=${modelPath ?: modelAsset} run_id=$runId quality_n=$qualityN"
    }

    // ------------------------------------------------------------------- run

    private fun runAll(cfg: Config) {
        val j = StringBuilder()
        j.append("{")
        j.append(kv("schema", "npu-runner-smoke-v1")).append(",")
        j.append(kv("run_id", cfg.runId)).append(",")
        j.append(kv("engine", "litert-compiled-model")).append(",")
        j.append(kv("accelerator_requested", cfg.accelerator.name)).append(",")
        j.append(kv("model", cfg.modelPath ?: cfg.modelAsset ?: "")).append(",")
        j.append(kv("dtype", cfg.dtype)).append(",")
        j.append(kv("input_generator", NpuDeterministicInput.VERSION)).append(",")
        j.append(kv("input_normalization", NpuDeterministicInput.NORMALIZATION)).append(",")
        j.append("\"iterations\":${cfg.iterations},\"warmup\":${cfg.warmup},")
        j.append("\"device_model\":\"${android.os.Build.MODEL}\",")
        j.append("\"android_sdk\":${android.os.Build.VERSION.SDK_INT},")
        j.append("\"build_fingerprint\":\"${android.os.Build.FINGERPRINT}\",")

        var engine: NpuBenchmarkEngine? = null
        try {
            engine = NpuBenchmarkEngine(
                context = this,
                accelerator = cfg.accelerator,
                modelAssetPath = cfg.modelAsset,
                modelFilePath = cfg.modelPath,
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
            val inputF = if (useFloat) NpuDeterministicInput.floats(cfg.elements) else FloatArray(0)
            val inputB = if (useFloat) ByteArray(0) else NpuDeterministicInput.uint8Bytes(cfg.elements)
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
                j.append(runQualityGate(cfg, engine, useFloat)).append(",")
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
    private fun runQualityGate(cfg: Config, candidate: NpuBenchmarkEngine, useFloat: Boolean): String {
        if (!useFloat) {
            // uint8 AOT 모델과 짝이 맞는 CPU 기준(원본 quant 모델)이 assets 에 없다
            append("quality gate: NOT_APPLICABLE (uint8)\n")
            return "\"quality_gate\":{\"version\":\"${NpuQualityGate.VERSION}\"," +
                "\"verdict\":\"NOT_APPLICABLE\",\"reason\":\"uint8 has no matching CPU reference model\"}"
        }
        append("quality gate: n=${cfg.qualityN} candidate=${cfg.accelerator} reference=CPU\n")
        val inputs = NpuDeterministicInput.floatSet(cfg.qualityN, cfg.elements)
        val candidateOut = inputs.map { candidate.runFloat(it).second }
        val referenceOut = NpuBenchmarkEngine(
            context = this,
            accelerator = Accelerator.CPU,
            modelAssetPath = cfg.referenceAsset,
            modelFilePath = null,
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
        return result.toJson(cfg.referenceAsset, "${cfg.accelerator}:${cfg.modelPath ?: cfg.modelAsset}")
    }

    // --------------------------------------------------------------- helpers

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
