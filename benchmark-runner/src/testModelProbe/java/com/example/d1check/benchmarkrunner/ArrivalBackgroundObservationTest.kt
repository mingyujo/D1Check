package com.example.d1check.benchmarkrunner
import org.junit.Assert.*
import org.junit.Test

class ArrivalBackgroundObservationTest {
    @Test fun exactControlAndRegisteredMixedInputOnly() {
        ArrivalBackgroundObservation.validate(ArrivalBackgroundObservation.VERSION,ArrivalRecordedReplay.POLICY,
            "development","burst",emptyList(),ArrivalEnergyContract.RESIDENT_CONTROL)
        val rows=(0 until 96).map { i -> ArrivalEnergyContract.Request("q$i",i,
            if(i%2==0) "classification" else "detection",if(i%2==0) "urgent" else "normal",
            35000+i*350L,if(i%2==0) 1500 else 6000) }
        for(p in listOf(ArrivalPolicyStudy.CPU,ArrivalPolicyStudy.PARALLEL))
            ArrivalBackgroundObservation.validate(ArrivalBackgroundObservation.VERSION,p,"development","separated_power",rows,"")
        for(p in listOf(ArrivalPolicyStudy.SERIAL,"bad")) try {
            ArrivalBackgroundObservation.validate(ArrivalBackgroundObservation.VERSION,p,"development","separated_power",rows,"")
            fail("unregistered policy")
        } catch (_: IllegalArgumentException) {}
        try { ArrivalBackgroundObservation.validate(ArrivalBackgroundObservation.VERSION,ArrivalPolicyStudy.CPU,
            "confirmation","separated_power",rows,"");fail("role") } catch (_: IllegalArgumentException) {}
    }
    @Test fun pastOnlyIntegrationPublicationFreshnessAndMissing() {
        val window=ArrivalPastPowerWindow()
        for(i in 0..15) window.add(ArrivalPastPowerWindow.Sample(i*1000000000L,i*1000000000L+100,2.0,i*100L))
        val before=window.at(15000000100L)
        assertEquals(2.0,before["mean_whole_device_w"])
        assertEquals(.1,before["self_cpu_fraction"])
        window.add(ArrivalPastPowerWindow.Sample(16000000000L,19000000000L,2000.0,9999))
        assertEquals(before,window.at(15000000100L))
        assertNull(window.at(18000000200L)["mean_whole_device_w"])
        val missing=ArrivalPastPowerWindow()
        for(i in 0..12) missing.add(ArrivalPastPowerWindow.Sample(i*1000000000L,i*1000000000L,
            if(i==7) null else 2.0,i*100L))
        assertNull(missing.at(12000000000L)["mean_whole_device_w"])
    }
    @Test fun boundedRingAndGapCannotBecomeZeroPower() {
        val window=ArrivalPastPowerWindow()
        for(i in 0..200) window.add(ArrivalPastPowerWindow.Sample(i*1000000000L,i*1000000000L,2.0,i*100L))
        assertEquals("available",window.at(200000000000L)["status"])
        val gap=ArrivalPastPowerWindow()
        for(i in listOf(0,1,2,3,7,8,9,10,11)) gap.add(ArrivalPastPowerWindow.Sample(i*1000000000L,i*1000000000L,2.0,i*100L))
        assertNull(gap.at(11000000000L)["mean_whole_device_w"])
    }
}
