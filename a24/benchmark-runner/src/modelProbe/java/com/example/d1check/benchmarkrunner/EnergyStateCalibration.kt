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
    /** Diagnostic only: six fixed 80 s cycles, same aggregate 480 s and 1680-call cap.
     * A 20 s pair/15 s solo is observable at the existing AP cadence, unlike a
     * sub-second individual arrival. It is not an arbitrary-arrival validation.
     */
    fun shortTransitionBlocks(): List<Block> = (0 until 6).flatMap { cycle ->
        listOf(Block("cycle${cycle}_pair", listOf(0, 1), 20),
            Block("cycle${cycle}_idle_after_pair", emptyList(), 10),
            Block("cycle${cycle}_solo_b", listOf(1), 15),
            Block("cycle${cycle}_idle_after_b", emptyList(), 10),
            Block("cycle${cycle}_solo_a", listOf(0), 15),
            Block("cycle${cycle}_idle_after_a", emptyList(), 10))
    }
    fun validate(blocks: List<Block>) {
        require(blocks.sumOf { it.seconds } == 480)
        require(blocks.sumOf { b -> b.lanes.size * (b.seconds * 4) } == MAX_WORK_CALLS)
        require(blocks.all { b -> b.seconds > 0 && b.lanes.distinct() == b.lanes && b.lanes.all { it in 0..1 } })
    }
}
