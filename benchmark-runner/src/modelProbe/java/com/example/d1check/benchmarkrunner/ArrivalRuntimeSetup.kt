package com.example.d1check.benchmarkrunner

import java.util.concurrent.ExecutorService
import java.util.concurrent.TimeUnit

/** Same ordered, blocking initialization as CAL-02; no invocation callback is accepted. */
internal object ArrivalRuntimeSetup {
    fun initialize(keys: Set<String>, setupOnly: Boolean, warmups: Int, requests: Int,
                   create: (String) -> Unit): Boolean {
        if (setupOnly) require(warmups == 0 && requests == 0) { "setup-only forbids calls" }
        require(keys == setOf("classification_CPU", "classification_GPU", "detection_CPU", "detection_GPU"))
        keys.sorted().forEach(create) // Exception stops the sequence; never retry.
        return setupOnly
    }

    fun firstWarmupOnly(scope: String?, keys: List<String>, requests: Int): Boolean {
        if (scope != "first_warmup") return false
        require(keys == listOf("classification_CPU") && requests == 0) { "first-warmup cap/order" }
        return true
    }

    fun runFirstWarmup(lane: ExecutorService, journal: ArrivalFailureJournal, id: String,
                       timeout: Long = 30, unit: TimeUnit = TimeUnit.SECONDS, call: () -> Unit) {
        val key = "classification_CPU"
        arrivalDiagnosticOperation(journal, "warmup_wait", key, id) {
            lane.submit {
                arrivalDiagnosticOperation(journal, "warmup", key, id, call)
            }.get(timeout, unit)
        }
        journal.mark("first_warmup", "succeeded")
    }

    fun integratedCalls(scope: String?, keys: List<String>, requests: Int) {
        if (scope != "warmup_and_request") return
        require(keys == listOf("classification_CPU", "classification_CPU", "classification_GPU", "classification_GPU",
            "detection_CPU", "detection_CPU", "detection_GPU", "detection_GPU") && requests == 1)
    }

    fun runWarmup(lane: ExecutorService, journal: ArrivalFailureJournal?, key: String, id: String,
                  timeout: Long = 30, unit: TimeUnit = TimeUnit.SECONDS, call: () -> Unit) {
        arrivalDiagnosticOperation(journal, "warmup_wait", key, id) {
            lane.submit { arrivalDiagnosticOperation(journal, "warmup", key, id, call) }.get(timeout, unit)
        }
    }

    fun closeLane(lane: ExecutorService, timeout: Long = 5, unit: TimeUnit = TimeUnit.SECONDS,
                  close: () -> Unit) {
        // A stuck constructor cannot make the caller wait indefinitely for the queued close.
        lane.submit { close() }.get(timeout, unit)
    }
}
