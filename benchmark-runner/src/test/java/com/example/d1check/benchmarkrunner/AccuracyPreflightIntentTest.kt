package com.example.d1check.benchmarkrunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Test

class AccuracyPreflightIntentTest {
    private val commandId = "11111111-2222-3333-4444-555555555555"

    @Test
    fun disabledIntentIsIgnored() {
        assertNull(AccuracyPreflightIntentParser.parse(emptyMap()))
    }

    @Test
    fun explicitConfigurationIsParsed() {
        val config = AccuracyPreflightIntentParser.parse(mapOf(
            AccuracyPreflightIntentParser.EXTRA_ENABLED to true,
            AccuracyPreflightIntentParser.EXTRA_COMMAND_ID to commandId,
            AccuracyPreflightIntentParser.EXTRA_INPUT_COUNT to 32,
            AccuracyPreflightIntentParser.EXTRA_SEED to 99L,
            AccuracyPreflightIntentParser.EXTRA_CPU_THREADS to 2,
            AccuracyPreflightIntentParser.EXTRA_ATOL to "0.0002",
            AccuracyPreflightIntentParser.EXTRA_RTOL to "0.002",
            AccuracyPreflightIntentParser.EXTRA_RELATIVE_EPSILON to "0.000001",
            AccuracyPreflightIntentParser.EXTRA_GPU_PROFILE to "gpu-fp32-strict-v1",
        ))!!
        assertEquals(32, config.inputCount)
        assertEquals(99L, config.seed)
        assertEquals(2, config.cpuThreads)
        assertEquals(0.0002, config.tolerance.atol, 0.0)
        assertEquals(GpuDelegateProfile.FP32_STRICT, config.gpuDelegateProfile)
    }

    @Test
    fun representativeRequiresTensorSetPath() {
        val config = AccuracyPreflightIntentParser.parse(mapOf(
            AccuracyPreflightIntentParser.EXTRA_ENABLED to true,
            AccuracyPreflightIntentParser.EXTRA_COMMAND_ID to commandId,
            AccuracyPreflightIntentParser.EXTRA_CHECK_TYPE to "representative",
            AccuracyPreflightIntentParser.EXTRA_TENSOR_SET_PATH to "/sdcard/input.d1tset",
            AccuracyPreflightIntentParser.EXTRA_TENSOR_SET_SHA256 to "a".repeat(64),
            AccuracyPreflightIntentParser.EXTRA_PREPROCESSING_SHA256 to "b".repeat(64),
        ))!!
        assertEquals(AccuracyCheckType.REPRESENTATIVE, config.checkType)
        assertEquals("/sdcard/input.d1tset", config.representativeTensorSetPath)
        assertEquals("a".repeat(64), config.expectedTensorSetContainerSha256)
        assertEquals("b".repeat(64), config.expectedPreprocessingConfigurationSha256)
    }

    @Test
    fun invalidCountAndToleranceAreRejected() {
        assertThrows(IllegalArgumentException::class.java) {
            AccuracyPreflightIntentParser.parse(mapOf(
                AccuracyPreflightIntentParser.EXTRA_ENABLED to true,
                AccuracyPreflightIntentParser.EXTRA_COMMAND_ID to commandId,
                AccuracyPreflightIntentParser.EXTRA_INPUT_COUNT to 0,
            ))
        }
        assertThrows(IllegalArgumentException::class.java) {
            AccuracyPreflightIntentParser.parse(mapOf(
                AccuracyPreflightIntentParser.EXTRA_ENABLED to true,
                AccuracyPreflightIntentParser.EXTRA_COMMAND_ID to commandId,
                AccuracyPreflightIntentParser.EXTRA_ATOL to "NaN",
            ))
        }
    }
}
