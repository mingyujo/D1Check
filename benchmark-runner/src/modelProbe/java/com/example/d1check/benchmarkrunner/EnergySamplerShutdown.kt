package com.example.d1check.benchmarkrunner

import java.util.concurrent.ExecutorService
import java.util.concurrent.TimeUnit

/** A snapshot already running must leave its event writer before the journal closes. */
internal object EnergySamplerShutdown {
    fun stop(executor: ExecutorService, timeoutMillis: Long = 3000) {
        require(timeoutMillis > 0)
        executor.shutdownNow()
        check(executor.awaitTermination(timeoutMillis,TimeUnit.MILLISECONDS)) { "sampler shutdown not confirmed" }
    }
}
