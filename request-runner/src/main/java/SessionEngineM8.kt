package com.example.d1check.requestrunner

import com.example.d1check.requestrunner.MixreqContract.Request
import org.json.JSONArray
import java.io.File
import java.util.Base64
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledFuture
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/*
 * M8 세션 실행기 (2026-10-14 · d1sim/docs/M8_계약표_v1.md · s26/results/m8_prep/contract/{policies,banks,response,session}_m8.json · 조민규 답 10/14 §3 ~ §7).
 * SessionEngine (M6/M7 행) 은 한 줄도 바꾸지 않는다 — 이 파일은 contract = M8 행에서만 돈다 (SessionActivity 가 고른다). 같은 산출물 꼴 (progress.jsonl ·
 * requests.json · common_boundary.json · summary.json · cleanup.json · <id>.result.json · <id>.event.json) 에 M8 열 · 이벤트를 더한다.
 * SessionEngine 과 다른 점 (전부 계약표):
 *   1. 선택 = PolicyStudy.chooseM8 (FIFO/EDD strict head · SERIAL/PAIR · 실제 running 집합) · 모든 결정 (null 포함) 을 decision 이벤트로.
 *   2. WAIT (FIFO_WAIT_CG_V1 + policy_args): 묶음 첫 배정 전 고정 타이머 · 타이머 중 도착 = enqueue 만 · 120 s 경계 · stop 이 끊으면 잘린 dose · wait 이벤트 · summary.wait.
 *   3. 응답 경계 = priority: urgent = output_ready · normal = persist 뒤 readback (파일 다시 읽어 SHA 대조 · 시각 · 성공/실패 기록) · response_ns 열.
 *   4. 서비스 120 s 뒤 새 dispatch 0 (waiting → undispatched) · running 만 비선점 drain (≤ 30 s).
 *   5. 준비 role (prep.kind CPU60 = 분류 CPU 연속 호출 60 s / IDLE60 = 유휴 60 s) → prep_end (마지막 실제 AVAILABLE) + 5 s = 첫 본 요청 (t 35) → common 0 = prep_end − 30 s.
 *   6. baseline 60 · cooling 90 (M8 상수) · 같은 시각 8건 = 한 타이머에서 ordinal 순서로 enqueue · 블록 NONE = runtime 0 (setup · warmup 건너뜀 · sampler · logger 같음).
 * Android 의존 (시계 · 표본 · 디코드 · 런타임 · 로그) 은 SessionEngine 과 같이 주입 → Robolectric 시험 (M8RoundTripTest).
 */
