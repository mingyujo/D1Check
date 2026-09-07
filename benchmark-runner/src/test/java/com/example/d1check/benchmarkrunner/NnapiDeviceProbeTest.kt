package com.example.d1check.benchmarkrunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class NnapiDeviceProbeTest {
    @Test
    fun requiresApi29ForDeviceDiscovery() {
        assertFalse(NnapiDeviceProbe.isSupportedApiLevel(28))
        assertTrue(NnapiDeviceProbe.isSupportedApiLevel(29))
    }

    @Test
    fun mapsNnapiDeviceTypeNumbers() {
        assertEquals("UNKNOWN", NnapiDeviceProbe.typeName(0))
        assertEquals("OTHER", NnapiDeviceProbe.typeName(1))
        assertEquals("CPU", NnapiDeviceProbe.typeName(2))
        assertEquals("GPU", NnapiDeviceProbe.typeName(3))
        assertEquals("ACCELERATOR", NnapiDeviceProbe.typeName(4))
        assertEquals("UNKNOWN", NnapiDeviceProbe.typeName(99))
    }

    @Test
    fun decodesNativeDeviceFieldsWithoutNameBasedNpuInference() {
        val devices = NnapiDeviceProbe.decodeNativeDevices(
            arrayOf("0", "vendor-neuron-mdla-apu", "4", "1.2", "6"),
        )

        assertEquals(1, devices.size)
        assertEquals("ACCELERATOR", devices.single().typeName)
        assertFalse(devices.single().isReferenceCpu)
    }

    @Test
    fun marksNnapiReferenceAsReferenceCpu() {
        val device = NnapiDeviceProbe.decodeNativeDevices(
            arrayOf("1", "nnapi-reference", "2", "reference", "3"),
        ).single()

        assertEquals("CPU", device.typeName)
        assertTrue(device.isReferenceCpu)
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsMalformedNativeFieldCount() {
        NnapiDeviceProbe.decodeNativeDevices(arrayOf("0", "incomplete"))
    }
}
