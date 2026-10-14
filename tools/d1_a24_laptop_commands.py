#!/usr/bin/env python3
"""Render future A24 commands from exact local bytes; never execute them.

Device authorization/identity, post-warmup AP admission and claim are later
operations. This command emitter cannot authorize them or mark a plan used.
Missing binding renders the reviewed workflow BLOCKED, not executable argv.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from d1_a24_laptop_validator import PROTOCOL, SHA, ValidationError, contained_file, load_json, manifest_requests, sha256

PACKAGE = "com.example.d1check.benchmarkrunner.modelprobe"
COMPONENT = PACKAGE + "/com.example.d1check.benchmarkrunner.A24PreparationActivity"
SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
WORKFLOW = [
    "Separate later user authorization; verify one A24 serial/fingerprint and USB/charging configuration",
    "Verify exact source/runtime/model/input/tensor/APK/platform-tools and signature bindings again",
    "Install exact APK and stage flat input bundle under run-as app-owned session UUID directory",
    "Start the explicit opt-in activity; wait for runtime/warmup ready marker",
    "Collect raw HAL AP history for at least 60 seconds after ready; verify frozen AP/SOC/environment gate",
    "Write post-warmup start_approval only after gate admission; claim a new unused session in the future registry",
    "Run 0..210s logging with dispatch cutoff120s and complete AVAILABLE drain; preserve every attempt/failure",
    "Recover app files and host raw HAL/read timing; create exact transport SHA manifest before offline validation",
    "Validate all planned requests, WAIT dose, owners, response/persistence/AVAILABLE and sensor coverage",
]


def command_plan(manifest: dict[str, Any], bindings: dict[str, Any], *, authorization: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest_requests(manifest, require_materials=True)
    result: dict[str, Any] = {"schema": "a24-laptop-future-command-plan-v1", "status": "BLOCKED_DEVICE_UNVERIFIED",
        "execution_performed": False, "commands_are_review_only": True, "workflow": WORKFLOW,
        "actual_device_commands": 0, "NN_calls": 0, "registry_claims": 0, "sessions_consumed": 0,
        "device_status": "DEVICE_UNVERIFIED", "blockers": [], "commands": []}
    if bindings.get("schema") != "a24-laptop-future-bindings-v1":
        result["blockers"].append("exact future bundle/APK/tool binding schema missing")
        return result
    expected_plan = bindings.get("plan_sha256")
    if expected_plan != manifest.get("plan_sha256") or not SHA.fullmatch(str(expected_plan)):
        result["blockers"].append("exact current plan SHA missing/mismatch")
    files = bindings.get("files", [])
    bundle_root = Path(bindings.get("bundle_root", "."))
    filenames: set[str] = set()
    for item in files:
        name = item.get("path")
        if not isinstance(name, str) or not SAFE_NAME.fullmatch(name) or name.casefold() in filenames:
            result["blockers"].append("future app input names must be unique safe flat names")
            continue
        filenames.add(name.casefold())
        try:
            path = contained_file(bundle_root, name)
            if sha256(path) != item.get("sha256") or path.stat().st_size != item.get("bytes"):
                result["blockers"].append(f"bundle SHA/bytes mismatch: {name}")
        except (ValidationError, OSError) as error:
            result["blockers"].append(str(error))
    if "session_manifest.json" not in filenames:
        result["blockers"].append("exact assembled session_manifest.json missing from flat bundle")
    else:
        try:
            file_manifest = load_json(bundle_root / "session_manifest.json")
            if file_manifest != manifest:
                result["blockers"].append("supplied session manifest differs from bundle manifest")
        except ValidationError as error:
            result["blockers"].append(str(error))
    models = manifest.get("models", {})
    if set(models) != {"C_CPU", "C_GPU", "D_CPU", "D_GPU"}:
        result["blockers"].append("common resident runtime four-key binding incomplete; D_GPU is resident only")
    for key in ("apk", "adb"):
        item = bindings.get(key, {})
        path = Path(item.get("path", ""))
        if not path.is_file() or not SHA.fullmatch(str(item.get("sha256"))) or sha256(path) != item["sha256"]:
            result["blockers"].append(f"exact {key} file/SHA missing")
    identity = bindings.get("apk_identity", {})
    if identity.get("package") != PACKAGE or identity.get("signature_verification") != "PASS" or identity.get("apk_sha256") != bindings.get("apk", {}).get("sha256") or not SHA.fullmatch(str(identity.get("signer_certificate_sha256"))):
        result["blockers"].append("static APK signature identity not bound")
    if authorization is None:
        result["blockers"].append("separate future device authorization/serial/fingerprint/AP-gate binding missing")
    else:
        expected = {"schema": "a24-laptop-future-authorization-v1", "authorization": "USER_AUTHORIZED_FUTURE_MEASUREMENT",
                    "session_id": manifest["session_id"], "plan_sha256": manifest.get("plan_sha256"),
                    "apk_sha256": bindings.get("apk", {}).get("sha256")}
        if any(authorization.get(key) != value for key, value in expected.items()):
            result["blockers"].append("future authorization binds different session/plan/APK")
        if not isinstance(authorization.get("serial"), str) or not SAFE_NAME.fullmatch(authorization["serial"]) or not authorization.get("fingerprint"):
            result["blockers"].append("one exact future A24 serial/fingerprint missing")
        if not SHA.fullmatch(str(authorization.get("frozen_ap_gate_sha256"))):
            result["blockers"].append("frozen post-warmup AP gate SHA missing")
    if result["blockers"]:
        return result
    serial = authorization["serial"]
    adb = bindings["adb"]["path"]
    session_id = manifest["session_id"]
    adb_prefix = [adb, "-s", serial]
    remote_in = f"files/a24_laptop_inputs/{session_id}"
    remote_out = f"files/a24_laptop_results/{session_id}"
    commands: list[dict[str, Any]] = [
        {"phase": "LATER_DEVICE_IDENTITY_CHECK", "argv": adb_prefix + ["shell", "getprop", "ro.build.fingerprint"], "must_equal": authorization["fingerprint"]},
        {"phase": "LATER_INSTALL_AFTER_AUTHORIZATION", "argv": adb_prefix + ["install", "-r", bindings["apk"]["path"]]},
        {"phase": "LATER_STAGE", "argv": adb_prefix + ["shell", "run-as", PACKAGE, "mkdir", "-p", remote_in]},
    ]
    for item in files:
        name = item["path"]
        temporary = f"/data/local/tmp/a24-{session_id}-{name}"
        commands.append({"phase": "LATER_STAGE", "argv": adb_prefix + ["push", str(bundle_root / name), temporary]})
        commands.append({"phase": "LATER_STAGE", "argv": adb_prefix + ["shell", "run-as", PACKAGE, "cp", temporary, f"{remote_in}/{name}"]})
    commands.extend([
        {"phase": "LATER_OPT_IN_RUNTIME_PREPARATION", "argv": adb_prefix + ["shell", "am", "start", "-n", COMPONENT, "--es", "a24_protocol", PROTOCOL, "--ez", "a24_execute_authorized", "true", "--es", "session_id", session_id]},
        {"phase": "LATER_READY_WAIT", "argv": adb_prefix + ["exec-out", "run-as", PACKAGE, "cat", f"{remote_out}/ready.json"]},
        {"phase": "LATER_HOST_HAL_LOGGING_TEMPLATE", "argv": adb_prefix + ["shell", "dumpsys", "thermalservice"], "note": "repeat using a later authorized timestamped host logger; preserve read start/end and raw names/types; cache/HAL sample time unknown must remain null"},
        {"phase": "LATER_POST_READY_AP_GATE_AND_NEW_CLAIM", "operation": "verify >=60s actual HAL history and frozen SOC/environment/AP criteria; create new registry claim only after separate authorization; then write exact start_approval.json via run-as", "executable_argv": None},
        {"phase": "LATER_RECOVERY", "argv": adb_prefix + ["exec-out", "run-as", PACKAGE, "tar", "-cf", "-", remote_out], "stdout": "new local session tar file opened as binary; then safe member extraction and transport SHA manifest"},
        {"phase": "OFFLINE_VALIDATION_AFTER_RECOVERY", "argv": [sys.executable, "-B", "tools/d1_a24_laptop_validator.py", "trace", "<NEW_LOCAL_RECOVERED_SESSION_DIRECTORY>"]},
    ])
    result.update({"status": "REVIEWABLE_FUTURE_COMMANDS_ONLY_DEVICE_UNVERIFIED", "commands": commands,
                   "blockers": ["device identity and AP admission must still be checked on the later phone; rendering does not assert either", "post-ready claim/AP-admission step intentionally requires the future authorized collector; no claim created by emitter"]})
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("bindings", type=Path)
    parser.add_argument("--future-authorization", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        result = command_plan(load_json(args.manifest), load_json(args.bindings), authorization=load_json(args.future_authorization) if args.future_authorization else None)
    except (ValidationError, OSError, ValueError, TypeError) as error:
        print(json.dumps({"status": "BLOCKED", "reason": str(error), "actual_device_commands": 0}))
        return 2
    print(json.dumps(result, indent=2))
    return 2 if not result["commands"] else 0


if __name__ == "__main__":
    sys.exit(main())
