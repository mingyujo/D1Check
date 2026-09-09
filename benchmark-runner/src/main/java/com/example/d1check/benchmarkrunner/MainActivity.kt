package com.example.d1check.benchmarkrunner

import android.content.Intent
import android.os.Bundle
import android.view.WindowManager
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.ScrollView
import android.widget.Spinner
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import java.util.concurrent.Executors

class MainActivity : AppCompatActivity() {
    private val executor = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, GpuBenchmarkEngine.THREAD_NAME)
    }
    private lateinit var resourceSpinner: Spinner
    private lateinit var countMode: RadioButton
    private lateinit var countInput: EditText
    private lateinit var durationInput: EditText
    private lateinit var warmupInput: EditText
    private lateinit var diagnosticInput: CheckBox
    private lateinit var startButton: Button
    private lateinit var probeNnapiButton: Button
    private lateinit var statusView: TextView
    private lateinit var commandReplayStore: CommandReplayStore

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        resourceSpinner = Spinner(this).apply {
            adapter = ArrayAdapter(
                this@MainActivity,
                android.R.layout.simple_spinner_dropdown_item,
                listOf(ResourceTarget.CPU4.name, ResourceTarget.GPU.name),
            )
        }
        countMode = RadioButton(this).apply { text = "Inference count"; isChecked = true }
        val durationMode = RadioButton(this).apply { text = "Duration (seconds)" }
        val limitModes = RadioGroup(this).apply {
            orientation = RadioGroup.HORIZONTAL
            addView(countMode)
            addView(durationMode)
        }
        countInput = numericInput("1000")
        durationInput = numericInput("300")
        warmupInput = numericInput("20")
        diagnosticInput = CheckBox(this).apply {
            text = "Diagnostic run (Perfetto is controlled by host logger)"
            isChecked = false
        }
        startButton = Button(this).apply {
            text = "Start: baseline 60s, then load"
            setOnClickListener { startManualBenchmark() }
        }
        probeNnapiButton = Button(this).apply {
            text = "Probe NNAPI devices"
            setOnClickListener { probeNnapiDevices() }
        }
        statusView = TextView(this).apply {
            text = "Start D1Check new run and host logger before pressing Start."
            setPadding(24, 32, 24, 32)
        }
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 32, 32, 32)
            addLabel("Resource")
            addView(resourceSpinner)
            addLabel("Limit mode")
            addView(limitModes)
            addLabel("Inference count")
            addView(countInput)
            addLabel("Duration seconds")
            addView(durationInput)
            addLabel("Warmup count")
            addView(warmupInput)
            addView(diagnosticInput)
            addView(startButton)
            addView(probeNnapiButton)
            addView(statusView)
        }
        setContentView(ScrollView(this).apply { addView(layout) })
        commandReplayStore = CommandReplayStore(this)
        handleAutomationIntent(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleAutomationIntent(intent)
    }

    override fun onDestroy() {
        executor.shutdownNow()
        super.onDestroy()
    }

    private fun startManualBenchmark() {
        val config = try {
            RunConfig(
                resource = ResourceTarget.valueOf(resourceSpinner.selectedItem.toString()),
                limit = if (countMode.isChecked) {
                    RunLimit.Count(countInput.text.toString().toInt())
                } else {
                    RunLimit.Duration(durationInput.text.toString().toLong())
                },
                warmupCount = warmupInput.text.toString().toInt(),
                experimentMode = if (diagnosticInput.isChecked) {
                    ExperimentMode.DIAGNOSTIC
                } else {
                    ExperimentMode.BASIC
                },
            )
        } catch (error: Exception) {
            statusView.text = "Invalid configuration: ${error.message}"
            return
        }

        startBenchmark(config)
    }

    private fun startBenchmark(config: RunConfig) {
        if (!BenchmarkExecutionGate.tryAcquire()) {
            statusView.text = "A benchmark is already running."
            return
        }

        startButton.isEnabled = false
        probeNnapiButton.isEnabled = false
        statusView.text = "Baseline 60 seconds. No GPU load has started yet."
        executor.execute {
            val result = try {
                GpuBenchmarkEngine(applicationContext).execute(config)
            } catch (error: Throwable) {
                BenchmarkResult(false, "${error.javaClass.simpleName}: ${error.message}", null)
            }
            runOnUiThread {
                BenchmarkExecutionGate.release()
                startButton.isEnabled = true
                probeNnapiButton.isEnabled = true
                statusView.text = buildString {
                    append(if (result.success) "Complete" else "Failed")
                    append("\n")
                    append(result.message)
                    result.flushResult?.let {
                        append("\nevents=").append(it.eventCount)
                        append("\nfile=").append(it.file.absolutePath)
                    }
                }
            }
        }
    }

    private fun handleAutomationIntent(intent: Intent) {
        val values = buildMap<String, Any?> {
            if (intent.hasExtra(AutomationIntentParser.EXTRA_AUTO_START)) {
                put(
                    AutomationIntentParser.EXTRA_AUTO_START,
                    intent.getBooleanExtra(AutomationIntentParser.EXTRA_AUTO_START, false),
                )
            }
            listOf(
                AutomationIntentParser.EXTRA_RESOURCE,
                AutomationIntentParser.EXTRA_LIMIT_MODE,
                AutomationIntentParser.EXTRA_RUN_ID,
                AutomationIntentParser.EXTRA_COMMAND_ID,
                AutomationIntentParser.EXTRA_EXPERIMENT_MODE,
            ).forEach { key ->
                if (intent.hasExtra(key)) put(key, intent.getStringExtra(key))
            }
            listOf(
                AutomationIntentParser.EXTRA_CPU_THREADS,
                AutomationIntentParser.EXTRA_INFERENCE_COUNT,
                AutomationIntentParser.EXTRA_WARMUP_COUNT,
                AutomationIntentParser.EXTRA_DUTY_CYCLE_PERCENT,
            ).forEach { key ->
                if (intent.hasExtra(key)) put(key, intent.getIntExtra(key, Int.MIN_VALUE))
            }
            if (intent.hasExtra(AutomationIntentParser.EXTRA_DURATION_S)) {
                put(
                    AutomationIntentParser.EXTRA_DURATION_S,
                    intent.getLongExtra(AutomationIntentParser.EXTRA_DURATION_S, Long.MIN_VALUE),
                )
            }
            if (intent.hasExtra(AutomationIntentParser.EXTRA_DUTY_CYCLE_PERIOD_S)) {
                put(
                    AutomationIntentParser.EXTRA_DUTY_CYCLE_PERIOD_S,
                    intent.getFloatExtra(
                        AutomationIntentParser.EXTRA_DUTY_CYCLE_PERIOD_S,
                        Float.NaN,
                    ),
                )
            }
        }
        val request = try {
            AutomationIntentParser.parse(values)
        } catch (error: IllegalArgumentException) {
            statusView.text = "Invalid automation request: ${error.message}"
            return
        } ?: return

        if (BenchmarkExecutionGate.isRunning) {
            statusView.text = "Automation request ignored: a benchmark is already running."
            return
        }
        val commandId = checkNotNull(request.config.commandId)
        if (!commandReplayStore.claim(commandId)) {
            statusView.text = "Automation replay ignored: command_id=$commandId"
            return
        }
        startBenchmark(request.config)
    }

    private fun probeNnapiDevices() {
        startButton.isEnabled = false
        probeNnapiButton.isEnabled = false
        statusView.text = "Probing NNAPI devices..."
        executor.execute {
            val message = try {
                when (val result = NnapiDeviceProbe.probeAndLog()) {
                    is NnapiProbeResult.Unsupported ->
                        "NNAPI device probe is unsupported below API 29 (device API ${result.apiLevel})."
                    is NnapiProbeResult.Success ->
                        "NNAPI probe complete: ${result.devices.size} device(s). See D1NPU log lines."
                }
            } catch (error: Throwable) {
                "NNAPI probe failed: ${error.javaClass.simpleName}: ${error.message}"
            }
            runOnUiThread {
                startButton.isEnabled = true
                probeNnapiButton.isEnabled = true
                statusView.text = message
            }
        }
    }

    private fun numericInput(defaultValue: String) = EditText(this).apply {
        inputType = android.text.InputType.TYPE_CLASS_NUMBER
        setText(defaultValue)
    }

    private fun LinearLayout.addLabel(text: String) {
        addView(TextView(this@MainActivity).apply { this.text = text })
    }
}
