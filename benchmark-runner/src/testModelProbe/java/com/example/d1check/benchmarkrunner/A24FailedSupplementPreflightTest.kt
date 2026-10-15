package com.example.d1check.benchmarkrunner

import java.io.File
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Actual production parser, on PC only. No device or inference. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk=[34])
class A24FailedSupplementPreflightTest {
    @Test fun twelveFreshSupplementManifestsUseTheUnchangedActualParser() {
        val directory=File(requireNotNull(System.getenv("A24_SUPPLEMENT_MANIFEST_DIR")))
        val files=directory.listFiles { it.extension=="json" }!!
        assertEquals(12,files.size)
        var count=0
        var idle=0
        val ids=mutableSetOf<String>()
        for(file in files) {
            val root=JSONObject(file.readText())
            val parsed=A24PreparationManifest.parse(root)
            assertEquals(file.nameWithoutExtension,parsed.sessionId)
            assertEquals("A24-FAILED-SUPPLEMENT12-20261016",root.getString("plan_id"))
            assertEquals("DEV",root.getString("stage"))
            assertTrue(ids.add(parsed.sessionId))
            assertNotEquals(root.getString("original_failed_session_id"),parsed.sessionId)
            assertEquals(10,parsed.minimumBatteryPercent())
            assertEquals(2,root.getInt("warmups_per_runtime"))
            if(root.getString("recipe")=="IDLE") { assertTrue(parsed.requests.isEmpty());idle++ }
            for(key in A24PreparationContract.RUNTIME_KEYS) {
                val spec=ModelProbeManifestParser.parse(root.getJSONObject("models").getJSONObject(key))
                assertEquals(parsed.sessionId,spec.identity.sessionId)
                assertEquals(root.getString("apk_sha256"),spec.target.apkSha256)
                assertEquals(root.getString("device_fingerprint"),spec.target.buildFingerprint)
                A24PreparationContract.validateRuntimeMapping(key,spec.model.task.wireName,spec.execution.backend.name)
            }
            count+=parsed.requests.size
        }
        assertEquals(2,idle)
        assertEquals(1520,count)
    }
}
