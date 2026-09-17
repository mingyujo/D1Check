package com.example.d1check.benchmarkrunner

import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

internal data class CalibrationArtifactEntry(
    val relativePath: String,
    val byteCount: Long,
    val sha256: String,
)

internal data class CalibrationThermalSample(
    val timestampNs: Long,
    val thermalStatus: Int?,
    val batteryTemperatureDeciC: Int?,
)

internal fun interface CalibrationThermalProvider {
    fun sample(): CalibrationThermalSample
}

internal class AndroidCalibrationThermalProvider(
    private val context: Context,
) : CalibrationThermalProvider {
    override fun sample(): CalibrationThermalSample = CalibrationThermalSample(
        timestampNs = AndroidCalibrationClock.monotonicNanos(),
        thermalStatus = readThermalStatus(context),
        batteryTemperatureDeciC = readBatteryTemperatureDeciC(context),
    )
}

internal class CalibrationSessionArtifacts private constructor(
    private val context: Context,
    val manifest: CalibrationInputManifest,
    val root: File,
    private val requestStream: FileOutputStream,
    private val thermalStream: FileOutputStream,
    private val thermalProvider: CalibrationThermalProvider,
    initialThermalSample: CalibrationThermalSample,
    private val startMonoNs: Long,
    private val actualApkSha256: String,
    private val actualModelSha256: String,
) : CalibrationResultRecorder, AutoCloseable {
    private val counts = CalibrationTerminalStatus.entries.associateWith { 0L }.toMutableMap()
    private val deadlineCounts = CalibrationDeadlineOutcome.entries.associateWith { 0L }.toMutableMap()
    private var top1CorrectCount = 0L
    private var top5CorrectCount = 0L
    private var classifiedCount = 0L
    private var unverifiedGpuCount = 0L
    private var highestBatteryTemperatureDeciC: Int? = null
    private var highestThermalStatus: Int? = null
    private var thermalSampleCount = 0L
    private var lastThermalTimestampNs: Long? = null
    @Volatile
    private var environmentSamplingFailure: Throwable? = null
    private var finalized = false
    init {
        recordThermalSample(initialThermalSample)
    }
    private val environmentSampler = Executors.newSingleThreadScheduledExecutor { runnable ->
        Thread(runnable, "d1-calibration-environment").apply { isDaemon = true }
    }.apply {
        scheduleWithFixedDelay({
            try {
                sampleEnvironment()
            } catch (error: Throwable) {
                synchronized(this@CalibrationSessionArtifacts) {
                    if (environmentSamplingFailure == null) environmentSamplingFailure = error
                }
            }
        }, 1L, 1L, TimeUnit.SECONDS)
    }

    override fun record(result: CalibrationRequestResult) {
        check(!finalized) { "calibration artifacts are finalized" }
        result.timestamps.validateMonotonic(result.terminalStatus)
        if (result.terminalStatus == CalibrationTerminalStatus.SUCCEEDED) {
            check(result.output != null) { "succeeded request must contain output" }
            when (result.request.requestType) {
                CalibrationRequestType.URGENT -> check(
                    result.timestamps.outputReadyNs != null && result.persistedRelativePath == null
                ) { "succeeded urgent request boundary mismatch" }
                CalibrationRequestType.NORMAL -> check(
                    result.timestamps.persistenceCompletedNs != null &&
                        result.persistedRelativePath == "results/${result.request.requestId}.json"
                ) { "succeeded normal request boundary mismatch" }
            }
        } else {
            check(result.output == null && result.persistedRelativePath == null) {
                "non-succeeded request must not contain output or persistence"
            }
        }
        val line = result.toJson(manifest.sessionId, manifest.calibrationMode).toString() + "\n"
        requestStream.write(line.toByteArray(Charsets.UTF_8))
        requestStream.flush()
        requestStream.fd.sync()
        counts[result.terminalStatus] = counts.getValue(result.terminalStatus) + 1L
        deadlineCounts[result.deadlineOutcome] =
            deadlineCounts.getValue(result.deadlineOutcome) + 1L
        result.output?.let { output ->
            classifiedCount++
            if (output.topLabels.firstOrNull() == result.request.image.label) top1CorrectCount++
            if (result.request.image.label in output.topLabels) top5CorrectCount++
        }
        if (result.request.requestedBackend == CalibrationBackend.GPU &&
            result.fallbackStatus == CalibrationFallbackStatus.UNVERIFIED
        ) unverifiedGpuCount++
        sampleEnvironment()
    }

    fun finalizeAndValidate(): List<CalibrationArtifactEntry> {
        check(!finalized) { "calibration artifacts already finalized" }
        requestStream.close()
        environmentSampler.shutdownNow()
        sampleEnvironment()
        thermalStream.close()
        check(environmentSamplingFailure == null) {
            "thermal sampling failed: ${environmentSamplingFailure?.message}"
        }
        val summary = JSONObject()
            .put("schema_version", CalibrationContract.SCHEMA_VERSION)
            .put("protocol_version", CalibrationContract.PROTOCOL_VERSION)
            .put("session_id", manifest.sessionId)
            .put("calibration_mode", manifest.calibrationMode.wireName)
            .put("clock", CalibrationContract.CLOCK)
            .put("start_mono_ns", startMonoNs)
            .put("end_mono_ns", AndroidCalibrationClock.monotonicNanos())
            .put("deadline_state", "calibration_pending")
            .put("highest_battery_temperature_deci_c", highestBatteryTemperatureDeciC)
            .put("highest_thermal_status", highestThermalStatus)
            .put("classified_count", classifiedCount)
            .put("top1_correct_count", top1CorrectCount)
            .put("top5_correct_count", top5CorrectCount)
            .put("unverified_gpu_request_count", unverifiedGpuCount)
            .put("gpu_results_require_host_full_delegation_evidence", unverifiedGpuCount > 0)
            .put("counts", JSONObject().apply {
                counts.forEach { (status, count) -> put(status.wireName, count) }
            })
            .put("deadline_counts", JSONObject().apply {
                deadlineCounts.forEach { (outcome, count) -> put(outcome.wireName, count) }
            })
            .put("arrived_count", counts.values.sum())
            .put("completed_count", counts.getValue(CalibrationTerminalStatus.SUCCEEDED))
            .put("overall_completion_rate", ratioOrNull(
                counts.getValue(CalibrationTerminalStatus.SUCCEEDED),
                counts.values.sum(),
            ))
            .put("deadline_set_count", deadlineCounts.entries.sumOf { (outcome, count) ->
                if (outcome == CalibrationDeadlineOutcome.NOT_SET) 0L else count
            })
            .put("on_time_completion_rate", ratioOrNull(
                deadlineCounts.getValue(CalibrationDeadlineOutcome.ON_TIME),
                deadlineCounts.entries.sumOf { (outcome, count) ->
                    if (outcome == CalibrationDeadlineOutcome.NOT_SET) 0L else count
                },
            ))
            .put("deadline_violation_rate", ratioOrNull(
                deadlineCounts.getValue(CalibrationDeadlineOutcome.LATE) +
                    deadlineCounts.getValue(CalibrationDeadlineOutcome.NOT_COMPLETED),
                deadlineCounts.entries.sumOf { (outcome, count) ->
                    if (outcome == CalibrationDeadlineOutcome.NOT_SET) 0L else count
                },
            ))
            .put("thermal_sample_count", thermalSampleCount)
        writeNewSynced(File(root, SUMMARY_FILE), summary.toString().toByteArray(Charsets.UTF_8))

        val files = artifactFiles(root)
        val actualPaths = files.map { it.relativeTo(root).invariantSeparatorsPath }.toSet()
        val contractPaths = contractArtifactPaths(root)
        check(actualPaths == contractPaths) {
            "calibration artifact set violates the fixed contract: " +
                "unexpected=${(actualPaths - contractPaths).sorted()}, " +
                "missing=${(contractPaths - actualPaths).sorted()}"
        }
        val entries = files.map { file ->
            CalibrationArtifactEntry(
                relativePath = file.relativeTo(root).invariantSeparatorsPath,
                byteCount = file.length(),
                sha256 = sha256File(file),
            )
        }.sortedBy { it.relativePath }
        val provenance = JSONObject()
            .put("schema_version", CalibrationContract.SCHEMA_VERSION)
            .put("protocol_version", CalibrationContract.PROTOCOL_VERSION)
            .put("session_id", manifest.sessionId)
            .put("manifest_sha256", manifest.manifestSha256)
            .put("apk_sha256", actualApkSha256)
            .put("model_sha256", actualModelSha256)
            .put("artifact_set", JSONArray().apply {
                entries.forEach { entry ->
                    put(JSONObject()
                        .put("relative_path", entry.relativePath)
                        .put("byte_count", entry.byteCount)
                        .put("sha256", entry.sha256))
                }
            })
        writeNewSynced(
            File(root, PROVENANCE_FILE),
            provenance.toString().toByteArray(Charsets.UTF_8),
        )
        finalized = true
        CalibrationArtifactValidator.validate(root, manifest.sessionId)
        return entries
    }

    override fun close() {
        environmentSampler.shutdownNow()
        if (!finalized) {
            requestStream.close()
            synchronized(this) { thermalStream.close() }
        }
    }

    @Synchronized
    private fun sampleEnvironment() {
        recordThermalSample(thermalProvider.sample())
    }

    private fun recordThermalSample(sample: CalibrationThermalSample) {
        require(sample.timestampNs >= startMonoNs) { "thermal sample predates session" }
        require(lastThermalTimestampNs == null ||
            sample.timestampNs >= checkNotNull(lastThermalTimestampNs)) {
            "thermal sample timestamps are not monotonic"
        }
        require(sample.thermalStatus == null || sample.thermalStatus in 0..6) {
            "Android thermal status is out of range"
        }
        lastThermalTimestampNs = sample.timestampNs
        highestBatteryTemperatureDeciC = maxNullable(
            highestBatteryTemperatureDeciC,
            sample.batteryTemperatureDeciC,
        )
        highestThermalStatus = maxNullable(highestThermalStatus, sample.thermalStatus)
        val line = JSONObject()
            .put("schema_version", CalibrationContract.SCHEMA_VERSION)
            .put("protocol_version", CalibrationContract.PROTOCOL_VERSION)
            .put("session_id", manifest.sessionId)
            .put("calibration_mode", manifest.calibrationMode.wireName)
            .put("timestamp_ns", sample.timestampNs)
            .put("thermal_status", sample.thermalStatus ?: JSONObject.NULL)
            .put("battery_temperature_deci_c",
                sample.batteryTemperatureDeciC ?: JSONObject.NULL)
            .toString() + "\n"
        thermalStream.write(line.toByteArray(Charsets.UTF_8))
        thermalStream.flush()
        thermalStream.fd.sync()
        thermalSampleCount++
    }

    companion object {
        const val METADATA_FILE = "metadata.json"
        const val INPUT_MANIFEST_FILE = "input_manifest.json"
        const val LABEL_MAPPING_FILE = "label_mapping.txt"
        const val REQUESTS_FILE = "requests.jsonl"
        const val THERMAL_SAMPLES_FILE = "thermal_samples.jsonl"
        const val SUMMARY_FILE = "summary.json"
        const val PROVENANCE_FILE = "provenance.json"

        fun create(
            context: Context,
            manifestBytes: ByteArray,
            labelBytes: ByteArray,
            thermalProvider: CalibrationThermalProvider =
                AndroidCalibrationThermalProvider(context),
        ): Pair<CalibrationSessionArtifacts, CalibrationLabelMapping> {
            val manifest = CalibrationInputManifest.parse(manifestBytes)
            val labels = CalibrationLabelMapping.parse(labelBytes)
            check(labels.sha256 == manifest.labelMappingSha256) { "label mapping SHA-256 mismatch" }
            manifest.images.forEach { image ->
                check(labels.labels[image.labelIndex] == image.label) {
                    "image label_index/label mapping mismatch: ${image.imageId}"
                }
            }
            check(manifest.modelSha256.equals(ModelLoader.MODEL_SHA256, ignoreCase = true)) {
                "manifest model SHA-256 does not identify the packaged model"
            }
            check(manifest.preprocessingSha256 == MobileNetCalibrationPreprocessor.configurationSha256) {
                "preprocessing configuration SHA-256 mismatch"
            }
            check(manifest.preprocessingContractId == MobileNetCalibrationPreprocessor.CONTRACT_ID) {
                "preprocessing contract ID mismatch"
            }
            val apk = File(context.applicationInfo.sourceDir).canonicalFile
            check(apk.isFile) { "installed APK path is not a regular file" }
            val apkHash = sha256File(apk)
            check(apkHash == manifest.expectedApkSha256) { "installed APK SHA-256 mismatch" }
            val modelHash = context.assets.open(ModelLoader.ASSET_PATH).use { input ->
                CalibrationContract.sha256(input.readBytes())
            }
            check(modelHash.equals(manifest.modelSha256, ignoreCase = true)) {
                "packaged model SHA-256 mismatch"
            }
            val initialThermalSample = thermalProvider.sample()
            check(initialThermalSample.batteryTemperatureDeciC != null) {
                "start battery temperature is unavailable"
            }
            val startStatus = checkNotNull(initialThermalSample.thermalStatus) {
                "start Android thermal status is unavailable"
            }
            check(startStatus in 0..6) { "start Android thermal status is out of range" }
            if (manifest.calibrationMode != CalibrationSessionMode.THERMAL_STRESS) {
                check(startStatus <= 1) {
                    "baseline calibration start thermal status exceeds 1"
                }
            }
            manifest.temperaturePolicy?.let { policy ->
                check(checkNotNull(initialThermalSample.batteryTemperatureDeciC) <=
                    policy.maximumStartBatteryTemperatureDeciC) {
                    "baseline formal start battery temperature exceeds policy"
                }
            }
            val metadata = sessionMetadata(
                context, manifest, labels.sha256, apkHash, modelHash, initialThermalSample
            )

            val parent = requireNotNull(
                context.getExternalFilesDir(CalibrationContract.OUTPUT_DIRECTORY)
            ).canonicalFile
            parent.mkdirs()
            val root = File(parent, manifest.sessionId).canonicalFile
            check(root.parentFile == parent) { "calibration session path escapes output root" }
            check(root.mkdir()) { "calibration session directory already exists or cannot be created" }
            val results = File(root, "results")
            check(results.mkdir()) { "calibration results directory could not be created" }
            writeNewSynced(File(root, INPUT_MANIFEST_FILE), manifestBytes)
            writeNewSynced(File(root, LABEL_MAPPING_FILE), labelBytes)
            writeNewSynced(
                File(root, METADATA_FILE),
                metadata.toString().toByteArray(Charsets.UTF_8),
            )
            val requestFile = File(root, REQUESTS_FILE)
            check(requestFile.createNewFile()) { "request telemetry already exists" }
            val thermalFile = File(root, THERMAL_SAMPLES_FILE)
            check(thermalFile.createNewFile()) { "thermal sample artifact already exists" }
            return CalibrationSessionArtifacts(
                context,
                manifest,
                root,
                FileOutputStream(requestFile, true),
                FileOutputStream(thermalFile, true),
                thermalProvider,
                initialThermalSample,
                initialThermalSample.timestampNs,
                apkHash,
                modelHash,
            ) to labels
        }

        private fun sessionMetadata(
            context: Context,
            manifest: CalibrationInputManifest,
            labelSha: String,
            apkSha: String,
            modelSha: String,
            initialThermalSample: CalibrationThermalSample,
        ): JSONObject {
            @Suppress("DEPRECATION")
            val packageInfo = context.packageManager.getPackageInfo(context.packageName, 0)
            @Suppress("DEPRECATION")
            val versionCode = if (Build.VERSION.SDK_INT >= 28) {
                packageInfo.longVersionCode
            } else {
                packageInfo.versionCode.toLong()
            }
            val battery = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
            val power = context.getSystemService(PowerManager::class.java)
            val batteryStatus = battery?.getIntExtra(BatteryManager.EXTRA_STATUS, -1) ?: -1
            check(batteryStatus in setOf(
                BatteryManager.BATTERY_STATUS_CHARGING,
                BatteryManager.BATTERY_STATUS_DISCHARGING,
                BatteryManager.BATTERY_STATUS_FULL,
                BatteryManager.BATTERY_STATUS_NOT_CHARGING,
            )) { "battery charging status is unavailable" }
            val charging = batteryStatus in setOf(
                BatteryManager.BATTERY_STATUS_CHARGING,
                BatteryManager.BATTERY_STATUS_FULL,
            )
            val screenOn = power?.isInteractive
            check(screenOn != null) { "screen state is unavailable" }
            check(charging == manifest.environment.expectedCharging) {
                "charging state differs from calibration manifest"
            }
            check(screenOn == manifest.environment.expectedScreenOn) {
                "screen state differs from calibration manifest"
            }
            return JSONObject()
                .put("schema_version", CalibrationContract.SCHEMA_VERSION)
                .put("protocol_version", CalibrationContract.PROTOCOL_VERSION)
                .put("session_id", manifest.sessionId)
                .put("calibration_mode", manifest.calibrationMode.wireName)
                .put("clock", CalibrationContract.CLOCK)
                .put("manifest_sha256", manifest.manifestSha256)
                .put("model_sha256", modelSha)
                .put("label_mapping_sha256", labelSha)
                .put("preprocessing_sha256", manifest.preprocessingSha256)
                .put("preprocessing_contract_id", manifest.preprocessingContractId)
                .put("preprocessing_configuration", MobileNetCalibrationPreprocessor.CONFIGURATION)
                .put("temperature_policy_sha256",
                    manifest.temperaturePolicy?.sha256 ?: JSONObject.NULL)
                .put("apk_sha256", apkSha)
                .put("package_name", context.packageName)
                .put("version_code", versionCode)
                .put("version_name", packageInfo.versionName)
                .put("device", Build.DEVICE)
                .put("model", Build.MODEL)
                .put("build_fingerprint", Build.FINGERPRINT)
                .put("sdk_int", Build.VERSION.SDK_INT)
                .put("boot_id", readBootId())
                .put("physical_position", manifest.environment.physicalPosition)
                .put("ambient_temperature_c", manifest.environment.ambientTemperatureC)
                .put("charging", charging)
                .put("battery_status", batteryStatus)
                .put("battery_level", battery?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1))
                .put("battery_scale", battery?.getIntExtra(BatteryManager.EXTRA_SCALE, -1))
                .put("screen_on", screenOn)
                .put("screen_brightness", Settings.System.getInt(
                    context.contentResolver,
                    Settings.System.SCREEN_BRIGHTNESS,
                    -1,
                ))
                .put("orientation", context.resources.configuration.orientation)
                .put("start_battery_temperature_deci_c",
                    initialThermalSample.batteryTemperatureDeciC)
                .put("start_thermal_status", initialThermalSample.thermalStatus)
                .put("start_thermal_sample_ns", initialThermalSample.timestampNs)
                .put("durability", CalibrationContract.DURABILITY)
                .put("deadline_state", "calibration_pending")
        }
    }
}

