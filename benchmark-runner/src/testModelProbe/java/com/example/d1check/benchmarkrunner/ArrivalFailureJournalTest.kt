package com.example.d1check.benchmarkrunner

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File
import java.nio.file.Files
import java.util.concurrent.*

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class ArrivalFailureJournalTest {
    private val sid = "00000000-0000-0000-0000-000000000001"
    private val records = mutableListOf<JSONObject>()
    private var ticks = 0L
    private fun journal(capacity: Int = 128) = ArrivalFailureJournal(sid, "a".repeat(64), { ++ticks },
        { records.add(JSONObject(String(it, Charsets.UTF_8))) }, capacity = capacity)

    @Test fun firstAndLaterRuntimeFailuresPreserveExactPrefix() {
        for (failAt in listOf(0, 3)) {
            records.clear(); val j = journal(); var entered = 0
            assertThrows(IllegalStateException::class.java) {
                listOf("classification_CPU", "classification_GPU", "detection_CPU", "detection_GPU").forEachIndexed { i, key ->
                    arrivalDiagnosticOperation(j, "runtime_create", key) { entered++; if (i == failAt) error("injected create failure") }
                }
            }
            assertEquals(failAt + 1, entered)
            assertEquals(failAt, records.count { it.getString("edge") == "succeeded" })
            assertEquals("failed", records.last().getString("edge"))
            assertTrue(records.all { it.getString("session_id") == sid && it.getString("manifest_sha256") == "a".repeat(64) })
        }
    }

    @Test fun warmupAndRequestFailureNeverBecomeCompletionOrRetry() {
        for (stage in listOf("warmup", "diagnostic")) {
            records.clear(); val j=journal()
            arrivalDiagnosticOperation(j, stage, "classification_GPU", "q0") { 1 }
            assertThrows(IllegalArgumentException::class.java) {
                arrivalDiagnosticOperation(j, stage, "classification_GPU", "q1") { throw IllegalArgumentException("injected invoke") }
            }
            assertThrows(CancellationException::class.java) { arrivalDiagnosticOperation(j,stage,"classification_GPU","q2") { error("must not enter") } }
            assertEquals(1,records.count { it.getString("edge")=="succeeded" })
            assertEquals("q1",records.last().getString("request_id"))
        }
    }

    @Test fun timeoutRecordsWaitFailureWithoutInventingNativeCompletion() {
        val j=journal(); val pool=Executors.newSingleThreadExecutor(); val release=CountDownLatch(1)
        val started=CountDownLatch(1)
        try {
            assertThrows(TimeoutException::class.java) {
                arrivalDiagnosticOperation(j,"runtime_wait","detection_GPU") {
                    pool.submit {
                        j.mark("runtime_create","start","detection_GPU")
                        started.countDown(); release.await()
                    }.also { assertTrue(started.await(2,TimeUnit.SECONDS)) }.get(1,TimeUnit.MILLISECONDS)
                }
            }
            assertTrue(records.any { it.getString("stage")=="runtime_create" && it.getString("edge")=="start" })
            assertFalse(records.any { it.getString("edge")=="succeeded" })
            assertEquals("runtime_wait",records.last().getString("stage"))
        } finally { release.countDown(); pool.shutdownNow(); pool.awaitTermination(2,TimeUnit.SECONDS) }
    }

    @Test fun cancellationAndWriteFailureStopBeforeNextCallButDoNotBlockCleanup() {
        val j=journal();j.mark("session","start");j.stop("cancelled by lifecycle")
        assertThrows(CancellationException::class.java) { j.operation("warmup","CPU","q") { error("not entered") } }
        var entered=false;var closed=false
        val bad=ArrivalFailureJournal(sid,"a".repeat(64),{1L},{throw java.io.IOException("disk full")})
        try { assertThrows(java.io.IOException::class.java) { bad.operation("runtime_create","CPU") { entered=true } } }
        finally { closed=true }
        assertFalse(entered);assertTrue(closed);assertNotNull(bad.recordingFailure)
    }

    @Test fun boundedJournalAndDiskPrefixSurviveWithoutFinally() {
        val root=Files.createTempDirectory("arrival-journal-test").toFile()
        try {
            val j=ArrivalFailureJournal.open(root,sid,"a".repeat(64),{++ticks},{})
            j.mark("session","start");j.mark("runtime_create","start","detection_GPU")
            // No terminal/finally: two durable records remain readable by another reader.
            val rows=File(root,"failure_progress.jsonl").readLines().map(::JSONObject)
            assertEquals(2,rows.size);assertEquals("start",rows.last().getString("edge"))
            val bounded=journal(1);bounded.mark("session","start")
            assertThrows(IllegalStateException::class.java) { bounded.operation("warmup","CPU","q") { error("not entered") } }
            assertNotNull(bounded.recordingFailure)
        } finally { root.deleteRecursively() }
    }

    @Test fun legacyNullJournalDoesNotWriteOrChangeReturn() {
        assertEquals(17,arrivalDiagnosticOperation(null,"runtime_create","CPU") { 17 })
        assertTrue(records.isEmpty())
    }

    @Test fun terminalWriteFailureRetainsStartButCannotClaimReturnOrRunNextCall() {
        var writes=0;var bodyReturned=false
        val j=ArrivalFailureJournal(sid,"a".repeat(64),{++ticks},{ bytes ->
            if (++writes==2) throw java.io.IOException("injected terminal fsync failure")
            records.add(JSONObject(String(bytes,Charsets.UTF_8)))
        })
        assertThrows(java.io.IOException::class.java) {
            j.operation("diagnostic","CPU","q0") { bodyReturned=true }
        }
        assertTrue(bodyReturned);assertEquals(1,records.size)
        assertEquals("start",records.single().getString("edge"))
        assertThrows(CancellationException::class.java) { j.operation("diagnostic","CPU","q1") { error("not entered") } }
    }
}
