package com.example.d1check.requestrunner

import android.app.Activity
import android.graphics.BitmapFactory
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.Process
import android.os.SystemClock
import android.util.Log
import android.widget.TextView
import java.io.File
import java.util.concurrent.Executors

/**
 * M5 Q1 입력 목록 실행 = Activity 하나 = backend 하나 (SessionActivity 와 따로 — 세션 경로 무변경).
 *   adb shell am start -W -n com.example.d1check.requestrunner/.InputListActivity \
 *     --es d1_q1_manifest /data/local/tmp/quality20/q1_manifest.json --es d1_q1_backend CPU --es d1_q1_run_id <run_id>
 * 산출물: getExternalFilesDir("q1")/<run_id>/<backend>/ (호스트가 pull). 그 폴더가 이미 있으면 시작하지 않는다.
 * 화면: FLAG_KEEP_SCREEN_ON 을 쓰지 않는다 — 호스트가 screen_off_timeout 을 넣는다 (S26 관례).
 */
class InputListActivity : Activity() {
    private val setup = Executors.newSingleThreadExecutor { Thread(it, "d1q1-setup") }
    private val handler = Handler(Looper.getMainLooper())
    private val watchdog = Runnable { Process.killProcess(Process.myPid()) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(TextView(this).apply { text = "D1 Request Runner (M5 Q1 input list)"; setPadding(24, 24, 24, 24) })
        handler.postDelayed(watchdog, WATCHDOG_MS)
        setup.execute { runOnce() }
    }

    private fun runOnce() {
        var outcome = "not_started"
        try {
            val manifestPath = requireNotNull(intent.getStringExtra(EXTRA_MANIFEST)) { "missing $EXTRA_MANIFEST" }
            val backend = requireNotNull(intent.getStringExtra(EXTRA_BACKEND)) { "missing $EXTRA_BACKEND" }
            val runId = requireNotNull(intent.getStringExtra(EXTRA_RUN_ID)) { "missing $EXTRA_RUN_ID" }
            require(backend in InputListManifest.BACKENDS) { "backend $backend" }
            require(runId.matches(Regex("[A-Za-z0-9_.-]{1,64}"))) { "run_id" }
            val manifestFile = File(manifestPath)
            check(manifestFile.isFile && manifestFile.length() in 1..1_048_576) { "manifest file" }
            val bytes = manifestFile.readBytes()
            val manifest = InputListManifest.parse(String(bytes, Charsets.UTF_8)).also { it.validate() }
            val outRoot = File(getExternalFilesDir("q1"), "$runId/$backend")
            val apkSha = runCatching { TaskRuntime.sha256(File(applicationInfo.sourceDir)) }.getOrNull()
            Log.i(TAG, "activity_start run_id=$runId backend=$backend pid=${Process.myPid()} apk_sha256=$apkSha out=$outRoot")
            val engine = InputListEngine(
                manifest = manifest,
                manifestBytes = bytes,
                backend = backend,
                runId = runId,
                outRoot = outRoot,
                runtimeFactory = { spec -> CompiledModelRuntime(this, spec) },
                decodeImage = ::decodeBitmap,
                now = SystemClock::elapsedRealtimeNanos,
                identity = linkedMapOf(
                    "pid" to Process.myPid(), "apk_sha256_in_app" to apkSha, "package" to packageName,
                    "device_model" to Build.MODEL, "sdk_int" to Build.VERSION.SDK_INT, "native_lib_dir" to applicationInfo.nativeLibraryDir,
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
        setup.shutdown()
        super.onDestroy()
    }

    companion object {
        const val TAG = "D1Q1"
        const val EXTRA_MANIFEST = "d1_q1_manifest"
        const val EXTRA_BACKEND = "d1_q1_backend"
        const val EXTRA_RUN_ID = "d1_q1_run_id"
        /** 20장 × 2회 + PNG 1장 — Q20 (840 s) 과 같은 상한. */
        const val WATCHDOG_MS = 840_000L
    }
}
