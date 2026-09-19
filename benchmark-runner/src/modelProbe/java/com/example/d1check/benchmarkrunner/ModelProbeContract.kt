package com.example.d1check.benchmarkrunner

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID

internal const val MODEL_PROBE_PROTOCOL = "model-probe-v1"
internal const val MODEL_PROBE_SCHEMA = 1

internal enum class ProbeTask(val wireName: String) {
    CLASSIFICATION("classification"),
    DETECTION("detection"),
    ;

    companion object {
        fun parse(value: String): ProbeTask = entries.firstOrNull { it.wireName == value }
            ?: throw IllegalArgumentException("Unsupported probe task: $value")
    }
}

internal enum class ProbeBackend {
    CPU,
    GPU,
}

internal data class ProbeIdentity(
    val sessionId: String,
    val createdUtc: String,
)

internal data class ProbeTarget(
    val deviceId: String,
    val packageName: String,
    val apkSha256: String,
    val adbSerial: String,
    val manufacturer: String,
    val model: String,
    val soc: String,
    val abi: String,
    val ramBytes: Long,
    val androidRelease: String,
    val apiLevel: Int,
    val buildFingerprint: String,
    val cpuAbi: String,
    val cpuFeatures: String,
    val gpuVendor: String,
    val gpuRenderer: String,
    val gpuDriver: String,
    val thermalCapability: String,
)

internal data class ProbeModel(
    val task: ProbeTask,
    val modelId: String,
    val url: String,
    val filename: String,
    val byteCount: Long,
    val sha256: String,
    val distributionPolicy: String,
    val labelFilename: String,
    val labelRows: Int,
    val labelSha256: String,
)

internal data class ProbeTensor(
    val index: Int,
    val name: String,
    val shape: IntArray,
    val dtype: String,
)

internal data class ProbeTensorContract(
    val inputs: List<ProbeTensor>,
    val outputs: List<ProbeTensor>,
    val normalization: String,
    val rawOutputSemantics: String,
)

internal data class ProbeRuntime(
    val litertVersion: String,
    val cpuThreads: Int,
    val xnnpack: Boolean,
    val gpuProfileId: String,
    val gpuConfigurationSha256: String,
    val tasksVisionVersion: String,
)

internal data class ProbeInput(
    val inputId: String,
    val kind: String,
    val generationRule: String,
    val seed: Int?,
    val url: String?,
    val filename: String?,
    val byteCount: Long,
    val sha256: String?,
    val decodeContract: String,
)

internal data class ProbeComparator(
    val comparatorId: String,
    val atol: Double,
    val rtol: Double,
    val relativeEpsilon: Double,
    val decodedBoxAtolPx: Double,
    val decodedScoreAtol: Double,
    val decodedOrder: String,
)

internal data class ProbeExecution(
    val backend: ProbeBackend,
    val coldRepetitions: Int,
    val warmRepetitions: Int,
    val maximumDurationMs: Long,
    val timeoutPolicy: String,
    val cleanupPolicy: String,
)

internal data class ModelProbeManifest(
    val identity: ProbeIdentity,
    val target: ProbeTarget,
    val model: ProbeModel,
    val tensor: ProbeTensorContract,
    val runtime: ProbeRuntime,
    val input: ProbeInput,
    val comparator: ProbeComparator,
    val execution: ProbeExecution,
)

