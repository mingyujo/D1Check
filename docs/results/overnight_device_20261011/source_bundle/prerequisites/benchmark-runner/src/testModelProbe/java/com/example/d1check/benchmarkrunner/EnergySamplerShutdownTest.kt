package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

class EnergySamplerShutdownTest {
    @Test fun waitsForAnAlreadyRunningUninterruptibleSnapshotBeforeJournalClose() {
        val samples=Executors.newSingleThreadExecutor();val owner=Executors.newSingleThreadExecutor()
        val started=CountDownLatch(1);val interrupted=CountDownLatch(1);val release=CountDownLatch(1)
        val written=AtomicBoolean(false);val closed=AtomicBoolean(false)
        try {
            samples.submit {
                started.countDown()
                try { release.await() } catch(_: InterruptedException) { interrupted.countDown();release.await() }
                check(!closed.get());written.set(true)
            }
            assertTrue(started.await(1,TimeUnit.SECONDS))
            val stopping=owner.submit { EnergySamplerShutdown.stop(samples);closed.set(true) }
            assertTrue(interrupted.await(1,TimeUnit.SECONDS));assertFalse(stopping.isDone)
            release.countDown();stopping.get(1,TimeUnit.SECONDS)
            assertTrue(written.get());assertTrue(closed.get());assertTrue(samples.isTerminated)
        } finally { release.countDown();samples.shutdownNow();owner.shutdownNow() }
    }
}
