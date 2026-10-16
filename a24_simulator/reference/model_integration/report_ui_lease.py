"""Registered saved-report render/UI QA under the original worker lease.

Source preparation only. No import-time work, refit, simulator or scheduling.
The frozen audit lease helper supplies CIM ancestry and a kill-on-exit job;
the unchanged runtime_guard.operation owns lock/reserve/pins/original351.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import ntpath
import os
from pathlib import Path
import subprocess
import sys

FROZEN_GUARD_SHA = "d2583f2b6d3e92197893bb97736543723dd99c0e924a75a843a2cb3f08b83735"
FROZEN_AUDIT_LEASE_SHA = "71d9a7b184b8a42a06155a478ad5dd1952a7ba163c85c6ad8b83170bc742c276"
ORIGINAL_LOCK = "C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/outputs/A24-INTEGRATED-SIM-20261016-G002/worker.lock"
MANIFEST_SCHEMA = "A24-model-report-UI-lease-manifest-v2"
STAGE_STATUS = {"render": "RENDERED_PENDING_REGISTERED_UI_QA", "qa": "PASS_UI_BINDING_AND_LAYOUT_ONLY"}
ZERO_FIELDS = ("new_environment", "new_fit", "NN", "optimizer", "HTTP", "device_commands")


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def canon(value):
    require(isinstance(value, str) and ntpath.isabs(value), "Absolute Windows path required")
    return ntpath.normcase(ntpath.normpath(value))


def has_pin(spec, roster):
    return any(canon(p["path"]) == canon(spec["path"]) and p["sha256"] == spec["sha256"] for p in roster)


def validate_manifest(op, manifest, operation_path, entry):
    """Pure contract checks; fixtures do not start processes or read files."""
    require(op["mode"] == "REPORT_UI", "Exact REPORT_UI operation required")
    require(manifest["schema"] == MANIFEST_SCHEMA and manifest.get("allow_execution") is True,
            "Registered UI manifest required")
    require(op.get("automatic_retry") is False and manifest.get("automatic_retry") is False, "No automatic retry")
    for obj in (op, manifest):
        require(all(type(obj.get(k)) is int and obj[k] == 0 for k in ZERO_FIELDS), "Saved-only zero boundary")
    require(canon(op["worker_lock_path"]) == canon(ORIGINAL_LOCK) == canon(manifest["worker_lock_path"]), "Original shared lock")
    require(canon(manifest["expected_lease_operation_path"]) == canon(operation_path), "Future operation path differs")
    require(canon(manifest["lease_wrapper_entry_pin"]["path"]) == canon(entry), "Actual wrapper entry differs")
    require(has_pin(manifest["lease_wrapper_entry_pin"], op["source_pins"]), "Wrapper not source pinned")
    require(canon(manifest["output_dir"]) == canon(op["output_dir"]), "UI lease output namespace differs")
    filename = manifest["rendered_html_filename"]
    require(isinstance(filename, str) and ntpath.basename(filename) == filename and filename.endswith(".html"),
            "Fresh HTML filename only; no path traversal")
    require(filename not in ("report.template.html", "view.template.html"), "Never replace a source template")
    require(len(op["protected_pins"]) == 351 and len(manifest["protected_pins"]) == 351, "Original351 roster required")
    roster = lambda xs: sorted((canon(p["path"]), p["sha256"]) for p in xs)
    require(roster(op["protected_pins"]) == roster(manifest["protected_pins"]), "Protection rosters differ")
    require(manifest.get("expected_sessions") == 115, "All115 observed sessions required")
    require(has_pin(op["ui_manifest_pin"], op["input_pins"]), "UI manifest not input pinned")
    for name in ("data_pin", "template_pin", "node_executable_pin", "chrome_executable_pin", "playwright_entry_pin"):
        require(has_pin(manifest[name], op["input_pins"]), "Missing operation input: " + name)
    for name in ("renderer_pin", "qa_pin", "node_guard_pin"):
        require(has_pin(manifest[name], op["source_pins"]), "Missing operation source: " + name)
    require(any(ntpath.basename(p["path"]) == "runtime_guard.py" and p["sha256"] == FROZEN_GUARD_SHA for p in op["source_pins"]),
            "Exact frozen runtime guard required")
    require(any(ntpath.basename(p["path"]) == "audit_lease.py" and p["sha256"] == FROZEN_AUDIT_LEASE_SHA for p in op["source_pins"]),
            "Exact frozen ancestry/job helper required")
    return True


def stage_command(stage, manifest, manifest_path):
    require(stage in STAGE_STATUS, "Unknown UI child stage")
    entry = manifest["renderer_pin" if stage == "render" else "qa_pin"]["path"]
    for p in (manifest["node_executable_pin"]["path"], entry, manifest_path):
        canon(p)
    return [manifest["node_executable_pin"]["path"], "--max-old-space-size=4096", entry, "--manifest", manifest_path]


def accepted_stage(stage, return_code, result, manifest_sha):
    return (stage in STAGE_STATUS and return_code == 0 and result.get("status") == STAGE_STATUS[stage]
            and result.get("manifest_sha256") == manifest_sha
            and all(type(result.get(k)) is int and result[k] == 0 for k in ZERO_FIELDS)
            and result.get("measured_J") is None and result.get("physical_goal_pass") is False
            and (stage != "qa" or (type(result.get("failed_checks")) is int and result["failed_checks"] == 0
                    and type(result.get("checks")) is int and result["checks"] > 0
                    and result.get("HTTP_attempts") == [] and result.get("JS_errors") == []
                    and result.get("observed_sessions_with_all_source_curve_coordinates_checked") == 115
                    and type(result.get("scenario_policy_states_checked")) is int and result["scenario_policy_states_checked"] > 0
                    and len(result.get("states", [])) == 6
                    and {(s.get("theme"), s.get("width"), s.get("status")) for s in result["states"]} ==
                        {(theme,width,"PASS") for theme in ("light","dark") for width in (360,736,1280)})))


def load_exact(name, filename, expected_sha):
    source = Path(__file__).with_name(filename)
    require(hashlib.sha256(source.read_bytes()).hexdigest() == expected_sha, "Frozen helper SHA differs: " + filename)
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def paths_in(value):
    if isinstance(value, dict):
        return ([value["path"]] if isinstance(value.get("path"), str) else []) + [p for x in value.values() for p in paths_in(x)]
    if isinstance(value, list):
        return [p for x in value for p in paths_in(x)]
    return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--operation", required=True)
    args = parser.parse_args()
    require(os.name == "nt" and sys.dont_write_bytecode, "Windows and -B required")
    guard = load_exact("a24_ui_frozen_guard", "runtime_guard.py", FROZEN_GUARD_SHA)
    operation_path = str(Path(args.operation).absolute())
    with guard.operation(operation_path, __file__) as (op, out):
        manifest_path = guard.pin(op["ui_manifest_pin"])
        manifest = guard.read(manifest_path)
        validate_manifest(op, manifest, operation_path, str(Path(__file__).absolute()))
        helper = load_exact("a24_ui_frozen_job_helper", "audit_lease.py", FROZEN_AUDIT_LEASE_SHA)
        for spec in [manifest["lease_wrapper_entry_pin"], *[manifest[k] for k in
                     ("data_pin", "template_pin", "node_executable_pin", "chrome_executable_pin", "playwright_entry_pin",
                      "renderer_pin", "qa_pin", "node_guard_pin")]]:
            guard.pin(spec)
        volumes = guard.free_guard([*paths_in(manifest), str(out), operation_path, op["worker_lock_path"]])
        rows = helper._snapshot()
        allowed = helper.wrapper_chain(rows, os.getpid(), str(Path(__file__).absolute()), operation_path)
        require(not any(str(r.get("Name") or "").lower().startswith("node") and helper.OWN_NODE.search(str(r.get("CommandLine") or "")) for r in rows),
                "Another own Node producer exists")
        job = helper.hold_process_tree_job()
        actual = next(r for r in rows if int(r["ProcessId"]) == os.getpid())
        stage_receipts = []
        environment = dict(os.environ)
        for name in ("NODE_OPTIONS", "NODE_PATH"):
            environment.pop(name, None)
        for stage in ("render", "qa"):
            ready = dict(status="LOCK_HELD_BEFORE_REPORT_NODE_LAUNCH", stage=stage,
                operation_sha256=guard.sha(operation_path), manifest_sha256=op["ui_manifest_pin"]["sha256"],
                wrapper_pid=os.getpid(), wrapper_created_utc=actual["CreatedUtc"],
                wrapper_entry_pin=manifest["lease_wrapper_entry_pin"], accepted_python_ancestor_pids=allowed,
                worker_lock_path=op["worker_lock_path"], process_tree_job=job, volume_guard=volumes)
            if stage == "qa":
                html = out / manifest["rendered_html_filename"]
                ready["html_pin"] = dict(path=str(html), bytes=html.stat().st_size, sha256=guard.sha(html))
                render_receipt = out / "RENDER_RESULT.json"
                ready["render_result_pin"] = dict(path=str(render_receipt), bytes=render_receipt.stat().st_size, sha256=guard.sha(render_receipt))
            guard.write_new(out / ("UI_LEASE_READY_" + stage + ".json"), ready)
            command = stage_command(stage, manifest, str(manifest_path))
            process = None
            with (out / (stage + ".stdout.log")).open("xb") as stdout, (out / (stage + ".stderr.log")).open("xb") as stderr:
                try:
                    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                        cwd=str(Path(__file__).parent), env=environment, creationflags=0x08000000)
                    guard.write_new(out / ("UI_NODE_" + stage + ".json"), dict(pid=process.pid, parent_pid=os.getpid(), command=command))
                    code = process.wait()
                finally:
                    if process is not None and process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)
            result_path = out / ("RENDER_RESULT.json" if stage == "render" else "ui_qa/UI_QA.json")
            require(result_path.is_file(), "Child report absent; retain logs and do not retry")
            result = guard.read(result_path)
            ok = accepted_stage(stage, code, result, op["ui_manifest_pin"]["sha256"])
            receipt = dict(stage=stage, child_return_code=code, accepted=ok,
                result_pin=dict(path=str(result_path), sha256=guard.sha(result_path), bytes=result_path.stat().st_size))
            guard.write_new(out / ("UI_STAGE_" + stage + "_RESULT.json"), receipt)
            require(ok, "UI child failed or held; preserve result, no automatic retry")
            require(result.get("data_sha256") == manifest["data_pin"]["sha256"], "Child report data SHA binding differs")
            html = out / manifest["rendered_html_filename"]
            require(guard.sha(html) == result["html_sha256"], "Child HTML SHA binding differs")
            stage_receipts.append(receipt)
        guard.write_new(out / "REPORT_UI_LEASE_RESULT.json", dict(status="PASS_SAVED_REPORT_RENDER_AND_UI_BINDING_ONLY",
            stages=stage_receipts, html_pin=dict(path=str(html), sha256=guard.sha(html), bytes=html.stat().st_size),
            manifest_pin=op["ui_manifest_pin"], measured_J=None, physical_goal_pass=False, fresh_confirmation=False,
            scientific_accuracy_PASS=None, automatic_retry=False, **{k:0 for k in ZERO_FIELDS}))


if __name__ == "__main__":
    main()
