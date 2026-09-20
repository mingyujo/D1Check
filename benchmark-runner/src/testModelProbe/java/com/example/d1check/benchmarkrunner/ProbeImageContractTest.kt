package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test
import java.nio.ByteOrder

class ProbeImageContractTest {
    @Test fun identityAndClampedSinglePixel() {
        val input = ByteArray(12) { it.toByte() }
        assertArrayEquals(input, ProbeImageContract.resize(input, 2, 2, 2))
        assertArrayEquals(ByteArray(27) { byteArrayOf(1, -128, -1)[it % 3] },
            ProbeImageContract.resize(byteArrayOf(1, -128, -1), 1, 1, 3))
    }
    @Test fun sharedHalfPixelFixtureAndNormalization() {
        val fixture = byteArrayOf(0, 0, 0, -1, -1, -1)
        val expectedRow = byteArrayOf(0, 0, 0, -128, -128, -128, -1, -1, -1)
        assertArrayEquals(ByteArray(27) { expectedRow[it % 9] }, ProbeImageContract.resize(fixture, 2, 1, 3))
        val values = ProbeImageContract.tensor(byteArrayOf(0, -1)).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer()
        assertEquals(-1f, values.get(), 0f)
        assertEquals(1f, values.get(), 0f)
    }
    @Test fun malformedGeometryRejected() {
        assertThrows(IllegalArgumentException::class.java) { ProbeImageContract.resize(byteArrayOf(0), 1, 1) }
    }
}
