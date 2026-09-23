package com.example.d1check.benchmarkrunner

import android.graphics.BitmapFactory
import org.json.JSONArray
import java.io.File
import java.security.MessageDigest
import kotlin.math.exp

/** Explicit decoded adapter; MediaPipe Tasks is not loaded into this runtime. */
internal class ProbeTaskAdapter(
    private val manifest: ModelProbeManifest,
    model: VerifiedProbeFile,
    anchorsFile: File?,
) : AutoCloseable {
    private val labels: List<String>
    private val anchors: List<DoubleArray>
    private val session: ProbeRawSession

    init {
        // Android ZipFile rejects the TFLite prefix before appended associated files.
        // The host extracts the original associated file; its pinned hash is authoritative.
        val inputRoot = requireNotNull(anchorsFile).canonicalFile.parentFile
        val labelFile = File(inputRoot, manifest.model.labelFilename)
        require(labelFile.isFile && labelFile.absoluteFile == labelFile.canonicalFile && labelFile.canonicalFile.parentFile == inputRoot)
        val labelBytes = labelFile.readBytes()
        require(digest(labelBytes) == manifest.model.labelSha256)
        labels = labelBytes.toString(Charsets.UTF_8).lineSequence().filter { it.isNotEmpty() }.toList()
        require(labels.size == manifest.model.labelRows)
        anchors = if (manifest.model.task == ProbeTask.DETECTION) {
            val file = requireNotNull(anchorsFile)
            require(ProbeModelFile.sha256(file) == ANCHORS_SHA256)
            val rows = JSONArray(file.readText())
            require(rows.length() == 19206)
            List(rows.length()) { i -> val row = rows.getJSONArray(i); require(row.length() == 4); DoubleArray(4) { row.getDouble(it) } }
        } else emptyList()
        session = ProbeRawSession.create(manifest, model)
    }

    fun execute(image: File, imageSha256: String, invocationObserver: ((Long, Long) -> Unit)? = null): Map<String, Any?> {
        // Integrity/read/decode are part of each service, not a cached synthetic tensor.
        require(ProbeModelFile.sha256(image) == imageSha256)
        ProbeImageContract.requireCanonicalPng(image.readBytes())
        val bitmap = requireNotNull(BitmapFactory.decodeFile(image.absolutePath))
        try {
            val width = bitmap.width
            val height = bitmap.height
            require(width in 1..4096 && height in 1..4096)
            val pixels = IntArray(width * height)
            bitmap.getPixels(pixels, 0, width, 0, 0, width, height)
            val rgb = ByteArray(pixels.size * 3)
            pixels.forEachIndexed { i, p -> rgb[i * 3] = (p shr 16).toByte(); rgb[i * 3 + 1] = (p shr 8).toByte(); rgb[i * 3 + 2] = p.toByte() }
            val classification = manifest.model.task == ProbeTask.CLASSIFICATION
            val resized = ProbeImageContract.resize(rgb, width, height, if (classification) 224 else 320)
            val tensor = if (classification) java.nio.ByteBuffer.allocateDirect(resized.size * 4).order(java.nio.ByteOrder.LITTLE_ENDIAN).apply {
                resized.forEach { putFloat(((it.toInt() and 255) - 127f) / 128f) }; rewind()
            } else ProbeImageContract.tensor(resized)
            val raw = session.invokePrepared(tensor, invocationObserver = invocationObserver)
            val results: List<Map<String, Any?>> = if (classification) {
                raw.outputs.single().indices.sortedWith(compareByDescending<Int> { raw.outputs[0][it] }.thenBy { it }).take(5).map { i ->
                    mapOf("label" to labels[i], "class_index" to i, "score" to raw.outputs[0][i])
                }
            } else ExplicitDetectionDecoder.decode(raw.outputs[0], raw.outputs[1], anchors, labels, width, height)
            return mapOf("task_id" to manifest.model.task.wireName, "model_id" to manifest.model.modelId,
                "model_sha256" to manifest.model.sha256, "image_sha256" to imageSha256,
                "image_size" to listOf(width, height), "input_tensor_sha256" to raw.inputSha256,
                "raw_output_sha256" to raw.outputSha256, "results" to results, "inference_ns" to raw.invokeNs,
                "requested_backend" to manifest.execution.backend.name,
                "actual_backend" to if (manifest.execution.backend == ProbeBackend.CPU) "CPU" else "unverified_requires_host_delegate_log",
                "adapter_contract" to "explicit-image-task-v2", "canonical_input_contract" to "canonical-srgb-png-v2")
        } finally { bitmap.recycle() }
    }

    override fun close() = session.close()

    companion object {
        const val ANCHORS_SHA256 = "e095e869203d5f5442583712e1546aac8f5112512b1a98925165fe17b455c3bc"
        fun digest(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
    }
}

internal object ExplicitDetectionDecoder {
    private data class Candidate(val index: Int, val label: String, val score: Double, val box: DoubleArray)

    fun decode(scores: FloatArray, locations: FloatArray, anchors: List<DoubleArray>, labels: List<String>, width: Int, height: Int): List<Map<String, Any?>> {
        require(width > 0 && height > 0 && labels.isNotEmpty())
        require(scores.size == anchors.size * labels.size && locations.size == anchors.size * 4)
        require(scores.all { it.isFinite() } && locations.all { it.isFinite() })
        val candidates = anchors.mapIndexedNotNull { i, a ->
            require(a.size == 4 && a.all { it.isFinite() } && a[2] > 0 && a[3] > 0)
            var cls = 0
            for (j in 1 until labels.size) if (scores[i * labels.size + j] > scores[i * labels.size + cls]) cls = j
            val score = scores[i * labels.size + cls].toDouble()
            if (score < 0.5) return@mapIndexedNotNull null
            val cx = locations[i * 4 + 1] * a[2] + a[0]
            val cy = locations[i * 4] * a[3] + a[1]
            val w = exp(locations[i * 4 + 3].toDouble()) * a[2]
            val h = exp(locations[i * 4 + 2].toDouble()) * a[3]
            val box = doubleArrayOf((cx - w / 2) * width, (cy - h / 2) * height, w * width, h * height)
            require(box.all { it.isFinite() } && w > 0 && h > 0)
            Candidate(i, labels[cls], score, box)
        }.sortedWith(compareByDescending<Candidate> { it.score }.thenBy { it.index })
        val accepted = mutableListOf<Candidate>()
        for (candidate in candidates) if (accepted.all { iou(it.box, candidate.box) <= 0.3 }) accepted += candidate
        return accepted.sortedWith(compareByDescending<Candidate> { it.score }.thenBy { it.label }
            .thenBy { it.box[0] }.thenBy { it.box[1] }.thenBy { it.box[2] }.thenBy { it.box[3] })
            .map { mapOf("label" to it.label, "score" to it.score, "box" to it.box.toList()) }
    }

    internal fun iou(a: DoubleArray, b: DoubleArray): Double {
        val intersection = maxOf(0.0, minOf(a[0] + a[2], b[0] + b[2]) - maxOf(a[0], b[0])) *
            maxOf(0.0, minOf(a[1] + a[3], b[1] + b[3]) - maxOf(a[1], b[1]))
        val union = a[2] * a[3] + b[2] * b[3] - intersection
        return if (union > 0) intersection / union else 0.0
    }
}
