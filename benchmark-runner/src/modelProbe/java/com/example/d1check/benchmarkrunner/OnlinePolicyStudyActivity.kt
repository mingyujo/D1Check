package com.example.d1check.benchmarkrunner

import android.content.res.Configuration

/** Opt-in owner handles common display changes; actual destruction still cancels.
 * The static measurement view has no orientation/theme-specific mutable resources.
 */
class OnlinePolicyStudyActivity : ArrivalEnergyActivity() {
    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        recordConfigurationChange(newConfig)
    }
}
