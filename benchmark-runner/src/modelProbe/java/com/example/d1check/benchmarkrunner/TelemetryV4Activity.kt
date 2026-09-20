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
import java.util.concurrent.atomic.AtomicBoolean

/** Separate bounded resident-runtime probe. No formal experiments or scheduler policies. */
class TelemetryV4Activity : Activity() {
    private val handler = Handler(Looper.getMainLooper())
    private val controller = Executors.newSingleThreadExecutor()
    private val peakPss = AtomicLong(0)
    private var trace: V4Telemetry? = null
    private var output: File? = null
    private val watchdog = Runnable {
        try { output?.let { save(it, "watchdog_failure.json", mapOf("reason" to "120_second_bound")) }
            trace?.let { t -> output?.let { save(it, "watchdog_events.json", t.snapshot()) } }
        } finally { android.os.Process.killProcess(android.os.Process.myPid()) }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setShowWhenLocked(true); setTurnScreenOn(true)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        setContentView(TextView(this).apply { text = "계측 검증 중"; textSize = 20f })
        handler.postDelayed(watchdog, 120000)
        controller.execute { runV4() }
    }

    private fun runV4() {
        val workers = listOf(Executors.newSingleThreadExecutor(), Executors.newSingleThreadExecutor())
        val arrivals = Executors.newSingleThreadScheduledExecutor()
        val sampling = Executors.newSingleThreadScheduledExecutor()
        val adapters = mutableMapOf<String, V4TaskAdapter>()
        val stopAdmissions = AtomicBoolean(false)
        val scopes = linkedMapOf<String, V4Scope>()
        var failure: Throwable? = null
        var workloadStarted = false
        try {
            require(intent.action == "com.example.d1check.benchmarkrunner.action.TELEMETRY_V4")
            val id = requireNotNull(intent.getStringExtra("session_id"))
            require(UUID.fromString(id).toString() == id)
            val root = canonicalProbeOutputRoot(filesDir, "task-profile-v4", id)
            require(!root.exists() && root.mkdirs()) { "Stale v4 session" }; output = root
            val t = V4Telemetry(id); trace = t; t.emit("session_start")
            Log.i("D1V4", "session_start=$id")
            val inputs = canonicalProbeInputRoot(filesDir, "telemetry-v4-inputs", id)
            val m = JSONObject(File(inputs, "manifest.json").readText())
            require(m.getString("protocol") == "task-profile-v4" && m.getInt("schema_version") == 1)
            require(m.getString("session_id") == id && m.getLong("maximum_duration_ms") == 120000L)
            val purpose = m.getString("purpose")
            require(purpose in setOf("telemetry_smoke", "instrumentation_calibration"))
            require(m.getString("device_fingerprint") == Build.FINGERPRINT)
            require(m.getString("apk_sha256") == ProbeModelFile.sha256(File(applicationInfo.sourceDir)))
            require(m.getString("memory_contract") == V4Gate.CONTRACT && m.getInt("thermal_gate") == 0)
            require(m.isNull("deadline_ns"))
            val configuration = m.getString("configuration")
            require(configuration in setOf("lifecycle", "resident_cpu_serial", "resident_corun"))
            val slots = m.getJSONArray("runtimes")
            require(slots.length() == if (configuration == "lifecycle") 1 else 2)
            val requests = m.getJSONArray("requests")
            val warmups = m.getJSONArray("warmup_requests")
            val warmupCount = m.getInt("warmup_per_runtime")
            require(warmupCount in 2..20 && warmups.length() == slots.length() * warmupCount)
            if (purpose == "telemetry_smoke") require(warmupCount == 2 && requests.length() <= 8)
            require(requests.length() in 1..48 && requests.length() + warmups.length() <= 48)
            val ids = mutableSetOf<String>()
            for (a in listOf(warmups, requests)) repeat(a.length()) { i ->
                val q = a.getJSONObject(i); val qid = q.getString("request_id")
                require(UUID.fromString(qid).toString() == qid && ids.add(qid))
                require(q.getString("priority") in setOf("urgent", "normal"))
                require(q.getLong("offset_ms") in 0..60000)
            }
            val images = m.getJSONArray("images")
            val imageMap = (0 until images.length()).associate { i ->
                val im = images.getJSONObject(i); val f = File(inputs, im.getString("filename"))
                require(f.absoluteFile == f.canonicalFile && f.parentFile == inputs && f.isFile)
                require(ProbeModelFile.sha256(f) == im.getString("sha256"))
                im.getString("sample_id") to Pair(f, im.getString("sha256"))
            }
            val models = m.getJSONObject("models")
            val specs = models.keys().asSequence().associateWith { key ->
                ModelProbeManifestParser.parse(models.getJSONObject(key)).also {
                    require(it.identity.sessionId == id && it.target.apkSha256 == m.getString("apk_sha256"))
                    require(it.runtime.cpuThreads == 1 && it.runtime.xnnpack && it.runtime.litertVersion == "1.4.2")
                }
            }
            require(specs.size == slots.length())
            for (key in specs.keys) require((0 until warmups.length()).count { warmups.getJSONObject(it).getString("model_key") == key } == warmupCount)
            if (configuration == "resident_cpu_serial") require(specs.values.all { it.execution.backend == ProbeBackend.CPU })
            if (configuration == "resident_corun") require(specs.values.map { it.execution.backend }.toSet() == setOf(ProbeBackend.CPU, ProbeBackend.GPU))
            if (slots.length() == 2) require(specs.values.map { it.model.task.wireName }.toSet() == setOf("classification", "detection"))
            val runtimeIds = mutableSetOf<String>()
            repeat(slots.length()) { i ->
                val slot = slots.getJSONObject(i); val key = slot.getString("model_key"); val spec = specs.getValue(key)
                val rid = slot.getString("runtime_id")
                require(UUID.fromString(rid).toString() == rid && runtimeIds.add(rid) && key !in scopes)
                val worker = V4Gate.worker(configuration, i)
                require(slot.getInt("worker_id") == worker)
                scopes[key] = V4Scope(t, rid, spec.model.task.wireName, spec.execution.backend.name, worker)
            }
            saveBytes(root, "manifest.json", File(inputs, "manifest.json").readBytes())
            sample(t, "before_runtime_creation", 0)
            sampling.scheduleAtFixedRate({ try { sample(t, "sampled", null) } catch (e: Throwable) {
                t.emit("memory_sample_failed", state = "failed", data = mapOf("error" to e.toString()))
            } }, 0, 500, TimeUnit.MILLISECONDS)
            val lane = Semaphore(if (configuration == "resident_corun") 2 else 1, true)
            for ((key, scope) in scopes) {
                workers[scope.worker].submit {
                    admission(t, scope, "before_runtime_creation")
                    t.emit("runtime_creation_requested", scope)
                    val verified = V4ModelFile.open(inputs, specs.getValue(key).model, scope)
                    if (scope.backend == "CPU") t.emit("delegate_creation_not_applicable", scope)
                    adapters[key] = V4TaskAdapter(specs.getValue(key), verified, File(inputs, "anchors.json"), scope)
                    t.emit("runtime_ready", scope)
                    sample(t, "resident_runtime_count", adapters.size)
                }.get(30, TimeUnit.SECONDS)
            }
            fun execute(q: JSONObject, role: String) {
                val key = q.getString("model_key"); val scope = scopes.getValue(key)
                scope.requestId = q.getString("request_id")
                var status = "failed"
                t.emit("worker_acquisition_start", scope)
                lane.acquire()
                t.emit("worker_dispatch", scope); t.emit("queue_wait_end", scope)
                try {
                    check(!stopAdmissions.get()) { "Session admission stopped after earlier failure" }
                    admission(t, scope, "before_invocation")
                    val image = imageMap.getValue(q.getString("sample_id"))
                    t.emit("active_service_start", scope, data = mapOf("role" to role))
                    val result = adapters.getValue(key).execute(image.first, image.second)
                    val payload = ModelProbeArtifacts.json(result).toByteArray(Charsets.UTF_8)
                    val ready = SystemClock.elapsedRealtimeNanos()
                    t.emit("output_ready", scope, at = ready)
                    saveBytes(root, scope.requestId + ".result.json", payload)
                    val complete = if (q.getString("priority") == "normal") SystemClock.elapsedRealtimeNanos() else ready
                    if (q.getString("priority") == "normal") t.emit("persist_complete", scope, at = complete)
                    t.emit("active_service_end", scope, at = complete, data = mapOf("inference_ns" to result["inference_ns"], "role" to role))
                    status = "succeeded"
                } catch (e: Throwable) {
                    stopAdmissions.set(true)
                    t.emit("request_error", scope, data = mapOf("error" to e.toString()))
                    throw e
                } finally {
                    t.emit("worker_release_start", scope)
                    lane.release()
                    t.emit("worker_release_end", scope)
                    t.emit("request_terminal", scope, status)
                    scope.requestId = null
                }
            }
            repeat(warmups.length()) { i ->
                val q = warmups.getJSONObject(i); val scope = scopes.getValue(q.getString("model_key"))
                val enqueueScope = V4Scope(t, scope.runtimeId, scope.task, scope.backend, scope.worker).apply { requestId = q.getString("request_id") }
                t.emit("request_enqueue", enqueueScope)
                workers[scope.worker].submit { execute(q, "warmup") }.get(30, TimeUnit.SECONDS)
            }
            admission(t, null, "before_workload")
            val start = SystemClock.elapsedRealtimeNanos()
            t.emit("workload_start", at = start); workloadStarted = true
            val done = CountDownLatch(requests.length())
            val errors = java.util.Collections.synchronizedList(mutableListOf<Throwable>())
            repeat(requests.length()) { i ->
                val q = requests.getJSONObject(i); val scope = scopes.getValue(q.getString("model_key"))
                arrivals.schedule({
                    val enqueueScope = V4Scope(t, scope.runtimeId, scope.task, scope.backend, scope.worker).apply { requestId = q.getString("request_id") }
                    t.emit("request_enqueue", enqueueScope, data = mapOf("scheduled_arrival_ns" to start + q.getLong("offset_ms") * 1000000L))
                    workers[scope.worker].execute {
                        try { execute(q, purpose) } catch (e: Throwable) { errors.add(e) } finally { done.countDown() }
                    }
                }, maxOf(0L, start + q.getLong("offset_ms") * 1000000L - SystemClock.elapsedRealtimeNanos()), TimeUnit.NANOSECONDS)
            }
            check(done.await(65, TimeUnit.SECONDS)) { "Bounded workload timeout" }
            check(errors.isEmpty()) { errors.joinToString() }
            t.emit("workload_end")
        } catch (e: Throwable) { failure = e }
        finally {
            arrivals.shutdownNow()
            for ((key, scope) in scopes) {
                try { workers[scope.worker].submit {
                    scope.requestId = null
                    adapters[key]?.let { t ->
                        scope.mark("runtime_close", "start")
                        t.close()
                        scope.mark("runtime_close", "finish")
                    }
                }.get(5, TimeUnit.SECONDS) }
                catch (e: Throwable) { if (failure == null) failure = e else failure?.addSuppressed(e) }
            }
            workers.forEach { it.shutdownNow() }
            sampling.shutdown(); sampling.awaitTermination(2, TimeUnit.SECONDS)
            val root = output; val t = trace
            if (root != null && t != null) {
                try {
                    sample(t, "after_runtime_close", 0)
                    t.emit("session_end", state = if (failure == null) "succeeded" else "failed",
                        data = mapOf("error" to failure?.toString(), "workload_started" to workloadStarted))
                    save(root, "events.json", t.snapshot())
                    save(root, "summary.json", mapOf("protocol" to "task-profile-v4", "session_id" to t.sessionId,
                        "status" to if (failure == null) "succeeded" else "failed", "sampled_peak_pss_bytes" to peakPss.get(),
                        "memory_scope" to "500ms and boundary sampled PSS; not continuous peak", "error" to failure?.toString()))
                    save(root, "provenance.json", mapOf("protocol" to "task-profile-v4", "session_id" to t.sessionId,
                        "files" to root.listFiles()!!.map { mapOf("name" to it.name, "sha256" to ProbeModelFile.sha256(it), "bytes" to it.length()) }))
                    Log.i("D1V4", "session_finalized=${t.sessionId}")
                } catch (e: Throwable) { Log.e("D1V4", "finalization failure", e) }
            }
            handler.removeCallbacks(watchdog)
            if (workers.any { !it.isTerminated && !it.awaitTermination(1, TimeUnit.SECONDS) }) android.os.Process.killProcess(android.os.Process.myPid())
            runOnUiThread { finish() }
        }
    }