internal object CalibrationArtifactValidator {
    fun validate(root: File, expectedSessionId: String): List<CalibrationArtifactEntry> {
        check(!isSymbolicLink(root)) {
            "symlink calibration root rejected"
        }
        val canonicalRoot = root.canonicalFile
        check(canonicalRoot.isDirectory)
        check(canonicalRoot.walkTopDown().none {
            isSymbolicLink(it)
        }) { "symlink in calibration artifact tree rejected" }
        val provenanceFile = File(canonicalRoot, CalibrationSessionArtifacts.PROVENANCE_FILE)
        check(provenanceFile.isFile) { "calibration provenance is missing" }
        val provenance = JSONObject(provenanceFile.readText(Charsets.UTF_8))
        check(provenance.keys().asSequence().toSet() == setOf(
            "schema_version", "protocol_version", "session_id", "manifest_sha256",
            "apk_sha256", "model_sha256", "artifact_set",
        )) { "calibration provenance field set mismatch" }
        check(provenance.getInt("schema_version") == CalibrationContract.SCHEMA_VERSION)
        check(provenance.getString("protocol_version") == CalibrationContract.PROTOCOL_VERSION)
        check(provenance.getString("session_id") == expectedSessionId)
        CalibrationContract.canonicalSha256(provenance.getString("manifest_sha256"), "manifest sha256")
        CalibrationContract.canonicalSha256(provenance.getString("apk_sha256"), "apk sha256")
        CalibrationContract.canonicalSha256(provenance.getString("model_sha256"), "model sha256")
        val expected = mutableMapOf<String, CalibrationArtifactEntry>()
        val array = provenance.getJSONArray("artifact_set")
        repeat(array.length()) { index ->
            val item = array.getJSONObject(index)
            check(item.keys().asSequence().toSet() == setOf(
                "relative_path", "byte_count", "sha256"
            )) { "calibration artifact entry field set mismatch" }
            val path = item.getString("relative_path")
            check(path.isNotBlank() && !path.startsWith("/") && !path.contains("..") &&
                !path.contains('\\')) { "unsafe calibration artifact path" }
            val entry = CalibrationArtifactEntry(
                path,
                item.getLong("byte_count"),
                CalibrationContract.canonicalSha256(item.getString("sha256"), "artifact sha256"),
            )
            check(expected.put(path, entry) == null) { "duplicate calibration artifact" }
        }
        val actualFiles = artifactFiles(canonicalRoot)
        val actualPaths = actualFiles.map { it.relativeTo(canonicalRoot).invariantSeparatorsPath }.toSet()
        check(actualPaths == expected.keys) {
            "calibration artifact set mismatch: " +
                "unexpected=${(actualPaths - expected.keys).sorted()}, " +
                "missing=${(expected.keys - actualPaths).sorted()}"
        }
        check(actualPaths.containsAll(setOf(
            CalibrationSessionArtifacts.INPUT_MANIFEST_FILE,
            CalibrationSessionArtifacts.LABEL_MAPPING_FILE,
            CalibrationSessionArtifacts.METADATA_FILE,
            CalibrationSessionArtifacts.REQUESTS_FILE,
            CalibrationSessionArtifacts.THERMAL_SAMPLES_FILE,
            CalibrationSessionArtifacts.SUMMARY_FILE,
        ))) { "required calibration artifact is missing" }
        actualFiles.forEach { file ->
            check(!isSymbolicLink(file)) { "symlink artifact rejected" }
            val canonical = file.canonicalFile
            check(canonical.path.startsWith(canonicalRoot.path + File.separator)) {
                "calibration artifact escapes session root"
            }
            val path = canonical.relativeTo(canonicalRoot).invariantSeparatorsPath
            val entry = expected.getValue(path)
            check(canonical.isFile && canonical.length() == entry.byteCount)
            check(sha256File(canonical) == entry.sha256) { "calibration artifact SHA-256 mismatch" }
        }
        val contractPaths = contractArtifactPaths(canonicalRoot)
        check(actualPaths == contractPaths) {
            "calibration artifact set violates the fixed contract: " +
                "unexpected=${(actualPaths - contractPaths).sorted()}, " +
                "missing=${(contractPaths - actualPaths).sorted()}"
        }
        validateIdentity(canonicalRoot, expectedSessionId, provenance)
        return expected.values.sortedBy { it.relativePath }
    }