internal object ModelProbeManifestParser {
    const val MAX_MANIFEST_BYTES = 256 * 1024L
    private val sha256Regex = Regex("[0-9a-f]{64}")
    private val filenameRegex = Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,126}")
    private val deviceIdRegex = Regex("[a-z0-9][a-z0-9._-]{0,63}")

    fun parse(file: File): ModelProbeManifest {
        require(file.isFile) { "Probe manifest is not a regular file" }
        require(file.length() in 1..MAX_MANIFEST_BYTES) { "Probe manifest byte count is invalid" }
        val bytes = file.readBytes()
        require(!(bytes.size >= 3 && bytes[0] == 0xef.toByte() && bytes[1] == 0xbb.toByte() && bytes[2] == 0xbf.toByte())) {
            "Probe manifest UTF-8 BOM is not allowed"
        }
        return parse(JSONObject(bytes.toString(Charsets.UTF_8)))
    }

    fun parse(root: JSONObject): ModelProbeManifest {
        root.requireKeys("manifest", setOf(
            "identity", "target", "model", "tensor", "runtime", "input", "comparator", "execution"
        ))
        val identity = parseIdentity(root.getJSONObject("identity"))
        val target = parseTarget(root.getJSONObject("target"))
        val model = parseModel(root.getJSONObject("model"))
        val tensor = parseTensor(root.getJSONObject("tensor"), model.task)
        val runtime = parseRuntime(root.getJSONObject("runtime"), model.task)
        val input = parseInput(root.getJSONObject("input"), model.task)
        val comparator = parseComparator(root.getJSONObject("comparator"))
        val execution = parseExecution(root.getJSONObject("execution"))
        return ModelProbeManifest(identity, target, model, tensor, runtime, input, comparator, execution)
    }

    private fun parseIdentity(value: JSONObject): ProbeIdentity {
        value.requireKeys("identity", setOf("schema_version", "protocol_version", "session_id", "created_utc"))
        require(value.getInt("schema_version") == MODEL_PROBE_SCHEMA) { "Probe schema mismatch" }
        require(value.getString("protocol_version") == MODEL_PROBE_PROTOCOL) { "Probe protocol mismatch" }
        val sessionId = value.nonEmptyString("session_id")
        require(UUID.fromString(sessionId).toString() == sessionId) { "session_id must be canonical lowercase UUID" }
        val createdUtc = value.nonEmptyString("created_utc")
        require(Regex("\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?Z").matches(createdUtc)) {
            "created_utc must be canonical UTC text"
        }
        return ProbeIdentity(sessionId, createdUtc)
    }

    private fun parseTarget(value: JSONObject): ProbeTarget {
        val keys = setOf(
            "device_id", "package_name", "apk_sha256", "adb_serial", "manufacturer", "model",
            "soc", "abi", "ram_bytes", "android_release", "api_level", "build_fingerprint",
            "cpu_abi", "cpu_features", "gpu_vendor", "gpu_renderer", "gpu_driver",
            "thermal_capability",
        )
        value.requireKeys("target", keys)
        val deviceId = value.nonEmptyString("device_id")
        require(deviceIdRegex.matches(deviceId)) { "Invalid target.device_id" }
        val packageName = value.nonEmptyString("package_name")
        require(packageName == "com.example.d1check.benchmarkrunner.modelprobe") {
            "Unexpected target package"
        }
        val apkSha256 = value.sha256("apk_sha256")
        val adbSerial = value.nonEmptyString("adb_serial")
        require(Regex("[A-Za-z0-9][A-Za-z0-9._:-]{0,255}").matches(adbSerial)) {
            "Invalid target.adb_serial"
        }
        val textValues = listOf(
            "manufacturer", "model", "soc", "abi", "android_release", "build_fingerprint",
            "cpu_abi", "cpu_features", "gpu_vendor", "gpu_renderer", "gpu_driver",
            "thermal_capability",
        ).associateWith { key -> value.nonEmptyString(key) }
        val ramBytes = value.getLong("ram_bytes")
        val apiLevel = value.getInt("api_level")
        require(ramBytes > 0L) { "target.ram_bytes must be positive" }
        require(apiLevel >= 24) { "target.api_level is below minSdk" }
        return ProbeTarget(
            deviceId, packageName, apkSha256, adbSerial,
            textValues.getValue("manufacturer"), textValues.getValue("model"),
            textValues.getValue("soc"), textValues.getValue("abi"), ramBytes,
            textValues.getValue("android_release"), apiLevel,
            textValues.getValue("build_fingerprint"), textValues.getValue("cpu_abi"),
            textValues.getValue("cpu_features"), textValues.getValue("gpu_vendor"),
            textValues.getValue("gpu_renderer"), textValues.getValue("gpu_driver"),
            textValues.getValue("thermal_capability"),
        )
    }

    private fun parseModel(value: JSONObject): ProbeModel {
        val keys = setOf(
            "task_id", "model_id", "url", "filename", "byte_count", "sha256",
            "distribution_policy", "metadata_license_status", "label_filename", "label_rows",
            "label_sha256",
        )
        value.requireKeys("model", keys)
        val task = ProbeTask.parse(value.nonEmptyString("task_id"))
        val modelId = value.nonEmptyString("model_id")
        val expected = ApprovedProbeModel.fromId(modelId)
        require(expected.task == task) { "model.task_id does not match model.model_id" }
        val url = value.nonEmptyString("url")
        require(url == expected.url && !url.contains("/latest/")) { "Model URL does not match pinned contract" }
        val filename = value.simpleFilename("filename")
        val byteCount = value.getLong("byte_count")
        val sha256 = value.sha256("sha256")
        require(filename == expected.filename && byteCount == expected.byteCount && sha256 == expected.sha256) {
            "Model filename/bytes/SHA-256 do not match pinned contract"
        }
        val distributionPolicy = value.nonEmptyString("distribution_policy")
        require(distributionPolicy == expected.distributionPolicy) { "Model distribution policy mismatch" }
        value.nonEmptyString("metadata_license_status")
        val labelFilename = value.simpleFilename("label_filename")
        val labelRows = value.getInt("label_rows")
        val labelSha256 = value.sha256("label_sha256")
        require(
            labelFilename == expected.labelFilename && labelRows == expected.labelRows &&
                labelSha256 == expected.labelSha256
        ) { "Model associated-label contract mismatch" }
        return ProbeModel(
            task, modelId, url, filename, byteCount, sha256, distributionPolicy,
            labelFilename, labelRows, labelSha256,
        )
    }

    private fun parseTensor(value: JSONObject, task: ProbeTask): ProbeTensorContract {
        value.requireKeys("tensor", setOf(
            "input_count", "inputs", "output_count", "outputs", "normalization", "raw_output_semantics"
        ))
        val inputs = parseTensorArray(value.getJSONArray("inputs"), "inputs")
        val outputs = parseTensorArray(value.getJSONArray("outputs"), "outputs")
        require(value.getInt("input_count") == inputs.size && value.getInt("output_count") == outputs.size) {
            "Tensor count mismatch"
        }
        val expectedInput = if (task == ProbeTask.CLASSIFICATION) intArrayOf(1, 224, 224, 3) else intArrayOf(1, 320, 320, 3)
        val expectedOutputs = if (task == ProbeTask.CLASSIFICATION) {
            listOf(intArrayOf(1, 1000))
        } else {
            listOf(intArrayOf(1, 19206, 90), intArrayOf(1, 19206, 4))
        }
        require(inputs.size == 1 && inputs.single().shape.contentEquals(expectedInput)) { "Probe input tensor mismatch" }
        require(outputs.size == expectedOutputs.size && outputs.indices.all {
            outputs[it].shape.contentEquals(expectedOutputs[it])
        }) { "Probe output tensor mismatch" }
        val normalization = value.nonEmptyString("normalization")
        val expectedNormalization = if (task == ProbeTask.CLASSIFICATION) "(RGB-127.0)/128.0" else "(RGB-127.5)/127.5"
        require(normalization == expectedNormalization) { "Probe normalization mismatch" }
        return ProbeTensorContract(
            inputs, outputs, normalization, value.nonEmptyString("raw_output_semantics")
        )
    }

    private fun parseTensorArray(value: JSONArray, area: String): List<ProbeTensor> =
        (0 until value.length()).map { index ->
            val item = value.getJSONObject(index)
            item.requireKeys("tensor.$area[$index]", setOf("index", "name", "shape", "dtype", "quantization"))
            require(item.getInt("index") == index) { "tensor.$area indexes must be contiguous" }
            require(item.getString("dtype") == "FLOAT32" && item.getString("quantization") == "none") {
                "tensor.$area[$index] must be unquantized FLOAT32"
            }
            val rawShape = item.getJSONArray("shape")
            val shape = IntArray(rawShape.length()) { position -> rawShape.getInt(position) }
            require(shape.isNotEmpty() && shape.all { it > 0 }) { "tensor.$area[$index] shape is invalid" }
            ProbeTensor(index, item.nonEmptyString("name"), shape, item.getString("dtype"))
        }

    private fun parseRuntime(value: JSONObject, task: ProbeTask): ProbeRuntime {
        value.requireKeys("runtime", setOf(
            "litert_version", "cpu_threads", "xnnpack", "gpu_profile_id",
            "gpu_configuration_sha256", "tasks_vision_version",
        ))
        val tasksVersion = value.nonEmptyString("tasks_vision_version")
        require(
            (task == ProbeTask.CLASSIFICATION && tasksVersion == "not_used") ||
                (task == ProbeTask.DETECTION && tasksVersion == "1.0.0")
        ) { "Tasks Vision version is not pinned for this task" }
        val cpuThreads = value.getInt("cpu_threads")
        require(cpuThreads > 0) { "runtime.cpu_threads must be positive" }
        return ProbeRuntime(
            value.nonEmptyString("litert_version"), cpuThreads, value.getBoolean("xnnpack"),
            value.nonEmptyString("gpu_profile_id"), value.sha256("gpu_configuration_sha256"),
            tasksVersion,
        )
    }

    private fun parseInput(value: JSONObject, task: ProbeTask): ProbeInput {
        value.requireKeys("input", setOf(
            "input_id", "kind", "generation_rule", "seed", "url", "filename",
            "byte_count", "sha256", "decode_contract",
        ))
        val kind = value.nonEmptyString("kind")
        val seed = value.nullableInt("seed")
        val url = value.nullableString("url")
        val filename = value.nullableString("filename")
        val sha256 = value.nullableString("sha256")
        val byteCount = value.getLong("byte_count")
        when (kind) {
            "deterministic_rgb" -> {
                require(value.getString("generation_rule") == "coordinate-rgb-v1") { "Input generation rule mismatch" }
                require(seed != null && seed >= 0 && url == null && filename == null && sha256 == null) {
                    "Deterministic input fields are invalid"
                }
                require(byteCount == 0L && value.getString("decode_contract") == "not_used") {
                    "Deterministic input external fields must be empty"
                }
            }
            "external_image" -> {
                require(task == ProbeTask.DETECTION) { "External image is only approved for detection" }
                require(value.getString("generation_rule") == "not_used" && seed == null) {
                    "External input generation fields must be empty"
                }
                require(
                    url == ApprovedProbeInput.CAT_AND_DOG.url &&
                        filename == ApprovedProbeInput.CAT_AND_DOG.filename &&
                        byteCount == ApprovedProbeInput.CAT_AND_DOG.byteCount &&
                        sha256 == ApprovedProbeInput.CAT_AND_DOG.sha256
                ) { "External input does not match pinned contract" }
                require(value.getString("decode_contract") == "android-bitmap-argb8888-v1") {
                    "External input decode contract mismatch"
                }
            }
            else -> throw IllegalArgumentException("Unsupported probe input kind: $kind")
        }
        return ProbeInput(
            value.nonEmptyString("input_id"), kind, value.nonEmptyString("generation_rule"),
            seed, url, filename, byteCount, sha256, value.nonEmptyString("decode_contract"),
        )
    }

    private fun parseComparator(value: JSONObject): ProbeComparator {
        value.requireKeys("comparator", setOf(
            "comparator_id", "atol", "rtol", "relative_epsilon", "decoded_box_atol_px",
            "decoded_score_atol", "decoded_order",
        ))
        val result = ProbeComparator(
            value.nonEmptyString("comparator_id"), value.getDouble("atol"),
            value.getDouble("rtol"), value.getDouble("relative_epsilon"),
            value.getDouble("decoded_box_atol_px"), value.getDouble("decoded_score_atol"),
            value.nonEmptyString("decoded_order"),
        )
        require(
            result.comparatorId == "combined-tolerance-v1" && result.atol == 1e-4 &&
                result.rtol == 1e-3 && result.relativeEpsilon == 1e-6 &&
                result.decodedBoxAtolPx == 2.0 && result.decodedScoreAtol == 1e-3 &&
                result.decodedOrder == "score_desc_label_box"
        ) { "Comparator contract mismatch" }
        return result
    }

    private fun parseExecution(value: JSONObject): ProbeExecution {
        value.requireKeys("execution", setOf(
            "backend", "cold_repetitions", "warm_repetitions", "maximum_duration_ms",
            "timeout_policy", "cleanup_policy",
        ))
        val cold = value.getInt("cold_repetitions")
        val warm = value.getInt("warm_repetitions")
        val maximumDurationMs = value.getLong("maximum_duration_ms")
        require(cold == 3 && warm == 10 && maximumDurationMs in 1L..300_000L) {
            "Probe repetition/duration contract mismatch"
        }
        val timeoutPolicy = value.nonEmptyString("timeout_policy")
        val cleanupPolicy = value.nonEmptyString("cleanup_policy")
        require(timeoutPolicy == "bounded-host-and-device-v1") { "Probe timeout policy mismatch" }
        require(cleanupPolicy == "bounded-delete-and-confirm-v1") { "Probe cleanup policy mismatch" }
        return ProbeExecution(
            ProbeBackend.valueOf(value.getString("backend")), cold, warm, maximumDurationMs,
            timeoutPolicy, cleanupPolicy,
        )
    }

    private fun JSONObject.requireKeys(location: String, expected: Set<String>) {
        val actual = mutableSetOf<String>()
        keys().forEachRemaining(actual::add)
        require(actual == expected) {
            "$location keys mismatch: missing=${(expected - actual).sorted()}, unknown=${(actual - expected).sorted()}"
        }
    }

    private fun JSONObject.nonEmptyString(key: String): String = getString(key).also {
        require(it.isNotEmpty()) { "$key must be non-empty" }
    }

    private fun JSONObject.nullableString(key: String): String? =
        if (isNull(key)) null else nonEmptyString(key)

    private fun JSONObject.nullableInt(key: String): Int? = if (isNull(key)) null else getInt(key)

    private fun JSONObject.sha256(key: String): String = nonEmptyString(key).also {
        require(sha256Regex.matches(it)) { "$key must be lowercase SHA-256" }
    }

    private fun JSONObject.simpleFilename(key: String): String = nonEmptyString(key).also {
        require(filenameRegex.matches(it) && it != "." && it != "..") { "$key must be a simple filename" }
    }
}

