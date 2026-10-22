package com.example.d1check.benchmarkrunner

import java.nio.ByteBuffer
import java.nio.ByteOrder

/** Shared RGB8 integer contract: half-pixel bilinear stretch, Q16, round half up. */
internal object ProbeImageContract {
    const val ID = "rgb8-bilinear-q16-stretch-v1"

    fun requireCanonicalPng(bytes: ByteArray) {
        require(bytes.size >= 33 && bytes.take(8).toByteArray().contentEquals(byteArrayOf(-119,80,78,71,13,10,26,10)))
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.BIG_ENDIAN).apply { position(8) }
        var header = false; var data = false; var end = false
        while (buffer.remaining() >= 12 && !end) {
            val length = buffer.int
            val kind = ByteArray(4).also { buffer.get(it) }.toString(Charsets.US_ASCII)
            require(length >= 0 && length.toLong() + 4 <= buffer.remaining())
            when (kind) {
                "IHDR" -> {
                    require(!header && length == 13 && buffer.position() == 16)
                    require(buffer.getInt(buffer.position()) in 1..4096 && buffer.getInt(buffer.position()+4) in 1..4096)
                    require(buffer.get(buffer.position()+8).toInt() == 8 && buffer.get(buffer.position()+9).toInt() == 2)
                    header = true
                }
                "IDAT" -> { require(header); data = true }
                "IEND" -> { require(header && data && length == 0); end = true }
                else -> error("Canonical RGB PNG must not contain color/orientation/ancillary chunks: $kind")
            }
            buffer.position(buffer.position() + length + 4)
        }
        require(end && buffer.remaining() == 0)
    }

    fun resize(rgb: ByteArray, width: Int, height: Int, size: Int = 320): ByteArray {
        require(width > 0 && height > 0 && size > 0 && rgb.size.toLong() == width.toLong() * height * 3)
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

    fun tensor(rgb: ByteArray): ByteBuffer = ByteBuffer.allocateDirect(rgb.size * 4)
        .order(ByteOrder.LITTLE_ENDIAN).apply {
            rgb.forEach { putFloat(((it.toInt() and 255) - 127.5f) / 127.5f) }
            rewind()
        }
}
