package com.example.d1check.requestrunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files

/** K5: JSON 직렬화 · 원자 저장 (.part → rename, 덮어쓰기 거부, 실패 시 산출물 없음) · 두 스레드 20,000 줄 동시 기록에 줄 깨짐 0. */
class EventLogTest {
    @Test fun jsonKeepsInsertionOrderAndRejectsNonFinite() {
        val text = Json.encode(linkedMapOf("b" to 1, "a" to listOf(1.5, "x\"y", null, true), "c" to floatArrayOf(0.5f), "d" to mapOf("z" to 2L)))
        assertEquals("""{"b":1,"a":[1.5,"x\"y",null,true],"c":[0.5],"d":{"z":2}}""", text)
        assertThrows(IllegalArgumentException::class.java) { Json.encode(mapOf("x" to Double.NaN)) }
        assertThrows(IllegalArgumentException::class.java) { Json.encode(listOf(Float.POSITIVE_INFINITY)) }
        assertEquals("\"\\n\\t\\u0001\"", Json.encode("\n\t\u0001"))
        // Float widens to the exact double (Python json.dumps(float(np.float32(x))) gives the same digits)
        assertEquals("[0.6962097883224487]", Json.encode(floatArrayOf(0.6962098f)))
        val parsed = TestJson.parse(text) as Map<*, *>
        assertEquals(listOf("b", "a", "c", "d"), parsed.keys.toList())
    }

    @Test fun saveIsAtomicRefusesOverwriteAndLeavesNothingOnEncodeFailure() {
        val root = Files.createTempDirectory("d1mix-store").toFile()
        val store = ArtifactStore(root)
        store.save("x.json", mapOf("k" to 1))
        assertEquals("""{"k":1}""", File(root, "x.json").readText())
        assertFalse(File(root, "x.json.part").exists())
        assertThrows(IllegalStateException::class.java) { store.save("x.json", mapOf("k" to 2)) }
        assertEquals("""{"k":1}""", File(root, "x.json").readText())
        assertThrows(IllegalArgumentException::class.java) { store.save("y.json", mapOf("k" to Double.NaN)) }
        assertFalse(File(root, "y.json").exists())
        assertFalse(File(root, "y.json.part").exists())
    }

    @Test fun twoWritersTwentyThousandLinesNoTornLines() {
        val file = File(Files.createTempDirectory("d1mix-progress").toFile(), "progress.jsonl")
        ProgressWriter(file, capacity = 65_536).use { writer ->
            val threads = (0 until 2).map { t ->
                Thread {
                    for (i in 0 until 10_000) writer.add(Json.encode(mapOf("t" to t, "i" to i, "pad" to "x".repeat(40))))
                }
            }
            threads.forEach { it.start() }
            threads.forEach { it.join() }
            writer.flush()
        }
        val lines = file.readLines()
        assertEquals(20_000, lines.size)
        val seen = HashSet<String>()
        for (line in lines) {
            val obj = TestJson.parse(line) as Map<*, *>
            assertEquals(3, obj.size)
            assertTrue(seen.add("${obj["t"]}/${obj["i"]}"))
        }
        assertEquals(20_000, seen.size)
    }

    @Test fun progressWriterFailsClosedAfterClose() {
        val file = File(Files.createTempDirectory("d1mix-progress2").toFile(), "progress.jsonl")
        val writer = ProgressWriter(file)
        writer.add("{}")
        writer.close()
        assertThrows(IllegalStateException::class.java) { writer.add("{}") }
        assertEquals(1, file.readLines().size)
    }

    @Test fun labelLinesKeepInteriorEmptyRowsLikePythonSplitlines() {
        assertEquals(listOf("a", "", "c"), TaskRuntime.labelLines("a\n\nc\n"))
        assertEquals(listOf("a", "b"), TaskRuntime.labelLines("a\r\nb"))
        assertEquals(listOf("person", "???"), TaskRuntime.labelLines("person\n???\n"))
    }
}
