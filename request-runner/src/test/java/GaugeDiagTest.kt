package com.example.d1check.requestrunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File
import java.util.concurrent.atomic.AtomicInteger

/**
 * M6 게이지 진단 (등록 v3 §2-1) — GaugeDiag 를 가짜 읽기 · 가짜 부하로 짧게 (스모크 ID · 각 구간 300 ms):
 * 폴링 (목표 20 ms · 한 스레드 · 필드 순서 · 읽기 전/후/필드별 시각) · 구간 표식 (setup → idle → load → rest) · 출력 꼴
 * (config · header · samples.jsonl · markers.jsonl · inferences.jsonl · summary) · sysfs 읽기 시험 · 멈춤 규칙 · 설정 검증.
 * 산출물 build/m6-gauge/<case>/ 는 s26/tools/mixreq/test_m6.py 가 m6_gauge_check 로 다시 읽는다.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class GaugeDiagTest {
    private val root = File(File(".").absoluteFile, "build/m6-gauge")
    private val sha = "a".repeat(64)

    private class FakeSource(private val pluggedAfterPolls: Int = Int.MAX_VALUE, private val sysfsReadable: Boolean = true) : GaugeSource {
        val polls = AtomicInteger(0)
        override fun currentNow(): Int = -400_000 - polls.incrementAndGet()
        override fun currentAverage(): Int = -380_000
        override fun chargeCounter(): Int = 3_000_000 - (polls.get() / 30) * 4_275
        override fun energyCounter(): Long = Long.MIN_VALUE
        override fun sticky(): Map<String, Any?> = linkedMapOf("voltage_mV" to 4_012, "plugged" to if (polls.get() > pluggedAfterPolls) 2 else 0,
            "battery_temperature_deci_c" to 301, "battery_level" to 77)
        override fun status(): Map<String, Any?> = linkedMapOf("thermal_status" to 0, "interactive" to true)
        override fun sysfs(path: String): String = if (sysfsReadable && path.endsWith("current_now")) "-401234" else throw SecurityException("EACCES $path")
    }

    private class FakeLoad(private val ms: Long) : GaugeDiag.Load {
        val runs = AtomicInteger(0)
        override val initRecord: Map<String, Any?> = mapOf("engine" to "fake")
        override fun runOne(): Map<String, Any?> { runs.incrementAndGet(); Thread.sleep(ms); return mapOf("inference_ns" to ms * 1_000_000L) }
        override fun close() {}
    }

    private fun config(runId: String, experimentId: String = MixreqContract.M6_E_SMOKE_EXPERIMENT_ID, idle: Long = 300, load: Long = 300, rest: Long = 300) =
        GaugeConfig(experimentId, runId, idle, load, rest, 20, SessionManifest.FileSpec("/x/efficientnet_lite0.tflite", sha),
            SessionManifest.FileSpec("/x/i.png", sha), SessionManifest.FileSpec("/x/c.txt", sha))

    private fun lines(f: File) = f.readLines().filter { it.isNotBlank() }.map { TestJson.parse(it) as Map<*, *> }

    @Test fun pollsMarksAndWritesTheRegisteredForm() {
        val dir = File(root, "ok").apply { deleteRecursively(); parentFile!!.mkdirs() }
        val source = FakeSource()
        val load = FakeLoad(15)
        val cfg = config("ok")
        val diag = GaugeDiag(cfg, "{\"run_id\":\"ok\"}".toByteArray(), dir, source, { load }, System::nanoTime, mapOf("pid" to 1))
        assertEquals("completed", diag.run())
        for (name in listOf("config.json", "header.json", "samples.jsonl", "markers.jsonl", "inferences.jsonl", "summary.json")) assertTrue(name, File(dir, name).isFile)
        val markers = lines(File(dir, "markers.jsonl")).map { it["marker"] }
        assertEquals(listOf("setup_start", "warmup", "warmup", "idle_start", "idle_end", "load_start", "load_end", "rest_start", "rest_end"), markers)
        val samples = lines(File(dir, "samples.jsonl"))
        assertTrue("polls ${samples.size}", samples.size >= 20)
        assertEquals(setOf("idle", "load", "rest"), samples.map { it["phase"] }.toSet() - "setup")
        samples.forEach { s ->
            val t0 = (s["t0"] as Number).toLong(); val t1 = (s["t1"] as Number).toLong()
            assertTrue(t0 <= (s["t_current_now"] as Number).toLong() && (s["t_current_now"] as Number).toLong() <= (s["t_current_avg"] as Number).toLong())
            assertTrue((s["t_charge_counter"] as Number).toLong() <= (s["t_energy_counter"] as Number).toLong() && (s["t_sticky"] as Number).toLong() <= t1)
            assertNotNull(s["current_now"]); assertNotNull(s["current_avg"]); assertNotNull(s["charge_counter"]); assertNotNull(s["sticky"])
            assertEquals(Long.MIN_VALUE, (s["energy_counter"] as Number).toLong())
            assertEquals("-401234", s["sysfs_current_now"])   // readable sysfs only
            assertTrue(!s.containsKey("sysfs_voltage_now"))
        }
        // status every 50 polls (seq 0, 50, ...)
        assertTrue(samples.filter { (it["seq"] as Number).toLong() % 50 == 0L }.all { it.containsKey("status") })
        assertTrue(samples.filter { (it["seq"] as Number).toLong() % 50 != 0L }.none { it.containsKey("status") })
        val seqs = samples.map { (it["seq"] as Number).toLong() }
        assertEquals((0L until samples.size).toList(), seqs)
        val t0s = samples.map { (it["t0"] as Number).toLong() }
        val gaps = t0s.zipWithNext { a, b -> b - a }.sorted()
        val median = gaps[gaps.size / 2]
        assertTrue("median poll gap $median", median in 15_000_000L..40_000_000L)   // target 20 ms (Windows sleep granularity)
        // inferences only inside load, back to back
        val inf = lines(File(dir, "inferences.jsonl"))
        val marks = lines(File(dir, "markers.jsonl")).associateBy { it["marker"] }
        val loadStart = (marks.getValue("load_start")["t_ns"] as Number).toLong(); val loadEnd = (marks.getValue("load_end")["t_ns"] as Number).toLong()
        assertTrue(inf.isNotEmpty())
        assertTrue(inf.all { (it["start_ns"] as Number).toLong() >= loadStart && (it["end_ns"] as Number).toLong() <= loadEnd })
        assertEquals(inf.size.toLong() + GaugeDiag.WARMUPS, load.runs.get().toLong())
        val header = TestJson.parse(File(dir, "header.json").readText()) as Map<*, *>
        assertEquals(GaugeDiag.SCHEMA, header["schema"])
        assertEquals(listOf("/sys/class/power_supply/battery/current_now"), header["sysfs_polled"])
        val probe = header["sysfs_probe"] as Map<*, *>
        assertEquals(false, (probe["/sys/class/power_supply/battery/voltage_now"] as Map<*, *>)["readable"])
        val summary = TestJson.parse(File(dir, "summary.json").readText()) as Map<*, *>
        assertEquals("completed", summary["status"])
        assertEquals(samples.size.toLong(), (summary["polls"] as Number).toLong())
        assertNotNull((summary["poll_interval_ns"] as Map<*, *>)["median"])
    }

    @Test fun stopsOnPluggedAndRefusesAnExistingFolder() {
        val dir = File(root, "plugged").apply { deleteRecursively(); parentFile!!.mkdirs() }
        val diag = GaugeDiag(config("plugged"), "{}".toByteArray(), dir, FakeSource(pluggedAfterPolls = 5, sysfsReadable = false), { FakeLoad(5) }, System::nanoTime)
        val result = diag.run()
        assertTrue(result, result.startsWith("stopped: environment/plugged_2"))
        val summary = TestJson.parse(File(dir, "summary.json").readText()) as Map<*, *>
        assertEquals(emptyList<Any>(), summary["sysfs_polled"])
        assertThrows(IllegalStateException::class.java) {
            GaugeDiag(config("plugged"), "{}".toByteArray(), dir, FakeSource(), { FakeLoad(5) }, System::nanoTime).run()
        }
    }

    @Test fun configValidation() {
        GaugeConfig(MixreqContract.M6_E_EXPERIMENT_ID, "E1", 60_000, 120_000, 120_000, 20, SessionManifest.FileSpec("/x/efficientnet_lite0.tflite", sha),
            SessionManifest.FileSpec("/x/i.png", sha), SessionManifest.FileSpec("/x/c.txt", sha)).validate()
        assertThrows(IllegalArgumentException::class.java) { config("E1", MixreqContract.M6_E_EXPERIMENT_ID).validate() }   // not the registered segments
        config("smoke").validate()
        assertThrows(IllegalArgumentException::class.java) { config("smoke", idle = 60_001).validate() }
        assertThrows(IllegalStateException::class.java) { config("x", "S26-M6-P").validate() }
        val parsed = GaugeConfig.parse("""{"experiment_id":"S26-M6-E","run_id":"E2","idle_ms":60000,"load_ms":120000,"rest_ms":120000,"poll_target_ms":20,
            "model":{"path":"/d/efficientnet_lite0.tflite","sha256":"$sha"},"image":{"path":"/d/i.png","sha256":"$sha"},"labels":{"path":"/d/l.txt","sha256":"$sha"}}""")
        parsed.validate()
        assertEquals("E2", parsed.runId)
        assertThrows(IllegalArgumentException::class.java) {
            GaugeConfig(MixreqContract.M6_E_SMOKE_EXPERIMENT_ID, "n", 300, 300, 300, 20, SessionManifest.FileSpec("/x/efficientnet_lite0_Samsung_E9965.tflite", sha),
                SessionManifest.FileSpec("/x/i.png", sha), SessionManifest.FileSpec("/x/c.txt", sha)).validate()
        }
    }
}
