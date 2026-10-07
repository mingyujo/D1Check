package com.example.d1check.requestrunner

import com.example.d1check.requestrunner.MixreqContract.Request
import org.json.JSONArray
import java.io.File
import java.util.Base64
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CountDownLatch
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/*
 * 세션 실행기 — 출처: feature/arrival-scheduling-20260923 @ d588323
 *   benchmark-runner/src/modelProbe/.../ArrivalEnergyActivity.kt 169~496행 (runSession · gate · runWindow · pump · lane · cleanup)
 *   benchmark-runner/src/modelProbe/.../ArrivalRuntimeSetup.kt (정렬 순서 생성 · warmup 2 · 호출당 30 s · closeLane 5 s)
 * 구조를 그대로 옮겼다: 단일 스레드 executor dispatch · lane cpu / gpu (+ npu, 블록 N) · 예약 arrivals · 표본 samples (900 ms) ·
 * pump() 는 큐 진입 · lane_available 마다 dispatch 스레드에서 · 요청 경계 (dispatch → execution_start → host_inference_start/return →
 * output_ready → persist(.part · fsync · rename) → worker_release (finally) → lane_available (dispatch 스레드, busy=false 직전)).
 * 바꾼 것: 엔진 (CompiledModel) · lane 에 NPU 추가 · 단계 길이 상수는 계약 · 시작 확인은 앱 안 thermal status ≤ 1 (A24 는 호스트 AP 게이트) ·
 *   앱 안 멈춤 규칙은 S26 (plugged · status ≥ 3 · BAT ≥ 42 · SOC < 20 · 화면) · time_scale (PC 자체 시험 전용, 본 세션 = 1) ·
 *   Android 의존 (시계 · 표본 · 디코드 · 런타임 · 로그) 은 전부 주입 → JVM / Robolectric 시험에서 가짜로 돌린다.
 */
