package com.example.d1check.benchmarkrunner

import android.app.Activity
import android.app.ActivityManager
import android.content.Intent
import android.content.IntentFilter
import android.os.*
import android.widget.TextView
import android.util.Log
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.util.UUID
import java.util.concurrent.*
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicReference

/** Fixed-work energy collection only. No policy optimization, no simulated inference. */
class EnergyCollectionActivity : Activity() {
    private val cpu = Executors.newSingleThreadExecutor()
    private val gpu = Executors.newSingleThreadExecutor()
    private val setup = Executors.newSingleThreadExecutor()
    private val samples = Executors.newSingleThreadScheduledExecutor()
    private val handler = Handler(Looper.getMainLooper())
    private val stop = AtomicReference<String?>(null)
    private val peak = AtomicLong(0)
    private var progress: EnergyProgress? = null
    private lateinit var root: File
    private lateinit var sid: String
    private var seq = 0L
    private val observed = EnergyObservedState<ProbeTaskAdapter> { now() }
    private var phase: String
        get() = observed.phase
        set(value) { observed.phase = value }
    @Volatile private var done = false
    private val sampler = EnergySamplerGuard(stop,
        { error -> EnergyFailureEvidence.capture(error, sid, phase, "sampler_snapshot_or_event", now()) },
        { evidence -> save("sampler_failure.json", evidence) })
    private val watchdog = Runnable { android.os.Process.killProcess(android.os.Process.myPid()) }
    private fun now() = SystemClock.elapsedRealtimeNanos()
    private fun lane(key: String) = if (key.endsWith("_CPU")) cpu else gpu
    @Synchronized private fun event(kind: String, data: Map<String, Any?> = emptyMap()) {
        progress?.add(ModelProbeArtifacts.json(data + mapOf("kind" to kind, "mono_ns" to now(), "sequence" to seq++,
            "session_id" to sid, "phase" to (data["phase"] ?: phase), "thread_id" to Thread.currentThread().id,
            "thread_name" to Thread.currentThread().name)))
    }
    private fun save(name: String, value: Any) {
        val f = File(root, name); val temp = File(root, "$name.part")
        check(!f.exists() && temp.createNewFile())
        FileOutputStream(temp).use { it.write(ModelProbeArtifacts.json(value).toByteArray(Charsets.UTF_8)); it.fd.sync() }
        check(temp.renameTo(f))
    }
    private fun healthy() {
        check(stop.get() == null && progress?.failure?.get() == null && !Thread.currentThread().isInterrupted) {
            "stopped: ${stop.get()}/${progress?.failure?.get()}"
        }
    }
    private fun snapshot(): Map<String, Any?> {
        val snapshotStart = now()
        val am = getSystemService(ActivityManager::class.java); val mem = ActivityManager.MemoryInfo(); am.getMemoryInfo(mem)
        val debug = Debug.MemoryInfo(); Debug.getMemoryInfo(debug); peak.updateAndGet { maxOf(it, debug.totalPss.toLong() * 1024) }
        val b = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val bm = getSystemService(BatteryManager::class.java); val pm = getSystemService(PowerManager::class.java)
        val current = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CURRENT_NOW)
        val charge = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CHARGE_COUNTER)
        val thermal = pm.currentThermalStatus
        val peakBytes = peak.get(); val interactive = pm.isInteractive
        val reason = V4Gate.reason(mem.availMem, mem.threshold, mem.lowMemory, peakBytes, thermal)
        val plugged = b?.getIntExtra(BatteryManager.EXTRA_PLUGGED, -1)
        val temp = b?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1)
        val level = b?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
        val scale = b?.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
        if (reason != "admit" || plugged != 0 || temp == null || temp !in 0..350 ||
            level == null || level < 20 || scale != 100 || !interactive) stop.compareAndSet(null, "environment/$reason")
        return mapOf("current_raw" to current, "current_valid" to (current != Int.MIN_VALUE),
            "current_nominal_unit" to "uA_API_unverified_device_scale", "voltage_mV" to b?.getIntExtra(BatteryManager.EXTRA_VOLTAGE, -1),
            "charge_counter_raw" to charge, "charge_valid" to (charge != Int.MIN_VALUE), "charge_nominal_unit" to "uAh",
            "plugged" to plugged, "battery_temperature_deci_c" to temp, "battery_level" to level, "thermal_status" to thermal,
            "interactive" to interactive, "avail_bytes" to mem.availMem, "threshold_bytes" to mem.threshold,
            "low_memory" to mem.lowMemory, "peak_pss_bytes" to peakBytes, "admission_reason" to reason,
            "snapshot_start_ns" to snapshotStart, "sensor_read_end_ns" to now()) + observed.snapshot()
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(TextView(this).apply { text = "에너지·열 고정 작업량 수집" })
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        handler.postDelayed(watchdog, EnergyCollectionCore.WATCHDOG_MS)
        setup.execute { run() }
    }
    private fun gate(inputs: File, name: String, manifestHash: String, waitNs: Long = 60_000_000_000) {
        progress!!.flushBeforeGate() // Outside measured load; ready never precedes durable gate evidence.
        save("$name.ready.json", mapOf("manifest_sha256" to manifestHash, "mono_ns" to now()))
        val start = now()
        while (!File(inputs, "$name.arm").exists()) {
            healthy(); EnergyCollectionCore.requireTime(now(), start, waitNs); Thread.sleep(50)
        }
        check(File(inputs, "$name.arm").readText().trim() == manifestHash)
        event("host_gate_accepted", mapOf("gate" to name))
    }
    private fun idle(label: String, seconds: Long) {
        phase = label; event("phase_start"); val start = now()
        while (now() - start < seconds * 1_000_000_000) { healthy(); Thread.sleep(100) }
        event("phase_end")
    }
    private fun run() {
        var failure: String? = null
        try {
            check(intent.action == "com.example.d1check.benchmarkrunner.action.ENERGY_COLLECTION")
            sid = requireNotNull(intent.getStringExtra("session_id")); check(UUID.fromString(sid).toString() == sid)
            val inputs = canonicalProbeInputRoot(filesDir, "arrival-scheduler-inputs", sid)
            val mf = File(inputs, "manifest.json"); val m = JSONObject(mf.readText()); val hash = ProbeModelFile.sha256(mf)
            val calibration = m.optBoolean("state_model_calibration", false)
            val protocol = if (calibration) EnergyStateCalibration.PROTOCOL else EnergyCollectionCore.PROTOCOL
            if (calibration) {
                handler.removeCallbacks(watchdog); handler.postDelayed(watchdog, EnergyStateCalibration.WATCHDOG_MS)
            }
            root = canonicalProbeOutputRoot(filesDir, protocol, sid); check(!root.exists() && root.mkdirs())
            FileOutputStream(File(root, "manifest.json")).use { it.write(mf.readBytes()); it.fd.sync() }
            progress = EnergyProgress(File(root, "progress.jsonl")); event("session_start", mapOf("manifest_sha256" to hash))
            Log.i("D1ENERGY", "runtime_scope_start=$sid")
            check(m.getString("protocol") == protocol && m.getString("session_id") == sid)
            check(m.getLong("maximum_duration_ms") == (if (calibration) EnergyStateCalibration.WATCHDOG_MS else EnergyCollectionCore.WATCHDOG_MS) && !m.getBoolean("experiment_ready"))
            check(m.getString("apk_sha256") == ProbeModelFile.sha256(File(applicationInfo.sourceDir)) && m.getString("device_fingerprint") == Build.FINGERPRINT)
            check(m.getInt("cpu_threads") == 1 && m.getInt("baseline_seconds") == 120 && m.getInt("cooling_seconds") == 180)
            val preparation = m.optJSONObject("temperature_preparation")
            val operational = m.optBoolean("operational_only", false)
            if (calibration) {
                check(operational && m.getString("calibration_version") == "state-regimen-v1")
                check(m.getInt("common_work_seconds") == 600 && m.getInt("work_call_cap") == EnergyStateCalibration.MAX_WORK_CALLS)
                check(m.getInt("cadence_ms") == 250 && m.getString("mode") == "calibration")
                EnergyStateCalibration.validate(EnergyStateCalibration.blocks(m.getString("phase") == "confirmation"))
            }
            check(preparation?.getString("version") == (if (operational) "resident-fixed-preparation-v1" else "resident-ap-preparation-v1") &&
                preparation.getInt("max_wait_seconds") == 360)
            val keys = EnergyCollectionCore.keys(m.getString("pair")); val parallel = m.getString("mode") == "parallel"
            check(calibration || m.getString("mode") in setOf("serial", "parallel"))
            val images = m.getJSONArray("images"); check(images.length() == 1)
            val imageSpec = images.getJSONObject(0); val image = File(inputs, imageSpec.getString("filename"))
            val imageHash = imageSpec.getString("sha256"); check(ProbeModelFile.sha256(image) == imageHash)
            val anchors = File(inputs, "anchors.json")
            samples.scheduleAtFixedRate({ sampler.tick { event("power_sample", snapshot()) } },0,1,TimeUnit.SECONDS)
            val setupStart = now()
            ArrivalRuntimeSetup.initialize(EnergyCollectionCore.KEYS, false, 8, if (calibration) EnergyStateCalibration.MAX_WORK_CALLS + 4 else if (operational) 874 else 872) { key ->
                healthy(); EnergyCollectionCore.requireTime(now(),setupStart,150_000_000_000)
                event("runtime_submit",mapOf("key" to key))
                lane(key).submit {
                    event("runtime_start",mapOf("key" to key)); event("admission", snapshot()); healthy()
                    val spec = ModelProbeManifestParser.parse(m.getJSONObject("models").getJSONObject(key))
                    check(spec.identity.sessionId == sid && spec.target.apkSha256 == m.getString("apk_sha256") && spec.runtime.cpuThreads == 1)
                    val runtime = ProbeTaskAdapter(spec, ProbeModelFile.open(inputs,spec.model),anchors)
                    observed.addRuntime(key, runtime)
                    event("runtime_return",mapOf("key" to key))
                }.get(EnergyCollectionCore.remainingCall(now(),setupStart,150_000_000_000),TimeUnit.NANOSECONDS)
            }
            val warm = mutableListOf<Map<String,Any?>>()
            Log.i("D1ENERGY", "runtime_scope_end=$sid")
            for (key in EnergyCollectionCore.KEYS.sorted()) repeat(2) { i ->
                healthy(); EnergyCollectionCore.requireTime(now(),setupStart,150_000_000_000)
                event("warmup_submit",mapOf("id" to "$key-$i","key" to key))
                val result = lane(key).submit<Map<String,Any?>> {
                    event("warmup_start",mapOf("id" to "$key-$i","key" to key))
                    event("admission",snapshot()); healthy()
                    observed.runtime(key).execute(image,imageHash, diagnosticMark={stage,edge ->
                        event("call_stage",mapOf("id" to "$key-$i","key" to key,"stage" to stage,"edge" to edge))
                    }).also { event("warmup_return",mapOf("id" to "$key-$i","key" to key)) }
                }.get(EnergyCollectionCore.remainingCall(now(),setupStart,150_000_000_000),TimeUnit.NANOSECONDS)
                warm.add(mapOf("key" to key,"result" to result))
            }
            save("warmup.json",warm); phase = "warmup_gate"; gate(inputs,"warmup",hash)
            // Identical technical preparation in BOTH operational arms, independent of sample order.
            for ((label, concurrent) in EnergyCollectionCore.probes(operational, parallel)) {
                phase = label; workload(keys, concurrent, listOf(1,1),image,imageHash,30_000_000_000)
                if (operational && !concurrent) { phase = "serial_probe_gate"; gate(inputs,"serial_probe",hash) }
            }
            phase = "temperature_preparation"; event("phase_start")
            gate(inputs,"probe",hash,preparation.getLong("max_wait_seconds")*1_000_000_000)
            event("phase_end") // Host quality and AP readiness precede the only official baseline.
            idle("resident_baseline",120)
            phase = "baseline_gate"; gate(inputs,"baseline",hash)
            phase = "load"; val commonStart = now()
            if (calibration) calibrationWorkload(keys,image,imageHash,m.getString("phase") == "confirmation",commonStart)
            else workload(keys,parallel,listOf(678,192),image,imageHash,EnergyCollectionCore.LOAD_NS)
            phase = "post_work_wait"; event("phase_start")
            val commonNs = if (calibration) EnergyStateCalibration.COMMON_NS else EnergyCollectionCore.LOAD_NS
            while (now()-commonStart < commonNs) { healthy(); Thread.sleep(100) }
            event("phase_end")
            idle("resident_cooling",180)
            save("summary.json",mapOf("status" to "completed","requests" to (if (calibration) "bounded_by_journal" else 870),"probe" to (if (operational) 4 else 2),"warmup" to 8,"mono_ns" to now()))
        } catch(e: Throwable) {
            failure = e.toString(); stop.compareAndSet(null,failure)
            try { save("session_failure.json", EnergyFailureEvidence.capture(e,sid,phase,"session",now())) }
            catch(recordError: Throwable) { failure = "$failure; failure_record: $recordError" }
            try { event("session_failed",mapOf("error" to failure)) } catch(_: Throwable) {}
        } finally {
            phase = "cleanup"; samples.shutdownNow()
            for ((executor,suffix) in listOf(cpu to "_CPU",gpu to "_GPU")) {
                try { ArrivalRuntimeSetup.closeLane(executor) { observed.laneRuntimes(suffix).forEach { it.close() } } }
                catch(e: Throwable) { failure = "$failure; cleanup: $e" }
            }
            try { event("app_cleanup",mapOf("error" to failure)); progress?.close() } catch(e: Throwable) { failure = "$failure; flush: $e" }
            if (::root.isInitialized) try { save("cleanup.json",mapOf("status" to if(failure==null) "completed" else "failed","error" to failure,"mono_ns" to now(),
                "sampler_failure" to sampler.failure.get(), "sampler_failure_recording_error" to sampler.recordingFailure.get())) } catch(_: Throwable) {}
            done = true; cpu.shutdownNow(); gpu.shutdownNow(); setup.shutdown(); handler.removeCallbacks(watchdog)
            if (!cpu.awaitTermination(1,TimeUnit.SECONDS) || !gpu.awaitTermination(1,TimeUnit.SECONDS)) android.os.Process.killProcess(android.os.Process.myPid())
            runOnUiThread { finish() }
        }
    }
    private fun calibrationWorkload(keys: List<String>, image: File, imageHash: String,
                                    confirmation: Boolean, commonStart: Long) {
        val blocks = EnergyStateCalibration.blocks(confirmation)
        EnergyStateCalibration.validate(blocks)
        event("phase_start", mapOf("calibration_version" to "state-regimen-v1"))
        var nominalOffset = 0L
        for (block in blocks) {
            healthy(); EnergyCollectionCore.requireTime(now(), commonStart, EnergyStateCalibration.COMMON_NS)
            val start = now(); val end = start + block.seconds * 1_000_000_000L
            event("block_start", mapOf("block" to block.id, "keys" to block.lanes.map { keys[it] },
                "nominal_offset_ns" to nominalOffset, "target_seconds" to block.seconds,
                "cadence_ns" to EnergyStateCalibration.CADENCE_NS,
                "max_calls_per_lane" to EnergyStateCalibration.MAX_PER_LANE_PER_BLOCK))
            if (block.lanes.isEmpty()) {
                while (now() < end) { healthy(); Thread.sleep(100) }
            } else {
                val workers = block.lanes.map { index ->
                    val key = keys[index]
                    val activeStart = AtomicLong(0)
                    val future = lane(key).submit<Int> {
                        var count = 0
                        while (now() < end) {
                            healthy()
                            check(count < EnergyStateCalibration.MAX_PER_LANE_PER_BLOCK) { "calibration call cap" }
                            val id = "cal-${block.id}-$index-$count"
                            val dispatch = now(); activeStart.set(dispatch); observed.dispatch(key,id)
                            event("dispatch",mapOf("id" to id,"key" to key,"block" to block.id,
                                "scheduled_arrival_ns" to dispatch,"dispatch_ns" to dispatch))
                            val execution = now(); event("request_start",mapOf("id" to id,"key" to key,"block" to block.id))
                            event("admission",snapshot()); healthy()
                            var a = 0L; var b = 0L
                            val result = observed.runtime(key).execute(image,imageHash,
                                invocationObserver={x,y-> a=x;b=y},
                                diagnosticMark={stage,edge -> event("call_stage",mapOf("id" to id,"key" to key,
                                    "block" to block.id,"stage" to stage,"edge" to edge)) })
                            val ready = now(); event("output_ready",mapOf("id" to id,"key" to key,"block" to block.id))
                            save("$id.result.json",result); val persisted = now(); val release = now()
                            val row = mapOf("id" to id,"key" to key,"block" to block.id,
                                "scheduled_arrival_ns" to dispatch,"dispatch_ns" to dispatch,
                                "execution_start_ns" to execution,"invocation_start_ns" to a,
                                "invocation_end_ns" to b,"output_ready_ns" to ready,
                                "persist_complete_ns" to persisted,"worker_release_ns" to release,
                                "terminal_status" to "succeeded")
                            event("worker_release",row)
                            observed.release(key)
                            val available = now(); event("lane_available",row + mapOf("lane_available_ns" to available))
                            activeStart.set(0)
                            count++
                            val next = start + count * EnergyStateCalibration.CADENCE_NS
                            if (next > now()) Thread.sleep((next-now()+999_999L)/1_000_000L)
                        }
                        count
                    }
                    future to activeStart
                }
                while (workers.any { !it.first.isDone }) {
                    healthy()
                    for ((_,activeStart) in workers) {
                        val started = activeStart.get()
                        if (started != 0L) EnergyCollectionCore.requireTime(now(),started,EnergyCollectionCore.CALL_NS)
                    }
                    check(now()-start < (block.seconds+30L)*1_000_000_000L) { "calibration block timeout" }
                    Thread.sleep(10)
                }
                val counts = workers.map { it.first.get() }
                check(counts.all { it > 0 }) { "empty calibration state" }
                event("block_counts",mapOf("block" to block.id,"counts" to counts))
            }
            event("block_end",mapOf("block" to block.id,"actual_duration_ns" to now()-start))
            nominalOffset += block.seconds * 1_000_000_000L
        }
        check(now()-commonStart < EnergyStateCalibration.COMMON_NS) { "no common-window tail reserve" }
        event("phase_end")
    }
    private fun workload(keys: List<String>, parallel: Boolean, counts: List<Int>, image: File, imageHash: String, budget: Long) {
        val start = now(); val label = phase; event("phase_start")
        val remaining = counts.toMutableList(); val next = mutableListOf(0,0)
        val inflight = mutableMapOf<Int,Pair<Future<Map<String,Any?>>,Long>>()
        val completed = mutableListOf<Map<String,Any?>>()
        while (remaining.any { it>0 } || inflight.isNotEmpty()) {
            healthy(); EnergyCollectionCore.requireTime(now(),start,budget)
            for (i in inflight.keys.toList()) {
                val (f,submitted) = inflight.getValue(i)
                if (f.isDone) {
                    val row = f.get(); val available = now()
                    val full = row + mapOf("lane_available_ns" to available)
                    event("lane_available",full); completed.add(full); inflight.remove(i); observed.release(keys[i])
                } else EnergyCollectionCore.requireTime(now(),submitted,EnergyCollectionCore.CALL_NS)
            }
            for (i in EnergyCollectionCore.selectable(remaining,inflight.keys,parallel)) {
                val key = keys[i]; val n = next[i]++; remaining[i]--; val id = "$label-$i-$n"
                val dispatch = now(); observed.dispatch(key,id)
                event("dispatch",mapOf("id" to id,"key" to key,"scheduled_arrival_ns" to start,"dispatch_ns" to dispatch))
                val future = lane(key).submit<Map<String,Any?>> {
                    val execution = now(); event("request_start",mapOf("id" to id,"key" to key)); event("admission",snapshot()); healthy()
                    var a = 0L; var b = 0L
                    val result = observed.runtime(key).execute(image,imageHash,invocationObserver={x,y-> a=x;b=y},
                        diagnosticMark={stage,edge -> event("call_stage",mapOf("id" to id,"key" to key,"stage" to stage,"edge" to edge)) })
                    val ready = now(); event("output_ready",mapOf("id" to id,"key" to key))
                    save("$id.result.json",result); val persisted = now()
                    val release = now()
                    mapOf("id" to id,"key" to key,"scheduled_arrival_ns" to start,"dispatch_ns" to dispatch,
                        "execution_start_ns" to execution,"invocation_start_ns" to a,"invocation_end_ns" to b,
                        "output_ready_ns" to ready,"persist_complete_ns" to persisted,"worker_release_ns" to release,
                        "priority" to if(i==0) "normal" else "urgent", "terminal_status" to "succeeded").also { event("worker_release",it) }
                }
                inflight[i] = future to dispatch
            }
            Thread.sleep(1) // Same scheduler polling cost in both arms; measured, not subtracted.
        }
        save("$label.requests.json",completed); event("phase_end")
    }
    override fun onDestroy() { if(!done) stop.compareAndSet(null,"lifecycle_cancelled"); super.onDestroy() }
}