    private fun validateIdentity(root: File, sessionId: String, provenance: JSONObject) {
        fun checkIdentity(value: JSONObject) {
            check(value.getInt("schema_version") == CalibrationContract.SCHEMA_VERSION)
            check(value.getString("protocol_version") == CalibrationContract.PROTOCOL_VERSION)
            check(value.getString("session_id") == sessionId)
        }
        val inputManifestFile = File(root, CalibrationSessionArtifacts.INPUT_MANIFEST_FILE)
        check(sha256File(inputManifestFile) == provenance.getString("manifest_sha256"))
        val inputManifest = CalibrationInputManifest.parse(inputManifestFile.readBytes())
        check(inputManifest.sessionId == sessionId)
        val labelFile = File(root, CalibrationSessionArtifacts.LABEL_MAPPING_FILE)
        check(sha256File(labelFile) == inputManifest.labelMappingSha256)
        val metadata = JSONObject(File(root, CalibrationSessionArtifacts.METADATA_FILE).readText())
        checkIdentity(metadata)
        check(metadata.getString("calibration_mode") == inputManifest.calibrationMode.wireName)
        check(metadata.getString("manifest_sha256") == inputManifest.manifestSha256)
        check(metadata.getString("label_mapping_sha256") == inputManifest.labelMappingSha256)
        check(metadata.getString("preprocessing_sha256") == inputManifest.preprocessingSha256)
        check(metadata.getString("preprocessing_contract_id") ==
            inputManifest.preprocessingContractId)
        check(metadata.getString("preprocessing_configuration") ==
            MobileNetCalibrationPreprocessor.CONFIGURATION)
        if (inputManifest.temperaturePolicy == null) {
            check(metadata.isNull("temperature_policy_sha256"))
        } else {
            check(metadata.getString("temperature_policy_sha256") ==
                inputManifest.temperaturePolicy.sha256)
        }
        check(metadata.getString("apk_sha256") == provenance.getString("apk_sha256"))
        check(metadata.getString("model_sha256") == provenance.getString("model_sha256"))
        check(metadata.getString("apk_sha256") == inputManifest.expectedApkSha256)
        check(metadata.getString("model_sha256") == inputManifest.modelSha256)
        val summary = JSONObject(File(root, CalibrationSessionArtifacts.SUMMARY_FILE).readText())
        checkIdentity(summary)
        check(summary.getString("calibration_mode") == inputManifest.calibrationMode.wireName)
        val thermalStartNs = metadata.getLong("start_thermal_sample_ns")
        val thermalEndNs = summary.getLong("end_mono_ns")
        check(thermalStartNs >= 0L && summary.getLong("start_mono_ns") == thermalStartNs &&
            thermalEndNs >= thermalStartNs) { "thermal session bounds mismatch" }
        val thermalFile = File(root, CalibrationSessionArtifacts.THERMAL_SAMPLES_FILE)
        check(thermalFile.length() > 0L) { "thermal sample telemetry is empty" }
        var previousThermalTimestamp: Long? = null
        var thermalCount = 0L
        thermalFile.forEachLine(Charsets.UTF_8) { line ->
            check(line.isNotBlank()) { "blank thermal sample line" }
            val sample = JSONObject(line)
            check(sample.keys().asSequence().toSet() == setOf(
                "schema_version", "protocol_version", "session_id", "calibration_mode",
                "timestamp_ns", "thermal_status", "battery_temperature_deci_c",
            )) { "thermal sample field set mismatch" }
            checkIdentity(sample)
            check(sample.getString("calibration_mode") == inputManifest.calibrationMode.wireName) {
                "thermal sample calibration mode mismatch"
            }
            val timestamp = sample.getLong("timestamp_ns")
            check(timestamp in thermalStartNs..thermalEndNs &&
                (previousThermalTimestamp == null ||
                timestamp >= checkNotNull(previousThermalTimestamp))) {
                "thermal sample timestamps are not monotonic"
            }
            if (thermalCount == 0L) {
                check(timestamp == thermalStartNs) { "initial thermal timestamp mismatch" }
            }
            if (!sample.isNull("thermal_status")) {
                check(sample.getInt("thermal_status") in 0..6) {
                    "Android thermal status is out of range"
                }
            }
            previousThermalTimestamp = timestamp
            thermalCount++
        }
        check(summary.getLong("thermal_sample_count") == thermalCount)
        val requestIds = mutableSetOf<String>()
        val counts = CalibrationTerminalStatus.entries.associateWith { 0L }.toMutableMap()
        val requestFile = File(root, CalibrationSessionArtifacts.REQUESTS_FILE)
        check(requestFile.length() > 0L) { "request telemetry is empty" }
        requestFile.forEachLine(Charsets.UTF_8) { line ->
            check(line.isNotBlank()) { "blank request telemetry line" }
            val request = JSONObject(line)
            checkIdentity(request)
            check(request.getString("calibration_mode") == inputManifest.calibrationMode.wireName) {
                "request calibration mode mismatch"
            }
            val requestId = CalibrationContract.canonicalUuid(
                request.getString("request_id"), "request_id"
            )
            check(requestIds.add(requestId)) { "duplicate calibration request_id" }
            val status = CalibrationTerminalStatus.entries.singleOrNull {
                it.wireName == request.getString("terminal_status")
            } ?: error("invalid calibration terminal status")
            val requestType = CalibrationRequestType.entries.singleOrNull {
                it.wireName == request.getString("request_type")
            } ?: error("invalid calibration request type")
            counts[status] = counts.getValue(status) + 1L
            val deadlineOutcome = CalibrationDeadlineOutcome.entries.singleOrNull {
                it.wireName == request.getString("deadline_outcome")
            } ?: error("invalid deadline outcome")
            val deadlineNs = if (request.isNull("deadline_ns")) null else {
                request.getLong("deadline_ns")
            }
            val completionNs = when (requestType) {
                CalibrationRequestType.URGENT -> if (request.isNull("output_ready_ns")) {
                    null
                } else request.getLong("output_ready_ns")
                CalibrationRequestType.NORMAL -> if (request.isNull("persistence_completed_ns")) {
                    null
                } else request.getLong("persistence_completed_ns")
            }
            val expectedDeadlineOutcome = when {
                deadlineNs == null -> CalibrationDeadlineOutcome.NOT_SET
                status != CalibrationTerminalStatus.SUCCEEDED ->
                    CalibrationDeadlineOutcome.NOT_COMPLETED
                checkNotNull(completionNs) < deadlineNs -> CalibrationDeadlineOutcome.ON_TIME
                else -> CalibrationDeadlineOutcome.LATE
            }
            check(deadlineOutcome == expectedDeadlineOutcome) {
                "terminal/deadline outcome mismatch"
            }
            val expectedDeadlineMet = when (deadlineOutcome) {
                CalibrationDeadlineOutcome.NOT_SET -> null
                CalibrationDeadlineOutcome.ON_TIME -> true
                CalibrationDeadlineOutcome.LATE,
                CalibrationDeadlineOutcome.NOT_COMPLETED -> false
            }
            check(if (expectedDeadlineMet == null) request.isNull("deadline_met") else
                request.getBoolean("deadline_met") == expectedDeadlineMet)
            if (status == CalibrationTerminalStatus.SUCCEEDED) {
                check(!request.isNull("output_sha256")) { "succeeded request output is missing" }
            } else {
                check(request.isNull("output_sha256") &&
                    request.isNull("persisted_relative_path")) {
                    "non-succeeded request contains output or persistence"
                }
            }
            if (requestType == CalibrationRequestType.NORMAL &&
                status == CalibrationTerminalStatus.SUCCEEDED
            ) {
                val expectedPath = "results/$requestId.json"
                check(request.getString("persisted_relative_path") == expectedPath) {
                    "normal persistence path mismatch"
                }
                val result = File(root, expectedPath).canonicalFile
                check(result.isFile && result.parentFile == File(root, "results").canonicalFile)
                val stored = JSONObject(result.readText())
                check(stored.getString("request_id") == requestId)
                check(stored.getString("protocol_version") == CalibrationContract.PROTOCOL_VERSION)
            } else {
                check(request.isNull("persisted_relative_path")) {
                    "non-success result must not reference a persistence artifact"
                }
            }
        }
        val summaryCounts = summary.getJSONObject("counts")
        counts.forEach { (status, count) ->
            check(summaryCounts.getLong(status.wireName) == count) {
                "summary terminal count mismatch"
            }
        }
        val deadlineSummary = summary.getJSONObject("deadline_counts")
        val computedDeadlineCounts = CalibrationDeadlineOutcome.entries.associateWith { outcome ->
            var count = 0L
            requestFile.forEachLine(Charsets.UTF_8) { line ->
                if (JSONObject(line).getString("deadline_outcome") == outcome.wireName) count++
            }
            count
        }
        computedDeadlineCounts.forEach { (outcome, count) ->
            check(deadlineSummary.getLong(outcome.wireName) == count) {
                "summary deadline count mismatch"
            }
        }
        val arrived = counts.values.sum()
        val completed = counts.getValue(CalibrationTerminalStatus.SUCCEEDED)
        val deadlineSet = computedDeadlineCounts.entries.sumOf { (outcome, count) ->
            if (outcome == CalibrationDeadlineOutcome.NOT_SET) 0L else count
        }
        check(summary.getLong("arrived_count") == arrived)
        check(summary.getLong("completed_count") == completed)
        check(summary.getLong("deadline_set_count") == deadlineSet)
        checkRate(summary, "overall_completion_rate", completed, arrived)
        checkRate(
            summary, "on_time_completion_rate",
            computedDeadlineCounts.getValue(CalibrationDeadlineOutcome.ON_TIME), deadlineSet,
        )
        checkRate(
            summary, "deadline_violation_rate",
            computedDeadlineCounts.getValue(CalibrationDeadlineOutcome.LATE) +
                computedDeadlineCounts.getValue(CalibrationDeadlineOutcome.NOT_COMPLETED),
            deadlineSet,
        )
    }
}

