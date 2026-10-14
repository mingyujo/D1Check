#!/usr/bin/env python3
"""Offline, fail-closed validation for a24-laptop-measurement-v1.

This module does not import or invoke ADB, start a registry claim, or execute
inference. Software mock validity never grants a device-ready status.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import uuid
from pathlib import Path
from typing import Any

PROTOCOL = "a24-laptop-measurement-v1"
NS = 1_000_000_000
SERVICE_NS = 120 * NS
LOGGING_NS = 210 * NS
SHA = re.compile(r"[0-9a-f]{64}\Z")
RECIPE_COUNTS = {"L64": (64, 32, 32), "C252": (252, 252, 0), "M128": (128, 96, 32), "IDLE": (0, 0, 0), "I_C32": (32, 32, 0)}
ARMS = {
    "L64_BASE": ("L64", "FIFO", "C_GPU_D_CPU", "SERIAL", 0),
    "L64_PAIR_G": ("L64", "FIFO", "C_GPU_D_CPU", "CG_DC", 0),
    "C252_CPU": ("C252", "FIFO", "C_CPU", "SERIAL", 0),
    "C252_GPU": ("C252", "FIFO", "C_GPU_D_CPU", "SERIAL", 0),
    "M128_BASE": ("M128", "FIFO", "C_GPU_D_CPU", "SERIAL", 0),
    "M128_ORDER": ("M128", "EDD", "C_GPU_D_CPU", "SERIAL", 0),
    "M128_PAIR_G": ("M128", "FIFO", "C_GPU_D_CPU", "CG_DC", 0),
    "M128_WAIT200": ("M128", "FIFO", "C_GPU_D_CPU", "SERIAL", 200),
    "IDLE_UNRESIDENT": ("IDLE", "FIFO", "C_GPU_D_CPU", "SERIAL", 0),
    "IDLE_RESIDENT": ("IDLE", "FIFO", "C_GPU_D_CPU", "SERIAL", 0),
    "I_C32_OFF": ("I_C32", "FIFO", "C_GPU_D_CPU", "SERIAL", 0),
    "I_C32_ON": ("I_C32", "FIFO", "C_GPU_D_CPU", "SERIAL", 0),
}
TERMINALS = {"COMPLETED", "COMPLETED_DRAIN", "FAILED", "UNFINISHED", "REJECTED", "CANCELLED"}
PHASES = ("arrival", "queue_entry", "dispatch", "execution_start", "output_ready", "persist_write", "persist_flush", "persist_fsync", "persist_rename", "persist_readback", "worker_release", "lane_available")
PHASE_FIELDS = {
    "arrival": "actual_arrival_ns", "queue_entry": "queue_entry_ns",
    "dispatch": "dispatch_ns", "execution_start": "execution_start_ns",
    "output_ready": "output_ready_ns", "persist_readback": "persist_complete_ns",
    "worker_release": "worker_release_ns", "lane_available": "lane_available_ns",
}


class ValidationError(ValueError):
    pass


def sha256(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(part)
    return result.hexdigest()


def load_json(path: Path) -> Any:
    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        answer: dict[str, Any] = {}
        for key, value in pairs:
            if key in answer:
                raise ValidationError(f"duplicate JSON key: {key}")
            answer[key] = value
        return answer
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=no_duplicates,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValidationError(f"non-finite JSON: {value}")))
    except (OSError, json.JSONDecodeError) as error:
        raise ValidationError(f"cannot read {path.name}: {error}") from error


def contained_file(root: Path, relative: str) -> Path:
    """Reject traversal, absolute paths and symlink/reparse ancestry."""
    import stat
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValidationError("artifact path must be a nonempty POSIX relative path")
    local = Path(relative)
    if local.is_absolute() or ":" in relative or any(part in {".", ".."} for part in relative.split("/")):
        raise ValidationError(f"unsafe artifact path: {relative}")
    root = root.resolve()
    target = root / local
    for item in [target, *target.parents]:
        if item == root:
            break
        if item.exists():
            attrs = getattr(item.lstat(), "st_file_attributes", 0)
            if item.is_symlink() or attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
                raise ValidationError(f"symlink/reparse artifact: {relative}")
    try:
        target.resolve().relative_to(root)
    except ValueError as error:
        raise ValidationError(f"artifact escapes root: {relative}") from error
    if not target.is_file():
        raise ValidationError(f"artifact missing: {relative}")
    return target


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def integer(value: Any, name: str, minimum: int = 0) -> int:
    require(isinstance(value, int) and not isinstance(value, bool) and value >= minimum, f"invalid integer {name}")
    return value


def manifest_requests(manifest: dict[str, Any], *, require_materials: bool = False) -> list[dict[str, Any]]:
    require(manifest.get("protocol") == PROTOCOL, "wrong opt-in protocol")
    try:
        parsed = uuid.UUID(manifest.get("session_id", ""))
        require(str(parsed) == manifest["session_id"], "noncanonical session UUID")
    except (ValueError, AttributeError, TypeError) as error:
        raise ValidationError("new canonical session UUID required") from error
    recipe = manifest.get("recipe")
    require(recipe in RECIPE_COUNTS, "unsupported recipe; no implicit replacement")
    settings = (recipe, manifest.get("order"), manifest.get("route"), manifest.get("concurrency"), manifest.get("wait_ms"))
    require(settings in ARMS.values(), "unsupported prescription tuple")
    if manifest.get("prescription_id") in ARMS:
        require(settings == ARMS[manifest["prescription_id"]], "arm ID/settings mismatch")
    require(manifest.get("service_cutoff_ns") == SERVICE_NS, "service window changed")
    require(manifest.get("sensor_end_ns") == LOGGING_NS, "logging window changed")
    requests = manifest.get("requests")
    require(isinstance(requests, list), "requests must be a list")
    total, c_count, d_count = RECIPE_COUNTS[recipe]
    require(len(requests) == total, "planned request denominator changed")
    require(sum(row.get("task") == "C" for row in requests) == c_count and sum(row.get("task") == "D" for row in requests) == d_count, "task counts changed")
    ids: set[str] = set()
    delta = integer(manifest.get("m128_delta_ns", 0), "m128_delta_ns")
    if recipe == "M128":
        require(delta > 0 and delta % 1000 == 0, "M128 delta must be explicit, rounded up to 1us")
        source = manifest.get("nominal_profile_sha256")
        require(isinstance(source, str) and SHA.fullmatch(source) is not None, "M128 source profile SHA missing")
    for i, row in enumerate(requests):
        require(isinstance(row, dict), "invalid request")
        request_id = row.get("request_id")
        require(isinstance(request_id, str) and request_id and request_id not in ids, "missing/duplicate request identity")
        ids.add(request_id)
        require(row.get("ordinal") == i, "ordinal must cover all planned requests in recipe order")
        task = "C" if recipe in {"C252", "I_C32"} or (recipe == "L64" and i % 2 == 0) or (recipe == "M128" and i % 8 in {0, 1, 2, 4, 5, 6}) else "D"
        require(row.get("task") == task, "recipe task order changed")
        expected_arrival = 35 * NS + (i * NS if recipe in {"L64", "I_C32"} else i * 333_200_000 if recipe == "C252" else (i // 8) * delta)
        require(integer(row.get("scheduled_arrival_ns"), "scheduled_arrival_ns") == expected_arrival, "recipe arrival changed or future insertion")
        require(row.get("relative_deadline_ns") == (2_200_000_000 if task == "C" else 5 * NS), "relative deadline changed")
        require(row.get("deadline_ns") == expected_arrival + (2_200_000_000 if task == "C" else 5 * NS), "declared relative deadline changed")
        require(row.get("group", -1) == (i // 8 if recipe == "M128" else -1), "group mismatch")
        if require_materials:
            for key in ("input_sha256", "tensor_sha256"):
                value = row.get(key)
                require(isinstance(value, str) and SHA.fullmatch(value) is not None, f"exact approved {key} missing")
            require(isinstance(row.get("input_file"), str) and row["input_file"], "approved input path missing")
    return requests


def route_backend(manifest: dict[str, Any], request: dict[str, Any]) -> str:
    return "CPU" if manifest["route"] == "C_CPU" or request["task"] == "D" else "GPU"


def validate_events(manifest: dict[str, Any], events: list[dict[str, Any]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Replay only public arrivals and actual AVAILABLE boundaries, not predictions."""
    planned = manifest_requests(manifest)
    by_id = {row["request_id"]: row for row in planned}
    require(len(rows) == len(planned), "request result denominator is not all planned arrivals")
    results = {row.get("request_id"): row for row in rows}
    require(len(results) == len(rows) and set(results) == set(by_id), "missing/duplicate/extra result identity")
    common = [event for event in events if event.get("kind") == "common_start"]
    require(len(common) == 1, "exactly one common_start event required")
    t0 = integer(common[0].get("origin_ns", common[0].get("mono_ns")), "t0")
    require(t0 <= common[0].get("mono_ns", -1), "common origin follows journal timestamp")
    ready: set[str] = set()
    dispatched: set[str] = set()
    owners: dict[str, str | None] = {"CPU": None, "GPU": None}
    seen: dict[str, dict[str, int]] = {request_id: {} for request_id in by_id}
    wait: dict[str, Any] | None = None
    wait_groups: set[int] = set()
    started_groups: set[int] = set()
    wait_durations: list[int] = []
    wait_nominal_durations: list[int] = []
    wait_overshoots: list[int] = []
    overlap_intervals: list[tuple[int, int]] = []
    overlap_start: int | None = None
    stopped = False
    actual_stop_ns: int | None = None
    logging_end_ns: int | None = None
    previous_ns = 0
    common_seen = False
    first_sequence = integer(events[0].get("sequence"), "event sequence")
    for index, event in enumerate(events):
        kind = event.get("kind")
        now = integer(event.get("mono_ns"), "event mono_ns")
        require(now >= previous_ns, "event clock moved backwards")
        previous_ns = now
        require(event.get("sequence") == first_sequence + index, "event sequence missing/duplicate")
        require(event.get("session_id") == manifest["session_id"], "cross-session event")
        if kind == "common_start":
            require(not common_seen, "duplicate common_start")
            common_seen = True
            continue
        if not common_seen:
            require(kind in {"runtime_submit", "runtime_ready", "warmup_result", "sensor_sample"}, "request execution before common_start")
            continue
        if kind == "dispatch_stop":
            require(not stopped and now >= t0 + SERVICE_NS, "dispatch stop precedes prescribed boundary")
            require(event.get("planned_stop_ns", t0 + SERVICE_NS) == t0 + SERVICE_NS, "planned dispatch stop changed")
            stopped = True
            actual_stop_ns = now
            continue
        if kind in {"wait_start", "wait_end"}:
            require(manifest["wait_ms"] == 200, "intentional WAIT on WAIT0 arm")
            if kind == "wait_start":
                started_ns = integer(event.get("actual_start_ns", now), "WAIT start")
                require(started_ns <= now, "WAIT start follows journal timestamp")
                require(wait is None and not stopped and started_ns < t0 + SERVICE_NS, "nested/late WAIT")
                require(ready and not any(owners.values()), "WAIT requires ready head and actual idle lanes")
                head = min(ready, key=lambda rid: (by_id[rid]["scheduled_arrival_ns"], by_id[rid]["ordinal"], rid))
                group = event.get("group")
                require(group == by_id[head]["group"] and group not in wait_groups and group not in started_groups, "WAIT is not before group's first dispatch")
                require(event.get("planned_wait_ns") == 200_000_000, "WAIT dose changed")
                require(set(event.get("waiting", [])) == ready and event.get("owners") == owners, "WAIT public state snapshot inconsistent")
                planned_end = min(started_ns + 200_000_000, t0 + SERVICE_NS)
                require(event.get("planned_end_ns", planned_end) == planned_end, "WAIT planned end changed")
                wait = {"group": group, "start": started_ns, "planned_end": planned_end}
                wait_groups.add(group)
            else:
                require(wait is not None and event.get("group") == wait["group"], "WAIT end without matching start")
                ended_ns = integer(event.get("actual_end_ns", now), "WAIT end")
                require(ended_ns <= now, "WAIT end follows journal timestamp")
                duration = ended_ns - wait["start"]
                expected = wait["planned_end"] - wait["start"]
                require(ended_ns >= wait["planned_end"], "WAIT ended before prescribed timer/cutoff")
                require(set(event.get("waiting", [])) == ready and event.get("owners") == owners, "WAIT end state snapshot inconsistent")
                wait_durations.append(duration)
                wait_nominal_durations.append(expected)
                wait_overshoots.append(duration - expected)
                wait = None
            continue
        if kind == "sensor_sample":
            continue
        if kind == "dispatch_selection_cutoff":
            request_id = event.get("request_id")
            captured = integer(event.get("captured_dispatch_ns"), "captured dispatch cutoff")
            require(request_id in ready and request_id not in dispatched, "cutoff diagnostic must preserve unstarted ready request")
            require(t0 + SERVICE_NS <= captured <= now and event.get("planned_stop_ns") == t0 + SERVICE_NS, "cutoff diagnostic has incorrect clock/boundary")
            require(set(event.get("waiting", [])) == ready and event.get("owners") == owners, "cutoff did not restore public queue/lane state")
            continue
        require(kind in PHASES or kind in {"request_failed", "request_failure", "request_rejected", "logging_stop", "logging_end", "phase", "session_failure", "hard_timeout"}, f"unknown event kind: {kind}")
        if kind in {"logging_stop", "logging_end"}:
            require(logging_end_ns is None, "duplicate logging end")
            require(now >= t0 + LOGGING_NS, "logging ended before sensor boundary coverage target")
            logging_end_ns = now
            continue
        if kind in {"session_failure", "hard_timeout"}:
            continue
        request_id = event.get("request_id")
        require(request_id in by_id, "unplanned/future request identity")
        request = by_id[request_id]
        phases = seen[request_id]
        if kind == "phase":
            require("execution_start" in phases and "output_ready" not in phases, "diagnostic execution phase lies outside execution")
            require(event.get("edge") in {"enter", "exit", "start", "end", "succeeded", "failed"} and isinstance(event.get("stage"), str), "invalid diagnostic phase marker")
            continue
        if kind == "request_failure":
            kind = "request_failed"
        if kind in {"request_failed", "request_rejected"}:
            require(kind not in phases, "duplicate failure")
            phases[kind] = now
            ready.discard(request_id)
            continue
        require(kind not in phases, "duplicate request phase")
        field = PHASE_FIELDS.get(kind)
        phase_ns = event.get(field, now) if field else now
        if kind == "persist_readback":
            phase_ns = event.get("completed_ns", phase_ns)
        phase_ns = integer(phase_ns, f"{kind} authoritative timestamp")
        require(phase_ns <= now, "phase time follows journal record timestamp")
        if kind == "arrival":
            require(phase_ns >= t0 + request["scheduled_arrival_ns"], "future arrival exposed before scheduled time")
            require(event.get("scheduled_arrival_ns") == t0 + request["scheduled_arrival_ns"], "scheduled arrival reference changed")
        elif kind == "queue_entry":
            require("arrival" in phases and phase_ns >= phases["arrival"], "enqueue precedes actual arrival")
            ready.add(request_id)
        elif kind == "dispatch":
            require(not stopped and phase_ns < t0 + SERVICE_NS, "dispatch after service-window stop")
            require(wait is None and request_id in ready, "dispatch while WAIT / unarrived / duplicate")
            require(phase_ns >= phases["queue_entry"], "dispatch precedes enqueue")
            key = lambda rid: ((by_id[rid]["deadline_ns"],) if manifest["order"] == "EDD" else ()) + (by_id[rid]["scheduled_arrival_ns"], by_id[rid]["ordinal"], rid)
            head = min(ready, key=key)
            require(request_id == head, "FIFO head bypass or incorrect EDD/tie order")
            backend = route_backend(manifest, request)
            require(event.get("backend") == backend, "unsupported or prescribed route changed")
            require(owners[backend] is None, "lane reused before actual AVAILABLE")
            require(manifest["concurrency"] != "SERIAL" or not any(owners.values()), "global serial capacity violated")
            if manifest["wait_ms"] == 200 and request["group"] not in started_groups:
                require(request["group"] in wait_groups, "first group dispatch skipped prescribed WAIT")
            owners[backend] = request_id
            started_groups.add(request["group"])
            ready.remove(request_id)
            dispatched.add(request_id)
            if all(owners.values()):
                require(manifest["concurrency"] == "CG_DC", "unsupported pair")
                require(by_id[owners["CPU"]]["task"] == "D" and by_id[owners["GPU"]]["task"] == "C", "unsupported concurrent task combination")
                overlap_start = phase_ns
        elif kind == "execution_start":
            require("dispatch" in phases and phase_ns >= phases["dispatch"], "execution precedes dispatch")
        elif kind == "output_ready":
            require("execution_start" in phases and phase_ns >= phases["execution_start"], "output precedes execution")
        elif kind.startswith("persist_"):
            order = ("output_ready", "persist_write", "persist_flush", "persist_fsync", "persist_rename", "persist_readback")
            before = order[order.index(kind) - 1]
            require(before in phases and phase_ns >= phases[before], "persistence boundary/order missing")
        elif kind == "worker_release":
            response = "output_ready" if request["task"] == "C" else "persist_readback"
            require(response in phases or "request_failed" in phases, "worker release before response/failure")
            boundary = phases.get("request_failed") if "request_failed" in phases else phases[response]
            require(phase_ns >= boundary, "worker release clock precedes response/failure")
        elif kind == "lane_available":
            backend = route_backend(manifest, request)
            require("worker_release" in phases and phase_ns >= phases["worker_release"], "AVAILABLE precedes worker release")
            require(owners[backend] == request_id, "AVAILABLE owner mismatch")
            if overlap_start is not None:
                require(phase_ns >= overlap_start, "pair overlap clock reversal")
                overlap_intervals.append((overlap_start, phase_ns))
                overlap_start = None
            owners[backend] = None
        phases[kind] = phase_ns
    require(stopped, "dispatch_stop event absent")
    require(logging_end_ns is not None, "logging_end event absent; trace is incomplete")
    require(wait is None, "WAIT has no end/cutoff record")
    require(len(wait_groups) <= 16 and sum(wait_nominal_durations) <= 3_200_000_000, "WAIT count/cumulative nominal dose exceeded")
    metrics: dict[str, Any] = {"planned": len(planned), "C_planned": 0, "D_planned": 0, "completed_in_service": 0, "drain_completed": 0, "failed": 0, "unfinished": 0, "dispatches": len(dispatched), "wait_count": len(wait_durations), "wait_nominal_ns": sum(wait_nominal_durations), "wait_actual_ns": sum(wait_durations), "wait_timer_overshoot_ns": sum(wait_overshoots), "actual_pair_overlap_ns": sum(end - start for start, end in overlap_intervals), "owners_at_end": owners}
    metrics.update({"common_origin_ns": t0, "dispatch_stop_actual_ns": actual_stop_ns,
                    "dispatch_stop_timer_overshoot_ns": actual_stop_ns - (t0 + SERVICE_NS),
                    "logging_end_ns": logging_end_ns, "last_journal_record_ns": previous_ns})
    response_times: dict[str, list[int]] = {"C": [], "D": []}
    on_time: dict[str, int] = {"C": 0, "D": 0}
    for request_id, request in by_id.items():
        row = results[request_id]
        phases = seen[request_id]
        require(row.get("terminal_status") in TERMINALS, "missing/unsupported terminal status")
        require(row.get("scheduled_arrival_ns") == t0 + request["scheduled_arrival_ns"], "result planned arrival changed")
        for phase, field in PHASE_FIELDS.items():
            require(row.get(field) == phases.get(phase), f"result/event mismatch: {field}")
        require(row.get("backend") in {None, route_backend(manifest, request)}, "result backend changed")
        response = phases.get("output_ready" if request["task"] == "C" else "persist_readback")
        status = row["terminal_status"]
        if status in {"COMPLETED", "COMPLETED_DRAIN"}:
            require(response is not None and "lane_available" in phases, "completed request lacks response/AVAILABLE")
            if status == "COMPLETED_DRAIN":
                require(response > t0 + SERVICE_NS, "drain result lies in service window")
            else:
                require(response <= t0 + SERVICE_NS, "late result must be explicitly drain")
        if status == "FAILED":
            require("request_failed" in phases, "failed result has no failure evidence")
        if status in {"UNFINISHED", "REJECTED", "CANCELLED"}:
            require(response is None, "completed response hidden as unfinished/rejected")
        metrics[f"{request['task']}_planned"] += 1
        if response is not None and status in {"COMPLETED", "COMPLETED_DRAIN"}:
            response_times[request["task"]].append(response - (t0 + request["scheduled_arrival_ns"]))
            if response <= t0 + SERVICE_NS:
                metrics["completed_in_service"] += 1
                on_time[request["task"]] += int(response <= t0 + request["deadline_ns"])
            else:
                metrics["drain_completed"] += 1
        elif status == "FAILED":
            metrics["failed"] += 1
        else:
            metrics["unfinished"] += 1
    for task in ("C", "D"):
        denominator = metrics[f"{task}_planned"]
        samples = sorted(response_times[task])
        metrics[f"{task}_on_time"] = on_time[task]
        metrics[f"{task}_on_time_rate_all_planned"] = on_time[task] / denominator if denominator else None
        metrics[f"{task}_response_p95_ns_completed_only"] = samples[math.ceil(0.95 * len(samples)) - 1] if samples else None
    return {"status": "SOFTWARE_TRACE_VALIDATED_DEVICE_UNVERIFIED", "protocol": PROTOCOL,
            "device_verified": False, "actual_device_commands_from_validator": 0, "NN_calls_from_validator": 0,
            "registry_claims_from_validator": 0, "metrics": metrics}