internal enum class ApprovedProbeModel(
    val task: ProbeTask,
    val modelId: String,
    val url: String,
    val filename: String,
    val byteCount: Long,
    val sha256: String,
    val distributionPolicy: String,
    val labelFilename: String,
    val labelRows: Int,
    val labelSha256: String,
) {
    EFFICIENTNET_LITE0(
        ProbeTask.CLASSIFICATION,
        "efficientnet-lite0-float32-v1",
        "https://storage.googleapis.com/mediapipe-models/image_classifier/efficientnet_lite0/float32/1/efficientnet_lite0.tflite",
        "efficientnet_lite0.tflite",
        18_582_189L,
        "6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0",
        "external_verified_apache_2_0",
        "labels_without_background.txt",
        1000,
        "e697a491aa735cc6c2aaf982f8e86e8fc7b0a1ea7750a2cc6a2bdfc1e109012f",
    ),
    EFFICIENTDET_LITE0(
        ProbeTask.DETECTION,
        "efficientdet-lite0-float32-v1",
        "https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/float32/1/efficientdet_lite0.tflite",
        "efficientdet_lite0.tflite",
        13_836_895L,
        "40338edf5ec70d43e318b0a716a84d4564cd1802759a7a07170c7e43796dbf58",
        "external_research_only_no_redistribution",
        "labels.txt",
        90,
        "f8803ef7900160c629d570848dfda4175e21667bf7b71f73f8ece4938c9f2bf2",
    ),
    ;

    companion object {
        fun fromId(value: String): ApprovedProbeModel = entries.firstOrNull { it.modelId == value }
            ?: throw IllegalArgumentException("Model is not approved for probe: $value")
    }
}

internal enum class ApprovedProbeInput(
    val url: String,
    val filename: String,
    val byteCount: Long,
    val sha256: String,
) {
    CAT_AND_DOG(
        "https://storage.googleapis.com/download/storage/v1/b/mediapipe-assets/o/cat_and_dog_2.jpg?generation=1669228153863445&alt=media",
        "cat_and_dog_2.jpg",
        145_626L,
        "85eb9ad2c6b0c397aa873faf97befc4a871d987cea822d9854617415778b6c8c",
    ),
}
