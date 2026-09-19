package com.example.d1check.benchmarkrunner

import android.os.SystemClock
import android.util.Log
import java.io.File
import java.io.FileOutputStream
import java.util.UUID

/** Separate diagnostic journal, never a finalized probe artifact or official timing sample. */
internal class ProbeProgress(
    filesDir: File,
    private val sessionId: String,
    private val clock: () -> Long = SystemClock::elapsedRealtimeNanos,
    private val mirror: (String) -> Unit = { Log.i("D1PROGRESS", it) },
) {
    private val file: File
    private var sequence = 0
    private var previous = -1L
    private var manifestHash: String? = null

    init {
        require(UUID.fromString(sessionId).toString() == sessionId)
        val base = filesDir.canonicalFile
        val parent = File(base, "model-probe-progress-v1")
        require(parent.absoluteFile == parent.canonicalFile && parent.parentFile == base)
        require(parent.isDirectory || parent.mkdirs())
        file = File(parent, "$sessionId.jsonl")
        require(file.absoluteFile == file.canonicalFile && file.createNewFile()) { "Stale progress session" }
    }

    fun bind(hash: String) {
        require(manifestHash == null && hash.matches(Regex("[a-f0-9]{64}")))
        manifestHash = hash
        mark("manifest_binding", "finish")
    }

    @Synchronized
    fun mark(phase: String, edge: String) {
        require(phase.matches(Regex("[a-z0-9_]+")) && edge in setOf("start", "finish", "failed"))
        val now = clock()
        check(now >= 0 && now >= previous) { "Progress clock regressed" }
        val line = ModelProbeArtifacts.json(linkedMapOf(
            "protocol" to "model-probe-progress-v1", "session_id" to sessionId,
            "manifest_sha256" to manifestHash, "sequence" to sequence,
            "mono_ns" to now, "clock" to "elapsedRealtimeNanos",
            "phase" to phase, "edge" to edge,
            "thread_id" to Thread.currentThread().id,
        ))
        FileOutputStream(file, true).use { stream ->
            stream.write((line + "\n").toByteArray(Charsets.UTF_8))
            stream.fd.sync()
        }
        previous = now
        sequence++
        mirror(line)
    }
}
