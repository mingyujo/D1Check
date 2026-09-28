#!/usr/bin/env python3
"""npu-runner chain mode (P2, 2026-09-28): chain-spec validation and the chain conservation check.

A chain slot runs a list of segments [{accelerator, model, input_spec, duty, duration_s}, ...] in ONE
npu-runner process: one baseline, no force-stop / cooling / safety re-gate between segments. The runner
(npu-runner/src/main/java/NpuChain.kt) marks boundaries in its JSONL with segment_start/segment_end and
chain_transition_start/chain_transition_end instants inside a single load_start..load_end window.

This module is imported by d1_experiment_orchestrator.py (--npu-chain) and can be run on its own:
    py tools/npu_chain.py validate <chain.json>          # canonical form, SHA-256, total seconds
    py tools/npu_chain.py check <runner.jsonl> <chain.json>

Conservation tolerances are fixed here BEFORE any phone chain run exists (only Robolectric output has
been seen). Changing them later needs a new pre-registration note, not an edit.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

SCHEMA = "d1-npu-chain-v1"
MAX_SEGMENTS = 32
MAX_TOTAL_SECONDS = 3600
ACCELERATORS = ("NPU", "CPU", "GPU")
MODEL_PREPARE = ("per_segment", "upfront")
# Host accepts only the LCG specs the orchestrator already uses (the runner accepts a superset).
INPUT_SPECS = ("lcg-unit", "lcg-rgb-127-128", "lcg-rgb-127.5-127.5")
GPU_PRECISIONS = ("DEFAULT", "FP16", "FP32", "FP16_WITH_FP32_ACCUM")
AOT_MARKER = "_Samsung_E9965"
TOP_KEYS = {"schema", "chain_id", "model_prepare", "segments"}
SEGMENT_KEYS = {
    "accelerator", "model", "model_path", "input_spec", "duty", "duration_s", "warmup",
    "gpu_precision", "label",
}
ID_RE = re.compile(r"[A-Za-z0-9_.-]{1,64}")
LABEL_RE = re.compile(r"[A-Za-z0-9_.-]{0,64}")

# ---- conservation tolerances (pre-registered 2026-09-28, before any device chain run) ----
# Bookkeeping between windows (an instant() + a JSON detail + a DutyCycleTracker) is sub-millisecond
# on a JVM; 50 ms per boundary absorbs a GC pause or scheduler preemption on the phone [E].
BOUNDARY_GAP_TOLERANCE_NS = 50_000_000
# A transition window must be explained by the spans recorded inside it (model close/init, warmups).
TRANSITION_EXPLAINED_TOLERANCE_NS = 50_000_000
# Telemetry samples (d1check / thermalservice) inside the load window: no gap > 3x the median interval,
# the same rule as sim/스로틀곡선_사전등록_0928.md 1-6 #3.
TELEMETRY_GAP_FACTOR = 3.0


class ChainSpecError(ValueError):
    pass


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def validate_spec(spec: Any) -> dict[str, Any]:
    """Host mirror of NpuChainSpec.parse (fail closed). Returns a summary of the chain."""
    if not isinstance(spec, dict):
        raise ChainSpecError("chain must be a JSON object")
    unknown = sorted(set(spec) - TOP_KEYS)
    if unknown:
        raise ChainSpecError(f"chain has unknown keys {unknown}")
    if spec.get("schema") != SCHEMA:
        raise ChainSpecError(f"schema must be {SCHEMA}")
    if not isinstance(spec.get("chain_id"), str) or not ID_RE.fullmatch(spec["chain_id"]):
        raise ChainSpecError("chain_id must match [A-Za-z0-9_.-]{1,64}")
    if spec.get("model_prepare") not in MODEL_PREPARE:
        raise ChainSpecError("model_prepare must be per_segment or upfront (recorded; no default)")
    segments = spec.get("segments")
    if not isinstance(segments, list) or not 1 <= len(segments) <= MAX_SEGMENTS:
        raise ChainSpecError(f"segments must be a list of 1..{MAX_SEGMENTS}")
    total = 0
    for index, segment in enumerate(segments):
        where = f"segment {index}"
        if not isinstance(segment, dict):
            raise ChainSpecError(f"{where} must be an object")
        unknown = sorted(set(segment) - SEGMENT_KEYS)
        if unknown:
            raise ChainSpecError(f"{where} has unknown keys {unknown}")
        accelerator = segment.get("accelerator")
        if accelerator not in ACCELERATORS:
            raise ChainSpecError(f"{where} accelerator must be one of {ACCELERATORS} (one, not a list)")
        if ("model" in segment) == ("model_path" in segment):
            raise ChainSpecError(f"{where} needs exactly one of model / model_path")
        source = segment.get("model", segment.get("model_path"))
        if "model" in segment and not (
            isinstance(source, str) and source.startswith("models/") and source.endswith(".tflite")
        ):
            raise ChainSpecError(f"{where} model must be models/*.tflite")
        if "model_path" in segment and not (
            isinstance(source, str) and source.startswith("/") and source.endswith(".tflite")
        ):
            raise ChainSpecError(f"{where} model_path must be an absolute *.tflite path")
        if (AOT_MARKER in source) != (accelerator == "NPU"):
            raise ChainSpecError(
                f"{where}: AOT (*{AOT_MARKER}*) models are NPU-only and NPU needs an AOT model ({source})"
            )
        if segment.get("input_spec") not in INPUT_SPECS:
            raise ChainSpecError(f"{where} input_spec must be one of {INPUT_SPECS}")
        if not _is_int(segment.get("duty")) or not 1 <= segment["duty"] <= 100:
            raise ChainSpecError(f"{where} duty must be an integer 1..100")
        if not _is_int(segment.get("duration_s")) or not 1 <= segment["duration_s"] <= MAX_TOTAL_SECONDS:
            raise ChainSpecError(f"{where} duration_s must be an integer 1..{MAX_TOTAL_SECONDS}")
        if "warmup" in segment and (not _is_int(segment["warmup"]) or not 0 <= segment["warmup"] <= 10_000):
            raise ChainSpecError(f"{where} warmup must be an integer 0..10000")
        if "gpu_precision" in segment and (
            accelerator != "GPU" or segment["gpu_precision"] not in GPU_PRECISIONS
        ):
            raise ChainSpecError(f"{where} gpu_precision is GPU-only, one of {GPU_PRECISIONS}")
        if "label" in segment and (
            not isinstance(segment["label"], str) or not LABEL_RE.fullmatch(segment["label"])
        ):
            raise ChainSpecError(f"{where} label must match [A-Za-z0-9_.-]{{0,64}}")
        total += segment["duration_s"]
    if not 1 <= total <= MAX_TOTAL_SECONDS:
        raise ChainSpecError(f"sum of segment durations must be 1..{MAX_TOTAL_SECONDS} s (got {total})")
    return {"segment_count": len(segments), "total_duration_s": total}


def canonical_json(spec: dict[str, Any]) -> str:
    """The exact text sent to the runner (key order as written, ASCII, no spaces)."""
    return json.dumps(spec, ensure_ascii=True, separators=(",", ":"))


def load_chain(path: Path) -> dict[str, Any]:
    raw = Path(path).read_bytes()
    try:
        spec = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ChainSpecError(f"chain file is not UTF-8 JSON: {error}") from error
    summary = validate_spec(spec)
    text = canonical_json(spec)
    return {
        "schema": SCHEMA,
        "chain_id": spec["chain_id"],
        "model_prepare": spec["model_prepare"],
        "spec": spec,
        "canonical_json": text,
        "sha256": hashlib.sha256(text.encode("ascii")).hexdigest(),
        "b64": base64.b64encode(text.encode("ascii")).decode("ascii"),
        "source_file": str(Path(path).resolve()),
        "source_file_sha256": hashlib.sha256(raw).hexdigest(),
        **summary,
    }


# ------------------------------------------------------------------ conservation check

def _detail(event: dict[str, Any]) -> dict[str, Any]:
    value = event.get("detail")
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value) if isinstance(value, str) else None
    except json.JSONDecodeError:
        parsed = None
    return parsed if isinstance(parsed, dict) else {}


def scheduled_active_ns(duty: int, period_ns: int, duration_ns: int) -> int:
    """Same arithmetic as DutyCycleTracker.scheduledActiveDuration (npu-runner NpuDutyCycle.kt)."""
    if duty == 100:
        return duration_ns
    active = max(1, (period_ns // 100) * duty + (period_ns % 100) * duty // 100)
    return (duration_ns // period_ns) * active + min(duration_ns % period_ns, active)


def check_chain(
    events: list[dict[str, Any]],
    expected_spec: dict[str, Any],
    expected_sha256: str | None = None,
    telemetry_mono_ns: list[int] | None = None,
) -> dict[str, Any]:
    """Falsifiable-experiments §8 conservation for one chain slot. Every check is a bool; passed = all.

    events: the runner JSONL (run_metadata first). telemetry_mono_ns: optional d1check/thermalservice
    sample times of the same run (then the load-window telemetry-gap check runs too).
    """
    checks: dict[str, bool] = {}
    notes: list[str] = []
    metadata = next((e for e in events if e.get("event") == "run_metadata"), {})
    footer = next((e for e in reversed(events) if e.get("event") == "file_summary"), {})
    segments_spec = expected_spec.get("segments", [])
    n = len(segments_spec)

    # 1. the chain the runner recorded is the chain the host sent
    checks["spec_roundtrip"] = metadata.get("chain_spec") == expected_spec
    checks["sha_roundtrip"] = expected_sha256 is None or metadata.get("chain_sha256") == expected_sha256
    checks["chain_mode_flag"] = metadata.get("chain_mode") is True

    starts = [e for e in events if e.get("event") == "segment_start"]
    ends = [e for e in events if e.get("event") == "segment_end"]
    t_starts = [e for e in events if e.get("event") == "chain_transition_start"]
    t_ends = [e for e in events if e.get("event") == "chain_transition_end"]
    load_starts = [e for e in events if e.get("event") == "load_start"]
    load_ends = [e for e in events if e.get("event") == "load_end"]
    checks["single_load_window"] = len(load_starts) == 1 and len(load_ends) == 1

    # 2. start/end pairs, count and order equal the spec
    s_detail = [_detail(e) for e in starts]
    e_detail = [_detail(e) for e in ends]
    checks["segment_count"] = len(starts) == len(ends) == n
    checks["segment_order"] = (
        [d.get("index") for d in s_detail] == list(range(n))
        and [d.get("index") for d in e_detail] == list(range(n))
    )
    fields_match = len(s_detail) == n
    for index, (spec_segment, detail) in enumerate(zip(segments_spec, s_detail)):
        expected_model = spec_segment.get("model", spec_segment.get("model_path"))
        same = (
            detail.get("accelerator") == spec_segment.get("accelerator")
            and detail.get("model") == expected_model
            and detail.get("input_spec") == spec_segment.get("input_spec")
            and detail.get("duty") == spec_segment.get("duty")
            and detail.get("duration_s") == spec_segment.get("duration_s")
        )
        if not same:
            notes.append(f"segment {index} start detail differs from the spec: {detail}")
        fields_match = fields_match and same
    checks["segment_fields_match_spec"] = fields_match
    checks["segment_duty_request"] = len(e_detail) == n and all(
        d.get("requested_duty_cycle_percent") == s.get("duty") for d, s in zip(e_detail, segments_spec)
    )
    checks["segments_completed"] = len(e_detail) == n and all(
        d.get("termination_reason") == "duration_complete" for d in e_detail
    )
    # per-segment duty identities (what validate_result checks once for a single-duty slot)
    period_ns = metadata.get("duty_cycle_period_ns")
    duty_ok = len(e_detail) == n and _is_int(period_ns) and period_ns > 0
    for detail, spec_segment in zip(e_detail, segments_spec):
        active, idle, actual = (detail.get(k) for k in (
            "actual_active_duration_ns", "actual_idle_duration_ns", "actual_duration_ns"))
        achieved = detail.get("achieved_duty_cycle_percent")
        duty = spec_segment.get("duty")
        target = spec_segment.get("duration_s", 0) * 1_000_000_000
        duty_ok = duty_ok and all(_is_int(v) for v in (active, idle, actual)) and (
            active + idle == actual
            and isinstance(achieved, (int, float))
            and abs(achieved - (active * 100.0 / actual if actual else 0.0)) <= 1e-9
            and (idle == 0 if duty == 100 else idle > 0)
            and detail.get("target_active_duration_ns") == scheduled_active_ns(duty, period_ns, target)
        )
    checks["segment_duty_identities"] = duty_ok
    checks["transition_count"] = len(t_starts) == len(t_ends) == max(0, n - 1)

    # 3. time: ordered, no overlap, Σ segments + Σ transitions = load window (± declared tolerance)
    try:
        load0 = int(load_starts[0]["mono_ns"])
        load1 = int(load_ends[0]["mono_ns"])
        seg = [(int(s["start_ns"]), int(e["end_ns"])) for s, e in zip(s_detail, e_detail)]
        trans = [(int(_detail(a)["start_ns"]), int(_detail(b)["end_ns"])) for a, b in zip(t_starts, t_ends)]
        timeline = [load0]
        for k, (s0, s1) in enumerate(seg):
            if k > 0:
                timeline += list(trans[k - 1])
            timeline += [s0, s1]
        timeline.append(load1)
        checks["no_overlap"] = all(a <= b for a, b in zip(timeline, timeline[1:])) and all(
            s0 < s1 for s0, s1 in seg
        )
        gaps = [timeline[i + 1] - timeline[i] for i in range(0, len(timeline) - 1, 2)]
        checks["boundary_gaps_within_tolerance"] = all(0 <= g <= BOUNDARY_GAP_TOLERANCE_NS for g in gaps)
        segment_ns = sum(b - a for a, b in seg)
        transition_ns = sum(b - a for a, b in trans)
        window_ns = load1 - load0
        residual = window_ns - segment_ns - transition_ns
        checks["time_conservation"] = 0 <= residual <= BOUNDARY_GAP_TOLERANCE_NS * len(gaps)
        # segment/transition totals come from the same detail timestamps -> exact. The load window in
        # metadata is captured next to (not inside) the load_start/load_end instants -> boundary tolerance.
        load_metadata = metadata.get("actual_load_duration_ns")
        checks["metadata_time_totals"] = (
            metadata.get("chain_segment_total_ns") == segment_ns
            and metadata.get("chain_transition_total_ns") == transition_ns
            and _is_int(load_metadata)
            and abs(load_metadata - window_ns) <= BOUNDARY_GAP_TOLERANCE_NS
        )
        notes.append(
            f"load window {window_ns} ns = segments {segment_ns} + transitions {transition_ns} "
            f"+ residual {residual} ns (tolerance {BOUNDARY_GAP_TOLERANCE_NS * len(gaps)} ns)"
        )
    except (IndexError, KeyError, TypeError, ValueError) as error:
        seg, trans = [], []
        for key in ("no_overlap", "boundary_gaps_within_tolerance", "time_conservation", "metadata_time_totals"):
            checks[key] = False
        notes.append(f"timeline incomplete: {error!r}")

    # 4. inferences: Σ per segment = total, every inference inside its segment, indexes contiguous
    inferences = [e for e in events if e.get("event") == "inference"]
    counts = [d.get("inference_count") for d in e_detail]
    checks["inference_conservation"] = (
        all(_is_int(c) for c in counts)
        and sum(counts) == len(inferences)
        == metadata.get("completed_inference_count")
        == footer.get("inference_span_count")
    )
    inside = bool(seg) and len(seg) == len(counts)
    if inside:
        cursor = 0
        by_segment = [0] * len(seg)
        for event in sorted(inferences, key=lambda e: int(e["start_mono_ns"])):
            start, end = int(event["start_mono_ns"]), int(event["mono_ns"])
            while cursor < len(seg) and start >= seg[cursor][1]:
                cursor += 1
            if cursor >= len(seg) or not (seg[cursor][0] <= start and end <= seg[cursor][1]):
                inside = False
                break
            by_segment[cursor] += 1
        inside = inside and by_segment == counts
    checks["inferences_inside_their_segment"] = inside
    firsts = [d.get("first_inference_index") for d in e_detail]
    expected_firsts = [sum(counts[:k]) for k in range(len(counts))] if all(_is_int(c) for c in counts) else None
    indexes = sorted(int(e["inference_index"]) for e in inferences)
    checks["inference_index_contiguous"] = firsts == expected_firsts and indexes == list(range(len(inferences)))

    # 5. transitions are explained by the spans recorded inside them (no silent gap at a boundary)
    explained = len(trans) == max(0, n - 1)
    for a, b in trans:
        inside_spans = [
            e for e in events
            if e.get("event") in ("chain_model_close", "chain_model_init", "warmup")
            and "start_mono_ns" in e and a <= int(e["start_mono_ns"]) and int(e["mono_ns"]) <= b
        ]
        covered = sum(int(e["mono_ns"]) - int(e["start_mono_ns"]) for e in inside_spans)
        if not 0 <= (b - a) - covered <= TRANSITION_EXPLAINED_TOLERANCE_NS:
            explained = False
            notes.append(f"transition [{a},{b}] covered {covered} ns of {b - a} ns")
    checks["transitions_explained"] = explained

    # 6. telemetry continuity inside the load window (only when samples are supplied)
    if telemetry_mono_ns is not None and checks["single_load_window"]:
        window = sorted(t for t in telemetry_mono_ns if load0 <= t <= load1)
        intervals = [b - a for a, b in zip(window, window[1:])]
        if len(intervals) >= 3:
            median = sorted(intervals)[len(intervals) // 2]
            checks["telemetry_no_gap_in_load"] = max(intervals) <= TELEMETRY_GAP_FACTOR * median
        else:
            checks["telemetry_no_gap_in_load"] = False
            notes.append("fewer than 4 telemetry samples inside the load window")

    failed = [name for name, value in checks.items() if not value]
    return {
        "passed": not failed,
        "checks": checks,
        "failed_checks": failed,
        "notes": notes,
        "tolerances_ns": {
            "boundary_gap": BOUNDARY_GAP_TOLERANCE_NS,
            "transition_explained": TRANSITION_EXPLAINED_TOLERANCE_NS,
            "telemetry_gap_factor": TELEMETRY_GAP_FACTOR,
        },
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in Path(path).read_text("utf-8").splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("chain", type=Path)
    check = sub.add_parser("check")
    check.add_argument("runner_jsonl", type=Path)
    check.add_argument("chain", type=Path)
    args = parser.parse_args(argv)
    chain = load_chain(args.chain)
    if args.command == "validate":
        print(json.dumps({k: chain[k] for k in (
            "chain_id", "model_prepare", "segment_count", "total_duration_s", "sha256", "canonical_json",
        )}, ensure_ascii=False, indent=2))
        return 0
    report = check_chain(_load_jsonl(args.runner_jsonl), chain["spec"], chain["sha256"])
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ChainSpecError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
