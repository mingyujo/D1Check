package com.example.d1check.benchmarkrunner

import java.io.File
import java.io.FileInputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.channels.FileChannel
import java.security.MessageDigest

internal object V4ModelFile {
    fun open(sessionRoot: File, expected: ProbeModel, scope: V4Scope): VerifiedProbeFile = openVerified(
        sessionRoot, expected.filename, expected.byteCount, expected.sha256, scope)

    private fun openVerified(
        sessionRoot: File,
        filename: String,
        expectedBytes: Long,
        expectedSha256: String,
        scope: V4Scope,
    ): VerifiedProbeFile {
        require(filename.matches(Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,126}"))) {
            "Probe filename is invalid"
        }
        require(!filename.endsWith(".part")) { "Partial probe input is not allowed" }
        val canonicalRoot = sessionRoot.canonicalFile
        require(sessionRoot.absoluteFile == canonicalRoot) { "Probe session root must not be a symlink" }
        require(canonicalRoot.isDirectory) { "Probe session root does not exist" }
        require(canonicalRoot.listFiles()?.none { it.name.endsWith(".part") } == true) {
            "Probe session contains a partial file"
        }
        val requested = File(canonicalRoot, filename)
        val canonicalFile = requested.canonicalFile
        require(requested.absoluteFile == canonicalFile) { "Probe file must not be a symlink" }
        require(canonicalFile.parentFile == canonicalRoot) { "Probe file escapes the session root" }
        require(canonicalFile.isFile) { "Probe file is not a regular file" }
        require(canonicalFile.length() == expectedBytes) { "Probe file byte count mismatch" }
        val sha256 = sha256(canonicalFile)
        require(sha256 == expectedSha256) { "Probe file SHA-256 mismatch" }
        scope.mark("model_file_open", "start")
        val input = FileInputStream(canonicalFile)
        scope.mark("model_file_open", "finish")
        val mapped = input.channel.use { channel ->
            scope.mark("model_map", "start")
            val buffer = channel.map(FileChannel.MapMode.READ_ONLY, 0L, expectedBytes)
                .order(ByteOrder.nativeOrder())
                .asReadOnlyBuffer()
            scope.mark("model_map", "finish")
            buffer
        }
        return VerifiedProbeFile(canonicalFile, expectedBytes, sha256, mapped)
    }

    internal fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(1024 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}
