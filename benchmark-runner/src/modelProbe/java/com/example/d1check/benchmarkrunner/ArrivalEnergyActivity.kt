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

/** Isolated, measured 24-arrival path; old ArrivalSchedulerActivity remains unchanged. */
class ArrivalEnergyActivity : Activity() {
    private val activityInstanceId = UUID.randomUUID().toString()
    private val setup = Executors.newSingleThreadExecutor()
    private val dispatch = Executors.newSingleThreadExecutor()
    private val cpu = Executors.newSingleThreadExecutor()
    private val gpu = Executors.newSingleThreadExecutor()
    private val arrivals = Executors.newSingleThreadScheduledExecutor()
    private val samples = Executors.newSingleThreadScheduledExecutor()
    private val handler = Handler(Looper.getMainLooper())
    private val stop = AtomicReference<String?>(null)
    private val peak = AtomicLong(0)
    private val observed = EnergyObservedState<ProbeTaskAdapter> { now() }
    private val rows = ConcurrentHashMap<String, MutableMap<String, Any?>>()
    private var progress: EnergyProgress? = null
    private lateinit var root: File
    private lateinit var sid: String
    private var createdFromSavedState = false
    private var activityCreatedNs = 0L
    private var sequence = 0L
    @Volatile private var finished = false
    @Volatile private var finishRequested = false
    private var phase: String
        get() = observed.phase
        set(value) { observed.phase = value }
    private val sampler = EnergySamplerGuard(stop,
        { e -> EnergyFailureEvidence.capture(e, sid, phase, "arrival_energy_sample", now()) },
        { evidence -> save("sampler_failure.json", evidence) })
    private val watchdog = Runnable { android.os.Process.killProcess(android.os.Process.myPid()) }
    private fun now() = SystemClock.elapsedRealtimeNanos()
    private fun lane(key: String) = if (key.endsWith("_CPU")) cpu else gpu

    private fun lifecycle(callback: String) {
        if (progress == null) return
        try {
            event("activity_lifecycle", mapOf("callback" to callback,
                "activity_instance_id" to activityInstanceId,
                "activity_created_ns" to activityCreatedNs,
                "is_finishing" to isFinishing,
                "is_changing_configurations" to isChangingConfigurations,
                "created_from_saved_state" to createdFromSavedState,
                "finish_requested_by_session" to finishRequested,
                "stop_reason" to stop.get()))
        } catch (error: Throwable) {
            // A journal failure cannot replace the first cancellation or session error.
            Log.w("D1ARRIVALENERGY", "lifecycle journal unavailable: $callback", error)
        }
    }

