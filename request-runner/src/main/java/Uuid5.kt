package com.example.d1check.requestrunner

import java.nio.ByteBuffer
import java.security.MessageDigest
import java.util.UUID

/**
 * RFC 4122 버전 5 (SHA-1 이름 기반) UUID. Java 에는 v3 (nameUUIDFromBytes, MD5) 만 있어 직접 구현한다.
 * Python `uuid.uuid5(uuid.NAMESPACE_URL, name)` 과 같은 값이어야 한다 (K1 시험이 Python 생성값과 대조).
 * A24: tools/d1_sustained_plan.py 85~87행 — sid = uuid5(NAMESPACE_URL, NAME + '/' + i) · request_id = uuid5(NAMESPACE_URL, sid + '/' + ordinal)
 */
object Uuid5 {
    val NAMESPACE_URL: UUID = UUID.fromString("6ba7b811-9dad-11d1-80b4-00c04fd430c8")

    fun uuid5(namespace: UUID, name: String): UUID {
        val digest = MessageDigest.getInstance("SHA-1")
        digest.update(
            ByteBuffer.allocate(16)
                .putLong(namespace.mostSignificantBits)
                .putLong(namespace.leastSignificantBits)
                .array(),
        )
        digest.update(name.toByteArray(Charsets.UTF_8))
        val hash = digest.digest()
        hash[6] = ((hash[6].toInt() and 0x0f) or 0x50).toByte() // version 5
        hash[8] = ((hash[8].toInt() and 0x3f) or 0x80).toByte() // RFC 4122 variant
        val buffer = ByteBuffer.wrap(hash, 0, 16)
        return UUID(buffer.long, buffer.long)
    }

    fun isCanonical(text: String): Boolean =
        runCatching { UUID.fromString(text).toString() == text }.getOrDefault(false)
}
