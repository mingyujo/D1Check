package com.example.d1check.benchmarkrunner

import kotlin.math.abs
import kotlin.math.max
import kotlin.math.sqrt

internal data class ComparatorTolerance(
    val atol: Double,
    val rtol: Double,
    val relativeErrorEpsilon: Double,
) {
    init {
        require(atol.isFinite() && atol >= 0.0)
        require(rtol.isFinite() && rtol >= 0.0)
        require(relativeErrorEpsilon.isFinite() && relativeErrorEpsilon > 0.0)
    }
}

internal data class TensorDescription(val shape: List<Int>, val dtype: String)

internal data class InputComparison(
    val index: Int,
    val outputElementCount: Int,
    val maxAbsoluteError: Double,
    val maxAbsoluteErrorIndex: Int?,
    val maxAbsoluteErrorReference: Double?,
    val maxAbsoluteErrorCandidate: Double?,
    val maxAbsoluteErrorThreshold: Double?,
    val meanAbsoluteError: Double,
    val rmse: Double,
    val maxRelativeError: Double,
    val mismatchCount: Int,
    val nonFiniteCount: Int,
    val referenceMinimum: Double?,
    val referenceMaximum: Double?,
    val referenceSum: Double?,
    val candidateMinimum: Double?,
    val candidateMaximum: Double?,
    val candidateSum: Double?,
    val cosineSimilarity: Double?,
    val totalVariationDistance: Double?,
    val referenceArgmax: Int?,
    val candidateArgmax: Int?,
    val argmaxMatches: Boolean,
    val referenceTop5: List<Int>,
    val candidateTop5: List<Int>,
    val top5OverlapCount: Int,
    val top5OverlapApplicable: Boolean,
    val top5OverlapNotApplicableReason: String?,
    val top5SetMatches: Boolean,
    val orderedTop5Matches: Boolean,
    val referenceTop1Margin: Double?,
    val candidateTop1Margin: Double?,
    val referenceTop5BoundaryMargin: Double?,
    val candidateTop5BoundaryMargin: Double?,
)

internal data class AggregateComparison(
    val outputElementCount: Long,
    val maxAbsoluteError: Double,
    val meanAbsoluteError: Double,
    val rmse: Double,
    val maxRelativeError: Double,
    val mismatchCount: Long,
    val nonFiniteCount: Long,
    val argmaxMatchCount: Int,
    val argmaxMismatchCount: Int,
    val top5SetMatchCount: Int,
    val orderedTop5MatchCount: Int,
    val minimumTop5OverlapCount: Int?,
    val top5OverlapApplicableCount: Int,
    val top5OverlapNotApplicableCount: Int,
    val meanCosineSimilarity: Double?,
    val minimumCosineSimilarity: Double?,
    val meanTotalVariationDistance: Double?,
    val maximumTotalVariationDistance: Double?,
    val referenceProbabilitySumMinimum: Double?,
    val referenceProbabilitySumMaximum: Double?,
    val candidateProbabilitySumMinimum: Double?,
    val candidateProbabilitySumMaximum: Double?,
)

internal data class EquivalenceDecision(
    val executionIntegrityPassed: Boolean,
    val numericalToleranceResult: String,
    val failureReasons: List<String>,
    val perInput: List<InputComparison>,
    val aggregate: AggregateComparison,
) {
    @Deprecated("Use executionIntegrityPassed; tolerance is diagnostic")
    val passed: Boolean get() = executionIntegrityPassed
}

internal data class TaskAccuracyMetrics(
    val labeledInputCount: Int,
    val referenceTop1CorrectCount: Int,
    val candidateTop1CorrectCount: Int,
    val referenceTop5CorrectCount: Int,
    val candidateTop5CorrectCount: Int,
    val referenceTop1Accuracy: Double,
    val candidateTop1Accuracy: Double,
    val referenceTop5Accuracy: Double,
    val candidateTop5Accuracy: Double,
    val top1AccuracyDelta: Double,
    val top5AccuracyDelta: Double,
)

internal object OutputEquivalenceComparator {
    const val VERSION = "output-equivalence-v3"
    const val TIE_BREAK_RULE = "score_descending_then_index_ascending"

