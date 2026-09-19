package com.example.d1check.benchmarkrunner

import android.os.SystemClock
import android.util.Log
import java.io.File
import java.io.FileOutputStream
import java.util.UUID
import java.nio.ByteBuffer
import java.nio.ByteOrder

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
    private val rawRoot = File(filesDir.canonicalFile, "model-probe-raw-v1/$sessionId")
    private var captured = false

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

    /** First invocation only; hashes are also present in the finalized 8-file probe result. */
    fun captureRaw(value: ProbeRawInvocation) {
        if (captured) return
        check(manifestHash != null)
        require(rawRoot.absoluteFile == rawRoot.canonicalFile && !rawRoot.exists() && rawRoot.mkdirs())
        val outputs = value.outputs.mapIndexed { index, values ->
            val file = File(rawRoot, "output_$index.f32le")
            val bytes = ByteBuffer.allocate(values.size * 4).order(ByteOrder.LITTLE_ENDIAN)
                .apply { values.forEach { putFloat(it) } }.array()
            FileOutputStream(file).use { it.write(bytes); it.fd.sync() }
            require(ProbeModelFile.sha256(file) == value.outputSha256[index])
            mapOf("filename" to file.name, "bytes" to bytes.size, "sha256" to value.outputSha256[index])
        }
        val descriptor = mapOf("protocol" to "model-probe-raw-v1", "session_id" to sessionId,
            "manifest_sha256" to manifestHash, "seed" to value.seed, "backend" to value.backend.name,
            "input_sha256" to value.inputSha256, "outputs" to outputs)
        FileOutputStream(File(rawRoot, "capture.json")).use {
            it.write(ModelProbeArtifacts.json(descriptor).toByteArray(Charsets.UTF_8)); it.fd.sync()
        }
        captured = true
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

/** Diagnostic storage failure must never prevent native resource cleanup. */
internal fun closeProbeResource(progress: ProbeProgress?, phase: String, close: () -> Unit) {
    var first: Throwable? = null
    var closeSucceeded = false
    listOf<() -> Unit>({ progress?.mark(phase, "start") }, { close(); closeSucceeded = true },
        { progress?.mark(phase, if (closeSucceeded) "finish" else "failed") }).forEach { operation ->
        try { operation() } catch (error: Throwable) {
            if (first == null) first = error else first?.addSuppressed(error)
        }
    }
    first?.let { throw it }
}
