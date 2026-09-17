package com.example.d1check.benchmarkrunner

import android.net.Uri
import android.graphics.Bitmap
import android.graphics.RectF
import androidx.exifinterface.media.ExifInterface
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import java.util.Base64
import java.io.ByteArrayInputStream

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class AndroidCalibrationImageIntegrationTest {
    @get:Rule
    val temporary = TemporaryFolder()

    @Test
    fun productionReaderAndroidDecoderAndMobileNetPreprocessorConsumeRealImageFile() {
        val fixture = requireNotNull(javaClass.getResourceAsStream("/calibration/fixture.png.base64")) {
            "required calibration PNG fixture is missing from test resources"
        }.bufferedReader(Charsets.US_ASCII).use { it.readText() }
        val png = Base64.getMimeDecoder().decode(fixture)
        val orientationRange = ExifInterface(ByteArrayInputStream(png))
            .getAttributeRange(ExifInterface.TAG_ORIENTATION)
        assertTrue("PNG fixture must not contain an explicit orientation tag",
            orientationRange == null || orientationRange[0] < 0L)
        val file = temporary.newFile("explicit-test-fixture.png").apply { writeBytes(png) }
        val context = RuntimeEnvironment.getApplication()
        val image = AndroidCalibrationImageReader(context.contentResolver).read(Uri.fromFile(file).toString())
        assertEquals("image/png", image.mimeType)
        assertEquals(CalibrationContract.sha256(png), image.sha256)
        assertEquals(png.size.toLong(), image.byteCount)
        assertEquals(1, image.exifOrientation)
        AndroidCalibrationImageDecoder.decode(image).use { decoded ->
            assertEquals(1, decoded.rawWidth)
            assertEquals(1, decoded.rawHeight)
            assertEquals(1, decoded.exifOrientation)
            assertEquals(1, decoded.width)
            assertEquals(1, decoded.height)
            val input = MobileNetCalibrationPreprocessor.preprocess(decoded)
            assertEquals(224 * 224 * 3 * 4, input.buffer.capacity())
            assertTrue(input.sha256.matches(Regex("[0-9a-f]{64}")))
        }
        val requestId = java.util.UUID.randomUUID().toString()
        val receipt = DurableCalibrationResultStore(temporary.newFolder("results")).persist(
            CalibrationRequest(
                requestId,
                CalibrationRequestType.NORMAL,
                CalibrationImageSpec(
                    "fixture", "images/fixture.png", image.sha256, image.byteCount,
                    0, "fixture", 1, 1, 1, 1, 1, "image/png",
                ),
                Uri.fromFile(file).toString(),
                CalibrationBackend.CPU,
                null,
                1L,
                null,
            ),
            ClassificationOutput(listOf(0), listOf("fixture"), "0".repeat(64), 0),
        )
        assertEquals("results/$requestId.json", receipt.relativePath)
    }

    @Test
    fun productionReaderAndDecoderApplyAllExifOrientationsIncludingMirrors() {
        val expected = mapOf(
            1 to intArrayOf(0, 1, 2, 3, 4, 5),
            2 to intArrayOf(1, 0, 3, 2, 5, 4),
            3 to intArrayOf(5, 4, 3, 2, 1, 0),
            4 to intArrayOf(4, 5, 2, 3, 0, 1),
            5 to intArrayOf(0, 2, 4, 1, 3, 5),
            6 to intArrayOf(4, 2, 0, 5, 3, 1),
            7 to intArrayOf(5, 3, 1, 4, 2, 0),
            8 to intArrayOf(1, 3, 5, 0, 2, 4),
        )
        expected.forEach { (orientation, order) ->
            val matrix = exifOrientationMatrix(orientation)
            val bounds = RectF(0f, 0f, 2f, 3f)
            matrix.mapRect(bounds)
            val width = if (orientation in 5..8) 3 else 2
            val height = if (orientation in 5..8) 2 else 3
            assertEquals(width.toFloat(), bounds.width(), 0.0001f)
            assertEquals(height.toFloat(), bounds.height(), 0.0001f)
            val points = FloatArray(12) { index ->
                val pixel = index / 2
                if (index % 2 == 0) pixel % 2 + 0.5f else pixel / 2 + 0.5f
            }
            matrix.mapPoints(points)
            // Bitmap.createBitmap translates the mapped bounds to the origin.
            // Verify all six source pixel centres, including each mirror, without
            // relying on ShadowLegacyBitmap's absent BufferedImage backing.
            order.forEachIndexed { destination, source ->
                assertEquals("orientation $orientation x/$source",
                    destination % width + 0.5f, points[source * 2] - bounds.left, 0.0001f)
                assertEquals("orientation $orientation y/$source",
                    destination / width + 0.5f, points[source * 2 + 1] - bounds.top, 0.0001f)
            }
        }

        val context = RuntimeEnvironment.getApplication()
        (1..8).forEach { orientation ->
            val file = temporary.newFile("orientation-$orientation.jpg")
            Bitmap.createBitmap(2, 3, Bitmap.Config.ARGB_8888).let { bitmap ->
                file.outputStream().use { output ->
                    assertTrue(bitmap.compress(Bitmap.CompressFormat.JPEG, 95, output))
                }
                bitmap.recycle()
            }
            ExifInterface(file.absolutePath).apply {
                setAttribute(ExifInterface.TAG_ORIENTATION, orientation.toString())
                saveAttributes()
            }
            val image = AndroidCalibrationImageReader(context.contentResolver)
                .read(Uri.fromFile(file).toString())
            assertEquals(orientation, image.exifOrientation)
            AndroidCalibrationImageDecoder.decode(image).use { decoded ->
                assertEquals(2, decoded.rawWidth)
                assertEquals(3, decoded.rawHeight)
                assertEquals(if (orientation in 5..8) 3 else 2, decoded.width)
                assertEquals(if (orientation in 5..8) 2 else 3, decoded.height)
            }
        }
        for (orientation in listOf(0, 9)) {
            val file = temporary.newFile("invalid-orientation-$orientation.jpg")
            val bitmap = Bitmap.createBitmap(2, 3, Bitmap.Config.ARGB_8888)
            file.outputStream().use { assertTrue(bitmap.compress(Bitmap.CompressFormat.JPEG, 95, it)) }
            bitmap.recycle()
            ExifInterface(file.absolutePath).apply {
                setAttribute(ExifInterface.TAG_ORIENTATION, orientation.toString())
                saveAttributes()
            }
            assertEquals(orientation, ExifInterface(file.absolutePath)
                .getAttributeInt(ExifInterface.TAG_ORIENTATION, -1))
            assertThrows(IllegalArgumentException::class.java) {
                AndroidCalibrationImageReader(context.contentResolver).read(Uri.fromFile(file).toString())
            }
        }
    }

    @Test
    fun corruptImageDecodeFailsClosed() {
        val corrupt = byteArrayOf(
            0x89.toByte(), 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
        )
        val error = assertThrows(IllegalArgumentException::class.java) {
            AndroidCalibrationImageDecoder.decode(
                CalibrationImageBytes(
                    corrupt,
                    CalibrationContract.sha256(corrupt),
                    "image/png",
                    corrupt.size.toLong(),
                    1,
                )
            )
        }
        assertEquals("Android image decode failed", error.message)
        assertTrue("Robolectric decode RuntimeException cause must be retained",
            error.cause is RuntimeException)
    }
}
