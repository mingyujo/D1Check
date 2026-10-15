package com.example.d1check.benchmarkrunner

import java.io.File
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** PC parser only. These40 drafts explicitly fail the Activity execution guard. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class A24SuiteManifestPreflightTest {
    @Test fun all40ConfirmationDraftsParseWithoutAnyExecutionPermission() {
        val directory = System.getenv("A24_SUITE_MANIFEST_DIR")
        assumeTrue("Supply private non-executable suite drafts", directory != null)
        val files = File(directory!!).listFiles { f -> f.extension == "json" }!!.sortedBy { it.name }
        assertEquals(40, files.size)
        val groups = mutableMapOf<String, MutableList<JSONObject>>()
        var requests = 0
        var runtimes = 0
        for (file in files) {
            val root = JSONObject(file.readText())
            val manifest = A24PreparationManifest.parse(root)
            assertEquals(file.nameWithoutExtension, manifest.sessionId)
            assertEquals("CONFIRM", root.getString("stage"))
            assertFalse(root.getBoolean("execution_authorized"))
            assertTrue(root.getBoolean("mock"))
            assertEquals("PC_ONLY_NOT_APPROVED", root.getString("device_status"))
            assertEquals(10, manifest.minimumBatteryPercent())
            assertEquals(2, root.getInt("warmups_per_runtime"))
            assertEquals(root.getInt("request_count"), manifest.requests.size)
            groups.getOrPut(root.getString("gate_block_id")) { mutableListOf() }.add(root)
            requests += manifest.requests.size
            val models = root.getJSONObject("models")
            for (key in A24PreparationContract.RUNTIME_KEYS) {
                val spec = ModelProbeManifestParser.parse(models.getJSONObject(key))
                assertEquals(manifest.sessionId, spec.identity.sessionId)
                assertEquals(root.getString("apk_sha256"), spec.target.apkSha256)
                A24PreparationContract.validateRuntimeMapping(key, spec.model.task.wireName, spec.execution.backend.name)
                runtimes++
            }
        }
        assertEquals(5720, requests)
        assertEquals(160, runtimes)
        assertEquals(15, groups.size)
        for (group in groups.values) {
            assertEquals(1, group.count { it.getString("reference_role") == "SELECT_FIRST" })
            val first = group.single { it.getString("reference_role") == "SELECT_FIRST" }
            assertTrue(group.all { it.getString("reference_owner_session_id") == first.getString("session_id") })
            assertTrue(group.all { it.getJSONArray("requests").toString() == first.getJSONArray("requests").toString() })
        }
    }
}
