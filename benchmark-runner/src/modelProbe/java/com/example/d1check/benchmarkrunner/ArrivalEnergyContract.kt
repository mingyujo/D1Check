package com.example.d1check.benchmarkrunner

/** Isolated synthetic-arrival collection. No change to existing arrival/energy protocols. */
internal object ArrivalEnergyContract {
    const val PROTOCOL = "arrival-energy-synthetic-v1"
    const val WATCHDOG_MS = 480_000L
    const val COMMON_NS = 120_000_000_000L
    const val DRAIN_SECONDS = 30L
    const val BASELINE_SECONDS = 30L
    const val COOLING_SECONDS = 60L
    const val SETUP_NS = 150_000_000_000L
    const val GATE_NS = 60_000_000_000L
    const val CALL_NS = 30_000_000_000L
    const val COUNT = 24

    data class Request(val id: String, val ordinal: Int, val task: String,
                       val priority: String, val offsetMs: Long, val deadlineMs: Long)

    fun offset(scenario: String, index: Int): Long {
        require(index in 0 until COUNT)
        return when (scenario) {
            "low" -> index * 1200L
            "queue" -> index * 200L
            "burst" -> index * 80L + (index / 6) * 1000L
            else -> error("unsupported scenario")
        }
    }

    fun validate(scenario: String, requests: List<Request>) {
        require(requests.size == COUNT && requests.map { it.id }.toSet().size == COUNT)
        requests.forEachIndexed { i, r ->
            val urgent = i % 4 == 1
            require(r.ordinal == i && r.offsetMs == offset(scenario, i) &&
                r.priority == (if (urgent) "urgent" else "normal"))
            require(r.task == (if (urgent) "classification" else "detection"))
            require(r.deadlineMs == (if (urgent) 1500L else 6000L))
        }
    }
}
