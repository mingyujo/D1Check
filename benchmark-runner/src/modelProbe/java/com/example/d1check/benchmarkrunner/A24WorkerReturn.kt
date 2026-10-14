package com.example.d1check.benchmarkrunner

import java.util.concurrent.Executor

/** Invoke from the worker finally block. The marker cannot run until that worker returns. */
internal object A24WorkerReturn {
    fun afterReturn(lane: Executor, dispatch: Executor, recordRelease: () -> Unit,
                    available: () -> Unit, failed: (Throwable) -> Unit) {
        try { recordRelease() } catch(e:Throwable) { failed(e) }
        finally {
            try { lane.execute {
                try { dispatch.execute { available() } } catch(e:Throwable) { failed(e) }
            } } catch(e:Throwable) { failed(e) }
        }
    }
}
