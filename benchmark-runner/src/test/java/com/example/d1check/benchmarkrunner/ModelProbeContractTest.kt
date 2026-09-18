package com.example.d1check.benchmarkrunner

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertThrows
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File
import java.nio.ByteBuffer
import java.nio.file.Files
import java.security.MessageDigest

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class ModelProbeContractTest {
    @Test
    fun manifestIsDeviceDrivenAndRejectsContractDrift() {
        val first = ModelProbeManifestParser.parse(validManifest("a24-primary", "serial-a24"))
        val second = ModelProbeManifestParser.parse(
            validManifest("replication-device-01", "serial-other")
        )
        assertEquals("a24-primary", first.target.deviceId)
        assertEquals("replication-device-01", second.target.deviceId)
        assertNotEquals(first.target.adbSerial, second.target.adbSerial)

        val unknown = validManifest("a24-primary", "serial-a24")
        unknown.getJSONObject("target").put("unexpected", true)
        assertThrows(IllegalArgumentException::class.java) {
            ModelProbeManifestParser.parse(unknown)
        }

        val changedHash = validManifest("a24-primary", "serial-a24")
        changedHash.getJSONObject("model").put("sha256", "0".repeat(64))
        assertThrows(IllegalArgumentException::class.java) {
            ModelProbeManifestParser.parse(changedHash)
        }
    }

    @Test
    fun modelFileRequiresContainedExactRegularBytesAndRejectsPartFiles() {
        val root = Files.createTempDirectory("probe-model").toFile()
        try {
            val bytes = "model-fixture".toByteArray()
            val file = File(root, "fixture.tflite").apply { writeBytes(bytes) }
            val expected = ProbeModel(
                task = ProbeTask.CLASSIFICATION,
                modelId = "fixture",
                url = "https://example.invalid/1/fixture.tflite",
                filename = file.name,
                byteCount = bytes.size.toLong(),
                sha256 = sha256(bytes),
                distributionPolicy = "test",
                labelFilename = "labels.txt",
                labelRows = 1,
                labelSha256 = "0".repeat(64),
            )
            val opened = ProbeModelFile.open(root, expected)
            assertEquals(bytes.size.toLong(), opened.byteCount)
            assertEquals(sha256(bytes), opened.sha256)

            File(root, "stale.part").writeText("partial")
            assertThrows(IllegalArgumentException::class.java) {
                ProbeModelFile.open(root, expected)
            }
        } finally {
            root.deleteRecursively()
        }
    }

    @Test
    fun deterministicInputsAreStableAndTaskSpecific() {
        val classification = ProbeRawSession.deterministicInput(ProbeTask.CLASSIFICATION, 0)
        val detection = ProbeRawSession.deterministicInput(ProbeTask.DETECTION, 0)
        assertEquals(224 * 224 * 3 * 4, classification.remaining())
        assertEquals(320 * 320 * 3 * 4, detection.remaining())
        assertEquals(
            "13c9a4dcafa0958cd779537752ac40cfba74660fe8c34a0bf8f3b5dc6b6ff75c",
            sha256(classification),
        )
        assertEquals(
            "35d7b69f58ba2beaebc0d86e4fc303017390d11939e6f758ecdd6d1d591b4111",
            sha256(detection),
        )
        assertNotEquals(
            sha256(ProbeRawSession.deterministicInput(ProbeTask.CLASSIFICATION, 0)),
            sha256(ProbeRawSession.deterministicInput(ProbeTask.CLASSIFICATION, 1)),
        )
    }

    private fun validManifest(deviceId: String, serial: String): JSONObject = JSONObject().apply {
        put("identity", JSONObject().apply {
            put("schema_version", 1)
            put("protocol_version", "model-probe-v1")
            put("session_id", "71d5f7df-356f-4b3e-9ea7-a4be9d887801")
            put("created_utc", "2026-09-18T12:00:00Z")
        })
        put("target", JSONObject().apply {
            put("device_id", deviceId)
            put("package_name", "com.example.d1check.benchmarkrunner")
            put("apk_sha256", "a".repeat(64))
            put("adb_serial", serial)
            put("manufacturer", "vendor")
            put("model", "model")
            put("soc", "soc")
            put("abi", "arm64-v8a")
            put("ram_bytes", 8_000_000_000L)
            put("android_release", "16")
            put("api_level", 36)
            put("build_fingerprint", "vendor/product/device:16/build:user/release-keys")
            put("cpu_abi", "arm64-v8a")
            put("cpu_features", "asimd")
            put("gpu_vendor", "vendor")
            put("gpu_renderer", "renderer")
            put("gpu_driver", "driver")
            put("thermal_capability", "android-thermal-status")
        })
        put("model", JSONObject().apply {
            put("task_id", "classification")
            put("model_id", "efficientnet-lite0-float32-v1")
            put("url", "https://storage.googleapis.com/mediapipe-models/image_classifier/efficientnet_lite0/float32/1/efficientnet_lite0.tflite")
            put("filename", "efficientnet_lite0.tflite")
            put("byte_count", 18_582_189L)
            put("sha256", "6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0")
            put("distribution_policy", "external_verified_apache_2_0")
            put("metadata_license_status", "apache-2.0")
            put("label_filename", "labels_without_background.txt")
            put("label_rows", 1000)
            put("label_sha256", "e697a491aa735cc6c2aaf982f8e86e8fc7b0a1ea7750a2cc6a2bdfc1e109012f")
        })
        put("tensor", JSONObject().apply {
            put("input_count", 1)
            put("inputs", JSONArray().put(tensor(0, "images", intArrayOf(1, 224, 224, 3))))
            put("output_count", 1)
            put("outputs", JSONArray().put(tensor(0, "Softmax", intArrayOf(1, 1000))))
            put("normalization", "(RGB-127.0)/128.0")
            put("raw_output_semantics", "class_probabilities")
        })
        put("runtime", JSONObject().apply {
            put("litert_version", "1.4.2")
            put("cpu_threads", 1)
            put("xnnpack", true)
            put("gpu_profile_id", "gpu-fp32-strict-v1")
            put("gpu_configuration_sha256", "58ee1a9dad76bb62d85dedae9204790863eacc7d8c3c0da404505616ca098068")
            put("tasks_vision_version", "not_used")
        })
        put("input", JSONObject().apply {
            put("input_id", "raw-seed-0")
            put("kind", "deterministic_rgb")
            put("generation_rule", "coordinate-rgb-v1")
            put("seed", 0)
            put("url", JSONObject.NULL)
            put("filename", JSONObject.NULL)
            put("byte_count", 0)
            put("sha256", JSONObject.NULL)
            put("decode_contract", "not_used")
        })
        put("comparator", JSONObject().apply {
            put("comparator_id", "combined-tolerance-v1")
            put("atol", 1e-4)
            put("rtol", 1e-3)
            put("relative_epsilon", 1e-6)
            put("decoded_box_atol_px", 2.0)
            put("decoded_score_atol", 1e-3)
            put("decoded_order", "score_desc_label_box")
        })
        put("execution", JSONObject().apply {
            put("backend", "CPU")
            put("cold_repetitions", 3)
            put("warm_repetitions", 10)
            put("maximum_duration_ms", 120_000)
            put("timeout_policy", "bounded-host-and-device-v1")
            put("cleanup_policy", "bounded-delete-and-confirm-v1")
        })
    }

    private fun tensor(index: Int, name: String, shape: IntArray): JSONObject = JSONObject().apply {
        put("index", index)
        put("name", name)
        put("shape", JSONArray(shape.toList()))
        put("dtype", "FLOAT32")
        put("quantization", "none")
    }

    private fun sha256(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes).toHex()

    private fun sha256(buffer: ByteBuffer): String {
        val duplicate = buffer.asReadOnlyBuffer().apply { rewind() }
        val digest = MessageDigest.getInstance("SHA-256")
        digest.update(duplicate)
        return digest.digest().toHex()
    }

    private fun ByteArray.toHex(): String = joinToString("") { "%02x".format(it) }
}
