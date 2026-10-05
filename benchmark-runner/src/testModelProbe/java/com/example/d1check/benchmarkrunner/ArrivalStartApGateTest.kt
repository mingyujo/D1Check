package com.example.d1check.benchmarkrunner
import org.junit.Assert.*
import org.junit.Test

class ArrivalStartApGateTest {
    @Test fun boundariesAndStartDelay() {
        for (ap in listOf(32.5,34.0)) {
            val r=ArrivalStartApGate.parse("hash 100 100 200 $ap 0","hash",100)
            ArrivalStartApGate.atStart(r,3_000_000_100L)
            try { ArrivalStartApGate.atStart(r,3_000_000_101L); fail("stale admitted") }
            catch (_: IllegalArgumentException) {}
        }
    }
    @Test fun malformedWrongSessionMissingAndOutOfRangeBlock() {
        for (s in listOf("", "wrong 100 100 200 33 0", "hash 99 100 200 33 0",
            "hash 100 99 200 33 0", "hash 100 200 100 33 0", "hash 100 100 200 NaN 0",
            "hash 100 100 200 32.4 0", "hash 100 100 200 34.1 0", "hash 100 100 200 33 1")) {
            try { ArrivalStartApGate.parse(s,"hash",100); fail("invalid admitted: $s") }
            catch (_: IllegalArgumentException) {}
        }
    }
    @Test fun diagnosticAcceptsFiniteFreshApButLegacyStillBlocksBelowRange() {
        val payload = "hash 100 100 200 28.8 0"
        val reading = ArrivalStartApGate.parse(payload, "hash", 100, ArrivalStartApGate.DIAGNOSTIC_VERSION)
        assertEquals(28.8, reading.ap, 0.0)
        ArrivalStartApGate.atStart(reading, 3_000_000_100L)
        try { ArrivalStartApGate.parse(payload, "hash", 100); fail("legacy range changed") }
        catch (_: IllegalArgumentException) {}
        for (invalid in listOf("NaN", "Infinity")) {
            try { ArrivalStartApGate.parse("hash 100 100 200 $invalid 0", "hash", 100,
                ArrivalStartApGate.DIAGNOSTIC_VERSION); fail("nonfinite admitted") }
            catch (_: IllegalArgumentException) {}
        }
    }
}
