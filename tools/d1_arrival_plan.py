"""Versioned A24 asynchronous-arrival plans; planning never calls ADB."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import uuid

PROTOCOL = "arrival-scheduler-v1"
POLICIES = ("CPU_FIFO", "CPU_URGENT", "CONDITIONAL")
SOURCE_KEYS = ("classification_CPU", "classification_GPU", "detection_CPU", "detection_GPU")
ESTIMATES_MS = dict(classification_CPU=97, classification_GPU=250,
                    detection_CPU=558, detection_GPU=1063)
EVALUATION_ANALYSIS = dict(
    paired_unit="workload block, never request",
    fixed_primary_blocks=6,
    primary_contrast="CONDITIONAL-CPU_URGENT",
    mechanism_contrast="CPU_URGENT-CPU_FIFO",
    urgent_p95_minimum_relative_improvement=0.10,
    normal_mean_response_max_relative_loss=0.10,
    normal_on_time_rate_max_loss=0.02,
    completion_rate_max_loss=0.02,
    confidence_interval="two-sided 95% paired t interval on block-relative differences",
    primary_pass_rule="urgent upper confidence bound <= -0.10 and normal-loss upper bound <= 0.10",
    deadline_interpretation="descriptive engineering scenario, not a validated UX SLA",
    technical_failure_rule="no retry or replacement; preserve and report incomplete block",
    stopping_rule="run all 27 planned sessions unless a frozen safety/quality gate stops the run",
)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def recipes():
    """Three paired burst blocks, one reversed burst, low and queue sanity blocks."""
    result = [("burst", "classification", block) for block in range(3)]
    result += [("burst", "detection", 0), ("low", "classification", 0),
               ("queue", "classification", 0)]
    return result


def evaluation_recipes():
    """Six primary blocks plus three fixed supporting blocks; nine balanced triples."""
    result = [("burst", "classification", block) for block in range(6)]
    result += [("burst", "detection", 0), ("low", "classification", 0),
               ("queue", "classification", 0)]
    return result


def trace(kind, urgent_task):
    normal_task = "detection" if urgent_task == "classification" else "classification"
    if kind == "burst":
        events = [(0, normal_task, "normal"), (150, normal_task, "normal"),
                  (300, normal_task, "normal"), (450, urgent_task, "urgent"),
                  (500, urgent_task, "urgent"), (550, normal_task, "normal"),
                  (700, normal_task, "normal"), (850, normal_task, "normal")]
    elif kind == "queue":
        events = [(0, normal_task, "normal"), (200, normal_task, "normal"),
                  (400, normal_task, "normal"), (600, urgent_task, "urgent"),
                  (800, normal_task, "normal"), (1000, normal_task, "normal")]
    elif kind == "low":
        events = [(0, normal_task, "normal"), (3000, urgent_task, "urgent"),
                  (6000, normal_task, "normal"), (9000, urgent_task, "urgent")]
    else:
        raise ValueError(kind)
    return events


def source_catalog(source_plan):
    plan = read(source_plan)
    models, files, images = {}, {}, None
    fingerprint = None
    for entry in plan["entries"]:
        manifest_path = Path(entry["manifest"])
        manifest = read(manifest_path)
        fingerprint = fingerprint or manifest["device_fingerprint"]
        if fingerprint != manifest["device_fingerprint"]:
            raise ValueError("source device fingerprint mismatch")
        images = images or manifest["images"]
        for key, spec in manifest["models"].items():
            if key in SOURCE_KEYS:
                if key in models and models[key]["model"]["sha256"] != spec["model"]["sha256"]:
                    raise ValueError("source model mismatch")
                models[key] = spec
        for name, expected in entry["input_hashes"].items():
            if name == "manifest.json":
                continue
            path = manifest_path.parent / name
            if digest(path) != expected:
                raise ValueError(f"source changed: {path}")
            if name in files and files[name]["sha256"] != expected:
                raise ValueError(f"source filename collision: {name}")
            files[name] = dict(path=str(path.resolve()), sha256=expected, bytes=path.stat().st_size)
    if set(models) != set(SOURCE_KEYS) or images is None:
        raise ValueError("all four validated source cells are required")
    return models, files, images, fingerprint


def validate(plan, base):
    phase = plan["protocol"]
    if phase == "arrival-development-pilot-v1":
        expected_sessions, expected_groups = 19, 6
    elif phase == "arrival-independent-evaluation-v1":
        expected_sessions, expected_groups = 27, 9
        if plan.get("analysis_contract") != EVALUATION_ANALYSIS:
            raise ValueError("evaluation analysis contract changed")
    else:
        raise ValueError("unknown arrival plan protocol")
    if len(plan["entries"]) != expected_sessions:
        raise ValueError("plan size changed")
    if plan["session_cap"] != expected_sessions or plan["device_retry_cap"] != 0:
        raise ValueError("budget changed")
    for name, source in plan["source_files"].items():
        if digest(source["path"]) != source["sha256"] or Path(source["path"]).stat().st_size != source["bytes"]:
            raise ValueError(f"source file changed: {name}")
    for entry in plan["entries"]:
        manifest_path = base / entry["manifest"]
        if digest(manifest_path) != entry["manifest_sha256"]:
            raise ValueError("manifest changed")
        m = read(manifest_path)
        if m["protocol"] != PROTOCOL or m["session_id"] != entry["session_id"]:
            raise ValueError("session mismatch")
        if m["policy"] != entry["policy"] or m["estimated_service_ms"] != ESTIMATES_MS:
            raise ValueError("policy or estimates changed")
        if len(m["warmup_requests"]) != 8 or len(m["requests"]) != entry["request_count"]:
            raise ValueError("request count changed")
        offsets = [q["offset_ms"] for q in m["requests"]]
        if offsets != sorted(offsets):
            raise ValueError("arrival order changed")
        if any(q["deadline_ms"] != (2000 if q["priority"] == "urgent" else 8000) for q in m["requests"]):
            raise ValueError("deadline scenario changed")
    groups = {}
    for entry in plan["entries"]:
        if entry["kind"] == "smoke":
            continue
        m = read(base / entry["manifest"])
        signature = [(q["request_id"], q["task_id"], q["priority"], q["sample_id"],
                      q["offset_ms"], q["deadline_ms"]) for q in m["requests"]]
        groups.setdefault(entry["pair_id"], []).append((entry["policy"], signature))
    if len(groups) != expected_groups or any({p for p, _ in members} != set(POLICIES) or
                                              any(sig != members[0][1] for _, sig in members)
                                              for members in groups.values()):
        raise ValueError("paired workload mismatch")
    return dict(status="dry_run_pass", phase=phase, sessions=expected_sessions,
                requests=sum(e["request_count"] for e in plan["entries"]),
                paired_groups=expected_groups, adb_calls=0, model_invocations=0)


def generate(source_plan, apk, output):
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    models, files, images, fingerprint = source_catalog(source_plan)
    apk_hash = digest(apk)
    output.mkdir(parents=True)
    entries = []
    blocks = [("smoke", "classification", -1)] + recipes()
    for block_index, (kind, urgent_task, replicate) in enumerate(blocks):
        pair_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{PROTOCOL}/{kind}/{urgent_task}/{replicate}"))
        # Two complete Latin cycles across the six paired groups.
        order = [POLICIES[(i + block_index - 1) % 3] for i in range(3)] if kind != "smoke" else [POLICIES[0]]
        events = trace("low" if kind == "smoke" else kind, urgent_task)
        for policy in order:
            sid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{pair_id}/{policy}/pilot"))
            requests = []
            for ordinal, (offset, task, priority) in enumerate(events):
                rid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{pair_id}/{ordinal}"))
                requests.append(dict(request_id=rid, ordinal=ordinal, offset_ms=offset,
                                     task_id=task, priority=priority, sample_id=images[0]["sample_id"],
                                     deadline_ms=2000 if priority == "urgent" else 8000))
            warmups = [dict(request_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{sid}/warm/{key}/{i}")),
                            model_key=key, sample_id=images[0]["sample_id"])
                       for key in SOURCE_KEYS for i in range(2)]
            session_models = copy.deepcopy(models)
            for spec in session_models.values():
                spec["identity"]["session_id"] = sid
                spec["target"]["apk_sha256"] = apk_hash
            m = dict(protocol=PROTOCOL, session_id=sid, apk_sha256=apk_hash,
                     device_fingerprint=fingerprint, cpu_threads=1, maximum_concurrency=2,
                     maximum_duration_ms=120000, memory_contract="android-low-memory-resident-v1",
                     thermal_gate=0, policy=policy, estimated_service_ms=ESTIMATES_MS,
                     arrival_lag_limit_ms=100, models=session_models, images=images,
                     warmup_requests=warmups, requests=requests, pair_id=pair_id,
                     development_only=True, deadline_kind="engineering_scenario")
            path = output / "manifests" / f"{sid}.json"
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(canonical(m))
            entries.append(dict(index=len(entries), kind=kind, urgent_task=urgent_task,
                                replicate=replicate, pair_id=pair_id, policy=policy, session_id=sid,
                                request_count=len(requests), manifest=str(path.relative_to(output)),
                                manifest_sha256=digest(path)))
    plan = dict(protocol="arrival-development-pilot-v1", status="planned_not_measured",
                source_plan=str(Path(source_plan).resolve()), source_files=files,
                apk_path=str(Path(apk).resolve()), apk_sha256=apk_hash,
                device_fingerprint=fingerprint, session_cap=19, device_retry_cap=0,
                entry_order="one smoke; three cyclic primary burst blocks; reversed burst; low; queue",
                cool_down_seconds=120, maximum_duration_seconds=120,
                worst_case_device_minutes=19 * 4, entries=entries)
    result = validate(plan, output)
    (output / "pilot_plan.json").write_bytes(canonical(plan))
    return result


def generate_evaluation(source_plan, apk, output):
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    models, files, images, fingerprint = source_catalog(source_plan)
    apk_hash = digest(apk)
    output.mkdir(parents=True)
    entries = []
    for block_index, (kind, urgent_task, replicate) in enumerate(evaluation_recipes()):
        pair_id = str(uuid.uuid5(
            uuid.NAMESPACE_URL, f"{PROTOCOL}/evaluation/{kind}/{urgent_task}/{replicate}"))
        order = [POLICIES[(i + block_index) % 3] for i in range(3)]
        events = trace(kind, urgent_task)
        for policy in order:
            sid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{pair_id}/{policy}/evaluation"))
            requests = []
            for ordinal, (offset, task, priority) in enumerate(events):
                rid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{pair_id}/{ordinal}"))
                requests.append(dict(request_id=rid, ordinal=ordinal, offset_ms=offset,
                                     task_id=task, priority=priority,
                                     sample_id=images[0]["sample_id"],
                                     deadline_ms=2000 if priority == "urgent" else 8000))
            warmups = [dict(
                request_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{sid}/warm/{key}/{i}")),
                model_key=key, sample_id=images[0]["sample_id"])
                for key in SOURCE_KEYS for i in range(2)]
            session_models = copy.deepcopy(models)
            for spec in session_models.values():
                spec["identity"]["session_id"] = sid
                spec["target"]["apk_sha256"] = apk_hash
            manifest = dict(
                protocol=PROTOCOL, session_id=sid, apk_sha256=apk_hash,
                device_fingerprint=fingerprint, cpu_threads=1, maximum_concurrency=2,
                maximum_duration_ms=120000, memory_contract="android-low-memory-resident-v1",
                thermal_gate=0, policy=policy, estimated_service_ms=ESTIMATES_MS,
                arrival_lag_limit_ms=100, models=session_models, images=images,
                warmup_requests=warmups, requests=requests, pair_id=pair_id,
                development_only=False, evaluation_phase="independent",
                deadline_kind="engineering_scenario")
            path = output / "manifests" / f"{sid}.json"
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(canonical(manifest))
            entries.append(dict(
                index=len(entries), kind=kind, urgent_task=urgent_task,
                replicate=replicate, pair_id=pair_id, policy=policy, session_id=sid,
                request_count=len(requests), manifest=str(path.relative_to(output)),
                manifest_sha256=digest(path)))
    plan = dict(
        protocol="arrival-independent-evaluation-v1", status="proposed_not_approved",
        source_plan=str(Path(source_plan).resolve()), source_files=files,
        apk_path=str(Path(apk).resolve()), apk_sha256=apk_hash,
        device_fingerprint=fingerprint, session_cap=27, device_retry_cap=0,
        entry_order="six cyclic primary burst blocks; reversed burst; low; queue",
        cool_down_seconds=120, maximum_duration_seconds=120,
        estimated_device_minutes=65, worst_case_device_minutes=120,
        analysis_contract=EVALUATION_ANALYSIS, entries=entries)
    result = validate(plan, output)
    (output / "evaluation_plan.json").write_bytes(canonical(plan))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("generate")
    make.add_argument("--source-plan", type=Path, required=True)
    make.add_argument("--apk", type=Path, required=True)
    make.add_argument("--output", type=Path, required=True)
    evaluation = sub.add_parser("generate-evaluation")
    evaluation.add_argument("--source-plan", type=Path, required=True)
    evaluation.add_argument("--apk", type=Path, required=True)
    evaluation.add_argument("--output", type=Path, required=True)
    check = sub.add_parser("dry-run")
    check.add_argument("--plan", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "generate":
        result = generate(args.source_plan, args.apk, args.output)
    elif args.command == "generate-evaluation":
        result = generate_evaluation(args.source_plan, args.apk, args.output)
    else:
        result = validate(read(args.plan), args.plan.parent)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
