package com.example.d1check.benchmarkrunner

/** Diagnostic replay of a recorded PC dispatch plan, not an online scheduling policy. */
internal object ArrivalRecordedReplay {
    const val POLICY = "RECORDED_B2_REPLAY_V1"
    const val VERSION = "recorded-b2-dispatch-gate-v1"

    data class Entry(val id: String, val ordinal: Int, val task: String,
                     val arrivalNs: Long, val releaseNs: Long, val backend: String,
                     val sourceId: String)

    fun validate(entries: List<Entry>, requests: List<ArrivalEnergyContract.Request>) {
        require(entries.size == requests.size && entries.map { it.id }.toSet().size == entries.size)
        entries.zip(requests).forEach { (entry, request) ->
            require(entry.id == request.id && entry.ordinal == request.ordinal &&
                entry.task == request.task && entry.arrivalNs == request.offsetMs * 1_000_000L)
            require(entry.releaseNs >= entry.arrivalNs && entry.releaseNs < ArrivalEnergyContract.COMMON_NS)
            require(entry.backend == (if (entry.task == "classification") "GPU" else "CPU"))
            require(entry.sourceId.isNotBlank())
        }
    }

    fun choose(waiting: List<ArrivalPolicy.Ticket>, entries: Map<String, Entry>,
               elapsedNs: Long, freeCpu: Boolean, freeGpu: Boolean): ArrivalPolicy.Choice? {
        require(elapsedNs >= 0)
        return waiting.map { ticket -> entries.getValue(ticket.id) to ticket }
            .filter { (entry, _) -> entry.releaseNs <= elapsedNs &&
                (if (entry.backend == "CPU") freeCpu else freeGpu) }
            .sortedWith(compareBy<Pair<Entry, ArrivalPolicy.Ticket>> { it.first.releaseNs }
                .thenBy { it.first.ordinal }.thenBy { it.first.sourceId })
            .firstOrNull()?.let { (entry, ticket) ->
                ArrivalPolicy.Choice(ticket, entry.backend, "recorded_dispatch_gate")
            }
    }
}
