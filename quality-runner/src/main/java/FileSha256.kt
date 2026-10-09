package com.example.d1check.qualityrunner

import java.io.File
import java.security.MessageDigest

/** ★ 사본 — request-runner Runtimes.kt TaskRuntime.companion.sha256(File) (blob 7f9ba0a7…) 과 같은 코드. 바이트 배열 판을 더했다. */
object FileSha256 {
    fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(1 shl 16)
            while (true) {
                val n = input.read(buffer)
                if (n < 0) break
                digest.update(buffer, 0, n)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    fun sha256(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
}
