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

The CPU/GPU output-equivalence preflight uses at least 32 deterministic inputs. It is a numerical
backend check, not a task-accuracy evaluation.

## Repeat experiment orchestrator MVP

`d1_experiment_orchestrator.py` automates BASIC CPU/GPU duration experiments. CPU conditions are
the Cartesian product of selected CPU thread levels and duty cycles; GPU conditions use duty only
and always store `cpu_threads=null`. `--repeat` defines randomized-complete-block repetitions. Each
block contains every condition exactly once, and `--seed` shuffles only within each block. No
global shuffle crosses block boundaries. The manifest records block design/version,
`block_index`, stable `condition_id`, and global `order_index`. Each slot receives a new D1Check
run UUID and runner command UUID. Blocking by repetition helps distribute time-varying ambient and
device conditions across treatments, but does not eliminate them.

The legacy `--cpu-threads` and `--duty-cycle-percent` single-value options remain available.
Matrices use `--cpu-thread-levels` and `--duty-cycles`. Supplying a single-value and its multi-value
form together is rejected as ambiguous. Duplicate axis values are also rejected rather than
silently normalized. CPU threads must be 1--16 and every duty value must be 1--100.

Dry-run performs no ADB calls and writes no manifest:

~~~powershell
python tools/d1_experiment_orchestrator.py --dry-run --mode pilot `
  --resources CPU GPU --duration 60 --warmup 20 --repeat 2 --seed 20260908
~~~

The full 3-thread x 4-duty CPU matrix plus the 4 GPU-duty conditions contains 16 conditions per
block and 80 slots over five blocks:

~~~powershell
python tools/d1_experiment_orchestrator.py --dry-run `
  --mode formal --resources CPU GPU `
  --cpu-thread-levels 1 2 4 --duty-cycles 25 50 75 100 `
  --duration 600 --warmup 20 --repeat 5 --seed 20260909 `
  --duty-cycle-period-seconds 10 `
  --start-policy stable --cooling-policy stable
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

Duration runs accept `--duty-cycle-percent` (1--100, default 100) and
`--duty-cycle-period-seconds` (positive, default 10). The orchestrator passes these as
`d1_duty_cycle_percent` and `d1_duty_cycle_period_s`. The schedule is anchored to Android
`elapsedRealtimeNanos()` at `load_start`; host wall time is never used. At 100%, inference remains
continuous as before. Below 100%, each period begins with an active window and ends with an idle
window. Inference starts only in an active window, but an inference already in progress may cross
the boundary. `duty_cycle_active_overrun_ns` is the cumulative intrusion into intended idle
windows. `actual_idle_duration_ns` is actual scheduler sleep time, and
`actual_active_duration_ns = actual_load_duration_ns - actual_idle_duration_ns`, so active plus
idle always explains the full measured load. `achieved_duty_cycle_percent` uses those actual
values. The overall DURATION deadline remains elapsed load time, including idle; COUNT semantics
are unchanged.

Thermal conditioning and post-load cooling are opt-in, so existing commands retain their previous
timing. `--start-policy safety` is the default and applies only the preflight above. `stable`
samples only the `Current temperatures from HAL` section of `dumpsys thermalservice`; every sample
must contain exactly one AP, BAT, PA (PA/PATHM/PA1THM alias), and SKIN value. Missing, duplicate,
malformed, or non-finite required values stop the slot. A rolling window passes only when every
sensor's range and absolute least-squares slope are within the configured bounds:

~~~powershell
python tools/d1_experiment_orchestrator.py `
  --serial <A24-IP:PORT> --mode pilot --resources CPU `
  --duration 60 --warmup 20 --repeat 1 `
  --duty-cycle-percent 25 --duty-cycle-period-seconds 10 `
  --start-policy stable --stability-window-seconds 30 `
  --stability-sample-interval-seconds 5 --stability-timeout-seconds 300 `
  --stability-max-range-c 0.5 --stability-max-slope-c-per-minute 0.3 `
  --cooling-policy stable --cooling-min-seconds 30 `
  --cooling-timeout-seconds 300 `
  --emergency-check-interval-seconds 30 `
  --emergency-max-battery-temperature-c 42 `
  --emergency-max-android-thermal-status 1 `
  --output-dir results/A24_stable_cooling_60s
