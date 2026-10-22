package com.example.d1check.benchmarkrunner

import android.content.Intent
import android.os.BatteryManager
import android.os.PowerManager
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import java.io.File
import java.util.UUID

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class CalibrationArtifactValidatorTest {
    @get:Rule
    val temporary = TemporaryFolder()

    @Test
    fun finalizedArtifactSetValidatesAndHashReplacementFailsClosed() {
        val (root, session) = productionFinalizedArtifacts()
        val metadata = File(root, "metadata.json")
        val entries = CalibrationArtifactValidator.validate(root, session)
        assertEquals(6, entries.size)
        assertTrue(File(root, "provenance.json").isFile)
        assertTrue(entries.none { it.relativePath == "provenance.json" })
        metadata.writeText("replaced")
        assertThrows(IllegalStateException::class.java) {
            CalibrationArtifactValidator.validate(root, session)
        }
    }

    @Test
    fun nestedProvenanceIsRejectedEvenWhenListedWithItsActualHash() {
        for (relative in listOf("results/provenance.json", "nested/path/provenance.json")) {
            val (root, session) = productionFinalizedArtifacts()
            val extra = File(root, relative)
            val parent = requireNotNull(extra.parentFile)
            assertTrue(parent.isDirectory || parent.mkdirs())
            extra.writeText("unexpected nested provenance")
            val unlisted = assertThrows(IllegalStateException::class.java) {
                CalibrationArtifactValidator.validate(root, session)
            }
            assertTrue(unlisted.message.orEmpty().contains(relative))

            val provenanceFile = File(root, "provenance.json")
            val stored = JSONObject(provenanceFile.readText())
            stored.getJSONArray("artifact_set").put(JSONObject()
                .put("relative_path", relative)
                .put("byte_count", extra.length())
                .put("sha256", sha256File(extra)))
            provenanceFile.writeText(stored.toString())
            val listed = assertThrows(IllegalStateException::class.java) {
                CalibrationArtifactValidator.validate(root, session)
            }
            assertTrue(listed.message.orEmpty().contains(relative))
        }
    }

    @Test
    fun productionFinalizerRejectsNestedProvenanceBeforeWritingRootProvenance() {
        for (relative in listOf("results/provenance.json", "nested/path/provenance.json")) {
            val failure = assertThrows(IllegalStateException::class.java) {
                productionFinalizedArtifacts(relative)
            }
            assertTrue(failure.message.orEmpty().contains(relative))
        }
    }

    @Test
    fun partialExtraDuplicateAndUnsafeArtifactsFailClosed() {
        val session = UUID.randomUUID().toString()
        val missing = temporary.newFolder("missing")
        File(missing, "provenance.json").writeText(
            provenance(session, listOf(CalibrationArtifactEntry("missing.json", 1, "0".repeat(64)))).toString()
        )
        assertThrows(IllegalStateException::class.java) {
            CalibrationArtifactValidator.validate(missing, session)
        }

        val extra = temporary.newFolder("extra")
        val validEntries = validArtifacts(extra, session)
        File(extra, "unexpected.json").writeText("x")
        File(extra, "provenance.json").writeText(
            provenance(session, validEntries).toString()
        )
        assertThrows(IllegalStateException::class.java) {
            CalibrationArtifactValidator.validate(extra, session)
        }

        val provenanceIncludedExtra = temporary.newFolder("provenance-included-extra")
        val includedEntries = validArtifacts(provenanceIncludedExtra, session).toMutableList()
        val partial = File(provenanceIncludedExtra, "results/.partial.part").apply {
            requireNotNull(parentFile).mkdirs()
            writeText("partial")
        }
        includedEntries += entry(partial, "results/.partial.part")
        File(provenanceIncludedExtra, "provenance.json").writeText(
            provenance(session, includedEntries).toString()
        )
        assertThrows(IllegalStateException::class.java) {
            CalibrationArtifactValidator.validate(provenanceIncludedExtra, session)
        }

        val hashMismatch = temporary.newFolder("hash-mismatch")
        val hashEntries = validArtifacts(hashMismatch, session).toMutableList()
        val metadataIndex = hashEntries.indexOfFirst { it.relativePath == "metadata.json" }
        hashEntries[metadataIndex] = hashEntries[metadataIndex].copy(sha256 = "0".repeat(64))
        File(hashMismatch, "provenance.json").writeText(
            provenance(session, hashEntries).toString()
        )
        assertThrows(IllegalStateException::class.java) {
            CalibrationArtifactValidator.validate(hashMismatch, session)
        }

        val identityMismatch = temporary.newFolder("identity-mismatch")
        val identityEntries = validArtifacts(identityMismatch, session)
        File(identityMismatch, "provenance.json").writeText(
            provenance(UUID.randomUUID().toString(), identityEntries).toString()
        )
        assertThrows(IllegalStateException::class.java) {
            CalibrationArtifactValidator.validate(identityMismatch, session)
        }

        val unsafe = temporary.newFolder("unsafe")
        File(unsafe, "provenance.json").writeText(
            provenance(session, listOf(CalibrationArtifactEntry("../escape", 1, "0".repeat(64)))).toString()
        )
        assertThrows(IllegalStateException::class.java) {
            CalibrationArtifactValidator.validate(unsafe, session)
        }
    }

    @Test
    fun baselineThermalGateFormalPolicyAndProductionProviderAreEnforced() {
        val context = RuntimeEnvironment.getApplication()
        context.sendStickyBroadcast(Intent(Intent.ACTION_BATTERY_CHANGED)
            .putExtra(BatteryManager.EXTRA_STATUS, BatteryManager.BATTERY_STATUS_DISCHARGING)
            .putExtra(BatteryManager.EXTRA_LEVEL, 80)
            .putExtra(BatteryManager.EXTRA_SCALE, 100)
            .putExtra(BatteryManager.EXTRA_TEMPERATURE, 250))

        for (status in 0..1) {
            val (artifacts, _) = CalibrationSessionArtifacts.create(
                context,
                productionManifest(context, CalibrationSessionMode.BASELINE_PILOT),
                productionLabels(),
                CalibrationThermalProvider {
                    CalibrationThermalSample(AndroidCalibrationClock.monotonicNanos(), status, 250)
                },
            )
            artifacts.close()
        }
        assertThrows(IllegalStateException::class.java) {
            CalibrationSessionArtifacts.create(
                context,
                productionManifest(context, CalibrationSessionMode.BASELINE_PILOT),
                productionLabels(),
                CalibrationThermalProvider {
                    CalibrationThermalSample(AndroidCalibrationClock.monotonicNanos(), 2, 250)
                },
            )
        }
        val (stress, _) = CalibrationSessionArtifacts.create(
            context,
            productionManifest(context, CalibrationSessionMode.THERMAL_STRESS),
            productionLabels(),
            CalibrationThermalProvider {
                CalibrationThermalSample(AndroidCalibrationClock.monotonicNanos(), 4, 350)
            },
        )
        stress.close()

        val productionSample = AndroidCalibrationThermalProvider(context).sample()
        assertTrue(productionSample.timestampNs >= 0L)
        assertEquals(250, productionSample.batteryTemperatureDeciC)
        assertNotNull(productionSample.thermalStatus)
        val (productionThermalArtifacts, _) = CalibrationSessionArtifacts.create(
            context,
            productionManifest(context, CalibrationSessionMode.BASELINE_PILOT),
            productionLabels(),
        )
        val productionMetadata = JSONObject(File(
            productionThermalArtifacts.root, "metadata.json"
        ).readText())
        assertEquals(250, productionMetadata.getInt("start_battery_temperature_deci_c"))
        val initialRecordedSample = JSONObject(File(
            productionThermalArtifacts.root, "thermal_samples.jsonl"
        ).readLines().first())
        assertEquals(
            productionMetadata.getLong("start_thermal_sample_ns"),
            initialRecordedSample.getLong("timestamp_ns"),
        )
        productionThermalArtifacts.close()

        val missingPolicy = productionManifest(
            context, CalibrationSessionMode.BASELINE_FORMAL, JSONObject.NULL
        )
        assertThrows(IllegalArgumentException::class.java) {
            CalibrationInputManifest.parse(missingPolicy)
        }
        val badPolicy = temperaturePolicy().put("sha256", "0".repeat(64))
        assertThrows(IllegalArgumentException::class.java) {
            CalibrationInputManifest.parse(productionManifest(
                context, CalibrationSessionMode.BASELINE_FORMAL, badPolicy
            ))
        }
        val (formal, _) = CalibrationSessionArtifacts.create(
            context,
            productionManifest(
                context, CalibrationSessionMode.BASELINE_FORMAL, temperaturePolicy()
            ),
            productionLabels(),
            CalibrationThermalProvider {
                CalibrationThermalSample(AndroidCalibrationClock.monotonicNanos(), 1, 250)
            },
        )
        formal.close()
    }

    @Test
    fun thermalModeSessionAndTimestampMixingFailClosed() {
        for (mutation in listOf("mode", "session", "timestamp")) {
            val session = UUID.randomUUID().toString()
            val root = temporary.newFolder("thermal-$mutation")
            validArtifacts(root, session)
            val thermal = File(root, "thermal_samples.jsonl")
            val sample = JSONObject(thermal.readText().trim())
            when (mutation) {
                "mode" -> sample.put("calibration_mode", "thermal_stress")
                "session" -> sample.put("session_id", UUID.randomUUID().toString())
                else -> sample.put("timestamp_ns", 99L)
            }
            thermal.writeText(sample.toString() + "\n")
            rewriteProvenance(root, session)
            assertThrows(IllegalStateException::class.java) {
                CalibrationArtifactValidator.validate(root, session)
            }
        }
    }

    @Test
    fun failedRejectedAndExpiredTelemetryCannotContainOutput() {
        for (status in listOf("failed", "rejected", "expired")) {
            for (evidence in listOf("output", "persistence")) {
                val session = UUID.randomUUID().toString()
                val root = temporary.newFolder("non-success-$status-$evidence")
                validArtifacts(root, session)
                val requests = File(root, "requests.jsonl")
                val request = JSONObject(requests.readText().trim())
                    .put("terminal_status", status)
                    .put("deadline_ns", 100L)
                    .put("deadline_outcome", "not_completed")
                    .put("deadline_met", false)
                if (evidence == "persistence") {
                    val relative = "results/${request.getString("request_id")}.json"
                    request.put("output_sha256", JSONObject.NULL)
                        .put("persisted_relative_path", relative)
                    File(root, relative).apply {
                        requireNotNull(parentFile).mkdirs()
                        writeText("{}")
                    }
                }
                requests.writeText(request.toString() + "\n")
                rewriteProvenance(root, session)
                assertThrows(IllegalStateException::class.java) {
                    CalibrationArtifactValidator.validate(root, session)
                }
            }
        }
    }

    @Test
    fun summarySeparatesCompletionAndDeadlineRates() {
        val context = RuntimeEnvironment.getApplication()
        val (artifacts, _) = CalibrationSessionArtifacts.create(
            context,
            productionManifest(context, CalibrationSessionMode.BASELINE_PILOT),
            productionLabels(),
            CalibrationThermalProvider {
                CalibrationThermalSample(AndroidCalibrationClock.monotonicNanos(), 1, 250)
            },
        )
        val image = productionImage()
        val output = ClassificationOutput(listOf(0), listOf("label-0"), "5".repeat(64), 0)
        val urgent = request(image, CalibrationRequestType.URGENT, 10L, 30L)
        artifacts.record(result(
            urgent, CalibrationTerminalStatus.SUCCEEDED, 20L, output, null
        ))
        val normal = request(image, CalibrationRequestType.NORMAL, 40L, 50L)
        val receipt = DurableCalibrationResultStore(File(artifacts.root, "results"))
            .persist(normal, output)
        artifacts.record(result(
            normal, CalibrationTerminalStatus.SUCCEEDED, 60L, output, receipt.relativePath
        ))
        val expired = request(image, CalibrationRequestType.URGENT, 70L, 80L)
        artifacts.record(result(expired, CalibrationTerminalStatus.EXPIRED, 90L, null, null))
        val rejected = request(image, CalibrationRequestType.URGENT, 100L, 110L)
        artifacts.record(result(rejected, CalibrationTerminalStatus.REJECTED, 101L, null, null))
        artifacts.finalizeAndValidate()

        val summary = JSONObject(File(artifacts.root, "summary.json").readText())
        assertEquals(4L, summary.getLong("arrived_count"))
        assertEquals(2L, summary.getLong("completed_count"))
        assertEquals(0.5, summary.getDouble("overall_completion_rate"), 0.0)
        assertEquals(0.25, summary.getDouble("on_time_completion_rate"), 0.0)
        assertEquals(0.75, summary.getDouble("deadline_violation_rate"), 0.0)
    }

    private fun entry(file: File, relative: String) = CalibrationArtifactEntry(
        relative, file.length(), sha256File(file)
    )

    private fun rewriteProvenance(root: File, session: String) {
        val entries = root.walkTopDown()
            .filter {
                it.isFile && it.relativeTo(root).normalize().invariantSeparatorsPath !=
                    "provenance.json"
            }
            .map { entry(it, it.relativeTo(root).invariantSeparatorsPath) }
            .toList()
        File(root, "provenance.json").writeText(provenance(session, entries).toString())
    }

    private fun productionLabels() = (0..1000)
        .joinToString("\n", postfix = "\n") { "label-$it" }
        .toByteArray(Charsets.UTF_8)

    private fun productionImage() = CalibrationImageSpec(
        "fixture", "images/fixture.png", "3".repeat(64), 68, 0, "label-0",
        1, 1, 1, 1, 1, "image/png",
    )

    private fun temperaturePolicy(): JSONObject {
        val policy = CalibrationTemperaturePolicy(
            "a24-baseline-v1", 300, 60_000L, 5,
            CalibrationContract.sha256(
                "policy_id=a24-baseline-v1|".plus(
                    "maximum_start_battery_temperature_deci_c=300|"
                ).plus("stability_window_ms=60000|")
                    .plus("maximum_stability_delta_deci_c=5")
                    .toByteArray(Charsets.UTF_8)
            ),
        )
        return JSONObject()
            .put("policy_id", policy.policyId)
            .put("maximum_start_battery_temperature_deci_c",
                policy.maximumStartBatteryTemperatureDeciC)
            .put("stability_window_ms", policy.stabilityWindowMs)
            .put("maximum_stability_delta_deci_c", policy.maximumStabilityDeltaDeciC)
            .put("sha256", policy.sha256)
    }

    private fun productionManifest(
        context: android.content.Context,
        mode: CalibrationSessionMode,
        policy: Any = if (mode == CalibrationSessionMode.BASELINE_FORMAL) {
            temperaturePolicy()
        } else JSONObject.NULL,
    ): ByteArray {
        @Suppress("DEPRECATION")
        context.sendStickyBroadcast(Intent(Intent.ACTION_BATTERY_CHANGED)
            .putExtra(BatteryManager.EXTRA_STATUS, BatteryManager.BATTERY_STATUS_DISCHARGING)
            .putExtra(BatteryManager.EXTRA_LEVEL, 80)
            .putExtra(BatteryManager.EXTRA_SCALE, 100)
            .putExtra(BatteryManager.EXTRA_TEMPERATURE, 250))
        val labels = productionLabels()
        val apk = File(context.applicationInfo.sourceDir).canonicalFile
        val screenOn = context.getSystemService(PowerManager::class.java).isInteractive
        return JSONObject()
            .put("schema_version", CalibrationContract.SCHEMA_VERSION)
            .put("protocol_version", CalibrationContract.PROTOCOL_VERSION)
            .put("session_id", UUID.randomUUID().toString())
            .put("calibration_mode", mode.wireName)
            .put("mode", "fixed")
            .put("fixed_backend", "CPU")
            .put("cpu_threads", 1)
            .put("queue_capacity", 8)
            .put("warmup_count", 0)
            .put("model_sha256", ModelLoader.MODEL_SHA256.lowercase())
            .put("label_mapping_sha256", CalibrationContract.sha256(labels))
            .put("preprocessing_sha256", MobileNetCalibrationPreprocessor.configurationSha256)
            .put("preprocessing_contract_id", MobileNetCalibrationPreprocessor.CONTRACT_ID)
            .put("expected_apk_sha256", sha256File(apk))
            .put("deadline_state", "calibration_pending")
            .put("temperature_policy", policy)
            .put("environment", JSONObject()
                .put("physical_position", "robolectric")
                .put("ambient_temperature_c", JSONObject.NULL)
                .put("expected_charging", false)
                .put("expected_screen_on", screenOn))
            .put("images", JSONArray().put(JSONObject()
                .put("image_id", "fixture")
                .put("relative_path", "images/fixture.png")
                .put("sha256", "3".repeat(64))
                .put("byte_count", 68)
                .put("label_index", 0)
                .put("label", "label-0")
                .put("raw_width", 1)
                .put("raw_height", 1)
                .put("exif_orientation", 1)
                .put("transformed_width", 1)
                .put("transformed_height", 1)
                .put("mime_type", "image/png")))
            .toString().toByteArray(Charsets.UTF_8)
    }

    private fun request(
        image: CalibrationImageSpec,
        type: CalibrationRequestType,
        acceptedNs: Long,
        deadlineNs: Long,
    ) = CalibrationRequest(
        UUID.randomUUID().toString(), type, image, "fixture://image",
        CalibrationBackend.CPU, null, acceptedNs, deadlineNs,
    )

    private fun result(
        request: CalibrationRequest,
        status: CalibrationTerminalStatus,
        completedNs: Long,
        output: ClassificationOutput?,
        persistedPath: String?,
    ): CalibrationRequestResult {
        val timestamps = CalibrationTimestamps(null, request.acceptedNs).apply {
            executionStartNs = request.acceptedNs
            if (status == CalibrationTerminalStatus.SUCCEEDED) {
                if (request.requestType == CalibrationRequestType.URGENT) {
                    outputReadyNs = completedNs
                } else {
                    persistenceStartNs = completedNs - 1
                    persistenceCompletedNs = completedNs
                }
            }
            terminalNs = completedNs
        }
        return CalibrationRequestResult(
            request, status, timestamps,
            if (status == CalibrationTerminalStatus.SUCCEEDED) CalibrationBackend.CPU else null,
            CalibrationFallbackStatus.NOT_APPLICABLE,
            if (status == CalibrationTerminalStatus.SUCCEEDED) CalibrationThermalClass.WARM else null,
            null, null, output, persistedPath,
            if (status == CalibrationTerminalStatus.SUCCEEDED) null else status.wireName,
        )
    }

    @Suppress("DEPRECATION")
    private fun productionFinalizedArtifacts(unexpectedRelativePath: String? = null): Pair<File, String> {
        val context = RuntimeEnvironment.getApplication()
        context.sendStickyBroadcast(Intent(Intent.ACTION_BATTERY_CHANGED)
            .putExtra(BatteryManager.EXTRA_STATUS, BatteryManager.BATTERY_STATUS_DISCHARGING)
            .putExtra(BatteryManager.EXTRA_LEVEL, 80)
            .putExtra(BatteryManager.EXTRA_SCALE, 100)
            .putExtra(BatteryManager.EXTRA_TEMPERATURE, 250))
        val labels = (0..1000).joinToString("\n", postfix = "\n") { "label-$it" }
            .toByteArray(Charsets.UTF_8)
        val session = UUID.randomUUID().toString()
        val imageSha = "3".repeat(64)
        val apk = File(context.applicationInfo.sourceDir).canonicalFile
        check(apk.isFile) { "Robolectric APK fixture is missing" }
        val screenOn = context.getSystemService(PowerManager::class.java).isInteractive
        val manifest = JSONObject()
            .put("schema_version", CalibrationContract.SCHEMA_VERSION)
            .put("protocol_version", CalibrationContract.PROTOCOL_VERSION)
            .put("session_id", session)
            .put("calibration_mode", "baseline_pilot")
            .put("mode", "fixed")
            .put("fixed_backend", "CPU")
            .put("cpu_threads", 1)
            .put("queue_capacity", 8)
            .put("warmup_count", 0)
            .put("model_sha256", ModelLoader.MODEL_SHA256.lowercase())
            .put("label_mapping_sha256", CalibrationContract.sha256(labels))
            .put("preprocessing_sha256", MobileNetCalibrationPreprocessor.configurationSha256)
            .put("preprocessing_contract_id", MobileNetCalibrationPreprocessor.CONTRACT_ID)
            .put("expected_apk_sha256", sha256File(apk))
            .put("deadline_state", "calibration_pending")
            .put("temperature_policy", JSONObject.NULL)
            .put("environment", JSONObject()
                .put("physical_position", "robolectric")
                .put("ambient_temperature_c", JSONObject.NULL)
                .put("expected_charging", false)
                .put("expected_screen_on", screenOn))
             .put("images", JSONArray().put(JSONObject()
                 .put("image_id", "fixture")
                 .put("relative_path", "images/fixture.png")
                 .put("sha256", imageSha)
                 .put("byte_count", 68)
                 .put("label_index", 0)
                 .put("label", "label-0")
                 .put("raw_width", 1)
                 .put("raw_height", 1)
                 .put("exif_orientation", 1)
                 .put("transformed_width", 1)
                 .put("transformed_height", 1)
                 .put("mime_type", "image/png")))
            .toString().toByteArray(Charsets.UTF_8)
        val thermal = CalibrationThermalProvider {
            CalibrationThermalSample(AndroidCalibrationClock.monotonicNanos(), 1, 250)
        }
        val (artifacts, _) = CalibrationSessionArtifacts.create(context, manifest, labels, thermal)
        val request = CalibrationRequest(
            UUID.randomUUID().toString(), CalibrationRequestType.URGENT,
            CalibrationImageSpec(
                "fixture", "images/fixture.png", imageSha, 68, 0, "label-0",
                1, 1, 1, 1, 1, "image/png",
            ),
            "fixture://image", CalibrationBackend.CPU, null, 1L, null,
        )
        artifacts.record(CalibrationRequestResult(
            request = request,
            terminalStatus = CalibrationTerminalStatus.SUCCEEDED,
            timestamps = CalibrationTimestamps(
                pickerResultReceivedNs = null,
                acceptedNs = 1L,
                executionStartNs = 2L,
                outputReadyNs = 3L,
                terminalNs = 4L,
            ),
            actualBackend = CalibrationBackend.CPU,
            fallbackStatus = CalibrationFallbackStatus.NOT_APPLICABLE,
            executionClass = CalibrationThermalClass.COLD,
            transition = null,
            inputTensorSha256 = "4".repeat(64),
            output = ClassificationOutput(
                listOf(0), listOf("label-0"), "5".repeat(64), 0,
            ),
            persistedRelativePath = null,
            error = null,
        ))
        if (unexpectedRelativePath != null) {
            val extra = File(artifacts.root, unexpectedRelativePath)
            val parent = requireNotNull(extra.parentFile)
            assertTrue(parent.isDirectory || parent.mkdirs())
            extra.writeText("unexpected nested provenance")
        }
        try {
            assertEquals(6, artifacts.finalizeAndValidate().size)
        } catch (failure: IllegalStateException) {
            if (unexpectedRelativePath != null) {
                assertTrue(!File(artifacts.root, "provenance.json").exists())
            }
            throw failure
        } finally {
            artifacts.close()
        }
        return artifacts.root to session
    }

    private fun validArtifacts(root: File, session: String): List<CalibrationArtifactEntry> {
        val labels = File(root, "label_mapping.txt").apply {
            writeText((0..1000).joinToString("\n", postfix = "\n") { "label-$it" })
        }
        val manifest = JSONObject()
            .put("schema_version", CalibrationContract.SCHEMA_VERSION)
            .put("protocol_version", "calibration-v1")
            .put("session_id", session)
            .put("calibration_mode", "baseline_pilot")
            .put("mode", "fixed")
            .put("fixed_backend", "CPU")
            .put("cpu_threads", 1)
            .put("queue_capacity", 8)
            .put("warmup_count", 0)
            .put("model_sha256", ModelLoader.MODEL_SHA256.lowercase())
            .put("label_mapping_sha256", sha256File(labels))
            .put("preprocessing_sha256", MobileNetCalibrationPreprocessor.configurationSha256)
            .put("preprocessing_contract_id", MobileNetCalibrationPreprocessor.CONTRACT_ID)
            .put("expected_apk_sha256", "2".repeat(64))
            .put("deadline_state", "calibration_pending")
            .put("temperature_policy", JSONObject.NULL)
            .put("environment", JSONObject()
                .put("physical_position", "test")
                .put("ambient_temperature_c", JSONObject.NULL)
                .put("expected_charging", false)
                .put("expected_screen_on", true))
             .put("images", JSONArray().put(JSONObject()
                 .put("image_id", "fixture")
                 .put("relative_path", "images/fixture.png")
                 .put("sha256", "3".repeat(64))
                 .put("byte_count", 68)
                 .put("label_index", 0)
                 .put("label", "label-0")
                 .put("raw_width", 8)
                 .put("raw_height", 8)
                 .put("exif_orientation", 1)
                 .put("transformed_width", 8)
                 .put("transformed_height", 8)
                 .put("mime_type", "image/png")))
        File(root, "input_manifest.json").writeText(manifest.toString())
        val identity = JSONObject()
            .put("schema_version", CalibrationContract.SCHEMA_VERSION)
            .put("protocol_version", CalibrationContract.PROTOCOL_VERSION)
            .put("session_id", session)
        File(root, "metadata.json").writeText(JSONObject(identity.toString())
            .put("calibration_mode", "baseline_pilot")
            .put("manifest_sha256", sha256File(File(root, "input_manifest.json")))
            .put("label_mapping_sha256", sha256File(labels))
            .put("preprocessing_sha256", MobileNetCalibrationPreprocessor.configurationSha256)
            .put("preprocessing_contract_id", MobileNetCalibrationPreprocessor.CONTRACT_ID)
            .put("preprocessing_configuration", MobileNetCalibrationPreprocessor.CONFIGURATION)
            .put("start_thermal_sample_ns", 1L)
            .put("temperature_policy_sha256", JSONObject.NULL)
            .put("apk_sha256", "2".repeat(64))
            .put("model_sha256", ModelLoader.MODEL_SHA256.lowercase()).toString())
        File(root, "requests.jsonl").writeText(JSONObject(identity.toString())
            .put("calibration_mode", "baseline_pilot")
            .put("request_id", UUID.randomUUID().toString())
            .put("request_type", "urgent")
            .put("terminal_status", "succeeded")
            .put("deadline_outcome", "not_set")
            .put("deadline_met", JSONObject.NULL)
            .put("output_sha256", "5".repeat(64))
            .put("persisted_relative_path", JSONObject.NULL).toString() + "\n")
        File(root, "thermal_samples.jsonl").writeText(JSONObject(identity.toString())
            .put("calibration_mode", "baseline_pilot")
            .put("timestamp_ns", 1L)
            .put("thermal_status", 1)
            .put("battery_temperature_deci_c", 250).toString() + "\n")
        File(root, "summary.json").writeText(JSONObject(identity.toString())
            .put("calibration_mode", "baseline_pilot")
            .put("start_mono_ns", 1L)
            .put("end_mono_ns", 2L)
            .put("counts", JSONObject()
                .put("succeeded", 1)
                .put("failed", 0)
                .put("rejected", 0)
                .put("expired", 0))
            .put("deadline_counts", JSONObject()
                .put("not_set", 1).put("on_time", 0).put("late", 0)
                .put("not_completed", 0))
            .put("arrived_count", 1)
            .put("completed_count", 1)
            .put("deadline_set_count", 0)
            .put("overall_completion_rate", 1.0)
            .put("on_time_completion_rate", JSONObject.NULL)
            .put("deadline_violation_rate", JSONObject.NULL)
            .put("thermal_sample_count", 1).toString())
        return listOf(
            "input_manifest.json", "label_mapping.txt", "metadata.json",
            "requests.jsonl", "thermal_samples.jsonl", "summary.json",
        ).map {
            entry(File(root, it), it)
        }
    }

    private fun provenance(session: String, entries: List<CalibrationArtifactEntry>) = JSONObject()
        .put("schema_version", CalibrationContract.SCHEMA_VERSION)
        .put("protocol_version", CalibrationContract.PROTOCOL_VERSION)
        .put("session_id", session)
        .put("manifest_sha256", entries.singleOrNull {
            it.relativePath == "input_manifest.json"
        }?.sha256 ?: "1".repeat(64))
        .put("apk_sha256", "2".repeat(64))
        .put("model_sha256", ModelLoader.MODEL_SHA256.lowercase())
        .put("artifact_set", JSONArray().apply {
            entries.forEach {
                put(JSONObject()
                    .put("relative_path", it.relativePath)
                    .put("byte_count", it.byteCount)
                    .put("sha256", it.sha256))
            }
        })
}
