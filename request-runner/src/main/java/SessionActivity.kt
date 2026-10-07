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
 * 세션 하나 = Activity 하나 (A24 ArrivalEnergyActivity 와 같은 구조).
 *   adb shell am start -W -n com.example.d1check.requestrunner/.SessionActivity \
 *     --es d1_session_manifest /data/local/tmp/mixreq/sessions/<sid>/a<attempt>/manifest.json \
 *     --es d1_session_id <sid> --es d1_command_id <uuid>
 * 산출물: getExternalFilesDir("mixreq")/<sid>/a<attempt>/ (호스트가 pull). 그 폴더가 이미 있으면 시작하지 않는다 (등록 §4 시도 번호).
 * 화면: FLAG_KEEP_SCREEN_ON 을 쓰지 않는다 — 호스트가 screen_off_timeout 을 넣는다 (S26 관례 · A24 와 다름).
 */
class SessionActivity : Activity() {
    private val setup = Executors.newSingleThreadExecutor { Thread(it, "d1mix-setup") }
    private val handler = Handler(Looper.getMainLooper())
    private val watchdog = Runnable { Process.killProcess(Process.myPid()) }
    @Volatile private var engine: SessionEngine? = null
    @Volatile private var finished = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(TextView(this).apply { text = "D1 Request Runner (S26 mixreq)"; setPadding(24, 24, 24, 24) })
        handler.postDelayed(watchdog, MixreqContract.WATCHDOG_MS)
        setup.execute { runSession() }
    }

    private fun runSession() {
        var outcome = "not_started"
        try {
            val manifestPath = requireNotNull(intent.getStringExtra(EXTRA_MANIFEST)) { "missing $EXTRA_MANIFEST" }
            val sid = requireNotNull(intent.getStringExtra(EXTRA_SESSION_ID)) { "missing $EXTRA_SESSION_ID" }
            val commandId = intent.getStringExtra(EXTRA_COMMAND_ID)
            val manifestFile = File(manifestPath)
            check(manifestFile.isFile && manifestFile.length() in 1..4_194_304) { "manifest file" }
            val bytes = manifestFile.readBytes()
            val manifest = SessionManifest.parse(String(bytes, Charsets.UTF_8)).also { it.validate() }
            check(manifest.sessionId == sid) { "session_id extra != manifest" }
            val outRoot = File(getExternalFilesDir("mixreq"), "$sid/a${manifest.attempt}")
            val apkSha = runCatching { TaskRuntime.sha256(File(applicationInfo.sourceDir)) }.getOrNull()
            Log.i(TAG, "activity_start sid=$sid attempt=${manifest.attempt} command_id=$commandId pid=${Process.myPid()} apk_sha256=$apkSha out=$outRoot")
            val sampler = BatterySampler(this)
            val built = SessionEngine(
                manifest = manifest,
                manifestBytes = bytes,
                inputsRoot = requireNotNull(manifestFile.parentFile),
                outRoot = outRoot,
                runtimeFactory = { spec -> CompiledModelRuntime(this, spec) },
                decodeImage = ::decodeBitmap,
                snapshot = sampler::snapshot,
                now = SystemClock::elapsedRealtimeNanos,
                identity = linkedMapOf(
                    "pid" to Process.myPid(), "apk_sha256" to apkSha, "device_model" to Build.MODEL,
                    "sdk_int" to Build.VERSION.SDK_INT, "command_id" to commandId, "package" to packageName,
                ),
                log = { Log.i(TAG, it) },
            )
            engine = built
            built.lifecycle("onCreate")
            outcome = if (built.run()) "completed" else "failed"
        } catch (e: Throwable) {
            outcome = "error_before_engine: $e"
            Log.e(TAG, "session not started", e)
        } finally {
            finished = true
            Log.i(TAG, "activity_end outcome=$outcome")
            handler.removeCallbacks(watchdog)
            runOnUiThread { finish() }
        }
    }

    /** A24 ProbeTaskAdapter 48~56행: BitmapFactory.decodeFile + getPixels (요청마다 같은 일). */
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

    override fun onStart() { super.onStart(); engine?.lifecycle("onStart") }
    override fun onResume() { super.onResume(); engine?.lifecycle("onResume") }
    override fun onPause() { engine?.lifecycle("onPause"); super.onPause() }
    override fun onStop() { engine?.lifecycle("onStop"); super.onStop() }
    override fun onDestroy() {
        if (!finished) engine?.stop?.compareAndSet(null, "lifecycle_cancelled")
        engine?.lifecycle("onDestroy")
        setup.shutdown()
        super.onDestroy()
    }

    companion object {
        const val TAG = MixreqContract.LOG_TAG
        const val EXTRA_MANIFEST = "d1_session_manifest"
        const val EXTRA_SESSION_ID = "d1_session_id"
        const val EXTRA_COMMAND_ID = "d1_command_id"
    }
}
