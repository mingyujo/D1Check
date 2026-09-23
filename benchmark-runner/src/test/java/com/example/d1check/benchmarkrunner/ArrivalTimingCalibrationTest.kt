package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test

class ArrivalTimingCalibrationTest {
    private val missing = listOf("classification", "detection").flatMap { task ->
        listOf("CPU", "GPU").map { "${task}_$it" to ArrivalTimingDev.Budget(null, null, null, null) }
    }.toMap()
    private fun ticket(task: String = "detection", priority: String = "urgent") = ArrivalPolicy.Ticket("q", task, priority, 0)

    @Test fun allEightCellsExecuteFixedRouteWithoutPredictions() {
        for (backend in listOf("CPU", "GPU")) for (task in listOf("classification", "detection"))
            for (priority in listOf("urgent", "normal")) {
                var time = 1L
                val recorder = ArrivalTimingDev.Recorder({ time++ }, missing, "missing", "calibration", calibrationBackend = backend)
                val result = recorder.choose(listOf(ticket(task, priority))).first
                assertEquals(backend, result.choice?.backend)
                assertEquals("calibration_fixed_backend", result.reason)
                assertTrue(result.candidates.isEmpty())
                assertEquals(ArrivalTimingDev.CALIBRATION_PROTOCOL, recorder.artifact(false)["protocol"])
                assertEquals(false, recorder.artifact(false)["experiment_ready"])
            }
    }
    @Test fun otherBusyLaneBlocksEvenForcedGpu() {
        val recorder = ArrivalTimingDev.Recorder({ 1L }, missing, "missing", "calibration", calibrationBackend = "GPU")
        recorder.mark("CPU", ticket(), ArrivalTimingDev.Phase.ASSIGNED)
        assertEquals("wait_calibration_solo_busy", recorder.choose(listOf(ticket().copy(id = "new"))).first.reason)
        assertFalse(recorder.isIdle())
    }
    @Test fun releaseCallbackAndDelayedArrivalCallbackCannotHideOverlap() {
        var time = 10L
        val recorder = ArrivalTimingDev.Recorder({ time++ }, missing, "missing", "calibration", calibrationBackend = "GPU")
        recorder.mark("GPU", ticket(), ArrivalTimingDev.Phase.ASSIGNED)
        recorder.mark("GPU", ticket(), ArrivalTimingDev.Phase.WORKER_RELEASED)
        assertFalse(recorder.isIdle())
        recorder.mark("GPU", ticket(), ArrivalTimingDev.Phase.AVAILABLE)
        assertFalse(recorder.isIdle(11)) // Actual arrival before release, enqueue callback after release.
        assertTrue(recorder.isIdle(12))
        assertEquals("wait_empty", recorder.choose(emptyList()).first.reason)
    }
    @Test fun fabricatedEstimateCannotEnableCalibration() {
        assertThrows(IllegalArgumentException::class.java) {
            ArrivalTimingDev.Recorder({ 1L }, missing + ("classification_CPU" to ArrivalTimingDev.Budget(0, null, null, null)),
                "bad", "bad", calibrationBackend = "GPU")
        }
    }
    @Test fun overflowCannotDispatchAndRemainsIncomplete() {
        val recorder = ArrivalTimingDev.Recorder({ 1L }, missing, "missing", "calibration", 1, "CPU")
        recorder.choose(emptyList())
        assertNull(recorder.choose(listOf(ticket())).first.choice)
        assertTrue(recorder.overflow)
        assertEquals(false, recorder.artifact(true)["complete"])
    }
    @Test fun adaptiveDevelopmentRemainsUnknownAndSeparate() {
        val recorder = ArrivalTimingDev.Recorder({ 1L }, missing, "missing", "development")
        val choice = recorder.choose(listOf(ticket())).first.choice
        assertEquals("CPU", choice?.backend)
        assertEquals("fallback_cpu_unknown", choice?.reason)
        assertEquals(ArrivalTimingDev.PROTOCOL, recorder.artifact(false)["protocol"])
        assertFalse(recorder.artifact(false).containsKey("calibration_backend"))
    }
    @Test fun uncommittedEventPreservesArrivalWithoutInventingExecutionOrSuccess() {
        val planned = mapOf("request_id" to "q", "scheduled_arrival_ns" to 10L, "terminal_status" to "unfinished")
        val arrived = mapOf("request_id" to "q", "actual_arrival_ns" to 12L, "queue_entry_ns" to 15L)
        val output = ArrivalTimingDev.unfinishedWithArrival(planned, arrived)
        assertEquals(12L, output["actual_arrival_ns"])
        assertEquals(15L, output["queue_entry_ns"])
        assertEquals("unfinished", output["terminal_status"])
        assertFalse(output.containsKey("execution_start_ns"))
        assertFalse(ArrivalTimingDev.unfinishedWithArrival(planned, null).containsKey("actual_arrival_ns"))
    }
}
