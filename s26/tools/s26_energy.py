"""s26_energy.py -- verify the current unit and build the first energy table.

Every run stores 1 Hz telemetry (current_raw, charge_counter_raw, voltage_mV) in
merged/events.jsonl. This walks every run of an experiment and, per run:

  * integrates current over baseline / load / cooling
  * compares that integral against the charge counter drop over the same window
  * derives load and idle power, and net energy per inference

The ratio (integrated current / charge counter delta) is the unit check. If the
current is reported in microamperes the ratio is close to 1.0. Judge it on the
whole-run window and on the 80-run total, never on a single 60 s phase -- the
charge counter is coarsely quantized and a short window lands between steps.

No J or mWh value from this script goes into the paper until the aggregate
ratio is inside the tolerance the team registered beforehand.

Usage:
    python s26_energy.py <experiment directory> [-o output.csv]

Example:
    python s26_energy.py results\\S26_formal_strict
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path


PHASES = ("baseline", "load", "cooling")


def read_run_index(experiment: Path) -> dict:
    """run_id -> condition fields, taken from exports-v2/run_summary.csv."""
    summary = experiment / "exports-v2" / "run_summary.csv"
    if not summary.is_file():
        return {}
    index = {}
    with summary.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            index[row["run_id"]] = row
    return index


def load_events(path: Path):
    """Return (telemetry samples, load_start_mono_ns, load_end_mono_ns, inference count).

    Most lines are inference records. Prefilter on a substring before paying for
    json.loads, otherwise an 80-run pass takes minutes.
    """
    samples = []
    load_start = load_end = None
    inferences = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if '"inference"' in line:
                inferences += 1
                continue
            if '"d1check"' in line and '"sample"' in line:
                event = json.loads(line)
                if event.get("event") == "sample":
                    samples.append(event)
                continue
            if '"load_start"' in line or '"load_end"' in line:
                event = json.loads(line)
                if event.get("event") == "load_start":
                    load_start = event.get("mono_ns")
                elif event.get("event") == "load_end":
                    load_end = event.get("mono_ns")
    samples.sort(key=lambda e: e["mono_ns"])
    return samples, load_start, load_end, inferences


def integrate(samples: list) -> float:
    """Trapezoidal integral of current_raw over time. Returns raw-units * seconds."""
    total = 0.0
    for first, second in zip(samples, samples[1:]):
        dt = (second["mono_ns"] - first["mono_ns"]) / 1e9
        total += (first["current_raw"] + second["current_raw"]) / 2.0 * dt
    return total


def window(samples: list, start: int, end: int) -> list:
    return [e for e in samples if start <= e["mono_ns"] <= end]


def describe(samples: list) -> dict:
    """Duration, integral, charge counter delta and mean voltage for one window."""
    if len(samples) < 3:
        return {}
    duration = (samples[-1]["mono_ns"] - samples[0]["mono_ns"]) / 1e9
    integral = integrate(samples)
    return {
        "seconds": duration,
        "mean_uA": integral / duration if duration else 0.0,
        "uAh": integral / 3600.0,
        "cc_delta": samples[-1]["charge_counter_raw"] - samples[0]["charge_counter_raw"],
        "mV": statistics.median(e["voltage_mV"] for e in samples if e.get("voltage_mV")),
        "n": len(samples),
    }


def analyse_run(run_dir: Path, meta: dict) -> dict:
    events = run_dir / "merged" / "events.jsonl"
    if not events.is_file():
        return {}
    samples, load_start, load_end, inferences = load_events(events)
    if len(samples) < 10 or load_start is None or load_end is None:
        return {}

    first, last = samples[0]["mono_ns"], samples[-1]["mono_ns"]
    parts = {
        "baseline": describe(window(samples, first, load_start)),
        "load": describe(window(samples, load_start, load_end)),
        "cooling": describe(window(samples, load_end, last)),
        "total": describe(samples),
    }
    if not parts["load"] or not parts["total"]:
        return {}

    row = {
        "run_id": run_dir.name,
        "slot_id": meta.get("slot_id", ""),
        "resource": meta.get("resource", ""),
        "cpu_threads": meta.get("cpu_threads", ""),
        "duty": meta.get("requested_duty_cycle_percent", ""),
        "plugged_any": int(any(e.get("plugged") for e in samples)),
        "current_valid_all": int(all(e.get("current_valid", True) for e in samples)),
        "inferences": inferences,
    }
    for name in ("baseline", "load", "cooling", "total"):
        part = parts[name]
        row["%s_s" % name] = round(part.get("seconds", 0.0), 2)
        row["%s_uAh" % name] = round(part.get("uAh", 0.0), 1)
        row["%s_cc_delta" % name] = part.get("cc_delta", 0)
    row["total_ratio"] = (
        round(parts["total"]["uAh"] / parts["total"]["cc_delta"], 4)
        if parts["total"]["cc_delta"] else ""
    )

    # Power assumes current_raw is in microamperes. That assumption is exactly
    # what the ratio column tests, so treat these as provisional.
    volts = parts["load"]["mV"] / 1000.0
    load_w = abs(parts["load"]["mean_uA"]) * 1e-6 * volts
    idle_w = abs(parts["baseline"]["mean_uA"]) * 1e-6 * volts if parts["baseline"] else 0.0
    row["voltage_mV"] = round(parts["load"]["mV"], 0)
    row["load_W_if_uA"] = round(load_w, 3)
    row["idle_W_if_uA"] = round(idle_w, 3)
    row["net_mJ_per_inference_if_uA"] = (
        round((load_w - idle_w) * parts["load"]["seconds"] / inferences * 1000.0, 2)
        if inferences else ""
    )
    return row


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description="S26 energy unit audit")
    parser.add_argument("experiment", help="experiment directory containing runs/")
    parser.add_argument("-o", "--output", default=None, help="output CSV path")
    args = parser.parse_args(argv[1:])

    experiment = Path(args.experiment)
    runs_dir = experiment / "runs"
    if not runs_dir.is_dir():
        print("[X] no runs/ directory under %s" % experiment)
        return 1

    index = read_run_index(experiment)
    run_dirs = sorted(p for p in runs_dir.iterdir() if p.is_dir())
    print("runs found: %d" % len(run_dirs))
    print("")

    rows = []
    for position, run_dir in enumerate(run_dirs, 1):
        row = analyse_run(run_dir, index.get(run_dir.name, {}))
        if row:
            rows.append(row)
        sys.stdout.write("\r  parsed %d / %d" % (position, len(run_dirs)))
        sys.stdout.flush()
    print("")
    print("")

    if not rows:
        print("[X] no run produced usable telemetry.")
        return 1

    output = Path(args.output) if args.output else experiment / "energy_audit.csv"
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print("wrote %s  (%d rows)" % (output, len(rows)))
    print("")

    # ---- unit verdict -------------------------------------------------
    total_uAh = sum(r["total_uAh"] for r in rows)
    total_cc = sum(r["total_cc_delta"] for r in rows)
    print("=== current unit check (whole experiment) ===")
    print("  integrated current : %12.0f uAh   (assuming current_raw is uA)" % total_uAh)
    print("  charge counter     : %12.0f uAh" % total_cc)
    if total_cc:
        aggregate = total_uAh / total_cc
        print("  ratio              : %.4f    (1.000 = perfect agreement)" % aggregate)
        print("  deviation          : %+.1f %%" % ((aggregate - 1.0) * 100.0))
    per_run = [r["total_ratio"] for r in rows if r["total_ratio"] != ""]
    if per_run:
        print("  per-run ratio      : min %.3f / median %.3f / max %.3f"
              % (min(per_run), statistics.median(per_run), max(per_run)))
    print("")

    plugged = [r for r in rows if r["plugged_any"]]
    invalid = [r for r in rows if not r["current_valid_all"]]
    if plugged:
        print("  [!] %d run(s) saw a charger attached -- exclude before judging." % len(plugged))
    if invalid:
        print("  [!] %d run(s) had current_valid=false samples." % len(invalid))
    if not plugged and not invalid:
        print("  all runs discharging, all current samples valid.")
    print("")

    # ---- provisional cost table ---------------------------------------
    print("=== provisional energy per inference (only valid if the ratio passes) ===")
    print("  %-6s %-4s %-5s %4s  %9s %9s %14s"
          % ("res", "thr", "duty", "n", "load W", "idle W", "net mJ/infer"))
    grouped = {}
    for row in rows:
        key = (row["resource"], row["cpu_threads"] or "-", row["duty"])
        grouped.setdefault(key, []).append(row)
    for key in sorted(grouped):
        group = grouped[key]
        pick = lambda field: statistics.median(
            [r[field] for r in group if r[field] != ""]
        )
        print("  %-6s %-4s %-5s %4d  %9.3f %9.3f %14.2f"
              % (key[0], key[1], key[2], len(group),
                 pick("load_W_if_uA"), pick("idle_W_if_uA"),
                 pick("net_mJ_per_inference_if_uA")))
    print("")
    print("Reminder: these numbers are provisional until the team accepts the")
    print("ratio above against the tolerance registered before the run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
