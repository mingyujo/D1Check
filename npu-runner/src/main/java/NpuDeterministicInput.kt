package com.example.d1check.npurunner

import java.security.MessageDigest

/**
 * benchmark-runner 의 `DeterministicInputSet` 과 **비트 단위로 같은** 합성 입력을 만든다.
 *
 * 원본: benchmark-runner/src/main/java/com/example/d1check/benchmarkrunner/DeterministicInputSet.kt
 *   state = state * 1664525 + 1013904223          (Int 오버플로 wrap)
 *   value = ((state ushr 8) and 0xFFFFFF) / 16777215.0f
 *   seed  = 0x12345678
 *
 * 값이 같아야 CPU(Interpreter) 출력과 NPU(CompiledModel) 출력을 직접 대조할 수 있다.
 * 원본을 import 하지 않고 복사한 이유: 모듈 의존을 만들면 benchmark-runner 의 LiteRT 1.4.2 가
 * npu-runner 의 LiteRT Next 와 같은 classpath 에 올라와 충돌한다 (SPEC §7).
 */
internal object NpuDeterministicInput {
    const val VERSION = "lcg-float32-unit-v1"
    const val DEFAULT_SEED = 0x12345678L
    const val NORMALIZATION = "synthetic_[0,1]_float32_no_additional_normalization"

    /** MobileNet V1 1.0 224: [1,224,224,3] */
    const val DEFAULT_ELEMENT_COUNT = 1 * 224 * 224 * 3

    fun floats(elementCount: Int, seed: Long = DEFAULT_SEED): FloatArray {
        require(elementCount > 0)
        var state = seed.toInt()
        val out = FloatArray(elementCount)
        for (i in 0 until elementCount) {
            state = state * 1664525 + 1013904223
            out[i] = ((state ushr 8) and 0xFFFFFF) / 16777215.0f
        }
        return out
    }

    /**
     * 품질 게이트용 n 개 입력. benchmark-runner AccuracyPreflightEngine 과 같이
     * **하나의 LCG 스트림을 이어서** n 개 텐서로 자른다 (`generator(seed, bytes).next()` × n).
     * 따라서 0 번 원소는 floats(elementCount, seed) 와 비트 단위로 같다.
     */
    fun floatSet(count: Int, elementCount: Int, seed: Long = DEFAULT_SEED): List<FloatArray> {
        require(count > 0 && elementCount > 0)
        var state = seed.toInt()
        return List(count) {
            FloatArray(elementCount) {
                state = state * 1664525 + 1013904223
                ((state ushr 8) and 0xFFFFFF) / 16777215.0f
            }
        }
    }

    /**
     * uint8 입력 모델(INT8 컴파일 산출물)용. **스모크 전용**이다.
     * 실제 정확도 평가는 대표 텐서셋을 입력 scale/zero_point 로 양자화해야 한다
     * (NEXT_3WEEKS §3.4 3번 항목). 여기서는 배선 확인만 한다.
     */
    fun uint8Bytes(elementCount: Int, seed: Long = DEFAULT_SEED): ByteArray {
        val f = floats(elementCount, seed)
        val out = ByteArray(elementCount)
        for (i in f.indices) {
            out[i] = (Math.round(f[i] * 255.0f).coerceIn(0, 255)).toByte()
        }
        return out
    }

    fun sha256(values: FloatArray): String {
        val digest = MessageDigest.getInstance("SHA-256")
        val buf = java.nio.ByteBuffer.allocate(4)
        for (v in values) {
            buf.clear()
            buf.putFloat(v)
            digest.update(buf.array())
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    fun sha256(values: ByteArray): String {
        val digest = MessageDigest.getInstance("SHA-256")
        digest.update(values)
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}