    @Synchronized private fun event(kind: String, data: Map<String, Any?> = emptyMap()) {
        progress?.add(ModelProbeArtifacts.json(data + mapOf("kind" to kind, "mono_ns" to now(),
            "sequence" to sequence++, "session_id" to sid, "phase" to (data["phase"] ?: phase),
            "thread_id" to Thread.currentThread().id, "thread_name" to Thread.currentThread().name)))
    }
    private fun save(name: String, value: Any) {
        val output = File(root, name); val temp = File(root, "$name.part")
        check(!output.exists() && temp.createNewFile())
        FileOutputStream(temp).use { it.write(ModelProbeArtifacts.json(value).toByteArray(Charsets.UTF_8)); it.fd.sync() }
        check(temp.renameTo(output))
    }
    private fun healthy() {
        check(stop.get() == null && progress?.failure?.get() == null && !Thread.currentThread().isInterrupted) {
            "stopped: ${stop.get()}/${progress?.failure?.get()}"
        }
    }
    private fun snapshot(): Map<String, Any?> {
        val start = now()
        val am = getSystemService(ActivityManager::class.java); val memory = ActivityManager.MemoryInfo(); am.getMemoryInfo(memory)
        val debug = Debug.MemoryInfo(); Debug.getMemoryInfo(debug)
        peak.updateAndGet { maxOf(it, debug.totalPss.toLong() * 1024) }
        val battery = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val bm = getSystemService(BatteryManager::class.java); val pm = getSystemService(PowerManager::class.java)
        val current = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CURRENT_NOW)
        val charge = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CHARGE_COUNTER)
        val thermal = pm.currentThermalStatus
        val reason = V4Gate.reason(memory.availMem, memory.threshold, memory.lowMemory, peak.get(), thermal)
        val plugged = battery?.getIntExtra(BatteryManager.EXTRA_PLUGGED, -1)
        val temperature = battery?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1)
        val level = battery?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
        val scale = battery?.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
        if (reason != "admit" || plugged != 0 || temperature == null || temperature !in 0..350 ||
            level == null || level < 20 || scale != 100 || !pm.isInteractive)
            stop.compareAndSet(null, "environment/$reason")
        return mapOf("current_raw" to current, "current_valid" to (current != Int.MIN_VALUE),
            "current_nominal_unit" to "uA_API_unverified_device_scale",
            "voltage_mV" to battery?.getIntExtra(BatteryManager.EXTRA_VOLTAGE, -1),
            "charge_counter_raw" to charge, "charge_valid" to (charge != Int.MIN_VALUE),
            "charge_nominal_unit" to "uAh", "plugged" to plugged,
            "battery_temperature_deci_c" to temperature, "battery_level" to level,
            "thermal_status" to thermal, "interactive" to pm.isInteractive,
            "avail_bytes" to memory.availMem, "threshold_bytes" to memory.threshold,
            "low_memory" to memory.lowMemory, "peak_pss_bytes" to peak.get(),
            "admission_reason" to reason, "snapshot_start_ns" to start,
            "sensor_read_end_ns" to now()) + observed.snapshot()
    }
    private fun update(row: MutableMap<String, Any?>, fields: Map<String, Any?>) = synchronized(row) { row.putAll(fields) }
    private fun detached(row: MutableMap<String, Any?>) = synchronized(row) { LinkedHashMap(row) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        activityCreatedNs = now()
        createdFromSavedState = savedInstanceState != null
        setContentView(TextView(this).apply { text = "합성 도착 에너지·AP 계측" })
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        handler.postDelayed(watchdog, ArrivalEnergyContract.WATCHDOG_MS)
        setup.execute { runSession() }
    }

    private fun gate(inputs: File, hash: String) {
        phase = "warmup_gate"; progress!!.flushBeforeGate()
        save("warmup.ready.json", mapOf("manifest_sha256" to hash, "mono_ns" to now()))
        val start = now(); val arm = File(inputs, "warmup.arm")
        while (!arm.exists()) {
            healthy(); check(now() - start < ArrivalEnergyContract.GATE_NS) { "warmup gate timeout" }
            Thread.sleep(50)
        }
        check(arm.readText().trim() == hash)
        event("host_gate_accepted", mapOf("gate" to "warmup"))
    }

    private fun runSession() {
        var failure: String? = null
        try {
            check(intent.action == "com.example.d1check.benchmarkrunner.action.ARRIVAL_ENERGY")
            sid = requireNotNull(intent.getStringExtra("session_id")); check(UUID.fromString(sid).toString() == sid)
            val inputs = canonicalProbeInputRoot(filesDir, "arrival-scheduler-inputs", sid)
            val mf = File(inputs, "manifest.json"); check(mf.length() in 1..1_048_576)
            val m = JSONObject(mf.readText()); val hash = ProbeModelFile.sha256(mf)
            root = canonicalProbeOutputRoot(filesDir, ArrivalEnergyContract.PROTOCOL, sid)
            check(!root.exists() && root.mkdirs())
            FileOutputStream(File(root, "manifest.json")).use { it.write(mf.readBytes()); it.fd.sync() }
            progress = EnergyProgress(File(root, "progress.jsonl"))
            event("session_start", mapOf("manifest_sha256" to hash))
            lifecycle("onCreate")
            check(m.getString("protocol") == ArrivalEnergyContract.PROTOCOL && m.getString("session_id") == sid)
            check(!m.getBoolean("experiment_ready") && m.getLong("maximum_duration_ms") == ArrivalEnergyContract.WATCHDOG_MS)
            check(m.getString("apk_sha256") == ProbeModelFile.sha256(File(applicationInfo.sourceDir)) &&
                m.getString("device_fingerprint") == Build.FINGERPRINT && m.getInt("cpu_threads") == 1)
            check(m.getInt("common_window_seconds") == 120 && m.getInt("cooling_seconds") == 60 &&
                m.getInt("resident_baseline_seconds").toLong() == ArrivalEnergyContract.BASELINE_SECONDS)
            check(m.getInt("maximum_concurrency") == 2 && m.getString("memory_contract") == V4Gate.CONTRACT && m.getInt("thermal_gate") == 0)
            val policy = m.getString("policy")
            val apMode = m.optString("start_ap_gate", "")
            check(apMode == "" || apMode == ArrivalStartApGate.VERSION) { "unknown start AP gate" }
            check(policy in setOf(ArrivalPolicy.URGENT, ArrivalPolicy.FIXED, ArrivalRecordedReplay.POLICY))
            val imageSpec = m.getJSONArray("images").also { check(it.length() == 1) }.getJSONObject(0)
            val image = File(inputs, imageSpec.getString("filename")); val imageHash = imageSpec.getString("sha256")
            check(ProbeModelFile.sha256(image) == imageHash)
            val anchors = File(inputs, "anchors.json"); check(ProbeModelFile.sha256(anchors) == ProbeTaskAdapter.ANCHORS_SHA256)
            val specs = m.getJSONObject("models"); check(specs.keys().asSequence().toSet() == EnergyCollectionCore.KEYS)
            val requestJson = m.getJSONArray("requests")
            val requests = (0 until requestJson.length()).map { i -> requestJson.getJSONObject(i).let { q ->
                ArrivalEnergyContract.Request(q.getString("request_id"), q.getInt("ordinal"), q.getString("task_id"),
                    q.getString("priority"), q.getLong("offset_ms"), q.getLong("deadline_ms"))
            } }
            ArrivalEnergyContract.validate(m.getString("scenario"), requests)
            requests.forEach { check(UUID.fromString(it.id).toString() == it.id) }
            val replay = if (policy == ArrivalRecordedReplay.POLICY) {
                check(m.getString("replay_version") == ArrivalRecordedReplay.VERSION)
                requestJson.let { arr -> (0 until arr.length()).map { i -> arr.getJSONObject(i).let { q ->
                    ArrivalRecordedReplay.Entry(q.getString("request_id"), q.getInt("ordinal"),
                        q.getString("task_id"), q.getLong("offset_ms") * 1_000_000L,
                        q.getLong("release_offset_ns"), q.getString("recorded_backend"),
                        q.getString("source_request_id"))
                } } }.also { ArrivalRecordedReplay.validate(it, requests) }.associateBy { it.id }
            } else emptyMap()
            samples.scheduleAtFixedRate({ sampler.tick { event("power_sample", snapshot()) } }, 0, 1, TimeUnit.SECONDS)
            val setupStart = now()
            Log.i("D1ENERGY", "runtime_scope_start=$sid")
            ArrivalRuntimeSetup.initialize(EnergyCollectionCore.KEYS, false, 8, requests.size) { key ->
                healthy(); check(now() - setupStart < ArrivalEnergyContract.SETUP_NS)
                event("runtime_submit", mapOf("key" to key))
                lane(key).submit {
                    event("runtime_start", mapOf("key" to key)); event("admission", snapshot()); healthy()
                    val spec = ModelProbeManifestParser.parse(specs.getJSONObject(key))
                    check(spec.identity.sessionId == sid && spec.target.apkSha256 == m.getString("apk_sha256") && spec.runtime.cpuThreads == 1)
                    observed.addRuntime(key, ProbeTaskAdapter(spec, ProbeModelFile.open(inputs, spec.model), anchors))
                    event("runtime_return", mapOf("key" to key))
                }.get(minOf(ArrivalEnergyContract.CALL_NS, ArrivalEnergyContract.SETUP_NS - (now()-setupStart)), TimeUnit.NANOSECONDS)
            }
            val warmups = mutableListOf<Map<String, Any?>>()
            for (key in EnergyCollectionCore.KEYS.sorted()) repeat(2) { i ->
                healthy(); check(now() - setupStart < ArrivalEnergyContract.SETUP_NS)
                event("warmup_submit", mapOf("key" to key, "index" to i))
                val outcome = lane(key).submit<Map<String, Any?>> {
                    event("warmup_start", mapOf("key" to key, "index" to i)); event("admission", snapshot()); healthy()
                    observed.runtime(key).execute(image, imageHash).also { event("warmup_return", mapOf("key" to key, "index" to i)) }
                }.get(minOf(ArrivalEnergyContract.CALL_NS, ArrivalEnergyContract.SETUP_NS - (now()-setupStart)), TimeUnit.NANOSECONDS)
                warmups.add(mapOf("key" to key, "result" to outcome))
            }
            Log.i("D1ENERGY", "runtime_scope_end=$sid")
            save("warmup.json", warmups); gate(inputs, hash)
            check(stop.get() == null)
            phase = "resident_baseline"; event("phase_start")
            val baselineStart = now()
            while (now()-baselineStart < ArrivalEnergyContract.BASELINE_SECONDS*1_000_000_000) { healthy(); Thread.sleep(100) }
            event("phase_end")
            var startReading: ArrivalStartApGate.Reading? = null
            if (apMode == ArrivalStartApGate.VERSION) {
                phase = "start_ap_gate"
                val ready = now()
                progress!!.flushBeforeGate()
                save("start_ap.ready.json", mapOf("manifest_sha256" to hash, "mono_ns" to ready))
                val approval = File(inputs, "start_ap.arm")
                while (!approval.exists()) {
                    healthy()
                    check(now() - ready < ArrivalStartApGate.WAIT_NS) { "start AP gate timeout; no load" }
                    Thread.sleep(25)
                }
                healthy()
                check(now() - ready < ArrivalStartApGate.WAIT_NS && approval.length() in 1..512) { "late/oversized AP approval" }
                startReading = ArrivalStartApGate.parse(approval.readText(), hash, ready)
            }
            phase = "common_window"; val start = now()
            startReading?.let {
                ArrivalStartApGate.atStart(it, start)
                save("start_ap.accepted.json", mapOf("ap_c" to it.ap, "read_before_ns" to it.before,
                    "read_after_ns" to it.after, "common_start_ns" to start,
                    "read_to_start_ns" to start-it.after, "max_age_ns" to ArrivalStartApGate.MAX_AGE_NS))
            }
            event("common_start", mapOf("scheduled_origin_ns" to start, "window_ns" to ArrivalEnergyContract.COMMON_NS))
            val waiting = mutableListOf<ArrivalPolicy.Ticket>() // dispatch executor only
            val busy = mutableMapOf("CPU" to false, "GPU" to false)
            val done = CountDownLatch(requests.size)
            lateinit var pump: () -> Unit
            pump = {
                while (stop.get() == null) {
                    val begin = now()
                    val choice = if (policy == ArrivalRecordedReplay.POLICY)
                        ArrivalRecordedReplay.choose(waiting, replay, maxOf(0L, begin-start),
                            !busy.getValue("CPU"), !busy.getValue("GPU"))
                    else ArrivalPolicy.choose(policy, waiting, !busy.getValue("CPU"), !busy.getValue("GPU"), 0, emptyMap())
                    event("decision", mapOf("policy" to policy, "waiting" to waiting.size,
                        "selected" to choice?.ticket?.id, "backend" to choice?.backend,
                        "decision_start_ns" to begin, "decision_end_ns" to now()))
                    if (choice == null) break
                    waiting.remove(choice.ticket); observed.setWaiting(waiting.size)
                    busy[choice.backend] = true
                    val row = rows.getValue(choice.ticket.id); val key = "${choice.ticket.task}_${choice.backend}"
                    val dispatched = now(); observed.dispatch(key, choice.ticket.id)
                    update(row, mapOf("selected_backend" to choice.backend, "decision_reason" to choice.reason,
                        "dispatch_ns" to dispatched, "recorded_release_ns" to replay[choice.ticket.id]?.let { start+it.releaseNs },
                        "release_gate_delay_ns" to replay[choice.ticket.id]?.let { dispatched-(start+it.releaseNs) }))
                    event("dispatch", mapOf("id" to choice.ticket.id, "key" to key, "dispatch_ns" to dispatched))
                    lane(key).execute {
                        try {
                            val execution = now(); update(row, mapOf("execution_start_ns" to execution))
                            event("request_start", mapOf("id" to choice.ticket.id, "key" to key))
                            event("admission", snapshot()); healthy()
                            val inferenceStart = now(); update(row, mapOf("host_inference_start_ns" to inferenceStart))
                            event("host_inference_start", mapOf("id" to choice.ticket.id, "key" to key))
                            val outcome = observed.runtime(key).execute(image, imageHash)
                            val inferenceReturn = now(); update(row, mapOf("host_inference_return_ns" to inferenceReturn))
                            event("host_inference_return", mapOf("id" to choice.ticket.id, "key" to key))
                            val ready = now(); update(row, mapOf("output_ready_ns" to ready))
                            event("output_ready", mapOf("id" to choice.ticket.id, "key" to key))
                            save("${choice.ticket.id}.result.json", outcome)
                            val persisted = now(); update(row, mapOf("persist_complete_ns" to persisted,
                                "terminal_status" to "succeeded"))
                            event("persist_complete", mapOf("id" to choice.ticket.id, "key" to key))
                        } catch (e: Throwable) {
                            stop.compareAndSet(null, "request_failed: $e")
                            update(row, mapOf("terminal_status" to "failed", "reason" to e.toString()))
                            try { save("${choice.ticket.id}.failure.json", EnergyFailureEvidence.capture(e,sid,phase,"request",now())) } catch (_: Throwable) {}
                        } finally {
                            val released = now(); update(row, mapOf("worker_release_ns" to released))
                            try { event("worker_release", mapOf("id" to choice.ticket.id, "key" to key)) } catch (_: Throwable) {}
                            try { save("${choice.ticket.id}.event.json", detached(row)) } catch (e: Throwable) { stop.compareAndSet(null, "event_save_failed: $e") }
                            dispatch.execute {
                                val available = now(); update(row, mapOf("lane_available_ns" to available))
                                observed.release(key); busy[choice.backend] = false
                                try { event("lane_available", mapOf("id" to choice.ticket.id, "key" to key)) } finally {
                                    done.countDown(); pump()
                                }
                            }
                        }
                    }
                }
            }
            observed.setWaiting(0)
            for (q in requests) {
                val target = start + q.offsetMs * 1_000_000
                arrivals.schedule({
                    val actual = now()
                    val row = linkedMapOf<String, Any?>("request_id" to q.id, "ordinal" to q.ordinal,
                        "task_id" to q.task, "priority" to q.priority,
                        "source_request_id" to replay[q.id]?.sourceId,
                        "scheduled_arrival_ns" to target, "actual_arrival_ns" to actual,
                        "deadline_ns" to target + q.deadlineMs * 1_000_000,
                        "terminal_status" to "unfinished")
                    rows[q.id] = row
                    event("arrival", mapOf("id" to q.id, "scheduled_arrival_ns" to target,
                        "actual_arrival_ns" to actual))
                    dispatch.execute {
                        update(row, mapOf("queue_entry_ns" to now()))
                        waiting.add(ArrivalPolicy.Ticket(q.id, q.task, q.priority, q.ordinal))
                        observed.setWaiting(waiting.size)
                        event("queue_entry", mapOf("id" to q.id)); pump()
                    }
                }, maxOf(0, target - now()), TimeUnit.NANOSECONDS)
            }
            if (policy == ArrivalRecordedReplay.POLICY) for (entry in replay.values) {
                val target = start + entry.releaseNs
                arrivals.schedule({ dispatch.execute {
                    event("recorded_release_gate", mapOf("id" to entry.id,
                        "source_request_id" to entry.sourceId, "scheduled_ns" to target,
                        "actual_ns" to now()))
                    pump()
                } }, maxOf(0, target-now()), TimeUnit.NANOSECONDS)
            }
            while (now()-start < ArrivalEnergyContract.COMMON_NS) { healthy(); Thread.sleep(100) }
            val commonEnd = now(); event("common_end", mapOf("common_end_ns" to commonEnd))
            save("common_boundary.json", mapOf("start_ns" to start, "planned_end_ns" to start + ArrivalEnergyContract.COMMON_NS,
                "end_ns" to commonEnd,
                "planned" to requests.size, "rows" to requests.map { q -> rows[q.id]?.let(::detached) ?: mapOf(
                    "request_id" to q.id, "scheduled_arrival_ns" to start+q.offsetMs*1_000_000,
                    "terminal_status" to "unobserved_arrival") }))
            phase = "post_window_drain"
            check(done.await(ArrivalEnergyContract.DRAIN_SECONDS, TimeUnit.SECONDS)) { "post-window drain incomplete" }
            healthy()
            val finalRows = requests.map { detached(rows.getValue(it.id)) }
            save("requests.json", finalRows)
            phase = "resident_cooling"; event("phase_start")
            val cool = now(); while (now()-cool < ArrivalEnergyContract.COOLING_SECONDS*1_000_000_000) { healthy(); Thread.sleep(100) }
            event("phase_end")
            save("summary.json", mapOf("status" to "completed", "planned" to requests.size,
                "terminal" to finalRows.count { it["terminal_status"] == "succeeded" },
                "policy" to policy, "scenario" to m.getString("scenario"), "common_start_ns" to start,
                "common_end_ns" to commonEnd, "experiment_ready" to false))
        } catch (e: Throwable) {
            failure = e.toString(); stop.compareAndSet(null, failure)
            if (::root.isInitialized) try { save("session_failure.json", EnergyFailureEvidence.capture(e,sid,phase,"session",now())) } catch (_: Throwable) {}
            try { event("session_failed", mapOf("error" to failure)) } catch (_: Throwable) {}
            Log.e("D1ARRIVALENERGY", "session failed", e)
        } finally {
            phase = "cleanup"; arrivals.shutdownNow(); samples.shutdownNow()
            for ((executor,suffix) in listOf(cpu to "_CPU",gpu to "_GPU")) {
                try { ArrivalRuntimeSetup.closeLane(executor) { observed.laneRuntimes(suffix).forEach { it.close() } } }
                catch(e: Throwable) { failure = "$failure; cleanup: $e" }
            }
            try {
                event("app_cleanup", mapOf("error" to failure))
                finishRequested = true
                lifecycle("finish_requested")
                progress?.close()
            }
            catch(e: Throwable) { failure = "$failure; flush: $e" }
            if (::root.isInitialized) try { save("cleanup.json", mapOf("status" to if(failure==null) "completed" else "failed",
                "error" to failure, "mono_ns" to now(), "sampler_failure" to sampler.failure.get(),
                "sampler_failure_recording_error" to sampler.recordingFailure.get())) } catch (_: Throwable) {}
            finished = true; cpu.shutdownNow(); gpu.shutdownNow(); dispatch.shutdownNow(); setup.shutdown()
            handler.removeCallbacks(watchdog)
            if (!cpu.awaitTermination(1,TimeUnit.SECONDS) || !gpu.awaitTermination(1,TimeUnit.SECONDS))
                android.os.Process.killProcess(android.os.Process.myPid())
            runOnUiThread { finish() }
        }
    }
    override fun onStart() { super.onStart(); lifecycle("onStart") }
    override fun onResume() { super.onResume(); lifecycle("onResume") }
    override fun onPause() { lifecycle("onPause"); super.onPause() }
    override fun onStop() { lifecycle("onStop"); super.onStop() }
    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); lifecycle("onNewIntent") }
    override fun onDestroy() {
        if (!finished) stop.compareAndSet(null,"lifecycle_cancelled")
        lifecycle("onDestroy")
        super.onDestroy()
    }
}
