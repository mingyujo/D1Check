package com.example.d1check.requestrunner

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File

/**
 * K3: A24 ProbeImageContractTest 이식 + 실제 자료 — local_inputs/reference_pc/rgb.bin (조민규 PNG 를 Pillow 로 디코드한 RGB,
 * SHA ca6c2e2b…) → Kotlin resize · 정규화 → 분류 텐서 SHA 603328d0… (A24 CPU 기준 입력) · 탐지 텐서 SHA e1ce665b… (1-2 PC 참조).
 * 실제 자료는 git 밖이라 없으면 그 시험만 건너뛴다 (Assume).
 */
class ImageContractTest {
    private fun png(extra: Boolean = false, colorType: Int = 2, depth: Int = 8): ByteArray {
        val stream = java.io.ByteArrayOutputStream()
        val out = java.io.DataOutputStream(stream)
        out.write(byteArrayOf(-119, 80, 78, 71, 13, 10, 26, 10))
        fun chunk(name: String, bytes: ByteArray) { out.writeInt(bytes.size); out.writeBytes(name); out.write(bytes); out.writeInt(0) }
        val header = java.nio.ByteBuffer.allocate(13).putInt(1).putInt(1).put(depth.toByte()).put(colorType.toByte()).put(0).put(0).put(0).array()
        chunk("IHDR", header)
        if (extra) chunk("iCCP", byteArrayOf(1))
        chunk("IDAT", byteArrayOf(1)); chunk("IEND", byteArrayOf())
        return stream.toByteArray()
    }

    @Test fun canonicalChunkContractRejectsColorMetadataTruncationAndNonRgb8() {
        ImageContract.requireCanonicalPng(png())
        for (bytes in listOf(png(true), png().dropLast(1).toByteArray(), png(colorType = 6), png(depth = 16))) {
            assertThrows(RuntimeException::class.java) { ImageContract.requireCanonicalPng(bytes) }
        }
        // orientation / gamma / text chunks are rejected too (canonical-srgb-png-v2: IHDR/IDAT/IEND only)
        for (kind in listOf("eXIf", "gAMA", "tEXt", "pHYs", "sRGB")) {
            val stream = java.io.ByteArrayOutputStream(); val out = java.io.DataOutputStream(stream)
            out.write(byteArrayOf(-119, 80, 78, 71, 13, 10, 26, 10))
            fun chunk(name: String, bytes: ByteArray) { out.writeInt(bytes.size); out.writeBytes(name); out.write(bytes); out.writeInt(0) }
            chunk("IHDR", java.nio.ByteBuffer.allocate(13).putInt(1).putInt(1).put(8).put(2).put(0).put(0).put(0).array())
            chunk(kind, byteArrayOf(1)); chunk("IDAT", byteArrayOf(1)); chunk("IEND", byteArrayOf())
            assertThrows(kind, RuntimeException::class.java) { ImageContract.requireCanonicalPng(stream.toByteArray()) }
        }
    }

    @Test fun identityAndClampedSinglePixel() {
        val input = ByteArray(12) { it.toByte() }
        assertArrayEquals(input, ImageContract.resize(input, 2, 2, 2))
        assertArrayEquals(ByteArray(27) { byteArrayOf(1, -128, -1)[it % 3] }, ImageContract.resize(byteArrayOf(1, -128, -1), 1, 1, 3))
    }

    @Test fun sharedHalfPixelFixtureAndNormalization() {
        val fixture = byteArrayOf(0, 0, 0, -1, -1, -1)
        val expectedRow = byteArrayOf(0, 0, 0, -128, -128, -128, -1, -1, -1)
        assertArrayEquals(ByteArray(27) { expectedRow[it % 9] }, ImageContract.resize(fixture, 2, 1, 3))
        val det = ImageContract.detectionTensor(byteArrayOf(0, -1))
        assertEquals(-1f, det[0], 0f)
        assertEquals(1f, det[1], 0f)
        val cls = ImageContract.classificationTensor(byteArrayOf(127, -1, 0))
        assertEquals(0f, cls[0], 0f)
        assertEquals(1f, cls[1], 0f)
        assertEquals(-127f / 128f, cls[2], 0f)
    }

    @Test fun malformedGeometryRejected() {
        assertThrows(IllegalArgumentException::class.java) { ImageContract.resize(byteArrayOf(0), 1, 1) }
        assertThrows(IllegalArgumentException::class.java) { DecodedImage(2, 2, ByteArray(3)) }
    }

    @Test fun realImageReproducesTheA24ClassificationAndDetectionInputTensors() {
        val rgb = File("../local_inputs/reference_pc/rgb.bin")
        assumeTrue("local_inputs/reference_pc/rgb.bin missing (git 밖)", rgb.isFile)
        val bytes = rgb.readBytes()
        assertEquals(1024 * 683 * 3, bytes.size)
        assertEquals("ca6c2e2bf77bfd8c9240404f516a17eb21c24ba34159ce2e3722bf8aaf225455", ImageContract.sha256(bytes))
        val cls = ImageContract.tensorFor("classification", bytes, 1024, 683)
        assertEquals(224 * 224 * 3, cls.size)
        assertEquals("603328d02dfc2b1aa356b26b0f14b9e70f8cdb80609c89fd171bcf4c3ff85462", ImageContract.sha256(cls))
        val det = ImageContract.tensorFor("detection", bytes, 1024, 683)
        assertEquals(320 * 320 * 3, det.size)
        assertEquals("e1ce665bedf565285adccc4098433e338b9cdb08d681e0c0d424cae521e273ad", ImageContract.sha256(det))
        // the PNG itself passes the canonical contract and has the registered SHA
        val png = File("../local_inputs/canonical_v123/00575b9132bb3746.png")
        assumeTrue(png.isFile)
        val pngBytes = png.readBytes()
        ImageContract.requireCanonicalPng(pngBytes)
        assertEquals("3e8b925feafbfe5fdd4efb9d7911f445a3212100fa73744f6fd855cf6160f1ab", ImageContract.sha256(pngBytes))
    }
}