    fun evaluate(
        references: List<FloatArray>,
        candidates: List<FloatArray>,
        referenceTensor: TensorDescription,
        candidateTensor: TensorDescription,
        tolerance: ComparatorTolerance,
        fullDelegationVerified: Boolean,
        minimumInputCount: Int = 32,
    ): EquivalenceDecision {
        val failures = mutableListOf<String>()
        if (referenceTensor.shape != candidateTensor.shape) failures += "output_shape_mismatch"
        if (referenceTensor.dtype != candidateTensor.dtype) failures += "output_dtype_mismatch"
        if (references.size != candidates.size) failures += "output_input_count_mismatch"
        if (references.size == candidates.size && references.indices.any {
                references[it].size != candidates[it].size
            }) failures += "output_element_count_mismatch"
        if (references.size < minimumInputCount) failures += "insufficient_input_count"
        if (!fullDelegationVerified) failures += "gpu_full_delegation_unverified"
        if (failures.any { it in setOf(
                "output_shape_mismatch", "output_dtype_mismatch", "output_input_count_mismatch",
                "output_element_count_mismatch",
            ) }) {
            return EquivalenceDecision(false, "not_evaluated", failures, emptyList(), emptyAggregate())
        }

        val perInput = references.indices.map { index ->
            compare(index, references[index], candidates[index], tolerance)
        }
        val aggregate = aggregate(perInput)
        if (aggregate.nonFiniteCount > 0) failures += "non_finite_output"
        return EquivalenceDecision(
            executionIntegrityPassed = failures.isEmpty(),
            numericalToleranceResult = if (aggregate.mismatchCount == 0L) "within" else "outside",
            failureReasons = failures.distinct(),
            perInput = perInput,
            aggregate = aggregate,
        )
    }

    fun compare(index: Int, reference: FloatArray, candidate: FloatArray, tolerance: ComparatorTolerance): InputComparison {
        require(reference.size == candidate.size) { "output element count mismatch" }
        var maxAbsolute = 0.0
        var maxAbsoluteIndex: Int? = null
        var maxReference: Double? = null
        var maxCandidate: Double? = null
        var maxThreshold: Double? = null
        var absoluteSum = 0.0
        var squaredSum = 0.0
        var maxRelative = 0.0
        var mismatchCount = 0
        var nonFiniteCount = 0
        var dot = 0.0
        var referenceSquared = 0.0
        var candidateSquared = 0.0
        for (position in reference.indices) {
            val referenceValue = reference[position].toDouble()
            val candidateValue = candidate[position].toDouble()
            if (!referenceValue.isFinite() || !candidateValue.isFinite()) {
                nonFiniteCount++
                mismatchCount++
                continue
            }
            val absoluteError = abs(candidateValue - referenceValue)
            val threshold = tolerance.atol + tolerance.rtol * abs(referenceValue)
            val relativeError = absoluteError / max(abs(referenceValue), tolerance.relativeErrorEpsilon)
            if (maxAbsoluteIndex == null || absoluteError > maxAbsolute) {
                maxAbsolute = absoluteError
                maxAbsoluteIndex = position
                maxReference = referenceValue
                maxCandidate = candidateValue
                maxThreshold = threshold
            }
            absoluteSum += absoluteError
            squaredSum += absoluteError * absoluteError
            maxRelative = max(maxRelative, relativeError)
            dot += referenceValue * candidateValue
            referenceSquared += referenceValue * referenceValue
            candidateSquared += candidateValue * candidateValue
            if (absoluteError > threshold) mismatchCount++
        }
        val finiteCount = reference.size - nonFiniteCount
        val referenceTop6 = topK(reference, 6)
        val candidateTop6 = topK(candidate, 6)
        val referenceTop5 = referenceTop6.take(5)
        val candidateTop5 = candidateTop6.take(5)
        val referenceArgmax = referenceTop5.firstOrNull()
        val candidateArgmax = candidateTop5.firstOrNull()
        val referenceBoundaryTie = boundaryTie(reference, referenceTop6)
        val candidateBoundaryTie = boundaryTie(candidate, candidateTop6)
        val overlapApplicable = !referenceBoundaryTie && !candidateBoundaryTie &&
            referenceTop5.size == 5 && candidateTop5.size == 5
        val overlapReason = when {
            referenceBoundaryTie && candidateBoundaryTie ->
                "reference_and_candidate_top5_boundary_tie"
            referenceBoundaryTie -> "reference_top5_boundary_tie"
            candidateBoundaryTie -> "candidate_top5_boundary_tie"
            referenceTop5.size != 5 || candidateTop5.size != 5 ->
                "top5_ranking_unavailable"
            else -> null
        }
        val denominator = sqrt(referenceSquared) * sqrt(candidateSquared)
        return InputComparison(
            index, reference.size, maxAbsolute, maxAbsoluteIndex, maxReference, maxCandidate,
            maxThreshold, if (finiteCount > 0) absoluteSum / finiteCount else 0.0,
            if (finiteCount > 0) sqrt(squaredSum / finiteCount) else 0.0, maxRelative,
            mismatchCount, nonFiniteCount, finiteStatistic(reference, true),
            finiteStatistic(reference, false), finiteSum(reference), finiteStatistic(candidate, true),
            finiteStatistic(candidate, false), finiteSum(candidate),
            if (nonFiniteCount == 0 && denominator > 0.0) dot / denominator else null,
            if (nonFiniteCount == 0) absoluteSum / 2.0 else null,
            referenceArgmax, candidateArgmax,
            referenceArgmax != null && referenceArgmax == candidateArgmax,
            referenceTop5, candidateTop5,
            referenceTop5.intersect(candidateTop5.toSet()).size,
            overlapApplicable, overlapReason,
            referenceTop5.size == 5 && referenceTop5.toSet() == candidateTop5.toSet(),
            referenceTop5.size == 5 && referenceTop5 == candidateTop5,
            margin(reference, referenceTop6, 0, 1), margin(candidate, candidateTop6, 0, 1),
            margin(reference, referenceTop6, 4, 5), margin(candidate, candidateTop6, 4, 5),
        )
    }

