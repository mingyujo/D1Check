package com.example.d1check.benchmarkrunner

import android.content.ContentResolver
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import androidx.exifinterface.media.ExifInterface
import android.net.Uri
import android.os.Build
import android.os.SystemClock
import android.system.Os
import org.json.JSONArray
import org.json.JSONObject
import org.tensorflow.lite.DataType
import org.tensorflow.lite.Interpreter
import org.tensorflow.lite.gpu.CompatibilityList
import org.tensorflow.lite.gpu.GpuDelegate
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileOutputStream
import java.io.ByteArrayInputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.security.MessageDigest

internal class AndroidCalibrationImageReader(
    private val resolver: ContentResolver,
) : CalibrationImageReader {
    override fun read(uri: String): CalibrationImageBytes {
        val output = ByteArrayOutputStream()
        resolver.openInputStream(Uri.parse(uri)).use { input ->
            requireNotNull(input) { "image URI could not be opened" }
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                check(output.size() + count <= CalibrationContract.MAX_IMAGE_BYTES) {
                    "image exceeds maximum byte size"
                }
                output.write(buffer, 0, count)
            }
        }
        val bytes = output.toByteArray()
        require(bytes.isNotEmpty()) { "image is empty" }
        val mimeType = detectMime(bytes)
        val orientation = try {
            val exif = ExifInterface(ByteArrayInputStream(bytes))
            // Some implementations synthesize an undefined (0) default. Only a
            // tag backed by bytes in the original image is explicitly supplied.
            val range = exif.getAttributeRange(ExifInterface.TAG_ORIENTATION)
            if (range == null || range[0] < 0L) {
                ExifInterface.ORIENTATION_NORMAL
            } else {
                requireNotNull(exif.getAttribute(ExifInterface.TAG_ORIENTATION)?.toIntOrNull()) {
                    "unsupported EXIF orientation"
                }
            }
        } catch (error: java.io.IOException) {
            throw IllegalArgumentException("image EXIF metadata is malformed", error)
        }
        require(orientation in ExifInterface.ORIENTATION_NORMAL..
            ExifInterface.ORIENTATION_ROTATE_270) { "unsupported EXIF orientation" }
        return CalibrationImageBytes(
            bytes,
            CalibrationContract.sha256(bytes),
            mimeType,
            bytes.size.toLong(),
            orientation,
        )
    }

    private fun detectMime(bytes: ByteArray): String = when {
        bytes.size >= 3 && bytes[0] == 0xff.toByte() && bytes[1] == 0xd8.toByte() &&
            bytes[2] == 0xff.toByte() -> "image/jpeg"
        bytes.size >= 8 && bytes.copyOfRange(0, 8).contentEquals(
            byteArrayOf(0x89.toByte(), 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a)
        ) -> "image/png"
        bytes.size >= 12 && bytes.copyOfRange(0, 4).toString(Charsets.US_ASCII) == "RIFF" &&
            bytes.copyOfRange(8, 12).toString(Charsets.US_ASCII) == "WEBP" -> "image/webp"
        else -> error("unsupported or malformed image bytes")
    }
}

internal class BitmapCalibrationImage(
    val bitmap: Bitmap,
    override val rawWidth: Int,
    override val rawHeight: Int,
    override val exifOrientation: Int,
) : CalibrationDecodedImage {
    override val width: Int get() = bitmap.width
    override val height: Int get() = bitmap.height
    override fun close() = bitmap.recycle()
}

internal object AndroidCalibrationImageDecoder : CalibrationImageDecoder {
    override fun decode(image: CalibrationImageBytes): CalibrationDecodedImage {
        val bitmap = try {
            BitmapFactory.decodeByteArray(image.bytes, 0, image.bytes.size)
        } catch (error: RuntimeException) {
            throw IllegalArgumentException("Android image decode failed", error)
        }
        val decoded = requireNotNull(bitmap) { "Android image decode failed" }
        val rawWidth = decoded.width
        val rawHeight = decoded.height
        val oriented = try {
            applyExifOrientation(decoded, image.exifOrientation)
        } catch (error: RuntimeException) {
            decoded.recycle()
            throw error
        }
        if (oriented !== decoded) decoded.recycle()
        return BitmapCalibrationImage(
            oriented,
            rawWidth = rawWidth,
            rawHeight = rawHeight,
            exifOrientation = image.exifOrientation,
        )
    }
}

