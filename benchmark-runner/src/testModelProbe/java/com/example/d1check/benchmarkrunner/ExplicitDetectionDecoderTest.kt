package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test

class ExplicitDetectionDecoderTest {
    @Test fun yxhwLabelOffsetAndOriginalCoordinates() {
        val result = ExplicitDetectionDecoder.decode(floatArrayOf(.1f, .75f), floatArrayOf(.5f, -.25f, 0f, 0f),
            listOf(doubleArrayOf(.5, .5, .4, .2)), listOf("a", "b"), 100, 200).single()
        assertEquals("b", result["label"])
        val box = result["box"] as List<*>
        listOf(20.0, 100.0, 40.0, 40.0).forEachIndexed { i, v -> assertEquals(v, box[i] as Double, 1e-8) }
    }
    @Test fun fixedThresholdNmsAndTieRules() {
        val results = ExplicitDetectionDecoder.decode(floatArrayOf(.5f, .1f, .1f, .7f), FloatArray(8),
            List(2) { doubleArrayOf(.5, .5, .2, .2) }, listOf("a", "b"), 100, 100)
        assertEquals(1, results.size)
        assertEquals("b", results.single()["label"])
        val threshold = ExplicitDetectionDecoder.decode(floatArrayOf(.5f, .5f), FloatArray(4),
            listOf(doubleArrayOf(.5, .5, 1.0, 1.0)), listOf("a", "b"), 1, 1)
        assertEquals("a", threshold.single()["label"])
    }
    @Test fun malformedAndNonfiniteFailClosed() {
        assertThrows(IllegalArgumentException::class.java) {
            ExplicitDetectionDecoder.decode(floatArrayOf(Float.NaN), FloatArray(4), listOf(doubleArrayOf(.5,.5,1.0,1.0)), listOf("a"), 1, 1)
        }
        assertThrows(IllegalArgumentException::class.java) {
            ExplicitDetectionDecoder.decode(floatArrayOf(.5f), FloatArray(3), listOf(doubleArrayOf(.5,.5,1.0,1.0)), listOf("a"), 1, 1)
        }
    }
}
