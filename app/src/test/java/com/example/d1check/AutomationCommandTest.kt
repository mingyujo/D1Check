package com.example.d1check

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AutomationCommandTest {
    @Test
    fun absentCommandPreservesManualStartBehavior() {
        assertNull(AutomationCommandParser.parse(null))
    }

    @Test
    fun parsesStartAndStopCommands() {
        assertEquals(
            AutomationCommand.START_RUN,
            AutomationCommandParser.parse("START_RUN"),
        )
        assertEquals(
            AutomationCommand.STOP_RUN,
            AutomationCommandParser.parse("stop_run"),
        )
    }

    @Test
    fun manualAndStartRunOnlyRouteToStart() {
        assertEquals(
            TelemetryCommandAction.START,
            AutomationCommandRouter.route(null),
        )
        assertEquals(
            TelemetryCommandAction.START,
            AutomationCommandRouter.route(AutomationCommand.START_RUN),
        )
    }

    @Test
    fun stopRunOnlyRoutesToStop() {
        assertEquals(
            TelemetryCommandAction.STOP,
            AutomationCommandRouter.route(AutomationCommand.STOP_RUN),
        )
    }

    @Test
    fun repeatedStopOnlyAllowsOneRunStopEvent() {
        val gate = RunStopEventGate()
        gate.markRunStarted()

        assertTrue(gate.consumeStop())
        assertFalse(gate.consumeStop())
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsUnknownCommand() {
        AutomationCommandParser.parse("restart_old_run")
    }
}