class SessionEngineM8(
    private val manifest: SessionManifest,
    private val manifestBytes: ByteArray,
    private val inputsRoot: File,
    private val outRoot: File,
    private val runtimeFactory: (RuntimeSpec) -> InferenceRuntime,
    private val decodeImage: (File) -> DecodedImage,
    private val snapshot: () -> Map<String, Any?>,
    private val now: () -> Long,
    private val identity: Map<String, Any?> = emptyMap(),
    private val log: (String) -> Unit = {},
) {
    val stop = AtomicReference<String?>(null)
    val samplerFailure = AtomicReference<String?>(null)
    @Volatile var phase: String = "created"
        private set
    @Volatile var commonStartNs: Long? = null
        private set
    @Volatile var commonEndNs: Long? = null
        private set

    private val sid = manifest.sessionId
    private val scale = manifest.timeScale
    private val dispatch = single("d1mix-dispatch")
    private val lanes: Map<String, ExecutorService> = MixreqContract.LANES.associateWith { single("d1mix-${it.lowercase()}") }
    private val arrivals = Executors.newSingleThreadScheduledExecutor { Thread(it, "d1mix-arrivals") }
    private val samples = Executors.newSingleThreadScheduledExecutor { Thread(it, "d1mix-samples") }
    private val waitTimer = Executors.newSingleThreadScheduledExecutor { Thread(it, "d1mix-wait") }
    private val rows = ConcurrentHashMap<String, MutableMap<String, Any?>>()
    private val runtimes = ConcurrentHashMap<String, TaskRuntime>()
    private var progress: ProgressWriter? = null
    private var store: ArtifactStore? = null
    private var sequence = 0L
    private val waitEvents = mutableListOf<Map<String, Any?>>()   // dispatch executor only
    private var prepRecord: Map<String, Any?>? = null

    init { require(manifest.isM8) { "SessionEngineM8 runs contract M8 rows only (manifest contract ${manifest.contract})" } }

    private fun single(name: String) = Executors.newSingleThreadExecutor { Thread(it, name) }
    private fun lane(key: String) = lanes.getValue(MixreqContract.laneOf(key))
    private fun scaled(ns: Long) = ns / scale

    @Synchronized
    fun event(kind: String, data: Map<String, Any?> = emptyMap()) {
        progress?.add(
            Json.encode(
                data + mapOf(
                    "kind" to kind, "mono_ns" to now(), "sequence" to sequence++, "session_id" to sid,
                    "phase" to (data["phase"] ?: phase), "thread_id" to Thread.currentThread().id,
                    "thread_name" to Thread.currentThread().name,
                ),
            ),
        )
    }

    fun lifecycle(callback: String, extra: Map<String, Any?> = emptyMap()) {
        if (progress == null) return
        runCatching { event("activity_lifecycle", mapOf("callback" to callback, "stop_reason" to stop.get()) + extra) }
            .onFailure { log("lifecycle journal unavailable: $callback $it") }
    }

    private fun healthy() {
        check(stop.get() == null && progress?.failure?.get() == null && !Thread.currentThread().isInterrupted) {
            "stopped: ${stop.get()}/${progress?.failure?.get()}"
        }
    }

    private fun update(row: MutableMap<String, Any?>, fields: Map<String, Any?>) = synchronized(row) { row.putAll(fields) }
    private fun detached(row: MutableMap<String, Any?>): Map<String, Any?> = synchronized(row) { LinkedHashMap(row) }

    /** 등록 §3-6 과 같은 앱 안 멈춤 규칙 (M8 도 같음). */
    fun stopReason(data: Map<String, Any?>): String? {
        val plugged = (data["plugged"] as? Number)?.toInt()
        val thermal = (data["thermal_status"] as? Number)?.toInt()
        val temperature = (data["battery_temperature_deci_c"] as? Number)?.toInt()
        val level = (data["battery_level"] as? Number)?.toInt()
        val interactive = data["interactive"] as? Boolean
        return when {
            plugged == null || plugged != 0 -> "plugged_$plugged"
            thermal == null || thermal > manifest.stopRules.thermalStatusMax -> "thermal_status_$thermal"
            temperature == null || temperature >= manifest.stopRules.batteryDeciCMax -> "bat_deci_c_$temperature"
            level == null || level < manifest.stopRules.socMin -> "soc_$level"
            interactive != true -> "screen_off"
            else -> null
        }
    }

    private fun sample() {
        try {
            val data = snapshot()
            stopReason(data)?.let { stop.compareAndSet(null, "environment/$it") }
            event("power_sample", data)
        } catch (e: Throwable) {
            samplerFailure.compareAndSet(null, e.toString())
            stop.compareAndSet(null, "sampler_failed: $e")
        }
    }

    private fun sleepHealthy(durationNs: Long) = sleepUntilHealthy(now() + durationNs)

    private fun sleepUntilHealthy(untilNs: Long) {
        while (now() < untilNs) {
            healthy()
            val remainingMs = (untilNs - now()) / 1_000_000
            Thread.sleep(remainingMs.coerceIn(1L, 100L))
        }
    }

    private fun loadAnchors(): List<DoubleArray> {
        val file = File(manifest.anchors.path)
        require(TaskRuntime.sha256(file) == manifest.anchors.sha256) { "anchors SHA-256 mismatch" }
        val rows = JSONArray(file.readText())
        require(rows.length() == 19_206) { "anchors count ${rows.length()}" }
        return List(rows.length()) { i ->
            val row = rows.getJSONArray(i)
            require(row.length() == 4) { "anchor $i" }
            DoubleArray(4) { row.getDouble(it) }
        }
    }

    private fun loadLabels(): Map<String, List<String>> = manifest.labels.mapValues { (task, spec) ->
        val file = File(spec.path)
        require(TaskRuntime.sha256(file) == spec.sha256) { "$task labels SHA-256 mismatch" }
        TaskRuntime.labelLines(file.readText(Charsets.UTF_8))
    }

    fun run(): Boolean {
        var failure: String? = null
        val manifestSha = ImageContract.sha256(manifestBytes)
        try {
            check(!outRoot.exists() && outRoot.mkdirs()) { "attempt folder exists or not creatable: $outRoot" }
            val artifacts = ArtifactStore(outRoot).also { store = it }
            artifacts.saveBytes("manifest.json", manifestBytes)
            progress = ProgressWriter(File(outRoot, "progress.jsonl"))
            event("session_start", identity + mapOf(
                "protocol" to MixreqContract.PROTOCOL, "manifest_sha256" to manifestSha, "experiment_id" to manifest.experimentId,
                "split" to manifest.split, "block" to manifest.block, "policy" to manifest.policy, "attempt" to manifest.attempt,
                "time_scale" to scale, "engine" to MixreqContract.ENGINE, "litert_version" to MixreqContract.LITERT_VERSION,
                "contract" to MixreqContract.CONTRACT_M8, "policy_args" to manifest.policyArgs?.record(), "prep" to manifest.prep.name,
            ))
            log("session_start sid=$sid attempt=${manifest.attempt} block=${manifest.block} policy=${manifest.policy} contract=M8 manifest_sha256=$manifestSha time_scale=$scale")
            samples.scheduleAtFixedRate({ sample() }, 0, manifest.samplePeriodMs, TimeUnit.MILLISECONDS)

            // ---- runtime setup (블록 NONE 이면 0 — 이벤트는 남긴다)
            phase = "runtime_setup"
            event("phase_start", mapOf("runtime_count" to manifest.runtimes.size))
            log("phase=runtime_setup runtimes=${manifest.runtimes.size}")
            val setupStart = now()
            val setupNs = manifest.setupNs
            val image = File(manifest.image.path)
            check(TaskRuntime.sha256(image) == manifest.image.sha256) { "image SHA-256 mismatch at setup" }
            val anchors = loadAnchors()
            val labels = loadLabels()
            val differences = mutableListOf<String>()
            for (spec in manifest.runtimes.sortedBy { it.key }) {
                healthy()
                check(now() - setupStart < setupNs) { "setup timeout before ${spec.key}" }
                event("runtime_submit", mapOf("key" to spec.key))
                log("runtime create_start key=${spec.key} backend=${spec.backend} model=${spec.modelId}")
                try {
                    lane(spec.key).submit<Unit> {
                        event("runtime_start", mapOf("key" to spec.key))
                        event("admission", snapshot())
                        healthy()
                        val modelSha = TaskRuntime.sha256(File(spec.modelPath))
                        check(modelSha == spec.modelSha256) { "${spec.key}: model SHA-256 $modelSha != ${spec.modelSha256}" }
                        val runtime = runtimeFactory(spec)
                        runtimes[spec.key] = TaskRuntime(spec, runtime, labels.getValue(spec.task), if (spec.task == "detection") anchors else emptyList(), decodeImage, now)
                        event("runtime_return", mapOf("key" to spec.key, "model_sha256" to modelSha) + runtime.initRecord())
                    }.get(minOf(MixreqContract.CALL_NS, setupNs - (now() - setupStart)), TimeUnit.NANOSECONDS)
                    log("runtime create_end key=${spec.key} ok")
                } catch (e: Throwable) {
                    val cause = (e as? java.util.concurrent.ExecutionException)?.cause ?: e
                    if (spec.key == SessionEngine.DETECTION_GPU_KEY && stop.get() == null) {
                        event("runtime_create_failed", mapOf("key" to spec.key, "error" to cause.toString()))
                        log("runtime create_end key=${spec.key} error=${cause.javaClass.simpleName}")
                        differences += "A24 와 다름: detection_GPU 생성 실패 → 그 runtime 없이 진행 (${cause.javaClass.simpleName})"
                    } else {
                        throw cause
                    }
                }
            }
            event("phase_end", mapOf("created" to runtimes.keys.sorted()))

            // ---- warmup 2 per key (NONE 이면 0)
            phase = "warmup"
            event("phase_start")
            log("phase=warmup")
            val warmups = mutableListOf<Map<String, Any?>>()
            for (key in manifest.runtimes.map { it.key }.sorted().filter { runtimes.containsKey(it) }) repeat(MixreqContract.WARMUPS_PER_KEY) { index ->
                healthy()
                check(now() - setupStart < setupNs) { "setup timeout before warmup $key/$index" }
                event("warmup_submit", mapOf("key" to key, "index" to index))
                log("warmup_start key=$key index=$index")
                val outcome = lane(key).submit<TaskRuntime.Outcome> {
                    event("warmup_start", mapOf("key" to key, "index" to index))
                    event("admission", snapshot())
                    healthy()
                    runtimes.getValue(key).execute(image, manifest.image.sha256, recordDecodedRgb = true)
                        .also { event("warmup_return", mapOf("key" to key, "index" to index)) }
                }.get(minOf(MixreqContract.CALL_NS, setupNs - (now() - setupStart)), TimeUnit.NANOSECONDS)
                log("warmup_end key=$key index=$index ok")
                warmups += linkedMapOf(
                    "key" to key, "index" to index, "result" to outcome.record,
                    "softmax_sha256" to outcome.softmax?.let { ImageContract.sha256(it) },
                    "softmax_f32le_base64" to outcome.softmax?.let { Base64.getEncoder().encodeToString(SessionEngine.floatBytes(it)) },
                )
            }
            log("phase=warmup_end")
            event("phase_end", mapOf("warmups" to warmups.size))
            artifacts.save("warmup.json", warmups)
            if (manifest.warmupOnly) {
                log("warmup_only: session ends after warmup")
                artifacts.save("summary.json", mapOf(
                    "status" to "warmup_only", "protocol" to MixreqContract.PROTOCOL, "experiment_id" to manifest.experimentId, "contract" to MixreqContract.CONTRACT_M8,
                    "split" to manifest.split, "session_id" to sid, "session_index" to manifest.sessionIndex, "block" to manifest.block,
                    "policy" to manifest.policy, "planned" to 0, "terminal" to 0, "time_scale" to scale, "runtime_keys" to runtimes.keys.sorted(),
                    "detection_gpu_created" to runtimes.containsKey(SessionEngine.DETECTION_GPU_KEY), "a24_differences" to differences,
                    "manifest_sha256" to manifestSha, "experiment_ready" to false,
                ) + identity)
                return true
            }

            // ---- host warmup gate (same as M6: warmup.ready.json → warmup.arm == manifest SHA, ≤ 60 s)
            if (manifest.warmupGate) {
                phase = "warmup_gate"
                progress?.flush()
                artifacts.save("warmup.ready.json", mapOf("manifest_sha256" to manifestSha, "mono_ns" to now()))
                log("warmup_gate ready")
                val gateStart = now()
                val arm = File(inputsRoot, "warmup.arm")
                while (!arm.exists()) {
                    healthy()
                    check(now() - gateStart < MixreqContract.GATE_NS) { "warmup gate timeout" }
                    Thread.sleep(50)
                }
                check(arm.readText().trim() == manifestSha) { "warmup gate manifest SHA mismatch" }
                event("host_gate_accepted", mapOf("gate" to "warmup"))
                log("warmup_gate accepted")
            }
            check(stop.get() == null) { "stopped before baseline: ${stop.get()}" }

            // ---- resident baseline 60 s (M8)
            phase = "resident_baseline"
            event("phase_start", mapOf("baseline_s" to manifest.phases.baselineS))
            log("phase=resident_baseline ${manifest.phases.baselineS} s")
            sleepHealthy(scaled(manifest.phases.baselineS * 1_000_000_000L))
            event("phase_end")

            // ---- start check (앱 안: thermal status ≤ 1 · plugged 0) — 호스트 게이트 (gate_m8.json) 는 드라이버
            phase = "start_check"
            val startSnapshot = snapshot()
            val thermal = (startSnapshot["thermal_status"] as? Number)?.toInt()
            val plugged = (startSnapshot["plugged"] as? Number)?.toInt()
            val passed = thermal != null && thermal <= manifest.startThermalStatusMax && plugged == 0
            artifacts.save("start_check.json", startSnapshot + mapOf("thermal_status_max" to manifest.startThermalStatusMax, "passed" to passed))
            check(passed) { "start_check: thermal_status=$thermal plugged=$plugged" }

            // ---- prep (RECENT 행만): CPU60 / IDLE60 → prep_end → + 5 s = 첫 본 요청 (t 35) → common 0 = prep_end − 30 s
            val start: Long
            if (manifest.prep != M8Plan.Prep.NONE) {
                val prepEnd = runPrep(image, artifacts)
                start = prepEnd + scaled(M8Plan.PREP_GAP_S * 1_000_000_000L) - scaled(M8Plan.FIRST_OFFSET_US * 1_000L)
            } else {
                start = now()
            }

            // ---- common window 120 s (origin may lie in the past for RECENT rows)
            phase = "common_window"
            commonStartNs = start
            event("common_start", mapOf("scheduled_origin_ns" to start, "window_ns" to scaled(MixreqContract.COMMON_NS), "time_scale" to scale,
                "prep" to manifest.prep.name, "origin_before_now_ns" to (now() - start)))
            log("common_start origin_ns=$start prep=${manifest.prep} now_minus_origin_ns=${now() - start}")
            runWindow(image, start, artifacts)

            // ---- resident cooling 90 s (M8)
            phase = "resident_cooling"
            event("phase_start", mapOf("cooling_s" to manifest.phases.coolingS))
            log("phase=resident_cooling ${manifest.phases.coolingS} s")
            sleepHealthy(scaled(manifest.phases.coolingS * 1_000_000_000L))
            event("phase_end")
            val finalRows = manifest.requests.map { detached(rows.getValue(it.id)) }
            val normals = finalRows.filter { it["priority"] == "normal" }
            artifacts.save("summary.json", mapOf(
                "status" to "completed", "protocol" to MixreqContract.PROTOCOL, "experiment_id" to manifest.experimentId, "contract" to MixreqContract.CONTRACT_M8,
                "split" to manifest.split, "session_id" to sid, "session_index" to manifest.sessionIndex, "block" to manifest.block,
                "pair" to manifest.pair, "attempt" to manifest.attempt, "policy" to manifest.policy, "policy_args" to manifest.policyArgs?.record(),
                "selection" to (if (manifest.policy in MixreqContract.M8_POLICIES) PolicyStudy.selectionOf(manifest.policy) else null),
                "concurrency" to (if (manifest.policy in MixreqContract.M8_POLICIES) PolicyStudy.concurrencyOf(manifest.policy) else null),
                "planned" to manifest.requests.size, "terminal" to finalRows.count { it["terminal_status"] == "succeeded" },
                "failed" to finalRows.count { it["terminal_status"] == "failed" }, "undispatched" to finalRows.count { it["terminal_status"] == "undispatched" },
                "unfinished" to finalRows.count { it["terminal_status"] == "unfinished" },
                "readback" to mapOf("performed" to normals.count { it["readback_ok"] != null }, "ok" to normals.count { it["readback_ok"] == true },
                    "failed" to normals.count { it["readback_ok"] == false }, "normal_planned" to normals.size),
                "response_boundary" to mapOf("urgent" to "output_ready", "normal" to "readback_complete", "selected_by" to "priority"),
                "wait" to waitSummary(), "prep" to prepRecord, "common_start_ns" to start, "common_end_ns" to commonEndNs, "time_scale" to scale,
                "runtime_keys" to runtimes.keys.sorted(), "used_keys" to manifest.usedKeys.sorted(),
                "detection_gpu_created" to runtimes.containsKey(SessionEngine.DETECTION_GPU_KEY), "a24_differences" to differences,
                "manifest_sha256" to manifestSha, "experiment_ready" to false,
            ) + identity)
            return true
        } catch (e: Throwable) {
            failure = e.toString()
            stop.compareAndSet(null, failure)
            runCatching {
                store?.save("session_failure.json", mapOf("error" to failure, "phase" to phase, "mono_ns" to now(),
                    "stop_reason" to stop.get(), "stack" to e.stackTraceToString().take(4_000)))
            }
            runCatching { event("session_failed", mapOf("error" to failure)) }
            log("session_failed phase=$phase error=$failure")
            return false
        } finally {
            phase = "cleanup"
            arrivals.shutdownNow()
            waitTimer.shutdownNow()
            samples.shutdownNow()
            for ((laneName, executor) in lanes) {
                runCatching {
                    executor.submit { runtimes.values.filter { it.spec.lane == laneName }.forEach { it.close() } }.get(5, TimeUnit.SECONDS)
                }.onFailure { failure = "$failure; cleanup $laneName: $it" }
            }
            runCatching {
                event("app_cleanup", mapOf("error" to failure))
                progress?.close()
            }.onFailure { failure = "$failure; flush: $it" }
            runCatching {
                store?.save("cleanup.json", mapOf("status" to if (failure == null) "completed" else "failed", "error" to failure,
                    "mono_ns" to now(), "sampler_failure" to samplerFailure.get(), "stop_reason" to stop.get()))
            }
            lanes.values.forEach { it.shutdownNow() }
            dispatch.shutdownNow()
            log("session_end status=${if (failure == null) "completed" else "failed"}")
        }
    }

    /** 준비 (session_m8.json prep): CPU60 = classification_CPU 연속 호출 (호출마다 시각 · 요청 아님) · IDLE60 = 유휴. 반환 = prep_end (마지막 실제 AVAILABLE · 기기 시계). */
    private fun runPrep(image: File, artifacts: ArtifactStore): Long {
        phase = "prep"
        val prepNs = scaled(M8Plan.PREP_S * 1_000_000_000L)
        val prepStart = now()
        event("phase_start", mapOf("role" to "prep", "prep_kind" to manifest.prep.name, "prep_ns" to prepNs))
        log("phase=prep kind=${manifest.prep}")
        val calls = mutableListOf<Map<String, Any?>>()
        var lastAvailable = prepStart
        if (manifest.prep == M8Plan.Prep.CPU60) {
            val key = "classification_CPU"
            val runtime = runtimes[key] ?: error("prep CPU60 needs $key resident")
            while (now() - prepStart < prepNs) {
                healthy()
                val startNs = now()
                event("prep_call_start", mapOf("key" to key, "index" to calls.size))
                val outcome = lane(key).submit<TaskRuntime.Outcome> { runtime.execute(image, manifest.image.sha256) }.get(MixreqContract.CALL_NS, TimeUnit.NANOSECONDS)
                val endNs = now()
                lastAvailable = endNs
                event("prep_call_end", mapOf("key" to key, "index" to calls.size, "inference_ns" to outcome.record["inference_ns"]))
                calls += linkedMapOf("index" to calls.size, "start_ns" to startNs, "end_ns" to endNs, "inference_ns" to outcome.record["inference_ns"])
            }
        } else {
            sleepHealthy(prepNs)
            lastAvailable = now()
        }
        val prepEnd = lastAvailable
        event("prep_end", mapOf("prep_kind" to manifest.prep.name, "prep_start_ns" to prepStart, "prep_end_ns" to prepEnd, "prep_last_available_ns" to lastAvailable, "calls" to calls.size))
        event("phase_end", mapOf("role" to "prep"))
        prepRecord = linkedMapOf("kind" to manifest.prep.name, "prep_start_ns" to prepStart, "prep_end_ns" to prepEnd, "prep_last_available_ns" to lastAvailable,
            "calls" to calls.size, "gap_to_first_request_ns" to scaled(M8Plan.PREP_GAP_S * 1_000_000_000L), "common_origin_rule" to "prep_end + 5 s − 35 s",
            "planned_prep_ns" to prepNs, "actual_prep_ns" to (prepEnd - prepStart))
        artifacts.save("prep.json", prepRecord!! + mapOf("call_records" to calls))
        log("prep_end calls=${calls.size} actual_ns=${prepEnd - prepStart}")
        return prepEnd
    }

    private fun waitSummary(): Map<String, Any?> {
        val events = synchronized(waitEvents) { waitEvents.toList() }
        val args = manifest.policyArgs
        return linkedMapOf(
            "policy_has_wait" to (args != null), "args" to args?.record(), "count" to events.size, "interventions" to events.size,
            "planned_total_ms" to events.sumOf { (it["planned_ms"] as Number).toLong() }, "dose_total_ms" to events.sumOf { (it["dose_ms"] as Number).toDouble() },
            "cut" to events.count { it["cut_reason"] != null }, "bursts" to events.map { it["burst_index"] }, "note" to (if (args != null && events.isEmpty()) "의도 WAIT 발생 0 (기록)" else null),
        )
    }

    private fun runWindow(image: File, start: Long, artifacts: ArtifactStore) {
        val requests: List<Request> = manifest.requests
        val policy = manifest.policy
        val windowNs = scaled(MixreqContract.COMMON_NS)
        val windowEnd = start + windowNs
        val waitArgs = manifest.policyArgs
        val burstOf = M8Plan.burstIndexOf(requests)
        val waiting = mutableListOf<PolicyStudy.TicketM8>()          // dispatch executor only
        val running = linkedMapOf<String, String>()                  // key → request id · dispatch executor only (실제 lane 점유)
        val burstsWaited = mutableSetOf<Int>()
        var cumulativeWaitMs = 0L
        var waitActive: Map<String, Any?>? = null                     // dispatch executor only
        var waitFuture: ScheduledFuture<*>? = null
        var dispatchClosed = false
        val drainLock = Object()
        var dispatched = 0
        var finished = 0
        lateinit var pump: () -> Unit

        fun recordWaitEnd(wait: Map<String, Any?>, cutReason: String?) {
            val endNs = now()
            val doseMs = (endNs - (wait["wait_start_ns"] as Long)) / 1e6
            cumulativeWaitMs += (wait["planned_ms"] as Long)
            val rec = wait + mapOf("wait_end_ns" to endNs, "dose_ms" to doseMs, "cut_reason" to cutReason, "cumulative_planned_ms" to cumulativeWaitMs,
                "arrivals_during_wait" to (waiting.size - (wait["waiting_count_at_start"] as Int)))
            synchronized(waitEvents) { waitEvents += rec }
            event("wait_end", rec)
            rows[wait["head_id"] as String]?.let { update(it, mapOf("wait_burst_index" to wait["burst_index"], "wait_planned_ms" to wait["planned_ms"], "wait_dose_ms" to doseMs, "wait_cut_reason" to cutReason)) }
        }

        pump = {
            while (stop.get() == null && waitActive == null && !dispatchClosed) {
                val begin = now()
                val choice = PolicyStudy.chooseM8(policy, waiting, running.keys, begin, windowEnd)
                event("decision", mapOf("policy" to policy, "waiting" to waiting.size, "running" to running.keys.toList(), "selected" to choice?.ticket?.id,
                    "backend" to choice?.backend, "reason" to (choice?.reason ?: if (begin >= windowEnd) "window_end" else if (waiting.isEmpty()) "no_ready" else "head_blocked"),
                    "decision_start_ns" to begin, "decision_end_ns" to now()))
                if (choice == null) break
                // ---- WAIT (policies_m8.json): 묶음 첫 배정 전 · 고정 타이머 · 타이머 중 도착 = enqueue 만
                if (waitArgs != null) {
                    val burst = burstOf.getValue(choice.ticket.id)
                    val planned = PolicyStudy.plannedWaitMs(waitArgs, burst, burstsWaited, cumulativeWaitMs, running.size, waiting.isNotEmpty())
                    if (planned != null) {
                        burstsWaited += burst
                        val startNs = now()
                        val wait = linkedMapOf<String, Any?>("burst_index" to burst, "head_id" to choice.ticket.id, "planned_ms" to planned, "wait_start_ns" to startNs,
                            "waiting_count_at_start" to waiting.size, "cap_ms" to waitArgs.capMs, "first_n_bursts" to waitArgs.firstNBursts)
                        waitActive = wait
                        event("wait_start", wait)
                        val delayNs = minOf(scaled(planned * 1_000_000L), maxOf(0L, windowEnd - startNs))
                        waitFuture = waitTimer.schedule({
                            dispatch.execute {
                                if (waitActive === wait) {
                                    waitActive = null
                                    recordWaitEnd(wait, if (now() >= windowEnd) "window_end" else null)
                                    pump()
                                }
                            }
                        }, delayNs, TimeUnit.NANOSECONDS)
                        break
                    }
                }
                waiting.remove(choice.ticket)
                running[choice.key] = choice.ticket.id
                synchronized(drainLock) { dispatched++ }
                val row = rows.getValue(choice.ticket.id)
                val key = choice.key
                val dispatchedNs = now()
                update(row, mapOf("selected_backend" to choice.backend, "decision_reason" to choice.reason, "dispatch_ns" to dispatchedNs))
                event("dispatch", mapOf("id" to choice.ticket.id, "key" to key, "dispatch_ns" to dispatchedNs))
                lane(key).execute {
                    try {
                        val execution = now()
                        update(row, mapOf("execution_start_ns" to execution))
                        event("request_start", mapOf("id" to choice.ticket.id, "key" to key))
                        event("admission", snapshot())
                        healthy()
                        val inferenceStart = now()
                        update(row, mapOf("host_inference_start_ns" to inferenceStart))
                        event("host_inference_start", mapOf("id" to choice.ticket.id, "key" to key))
                        val outcome = runtimes.getValue(key).execute(image, manifest.image.sha256)
                        val inferenceReturn = now()
                        update(row, mapOf("host_inference_return_ns" to inferenceReturn))
                        event("host_inference_return", mapOf("id" to choice.ticket.id, "key" to key))
                        val ready = now()
                        update(row, mapOf("output_ready_ns" to ready))
                        event("output_ready", mapOf("id" to choice.ticket.id, "key" to key))
                        if (choice.ticket.priority == "urgent") update(row, mapOf("response_ns" to ready, "response_boundary" to "output_ready"))
                        val bytes = Json.encode(outcome.record).toByteArray(Charsets.UTF_8)
                        val name = "${choice.ticket.id}.result.json"
                        artifacts.saveBytes(name, bytes)
                        val persisted = now()
                        update(row, mapOf("persist_complete_ns" to persisted))
                        event("persist_complete", mapOf("id" to choice.ticket.id, "key" to key))
                        if (choice.ticket.priority == "normal") {
                            // ---- readback (response_m8.json): 파일 다시 열어 전부 읽고 SHA 대조 · 시각 · 성공/실패 기록 (host pull 시각 대체 0)
                            val rbStart = now()
                            update(row, mapOf("readback_start_ns" to rbStart))
                            val expected = ImageContract.sha256(bytes)
                            val actual = ImageContract.sha256(File(outRoot, name).readBytes())
                            val rbEnd = now()
                            val ok = actual == expected
                            update(row, mapOf("readback_end_ns" to rbEnd, "readback_ok" to ok, "readback_sha256" to actual, "readback_expected_sha256" to expected,
                                "readback_error" to (if (ok) null else "sha256 mismatch")))
                            event("readback", mapOf("id" to choice.ticket.id, "key" to key, "ok" to ok, "readback_start_ns" to rbStart, "readback_end_ns" to rbEnd))
                            check(ok) { "readback sha256 mismatch for ${choice.ticket.id}" }
                            update(row, mapOf("response_ns" to rbEnd, "response_boundary" to "readback_complete"))
                        } else {
                            update(row, mapOf("readback_skipped" to "urgent"))
                        }
                        update(row, mapOf("terminal_status" to "succeeded"))
                    } catch (e: Throwable) {
                        stop.compareAndSet(null, "request_failed: $e")
                        update(row, mapOf("terminal_status" to "failed", "reason" to e.toString()))
                        runCatching { artifacts.save("${choice.ticket.id}.failure.json", mapOf("error" to e.toString(), "phase" to phase, "mono_ns" to now())) }
                    } finally {
                        val released = now()
                        update(row, mapOf("worker_release_ns" to released))
                        runCatching { event("worker_release", mapOf("id" to choice.ticket.id, "key" to key)) }
                        runCatching { artifacts.save("${choice.ticket.id}.event.json", detached(row)) }
                            .onFailure { stop.compareAndSet(null, "event_save_failed: $it") }
                        dispatch.execute {
                            val available = now()
                            update(row, mapOf("lane_available_ns" to available))
                            running.remove(key)
                            try {
                                event("lane_available", mapOf("id" to choice.ticket.id, "key" to key))
                            } finally {
                                synchronized(drainLock) { finished++; drainLock.notifyAll() }
                                pump()
                            }
                        }
                    }
                }
            }
        }
        // ---- arrivals: 같은 예정 도착 (offset_us) 은 한 타이머에서 ordinal 순서로 enqueue (같은 시각 8건의 ordinal 규칙)
        for ((offsetUs, group) in requests.groupBy { it.offsetUs }.toSortedMap()) {
            val target = start + scaled(offsetUs * 1_000L)
            val ordered = group.sortedBy { it.ordinal }
            arrivals.schedule({
                val actual = now()
                for (q in ordered) {
                    val row = linkedMapOf<String, Any?>(
                        "request_id" to q.id, "ordinal" to q.ordinal, "task_id" to q.task, "priority" to q.priority,
                        "scheduled_arrival_ns" to target, "actual_arrival_ns" to actual, "offset_us" to q.offsetUs,
                        "deadline_ns" to target + scaled(q.deadlineMs * 1_000_000L), "burst_index" to burstOf[q.id], "terminal_status" to "unfinished",
                    )
                    rows[q.id] = row
                    event("arrival", mapOf("id" to q.id, "scheduled_arrival_ns" to target, "actual_arrival_ns" to actual, "burst_index" to burstOf[q.id]))
                }
                dispatch.execute {
                    for (q in ordered) {
                        val row = rows.getValue(q.id)
                        update(row, mapOf("queue_entry_ns" to now()))
                        waiting.add(PolicyStudy.TicketM8(q.id, q.task, q.priority, q.ordinal, target, target + scaled(q.deadlineMs * 1_000_000L)))
                        event("queue_entry", mapOf("id" to q.id, "wait_active" to (waitActive != null)))
                    }
                    pump()
                }
            }, maxOf(0L, target - now()), TimeUnit.NANOSECONDS)
        }
        sleepUntilHealthy(windowEnd)
        // ---- 서비스 120 s 경계: 새 dispatch 0 · 활성 WAIT 는 끊음 (잘린 dose) · waiting → undispatched
        dispatch.submit {
            dispatchClosed = true
            waitActive?.let { w -> waitFuture?.cancel(false); waitActive = null; recordWaitEnd(w, "window_end") }
            for (t in waiting) rows[t.id]?.let { update(it, mapOf("terminal_status" to "undispatched", "undispatched_reason" to "service window end (120 s) — no new dispatch")) }
            event("dispatch_closed", mapOf("undispatched" to waiting.size, "running" to running.keys.toList()))
            waiting.clear()
        }.get(10, TimeUnit.SECONDS)
        val commonEnd = now()
        commonEndNs = commonEnd
        event("common_end", mapOf("common_end_ns" to commonEnd))
        log("common_end end_ns=$commonEnd")
        artifacts.save("common_boundary.json", mapOf(
            "start_ns" to start, "planned_end_ns" to windowEnd, "end_ns" to commonEnd, "planned" to requests.size, "time_scale" to scale, "contract" to MixreqContract.CONTRACT_M8,
            "rows" to requests.map { q -> rows[q.id]?.let(::detached) ?: mapOf("request_id" to q.id, "scheduled_arrival_ns" to start + scaled(q.offsetUs * 1_000L), "terminal_status" to "unobserved_arrival") },
        ))
        phase = "post_window_drain"
        event("phase_start", mapOf("running" to dispatched - finished))
        log("phase=post_window_drain running=${dispatched - finished}")
        val deadline = now() + scaled(MixreqContract.DRAIN_SECONDS * 1_000_000_000L)
        synchronized(drainLock) {
            while (finished < dispatched && now() < deadline) {
                healthy()
                drainLock.wait(50)
            }
            check(finished >= dispatched) { "post-window drain incomplete" }
        }
        healthy()
        event("phase_end")
        log("drain_end")
        artifacts.save("requests.json", requests.map { q -> rows[q.id]?.let(::detached) ?: mapOf("request_id" to q.id, "ordinal" to q.ordinal, "task_id" to q.task, "priority" to q.priority,
            "scheduled_arrival_ns" to start + scaled(q.offsetUs * 1_000L), "terminal_status" to "unobserved_arrival") })
    }
}
