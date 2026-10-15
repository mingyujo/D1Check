package com.example.d1check.benchmarkrunner

import java.io.File
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Exact private DEV8 bytes, parsed on PC before any phone launch. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk=[34])
class A24SuiteDeviceManifestPreflightTest {
    @Test fun eightApprovedDevelopmentManifestsUseActualParser() {
        val directory=System.getenv("A24_SUITE_DEVICE_MANIFEST_DIR")
        assumeTrue(directory!=null)
        val files=File(directory!!).listFiles { it.extension=="json" }!!
        assertEquals(8,files.size)
        var count=0
        for(file in files) {
            val root=JSONObject(file.readText())
            val parsed=A24PreparationManifest.parse(root)
            assertEquals(file.nameWithoutExtension,parsed.sessionId)
            assertEquals("DEV",root.getString("stage"))
            assertTrue(root.getBoolean("execution_authorized"))
            assertFalse(root.getBoolean("mock"))
            assertEquals("DEVICE_APPROVED_FOR_NEW_CONTRACT",root.getString("device_status"))
            assertEquals(10,parsed.minimumBatteryPercent())
            assertEquals(2,root.getInt("warmups_per_runtime"))
            count+=parsed.requests.size
            for(key in A24PreparationContract.RUNTIME_KEYS) {
                val spec=ModelProbeManifestParser.parse(root.getJSONObject("models").getJSONObject(key))
                assertEquals(parsed.sessionId,spec.identity.sessionId)
                assertEquals(root.getString("apk_sha256"),spec.target.apkSha256)
                assertEquals(root.getString("device_fingerprint"),spec.target.buildFingerprint)
                A24PreparationContract.validateRuntimeMapping(key,spec.model.task.wireName,spec.execution.backend.name)
            }
        }
        assertEquals(1144,count)
    }
}
