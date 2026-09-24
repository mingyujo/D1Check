package com.example.d1check.benchmarkrunner

import java.io.File
import java.io.FileOutputStream
import java.util.UUID
import java.util.concurrent.CancellationException
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.locks.ReentrantLock

/** Opt-in failure diagnosis ONLY. Fsync cost makes these runs ineligible for calibration/performance. */
internal class ArrivalFailureJournal(
    private val sessionId: String,
    private val manifestHash: String,
    private val clock: () -> Long,
    private val append: (ByteArray) -> Unit,
    private val mirrorFailure: (String) -> Unit = {},
    private val capacity: Int = 128,
) {
    companion object {
        const val CONTRACT = "arrival-failure-journal-v1"
        fun open(output: File, sid: String, hash: String, clock: () -> Long,
                 mirror: (String) -> Unit): ArrivalFailureJournal {
            val file = File(output, "failure_progress.jsonl")
            check(file.createNewFile()) { "progress already exists" }
            return ArrivalFailureJournal(sid, hash, clock, { bytes ->
                FileOutputStream(file, true).use { it.write(bytes); it.fd.sync() }
            }, mirror)
        }
    }
    private val lock = ReentrantLock()
    private val stopped = AtomicBoolean(false)
    @Volatile var recordingFailure: String? = null
        private set
    private var sequence = 0
    private var previousWriteNs = 0L
    init {
        require(UUID.fromString(sessionId).toString() == sessionId)
        require(manifestHash.matches(Regex("[a-f0-9]{64}")))
    }

    fun mark(stage: String, edge: String, key: String? = null, requestId: String? = null,
             detail: String? = null) {
        check(recordingFailure == null) { "journal poisoned: $recordingFailure" }
        try {
            check(lock.tryLock(50, TimeUnit.MILLISECONDS)) { "journal lock timeout" }
            try {
                check(sequence < capacity) { "journal capacity exceeded" }
                val start = clock()
                val bytes = (ModelProbeArtifacts.json(linkedMapOf(
                    "protocol" to CONTRACT, "session_id" to sessionId, "manifest_sha256" to manifestHash,
                    "sequence" to sequence, "mono_ns" to start, "stage" to stage, "edge" to edge,
                    "model_key" to key, "request_id" to requestId, "detail" to detail?.take(1024),
                    "thread_id" to Thread.currentThread().id, "previous_append_ns" to previousWriteNs,
                    "performance_excluded" to true,
                )) + "\n").toByteArray(Charsets.UTF_8)
                check(bytes.size <= 8192) { "journal event too large" }
                append(bytes) // Must succeed before the protected operation is entered.
                previousWriteNs = clock() - start
                sequence++
            } finally { lock.unlock() }
        } catch (e: Throwable) {
            recordingFailure = e.toString(); stopped.set(true)
            mirrorFailure("journal_failure session=$sessionId: $e")
            throw e
        }
    }

    fun ensureActive() {
        if (stopped.get() || recordingFailure != null) throw CancellationException("diagnostic stopped: $recordingFailure")
    }

    fun bestEffort(stage: String, edge: String, detail: String? = null) {
        try { mark(stage, edge, detail = detail) } catch (_: Throwable) { /* sticky failure; cleanup still required */ }
    }

    fun requestStop() { stopped.set(true) }
    fun stop(reason: String) { requestStop(); bestEffort("session", "stopped", reason) }

    fun <T> operation(stage: String, key: String?, requestId: String? = null, body: () -> T): T {
        ensureActive()
        mark(stage, "start", key, requestId) // A start is an intent/upper bound, never proof of completion.
        try {
            ensureActive()
            val value = body()
            mark(stage, "succeeded", key, requestId)
            return value
        } catch (e: Throwable) {
            try { mark(stage, when (e) {
                is CancellationException, is InterruptedException -> "cancelled"
                is java.util.concurrent.TimeoutException -> "timeout"
                else -> "failed"
            },
                key, requestId, e.toString()) } catch (_: Throwable) {}
            stopped.set(true)
            throw e
        }
    }
}

/** Persist intent/result around bounded waits, independently of a possibly stuck native worker. */
internal fun <T> arrivalDiagnosticOperation(journal: ArrivalFailureJournal?, stage: String, key: String?,
                                          id: String? = null, body: () -> T): T =
    if (journal == null) body() else journal.operation(stage, key, id, body)
