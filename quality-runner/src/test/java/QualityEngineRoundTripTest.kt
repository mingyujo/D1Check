package com.example.d1check.qualityrunner

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** Q3: 가짜 runtime 으로 한 번 왕복 — 산출물 수 · raw 파일 = 출력 바이트 · SHA 일치 · 실패 보존 · 계속 진행 · runtime 생성 실패 summary. */
class QualityEngineRoundTripTest {
    private var clock = 0L
    private val marks = ArrayList<String>()

    @Suppress("UNCHECKED_CAST")
    private fun json(f: File) = MiniJson.parse(f.readText()) as Map<String, Any?>

    private fun engine(built: TestFixtures.Built, backend: String, out: File, factory: (RuntimeSpec) -> InferenceRuntime) = QualityEngine(
        manifest = QualityManifest.parse(built.manifestText).also { it.validate() },
        manifestBytes = built.manifestFile.readBytes(),
        backend = backend, runId = "jvm_test", outRoot = out,
        runtimeFactory = factory, now = { clock += 1_000; clock }, wallClock = { "2026-10-09T00:00:00.000+09:00" },
        identity = mapOf("pid" to 1), log = { marks += it },
    )

    @Test fun fullRoundTripWritesEveryArtifact() {
        val built = TestFixtures.build()
        val out = File(built.root, "out/jvm_test/CPU")
        var fake: FakeRuntime? = null
        assertTrue(engine(built, "CPU", out) { spec -> FakeRuntime(spec).also { fake = it } }.run())
        assertTrue(fake!!.closed)
        assertEquals(40, fake!!.runs)
        val results = out.listFiles { f -> f.name.endsWith(".result.json") }!!.sortedBy { it.name }
        val raws = out.listFiles { f -> f.name.endsWith(".f32le") }!!
        assertEquals(20, results.size)
        assertEquals(40, raws.size)
        assertTrue(out.listFiles { f -> f.name.endsWith(".part") }!!.isEmpty())
        assertTrue(out.listFiles { f -> f.name.endsWith(".failure.json") }!!.isEmpty())
        val summary = json(File(out, "summary.json"))
        assertEquals("completed", summary["status"])
        assertEquals(20L, summary["images_ok"])
        assertEquals(true, summary["model_sha_ok"])
        assertEquals("classification_CPU", summary["runtime_key"])
        assertEquals(FileSha256.sha256(built.manifestFile.readBytes()), summary["manifest_sha256"])
        assertEquals(FileSha256.sha256(built.manifestFile.readBytes()), FileSha256.sha256(File(out, "manifest.json")))
        // raw 파일 바이트 = 가짜 runtime 이 돌려준 출력 그대로 · SHA 일치 · 2회 비트 동일
        val r0 = json(results[0])
        assertEquals(built.samples[0].sampleId, r0["sample_id"])
        assertEquals(true, r0["bit_identical_runs"])
        val runs = r0["runs"] as List<Map<String, Any?>>
        assertEquals(2, runs.size)
        val raw0 = File(out, runs[0]["output_file"] as String).readBytes()
        assertEquals(4000, raw0.size)
        assertEquals(runs[0]["output_sha256"], FileSha256.sha256(raw0))
        assertEquals(1000L, runs[0]["output_elements"])
        assertEquals(true, runs[0]["all_finite"])
        val expected = FakeRuntime(QualityManifest.parse(built.manifestText).runtimeFor("CPU")).run(F32le.toFloats(TestFixtures.inputBytes(0), QualityContract.INPUT_ELEMENTS))[0]
        assertArrayEquals(expected, F32le.toFloats(raw0, 1000), 0f)
        // 표시 순서: create_start → create_end → image_start 0 … image_end 19
        assertTrue(marks[0].startsWith("runtime create_start key=classification_CPU"))
        assertTrue(marks[1].startsWith("runtime create_end key=classification_CPU ok=true"))
        assertEquals(20, marks.count { it.startsWith("image_start idx=") })
        assertEquals(20, marks.count { it.startsWith("image_end idx=") && it.endsWith("ok=true") })
    }

