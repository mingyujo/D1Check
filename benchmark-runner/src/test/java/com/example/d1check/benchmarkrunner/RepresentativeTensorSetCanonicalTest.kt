package com.example.d1check.benchmarkrunner

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.security.MessageDigest

class RepresentativeTensorSetCanonicalTest {
    @Test
    fun pythonGoldenFixtureHasIdenticalCanonicalBytesAndSha256() {
        val configuration = linkedMapOf<String, Any?>(
            "shape" to listOf(1, 224, 224, 3),
            "normalization_range" to listOf(-1.0, 1.0),
            "normalization" to "(pixel/255.0 - 0.5) * 2.0",
            "central_crop_fraction" to 0.875,
            "resize" to linkedMapOf(
                "width" to 224,
                "height" to 224,
                "algorithm" to "Pillow.Image.Resampling.BILINEAR",
                "tf_slim_reference" to "tf.image.resize_bilinear_align_corners_false",
                "implementation_equivalence_claimed" to false,
                "limitation" to
                    "Pillow and TensorFlow bilinear sampling kernels are not byte-identical",
            ),
            "implementation" to "Pillow",
            "implementation_version" to "12.0.0",
            "rgb_order" to "RGB",
            "exif_orientation_policy" to "ImageOps.exif_transpose_before_RGB_conversion",
            "central_crop_rounding" to "symmetric_floor_offset_keep_remainder",
            "dtype" to "FLOAT32",
            "endian" to "LITTLE",
            "version" to "tf-slim-mobilenet-v1-eval-pillow-v1",
        )
        val actual = PreprocessingCanonicalJsonV1.bytes(configuration)
        val fixture = sequenceOf(
            File("tools/fixtures/mobilenet_preprocessing_configuration_v1.canonical.json"),
            File("../tools/fixtures/mobilenet_preprocessing_configuration_v1.canonical.json"),
        ).first(File::isFile).readBytes().let { bytes ->
            if (bytes.lastOrNull() == '\n'.code.toByte()) bytes.dropLast(1).toByteArray() else bytes
        }
        assertArrayEquals(fixture, actual)
        assertEquals(
            "ad6f76b120f8ccf0f64a260ee388f7af2b002dc722436f8b19552dcb6f702260",
            sha256(actual),
        )
        val text = actual.toString(Charsets.UTF_8)
        assertTrue(text.contains("[-1.0,1.0]"))
        assertTrue(text.contains("pixel/255.0"))
        assertFalse(text.contains("\\/"))
    }

    @Test(expected = IllegalArgumentException::class)
    fun exponentFormNumberIsRejectedByVersionOneContract() {
        PreprocessingCanonicalJsonV1.bytes(mapOf("unsupported" to 1e-7))
    }

    @Test
    fun declaredExpectedAndRecomputedHashesAreAllEnforced() {
        RepresentativeHashContract.verifyPreprocessing(
            EXPECTED_PREPROCESSING_SHA, EXPECTED_PREPROCESSING_SHA,
            EXPECTED_PREPROCESSING_SHA,
        )
        val expectedMismatch = kotlin.runCatching {
            RepresentativeHashContract.verifyPreprocessing(
                EXPECTED_PREPROCESSING_SHA, "0".repeat(64),
                EXPECTED_PREPROCESSING_SHA,
            )
        }.exceptionOrNull() as IllegalArgumentException
        assertTrue(expectedMismatch.message!!.contains("declared=$EXPECTED_PREPROCESSING_SHA"))
        assertTrue(expectedMismatch.message!!.contains("expected=${"0".repeat(64)}"))
        assertTrue(expectedMismatch.message!!.contains("recomputed=$EXPECTED_PREPROCESSING_SHA"))

        val recomputedMismatch = kotlin.runCatching {
            RepresentativeHashContract.verifyPreprocessing(
                EXPECTED_PREPROCESSING_SHA, EXPECTED_PREPROCESSING_SHA,
                "1".repeat(64),
            )
        }.exceptionOrNull() as IllegalArgumentException
        assertTrue(recomputedMismatch.message!!.contains("recomputed=${"1".repeat(64)}"))
        RepresentativeHashContract.verifyContainer("2".repeat(64), "2".repeat(64))
        val containerMismatch = kotlin.runCatching {
            RepresentativeHashContract.verifyContainer("2".repeat(64), "3".repeat(64))
        }.exceptionOrNull() as IllegalArgumentException
        assertTrue(containerMismatch.message!!.contains("expected=${"2".repeat(64)}"))
        assertTrue(containerMismatch.message!!.contains("recomputed=${"3".repeat(64)}"))
    }

    private fun sha256(value: ByteArray): String = MessageDigest.getInstance("SHA-256")
        .digest(value).joinToString("") { "%02x".format(it) }

    companion object {
        private const val EXPECTED_PREPROCESSING_SHA =
            "ad6f76b120f8ccf0f64a260ee388f7af2b002dc722436f8b19552dcb6f702260"
    }
}