~~~

For formal thermal-model data collection, `stable` is the recommended policy. The model should use
the measured temperatures at the actual `load_start` as state variables or covariates rather than
assuming that every slot began at one identical absolute temperature. Randomized complete blocks
reduce systematic coupling between treatment order and time/environment drift; they do not make
the starting thermal states identical.

`matched` is intended for short, direct CPU/GPU comparisons and diagnostics. It first requires the
same stable condition, then stores the first passing AP/BAT/PA/SKIN vector once at manifest scope.
Every later CPU/GPU/thread/duty slot and matched cooling decision uses that same reference and must
fall within
`--matched-tolerance-c` for every sensor. Resume reuses that stored reference and never derives a
new one. A missing reference after any attempted slot, or a malformed reference, stops resume
instead of silently replacing it. This is tolerance-based control of observed start temperatures,
not proof of statistical equivalence. A matched-start plan with more than two conditions is allowed
but records the non-blocking `matched_global_reference_long_matrix` methodology warning in both
dry-run output and the manifest. Delayed heat transfer and ambient-temperature drift can make a
return to one global reference impractical; use `stable` plus actual start-temperature covariates
for a long formal matrix.

In one Galaxy A24 pilot, a matched matrix did not return to its initial reference within 300 s after
the first CPU 2-thread, 100% duty load: the final stable AP, PA, and SKIN readings remained +0.8 C,
+0.9 C, and +0.6 C above reference, respectively, exceeding a 0.5 C tolerance. The same six-slot
matrix completed every slot on its first attempt with stable start/cooling policies. This is one
device-session observation, not a general bound for Galaxy A24 devices or other environments.

Cooling uses `--cooling-policy fixed|stable|matched` (default `fixed`). Fixed mode preserves the
existing `--post-load-idle-seconds` behavior exactly. Stable and matched modes always force-stop
the runner after its successful footer while D1Check telemetry and the logger remain active.
They wait at least the greater of `--cooling-min-seconds` and the legacy
`--post-load-idle-seconds`, and stop no later than `--cooling-timeout-seconds`. Stable reuses the
start-conditioning window/range/slope criteria. Matched additionally requires every sensor to be
within `--matched-tolerance-c` of the stored `thermal_conditioning_reference`; absence of that
reference is an explicit failure. D1Check is stopped only after the cooling policy completes,
leaving `load_end` through `run_stop` available as the cooling interval. Raw samples, each
stability decision, reference deltas, emergency outcome, completion reason, UTC times, and host
monotonic times are recorded. Android `load_end_mono_ns` and `run_stop_mono_ns` remain a separate
clock domain and must not be subtracted from host timestamps. A matched cooling deadline records
`status=timeout`, `completion_reason=cooling_timeout`, and
`failure_classification=thermal_conditioning_timeout`; it is not classified as an emergency abort
or runner failure.

Runtime emergency monitoring is disabled by default (`--emergency-check-interval-seconds 0`) to
preserve prior measurement behavior. When enabled, D1 Logcat samples are checked first and sparse
`dumpsys` checks fill the gaps at the requested interval. A thermal-status limit violation,
charging connection, non-DISCHARGING battery status, or battery-temperature limit violation first
force-stops the runner and then invokes normal D1/logger cleanup. Thresholds, observations,
original failure, and cleanup outcomes are retained in the manifest. Choose the interval to avoid
unnecessary ADB polling during measurement.

Every transition and failure is atomically checkpointed in
`<output-dir>/experiment_manifest.json`. A failed slot halts the experiment and later slots remain
pending. After correcting the cause, resume with the same options plus `--resume`; completed slots
are never run again. Stored order, condition IDs, and the shared thermal reference remain
unchanged. Changing resources, CPU-thread axis, duty axis, repeat count, or seed is rejected:

