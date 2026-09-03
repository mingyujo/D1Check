package com.example.d1check

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.os.SystemClock
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import org.json.JSONObject
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledFuture
import java.util.concurrent.TimeUnit

class TelemetryForegroundService : Service() {
    private val executor = Executors.newSingleThreadScheduledExecutor { runnable ->
        Thread(runnable, "d1check-sampler")
    }
    private lateinit var sessionStore: RunSessionStore
    private var scheduledTask: ScheduledFuture<*>? = null
    @Volatile private var writer: TelemetryLogWriter? = null
    @Volatile private var run: RunContext? = null
    private var tick = 0L
    private var headroomNow = Float.NaN
    private var headroom60s = Float.NaN
    private var cleanStop = false
    private var nextSampleNs = 0L

    override fun onCreate() {
        super.onCreate()
        sessionStore = RunSessionStore(this)
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(NOTIFICATION_ID, buildNotification())
        if (intent?.action == ACTION_STOP) {
            stopRun("user_stop")
            stopSelf()
            return START_NOT_STICKY
        }

        val forceNew = intent?.getBooleanExtra(EXTRA_FORCE_NEW_RUN, false) == true
        val requestedRunId = intent?.getStringExtra(EXTRA_RUN_ID)
        if (forceNew && run != null) stopRun("replaced_by_new_run")
        if (run == null) startRun(forceNew, requestedRunId)
        return START_STICKY
    }

