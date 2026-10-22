package com.example.d1check.benchmarkrunner

import org.junit.Assert.assertEquals
import org.junit.Test
import java.nio.ByteBuffer

class TensorBufferResetTest {
    @Test
    fun resetsPositionsBeforeBuffersAreReused() {
        val input = ByteBuffer.allocate(16).apply {
            position(12)
            limit(14)
        }
        val output = ByteBuffer.allocate(24).apply {
            position(20)
            limit(22)
        }

        resetTensorBuffers(input, output)

        assertEquals(0, input.position())
        assertEquals(14, input.limit())
        assertEquals(0, output.position())
        assertEquals(output.capacity(), output.limit())
    }
}
