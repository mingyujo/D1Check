package com.example.d1check.requestrunner

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.graphics.BitmapFactory
import android.os.BatteryManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.os.Process
import android.os.SystemClock
import android.util.Log
import android.widget.TextView
import org.json.JSONObject
import java.io.BufferedWriter
import java.io.File
import java.io.OutputStreamWriter
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicReference

/**
 * M6 게이지 진단 E — d1sim/docs/M6_동일APK_사전등록_v3.md §2-1 (SHA-256 b57b8957…). 세션 경로 (SessionActivity · SessionEngine) 와 따로.
 *   adb shell am start -W -n com.example.d1check.requestrunner/.GaugeDiagActivity \
 *     --es d1_gauge_config /data/local/tmp/mixreq/gauge/<run_id>.json --es d1_gauge_run_id <run_id>
 * 꼴: (준비: 분류 CPU runtime 생성 + warmup 2) → 무부하 60 s (상주 · 추론 0) → 연속 부하 120 s (분류 CPU · 같은 모델 · numThreads 1 ·
 *   간격 없이 연속, 요청 경로와 같은 TaskRuntime.execute) → 쉼 120 s. 폴링 스레드 하나가 목표 20 ms 마다 같은 시계 (elapsedRealtimeNanos) 로
 *   CURRENT_NOW · CURRENT_AVERAGE · CHARGE_COUNTER · ENERGY_COUNTER · EXTRA_VOLTAGE (sticky) 와 읽기 전 · 후 · 필드별 끝 시각 · 구간 표식을 적는다.
 *   /sys/class/power_supply/battery/{current_now,voltage_now,charge_counter} 는 시작 때 1회 읽기 시험 → 읽히는 것만 같은 폴링에 추가.
 * 산출물: getExternalFilesDir("gauge")/<run_id>/ = config.json · header.json · samples.jsonl · markers.jsonl · inferences.jsonl · summary.json
 *   (호스트가 pull). 그 폴더가 이미 있으면 시작하지 않는다. 안전 멈춤 = 세션과 같은 규칙 (plugged · thermal status ≥ 3 · BAT ≥ 42.0 ℃ ·
 *   SOC < 20 · 화면 꺼짐) — status 는 1 s 마다, sticky (plugged · BAT · SOC) 는 매 폴링.
 * 화면: FLAG_KEEP_SCREEN_ON 을 쓰지 않는다 — 호스트가 screen_off_timeout 을 넣는다 (S26 관례).
 */
