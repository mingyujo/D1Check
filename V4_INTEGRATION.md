# D1Check v4 + Benchmark Runner

## Fixed experiment order

Use the following order for every basic experiment.

1. Clear Logcat:

   ~~~powershell
   python tools/d1_logger_v4.py clear
   ~~~

2. Start the logger:

   ~~~powershell
   python tools/d1_logger_v4.py capture results
   ~~~

3. Open D1Check and tap **새 run 시작**.
4. Open Benchmark Runner, select CPU4 or GPU, and press Start.
5. The runner waits for a fixed 60-second baseline before recording load_start.
6. It performs initialization, warmup and inference, records load_end, shuts down, and flushes.
7. The logger detects file_summary and automatically pulls the authoritative GPU JSONL.
8. Keep D1Check running for the desired cooldown period.
9. Stop the D1Check run. The logger exits after observing run_stop.
10. Analyze:

   ~~~powershell
   python tools/d1_logger_v4.py analyze results/<run_id>
   ~~~

Python is not installed on the current development PC, so these commands remain unverified until
an actual interpreter is installed or its path is supplied.

## Resource behavior

- CPU4 uses standalone LiteRT Interpreter with four CPU threads.
- GPU uses standalone LiteRT Interpreter 1.4.2 with GpuDelegate.
- GPU mode requests GpuDelegate and fails if delegate/interpreter setup fails. This alone does not
  prove that every graph node was delegated; only host-captured evidence can verify that claim.
- NPU and INT8 exist only as future enum/config values and are not selectable.
- Delegate creation, interpreter creation, warmup, inference, and shutdown all execute on the
  single d1-benchmark-runner thread.

The bundled model is mobilenet_v1_1.0_224.tflite float32:

- input: [1,224,224,3] FLOAT32
- output: [1,1001] FLOAT32
- SHA-256: D95B3C5EA86750CEF882FA867CA357DFE4D265D0B80B67E83277A0BDA310CFBB

## Measurement boundary

Each inference executes only:

~~~kotlin
val startNs = SystemClock.elapsedRealtimeNanos()
interpreter.run(input, output)
val endNs = SystemClock.elapsedRealtimeNanos()
~~~

The completed span is then copied into preallocated primitive arrays. There is no Logcat, JSON,
file I/O, input generation, allocation, or UI update inside the timed region. A maximum of
250,000 inference spans can be retained. Duration mode stops with a buffer_limit error if this
limit is reached.

All GPU JSON and Logcat messages are generated after load_end and shutdown. One inference
produces one inference span containing start_mono_ns, mono_ns, and latency_ns; separate start/end
events are not emitted.

## Authoritative files

The usual external-files path is:

~~~text
/storage/emulated/0/Android/data/com.example.d1check.benchmarkrunner/files/runs/
  gpu-events-<run_id>-<runner_session_id>.jsonl
~~~

If external storage is unavailable the app falls back to:

~~~text
/data/user/0/com.example.d1check.benchmarkrunner/files/runs/
~~~

The logger first uses adb pull and then, for a debuggable build, falls back to adb exec-out
run-as. The pulled runner file is authoritative. D1GPU Logcat is only a status and recovery copy.
Files are created without overwrite and every record includes `runner_session_id`. Analysis
rejects a non-contiguous sequence, mismatched run/session ID, missing footer, incorrect count, or
a GPU load outside the D1Check run envelope. A formal/basic run may contain one runner session.

Result layout:

~~~text
results/<run_id>/
├─ metadata.json
├─ raw/
│  ├─ logcat.jsonl
│  ├─ thermalservice.jsonl
│  └─ thermalservice-probe.txt
├─ gpu/
│  └─ gpu-events-<run_id>-<runner_session_id>.jsonl
├─ merged/
│  ├─ events.jsonl
│  ├─ latency_timeline.csv
│  └─ summary.json
└─ diagnostics/
   └─ d1check.perfetto-trace
~~~

current_raw is stored exactly as reported; no unit conversion or sign change is performed. The
Galaxy A24 parser retains AP, SKIN, BAT, and PA/PATHM/PA1THM aliases from d1_logger.py.

## Signature permission

The provider requires com.example.d1check.permission.READ_RUN_CONTEXT with signature protection.
D1Check and Benchmark Runner must be signed by the same certificate. Debug builds from this
project share the debug key; release APKs must use the same release signing key.

## Diagnostic mode

Perfetto is disabled by default. For a separate diagnostic run:

~~~powershell
python tools/d1_logger_v4.py capture results --diagnostic-perfetto
~~~

Also select Diagnostic run in Benchmark Runner. Diagnostic summaries are labeled
statistics_group=diagnostic and must not be pooled with basic-run latency statistics. GPU
frequency ftrace events are device/kernel dependent and may be absent on the Galaxy A24.

Perfetto starts on the runner's control marker immediately before GPU load and stops on the marker
immediately after load. The config uses a 32,768 KiB ring buffer and the maximum selectable
diagnostic duration is 3,600 seconds. Long/high-rate traces can overwrite older packets, so each
diagnostic summary includes an explicit overwrite warning.

## Run validity and delegation evidence

D1Check never resumes a stored active run. Every Activity launch or New Run action creates a new
UUID; an old active value is marked stale/aborted. The service is `START_NOT_STICKY`. The provider
and records carry a boot identifier. The runner revalidates run ID, active state, and boot ID before
baseline, before warmup, before GPU load, after GPU load, and before file flush. A mismatch records
`run_context_mismatch` and invalidates the experiment.

The host preserves D1CHECK_EVENT, D1GPU, `tflite`, and `TfLite` lines in `raw/logcat.txt`.
`delegate_evidence.json` verifies full delegation only when the GPU delegate was created,
`TfLiteGpuDelegateV2` replaced X out of Y nodes with X=Y>0, at least one GPU delegate kernel was
created, and no apply failure, restored-plan, unsupported-op, or CPU-fallback evidence exists.
Missing evidence is `unverified`, not proof of CPU fallback. Formal GPU data is valid only for
Galaxy A24, the bundled model SHA-256, LiteRT 1.4.2, verified full delegation, at least 95% valid
thermal sampling coverage, and a valid thermal sample during GPU load.

Warmup is capped at 10,000 operations, inference records at 250,000, lifecycle events at 20,000,
and duration at 3,600 seconds.
