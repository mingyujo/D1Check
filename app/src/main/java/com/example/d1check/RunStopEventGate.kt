package com.example.d1check

/** Allows one run_stop event for each run that reached startRun(). */
internal class RunStopEventGate {
    private var active = false

    fun markRunStarted() {
        active = true
    }

    fun consumeStop(): Boolean {
        if (!active) return false
        active = false
        return true
    }
}
