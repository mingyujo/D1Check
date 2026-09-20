package com.example.d1check.benchmarkrunner

import android.graphics.BitmapFactory
import org.json.JSONArray
import java.io.File
import java.security.MessageDigest
import kotlin.math.exp

/** Explicit decoded adapter; MediaPipe Tasks is not loaded into this runtime. */
internal class V4TaskAdapter(
    private val manifest: ModelProbeManifest,
    model: VerifiedProbeFile,
    anchorsFile: File?,
    private val scope: V4Scope,
) : AutoCloseable {
    private val labels: List<String>
    private val anchors: List<DoubleArray>
    private val session: V4RawSession

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
        session = V4RawSession.create(manifest, model, scope)
    }

    fun execute(image: File, imageSha256: String): Map<String, Any?> {
        scope.mark("preprocess", "start")
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
            scope.mark("preprocess", "finish")
            val raw = session.invokePrepared(tensor)
            scope.mark("decode_postprocess", "start")
            val results: List<Map<String, Any?>> = if (classification) {
                raw.outputs.single().indices.sortedWith(compareByDescending<Int> { raw.outputs[0][it] }.thenBy { it }).take(5).map { i ->
                    mapOf("label" to labels[i], "class_index" to i, "score" to raw.outputs[0][i])
                }
            } else ExplicitDetectionDecoder.decode(raw.outputs[0], raw.outputs[1], anchors, labels, width, height)
            scope.mark("decode_postprocess", "finish")
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