class GaugeDiagActivity : Activity() {
    private val setup = Executors.newSingleThreadExecutor { Thread(it, "d1gauge-main") }
    private val handler = Handler(Looper.getMainLooper())
    private val watchdog = Runnable { Process.killProcess(Process.myPid()) }
    @Volatile private var diag: GaugeDiag? = null
    @Volatile private var finished = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(TextView(this).apply { text = "D1 Request Runner (M6 gauge diagnostic)"; setPadding(24, 24, 24, 24) })
        handler.postDelayed(watchdog, GaugeConfig.WATCHDOG_MS)
        setup.execute { runOnce() }
    }

    private fun runOnce() {
        var outcome = "not_started"
        try {
            val configPath = requireNotNull(intent.getStringExtra(EXTRA_CONFIG)) { "missing $EXTRA_CONFIG" }
            val runId = requireNotNull(intent.getStringExtra(EXTRA_RUN_ID)) { "missing $EXTRA_RUN_ID" }
            require(runId.matches(Regex("[A-Za-z0-9_.-]{1,64}"))) { "run_id" }
            val configFile = File(configPath)
            check(configFile.isFile && configFile.length() in 1..65_536) { "config file" }
            val bytes = configFile.readBytes()
            val config = GaugeConfig.parse(String(bytes, Charsets.UTF_8)).also { it.validate() }
            require(config.runId == runId) { "run_id extra != config" }
            val outRoot = File(getExternalFilesDir("gauge"), runId)
            val apkSha = runCatching { TaskRuntime.sha256(File(applicationInfo.sourceDir)) }.getOrNull()
            Log.i(TAG, "activity_start run_id=$runId pid=${Process.myPid()} apk_sha256=$apkSha out=$outRoot")
            val built = GaugeDiag(
                config = config,
                configBytes = bytes,
                outRoot = outRoot,
                source = AndroidGaugeSource(this),
                prepareLoad = { prepareClassificationCpu(config) },
                now = SystemClock::elapsedRealtimeNanos,
                identity = linkedMapOf(
                    "pid" to Process.myPid(), "apk_sha256" to apkSha, "device_model" to Build.MODEL, "sdk_int" to Build.VERSION.SDK_INT,
                    "package" to packageName,
                ),
                log = { Log.i(TAG, it) },
            )
            diag = built
            outcome = built.run()
        } catch (e: Throwable) {
            outcome = "error_before_run: $e"
            Log.e(TAG, "gauge run not started", e)
        } finally {
            finished = true
            Log.i(TAG, "activity_end outcome=$outcome")
            handler.removeCallbacks(watchdog)
            runOnUiThread { finish() }
        }
    }

    /** 기존 Runtimes 의 생성 · 실행 함수 호출만: CompiledModelRuntime (CPU · numThreads 1) + TaskRuntime.execute (요청 경로와 같은 이미지 파이프라인). */
    private fun prepareClassificationCpu(config: GaugeConfig): GaugeDiag.Load {
        val spec = RuntimeSpec("classification_CPU", "classification", Backend.CPU, config.model.path, config.model.sha256, cpuThreads = 1)
        val modelSha = TaskRuntime.sha256(File(spec.modelPath))
        check(modelSha == spec.modelSha256) { "model SHA-256 $modelSha != ${spec.modelSha256}" }
        val labelsFile = File(config.labels.path)
        check(TaskRuntime.sha256(labelsFile) == config.labels.sha256) { "labels SHA-256 mismatch" }
        val image = File(config.image.path)
        check(TaskRuntime.sha256(image) == config.image.sha256) { "image SHA-256 mismatch" }
        val task = TaskRuntime(spec, CompiledModelRuntime(this, spec), TaskRuntime.labelLines(labelsFile.readText(Charsets.UTF_8)),
            emptyList(), ::decodeBitmap, SystemClock::elapsedRealtimeNanos)
        return object : GaugeDiag.Load {
            override val initRecord: Map<String, Any?> get() = task.initRecord
            override fun runOne(): Map<String, Any?> {
                val record = task.execute(image, config.image.sha256).record
                return linkedMapOf("inference_ns" to record["inference_ns"], "top1" to (record["results"] as? List<*>)?.firstOrNull())
            }
            override fun close() = task.close()
        }
    }

    /** SessionActivity.decodeBitmap 과 같은 줄 (A24 ProbeTaskAdapter 48~56행). */
    private fun decodeBitmap(file: File): DecodedImage {
        val bitmap = requireNotNull(BitmapFactory.decodeFile(file.absolutePath)) { "BitmapFactory returned null" }
        try {
            val width = bitmap.width
            val height = bitmap.height
            require(width in 1..4096 && height in 1..4096) { "bitmap geometry" }
            val pixels = IntArray(width * height)
            bitmap.getPixels(pixels, 0, width, 0, 0, width, height)
            return DecodedImage(width, height, ImageContract.rgbFromArgb(pixels))
        } finally {
            bitmap.recycle()
        }
    }

    override fun onDestroy() {
        if (!finished) diag?.stop?.compareAndSet(null, "lifecycle_cancelled")
        setup.shutdown()
        super.onDestroy()
    }

    companion object {
        const val TAG = "D1GAUGE"
        const val EXTRA_CONFIG = "d1_gauge_config"
        const val EXTRA_RUN_ID = "d1_gauge_run_id"
    }
}

/** 호스트 (s26/tools/mixreq/m6_gauge.ps1) 가 만드는 실행 설정. 앱은 등록 값과 다시 대조한다 (fail closed). */
class GaugeConfig(
    val experimentId: String,
    val runId: String,
    val idleMs: Long,
    val loadMs: Long,
    val restMs: Long,
    val pollTargetMs: Long,
    val model: SessionManifest.FileSpec,
    val image: SessionManifest.FileSpec,
    val labels: SessionManifest.FileSpec,
) {
    fun validate() {
        require(runId.matches(Regex("[A-Za-z0-9_.-]{1,64}"))) { "run_id" }
        when (experimentId) {
            MixreqContract.M6_E_EXPERIMENT_ID -> require(idleMs == IDLE_MS && loadMs == LOAD_MS && restMs == REST_MS && pollTargetMs == POLL_TARGET_MS) {
                "S26-M6-E needs the registered segments $IDLE_MS/$LOAD_MS/$REST_MS ms and poll $POLL_TARGET_MS ms"
            }
            MixreqContract.M6_E_SMOKE_EXPERIMENT_ID -> require(idleMs in 100..IDLE_MS && loadMs in 100..LOAD_MS && restMs in 100..REST_MS &&
                pollTargetMs == POLL_TARGET_MS) { "smoke segments must be shorter than the registered ones" }
            else -> error("unknown gauge experiment_id $experimentId")
        }
        require(!model.path.endsWith("_Samsung_E9965.tflite")) { "gauge load is classification CPU (not the NPU AOT artifact)" }
    }

    companion object {
        /** 등록 §2-1: 무부하 60 → 연속 부하 120 → 쉼 120 s · 목표 20 ms. */
        const val IDLE_MS = 60_000L
        const val LOAD_MS = 120_000L
        const val REST_MS = 120_000L
        const val POLL_TARGET_MS = 20L
        /** 준비 (≤ 150 s) + 300 s + 여유 = 600 s. */
        const val WATCHDOG_MS = 600_000L

        fun parse(text: String): GaugeConfig {
            val c = JSONObject(text)
            fun file(name: String) = c.getJSONObject(name).let { SessionManifest.FileSpec(it.getString("path"), it.getString("sha256")) }
            return GaugeConfig(
                experimentId = c.getString("experiment_id"),
                runId = c.getString("run_id"),
                idleMs = c.getLong("idle_ms"),
                loadMs = c.getLong("load_ms"),
                restMs = c.getLong("rest_ms"),
                pollTargetMs = c.getLong("poll_target_ms"),
                model = file("model"),
                image = file("image"),
                labels = file("labels"),
            )
        }
    }
}

