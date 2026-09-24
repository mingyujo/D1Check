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
     * 모델별 입력 규칙. `--es input_spec <wireName>` 으로 고른다.
     *
     * **기본값 LCG_UNIT 은 바꾸지 말 것** — 9/24 G4 품질 게이트(MobileNet V1)가 이 입력으로 잰 것이다
     * (`input_sha256 5dc1cb09…`, NpuDeterministicInputTest 가 고정).
     *
     * 정규화 값은 조민규 `model-probe-v1` 계약(MODEL_02_INVENTORY §4)을 그대로 따른다:
     *   EfficientNet-Lite0 `(RGB - 127.0) / 128.0`, [1,224,224,3]
     *   EfficientDet-Lite0 `(RGB - 127.5) / 127.5`, [1,320,320,3]
     *
     * - LCG_RGB_*   : 같은 LCG 스트림의 상위 8 bit 를 RGB 바이트(0..255)로 쓰고 정규화. 품질 게이트 n=32 용
     * - COORD_RGB_* : 조민규 ProbeRawAdapter.deterministicInput 의 `coordinate-rgb-v1` 과 같은 공식.
     *                 표본 i 에 seed i 를 쓰고, 그쪽 계약대로 seed 는 0..2 만 허용 (n ≤ 3)
     */
    enum class InputSpec(
        val wireName: String,
        val generator: String,
        val normalization: String,
        val defaultElements: Int,
    ) {
        LCG_UNIT("lcg-unit", VERSION, NORMALIZATION, DEFAULT_ELEMENT_COUNT),
        LCG_RGB_127_128("lcg-rgb-127-128", "lcg-rgb-u8-v1", "(RGB-127.0)/128.0", 224 * 224 * 3),
        LCG_RGB_1275_1275("lcg-rgb-127.5-127.5", "lcg-rgb-u8-v1", "(RGB-127.5)/127.5", 320 * 320 * 3),
        COORD_RGB_CLASSIFICATION(
            "coordinate-rgb-classification", "coordinate-rgb-v1", "(RGB-127.0)/128.0", 224 * 224 * 3,
        ),
        COORD_RGB_DETECTION(
            "coordinate-rgb-detection", "coordinate-rgb-v1", "(RGB-127.5)/127.5", 320 * 320 * 3,
        ),
        ;

        companion object {
            fun fromWire(name: String?): InputSpec? =
                if (name == null) LCG_UNIT else entries.firstOrNull { it.wireName == name }
        }
    }

    /** spec 에 맞는 입력 n 개. LCG_UNIT 은 floatSet 과 같다 (0 번 = floats). */
    fun inputSet(spec: InputSpec, count: Int, elementCount: Int, seed: Long = DEFAULT_SEED): List<FloatArray> {
        require(count > 0 && elementCount > 0)
        return when (spec) {
            InputSpec.LCG_UNIT -> floatSet(count, elementCount, seed)
            InputSpec.LCG_RGB_127_128 -> lcgRgb(count, elementCount, seed, 127.0f, 128.0f)
            InputSpec.LCG_RGB_1275_1275 -> lcgRgb(count, elementCount, seed, 127.5f, 127.5f)
            InputSpec.COORD_RGB_CLASSIFICATION -> coordinateRgb(count, elementCount, 224, 127.0f, 128.0f)
            InputSpec.COORD_RGB_DETECTION -> coordinateRgb(count, elementCount, 320, 127.5f, 127.5f)
        }
    }

    private fun lcgRgb(count: Int, elementCount: Int, seed: Long, center: Float, scale: Float): List<FloatArray> {
        var state = seed.toInt()
        return List(count) {
            FloatArray(elementCount) {
                state = state * 1664525 + 1013904223
                (((state ushr 24) and 0xFF) - center) / scale
            }
        }
    }

    private fun coordinateRgb(count: Int, elementCount: Int, size: Int, center: Float, scale: Float): List<FloatArray> {
        require(count <= 3) { "coordinate-rgb-v1 allows seed 0..2 only (n <= 3), got n=$count" }
        require(elementCount == size * size * 3) {
            "coordinate-rgb-v1 needs ${size}x${size}x3 = ${size * size * 3} elements, model has $elementCount"
        }
        return List(count) { seed ->
            val out = FloatArray(elementCount)
            var k = 0
            for (y in 0 until size) {
                for (x in 0 until size) {
                    out[k++] = (((3 * x + 5 * y + 17 + 29 * seed) and 0xff) - center) / scale
                    out[k++] = (((11 * x + 7 * y + 29 + 31 * seed) and 0xff) - center) / scale
                    out[k++] = (((13 * x + 19 * y + 43 + 37 * seed) and 0xff) - center) / scale
                }
            }
            out
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
