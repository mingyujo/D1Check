package com.example.d1check.benchmarkrunner

import android.app.Activity
import android.app.ActivityManager
import android.content.Intent
import android.content.IntentFilter
import android.os.*
import android.util.Log
import android.widget.TextView
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.util.UUID
import java.util.concurrent.*
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicReference

/** Isolated development experiment. It does not change task-profile-v3/v4 or formal timing. */
class ArrivalSchedulerActivity : Activity() {
    private val setup = Executors.newSingleThreadExecutor()
    private val dispatch = Executors.newSingleThreadExecutor()
    private val cpu = Executors.newSingleThreadExecutor()
    private val gpu = Executors.newSingleThreadExecutor()
    private val arrivals = Executors.newSingleThreadScheduledExecutor()
    private val sampler = Executors.newSingleThreadScheduledExecutor()
    private val handler = Handler(Looper.getMainLooper())
    private val peakPss = AtomicLong(0)
    private val environment = java.util.Collections.synchronizedList(mutableListOf<Map<String, Any?>>())
    private val rows = ConcurrentHashMap<String, MutableMap<String, Any?>>()
    private var root: File? = null
    @Volatile private var failureJournal: ArrivalFailureJournal? = null
    @Volatile private var diagnosticFinished = false
    @Volatile private var setupThread: Thread? = null
    private val watchdog = Runnable {
        failureJournal?.let { journal ->
            journal.requestStop()
            // Never wait for diagnostic fsync on the kill path. Host timeout is still mandatory.
            Thread { journal.bestEffort("watchdog", "timeout") }.apply { isDaemon = true; start() }
            Log.e("D1ARRIVAL", "diagnostic_watchdog_kill; journal may be incomplete")
            android.os.Process.killProcess(android.os.Process.myPid())
            return@Runnable
        }
        root?.let { try { save(it, "watchdog.json", mapOf("reason" to "120_second_bound", "mono_ns" to now())) } catch (_: Throwable) {} }
        android.os.Process.killProcess(android.os.Process.myPid())
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(TextView(this).apply { text = "도착 스케줄링 개발 실험"; textSize = 20f })
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        handler.postDelayed(watchdog, 120_000)
        setup.execute { runSession() }
    }