private fun CalibrationRequestResult.toJson(
    sessionId: String,
    calibrationMode: CalibrationSessionMode,
): JSONObject = JSONObject()
    .put("schema_version", CalibrationContract.SCHEMA_VERSION)
    .put("protocol_version", CalibrationContract.PROTOCOL_VERSION)
    .put("session_id", sessionId)
    .put("calibration_mode", calibrationMode.wireName)
    .put("request_id", request.requestId)
    .put("request_type", request.requestType.wireName)
    .put("image_id", request.image.imageId)
    .put("image_sha256", request.image.sha256)
    .put("image_mime_type", request.image.mimeType)
    .put("image_relative_path", request.image.relativePath)
    .put("image_byte_count", request.image.byteCount)
    .put("label_index", request.image.labelIndex)
    .put("raw_width", request.image.rawWidth)
    .put("raw_height", request.image.rawHeight)
    .put("exif_orientation", request.image.exifOrientation)
    .put("transformed_width", request.image.transformedWidth)
    .put("transformed_height", request.image.transformedHeight)
    .put("terminal_status", terminalStatus.wireName)
    .put("deadline_outcome", deadlineOutcome.wireName)
    .put("deadline_met", deadlineMet ?: JSONObject.NULL)
    .put("requested_backend", request.requestedBackend.wireName)
    .put("actual_backend", actualBackend?.wireName)
    .put("fallback_status", fallbackStatus.wireName)
    .put("execution_class", executionClass?.wireName)
    .put("transition", transition)
    .put("warmup", request.isWarmup)
    .put("deadline_ns", request.deadlineNs)
    .put("picker_result_received_ns", timestamps.pickerResultReceivedNs)
    .put("request_accepted_ns", timestamps.acceptedNs)
    .put("queue_enqueue_ns", timestamps.acceptedNs)
    .put("queue_enter_ns", timestamps.acceptedNs)
    .put("execution_start_ns", timestamps.executionStartNs)
    .put("image_read_start_ns", timestamps.imageReadStartNs)
    .put("image_read_end_ns", timestamps.imageReadEndNs)
    .put("decode_start_ns", timestamps.decodeStartNs)
    .put("decode_end_ns", timestamps.decodeEndNs)
    .put("preprocessing_start_ns", timestamps.preprocessingStartNs)
    .put("preprocessing_end_ns", timestamps.preprocessingEndNs)
    .put("preprocess_start_ns", timestamps.preprocessingStartNs)
    .put("preprocess_end_ns", timestamps.preprocessingEndNs)
    .put("scheduler_decision_start_ns", timestamps.schedulerDecisionStartNs)
    .put("scheduler_decision_end_ns", timestamps.schedulerDecisionEndNs)
    .put("backend_prepare_start_ns", timestamps.backendPrepareStartNs)
    .put("backend_prepare_end_ns", timestamps.backendPrepareEndNs)
    .put("interpreter_run_start_ns", timestamps.interpreterRunStartNs)
    .put("interpreter_run_end_ns", timestamps.interpreterRunEndNs)
    .put("inference_start_ns", timestamps.interpreterRunStartNs)
    .put("inference_end_ns", timestamps.interpreterRunEndNs)
    .put("postprocessing_start_ns", timestamps.postprocessingStartNs)
    .put("postprocessing_end_ns", timestamps.postprocessingEndNs)
    .put("postprocess_start_ns", timestamps.postprocessingStartNs)
    .put("postprocess_end_ns", timestamps.postprocessingEndNs)
    .put("output_ready_ns", timestamps.outputReadyNs)
    .put("persistence_start_ns", timestamps.persistenceStartNs)
    .put("persistence_completed_ns", timestamps.persistenceCompletedNs)
    .put("persist_start_ns", timestamps.persistenceStartNs)
    .put("persist_commit_ns", timestamps.persistenceCompletedNs)
    .put("terminal_ns", timestamps.terminalNs)
    .put("queue_wait_ns", queueWaitNs)
    .put("end_to_end_ns", endToEndNs)
    .put("input_tensor_sha256", inputTensorSha256)
    .put("output_sha256", output?.outputSha256)
    .put("non_finite_count", output?.nonFiniteCount)
    .put("top_indices", output?.let { JSONArray(it.topIndices) })
    .put("top_labels", output?.let { JSONArray(it.topLabels) })
    .put("expected_label", request.image.label)
    .put("top1_correct", output?.let { it.topLabels.firstOrNull() == request.image.label })
    .put("top5_correct", output?.let { request.image.label in it.topLabels })
    .put("persisted_relative_path", persistedRelativePath)
    .put("durability", if (request.requestType == CalibrationRequestType.NORMAL) {
        CalibrationContract.DURABILITY
    } else null)
    .put("error", error)

