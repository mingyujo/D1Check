package com.example.d1check.benchmarkrunner

import java.nio.ByteBuffer
import java.nio.ByteOrder
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DeterministicInputSetTest {
    @Test
    fun legacyTimedTensorBytesAreUnchanged() {
        val expected = ByteBuffer.allocateDirect(64).order(ByteOrder.nativeOrder())
        var state = 0x12345678
        while (expected.remaining() >= Float.SIZE_BYTES) {
            state = state * 1664525 + 1013904223
            expected.putFloat(((state ushr 8) and 0xFFFFFF) / 16777215.0f)
        }
        expected.rewind()
        val actual = DeterministicInputSet.legacyTimedInput(64)

        assertEquals(DeterministicInputSet.sha256(expected), DeterministicInputSet.sha256(actual))
        assertEquals(
            "1c84eb2a3e523a7b0ba21faa795956987ffe4c4c2c9025f562544c3bcb04ac27",
            DeterministicInputSet.sha256(actual),
        )
    }

    @Test
    fun sameSeedReproducesWholeSequenceAndDifferentSeedChangesIt() {
        fun hashes(seed: Long) = DeterministicInputSet.generator(seed, 64).let { generator ->
            List(32) { DeterministicInputSet.sha256(generator.next()) }
        }
        assertEquals(hashes(123), hashes(123))
        assertNotEquals(hashes(123), hashes(124))
        assertEquals(32, hashes(123).distinct().size)
    }

    @Test
    fun generatedValuesAreFiniteAndWithinUnitInterval() {
        val values = DeterministicInputSet.generator(7, 128).next()
            .order(ByteOrder.nativeOrder()).asFloatBuffer()
        while (values.hasRemaining()) {
            val value = values.get()
            assertTrue(value.isFinite())
            assertTrue(value in 0.0f..1.0f)
        }
    }
}
