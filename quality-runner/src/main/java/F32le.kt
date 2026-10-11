package com.example.d1check.qualityrunner

import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * little-endian float32 ↔ 바이트. 입력 (등록 §1: LE float32 NHWC, 602,112 B) 은 바이트를 그대로 FloatArray 로 보고 텐서에 쓴다 —
 * resize · 정규화 · 변환 없음. 출력 (Softmax 1000 float32) 은 readFloat() 의 FloatArray 를 LE 바이트로 그대로 적는다 (호스트 판정기가 읽는다).
 */
object F32le {
    fun toFloats(bytes: ByteArray, expectedElements: Int): FloatArray {
        require(bytes.size == expectedElements * 4) { "f32le size ${bytes.size} != ${expectedElements * 4}" }
        val out = FloatArray(expectedElements)
        ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(out)
        return out
    }

    fun toBytes(values: FloatArray): ByteArray {
        val buffer = ByteBuffer.allocate(values.size * 4).order(ByteOrder.LITTLE_ENDIAN)
        buffer.asFloatBuffer().put(values)
        return buffer.array()
    }
}