    @Test fun shaMismatchAndRunFailureArePreservedAndTheRestContinues() {
        val built = TestFixtures.build(corruptSha = setOf(2))
        val out = File(built.root, "out/jvm_test/GPU")
        assertTrue(engine(built, "GPU", out) { spec -> FakeRuntime(spec, failRunAt = 11) }.run())   // run #11 = image 5 (sha 실패한 2 는 run 안 함) 의 2회째
        val failures = out.listFiles { f -> f.name.endsWith(".failure.json") }!!.sortedBy { it.name }
        assertEquals(2, failures.size)
        assertTrue(failures[0].name.startsWith("02_"))
        assertTrue(json(failures[0])["error"].toString().contains("input sha256 mismatch"))
        assertTrue(json(failures[1])["error"].toString().contains("fake run failure"))
        assertEquals(18, out.listFiles { f -> f.name.endsWith(".result.json") }!!.size)
        val summary = json(File(out, "summary.json"))
        assertEquals("completed_with_failures", summary["status"])
        assertEquals(18L, summary["images_ok"])
        assertEquals(2, (summary["failures"] as List<*>).size)
        assertTrue(marks.any { it.startsWith("image_end idx=2 ok=false") })
        assertTrue(marks.any { it.startsWith("image_end idx=19 ok=true") })
    }

    @Test fun nonFiniteAndDriftAreRecordedNotJudged() {
        val built = TestFixtures.build()
        val out = File(built.root, "out/jvm_test/NPU")
        assertTrue(engine(built, "NPU", out) { spec -> FakeRuntime(spec, nanAt = 7, driftSecondRun = true) }.run())
        val r = json(out.listFiles { f -> f.name.endsWith(".result.json") }!!.first())
        val runs = r["runs"] as List<Map<String, Any?>>
        assertEquals(false, runs[0]["all_finite"])
        assertEquals(false, r["bit_identical_runs"])
        assertEquals("completed", json(File(out, "summary.json"))["status"])   // 지표 · 판정은 호스트 판정기만
    }

    @Test fun runtimeCreateFailureLeavesSummaryAndNoResults() {
        val built = TestFixtures.build()
        val out = File(built.root, "out/jvm_test/NPU2")
        assertFalse(engine(built, "NPU", out) { spec -> FakeRuntime(spec, failOnCreate = true) }.run())
        val summary = json(File(out, "summary.json"))
        assertEquals("runtime_create_failed", summary["status"])
        assertTrue(summary["runtime_create_error"].toString().contains("creation failure"))
        assertEquals(0L, summary["images_ok"])
        assertTrue(out.listFiles { f -> f.name.endsWith(".result.json") }!!.isEmpty())
        assertTrue(marks.any { it.startsWith("runtime create_end key=classification_NPU ok=false") })
    }

    @Test fun modelShaMismatchDoesNotCreateRuntime() {
        val built = TestFixtures.build { m ->
            @Suppress("UNCHECKED_CAST")
            val runtimes = m["runtimes"] as Map<String, Any?>
            // CPU · GPU 는 같은 원본을 열어야 하므로 둘 다 틀린 SHA 로 (manifest 는 통과 · 파일 SHA 대조에서 걸린다)
            for (b in listOf("CPU", "GPU")) (runtimes[b] as MutableMap<String, Any?>)["model_sha256"] = "a".repeat(64)
        }
        val out = File(built.root, "out/jvm_test/CPU2")
        var created = false
        assertFalse(engine(built, "CPU", out) { spec -> created = true; FakeRuntime(spec) }.run())
        assertFalse(created)
        assertEquals("model_sha_mismatch", json(File(out, "summary.json"))["status"])
    }

    @Test fun refusesExistingOutDir() {
        val built = TestFixtures.build()
        val out = File(built.root, "out/jvm_test/CPU3").apply { mkdirs() }
        val thrown = runCatching { engine(built, "CPU", out) { spec -> FakeRuntime(spec) }.run() }.exceptionOrNull()
        assertTrue(thrown is IllegalStateException)
    }
}
