package com.example.d1check.benchmarkrunner

import android.content.Intent
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File
import java.nio.file.Files
import java.util.concurrent.AbstractExecutorService
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/** Runs real Activity callbacks, while withholding the inference worker and all device calls. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class EnergyCollectionLifecycleTest {
    private class HeldSetup : AbstractExecutorService() {
        var submissions = 0
        override fun execute(command: Runnable) { submissions++ }
        override fun shutdown() {}
        override fun shutdownNow(): MutableList<Runnable> = mutableListOf()
        override fun isShutdown() = false
        override fun isTerminated() = false
        override fun awaitTermination(timeout: Long, unit: TimeUnit) = false
    }

    private fun field(activity: EnergyCollectionActivity, name: String, value: Any) {
        EnergyCollectionActivity::class.java.getDeclaredField(name).apply {
            isAccessible = true
            set(activity, value)
        }
    }

    @Suppress("UNCHECKED_CAST")
    @Test fun destroyDuringPreparationRecordsFirstCauseAndLifecycleOrder() {
        val controller = Robolectric.buildActivity(EnergyCollectionActivity::class.java)
        val activity = controller.get()
        val held = HeldSetup()
        field(activity, "setup", held)
        controller.create().start().resume()
        assertEquals(1, held.submissions)

        val journal = File(Files.createTempDirectory("d1-lifecycle").toFile(), "progress.jsonl")
        val progress = EnergyProgress(journal)
        field(activity, "sid", "fixture-session")
        field(activity, "progress", progress)
        field(activity, "sessionControl", EnergySessionControl.DEVICE_AFTER_PROBE)
        EnergyCollectionActivity::class.java.getDeclaredMethod("onNewIntent", Intent::class.java).apply {
            isAccessible = true
        }.invoke(activity, Intent("fixture-second-intent"))
        controller.pause().stop().destroy()
        progress.close()

        val stop = EnergyCollectionActivity::class.java.getDeclaredField("stop").apply {
            isAccessible = true
        }.get(activity) as AtomicReference<String?>
        assertEquals("lifecycle_cancelled", stop.get())
        val rows = journal.readLines().map { JSONObject(it) }
        assertEquals(listOf("onNewIntent", "onPause", "onStop", "onDestroy"),
            rows.map { it.getString("callback") })
        assertEquals(1, rows.map { it.getString("activity_instance_id") }.toSet().size)
        assertEquals("lifecycle_cancelled", rows.last().getString("stop_reason"))
        assertFalse(rows.last().getBoolean("finish_requested_by_session"))
    }

    @Test fun destroyDoesNotReplaceEarlierGateCause() {
        val controller = Robolectric.buildActivity(EnergyCollectionActivity::class.java)
        val activity = controller.get()
        field(activity, "setup", HeldSetup())
        controller.create().start().resume()
        val stop = EnergyCollectionActivity::class.java.getDeclaredField("stop").apply {
            isAccessible = true
        }.get(activity) as AtomicReference<String?>
        stop.set("environment/screen_settings")
        controller.pause().stop().destroy()
        assertEquals("environment/screen_settings", stop.get())
    }
}
