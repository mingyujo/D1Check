package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test
import java.nio.ByteOrder

class ProbeImageContractTest {
    private fun png(extra: Boolean = false): ByteArray {
        val stream = java.io.ByteArrayOutputStream()
        val out = java.io.DataOutputStream(stream)
        out.write(byteArrayOf(-119,80,78,71,13,10,26,10))
        fun chunk(name: String, bytes: ByteArray) { out.writeInt(bytes.size);out.writeBytes(name);out.write(bytes);out.writeInt(0) }
        val header = java.nio.ByteBuffer.allocate(13).putInt(1).putInt(1).put(8).put(2).put(0).put(0).put(0).array()
        chunk("IHDR",header)
        if (extra) chunk("iCCP",byteArrayOf(1))
        chunk("IDAT",byteArrayOf(1));chunk("IEND",byteArrayOf())
        return stream.toByteArray()
    }
    @Test fun canonicalChunkContractRejectsColorMetadataAndTruncation() {
        ProbeImageContract.requireCanonicalPng(png())
        for (bytes in listOf(png(true), png().dropLast(1).toByteArray())) {
            try { ProbeImageContract.requireCanonicalPng(bytes);fail("invalid PNG contract accepted") } catch (_: RuntimeException) { }
        }
    }
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
