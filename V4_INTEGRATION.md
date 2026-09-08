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

If `python` is not on `PATH`, invoke an installed Python 3.11+ executable by its full path.

## Resource behavior

- CPU4 remains a legacy UI/Intent alias for standalone LiteRT Interpreter CPU execution with four
  requested threads. New runner metadata records `resource=CPU`, `cpu_threads=4`, and
  `cpu_affinity=NONE`; it does not claim that four fixed CPU cores are pinned.
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

On Galaxy A24/Android, the host pushes the config to
`/data/misc/perfetto-configs/d1check-gpu-diagnostic.pbtxt` and writes the device trace to
`/data/misc/perfetto-traces/d1check-diagnostic.perfetto-trace`. Both files are removed after the
trace is pulled. `/data/local/tmp` is not used because Perfetto cannot read the config there on the
validated device build.

Perfetto capture is single-shot per logger session. Lifecycle events replayed from the runner file
cannot restart a completed or failed capture. The host pulls to a temporary local file, verifies a
non-empty result, atomically installs it without replacing an existing successful trace, and only
then removes the remote config and trace. On pull failure the remote trace is retained for manual
recovery.

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

## Phase 0-3 automation

D1Check accepts explicit Activity commands. `START_RUN` always starts a fresh UUID and `STOP_RUN`
stops the current service without first creating another run:

~~~powershell
adb shell am start -W -n com.example.d1check/.MainActivity --es d1_automation_command START_RUN
adb shell am start -W -n com.example.d1check/.MainActivity --es d1_automation_command STOP_RUN
~~~

Benchmark Runner accepts an automated duration request. `d1_command_id` and `d1_run_id` must be
UUIDs, the requested run ID must match the active provider context, and replayed command IDs are
ignored:

~~~powershell
adb shell am start -W -n com.example.d1check.benchmarkrunner/.MainActivity `
  --ez d1_auto_start true --es d1_resource CPU4 --ei d1_cpu_threads 4 `
  --es d1_limit_mode DURATION --el d1_duration_s 60 --ei d1_warmup_count 20 `
  --es d1_experiment_mode BASIC --es d1_run_id <run-uuid> `
  --es d1_command_id <command-uuid>
~~~

COUNT and DURATION are separate configuration types. A DURATION run has no requested inference
count; the count is an output. Metadata adds `termination_reason`, `target_duration_ns`,
`actual_load_duration_ns`, and `duration_overrun_ns`. A final inference can cross the monotonic
deadline because `Interpreter.run()` cannot be interrupted.

Automated pilot starts currently enforce a pilot-only gate: Android thermal status at most LIGHT
(1), unplugged, battery status DISCHARGING (3), battery level 30--100%, and battery temperature at
most 35 C. SOC 91--100% is allowed for functional/safety pilots but records
`formal_energy_eligible=false`; formal energy eligibility recommends SOC 30--90%. Metadata
explicitly records `safety_policy_scope=PILOT_START_ONLY`, while
`formal_safety_limits_applied=false` and `matched_start_limits_applied=false`. Manual execution is
unchanged. Formal hard-safety monitoring and matched-start control belong to later phases.

No device-battery energy is produced in phase 0-3. Future current/charge-counter scale validation
uses one sign convention for both sources: positive discharge magnitude. Android negative
`CURRENT_NOW` is negated, while a decreasing charge counter is `(start_uAh-end_uAh)/hours`.
Scale mismatch is never silently corrected.

The later CPU/GPU accuracy preflight will use at least 32 deterministic inputs. Output SHA-256 is
provenance only; top-k agreement, cosine similarity, and absolute/relative error are the pass
criteria. Duty cycling, output comparison, and energy integration are not implemented.

## Repeat experiment orchestrator MVP

`d1_experiment_orchestrator.py` automates BASIC CPU/GPU duration experiments. One repeat means one
run per selected resource. `--seed` shuffles the stored plan reproducibly; without a seed the order
is the order supplied to `--resources`. Each slot receives a new D1Check run UUID and runner
command UUID.

Dry-run performs no ADB calls and writes no manifest:

~~~powershell
python tools/d1_experiment_orchestrator.py --dry-run --mode pilot `
  --resources CPU GPU --duration 60 --warmup 20 --repeat 2 --seed 20260908
~~~

Galaxy A24 pilot example (wireless ADB, unplugged):

~~~powershell
python tools/d1_experiment_orchestrator.py `
  --serial <A24-IP:PORT> --mode pilot --resources CPU GPU `
  --cpu-threads 4 --duration 60 --warmup 20 --repeat 1 --seed 20260908 `
  --output-dir results/A24_pilot_60s
~~~

The orchestrator verifies the selected ADB device, force-stops the runner, starts the existing v4
logger, confirms its `capture started` marker, creates the D1Check run, starts the runner, waits for
its footer or explicit failure, stops D1Check, analyzes the captured directory, and validates the
result. Pilot preflight permits SOC 30--100%; formal mode requires SOC 30--90%. Both require
unplugged, DISCHARGING, battery temperature at most 35 C, and Android thermal status at most LIGHT.

Every transition and failure is atomically checkpointed in
`<output-dir>/experiment_manifest.json`. A failed slot halts the experiment and later slots remain
pending. After correcting the cause, resume with the same options plus `--resume`; completed slots
are never run again:

~~~powershell
python tools/d1_experiment_orchestrator.py `
  --serial <A24-IP:PORT> --mode pilot --resources CPU GPU `
  --cpu-threads 4 --duration 60 --warmup 20 --repeat 1 --seed 20260908 `
  --output-dir results/A24_pilot_60s --resume
~~~

If Activity-based STOP does not produce the matching `run_stop`, the orchestrator uses the tested
`run-as ... start-foreground-service` recovery and records that fact. A timeout, disconnected ADB
stream, runner failure, abnormal logger exit, failed analysis, or invalid result stops the whole
plan. There is no automatic retry; resume is an explicit operator decision.

Logcat remains the fast terminal-event path, but it is not authoritative: Android may evict the
late `D1GPU` replay before `file_summary` reaches the host. Remote fallback starts only after the
expected 60-second baseline plus requested load duration and a 30-second setup/warmup grace. It
then checks the runner directory at 15-second intervals and once more immediately before the hard
timeout. Exactly one matching `gpu-events-<run_id>-<runner_session_id>.jsonl` is required. Its tail
must have the expected run/session IDs, GPU source, schema version, contiguous sequence, and a
valid final `file_summary` with `status=ok`; inference-only tails remain pending. Missing files and
ADB command failures are distinct outcomes, and multiple matching files stop the experiment as
ambiguous. The manifest records `terminal_event_source`, `terminal_fallback_used`,
`remote_runner_path`, and `logcat_terminal_missing`.

On every failed slot, cleanup records separate manifest steps for Activity STOP, direct-service
STOP use, matching `run_stop` confirmation, logger exit or forced termination, runner force-stop,
and recoverable local/remote artifact paths. Cleanup errors are supplementary and never replace
the original experiment failure.

The manifest keeps `current_raw_policy=raw_unscaled_unit_unverified` and
`energy_calculation=false`. The MVP never scales current, integrates device-battery energy, runs a
duty cycle, or compares model accuracy.
