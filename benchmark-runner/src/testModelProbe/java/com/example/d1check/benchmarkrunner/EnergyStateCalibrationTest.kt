package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test

class EnergyStateCalibrationTest {
    @Test fun boundedBalancedBlockOrders() {
        val development = EnergyStateCalibration.blocks(false)
        val confirmation = EnergyStateCalibration.blocks(true)
        EnergyStateCalibration.validate(development)
        EnergyStateCalibration.validate(confirmation)
        assertEquals(listOf("solo_a", "idle_1", "solo_b", "idle_2", "pair", "idle_tail"), development.map { it.id })
        assertEquals(listOf("pair", "idle_1", "solo_b", "idle_2", "solo_a", "idle_tail"), confirmation.map { it.id })
        assertEquals(480, development.sumOf { it.seconds })
        assertEquals(1_680, development.sumOf { it.lanes.size * it.seconds * 4 })
        assertTrue(EnergyStateCalibration.COMMON_NS > 480_000_000_000L)
    }

    @Test fun shortTransitionDiagnosticKeepsOriginalCaps() {
        val blocks = EnergyStateCalibration.shortTransitionBlocks()
        EnergyStateCalibration.validate(blocks)
        assertEquals(36, blocks.size)
        assertEquals(36, blocks.map { it.id }.toSet().size)
        assertEquals(480, blocks.sumOf { it.seconds })
        assertEquals(1_680, blocks.sumOf { it.lanes.size * it.seconds * 4 })
        assertEquals(120, blocks.filter { it.lanes.size == 2 }.sumOf { it.seconds })
        assertEquals(180, blocks.filter { it.lanes.isEmpty() }.sumOf { it.seconds })
    }
}
