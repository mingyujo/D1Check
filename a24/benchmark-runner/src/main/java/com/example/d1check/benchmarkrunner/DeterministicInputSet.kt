package com.example.d1check.benchmarkrunner

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest

internal object DeterministicInputSet {
    const val VERSION = "lcg-float32-unit-v1"
    const val DEFAULT_SEED = 0x12345678L
    const val NORMALIZATION = "synthetic_[0,1]_float32_no_additional_normalization"
    val INPUT_SHAPE = intArrayOf(1, 224, 224, 3)
    const val INPUT_DTYPE = "FLOAT32"

    fun generator(seed: Long, tensorByteCount: Int): Generator =
        Generator(seed.toInt(), tensorByteCount)

    fun legacyTimedInput(tensorByteCount: Int): ByteBuffer =
        generator(DEFAULT_SEED, tensorByteCount).next()

    class Generator internal constructor(
        private var state: Int,
        private val tensorByteCount: Int,
    ) {
        init {
            require(tensorByteCount > 0 && tensorByteCount % Float.SIZE_BYTES == 0)
        }

        fun next(): ByteBuffer {
            val buffer = ByteBuffer.allocateDirect(tensorByteCount).order(ByteOrder.nativeOrder())
            while (buffer.remaining() >= Float.SIZE_BYTES) {
                state = state * 1664525 + 1013904223
                buffer.putFloat(((state ushr 8) and 0xFFFFFF) / 16777215.0f)
            }
            return buffer.rewind() as ByteBuffer
        }
    }

    fun sha256(buffer: ByteBuffer): String {
        val duplicate = buffer.asReadOnlyBuffer()
        duplicate.rewind()
        val digest = MessageDigest.getInstance("SHA-256")
        digest.update(duplicate)
        return digest.digest().toHex()
    }

    fun MessageDigest.hexDigest(): String = digest().toHex()

    private fun ByteArray.toHex(): String = joinToString("") { "%02x".format(it) }
}
