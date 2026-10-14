package com.example.d1check.requestrunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File

/**
 * M8 왕복 (폰 없이 · SessionEngineM8 · 가짜 backend · time_scale 10): 계약표 v1 §1 ~ §6 의 동작을 산출물로 확인한다.
 *   M128 BASE (FIFO 직렬 · 같은 시각 8건 ordinal · readback · response 경계 = priority · cooling 90) · PAIR_G (겹침 > 0 · 동시 ≤ 2) · WAIT200x16 (wait 16 · dose · 개입) ·
 *   C252 CPU 느린 서비스 (120 s 경계 뒤 dispatch 0 · undispatched) · RECENT CPU60 (준비 → 5 s → t 35 · common 0 = prep_end − 30 s) · IDLE NO_RUNTIME (runtime 0 · sampler 유지).
 * 산출물 build/m8-roundtrip/<case>/a1 은 s26/tools/mixreq/test_m8.py 가 m8_validate · coverage_check 로 다시 읽는다. 가짜 서비스 시간 = 시험용 숫자 (결과 아님).
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class M8RoundTripTest {
    private val moduleDir = File(".").absoluteFile
    private val root = File(moduleDir, "build/m8-roundtrip")
    private val inputs = File(root, "_inputs")
    private val rgb = byteArrayOf(10, 20, 30, 40, 50, 60)
    private val sha = HashMap<String, String>()
    private val scale = 10

    private class FakeRuntime(override val spec: RuntimeSpec, private val latencyNs: Long, private val variant: Float) : InferenceRuntime {
        override fun inputElementCount() = if (spec.task == "classification") 224 * 224 * 3 else 320 * 320 * 3
        override fun run(input: FloatArray): List<FloatArray> {
            val until = System.nanoTime() + latencyNs
            if (latencyNs > 2_000_000L) Thread.sleep((latencyNs - 1_000_000L) / 1_000_000L)
            while (System.nanoTime() < until) Thread.onSpinWait()
            return if (spec.task == "classification") listOf(SessionRoundTripTest.classification(variant))
            else listOf(SessionRoundTripTest.detectionScores(variant), FloatArray(19_206 * 4))
        }
        override fun initRecord(): Map<String, Any?> = mapOf("engine" to "fake")
        override fun close() {}
    }

    private fun writeInputs() {
        inputs.mkdirs()
        fun put(name: String, bytes: ByteArray) { File(inputs, name).writeBytes(bytes); sha[name] = ImageContract.sha256(bytes) }
        put("image.png", SessionRoundTripTest.canonicalPng(2, 1, rgb))
        put("labels_without_background.txt", ((0 until 1000).joinToString("\n") { "cls$it" } + "\n").toByteArray())
        put("labels.txt", ((0 until 90).joinToString("\n") { "det$it" } + "\n").toByteArray())
        val anchors = StringBuilder("[")
        for (i in 0 until 19_206) { if (i > 0) anchors.append(','); anchors.append("[${(i % 139 + 0.5) / 139},${(i / 139 + 0.5) / 139},0.05,0.05]") }
        put("anchors.json", anchors.append(']').toString().toByteArray())
        put("efficientnet_lite0.tflite", "fake classification model".toByteArray())
        put("efficientdet_lite0.tflite", "fake detection model".toByteArray())
        put("efficientnet_lite0_Samsung_E9965.tflite", "fake NPU AOT artifact".toByteArray())
    }

    private fun manifestBytes(experimentId: String, index: Int, mutate: (MixreqContract.Request) -> MixreqContract.Request = { it }): ByteArray {
        val arm = M8Plan.armOf(experimentId, index)
        val sid = M8Plan.sessionId(experimentId, index)
        val requests = M8Plan.requests(experimentId, index, sid).map(mutate).map { linkedMapOf("request_id" to it.id, "ordinal" to it.ordinal, "task_id" to it.task,
            "priority" to it.priority, "offset_ms" to it.offsetMs, "deadline_ms" to it.deadlineMs, "offset_us" to it.offsetUs, "offset_ns" to it.offsetNs) }
        fun spec(key: String): Map<String, Any?> {
            val task = MixreqContract.taskOf(key); val lane = MixreqContract.laneOf(key)
            val model = when { lane == "NPU" -> "efficientnet_lite0_Samsung_E9965.tflite"; task == "classification" -> "efficientnet_lite0.tflite"; else -> "efficientdet_lite0.tflite" }
            return linkedMapOf("key" to key, "task" to task, "backend" to lane, "model_path" to File(inputs, model).path, "model_sha256" to sha.getValue(model),
                "gpu_precision" to (if (lane == "GPU") "FP32" else null), "cpu_threads" to (if (lane == "CPU") 1 else null))
        }
        val m = linkedMapOf<String, Any?>(
            "protocol" to MixreqContract.PROTOCOL, "experiment_id" to experimentId, "split" to MixreqContract.SPLIT_DIAGNOSTIC, "contract" to "M8",
            "session_id" to sid, "session_index" to index, "block" to arm.block, "pair" to 0, "attempt" to 1, "policy" to arm.policy,
            "policy_args" to arm.wait?.record(), "prep" to linkedMapOf("kind" to arm.prep.name, "prep_s" to 60, "gap_s" to 5),
            "runtimes" to MixreqContract.keysOf(arm.block).sorted().map(::spec),
            "image" to linkedMapOf("path" to File(inputs, "image.png").path, "sha256" to sha.getValue("image.png"), "width" to 2, "height" to 1),
            "anchors" to linkedMapOf("path" to File(inputs, "anchors.json").path, "sha256" to sha.getValue("anchors.json")),
            "labels" to linkedMapOf("classification" to linkedMapOf("path" to File(inputs, "labels_without_background.txt").path, "sha256" to sha.getValue("labels_without_background.txt")),
                "detection" to linkedMapOf("path" to File(inputs, "labels.txt").path, "sha256" to sha.getValue("labels.txt"))),
            "requests" to requests,
            "phases" to linkedMapOf("setup_s" to 180, "gate_s" to 60, "baseline_s" to 60, "common_s" to 120, "drain_s" to 30, "cooling_s" to 90),
            "sample_period_ms" to 900, "time_scale" to scale, "warmup_gate" to true,
            "stop_rules" to linkedMapOf("battery_deci_c_max" to 420, "thermal_status_max" to 2, "soc_min" to 20),
            "start_check" to linkedMapOf("thermal_status_max" to 1),
        )
        return Json.encode(m).toByteArray()
    }

    private fun run(case: String, experimentId: String, index: Int, clsMs: Long = 60, detMs: Long = 240, expectCompleted: Boolean = true,
                    mutate: (MixreqContract.Request) -> MixreqContract.Request = { it }, validate: Boolean = true): Pair<File, SessionEngineM8> {
        writeInputs()
        val caseDir = File(root, case).apply { deleteRecursively(); mkdirs() }
        val bytes = manifestBytes(experimentId, index, mutate)
        val manifest = SessionManifest.parse(String(bytes)).also { if (validate) it.validate() }
        val sessionInputs = File(caseDir, "inputs").apply { mkdirs() }
        File(sessionInputs, "manifest.json").writeBytes(bytes)
        val out = File(caseDir, "a1")
        val snapshot = { linkedMapOf<String, Any?>("current_raw" to -523_000, "current_valid" to true, "voltage_mV" to 4_012, "charge_counter_raw" to 3_000_000,
            "charge_valid" to true, "plugged" to 0, "battery_temperature_deci_c" to 301, "battery_level" to 77, "battery_scale" to 100, "thermal_status" to 0,
            "interactive" to true, "snapshot_start_ns" to System.nanoTime(), "sensor_read_end_ns" to System.nanoTime()) }
        val engine = SessionEngineM8(manifest, bytes, sessionInputs, out,
            runtimeFactory = { spec -> FakeRuntime(spec, (if (spec.task == "classification") clsMs else detMs) * 1_000_000L / scale, when (spec.backend) { Backend.CPU -> 0f; Backend.GPU -> 1e-5f; Backend.NPU -> 5e-4f }) },
            decodeImage = { DecodedImage(2, 1, rgb) }, snapshot = snapshot, now = System::nanoTime, identity = mapOf("pid" to 4242), log = { })
        val hash = ImageContract.sha256(bytes)
        val host = Thread {
            val ready = File(out, "warmup.ready.json"); val deadline = System.nanoTime() + 120_000_000_000L
            while (!ready.exists() && System.nanoTime() < deadline && engine.phase != "cleanup") Thread.sleep(20)
            if (ready.exists()) File(sessionInputs, "warmup.arm").writeText(hash)
        }.apply { isDaemon = true; start() }
        val completed = engine.run()
        host.join(1000)
        assertEquals("$case completed=$completed stop=${engine.stop.get()}", expectCompleted, completed)
        File(caseDir, "roundtrip.json").writeText(Json.encode(mapOf("case" to case, "experiment_id" to experimentId, "session_index" to index, "time_scale" to scale,
            "cls_ms" to clsMs, "det_ms" to detMs, "expect_completed" to expectCompleted, "stop_reason" to engine.stop.get(), "manifest_sha256" to hash, "contract" to "M8")))
        return out to engine
    }

    private fun rows(out: File): List<Map<*, *>> = (TestJson.parse(File(out, "requests.json").readText()) as List<*>).map { it as Map<*, *> }
    private fun summary(out: File): Map<*, *> = TestJson.parse(File(out, "summary.json").readText()) as Map<*, *>
    private fun ns(row: Map<*, *>, key: String) = (row[key] as Number).toLong()
    private fun events(out: File, kind: String): List<Map<*, *>> = File(out, "progress.jsonl").readLines().filter { it.contains("\"kind\":\"$kind\"") }.map { TestJson.parse(it) as Map<*, *> }

    private fun busy(rows: List<Map<*, *>>) = rows.filter { it["dispatch_ns"] != null && it["lane_available_ns"] != null }.map { Triple(it["selected_backend"] as String, ns(it, "dispatch_ns"), ns(it, "lane_available_ns")) }
    private fun maxConcurrent(rows: List<Map<*, *>>): Int {
        val b = busy(rows)
        return b.maxOf { (_, s, _) -> b.count { (_, s2, e2) -> s2 <= s && s < e2 } }
    }

    @Test fun m128BaseFifoSerialWithReadbackAndOrdinalReplay() {
        val (out, _) = run("M128_BASE", "S26-M8-M128-SMOKE", 0)
        val r = rows(out)
        assertEquals(128, r.size); assertTrue(r.all { it["terminal_status"] == "succeeded" })
        assertEquals(1, maxConcurrent(r))                                                                  // SERIAL 전역 1
        // 같은 시각 8건: dispatch 순서 = ordinal 순서 (strict FIFO)
        val dispatchOrder = r.sortedBy { ns(it, "dispatch_ns") }.map { (it["ordinal"] as Number).toInt() }
        assertEquals((0 until 128).toList(), dispatchOrder)
        assertTrue(r.all { ns(it, "scheduled_arrival_ns") <= ns(it, "queue_entry_ns") && ns(it, "queue_entry_ns") <= ns(it, "dispatch_ns") })
        for (row in r) {
            if (row["priority"] == "urgent") {
                assertEquals(ns(row, "output_ready_ns"), ns(row, "response_ns")); assertEquals("output_ready", row["response_boundary"]); assertEquals("urgent", row["readback_skipped"]); assertNull(row["readback_ok"])
            } else {
                assertEquals(true, row["readback_ok"]); assertEquals(ns(row, "readback_end_ns"), ns(row, "response_ns")); assertEquals("readback_complete", row["response_boundary"])
                assertTrue(ns(row, "persist_complete_ns") <= ns(row, "readback_start_ns") && ns(row, "readback_start_ns") <= ns(row, "readback_end_ns") && ns(row, "readback_end_ns") <= ns(row, "worker_release_ns"))
                assertEquals(row["readback_expected_sha256"], row["readback_sha256"])
            }
            assertEquals("classification_GPU".takeIf { row["task_id"] == "classification" } ?: "detection_CPU", "${row["task_id"]}_${row["selected_backend"]}")
            assertEquals((row["ordinal"] as Number).toInt() / 8, (row["burst_index"] as Number).toInt())
        }
        val s = summary(out)
        assertEquals("M8", s["contract"]); assertEquals(0L, ((s["wait"] as Map<*, *>)["count"] as Number).toLong()); assertEquals(false, (s["wait"] as Map<*, *>)["policy_has_wait"])
        assertEquals(32L, ((s["readback"] as Map<*, *>)["ok"] as Number).toLong()); assertEquals(0L, (s["undispatched"] as Number).toLong())
        assertEquals("priority", ((s["response_boundary"] as Map<*, *>)["selected_by"]))
        assertEquals(90L, (events(out, "phase_start").first { it["phase"] == "resident_cooling" }["cooling_s"] as Number).toLong())
        // 계약: 앱 power 마지막 표본 ≥ common 0 + 210 s (time_scale 10 → 21 s) — cooling 뒤 연장 대기
        val origin = ns(TestJson.parse(File(out, "common_boundary.json").readText()) as Map<*, *>, "start_ns")
        assertTrue(events(out, "power_sample").maxOf { ns(it, "mono_ns") } >= origin + 21_000_000_000L)
        assertTrue(s.containsKey("cooling_extended_ns"))
        assertEquals(60L, (events(out, "phase_start").first { it["phase"] == "resident_baseline" }["baseline_s"] as Number).toLong())
        assertEquals(128, out.listFiles()!!.count { it.name.endsWith(".result.json") })
        assertTrue(events(out, "decision").isNotEmpty())
        assertEquals(1, events(out, "dispatch_closed").size)
    }

    /** 조민규 01:5x #4 왕복: SMOOTH128 예정 도착 = origin + floor(i × 15 × 537,155,000 / 127)/scale (ns) · 절대기한 = 그 도착 + C 0.8 / D 2 s (묶음 기한 아님) · 묶음 없음 (wait 이벤트 0). */
    @Test fun smooth128ArrivalsAndDeadlinesFollowTheNsFormula() {
        val (out, _) = run("SMOOTH128_BASE", "S26-M8-S128-SMOKE", 0)
        val r = rows(out).sortedBy { (it["ordinal"] as Number).toInt() }
        assertEquals(128, r.size); assertTrue(r.all { it["terminal_status"] == "succeeded" })
        val origin = ns(TestJson.parse(File(out, "common_boundary.json").readText()) as Map<*, *>, "start_ns")
        r.forEachIndexed { i, row ->
            val offsetNs = 35_000_000_000L + Math.floorDiv(i.toLong() * 15L * 537_155_000L, 127L)
            assertEquals("ordinal $i offset_ns", offsetNs, ns(row, "offset_ns"))
            assertEquals("ordinal $i scheduled", origin + offsetNs / scale, ns(row, "scheduled_arrival_ns"))
            val rel = if (row["priority"] == "urgent") 800_000_000L else 2_000_000_000L
            assertEquals("ordinal $i deadline", ns(row, "scheduled_arrival_ns") + rel / scale, ns(row, "deadline_ns"))
            assertEquals(i, (row["burst_index"] as Number).toInt())                                   // 요청마다 다른 시각 = 묶음 index 가 ordinal
        }
        assertEquals(0, events(out, "wait_end").size)
    }

    /**
     * 조민규 01:5x #6: 응답 경계는 priority 기준 (task 무관) — C/D × urgent/normal 네 조합 코드 시험.
     * bank 는 C=urgent · D=normal 고정이고 SessionManifest.validate 가 교차 행을 거부하므로 (fail closed) 이 시험은 diagnostic manifest 의 priority 를 바꿔 validate 없이 엔진 경계 선택만 본다.
     * 실제 교차 실측은 P3 범위 (핵심 C긴급/D일반 자료로 교차 효과를 검증했다고 하지 않음).
     */
    @Test fun responseBoundaryAllFourTaskPriorityCombos() {
        val flip = { q: MixreqContract.Request -> if (q.ordinal % 4 == 1 || q.ordinal % 4 == 2) q.copy(priority = if (q.priority == "urgent") "normal" else "urgent") else q }
        val (out, _) = run("L64_CROSS", "S26-M8-L64-SMOKE", 0, mutate = flip, validate = false)
        val r = rows(out)
        assertEquals(64, r.size); assertTrue(r.all { it["terminal_status"] == "succeeded" })
        val combos = r.groupBy { "${it["task_id"]}/${it["priority"]}" }
        assertEquals(setOf("classification/urgent", "detection/urgent", "classification/normal", "detection/normal"), combos.keys)
        combos.forEach { (_, rows) -> assertEquals(16, rows.size) }
        for (task in listOf("classification", "detection")) {
            combos.getValue("$task/urgent").forEach { row ->
                assertEquals("output_ready", row["response_boundary"]); assertEquals(ns(row, "output_ready_ns"), ns(row, "response_ns"))
            }
            combos.getValue("$task/normal").forEach { row ->
                assertEquals("readback_complete", row["response_boundary"]); assertEquals(true, row["readback_ok"]); assertEquals(ns(row, "readback_end_ns"), ns(row, "response_ns"))
                assertTrue(ns(row, "readback_end_ns") > ns(row, "output_ready_ns"))
            }
        }
        // 교차 행이 bank 검증을 통과하지 않음 (fail closed)
        var rejected = false
        try { SessionManifest.parse(String(manifestBytes("S26-M8-L64-SMOKE", 0, flip))).validate() } catch (e: IllegalArgumentException) { rejected = true }
        assertTrue(rejected)
    }

    @Test fun responseBoundaryFollowsPriorityNotTask() {
        // 같은 task (classification) 두 우선순위를 가진 표는 bank 에 없다 → 행 단위 사실: normal 탐지는 readback · urgent 분류는 output_ready (priority 열로 고름).
        val (out, _) = run("L64_BASE", "S26-M8-L64-SMOKE", 0)
        val r = rows(out)
        assertEquals(64, r.size)
        assertTrue(r.filter { it["priority"] == "normal" }.all { it["response_boundary"] == "readback_complete" && it["task_id"] == "detection" })
        assertTrue(r.filter { it["priority"] == "urgent" }.all { it["response_boundary"] == "output_ready" })
    }

    @Test fun m128PairGOverlapsAtMostTwo() {
        val (out, _) = run("M128_PAIR_G", "S26-M8-M128-SMOKE", 2, detMs = 400)
        val r = rows(out)
        assertTrue(r.all { it["terminal_status"] == "succeeded" })
        assertEquals(2, maxConcurrent(r))                                                                  // 허용 조합 최대 2
        val b = busy(r)
        var overlap = 0L
        for ((la, s1, e1) in b.filter { it.first == "GPU" }) for ((lb, s2, e2) in b.filter { it.first == "CPU" }) { if (la != lb) overlap += maxOf(0L, minOf(e1, e2) - maxOf(s1, s2)) }
        assertTrue(overlap > 0L)
        assertEquals(96, r.count { it["selected_backend"] == "GPU" })
    }

    @Test fun m128Wait200x16RecordsSixteenDoses() {
        val (out, _) = run("M128_WAIT200x16", "S26-M8-M128-SMOKE", 3)
        val r = rows(out)
        assertTrue(r.all { it["terminal_status"] == "succeeded" })
        val waits = events(out, "wait_end")
        assertEquals(16, waits.size)
        assertEquals((0 until 16).toList(), waits.map { (it["burst_index"] as Number).toInt() })
        assertTrue(waits.all { (it["planned_ms"] as Number).toLong() == 200L && it["cut_reason"] == null })
        assertTrue(waits.all { (it["dose_ms"] as Number).toDouble() in 15.0..60.0 })                         // 200 ms / time_scale 10 = 20 ms (호스트 타이머 여유)
        val s = summary(out)["wait"] as Map<*, *>
        assertEquals(16L, (s["count"] as Number).toLong()); assertEquals(3_200L, (s["planned_total_ms"] as Number).toLong()); assertEquals(16L, (s["interventions"] as Number).toLong())
        assertEquals(3_200L, (s["nominal_total_ms"] as Number).toLong())                              // 명목 (별도 열) ≠ 실제 dose_total_ms
        assertTrue((s["dose_total_ms"] as Number).toDouble() != 3_200.0 && (s["overrun_total_ms"] as Number).toDouble() == (s["dose_total_ms"] as Number).toDouble() - 3_200.0)
        assertTrue(waits.all { (it["nominal_total_ms"] as Number).toLong() == 3_200L && (it["overrun_ms"] as Number).toDouble() == (it["dose_ms"] as Number).toDouble() - 200.0 })
        assertEquals(16, r.count { it["wait_burst_index"] != null })
        // WAIT 중 dispatch 0: 모든 dispatch 는 어떤 wait 구간 [start, end) 밖
        for (row in r) { val d = ns(row, "dispatch_ns"); assertTrue(waits.none { d >= ns(it, "wait_start_ns") && d < ns(it, "wait_end_ns") }) }
    }

    @Test fun c252SlowCpuLeavesUndispatchedAtWindowEnd() {
        val (out, _) = run("C252_CPU_slow", "S26-M8-C252-SMOKE", 0, clsMs = 500)
        val r = rows(out)
        val s = summary(out)
        val und = r.count { it["terminal_status"] == "undispatched" }
        assertTrue("undispatched $und", und > 0)
        assertEquals(und.toLong(), (s["undispatched"] as Number).toLong())
        assertEquals(252L, (s["planned"] as Number).toLong())
        assertEquals(252, r.count { it["terminal_status"] == "succeeded" } + und)
        val boundary = TestJson.parse(File(out, "common_boundary.json").readText()) as Map<*, *>
        val windowEnd = ns(boundary, "planned_end_ns")
        assertTrue(r.filter { it["dispatch_ns"] != null }.all { ns(it, "dispatch_ns") < windowEnd })        // 120 s 뒤 dispatch 0
        assertTrue(r.filter { it["terminal_status"] == "undispatched" }.all { it["dispatch_ns"] == null && it["undispatched_reason"] != null })
        assertEquals(12_000_000_000L, windowEnd - ns(boundary, "start_ns"))                                 // 120 s / 10
    }

    @Test fun recentCpu60PrepDefinesTheCommonOrigin() {
        val (out, _) = run("RECENT_CPU60_C252_CPU", "S26-M8-RECENT-SMOKE", 0, clsMs = 30)
        val prep = TestJson.parse(File(out, "prep.json").readText()) as Map<*, *>
        assertEquals("CPU60", prep["kind"]); assertTrue((prep["calls"] as Number).toInt() > 50)
        val prepEnd = ns(prep, "prep_end_ns")
        assertTrue(ns(prep, "actual_prep_ns") >= 6_000_000_000L)                                            // 60 s / 10
        val boundary = TestJson.parse(File(out, "common_boundary.json").readText()) as Map<*, *>
        val origin = ns(boundary, "start_ns")
        assertEquals(prepEnd + 500_000_000L - 3_500_000_000L, origin)                                       // common 0 = prep_end + 5 s − 35 s (scaled)
        val r = rows(out)
        assertEquals(prepEnd + 500_000_000L, r.minOf { ns(it, "scheduled_arrival_ns") })                    // 첫 본 요청 = prep_end + 5 s
        assertTrue(r.all { it["terminal_status"] == "succeeded" })
        val cs = events(out, "common_start").first()
        assertEquals("CPU60", cs["prep"]); assertTrue((cs["origin_before_now_ns"] as Number).toLong() >= 2_900_000_000L)
        assertTrue(events(out, "prep_call_end").size == (prep["calls"] as Number).toInt())
        assertTrue(events(out, "power_sample").size > 20)                                                   // 준비부터 센서 연속 (sampler 계속)
        assertEquals("prep", events(out, "phase_start").first { it["phase"] == "prep" }["role"])
    }

    @Test fun idleNoRuntimeKeepsTheSamplerWithoutRuntimes() {
        val (out, _) = run("IDLE_NO_RUNTIME", "S26-M8-IDLE-SMOKE", 0)
        val s = summary(out)
        assertEquals(listOf<String>(), s["runtime_keys"]); assertEquals(0L, (s["planned"] as Number).toLong()); assertEquals("NONE", TestJson.parse(File(out, "manifest.json").readText()).let { (it as Map<*, *>)["block"] })
        assertEquals(0, (TestJson.parse(File(out, "warmup.json").readText()) as List<*>).size)
        assertEquals(0, rows(out).size)
        assertTrue(events(out, "power_sample").size > 20)
        assertTrue(events(out, "runtime_return").isEmpty())
        assertFalse(File(out, "prep.json").exists())
        assertEquals(1, events(out, "common_start").size)
        val (out2, _) = run("IDLE_RESIDENT", "S26-M8-IDLE-SMOKE", 1)
        assertEquals(MixreqContract.keysOf("M").sorted(), summary(out2)["runtime_keys"]); assertEquals(0, rows(out2).size)
    }
}
