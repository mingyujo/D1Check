"""PC-only CAL-03 conversion and causal development policy; no device entry point.

The frozen phase medians are observations, not bounds. Joint interval medians
are derived from development requests before aggregation, never confirmation.
Existing Android policy IDs, estimates and artifact validators remain unchanged.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import statistics
from pathlib import Path

from tools import d1_arrival_plan as common
from tools import d1_arrival_timing_calibration as calibration
from tools import d1_arrival_timing_dev as legacy

VERSION = "cal03-priority-joint-estimates-dev-v1"
POLICY = "CAL03_SOLO_CONDITIONAL_PC_DEV_1"
CELLS = {f"{t}_{b}_{p}" for t in ("classification", "detection")
         for b in ("CPU", "GPU") for p in ("urgent", "normal")}
JOINTS = {
    "dispatch_to_response_ns": ("dispatch_ns", "completion_ns"),
    "dispatch_to_lane_ns": ("dispatch_ns", "lane_available_ns"),
    "start_to_lane_ns": ("execution_start_ns", "lane_available_ns"),
    "output_to_lane_ns": ("output_ready_ns", "lane_available_ns"),
    "persist_to_lane_ns": ("persist_complete_ns", "lane_available_ns"),
}
# Realizations retain the paired vector including the W/L split; never sum medians.
STEPS = ("dispatch_ns", "execution_start_ns", "output_ready_ns",
         "persist_complete_ns", "worker_release_ns", "lane_available_ns")
PHASE_FIELDS = {"ASSIGNED": "dispatch_to_start_ns", "EXECUTING": "start_to_output_ready_ns",
                "OUTPUT_READY": "output_ready_to_persist_ns", "PERSISTED": "persist_to_lane_available_ns",
                "WORKER_RELEASED": "persist_to_lane_available_ns"}
PHASE_JOINTS = dict(zip(PHASE_FIELDS, ("dispatch_to_lane_ns", "start_to_lane_ns",
                                    "output_to_lane_ns", "persist_to_lane_ns", "persist_to_lane_ns")))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def stats(values):
    require(bool(values) and all(type(v) is int and v >= 0 for v in values), "nonnegative integer ns required")
    return dict(median_ns=statistics.median(values), min_ns=min(values), max_ns=max(values),
                independent_sessions=1, correlated_requests=len(values), method="median_of_per_request_interval")


def derive(plan_path, fit_path, development):
    """Read only the 8 development sessions. Reuse the existing boundary replayer.

    Does not rerun fit/confirm, APK verification, environmental or GPU audits.
    Bind every artifact read by the reused validator to the existing frozen hash.
    """
    plan_path, fit_path, development = map(Path, (plan_path, fit_path, development))
    plan, fit = common.read(plan_path), common.read(fit_path)
    require(fit["protocol"] == "arrival-timing-calibration-fit-v1" and
            fit["observation_contract"] == "arrival-phase-observations-v2" and
            fit["plan_sha256"] == common.digest(plan_path) and not fit["experiment_ready"], "freeze/plan identity")
    require(plan["experiment_id"] == "ARRIVAL-TIMING-CAL-03", "CAL-03 plan required")
    entries = [e for e in plan["entries"] if e["phase"] == "development"]
    require(len(entries) == 8 and set(fit["estimates"]) == CELLS, "eight development cells required")
    frozen_hashes = {str(Path(k).resolve()): v for k, v in fit["input_hashes"].items()}
    cells, vectors, replay, inputs, scope = {}, {}, [], {}, None
    for entry in entries:
        key = f"{entry['task']}_{entry['backend']}_{entry['priority']}"
        require(key not in cells, "duplicate cell")
        folder = development / f"{entry['index']:02d}_{entry['session_id']}" / "artifacts"
        for source in sorted(folder.iterdir()):
            if source.is_file():
                actual = common.digest(source)
                require(frozen_hashes.get(str(source.resolve())) == actual, f"frozen input mismatch: {source.name}")
                inputs[str(source.resolve())] = actual
        manifest = common.read(folder / "manifest.json")
        require(manifest["collection_phase"] == "development" and
                manifest["session_id"] == entry["session_id"] and
                common.digest(folder / "manifest.json") == entry["manifest_sha256"], "development identity")
        samples = calibration.observations(folder)  # compatibility/time-boundary replay, not predictive validation
        rows = sorted(common.read(folder / "requests.json"), key=lambda r: r["ordinal"])
        require(all(f"{r['task_id']}_{r['selected_backend']}_{r['priority']}" == key for r in rows), "cell mismatch")
        for field in legacy.ALL_FIELDS:
            require(statistics.median(s["values"][field] for s in samples) == fit["estimates"][key][field]["median_ns"],
                    "frozen phase median mismatch")
        current_scope = dict(device_fingerprint=manifest["device_fingerprint"], apk_sha256=manifest["apk_sha256"],
            cpu_threads=manifest["cpu_threads"], maximum_concurrency=manifest["maximum_concurrency"],
            models={k: {"model": v["model"], "runtime": v["runtime"], "tensor": v["tensor"]}
                    for k, v in manifest["models"].items()}, images=manifest["images"],
            resident_runtimes=4, warmup_calls=8, persist="all priorities", clock="elapsedRealtimeNanos", unit="ns",
            environment="observed CAL-03 awake/interactive, thermal0, sparse host power observation; no continuous-state claim")
        if scope is None:
            scope = current_scope
        require(scope == current_scope and scope["maximum_concurrency"] == 1, "mixed execution scope")
        joint = {name: stats([r[b] - r[a] for r in rows]) for name, (a, b) in JOINTS.items()}
        cells[key] = dict(observed_phases=copy.deepcopy(fit["estimates"][key]), joint=joint,
            adaptive_decision_to_dispatch_ns=None,
            adaptive_decision_status="missing_policy_specific_measurement",
            transfer_status="solo_fixed_path_to_new_policy_unvalidated", session_id=entry["session_id"])
        vectors[key] = []
        for r in rows:
            require(all(r[a] <= r[b] for a, b in zip(STEPS, STEPS[1:])), "W/L timing order")
            vectors[key].append(dict(source_request_id=r["request_id"], source_session_id=r["session_id"],
                ordinal=r["ordinal"], durations_ns=[r[b] - r[a] for a, b in zip(STEPS, STEPS[1:])]))
        replay.append(dict(cell=key, session_id=entry["session_id"], requests=len(rows), lane_reuse_pairs=3,
            dispatch_response_median_ns=joint["dispatch_to_response_ns"]["median_ns"],
            sum_phase_response_medians_ns=sum(fit["estimates"][key][f]["median_ns"]
                for f in legacy.FIELDS[:2 if entry["priority"] == "urgent" else 3])))
    require(set(cells) == CELLS, "missing cell")
    config = dict(protocol=VERSION, policy=POLICY, experiment_ready=False, scope=scope, cells=cells,
        provenance=dict(fit_sha256=common.digest(fit_path), plan_sha256=common.digest(plan_path),
            original_source_code=fit["source_code"], development_inputs=inputs,
            role="post-unblinding development derivative; confirmation not read or retuned"),
        missing=["adaptive D->A", "arrival/queue-load-dependent preparation and callback cost",
                 "CPU/GPU overlap interference", "overrun residual distribution", "independent predictive acceptance criteria"],
        applicability="descriptive solo resident point estimates, not bounds/tail/independent validation")
    validate_config(config)
    return config, dict(protocol=VERSION, evidence_role="development observed joint vectors, not probability distribution",
                        cells=vectors), dict(protocol=VERSION, sessions=8, requests=32, lane_reuse_pairs=24,
                        role="existing calibration validator compatibility replay only", cells=replay)


def validate_config(config):
    require(config["protocol"] == VERSION and config["policy"] == POLICY and
            config["experiment_ready"] is False and set(config["cells"]) == CELLS, "configuration identity/readiness")
    require(config["scope"]["maximum_concurrency"] == 1 and config["scope"]["unit"] == "ns", "scope/units")
    for key, cell in config["cells"].items():
        require(cell["adaptive_decision_to_dispatch_ns"] is None, "unmeasured policy overhead cannot be fitted here")
        require(set(cell["observed_phases"]) == set(legacy.ALL_FIELDS) and set(cell["joint"]) == set(JOINTS), "interval schema")
        for value in [*cell["observed_phases"].values(), *cell["joint"].values()]:
            require(all(type(value[n]) in (int, float) and math.isfinite(value[n]) and value[n] >= 0
                        for n in ("median_ns", "min_ns", "max_ns")), "invalid measured duration")
            require(value["min_ns"] <= value["median_ns"] <= value["max_ns"], "invalid range")
        for field, value in cell["observed_phases"].items():
            priority = key.rsplit("_", 1)[1]
            require(value["response_use"] == calibration.usage(priority, field, "response") and
                    value["lane_use"] == calibration.usage(priority, field, "lane_from_dispatch"), "priority applicability")
    return True


def available(now=0):
    return dict(phase="AVAILABLE", request_id=None, task=None, priority=None, phase_since_ns=now, persist_since_ns=None)


def remaining(config, backend, lane, now):
    require(set(lane) == set(available()) and lane["phase_since_ns"] <= now, "causal lane schema")
    phase = lane["phase"]
    if phase == "AVAILABLE":
        return dict(ns=0, state="AVAILABLE")
    require(phase in PHASE_FIELDS, "unknown phase")
    key = f"{lane['task']}_{backend}_{lane['priority']}"
    require(key in config["cells"], "unsupported task/backend/priority")
    cell = config["cells"][key]
    origin = lane["persist_since_ns"] if phase in ("PERSISTED", "WORKER_RELEASED") else lane["phase_since_ns"]
    if origin is None:
        return dict(ns=None, state="UNKNOWN_MISSING_ORIGIN")
    require(origin <= now, "future phase origin")
    elapsed = now - origin
    # Guard the current phase median, but estimate the whole remaining joint interval.
    # W never restarts the P->L clock, and estimates never set AVAILABLE.
    if elapsed >= cell["observed_phases"][PHASE_FIELDS[phase]]["median_ns"]:
        return dict(ns=None, state="UNKNOWN_OVERRUN")
    left = cell["joint"][PHASE_JOINTS[phase]]["median_ns"] - elapsed
    return dict(ns=left if left > 0 else None, state="ESTIMATED_POINT" if left > 0 else "UNKNOWN_OVERRUN")


def decide(config, queue, lanes, now, *, assumed_common_decision_ns=None):
    """Only arrived tickets and observed lane phases. No outcome/realization argument.

    Strict mode exposes CAL-03 candidate estimates but keeps CPU fallback because
    adaptive D->A is missing. Explicit assumption mode ranks dispatch-relative
    response medians; it is a PC sensitivity choice, not an Android-ready policy.
    Both modes serialize globally while concurrency transfer is unmeasured.
    """
    require(set(lanes) == {"CPU", "GPU"}, "two lanes required")
    for ticket in queue:
        require(set(ticket) == {"id", "task", "priority", "ordinal", "arrival_ns"} and ticket["arrival_ns"] <= now,
                "future/unknown ticket information")
        require(ticket["priority"] in ("urgent", "normal") and ticket["task"] in ("classification", "detection"), "ticket type")
    require(len({t["id"] for t in queue}) == len(queue), "duplicate ticket")
    require(assumed_common_decision_ns is None or type(assumed_common_decision_ns) is int and assumed_common_decision_ns >= 0,
            "explicit nonnegative decision-cost assumption required")
    residuals = {b: remaining(config, b, lane, now) for b, lane in lanes.items()}
    ordered = sorted(queue, key=lambda t: (t["priority"] != "urgent", t["ordinal"], t["id"]))
    candidates = []
    for t in ordered:
        values = {}
        for b in ("CPU", "GPU"):
            cell = config["cells"][f"{t['task']}_{b}_{t['priority']}"]
            reply = cell["joint"]["dispatch_to_response_ns"]["median_ns"]
            values[b] = dict(dispatch_to_response_ns=reply,
                decision_to_response_ns=None if assumed_common_decision_ns is None else assumed_common_decision_ns + reply,
                dispatch_to_lane_ns=cell["joint"]["dispatch_to_lane_ns"]["median_ns"])
        candidates.append(dict(request_id=t["id"], predictions=values))
    selected = None
    if not queue:
        reason = "wait_empty"
    elif any(l["phase"] != "AVAILABLE" for l in lanes.values()):
        reason = "wait_solo_scope_busy"
    else:
        backend = "CPU" if assumed_common_decision_ns is None else min(("CPU", "GPU"),
            key=lambda b: (candidates[0]["predictions"][b]["decision_to_response_ns"], b != "CPU"))
        reason = "fallback_cpu_missing_adaptive_cost" if assumed_common_decision_ns is None else "assumed_common_cost_min_reply"
        selected = dict(request_id=ordered[0]["id"], backend=backend)
    return dict(policy=POLICY, now_ns=now, queue=copy.deepcopy(ordered), lanes=copy.deepcopy(lanes),
                residuals=residuals, candidates=candidates, selected=selected, reason=reason,
                assumed_common_decision_ns=assumed_common_decision_ns, experiment_ready=False)


def export(plan, fit, development, output):
    output = Path(output)
    require(not output.exists(), "output exists; preserve prior derivative")
    config, vectors, replay = derive(plan, fit, development)
    output.mkdir(parents=True)
    for name, obj in (("estimates.json", config), ("realizations.json", vectors), ("boundary_replay.json", replay)):
        (output / name).write_bytes(common.canonical(obj))
    receipt = dict(protocol=VERSION, files={p.name: common.digest(p) for p in output.iterdir()},
                   experiment_ready=False, device_calls=0, confirmation_read=False)
    (output / "receipt.json").write_bytes(common.canonical(receipt))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "fit", "development", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(export(args.plan, args.fit, args.development, args.output), indent=2))


if __name__ == "__main__":
    main()
