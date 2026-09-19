package com.example.d1check.benchmarkrunner

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.os.SystemClock
import com.google.mediapipe.framework.image.BitmapImageBuilder
import com.google.mediapipe.framework.image.MPImage
import com.google.mediapipe.tasks.core.BaseOptions
import com.google.mediapipe.tasks.core.Delegate
import com.google.mediapipe.tasks.vision.core.RunningMode
import com.google.mediapipe.tasks.vision.objectdetector.ObjectDetector

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

/** A decoded detector whose create/invoke/close operations stay on the caller's worker. */
internal class ProbeDecodedSession private constructor(
    private val backend: ProbeBackend,
    private val detector: ObjectDetector,
    private val image: MPImage,
    private val originalBitmap: Bitmap,
    private val argbBitmap: Bitmap,
) : AutoCloseable {
    private var closed = false

    fun invoke(): ProbeDecodedResult {
        check(!closed) { "Decoded probe session is closed" }
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
            backend = backend,
            delegationStatus = if (backend == ProbeBackend.GPU) {
                "unverified_requires_host_delegate_log"
            } else {
                "not_applicable_cpu"
            },
        )
    }

    override fun close() {
        if (closed) return
        closed = true
        var first: Throwable? = null
        listOf<() -> Unit>(
            { detector.close() },
            { image.close() },
            { if (argbBitmap !== originalBitmap) argbBitmap.recycle() },
            { originalBitmap.recycle() },
        ).forEach { cleanup ->
            try {
                cleanup()
            } catch (error: Throwable) {
                if (first == null) first = error else first?.addSuppressed(error)
            }
        }
        first?.let { throw it }
    }

    companion object {
        fun create(
            context: Context,
            manifest: ModelProbeManifest,
            model: VerifiedProbeFile,
            input: VerifiedProbeFile,
        ): ProbeDecodedSession {
            require(manifest.model.task == ProbeTask.DETECTION) {
                "Decoded adapter requires detection task"
            }
            require(manifest.input.kind == "external_image") {
                "Decoded adapter requires external image"
            }
            require(manifest.runtime.tasksVisionVersion == ProbeDecodedDetector.TASKS_VISION_VERSION) {
                "Tasks Vision contract mismatch"
            }
            val bitmap = BitmapFactory.decodeFile(input.file.absolutePath)
                ?: throw IllegalArgumentException("Probe image decode failed")
            val argb = if (bitmap.config == Bitmap.Config.ARGB_8888) {
                bitmap
            } else {
                bitmap.copy(Bitmap.Config.ARGB_8888, false)
                    ?: throw IllegalArgumentException("Probe image ARGB_8888 conversion failed")
            }
            var image: MPImage? = null
            var detector: ObjectDetector? = null
            try {
                image = BitmapImageBuilder(argb).build()
                val baseOptions = BaseOptions.builder()
                    .setModelAssetBuffer(model.readOnlyBuffer.duplicate().apply { rewind() })
                    .setDelegate(
                        if (manifest.execution.backend == ProbeBackend.GPU) Delegate.GPU else Delegate.CPU
                    )
                    .build()
                val options = ObjectDetector.ObjectDetectorOptions.builder()
                    .setBaseOptions(baseOptions)
                    .setRunningMode(RunningMode.IMAGE)
                    .setScoreThreshold(ProbeDecodedDetector.SCORE_THRESHOLD)
                    .build()
                detector = ObjectDetector.createFromOptions(context, options)
                return ProbeDecodedSession(
                    manifest.execution.backend, detector, image, bitmap, argb
                )
            } catch (error: Throwable) {
                try { detector?.close() } catch (cleanup: Throwable) { error.addSuppressed(cleanup) }
                try { image?.close() } catch (cleanup: Throwable) { error.addSuppressed(cleanup) }
                if (argb !== bitmap) argb.recycle()
                bitmap.recycle()
                throw error
            }
        }
    }
}

internal object ProbeDecodedDetector {
    const val TASKS_VISION_VERSION = "1.0.0"
    const val SCORE_THRESHOLD = 0.5f
}