    private fun runSession() {
        setupThread = Thread.currentThread()
        val adapters = mutableMapOf<String, ProbeTaskAdapter>()
        var failure: String? = null
        var started = false
        var timing: ArrivalTimingDev.Recorder? = null
        var timingComplete = false
        var calibrationRun = false
        val warmupTrace = java.util.Collections.synchronizedList(mutableListOf<Map<String, Any?>>())
        try {
            require(intent.action == "com.example.d1check.benchmarkrunner.action.ARRIVAL_SCHEDULER")
            val sid = requireNotNull(intent.getStringExtra("session_id"))
            require(UUID.fromString(sid).toString() == sid)
            val inputs = canonicalProbeInputRoot(filesDir, "arrival-scheduler-inputs", sid)
            val manifestFile = File(inputs, "manifest.json")
            require(manifestFile.length() in 1..1_048_576)
            val m = JSONObject(manifestFile.readText())
            val protocol = m.getString("protocol")
            val calibration = protocol == ArrivalTimingDev.CALIBRATION_PROTOCOL
            calibrationRun = calibration
            val timingDev = protocol == ArrivalTimingDev.PROTOCOL || calibration
            require(protocol in setOf("arrival-scheduler-v1", ArrivalTimingDev.PROTOCOL, ArrivalTimingDev.CALIBRATION_PROTOCOL) && m.getString("session_id") == sid)
            val diagnostic = m.optString("failure_diagnostic_contract", "").isNotEmpty()
            val setupOnly = diagnostic && m.optString("failure_diagnostic_scope") == "setup_only"
            if (diagnostic) {
                require(calibration && m.getString("failure_diagnostic_contract") == ArrivalFailureJournal.CONTRACT &&
                    m.getBoolean("performance_excluded") && !m.getBoolean("experiment_ready") &&
                    m.getString("failure_diagnostic_scope") in setOf("setup_only", "calls"))
                val early = canonicalProbeOutputRoot(filesDir, protocol, sid)
                require(!early.exists() && early.mkdirs()); root = early
                save(early, "manifest.json", manifestFile.readBytes())
                failureJournal = ArrivalFailureJournal.open(early, sid, ProbeModelFile.sha256(manifestFile), ::now) {
                    Log.e("D1ARRIVAL", it)
                }
                failureJournal!!.mark("session", "start", detail = "scope=${m.getString("failure_diagnostic_scope")}")
            }
            require(m.getString("apk_sha256") == ProbeModelFile.sha256(File(applicationInfo.sourceDir)))
            require(m.getString("device_fingerprint") == Build.FINGERPRINT)
            require(m.getLong("maximum_duration_ms") == 120_000L)
            require(m.getInt("cpu_threads") == 1 && m.getInt("maximum_concurrency") == if (calibration) 1 else 2)
            require(m.getString("memory_contract") == V4Gate.CONTRACT && m.getInt("thermal_gate") == 0)
            val policy = m.getString("policy")
            require(if (calibration) policy == ArrivalTimingDev.CALIBRATION_POLICY else if (timingDev) policy == ArrivalTimingDev.POLICY else
                policy in setOf(ArrivalPolicy.FIFO, ArrivalPolicy.URGENT, ArrivalPolicy.CONDITIONAL, ArrivalPolicy.FIXED))
            require(m.getLong("arrival_lag_limit_ms") in 1..1000)
            val expectedKeys = setOf("classification_CPU", "classification_GPU", "detection_CPU", "detection_GPU")
            val estimates = if (!timingDev) {
                val estimatesObject = m.getJSONObject("estimated_service_ms")
                require(estimatesObject.keys().asSequence().toSet() == expectedKeys)
                expectedKeys.associateWith { estimatesObject.getLong(it).also { value -> require(value in 1..20_000) } }
            } else emptyMap()
            if (timingDev) {
                require(m.getBoolean("development_only") && !m.getBoolean("experiment_ready"))
                val config = m.getJSONObject("timing_estimates")
                require(config.getString("contract") == ArrivalTimingDev.ESTIMATE_CONTRACT)
                val budgets = config.getJSONObject("budgets")
                require(budgets.keys().asSequence().toSet() == expectedKeys)
                val parsed = expectedKeys.associateWith { key ->
                    val b = budgets.getJSONObject(key)
                    require(b.keys().asSequence().toSet() == setOf("decision_to_dispatch_ns", "dispatch_to_start_ns", "start_to_output_ready_ns",
                        "output_ready_to_persist_ns", "persist_to_lane_available_ns"))
                    fun field(name: String): Long? {
                        require(b.has(name))
                        if (b.isNull(name)) return null
                        require(b.get(name) is Int || b.get(name) is Long)
                        return b.getLong(name)
                    }
                    ArrivalTimingDev.Budget(field("dispatch_to_start_ns"), field("start_to_output_ready_ns"),
                        field("output_ready_to_persist_ns"), field("persist_to_lane_available_ns"), field("decision_to_dispatch_ns"))
                }
                val backend = if (calibration) m.getString("calibration_backend") else null
                if (calibration) require(m.getString("execution_purpose") == "boundary_calibration_only" &&
                    m.getString("storage_mode") == "persist_all" && m.getString("observation_contract") == "arrival-phase-observations-v2")
                timing = ArrivalTimingDev.Recorder(::now, parsed, config.getString("version"), config.getString("provenance"),
                    calibrationBackend = backend)
            }
            val recorder = timing
            val modelsObject = m.getJSONObject("models")
            require(modelsObject.keys().asSequence().toSet() == expectedKeys)
            val specs = expectedKeys.associateWith { key -> ModelProbeManifestParser.parse(modelsObject.getJSONObject(key)).also { spec ->
                require(spec.identity.sessionId == sid && spec.target.apkSha256 == m.getString("apk_sha256"))
                require(spec.runtime.cpuThreads == 1 && spec.runtime.xnnpack && spec.runtime.litertVersion == "1.4.2")
                require(key == "${spec.model.task.wireName}_${spec.execution.backend.name}")
            } }
            val imagesJson = m.getJSONArray("images")
            require(imagesJson.length() in 1..24)
            val images = (0 until imagesJson.length()).associate { i ->
                val image = imagesJson.getJSONObject(i)
                val file = contained(inputs, image.getString("filename"), image.getLong("bytes"), image.getString("sha256"))
                image.getString("sample_id") to Pair(file, image.getString("sha256"))
            }
            require(images.size == imagesJson.length())
            val anchors = contained(inputs, "anchors.json", File(inputs, "anchors.json").length(), ProbeTaskAdapter.ANCHORS_SHA256)
            val requestsJson = m.getJSONArray("requests")
            val warmupsJson = m.getJSONArray("warmup_requests")
            require(if (setupOnly) requestsJson.length() == 0 && warmupsJson.length() == 0
                else requestsJson.length() in 1..24 && warmupsJson.length() == 8)
            val requests = (0 until requestsJson.length()).map { requestsJson.getJSONObject(it) }
            val warmups = (0 until warmupsJson.length()).map { warmupsJson.getJSONObject(it) }
            val ids = mutableSetOf<String>()
            var lastOffset = -1L
            for ((ordinal, q) in requests.withIndex()) {
                val id = q.getString("request_id")
                require(UUID.fromString(id).toString() == id && ids.add(id))
                require(q.getString("task_id") in setOf("classification", "detection"))
                require(q.getString("sample_id") in images && q.getString("priority") in setOf("urgent", "normal"))
                val offset = q.getLong("offset_ms")
                require(offset in lastOffset..60_000 && q.getLong("deadline_ms") in 1..60_000)
                require(q.getInt("ordinal") == ordinal)
                lastOffset = offset
            }
            for (q in warmups) {
                require(q.getString("model_key") in expectedKeys && q.getString("sample_id") in images)
                val id = q.getString("request_id")
                require(UUID.fromString(id).toString() == id && ids.add(id))
            }
            require(setupOnly || expectedKeys.all { key -> warmups.count { it.getString("model_key") == key } == 2 })
            if (calibration && !setupOnly) {
                require(requests.size == 4 && requests.map { it.getLong("offset_ms") } == listOf(0L, 5000L, 10000L, 15000L))
                require(requests.map { it.getString("task_id") }.toSet().size == 1 &&
                    requests.map { it.getString("priority") }.toSet().size == 1 &&
                    requests.map { it.getString("sample_id") }.toSet().size == 1)
            }
            val output = root ?: canonicalProbeOutputRoot(filesDir, protocol, sid)
            if (!diagnostic) require(!output.exists() && output.mkdirs())
            root = output
            if (!diagnostic) save(output, "manifest.json", manifestFile.readBytes())
            Log.i("D1ARRIVAL", "session_start=$sid")
            sampler.scheduleAtFixedRate({ try { environment.add(snapshot()) } catch (e: Throwable) {
                environment.add(mapOf("mono_ns" to now(), "error" to e.toString()))
            } }, 0, 500, TimeUnit.MILLISECONDS)
            for (key in expectedKeys.sorted()) {
                val lane = if (key.endsWith("_CPU")) cpu else gpu
                arrivalDiagnosticOperation(failureJournal, "runtime_wait", key) {
                    lane.submit {
                        check(admission("before_runtime_creation", key) == "admit")
                        arrivalDiagnosticOperation(failureJournal, "runtime_create", key) {
                            adapters[key] = ProbeTaskAdapter(specs.getValue(key), ProbeModelFile.open(inputs, specs.getValue(key).model), anchors)
                        }
                    }.get(30, TimeUnit.SECONDS)
                }
            }
            if (setupOnly) {
                failureJournal!!.mark("setup_only", "succeeded")
                return // Explicitly zero warmup/inference requests, never a calibration result.
            }
            for (q in warmups) {
                val key = q.getString("model_key")
                val lane = if (key.endsWith("_CPU")) cpu else gpu
                lane.submit {
                    val image = images.getValue(q.getString("sample_id"))
                    if (!calibration) adapters.getValue(key).execute(image.first, image.second) else {
                        val base = mapOf("request_id" to q.getString("request_id"), "model_key" to key)
                        warmupTrace.add(base + mapOf("kind" to "start", "mono_ns" to now()))
                        var status = "failed"
                        try {
                            arrivalDiagnosticOperation(failureJournal, "warmup", key, q.getString("request_id")) {
                                adapters.getValue(key).execute(image.first, image.second)
                            }
                            status = "succeeded"
                        }
                        finally { warmupTrace.add(base + mapOf("kind" to "end", "mono_ns" to now(), "status" to status)) }
                    }
                }.get(30, TimeUnit.SECONDS)
            }
            require(admission("before_workload", null) == "admit")
            val workloadStart = now()
            started = true
            val waiting = mutableListOf<ArrivalPolicy.Ticket>() // dispatch thread only
            val busy = mutableMapOf("CPU" to false, "GPU" to false)
            val activeCpu = LongArray(1)
            val activeCpuEstimate = LongArray(1)
            val done = CountDownLatch(requests.size)
            val calibrationFailure = AtomicReference<String?>(null)
            val calibrationArrivals = ConcurrentHashMap<String, Map<String, Any?>>()
            lateinit var pump: () -> Unit
            pump = {
                while (!calibration || calibrationFailure.get() == null) {
                    val remainingMs = if (busy.getValue("CPU"))
                        maxOf(0, (activeCpu[0] + activeCpuEstimate[0] - now()) / 1_000_000) else 0
                    val begin = now()
                    val devDecision = recorder?.choose(waiting)
                    val choice = if (devDecision != null) devDecision.first.choice else
                        ArrivalPolicy.choose(policy, waiting, !busy.getValue("CPU"), !busy.getValue("GPU"), remainingMs, estimates)
                    val decisionEnd = now()
                    if (choice == null) break
                    val ticket = choice.ticket
                    waiting.remove(ticket)
                    busy[choice.backend] = true
                    val row = rows.getValue(ticket.id)
                    row["selected_backend"] = choice.backend
                    row["decision_reason"] = choice.reason
                    row["policy_compute_ns"] = decisionEnd - begin
                    devDecision?.let { row["policy_evaluation_ns"] = it.second }
                    row["dispatch_ns"] = recorder?.mark(choice.backend, ticket, ArrivalTimingDev.Phase.ASSIGNED) ?: decisionEnd
                    if (choice.backend == "CPU" && recorder == null) {
                        activeCpu[0] = decisionEnd
                        activeCpuEstimate[0] = estimates.getValue("${ticket.task}_CPU") * 1_000_000
                    }
                    val lane = if (choice.backend == "CPU") cpu else gpu
                    lane.execute {
                        try {
                            val reason = admission("before_invocation", "${ticket.task}_${choice.backend}")
                            if (reason != "admit") {
                                row["terminal_status"] = "rejected"; row["reason"] = reason
                                if (calibration) calibrationFailure.compareAndSet(null, "admission_rejected: $reason")
                            } else {
                                val image = images.getValue(row.getValue("sample_id") as String)
                                row["execution_start_ns"] = recorder?.mark(choice.backend, ticket, ArrivalTimingDev.Phase.EXECUTING) ?: now()
                                val observer: ((Long, Long) -> Unit)? = if (recorder == null) null else { start, end ->
                                    row["inference_start_ns"] = start; row["inference_end_ns"] = end
                                }
                                val result = arrivalDiagnosticOperation(failureJournal, "diagnostic", "${ticket.task}_${choice.backend}", ticket.id) {
                                    adapters.getValue("${ticket.task}_${choice.backend}").execute(image.first, image.second, observer)
                                }
                                val payload = ModelProbeArtifacts.json(result).toByteArray(Charsets.UTF_8)
                                val ready = recorder?.mark(choice.backend, ticket, ArrivalTimingDev.Phase.OUTPUT_READY) ?: now()
                                row["output_ready_ns"] = ready
                                row["inference_ns"] = result["inference_ns"]
                                row["actual_backend"] = result["actual_backend"]
                                row["input_tensor_sha256"] = result["input_tensor_sha256"]
                                row["result_sha256"] = ProbeTaskAdapter.digest(payload)
                                // Urgent response is ready before durable persistence, as in the existing contract.
                                row["completion_ns"] = if (ticket.priority == "urgent") ready else null
                                save(output, "${ticket.id}.result.json", payload)
                                row["persist_complete_ns"] = recorder?.mark(choice.backend, ticket, ArrivalTimingDev.Phase.PERSISTED) ?: now()
                                if (ticket.priority == "normal") row["completion_ns"] = row["persist_complete_ns"]
                                row["late_success"] = (row["completion_ns"] as Long) > (row["deadline_ns"] as Long)
                                row["queue_wait_ns"] = (row["execution_start_ns"] as Long) - (row["queue_entry_ns"] as Long)
                                row["response_ns"] = (row["completion_ns"] as Long) - (row["scheduled_arrival_ns"] as Long)
                                row["actual_arrival_response_ns"] = (row["completion_ns"] as Long) - (row["actual_arrival_ns"] as Long)
                                row["terminal_status"] = "succeeded"
                            }
                        } catch (e: Throwable) {
                            row["terminal_status"] = "failed"; row["reason"] = e.toString()
                            if (calibration) calibrationFailure.compareAndSet(null, "invocation_failed: $e")
                        } finally {
                            row["terminal_ns"] = now()
                            row["worker_release_ns"] = recorder?.mark(choice.backend, ticket, ArrivalTimingDev.Phase.WORKER_RELEASED) ?: now()
                            try { save(output, "${ticket.id}.event.json", ModelProbeArtifacts.json(row).toByteArray()) }
                            catch (e: Throwable) {
                                Log.e("D1ARRIVAL", "event write failed", e)
                                if (calibration) calibrationFailure.compareAndSet(null, "event_write_failed: $e")
                            }
                            if (recorder == null) {
                                done.countDown()
                                dispatch.execute { busy[choice.backend] = false; pump() }
                            } else {
                                dispatch.execute {
                                    row["lane_available_ns"] = recorder.mark(choice.backend, ticket, ArrivalTimingDev.Phase.AVAILABLE)
                                    busy[choice.backend] = false
                                    try { pump() } finally { done.countDown() }
                                }
                            }
                        }
                    }
                }
            }
            for (q in requests) {
                val offset = q.getLong("offset_ms")
                val target = workloadStart + offset * 1_000_000
                arrivals.schedule({
                    val actual = now()
                    val id = q.getString("request_id")
                    val row = linkedMapOf<String, Any?>(
                        "protocol" to protocol, "session_id" to sid, "request_id" to id,
                        "ordinal" to q.getInt("ordinal"), "task_id" to q.getString("task_id"),
                        "priority" to q.getString("priority"), "sample_id" to q.getString("sample_id"),
                        "scheduled_arrival_ns" to target, "actual_arrival_ns" to actual,
                        "arrival_lag_ns" to actual - target,
                        "deadline_ns" to target + q.getLong("deadline_ms") * 1_000_000)
                    rows[id] = row
                    if (calibration) calibrationArrivals[id] = row.toMap() // Immutable arrival facts before dispatch.
                    dispatch.execute {
                        row["queue_entry_ns"] = now()
                        if (calibration) calibrationArrivals.computeIfPresent(id) { _, facts -> facts + ("queue_entry_ns" to row["queue_entry_ns"]) }
                        if (calibration && !recorder!!.isIdle(actual))
                            calibrationFailure.compareAndSet(null, "solo_arrival_while_lane_busy")
                        waiting.add(ArrivalPolicy.Ticket(id, q.getString("task_id"), q.getString("priority"), q.getInt("ordinal")))
                        pump()
                    }
                }, maxOf(0, target - now()), TimeUnit.NANOSECONDS)
            }
            val drained = done.await(100, TimeUnit.SECONDS)
            val end = now()
            if (!drained) failure = "bounded_drain_timeout"
            calibrationFailure.get()?.let { failure = it }
            dispatch.submit {}.get(2, TimeUnit.SECONDS)
            if (recorder?.overflow == true) failure = "decision_trace_overflow"
            timingComplete = drained && failure == null
            val all = requests.map { q ->
                val id = q.getString("request_id")
                if (File(output, "$id.event.json").isFile) rows[id]!!.toMap() else mapOf(
                    "request_id" to id, "task_id" to q.getString("task_id"),
                    "priority" to q.getString("priority"), "sample_id" to q.getString("sample_id"),
                    "scheduled_arrival_ns" to workloadStart + q.getLong("offset_ms") * 1_000_000,
                    "deadline_ns" to workloadStart + (q.getLong("offset_ms") + q.getLong("deadline_ms")) * 1_000_000,
                    "terminal_status" to "unfinished", "reason" to "event_not_committed").let { planned ->
                        if (calibration) ArrivalTimingDev.unfinishedWithArrival(planned, calibrationArrivals[id]) else planned
                    }
            }
            save(output, "requests.json", all)
            save(output, "environment.json", environment.toList())
            val lagLimit = m.getLong("arrival_lag_limit_ms") * 1_000_000
            val lateArrivals = all.count { (it["arrival_lag_ns"] as? Long ?: Long.MAX_VALUE) > lagLimit }
            save(output, "summary.json", mapOf("protocol" to protocol, "session_id" to sid,
                "policy" to policy, "workload_start_ns" to workloadStart, "drain_end_ns" to end,
                "request_count" to requests.size, "terminal_count" to all.count { it["terminal_status"] in setOf("succeeded", "failed", "rejected", "expired") },
                "arrival_lag_limit_ns" to lagLimit, "arrival_lag_exceeded" to lateArrivals,
                "status" to if (failure == null && lateArrivals == 0 && all.all { it["terminal_status"] == "succeeded" }) "completed" else "incomplete",
                "failure" to failure, "sampled_peak_pss_bytes" to peakPss.get()))
            Log.i("D1ARRIVAL", "session_finalized=$sid")
        } catch (e: Throwable) {
            failure = e.toString()
            failureJournal?.stop("setup_or_session_failure: $e") // Before resource close, which may block.
            Log.e("D1ARRIVAL", "session failed", e)
        } finally {
            arrivals.shutdownNow(); sampler.shutdownNow()
            failureJournal?.bestEffort("cleanup", "start", failure)
            for (lane in listOf(cpu, gpu)) {
                try { lane.submit { adapters.filterKeys { it.endsWith(if (lane === cpu) "_CPU" else "_GPU") }.values.forEach { it.close() } }
                    .get(5, TimeUnit.SECONDS) } catch (e: Throwable) {
                    failure = "$failure; close: $e"
                    failureJournal?.bestEffort("runtime_close", "failed", e.toString())
                }
            }
            failureJournal?.bestEffort("cleanup", if (failure == null) "succeeded" else "failed", failure)
            diagnosticFinished = true
            // Bounded in-memory trace: flush outside dispatch/worker critical paths, including failed runs.
            if (calibrationRun) root?.let { output -> try {
                save(output, "warmup_trace.json", synchronized(warmupTrace) { warmupTrace.toList() })
            } catch (e: Throwable) { failure = "$failure; warmup_trace_flush: $e" } }
            timing?.let { trace -> root?.let { output -> try {
                save(output, "decision_trace.json", trace.artifact(timingComplete))
            } catch (e: Throwable) { failure = "$failure; trace_flush: $e" } } }
            root?.let { if (failure != null) try { save(it, "failure.json", mapOf("reason" to failure, "started" to started, "mono_ns" to now())) } catch (_: Throwable) {} }
            root?.let { try { save(it, "cleanup.json", mapOf("status" to if (failure == null) "completed" else "failed",
                "mono_ns" to now(), "error" to failure)) } catch (e: Throwable) { Log.e("D1ARRIVAL", "cleanup receipt failed", e) } }
            cpu.shutdownNow(); gpu.shutdownNow(); dispatch.shutdownNow(); setup.shutdown()
            handler.removeCallbacks(watchdog)
            if (!cpu.awaitTermination(1, TimeUnit.SECONDS) || !gpu.awaitTermination(1, TimeUnit.SECONDS))
                android.os.Process.killProcess(android.os.Process.myPid())
            runOnUiThread { finish() }
        }
    }

