package com.example.d1check.benchmarkrunner

import org.junit.Assert.assertFalse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class OutputEquivalenceComparatorTest {
    private val tensor = TensorDescription(listOf(1, 6), "FLOAT32")
    private val tolerance = ComparatorTolerance(1e-4, 1e-3, 1e-6)

    private fun decision(
        reference: FloatArray,
        candidate: FloatArray,
        count: Int = 32,
        candidateTensor: TensorDescription = tensor,
        delegated: Boolean = true,
        usedTolerance: ComparatorTolerance = tolerance,
    ) = OutputEquivalenceComparator.evaluate(
        references = List(count) { reference.copyOf() },
        candidates = List(count) { candidate.copyOf() },
        referenceTensor = tensor,
        candidateTensor = candidateTensor,
        tolerance = usedTolerance,
        fullDelegationVerified = delegated,
    )

    @Test
    fun identicalOutputPassesAtThirtyTwoInputs() {
        assertTrue(decision(floatArrayOf(0f, 1f, 2f, 3f, 4f, 5f),
            floatArrayOf(0f, 1f, 2f, 3f, 4f, 5f)).executionIntegrityPassed)
    }

    @Test
    fun combinedToleranceBoundaryIsInclusiveAndExcessFails() {
        val reference = floatArrayOf(1f, 0f, 0f, 0f, 0f, 0f)
        val exactTolerance = ComparatorTolerance(0.125, 0.0, 1e-6)
        val atBoundary = reference.copyOf().also { it[0] = 1.125f }
        val beyond = reference.copyOf().also { it[0] = 1.126f }
        assertEquals(
            "within",
            decision(reference, atBoundary, usedTolerance = exactTolerance).numericalToleranceResult,
        )
        val outside = decision(reference, beyond, usedTolerance = exactTolerance)
        assertTrue(outside.executionIntegrityPassed)
        assertEquals("outside", outside.numericalToleranceResult)
    }

    @Test
    fun nanAndInfinityFail() {
        val reference = floatArrayOf(0f, 1f, 2f, 3f, 4f, 5f)
        for (bad in listOf(Float.NaN, Float.POSITIVE_INFINITY)) {
            val candidate = reference.copyOf().also { it[0] = bad }
            assertFalse(decision(reference, candidate).executionIntegrityPassed)
            assertTrue(decision(reference, candidate).failureReasons.contains("non_finite_output"))
        }
    }

    @Test
    fun shapeAndDtypeMismatchFailImmediately() {
        val values = floatArrayOf(0f, 1f, 2f, 3f, 4f, 5f)
        assertTrue(decision(values, values, candidateTensor =
            TensorDescription(listOf(1, 3, 2), "FLOAT32")).failureReasons
            .contains("output_shape_mismatch"))
        assertTrue(decision(values, values, candidateTensor =
            TensorDescription(listOf(1, 6), "UINT8")).failureReasons
            .contains("output_dtype_mismatch"))
    }

    @Test
    fun argmaxMismatchIsRecordedWithoutCorruptingSyntheticIntegrity() {
        val reference = floatArrayOf(0f, 1.00000f, 0.99995f, 0f, 0f, 0f)
        val candidate = floatArrayOf(0f, 0.99995f, 1.00000f, 0f, 0f, 0f)
        val result = decision(reference, candidate)
        assertTrue(result.aggregate.mismatchCount == 0L)
        assertTrue(result.executionIntegrityPassed)
        assertEquals(32, result.aggregate.argmaxMismatchCount)
    }

    @Test
    fun oneElementBeyondToleranceIsDiagnosticOutside() {
        val reference = floatArrayOf(0f, 1f, 2f, 3f, 4f, 5f)
        val candidate = reference.copyOf().also { it[2] += 0.1f }
        val result = decision(reference, candidate)
        assertTrue(result.executionIntegrityPassed)
        assertEquals("outside", result.numericalToleranceResult)
        assertTrue(result.aggregate.mismatchCount == 32L)
    }

    @Test
    fun thirtyOneInputsFailAndThirtyTwoSatisfyMinimum() {
        val values = floatArrayOf(0f, 1f, 2f, 3f, 4f, 5f)
        assertTrue(decision(values, values, count = 31).failureReasons
            .contains("insufficient_input_count"))
        assertTrue(decision(values, values, count = 32).executionIntegrityPassed)
    }

    @Test
    fun partialFallbackOrUnverifiedDelegationFails() {
        val values = floatArrayOf(0f, 1f, 2f, 3f, 4f, 5f)
        val result = decision(values, values, delegated = false)
        assertFalse(result.executionIntegrityPassed)
        assertTrue(result.failureReasons.contains("gpu_full_delegation_unverified"))
    }

    @Test
    fun deterministicTieBreakAndRepresentativeMetricsAreComputed() {
        val reference = floatArrayOf(0.1f, 0.4f, 0.4f, 0.05f, 0.03f, 0.02f)
        val candidate = floatArrayOf(0.1f, 0.39f, 0.41f, 0.05f, 0.03f, 0.02f)
        val comparison = OutputEquivalenceComparator.compare(0, reference, candidate, tolerance)
        assertEquals(listOf(1, 2, 0, 3, 4), comparison.referenceTop5)
        assertEquals(listOf(2, 1, 0, 3, 4), comparison.candidateTop5)
        assertTrue(comparison.top5SetMatches)
        assertFalse(comparison.orderedTop5Matches)
        assertEquals(0.01, comparison.totalVariationDistance!!, 1e-6)
        assertTrue(comparison.cosineSimilarity!! > 0.999)
    }

    @Test
    fun taskAccuracyAndDeltaAreSeparateFromEquivalence() {
        val first = OutputEquivalenceComparator.compare(
            0, floatArrayOf(0f, 0.8f, 0.2f, 0f, 0f, 0f),
            floatArrayOf(0f, 0.7f, 0.3f, 0f, 0f, 0f), tolerance,
        )
        val second = OutputEquivalenceComparator.compare(
            1, floatArrayOf(0f, 0.8f, 0.2f, 0f, 0f, 0f),
            floatArrayOf(0f, 0.2f, 0.8f, 0f, 0f, 0f), tolerance,
        )
        val metrics = OutputEquivalenceComparator.taskAccuracy(listOf(first, second), listOf(1, 1))
        assertEquals(1.0, metrics.referenceTop1Accuracy, 0.0)
        assertEquals(0.5, metrics.candidateTop1Accuracy, 0.0)
        assertEquals(-0.5, metrics.top1AccuracyDelta, 0.0)
    }

    @Test
    fun allZeroOrUnderflowTailMakesTop5OverlapNotApplicable() {
        val allZero = OutputEquivalenceComparator.compare(
            0, FloatArray(8), FloatArray(8), tolerance,
        )
        assertFalse(allZero.top5OverlapApplicable)
        assertEquals(
            "reference_and_candidate_top5_boundary_tie",
            allZero.top5OverlapNotApplicableReason,
        )
        val tail = floatArrayOf(0.7f, 0.2f, 0.1f, 0f, 0f, 0f, 0f, 0f)
        val underflowTail = decision(tail, tail)
        assertEquals(0, underflowTail.aggregate.top5OverlapApplicableCount)
        assertEquals(32, underflowTail.aggregate.top5OverlapNotApplicableCount)
        assertEquals(null, underflowTail.aggregate.minimumTop5OverlapCount)
    }

    @Test
    fun exactBoundaryTieIsExcludedButDeterminateOverlapIsRetained() {
        val tied = OutputEquivalenceComparator.compare(
            0,
            floatArrayOf(0.6f, 0.2f, 0.1f, 0.05f, 0.025f, 0.025f),
            floatArrayOf(0.6f, 0.2f, 0.1f, 0.05f, 0.03f, 0.02f),
            tolerance,
        )
        assertFalse(tied.top5OverlapApplicable)
        assertEquals("reference_top5_boundary_tie", tied.top5OverlapNotApplicableReason)

        val determinate = decision(
            floatArrayOf(0.60f, 0.15f, 0.10f, 0.07f, 0.05f, 0.03f, 0.0f),
            floatArrayOf(0.60f, 0.15f, 0.10f, 0.0f, 0.03f, 0.05f, 0.07f),
        )
        assertEquals(3, determinate.aggregate.minimumTop5OverlapCount)
        assertEquals(32, determinate.aggregate.top5OverlapApplicableCount)
    }
}
