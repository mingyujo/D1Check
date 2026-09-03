#!/usr/bin/env python3
"""Capture and analyze correlated D1Check v4 and GPU benchmark events."""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


def extract_json(line: str) -> dict[str, Any] | None:
    start = line.find("{")
    if start < 0:
        return None
    try:
        value = json.loads(line[start:])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def capture(output: Path, adb: str, clear: bool) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    if clear:
        subprocess.run([adb, "logcat", "-c"], check=True)
    command = [
        adb,
        "logcat",
        "-v",
        "raw",
        "D1CHECK_EVENT:I",
        "D1GPU:I",
        "*:S",
    ]
    print(f"capturing to {output}; stop with Ctrl-C", file=sys.stderr)
    try:
        with output.open("a", encoding="utf-8", newline="\n") as stream:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=sys.stderr,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            assert process.stdout is not None
            for line in process.stdout:
                event = extract_json(line)
                if event is None:
                    continue
                encoded = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
                stream.write(encoded + "\n")
                stream.flush()
                print(encoded)
    except KeyboardInterrupt:
        process.terminate()
        process.wait(timeout=5)
        return 0
    return process.wait()


def load_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            event = extract_json(line)
            if event is not None and "run_id" in event and "mono_ns" in event:
                events.append(event)
            elif line.strip():
                print(f"warning: ignored non-event line {line_number}", file=sys.stderr)
    return events


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def latency_stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "mean_ms": None, "median_ms": None, "p95_ms": None}
    return {
        "count": len(values),
        "mean_ms": statistics.fmean(values),
        "median_ms": statistics.median(values),
        "p95_ms": percentile(values, 0.95),
        "min_ms": min(values),
        "max_ms": max(values),
    }


def choose_run(events: list[dict[str, Any]], requested: str | None) -> str:
    if requested:
        if not any(event.get("run_id") == requested for event in events):
            raise ValueError(f"run_id not found: {requested}")
        return requested
    if not events:
        raise ValueError("no structured events found")
    # Capture order remains valid across device reboots; monotonic values do not.
    return str(events[-1]["run_id"])


def nearest_sample(
    samples: list[dict[str, Any]], sample_times: list[int], mono_ns: int
) -> dict[str, Any] | None:
    if not samples:
        return None
    index = bisect.bisect_left(sample_times, mono_ns)
    candidates = [candidate for candidate in (index - 1, index) if 0 <= candidate < len(samples)]
    best = min(candidates, key=lambda candidate: abs(sample_times[candidate] - mono_ns))
    return samples[best]


def write_jsonl(path: Path, events: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for event in events:
            stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


def analyze(input_path: Path, output_dir: Path, requested_run: str | None) -> None:
    all_events = load_events(input_path)
    run_id = choose_run(all_events, requested_run)
    events = sorted(
        (event for event in all_events if event.get("run_id") == run_id),
        key=lambda event: (int(event["mono_ns"]), int(event.get("sequence", -1))),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "merged.jsonl", events)

    samples = [
        event
        for event in events
        if event.get("source") == "d1check" and event.get("event") == "sample"
    ]
    sample_times = [int(sample["mono_ns"]) for sample in samples]
    gpu_completed = [
        event
        for event in events
        if event.get("source") == "gpu"
        and event.get("event") in {"inference_end", "batch_end"}
        and event.get("latency_ms") is not None
    ]

    start_ns = min(int(event["mono_ns"]) for event in events)
    timeline_fields = [
        "run_id",
        "sequence",
        "event",
        "inference_index",
        "batch_size",
        "start_mono_ns",
        "end_mono_ns",
        "elapsed_s",
        "latency_ms",
        "sample_delta_ms",
        "headroom_now",
        "headroom_60s",
        "thermal_status",
        "current_raw",
        "voltage_mV",
        "battery_temp_C",
    ]
    with (output_dir / "latency_timeline.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=timeline_fields)
        writer.writeheader()
        for event in gpu_completed:
            mono_ns = int(event["mono_ns"])
            sample = nearest_sample(samples, sample_times, mono_ns)
            row = {
                "run_id": run_id,
                "sequence": event.get("sequence"),
                "event": event.get("event"),
                "inference_index": event.get("inference_index"),
                "batch_size": event.get("batch_size"),
                "start_mono_ns": event.get("start_mono_ns"),
                "end_mono_ns": mono_ns,
                "elapsed_s": (mono_ns - start_ns) / 1_000_000_000.0,
                "latency_ms": event.get("latency_ms"),
            }
            if sample is not None:
                row["sample_delta_ms"] = (mono_ns - int(sample["mono_ns"])) / 1_000_000.0
                for key in timeline_fields[10:]:
                    row[key] = sample.get(key)
            writer.writerow(row)

    grouped: defaultdict[str, list[float]] = defaultdict(list)
    for event in events:
        if event.get("source") == "gpu" and event.get("latency_ms") is not None:
            grouped[str(event.get("event"))].append(float(event["latency_ms"]))
    summary = {
        "schema_version": 1,
        "run_id": run_id,
        "event_count": len(events),
        "telemetry_sample_count": len(samples),
        "gpu_timeline_count": len(gpu_completed),
        "latency": {name: latency_stats(values) for name, values in sorted(grouped.items())},
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    capture_parser = subparsers.add_parser("capture", help="capture structured adb logcat events")
    capture_parser.add_argument("output", type=Path)
    capture_parser.add_argument("--adb", default="adb")
    capture_parser.add_argument("--clear", action="store_true")
    analyze_parser = subparsers.add_parser("analyze", help="merge one run and produce statistics")
    analyze_parser.add_argument("input", type=Path)
    analyze_parser.add_argument("output_dir", type=Path)
    analyze_parser.add_argument("--run-id")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "capture":
        return capture(args.output, args.adb, args.clear)
    try:
        analyze(args.input, args.output_dir, args.run_id)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