private fun artifactFiles(root: File): List<File> = root.walkTopDown()
    .filter {
        it.isFile && it.relativeTo(root).normalize().invariantSeparatorsPath !=
            CalibrationSessionArtifacts.PROVENANCE_FILE
    }
    .sortedBy { it.relativeTo(root).normalize().invariantSeparatorsPath }
    .toList()

private fun contractArtifactPaths(root: File): Set<String> {
    val expected = mutableSetOf(
        CalibrationSessionArtifacts.INPUT_MANIFEST_FILE,
        CalibrationSessionArtifacts.LABEL_MAPPING_FILE,
        CalibrationSessionArtifacts.METADATA_FILE,
        CalibrationSessionArtifacts.REQUESTS_FILE,
        CalibrationSessionArtifacts.THERMAL_SAMPLES_FILE,
        CalibrationSessionArtifacts.SUMMARY_FILE,
    )
    val requestFile = File(root, CalibrationSessionArtifacts.REQUESTS_FILE)
    check(requestFile.isFile && requestFile.length() > 0L) { "request telemetry is empty" }
    requestFile.forEachLine(Charsets.UTF_8) { line ->
        check(line.isNotBlank()) { "blank request telemetry line" }
        val request = JSONObject(line)
        val requestId = CalibrationContract.canonicalUuid(
            request.getString("request_id"), "request_id"
        )
        val normalSuccess = request.getString("request_type") ==
            CalibrationRequestType.NORMAL.wireName &&
            request.getString("terminal_status") == CalibrationTerminalStatus.SUCCEEDED.wireName
        if (normalSuccess) {
            val path = "results/$requestId.json"
            check(request.getString("persisted_relative_path") == path) {
                "normal persistence path mismatch"
            }
            expected += path
        } else {
            check(request.isNull("persisted_relative_path")) {
                "non-success result must not reference a persistence artifact"
            }
        }
    }
    return expected
}

