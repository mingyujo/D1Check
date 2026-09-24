package com.example.d1check.npurunner

import com.example.d1check.npurunner.NpuDeterministicInput.InputSpec
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class NpuDeterministicInputTest {

    private val mobileNetElements = 224 * 224 * 3

    /** 9/24 G4 게이트가 기기에서 보고한 input_sha256. 기본 입력이 바뀌면 여기서 깨진다. */
    @Test
    fun defaultSpecIsTheG4Input() {
        assertEquals(InputSpec.LCG_UNIT, InputSpec.fromWire(null))
        val first = NpuDeterministicInput.inputSet(InputSpec.LCG_UNIT, 1, mobileNetElements)[0]
        assertEquals(
            "5dc1cb09d712429fa580bdb7976c01d3933956d77002a8c8ab3c82c40f3899f3",
            NpuDeterministicInput.sha256(first),
        )
        assertArrayEquals(NpuDeterministicInput.floats(mobileNetElements), first, 0f)
        assertEquals(NpuDeterministicInput.VERSION, InputSpec.LCG_UNIT.generator)
        assertEquals(NpuDeterministicInput.NORMALIZATION, InputSpec.LCG_UNIT.normalization)
    }

    @Test
    fun lcgUnitSetContinuesOneStream() {
        val set = NpuDeterministicInput.inputSet(InputSpec.LCG_UNIT, 3, 8)
        val flat = NpuDeterministicInput.floats(24)
        for (i in 0 until 3) assertArrayEquals(flat.copyOfRange(i * 8, i * 8 + 8), set[i], 0f)
    }

    @Test
    fun unknownSpecIsNull() {
        assertNull(InputSpec.fromWire("rgb"))
    }

    @Test
    fun lcgRgbStaysInNormalizedRange() {
        val effnet = NpuDeterministicInput.inputSet(InputSpec.LCG_RGB_127_128, 2, 1000)
        effnet.forEach { a -> a.forEach { assertTrue(it >= -127f / 128f && it <= 1f) } }
        val effdet = NpuDeterministicInput.inputSet(InputSpec.LCG_RGB_1275_1275, 2, 1000)
        effdet.forEach { a -> a.forEach { assertTrue(it >= -1f && it <= 1f) } }
    }

    /** 조민규 ProbeRawAdapter.deterministicInput(coordinate-rgb-v1) 공식과 같은 값. */
    @Test
    fun coordinateRgbMatchesTeamFormula() {
        val cls = NpuDeterministicInput.inputSet(InputSpec.COORD_RGB_CLASSIFICATION, 2, mobileNetElements)
        // seed 0, (x=0, y=0): R=17, G=29, B=43
        assertEquals((17 - 127f) / 128f, cls[0][0], 0f)
        assertEquals((29 - 127f) / 128f, cls[0][1], 0f)
        assertEquals((43 - 127f) / 128f, cls[0][2], 0f)
        // seed 0, (x=1, y=0): R=20
        assertEquals((20 - 127f) / 128f, cls[0][3], 0f)
        // seed 1, (x=0, y=0): R=17+29=46
        assertEquals((46 - 127f) / 128f, cls[1][0], 0f)
        // seed 0, (x=0, y=1): R=22 (행 우선: y 가 바깥 루프)
        assertEquals((22 - 127f) / 128f, cls[0][224 * 3], 0f)

        val det = NpuDeterministicInput.inputSet(InputSpec.COORD_RGB_DETECTION, 1, 320 * 320 * 3)
        assertEquals((17 - 127.5f) / 127.5f, det[0][0], 0f)
    }

    @Test(expected = IllegalArgumentException::class)
    fun coordinateRgbRejectsMoreThanThreeSeeds() {
        NpuDeterministicInput.inputSet(InputSpec.COORD_RGB_CLASSIFICATION, 4, mobileNetElements)
    }

    @Test(expected = IllegalArgumentException::class)
    fun coordinateRgbRejectsWrongTensorSize() {
        NpuDeterministicInput.inputSet(InputSpec.COORD_RGB_DETECTION, 1, mobileNetElements)
    }
}
