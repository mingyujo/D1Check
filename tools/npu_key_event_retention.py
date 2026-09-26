"""Key-event retention for one captured run (read-only).

Whole-line retention (e.g. 98.8 %) is dominated by tens of thousands of `inference` lines and says
nothing about whether the few events that carry the evidence survived. This splits the two:

  key events  : every non-inference runner event (run_metadata, baseline_*, npu_artifact_hash,
                compiled_model_init, warmup, load_start/load_end, run_only_summary, shutdown,
                file_summary). Ground truth = runner JSONL (gpu/*.jsonl); a logcat D1GPU copy counts
                when the same (event, sequence) appears in raw/logcat.txt.
  inferences  : same matching, reported separately.
  markers     : litert/tflite lines have no ground-truth count. They are reported as presence of an
                expected-marker list (taken from successful G4/formal runs) -- NOT a retention ratio.

Usage: py tools/npu_key_event_retention.py <run_dir> [<run_dir> ...]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

LINE = re.compile(r"^\S+ \S+\s+(\d+)\s+(\d+) ([VDIWEF]) (\S+?)\s*: ?(.*)$")
# Expected once per successful NPU run (observed in the 2026-09-25 formal 20 runs).
NPU_MARKERS = {
    "runtime_loaded": r"Loaded runtime library",
    "npu_accelerator_registered": r"NPU accelerator registered",
    "dispatch_library_loaded": r"\[litert_dispatch\.cc:\d+\] Loading shared library",
    "enn_loaded": r"Loading from: libenn_public_api_cpp\.so",
    "enn_soc_config": r"SetGenAiPerfConfigFromSoc",
    "dispatch_replacing": r"Replacing \d+ out of \d+ node\(s\) with delegate \(DispatchDelegate\)",
    "dispatch_buffer_info": r"Buffer info - inputs",
}
CPU_MARKERS = {"xnnpack_replacing": r"Replacing \d+ out of \d+ node\(s\) with delegate \(TfLiteXNNPackDelegate\)"}
GPU_MARKERS = {
    "gpu_delegate_created": r"Created TensorFlow Lite delegate for GPU",
    "gpu_replacing": r"Replacing \d+ out of \d+ node\(s\) with delegate \(TfLiteGpuDelegateV2\)",
    "gpu_kernels_created": r"Created \d+ GPU delegate kernels",
}


def analyse(run_dir: Path) -> dict:
    runner = sorted((run_dir / "gpu").glob("*.jsonl"))
    if not runner:
        return {"run_dir": str(run_dir), "error": "no runner jsonl"}
    truth = [json.loads(line) for line in runner[0].read_text("utf-8").splitlines() if line.strip()]
    copies = set()
    other = []
    for raw in (run_dir / "raw" / "logcat.txt").read_text("utf-8", errors="replace").splitlines():
        m = LINE.match(raw)
        if not m:
            continue
        tag, message = m.group(4), m.group(5)
        if tag == "D1GPU":
            ev = re.search(r'"event":"([a-z_]+)"', message)
            seq = re.search(r'"sequence":(\d+)', message)
            if ev:
                copies.add((ev.group(1), int(seq.group(1)) if seq else None))
        elif tag != "D1CHECK_EVENT":
            other.append(message)

    def found(e):
        return (e["event"], e.get("sequence")) in copies or (e.get("sequence") in (None, 0) and (e["event"], None) in copies)

    key = [e for e in truth if e.get("event") != "inference"]
    inf = [e for e in truth if e.get("event") == "inference"]
    key_missing = [f'{e["event"]}#{e.get("sequence")}' for e in key if not found(e)]
    inf_kept = sum(found(e) for e in inf)
    resource = next((e.get("resource") for e in truth if e.get("event") == "run_metadata"), None)
    accel = next((e.get("npu_accelerator_requested") for e in truth if e.get("event") == "run_metadata"), None)
    markers = dict(NPU_MARKERS) if resource == "NPU" and accel in (None, "NPU") else {}
    markers.update(GPU_MARKERS if resource == "GPU" else CPU_MARKERS if resource == "CPU" or accel == "CPU" else {})
    text = "\n".join(other)
    return {
        "run_dir": str(run_dir),
        "key_events_expected": len(key),
        "key_events_found": len(key) - len(key_missing),
        "key_events_missing": key_missing,
        "inferences_expected": len(inf),
        "inferences_found": inf_kept,
        "inference_retention": inf_kept / len(inf) if inf else None,
        "expected_markers_present": {k: bool(re.search(p, text)) for k, p in markers.items()},
        "marker_note": "presence against an expected list; no ground-truth count exists for these tags",
    }


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    for arg in argv:
        print(json.dumps(analyse(Path(arg)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