/** 게이지 읽기. 운영 = AndroidGaugeSource · 시험 = 가짜. 각 읽기는 값 하나 (실패하면 예외 → 기록). */
interface GaugeSource {
    fun currentNow(): Int
    fun currentAverage(): Int
    fun chargeCounter(): Int
    fun energyCounter(): Long
    /** ACTION_BATTERY_CHANGED sticky: voltage_mV · plugged · battery_temperature_deci_c · battery_level. */
    fun sticky(): Map<String, Any?>
    /** 1 s 마다: thermal_status · interactive. */
    fun status(): Map<String, Any?>
    /** sysfs 파일 한 개 (trim). 읽을 수 없으면 예외. */
    fun sysfs(path: String): String
}

class AndroidGaugeSource(private val context: Context) : GaugeSource {
    private val bm = context.getSystemService(BatteryManager::class.java)
    private val pm = context.getSystemService(PowerManager::class.java)
    private val filter = IntentFilter(Intent.ACTION_BATTERY_CHANGED)

    override fun currentNow(): Int = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CURRENT_NOW)
    override fun currentAverage(): Int = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CURRENT_AVERAGE)
    override fun chargeCounter(): Int = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CHARGE_COUNTER)
    override fun energyCounter(): Long = bm.getLongProperty(BatteryManager.BATTERY_PROPERTY_ENERGY_COUNTER)
    override fun sticky(): Map<String, Any?> {
        val b = context.registerReceiver(null, filter)
        return linkedMapOf(
            "voltage_mV" to b?.getIntExtra(BatteryManager.EXTRA_VOLTAGE, -1),
            "plugged" to b?.getIntExtra(BatteryManager.EXTRA_PLUGGED, -1),
            "battery_temperature_deci_c" to b?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1),
            "battery_level" to b?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1),
        )
    }
    override fun status(): Map<String, Any?> = linkedMapOf("thermal_status" to pm.currentThermalStatus, "interactive" to pm.isInteractive)
    override fun sysfs(path: String): String = File(path).readText().trim()
}

/**
 * 진단 실행기 (Android 의존 없음 — 시계 · 읽기 · 부하는 주입). run() = 출력 폴더 → sysfs 시험 → 부하 준비 (생성 + warmup 2) →
 * 폴링 시작 → idle → load → rest → 폴링 멈춤 → summary. 반환 = "completed" | "stopped: <이유>" | "failed: <오류>".
 */
