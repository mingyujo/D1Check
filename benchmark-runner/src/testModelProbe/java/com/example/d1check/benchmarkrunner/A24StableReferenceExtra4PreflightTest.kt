package com.example.d1check.benchmarkrunner

import java.io.File
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** PC parser verification only; post-observation extra4 is separate from CONFIRM40. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk=[34])
class A24StableReferenceExtra4PreflightTest {
    @Test fun fourFreshM128ManifestsUseTheUnchangedActualParser() {
        val directory=File(requireNotNull(System.getenv("A24_EXTRA4_MANIFEST_DIR")))
        val files=directory.listFiles { it.extension=="json" }!!
        assertEquals(4,files.size)
        val arms=mutableSetOf<String>()
        val ids=mutableSetOf<String>()
        var count=0
        for(file in files) {
            val root=JSONObject(file.readText())
            val parsed=A24PreparationManifest.parse(root)
            assertEquals(file.nameWithoutExtension,parsed.sessionId)
            assertEquals("A24R02-EXTRA4-STABLE-20261016",root.getString("plan_id"))
            assertEquals("DEV",root.getString("stage"))
            assertEquals("M128",root.getString("recipe"))
            assertTrue(root.getBoolean("execution_authorized"))
            assertFalse(root.getBoolean("mock"))
            assertEquals(128,parsed.requests.size)
            assertEquals(10,parsed.minimumBatteryPercent())
            assertEquals(2,root.getInt("warmups_per_runtime"))
            assertTrue(ids.add(parsed.sessionId))
            arms.add(root.getString("arm"))
            count+=parsed.requests.size
            for(key in A24PreparationContract.RUNTIME_KEYS) {
                val spec=ModelProbeManifestParser.parse(root.getJSONObject("models").getJSONObject(key))
                assertEquals(parsed.sessionId,spec.identity.sessionId)
                assertEquals(root.getString("apk_sha256"),spec.target.apkSha256)
                assertEquals(root.getString("device_fingerprint"),spec.target.buildFingerprint)
                A24PreparationContract.validateRuntimeMapping(key,spec.model.task.wireName,spec.execution.backend.name)
            }
        }
        assertEquals(setOf("BASE","PAIR_G","WAIT200","ORDER"),arms)
        assertEquals(512,count)
    }
}