internal fun applyExifOrientation(bitmap: Bitmap, orientation: Int): Bitmap {
    val matrix = exifOrientationMatrix(orientation)
    if (orientation == ExifInterface.ORIENTATION_NORMAL) return bitmap
    return Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, false)
}

internal fun exifOrientationMatrix(orientation: Int): Matrix {
    require(orientation in 1..8) { "EXIF orientation must be in 1..8" }
    return Matrix().apply {
        when (orientation) {
            ExifInterface.ORIENTATION_FLIP_HORIZONTAL -> setScale(-1f, 1f)
            ExifInterface.ORIENTATION_ROTATE_180 -> setRotate(180f)
            ExifInterface.ORIENTATION_FLIP_VERTICAL -> {
                setRotate(180f)
                postScale(-1f, 1f)
            }
            ExifInterface.ORIENTATION_TRANSPOSE -> {
                setRotate(90f)
                postScale(-1f, 1f)
            }
            ExifInterface.ORIENTATION_ROTATE_90 -> setRotate(90f)
            ExifInterface.ORIENTATION_TRANSVERSE -> {
                setRotate(-90f)
                postScale(-1f, 1f)
            }
            ExifInterface.ORIENTATION_ROTATE_270 -> setRotate(-90f)
        }
    }
}

internal object MobileNetCalibrationPreprocessor : CalibrationPreprocessor {
    const val CONTRACT_ID = "android-mobilenet-v1-image-v3"
    const val CONFIGURATION =
        "{\"contract_id\":\"android-mobilenet-v1-image-v3\"," +
            "\"exif_policy\":\"androidx-exifinterface-1.4.2-tag-absent-normal-explicit-1-to-8-before-crop\"," +
            "\"crop_policy\":\"center-square-floor-min-times-0.875\"," +
            "\"resize_method\":\"android-bitmap-bilinear\"," +
            "\"width\":224,\"height\":224,\"channels\":\"RGB\"," +
            "\"dtype\":\"FLOAT32\",\"normalization\":\"(value/127.5)-1\"}"
    val configurationSha256: String
        get() = CalibrationContract.sha256(CONFIGURATION.toByteArray(Charsets.UTF_8))

    override fun preprocess(image: CalibrationDecodedImage): CalibrationInputTensor {
        val source = (image as? BitmapCalibrationImage)?.bitmap
            ?: error("Android bitmap input is required")
        val cropWidth = (source.width * 0.875f).toInt().coerceAtLeast(1)
        val cropHeight = (source.height * 0.875f).toInt().coerceAtLeast(1)
        val cropSize = minOf(cropWidth, cropHeight)
        val left = (source.width - cropSize) / 2
        val top = (source.height - cropSize) / 2
        val cropped = Bitmap.createBitmap(source, left, top, cropSize, cropSize)
        val resized = Bitmap.createScaledBitmap(cropped, 224, 224, true)
        try {
            val pixels = IntArray(224 * 224)
            resized.getPixels(pixels, 0, 224, 0, 0, 224, 224)
            val buffer = ByteBuffer.allocateDirect(1 * 224 * 224 * 3 * 4)
                .order(ByteOrder.nativeOrder())
            pixels.forEach { pixel ->
                buffer.putFloat(((pixel shr 16) and 0xff) / 127.5f - 1.0f)
                buffer.putFloat(((pixel shr 8) and 0xff) / 127.5f - 1.0f)
                buffer.putFloat((pixel and 0xff) / 127.5f - 1.0f)
            }
            val bytes = ByteArray(buffer.position())
            buffer.duplicate().apply { flip() }.get(bytes)
            buffer.rewind()
            return CalibrationInputTensor(buffer, CalibrationContract.sha256(bytes))
        } finally {
            if (resized !== cropped) resized.recycle()
            if (cropped !== source) cropped.recycle()
        }
    }
}

