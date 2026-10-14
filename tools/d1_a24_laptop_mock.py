#!/usr/bin/env python3
"""Software-only scheduling fixture. Arbitrary durations, zero neural calls.

This is not a fitted simulator and its timings are never device measurements.
It creates no session claims and consumes no measurement plans.
"""

from __future__ import annotations

import argparse
import heapq
import json
import sys
import uuid
from pathlib import Path
from typing import Any

from d1_a24_laptop_validator import ARMS, NS, PHASE_FIELDS, SERVICE_NS, LOGGING_NS, manifest_requests, route_backend, validate_events


def fixture_manifest(arm: str) -> dict[str, Any]:
    recipe, order, route, concurrency, wait_ms = ARMS[arm]
    count = {"L64": 64, "C252": 252, "M128": 128, "IDLE": 0, "I_C32": 32}[recipe]
    manifest: dict[str, Any] = {"protocol": "a24-laptop-measurement-v1", "session_id": str(uuid.uuid4()), "prescription_id": arm,
        "recipe": recipe, "order": order, "route": route, "concurrency": concurrency, "wait_ms": wait_ms,
        "service_cutoff_ns": SERVICE_NS, "sensor_end_ns": LOGGING_NS,
        "m128_delta_ns": 2_032_194_000, "nominal_profile_sha256": "0" * 64,
        "evidence_level": "SOFTWARE_MOCK_DEVICE_UNVERIFIED", "mock": True, "NN_calls": 0, "requests": []}
    for i in range(count):
        task = "C" if recipe in {"C252", "I_C32"} or recipe == "L64" and i % 2 == 0 or recipe == "M128" and i % 8 in {0, 1, 2, 4, 5, 6} else "D"
        arrival = 35 * NS + (i * NS if recipe in {"L64", "I_C32"} else i * 333_200_000 if recipe == "C252" else i // 8 * manifest["m128_delta_ns"])
        relative = 2_200_000_000 if task == "C" else 5 * NS
        manifest["requests"].append({"request_id": f"MOCK-{i:04d}", "ordinal": i, "task": task, "group": i // 8 if recipe == "M128" else -1,
            "input_slot": i, "input_file": None, "input_sha256": None, "tensor_sha256": None,
            "scheduled_arrival_ns": arrival, "relative_deadline_ns": relative, "deadline_ns": arrival + relative})
    return manifest


def replay_mock(manifest: dict[str, Any], *, duration_ns: dict[str, int] | None = None, t0_ns: int = 10 * NS) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    requests = manifest_requests(manifest)
    # Deliberately arbitrary software-clock values; no fit or measured validity.
    durations = duration_ns or {"C_CPU": 410_000_000, "C_GPU": 310_000_000, "D_CPU": 620_000_000}
    by_id = {row["request_id"]: row for row in requests}
    result_rows = {rid: {"request_id": rid, "backend": None, "scheduled_arrival_ns": t0_ns + row["scheduled_arrival_ns"], "terminal_status": "UNFINISHED", **{field: None for field in PHASE_FIELDS.values()}} for rid, row in by_id.items()}
    events: list[dict[str, Any]] = []
    callbacks: list[tuple[int, int, str, dict[str, Any]]] = []
    ready: set[str] = set()
    owners: dict[str, str | None] = {"CPU": None, "GPU": None}
    group_waited: set[int] = set()
    group_dispatched: set[int] = set()
    active_wait: int | None = None
    stopped = False
    counter = 0

    def schedule(now: int, kind: str, data: dict[str, Any]) -> None:
        nonlocal counter
        counter += 1
        heapq.heappush(callbacks, (now, counter, kind, data))

    def emit(now: int, kind: str, **data: Any) -> None:
        events.append({"kind": kind, "mono_ns": now, "sequence": len(events), "session_id": manifest["session_id"], **data})
        if kind in PHASE_FIELDS:
            result_rows[data["request_id"]][PHASE_FIELDS[kind]] = now

    emit(t0_ns, "common_start")
    for request in requests:
        schedule(t0_ns + request["scheduled_arrival_ns"], "arrival", {"request_id": request["request_id"], "scheduled_arrival_ns": t0_ns + request["scheduled_arrival_ns"]})
    schedule(t0_ns + SERVICE_NS, "dispatch_stop", {})
    schedule(t0_ns + LOGGING_NS, "logging_stop", {})
    while callbacks:
        now = callbacks[0][0]
        at_time = []
        while callbacks and callbacks[0][0] == now:
            at_time.append(heapq.heappop(callbacks))
        # All actually due arrival callbacks enter the public queue before pump.
        for _, _, kind, data in at_time:
            if kind == "arrival":
                emit(now, kind, **data)
                emit(now, "queue_entry", request_id=data["request_id"])
                ready.add(data["request_id"])
            elif kind == "dispatch_stop":
                emit(now, kind)
                stopped = True
            elif kind == "wait_end":
                emit(now, kind, group=data["group"], waiting=sorted(ready), owners=dict(owners))
                active_wait = None
            else:
                emit(now, kind, **data)
                rid = data.get("request_id")
                if kind in {"output_ready", "persist_readback"} and by_id[rid]["task"] == ("C" if kind == "output_ready" else "D"):
                    result_rows[rid]["terminal_status"] = "COMPLETED" if now <= t0_ns + SERVICE_NS else "COMPLETED_DRAIN"
                if kind == "lane_available":
                    owners[route_backend(manifest, by_id[rid])] = None
        while ready and not stopped and active_wait is None:
            key = lambda rid: ((by_id[rid]["deadline_ns"],) if manifest["order"] == "EDD" else ()) + (by_id[rid]["scheduled_arrival_ns"], by_id[rid]["ordinal"], rid)
            rid = min(ready, key=key)
            request = by_id[rid]
            backend = route_backend(manifest, request)
            if owners[backend] is not None or manifest["concurrency"] == "SERIAL" and any(owners.values()):
                break
            if manifest["wait_ms"] == 200 and request["group"] not in group_dispatched and request["group"] not in group_waited:
                assert not any(owners.values())
                active_wait = request["group"]
                group_waited.add(active_wait)
                emit(now, "wait_start", group=active_wait, planned_wait_ns=200_000_000, waiting=sorted(ready), owners=dict(owners))
                schedule(min(now + 200_000_000, t0_ns + SERVICE_NS), "wait_end", {"group": active_wait})
                break
            ready.remove(rid)
            owners[backend] = rid
            group_dispatched.add(request["group"])
            result_rows[rid]["backend"] = backend
            emit(now, "dispatch", request_id=rid, backend=backend)
            emit(now, "execution_start", request_id=rid)
            release_time = now + durations[f"{request['task']}_{backend}"]
            output_time = release_time - 30_000_000
            schedule(output_time, "output_ready", {"request_id": rid})
            if request["task"] == "D":
                for offset, phase in enumerate(("persist_write", "persist_flush", "persist_fsync", "persist_rename", "persist_readback"), 1):
                    schedule(output_time + offset * 1_000_000, phase, {"request_id": rid})
            schedule(release_time - 10_000_000, "worker_release", {"request_id": rid})
            schedule(release_time, "lane_available", {"request_id": rid})
    return events, [result_rows[row["request_id"]] for row in requests]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=list(ARMS), default="M128_WAIT200")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    manifest = fixture_manifest(args.arm)
    events, rows = replay_mock(manifest)
    result = validate_events(manifest, events, rows)
    result.update({"evidence_level": "SOFTWARE_MOCK_DEVICE_UNVERIFIED", "mock_neural_calls": 0, "arbitrary_durations_not_device_prediction": True})
    if args.output is not None:
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / "session_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        (args.output / "events.jsonl").write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")
        (args.output / "requests.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        (args.output / "verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
