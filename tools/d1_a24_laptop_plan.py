"""Offline A24 I4/F4/DEV16/CONFIRM40 registration. Never starts/claims a session."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import uuid
from pathlib import Path

SCHEMA = "a24-laptop-requests-v1"
PROTOCOL = "a24-laptop-measurement-v1"
SOURCE_COMMIT = "7475b1838d538c2a163d4aeefa02327eeed6f407"
PLAN_NAMESPACE = uuid.UUID("e2e0996c-f594-4386-8bb3-1eb54e1c216e")
# Nominal AVAILABLE durations already declared in PLAN.md; not newly fitted values.
SERVICE_NS = {"C_CPU": 165_216_000, "C_GPU": 304_829_000, "D_CPU": 621_737_000}
NOMINAL_PROFILE = {"schema": "a24-declared-nominal-arrival-profile-v1", "AVAILABLE_ns": SERVICE_NS,
                   "source": "docs/team/a24-laptop-measurements-20261014/PLAN.md",
                   "source_PLAN_sha256": "29bbbdc882d273ddec769f748f86907866bb186423643d6f2546bbac55720225",
                   "original_profile_sha256": "5682082a936b7c83efeee747ceeb64fd0c64f0bef8765bbf1b90b807db872db2",
                   "original_profile_commit": SOURCE_COMMIT,
                   "original_profile_path": "docs/results/online_policy_study_01/overnight_sustained_run01/model.json",
                   "derivation": "sum 5 phase_means_ns per supported cell, mean across equal-count contexts, round to nearest microsecond",
                   "scope": "declared rounded nominal durations for arrival recipe; not a newly fitted or validated prediction profile"}
M128_DELTA_NS = math.ceil((8 * max(96 * SERVICE_NS["C_GPU"], 32 * SERVICE_NS["D_CPU"])) / (128 * 0.9) / 1000) * 1000
ARMS = [
    ("L64", "BASE", "FIFO", "C_GPU_D_CPU", "SERIAL", 0),
    ("L64", "PAIR_G", "FIFO", "C_GPU_D_CPU", "CG_DC", 0),
    ("C252", "CPU", "FIFO", "C_CPU", "SERIAL", 0),
    ("C252", "GPU", "FIFO", "C_GPU_D_CPU", "SERIAL", 0),
    ("M128", "BASE", "FIFO", "C_GPU_D_CPU", "SERIAL", 0),
    ("M128", "ORDER", "EDD", "C_GPU_D_CPU", "SERIAL", 0),
    ("M128", "PAIR_G", "FIFO", "C_GPU_D_CPU", "CG_DC", 0),
    ("M128", "WAIT200", "FIFO", "C_GPU_D_CPU", "SERIAL", 200),
]


def encode(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def identity(plan_id: str, value: str) -> str:
    return str(uuid.uuid5(PLAN_NAMESPACE, plan_id + ":" + value))


def bank(plan_id: str, block: str, recipe: str, seed: int, bindings: dict | None = None) -> dict:
    if recipe not in {"L64", "C252", "M128", "I_C32", "IDLE"}:
        raise ValueError("unsupported recipe")
    types = {"L64": ["C", "D"] * 32, "C252": ["C"] * 252,
             "M128": list("CCCDCCCD") * 16, "I_C32": ["C"] * 32, "IDLE": []}[recipe]
    approved = list((bindings or {}).get("approved_inputs", []))
    shuffled = list(range(len(approved)))
    random.Random(seed).shuffle(shuffled)
    requests = []
    for i, task in enumerate(types):
        arrival = 35_000_000_000 + (i // 8 * M128_DELTA_NS if recipe == "M128" else i * (333_200_000 if recipe == "C252" else 1_000_000_000))
        inp = approved[shuffled[i % len(shuffled)]] if shuffled else {}
        relative = 2_200_000_000 if task == "C" else 5_000_000_000
        requests.append({"request_id": identity(plan_id, f"{block}:{recipe}:{i}"), "ordinal": i,
                         "task": task, "priority": "urgent" if task == "C" else "normal",
                         "group": i // 8 if recipe == "M128" else -1,
                         "scheduled_arrival_ns": arrival, "relative_deadline_ns": relative,
                         "deadline_ns": arrival + relative, "input_slot": i,
                         "input_file": inp.get("input_file"), "input_sha256": inp.get("input_sha256"),
                         "tensor_sha256": inp.get("tensor_sha256", {}).get(task)})
    bound = all(r["input_file"] and r["input_sha256"] and r["tensor_sha256"] for r in requests)
    return {"schema": SCHEMA, "recipe": recipe, "block": block, "seed": seed,
            "requests": requests, "request_count": len(requests), "inputs_bound": bound,
            "approved_input_count": len(approved), "m128_delta_ns": M128_DELTA_NS,
            "nominal_AVAILABLE_ns": SERVICE_NS, "nominal_profile_source_commit": SOURCE_COMMIT,
            "nominal_profile_sha256": hashlib.sha256(encode(NOMINAL_PROFILE)).hexdigest(),
            "nominal_profile_scope": NOMINAL_PROFILE["scope"],
            "input_diversity": "SINGLE_APPROVED_IMAGE_REPEATED" if len(approved) == 1 else "BOUND_APPROVED_LIST" if approved else "UNBOUND",
            "evidence": "PLAN_ONLY_NOT_DEVICE_RESULTS"}


def make_plan(plan_id: str, bindings: dict | None = None) -> tuple[dict, dict[str, dict]]:
    if not plan_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in plan_id):
        raise ValueError("plan_id must be an explicit new portable identifier")
    banks: dict[str, dict] = {}
    sessions = []

    def add(stage: str, block: str, spec: tuple, input_seed: int, resident_mode: str = "STANDARD", perfetto: str = "OFF") -> None:
        recipe, arm, order, route, concurrency, wait_ms = spec
        key = f"{block}_{recipe}"
        if key not in banks:
            banks[key] = bank(plan_id, block, recipe, input_seed, bindings)
        b = banks[key]
        sessions.append({"protocol": PROTOCOL, "session_id": identity(plan_id, f"SESSION:{stage}:{block}:{recipe}:{arm}"),
                         "plan_id": plan_id, "stage": stage, "block": block, "recipe": recipe,
                         "arm": arm, "order": order, "route": route, "concurrency": concurrency,
                         "wait_ms": wait_ms, "resident_mode": resident_mode, "perfetto": perfetto,
                         "bank_file": f"banks/{key}.json", "bank_sha256": hashlib.sha256(encode(b)).hexdigest(),
                         "request_count": b["request_count"], "input_seed": input_seed,
                         "service_cutoff_ns": 120_000_000_000, "sensor_end_ns": 210_000_000_000,
                         "energy_windows_s": [0, 120, 180], "AP_window_s": [35, 180],
                         "initial_AP_gate": "DEVICE_UNVERIFIED_UNFROZEN",
                         "device_binding": "DEVICE_UNVERIFIED", "authorization": "PREPARATION_ONLY_NO_RUN",
                         "state": "PLANNED_UNCONSUMED", "consumed": False})

    add("I", "I01", ("IDLE", "IDLE_UNRESIDENT", "FIFO", "C_GPU_D_CPU", "SERIAL", 0), 2026101400, "NONE")
    add("I", "I02", ("IDLE", "IDLE_RESIDENT", "FIFO", "C_GPU_D_CPU", "SERIAL", 0), 2026101400)
    add("I", "I03", ("I_C32", "PERFETTO_OFF", "FIFO", "C_GPU_D_CPU", "SERIAL", 0), 2026101400)
    add("I", "I03", ("I_C32", "PERFETTO_ON", "FIFO", "C_GPU_D_CPU", "SERIAL", 0), 2026101400, perfetto="ON")
    for spec in [ARMS[2], ARMS[3], ARMS[4], ARMS[6]]:
        add("F", "F01", spec, 2026101410)
    for stage, n, start in [("DEV", 2, 2026101420), ("CONFIRM", 5, 2026101450)]:
        for i in range(n):
            block = f"{stage}{i+1:02d}"
            specs = ARMS.copy()
            order_seed = start + 100 + i
            random.Random(order_seed).shuffle(specs)
            for spec in specs:
                add(stage, block, spec, start + i)
                sessions[-1]["execution_order_seed"] = order_seed
    for ordinal, session in enumerate(sessions):
        session["plan_ordinal"] = ordinal
    plan = {"schema": "a24-laptop-plan-v1", "plan_id": plan_id,
            "source_request_commit": "38d34c62111d8ea2b71b7a808db5bdf172e56b1d",
            "source_runtime_commit": SOURCE_COMMIT, "status": "PREPARATION_ONLY_PLANNED_UNCONSUMED",
            "stages": {"I": 4, "F": 4, "DEV": 16, "FREEZE": 0, "CONFIRM": 40},
            "session_count": 64, "sessions": sessions,
            "retry": 0, "replacement": 0, "optional_followups_included": False,
            "actual_device_commands": 0, "NN_calls": 0, "measurement_runs": 0, "claims": 0,
            "freeze_before_confirm": True, "freeze_status": "NOT_PERFORMED",
            "runtime_resident_contract": "DEVICE_UNVERIFIED_MUST_BE_COMMON_WITHIN_BLOCK",
            "instrumentation_C32_recipe": "PROPOSED_35s_PLUS_1s_NO_JITTER_FIXED_BEFORE_DEVICE",
            "binding_required_before_any_device_run": True}
    return plan, banks


def write_plan(destination: Path, plan_id: str, bindings: dict | None = None) -> dict:
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError("write-once plan: use a new empty directory; never overwrite consumed plans")
    plan, banks = make_plan(plan_id, bindings)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "banks").mkdir()
    for name, value in banks.items():
        (destination / "banks" / (name + ".json")).write_bytes(encode(value))
    (destination / "plan.json").write_bytes(encode(plan))
    (destination / "nominal_profile.json").write_bytes(encode(NOMINAL_PROFILE))
    return {"plan_sha256": hashlib.sha256(encode(plan)).hexdigest(), "session_count": 64,
            "bank_count": len(banks), "status": plan["status"], "device_commands": 0, "claims": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plan-id", required=True)
    parser.add_argument("--bindings", type=Path)
    args = parser.parse_args()
    bindings = json.loads(args.bindings.read_text(encoding="utf-8")) if args.bindings else None
    print(json.dumps(write_plan(args.output, args.plan_id, bindings), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
