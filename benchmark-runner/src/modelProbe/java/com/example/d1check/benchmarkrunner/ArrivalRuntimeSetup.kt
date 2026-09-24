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

    fun closeLane(lane: ExecutorService, timeout: Long = 5, unit: TimeUnit = TimeUnit.SECONDS,
                  close: () -> Unit) {
        // A stuck constructor cannot make the caller wait indefinitely for the queued close.
        lane.submit { close() }.get(timeout, unit)
    }
}