def window_coverage(samples: list[dict[str, Any]], *, start_ns: int, end_ns: int, max_gap_ns: int, channel: str, unit: str, sensor_binding: dict[str, Any] | None = None) -> dict[str, Any]:
    """Pure coverage check. Never extrapolate or substitute battery for AP."""
    require(max_gap_ns > 0 and end_ns > start_ns, "invalid frozen window/gap")
    relevant = sorted((row for row in samples if row.get("channel") == channel), key=lambda row: row["sample_ns"])
    if not relevant:
        return {"status": "MISSING", "value": None}
    if channel == "AP":
        if not sensor_binding or not sensor_binding.get("sensor_name") or sensor_binding.get("sensor_type") in {None, "UNKNOWN", "BATTERY", 2}:
            return {"status": "AP_SENSOR_BINDING_UNVERIFIED", "value": None}
        for row in relevant:
            require(row.get("sensor_name") == sensor_binding["sensor_name"] and row.get("sensor_type") == sensor_binding["sensor_type"], "AP HAL sensor identity/type mismatch; battery cannot substitute AP")
    for row in relevant:
        require(row.get("unit") == unit, "sensor unit mismatch")
        value = row.get("value")
        require(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value), "invalid sensor value")
        begin = integer(row.get("read_start_ns"), "read_start_ns")
        end = integer(row.get("read_end_ns"), "read_end_ns")
        require(begin <= end <= row["reported_at_ns"], "sensor read/return clock order")
        integer(row.get("sample_ns"), "sample_ns")
        require(row["sample_ns"] <= row["reported_at_ns"], "future sensor sample")
        integer(row.get("cache_age_ns"), "cache_age_ns")
    before = [row for row in relevant if row["sample_ns"] <= start_ns]
    after = [row for row in relevant if row["sample_ns"] >= end_ns]
    if not before or not after:
        return {"status": "BOUNDARY_NOT_BRACKETED", "value": None}
    selected = [before[-1], *[row for row in relevant if start_ns < row["sample_ns"] < end_ns], after[0]]
    timestamps = [row["sample_ns"] for row in selected]
    if any(b - a > max_gap_ns for a, b in zip(timestamps, timestamps[1:])):
        return {"status": "GAP_EXCEEDS_FROZEN_LIMIT", "value": None}
    return {"status": "COVERAGE_ONLY_NOT_ENERGY_CALIBRATION", "sample_count": len(selected), "value": None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    m = sub.add_parser("manifest")
    m.add_argument("manifest", type=Path)
    m.add_argument("--require-materials", action="store_true")
    v = sub.add_parser("trace")
    v.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "manifest":
            requests = manifest_requests(load_json(args.manifest), require_materials=args.require_materials)
            result = {"status": "STRUCTURAL_VALIDATION_ONLY_DEVICE_UNVERIFIED", "planned": len(requests), "materials_required": args.require_materials}
        else:
            root = args.directory
            manifest = load_json(root / "session_manifest.json")
            events = [json.loads(line) for line in (root / "events.jsonl").read_text(encoding="utf-8-sig").splitlines() if line.strip()]
            rows = load_json(root / "requests.json")
            if isinstance(rows, dict):
                rows = rows["requests"]
            result = validate_events(manifest, events, rows)
    except (ValidationError, OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        print(json.dumps({"status": "BLOCKED", "reason": str(error), "actual_device_commands": 0}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
