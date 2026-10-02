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
import java.util.UUID
import java.util.concurrent.AbstractExecutorService
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/** Actual Activity callbacks with the inference worker held; no adapter or device calls. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class ArrivalEnergyLifecycleTest {
    private class HeldSetup : AbstractExecutorService() {
        val pending = mutableListOf<Runnable>()
        override fun execute(command: Runnable) { pending.add(command) }
        override fun shutdown() {}
        override fun shutdownNow(): MutableList<Runnable> = mutableListOf()
        override fun isShutdown() = false
        override fun isTerminated() = false
        override fun awaitTermination(timeout: Long, unit: TimeUnit) = false
    }

    private fun field(activity: ArrivalEnergyActivity, name: String, value: Any) {
        ArrivalEnergyActivity::class.java.getDeclaredField(name).apply {
            isAccessible = true
            set(activity, value)
        }
    }

    @Suppress("UNCHECKED_CAST")
    private fun stop(activity: ArrivalEnergyActivity) =
        ArrivalEnergyActivity::class.java.getDeclaredField("stop").apply {
            isAccessible = true
        }.get(activity) as AtomicReference<String?>

    @Test fun onlineConfigurationCallbackKeepsOneOwnerAndDestroyStillCancels() {
        val controller = Robolectric.buildActivity(OnlinePolicyStudyActivity::class.java)
        val activity = controller.get()
        val held = HeldSetup()
        field(activity, "setup", held)
        controller.create().start().resume().visible()
        val journal = File(Files.createTempDirectory("d1-online-config").toFile(), "progress.jsonl")
        val progress = EnergyProgress(journal)
        field(activity, "sid", "configuration-fixture")
        field(activity, "progress", progress)
        val changed = android.content.res.Configuration(activity.resources.configuration)
        changed.orientation = android.content.res.Configuration.ORIENTATION_LANDSCAPE
        changed.screenWidthDp = 800
        changed.screenHeightDp = 400
        controller.configurationChange(changed)
        assertSame(activity, controller.get())
        assertEquals(1, held.pending.size)
        assertNull(stop(activity).get())
        controller.pause().stop().destroy()
        progress.close()
        assertEquals("lifecycle_cancelled", stop(activity).get())
        val rows = journal.readLines().map { JSONObject(it) }
        assertEquals(1, rows.count { it.optString("callback") == "onConfigurationChanged" })
        assertEquals(1, rows.count { it.optString("callback") == "onDestroy" })
        assertEquals(1, rows.map { it.getString("activity_instance_id") }.toSet().size)
        assertTrue(rows.single { it.getString("kind") == "activity_configuration" }.getBoolean("owner_preserved"))
    }

    @Test fun pauseAndStopDoNotCancelButDestroyRecordsTheFirstCause() {
        val controller = Robolectric.buildActivity(ArrivalEnergyActivity::class.java)
        val activity = controller.get()
        val held = HeldSetup()
        field(activity, "setup", held)
        controller.create().start().resume()
        assertEquals(1, held.pending.size)

        val journal = File(Files.createTempDirectory("d1-arrival-life").toFile(), "progress.jsonl")
        val progress = EnergyProgress(journal)
        field(activity, "sid", "fixture-session")
        field(activity, "progress", progress)
        controller.pause().stop()
        assertNull(stop(activity).get())
        controller.destroy()
        progress.close()

        assertEquals("lifecycle_cancelled", stop(activity).get())
        val rows = journal.readLines().map { JSONObject(it) }
        assertEquals(listOf("onPause", "onStop", "onDestroy"),
            rows.map { it.getString("callback") })
        assertEquals(1, rows.map { it.getString("activity_instance_id") }.toSet().size)
        assertEquals("lifecycle_cancelled", rows.last().getString("stop_reason"))
        assertFalse(rows.last().getBoolean("finish_requested_by_session"))
    }

    @Test fun destroyDoesNotReplaceAnEarlierErrorOrCompletedSession() {
        val controller = Robolectric.buildActivity(ArrivalEnergyActivity::class.java)
        val activity = controller.get()
        field(activity, "setup", HeldSetup())
        controller.create().start().resume()
        stop(activity).set("environment/thermal")
        controller.pause().stop().destroy()
        assertEquals("environment/thermal", stop(activity).get())

        val normal = Robolectric.buildActivity(ArrivalEnergyActivity::class.java)
        val finished = normal.get()
        field(finished, "setup", HeldSetup())
        normal.create().start().resume()
        field(finished, "finished", true)
        field(finished, "finishRequested", true)
        normal.pause().stop().destroy()
        assertNull(stop(finished).get())
    }

    @Test fun staleSessionOutputRejectsSecondActivityBeforeInferenceOrCleanupWrite() {
        val sid = UUID.randomUUID().toString()
        val intent = Intent("com.example.d1check.benchmarkrunner.action.ARRIVAL_ENERGY")
            .putExtra("session_id", sid)
        val controller = Robolectric.buildActivity(ArrivalEnergyActivity::class.java, intent)
        val activity = controller.get()
        val held = HeldSetup()
        field(activity, "setup", held)
        controller.create().start().resume()
        val input = File(activity.filesDir, "arrival-scheduler-inputs/$sid")
        assertTrue(input.mkdirs())
        File(input, "manifest.json").writeText("{}")
        val owned = File(activity.filesDir, "${ArrivalEnergyContract.PROTOCOL}/$sid")
        assertTrue(owned.mkdirs())
        val sentinel = File(owned, "owner.txt")
        sentinel.writeText("first instance owns this output")

        held.pending.single().run()

        assertEquals("first instance owns this output", sentinel.readText())
        assertFalse(File(owned, "session_failure.json").exists())
        assertFalse(File(owned, "cleanup.json").exists())
        assertFalse(File(owned, "progress.jsonl").exists())
    }
}
