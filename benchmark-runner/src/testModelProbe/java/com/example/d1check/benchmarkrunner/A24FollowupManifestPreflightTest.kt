package com.example.d1check.benchmarkrunner
import java.io.File
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
@RunWith(RobolectricTestRunner::class)
@Config(sdk=[34])
class A24FollowupManifestPreflightTest {
    @Test fun exactFollowupUsesTheActualUnchangedParser() {
        val root=JSONObject(File(requireNotNull(System.getenv("A24_FOLLOWUP_MANIFEST"))).readText())
        val manifest=A24PreparationManifest.parse(root)
        assertEquals("C252",root.getString("recipe"))
        assertEquals("C_CPU",root.getString("route"))
        assertEquals("DEV",root.getString("stage"))
        assertEquals(252,manifest.requests.size)
        assertEquals(10,manifest.minimumBatteryPercent())
        for(key in A24PreparationContract.RUNTIME_KEYS) {
            val spec=ModelProbeManifestParser.parse(root.getJSONObject("models").getJSONObject(key))
            assertEquals(manifest.sessionId,spec.identity.sessionId)
            assertEquals(root.getString("apk_sha256"),spec.target.apkSha256)
            assertEquals(root.getString("device_fingerprint"),spec.target.buildFingerprint)
            assertEquals("SM-A245N",spec.target.model)
            A24PreparationContract.validateRuntimeMapping(key,spec.model.task.wireName,spec.execution.backend.name)
        }
    }
}