internal class CalibrationLabelMapping private constructor(
    val labels: List<String>,
    val sha256: String,
) {
    init {
        require(labels.size == 1001) { "MobileNet label mapping must contain 1001 labels" }
        require(labels.all { it.isNotBlank() }) { "label mapping contains a blank label" }
    }

    companion object {
        fun parse(bytes: ByteArray): CalibrationLabelMapping {
            val parts = bytes.toString(Charsets.UTF_8).split('\n').toMutableList()
            if (parts.lastOrNull().isNullOrEmpty()) parts.removeAt(parts.lastIndex)
            val labels = parts.map { it.removeSuffix("\r") }
            require(labels.none { it.isBlank() }) { "label mapping contains a blank line" }
            require(labels.firstOrNull()?.startsWith('\uFEFF') != true) {
                "UTF-8 BOM is not allowed in label mapping"
            }
            return CalibrationLabelMapping(labels, CalibrationContract.sha256(bytes))
        }
    }
}

internal class MobileNetCalibrationPostprocessor(
    private val labelMapping: CalibrationLabelMapping,
) : CalibrationPostprocessor {
    override fun process(output: FloatArray): ClassificationOutput {
        require(output.size == labelMapping.labels.size) { "unexpected model output size" }
        val nonFinite = output.count { !it.isFinite() }
        val bytes = ByteBuffer.allocate(output.size * 4).order(ByteOrder.nativeOrder())
        output.forEach(bytes::putFloat)
        val top = output.indices.sortedWith(
            compareByDescending<Int> { output[it] }.thenBy { it }
        ).take(5)
        return ClassificationOutput(
            topIndices = top,
            topLabels = top.map(labelMapping.labels::get),
            outputSha256 = CalibrationContract.sha256(bytes.array()),
            nonFiniteCount = nonFinite,
        )
    }
}

internal class LiteRtCalibrationRuntimePool(
    private val context: Context,
    private val cpuThreads: Int,
) : CalibrationRuntimePool {
    private val runtimes = mutableMapOf<CalibrationBackend, LiteRtCalibrationRuntime>()
    private var previousBackend: CalibrationBackend? = null

    override fun prepare(backend: CalibrationBackend): PreparedCalibrationBackend {
        val cold = backend !in runtimes
        val runtime = runtimes.getOrPut(backend) { create(backend) }
        val transition = previousBackend?.takeIf { it != backend }?.let {
            "${it.wireName}->${backend.wireName}"
        }
        previousBackend = backend
        return PreparedCalibrationBackend(runtime, cold, transition)
    }

    private fun create(backend: CalibrationBackend): LiteRtCalibrationRuntime {
        var delegate: GpuDelegate? = null
        var interpreter: Interpreter? = null
        try {
            val options = Interpreter.Options()
            when (backend) {
                CalibrationBackend.CPU -> options.setNumThreads(cpuThreads).setUseXNNPACK(true)
                CalibrationBackend.GPU -> {
                    check(CompatibilityList().isDelegateSupportedOnThisDevice) {
                        "GPU delegate is not supported; calibration does not fall back to CPU"
                    }
                    delegate = GpuDelegate(GpuDelegateProfile.DEFAULT.options())
                    options.addDelegate(delegate)
                }
            }
            interpreter = Interpreter(ModelLoader.map(context), options).also { it.allocateTensors() }
            val input = interpreter.getInputTensor(0)
            val output = interpreter.getOutputTensor(0)
            check(input.dataType() == DataType.FLOAT32 && input.shape().contentEquals(intArrayOf(1, 224, 224, 3)))
            check(output.dataType() == DataType.FLOAT32 && output.shape().contentEquals(intArrayOf(1, 1001)))
            return LiteRtCalibrationRuntime(backend, interpreter, delegate)
        } catch (error: Throwable) {
            try { interpreter?.close() } catch (cleanup: Throwable) { error.addSuppressed(cleanup) }
            try { delegate?.close() } catch (cleanup: Throwable) { error.addSuppressed(cleanup) }
            throw error
        }
    }

    override fun close() {
        var first: Throwable? = null
        runtimes.values.forEach {
            try { it.close() } catch (error: Throwable) {
                if (first == null) first = error else first?.addSuppressed(error)
            }
        }
        runtimes.clear()
        first?.let { throw it }
    }
}

