package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test
import java.util.ArrayDeque
import java.util.concurrent.Executor

class A24WorkerReturnTest {
    private class Queue: Executor {
        val tasks = ArrayDeque<Runnable>()
        override fun execute(command: Runnable) { tasks.add(command) }
        fun runOne() = tasks.remove().run()
    }
    @Test fun availableCannotPrecedeTheMeasuredWorkerReturn() {
        val lane = Queue(); val dispatch = Queue(); val log = mutableListOf<String>()
        var workerActive = true
        A24WorkerReturn.afterReturn(lane,dispatch,{ log+="worker_release" },{
            assertFalse(workerActive); log+="AVAILABLE"
        },{ throw it })
        assertEquals(listOf("worker_release"),log); assertTrue(dispatch.tasks.isEmpty())
        workerActive = false; lane.runOne()
        assertEquals(listOf("worker_release"),log)
        dispatch.runOne(); assertEquals(listOf("worker_release","AVAILABLE"),log)
    }
    @Test fun releaseLogFailurePreservesReturnMarkerAndFailure() {
        val lane = Queue(); val dispatch = Queue(); val log = mutableListOf<String>()
        A24WorkerReturn.afterReturn(lane,dispatch,{ error("disk full mock") },{ log+="AVAILABLE" },{ log+="FAILED" })
        assertEquals(listOf("FAILED"),log)
        lane.runOne(); dispatch.runOne(); assertEquals(listOf("FAILED","AVAILABLE"),log)
    }
    @Test fun markerSubmissionFailureDoesNotInventAvailability() {
        val dispatch = Queue(); var available = false; var failed = false
        A24WorkerReturn.afterReturn(Executor { error("executor rejected mock") },dispatch,{},
            { available=true },{ failed=true })
        assertTrue(failed); assertFalse(available); assertTrue(dispatch.tasks.isEmpty())
    }
}