class GaugeDiag(
    private val config: GaugeConfig,
    private val configBytes: ByteArray,
    private val outRoot: File,
    private val source: GaugeSource,
    private val prepareLoad: () -> Load,
    private val now: () -> Long,
    private val identity: Map<String, Any?> = emptyMap(),
    private val log: (String) -> Unit = {},
) {
    interface Load : AutoCloseable {
        val initRecord: Map<String, Any?>
        fun runOne(): Map<String, Any?>
    }

    val stop = AtomicReference<String?>(null)
    private val phase = AtomicReference("setup")
    @Volatile private var polling = false
    private var sysfsPaths: List<String> = emptyList()
    private val markers = mutableListOf<Map<String, Any?>>()
    private var pollCount = 0L
    private var pollErrors = 0L
    private val intervalsNs = ArrayList<Long>()

    private fun marker(name: String, extra: Map<String, Any?> = emptyMap()) {
        val m = linkedMapOf<String, Any?>("kind" to "marker", "marker" to name, "t_ns" to now()) + extra
        synchronized(markers) { markers += m }
        log("marker $name")
    }

    /** 등록 §3-4 앱 안 멈춤 규칙 (SessionEngine.stopReason 과 같은 기준값). */
    fun stopReason(sticky: Map<String, Any?>, status: Map<String, Any?>?): String? {
        val plugged = (sticky["plugged"] as? Number)?.toInt()
        val temperature = (sticky["battery_temperature_deci_c"] as? Number)?.toInt()
        val level = (sticky["battery_level"] as? Number)?.toInt()
        return when {
            plugged == null || plugged != 0 -> "plugged_$plugged"
            temperature == null || temperature >= 420 -> "bat_deci_c_$temperature"
            level == null || level < 20 -> "soc_$level"
            status != null && ((status["thermal_status"] as? Number)?.toInt() ?: 99) > 2 -> "thermal_status_${status["thermal_status"]}"
            status != null && status["interactive"] != true -> "screen_off"
            else -> null
        }
    }

    private fun probeSysfs(): Map<String, Any?> = SYSFS.associateWith { path ->
        try {
            linkedMapOf("readable" to true, "value" to source.sysfs(path))
        } catch (e: Throwable) {
            linkedMapOf("readable" to false, "error" to e.toString())
        }
    }

    /** 폴링 1회 = 한 줄. 필드마다 끝 시각 (t_*) — 읽기 순서는 고정: current_now → current_avg → charge_counter → energy → sticky → (status) → sysfs. */
    private fun pollOnce(seq: Long, withStatus: Boolean): Pair<Map<String, Any?>, String?> {
        val row = linkedMapOf<String, Any?>("kind" to "s", "seq" to seq, "phase" to phase.get())
        val t0 = now()
        row["t0"] = t0
        fun <T> field(name: String, read: () -> T) {
            try {
                row[name] = read()
            } catch (e: Throwable) {
                row[name] = null
                row["${name}_error"] = e.toString()
                pollErrors++
            }
            row["t_$name"] = now()
        }
        field("current_now") { source.currentNow() }
        field("current_avg") { source.currentAverage() }
        field("charge_counter") { source.chargeCounter() }
        field("energy_counter") { source.energyCounter() }
        var sticky: Map<String, Any?> = emptyMap()
        field("sticky") { source.sticky().also { sticky = it } }
        var status: Map<String, Any?>? = null
        if (withStatus) field("status") { source.status().also { status = it } }
        for (path in sysfsPaths) field("sysfs_" + path.substringAfterLast('/')) { source.sysfs(path) }
        row["t1"] = now()
        // sticky 읽기가 실패한 폴링은 멈춤 판정에 쓰지 않는다 (오류는 그 줄에 기록)
        return row to if (sticky.isEmpty()) null else stopReason(sticky, status)
    }

    private fun pollLoop(out: BufferedWriter) {
        val period = config.pollTargetMs * 1_000_000L
        var next = now()
        var last: Long? = null
        var lastFlush = now()
        var seq = 0L
        while (polling) {
            val (row, reason) = pollOnce(seq, seq % STATUS_EVERY == 0L)
            val t0 = row["t0"] as Long
            last?.let { intervalsNs += t0 - it }
            last = t0
            out.write(Json.encode(row))
            out.write("\n")
            pollCount++
            seq++
            if (reason != null && stop.compareAndSet(null, "environment/$reason")) log("stop $reason")
            if (now() - lastFlush >= 1_000_000_000L) {
                out.flush()
                lastFlush = now()
            }
            next += period
            val wait = next - now()
            if (wait > 0) Thread.sleep(wait / 1_000_000L, (wait % 1_000_000L).toInt()) else next = now()
        }
        out.flush()
    }

    private fun sleepWhileOk(durationMs: Long) {
        val end = now() + durationMs * 1_000_000L
        while (now() < end && stop.get() == null) Thread.sleep(minOf(50L, maxOf(1L, (end - now()) / 1_000_000L)))
    }

    fun run(): String {
        check(!outRoot.exists() && outRoot.mkdirs()) { "run folder exists or not creatable: $outRoot" }
        val store = ArtifactStore(outRoot)
        store.saveBytes("config.json", configBytes)
        var result = "completed"
        var load: Load? = null
        var poller: Thread? = null
        var pollFailure: String? = null
        val inferences = BufferedWriter(OutputStreamWriter(File(outRoot, "inferences.jsonl").outputStream(), Charsets.UTF_8))
        val samples = BufferedWriter(OutputStreamWriter(File(outRoot, "samples.jsonl").outputStream(), Charsets.UTF_8), 1 shl 16)
        var energyFirst: Any? = null
        var sysfs: Map<String, Any?> = emptyMap()
        try {
            marker("setup_start")
            sysfs = probeSysfs()
            sysfsPaths = SYSFS.filter { (sysfs[it] as Map<*, *>)["readable"] == true }
            energyFirst = runCatching { source.energyCounter() }.getOrElse { "error: $it" }
            load = prepareLoad()
            repeat(WARMUPS) { i ->
                val s = now()
                load.runOne()
                marker("warmup", mapOf("index" to i, "start_ns" to s))
            }
            store.save("header.json", linkedMapOf(
                "schema" to SCHEMA, "experiment_id" to config.experimentId, "run_id" to config.runId,
                "segments_ms" to linkedMapOf("idle" to config.idleMs, "load" to config.loadMs, "rest" to config.restMs),
                "poll_target_ms" to config.pollTargetMs, "clock" to "SystemClock.elapsedRealtimeNanos",
                "field_order" to listOf("current_now", "current_avg", "charge_counter", "energy_counter", "sticky", "status (1 s)") + sysfsPaths,
                "status_every_polls" to STATUS_EVERY, "sysfs_probe" to sysfs, "sysfs_polled" to sysfsPaths,
                "energy_counter_first" to energyFirst, "energy_counter_unsupported_value" to Long.MIN_VALUE,
                "load" to linkedMapOf("key" to "classification_CPU", "num_threads" to 1, "path" to "TaskRuntime.execute (request path)",
                    "model" to config.model.path, "model_sha256" to config.model.sha256, "warmups_before_idle" to WARMUPS),
                "load_init" to load.initRecord,
            ) + identity)
            polling = true
            poller = Thread({
                try {
                    pollLoop(samples)
                } catch (e: Throwable) {
                    pollFailure = e.toString()
                    stop.compareAndSet(null, "poll_failed: $e")
                }
            }, "d1gauge-poll").apply { start() }

            phase.set("idle")
            marker("idle_start")
            sleepWhileOk(config.idleMs)
            marker("idle_end")

            phase.set("load")
            marker("load_start")
            val loadEnd = now() + config.loadMs * 1_000_000L
            var n = 0L
            while (now() < loadEnd && stop.get() == null) {
                val s = now()
                val rec = load.runOne()
                val e = now()
                inferences.write(Json.encode(linkedMapOf<String, Any?>("n" to n++, "start_ns" to s, "end_ns" to e) + rec))
                inferences.write("\n")
            }
            marker("load_end", mapOf("inferences" to n))

            phase.set("rest")
            marker("rest_start")
            sleepWhileOk(config.restMs)
            marker("rest_end")
            stop.get()?.let { result = "stopped: $it" }
        } catch (e: Throwable) {
            stop.compareAndSet(null, e.toString())
            result = "failed: $e"
            log("gauge failed $e")
        } finally {
            polling = false
            poller?.join(5_000)
            runCatching { samples.close() }
            runCatching { inferences.close() }
            runCatching { load?.close() }
            val sorted = intervalsNs.sorted()
            fun q(p: Double) = if (sorted.isEmpty()) null else sorted[((sorted.size - 1) * p).toInt()]
            runCatching {
                File(outRoot, "markers.jsonl").writeText(synchronized(markers) { markers.joinToString("") { Json.encode(it) + "\n" } })
            }
            runCatching {
                store.save("summary.json", linkedMapOf(
                    "schema" to SCHEMA, "status" to result, "stop_reason" to stop.get(), "poll_failure" to pollFailure,
                    "experiment_id" to config.experimentId, "run_id" to config.runId, "polls" to pollCount, "poll_field_errors" to pollErrors,
                    "poll_interval_ns" to linkedMapOf("median" to q(0.5), "p05" to q(0.05), "p95" to q(0.95), "max" to sorted.lastOrNull()),
                    "sysfs_polled" to sysfsPaths, "energy_counter_first" to energyFirst,
                ) + identity)
            }
            log("gauge_end status=$result polls=$pollCount")
        }
        return result
    }

    companion object {
        const val SCHEMA = "s26-m6-gauge-diag-v1"
        const val WARMUPS = 2
        /** thermal status · interactive 는 50 폴링 (목표 1 s) 마다. */
        const val STATUS_EVERY = 50L
        val SYSFS = listOf(
            "/sys/class/power_supply/battery/current_now",
            "/sys/class/power_supply/battery/voltage_now",
            "/sys/class/power_supply/battery/charge_counter",
        )
    }
}
