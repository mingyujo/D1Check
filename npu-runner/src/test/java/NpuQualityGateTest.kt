package com.example.d1check.npurunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class NpuQualityGateTest {

    private fun probs(n: Int, top: Int): FloatArray =
        FloatArray(n) { if (it == top) 0.5f else 0.5f / (n - 1) }

    /** 비트 동일 = CPU 로 돈 것 → 다른 두 기준을 넘어도 FAIL (반전 논리). */
    @Test
    fun bitIdenticalOutputFails() {
        val ref = List(4) { probs(1001, 112) }
        val r = NpuQualityGate.evaluate(ref, ref.map { it.copyOf() })
        assertTrue(r.bitIdenticalToCpu)
        assertEquals(4, r.bitIdenticalCount)
        assertEquals(4, r.argmaxAgreement)
        assertFalse(r.pass)
    }

    /** 출력 길이는 하드코딩하지 않는다 (EfficientNet-Lite0 = 1000). */
    @Test
    fun closeButNotIdenticalPassesForAnyLength() {
        for (len in listOf(1000, 1001)) {
            val ref = List(4) { probs(len, 7) }
            val cand = ref.map { a -> FloatArray(a.size) { a[it] * 1.0001f } }
            val r = NpuQualityGate.evaluate(ref, cand)
            assertFalse(r.bitIdenticalToCpu)
            assertEquals(4, r.argmaxAgreement)
            assertTrue(r.cosineMin!! >= NpuQualityGate.COSINE_MIN_THRESHOLD)
            assertTrue(r.pass)
        }
    }

    @Test
    fun oneBitIdenticalSampleIsEnoughToFail() {
        val ref = List(3) { probs(10, 1) }
        val cand = listOf(ref[0].copyOf(), ref[1].map { it * 1.001f }.toFloatArray(), ref[2].map { it * 1.001f }.toFloatArray())
        val r = NpuQualityGate.evaluate(ref, cand)
        assertEquals(1, r.bitIdenticalCount)
        assertFalse(r.pass)
    }

    @Test
    fun argmaxDisagreementFails() {
        val ref = listOf(probs(10, 1), probs(10, 2))
        val cand = listOf(probs(10, 1).map { it * 1.001f }.toFloatArray(), probs(10, 3))
        val r = NpuQualityGate.evaluate(ref, cand)
        assertEquals(1, r.argmaxAgreement)
        assertFalse(r.pass)
    }

    @Test
    fun nonFiniteOutputFails() {
        val ref = listOf(probs(10, 1))
        val cand = listOf(probs(10, 1).also { it[3] = Float.NaN })
        val r = NpuQualityGate.evaluate(ref, cand)
        assertNull(r.cosineMin)
        assertFalse(r.pass)
    }

    @Test
    fun argmaxTieBreaksToLowestIndex() {
        assertEquals(2, NpuQualityGate.argmax(floatArrayOf(0f, 1f, 3f, 3f)))
    }

    @Test(expected = IllegalArgumentException::class)
    fun lengthMismatchThrows() {
        NpuQualityGate.evaluate(listOf(FloatArray(1000)), listOf(FloatArray(1001)))
    }
}
