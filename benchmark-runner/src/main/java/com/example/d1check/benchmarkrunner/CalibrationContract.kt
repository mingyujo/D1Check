package com.example.d1check.benchmarkrunner

import org.json.JSONArray
import org.json.JSONObject
import java.security.MessageDigest
import java.util.Locale
import java.util.UUID

internal object CalibrationContract {
    const val PROTOCOL_VERSION = "calibration-v1"
    const val SCHEMA_VERSION = 2
    const val OUTPUT_DIRECTORY = "calibration-v1"
    const val DURABILITY =
        "app_private_file_fd_sync_atomic_rename_and_readback_not_storage_controller_flush"
    const val CLOCK = "android_elapsed_realtime_nanos"
    const val MAX_QUEUE_CAPACITY = 64
    const val MAX_IMAGE_BYTES = 32 * 1024 * 1024

    fun canonicalUuid(value: String, label: String): String {
        val parsed = try {
            UUID.fromString(value)
        } catch (error: IllegalArgumentException) {
            throw IllegalArgumentException("$label must be a canonical UUID", error)
        }
        val canonical = parsed.toString()
        require(canonical == value) { "$label must be a canonical UUID" }
        return canonical
    }

    fun canonicalSha256(value: String, label: String): String {
        val normalized = value.lowercase(Locale.ROOT)
        require(normalized.matches(Regex("[0-9a-f]{64}"))) { "$label must be SHA-256" }
        return normalized
    }

    fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256")
        .digest(bytes)
        .joinToString("") { "%02x".format(it) }
}

internal enum class CalibrationRequestType(val wireName: String) {
    URGENT("urgent"),
    NORMAL("normal"),
}

internal enum class CalibrationTerminalStatus(val wireName: String) {
    SUCCEEDED("succeeded"),
    FAILED("failed"),
    REJECTED("rejected"),
    EXPIRED("expired"),
}

internal enum class CalibrationDeadlineOutcome(val wireName: String) {
    NOT_SET("not_set"),
    ON_TIME("on_time"),
    LATE("late"),
    NOT_COMPLETED("not_completed"),
}

internal enum class CalibrationSessionMode(val wireName: String) {
    BASELINE_PILOT("baseline_pilot"),
    BASELINE_FORMAL("baseline_formal"),
    THERMAL_STRESS("thermal_stress"),
}

internal enum class CalibrationBackend(val wireName: String) {
    CPU("CPU"),
    GPU("GPU"),
}

internal enum class CalibrationMode(val wireName: String) {
    FIXED("fixed"),
    TRANSITION_PROBE("transition_probe"),
}

internal enum class CalibrationThermalClass(val wireName: String) {
    COLD("cold"),
    WARMUP("warmup"),
    WARM("warm"),
}

internal enum class CalibrationFallbackStatus(val wireName: String) {
    NOT_APPLICABLE("not_applicable"),
    NOT_DETECTED("not_detected"),
    DETECTED("detected"),
    UNVERIFIED("unverified_requires_host_delegate_log"),
}

internal data class CalibrationImageSpec(
    val imageId: String,
    val relativePath: String,
    val sha256: String,
    val byteCount: Long,
    val labelIndex: Int,
    val label: String,
    val rawWidth: Int,
    val rawHeight: Int,
    val exifOrientation: Int,
    val transformedWidth: Int,
    val transformedHeight: Int,
    val mimeType: String,
) {
    init {
        require(imageId.matches(Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,127}"))) {
            "image_id is invalid"
        }
        require(relativePath.matches(Regex("images/[A-Za-z0-9][A-Za-z0-9._-]{0,127}"))) {
            "image relative_path is invalid"
        }
        CalibrationContract.canonicalSha256(sha256, "image sha256")
        require(byteCount > 0L) { "image byte_count must be positive" }
        require(labelIndex in 0..1000) { "label_index is out of range" }
        require(label.isNotBlank()) { "label is required" }
        require(rawWidth > 0 && rawHeight > 0) { "raw image dimensions must be positive" }
        require(exifOrientation in 1..8) { "EXIF orientation must be in 1..8" }
        require(transformedWidth > 0 && transformedHeight > 0) {
            "transformed image dimensions must be positive"
        }
        val expectedTransformed = if (exifOrientation in 5..8) {
            rawHeight to rawWidth
        } else {
            rawWidth to rawHeight
        }
        require(transformedWidth == expectedTransformed.first &&
            transformedHeight == expectedTransformed.second) {
            "transformed dimensions do not match EXIF orientation"
        }
        require(mimeType in setOf("image/jpeg", "image/png", "image/webp")) {
            "unsupported image mime type: $mimeType"
        }
    }
}

