package com.example.d1check.benchmarkrunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class GpuDelegateProfileTest {
    @Test
    fun profilesExposeExplicitStableConfiguration() {
        val compat = GpuDelegateProfile.fromId("gpu-compat-default-v1")
        val strict = GpuDelegateProfile.fromId("gpu-fp32-strict-v1")
        assertTrue(compat.precisionLossAllowed)
        assertFalse(strict.precisionLossAllowed)
        assertEquals("FAST_SINGLE_ANSWER", compat.inferencePreferenceName)
        assertEquals("UNSET", compat.forceBackendName)
        assertNotEquals(compat.configurationSha256, strict.configurationSha256)
        assertEquals(64, compat.configurationSha256.length)
    }
}
