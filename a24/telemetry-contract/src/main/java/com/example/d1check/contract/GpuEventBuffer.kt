package com.example.d1check.contract

internal data class BufferedGpuRecord(
    val event: String,
    val phase: String,
    val status: String,
    val startNs: Long,
    val endNs: Long,
    val index: Long,
    val batchSize: Int,
    val detail: String?,
)

/** Primitive arrays keep per-inference recording bounded and allocation-free. */
internal class GpuEventBuffer(
    private val maxInferenceSpans: Int,
    private val maxLifecycleEvents: Int,
) {
    private val starts = LongArray(maxInferenceSpans)
    private val ends = LongArray(maxInferenceSpans)
    private val indexes = LongArray(maxInferenceSpans)
    private val batchSizes = IntArray(maxInferenceSpans)
    private val lifecycle = ArrayList<BufferedGpuRecord>(32)

    var inferenceCount: Int = 0
        private set

    val hasInferenceCapacity: Boolean get() = inferenceCount < maxInferenceSpans

    fun recordInference(startNs: Long, endNs: Long, index: Long, batchSize: Int): Boolean {
        if (!hasInferenceCapacity) return false
        val position = inferenceCount
        starts[position] = startNs
        ends[position] = endNs
        indexes[position] = index
        batchSizes[position] = batchSize
        inferenceCount = position + 1
        return true
    }

    fun recordLifecycle(record: BufferedGpuRecord) {
        check(lifecycle.size < maxLifecycleEvents) { "lifecycle_event_limit" }
        lifecycle += record
    }

    val lifecycleCount: Int get() = lifecycle.size

    fun lifecycleRecordsAfterRun(): List<BufferedGpuRecord> =
        lifecycle.sortedWith(compareBy<BufferedGpuRecord> { it.startNs }.thenBy { it.endNs })

    fun inferenceStartAt(position: Int): Long = starts[position]
    fun inferenceEndAt(position: Int): Long = ends[position]
    fun inferenceIndexAt(position: Int): Long = indexes[position]
    fun inferenceBatchSizeAt(position: Int): Int = batchSizes[position]
}