class SessionEngine(
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
    private val rows = ConcurrentHashMap<String, MutableMap<String, Any?>>()
    private val runtimes = ConcurrentHashMap<String, TaskRuntime>()
    private var progress: ProgressWriter? = null
    private var store: ArtifactStore? = null
    private var sequence = 0L

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

    /** Activity 생명주기 콜백 기록 (A24 lifecycle). progress 가 없으면 무시. */
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

    /** 등록 §3-6. 표본마다 평가 · 첫 사유만 남는다. */
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

    private fun sleepHealthy(durationNs: Long) {
        val start = now()
        while (now() - start < durationNs) {
            healthy()
            val remainingMs = (durationNs - (now() - start)) / 1_000_000
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

    /** 세션 전체. true = completed (summary.json 있음). */
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
            ))
            log("session_start sid=$sid attempt=${manifest.attempt} block=${manifest.block} policy=${manifest.policy} manifest_sha256=$manifestSha time_scale=$scale")
            samples.scheduleAtFixedRate({ sample() }, 0, manifest.samplePeriodMs, TimeUnit.MILLISECONDS)

            // ---- runtime setup (정렬 순서 · 각 lane 스레드에서 생성 · 호출당 30 s · 전체 준비 상한)
            phase = "runtime_setup"
            event("phase_start")
            log("phase=runtime_setup")
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
                        runtimes[spec.key] = TaskRuntime(
                            spec, runtime, labels.getValue(spec.task),
                            if (spec.task == "detection") anchors else emptyList(), decodeImage, now,
                        )
                        event("runtime_return", mapOf("key" to spec.key, "model_sha256" to modelSha) + runtime.initRecord())
                    }.get(minOf(MixreqContract.CALL_NS, setupNs - (now() - setupStart)), TimeUnit.NANOSECONDS)
                    log("runtime create_end key=${spec.key} ok")
                } catch (e: Throwable) {
                    // 등록 §3-1: detection_GPU 생성 실패만 그 runtime 없이 간다 ("A24 와 다름" 기록). 다른 키의 실패 = 세션 실패.
                    val cause = (e as? java.util.concurrent.ExecutionException)?.cause ?: e
                    if (spec.key == DETECTION_GPU_KEY && stop.get() == null) {
                        event("runtime_create_failed", mapOf("key" to spec.key, "error" to cause.toString()))
                        log("runtime create_end key=${spec.key} error=${cause.javaClass.simpleName}")
                        differences += "A24 와 다름: detection_GPU 생성 실패 → 그 runtime 없이 진행 (${cause.javaClass.simpleName})"
                    } else {
                        throw cause
                    }
                }
            }

            // ---- warmup 2 per key (정렬 순서 · 직렬) — 출력 전체 기록 (분류 Softmax 1000 · 탐지 디코드 + raw SHA)
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
                    "softmax_f32le_base64" to outcome.softmax?.let { Base64.getEncoder().encodeToString(floatBytes(it)) },
                )
            }
            log("phase=warmup_end")
            artifacts.save("warmup.json", warmups)
            if (manifest.warmupOnly) {
                // 스모크 S1 (diagnostic): runtime 생성 + warmup 만. 요청 · 공통창 없음.
                log("warmup_only: session ends after warmup")
                artifacts.save("summary.json", mapOf(
                    "status" to "warmup_only", "protocol" to MixreqContract.PROTOCOL, "experiment_id" to manifest.experimentId,
                    "split" to manifest.split, "session_id" to sid, "session_index" to manifest.sessionIndex, "block" to manifest.block,
                    "policy" to manifest.policy, "planned" to 0, "terminal" to 0, "time_scale" to scale,
                    "runtime_keys" to runtimes.keys.sorted(), "detection_gpu_created" to runtimes.containsKey(DETECTION_GPU_KEY),
                    "a24_differences" to differences, "manifest_sha256" to manifestSha, "experiment_ready" to false,
                ) + identity)
                return true
            }

            // ---- host warmup gate (A24 gate: warmup.ready.json → warmup.arm == manifest SHA, ≤ 60 s)
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

            // ---- resident baseline 30 s
            phase = "resident_baseline"
            event("phase_start")
            log("phase=resident_baseline")
            sleepHealthy(scaled(MixreqContract.BASELINE_SECONDS * 1_000_000_000L))
            event("phase_end")

            // ---- start check (등록 §3-2: thermal status ≤ 1 · plugged 0) — A24 와 다름 (A24 = 호스트 AP 게이트)
            phase = "start_check"
            val startSnapshot = snapshot()
            val thermal = (startSnapshot["thermal_status"] as? Number)?.toInt()
            val plugged = (startSnapshot["plugged"] as? Number)?.toInt()
            val passed = thermal != null && thermal <= manifest.startThermalStatusMax && plugged == 0
            artifacts.save("start_check.json", startSnapshot + mapOf("thermal_status_max" to manifest.startThermalStatusMax, "passed" to passed))
            check(passed) { "start_check: thermal_status=$thermal plugged=$plugged" }

            // ---- common window 120 s
            phase = "common_window"
            val start = now()
            commonStartNs = start
            event("common_start", mapOf("scheduled_origin_ns" to start, "window_ns" to scaled(MixreqContract.COMMON_NS), "time_scale" to scale))
            log("common_start origin_ns=$start")
            runWindow(image, start, artifacts)

            // ---- resident cooling 60 s
            phase = "resident_cooling"
            event("phase_start")
            log("phase=resident_cooling")
            sleepHealthy(scaled(MixreqContract.COOLING_SECONDS * 1_000_000_000L))
            event("phase_end")
            val finalRows = manifest.requests.map { detached(rows.getValue(it.id)) }
            artifacts.save("summary.json", mapOf(
                "status" to "completed", "protocol" to MixreqContract.PROTOCOL, "experiment_id" to manifest.experimentId,
                "split" to manifest.split, "session_id" to sid, "session_index" to manifest.sessionIndex, "block" to manifest.block,
                "pair" to manifest.pair, "attempt" to manifest.attempt, "policy" to manifest.policy,
                "planned" to manifest.requests.size, "terminal" to finalRows.count { it["terminal_status"] == "succeeded" },
                "common_start_ns" to start, "common_end_ns" to commonEndNs, "time_scale" to scale,
                "runtime_keys" to runtimes.keys.sorted(), "used_keys" to manifest.usedKeys.sorted(),
                "detection_gpu_created" to runtimes.containsKey(DETECTION_GPU_KEY), "a24_differences" to differences,
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
            samples.shutdownNow()
            for ((laneName, executor) in lanes) {
                // A24 ArrivalRuntimeSetup.closeLane: 그 lane 스레드에서 닫고 5 s 만 기다린다
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

    private fun runWindow(image: File, start: Long, artifacts: ArtifactStore) {
        val requests: List<Request> = manifest.requests
        val policy = manifest.policy
        val waiting = mutableListOf<PolicyStudy.Ticket>() // dispatch executor only
        val busy = mutableMapOf("CPU" to false, "GPU" to false, "NPU" to false) // dispatch executor only
        val done = CountDownLatch(requests.size)
        lateinit var pump: () -> Unit
        pump = {
            while (stop.get() == null) {
                val begin = now()
                val choice = PolicyStudy.choose(policy, waiting, !busy.getValue("CPU"), !busy.getValue("GPU"), !busy.getValue("NPU"))
                event("decision", mapOf("policy" to policy, "waiting" to waiting.size, "selected" to choice?.ticket?.id,
                    "backend" to choice?.backend, "decision_start_ns" to begin, "decision_end_ns" to now()))
                if (choice == null) break
                waiting.remove(choice.ticket)
                busy[choice.backend] = true
                val row = rows.getValue(choice.ticket.id)
                val key = "${choice.ticket.task}_${choice.backend}"
                val dispatched = now()
                update(row, mapOf("selected_backend" to choice.backend, "decision_reason" to choice.reason, "dispatch_ns" to dispatched))
                event("dispatch", mapOf("id" to choice.ticket.id, "key" to key, "dispatch_ns" to dispatched))
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
                        artifacts.save("${choice.ticket.id}.result.json", outcome.record)
                        val persisted = now()
                        update(row, mapOf("persist_complete_ns" to persisted, "terminal_status" to "succeeded"))
                        event("persist_complete", mapOf("id" to choice.ticket.id, "key" to key))
                    } catch (e: Throwable) {
                        stop.compareAndSet(null, "request_failed: $e")
                        update(row, mapOf("terminal_status" to "failed", "reason" to e.toString()))
                        runCatching {
                            artifacts.save("${choice.ticket.id}.failure.json", mapOf("error" to e.toString(), "phase" to phase, "mono_ns" to now()))
                        }
                    } finally {
                        val released = now()
                        update(row, mapOf("worker_release_ns" to released))
                        runCatching { event("worker_release", mapOf("id" to choice.ticket.id, "key" to key)) }
                        runCatching { artifacts.save("${choice.ticket.id}.event.json", detached(row)) }
                            .onFailure { stop.compareAndSet(null, "event_save_failed: $it") }
                        dispatch.execute {
                            val available = now()
                            update(row, mapOf("lane_available_ns" to available))
                            busy[choice.backend] = false
                            try {
                                event("lane_available", mapOf("id" to choice.ticket.id, "key" to key))
                            } finally {
                                done.countDown()
                                pump()
                            }
                        }
                    }
                }
            }
        }
        for (q in requests) {
            val target = start + scaled(q.offsetMs * 1_000_000L)
            arrivals.schedule({
                val actual = now()
                val row = linkedMapOf<String, Any?>(
                    "request_id" to q.id, "ordinal" to q.ordinal, "task_id" to q.task, "priority" to q.priority,
                    "scheduled_arrival_ns" to target, "actual_arrival_ns" to actual,
                    "deadline_ns" to target + scaled(q.deadlineMs * 1_000_000L), "terminal_status" to "unfinished",
                )
                rows[q.id] = row
                event("arrival", mapOf("id" to q.id, "scheduled_arrival_ns" to target, "actual_arrival_ns" to actual))
                dispatch.execute {
                    update(row, mapOf("queue_entry_ns" to now()))
                    waiting.add(PolicyStudy.Ticket(q.id, q.task, q.priority, q.ordinal))
                    event("queue_entry", mapOf("id" to q.id))
                    pump()
                }
            }, maxOf(0L, target - now()), TimeUnit.NANOSECONDS)
        }
        sleepHealthy(scaled(MixreqContract.COMMON_NS))
        val commonEnd = now()
        commonEndNs = commonEnd
        event("common_end", mapOf("common_end_ns" to commonEnd))
        log("common_end end_ns=$commonEnd")
        artifacts.save("common_boundary.json", mapOf(
            "start_ns" to start, "planned_end_ns" to start + scaled(MixreqContract.COMMON_NS), "end_ns" to commonEnd,
            "planned" to requests.size, "time_scale" to scale,
            "rows" to requests.map { q ->
                rows[q.id]?.let(::detached) ?: mapOf("request_id" to q.id,
                    "scheduled_arrival_ns" to start + scaled(q.offsetMs * 1_000_000L), "terminal_status" to "unobserved_arrival")
            },
        ))
        phase = "post_window_drain"
        event("phase_start")
        log("phase=post_window_drain")
        check(done.await(scaled(MixreqContract.DRAIN_SECONDS * 1_000_000_000L), TimeUnit.NANOSECONDS)) { "post-window drain incomplete" }
        healthy()
        event("phase_end")
        log("drain_end")
        artifacts.save("requests.json", requests.map { detached(rows.getValue(it.id)) })
    }

    companion object {
        const val DETECTION_GPU_KEY = "detection_GPU"

        fun floatBytes(values: FloatArray): ByteArray {
            val buffer = java.nio.ByteBuffer.allocate(values.size * 4).order(java.nio.ByteOrder.LITTLE_ENDIAN)
            values.forEach { buffer.putFloat(it) }
            return buffer.array()
        }
    }
}
