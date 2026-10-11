package com.example.d1check.qualityrunner

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files

/** Q1: f32le 읽기 (LE · 크기 · SHA) · 결과 JSON 쓰기 (원자 저장 · 삽입 순서 · 비유한 거부). */
class F32leStoreTest {
    @Test fun littleEndianRoundTripAndSizeCheck() {
        // 1.0f = 00 00 80 3F (LE) ; -2.5f = 00 00 20 C0
        val bytes = byteArrayOf(0, 0, 0x80.toByte(), 0x3F, 0, 0, 0x20, 0xC0.toByte())
        val floats = F32le.toFloats(bytes, 2)
        assertEquals(1.0f, floats[0], 0f)
        assertEquals(-2.5f, floats[1], 0f)
        assertArrayEquals(bytes, F32le.toBytes(floats))
        assertThrows(IllegalArgumentException::class.java) { F32le.toFloats(bytes, 3) }
        assertThrows(IllegalArgumentException::class.java) { F32le.toFloats(ByteArray(602_111), QualityContract.INPUT_ELEMENTS) }
        val full = TestFixtures.inputBytes(0)
        assertEquals(602_112, full.size)
        assertArrayEquals(full, F32le.toBytes(F32le.toFloats(full, QualityContract.INPUT_ELEMENTS)))
    }

    @Test fun sha256MatchesKnownVector() {
        // SHA-256("abc") — FIPS 180-2 example
        assertEquals("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", FileSha256.sha256("abc".toByteArray()))
        val f = Files.createTempFile("d1q20", ".bin").toFile().apply { writeBytes("abc".toByteArray()) }
        assertEquals("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", FileSha256.sha256(f))
        assertEquals("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", FileSha256.sha256(ByteArray(0)))
    }

    @Test fun storeIsAtomicKeepsOrderAndRejectsNonFinite() {
        val root = Files.createTempDirectory("d1q20-store").toFile()
        val store = ArtifactStore(root)
        store.save("x.json", linkedMapOf("b" to 1, "a" to listOf(1.5, "s", null, true), "f" to floatArrayOf(0.5f)))
        assertEquals("""{"b":1,"a":[1.5,"s",null,true],"f":[0.5]}""", File(root, "x.json").readText())
        assertFalse(File(root, "x.json.part").exists())
        assertThrows(IllegalStateException::class.java) { store.save("x.json", mapOf("k" to 2)) }
        assertThrows(IllegalArgumentException::class.java) { store.save("y.json", mapOf("k" to Double.NaN)) }
        assertFalse(File(root, "y.json").exists())
        assertFalse(File(root, "y.json.part").exists())
        store.saveBytes("z.f32le", F32le.toBytes(floatArrayOf(Float.NaN)))   // raw 파일은 비유한도 그대로 보존 (판정기가 본다)
        assertTrue(File(root, "z.f32le").length() == 4L)
        val parsed = MiniJson.parse(File(root, "x.json").readText()) as Map<*, *>
        assertEquals(listOf("b", "a", "f"), parsed.keys.toList())
    }
}
