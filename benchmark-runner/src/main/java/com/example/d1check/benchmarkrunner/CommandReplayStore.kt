package com.example.d1check.benchmarkrunner

import android.content.Context

internal object CommandReplayPolicy {
    const val MAX_HISTORY = 64

    fun append(history: List<String>, commandId: String): List<String>? {
        if (commandId in history) return null
        return (history + commandId).takeLast(MAX_HISTORY)
    }
}

internal object BenchmarkExecutionGate {
    @Volatile
    var isRunning: Boolean = false
        private set

    @Synchronized
    fun tryAcquire(): Boolean {
        if (isRunning) return false
        isRunning = true
        return true
    }

    @Synchronized
    fun release() {
        isRunning = false
    }
}

internal class CommandReplayStore(context: Context) {
    private val preferences = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)

    @Synchronized
    fun claim(commandId: String): Boolean {
        val history = preferences.getString(HISTORY, "")
            .orEmpty()
            .lineSequence()
            .filter { it.isNotBlank() }
            .toList()
        val updated = CommandReplayPolicy.append(history, commandId) ?: return false
        return preferences.edit().putString(HISTORY, updated.joinToString("\n")).commit()
    }

    companion object {
        private const val PREFERENCES = "automation_commands"
        private const val HISTORY = "claimed_command_ids"
    }
}
