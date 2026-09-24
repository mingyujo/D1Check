"""Boundary-only, single-use calibration preparation. prepare/check never access a device."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import statistics
import uuid

from tools import d1_arrival_plan as p
from tools import d1_arrival_timing_dev as v

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "arrival-timing-calibration-plan-v1"
OBSERVATION = "arrival-phase-observations-v2"
EXPERIMENT = "ARRIVAL-TIMING-CAL-01"
SEED = 2026092401
STAGES = ("development", "confirmation")
CONDITIONS = [(t, b, priority) for t in ("classification", "detection") for b in ("CPU", "GPU")
              for priority in ("urgent", "normal")]
SOURCE_SHA = "9e826188a25ecc9ca33404995cc1e45238f00f539fbb3c41eabfcdb8295cf3c3"
CODE = ["tools/d1_arrival_timing_calibration.py", "tools/d1_arrival_timing_calibration_device.py",
        "tools/d1_apk_identity.py",
        "tools/d1_arrival_failure_evidence.py",
        "tools/d1_arrival_timing_dev.py", "tools/d1_arrival_plan.py", "tools/d1_arrival_device.py", "tools/d1_telemetry_v4.py",
        "tools/arrival_timing_isolated_build.gradle"] + [
    f"benchmark-runner/src/modelProbe/java/com/example/d1check/benchmarkrunner/{name}.kt"
    for name in ("ArrivalTimingDev", "ArrivalSchedulerActivity", "ArrivalPolicy", "ProbeRawAdapter", "ProbeTaskAdapter")]


def write_new(path, data):
    path = Path(path)
    with path.open("xb") as stream:
        stream.write(p.canonical(data))


def code_identity():
    names = set(CODE)
    for module in ("benchmark-runner", "telemetry-contract"):
        names.add(f"{module}/build.gradle.kts")
        for source in (ROOT / module / "src").rglob("*"):
            if source.is_file() and (source.suffix in (".kt", ".java", ".xml", ".cpp", ".h", ".json") or source.name == "CMakeLists.txt"):
                names.add(source.relative_to(ROOT).as_posix())
    for name in ("build.gradle.kts", "settings.gradle.kts", "gradle.properties", "gradle/libs.versions.toml", "gradle/wrapper/gradle-wrapper.properties"):
        if (ROOT / name).is_file():
            names.add(name)
    return {name: p.digest(ROOT / name) for name in sorted(names)}


def apk_sources(identity):
    """Host Python is bound by the plan, not compiled into the APK. Keep build receipts immutable."""
    return {name: sha for name, sha in identity.items()
            if (not name.startswith("tools/") or name.endswith(".gradle"))
            and "/src/test/" not in name and "/src/androidTest/" not in name}


def pending():
    return {"contract": v.CONTRACT, "version": "calibration-no-estimates-v1",
            "provenance": "UNMEASURED; fixed backend observations only",
            "budgets": {k: dict.fromkeys(v.ALL_FIELDS) for k in sorted(v.KEYS)}}


def layout():
    order = list(CONDITIONS)
    random.Random(SEED).shuffle(order)
    return [(stage, *cell) for stage in STAGES for cell in (order if stage == "development" else list(reversed(order)))]


def make_manifest(template, index, apk_sha, experiment=EXPERIMENT):
    stage, task, backend, priority = layout()[index]
    sid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{experiment}/{SEED}/{stage}/{task}/{backend}/{priority}"))
    m = copy.deepcopy(template)
    for field in ("estimated_service_ms", "pair_id", "evaluation_phase"):
        m.pop(field, None)
    m.update(protocol=v.CAL_PROTOCOL, policy=v.CAL_POLICY, session_id=sid, apk_sha256=apk_sha,
             experiment_id=experiment, collection_phase=stage, execution_purpose="boundary_calibration_only",
             development_only=True, experiment_ready=False, calibration_backend=backend,
             storage_mode="persist_all", observation_contract=OBSERVATION, maximum_concurrency=1,
             timing_estimates=pending(), cpu_threads=1, thermal_gate=0, maximum_duration_ms=120000,
             arrival_lag_limit_ms=100, deadline_kind="diagnostic_bound_not_UX_SLA")
    for spec in m["models"].values():
        spec["identity"]["session_id"] = sid
        spec["target"]["apk_sha256"] = apk_sha
    sample = m["images"][0]["sample_id"]
    m["requests"] = [dict(request_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{sid}/diagnostic/{n}")),
                          ordinal=n, task_id=task, priority=priority, sample_id=sample, offset_ms=n * 5000,
                          deadline_ms=5000) for n in range(4)]
    m["warmup_requests"] = [dict(request_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{sid}/warm/{k}/{n}")),
                                 model_key=k, sample_id=sample) for k in p.SOURCE_KEYS for n in range(2)]
    return m


def specification(source_file, apk=None, build_receipt=None, recovery=None, followup=None):
    source_file = Path(source_file).resolve()
    v.require(p.digest(source_file) == SOURCE_SHA, "reference plan identity changed")
    old = p.read(source_file)
    template_file = source_file.parent / old["entries"][0]["manifest"]
    v.require(p.digest(template_file) == old["entries"][0]["manifest_sha256"], "template identity")
    template = p.read(template_file)
    apk_sha = p.digest(apk) if apk is not None else None
    if apk is not None:
        v.require(apk_sha != old["apk_sha256"], "old frozen APK cannot implement calibration")
    v.require(not (recovery and followup), "recovery and followup are exclusive")
    experiment = "ARRIVAL-TIMING-CAL-03" if followup is not None else EXPERIMENT if recovery is None else "ARRIVAL-TIMING-CAL-02"
    manifests, entries = {}, []
    for i, (stage, task, backend, priority) in enumerate(layout()):
        m = make_manifest(template, i, apk_sha, experiment)
        name = f"manifests/{m['session_id']}.json"
        manifests[name] = m
        entries.append(dict(index=i, phase=stage, task=task, backend=backend, priority=priority,
                            session_id=m["session_id"], manifest=name, manifest_sha256=hashlib.sha256(p.canonical(m)).hexdigest(),
                            diagnostic_requests=4, warmup_calls=8))
    plan = dict(protocol=PROTOCOL, experiment_id=experiment, seed=SEED, source_plan=str(source_file),
                source_plan_sha256=SOURCE_SHA, source_files=old["source_files"], device_fingerprint=old["device_fingerprint"],
                apk_path=str(Path(apk).resolve()) if apk else None, apk_sha256=apk_sha,
                build_receipt=str(Path(build_receipt).resolve()) if build_receipt else None,
                build_receipt_sha256=p.digest(build_receipt) if build_receipt else None,
                status="proposed_budget_not_approved", experiment_ready=False,
                registry=str(source_file.parent.parent / "timing_calibration_execution_registry" / experiment),
                session_cap=16, diagnostic_request_cap=64, warmup_call_cap=128,
                device_retry_cap=0, replacement_cap=0, additional_session_cap=0,
                cool_down_seconds=120, initial_cool_seconds=120, host_phase_wall_seconds=3600,
                cleanup_seconds=45, battery_start_percent=55, battery_min_percent=30,
                battery_max_temperature_tenths_c=350, require_unplugged=True,
                estimated_active_minutes=[45, 60], maximum_active_seconds=7290,
                analysis_contract="one independent development session and one subsequent confirmation session per cell; four correlated requests/session; median/range only; no tail or superiority claim",
                source_code=code_identity(), entries=entries)
    if recovery is not None:
        parent_path = Path(recovery['parent_plan'])
        v.require(p.digest(parent_path) == recovery['parent_plan_sha256'], 'recovery parent identity')
        parent = p.read(parent_path)
        v.require(parent['experiment_id'] == EXPERIMENT and parent['apk_sha256'] != apk_sha,
                  'new APK and stopped parent required')
        stopped = Path(parent['registry']) / 'development_stopped.json'
        v.require(p.digest(stopped) == recovery['parent_stopped_sha256']
                  and p.read(stopped)['plan_sha256'] == recovery['parent_plan_sha256'], 'parent stop identity')
        plan['recovery'] = recovery
        plan['apk_preflight'] = recovery['apk_preflight']
        v.require(plan['apk_preflight']['candidate']['apk_sha256'] == apk_sha, 'candidate APK binding')
    if followup is not None:
        validate_followup(followup, apk_sha)
        plan['followup'] = followup
        plan['apk_preflight'] = followup['apk_preflight']
        plan['require_awake_interactive'] = True
        if 'execution_contract' in followup:
            execution_contract=followup['execution_contract']
            v.require(execution_contract['version']=='cal03-screen-and-freeze-v1', 'unknown execution contract')
            v.require(execution_contract['poll_interval_seconds']==10, 'screen poll interval fixed')
            plan['screen_contract']=execution_contract
        plan['collection_logging'] = 'no_failure_diagnostic_journal; in_memory_timing_trace_then_final_flush'
    return plan, manifests


def validate_followup(binding, apk_sha):
    """Provenance gate only; successful synchronous diagnosis is never calibration input."""
    required = ('parent_plan', 'parent_stopped', 'diagnostic_plan', 'diagnostic_receipt', 'diagnostic_verification')
    for key in required:
        v.require(p.digest(binding[key]) == binding[key+'_sha256'], 'followup identity: '+key)
    parent = p.read(binding['parent_plan'])
    stopped = p.read(binding['parent_stopped'])
    diagnostic = p.read(binding['diagnostic_plan'])
    receipt = p.read(binding['diagnostic_receipt'])
    verification = p.read(binding['diagnostic_verification'])
    v.require(parent['experiment_id'] == 'ARRIVAL-TIMING-CAL-02' and stopped['status'] == 'stopped_no_retry'
              and stopped['plan_sha256'] == binding['parent_plan_sha256'], 'closed CAL-02 provenance')
    v.require(diagnostic['experiment_id'] == 'ARRIVAL-STALL-OBS-DIAG-01' and diagnostic['apk_sha256'] == apk_sha
              and verification['plan_sha256'] == binding['diagnostic_plan_sha256']
              and verification['status'] == 'PASS_DIAGNOSTIC_ONLY', 'diagnostic provenance')
    v.require(receipt['status'] == 'complete_not_cause_resolved' and receipt['no_resume'] is True
              and receipt['runtime_returned'] == 4 and receipt['performance_eligible'] is False
              and all(receipt['counts'][k] == count for k,count in
                      [('session_attempts',1),('warmup_calls',8),('diagnostic_requests',1),('inference_calls',9)]),
              'complete integrated diagnosis required; not performance calibration')
    v.require(binding['apk_preflight']['candidate']['apk_sha256'] == apk_sha, 'followup APK binding')


def prepare(source, output, apk=None, build_receipt=None, recovery=None, followup=None):
    output = Path(output)
    v.require(not output.exists(), "new preparation path required")
    plan, manifests = specification(source, apk, build_receipt, recovery, followup)
    if apk is not None:
        v.require(build_receipt is not None, "isolated build receipt required")
        receipt = p.read(build_receipt)
        v.require(receipt["apk_sha256"] == plan["apk_sha256"] and apk_sources(receipt["source_code"]) == apk_sources(plan["source_code"]), "APK/source receipt mismatch")
        v.require(receipt["status"] == "built_not_device_verified", "build receipt status")
    (output / "manifests").mkdir(parents=True)
    for name, manifest in manifests.items():
        write_new(output / name, manifest)
    write_new(output / "calibration_plan.json", plan)
    return check(output / "calibration_plan.json")


def check(plan_file, for_execution=False):
    plan_file = Path(plan_file)
    plan = p.read(plan_file)
    v.require(plan["protocol"] == PROTOCOL and plan["experiment_ready"] is False, "calibration-only plan required")
    expected, manifests = specification(plan["source_plan"], plan["apk_path"], plan["build_receipt"], plan.get('recovery'), plan.get('followup'))
    v.require(plan == expected, "plan/code/budget/order changed")
    for name, manifest in manifests.items():
        v.require((plan_file.parent / name).read_bytes() == p.canonical(manifest), "manifest changed")
    for name, info in plan["source_files"].items():
        source = Path(info["path"])
        v.require(source.stat().st_size == info["bytes"] and p.digest(source) == info["sha256"], f"input identity: {name}")
    if plan["apk_path"] is not None:
        receipt = p.read(plan["build_receipt"])
        v.require(receipt["status"] == "built_not_device_verified" and apk_sources(receipt["source_code"]) == apk_sources(plan["source_code"])
                  and receipt["apk_sha256"] == plan["apk_sha256"], "APK/source receipt mismatch")
    if 'apk_preflight' in plan:
        from tools import d1_apk_identity as apk_identity
        gate = plan['apk_preflight']
        for name, digest in gate['tool_sha256'].items():
            v.require(p.digest(gate['toolchain'][name]) == digest, 'signature tool changed')
        v.require(apk_identity.inspect(plan['apk_path'], gate['toolchain']) == gate['candidate'],
                  'candidate signature identity changed')
    if for_execution:
        v.require(plan["apk_path"] is not None, "unbound APK; proposal cannot execute")
    return dict(status="PC_PLAN_VALID_NOT_MEASURED", sessions=16, diagnostic_requests=64, warmup_calls=128,
                source_code=plan["source_code"], apk_bound=plan["apk_path"] is not None,
                experiment_ready=False, adb_calls=0, model_invocations=0, generated_measurements=0,
                plan_sha256=p.digest(plan_file))


def claim(plan, phase, output, freeze=None):
    """Atomic phase claim before install. Recovery v2 does read-only signature preflight first."""
    v.require(plan["protocol"] == PROTOCOL and phase in STAGES, "calibration phase only")
    output = Path(output).resolve()
    v.require(not output.exists(), "existing output; recovery only")
    registry = Path(plan["registry"])
    registry.mkdir(parents=True, exist_ok=True)
    v.require(not any(registry.glob("*_stopped.json")), "previous failure; recovery only, no next phase")
    if phase == "confirmation":
        v.require((registry / "development_complete.json").is_file() and freeze is not None, "development/freeze incomplete")
        v.require(p.read(registry / "development_complete.json")["plan_sha256"] == hashlib.sha256(p.canonical(plan)).hexdigest(), "development plan mismatch")
        frozen = p.read(freeze)
        v.require(frozen["protocol"] == "arrival-timing-calibration-fit-v1" and frozen["source_code"] == plan["source_code"], "fit freeze identity")
    write_new(registry / f"{phase}_consumed.json", dict(phase=phase, output=str(output),
              experiment_id=plan["experiment_id"], plan_sha256=hashlib.sha256(p.canonical(plan)).hexdigest(),
              freeze_sha256=p.digest(freeze) if freeze else None))
    output.mkdir(parents=True)  # A failed mkdir still consumes the phase; do not silently retry.


def usage(priority, field, purpose):
    v.require(priority in ("urgent", "normal") and field in v.ALL_FIELDS, "usage identity")
    if purpose == "response":
        applicable = field in v.ALL_FIELDS[:3 if priority == "urgent" else 4]
    elif purpose == "lane_from_dispatch":
        applicable = field != v.DECISION_FIELD
    else:
        raise ValueError("unknown prediction purpose")
    return "applicable" if applicable else "not_applicable"


def observations(artifacts):
    """Only actual complete calibration artifacts; never synthesizes durations."""
    artifacts = Path(artifacts)
    diagnostic_manifest = p.read(artifacts / 'manifest.json')
    v.require(not diagnostic_manifest.get('failure_diagnostic_contract')
              and not diagnostic_manifest.get('performance_excluded', False),
              'failure diagnosis is not calibration/performance data')
    result = v.validate_artifacts(artifacts)
    manifest, trace, rows = (p.read(artifacts / name) for name in ("manifest.json", "decision_trace.json", "requests.json"))
    summary = p.read(artifacts / "summary.json")
    v.require(manifest["protocol"] == v.CAL_PROTOCOL and result["session_status"] == "completed"
              and result["cleanup_status"] == "completed", "incomplete diagnostic session")
    v.require(len(rows) == 4 and all(r["terminal_status"] == "succeeded" for r in rows), "failed diagnostic denominator")
    v.require(len({(r["task_id"], r["priority"], r["selected_backend"], r["sample_id"]) for r in rows}) == 1, "mixed diagnostic cell")
    planned = {q["request_id"]: q for q in manifest["requests"]}
    for row in rows:
        q = planned[row["request_id"]]
        v.require(row["scheduled_arrival_ns"] == summary["workload_start_ns"] + q["offset_ms"] * 1_000_000
                  and row["actual_arrival_ns"] >= row["scheduled_arrival_ns"]
                  and row["arrival_lag_ns"] == row["actual_arrival_ns"] - row["scheduled_arrival_ns"]
                  and row["deadline_ns"] == row["scheduled_arrival_ns"] + q["deadline_ms"] * 1_000_000, "arrival/deadline boundary")
    intervals = sorted((r["actual_arrival_ns"], r["lane_available_ns"]) for r in rows)
    v.require(all(a[1] <= b[0] for a, b in zip(intervals, intervals[1:])), "not isolated at actual arrival")
    starts = {r["selected"]["request_id"]: r["mono_ns"] for r in trace["records"] if r["kind"] == "decision" and r["selected"]}
    warm = p.read(artifacts / "warmup_trace.json")
    expected = {q["request_id"]: q["model_key"] for q in manifest["warmup_requests"]}
    v.require(len(expected) == 8 and len(warm) == 16, "warmup planned/started/ended count")
    for i, (rid, key) in enumerate(expected.items()):
        a, b = warm[2 * i:2 * i + 2]
        v.require(a["kind"] == "start" and b["kind"] == "end" and b["status"] == "succeeded"
                  and a["request_id"] == b["request_id"] == rid and a["model_key"] == b["model_key"] == key
                  and a["mono_ns"] <= b["mono_ns"] <= min(r["actual_arrival_ns"] for r in rows), "warmup identity/boundary")
        if i:
            v.require(warm[2 * i - 1]["mono_ns"] <= a["mono_ns"], "warmup overlap")
    samples = []
    for r in rows:
        times = [starts[r["request_id"]], r["dispatch_ns"], r["execution_start_ns"], r["output_ready_ns"],
                 r["persist_complete_ns"], r["lane_available_ns"]]
        samples.append(dict(request_id=r["request_id"], priority=r["priority"], ordinal=r["ordinal"],
                            values=dict(zip(v.ALL_FIELDS, [b - a for a, b in zip(times, times[1:])]))))
    return samples


def phase_inputs(plan_file, phase, run):
    check(plan_file, for_execution=True)
    plan, run = p.read(plan_file), Path(run).resolve()
    registry = Path(plan["registry"])
    v.require((registry / f"{phase}_complete.json").is_file() and (run / "complete.json").is_file(), "phase not complete")
    v.require(p.read(registry / f"{phase}_consumed.json")["output"] == str(run), "run identity")
    v.require(p.read(run / "complete.json")["plan_sha256"] == p.digest(plan_file), "run plan identity")
    cells, inputs = {}, {}
    for e in plan["entries"]:
        if e["phase"] != phase:
            continue
        folder = run / f"{e['index']:02d}_{e['session_id']}"
        v.require((folder / "validated.json").is_file() and (folder / "host_cleanup.json").is_file(), "session not validated/cleaned")
        v.require(p.read(folder / "host_cleanup.json")["status"] == "completed", "host cleanup failed")
        artifacts = folder / "artifacts"
        v.require(p.digest(artifacts / "manifest.json") == e["manifest_sha256"], "collected manifest mismatch")
        if plan.get('screen_contract'):
            screen=folder/'screen_observations'
            samples=sorted(screen.glob('*.json'))
            v.require((screen/'before_launch.json').is_file() and (screen/'poll_complete.json').is_file()
                      and (screen/'after_recovery.json').is_file() and (screen/'poll_00.json').is_file(), 'screen evidence missing')
            v.require(all(p.read(f)['status']=='sample_pass' for f in samples), 'screen evidence failed')
            for source in sorted(screen.iterdir()):
                if source.is_file():inputs[str(source)]=p.digest(source)
            inputs[str(folder/'validated.json')]=p.digest(folder/'validated.json')
            inputs[str(folder/'host_cleanup.json')]=p.digest(folder/'host_cleanup.json')
        cells[f"{e['task']}_{e['backend']}_{e['priority']}"] = observations(artifacts)
        for source in sorted(artifacts.iterdir()):
            if source.is_file():
                inputs[str(source)] = p.digest(source)
    v.require(len(cells) == 8, "incomplete cells; no fit or replacement")
    return plan, cells, inputs


def fit(plan_file, run, output):
    plan, cells, inputs = phase_inputs(plan_file, "development", run)
    estimates = {}
    for cell, samples in cells.items():
        priority = samples[0]["priority"]
        estimates[cell] = {}
        for field in v.ALL_FIELDS:
            values = [s["values"][field] for s in samples]
            estimates[cell][field] = dict(status="observed_development", median_ns=statistics.median(values),
                min_ns=min(values), max_ns=max(values), independent_sessions=1, correlated_requests=4,
                response_use=usage(priority, field, "response"), lane_use=usage(priority, field, "lane_from_dispatch"),
                adaptive_transfer="missing_policy_specific_measurement" if field == v.DECISION_FIELD else "unvalidated_solo_candidate")
    result = dict(protocol="arrival-timing-calibration-fit-v1", observation_contract=OBSERVATION,
                  plan_sha256=p.digest(plan_file), source_code=plan["source_code"], input_hashes=inputs,
                  experiment_ready=False, conditional_v1_budgets_unchanged=True, estimates=estimates,
                  interpretation="n=1 independent development session/cell; median/range descriptive, not tail or predictive coverage")
    write_new(output, result)
    return {"fit_file": str(output), "sha256": p.digest(output), "experiment_ready": False}


def confirm(plan_file, run, freeze, output):
    plan, cells, inputs = phase_inputs(plan_file, "confirmation", run)
    frozen = p.read(freeze)
    claim_record = p.read(Path(plan["registry"]) / "confirmation_consumed.json")
    v.require(claim_record["freeze_sha256"] == p.digest(freeze) and frozen["plan_sha256"] == p.digest(plan_file), "changed freeze")
    for path, sha in frozen["input_hashes"].items():
        v.require(p.digest(path) == sha, "development evidence changed")
    errors = {}
    for cell, samples in cells.items():
        errors[cell] = {}
        for field in v.ALL_FIELDS:
            predicted = frozen["estimates"][cell][field]["median_ns"]
            actual = [s["values"][field] for s in samples]
            errors[cell][field] = dict(frozen_median_ns=predicted, actual_ns=actual,
                signed_error_ns=[x - predicted for x in actual], overruns=sum(x > predicted for x in actual),
                denominator=4, independent_sessions=1, interpretation="diagnostic point counts; no tail/coverage guarantee")
    write_new(output, dict(protocol="arrival-timing-calibration-confirmation-v1", freeze_sha256=p.digest(freeze),
                          plan_sha256=p.digest(plan_file), input_hashes=inputs, errors=errors,
                          experiment_ready=False, performance_pass=None, unknown_overrun_rule="unchanged"))
    return {"report": str(output), "experiment_ready": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("prepare")
    make.add_argument("--source-plan", type=Path, required=True)
    make.add_argument("--output", type=Path, required=True)
    make.add_argument("--apk", type=Path)
    make.add_argument("--build-receipt", type=Path)
    make.add_argument("--recovery-binding", type=Path, help="PC-created immutable parent/signature binding")
    make.add_argument("--followup-binding", type=Path, help="PC-only CAL-03 provenance after integrated diagnosis")
    inspect = sub.add_parser("check")
    inspect.add_argument("--plan", type=Path, required=True)
    build = sub.add_parser("package")
    build.add_argument("--output", type=Path, required=True)
    for name in ("fit", "confirm"):
        cmd = sub.add_parser(name)
        for flag in ("--plan", "--run", "--output"):
            cmd.add_argument(flag, type=Path, required=True)
        if name == "confirm":
            cmd.add_argument("--freeze", type=Path, required=True)
    run = sub.add_parser("run")
    for flag in ("--plan", "--adb", "--output"):
        run.add_argument(flag, type=Path, required=True)
    run.add_argument("--phase", choices=STAGES, required=True)
    run.add_argument("--approved-total-cap", type=int, required=True)
    run.add_argument("--expected-plan-sha256", required=True)
    run.add_argument("--serial", required=True)
    run.add_argument("--freeze", type=Path)
    recovery = sub.add_parser("recover")
    for flag in ("--plan", "--adb", "--output"):
        recovery.add_argument(flag, type=Path, required=True)
    recovery.add_argument("--serial", required=True)
    recovery.add_argument("--session-id", required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.source_plan, args.output, args.apk, args.build_receipt,
                         p.read(args.recovery_binding) if args.recovery_binding else None,
                         p.read(args.followup_binding) if args.followup_binding else None)
    elif args.command == "check":
        result = check(args.plan)
    elif args.command == "fit":
        result = fit(args.plan, args.run, args.output)
    elif args.command == "confirm":
        result = confirm(args.plan, args.run, args.freeze, args.output)
    else:
        from tools import d1_arrival_timing_calibration_device as device
        if args.command == "package":
            result = device.package(args.output)
        elif args.command == "recover":
            result = device.recover(args.plan, args.adb, args.serial, args.session_id, args.output)
        else:
            result = device.run(args.plan, args.phase, args.output, args.adb, args.serial,
                                args.approved_total_cap, args.expected_plan_sha256, args.freeze)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