    override fun onDestroy() {
        scheduledTask?.cancel(false)
        synchronized(this) {
            if (!cleanStop) recordEvent("service_destroyed", "abnormal")
            writer?.close()
            run?.let { sessionStore.markInactive(it.runId) }
        }
        executor.shutdown()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    @Synchronized
    private fun startRun(forceNew: Boolean, requestedRunId: String?) {
        cleanStop = false
        tick = 0L
        headroomNow = Float.NaN
        headroom60s = Float.NaN
        run = sessionStore.getOrCreate(forceNew, requestedRunId)
        writer = TelemetryLogWriter(this, requireNotNull(run).runId)
        recordEvent("run_start", "ok", mapOf("file" to writer?.file?.absolutePath))
        nextSampleNs = SystemClock.elapsedRealtimeNanos()
        scheduledTask = executor.schedule({ sampleAndScheduleNext() }, 0L, TimeUnit.NANOSECONDS)
    }

    @Synchronized
    private fun stopRun(reason: String) {
        scheduledTask?.cancel(false)
        scheduledTask = null
        recordEvent("run_stop", "ok", mapOf("reason" to reason))
        run?.let { sessionStore.markInactive(it.runId) }
        writer?.close()
        writer = null
        run = null
        cleanStop = true
    }

    @Synchronized
    private fun sampleSafely() {
        try {
            sample()
        } catch (error: Throwable) {
            Log.e(EVENT_TAG, "Telemetry sample failed", error)
            recordEvent(
                "sample_error",
                "error",
                mapOf("error" to (error.message ?: error.javaClass.simpleName)),
            )
        }
    }

    private fun sampleAndScheduleNext() {
        if (run == null) return
        sampleSafely()
        if (run == null) return

        nextSampleNs += SAMPLE_PERIOD_NS
        val nowNs = SystemClock.elapsedRealtimeNanos()
        if (nextSampleNs <= nowNs) {
            // Skip missed ticks instead of emitting a burst after suspension or a slow sample.
            nextSampleNs = nowNs + SAMPLE_PERIOD_NS
        }
        scheduledTask = executor.schedule(
            { sampleAndScheduleNext() },
            nextSampleNs - nowNs,
            TimeUnit.NANOSECONDS,
        )
    }

    @Synchronized
    private fun sample() {
        val activeRun = run ?: return
        val monoNs = SystemClock.elapsedRealtimeNanos()
        val wallMs = System.currentTimeMillis()
        val powerManager = getSystemService(POWER_SERVICE) as PowerManager
        val batteryManager = getSystemService(BATTERY_SERVICE) as BatteryManager

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            if (tick % 2L == 0L) {
                headroomNow = powerManager.getThermalHeadroom(0)
            } else {
                headroom60s = powerManager.getThermalHeadroom(60)
            }
        }

        val currentRaw = batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CURRENT_NOW)
        val chargeCounterRaw =
            batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CHARGE_COUNTER)
        val batteryIntent = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val voltageMv = batteryIntent?.getIntExtra(BatteryManager.EXTRA_VOLTAGE, -1) ?: -1
        val batteryTempC =
            (batteryIntent?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1) ?: -10) / 10.0
        val plugged = batteryIntent?.getIntExtra(BatteryManager.EXTRA_PLUGGED, -1) ?: -1
        val currentValid = currentRaw != Int.MIN_VALUE
        val chargeCounterValid = chargeCounterRaw != Int.MIN_VALUE
        val thermalStatus = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            powerManager.currentThermalStatus
        } else {
            -1
        }
        val verdict = when {
            Build.VERSION.SDK_INT < Build.VERSION_CODES.R -> "HEADROOM_API_UNAVAILABLE"
            !headroomNow.isNaN() -> "HEADROOM_OK"
            tick >= 15L -> "HEADROOM_UNSUPPORTED_OR_ERROR"
            else -> "HEADROOM_WARMUP"
        }

        val values = linkedMapOf<String, Any?>(
            "schema_version" to RunSessionStore.SCHEMA_VERSION,
            "source" to "d1check",
            "event" to "sample",
            "run_id" to activeRun.runId,
            "mono_ns" to monoNs,
            "wall_ms" to wallMs,
            "elapsed_s" to ((monoNs - activeRun.startedElapsedNs) / 1_000_000_000.0),
            "tick" to tick,
            "headroom_now" to finiteOrNull(headroomNow),
            "headroom_60s" to finiteOrNull(headroom60s),
            "thermal_status" to thermalStatus,
            "current_raw" to currentRaw,
            "current_valid" to currentValid,
            "voltage_mV" to voltageMv,
            "battery_temp_C" to batteryTempC,
            "charge_counter_raw" to chargeCounterRaw,
            "charge_valid" to chargeCounterValid,
            "plugged" to plugged,
            "verdict" to verdict,
        )
        val json = toJson(values)
        writer?.append(json)
        Log.i(EVENT_TAG, json)

        val legacyLine = listOf(
            "t=${tick}s",
            "run_id=${activeRun.runId}",
            "mono_ns=$monoNs",
            "wall_ms=$wallMs",
            "headroom_now=$headroomNow",
            "headroom_60s=$headroom60s",
            "thermal_status=$thermalStatus",
            "current_raw=$currentRaw",
            "current_valid=$currentValid",
            "voltage_mV=$voltageMv",
            "battery_temp_C=$batteryTempC",
            "charge_counter_raw=$chargeCounterRaw",
            "charge_valid=$chargeCounterValid",
            "plugged=$plugged",
            "verdict=$verdict",
        ).joinToString(" | ")
        Log.i(LEGACY_TAG, legacyLine)
        sendBroadcast(
            Intent(ACTION_SAMPLE)
                .setPackage(packageName)
                .putExtra(EXTRA_DISPLAY_LINE, legacyLine)
        )
        tick++
    }

    private fun recordEvent(event: String, status: String, extras: Map<String, Any?> = emptyMap()) {
        val activeRun = run ?: return
        val values = linkedMapOf<String, Any?>(
            "schema_version" to RunSessionStore.SCHEMA_VERSION,
            "source" to "d1check",
            "event" to event,
            "run_id" to activeRun.runId,
            "mono_ns" to SystemClock.elapsedRealtimeNanos(),
            "wall_ms" to System.currentTimeMillis(),
            "status" to status,
        )
        values.putAll(extras)
        val json = toJson(values)
        writer?.append(json)
        Log.i(EVENT_TAG, json)
    }

    private fun toJson(values: Map<String, Any?>): String {
        val json = JSONObject()
        values.forEach { (key, value) -> json.put(key, value ?: JSONObject.NULL) }
        return json.toString()
    }

    private fun finiteOrNull(value: Float): Float? = value.takeIf { it.isFinite() }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                getString(R.string.telemetry_channel_name),
                NotificationManager.IMPORTANCE_LOW,
            )
            getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }

    private fun buildNotification() = NotificationCompat.Builder(this, CHANNEL_ID)
        .setSmallIcon(R.mipmap.ic_launcher)
        .setContentTitle(getString(R.string.telemetry_notification_title))
        .setContentText(getString(R.string.telemetry_notification_text))
        .setOngoing(true)
        .setContentIntent(
            PendingIntent.getActivity(
                this,
                0,
                Intent(this, MainActivity::class.java),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
            )
        )
        .build()

    companion object {
        const val ACTION_SAMPLE = "com.example.d1check.action.SAMPLE"
        const val EXTRA_DISPLAY_LINE = "display_line"
        const val EXTRA_RUN_ID = "run_id"
        const val EXTRA_FORCE_NEW_RUN = "force_new_run"
        private const val ACTION_START = "com.example.d1check.action.START"
        private const val ACTION_STOP = "com.example.d1check.action.STOP"
        private const val LEGACY_TAG = "D1CHECK"
        private const val EVENT_TAG = "D1CHECK_EVENT"
        private const val CHANNEL_ID = "d1check_telemetry"
        private const val NOTIFICATION_ID = 4104
        private const val SAMPLE_PERIOD_NS = 1_000_000_000L

        fun start(context: Context, forceNewRun: Boolean = false, runId: String? = null) {
            val intent = Intent(context, TelemetryForegroundService::class.java)
                .setAction(ACTION_START)
                .putExtra(EXTRA_FORCE_NEW_RUN, forceNewRun)
            runId?.let { intent.putExtra(EXTRA_RUN_ID, it) }
            ContextCompat.startForegroundService(context, intent)
        }

        fun stop(context: Context) {
            val intent = Intent(context, TelemetryForegroundService::class.java)
                .setAction(ACTION_STOP)
            ContextCompat.startForegroundService(context, intent)
        }
    }
}
