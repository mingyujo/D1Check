package com.example.d1check.requestrunner

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest

/*
 * 출처: feature/arrival-scheduling-20260923 @ d588323
 *   benchmark-runner/src/modelProbe/.../ProbeImageContract.kt (requireCanonicalPng · resize · tensor 정규화) — 그대로
 *   benchmark-runner/src/modelProbe/.../ProbeTaskAdapter.kt 55~61행 (RGB 추출 · 분류 (x-127)/128 · 탐지 (x-127.5)/127.5)
 * 바꾼 것: 디코드된 RGB 바이트를 받는 순수 함수로 분리하고 (JVM 시험용), 텐서를 FloatArray 로 돌려준다
 * (CompiledModel TensorBuffer.writeFloat 가 FloatArray 를 받는다). 값 · 순서 · 반올림은 A24 와 같다.
 */
object ImageContract {
    const val ID = "rgb8-bilinear-q16-stretch-v1"
    const val CLASSIFICATION_SIZE = 224
    const val DETECTION_SIZE = 320

    /** IHDR / IDAT / IEND 만 · RGB8 · 1..4096 — 색 · 방향 · 보조 청크는 거부 (A24 ProbeImageContract.requireCanonicalPng). */
    fun requireCanonicalPng(bytes: ByteArray) {
        require(bytes.size >= 33 && bytes.take(8).toByteArray().contentEquals(byteArrayOf(-119, 80, 78, 71, 13, 10, 26, 10))) {
            "not a PNG"
        }
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.BIG_ENDIAN).apply { position(8) }
        var header = false
        var data = false
        var end = false
        while (buffer.remaining() >= 12 && !end) {
            val length = buffer.int
            val kind = ByteArray(4).also { buffer.get(it) }.toString(Charsets.US_ASCII)
            require(length >= 0 && length.toLong() + 4 <= buffer.remaining()) { "truncated PNG chunk $kind" }
            when (kind) {
                "IHDR" -> {
                    require(!header && length == 13 && buffer.position() == 16) { "IHDR position/length" }
                    require(buffer.getInt(buffer.position()) in 1..4096 && buffer.getInt(buffer.position() + 4) in 1..4096) {
                        "IHDR geometry"
                    }
                    require(buffer.get(buffer.position() + 8).toInt() == 8 && buffer.get(buffer.position() + 9).toInt() == 2) {
                        "IHDR must be 8-bit RGB"
                    }
                    header = true
                }
                "IDAT" -> { require(header) { "IDAT before IHDR" }; data = true }
                "IEND" -> { require(header && data && length == 0) { "IEND" }; end = true }
                else -> error("Canonical RGB PNG must not contain color/orientation/ancillary chunks: $kind")
            }
            buffer.position(buffer.position() + length + 4)
        }
        require(end && buffer.remaining() == 0) { "incomplete canonical PNG" }
    }

    /** Q16 half-pixel bilinear stretch · clamp · round half up (A24 ProbeImageContract.resize). */
    fun resize(rgb: ByteArray, width: Int, height: Int, size: Int = DETECTION_SIZE): ByteArray {
        require(width > 0 && height > 0 && size > 0 && rgb.size.toLong() == width.toLong() * height * 3) { "RGB geometry" }
        fun axis(length: Int) = List(size) { i ->
            val q = (((2L * i + 1) * length * 65536) / (2L * size) - 32768)
                .coerceIn(0L, (length - 1L) * 65536)
            longArrayOf(q / 65536, minOf(q / 65536 + 1, length - 1L), q % 65536)
        }
        val xs = axis(width)
        val ys = axis(height)
        val out = ByteArray(size * size * 3)
        fun at(x: Long, y: Long, c: Int) = rgb[((y * width + x) * 3 + c).toInt()].toInt() and 255
        for (y in 0 until size) for (x in 0 until size) for (c in 0..2) {
            val (x0, x1, fx) = xs[x]
            val (y0, y1, fy) = ys[y]
            val a = at(x0, y0, c) * (65536 - fx) + at(x1, y0, c) * fx
            val b = at(x0, y1, c) * (65536 - fx) + at(x1, y1, c) * fx
            out[(y * size + x) * 3 + c] = ((a * (65536 - fy) + b * fy + 2147483648L) / 4294967296L).toByte()
        }
        return out
    }

    /** 분류: (x − 127) / 128 (A24 ProbeTaskAdapter 59~60행). */
    fun classificationTensor(resized: ByteArray): FloatArray =
        FloatArray(resized.size) { i -> ((resized[i].toInt() and 255) - 127f) / 128f }

    /** 탐지: (x − 127.5) / 127.5 (A24 ProbeImageContract.tensor). */
    fun detectionTensor(resized: ByteArray): FloatArray =
        FloatArray(resized.size) { i -> ((resized[i].toInt() and 255) - 127.5f) / 127.5f }

    fun tensorFor(task: String, rgb: ByteArray, width: Int, height: Int): FloatArray = when (task) {
        "classification" -> classificationTensor(resize(rgb, width, height, CLASSIFICATION_SIZE))
        "detection" -> detectionTensor(resize(rgb, width, height, DETECTION_SIZE))
        else -> error("unknown task $task")
    }

    /** A24 ProbeRawSession.sha256(ByteBuffer): float32 little-endian 바이트의 SHA-256. */
    fun sha256(values: FloatArray): String {
        val bytes = ByteBuffer.allocate(values.size * 4).order(ByteOrder.LITTLE_ENDIAN)
        values.forEach { bytes.putFloat(it) }
        return MessageDigest.getInstance("SHA-256").digest(bytes.array()).toHex()
    }

    fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes).toHex()

    fun ByteArray.toHex(): String = joinToString("") { "%02x".format(it) }

    /** ARGB int 픽셀 (Bitmap.getPixels) → RGB 바이트 (A24 ProbeTaskAdapter 55~56행). */
    fun rgbFromArgb(pixels: IntArray): ByteArray {
        val rgb = ByteArray(pixels.size * 3)
        pixels.forEachIndexed { i, p ->
            rgb[i * 3] = (p shr 16).toByte()
            rgb[i * 3 + 1] = (p shr 8).toByte()
            rgb[i * 3 + 2] = p.toByte()
        }
        return rgb
    }
}

/** 디코드 결과 (A24 는 BitmapFactory.decodeFile + getPixels — 요청마다 같은 일을 output_ready 안에 넣는다). */
class DecodedImage(val width: Int, val height: Int, val rgb: ByteArray) {
    init {
        require(width in 1..4096 && height in 1..4096 && rgb.size.toLong() == width.toLong() * height * 3) { "decoded geometry" }
    }
}