private class LiteRtCalibrationRuntime(
    override val actualBackend: CalibrationBackend,
    private val interpreter: Interpreter,
    private val delegate: GpuDelegate?,
) : CalibrationBackendRuntime {
    override val fallbackStatus: CalibrationFallbackStatus = when (actualBackend) {
        CalibrationBackend.CPU -> CalibrationFallbackStatus.NOT_APPLICABLE
        CalibrationBackend.GPU -> CalibrationFallbackStatus.UNVERIFIED
    }

    override fun run(input: ByteBuffer, clock: CalibrationClock): CalibrationRawOutput {
        val output = ByteBuffer.allocateDirect(1001 * 4).order(ByteOrder.nativeOrder())
        input.rewind()
        output.clear()
        val startNs = clock.monotonicNanos()
        interpreter.run(input, output)
        val endNs = clock.monotonicNanos()
        output.rewind()
        val values = FloatArray(1001).also { output.asFloatBuffer().get(it) }
        return CalibrationRawOutput(values, startNs, endNs)
    }

    override fun close() {
        var first: Throwable? = null
        try { interpreter.close() } catch (error: Throwable) { first = error }
        try { delegate?.close() } catch (error: Throwable) {
            if (first == null) first = error else first?.addSuppressed(error)
        }
        first?.let { throw it }
    }
}

internal class DurableCalibrationResultStore(
    root: File,
) : CalibrationResultStore {
    private val canonicalRoot = root.apply { mkdirs() }.canonicalFile

    override fun persist(
        request: CalibrationRequest,
        output: ClassificationOutput,
    ): CalibrationPersistenceReceipt {
        val finalFile = File(canonicalRoot, "${request.requestId}.json").canonicalFile
        check(finalFile.parentFile == canonicalRoot) { "result path escapes calibration store" }
        check(!finalFile.exists()) { "classification result already exists" }
        val temporary = File(canonicalRoot, ".${request.requestId}.part").canonicalFile
        check(temporary.parentFile == canonicalRoot && !temporary.exists())
        val bytes = JSONObject()
            .put("schema_version", CalibrationContract.SCHEMA_VERSION)
            .put("protocol_version", CalibrationContract.PROTOCOL_VERSION)
            .put("request_id", request.requestId)
            .put("image_id", request.image.imageId)
            .put("top_indices", JSONArray(output.topIndices))
            .put("top_labels", JSONArray(output.topLabels))
            .put("output_sha256", output.outputSha256)
            .put("durability", CalibrationContract.DURABILITY)
            .toString().toByteArray(Charsets.UTF_8)
        var moved = false
        try {
            FileOutputStream(temporary).use {
                it.write(bytes)
                it.flush()
                it.fd.sync()
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                Files.move(
                    temporary.toPath(),
                    finalFile.toPath(),
                    StandardCopyOption.ATOMIC_MOVE,
                )
            } else {
                Os.rename(temporary.absolutePath, finalFile.absolutePath)
            }
            moved = true
            check(finalFile.readBytes().contentEquals(bytes)) {
                "classification result readback failed"
            }
            return CalibrationPersistenceReceipt("results/${finalFile.name}") {
                check(!finalFile.exists() || finalFile.delete()) {
                    "failed persisted result rollback failed"
                }
            }
        } catch (error: Throwable) {
            if (temporary.exists() && !temporary.delete()) {
                error.addSuppressed(IllegalStateException("temporary result cleanup failed"))
            }
            if (moved && finalFile.exists() && !finalFile.delete()) {
                error.addSuppressed(IllegalStateException("failed result cleanup failed"))
            }
            throw error
        }
    }
}

internal fun sha256File(file: File): String {
    val digest = MessageDigest.getInstance("SHA-256")
    file.inputStream().use { input ->
        val buffer = ByteArray(1024 * 1024)
        while (true) {
            val count = input.read(buffer)
            if (count < 0) break
            digest.update(buffer, 0, count)
        }
    }
    return digest.digest().joinToString("") { "%02x".format(it) }
}

internal object AndroidCalibrationClock : CalibrationClock {
    override fun monotonicNanos(): Long = SystemClock.elapsedRealtimeNanos()
}
