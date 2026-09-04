package com.example.d1check

import android.content.Context
import android.provider.Settings
import android.os.SystemClock
import java.io.File
import java.util.UUID

data class RunContext(
    val runId: String,
    val active: Boolean,
    val startedElapsedNs: Long,
    val startedWallMs: Long,
    val bootId: String,
    val status: String,
)

data class NewRunDecision(val run: RunContext, val abortedRunId: String?)

/** Pure transition logic kept separate so stale-run and reboot behavior is JVM-testable. */
object RunSessionPolicy {
    fun startNew(
        existing: RunContext?,
        bootId: String,
        newRunId: String,
        elapsedNs: Long,
        wallMs: Long,
    ): NewRunDecision = NewRunDecision(
        run = RunContext(newRunId, true, elapsedNs, wallMs, bootId, STATUS_ACTIVE),
        abortedRunId = existing?.takeIf { it.active }?.runId,
    )

    const val STATUS_ACTIVE = "active"
    const val STATUS_STOPPED = "stopped"
    const val STATUS_ABORTED = "aborted"
}

object BootIdentifier {
    fun current(context: Context): String {
        val count = Settings.Global.getInt(context.contentResolver, Settings.Global.BOOT_COUNT, -1)
        if (count >= 0) return "boot_count:$count"
        val kernelId = runCatching {
            File("/proc/sys/kernel/random/boot_id").readText().trim()
        }.getOrNull()
        if (!kernelId.isNullOrBlank()) return "kernel_boot_id:$kernelId"
        // Last-resort boot-scoped approximation; rounded to absorb call-time jitter.
        val bootEpochMinute = (System.currentTimeMillis() - SystemClock.elapsedRealtime()) / 60_000L
        return "boot_epoch_minute:$bootEpochMinute"
    }
}

/** Same-process liveness gate: a provider revived after service process death rejects stale active. */
object TelemetryServiceLiveness {
    @Volatile var isRunning: Boolean = false
}

class RunSessionStore(private val context: Context) {
    private val preferences = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)

    @Synchronized
    fun current(): RunContext? {
        val runId = preferences.getString(KEY_RUN_ID, null) ?: return null
        return RunContext(
            runId = runId,
            active = preferences.getBoolean(KEY_ACTIVE, false),
            startedElapsedNs = preferences.getLong(KEY_STARTED_ELAPSED_NS, 0L),
            startedWallMs = preferences.getLong(KEY_STARTED_WALL_MS, 0L),
            bootId = preferences.getString(KEY_BOOT_ID, "") ?: "",
            status = preferences.getString(KEY_STATUS, RunSessionPolicy.STATUS_ABORTED)
                ?: RunSessionPolicy.STATUS_ABORTED,
        )
    }

    @Synchronized
    fun startNew(): RunContext {
        val existing = current()
        val decision = RunSessionPolicy.startNew(
            existing = existing,
            bootId = BootIdentifier.current(context),
            newRunId = UUID.randomUUID().toString(),
            elapsedNs = SystemClock.elapsedRealtimeNanos(),
            wallMs = System.currentTimeMillis(),
        )
        decision.abortedRunId?.let {
            preferences.edit()
                .putString(KEY_LAST_ABORTED_RUN_ID, it)
                .putString(KEY_LAST_ABORT_REASON, if (existing?.bootId == decision.run.bootId) {
                    "stale_active_run"
                } else {
                    "rebooted_active_run"
                })
                .commit()
        }
        val context = decision.run
        preferences.edit()
            .putString(KEY_RUN_ID, context.runId)
            .putBoolean(KEY_ACTIVE, true)
            .putLong(KEY_STARTED_ELAPSED_NS, context.startedElapsedNs)
            .putLong(KEY_STARTED_WALL_MS, context.startedWallMs)
            .putString(KEY_BOOT_ID, context.bootId)
            .putString(KEY_STATUS, context.status)
            .commit()
        return context
    }

    @Synchronized
    fun markInactive(runId: String, aborted: Boolean = false) {
        if (preferences.getString(KEY_RUN_ID, null) == runId) {
            preferences.edit()
                .putBoolean(KEY_ACTIVE, false)
                .putString(
                    KEY_STATUS,
                    if (aborted) RunSessionPolicy.STATUS_ABORTED else RunSessionPolicy.STATUS_STOPPED,
                )
                .commit()
        }
    }

    companion object {
        const val SCHEMA_VERSION = 2
        private const val PREFERENCES = "run_context"
        private const val KEY_RUN_ID = "run_id"
        private const val KEY_ACTIVE = "active"
        private const val KEY_STARTED_ELAPSED_NS = "started_elapsed_ns"
        private const val KEY_STARTED_WALL_MS = "started_wall_ms"
        private const val KEY_BOOT_ID = "boot_id"
        private const val KEY_STATUS = "status"
        private const val KEY_LAST_ABORTED_RUN_ID = "last_aborted_run_id"
        private const val KEY_LAST_ABORT_REASON = "last_aborted_reason"
    }
}
