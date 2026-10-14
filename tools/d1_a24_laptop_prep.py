#!/usr/bin/env python3
"""PC-only inspection and explicit offline preflight; never contacts a phone.

No ADB subprocess or device enumeration exists in this preparation CLI. The
future measurement gate deliberately refuses all starts in this package.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

from d1_a24_laptop_validator import PROTOCOL, SHA, ValidationError, contained_file, load_json, manifest_requests, sha256

CONFIG_SCHEMA = "a24-laptop-local-config-v1"
ASSET_ROLES = {
    "classification_model", "classification_labels", "classification_preprocessing",
    "detection_model", "detection_labels", "detection_anchors", "detection_preprocessing",
    "approved_inputs", "approved_tensors", "quality_contract", "runtime_C_CPU",
    "runtime_C_GPU", "runtime_D_CPU", "runtime_D_GPU", "apk", "apk_identity", "host_dependency_lock",
    "platform_tools_lock", "plan",
}
ZERO_COUNTERS = {"actual_device_commands": 0, "device_connections": 0, "installs": 0,
                 "NN_calls": 0, "instrumentation_runs": 0, "registry_claims": 0,
                 "sessions_consumed": 0}


def inspect_environment() -> dict[str, Any]:
    """Find binaries without executing any of them."""
    # platform.platform()/machine() can shell out to cmd.exe on Windows.
    # Built-in version access preserves the strict no-external-binary boundary.
    os_version = tuple(sys.getwindowsversion()) if hasattr(sys, "getwindowsversion") else None
    return {"schema": "a24-laptop-pc-inspection-v1", "status": "PC_ONLY_DEVICE_UNVERIFIED",
            "os": sys.platform, "os_version_builtin": os_version,
            "architecture_environment": os.environ.get("PROCESSOR_ARCHITECTURE"),
            "python_version": ".".join(str(value) for value in sys.version_info[:3]), "python_executable": sys.executable,
            "python_executable_sha256": sha256(Path(sys.executable)),
            "binary_paths_only_not_executed": {name: shutil.which(name) for name in ("git", "java", "adb", "apksigner", "aapt2")},
            "dependencies": "Python standard library only for new host tools", **ZERO_COUNTERS}


def _asset_path(asset: dict[str, Any], config: dict[str, Any], config_root: Path) -> Path:
    roots = config.get("roots", {})
    root_name = asset.get("root")
    if root_name not in roots:
        raise ValidationError(f"asset root missing: {root_name}")
    root = Path(roots[root_name])
    if not root.is_absolute():
        root = config_root / root
    return contained_file(root, asset.get("path"))


def inspect_config(config: dict[str, Any], config_root: Path) -> dict[str, Any]:
    if config.get("schema") != CONFIG_SCHEMA:
        raise ValidationError("wrong local config schema")
    assets = config.get("assets", [])
    if not isinstance(assets, list):
        raise ValidationError("assets must be a list")
    checks: list[dict[str, Any]] = []
    roles: set[str] = set()
    blockers: list[str] = []
    for asset in assets:
        role = asset.get("role")
        if not isinstance(role, str) or role in roles:
            raise ValidationError("duplicate/missing asset role")
        roles.add(role)
        expected = asset.get("sha256")
        if not isinstance(expected, str) or not SHA.fullmatch(expected):
            checks.append({"role": role, "status": "EXACT_SHA_MISSING"})
            blockers.append(f"{role}: exact SHA missing")
            continue
        try:
            path = _asset_path(asset, config, config_root)
            digest = sha256(path)
            match = digest == expected
            checks.append({"role": role, "status": "SHA_MATCH" if match else "SHA_MISMATCH", "bytes": path.stat().st_size, "sha256": digest})
            if not match:
                blockers.append(f"{role}: SHA mismatch")
            if role == "apk" and match:
                with zipfile.ZipFile(path) as archive:
                    if "AndroidManifest.xml" not in archive.namelist() or "classes.dex" not in archive.namelist():
                        blockers.append("APK: missing compiled Android manifest/classes.dex")
            if role == "apk_identity" and match:
                identity = load_json(path)
                if identity.get("signature_verification") != "PASS" or not SHA.fullmatch(str(identity.get("signer_certificate_sha256", ""))):
                    blockers.append("APK: static signature verification/certificate SHA missing")
                apk_assets = [row for row in assets if row.get("role") == "apk"]
                if not apk_assets or identity.get("apk_sha256") != apk_assets[0].get("sha256"):
                    blockers.append("APK identity does not bind exact built APK")
                if identity.get("package") != "com.example.d1check.benchmarkrunner.modelprobe":
                    blockers.append("APK package differs from intended runner")
        except (ValidationError, OSError, zipfile.BadZipFile) as error:
            checks.append({"role": role, "status": "MISSING_OR_INVALID", "reason": str(error)})
            blockers.append(f"{role}: missing or invalid")
    blockers.extend(f"{role}: asset missing" for role in sorted(ASSET_ROLES - roles))
    if config.get("protocol") != PROTOCOL:
        blockers.append("exact opt-in protocol not bound")
    if config.get("device_approval") is not None and config.get("device_approval") != "DEVICE_UNVERIFIED":
        blockers.append("device approval cannot be acquired by this PC preparation tool")
    return {"schema": "a24-laptop-preflight-v1", "status": "PC_ARTIFACTS_CHECKED_DEVICE_UNVERIFIED" if not blockers else "PC_PREPARATION_BLOCKED",
            "ready_for_actual_measurement": False, "device_status": "DEVICE_UNVERIFIED", "asset_checks": checks,
            "missing_or_blocked": blockers, "measurement_gate": "ACTUAL_DEVICE_EXECUTION_DISABLED_IN_PREPARATION_PACKAGE", **ZERO_COUNTERS}


def ledger_template(plan: dict[str, Any]) -> dict[str, Any]:
    """Return a template; never writes or claims an active experiment ledger."""
    sessions = plan.get("sessions")
    if not isinstance(sessions, list) or len(sessions) != 64:
        raise ValidationError("core plan must contain exactly 64 proposed sessions")
    ids = [row.get("session_id") for row in sessions]
    if len(set(ids)) != len(ids) or None in ids:
        raise ValidationError("unique new session UUIDs required")
    for row in sessions:
        if row.get("state", "PLANNED_UNCONSUMED") != "PLANNED_UNCONSUMED" or row.get("consumed", False):
            raise ValidationError("consumed/claimed sessions cannot be imported into a new template")
    stages = {name: sum(row.get("stage") == name for row in sessions) for name in ("I", "F", "DEV", "CONFIRM")}
    if stages != {"I": 4, "F": 4, "DEV": 16, "CONFIRM": 40}:
        raise ValidationError("I4/F4/DEV16/CONFIRM40 allocation changed")
    return {"schema": "a24-laptop-ledger-template-v1", "purpose": "OFFLINE_TEMPLATE_NOT_ACTIVE_REGISTRY",
            "plan_id": plan.get("plan_id"), "stages": stages,
            "sessions": [{"session_id": row["session_id"], "stage": row["stage"], "state": "PLANNED_UNCONSUMED", "start_ns": None, "claim": None, "raw_location": None} for row in sessions], **ZERO_COUNTERS}


def assemble_manifest(plan_file: Path, session_id: str) -> dict[str, Any]:
    """Bind plan and bank without creating a registry or changing session state."""
    plan = load_json(plan_file)
    ledger_template(plan)
    matches = [row for row in plan["sessions"] if row["session_id"] == session_id]
    if len(matches) != 1:
        raise ValidationError("exact proposed session UUID not present")
    session = dict(matches[0])
    bank_path = contained_file(plan_file.parent, session.get("bank_file"))
    if sha256(bank_path) != session.get("bank_sha256"):
        raise ValidationError("bank bytes differ from fixed plan SHA")
    bank = load_json(bank_path)
    if bank.get("schema") != "a24-laptop-requests-v1" or bank.get("recipe") != session.get("recipe"):
        raise ValidationError("request bank schema/recipe mismatch")
    if len(bank.get("requests", [])) != session.get("request_count"):
        raise ValidationError("planned request count differs from bank")
    for key in ("requests", "m128_delta_ns", "nominal_profile_sha256", "nominal_profile_source_commit", "nominal_AVAILABLE_ns", "input_diversity", "approved_input_count"):
        if key in bank:
            session[key] = bank[key]
    session.update({"prescription_id": f"{session['recipe']}_{session['arm']}", "plan_sha256": sha256(plan_file),
                    "evidence_level": "PREPARATION_ONLY_DEVICE_UNVERIFIED", "registry_claim": None,
                    "time_origin": "manifest requests relative to common_start; events and result rows absolute mono_ns"})
    manifest_requests(session)
    return session


def require_future_authorization(config: dict[str, Any], *, authorization: Any = None) -> None:
    """A call cannot silently turn software readiness into measurement approval."""
    raise ValidationError("DEVICE_UNVERIFIED: preparation package never performs START/claim; separate later device authorization and verified exact plan/APK/input/runtime binding required")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect")
    p = sub.add_parser("preflight")
    p.add_argument("config", type=Path)
    p = sub.add_parser("ledger-template")
    p.add_argument("plan", type=Path)
    p = sub.add_parser("session-manifest")
    p.add_argument("plan", type=Path)
    p.add_argument("session_id")
    p = sub.add_parser("start")
    p.add_argument("--authorization", default=None)
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            result = inspect_environment()
        elif args.command == "preflight":
            result = inspect_config(load_json(args.config), args.config.parent)
        elif args.command == "ledger-template":
            result = ledger_template(load_json(args.plan))
        elif args.command == "session-manifest":
            result = assemble_manifest(args.plan, args.session_id)
        else:
            require_future_authorization({}, authorization=args.authorization)
            raise AssertionError("unreachable")
    except (ValidationError, OSError, TypeError) as error:
        print(json.dumps({"status": "BLOCKED", "reason": str(error), **ZERO_COUNTERS}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result.get("missing_or_blocked") else 0


if __name__ == "__main__":
    sys.exit(main())
