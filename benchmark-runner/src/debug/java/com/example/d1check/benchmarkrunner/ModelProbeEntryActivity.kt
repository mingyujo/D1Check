package com.example.d1check.benchmarkrunner

import android.app.Activity
import android.app.ActivityManager
import android.os.Bundle
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.Process
import android.os.SystemClock
import android.system.Os
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.util.UUID
import java.util.concurrent.Executors

/** Debug-only ADB entry. It never emits a finalized/pass provenance artifact. */
class ModelProbeEntryActivity : Activity() {
    private val worker = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "d1-model-probe-entry").apply { isDaemon = true }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        worker.execute {
            val result = try {
                execute()
            } catch (error: Throwable) {
                Log.e(TAG, "Model probe seam failed", error)
                linkedMapOf<String, Any?>(
                    "status" to "failed",
                    "error_type" to error.javaClass.name,
                    "error" to (error.message ?: "unknown error"),
                )
            }
            try {
                writeUnfinalizedSummary(result)
                Log.i(TAG, JSONObject(result).toString())
            } catch (error: Throwable) {
                Log.e(TAG, "Cannot write model probe seam result", error)
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

    private fun execute(): LinkedHashMap<String, Any?> {
        require(intent?.action == ACTION_MODEL_PROBE) { "Unexpected model probe action" }
        val sessionId = requireNotNull(intent.getStringExtra(EXTRA_SESSION_ID)) {
            "Missing model probe session_id"
        }
        require(UUID.fromString(sessionId).toString() == sessionId) {
            "session_id must be canonical lowercase UUID"
        }
        activeSessionId = sessionId
        val inputRoot = File(filesDir, "$INPUT_ROOT/$sessionId")
        val canonicalInputRoot = inputRoot.canonicalFile
        require(inputRoot.absoluteFile == canonicalInputRoot && canonicalInputRoot.isDirectory) {
            "Probe input root is invalid"
        }
        require(canonicalInputRoot.listFiles()?.none { it.name.endsWith(".part") } == true) {
            "Probe input root contains partial files"
        }
        val manifestFile = File(canonicalInputRoot, MANIFEST_FILENAME)
        require(manifestFile.canonicalFile.parentFile == canonicalInputRoot) {
            "Probe manifest escapes input root"
        }
        val manifest = ModelProbeManifestParser.parse(manifestFile)
        require(manifest.identity.sessionId == sessionId) { "Intent/manifest session mismatch" }
        require(manifest.target.packageName == packageName) { "Manifest package mismatch" }
        scheduleWatchdog(manifest.execution.maximumDurationMs)
        verifyTarget(manifest.target)
        val model = ProbeModelFile.open(canonicalInputRoot, manifest.model)
        val startedNs = SystemClock.elapsedRealtimeNanos()
        val details = when (manifest.input.kind) {
            "deterministic_rgb" -> runRaw(manifest, model)
            "external_image" -> {
                val input = ProbeModelFile.openInput(canonicalInputRoot, manifest.input)
                val decoded = ProbeDecodedDetector.runBlocking(this, manifest, model, input)
                linkedMapOf(
                    "adapter" to "mediapipe_tasks_object_detector",
                    "tasks_detect_ns" to decoded.tasksDetectNs,
                    "detection_count" to decoded.detections.size,
                    "detections" to decoded.detections.map { detection ->
                        linkedMapOf(
                            "label" to detection.label,
                            "score" to detection.score,
                            "box" to listOf(
                                detection.left, detection.top, detection.width, detection.height
                            ),
                        )
                    },
                    "delegation_status" to decoded.delegationStatus,
                )
            }
            else -> error("Unsupported probe input kind")
        }
        val finishedNs = SystemClock.elapsedRealtimeNanos()
        return linkedMapOf(
            "schema_version" to MODEL_PROBE_SCHEMA,
            "protocol_version" to MODEL_PROBE_PROTOCOL,
            "session_id" to sessionId,
            "device_id" to manifest.target.deviceId,
            "model_id" to manifest.model.modelId,
            "backend" to manifest.execution.backend.name,
            "status" to "seam_smoke_only_unfinalized",
            "finalized" to false,
            "elapsed_ns" to (finishedNs - startedNs),
            "details" to details,
        )
    }

    private fun runRaw(
        manifest: ModelProbeManifest,
        model: VerifiedProbeFile,
    ): LinkedHashMap<String, Any?> {
        val seed = requireNotNull(manifest.input.seed)
        val cold = mutableListOf<ProbeRawInvocation>()
        repeat(manifest.execution.coldRepetitions) {
            ProbeRawSession.create(manifest, model).use { session ->
                cold += session.invoke(seed)
            }
        }
        val warm = ProbeRawSession.create(manifest, model).use { session ->
            List(manifest.execution.warmRepetitions) { session.invoke(seed) }
        }
        fun invocation(value: ProbeRawInvocation) = linkedMapOf<String, Any?>(
            "seed" to value.seed,
            "input_sha256" to value.inputSha256,
            "output_sha256" to value.outputSha256,
            "invoke_ns" to value.invokeNs,
            "delegation_status" to value.delegationStatus,
        )
        return linkedMapOf(
            "adapter" to "litert_raw",
            "cold" to cold.map(::invocation),
            "warm" to warm.map(::invocation),
            "output_values_persisted" to false,
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
        if (Build.VERSION.SDK_INT >= 31) {
            require(target.soc == Build.SOC_MODEL) { "Target SoC mismatch" }
        }
        val memory = ActivityManager.MemoryInfo()
        getSystemService(ActivityManager::class.java).getMemoryInfo(memory)
        require(target.ramBytes == memory.totalMem) { "Target RAM identity mismatch" }
        val installedApk = File(applicationInfo.sourceDir)
        require(ProbeModelFile.sha256(installedApk) == target.apkSha256) {
            "Installed APK SHA-256 mismatch"
        }
    }

    private fun writeUnfinalizedSummary(result: Map<String, Any?>) {
        val sessionId = activeSessionId ?: return
        val root = File(filesDir, "$OUTPUT_ROOT/$sessionId")
        require(!root.exists()) { "Probe output root already exists" }
        require(root.mkdirs()) { "Cannot create probe output root" }
        val finalFile = File(root, "summary.json")
        val temporary = File(root, "summary.json.part")
        try {
            FileOutputStream(temporary).use { stream ->
                stream.write(json(result).toByteArray(StandardCharsets.UTF_8))
                stream.fd.sync()
            }
            if (android.os.Build.VERSION.SDK_INT >= 26) {
                Files.move(
                    temporary.toPath(), finalFile.toPath(),
                    StandardCopyOption.ATOMIC_MOVE,
                )
            } else {
                Os.rename(temporary.absolutePath, finalFile.absolutePath)
            }
            require(finalFile.isFile && finalFile.length() > 0L) { "Probe summary finalization failed" }
        } catch (error: Throwable) {
            temporary.delete()
            throw error
        }
    }

    private fun scheduleWatchdog(maximumDurationMs: Long) {
        val task = Runnable {
            Log.e(TAG, "Model probe exceeded the device timeout; terminating isolated probe process")
            Process.killProcess(Process.myPid())
        }
        watchdog = task
        mainHandler.postDelayed(task, maximumDurationMs)
    }

    private fun cancelWatchdog() {
        watchdog?.let(mainHandler::removeCallbacks)
        watchdog = null
    }

    private fun json(value: Any?): String = when (value) {
        is Map<*, *> -> JSONObject().apply {
            value.forEach { (key, nested) -> put(key.toString(), jsonValue(nested)) }
        }.toString()
        else -> jsonValue(value).toString()
    }

    private fun jsonValue(value: Any?): Any = when (value) {
        null -> JSONObject.NULL
        is Map<*, *> -> JSONObject().apply {
            value.forEach { (key, nested) -> put(key.toString(), jsonValue(nested)) }
        }
        is Iterable<*> -> JSONArray().apply { value.forEach { put(jsonValue(it)) } }
        else -> value
    }

    private var activeSessionId: String? = null
    private val mainHandler = Handler(Looper.getMainLooper())
    private var watchdog: Runnable? = null

    companion object {
        const val TAG = "D1MODELPROBE"
        const val ACTION_MODEL_PROBE =
            "com.example.d1check.benchmarkrunner.action.MODEL_PROBE"
        const val EXTRA_SESSION_ID = "session_id"
        const val MANIFEST_FILENAME = "model_probe_manifest.json"
        const val INPUT_ROOT = "model-probe-inputs"
        const val OUTPUT_ROOT = "model-probe-v1"
    }
}
