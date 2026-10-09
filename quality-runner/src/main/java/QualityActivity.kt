package com.example.d1check.qualityrunner

import android.app.Activity
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.Process
import android.os.SystemClock
import android.util.Log
import android.widget.TextView
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.Executors

/**
 * Q20 한 실행 = Activity 하나 = backend 하나 (request-runner SessionActivity 와 같은 구조).
 *   adb shell am start -W -n com.example.d1check.qualityrunner/.QualityActivity \
 *     --es d1_q20_manifest /data/local/tmp/quality20/q20_manifest.json --es d1_q20_backend CPU --es d1_q20_run_id <run_id>
 * 산출물: getExternalFilesDir("quality20")/<run_id>/<backend>/ (호스트가 pull). 그 폴더가 이미 있으면 시작하지 않는다.
 * 화면: FLAG_KEEP_SCREEN_ON 을 쓰지 않는다 — 호스트가 screen_off_timeout 을 넣는다 (S26 관례).
 * logcat 태그 D1Q20 표시: activity_start · runtime create_start/end · image_start/end idx · activity_end (호스트 증거 창은 이것으로 자른다).
 */
class QualityActivity : Activity() {
    private val setup = Executors.newSingleThreadExecutor { Thread(it, "d1q20-setup") }
    private val handler = Handler(Looper.getMainLooper())
    private val watchdog = Runnable { Process.killProcess(Process.myPid()) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(TextView(this).apply { text = "D1 Quality Runner (S26 Q20)"; setPadding(24, 24, 24, 24) })
        handler.postDelayed(watchdog, QualityContract.WATCHDOG_MS)
        setup.execute { runOnce() }
    }

    private fun runOnce() {
        var outcome = "not_started"
        try {
            val manifestPath = requireNotNull(intent.getStringExtra(EXTRA_MANIFEST)) { "missing $EXTRA_MANIFEST" }
            val backend = requireNotNull(intent.getStringExtra(EXTRA_BACKEND)) { "missing $EXTRA_BACKEND" }
            val runId = requireNotNull(intent.getStringExtra(EXTRA_RUN_ID)) { "missing $EXTRA_RUN_ID" }
            require(backend in QualityContract.BACKENDS) { "backend $backend" }
            require(runId.matches(Regex("[A-Za-z0-9_.-]{1,64}"))) { "run_id" }
            val manifestFile = File(manifestPath)
            check(manifestFile.isFile && manifestFile.length() in 1..1_048_576) { "manifest file" }
            val bytes = manifestFile.readBytes()
            val manifest = QualityManifest.parse(String(bytes, Charsets.UTF_8)).also { it.validate() }
            val outRoot = File(getExternalFilesDir("quality20"), "$runId/$backend")
            val apkSha = runCatching { FileSha256.sha256(File(applicationInfo.sourceDir)) }.getOrNull()
            Log.i(TAG, "activity_start run_id=$runId backend=$backend pid=${Process.myPid()} apk_sha256=$apkSha out=$outRoot")
            val engine = QualityEngine(
                manifest = manifest,
                manifestBytes = bytes,
                backend = backend,
                runId = runId,
                outRoot = outRoot,
                runtimeFactory = { spec -> CompiledModelRuntime(this, spec) },
                now = SystemClock::elapsedRealtimeNanos,
                wallClock = { SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSXXX", Locale.US).format(Date()) },
                identity = linkedMapOf(
                    "pid" to Process.myPid(), "apk_sha256_in_app" to apkSha, "package" to packageName,
                    "device_model" to Build.MODEL, "device" to Build.DEVICE, "hardware" to Build.HARDWARE,
                    "sdk_int" to Build.VERSION.SDK_INT, "build_display" to Build.DISPLAY, "fingerprint" to Build.FINGERPRINT,
                    "native_lib_dir" to applicationInfo.nativeLibraryDir,
                ),
                log = { Log.i(TAG, it) },
            )
            outcome = if (engine.run()) "completed" else "runtime_failed"
        } catch (e: Throwable) {
            outcome = "error_before_engine: $e"
            Log.e(TAG, "run not started", e)
        } finally {
            Log.i(TAG, "activity_end outcome=$outcome")
            handler.removeCallbacks(watchdog)
            runOnUiThread { finish() }
        }
    }

    override fun onDestroy() {
        setup.shutdown()
        super.onDestroy()
    }

    companion object {
        const val TAG = QualityContract.LOG_TAG
        const val EXTRA_MANIFEST = "d1_q20_manifest"
        const val EXTRA_BACKEND = "d1_q20_backend"
        const val EXTRA_RUN_ID = "d1_q20_run_id"
    }
}
