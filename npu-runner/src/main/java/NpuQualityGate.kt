package com.example.d1check.npurunner

import kotlin.math.sqrt

/**
 * NPU 품질 동등성 게이트 (NPU_RUNNER_SPEC §6-3, 산공학회 CLAUDE.md §8).
 *
 * AOT 산출물은 FP32 입력이라도 가중치가 FP16 이라 benchmark-runner 의 수치 동등성
 * (atol=1e-4, rtol=1e-3)은 구조적으로 못 넘는다. 그래서 **결과를 보기 전에** 아래 셋으로 고정했다.
 *
 *   1. bit_identical_to_cpu == false   ← true 면 실패. NPU 가 아니라 CPU 로 돈 것이다
 *   2. argmax_agreement == n / n       (n = 32)
 *   3. cosine_min >= 0.99
 *
 * bit_identical_to_cpu 는 **보수적으로** 정의한다: n 개 중 하나라도 출력 전체가 비트 단위로
 * CPU 와 같으면 true. FP16 가중치로 1001 개 점수가 전부 같은 비트가 나올 수는 없다.
 *
 * argmax 동점 처리와 cosine 공식은 benchmark-runner OutputEquivalenceComparator 와 같다
 * (점수 내림차순, 동점이면 인덱스 오름차순 / double 누적 dot / (|ref| |cand|)).
 */
internal object NpuQualityGate {
    const val VERSION = "npu-quality-gate-v1"
    const val COSINE_MIN_THRESHOLD = 0.99
    const val CRITERIA =
        "bit_identical_to_cpu==false && argmax_agreement==n/n && cosine_min>=0.99"

    data class Sample(
        val index: Int,
        val referenceArgmax: Int,
        val candidateArgmax: Int,
        val cosine: Double?,
        val bitIdentical: Boolean,
    )

    data class Result(
        val samples: List<Sample>,
        val bitIdenticalCount: Int,
        val argmaxAgreement: Int,
        val cosineMin: Double?,
        val cosineMean: Double?,
    ) {
        val n: Int get() = samples.size
        val bitIdenticalToCpu: Boolean get() = bitIdenticalCount > 0
        val pass: Boolean
            get() = n > 0 && !bitIdenticalToCpu && argmaxAgreement == n &&
                cosineMin != null && cosineMin >= COSINE_MIN_THRESHOLD

        fun toJson(referenceModel: String, candidateModel: String): String {
            val sb = StringBuilder()
            sb.append("\"quality_gate\":{")
            sb.append("\"version\":\"$VERSION\",")
            sb.append("\"criteria\":\"$CRITERIA\",")
            sb.append("\"reference\":\"CPU:$referenceModel\",")
            sb.append("\"candidate\":\"$candidateModel\",")
            sb.append("\"n\":$n,")
            sb.append("\"bit_identical_count\":$bitIdenticalCount,")
            sb.append("\"bit_identical_to_cpu\":$bitIdenticalToCpu,")
            sb.append("\"argmax_agreement\":\"$argmaxAgreement/$n\",")
            sb.append("\"cosine_min\":${num(cosineMin)},")
            sb.append("\"cosine_mean\":${num(cosineMean)},")
            sb.append("\"verdict\":\"${if (pass) "PASS" else "FAIL"}\",")
            sb.append("\"per_sample\":[")
            samples.forEachIndexed { k, s ->
                if (k > 0) sb.append(",")
                sb.append("{\"i\":${s.index},\"ref_argmax\":${s.referenceArgmax},")
                sb.append("\"cand_argmax\":${s.candidateArgmax},\"cosine\":${num(s.cosine)},")
                sb.append("\"bit_identical\":${s.bitIdentical}}")
            }
            sb.append("]}")
            return sb.toString()
        }

        private fun num(v: Double?): String = v?.let { "%.8f".format(java.util.Locale.ROOT, it) } ?: "null"
    }

    fun evaluate(reference: List<FloatArray>, candidate: List<FloatArray>): Result {
        require(reference.size == candidate.size) { "sample count mismatch" }
        val samples = reference.indices.map { i ->
            val ref = reference[i]
            val cand = candidate[i]
            require(ref.size == cand.size) { "output element count mismatch at sample $i" }
            Sample(
                index = i,
                referenceArgmax = argmax(ref),
                candidateArgmax = argmax(cand),
                cosine = cosine(ref, cand),
                bitIdentical = bitIdentical(ref, cand),
            )
        }
        val cosines = samples.mapNotNull { it.cosine }
        return Result(
            samples = samples,
            bitIdenticalCount = samples.count { it.bitIdentical },
            argmaxAgreement = samples.count { it.referenceArgmax >= 0 && it.referenceArgmax == it.candidateArgmax },
            // 비유한 값이 하나라도 있으면 그 샘플의 cosine 은 null 이고, 그러면 min 도 null (= FAIL)
            cosineMin = if (cosines.size == samples.size) cosines.minOrNull() else null,
            cosineMean = if (cosines.size == samples.size) cosines.average() else null,
        )
    }

    /** 점수 내림차순, 동점이면 인덱스 오름차순의 첫 원소. 비유한 값이 있으면 -1. */
    fun argmax(v: FloatArray): Int {
        if (v.isEmpty() || v.any { !it.isFinite() }) return -1
        var best = 0
        for (i in 1 until v.size) if (v[i] > v[best]) best = i
        return best
    }

    fun cosine(a: FloatArray, b: FloatArray): Double? {
        var dot = 0.0
        var aa = 0.0
        var bb = 0.0
        for (i in a.indices) {
            val x = a[i].toDouble()
            val y = b[i].toDouble()
            if (!x.isFinite() || !y.isFinite()) return null
            dot += x * y
            aa += x * x
            bb += y * y
        }
        val d = sqrt(aa) * sqrt(bb)
        return if (d > 0.0) dot / d else null
    }

    fun bitIdentical(a: FloatArray, b: FloatArray): Boolean {
        if (a.size != b.size) return false
        for (i in a.indices) if (a[i].toRawBits() != b[i].toRawBits()) return false
        return true
    }
}
