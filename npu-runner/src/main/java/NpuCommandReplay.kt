package com.example.d1check.npurunner

import android.content.Context

/*
 * 미러 원본: benchmark-runner/.../CommandReplayStore.kt — 로직 무변경.
 * 같은 d1_command_id 가 두 번 오면(Activity 재생성 등) 두 번째는 무시한다. 기록은 이 앱의
 * SharedPreferences 에만 남으므로 benchmark-runner 의 기록과 섞이지 않는다.
 */

internal object CommandReplayPolicy {
    const val MAX_HISTORY = 64

    fun append(history: List<String>, commandId: String): List<String>? {
        if (commandId in history) return null
        return (history + commandId).takeLast(MAX_HISTORY)
    }
}

/** benchmark-runner 의 BenchmarkExecutionGate 와 같다. timed run 은 한 번에 하나. */
internal object NpuExecutionGate {
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