    private fun now() = SystemClock.elapsedRealtimeNanos()

    private fun snapshot(): Map<String, Any?> {
        val am = getSystemService(ActivityManager::class.java)
        val info = ActivityManager.MemoryInfo(); am.getMemoryInfo(info)
        val memory = Debug.MemoryInfo(); Debug.getMemoryInfo(memory)
        val pss = memory.totalPss.toLong() * 1024
        peakPss.updateAndGet { maxOf(it, pss) }
        val battery = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        return mapOf("mono_ns" to now(), "avail_bytes" to info.availMem, "threshold_bytes" to info.threshold,
            "low_memory" to info.lowMemory, "pss_bytes" to pss, "observed_peak_pss_bytes" to peakPss.get(),
            "thermal_status" to getSystemService(PowerManager::class.java).currentThermalStatus,
            "battery_temperature_deci_c" to battery?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1),
            "battery_level" to battery?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1))
    }

    private fun admission(stage: String, key: String?): String {
        val state = snapshot()
        val reason = V4Gate.reason(state["avail_bytes"] as Long, state["threshold_bytes"] as Long,
            state["low_memory"] as Boolean, state["observed_peak_pss_bytes"] as Long,
            state["thermal_status"] as Int)
        environment.add(state + mapOf("stage" to stage, "model_key" to key, "admission_reason" to reason))
        failureJournal?.mark("admission", "observed", key, detail = "$stage/$reason: ${ModelProbeArtifacts.json(state)}")
        return reason
    }

    private fun contained(base: File, name: String, length: Long, sha: String): File {
        require(name.matches(Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,126}")) && sha.matches(Regex("[a-f0-9]{64}")))
        val file = File(base, name)
        require(file.canonicalFile.parentFile == base.canonicalFile && file.isFile)
        require(file.length() == length && ProbeModelFile.sha256(file) == sha)
        return file
    }

    private fun save(base: File, name: String, value: Any) = save(base, name, ModelProbeArtifacts.json(value).toByteArray(Charsets.UTF_8))
    private fun save(base: File, name: String, bytes: ByteArray) {
        val file = File(base, name); val part = File(base, "$name.part")
        require(!file.exists() && part.createNewFile())
        FileOutputStream(part).use { it.write(bytes); it.fd.sync() }
        require(part.renameTo(file) && file.readBytes().contentEquals(bytes))
    }

    override fun onDestroy() {
        failureJournal?.let { journal ->
            if (diagnosticFinished) return@let
            journal.requestStop()
            setupThread?.interrupt()
            Thread { journal.bestEffort("lifecycle", "cancelled", "onDestroy") }.apply { isDaemon = true; start() }
        }
        setup.shutdown(); super.onDestroy()
    }
}