    fun topK(values: FloatArray, count: Int): List<Int> {
        if (values.size < count || values.any { !it.isFinite() }) return emptyList()
        return values.indices.sortedWith(compareByDescending<Int> { values[it] }.thenBy { it }).take(count)
    }

    fun taskAccuracy(comparisons: List<InputComparison>, groundTruthOutputIndexes: List<Int>): TaskAccuracyMetrics {
        require(comparisons.size == groundTruthOutputIndexes.size) { "ground-truth count mismatch" }
        require(groundTruthOutputIndexes.all { it in 1..1000 }) {
            "ground-truth indexes must reserve output 0 for background"
        }
        val referenceTop1 = comparisons.indices.count { comparisons[it].referenceArgmax == groundTruthOutputIndexes[it] }
        val candidateTop1 = comparisons.indices.count { comparisons[it].candidateArgmax == groundTruthOutputIndexes[it] }
        val referenceTop5 = comparisons.indices.count { groundTruthOutputIndexes[it] in comparisons[it].referenceTop5 }
        val candidateTop5 = comparisons.indices.count { groundTruthOutputIndexes[it] in comparisons[it].candidateTop5 }
        val count = comparisons.size
        fun rate(correct: Int) = if (count == 0) 0.0 else correct.toDouble() / count
        return TaskAccuracyMetrics(
            count, referenceTop1, candidateTop1, referenceTop5, candidateTop5,
            rate(referenceTop1), rate(candidateTop1), rate(referenceTop5), rate(candidateTop5),
            rate(candidateTop1) - rate(referenceTop1), rate(candidateTop5) - rate(referenceTop5),
        )
    }

    private fun aggregate(values: List<InputComparison>): AggregateComparison {
        if (values.isEmpty()) return emptyAggregate()
        val elementCount = values.sumOf { it.outputElementCount.toLong() }
        val finiteCount = values.sumOf { it.outputElementCount - it.nonFiniteCount }.toLong()
        val absoluteSum = values.sumOf { it.meanAbsoluteError * (it.outputElementCount - it.nonFiniteCount) }
        val squaredSum = values.sumOf { it.rmse * it.rmse * (it.outputElementCount - it.nonFiniteCount) }
        val cosine = values.mapNotNull { it.cosineSimilarity }
        val tv = values.mapNotNull { it.totalVariationDistance }
        val referenceSums = values.mapNotNull { it.referenceSum }
        val candidateSums = values.mapNotNull { it.candidateSum }
        val applicableOverlap = values.filter { it.top5OverlapApplicable }
        return AggregateComparison(
            elementCount, values.maxOf { it.maxAbsoluteError },
            if (finiteCount > 0) absoluteSum / finiteCount else 0.0,
            if (finiteCount > 0) sqrt(squaredSum / finiteCount) else 0.0,
            values.maxOf { it.maxRelativeError }, values.sumOf { it.mismatchCount.toLong() },
            values.sumOf { it.nonFiniteCount.toLong() }, values.count { it.argmaxMatches },
            values.count { !it.argmaxMatches }, values.count { it.top5SetMatches },
            values.count { it.orderedTop5Matches },
            applicableOverlap.minOfOrNull { it.top5OverlapCount },
            applicableOverlap.size, values.size - applicableOverlap.size,
            cosine.takeIf { it.isNotEmpty() }?.average(), cosine.minOrNull(),
            tv.takeIf { it.isNotEmpty() }?.average(), tv.maxOrNull(), referenceSums.minOrNull(),
            referenceSums.maxOrNull(), candidateSums.minOrNull(), candidateSums.maxOrNull(),
        )
    }

    private fun finiteStatistic(values: FloatArray, minimum: Boolean): Double? {
        if (values.any { !it.isFinite() }) return null
        return if (minimum) values.minOrNull()?.toDouble() else values.maxOrNull()?.toDouble()
    }

    private fun finiteSum(values: FloatArray): Double? =
        if (values.any { !it.isFinite() }) null else values.sumOf { it.toDouble() }

    private fun margin(values: FloatArray, ranking: List<Int>, first: Int, second: Int): Double? =
        if (ranking.size > second) values[ranking[first]].toDouble() - values[ranking[second]].toDouble() else null

    private fun boundaryTie(values: FloatArray, ranking: List<Int>): Boolean =
        ranking.size >= 6 && values[ranking[4]] == values[ranking[5]]

    private fun emptyAggregate() = AggregateComparison(
        0, 0.0, 0.0, 0.0, 0.0, 0, 0, 0, 0, 0, 0,
        null, 0, 0, null, null, null, null, null, null, null, null,
    )
}
