package com.example.d1check.contract

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class GpuEventBufferTest {
    @Test
    fun inferenceBufferIsBoundedAndPreservesSpans() {
        val buffer = GpuEventBuffer(2, 3)
        assertTrue(buffer.recordInference(10L, 20L, 0L, 1))
        assertTrue(buffer.recordInference(30L, 45L, 1L, 1))
        assertFalse(buffer.hasInferenceCapacity)
        assertFalse(buffer.recordInference(50L, 60L, 2L, 1))

        assertEquals(2, buffer.inferenceCount)
        assertEquals(10L, buffer.inferenceStartAt(0))
        assertEquals(20L, buffer.inferenceEndAt(0))
    }

    @Test(expected = IllegalStateException::class)
    fun lifecycleBufferHasExplicitUpperBound() {
        val buffer = GpuEventBuffer(1, 1)
        val record = BufferedGpuRecord("warmup", "warmup", "ok", 1, 2, 0, 1, null)
        buffer.recordLifecycle(record)
        buffer.recordLifecycle(record)
    }
}
