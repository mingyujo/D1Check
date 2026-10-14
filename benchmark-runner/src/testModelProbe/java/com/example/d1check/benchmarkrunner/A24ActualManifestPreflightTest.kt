package com.example.d1check.benchmarkrunner

import java.io.File
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** PC-only producer/consumer check of the exact registered manifests. No native interpreter. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk=[34])
class A24ActualManifestPreflightTest {
    @Test fun everyRegisteredRequestAndResidentBindingUsesTheActualAppParser() {
        val directory = System.getenv("A24_MANIFEST_PREFLIGHT_DIR")
        assumeTrue("Supply private PC manifests to perform this additional preflight", directory != null)
        val files = File(directory!!).listFiles { f -> f.extension == "json" }!!.sortedBy { it.name }
        assertEquals(64, files.size)
        var requestCount = 0
        var modelCount = 0
        for (file in files) {
            val root = JSONObject(file.readText())
            val manifest = A24PreparationManifest.parse(root)
            assertEquals(file.nameWithoutExtension, manifest.sessionId)
            assertEquals(10, manifest.minimumBatteryPercent())
            assertEquals(2, root.getInt("warmups_per_runtime"))
            val residentCount = if(root.getString("resident_mode") == "NONE") 0 else 4
            assertEquals(if(residentCount == 0) 0 else 8, residentCount*root.getInt("warmups_per_runtime"))
            assertEquals(64, manifest.exactPlanSha256().length)
            requestCount += manifest.requests.size
            val models = root.getJSONObject("models")
            assertEquals(A24PreparationContract.RUNTIME_KEYS.toSet(), models.keys().asSequence().toSet())
            for (key in A24PreparationContract.RUNTIME_KEYS) {
                val spec = ModelProbeManifestParser.parse(models.getJSONObject(key))
                assertEquals(manifest.sessionId, spec.identity.sessionId)
                assertEquals(root.getString("apk_sha256"), spec.target.apkSha256)
                assertEquals(root.getString("device_fingerprint"), spec.target.buildFingerprint)
                assertEquals("SM-A245N", spec.target.model)
                assertEquals(1, spec.runtime.cpuThreads)
                assertEquals("1.4.2", spec.runtime.litertVersion)
                A24PreparationContract.validateRuntimeMapping(key, spec.model.task.wireName, spec.execution.backend.name)
                modelCount++
            }
        }
        assertEquals(256, modelCount)
        assertEquals(8832, requestCount)
    }
}
