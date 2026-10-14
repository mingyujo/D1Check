#!/usr/bin/env python3
"""Future single-session controller. Default is offline review, never execution.

An explicit later --execute-authorized plus exact bytes and a frozen admission
contract is required before constructing any native ADB command. Current PC
preparation does not supply that authorization. Tests use fake clients only.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import re
import subprocess
import sys
import tarfile
import time
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

from d1_a24_laptop_commands import PACKAGE, COMPONENT, SAFE_NAME, WORKFLOW
from d1_a24_laptop_validator import NS, PROTOCOL, SHA, ValidationError, contained_file, load_json, manifest_requests, sha256, validate_events

# Production binds the controller in this repository. Pure tests may inject an
# identical-byte temporary controller into the source verification helper.
CONTROLLER_SOURCE_FILE = Path(__file__)
SOURCE_MANIFEST_SCHEMA = "a24-preparation-source-manifest-v1"
ISOLATED_PACKAGE = "com.example.d1check.benchmarkrunner.a24measurement"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def atomic_json(path: Path, value: Any) -> None:
    """New exact file only; do not replace prior attempts or a foreign registry."""
    require(not path.exists(), f"attempt/identity already exists: {path.name}")
    data = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    temporary = path.with_name(path.name + ".partial-" + str(uuid.uuid4()))
    with temporary.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    # Hard-link creates the committed name atomically and refuses an existing
    # target on Windows and POSIX; preserve .partial if a collision occurs.
    os.link(temporary, path)
    temporary.unlink()


def frozen_gate(gate: dict[str, Any]) -> None:
    require(gate.get("schema") == "a24-laptop-frozen-gate-v1" and gate.get("frozen") is True, "AP/SOC/environment gate is not frozen")
    require(gate.get("sensor_name") and gate.get("sensor_type") not in {None, "UNKNOWN", "BATTERY", 2}, "exact non-battery AP HAL name/type required")
    require(isinstance(gate.get("Tref_c"), (int, float)) and math.isfinite(gate["Tref_c"]), "Tref must be frozen before measurement")
    require(gate.get("tref_tolerance_c") == 0.5 and gate.get("maximum_abs_slope_c_per_min") == 0.1, "PLAN admission criteria changed; use a separately approved version")
    require(gate.get("history_ns") == 60 * NS and gate.get("maximum_gate_wait_ns") == 600 * NS, "post-ready history/wait bounds changed")
    soc_contract = gate.get("soc_contract", "PLAN_SOC40_80")
    expected_soc = (10, 100) if soc_contract == "USER_SOC_GE10_20261015" else (40, 80)
    require(soc_contract in {"PLAN_SOC40_80", "USER_SOC_GE10_20261015"}
            and (gate.get("minimum_SOC_percent"),gate.get("maximum_SOC_percent")) == expected_soc,
            "SOC criteria differ from explicitly versioned user contract")
    require(isinstance(gate.get("require_unplugged"), bool), "charging/transport choice must be explicitly frozen")
    for key in ("hal_poll_period_ns", "maximum_observation_gap_ns", "status_poll_period_ns", "ready_timeout_ns", "session_timeout_ns", "maximum_raw_bytes"):
        require(isinstance(gate.get(key), int) and not isinstance(gate[key], bool) and gate[key] > 0, f"frozen {key} missing")
    require(gate["maximum_observation_gap_ns"] >= gate["hal_poll_period_ns"], "frozen gap smaller than polling cadence")
    require(gate.get("environment_reviewed") is True and isinstance(gate.get("screen_contract"), str), "screen/environment contract not frozen")


def verify_source_entries(manifest: dict[str, Any], source_root: Path, *, controller_file: Path) -> dict[str, Any]:
    require(isinstance(manifest, dict) and manifest.get("schema") == SOURCE_MANIFEST_SCHEMA, "authorized source manifest schema mismatch")
    require(source_root.is_dir() and source_root.absolute() == source_root.resolve(), "source_root must be an existing canonical repository directory")
    root = source_root.resolve()
    try:
        controller_relative = controller_file.resolve().relative_to(root).as_posix()
    except (ValueError, OSError) as error:
        raise ValidationError("source_root does not contain the executing controller repository") from error
    require(controller_relative == "tools/d1_a24_laptop_control.py", "controller must bind its exact repository source path")
    entries = manifest.get("files")
    require(isinstance(entries, list) and bool(entries), "authorized source manifest has no file entries")
    checked: dict[str, str] = {}
    try:
        for entry in entries:
            require(isinstance(entry, dict), "invalid source manifest entry")
            name, size, digest = entry.get("path"), entry.get("bytes"), entry.get("sha256")
            require(isinstance(name, str) and name and name.casefold() not in checked, "duplicate or missing source path")
            require(isinstance(size, int) and not isinstance(size, bool) and size >= 0, "invalid exact source byte count")
            require(isinstance(digest, str) and SHA.fullmatch(digest) is not None, "exact source SHA missing")
            original = contained_file(root, name)
            require(original.stat().st_size == size and sha256(original) == digest, f"current source bytes/SHA differ: {name}")
            checked[name.casefold()] = digest
    except OSError as error:
        raise ValidationError("current source file cannot be verified") from error
    require(controller_relative.casefold() in checked, "executing controller is absent from authorized source manifest")
    require(checked[controller_relative.casefold()] == sha256(controller_file)
            and checked[controller_relative.casefold()] == sha256(Path(__file__)),
            "authorized source manifest does not bind the actual executing controller bytes")
    return {"status": "CURRENT_SOURCE_FILES_BYTES_VERIFIED", "file_count": len(checked)}


def check_authorization(manifest: dict[str, Any], config: dict[str, Any], authorization: dict[str, Any], gate: dict[str, Any], *, execute_authorized: bool) -> dict[str, Any]:
    package = config.get("package_name",PACKAGE)
    require(package in {PACKAGE,ISOLATED_PACKAGE},"unapproved measurement package namespace")
    require(package == PACKAGE or authorization.get("package_name") == package,"isolated package is not explicitly authorized")
    require(execute_authorized, "PREPARATION_ONLY: --execute-authorized is absent")
    manifest_requests(manifest, require_materials=True)
    require(manifest.get("execution_authorized") is True and manifest.get("device_status") == "DEVICE_APPROVED_FOR_NEW_CONTRACT" and manifest.get("mock") is False, "DEVICE_UNVERIFIED: preparation/bound templates are not executable device manifests")
    require(authorization.get("schema") == "a24-laptop-control-authorization-v1", "future authorization schema missing")
    require(authorization.get("authorization") == "USER_EXPLICIT_FUTURE_A24_MEASUREMENT", "current preparation scope cannot execute a phone measurement")
    require(authorization.get("scope") == "one_new_session", "authorization must cover exactly one unused session")
    for field in ("session_id", "plan_sha256"):
        require(authorization.get(field) == manifest.get(field), f"authorization {field} mismatch")
    require(authorization.get("manifest_sha256") == config.get("manifest_sha256"), "exact assembled manifest not authorized")
    require(authorization.get("gate_sha256") == config.get("gate_sha256"), "frozen gate SHA not authorized")
    require(authorization.get("apk_sha256") == config.get("apk", {}).get("sha256"), "APK SHA not authorized")
    require(SAFE_NAME.fullmatch(str(authorization.get("serial", ""))) is not None and authorization.get("fingerprint"), "one exact A24 serial/fingerprint missing")
    require(authorization.get("expected_model") == "SM-A245N", "only A24 admitted")
    require(SHA.fullmatch(str(manifest.get("plan_sha256"))) is not None, "plan SHA missing")
    frozen_gate(gate)
    require(config.get("gate_sha256") == hashlib.sha256(config["gate_bytes"]).hexdigest(), "gate bytes/SHA changed")
    require(config.get("manifest_sha256") == hashlib.sha256(config["manifest_bytes"]).hexdigest(), "manifest bytes/SHA changed")
    require(json.loads(config["manifest_bytes"]) == manifest, "manifest bytes contain different settings")
    for key in ("apk", "adb"):
        item = config.get(key, {})
        path = Path(item.get("path", ""))
        require(path.is_file() and sha256(path) == item.get("sha256"), f"exact {key} file/SHA unavailable")
    identity = config.get("apk_identity", {})
    require(identity.get("apk_sha256") == config["apk"]["sha256"] and identity.get("package") == package and identity.get("signature_verification") == "PASS" and SHA.fullmatch(str(identity.get("signer_certificate_sha256"))) is not None, "verified APK signer identity missing")
    require(set(manifest.get("models", {})) == {"C_CPU", "C_GPU", "D_CPU", "D_GPU"}, "four common resident models not bound")
    for key, model in manifest["models"].items():
        target = model.get("target", {})
        expected = {"adb_serial": authorization["serial"], "build_fingerprint": authorization["fingerprint"],
                    "apk_sha256": config["apk"]["sha256"], "package_name": package,
                    "model": "SM-A245N", "api_level": authorization.get("api_level"), "ram_bytes": authorization.get("ram_bytes")}
        require(all(target.get(field) == value and value is not None for field, value in expected.items()), f"DEVICE_UNVERIFIED: {key} target/new registration mismatch")
        for field in ("device_id", "abi", "cpu_abi", "cpu_features", "soc", "manufacturer", "gpu_vendor", "gpu_renderer", "gpu_driver", "android_release"):
            value = target.get(field)
            require(isinstance(value, str) and value and value not in {"UNKNOWN", "DEVICE_UNVERIFIED", "NOT_PROVIDED"}, f"DEVICE_UNVERIFIED: exact {key} target {field} missing")
        require(isinstance(target["api_level"], int) and target["api_level"] > 0 and isinstance(target["ram_bytes"], int) and target["ram_bytes"] > 0, "device API/RAM registration invalid")
        require(model.get("identity", {}).get("session_id") == manifest["session_id"], "old runtime session identity cannot be reused")
    root = Path(config.get("bundle_root", ""))
    files = config.get("files", [])
    require(files, "exact flat source/input bundle missing")
    names: set[str] = set()
    for item in files:
        name = item.get("path")
        require(isinstance(name, str) and SAFE_NAME.fullmatch(name) is not None and name.casefold() not in names, "unsafe/duplicate future input name")
        names.add(name.casefold())
        path = contained_file(root, name)
        require(sha256(path) == item.get("sha256") and path.stat().st_size == item.get("bytes"), "future input bytes/SHA mismatch")
    require("session_manifest.json" in names, "bound session manifest missing from bundle")
    require(sha256(root / "session_manifest.json") == config["manifest_sha256"], "bundle manifest differs from authorized manifest")
    require(config.get("source_code_sha256") == authorization.get("source_code_sha256") and SHA.fullmatch(str(config.get("source_code_sha256"))) is not None, "exact source version not authorized")
    require(config.get("host_dependency_lock_sha256") == authorization.get("host_dependency_lock_sha256") and SHA.fullmatch(str(config.get("host_dependency_lock_sha256"))) is not None, "host lock not authorized")
    for key, sha_key in (("source_code_manifest", "source_code_sha256"), ("host_dependency_lock", "host_dependency_lock_sha256")):
        path = Path(config.get(key, ""))
        require(path.is_file() and sha256(path) == config[sha_key], f"actual {key} bytes do not match authorization")
    source_root = config.get("source_root")
    require(isinstance(source_root, str) and bool(source_root), "exact current repository source_root missing")
    verify_source_entries(load_json(Path(config["source_code_manifest"])), Path(source_root), controller_file=CONTROLLER_SOURCE_FILE)
    require(authorization.get("control_source_sha256") == sha256(Path(__file__)), "controller source version not authorized")
    if manifest.get("stage") == "CONFIRM":
        freeze_path = Path(config.get("confirm_freeze", ""))
        require(freeze_path.is_file() and sha256(freeze_path) == authorization.get("confirm_freeze_sha256"), "CONFIRM forbidden before exact independent-confirm freeze certificate")
        freeze = load_json(freeze_path)
        require(freeze.get("status") == "FROZEN_BEFORE_CONFIRM" and freeze.get("plan_sha256") == manifest["plan_sha256"] and freeze.get("apk_sha256") == config["apk"]["sha256"], "CONFIRM freeze binds different plan/APK")
        require(freeze.get("recorded_prior_stage_attempts") == {"I": 4, "F": 4, "DEV": 16}, "CONFIRM requires preserved I4/F4/DEV16 attempt records")
        for field in ("analysis_contract_sha256", "pre_measurement_predictions_sha256", "prior_stage_ledger_sha256"):
            require(SHA.fullmatch(str(freeze.get(field))) is not None, f"CONFIRM frozen {field} missing")
    if manifest.get("perfetto") == "ON":
        tracing = config.get("perfetto", {})
        require(tracing.get("cli_binding_verified") is True and tracing.get("device_version"), "DEVICE_UNVERIFIED: on-device Perfetto CLI/version must be checked before I04")
        profile = Path(tracing.get("profile_path", ""))
        require(profile.is_file() and sha256(profile) == tracing.get("profile_sha256"), "exact bounded Perfetto profile SHA missing")
        text = profile.read_text(encoding="utf-8")
        require("duration_ms: 210000" in text and "write_into_file: true" in text and "max_file_size_bytes: 67108864" in text, "bounded Perfetto profile changed")
        require(tracing.get("profile_sha256") == authorization.get("perfetto_profile_sha256") and tracing.get("device_version") == authorization.get("perfetto_device_version"), "Perfetto configuration/version not authorized")
    return {"namespace": PROTOCOL, "plan_id": manifest.get("plan_id"), "plan_sha256": manifest["plan_sha256"], "session_id": manifest["session_id"], "authorization_sha256": hashlib.sha256(json.dumps(authorization, sort_keys=True).encode()).hexdigest()}


class FutureRegistry:
    """A fresh protocol-specific registry, created only after authorization."""
    def __init__(self, root: Path, authorized: dict[str, Any]):
        require(authorized.get("namespace") == PROTOCOL and authorized.get("plan_id"), "registry authorization missing")
        require(root.name == authorized["plan_id"] and root.parent.name == PROTOCOL, "legacy/foreign registry namespace forbidden")
        require(not root.is_symlink(), "registry symlink forbidden")
        header = {key: authorized[key] for key in ("namespace", "plan_id", "plan_sha256")}
        if root.exists():
            require((root / "namespace.json").is_file() and load_json(root / "namespace.json") == header, "existing foreign registry cannot be reused")
        else:
            root.mkdir(parents=True, exist_ok=False)
            atomic_json(root / "namespace.json", header)
        self.root = root
        self.authorized = authorized
        self.attempt_id = str(uuid.uuid4())
        self.session = root / authorized["session_id"]
        require(not self.session.exists(), "session previously attempted/claimed; no identity reuse or automatic retry")

    def record(self, state: str, detail: dict[str, Any]) -> None:
        require(state in {"PRESTART_REJECT", "START", "COMPLETE", "FAIL"}, "unsupported ledger transition")
        if state in {"PRESTART_REJECT", "START"}:
            self.session.mkdir(exist_ok=False)
        else:
            require((self.session / "START.json").is_file(), "terminal ledger row without START")
            require(not (self.session / "COMPLETE.json").exists() and not (self.session / "FAIL.json").exists(), "terminal attempt already finalized")
        row = {**self.authorized, "state": state, "host_wall_ns": time.time_ns(), "host_mono_ns": time.monotonic_ns(), "attempt_id": self.attempt_id, **detail}
        atomic_json(self.session / f"{state}.json", row)


class NativeAdbClient:
    """Not constructed by offline review or by this preparation's real tests."""
    def __init__(self, adb: str, serial: str):
        self.prefix = [adb, "-s", serial]
        self.actual_calls = 0

    def command(self, *args: str, input_bytes: bytes | None = None, accepted_codes: tuple[int, ...] = (0,), reject_stderr: bool = False) -> bytes:
        self.actual_calls += 1
        completed = subprocess.run(self.prefix + list(args), input=input_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
        require(completed.returncode in accepted_codes, f"ADB failed: {' '.join(args[:3])}; preserve attempt/raw logs")
        require(not reject_stderr or not completed.stderr.strip(), f"ADB lookup error: {' '.join(args[:3])}; cannot infer absent owner")
        return completed.stdout

    def sleep_ns(self, nanoseconds: int) -> None:
        time.sleep(nanoseconds / NS)


THERMAL = re.compile(r"Temperature\{[^}]*?mValue=([-+0-9.eE]+)[^}]*?mType=(\d+)[^}]*?mName=([^,}]+)[^}]*\}")

# AndroidManifest.xml is authoritative: a base PID query does not find isolated
# :model_probe or :a24_preparation activity processes. All must be idle before install.
APP_PROCESS_NAMES = (PACKAGE, PACKAGE + ":model_probe", PACKAGE + ":a24_preparation")


def require_no_app_process_owner(client: Any, *, package: str = PACKAGE) -> None:
    occupied: list[str] = []
    names = APP_PROCESS_NAMES if package == PACKAGE else (*APP_PROCESS_NAMES,package,package+":model_probe",package+":a24_preparation")
    for process_name in names:
        try:
            response = client.command("shell", "pidof", process_name, accepted_codes=(0, 1), reject_stderr=True)
            require(isinstance(response, bytes), "PID lookup returned a non-byte response")
            text = response.decode("ascii").strip()
            require(not text or re.fullmatch(r"[1-9][0-9]*(?:\s+[1-9][0-9]*)*", text) is not None,
                    "PID lookup returned malformed output; cannot infer absent owner")
        except Exception as error:
            raise ValidationError(f"PRESTART_REJECT: PID lookup failed for {process_name}; no install or takeover: {error}") from error
        if text:
            occupied.append(process_name)
    require(not occupied, "PRESTART_REJECT: existing app process/owner present; do not install, force-stop or kill")


def elapsed_ns(client: Any) -> int:
    first = client.command("shell", "cat", "/proc/uptime").decode("ascii").split()[0]
    return int(Decimal(first) * NS)


def read_hal(client: Any) -> dict[str, Any]:
    host_before, wall_before = time.monotonic_ns(), time.time_ns()
    device_before = elapsed_ns(client)
    read_start = time.monotonic_ns()
    raw = client.command("shell", "dumpsys", "thermalservice").decode("utf-8", errors="replace")
    read_end = time.monotonic_ns()
    device_after = elapsed_ns(client)
    host_after, wall_after = time.monotonic_ns(), time.time_ns()
    require(device_after >= device_before and host_after >= host_before, "clock bracket reversed")
    marker = "Current temperatures from HAL:"
    current = raw.split(marker, 1)[1].split("Current cooling devices from HAL:",1)[0] if marker in raw else ""
    return {"host_read_start_ns": read_start, "host_read_end_ns": read_end, "host_mono_before_ns": host_before, "host_mono_after_ns": host_after,
        "host_wall_before_ns": wall_before, "host_wall_after_ns": wall_after, "device_elapsed_before_ns": device_before, "device_elapsed_after_ns": device_after,
        "device_time_bracket_width_ns": device_after - device_before, "source_api": "dumpsys thermalservice", "raw": raw,
        "sensors": [{"sensor_name": name.strip(), "sensor_type": int(kind), "value_c": float(value), "sensor_timestamp_ns": None, "cache_age_ns": None} for value, kind, name in THERMAL.findall(current)],
        "sensor_source_section": "CURRENT_HAL" if marker in raw else "MISSING_CURRENT_HAL_SECTION",
        "cache_update_observed": None, "independent_sample_claim": False, "AP_from_battery": False}


def admission(samples: list[dict[str, Any]], gate: dict[str, Any], *, ready_ns: int, battery: dict[str, Any]) -> dict[str, Any]:
    frozen_gate(gate)
    points: list[tuple[int, float]] = []
    for sample in samples:
        found = [row for row in sample["sensors"] if row["sensor_name"] == gate["sensor_name"] and row["sensor_type"] == gate["sensor_type"]]
        if len(found) != 1 or not math.isfinite(found[0]["value_c"]):
            return {"admitted": False, "reason": "AP_HAL_SENSOR_MISSING_OR_AMBIGUOUS"}
        if sample["device_elapsed_before_ns"] >= ready_ns:
            points.append((sample["device_elapsed_before_ns"], found[0]["value_c"]))
    if len(points) < 2 or points[-1][0] - points[0][0] < gate["history_ns"]:
        return {"admitted": False, "reason": "POST_READY_60S_HISTORY_INCOMPLETE"}
    if any(b[0] - a[0] > gate["maximum_observation_gap_ns"] for a, b in zip(points, points[1:])):
        return {"admitted": False, "reason": "FROZEN_AP_OBSERVATION_GAP_EXCEEDED"}
    if any(abs(value - gate["Tref_c"]) > gate["tref_tolerance_c"] for _, value in points):
        return {"admitted": False, "reason": "AP_OUTSIDE_FROZEN_TREF_BAND"}
    xs = [(instant - points[0][0]) / (60 * NS) for instant, _ in points]
    mean_x, mean_y = sum(xs) / len(xs), sum(v for _, v in points) / len(points)
    variance = sum((x - mean_x) ** 2 for x in xs)
    slope = sum((x - mean_x) * (v - mean_y) for x, (_, v) in zip(xs, points)) / variance
    if abs(slope) > gate["maximum_abs_slope_c_per_min"]:
        return {"admitted": False, "reason": "AP_OBSERVED_SLOPE_EXCEEDED", "slope_c_per_min": slope}
    soc = battery.get("SOC_percent")
    if not isinstance(soc, (int, float)) or not gate["minimum_SOC_percent"] <= soc <= gate["maximum_SOC_percent"]:
        return {"admitted": False, "reason": "SOC_OUTSIDE_FROZEN_RANGE"}
    if gate["require_unplugged"] and battery.get("plugged") is not False:
        return {"admitted": False, "reason": "CHARGING_UNKNOWN_OR_PLUGGED"}
    return {"admitted": True, "reason": "OBSERVED_HAL_ADMISSION_ONLY_CACHE_AGE_UNKNOWN", "history_start_ns": points[0][0], "read_before_ns": points[-1][0], "read_after_ns": samples[-1]["device_elapsed_after_ns"], "slope_c_per_min": slope, "independent_sample_claim": False}


def read_battery(client: Any) -> dict[str, Any]:
    raw = client.command("shell", "dumpsys", "battery").decode("utf-8", errors="replace")
    level, scale = re.search(r"\blevel:\s*(\d+)", raw), re.search(r"\bscale:\s*(\d+)", raw)
    plugs = [re.search(rf"{name} powered:\s*(true|false)", raw, re.I) for name in ("AC", "USB", "Wireless")]
    return {"raw": raw, "SOC_percent": 100 * int(level[1]) / int(scale[1]) if level and scale and int(scale[1]) > 0 else None,
            "plugged": any(match[1].lower() == "true" for match in plugs) if all(plugs) else None}


def start_perfetto(client: Any, session_id: str, tracing: dict[str, Any]) -> dict[str, Any]:
    """Later only: detached trace has a fixed 210s watchdog and unique key.

    Official interfaces: https://perfetto.dev/docs/reference/perfetto-cli and
    https://perfetto.dev/docs/concepts/detached-mode (checked 2026-10-14).
    Detached mode is bounded here to avoid an unbounded leaked session.
    """
    version = client.command("shell", "perfetto", "--version").decode().strip()
    require(version == tracing["device_version"], "on-device Perfetto version changed")
    # Android's CLI writes help to stderr and returns 1. The fixed redirection
    # captures that documented interface without treating its help exit as a
    # tracing failure. No user-provided shell text is interpolated here.
    help_text = client.command("shell", "perfetto", "--help", "2>&1",
                               accepted_codes=(0,1),reject_stderr=True).decode(errors="replace")
    require("--detach" in help_text and "--attach" in help_text and "--stop" in help_text, "UNSUPPORTED: device Perfetto detach/attach/stop unavailable")
    key = "a24_" + session_id.replace("-", "")
    remote_profile = f"/data/local/tmp/a24-{session_id}-perfetto.pbtxt"
    remote_trace = f"/data/misc/perfetto-traces/a24-{session_id}.pftrace"
    client.command("push", tracing["profile_path"], remote_profile)
    client.command("shell", "perfetto", "--txt", "-c", remote_profile, "--detach=" + key, "-o", remote_trace)
    return {"key": key, "remote_trace": remote_trace, "source_url": "https://perfetto.dev/docs/concepts/detached-mode", "hard_duration_ms": 210000,
            "hardware_counter_values": None, "device_ftrace_sources_verified": False, "maximum_trace_bytes": 67108864}


def finish_perfetto(client: Any, trace: dict[str, Any]) -> dict[str, Any]:
    # Auto-expiry at duration_ms is expected. --attach --stop can then return
    # a nonzero missing-session code; preserve that condition, never call it PASS.
    stop_error = None
    try:
        client.command("shell", "perfetto", "--attach=" + trace["key"], "--stop")
    except ValidationError as error:
        stop_error = str(error)
    content = client.command("exec-out", "cat", trace["remote_trace"])
    require(len(content) <= trace["maximum_trace_bytes"], "Perfetto bounded trace size exceeded")
    return {"bytes": content, "stop_error_or_autoexpiry": stop_error, "status": "RAW_TRACE_ONLY_SOURCES_AND_LOSS_UNVERIFIED", "hardware_counter_values": None}


def safe_extract(payload: bytes, destination: Path, *, session_id: str, maximum_bytes: int) -> None:
    require(not destination.exists(), "recovery must use a new directory")
    prefix = f"files/a24_laptop_results/{session_id}/"
    members: list[tuple[str, bytes]] = []
    seen: set[str] = set()
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
        total = 0
        for member in archive:
            name = member.name.removeprefix("./")
            if member.isdir():
                require(name.rstrip("/") == prefix.rstrip("/") or name.startswith(prefix), "tar directory outside expected session")
                continue
            require(member.isfile() and name.startswith(prefix), "tar link/special member/outside-session path refused")
            relative = name[len(prefix):]
            require(relative and not any(part in {"", ".", ".."} for part in relative.split("/")) and "\\" not in relative and ":" not in relative, "unsafe tar member")
            require(relative.casefold() not in seen, "duplicate tar member")
            seen.add(relative.casefold())
            total += member.size
            require(total <= maximum_bytes, "frozen maximum raw bytes exceeded")
            extracted = archive.extractfile(member)
            require(extracted is not None, "tar member cannot be read")
            content = extracted.read()
            require(len(content) == member.size, "truncated tar member")
            members.append((relative, content))
    destination.mkdir(parents=True, exist_ok=False)
    for relative, content in members:
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def preserve_partial(client: Any, output: Path, *, session_id: str, raw: list[dict[str, Any]], maximum_bytes: int, package: str = PACKAGE) -> dict[str, Any]:
    """One bounded best-effort recovery; preserve failure, never retry the run."""
    recovery_error = None
    if not output.exists():
        try:
            payload = client.command("exec-out", "run-as", package, "tar", "-cf", "-", f"files/a24_laptop_results/{session_id}")
            safe_extract(payload, output, session_id=session_id, maximum_bytes=maximum_bytes)
        except Exception as error:
            recovery_error = str(error)
            output.mkdir(parents=True, exist_ok=True)
    path = output / "host_hal_partial.jsonl"
    if not path.exists():
        path.write_text("".join(json.dumps(row) + "\n" for row in raw), encoding="utf-8")
    return {"status": "PARTIAL_OR_PRESTART_REJECT_RAW_NOT_VALIDATED", "recovery_error": recovery_error, "automatic_retry": False}


def require_completed_app_cleanup(summary: dict[str, Any], cleanup: dict[str, Any]) -> None:
    require(isinstance(summary, dict) and summary.get("status") == "COMPLETED_PENDING_HOST_VALIDATION",
            "app summary is not a successful pending-validation terminal")
    require(isinstance(cleanup, dict) and cleanup.get("status") == "DRAINED"
            and cleanup.get("actual_return_confirmed") is True
            and cleanup.get("error") is None and cleanup.get("session_failure") is None,
            "app cleanup failed or actual worker return is unconfirmed; no COMPLETE")


def run_one(manifest: dict[str, Any], config: dict[str, Any], authorization: dict[str, Any], gate: dict[str, Any], *, execute_authorized: bool = False, client: Any = None) -> dict[str, Any]:
    package = config.get("package_name",PACKAGE)
    component = package + "/com.example.d1check.benchmarkrunner.A24PreparationActivity"
    authorized = check_authorization(manifest, config, authorization, gate, execute_authorized=execute_authorized)
    registry = FutureRegistry(Path(config["registry_root"]), authorized)
    output = Path(config["output_root"]) / manifest["session_id"]
    require(not output.exists(), "future output session already exists")
    client = client if client is not None else NativeAdbClient(config["adb"]["path"], authorization["serial"])
    host_raw: list[dict[str, Any]] = []
    started = False
    trace = None
    sid = manifest["session_id"]
    remote_input = f"files/a24_laptop_inputs/{sid}"
    remote_output = f"files/a24_laptop_results/{sid}"
    try:
        require(client.command("shell", "getprop", "ro.build.fingerprint").decode().strip() == authorization["fingerprint"], "device fingerprint mismatch")
        require(client.command("shell", "getprop", "ro.product.model").decode().strip() == "SM-A245N", "device is not approved A24")
        require_no_app_process_owner(client,package=package)
        require(all(not Path(path).exists() for path in config.get("existing_owner_files", [])), "PRESTART_REJECT: existing host owner marker present; no automatic takeover")
        before_warmup_battery = read_battery(client)
        soc = before_warmup_battery["SOC_percent"]
        require(isinstance(soc, (int, float)) and gate["minimum_SOC_percent"] <= soc <= gate["maximum_SOC_percent"], "PRESTART_REJECT: SOC outside frozen range before runtime preparation")
        require(not gate["require_unplugged"] or before_warmup_battery["plugged"] is False, "PRESTART_REJECT: charging condition unknown/plugged before runtime preparation")
        installed_matches = False
        if config.get("reuse_verified_installed_APK") is True:
            # Android returns exit 1 and no output when this isolated package
            # has never been installed. This is an absent APK, not a failure.
            paths = client.command("shell","pm","path",package,
                                   accepted_codes=(0,1),reject_stderr=True).decode().strip().splitlines()
            if len(paths)==1 and paths[0].startswith("package:"):
                installed = paths[0][8:]
                require(re.fullmatch(r"/[A-Za-z0-9_./=+~\-]+",installed) is not None,"unsafe installed APK path")
                installed_matches = client.command("shell","sha256sum",installed).decode().split()[0] == config["apk"]["sha256"]
        if not installed_matches:
            client.command("install", "-r", config["apk"]["path"])
        require(client.command("shell", "run-as", package, "test", "!", "-e", remote_input) == b"", "remote session identity already exists")
        client.command("shell", "run-as", package, "mkdir", "-p", remote_input)
        for item in config["files"]:
            name = item["path"]
            tmp = f"/data/local/tmp/a24-{sid}-{name}"
            client.command("push", str(Path(config["bundle_root"]) / name), tmp)
            client.command("shell", "run-as", package, "cp", tmp, f"{remote_input}/{name}")
        client.command("shell", "am", "start", "-n", component, "--es", "a24_protocol", PROTOCOL, "--ez", "a24_execute_authorized", "true", "--es", "session_id", sid)
        polling_started = elapsed_ns(client)
        ready = None
        while elapsed_ns(client) - polling_started <= gate["ready_timeout_ns"]:
            host_raw.append(read_hal(client))
            try:
                ready = json.loads(client.command("exec-out", "run-as", package, "cat", f"{remote_output}/ready.json"))
                break
            except (ValidationError, json.JSONDecodeError):
                client.sleep_ns(gate["status_poll_period_ns"])
        require(ready and ready.get("session_id") == sid and ready.get("plan_sha256") == manifest["plan_sha256"], "runtime ready timeout or exact binding mismatch")
        ready_ns = ready["ready_ns"]
        admitted = {"admitted": False, "reason": "POST_READY_HISTORY_INCOMPLETE"}
        post_ready: list[dict[str, Any]] = []
        while elapsed_ns(client) - ready_ns <= gate["maximum_gate_wait_ns"]:
            post_ready.append(read_hal(client)); host_raw.append(post_ready[-1])
            # Assess a trailing 60-second observed history, never a selected
            # policy outcome or unknown HAL cache update as an independent sample.
            cutoff = post_ready[-1]["device_elapsed_before_ns"] - gate["history_ns"]
            old = [i for i, row in enumerate(post_ready) if row["device_elapsed_before_ns"] <= cutoff]
            window = post_ready[old[-1]:] if old else post_ready
            admitted = admission(window, gate, ready_ns=ready_ns, battery=read_battery(client))
            if admitted["admitted"]:
                break
            client.sleep_ns(gate["hal_poll_period_ns"])
        if not admitted["admitted"]:
            registry.record("PRESTART_REJECT", {"reason": admitted["reason"], "START": False, "session_run_consumed": False})
            (registry.session / "host_hal_partial.jsonl").write_text("".join(json.dumps(row) + "\n" for row in host_raw), encoding="utf-8")
            partial = preserve_partial(client, output, session_id=sid, raw=host_raw, maximum_bytes=gate["maximum_raw_bytes"],package=package)
            return {"status": "PRESTART_REJECT", "admission": admitted, "partial_recovery": partial, "actual_adb_calls": getattr(client, "actual_calls", 0)}
        if manifest.get("perfetto") == "ON":
            trace = start_perfetto(client, sid, config["perfetto"])
        require(elapsed_ns(client) - admitted["read_after_ns"] <= 10 * NS, "AP admission too old before claim")
        registry.record("START", {"manifest_sha256": config["manifest_sha256"], "gate_sha256": config["gate_sha256"], "admission": admitted})
        started = True
        start_approval = {"session_id": sid, "plan_sha256": manifest["plan_sha256"], "admitted": True, "sixty_second_ap_history_checked": True,
                          **{key: admitted[key] for key in ("history_start_ns", "read_before_ns", "read_after_ns")}, "frozen_gate_sha256": config["gate_sha256"]}
        temporary = f"/data/local/tmp/a24-{sid}-start_approval.json"
        # Use a host-only new approval file; no shell text assembled from user data.
        approval_dir = registry.session
        approval_file = approval_dir / "start_approval.json"
        atomic_json(approval_file, start_approval)
        client.command("push", str(approval_file), temporary)
        client.command("shell", "run-as", package, "cp", temporary, f"{remote_input}/start_approval.json")
        session_started = elapsed_ns(client)
        complete = None
        cleanup = None
        journal_closed = None
        def optional_app_document(name: str) -> dict[str, Any] | None:
            try:
                raw = client.command("exec-out", "run-as", package, "cat", f"{remote_output}/{name}")
            except ValidationError:
                return None  # Not yet atomically published; bounded polling only.
            # ADB exec-out does not reliably carry the remote cat exit status.
            # The actual Android CLI returns this ENOENT text on stdout with
            # host exit0. Only this exact missing-path message means absent.
            if raw.strip() == f"cat: {remote_output}/{name}: No such file or directory".encode():
                return None
            try:
                value = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError) as error:
                raise ValidationError(f"malformed published app terminal artifact: {name}") from error
            require(isinstance(value, dict), f"app terminal artifact is not an object: {name}")
            return value
        while elapsed_ns(client) - session_started <= gate["session_timeout_ns"]:
            host_raw.append(read_hal(client))
            require(optional_app_document("failure.json") is None, "app failure artifact exists; preserve FAIL and partial logs")
            complete = optional_app_document("summary.json")
            cleanup = optional_app_document("cleanup.json")
            if complete is not None:
                require(complete.get("status") == "COMPLETED_PENDING_HOST_VALIDATION", "failed or unknown app summary; no COMPLETE")
            if cleanup is not None:
                require(cleanup.get("status") == "DRAINED" and cleanup.get("actual_return_confirmed") is True
                        and cleanup.get("error") is None and cleanup.get("session_failure") is None,
                        "app cleanup failed or actual worker return is unconfirmed; no COMPLETE")
            if complete is not None and cleanup is not None:
                require_completed_app_cleanup(complete, cleanup)
                if config.get("require_journal_closed_before_recovery") is True:
                    journal_closed = optional_app_document("journal_closed.json")
                    if journal_closed is None:
                        client.sleep_ns(gate["hal_poll_period_ns"])
                        continue
                    require(journal_closed.get("status") == "SYNCED_AND_CLOSED" and journal_closed.get("session_id") == sid
                            and isinstance(journal_closed.get("process_id"),int) and journal_closed["process_id"] > 0,
                            "journal close artifact is not bound to this completed session")
                break
            client.sleep_ns(gate["hal_poll_period_ns"])
        require(complete is not None and cleanup is not None, "session summary/cleanup timeout; preserve partial raw and FAIL")
        require(config.get("require_journal_closed_before_recovery") is not True or journal_closed is not None,
                "final journal closure timeout; preserve partial raw and FAIL")
        payload = client.command("exec-out", "run-as", package, "tar", "-cf", "-", remote_output)
        safe_extract(payload, output, session_id=sid, maximum_bytes=gate["maximum_raw_bytes"])
        recovered_summary = load_json(output / "summary.json")
        recovered_cleanup = load_json(output / "cleanup.json")
        require(recovered_summary == complete and recovered_cleanup == cleanup, "recovered terminal artifacts differ from observed app completion")
        require_completed_app_cleanup(recovered_summary, recovered_cleanup)
        if journal_closed is not None:
            require(load_json(output/"journal_closed.json") == journal_closed,"recovered journal closure differs from observed closure")
        require(not (output / "failure.json").exists(), "recovered app failure artifact exists; no COMPLETE")
        if trace is not None:
            trace_result = finish_perfetto(client, trace)
            (output / "instrumentation.pftrace").write_bytes(trace_result.pop("bytes"))
            atomic_json(output / "perfetto_receipt.json", trace_result)
            trace = None
        (output / "session_manifest.json").write_bytes(config["manifest_bytes"])
        (output / "host_hal_raw.jsonl").write_text("".join(json.dumps(row) + "\n" for row in host_raw), encoding="utf-8")
        events = [json.loads(line) for line in (output / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        result = validate_events(manifest, events, load_json(output / "requests.json"))
        # A valid trace is not an energy-calibration/quality/AP-accuracy PASS.
        files = [{"path": path.relative_to(output).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in sorted(output.rglob("*")) if path.is_file()]
        atomic_json(output / "transport_manifest.json", {"schema": "a24-laptop-transport-v1", "files": files})
        registry.record("COMPLETE", {"raw_file_count": len(files), "trace_validation": result["status"],
            "app_cleanup_status": "DRAINED", "actual_worker_return_confirmed": True,
            "journal_final_fsync_close_observed": journal_closed is not None,
            "journal_boundary": "exact post-fsync/close artifact observed and recovered" if journal_closed is not None else "cleanup follows worker close and dispatch barrier; final journal fd.sync/close not independently observed by this host",
            "sensor_metric_status": "REQUIRES_FROZEN_COVERAGE_ANALYSIS_NOT_ASSUMED_PASS"})
        return {"status": "COMPLETE_TRACE_RECOVERED", "trace": result, "actual_adb_calls": getattr(client, "actual_calls", 0)}
    except Exception as error:
        if trace is not None:
            try:
                failed_trace = finish_perfetto(client, trace)
                target = registry.session if registry.session.exists() else registry.root
                (target / f"{sid}-partial.pftrace").write_bytes(failed_trace["bytes"])
            except Exception:
                # The 210s duration remains an independent on-device stop bound.
                pass
        if started:
            registry.record("FAIL", {"reason": str(error), "automatic_retry": False})
        elif not registry.session.exists():
            registry.record("PRESTART_REJECT", {"reason": str(error), "START": False, "session_run_consumed": False})
        preserve_partial(client, output, session_id=sid, raw=host_raw, maximum_bytes=gate["maximum_raw_bytes"],package=package)
        # Preserve host observations even when app artifact recovery was partial.
        forensic = registry.session / "host_hal_partial.jsonl"
        if not forensic.exists():
            forensic.write_text("".join(json.dumps(row) + "\n" for row in host_raw), encoding="utf-8")
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("config", type=Path)
    parser.add_argument("--future-authorization", type=Path)
    parser.add_argument("--frozen-gate", type=Path)
    parser.add_argument("--execute-authorized", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute_authorized:
        print(json.dumps({"status": "PREPARATION_ONLY_DEVICE_UNVERIFIED", "workflow": WORKFLOW, "execution_enabled": False,
                          "actual_device_commands": 0, "NN_calls": 0, "registry_claims": 0, "sessions_consumed": 0}, indent=2))
        return 0
    try:
        require(args.future_authorization is not None and args.frozen_gate is not None, "separate later authorization and frozen gate required")
        config = load_json(args.config)
        config["manifest_bytes"] = args.manifest.read_bytes()
        config["gate_bytes"] = args.frozen_gate.read_bytes()
        result = run_one(load_json(args.manifest), config, load_json(args.future_authorization), load_json(args.frozen_gate), execute_authorized=True)
    except (ValidationError, OSError, ValueError) as error:
        print(json.dumps({"status": "BLOCKED_OR_FAILED_PRESERVE_ATTEMPT", "reason": str(error)}))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
