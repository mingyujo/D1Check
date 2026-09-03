# D1Check v4 integration

## Run workflow

1. Open D1Check and tap **새 run 시작**. Keep its foreground-service notification active.
2. The benchmark queries `content://com.example.d1check.run/current` once and creates a
   `GpuTelemetry` instance. Both apps then use the same `run_id`; Android's
   `elapsedRealtimeNanos()` supplies the shared, boot-scoped monotonic clock.
3. Start capture before the benchmark:

   ```powershell
   py tools/d1_logger_v4.py capture results/raw.jsonl --clear
   ```

4. Stop capture with Ctrl-C and analyze the run:

   ```powershell
   py tools/d1_logger_v4.py analyze results/raw.jsonl results/analysis
   ```

The analysis directory contains `merged.jsonl`, `summary.json`, and
`latency_timeline.csv`. The timeline joins every completed inference/batch to the nearest
1 Hz D1Check sample, retaining the signed sample time difference.

## Benchmark instrumentation

Build `:telemetry-contract:assembleRelease`, publish/copy the resulting AAR into the benchmark,
and add it as a dependency. The AAR manifest contributes the package-visibility query.

Create the logger only after D1Check has an active run:

```kotlin
val telemetry = GpuTelemetry.connect(applicationContext)

val delegate = telemetry.delegateInit {
    createGpuDelegate()
}

repeat(warmupCount) { index ->
    telemetry.warmup(index.toLong()) {
        interpreter.run(input, output)
    }
}

repeat(inferenceCount) { index ->
    telemetry.inference(index.toLong(), batchSize = 1) {
        interpreter.run(input, output)
    }
}

telemetry.shutdown {
    interpreter.close()
    delegate.close()
}
```

`delegateInit`, `warmup`, `inference`, and `shutdown` emit start/end events. Exceptions emit
an error event and are rethrown. Latency is measured before Logcat output, so the event-write
cost is excluded. For a short batch, call `inference(index, batchSize = n)` around the whole
batch. Do not wrap asynchronous enqueue alone: the measured block must include the GPU
completion/fence wait, otherwise it measures submission latency rather than inference latency.

## Log schema

Both sources emit JSON objects with `schema_version`, `source`, `event`, `run_id`, `mono_ns`,
and `wall_ms`. GPU completed spans additionally contain `start_mono_ns`, `latency_ns`, and
`latency_ms`. D1Check continues to emit its v3-compatible pipe-delimited `D1CHECK` line while
structured records use `D1CHECK_EVENT`; GPU records use `D1GPU`.

The device file is stored under the app-specific external `runs` directory as
`d1check-<run_id>.jsonl`. Logcat capture remains the primary cross-app merge path.

## Operational limits

A foreground service continues when another benchmark Activity is in front, but Android or
Samsung firmware can still terminate it under memory pressure or explicit battery restrictions.
For controlled experiments, exclude D1Check from battery optimization and verify the persistent
notification before each run. A stock benchmark APK cannot be instrumented from D1Check; its
source must call this contract (or emit an equivalent `D1GPU` schema).
