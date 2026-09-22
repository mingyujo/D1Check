package com.example.d1check.benchmarkrunner

/** Online, non-preemptive choice. Only already enqueued tickets enter this function. */
internal object ArrivalPolicy {
    const val FIFO = "CPU_FIFO"
    const val URGENT = "CPU_URGENT"
    const val CONDITIONAL = "CONDITIONAL"
    const val FIXED = "FIXED_SPLIT"

    data class Ticket(val id: String, val task: String, val priority: String, val ordinal: Int)
    data class Choice(val ticket: Ticket, val backend: String, val reason: String)

    fun choose(
        policy: String,
        waiting: List<Ticket>,
        freeCpu: Boolean,
        freeGpu: Boolean,
        cpuRemainingMs: Long,
        estimates: Map<String, Long>,
    ): Choice? {
        require(policy in setOf(FIFO, URGENT, CONDITIONAL, FIXED))
        if (waiting.isEmpty()) return null
        val ordered = if (policy == FIFO) waiting.sortedWith(compareBy<Ticket> { it.ordinal }.thenBy { it.id })
            else waiting.sortedWith(compareBy<Ticket> { it.priority != "urgent" }.thenBy { it.ordinal }.thenBy { it.id })
        for ((position, ticket) in ordered.withIndex()) {
            if (policy == FIFO || policy == URGENT) {
                if (freeCpu) return Choice(ticket, "CPU", "serial_${policy.lowercase()}")
                return null
            }
            if (policy == FIXED) {
                val lane = if (ticket.priority == "urgent") "CPU" else "GPU"
                if ((lane == "CPU" && freeCpu) || (lane == "GPU" && freeGpu))
                    return Choice(ticket, lane, "fixed_priority_split")
                continue
            }
            val cpuMs = estimates.getValue("${ticket.task}_CPU")
            val gpuMs = estimates.getValue("${ticket.task}_GPU")
            require(cpuMs > 0 && gpuMs > 0 && cpuRemainingMs >= 0)
            // The queued work ahead is visible now; no future arrival or measured outcome is read.
            val aheadMs = ordered.take(position).sumOf { estimates.getValue("${it.task}_CPU") }
            val predictedCpuMs = (if (freeCpu) 0 else cpuRemainingMs) + aheadMs + cpuMs
            if (freeCpu && (!freeGpu || predictedCpuMs <= gpuMs))
                return Choice(ticket, "CPU", "estimated_cpu_finish")
            if (freeGpu && gpuMs < predictedCpuMs)
                return Choice(ticket, "GPU", "estimated_gpu_finish")
        }
        return null
    }
}
