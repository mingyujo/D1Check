package com.example.d1check.benchmarkrunner

import java.io.File
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Exact REV02 producer/consumer validation on PC. No native interpreter/device. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk=[34])
class A24Revision02ManifestPreflightTest {
    @Test fun bothExactPilotManifestsAreReadByTheUnchangedActualAppParser() {
        val directory = requireNotNull(System.getenv("A24_REV02_MANIFEST_DIR"))
        val files = File(directory).listFiles { f -> f.extension == "json" }!!.sortedBy { it.name }
        assertEquals(2, files.size)
        val requestIds = mutableListOf<List<String>>()
        val arms = mutableSetOf<String>()
        val planHashes = mutableSetOf<String>()
        for(file in files) {
            val root = JSONObject(file.readText())
            val manifest = A24PreparationManifest.parse(root)
            assertEquals(file.nameWithoutExtension,manifest.sessionId)
            assertEquals("A24-BLOCKED-INITIAL-STATE-REV02-20261015",root.getString("revision_id"))
            assertEquals("DEV",root.getString("stage"))
            assertEquals("C252",root.getString("recipe"))
            assertEquals(10,manifest.minimumBatteryPercent())
            assertEquals(252,manifest.requests.size)
            assertEquals(2,root.getInt("warmups_per_runtime"))
            val arm=root.getString("arm");arms.add(arm)
            assertEquals(if(arm=="CPU") "C_CPU" else "C_GPU_D_CPU",root.getString("route"))
            val requests=root.getJSONArray("requests")
            requestIds.add((0 until requests.length()).map { requests.getJSONObject(it).getString("request_id") })
            planHashes.add(manifest.exactPlanSha256())
            val models=root.getJSONObject("models")
            assertEquals(A24PreparationContract.RUNTIME_KEYS.toSet(),models.keys().asSequence().toSet())
            for(key in A24PreparationContract.RUNTIME_KEYS) {
                val spec=ModelProbeManifestParser.parse(models.getJSONObject(key))
                assertEquals(manifest.sessionId,spec.identity.sessionId)
                assertEquals(root.getString("apk_sha256"),spec.target.apkSha256)
                assertEquals(root.getString("device_fingerprint"),spec.target.buildFingerprint)
                assertEquals("SM-A245N",spec.target.model)
                assertEquals(1,spec.runtime.cpuThreads)
                assertEquals("1.4.2",spec.runtime.litertVersion)
                A24PreparationContract.validateRuntimeMapping(key,spec.model.task.wireName,spec.execution.backend.name)
            }
        }
        assertEquals(setOf("CPU","GPU"),arms)
        assertEquals(requestIds[0],requestIds[1])
        assertEquals(252,requestIds[0].toSet().size)
        assertEquals(1,planHashes.size)
    }
}