private fun writeNewSynced(file: File, bytes: ByteArray) {
    check(file.createNewFile()) { "artifact already exists: ${file.name}" }
    FileOutputStream(file).use {
        it.write(bytes)
        it.flush()
        it.fd.sync()
    }
}

private fun ratioOrNull(numerator: Long, denominator: Long): Any =
    if (denominator == 0L) JSONObject.NULL else numerator.toDouble() / denominator.toDouble()

private fun checkRate(summary: JSONObject, key: String, numerator: Long, denominator: Long) {
    if (denominator == 0L) {
        check(summary.isNull(key)) { "$key must be null without a denominator" }
    } else {
        val expected = numerator.toDouble() / denominator.toDouble()
        check(kotlin.math.abs(summary.getDouble(key) - expected) <= 1e-12) {
            "$key mismatch"
        }
    }
}

private fun readBatteryTemperatureDeciC(context: Context): Int? = context
    .registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
    ?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, Int.MIN_VALUE)
    ?.takeUnless { it == Int.MIN_VALUE }

private fun readThermalStatus(context: Context): Int? = if (Build.VERSION.SDK_INT >= 29) {
    context.getSystemService(PowerManager::class.java)?.currentThermalStatus
} else null

private fun readBootId(): String? = try {
    File("/proc/sys/kernel/random/boot_id").readText().trim().takeIf { it.isNotEmpty() }
} catch (_: java.io.IOException) {
    null
}

private fun maxNullable(first: Int?, second: Int?): Int? = when {
    first == null -> second
    second == null -> first
    else -> maxOf(first, second)
}

private fun isSymbolicLink(file: File): Boolean =
    file.absoluteFile.canonicalPath != file.absoluteFile.path
