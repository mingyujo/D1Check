package com.example.d1check.benchmarkrunner

import android.app.Activity
import android.content.Intent
import android.content.IntentFilter
import android.os.*
import android.util.Log
import android.widget.TextView
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.util.UUID
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/** Bounded fixed-recipe calibration only: no scheduling policies or formal workload. */
class TaskProfileActivity : Activity() {
    private val controller = Executors.newSingleThreadExecutor()
    private val handler = Handler(Looper.getMainLooper())
    private val watchdog = Runnable { android.os.Process.killProcess(android.os.Process.myPid()) }
    private lateinit var view: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        view = TextView(this).apply { text = "이미지 분석 중"; textSize = 20f }
        setContentView(view)
        controller.execute { runProfile() }
    }

    private fun runProfile() {
        var output: File? = null
        val workers = listOf(Executors.newSingleThreadExecutor(), Executors.newSingleThreadExecutor())
        val arrivals = Executors.newSingleThreadScheduledExecutor()
        val sampling = Executors.newSingleThreadScheduledExecutor()
        val adapters = arrayOfNulls<ProbeTaskAdapter>(2)
        val keys = arrayOfNulls<String>(2)
        val events = java.util.Collections.synchronizedList(mutableListOf<Map<String, Any?>>())
        val environment = java.util.Collections.synchronizedList(mutableListOf<Map<String, Any?>>())
        try {
            require(intent.action == "com.example.d1check.benchmarkrunner.action.TASK_PROFILE")
            val id = requireNotNull(intent.getStringExtra("session_id"))
            require(UUID.fromString(id).toString() == id)
            val inputs = canonicalProbeInputRoot(filesDir, "task-profile-inputs", id)
            val manifestFile = File(inputs, "manifest.json")
            require(manifestFile.length() in 1..1_048_576)
            val manifest = JSONObject(manifestFile.readText())
            require(manifest.keys().asSequence().toSet() == setOf("protocol", "session_id", "apk_sha256", "device_fingerprint", "models", "images", "requests", "maximum_duration_ms", "purpose", "allowed_concurrency"))
            require(manifest.getString("protocol") == "task-profile-v1" && manifest.getString("session_id") == id)
            require(manifest.getString("purpose") in setOf("correctness", "solo", "transition", "corun", "holdout"))
            require(manifest.getString("device_fingerprint") == Build.FINGERPRINT)
            require(manifest.getString("apk_sha256") == ProbeModelFile.sha256(File(applicationInfo.sourceDir)))
            require(manifest.getLong("maximum_duration_ms") == 120000L)
            val concurrency = manifest.getInt("allowed_concurrency")
            require(concurrency in 1..2)
            val models = manifest.getJSONObject("models")
            val modelSpecs = models.keys().asSequence().associateWith { name ->
                ModelProbeManifestParser.parse(models.getJSONObject(name)).also { m ->
                    require(m.identity.sessionId == id && m.target.apkSha256 == manifest.getString("apk_sha256"))
                    require(m.runtime.litertVersion == "1.4.2" && m.runtime.cpuThreads == 1 && m.runtime.xnnpack)
                }
            }
            val verified = modelSpecs.mapValues { ProbeModelFile.open(inputs, it.value.model) }
            val images = manifest.getJSONArray("images")
            val imageSpecs = (0 until images.length()).associate { i ->
                val row = images.getJSONObject(i)
                val name = row.getString("filename")
                row.getString("sample_id") to Pair(contained(inputs, name, row.getLong("bytes"), row.getString("sha256")), row.getString("sha256"))
            }
            require(imageSpecs.size == images.length() && images.length() in 1..24)
            val anchorFile = contained(inputs, "anchors.json", File(inputs, "anchors.json").length(), ProbeTaskAdapter.ANCHORS_SHA256)
            val requests = manifest.getJSONArray("requests")
            require(requests.length() in 1..48)
            val requestIds = mutableSetOf<String>()
            var previousOffset = -1L
            repeat(requests.length()) { i ->
                val q = requests.getJSONObject(i)
                val requestId = q.getString("request_id")
                require(UUID.fromString(requestId).toString() == requestId && requestIds.add(requestId))
                require(q.getString("model_key") in modelSpecs && q.getString("sample_id") in imageSpecs)
                require(q.getString("priority") in setOf("urgent", "normal"))
                require(q.getString("role") in setOf("warmup", "calibration", "holdout"))
                val offset = q.getLong("offset_ms")
                require(offset >= previousOffset && offset in 0..60000)
                previousOffset = offset
                require(q.getInt("worker") in 0 until concurrency)
            }
            output = canonicalProbeOutputRoot(filesDir, "task-profile-v1", id)
            require(output.mkdirs())
            val root = output
            require(getSystemService(PowerManager::class.java).currentThermalStatus <= 1)
            handler.postDelayed(watchdog, 120000L)
            sampling.scheduleAtFixedRate({ environment.add(snapshot()) }, 0, 500, TimeUnit.MILLISECONDS)
            val start = SystemClock.elapsedRealtimeNanos()
            val done = CountDownLatch(requests.length())
            val serialGate = java.util.concurrent.Semaphore(concurrency)
            Log.i("D1PROFILE", "session_start=$id")
            repeat(requests.length()) { index ->
                val q = requests.getJSONObject(index)
                arrivals.schedule({
                    val enqueued = SystemClock.elapsedRealtimeNanos()
                    val worker = q.getInt("worker")
                    workers[worker].execute {
                        serialGate.acquire()
                        val execution = SystemClock.elapsedRealtimeNanos()
                        val requestId = q.getString("request_id")
                        val key = q.getString("model_key")
                        val spec = modelSpecs.getValue(key)
                        val row = linkedMapOf<String, Any?>("request_id" to requestId, "session_id" to id,
                            "sample_id" to q.getString("sample_id"), "task_id" to spec.model.task.wireName,
                            "model_id" to spec.model.modelId, "requested_backend" to spec.execution.backend.name,
                            "actual_backend" to if (spec.execution.backend == ProbeBackend.CPU) "CPU" else "unverified_requires_host_delegate_log",
                            "priority" to q.getString("priority"), "role" to q.getString("role"), "worker" to worker,
                            "scheduled_arrival_ns" to start + q.getLong("offset_ms") * 1000000L,
                            "enqueue_ns" to enqueued, "execution_start_ns" to execution,
                            "deadline_ns" to null, "deadline_outcome" to "not_set")
                        try {
                            check(getSystemService(PowerManager::class.java).currentThermalStatus <= 1) { "Thermal baseline stop" }
                            val prepareStart = SystemClock.elapsedRealtimeNanos()
                            row["cold"] = keys[worker] != key
                            if (keys[worker] != key) {
                                adapters[worker]?.close(); adapters[worker] = null; keys[worker] = null
                                adapters[worker] = ProbeTaskAdapter(spec, verified.getValue(key), anchorFile)
                                keys[worker] = key
                            }
                            row["prepare_ns"] = SystemClock.elapsedRealtimeNanos() - prepareStart
                            val image = imageSpecs.getValue(q.getString("sample_id"))
                            val result = adapters[worker]!!.execute(image.first, image.second)
                            val payload = ModelProbeArtifacts.json(result).toByteArray(Charsets.UTF_8)
                            val ready = SystemClock.elapsedRealtimeNanos()
                            row["output_ready_ns"] = ready
                            row["inference_ns"] = result["inference_ns"]
                            row["input_tensor_sha256"] = result["input_tensor_sha256"]
                            row["result_sha256"] = ProbeTaskAdapter.digest(payload)
                            row["result_file"] = "$requestId.result.json"
                            if (q.getString("priority") == "normal") {
                                save(root, "$requestId.result.json", payload)
                                row["persist_complete_ns"] = SystemClock.elapsedRealtimeNanos()
                            }
                            val complete = (row["persist_complete_ns"] as? Long) ?: ready
                            row["completion_ns"] = complete
                            row["service_ns"] = complete - execution
                            row["terminal_status"] = "succeeded"
                            runOnUiThread { view.text = "${spec.model.task.wireName}: ${result["results"]}" }
                            if (q.getString("priority") == "urgent") save(root, "$requestId.result.json", payload)
                        } catch (error: Throwable) {
                            row["terminal_status"] = "failed"
                            row["error"] = Log.getStackTraceString(error)
                            // An incomplete write is evidence, never an acknowledged result.
                            row.remove("result_file"); row.remove("result_sha256")
                        } finally {
                            row["terminal_ns"] = SystemClock.elapsedRealtimeNanos()
                            events.add(row)
                            serialGate.release(); done.countDown()
                        }
                    }
                }, q.getLong("offset_ms"), TimeUnit.MILLISECONDS)
            }
            check(done.await(110, TimeUnit.SECONDS)) { "Bounded profile did not drain" }
            val cleanup = CountDownLatch(2)
            val closeErrors = java.util.Collections.synchronizedList(mutableListOf<Throwable>())
            workers.forEachIndexed { i, worker -> worker.execute {
                try { adapters[i]?.close(); adapters[i] = null } catch (error: Throwable) { closeErrors.add(error) }
                finally { cleanup.countDown() }
            } }
            check(cleanup.await(5, TimeUnit.SECONDS)) { "Runtime close did not finish" }
            check(closeErrors.isEmpty()) { "Runtime close failed: $closeErrors" }
            sampling.shutdown(); check(sampling.awaitTermination(2, TimeUnit.SECONDS))
            val sorted = events.sortedBy { it["scheduled_arrival_ns"] as Long }
            save(root, "events.jsonl", sorted.joinToString("\n", postfix = "\n") { ModelProbeArtifacts.json(it) }.toByteArray())
            save(root, "environment.json", ModelProbeArtifacts.json(environment.toList()).toByteArray())
            save(root, "manifest.json", manifestFile.readBytes())
            val summary = mapOf("protocol" to "task-profile-v1", "session_id" to id,
                "status" to if (events.all { it["terminal_status"] == "succeeded" }) "completed" else "completed_with_failures",
                "request_count" to events.size, "succeeded" to events.count { it["terminal_status"] == "succeeded" },
                "failed" to events.count { it["terminal_status"] == "failed" }, "started_ns" to start,
                "finished_ns" to SystemClock.elapsedRealtimeNanos(), "purpose" to manifest.getString("purpose"),
                "deadline_status" to "calibration_pending", "peak_memory_scope" to "500ms sampled process PSS; not continuous peak",
                "model_verification_scope" to "session setup excluded from request service; runtime construction included when cold")
            save(root, "summary.json", ModelProbeArtifacts.json(summary).toByteArray())
            val provenance = mapOf("protocol" to "task-profile-v1", "session_id" to id,
                "manifest_sha256" to ProbeModelFile.sha256(manifestFile), "apk_sha256" to manifest.getString("apk_sha256"),
                "files" to root.listFiles()!!.map { mapOf("name" to it.name, "bytes" to it.length(), "sha256" to ProbeModelFile.sha256(it)) })
            save(root, "provenance.json", ModelProbeArtifacts.json(provenance).toByteArray())
            Log.i("D1PROFILE", "session_finalized=$id")
        } catch (error: Throwable) {
            Log.e("D1PROFILE", "profile failed", error)
            output?.let { save(it, "failure.json", ModelProbeArtifacts.json(mapOf("error" to Log.getStackTraceString(error))).toByteArray()) }
        } finally {
            arrivals.shutdownNow(); sampling.shutdownNow(); workers.forEach { it.shutdownNow() }
            val terminated = workers.all { it.awaitTermination(1, TimeUnit.SECONDS) }
            handler.removeCallbacks(watchdog)
            if (!terminated || adapters.any { it != null }) {
                // Interrupted native inference cannot be cancelled safely; terminate only this isolated process.
                android.os.Process.killProcess(android.os.Process.myPid())
            }
            runOnUiThread { finish() }
        }
    }

    private fun contained(root: File, name: String, bytes: Long, sha256: String): File {
        require(name.matches(Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,126}")) && sha256.matches(Regex("[a-f0-9]{64}")))
        val file = File(root, name)
        require(file.absoluteFile == file.canonicalFile && file.canonicalFile.parentFile == root.canonicalFile && file.isFile)
        require(file.length() == bytes && ProbeModelFile.sha256(file) == sha256)
        return file
    }

    private fun snapshot(): Map<String, Any?> {
        val battery = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val memory = Debug.MemoryInfo(); Debug.getMemoryInfo(memory)
        return mapOf("mono_ns" to SystemClock.elapsedRealtimeNanos(), "total_pss_kb" to memory.totalPss,
            "thermal_status" to getSystemService(PowerManager::class.java).currentThermalStatus,
            "battery_temperature_deci_c" to battery?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1),
            "battery_status" to battery?.getIntExtra(BatteryManager.EXTRA_STATUS, -1),
            "battery_level" to battery?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1))
    }

    private fun save(root: File, name: String, bytes: ByteArray) {
        val file = File(root, name); val temporary = File(root, "$name.part")
        require(!file.exists() && temporary.createNewFile())
        FileOutputStream(temporary).use { it.write(bytes); it.fd.sync() }
        require(temporary.renameTo(file) && file.readBytes().contentEquals(bytes))
    }

    override fun onDestroy() { controller.shutdown(); super.onDestroy() }
}
