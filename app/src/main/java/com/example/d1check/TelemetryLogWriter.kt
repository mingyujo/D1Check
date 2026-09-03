package com.example.d1check

import android.content.Context
import java.io.BufferedWriter
import java.io.File
import java.io.FileWriter

class TelemetryLogWriter(context: Context, runId: String) : AutoCloseable {
    val file: File
    private val writer: BufferedWriter

    init {
        val base = context.getExternalFilesDir("runs") ?: File(context.filesDir, "runs")
        check(base.exists() || base.mkdirs()) { "Cannot create telemetry directory: $base" }
        file = File(base, "d1check-$runId.jsonl")
        writer = BufferedWriter(FileWriter(file, true))
    }

    @Synchronized
    fun append(json: String) {
        writer.append(json)
        writer.newLine()
        writer.flush()
    }

    @Synchronized
    override fun close() = writer.close()
}
