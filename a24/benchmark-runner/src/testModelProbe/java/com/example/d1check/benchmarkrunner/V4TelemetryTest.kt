package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test

class V4TelemetryTest {
    private val id = "00000000-0000-0000-0000-000000000001"
    @Test fun capturedInferenceTimestampsAreNotReplacedByLoggerTime() {
        var clock = 100L
        val t = V4Telemetry(id) { clock++ }
        val s = V4Scope(t, id, "classification", "CPU", 0)
        t.emit("session_start")
        s.at("invocation_start", 110); s.at("invocation_end", 120)
        clock = 130; t.emit("session_end")
        val rows = t.snapshot()
        assertEquals(listOf(100L, 110L, 120L, 130L), rows.map { it["mono_ns"] })
        assertEquals(listOf(0,1,2,3), rows.map { it["sequence"] })
    }
    @Test fun requestIdentityIsCapturedBeforeOwnerScopeChanges() {
        val t = V4Telemetry(id) { 1L }; val s = V4Scope(t,id,"detection","CPU",0)
        s.requestId = "request_a"; t.emit("request_enqueue",s); s.requestId = "request_b"
        assertEquals("request_a",t.snapshot().single()["request_id"])
    }
    @Test fun monotonicRegressionRejected() {
        var clock = 2L; val t = V4Telemetry(id) { clock }
        t.emit("session_start"); clock=1
        assertThrows(IllegalStateException::class.java) { t.emit("session_end") }
    }
    @Test fun memoryPass() { assertEquals("admit", V4Gate.reason(10000,100,false,500,0)) }
    @Test fun lowMemoryRejects() { assertEquals("android_low_memory",V4Gate.reason(10000,100,true,500,0)) }
    @Test fun reserveEqualityRejects() { assertEquals("insufficient_dynamic_reserve",V4Gate.reason(600,100,false,500,0)) }
    @Test fun unmeasuredThermalRejects() { assertEquals("thermal_outside_zero",V4Gate.reason(10000,100,false,500,1)) }
    @Test fun unknownFootprintRejects() { assertEquals("missing_memory_evidence",V4Gate.reason(10000,100,false,0,0)) }
    @Test fun residentCpuUsesOneLaneForBothInstances() {
        assertEquals(0,V4Gate.worker("resident_cpu_serial",0)); assertEquals(0,V4Gate.worker("resident_cpu_serial",1))
    }
    @Test fun coRunKeepsSeparateOwnerWorkers() {
        assertEquals(0,V4Gate.worker("resident_corun",0)); assertEquals(1,V4Gate.worker("resident_corun",1))
    }
    @Test fun cleanupStillRunsAfterTelemetryFailure() {
        val t = V4Telemetry(id) { -1L }; val s = V4Scope(t,id,"detection","CPU",0);var closed=false
        assertThrows(IllegalArgumentException::class.java) { closeV4Resource(s,"runtime_close") { closed=true } }
        assertTrue(closed)
    }
}
