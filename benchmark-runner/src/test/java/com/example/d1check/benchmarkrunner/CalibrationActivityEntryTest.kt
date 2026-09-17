package com.example.d1check.benchmarkrunner

import android.content.Intent
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class CalibrationActivityEntryTest {
    @Test
    fun mainActivityOpensProductionCalibrationActivityAndPlatformDocumentPicker() {
        val main = Robolectric.buildActivity(MainActivity::class.java).setup().get()
        val calibrationButton = findButton(main.findViewById(android.R.id.content), "Open image calibration")
        assertNotNull(calibrationButton)
        calibrationButton!!.performClick()
        val launch = shadowOf(main).nextStartedActivity
        assertEquals(CalibrationActivity::class.java.name, launch.component?.className)

        val calibration = Robolectric.buildActivity(CalibrationActivity::class.java).setup().get()
        val manifestButton = findButton(
            calibration.findViewById(android.R.id.content),
            "Select calibration manifest",
        )
        assertNotNull(manifestButton)
        manifestButton!!.performClick()
        val picker = shadowOf(calibration).nextStartedActivity
        assertEquals(Intent.ACTION_OPEN_DOCUMENT, picker.action)
        assertEquals(Intent.CATEGORY_OPENABLE, picker.categories.single())
    }

    private fun findButton(root: View, text: String): Button? {
        if (root is Button && root.text.toString() == text) return root
        if (root is ViewGroup) {
            repeat(root.childCount) { index ->
                findButton(root.getChildAt(index), text)?.let { return it }
            }
        }
        return null
    }
}
