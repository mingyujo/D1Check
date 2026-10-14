package com.example.d1check.benchmarkrunner

import android.content.Intent
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Pure Robolectric entry rejection: no actual Android target or neural calls. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk=[34])
class A24PreparationEntryTest {
    @Test fun ordinaryLaunchCannotStartAMeasurement() {
        val controller = Robolectric.buildActivity(A24PreparationActivity::class.java).create()
        assertTrue(controller.get().isFinishing)
        assertFalse(controller.get().filesDir.resolve("a24_laptop_results").exists())
        controller.destroy()
    }
    @Test fun protocolAloneCannotAuthorizeAMeasurement() {
        val intent = Intent().putExtra("a24_protocol",A24PreparationContract.PROTOCOL)
        val controller = Robolectric.buildActivity(A24PreparationActivity::class.java,intent).create()
        assertTrue(controller.get().isFinishing)
        assertFalse(controller.get().filesDir.resolve("a24_laptop_results").exists())
        controller.destroy()
    }
    @Test fun invalidSessionNeverCreatesSessionEvidence() {
        val intent = Intent().putExtra("a24_protocol",A24PreparationContract.PROTOCOL)
            .putExtra("a24_execute_authorized",true).putExtra("session_id","not-a-uuid")
        val controller = Robolectric.buildActivity(A24PreparationActivity::class.java,intent).create()
        assertTrue(controller.get().isFinishing)
        assertFalse(controller.get().filesDir.resolve("a24_laptop_results").exists())
        controller.destroy()
    }
    @Test fun onlyAuthorizedValidSessionKeepsScreenOnWithoutChangingSettings() {
        val intent = Intent().putExtra("a24_protocol",A24PreparationContract.PROTOCOL)
            .putExtra("a24_execute_authorized",true).putExtra("session_id","12086e3c-817f-520f-88b0-53340522ad79")
        val controller = Robolectric.buildActivity(A24PreparationActivity::class.java,intent).create()
        assertTrue(controller.get().window.attributes.flags and android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON != 0)
        // No private input exists: preparation fails closed, without a model or native call.
        assertFalse(controller.get().filesDir.resolve("a24_laptop_results").exists())
        controller.destroy()
    }
}
