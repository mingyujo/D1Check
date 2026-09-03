package com.example.d1check

import android.content.Context
import android.os.SystemClock
import java.util.UUID

data class RunContext(
    val runId: String,
    val active: Boolean,
    val startedElapsedNs: Long,
    val startedWallMs: Long,
)

class RunSessionStore(context: Context) {
    private val preferences = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)

    @Synchronized
    fun current(): RunContext? {
        val runId = preferences.getString(KEY_RUN_ID, null) ?: return null
        return RunContext(
            runId = runId,
            active = preferences.getBoolean(KEY_ACTIVE, false),
            startedElapsedNs = preferences.getLong(KEY_STARTED_ELAPSED_NS, 0L),
            startedWallMs = preferences.getLong(KEY_STARTED_WALL_MS, 0L),
        )
    }

    @Synchronized
    fun getOrCreate(forceNew: Boolean, requestedRunId: String? = null): RunContext {
        val existing = current()
        if (!forceNew && existing?.active == true) return existing
        val context = RunContext(
            runId = requestedRunId?.takeIf { it.isNotBlank() } ?: UUID.randomUUID().toString(),
            active = true,
            startedElapsedNs = SystemClock.elapsedRealtimeNanos(),
            startedWallMs = System.currentTimeMillis(),
        )
        preferences.edit()
            .putString(KEY_RUN_ID, context.runId)
            .putBoolean(KEY_ACTIVE, true)
            .putLong(KEY_STARTED_ELAPSED_NS, context.startedElapsedNs)
            .putLong(KEY_STARTED_WALL_MS, context.startedWallMs)
            .commit()
        return context
    }

    @Synchronized
    fun markInactive(runId: String) {
        if (preferences.getString(KEY_RUN_ID, null) == runId) {
            preferences.edit().putBoolean(KEY_ACTIVE, false).commit()
        }
    }

    companion object {
        const val SCHEMA_VERSION = 1
        private const val PREFERENCES = "run_context"
        private const val KEY_RUN_ID = "run_id"
        private const val KEY_ACTIVE = "active"
        private const val KEY_STARTED_ELAPSED_NS = "started_elapsed_ns"
        private const val KEY_STARTED_WALL_MS = "started_wall_ms"
    }
}