    private fun memory(): Map<String, Any?> {
        val begin = SystemClock.elapsedRealtimeNanos()
        val am = getSystemService(ActivityManager::class.java)
        val info = ActivityManager.MemoryInfo(); am.getMemoryInfo(info)
        val pss = Debug.MemoryInfo(); Debug.getMemoryInfo(pss)
        val bytes = pss.totalPss.toLong() * 1024
        peakPss.updateAndGet { maxOf(it, bytes) }
        val battery = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        return mapOf("snapshot_start_ns" to begin, "snapshot_end_ns" to SystemClock.elapsedRealtimeNanos(),
            "avail_bytes" to info.availMem, "threshold_bytes" to info.threshold, "low_memory" to info.lowMemory,
            "memory_class_mib" to am.memoryClass, "large_memory_class_mib" to am.largeMemoryClass,
            "pss_bytes" to bytes, "observed_peak_pss_bytes" to peakPss.get(),
            "thermal_status" to getSystemService(PowerManager::class.java).currentThermalStatus,
            "battery_temperature_deci_c" to battery?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1))
    }
    private fun sample(t: V4Telemetry, label: String, residents: Int?) = t.emit("memory_sample",
        data = memory() + mapOf("label" to label, "resident_count" to residents))
    private fun admission(t: V4Telemetry, scope: V4Scope?, stage: String) {
        val snapshot = memory()
        val reason = V4Gate.reason(snapshot["avail_bytes"] as Long, snapshot["threshold_bytes"] as Long,
            snapshot["low_memory"] as Boolean, snapshot["observed_peak_pss_bytes"] as Long, snapshot["thermal_status"] as Int)
        t.emit("memory_admission", scope, data = snapshot + mapOf("stage" to stage, "contract" to V4Gate.CONTRACT,
            "reserve_bytes" to maxOf(snapshot["threshold_bytes"] as Long, snapshot["observed_peak_pss_bytes"] as Long),
            "decision" to if (reason == "admit") "admit" else "reject", "reason" to reason))
        check(reason == "admit") { "Memory/thermal admission rejected: $reason" }
    }
    private fun save(root: File, name: String, value: Any) = saveBytes(root, name, ModelProbeArtifacts.json(value).toByteArray(Charsets.UTF_8))
    private fun saveBytes(root: File, name: String, bytes: ByteArray) {
        val file = File(root, name)
        require(file.absoluteFile == file.canonicalFile && !file.exists())
        FileOutputStream(file).use { it.write(bytes); it.fd.sync() }
    }
}
