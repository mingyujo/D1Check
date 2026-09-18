package com.example.d1check.benchmarkrunner

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.os.SystemClock
import com.google.mediapipe.framework.image.BitmapImageBuilder
import com.google.mediapipe.tasks.core.BaseOptions
import com.google.mediapipe.tasks.core.Delegate
import com.google.mediapipe.tasks.vision.core.RunningMode
import com.google.mediapipe.tasks.vision.objectdetector.ObjectDetector
import java.util.concurrent.Callable
import java.util.concurrent.ExecutionException
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.TimeoutException

internal data class ProbeDetection(
    val label: String,
    val score: Float,
    val left: Float,
    val top: Float,
    val width: Float,
    val height: Float,
)

internal data class ProbeDecodedResult(
    val detections: List<ProbeDetection>,
    val tasksDetectNs: Long,
    val backend: ProbeBackend,
    val delegationStatus: String,
)

internal object ProbeDecodedDetector {
    fun runBlocking(
        context: Context,
        manifest: ModelProbeManifest,
        model: VerifiedProbeFile,
        input: VerifiedProbeFile,
    ): ProbeDecodedResult {
        require(manifest.model.task == ProbeTask.DETECTION) { "Decoded adapter requires detection task" }
        require(manifest.input.kind == "external_image") { "Decoded adapter requires external image" }
        require(manifest.runtime.tasksVisionVersion == TASKS_VISION_VERSION) {
            "Tasks Vision contract mismatch"
        }
        val worker = Executors.newSingleThreadExecutor { runnable ->
            Thread(runnable, "d1-model-probe-detector").apply { isDaemon = true }
        }
        val future = worker.submit(Callable {
            runOnWorker(context, manifest, model, input)
        })
        var primaryFailure: Throwable? = null
        try {
            return future.get(manifest.execution.maximumDurationMs, TimeUnit.MILLISECONDS)
        } catch (error: TimeoutException) {
            future.cancel(true)
            val failure = IllegalStateException("Decoded detector exceeded device timeout", error)
            primaryFailure = failure
            throw failure
        } catch (error: ExecutionException) {
            val failure = error.cause ?: error
            primaryFailure = failure
            throw failure
        } finally {
            worker.shutdownNow()
            if (!worker.awaitTermination(2, TimeUnit.SECONDS)) {
                val cleanup = IllegalStateException("Decoded detector worker did not terminate")
                val first = primaryFailure
                if (first == null) throw cleanup else first.addSuppressed(cleanup)
            }
        }
    }

    private fun runOnWorker(
        context: Context,
        manifest: ModelProbeManifest,
        model: VerifiedProbeFile,
        input: VerifiedProbeFile,
    ): ProbeDecodedResult {
        val bitmap = BitmapFactory.decodeFile(input.file.absolutePath)
            ?: throw IllegalArgumentException("Probe image decode failed")
        val argb = if (bitmap.config == Bitmap.Config.ARGB_8888) {
            bitmap
        } else {
            bitmap.copy(Bitmap.Config.ARGB_8888, false)
                ?: throw IllegalArgumentException("Probe image ARGB_8888 conversion failed")
        }
        val modelBuffer = model.readOnlyBuffer.duplicate().apply { rewind() }
        val baseOptions = BaseOptions.builder()
            .setModelAssetBuffer(modelBuffer)
            .setDelegate(
                if (manifest.execution.backend == ProbeBackend.GPU) Delegate.GPU else Delegate.CPU
            )
            .build()
        val options = ObjectDetector.ObjectDetectorOptions.builder()
            .setBaseOptions(baseOptions)
            .setRunningMode(RunningMode.IMAGE)
            .setScoreThreshold(SCORE_THRESHOLD)
            .build()
        try {
            val detector = ObjectDetector.createFromOptions(context, options)
            try {
                val image = BitmapImageBuilder(argb).build()
                try {
                    val startedNs = SystemClock.elapsedRealtimeNanos()
                    val result = detector.detect(image)
                    val finishedNs = SystemClock.elapsedRealtimeNanos()
                    val detections = result.detections().mapNotNull { detection ->
                        val category = detection.categories().maxByOrNull { it.score() }
                            ?: return@mapNotNull null
                        val box = detection.boundingBox()
                        ProbeDetection(
                            label = category.categoryName(),
                            score = category.score(),
                            left = box.left,
                            top = box.top,
                            width = box.width(),
                            height = box.height(),
                        )
                    }.sortedWith(
                        compareByDescending<ProbeDetection> { it.score }
                            .thenBy { it.label }
                            .thenBy { it.left }
                            .thenBy { it.top }
                            .thenBy { it.width }
                            .thenBy { it.height }
                    )
                    check(detections.all { detection ->
                        detection.label.isNotEmpty() && detection.score.isFinite() &&
                            detection.left.isFinite() && detection.top.isFinite() &&
                            detection.width.isFinite() && detection.height.isFinite()
                    }) { "Decoded detector returned invalid values" }
                    return ProbeDecodedResult(
                        detections = detections,
                        tasksDetectNs = finishedNs - startedNs,
                        backend = manifest.execution.backend,
                        delegationStatus = if (manifest.execution.backend == ProbeBackend.GPU) {
                            "unverified_requires_host_delegate_log"
                        } else {
                            "not_applicable_cpu"
                        },
                    )
                } finally {
                    image.close()
                }
            } finally {
                detector.close()
            }
        } finally {
            if (argb !== bitmap) argb.recycle()
            bitmap.recycle()
        }
    }

    const val TASKS_VISION_VERSION = "1.0.0"
    const val SCORE_THRESHOLD = 0.5f
}
