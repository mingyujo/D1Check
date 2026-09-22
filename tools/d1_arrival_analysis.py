"""Read-only raw-artifact analysis for arrival-scheduler-v1 development sessions."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from tools import d1_arrival_plan as p


def nearest_p95(values):
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1] if ordered else None


def session_metrics(entry, folder):
    summary_path = folder / "artifacts" / "summary.json"
    requests_path = folder / "artifacts" / "requests.json"
    if not summary_path.exists() or not requests_path.exists():
        return dict(index=entry["index"], session_id=entry["session_id"], status="missing_or_partial")
    summary, requests = p.read(summary_path), p.read(requests_path)
    if summary["session_id"] != entry["session_id"] or len(requests) != entry["request_count"]:
        raise ValueError(f"ledger mismatch: {folder}")
    ids = [row["request_id"] for row in requests]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate request ID")
    for row in requests:
        status = row["terminal_status"]
        if status not in {"succeeded", "failed", "rejected", "expired", "unfinished"}:
            raise ValueError("unknown terminal")
        if status == "succeeded":
            for start, end in (("scheduled_arrival_ns", "actual_arrival_ns"),
                               ("actual_arrival_ns", "queue_entry_ns"),
                               ("queue_entry_ns", "execution_start_ns"),
                               ("execution_start_ns", "output_ready_ns"),
                               ("output_ready_ns", "persist_complete_ns"),
                               ("persist_complete_ns", "worker_release_ns")):
                if row[start] > row[end]:
                    raise ValueError(f"clock order: {row['request_id']} {start}/{end}")
            if row["response_ns"] != row["completion_ns"] - row["scheduled_arrival_ns"]:
                raise ValueError("response mismatch")
            if row["late_success"] != (row["completion_ns"] > row["deadline_ns"]):
                raise ValueError("deadline mismatch")
    urgent = [r for r in requests if r.get("priority") == "urgent"]
    normal = [r for r in requests if r.get("priority") == "normal"]
    successful = [r for r in requests if r["terminal_status"] == "succeeded"]
    urgent_success = [r for r in urgent if r["terminal_status"] == "succeeded"]
    normal_success = [r for r in normal if r["terminal_status"] == "succeeded"]
    last_release = max((r.get("worker_release_ns", r.get("terminal_ns", summary["workload_start_ns"]))
                        for r in requests), default=summary["workload_start_ns"])
    makespan_s = max(0, last_release - summary["workload_start_ns"]) / 1e9
    def on_time(row):
        return row["terminal_status"] == "succeeded" and row["completion_ns"] <= row["deadline_ns"]
    return dict(index=entry["index"], session_id=entry["session_id"], kind=entry["kind"],
                urgent_task=entry["urgent_task"], replicate=entry["replicate"],
                pair_id=entry["pair_id"], policy=entry["policy"], status=summary["status"],
                urgent_completed=len(urgent_success), urgent_arrivals=len(urgent),
                urgent_p95_ms=(nearest_p95([r["response_ns"] for r in urgent_success]) or 0) / 1e6
                    if urgent_success else None,
                urgent_deadline_miss_rate=sum(not on_time(r) for r in urgent) / len(urgent) if urgent else None,
                normal_mean_response_ms=sum(r["response_ns"] for r in normal_success) / len(normal_success) / 1e6
                    if normal_success else None,
                normal_p95_ms=(nearest_p95([r["response_ns"] for r in normal_success]) or 0) / 1e6
                    if normal_success else None,
                normal_on_time_rate=sum(on_time(r) for r in normal) / len(normal) if normal else None,
                completion_rate=len(successful) / len(requests),
                makespan_s=makespan_s, throughput_per_s=len(successful) / makespan_s if makespan_s else None,
                arrival_lag_exceeded=summary["arrival_lag_exceeded"],
                max_arrival_lag_ms=max((r.get("arrival_lag_ns", 0) for r in requests), default=0) / 1e6,
                policy_compute_total_ms=sum(r.get("policy_compute_ns", 0) for r in requests) / 1e6,
                late_success_count=sum(r.get("late_success") is True for r in requests),
                terminal_counts={s: sum(r["terminal_status"] == s for r in requests)
                                 for s in ("succeeded", "failed", "rejected", "expired", "unfinished")})


def gantt_svg(requests, title):
    completed = [r for r in requests if r.get("execution_start_ns") is not None and r.get("worker_release_ns") is not None]
    if not completed:
        return ""
    origin = min(r["scheduled_arrival_ns"] for r in requests)
    end = max(r["worker_release_ns"] for r in completed)
    scale = 860 / max(1, end - origin)
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="150">',
             f'<text x="20" y="22" font-size="16">{title}</text>',
             '<text x="20" y="65">CPU</text><text x="20" y="110">GPU</text>']
    for row in completed:
        x = 100 + (row["execution_start_ns"] - origin) * scale
        width = max(1, (row["worker_release_ns"] - row["execution_start_ns"]) * scale)
        y = 47 if row["selected_backend"] == "CPU" else 92
        color = "#d95f02" if row["priority"] == "urgent" else "#1b9e77"
        parts.append(f'<rect x="{x:.2f}" y="{y}" width="{width:.2f}" height="24" fill="{color}"/>')
    parts.append('</svg>')
    return "".join(parts)


def analyze(plan_file, results, output):
    plan_file, results, output = Path(plan_file), Path(results), Path(output)
    plan = p.read(plan_file)
    p.validate(plan, plan_file.parent)
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    metrics = []
    for entry in plan["entries"]:
        folder = results / f"{entry['index']:02d}_{entry['session_id']}"
        metrics.append(session_metrics(entry, folder))
        if entry["kind"] == "burst" and entry["replicate"] == 0 and entry["urgent_task"] == "classification":
            path = folder / "artifacts" / "requests.json"
            if path.exists():
                (output / f"gantt_{entry['policy']}.svg").write_text(
                    gantt_svg(p.read(path), entry["policy"]), encoding="utf-8")
    (output / "session_kpi.json").write_bytes(p.canonical(metrics))
    with (output / "session_kpi.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = [key for key in metrics[0] if key != "terminal_counts"]
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(metrics)
    paired = []
    for pair_id in sorted({m.get("pair_id") for m in metrics if m.get("pair_id") and m.get("kind") != "smoke"}):
        group = {m["policy"]: m for m in metrics if m.get("pair_id") == pair_id}
        if set(group) != set(p.POLICIES) or any(m["status"] != "completed" for m in group.values()):
            paired.append(dict(pair_id=pair_id, status="incomplete_pair"))
            continue
        base = group["CPU_FIFO"]
        for policy in ("CPU_URGENT", "CONDITIONAL"):
            current = group[policy]
            paired.append(dict(pair_id=pair_id, policy=policy, status="paired",
                               urgent_p95_delta_ms=current["urgent_p95_ms"] - base["urgent_p95_ms"],
                               urgent_miss_delta=current["urgent_deadline_miss_rate"] - base["urgent_deadline_miss_rate"],
                               normal_on_time_delta=current["normal_on_time_rate"] - base["normal_on_time_rate"],
                               makespan_delta_s=current["makespan_s"] - base["makespan_s"],
                               throughput_delta_per_s=current["throughput_per_s"] - base["throughput_per_s"]))
    (output / "paired_kpi.json").write_bytes(p.canonical(paired))
    return dict(sessions=len(metrics), complete=sum(m["status"] == "completed" for m in metrics),
                paired_comparisons=sum(x["status"] == "paired" for x in paired))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.plan, args.results, args.output), indent=2))


if __name__ == "__main__":
    main()
