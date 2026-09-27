package com.example.d1check.benchmarkrunner

/** Opt-in macro-regimen, never a claim that individual sub-second calls are thermal states. */
internal object EnergyStateCalibration {
    const val PROTOCOL = "energy-ap-state-collection-v1"
    const val WATCHDOG_MS = 1_800_000L
    const val COMMON_NS = 600_000_000_000L
    const val CADENCE_NS = 250_000_000L
    const val MAX_PER_LANE_PER_BLOCK = 512
    const val MAX_WORK_CALLS = 1680
    data class Block(val id: String, val lanes: List<Int>, val seconds: Int)
    fun blocks(confirmation: Boolean): List<Block> = if (confirmation) listOf(
        Block("pair", listOf(0, 1), 120), Block("idle_1", emptyList(), 30),
        Block("solo_b", listOf(1), 90), Block("idle_2", emptyList(), 30),
        Block("solo_a", listOf(0), 90), Block("idle_tail", emptyList(), 120)) else listOf(
        Block("solo_a", listOf(0), 90), Block("idle_1", emptyList(), 30),
        Block("solo_b", listOf(1), 90), Block("idle_2", emptyList(), 30),
        Block("pair", listOf(0, 1), 120), Block("idle_tail", emptyList(), 120))
    fun validate(blocks: List<Block>) {
        require(blocks.sumOf { it.seconds } == 480)
        require(blocks.sumOf { b -> b.lanes.size * (b.seconds * 4) } == MAX_WORK_CALLS)
        require(blocks.all { b -> b.seconds > 0 && b.lanes.distinct() == b.lanes && b.lanes.all { it in 0..1 } })
    }
}
