package com.example.d1check.benchmarkrunner

import android.app.Activity
import android.app.ActivityManager
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.os.Process
import android.os.SystemClock
import android.util.Log
import java.io.File
import java.io.FileOutputStream
import java.nio.charset.StandardCharsets
import java.security.MessageDigest
import java.util.UUID
import java.util.concurrent.Executors

/** Debug-only ADB entry for finalized, UUID-scoped MODEL-02B profile artifacts. */
class ModelProbeEntryActivity : Activity() {
    private val worker = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "d1-model-probe-entry").apply { isDaemon = true }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        worker.execute {
            try {
                execute()
            } catch (error: Throwable) {
                Log.e(TAG, "Model probe failed session=$activeSessionId", error)
                writeFailureSummary(error)
            } finally {
                cancelWatchdog()
                runOnUiThread(::finish)
            }
        }
    }

    override fun onDestroy() {
        worker.shutdownNow()
        super.onDestroy()
    }

    private fun execute() {
        require(intent?.action == ACTION_MODEL_PROBE) { "Unexpected model probe action" }
        val sessionId = requireNotNull(intent.getStringExtra(EXTRA_SESSION_ID)) {
            "Missing model probe session_id"
        }
        require(UUID.fromString(sessionId).toString() == sessionId) {
            "session_id must be canonical lowercase UUID"
        }
        activeSessionId = sessionId
        val outputRoot = File(filesDir, "$OUTPUT_ROOT/$sessionId")
        require(outputRoot.absoluteFile == outputRoot.canonicalFile && !outputRoot.exists()) {
            "Stale or invalid probe output root"
        }
        failureOutputAllowed = true
        val canonicalInputRoot = canonicalProbeInputRoot(filesDir, INPUT_ROOT, sessionId)
        require(canonicalInputRoot.listFiles()?.none { it.name.endsWith(".part") } == true) {
            "Probe input root contains partial files"
        }
        val manifestFile = File(canonicalInputRoot, MANIFEST_FILENAME)
        require(manifestFile.canonicalFile.parentFile == canonicalInputRoot) {
            "Probe manifest escapes input root"
        }
        val manifest = ModelProbeManifestParser.parse(manifestFile)
        activeManifestSha256 = ProbeModelFile.sha256(manifestFile)
        activeManifest = manifest
        activeDeviceId = manifest.target.deviceId
        require(manifest.identity.sessionId == sessionId) { "Intent/manifest session mismatch" }
        require(manifest.target.packageName == packageName) { "Manifest package mismatch" }
        scheduleWatchdog(manifest.execution.maximumDurationMs)
        verifyTarget(manifest.target)
        val model = ProbeModelFile.open(canonicalInputRoot, manifest.model)
        val startedNs = SystemClock.elapsedRealtimeNanos()
        val startEnvironment = environmentSnapshot(startedNs)
        check(Build.VERSION.SDK_INT >= 29 &&
            getSystemService(PowerManager::class.java).currentThermalStatus <= 1) {
            "Probe thermal baseline gate failed"
        }
        val startMemory = memorySnapshot()
        Log.i(TAG, "session_start=$sessionId model=${manifest.model.modelId} backend=${manifest.execution.backend}")

        val measured = when (manifest.input.kind) {
            "deterministic_rgb" -> runRaw(manifest, model)
            "external_image" -> {
                val input = ProbeModelFile.openInput(canonicalInputRoot, manifest.input)
                runDecoded(manifest, model, input)
            }
            else -> error("Unsupported probe input kind")
        }
        val finishedNs = SystemClock.elapsedRealtimeNanos()
        val endEnvironment = environmentSnapshot(finishedNs)
        val endMemory = memorySnapshot()
        val identity = identity(manifest)
        val metadata = identity + linkedMapOf<String, Any?>(
            "status" to "succeeded",
            "finalized" to true,
            "task_id" to manifest.model.task.name.lowercase(),
            "model_id" to manifest.model.modelId,
            "model_sha256" to manifest.model.sha256,
            "input_id" to manifest.input.inputId,
            "input_sha256" to (manifest.input.sha256 ?: measured.inputHashes.first()),
            "backend" to manifest.execution.backend.name,
            "started_mono_ns" to startedNs,
            "finished_mono_ns" to finishedNs,
            "start_environment" to startEnvironment,
            "end_environment" to endEnvironment,
            "measurement_scope" to "model_probe_latency_not_accuracy",
            "npu_status" to "not_probed",
            "cpu_threads_requested" to manifest.runtime.cpuThreads,
            "cpu_threads_status" to if (manifest.input.kind == "external_image") {
                "not_exposed_by_tasks_api"
            } else { "configured_interpreter_threads" },
        )
        val memory = identity + linkedMapOf<String, Any?>(
            "start" to startMemory,
            "end" to endMemory,
            "delta_total_pss_kb" to ((endMemory["total_pss_kb"] as Int) - (startMemory["total_pss_kb"] as Int)),
            "scope" to "probe_process_only",
        )
        val delegationStatus = if (manifest.execution.backend == ProbeBackend.GPU) {
            "unverified_requires_delegate_evidence"
        } else {
            "not_applicable_cpu"
        }
        val delegateEvidence = identity + linkedMapOf<String, Any?>(
            "requested_backend" to manifest.execution.backend.name,
            "observed_backend" to if (manifest.execution.backend == ProbeBackend.GPU) {
                "unverified"
            } else { "CPU" },
            "status" to delegationStatus,
            "full_delegation_verified" to false,
            "silent_cpu_fallback_allowed" to false,
            "device_log_evidence" to "host_finalization_required_for_gpu",
        )
        val summary = identity + linkedMapOf<String, Any?>(
            "status" to "succeeded",
            "finalized" to true,
            "task_id" to manifest.model.task.name.lowercase(),
            "model_id" to manifest.model.modelId,
            "backend" to manifest.execution.backend.name,
            "adapter" to measured.adapter,
            "started_mono_ns" to startedNs,
            "finished_mono_ns" to finishedNs,
            "elapsed_ns" to (finishedNs - startedNs),
            "cold_repetitions" to manifest.execution.coldRepetitions,
            "warmup_repetitions" to 1,
            "warm_repetitions" to manifest.execution.warmRepetitions,
            "prepare_ns" to measured.prepareNs,
            "invoke_ns_cold" to measured.coldInvokeNs,
            "invoke_ns_warmup" to measured.warmupInvokeNs,
            "invoke_ns_warm" to measured.warmInvokeNs,
            "end_to_end_ns_cold" to measured.coldEndToEndNs,
            "end_to_end_ns_warm" to measured.warmEndToEndNs,
            "close_ns" to measured.closeNs,
            "output_hashes" to measured.outputHashes.distinct(),
            "output_element_counts" to measured.outputElementCounts,
            "non_finite_count" to 0,
            "success_count" to measured.events.size,
            "failure_count" to 0,
            "timeout_count" to 0,
            "delegation_status" to delegationStatus,
            "accuracy_evaluated" to false,
            "backend_switch_cost_ns" to null,
            "backend_switch_cost_status" to "not_measured_in_single_backend_probe",
        )
        ModelProbeArtifacts.writeFinalized(
            root = outputRoot,
            identity = identity,
            metadata = metadata,
            events = measured.events,
            rawEquivalence = identity + measured.rawEquivalence,
            decodedResults = identity + measured.decodedResults,
            memory = memory,
            delegateEvidence = delegateEvidence,
            summary = summary,
        )
        Log.i(TAG, "session_finalized=$sessionId artifacts=8 status=succeeded")
    }

    private fun runRaw(manifest: ModelProbeManifest, model: VerifiedProbeFile): MeasuredRun {
        val seed = requireNotNull(manifest.input.seed)
        val events = mutableListOf<Map<String, Any?>>()
        val prepare = mutableListOf<Long>()
        val coldInvoke = mutableListOf<Long>()
        val coldE2e = mutableListOf<Long>()
        val close = mutableListOf<Long>()
        val outputHashes = mutableListOf<String>()
        val inputHashes = mutableListOf<String>()
        var outputCounts = emptyList<Int>()
        repeat(manifest.execution.coldRepetitions) { repetition ->
            val e2eStart = SystemClock.elapsedRealtimeNanos()
            val prepareStart = e2eStart
            ProbeRawSession.create(manifest, model).use { session ->
            val prepareNs = SystemClock.elapsedRealtimeNanos() - prepareStart
            val invocation = session.invoke(seed)
            val closeStart = SystemClock.elapsedRealtimeNanos()
            session.close()
            val closeNs = SystemClock.elapsedRealtimeNanos() - closeStart
            val e2eNs = SystemClock.elapsedRealtimeNanos() - e2eStart
            prepare += prepareNs
            coldInvoke += invocation.invokeNs
            coldE2e += e2eNs
            close += closeNs
            outputHashes += invocation.outputSha256
            inputHashes += invocation.inputSha256
            outputCounts = invocation.outputs.map { it.size }
            events += event(manifest, "cold", repetition, prepareNs, invocation.invokeNs, e2eNs, invocation.outputSha256)
            }
        }
        val warmPrepareStart = SystemClock.elapsedRealtimeNanos()
        ProbeRawSession.create(manifest, model).use { warmSession ->
        prepare += SystemClock.elapsedRealtimeNanos() - warmPrepareStart
        val warmup = warmSession.invoke(seed)
        events += event(manifest, "warmup", 0, 0L, warmup.invokeNs, warmup.invokeNs, warmup.outputSha256)
        val warmInvoke = mutableListOf<Long>()
        val warmE2e = mutableListOf<Long>()
        repeat(manifest.execution.warmRepetitions) { repetition ->
            val e2eStart = SystemClock.elapsedRealtimeNanos()
            val invocation = warmSession.invoke(seed)
            val e2eNs = SystemClock.elapsedRealtimeNanos() - e2eStart
            warmInvoke += invocation.invokeNs
            warmE2e += e2eNs
            outputHashes += invocation.outputSha256
            inputHashes += invocation.inputSha256
            events += event(manifest, "warm", repetition, 0L, invocation.invokeNs, e2eNs, invocation.outputSha256)
        }
        val closeStart = SystemClock.elapsedRealtimeNanos()
        warmSession.close()
        close += SystemClock.elapsedRealtimeNanos() - closeStart
        return MeasuredRun(
            adapter = "litert_raw",
            events = events,
            prepareNs = prepare,
            coldInvokeNs = coldInvoke,
            warmupInvokeNs = warmup.invokeNs,
            warmInvokeNs = warmInvoke,
            coldEndToEndNs = coldE2e,
            warmEndToEndNs = warmE2e,
            closeNs = close,
            outputHashes = outputHashes,
            inputHashes = inputHashes,
            outputElementCounts = outputCounts,
            rawEquivalence = linkedMapOf(
                "status" to "single_backend_finite_output",
                "cross_backend_comparison" to "pending_host_pairing",
                "input_sha256" to inputHashes.distinct(),
                "output_sha256" to outputHashes.distinct(),
                "output_element_counts" to outputCounts,
                "non_finite_count" to 0,
            ),
            decodedResults = linkedMapOf("status" to "not_applicable_raw_adapter"),
        )
        }
    }

    private fun runDecoded(
        manifest: ModelProbeManifest,
        model: VerifiedProbeFile,
        input: VerifiedProbeFile,
    ): MeasuredRun {
        val events = mutableListOf<Map<String, Any?>>()
        val prepare = mutableListOf<Long>()
        val coldInvoke = mutableListOf<Long>()
        val coldE2e = mutableListOf<Long>()
        val close = mutableListOf<Long>()
        val outputHashes = mutableListOf<String>()
        var canonicalDetections: List<Map<String, Any?>> = emptyList()
        repeat(manifest.execution.coldRepetitions) { repetition ->
            val e2eStart = SystemClock.elapsedRealtimeNanos()
            val prepareStart = e2eStart
            ProbeDecodedSession.create(this, manifest, model, input).use { session ->
            val prepareNs = SystemClock.elapsedRealtimeNanos() - prepareStart
            val invocation = session.invoke()
            val hash = decodedHash(invocation)
            val closeStart = SystemClock.elapsedRealtimeNanos()
            session.close()
            val closeNs = SystemClock.elapsedRealtimeNanos() - closeStart
            val e2eNs = SystemClock.elapsedRealtimeNanos() - e2eStart
            prepare += prepareNs
            coldInvoke += invocation.tasksDetectNs
            coldE2e += e2eNs
            close += closeNs
            outputHashes += hash
            canonicalDetections = detections(invocation)
            events += event(manifest, "cold", repetition, prepareNs, invocation.tasksDetectNs, e2eNs, listOf(hash))
            }
        }
        val warmPrepareStart = SystemClock.elapsedRealtimeNanos()
        ProbeDecodedSession.create(this, manifest, model, input).use { warmSession ->
        prepare += SystemClock.elapsedRealtimeNanos() - warmPrepareStart
        val warmup = warmSession.invoke()
        val warmupHash = decodedHash(warmup)
        events += event(manifest, "warmup", 0, 0L, warmup.tasksDetectNs, warmup.tasksDetectNs, listOf(warmupHash))
        val warmInvoke = mutableListOf<Long>()
        val warmE2e = mutableListOf<Long>()
        repeat(manifest.execution.warmRepetitions) { repetition ->
            val e2eStart = SystemClock.elapsedRealtimeNanos()
            val invocation = warmSession.invoke()
            val hash = decodedHash(invocation)
            val e2eNs = SystemClock.elapsedRealtimeNanos() - e2eStart
            warmInvoke += invocation.tasksDetectNs
            warmE2e += e2eNs
            outputHashes += hash
            canonicalDetections = detections(invocation)
            events += event(manifest, "warm", repetition, 0L, invocation.tasksDetectNs, e2eNs, listOf(hash))
        }
        val closeStart = SystemClock.elapsedRealtimeNanos()
        warmSession.close()
        close += SystemClock.elapsedRealtimeNanos() - closeStart
        return MeasuredRun(
            adapter = "mediapipe_tasks_object_detector",
            events = events,
            prepareNs = prepare,
            coldInvokeNs = coldInvoke,
            warmupInvokeNs = warmup.tasksDetectNs,
            warmInvokeNs = warmInvoke,
            coldEndToEndNs = coldE2e,
            warmEndToEndNs = warmE2e,
            closeNs = close,
            outputHashes = outputHashes,
            inputHashes = listOf(input.sha256),
            outputElementCounts = listOf(canonicalDetections.size),
            rawEquivalence = linkedMapOf("status" to "not_applicable_decoded_adapter"),
            decodedResults = linkedMapOf(
                "status" to "finite_canonical_output",
                "accuracy_evaluated" to false,
                "input_sha256" to input.sha256,
                "output_sha256" to outputHashes.distinct(),
                "detection_count" to canonicalDetections.size,
                "detections" to canonicalDetections,
            ),
        )
        }
    }

    private fun event(
        manifest: ModelProbeManifest,
        role: String,
        repetition: Int,
        prepareNs: Long,
        invokeNs: Long,
        endToEndNs: Long,
        outputHashes: List<String>,
    ): Map<String, Any?> = identity(manifest) + linkedMapOf(
        "event" to "probe_invocation",
        "role" to role,
        "repetition" to repetition,
        "task_id" to manifest.model.task.name.lowercase(),
        "model_id" to manifest.model.modelId,
        "backend" to manifest.execution.backend.name,
        "prepare_ns" to prepareNs,
        "invoke_ns" to invokeNs,
        "end_to_end_ns" to endToEndNs,
        "output_sha256" to outputHashes,
        "mono_ns" to SystemClock.elapsedRealtimeNanos(),
        "terminal_status" to "succeeded",
    )

    private fun detections(value: ProbeDecodedResult): List<Map<String, Any?>> =
        value.detections.map { detection ->
            linkedMapOf(
                "label" to detection.label,
                "score" to detection.score,
                "box" to listOf(detection.left, detection.top, detection.width, detection.height),
            )
        }

    private fun decodedHash(value: ProbeDecodedResult): String {
        val bytes = ModelProbeArtifacts.json(detections(value)).toByteArray(StandardCharsets.UTF_8)
        return MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
    }

    private fun identity(manifest: ModelProbeManifest): LinkedHashMap<String, Any?> = linkedMapOf(
        "schema_version" to MODEL_PROBE_SCHEMA,
        "protocol_version" to MODEL_PROBE_PROTOCOL,
        "session_id" to manifest.identity.sessionId,
        "device_id" to manifest.target.deviceId,
        "artifact_contract_version" to 2,
        "manifest_sha256" to requireNotNull(activeManifestSha256),
        "apk_sha256" to manifest.target.apkSha256,
        "model_sha256" to manifest.model.sha256,
        "model_id" to manifest.model.modelId,
        "task_id" to manifest.model.task.name.lowercase(),
        "backend" to manifest.execution.backend.name,
    )

    private fun environmentSnapshot(monoNs: Long): Map<String, Any?> {
        val battery = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val power = getSystemService(PowerManager::class.java)
        return linkedMapOf(
            "mono_ns" to monoNs,
            "battery_level" to battery?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1),
            "battery_status" to battery?.getIntExtra(BatteryManager.EXTRA_STATUS, -1),
            "battery_temperature_deci_c" to battery?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1),
            "thermal_status" to if (Build.VERSION.SDK_INT >= 29) power.currentThermalStatus else null,
            "screen_interactive" to power.isInteractive,
            "power_save_mode" to power.isPowerSaveMode,
        )
    }

    private fun memorySnapshot(): Map<String, Any?> {
        val activityManager = getSystemService(ActivityManager::class.java)
        val info = activityManager.getProcessMemoryInfo(intArrayOf(Process.myPid())).single()
        val runtime = Runtime.getRuntime()
        return linkedMapOf(
            "mono_ns" to SystemClock.elapsedRealtimeNanos(),
            "total_pss_kb" to info.totalPss,
            "total_private_dirty_kb" to info.totalPrivateDirty,
            "total_shared_dirty_kb" to info.totalSharedDirty,
            "java_heap_used_bytes" to (runtime.totalMemory() - runtime.freeMemory()),
            "java_heap_committed_bytes" to runtime.totalMemory(),
        )
    }

    private fun verifyTarget(target: ProbeTarget) {
        require(target.manufacturer == Build.MANUFACTURER) { "Target manufacturer mismatch" }
        require(target.model == Build.MODEL) { "Target model mismatch" }
        require(target.androidRelease == Build.VERSION.RELEASE) { "Target Android release mismatch" }
        require(target.apiLevel == Build.VERSION.SDK_INT) { "Target API level mismatch" }
        require(target.buildFingerprint == Build.FINGERPRINT) { "Target build fingerprint mismatch" }
        val primaryAbi = Build.SUPPORTED_ABIS.firstOrNull()
            ?: throw IllegalStateException("Device exposes no supported ABI")
        require(target.abi == primaryAbi && target.cpuAbi == primaryAbi) { "Target ABI mismatch" }
        if (Build.VERSION.SDK_INT >= 31) require(target.soc == Build.SOC_MODEL) { "Target SoC mismatch" }
        val memory = ActivityManager.MemoryInfo()
        getSystemService(ActivityManager::class.java).getMemoryInfo(memory)
        require(target.ramBytes == memory.totalMem) { "Target RAM identity mismatch" }
        require(ProbeModelFile.sha256(File(applicationInfo.sourceDir)) == target.apkSha256) {
            "Installed APK SHA-256 mismatch"
        }
    }

    private fun writeFailureSummary(error: Throwable) {
        if (!failureOutputAllowed) return
        val session = activeSessionId ?: return
        val root = File(filesDir, "$OUTPUT_ROOT/$session")
        if (!root.exists() && !root.mkdirs()) return
        val summary = File(root, "summary.json")
        if (summary.exists()) return
        val temporary = File(root, "summary.json.part")
        try {
            val value = (activeManifest?.let(::identity) ?: emptyMap()) + linkedMapOf<String, Any?>(
                "schema_version" to MODEL_PROBE_SCHEMA,
                "protocol_version" to MODEL_PROBE_PROTOCOL,
                "session_id" to session,
                "device_id" to activeDeviceId,
                "status" to if (error is ProbeUnsupportedBackendException) "unsupported" else "failed",
                "finalized" to false,
                "error_type" to error.javaClass.name,
                "error" to (error.message ?: "unknown error"),
                "error_stacktrace" to Log.getStackTraceString(error),
            )
            FileOutputStream(temporary).use { stream ->
                stream.write(ModelProbeArtifacts.json(value).toByteArray(StandardCharsets.UTF_8))
                stream.fd.sync()
            }
            require(temporary.renameTo(summary)) { "Cannot finalize failure summary" }
        } catch (writeError: Throwable) {
            temporary.delete()
            Log.e(TAG, "Cannot write model probe failure summary", writeError)
        }
    }

    private fun scheduleWatchdog(maximumDurationMs: Long) {
        val task = Runnable {
            Log.e(TAG, "Model probe exceeded device timeout; terminating isolated process")
            Process.killProcess(Process.myPid())
        }
        watchdog = task
        mainHandler.postDelayed(task, maximumDurationMs)
    }

    private fun cancelWatchdog() {
        watchdog?.let(mainHandler::removeCallbacks)
        watchdog = null
    }

    private data class MeasuredRun(
        val adapter: String,
        val events: List<Map<String, Any?>>,
        val prepareNs: List<Long>,
        val coldInvokeNs: List<Long>,
        val warmupInvokeNs: Long,
        val warmInvokeNs: List<Long>,
        val coldEndToEndNs: List<Long>,
        val warmEndToEndNs: List<Long>,
        val closeNs: List<Long>,
        val outputHashes: List<String>,
        val inputHashes: List<String>,
        val outputElementCounts: List<Int>,
        val rawEquivalence: Map<String, Any?>,
        val decodedResults: Map<String, Any?>,
    )

    private var activeSessionId: String? = null
    private var failureOutputAllowed = false
    private var activeDeviceId: String? = null
    private var activeManifestSha256: String? = null
    private var activeManifest: ModelProbeManifest? = null
    private val mainHandler = Handler(Looper.getMainLooper())
    private var watchdog: Runnable? = null

    companion object {
        const val TAG = "D1MODELPROBE"
        const val ACTION_MODEL_PROBE = "com.example.d1check.benchmarkrunner.action.MODEL_PROBE"
        const val EXTRA_SESSION_ID = "session_id"
        const val MANIFEST_FILENAME = "model_probe_manifest.json"
        const val INPUT_ROOT = "model-probe-inputs"
        const val OUTPUT_ROOT = "model-probe-v1"
    }
}

internal fun canonicalProbeInputRoot(filesDir: File, rootName: String, sessionId: String): File {
    val canonicalFilesDir = filesDir.canonicalFile
    val parent = File(canonicalFilesDir, rootName)
    val canonicalParent = parent.canonicalFile
    val inputRoot = File(canonicalParent, sessionId)
    val canonicalInputRoot = inputRoot.canonicalFile
    require(parent.absoluteFile == canonicalParent && inputRoot.absoluteFile == canonicalInputRoot) {
        "Probe input root must not contain symlinks"
    }
    require(canonicalParent.parentFile == canonicalFilesDir && canonicalInputRoot.parentFile == canonicalParent) {
        "Probe input root escapes app-private files"
    }
    require(canonicalInputRoot.isDirectory) { "Probe input root is invalid" }
    return canonicalInputRoot
}
