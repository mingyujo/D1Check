package com.example.d1check.benchmarkrunner

import android.app.Activity
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.os.*
import android.util.Log
import com.google.mediapipe.framework.image.BitmapImageBuilder
import com.google.mediapipe.tasks.core.BaseOptions
import com.google.mediapipe.tasks.core.Delegate
import com.google.mediapipe.tasks.vision.core.RunningMode
import com.google.mediapipe.tasks.vision.objectdetector.ObjectDetector
import java.io.File
import java.io.FileOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.UUID
import java.util.concurrent.Executors

/** One bounded diagnostic, separate from legacy probe artifacts and service samples. */
class DecodeDiagnosticActivity : Activity() {
    private val worker = Executors.newSingleThreadExecutor()
    private val handler = Handler(Looper.getMainLooper())
    private val watchdog = Runnable { android.os.Process.killProcess(android.os.Process.myPid()) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        worker.execute {
            var root: File? = null
            try {
                require(intent.action == "com.example.d1check.benchmarkrunner.action.DECODE_DIAGNOSTIC")
                val id = requireNotNull(intent.getStringExtra("session_id"))
                require(UUID.fromString(id).toString() == id)
                root = canonicalProbeOutputRoot(filesDir, "decode-diagnostic-v1", id)
                require(root.mkdirs())
                handler.postDelayed(watchdog, 120000L)
                val inputRoot = canonicalProbeInputRoot(filesDir, "model-probe-inputs", id)
                val manifestFile = File(inputRoot, "model_probe_manifest.json")
                val m = ModelProbeManifestParser.parse(manifestFile)
                require(m.identity.sessionId == id && m.target.packageName == packageName)
                require(m.target.buildFingerprint == Build.FINGERPRINT && m.target.model == Build.MODEL)
                require(ProbeModelFile.sha256(File(applicationInfo.sourceDir)) == m.target.apkSha256)
                require(getSystemService(PowerManager::class.java).currentThermalStatus <= 1)
                val model = ProbeModelFile.open(inputRoot, m.model)
                val input = ProbeModelFile.openInput(inputRoot, m.input)
                val bitmap = requireNotNull(BitmapFactory.decodeFile(input.file.absolutePath))
                try {
                    val pixels = IntArray(bitmap.width * bitmap.height)
                    bitmap.getPixels(pixels, 0, bitmap.width, 0, 0, bitmap.width, bitmap.height)
                    val rgb = ByteArray(pixels.size * 3)
                    pixels.forEachIndexed { i, p -> rgb[i * 3] = (p shr 16).toByte(); rgb[i * 3 + 1] = (p shr 8).toByte(); rgb[i * 3 + 2] = p.toByte() }
                    save(root, "decoded_rgb.u8", rgb)
                    val resized = ProbeImageContract.resize(rgb, bitmap.width, bitmap.height)
                    save(root, "resized_rgb.u8", resized)
                    val tensor = ProbeImageContract.tensor(resized)
                    save(root, "input.f32le", ByteArray(tensor.capacity()).also { tensor.duplicate().get(it) })
                    Log.i("D1DECODE", "session_start=$id backend=${m.execution.backend}")
                    val invocation = ProbeRawSession.create(m, model).use { it.invokePrepared(tensor) }
                    invocation.outputs.forEachIndexed { i, values ->
                        save(root, "output_$i.f32le", ByteBuffer.allocate(values.size * 4).order(ByteOrder.LITTLE_ENDIAN).apply { values.forEach { putFloat(it) } }.array())
                    }
                    val base = BaseOptions.builder().setModelAssetBuffer(model.readOnlyBuffer.duplicate().apply { rewind() })
                        .setDelegate(if (m.execution.backend == ProbeBackend.GPU) Delegate.GPU else Delegate.CPU).build()
                    val options = ObjectDetector.ObjectDetectorOptions.builder().setBaseOptions(base)
                        .setRunningMode(RunningMode.IMAGE).setScoreThreshold(0.5f).build()
                    val taskResults = linkedMapOf<String, Any?>()
                    ObjectDetector.createFromOptions(this, options).use { detector ->
                        val scaledPixels = IntArray(320 * 320) { i ->
                            (255 shl 24) or ((resized[i * 3].toInt() and 255) shl 16) or
                                ((resized[i * 3 + 1].toInt() and 255) shl 8) or (resized[i * 3 + 2].toInt() and 255)
                        }
                        val scaled = Bitmap.createBitmap(scaledPixels, 320, 320, Bitmap.Config.ARGB_8888)
                        try {
                            for ((name, imageBitmap) in listOf("original" to bitmap, "canonical_320" to scaled)) {
                                val image = BitmapImageBuilder(imageBitmap).build()
                                try {
                                    val result = detector.detect(image)
                                    taskResults[name] = result.detections().map { detection ->
                                        val c = detection.categories().maxBy { it.score() }
                                        val box = detection.boundingBox()
                                        mapOf("label" to c.categoryName(), "class_index" to c.index(), "score" to c.score(),
                                            "box" to listOf(box.left, box.top, box.width(), box.height()))
                                    }
                                } finally { image.close() }
                            }
                        } finally { scaled.recycle() }
                    }
                    val record = mapOf("protocol" to "decode-diagnostic-v1", "session_id" to id,
                        "manifest_sha256" to ProbeModelFile.sha256(manifestFile), "apk_sha256" to m.target.apkSha256,
                        "model_sha256" to model.sha256, "image_sha256" to input.sha256,
                        "image_size" to listOf(bitmap.width, bitmap.height), "preprocessing_id" to ProbeImageContract.ID,
                        "requested_backend" to m.execution.backend.name, "actual_backend" to if (m.execution.backend == ProbeBackend.CPU) "CPU" else "unverified_requires_host_log",
                        "raw_output_sha256" to invocation.outputSha256, "input_tensor_sha256" to invocation.inputSha256,
                        "tasks" to taskResults, "status" to "completed_diagnostic_not_quality_or_service",
                        "files" to root.listFiles()!!.associate { it.name to ProbeModelFile.sha256(it) })
                    save(root, "diagnostic.json", ModelProbeArtifacts.json(record).toByteArray())
                    Log.i("D1DECODE", "session_finalized=$id")
                } finally { bitmap.recycle() }
            } catch (error: Throwable) {
                Log.e("D1DECODE", "diagnostic failed", error)
                root?.let { save(it, "failure.json", ModelProbeArtifacts.json(mapOf("error" to Log.getStackTraceString(error))).toByteArray()) }
            } finally {
                handler.removeCallbacks(watchdog)
                runOnUiThread { finish() }
            }
        }
    }

    override fun onDestroy() { worker.shutdown(); super.onDestroy() }

    private fun save(root: File, name: String, bytes: ByteArray) {
        val file = File(root, name)
        require(file.createNewFile()) { "Refusing to overwrite diagnostic" }
        FileOutputStream(file).use { it.write(bytes); it.fd.sync() }
        require(file.readBytes().contentEquals(bytes))
    }
}
