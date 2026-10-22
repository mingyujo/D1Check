package com.example.d1check.benchmarkrunner

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Spinner
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.UUID
import java.util.concurrent.Executors

class CalibrationActivity : AppCompatActivity() {
    private val worker = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "d1-calibration-worker")
    }
    private lateinit var status: TextView
    private lateinit var backend: Spinner
    private lateinit var image: Spinner
    private lateinit var urgent: Button
    private lateinit var normal: Button
    private lateinit var finish: Button
    private var manifestBytes: ByteArray? = null
    private var manifest: CalibrationInputManifest? = null
    private var artifacts: CalibrationSessionArtifacts? = null
    private var pipeline: CalibrationPipeline? = null
    private val submittedByBackend = CalibrationBackend.entries.associateWith { 0 }.toMutableMap()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        backend = Spinner(this).apply {
            adapter = ArrayAdapter(
                this@CalibrationActivity,
                android.R.layout.simple_spinner_dropdown_item,
                CalibrationBackend.entries.map { it.wireName },
            )
        }
        image = Spinner(this)
        urgent = Button(this).apply {
            text = "Select one urgent image"
            isEnabled = false
            setOnClickListener { openImages(false) }
        }
        normal = Button(this).apply {
            text = "Select normal batch images"
            isEnabled = false
            setOnClickListener { openImages(true) }
        }
        finish = Button(this).apply {
            text = "Finalize calibration artifacts"
            isEnabled = false
            setOnClickListener { finalizeSession() }
        }
        status = TextView(this).apply {
            text = "Select a calibration input manifest. No representative images are bundled."
        }
        val chooseManifest = Button(this).apply {
            text = "Select calibration manifest"
            setOnClickListener { openDocument(REQUEST_MANIFEST, arrayOf("application/json", "text/plain")) }
        }
        setContentView(ScrollView(this).apply {
            addView(LinearLayout(this@CalibrationActivity).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(32, 32, 32, 32)
                addView(chooseManifest)
                addView(backend)
                addView(image)
                addView(urgent)
                addView(normal)
                addView(finish)
                addView(status)
            })
        })
    }

    @Deprecated("Uses the platform document picker without adding a new dependency")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (resultCode != Activity.RESULT_OK || data == null) return
        try {
            when (requestCode) {
                REQUEST_MANIFEST -> {
                    val bytes = readDocument(requireNotNull(data.data), MAX_MANIFEST_BYTES)
                    manifest = CalibrationInputManifest.parse(bytes)
                    manifestBytes = bytes
                    openDocument(REQUEST_LABELS, arrayOf("text/plain", "application/octet-stream"))
                }
                REQUEST_LABELS -> initialize(readDocument(requireNotNull(data.data), MAX_LABEL_BYTES))
                REQUEST_URGENT -> submitUrgent(requireNotNull(data.data))
                REQUEST_NORMAL -> submitNormal(selectedUris(data))
            }
        } catch (error: Throwable) {
            status.text = "Calibration input rejected: ${error.javaClass.simpleName}: ${error.message}"
        }
    }

    private fun initialize(labelBytes: ByteArray) {
        val (sessionArtifacts, labels) = CalibrationSessionArtifacts.create(
            applicationContext,
            checkNotNull(manifestBytes),
            labelBytes,
        )
        val activeManifest = sessionArtifacts.manifest
        val resultStore = DurableCalibrationResultStore(File(sessionArtifacts.root, "results"))
        artifacts = sessionArtifacts
        pipeline = CalibrationPipeline(
            manifest = activeManifest,
            clock = AndroidCalibrationClock,
            imageReader = AndroidCalibrationImageReader(contentResolver),
            imageDecoder = AndroidCalibrationImageDecoder,
            preprocessor = MobileNetCalibrationPreprocessor,
            runtimePool = LiteRtCalibrationRuntimePool(applicationContext, activeManifest.cpuThreads),
            postprocessor = MobileNetCalibrationPostprocessor(labels),
            resultStore = resultStore,
            recorder = sessionArtifacts,
        )
        manifest = activeManifest
        image.adapter = ArrayAdapter(
            this,
            android.R.layout.simple_spinner_dropdown_item,
            activeManifest.images.map { it.imageId },
        )
        activeManifest.fixedBackend?.let {
            backend.setSelection(CalibrationBackend.entries.indexOf(it))
            backend.isEnabled = false
        }
        urgent.isEnabled = true
        normal.isEnabled = true
        finish.isEnabled = true
        status.text = "Calibration session ready: ${activeManifest.sessionId} " +
            "mode=${activeManifest.calibrationMode.wireName}"
    }

    private fun submitUrgent(uri: Uri) {
        val pickerNs = AndroidCalibrationClock.monotonicNanos()
        val spec = checkNotNull(manifest).images[image.selectedItemPosition]
        submit(CalibrationRequestType.URGENT, spec, uri, pickerNs)
    }

    private fun submitNormal(uris: List<Uri>) {
        val active = checkNotNull(manifest)
        require(uris.size == active.images.size) {
            "normal batch must select exactly ${active.images.size} images in manifest order"
        }
        uris.zip(active.images).forEach { (uri, spec) ->
            submit(CalibrationRequestType.NORMAL, spec, uri, null)
        }
    }

    private fun submit(
        type: CalibrationRequestType,
        spec: CalibrationImageSpec,
        uri: Uri,
        pickerNs: Long?,
    ) {
        val accepted = AndroidCalibrationClock.monotonicNanos()
        val selectedBackend = CalibrationBackend.valueOf(backend.selectedItem.toString())
        val priorBackendSubmissions = submittedByBackend.getValue(selectedBackend)
        val request = CalibrationRequest(
            requestId = UUID.randomUUID().toString(),
            requestType = type,
            image = spec,
            imageUri = uri.toString(),
            requestedBackend = selectedBackend,
            pickerResultReceivedNs = pickerNs,
            acceptedNs = accepted,
            deadlineNs = null,
            isWarmup = priorBackendSubmissions in 1..checkNotNull(manifest).warmupCount,
        )
        submittedByBackend[selectedBackend] = priorBackendSubmissions + 1
        val submission = checkNotNull(pipeline).submit(
            request,
            CalibrationOutputConsumer { completedRequest, output ->
                runOnUiThread {
                    status.text = "Output ready: ${completedRequest.image.imageId} " +
                        output.topLabels.firstOrNull().orEmpty()
                }
            },
        ) { result ->
            runOnUiThread {
                if (result.terminalStatus != CalibrationTerminalStatus.SUCCEEDED) {
                    status.text = "${result.terminalStatus.wireName}: ${result.error}"
                }
            }
        }
        if (submission.accepted) worker.execute { checkNotNull(pipeline).drainOne() }
    }

    private fun finalizeSession() {
        urgent.isEnabled = false
        normal.isEnabled = false
        finish.isEnabled = false
        worker.execute {
            try {
                check(checkNotNull(pipeline).pendingCount() == 0) { "requests are still queued" }
                pipeline?.close()
                val entries = checkNotNull(artifacts).finalizeAndValidate()
                runOnUiThread {
                    status.text = "Calibration artifacts finalized (${entries.size} files): " +
                        checkNotNull(artifacts).root.absolutePath
                }
            } catch (error: Throwable) {
                runOnUiThread {
                    status.text = "Calibration finalization failed: ${error.message}"
                }
            }
        }
    }

    private fun openImages(multiple: Boolean) {
        startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "image/*"
            putExtra(Intent.EXTRA_ALLOW_MULTIPLE, multiple)
        }, if (multiple) REQUEST_NORMAL else REQUEST_URGENT)
    }

    private fun openDocument(code: Int, mimeTypes: Array<String>) {
        startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "*/*"
            putExtra(Intent.EXTRA_MIME_TYPES, mimeTypes)
        }, code)
    }

    private fun readDocument(uri: Uri, maxBytes: Int): ByteArray {
        contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
        return contentResolver.openInputStream(uri).use { input ->
            requireNotNull(input)
            val output = ByteArrayOutputStream()
            val buffer = ByteArray(16 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                require(output.size() + count <= maxBytes) { "selected document is too large" }
                output.write(buffer, 0, count)
            }
            output.toByteArray().also { require(it.isNotEmpty()) }
        }
    }

    private fun selectedUris(data: Intent): List<Uri> {
        val clips = data.clipData
        return if (clips == null) listOfNotNull(data.data) else {
            List(clips.itemCount) { clips.getItemAt(it).uri }
        }
    }

    override fun onDestroy() {
        worker.execute {
            try { pipeline?.close() } catch (_: Throwable) { }
            try { artifacts?.close() } catch (_: Throwable) { }
        }
        worker.shutdown()
        super.onDestroy()
    }

    companion object {
        private const val REQUEST_MANIFEST = 801
        private const val REQUEST_LABELS = 802
        private const val REQUEST_URGENT = 803
        private const val REQUEST_NORMAL = 804
        private const val MAX_MANIFEST_BYTES = 1024 * 1024
        private const val MAX_LABEL_BYTES = 1024 * 1024
    }
}