~~~powershell
python tools/d1_experiment_orchestrator.py `
  --serial <A24-IP:PORT> --mode pilot --resources CPU GPU `
  --cpu-threads 4 --duration 60 --warmup 20 --repeat 1 --seed 20260908 `
  --output-dir results/A24_pilot_60s --resume
~~~

Manifests created before the matrix feature remain resumable for their single CPU-thread and duty
values. Missing axis/block fields are added while the original slot IDs and execution order are
preserved; completed slots are not regenerated or reordered.

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

### Methodology-corrected CPU-GPU validation

The experiment-level schema is version 2 and separates three questions. It never relabels a
schema-v1 artifact or its historical failed result.

- `synthetic_numerical_check` is a runtime/tensor/delegate/catastrophic-numerical smoke test. Its
  32 or more `lcg-float32-unit-v1` tensors are FLOAT32 `[1,224,224,3]` values in `[0,1]` with no
  image normalization. Shape/dtype/model/input identity, finite output, and host-verified full GPU
  delegation are structural gates. The combined tolerance result is retained as
  `numerical_tolerance_result=within|outside`, but `outside` alone is not execution-integrity
  failure and is not task accuracy. Probability sums, cosine similarity, total variation, top-1,
  deterministic top-5, margins, and the full numeric error distribution are recorded.
- `representative_input_equivalence` uses host-preprocessed real-image tensor bytes. CPU and GPU
  receive the identical verified bytes. The versioned `representative-equivalence-v2` policy and
  `output-equivalence-v3` comparator are
  recorded rather than hidden: at least 40 class-balanced samples, zero top-1 mismatch, at least
  4/5 top-5 overlap for every determinate sample, maximum per-sample total variation 0.02, and minimum cosine
  similarity 0.999. These thresholds are methodology defaults registered before the next A24 run;
  they are not auto-adjusted to the observed synthetic result. This is the blocking gate for
  `backend-performance-formal`.
- `task_accuracy_check` requires ground-truth WNIDs and records CPU and GPU top-1/top-5 accuracy and
  GPU-minus-CPU deltas under `task-accuracy-no-regression-v1`. It is separate from numerical
  equivalence and blocks only `accuracy-preserving-formal`. Without labels it remains `not_run`.
  Imagenette covers only ten ImageNet classes and is not full ImageNet accuracy.

All ranks use score descending then class index ascending. If either output has an exact tie
between ranks 5 and 6, its top-5 set is not unique: that input records
`top5_overlap_applicable=false` with a reason and is excluded only from the blocking minimum-overlap
calculation. Determinate overlap failures, top-1, total variation, cosine, and non-finite gates are
unchanged. Task-accuracy ranking retains the deterministic tie-break and is not redefined by this
applicability flag. `execution_integrity_status` covers artifact/container/preprocessing/model/input
identity, shape/dtype, finite outputs, full delegation, and host binary revalidation; representative
acceptance failure alone does not change it to failed. Historical v1/v2 results are not rejudged,
and their comparator/policy hashes prevent resume reuse. The diagnostic element rule remains
inclusive, `abs(GPU-CPU) <= atol + rtol*abs(CPU)`, with recorded defaults `atol=1e-4`,
`rtol=1e-3`, and relative-error epsilon `1e-6`. These values are not a task-accuracy threshold.
The output is `[1,1001]` FLOAT32 Softmax probability: index 0 is TF-Slim background and the 1,000
WNIDs map to output indexes 1..1000. The model's image evaluation path is RGB, EXIF normalization,
central crop 0.875, bilinear resize to 224x224, then `(pixel/255-0.5)*2` (`[-1,1]`).

Two explicit GPU profiles replace the ambiguous `CompatibilityList_bestOptions` provenance:

- `gpu-compat-default-v1`: `precision_loss_allowed=true`, quantized models allowed,
  `FAST_SINGLE_ANSWER`, backend `UNSET`.
- `gpu-fp32-strict-v1`: identical except `precision_loss_allowed=false`.

The default timed behavior remains the compatibility profile. Timed and preflight metadata must
carry the same profile ID and configuration SHA-256. `precision_loss_allowed=true` is permission,
not evidence that a driver actually executed FP16; LiteRT does not expose that fact here. The CPU
reference explicitly enables XNNPACK and records its thread count; it is not described as an
undelegated "plain CPU". GPU creation alone is not full-delegation evidence: the host still requires
the logger's X=Y>0 `TfLiteGpuDelegateV2`, positive kernel count, and absence of fallback evidence.

### Galaxy A24 representative v2 pilot observation (2026-09-10)

This is a single-device, 40-image pilot on one Galaxy A24 SM-A245N. The representative set is the
ten-class Imagenette subset, so these results are not full-ImageNet accuracy and must not be
generalized to other datasets or devices. Both runs used the FLOAT32 MobileNet V1 model
(`D95B3C5EA86750CEF882FA867CA357DFE4D265D0B80B67E83277A0BDA310CFBB`), a four-thread CPU
reference, host-verified 31/31 full GPU delegation, `output-equivalence-v3`, and
`representative-equivalence-v2`. The representative policy SHA-256 was
`428a1c1e60623293301929c66315c8bd7603fb87c1a620b0116cf328064353c5`. Neither manifest claims
that FP16 kernels actually executed: the LiteRT API does not expose that fact.

| Result | `gpu-compat-default-v1` | `gpu-fp32-strict-v1` |
|---|---:|---:|
| Experiment status | `failed` | `completed` |
| Execution integrity | `passed` | `passed` |
| Equivalence acceptance | `failed` | `passed` |
| Representative input count | 40 | 40 |
| Combined-tolerance mismatches | 270 / 40,040 | 0 / 40,040 |
| Non-finite outputs | 0 | 0 |
| Top-1 match | 39/40 | 40/40 |
| Top-5 set match | 34/40 | 40/40 |
| Top-5 overlap applicability | 36 applicable, 4 boundary-tie non-applicable | 40 applicable, 0 non-applicable |
| Minimum applicable Top-5 overlap | 4 | 5 |
| Minimum cosine similarity | 0.9993347908387198 | 0.9999999999732401 |
| Maximum total variation distance | 0.023043160735051908 | 0.00000381630014036766 |
| CPU/GPU task Top-1 accuracy | 0.75 / 0.75 | 0.75 / 0.75 |
| CPU/GPU task Top-5 accuracy | 0.95 / 0.925 | 0.95 / 0.95 |

The compatibility-profile failure was not an execution error. Container, preprocessing, model,
shape, dtype, artifact, finite-output, host binary, and full-delegation checks passed, so
`execution_integrity_status=passed`. The required representative gate correctly blocked the
experiment because one Top-1 result differed and the maximum total variation exceeded the fixed
0.02 limit; those are the recorded failure reasons. The four exact rank-5/rank-6 boundary ties were
excluded from the minimum-overlap calculation and were not failure reasons. Although task accuracy
is nonblocking for `backend-performance-formal`, representative equivalence is blocking. The
preflight therefore stopped this experiment before its timed slot, and no compatibility-profile
latency may be reported from this run.

The strict-profile run passed representative equivalence, execution integrity, and equivalence
acceptance. Its timed run also recorded `validation.valid=true`, `formal_gpu_valid=true`, 76
inferences, mean latency 131.60027836842104 ms, and p95 latency 137.1779235 ms. This supports only
the conclusion that the strict profile met this pilot's conservative equivalence policy. It does
not establish a general device result or a full-dataset accuracy difference. A formal performance
comparison between compatibility and strict profiles still requires repeated runs under matched
experimental conditions and statistical analysis. No threshold was relaxed or fitted to these
observations.

`tools/d1_representative_tensors.py` creates `d1-representative-tensor-set-v1` without downloading
anything. The binary layout is eight-byte magic `D1TSET01`, little-endian uint32 JSON-header length,
the canonical UTF-8 JSON header, then contiguous little-endian FLOAT32 tensor payloads. The header
contains dataset name/version/split/scope/source/license, class-stratified selection seed and IDs,
source-image hashes, WNIDs and background-offset output indexes, label-map hash, preprocessing
configuration/hash, RGB/EXIF/crop/resize/normalization details, shape/dtype/endian, offsets, and
per-tensor plus payload hashes. The complete container hash is recorded by the host validator and
passed separately with the runner Intent. Android validates that external container hash,
preprocessing hash, payload/per-tensor hashes, and every structural boundary before constructing either
interpreter. JPEG decoding/resizing and raw-image storage do not occur in the APK or timed run.
Pillow's exact version and bilinear rule are provenance; byte identity with TensorFlow's bilinear
kernel is explicitly not claimed.

For `d1-representative-tensor-set-v1`, the preprocessing configuration hash is SHA-256 of the
configuration object after removing only its top-level `configuration_sha256` member, serialized
as UTF-8 JSON with recursively sorted keys, no insignificant whitespace, literal non-ASCII UTF-8,
and Python-compatible string escaping (in particular `/` is not escaped). JSON integers remain
integers and decimal values such as `-1.0` remain decimals. Exponent-form floating values are not
permitted by the v1 preprocessing contract. Android hashes the parsed object directly; it must not
round-trip it through `JSONObject.toString()`, which can change number spelling and slash escaping.
The representative Intent carries both the expected whole-container SHA-256 and the expected
preprocessing-configuration SHA-256. A mismatch reports declared, expected, and recomputed hashes;
neither check is bypassed. Existing correctly generated v1 containers remain valid without schema
conversion.

Prepare a local Imagenette validation tree (`val/<WNID>/*`) and an official TF-Slim-order file with
exactly 1,000 unique WNIDs, then run (no internet download is performed):

~~~powershell
python tools/d1_representative_tensors.py `
  --dataset-dir "C:\datasets\imagenette2-320" `
  --label-map "C:\datasets\imagenet_lsvrc_2015_synsets.txt" `
  --sample-count 40 --seed 305419896 `
  --dataset-version "imagenette2-320" `
  --dataset-license "Imagenette distribution terms; verify upstream dataset/source-image licenses" `
  --output "C:\datasets\d1-imagenette-val40.d1tset"
python tools/d1_representative_tensors.py --validate "C:\datasets\d1-imagenette-val40.d1tset"
~~~

`--accuracy-validation-scope` selects `thermal-only-pilot`, `backend-performance-formal`, or
`accuracy-preserving-formal`. Pilot defaults to optional thermal-only synthetic smoke and may use
`--accuracy-preflight off`. Formal defaults to required backend equivalence and requires
`--representative-tensor-set`. The preflight runs before D1Check `START_RUN` and thermal
conditioning, uses independent CPU/GPU interpreter lifecycles, force-stops the runner afterward,
and then requires conditioning anew. It never shares buffers/interpreters with timed latency work.

Resume reuses only a passed schema-v2 result when device fingerprint, model and LiteRT versions,
GPU profile hash, comparator/input-set version, seed/tolerance, representative container/payload,
label-map and preprocessing hashes, and both policy hashes match. Every result, JSONL, interleaved
CPU/GPU output binary, and delegate log hash must still verify. Otherwise it reruns; legacy v1
status is preserved and never upgraded to passed. The output binary remains
`D1EQV001 + uint32 input_count + uint32 output_count + interleaved CPU/GPU FLOAT32 arrays`.

~~~powershell
python tools/d1_experiment_orchestrator.py `
  --serial <A24-IP:PORT> --mode formal --resources CPU GPU `
  --cpu-thread-levels 1 2 4 --duty-cycles 25 50 75 100 `
  --duration 600 --warmup 20 --repeat 5 --seed 20260910 `
  --accuracy-preflight required --accuracy-validation-scope backend-performance-formal `
  --representative-tensor-set "C:\datasets\d1-imagenette-val40.d1tset" `
  --gpu-profile gpu-compat-default-v1 `
  --accuracy-input-count 32 --accuracy-seed 305419896 `
  --accuracy-atol 0.0001 --accuracy-rtol 0.001 `
  --start-policy stable --cooling-policy stable `
  --output-dir results/A24_formal_equivalence
~~~

`energy_measurement.status=raw_unverified`, both unit-verification flags are false, and
`calculation_performed=false`. Current is never scaled or integrated, and no J or mWh value is
emitted. Calibrated device-battery energy remains future work.

## Thermal model dataset export

A successfully completed orchestrator plan automatically rebuilds schema-v2 `exports-v2/` from the complete
manifest. The same deterministic export can be run independently, including for an older or
failed experiment:

~~~powershell
python tools/d1_thermal_dataset.py `
  --experiment-dir "C:\Users\LG\Documents\D1Check_A24_matrix_stable_pilot_20260909_214158" `
  --output-dir "$env:TEMP\d1check-export-v2"
~~~

The exporter treats `experiment_manifest.json`, each available `merged/summary.json`, and
`raw/thermalservice.jsonl` as read-only authoritative thermal inputs. For a pre-schema-v2 summary,
it reads the matching runner `run_metadata` only to recover explicitly recorded GPU-profile
provenance; it never infers a missing profile. Thermal `mono_ns` and the summary's
`run_start_mono_ns`, `load_start_mono_ns`, `load_end_mono_ns`, and `run_stop_mono_ns` all use the
Android elapsed-realtime monotonic domain. UTC and host-monotonic timestamps are provenance only
and are never used for alignment. Per-sample ADB uptime-bracketing uncertainty is retained.

For every endpoint, only `parse_status=ok` samples with finite AP/BAT/PA/SKIN values are eligible.
The latest sample at or before the target is selected. Only `run_start` may fall back to the first
sample after its target when no prior sample exists. Signed and absolute offsets, selection method,
and sampling uncertainty are exported. The default absolute-offset limit is 2,000 ms; a farther
sample is labeled `too_far` and its temperature is left null.

Timeseries phases are non-overlapping half-open Android-monotonic intervals:

- baseline: `[run_start_mono_ns, load_start_mono_ns)`
- load: `[load_start_mono_ns, load_end_mono_ns)`
- cooling: `[load_end_mono_ns, run_stop_mono_ns)`

Valid raw samples outside that run envelope are not assigned an invented phase. The dataset
manifest separately records raw, valid-unique, phase-assigned, and outside/unassignable counts;
the timeseries row count equals the phase-assigned valid count. This distinction matters because
logger startup/shutdown races can produce a valid sample just outside `run_start` or `run_stop`.

`exports-v2/run_summary.csv` inventories every manifest slot, including failed and pending slots.
`exports-v2/phase_temperature_summary.csv` has four sensor rows per slot and contains endpoints,
changes, extrema, peaks, peak time, and selection quality. `exports-v2/thermal_timeseries.csv` contains
one row per phase-assigned valid sample. `exports-v2/dataset_manifest.json` records source-manifest
SHA-256, row and eligibility counts, exclusion reasons, clock/selection definitions, and SHA-256
for every CSV.
Experiment-level schema-v2 validation is copied without loss to `dataset_manifest.json`.
`run_summary.csv` has separate synthetic, representative, task-accuracy, and formal-gate status
columns while retaining the legacy aggregate status column. Schema-v1 failures are labeled as
legacy synthetic provenance and are not reinterpreted; older `not_run` remains `not_run`.

Thermal dataset schema v2 adds execution-profile provenance to all three CSVs:
`execution_profile_type`, profile ID/configuration SHA-256, precision-loss permission, inference
preference, forced backend, and the separately stated actual-FP16-execution status. CPU rows use
`cpu_not_applicable` and leave GPU-only cells empty. GPU profile identity is read from timed
`run_metadata` and checked against experiment config and accuracy-preflight cache provenance;
mismatches invalidate the run. A legacy GPU run with no explicit profile remains
`gpu_legacy_missing`—the exporter never guesses the compatibility profile. The dataset manifest's
`gpu_delegate_profile_inventory` separates each ID+hash and records per-profile run, phase-row,
and timeseries-row counts plus legacy-missing/invalid counts. Thus compatibility and strict GPU
runs cannot silently appear as one execution profile.

Default thermal-model eligibility requires completed slot status, `validation.valid=true`, formal
thermal coverage, a passing run envelope, all phase timestamps and endpoint selections, and
matching resource/config validation. GPU rows additionally require the preserved
`formal_gpu_valid=true`; CPU `formal_gpu_valid=null` is expected and is not an exclusion. No failed
slot is silently dropped: it remains in `run_summary.csv` with `model_eligible=false` and explicit
JSON exclusion reasons. Null values are never replaced with zero, and a pilot export does not
establish statistical significance.

All files are built and hash-checked in a staging directory before the complete `exports-v2/`
directory is swapped into place. Re-running replaces the export rather than appending rows. An
existing schema-v1 `exports/` directory is deliberately left untouched. `--output-dir` can place
the atomic export outside the source experiment for read-only validation. An
export failure leaves raw/merged/manifest inputs untouched, preserves the previous successful
export when replacement fails, records a `postprocessing` error in the experiment manifest when
invoked by the orchestrator, and prints the independent regeneration command.