internal data class CalibrationTemperaturePolicy(
    val policyId: String,
    val maximumStartBatteryTemperatureDeciC: Int,
    val stabilityWindowMs: Long,
    val maximumStabilityDeltaDeciC: Int,
    val sha256: String,
) {
    init {
        require(policyId.matches(Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,127}")))
        require(maximumStartBatteryTemperatureDeciC in -500..1000)
        require(stabilityWindowMs in 1_000L..3_600_000L)
        require(maximumStabilityDeltaDeciC in 0..100)
        require(sha256 == computedSha256()) { "temperature policy SHA-256 mismatch" }
    }

    fun canonicalConfiguration(): String = listOf(
        "policy_id=$policyId",
        "maximum_start_battery_temperature_deci_c=$maximumStartBatteryTemperatureDeciC",
        "stability_window_ms=$stabilityWindowMs",
        "maximum_stability_delta_deci_c=$maximumStabilityDeltaDeciC",
    ).joinToString("|")

    fun computedSha256(): String = CalibrationContract.sha256(
        canonicalConfiguration().toByteArray(Charsets.UTF_8)
    )
}

internal data class CalibrationEnvironmentPlan(
    val physicalPosition: String,
    val ambientTemperatureC: Double?,
    val expectedCharging: Boolean,
    val expectedScreenOn: Boolean,
) {
    init {
        require(physicalPosition.isNotBlank()) { "physical_position is required" }
        require(ambientTemperatureC == null || ambientTemperatureC.isFinite())
    }
}

internal data class CalibrationInputManifest(
    val sessionId: String,
    val calibrationMode: CalibrationSessionMode,
    val mode: CalibrationMode,
    val fixedBackend: CalibrationBackend?,
    val cpuThreads: Int,
    val queueCapacity: Int,
    val warmupCount: Int,
    val modelSha256: String,
    val labelMappingSha256: String,
    val preprocessingSha256: String,
    val preprocessingContractId: String,
    val expectedApkSha256: String,
    val temperaturePolicy: CalibrationTemperaturePolicy?,
    val environment: CalibrationEnvironmentPlan,
    val images: List<CalibrationImageSpec>,
    val manifestSha256: String,
) {
    init {
        CalibrationContract.canonicalUuid(sessionId, "session_id")
        require((mode == CalibrationMode.FIXED) == (fixedBackend != null)) {
            "fixed_backend is required only in fixed mode"
        }
        require(cpuThreads in 1..RunConfig.MAX_CPU_THREADS)
        require(queueCapacity in 1..CalibrationContract.MAX_QUEUE_CAPACITY)
        require(warmupCount in 0..20)
        CalibrationContract.canonicalSha256(modelSha256, "model_sha256")
        CalibrationContract.canonicalSha256(labelMappingSha256, "label_mapping_sha256")
        CalibrationContract.canonicalSha256(preprocessingSha256, "preprocessing_sha256")
        require(preprocessingContractId.matches(Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,127}")))
        CalibrationContract.canonicalSha256(expectedApkSha256, "expected_apk_sha256")
        require((calibrationMode == CalibrationSessionMode.BASELINE_FORMAL) ==
            (temperaturePolicy != null)) {
            "temperature_policy is required only for baseline_formal"
        }
        require(images.isNotEmpty()) { "images must not be empty" }
        require(images.map { it.imageId }.distinct().size == images.size) {
            "duplicate image_id"
        }
        require(images.map { it.relativePath }.distinct().size == images.size) {
            "duplicate image relative_path"
        }
        require(images.map { it.sha256 }.distinct().size == images.size) {
            "duplicate image sha256"
        }
    }

    companion object {
        fun parse(bytes: ByteArray): CalibrationInputManifest {
            val root = JSONObject(bytes.toString(Charsets.UTF_8))
            require(root.getInt("schema_version") == CalibrationContract.SCHEMA_VERSION) {
                "unsupported calibration schema_version"
            }
            require(root.getString("protocol_version") == CalibrationContract.PROTOCOL_VERSION) {
                "unsupported calibration protocol_version"
            }
            val allowed = setOf(
                "schema_version", "protocol_version", "session_id", "calibration_mode", "mode",
                "fixed_backend", "cpu_threads", "queue_capacity", "warmup_count",
                "model_sha256", "label_mapping_sha256", "preprocessing_sha256",
                "preprocessing_contract_id", "expected_apk_sha256", "deadline_state",
                "temperature_policy", "environment", "images",
            )
            require(root.keys().asSequence().toSet() == allowed) {
                "calibration manifest field set mismatch"
            }
            val mode = CalibrationMode.entries.singleOrNull {
                it.wireName == root.getString("mode")
            } ?: error("unsupported calibration mode")
            val calibrationMode = CalibrationSessionMode.entries.singleOrNull {
                it.wireName == root.getString("calibration_mode")
            } ?: error("unsupported calibration session mode")
            val fixedBackend = if (root.isNull("fixed_backend")) null else {
                CalibrationBackend.entries.singleOrNull {
                    it.wireName == root.getString("fixed_backend")
                } ?: error("unsupported fixed_backend")
            }
            val imageArray = root.getJSONArray("images")
            require(root.getString("deadline_state") == "calibration_pending") {
                "absolute deadline must remain calibration_pending"
            }
            val environmentJson = root.getJSONObject("environment")
            val environmentAllowed = setOf(
                "physical_position", "ambient_temperature_c", "expected_charging",
                "expected_screen_on",
            )
            require(environmentJson.keys().asSequence().toSet() == environmentAllowed) {
                "calibration environment field set mismatch"
            }
            val images = buildList {
                repeat(imageArray.length()) { index ->
                    val image = imageArray.getJSONObject(index)
                    val imageAllowed = setOf(
                        "image_id", "relative_path", "sha256", "byte_count", "label_index",
                        "label", "raw_width", "raw_height", "exif_orientation",
                        "transformed_width", "transformed_height", "mime_type"
                    )
                    require(image.keys().asSequence().toSet() == imageAllowed) {
                        "image manifest field set mismatch"
                    }
                    add(
                        CalibrationImageSpec(
                            imageId = image.getString("image_id"),
                            relativePath = image.getString("relative_path"),
                            sha256 = CalibrationContract.canonicalSha256(
                                image.getString("sha256"), "image sha256"
                            ),
                            byteCount = image.getLong("byte_count"),
                            labelIndex = image.getInt("label_index"),
                            label = image.getString("label"),
                            rawWidth = image.getInt("raw_width"),
                            rawHeight = image.getInt("raw_height"),
                            exifOrientation = image.getInt("exif_orientation"),
                            transformedWidth = image.getInt("transformed_width"),
                            transformedHeight = image.getInt("transformed_height"),
                            mimeType = image.getString("mime_type"),
                        )
                    )
                }
            }
            val temperaturePolicy = if (root.isNull("temperature_policy")) null else {
                val policy = root.getJSONObject("temperature_policy")
                require(policy.keys().asSequence().toSet() == setOf(
                    "policy_id", "maximum_start_battery_temperature_deci_c",
                    "stability_window_ms", "maximum_stability_delta_deci_c", "sha256",
                )) { "temperature policy field set mismatch" }
                CalibrationTemperaturePolicy(
                    policyId = policy.getString("policy_id"),
                    maximumStartBatteryTemperatureDeciC =
                        policy.getInt("maximum_start_battery_temperature_deci_c"),
                    stabilityWindowMs = policy.getLong("stability_window_ms"),
                    maximumStabilityDeltaDeciC =
                        policy.getInt("maximum_stability_delta_deci_c"),
                    sha256 = CalibrationContract.canonicalSha256(
                        policy.getString("sha256"), "temperature policy sha256"
                    ),
                )
            }
            return CalibrationInputManifest(
                sessionId = CalibrationContract.canonicalUuid(
                    root.getString("session_id"), "session_id"
                ),
                calibrationMode = calibrationMode,
                mode = mode,
                fixedBackend = fixedBackend,
                cpuThreads = root.getInt("cpu_threads"),
                queueCapacity = root.getInt("queue_capacity"),
                warmupCount = root.getInt("warmup_count"),
                modelSha256 = CalibrationContract.canonicalSha256(
                    root.getString("model_sha256"), "model_sha256"
                ),
                labelMappingSha256 = CalibrationContract.canonicalSha256(
                    root.getString("label_mapping_sha256"), "label_mapping_sha256"
                ),
                preprocessingSha256 = CalibrationContract.canonicalSha256(
                    root.getString("preprocessing_sha256"), "preprocessing_sha256"
                ),
                preprocessingContractId = root.getString("preprocessing_contract_id"),
                expectedApkSha256 = CalibrationContract.canonicalSha256(
                    root.getString("expected_apk_sha256"), "expected_apk_sha256"
                ),
                temperaturePolicy = temperaturePolicy,
                environment = CalibrationEnvironmentPlan(
                    physicalPosition = environmentJson.getString("physical_position"),
                    ambientTemperatureC = if (environmentJson.isNull("ambient_temperature_c")) {
                        null
                    } else {
                        environmentJson.getDouble("ambient_temperature_c")
                    },
                    expectedCharging = environmentJson.getBoolean("expected_charging"),
                    expectedScreenOn = environmentJson.getBoolean("expected_screen_on"),
                ),
                images = images,
                manifestSha256 = CalibrationContract.sha256(bytes),
            )
        }
    }
}

internal data class CalibrationRequest(
    val requestId: String,
    val requestType: CalibrationRequestType,
    val image: CalibrationImageSpec,
    val imageUri: String,
    val requestedBackend: CalibrationBackend,
    val pickerResultReceivedNs: Long?,
    val acceptedNs: Long,
    val deadlineNs: Long?,
    val isWarmup: Boolean = false,
) {
    init {
        CalibrationContract.canonicalUuid(requestId, "request_id")
        require(imageUri.isNotBlank()) { "image URI is required" }
        require(acceptedNs >= 0L)
        require(pickerResultReceivedNs == null || pickerResultReceivedNs <= acceptedNs)
        require(deadlineNs == null || deadlineNs >= acceptedNs)
    }
}

internal data class ClassificationOutput(
    val topIndices: List<Int>,
    val topLabels: List<String>,
    val outputSha256: String,
    val nonFiniteCount: Int,
)

internal data class CalibrationTimestamps(
    val pickerResultReceivedNs: Long?,
    val acceptedNs: Long,
    var imageReadStartNs: Long? = null,
    var imageReadEndNs: Long? = null,
    var decodeStartNs: Long? = null,
    var decodeEndNs: Long? = null,
    var preprocessingStartNs: Long? = null,
    var preprocessingEndNs: Long? = null,
    var executionStartNs: Long? = null,
    var schedulerDecisionStartNs: Long? = null,
    var schedulerDecisionEndNs: Long? = null,
    var backendPrepareStartNs: Long? = null,
    var backendPrepareEndNs: Long? = null,
    var interpreterRunStartNs: Long? = null,
    var interpreterRunEndNs: Long? = null,
    var postprocessingStartNs: Long? = null,
    var postprocessingEndNs: Long? = null,
    var outputReadyNs: Long? = null,
    var persistenceStartNs: Long? = null,
    var persistenceCompletedNs: Long? = null,
    var terminalNs: Long? = null,
) {
    fun validateMonotonic(status: CalibrationTerminalStatus) {
        val ordered = listOfNotNull(
            acceptedNs,
            executionStartNs,
            imageReadStartNs,
            imageReadEndNs,
            decodeStartNs,
            decodeEndNs,
            preprocessingStartNs,
            preprocessingEndNs,
            schedulerDecisionStartNs,
            schedulerDecisionEndNs,
            backendPrepareStartNs,
            backendPrepareEndNs,
            interpreterRunStartNs,
            interpreterRunEndNs,
            postprocessingStartNs,
            postprocessingEndNs,
            outputReadyNs ?: persistenceStartNs,
            persistenceCompletedNs,
            terminalNs,
        )
        require(ordered.zipWithNext().all { (a, b) -> a <= b }) {
            "calibration timestamps are not monotonic"
        }
        if (status == CalibrationTerminalStatus.SUCCEEDED) {
            require(terminalNs != null)
        }
    }
}

internal data class CalibrationRequestResult(
    val request: CalibrationRequest,
    val terminalStatus: CalibrationTerminalStatus,
    val timestamps: CalibrationTimestamps,
    val actualBackend: CalibrationBackend?,
    val fallbackStatus: CalibrationFallbackStatus,
    val executionClass: CalibrationThermalClass?,
    val transition: String?,
    val inputTensorSha256: String?,
    val output: ClassificationOutput?,
    val persistedRelativePath: String?,
    val error: String?,
) {
    val completionNs: Long?
        get() = when (request.requestType) {
            CalibrationRequestType.URGENT -> timestamps.outputReadyNs
            CalibrationRequestType.NORMAL -> timestamps.persistenceCompletedNs
        }

    val deadlineOutcome: CalibrationDeadlineOutcome
        get() = when {
            request.deadlineNs == null -> CalibrationDeadlineOutcome.NOT_SET
            terminalStatus != CalibrationTerminalStatus.SUCCEEDED ->
                CalibrationDeadlineOutcome.NOT_COMPLETED
            checkNotNull(completionNs) < request.deadlineNs -> CalibrationDeadlineOutcome.ON_TIME
            else -> CalibrationDeadlineOutcome.LATE
        }

    val deadlineMet: Boolean?
        get() = when (deadlineOutcome) {
            CalibrationDeadlineOutcome.NOT_SET -> null
            CalibrationDeadlineOutcome.ON_TIME -> true
            CalibrationDeadlineOutcome.LATE,
            CalibrationDeadlineOutcome.NOT_COMPLETED -> false
        }

    val queueWaitNs: Long?
        get() = timestamps.executionStartNs?.minus(timestamps.acceptedNs)

    val endToEndNs: Long?
        get() = completionNs?.minus(timestamps.acceptedNs)
}

internal fun JSONArray.toStringList(): List<String> = buildList {
    repeat(length()) { add(getString(it)) }
}
