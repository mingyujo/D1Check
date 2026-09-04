package com.example.d1check.benchmarkrunner

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
    private lateinit var statusView: TextView

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
            setOnClickListener { startBenchmark() }
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
            addView(statusView)
        }
        setContentView(ScrollView(this).apply { addView(layout) })
    }

    override fun onDestroy() {
        executor.shutdownNow()
        super.onDestroy()
    }

    private fun startBenchmark() {
        val config = try {
            RunConfig(
                resource = ResourceTarget.valueOf(resourceSpinner.selectedItem.toString()),
                limitMode = if (countMode.isChecked) LimitMode.COUNT else LimitMode.DURATION,
                inferenceCount = countInput.text.toString().toInt(),
                durationSeconds = durationInput.text.toString().toLong(),
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

        startButton.isEnabled = false
        statusView.text = "Baseline 60 seconds. No GPU load has started yet."
        executor.execute {
            val result = try {
                GpuBenchmarkEngine(applicationContext).execute(config)
            } catch (error: Throwable) {
                BenchmarkResult(false, "${error.javaClass.simpleName}: ${error.message}", null)
            }
            runOnUiThread {
                startButton.isEnabled = true
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

    private fun numericInput(defaultValue: String) = EditText(this).apply {
        inputType = android.text.InputType.TYPE_CLASS_NUMBER
        setText(defaultValue)
    }

    private fun LinearLayout.addLabel(text: String) {
        addView(TextView(this@MainActivity).apply { this.text = text })
    }
}
