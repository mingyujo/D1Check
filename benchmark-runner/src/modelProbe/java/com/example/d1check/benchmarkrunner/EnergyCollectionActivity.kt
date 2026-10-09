package com.example.d1check.benchmarkrunner

import android.app.Activity
import android.app.ActivityManager
import android.content.Intent
import android.content.IntentFilter
import android.os.*
import android.provider.Settings
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
    private val activityInstanceId = UUID.randomUUID().toString()
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
    private var outputOwned = false
    private var residentIdentification = false
    private var tailObservation = false
    private var sessionControl = EnergySessionControl.HOST_GATED
    private var diagnosticScreen: Triple<Int, Int, Int>? = null
    private var seq = 0L
    private val observed = EnergyObservedState<ProbeTaskAdapter> { now() }
    private var phase: String
        get() = observed.phase
        set(value) { observed.phase = value }
    @Volatile private var done = false
    @Volatile private var finishRequested = false
    private var createdFromSavedState = false
    private val sampler = EnergySamplerGuard(stop,
        { error -> EnergyFailureEvidence.capture(error, sid, phase, "sampler_snapshot_or_event", now()) },
        { evidence -> save("sampler_failure.json", evidence) })
    private val watchdog = Runnable { android.os.Process.killProcess(android.os.Process.myPid()) }
    private fun now() = SystemClock.elapsedRealtimeNanos()
    private fun lifecycle(callback: String) {
        if (sessionControl != EnergySessionControl.DEVICE_AFTER_PROBE || progress == null || done) return
        try {
            event("activity_lifecycle", mapOf("callback" to callback,
                "activity_instance_id" to activityInstanceId,
                "is_finishing" to isFinishing,
                "is_changing_configurations" to isChangingConfigurations,
                "finish_requested_by_session" to finishRequested,
                "created_from_saved_state" to createdFromSavedState,
                "stop_reason" to stop.get()))
        } catch (error: Throwable) {
            // A journal failure must not replace the first cancellation cause.
            Log.w("D1ENERGY", "lifecycle journal unavailable: $callback", error)
        }
    }
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
        // Only the opt-in diagnostic adds device-side settings checks. A missing
        // setting is failure, never a cached host value or a passing sample.
        val screen = diagnosticScreen?.let { expected ->
            val brightness = Settings.System.getInt(contentResolver, Settings.System.SCREEN_BRIGHTNESS, -1)
            val mode = Settings.System.getInt(contentResolver, Settings.System.SCREEN_BRIGHTNESS_MODE, -1)
            val timeout = Settings.System.getInt(contentResolver, Settings.System.SCREEN_OFF_TIMEOUT, -1)
            if (Triple(brightness, mode, timeout) != expected) stop.compareAndSet(null, "environment/screen_settings")
            mapOf("screen_brightness" to brightness, "screen_brightness_mode" to mode,
                "screen_off_timeout_ms" to timeout)
        } ?: emptyMap()
        return mapOf("current_raw" to current, "current_valid" to (current != Int.MIN_VALUE),
            "current_nominal_unit" to "uA_API_unverified_device_scale", "voltage_mV" to b?.getIntExtra(BatteryManager.EXTRA_VOLTAGE, -1),
            "charge_counter_raw" to charge, "charge_valid" to (charge != Int.MIN_VALUE), "charge_nominal_unit" to "uAh",
            "plugged" to plugged, "battery_temperature_deci_c" to temp, "battery_level" to level, "thermal_status" to thermal,
            "interactive" to interactive, "avail_bytes" to mem.availMem, "threshold_bytes" to mem.threshold,
            "low_memory" to mem.lowMemory, "peak_pss_bytes" to peakBytes, "admission_reason" to reason,
            "snapshot_start_ns" to snapshotStart, "sensor_read_end_ns" to now()) + screen + observed.snapshot()
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        createdFromSavedState = savedInstanceState != null
        setContentView(TextView(this).apply { text = "에너지·열 고정 작업량 수집" })
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        handler.postDelayed(watchdog, EnergyCollectionCore.WATCHDOG_MS)
        setup.execute { run() }
    }
    private fun gate(inputs: File, name: String, manifestHash: String, waitNs: Long = 60_000_000_000) {
        progress!!.flushBeforeGate() // Outside measured load; ready never precedes durable gate evidence.
        save("$name.ready.json", mapOf("manifest_sha256" to manifestHash, "mono_ns" to now()))
        if (!EnergySessionControl.hostArmRequired(sessionControl, name)) {
            save("device_continuation.json", mapOf("manifest_sha256" to manifestHash,
                "session_id" to sid, "gate" to name, "mono_ns" to now(),
                "scope" to "diagnostic_only_host_ap_unverified"))
            event("device_gate_continued", mapOf("gate" to name))
            return
        }
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
            tailObservation = m.has("tail_observation_version")
            if (tailObservation) EnergyTailObservation.validate(m) // Before watchdog or output ownership changes.
            residentIdentification = tailObservation || m.has("resident_identification_version")
            check(!residentIdentification || calibration)
            sessionControl = EnergySessionControl.validate(m.optString("session_control", EnergySessionControl.HOST_GATED),
                calibration, m.optBoolean("autonomous_diagnostic_only", false))
            val protocol = if (tailObservation) EnergyTailObservation.PROTOCOL
                else if (residentIdentification) EnergyResidentIdentification.PROTOCOL
                else if (calibration) EnergyStateCalibration.PROTOCOL else EnergyCollectionCore.PROTOCOL
            if (calibration) {
                handler.removeCallbacks(watchdog); handler.postDelayed(watchdog, if (tailObservation) EnergyTailObservation.WATCHDOG_MS else EnergyStateCalibration.WATCHDOG_MS)
            }
            root = canonicalProbeOutputRoot(filesDir, protocol, sid); check(!root.exists() && root.mkdirs())
            outputOwned = true
            FileOutputStream(File(root, "manifest.json")).use { it.write(mf.readBytes()); it.fd.sync() }
            progress = EnergyProgress(File(root, "progress.jsonl")); event("session_start", mapOf("manifest_sha256" to hash))
            if (sessionControl == EnergySessionControl.DEVICE_AFTER_PROBE) {
                event("activity_lifecycle", mapOf("callback" to "onCreate",
                    "activity_instance_id" to activityInstanceId,
                    "created_from_saved_state" to createdFromSavedState,
                    "intent_flags" to intent.flags))
            }
            Log.i("D1ENERGY", "runtime_scope_start=$sid")
            check(m.getString("protocol") == protocol && m.getString("session_id") == sid)
            check(m.getLong("maximum_duration_ms") == (if (tailObservation) EnergyTailObservation.WATCHDOG_MS else if (calibration) EnergyStateCalibration.WATCHDOG_MS else EnergyCollectionCore.WATCHDOG_MS) && !m.getBoolean("experiment_ready"))
            check(m.getString("apk_sha256") == ProbeModelFile.sha256(File(applicationInfo.sourceDir)) && m.getString("device_fingerprint") == Build.FINGERPRINT)
            check(m.getInt("cpu_threads") == 1 && m.getInt("baseline_seconds") == 120 && m.getInt("cooling_seconds") == (if (tailObservation) EnergyTailObservation.COOLING_SECONDS else 180))
            if (sessionControl == EnergySessionControl.DEVICE_AFTER_PROBE) {
                val screen = m.getJSONObject("device_screen_contract")
                diagnosticScreen = Triple(screen.getInt("screen_brightness"),
                    screen.getInt("screen_brightness_mode"), screen.getInt("screen_off_timeout"))
                check(diagnosticScreen == Triple(81, 0, 18_000_000))
                event("device_segment_contract", mapOf("control" to sessionControl,
                    "host_ap_after_probe" to "required_for_eligibility_not_device_verified"))
            }
            val preparation = m.optJSONObject("temperature_preparation")
            val operational = m.optBoolean("operational_only", false)
            val shortTransition = m.optBoolean("short_transition_diagnostic_only", false)
            check(!shortTransition || calibration)
            val identificationProfile = m.optString("identification_profile", "")
            val calibrationBlocks = if (tailObservation) EnergyTailObservation.blocks(identificationProfile)
                else if (residentIdentification) EnergyResidentIdentification.blocks(identificationProfile)
                else if (shortTransition) EnergyStateCalibration.shortTransitionBlocks()
                else EnergyStateCalibration.blocks(m.getString("phase") == "confirmation")
            if (tailObservation) {
                check(!shortTransition)
                EnergyTailObservation.validate(m)
            } else if (residentIdentification) {
                check(operational && !shortTransition && sessionControl == EnergySessionControl.DEVICE_AFTER_PROBE)
                val specified=m.getJSONArray("blocks").let { arr -> (0 until arr.length()).map { i -> arr.getJSONObject(i).let { b ->
                    EnergyStateCalibration.Block(b.getString("id"),b.getJSONArray("lane_indices").let { lanes -> (0 until lanes.length()).map(lanes::getInt) },b.getInt("seconds")) } } }
                EnergyResidentIdentification.validate(m.getString("resident_identification_version"),identificationProfile,specified,m.getInt("work_call_cap"))
                check(m.getString("calibration_version")==EnergyResidentIdentification.VERSION &&
                    m.getInt("common_work_seconds")==EnergyResidentIdentification.commonSeconds(identificationProfile) &&
                    m.getInt("cadence_ms")==250 && m.getString("mode")=="calibration")
            } else if (calibration) {
                check(operational && m.getString("calibration_version") ==
                    (if (shortTransition) "short-transition-diagnostic-v1" else "state-regimen-v1"))
                check(m.getInt("common_work_seconds") == 600 && m.getInt("work_call_cap") == EnergyStateCalibration.MAX_WORK_CALLS)
                check(m.getInt("cadence_ms") == 250 && m.getString("mode") == "calibration")
                EnergyStateCalibration.validate(calibrationBlocks)
                if (shortTransition) {
                    check(sessionControl == EnergySessionControl.DEVICE_AFTER_PROBE &&
                        m.optBoolean("autonomous_diagnostic_only") && m.getString("pair") == "CC_DG" &&
                        m.getString("phase") == "confirmation")
                    val specified = m.getJSONArray("blocks")
                    check(specified.length() == calibrationBlocks.size &&
                        calibrationBlocks.indices.all { i ->
                            val row = specified.getJSONObject(i)
                            val lanes = row.getJSONArray("lane_indices")
                            row.getString("id") == calibrationBlocks[i].id &&
                                row.getInt("seconds") == calibrationBlocks[i].seconds &&
                                (0 until lanes.length()).map(lanes::getInt) == calibrationBlocks[i].lanes
                        })
                }
            }
            check(preparation?.getString("version") == (if (operational) "resident-fixed-preparation-v1" else "resident-ap-preparation-v1") &&
                preparation.getInt("max_wait_seconds") == 360)
            val keys = EnergyCollectionCore.keys(m.getString("pair")); val parallel = m.getString("mode") == "parallel"
            check(calibration || m.getString("mode") in setOf("serial", "parallel"))
            val images = m.getJSONArray("images"); check(images.length() == 1)
            val imageSpec = images.getJSONObject(0); val image = File(inputs, imageSpec.getString("filename"))
            val imageHash = imageSpec.getString("sha256"); check(ProbeModelFile.sha256(image) == imageHash)
            val anchors = File(inputs, "anchors.json")
            samples.scheduleAtFixedRate({ sampler.tick { event("power_sample", snapshot()+mapOf("sample_period_ms" to if (residentIdentification) 900 else 1000)) } },0,if (residentIdentification) 900 else 1000,TimeUnit.MILLISECONDS)
            val setupStart = now()
            ArrivalRuntimeSetup.initialize(EnergyCollectionCore.KEYS, false, 8, if (tailObservation) EnergyTailObservation.workCap(identificationProfile)+4 else if (residentIdentification) EnergyResidentIdentification.workCap(identificationProfile)+4 else if (calibration) EnergyStateCalibration.MAX_WORK_CALLS + 4 else if (operational) 874 else 872) { key ->
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
            var identificationReading: ArrivalStartApGate.Reading? = null
            if (residentIdentification) {
                phase="start_ap_gate"; val ready=now(); progress!!.flushBeforeGate()
                save("start_ap.ready.json",mapOf("manifest_sha256" to hash,"mono_ns" to ready))
                val arm=File(inputs,"start_ap.arm")
                while (!arm.exists()) { healthy(); check(now()-ready<ArrivalStartApGate.WAIT_NS); Thread.sleep(25) }
                check(now()-ready<ArrivalStartApGate.WAIT_NS && arm.length() in 1..512)
                identificationReading=ArrivalStartApGate.parse(arm.readText(),hash,ready,ArrivalStartApGate.DIAGNOSTIC_VERSION)
            }
            phase = "load"; val commonStart = now()
            val commonNs = if (tailObservation) EnergyTailObservation.COMMON_SECONDS*1_000_000_000L
                else if (residentIdentification) EnergyResidentIdentification.commonSeconds(identificationProfile)*1_000_000_000L
                else if (calibration) EnergyStateCalibration.COMMON_NS else EnergyCollectionCore.LOAD_NS
            identificationReading?.let {
                ArrivalStartApGate.atStart(it,commonStart)
                save("start_ap.accepted.json",mapOf("ap_c" to it.ap,"read_before_ns" to it.before,"read_after_ns" to it.after,
                    "common_start_ns" to commonStart,"read_to_start_ns" to commonStart-it.after,"gate_mode" to ArrivalStartApGate.DIAGNOSTIC_VERSION))
                event("identification_common_start",mapOf("start_ns" to commonStart,"window_ns" to commonNs))
            }
            if (calibration) calibrationWorkload(if (residentIdentification) EnergyResidentIdentification.KEYS else keys,image,imageHash,calibrationBlocks,
                m.getString("calibration_version"),commonStart,commonNs)
            else workload(keys,parallel,listOf(678,192),image,imageHash,EnergyCollectionCore.LOAD_NS)
            phase = "post_work_wait"; event("phase_start")
            while (now()-commonStart < commonNs) { healthy(); Thread.sleep(100) }
            event("phase_end")
            if (residentIdentification) event("identification_common_end",mapOf("start_ns" to commonStart,"planned_end_ns" to commonStart+commonNs,"end_ns" to now()))
            idle("resident_cooling",if (tailObservation) EnergyTailObservation.COOLING_SECONDS.toLong() else 180)
            save("summary.json",mapOf("status" to "completed","requests" to (if (calibration) "bounded_by_journal" else 870),"probe" to (if (operational) 4 else 2),"warmup" to 8,"mono_ns" to now(),
                "session_control" to sessionControl,"formal_confirmation" to (sessionControl == EnergySessionControl.HOST_GATED)))
        } catch(e: Throwable) {
            failure = e.toString(); stop.compareAndSet(null,failure)
            try { if (outputOwned) save("session_failure.json", EnergyFailureEvidence.capture(e,sid,phase,"session",now())) }
            catch(recordError: Throwable) { failure = "$failure; failure_record: $recordError" }
            try { event("session_failed",mapOf("error" to failure)) } catch(_: Throwable) {}
        } finally {
            phase = "cleanup"; samples.shutdownNow()
            for ((executor,suffix) in listOf(cpu to "_CPU",gpu to "_GPU")) {
                try { ArrivalRuntimeSetup.closeLane(executor) { observed.laneRuntimes(suffix).forEach { it.close() } } }
                catch(e: Throwable) { failure = "$failure; cleanup: $e" }
            }
            finishRequested = true
            try {
                event("app_cleanup",mapOf("error" to failure))
                if (sessionControl == EnergySessionControl.DEVICE_AFTER_PROBE) {
                    event("activity_lifecycle",mapOf("callback" to "finish_requested",
                        "activity_instance_id" to activityInstanceId,"stop_reason" to stop.get()))
                }
                progress?.close()
            } catch(e: Throwable) { failure = "$failure; flush: $e" }
            if (outputOwned) try { save("cleanup.json",mapOf("status" to if(failure==null) "completed" else "failed","error" to failure,"mono_ns" to now(),
                "sampler_failure" to sampler.failure.get(), "sampler_failure_recording_error" to sampler.recordingFailure.get())) } catch(_: Throwable) {}
            done = true; cpu.shutdownNow(); gpu.shutdownNow(); setup.shutdown(); handler.removeCallbacks(watchdog)
            if (!cpu.awaitTermination(1,TimeUnit.SECONDS) || !gpu.awaitTermination(1,TimeUnit.SECONDS)) android.os.Process.killProcess(android.os.Process.myPid())
            runOnUiThread { finish() }
        }
    }
    private fun calibrationWorkload(keys: List<String>, image: File, imageHash: String,
                                    blocks: List<EnergyStateCalibration.Block>, version: String, commonStart: Long, commonNs: Long) {
        if (!residentIdentification) EnergyStateCalibration.validate(blocks)
        event("phase_start", mapOf("calibration_version" to version))
        var nominalOffset = 0L
        for (block in blocks) {
            healthy(); EnergyCollectionCore.requireTime(now(), commonStart, commonNs)
            val plannedStart=commonStart+nominalOffset
            while (residentIdentification && now()<plannedStart) { healthy(); Thread.sleep(10) }
            val start = now(); val end = (if (residentIdentification) plannedStart else start)+block.seconds * 1_000_000_000L
            check(!residentIdentification || start<end) { "missed registered block; no timeline shift" }
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
                            check(count < (if (residentIdentification) block.seconds*4 else EnergyStateCalibration.MAX_PER_LANE_PER_BLOCK)) { "calibration call cap" }
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
        finishCalibrationWindow(blocks,commonStart,commonNs)
    }
    private fun finishCalibrationWindow(blocks: List<EnergyStateCalibration.Block>, commonStart: Long, commonNs: Long) {
        if (tailObservation) EnergyTailObservation.requireCommonEnd(blocks,now()-commonStart,commonNs)
        else check(now()-commonStart < commonNs) { "no common-window tail reserve" }
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
    override fun onStart() { super.onStart(); lifecycle("onStart") }
    override fun onResume() { super.onResume(); lifecycle("onResume") }
    override fun onPause() { lifecycle("onPause"); super.onPause() }
    override fun onStop() { lifecycle("onStop"); super.onStop() }
    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); lifecycle("onNewIntent") }
    override fun onDestroy() {
        if (!done) stop.compareAndSet(null,"lifecycle_cancelled")
        lifecycle("onDestroy")
        super.onDestroy()
    }
}
