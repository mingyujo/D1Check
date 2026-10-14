package com.example.d1check.benchmarkrunner

import android.app.Activity
import android.app.ActivityManager
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Build
import android.os.Bundle
import android.os.Debug
import android.os.PowerManager
import android.os.SystemClock
import android.util.Log
import android.widget.TextView
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CompletableFuture
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/** Explicit new entry point. Merely building this activity does not admit any device/session. */
class A24PreparationActivity : Activity() {
    private val setup = Executors.newSingleThreadExecutor()
    private val dispatch = Executors.newSingleThreadScheduledExecutor()
    private val cpu = Executors.newSingleThreadExecutor()
    private val gpu = Executors.newSingleThreadExecutor()
    private val sensor = Executors.newSingleThreadScheduledExecutor()
    private val failure = AtomicReference<String?>(null)
    private val rows = ConcurrentHashMap<String,MutableMap<String,Any?>>()
    private val adapters = ConcurrentHashMap<String,ProbeTaskAdapter>()
    private val availability = ConcurrentHashMap<String,CompletableFuture<Unit>>()
    private val lock = Any()
    private var sequence = 0L
    private var origin = 0L
    private var finished = false
    private var minimumBatteryPercent = 20
    private val mainHandler = android.os.Handler(android.os.Looper.getMainLooper())
    private val watchdog = Runnable {
        failure.compareAndSet(null,"hard_timeout")
        try { event("hard_timeout") } catch(_:Throwable) { }
        android.os.Process.killProcess(android.os.Process.myPid())
    }
    private lateinit var output: File
    private lateinit var inputRoot: File
    private lateinit var manifest: A24PreparationManifest
    private lateinit var scheduler: A24PreparationScheduler
    private lateinit var journal: FileOutputStream
    private fun now() = SystemClock.elapsedRealtimeNanos()
    private fun lane(key: String) = if(key.endsWith("CPU")) cpu else gpu
    private fun healthy() { check(failure.get() == null) { failure.get().orEmpty() } }

    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        setContentView(TextView(this).apply { text = "A24 opt-in measurement preparation runner; device admission is required." })
        // No implicit restart or automatic fallback to an old measurement protocol.
        if(state != null || intent.getStringExtra("a24_protocol") != A24PreparationContract.PROTOCOL ||
            intent.getBooleanExtra("a24_execute_authorized",false) != true) { finish(); return }
        val sid = intent.getStringExtra("session_id") ?: run { finish(); return }
        try { require(UUID.fromString(sid).toString() == sid) } catch(_:Throwable) { finish(); return }
        inputRoot = File(filesDir,"a24_laptop_inputs/$sid").canonicalFile
        mainHandler.postDelayed(watchdog,1_200_000L)
        setup.execute { runSession(sid) }
    }
    private fun event(kind: String, data: Map<String,Any?> = emptyMap()) = synchronized(lock) {
        if(!::journal.isInitialized) return@synchronized
        val record = data+mapOf("kind" to kind,"mono_ns" to now(),"session_id" to manifest.sessionId,
            "sequence" to sequence++,"thread_name" to Thread.currentThread().name)
        journal.write((ModelProbeArtifacts.json(record)+"\n").toByteArray(Charsets.UTF_8))
        journal.flush()
    }
    private fun set(row: MutableMap<String,Any?>, values: Map<String,Any?>) = synchronized(row) { row.putAll(values) }
    private fun detached(row: MutableMap<String,Any?>): Map<String,Any?> = synchronized(row) { LinkedHashMap(row) }
    private fun write(name: String, value: Any) {
        val target = File(output,name); val part = File(output,"$name.part")
        check(!target.exists() && part.createNewFile())
        FileOutputStream(part).use { it.write(ModelProbeArtifacts.json(value).toByteArray()); it.flush(); it.fd.sync() }
        check(part.renameTo(target))
        check(target.readBytes().isNotEmpty())
    }
    private fun batterySample() {
        val before = now()
        val battery = registerReceiver(null,IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val bm = getSystemService(BatteryManager::class.java)
        val pm = getSystemService(PowerManager::class.java)
        val am = getSystemService(ActivityManager::class.java)
        val memory = ActivityManager.MemoryInfo().also { am.getMemoryInfo(it) }
        val debug = Debug.MemoryInfo().also { Debug.getMemoryInfo(it) }
        val current = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CURRENT_NOW)
        val charge = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CHARGE_COUNTER)
        val thermal = if(Build.VERSION.SDK_INT >= 29) pm.currentThermalStatus else -1
        val gate = if(thermal >= 0) V4Gate.reason(memory.availMem,memory.threshold,memory.lowMemory,
            debug.totalPss.toLong()*1024,thermal) else "thermal_API_unavailable"
        val after = now()
        val plugged = battery?.getIntExtra(BatteryManager.EXTRA_PLUGGED,-1)
        val temperature = battery?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE,-1)
        val level = battery?.getIntExtra(BatteryManager.EXTRA_LEVEL,-1)
        val scale = battery?.getIntExtra(BatteryManager.EXTRA_SCALE,-1)
        event("sensor_sample",mapOf("read_start_ns" to before,"read_end_ns" to after,"reported_at_ns" to after,
            "current_raw" to if(current == Int.MIN_VALUE) null else current,"current_unit" to "uA_API_DEVICE_UNVERIFIED",
            "voltage_raw" to battery?.getIntExtra(BatteryManager.EXTRA_VOLTAGE,-1),"voltage_unit" to "mV",
            "charge_counter_raw" to if(charge == Int.MIN_VALUE) null else charge,"charge_unit" to "uAh_API_DEVICE_UNVERIFIED",
            "battery_temperature_deci_c" to battery?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE,-1),
            "battery_level" to battery?.getIntExtra(BatteryManager.EXTRA_LEVEL,-1),
            "battery_scale" to battery?.getIntExtra(BatteryManager.EXTRA_SCALE,-1),
            "plugged" to battery?.getIntExtra(BatteryManager.EXTRA_PLUGGED,-1),
            "thermal_status" to thermal,"interactive" to pm.isInteractive,
            "ap_c" to null,"ap_source" to "host_HAL_required","cache_age_ns" to null,
            "peak_pss_bytes" to debug.totalPss.toLong()*1024,"memory_gate" to gate))
        if(gate != "admit" || !pm.isInteractive || plugged != 0 || temperature == null || temperature !in 0..350 ||
            !manifest.batteryAdmitted(level,scale)) failure.compareAndSet(null,"safety/$gate")
    }
    private fun runSession(sid: String) {
        try {
            val source = A24PreparationManifest.safeFile(inputRoot,"session_manifest.json")
            val manifestHash = ProbeModelFile.sha256(source)
            manifest = A24PreparationManifest.parse(JSONObject(source.readText()))
            require(manifest.sessionId == sid)
            val m = manifest.json
            val planHash = manifest.exactPlanSha256()
            minimumBatteryPercent = manifest.minimumBatteryPercent()
            require(m.getBoolean("execution_authorized") && !m.getBoolean("mock"))
            require(m.getString("device_status") == "DEVICE_APPROVED_FOR_NEW_CONTRACT")
            require(m.getString("device_fingerprint") == Build.FINGERPRINT)
            require(m.getString("apk_sha256") == ProbeModelFile.sha256(File(applicationInfo.sourceDir)))
            require(m.getInt("cpu_threads") == 1 && m.getString("target_model") == Build.MODEL)
            require(m.getString("runtime_scope") == "C_CPU_C_GPU_D_CPU_D_GPU_COMMON_RESIDENT_V1")
            require(m.getInt("warmups_per_runtime") == 2)
            val specs = m.getJSONObject("models")
            require(specs.keys().asSequence().toSet() == A24PreparationContract.RUNTIME_KEYS.toSet())
            val allInputs = manifest.inputs.values.toList()
            // Idle instrumentation still requires one separately approved warmup input binding.
            val warmup = m.getJSONObject("warmup_input")
            val warmupFile = A24PreparationManifest.safeFile(inputRoot,warmup.getString("input_file"))
            val warmupHash = warmup.getString("input_sha256")
            require(ProbeModelFile.sha256(warmupFile) == warmupHash)
            allInputs.forEach { spec -> require(ProbeModelFile.sha256(A24PreparationManifest.safeFile(inputRoot,spec.filename)) == spec.sha256) }
            val anchors = A24PreparationManifest.safeFile(inputRoot,"anchors.json")
            require(ProbeModelFile.sha256(anchors) == ProbeTaskAdapter.ANCHORS_SHA256)
            scheduler = A24PreparationScheduler(manifest.prescription,manifest.requests)
            output = File(filesDir,"a24_laptop_results/$sid").canonicalFile
            check(!output.exists() && output.mkdirs()) { "session output already exists; no restart" }
            journal = FileOutputStream(File(output,"events.jsonl"),false)
            write("session_manifest.json",m)
            write("identity.json",mapOf("session_id" to sid,"plan_sha256" to planHash,"fingerprint" to Build.FINGERPRINT,
                "manifest_sha256" to manifestHash,"process_id" to android.os.Process.myPid(),
                "apk_sha256" to m.getString("apk_sha256"),"source_commit" to m.getString("source_commit"),
                "evidence_level" to "DEVICE_RUN_PENDING_HOST_VALIDATION","experiment_ready" to false))
            sensor.scheduleAtFixedRate({ try { batterySample() } catch(e:Throwable) { failure.compareAndSet(null,"sensor/$e") } },0,
                m.getLong("sensor_period_ms").also { require(it in 100..2000) },TimeUnit.MILLISECONDS)
            val residents = if(m.getString("resident_mode") == "NONE") emptyList() else A24PreparationContract.RUNTIME_KEYS.sorted()
            require(m.getString("resident_mode") in setOf("NONE","STANDARD"))
            require(m.getString("resident_mode") != "NONE" || manifest.prescription.recipe == "IDLE")
            for(key in residents) {
                healthy()
                val spec = ModelProbeManifestParser.parse(specs.getJSONObject(key))
                require(spec.identity.sessionId == sid && spec.target.apkSha256 == m.getString("apk_sha256") &&
                    spec.target.buildFingerprint == Build.FINGERPRINT && spec.runtime.cpuThreads == 1 && spec.runtime.litertVersion == "1.4.2")
                A24PreparationContract.validateRuntimeMapping(key,spec.model.task.wireName,spec.execution.backend.name)
                event("runtime_submit",mapOf("key" to key))
                lane(key).submit {
                    adapters[key] = ProbeTaskAdapter(spec,ProbeModelFile.open(inputRoot,spec.model),anchors)
                    event("runtime_ready",mapOf("key" to key))
                }.get(120,TimeUnit.SECONDS)
            }
            for(key in residents) repeat(2) { index ->
                healthy()
                val tensor = if(key.startsWith("C")) warmup.getString("c_tensor_sha256") else warmup.getString("d_tensor_sha256")
                val result = lane(key).submit<Map<String,Any?>> {
                    adapters.getValue(key).execute(warmupFile,warmupHash,expectedInputTensorSha256 = tensor)
                }.get(30,TimeUnit.SECONDS)
                require(result["input_tensor_sha256"] == tensor)
                write("warmup_${key}_$index.json", result)
                event("warmup_result",mapOf("key" to key,"index" to index,"input_tensor_sha256" to tensor))
            }
            // Host supplies the real AP history and frozen initial condition approval after preparation.
            val readyAt = now()
            write("ready.json",mapOf("session_id" to sid,"plan_sha256" to planHash,"ready_ns" to readyAt,
                "required_prestart_ap_history_ns" to 60_000_000_000L,"device_status" to "WAITING_HOST_AP_GATE"))
            val approval = File(inputRoot,"start_approval.json")
            while(!approval.isFile) { healthy(); check(now()-readyAt < 600_000_000_000L); Thread.sleep(100) }
            val approved = JSONObject(approval.readText())
            require(approved.getString("session_id") == sid && approved.getString("plan_sha256") == planHash)
            require(approved.getBoolean("admitted") && approved.getBoolean("sixty_second_ap_history_checked"))
            require(approved.getLong("history_start_ns") >= readyAt &&
                approved.getLong("read_before_ns")-approved.getLong("history_start_ns") >= 60_000_000_000L)
            require(approved.getLong("read_before_ns") >= readyAt && approved.getLong("read_after_ns") <= now())
            require(now()-approved.getLong("read_after_ns") <= 10_000_000_000L)
            require(approved.getString("frozen_gate_sha256").matches(Regex("[0-9a-f]{64}")))
            origin = now()
            event("common_start",mapOf("origin_ns" to origin,"planned_requests" to manifest.requests.size,"plan_sha256" to planHash))
            for(q in manifest.requests) {
                val row = linkedMapOf<String,Any?>("request_id" to q.id,"ordinal" to q.ordinal,"task" to q.task,"group" to q.group,
                    "scheduled_arrival_ns" to origin+q.arrivalNs,"deadline_ns" to origin+q.deadlineNs,"terminal_status" to "UNFINISHED")
                rows[q.id] = row
                dispatch.schedule({
                    val actual = now()
                    set(row,mapOf("actual_arrival_ns" to actual))
                    event("arrival",mapOf("request_id" to q.id,"scheduled_arrival_ns" to origin+q.arrivalNs,"actual_arrival_ns" to actual))
                    scheduler.enqueue(q.id,actual-origin)
                    val queued = now(); set(row,mapOf("queue_entry_ns" to queued))
                    event("queue_entry",mapOf("request_id" to q.id,"queue_entry_ns" to queued))
                    pump()
                },maxOf(0,origin+q.arrivalNs-now()),TimeUnit.NANOSECONDS)
            }
            dispatch.schedule({
                scheduler.stopDispatch()
                scheduler.wait?.let { waiting ->
                    val ended = scheduler.endWait(maxOf(now()-origin,waiting.endNs))
                    event("wait_end",waitData(ended)+mapOf("actual_end_ns" to now(),"cut_by_service_stop" to true))
                }
                event("dispatch_stop",mapOf("planned_stop_ns" to origin+A24PreparationContract.SERVICE_NS,
                    "waiting" to scheduler.waiting(),"owners" to scheduler.owners()))
                write("service_boundary.json",mapOf("planned_requests" to manifest.requests.size,
                    "rows" to manifest.requests.map { detached(rows.getValue(it.id)) },"boundary_ns" to now()))
            },maxOf(0,origin+A24PreparationContract.SERVICE_NS-now()),TimeUnit.NANOSECONDS)
            while(now()-origin < A24PreparationContract.LOGGING_NS) { Thread.sleep(100); healthy() }
            event("logging_end",mapOf("planned_sensor_end_ns" to origin+A24PreparationContract.LOGGING_NS))
            // Wait for each actual worker-return marker AND its dispatch AVAILABLE callback.
            drain()
            write("requests.json",manifest.requests.map { detached(rows.getValue(it.id)) })
            write("summary.json",mapOf("status" to "COMPLETED_PENDING_HOST_VALIDATION","planned_requests" to manifest.requests.size,
                "started_requests" to scheduler.dispatchCount(),"common_start_ns" to origin,"experiment_ready" to false,
                "unfinished" to rows.values.count { detached(it)["terminal_status"] == "UNFINISHED" }))
        } catch(e:Throwable) {
            failure.compareAndSet(null,e.toString())
            Log.e("D1A24PREP","session failed; no automatic retry",e)
            if(::output.isInitialized) try {
                event("session_failure",mapOf("error" to e.toString()))
                write("failure.json",mapOf("status" to "FAILED","reason" to e.toString()))
            } catch(_:Throwable) { }
        } finally {
            var cleanupFailure: Throwable? = null
            sensor.shutdown(); sensor.awaitTermination(5,TimeUnit.SECONDS)
            try {
                if(::scheduler.isInitialized) dispatch.submit { scheduler.stopDispatch() }.get(5,TimeUnit.SECONDS)
                drain()
                for(worker in listOf(cpu,gpu)) worker.submit {
                    adapters.filterKeys { lane(it) === worker }.values.forEach { it.close() }
                }.get(30,TimeUnit.SECONDS)
                dispatch.submit {}.get(5,TimeUnit.SECONDS)
            } catch(e:Throwable) { cleanupFailure = e; failure.compareAndSet(null,"drain_or_close/$e") }
            if(::output.isInitialized) try {
                if(cleanupFailure == null && !File(output,"requests.json").exists())
                    write("requests.json",manifest.requests.map { q -> rows[q.id]?.let(::detached) ?: mapOf(
                        "request_id" to q.id,"ordinal" to q.ordinal,"terminal_status" to "UNFINISHED") })
                write("cleanup.json",mapOf("status" to if(cleanupFailure == null) "DRAINED" else "DRAIN_FAILED",
                    "error" to cleanupFailure?.toString(),"session_failure" to failure.get(),
                    "actual_return_confirmed" to (cleanupFailure == null)))
            } catch(e:Throwable) { failure.compareAndSet(null,"cleanup_record/$e") }
            if(cleanupFailure == null) {
                cpu.shutdown(); gpu.shutdown(); dispatch.shutdown()
                if(::journal.isInitialized) synchronized(lock) { journal.flush(); journal.fd.sync(); journal.close() }
                if(::output.isInitialized) write("journal_closed.json",mapOf("status" to "SYNCED_AND_CLOSED",
                    "session_id" to sid,"process_id" to android.os.Process.myPid(),"closed_ns" to now()))
                finished = true; mainHandler.removeCallbacks(watchdog); setup.shutdown(); runOnUiThread { finish() }
            } else {
                // A hung worker must not be declared AVAILABLE, have its journal closed, or
                // lose the isolated-process hard watchdog. No retry/restart is performed.
                setup.shutdown()
            }
        }
    }
    private fun waitData(wait: A24PreparationScheduler.Action.Wait) = mapOf("group" to wait.group,
        "planned_wait_ns" to A24PreparationContract.WAIT_NS,"planned_start_ns" to origin+wait.startNs,
        "planned_end_ns" to origin+wait.endNs,"waiting" to scheduler.waiting(),"owners" to scheduler.owners())
    private fun pump() {
        if(failure.get() != null) return
        while(true) when(val action = scheduler.select(now()-origin)) {
            null -> return
            is A24PreparationScheduler.Action.Wait -> {
                event("wait_start",waitData(action)+mapOf("actual_start_ns" to origin+action.startNs))
                dispatch.schedule({
                    if(scheduler.wait === action) {
                        scheduler.endWait(maxOf(now()-origin,action.endNs))
                        event("wait_end",waitData(action)+mapOf("actual_end_ns" to now(),"cut_by_service_stop" to (now()-origin >= A24PreparationContract.SERVICE_NS)))
                        pump()
                    }
                },maxOf(0,origin+action.endNs-now()),TimeUnit.NANOSECONDS)
                return
            }
            is A24PreparationScheduler.Action.Dispatch -> execute(action)
        }
    }
    private fun execute(action: A24PreparationScheduler.Action.Dispatch) {
        val q = action.request; val row = rows.getValue(q.id); val key = "${q.task}_${action.backend}"
        // Capture the logical dispatch commit once, after selection and before submission.
        val dispatched = now()
        if(dispatched-origin >= A24PreparationContract.SERVICE_NS) {
            scheduler.rollbackUnsubmitted(action)
            scheduler.stopDispatch()
            event("dispatch_selection_cutoff",mapOf("request_id" to q.id,"captured_dispatch_ns" to dispatched,
                "planned_stop_ns" to origin+A24PreparationContract.SERVICE_NS,
                "waiting" to scheduler.waiting(),"owners" to scheduler.owners()))
            return
        }
        set(row,mapOf("backend" to action.backend,"dispatch_ns" to dispatched))
        event("dispatch",mapOf("request_id" to q.id,"backend" to action.backend,"dispatch_ns" to dispatched,
            "waiting" to scheduler.waiting(),"owners" to scheduler.owners()))
        val returned = CompletableFuture<Unit>(); availability[q.id] = returned
        lane(key).execute {
            try {
                val started = now(); set(row,mapOf("execution_start_ns" to started))
                event("execution_start",mapOf("request_id" to q.id,"execution_start_ns" to started))
                healthy()
                val input = manifest.inputs.getValue(q.id)
                val result = adapters.getValue(key).execute(A24PreparationManifest.safeFile(inputRoot,input.filename),input.sha256,
                    diagnosticMark = { stage,edge -> event("phase",mapOf("request_id" to q.id,"stage" to stage,"edge" to edge)) },
                    expectedInputTensorSha256 = input.tensorSha256)
                require(result["input_tensor_sha256"] == input.tensorSha256)
                val ready = now(); set(row,mapOf("output_ready_ns" to ready))
                event("output_ready",mapOf("request_id" to q.id,"output_ready_ns" to ready))
                val ended = persist(q.id,result)
                val response = if(q.task == "C") detached(row).getValue("output_ready_ns") as Long else ended
                set(row,mapOf("persist_complete_ns" to ended,"terminal_status" to if(response-origin > A24PreparationContract.SERVICE_NS) "COMPLETED_DRAIN" else "COMPLETED"))
                set(row,mapOf("response_complete_ns" to response,"response_in_service_window" to (response-origin <= A24PreparationContract.SERVICE_NS)))
            } catch(e:Throwable) {
                set(row,mapOf("terminal_status" to "FAILED","reason" to e.toString()))
                failure.compareAndSet(null,"request/$e")
                event("request_failure",mapOf("request_id" to q.id,"error" to e.toString()))
            } finally {
                A24WorkerReturn.afterReturn(lane(key),dispatch,{
                    val released = now(); set(row,mapOf("worker_release_ns" to released))
                    event("worker_release",mapOf("request_id" to q.id,"backend" to action.backend,"worker_release_ns" to released))
                },{
                    try {
                        scheduler.available(q.id,action.backend)
                        val available = now(); set(row,mapOf("lane_available_ns" to available))
                        event("lane_available",mapOf("request_id" to q.id,"backend" to action.backend,"lane_available_ns" to available))
                    } catch(e:Throwable) { failure.compareAndSet(null,"available_record/$e") }
                    finally { returned.complete(Unit) }
                    pump()
                },{ error -> failure.compareAndSet(null,"worker_return/$error") })
            }
        }
    }
    private fun drain() {
        val until = now()+30_000_000_000L
        for(completion in availability.values.toList()) completion.get(maxOf(1,until-now()),TimeUnit.NANOSECONDS)
        if(::scheduler.isInitialized) dispatch.submit { check(scheduler.owners().values.all { it == null }) }.get(5,TimeUnit.SECONDS)
    }
    private fun persist(id: String, result: Map<String,Any?>): Long {
        val target = File(output,"$id.result.json"); val part = File(output,"$id.result.json.part")
        check(!target.exists() && part.createNewFile())
        val bytes = ModelProbeArtifacts.json(result).toByteArray(Charsets.UTF_8)
        FileOutputStream(part).use {
            it.write(bytes); event("persist_write",mapOf("request_id" to id))
            it.flush(); event("persist_flush",mapOf("request_id" to id))
            it.fd.sync(); event("persist_fsync",mapOf("request_id" to id))
        }
        check(part.renameTo(target)); event("persist_rename",mapOf("request_id" to id))
        check(target.readBytes().contentEquals(bytes))
        val completed = now()
        event("persist_readback",mapOf("request_id" to id,"completed_ns" to completed))
        return completed
    }
    override fun onDestroy() {
        if(!finished) failure.compareAndSet(null,"activity_destroyed_no_automatic_restart")
        super.onDestroy()
    }
}
