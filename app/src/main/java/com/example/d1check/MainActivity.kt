package com.example.d1check

import android.Manifest
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.ActivityInfo
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.view.WindowManager
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat

/** D1Check v4 UI. Sampling is owned by [TelemetryForegroundService]. */
class MainActivity : AppCompatActivity() {
    private lateinit var statusView: TextView

    private val sampleReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            val line = intent?.getStringExtra(TelemetryForegroundService.EXTRA_DISPLAY_LINE)
                ?: return
            statusView.text = line.replace(" | ", "\n") + "\n\n" +
                statusView.text.toString().take(3500)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        statusView = TextView(this).apply {
            textSize = 13f
            setPadding(32, 32, 32, 32)
            text = "D1Check v4\n수집 서비스를 시작합니다."
        }
        val startButton = Button(this).apply {
            text = "새 run 시작"
            setOnClickListener { startTelemetry(forceNewRun = true) }
        }
        val stopButton = Button(this).apply {
            text = "수집 종료"
            setOnClickListener { TelemetryForegroundService.stop(this@MainActivity) }
        }
        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            addView(startButton)
            addView(stopButton)
            addView(statusView)
        }
        setContentView(ScrollView(this).apply { addView(content) })

        requestNotificationPermissionIfNeeded()
        startTelemetry(forceNewRun = false)
    }

    override fun onStart() {
        super.onStart()
        val filter = IntentFilter(TelemetryForegroundService.ACTION_SAMPLE)
        ContextCompat.registerReceiver(
            this,
            sampleReceiver,
            filter,
            ContextCompat.RECEIVER_NOT_EXPORTED,
        )
    }

    override fun onStop() {
        unregisterReceiver(sampleReceiver)
        super.onStop()
    }

    private fun startTelemetry(forceNewRun: Boolean) {
        TelemetryForegroundService.start(this, forceNewRun)
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 100)
        }
    }
}
