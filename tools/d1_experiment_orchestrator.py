#!/usr/bin/env python3
"""Run repeatable D1Check CPU/GPU duration experiments without extra packages."""

from __future__ import annotations

import argparse
from collections import deque
from dataclasses import asdict, dataclass
import datetime as dt
import json
import math
import os
from pathlib import Path
import queue
import random
import re
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Iterable
import uuid


VERSION = "0.2"
D1_PACKAGE = "com.example.d1check"
D1_ACTIVITY = f"{D1_PACKAGE}/.MainActivity"
D1_SERVICE = f"{D1_PACKAGE}/.TelemetryForegroundService"
D1_STOP_ACTION = f"{D1_PACKAGE}.action.STOP"
RUNNER_PACKAGE = "com.example.d1check.benchmarkrunner"
RUNNER_ACTIVITY = f"{RUNNER_PACKAGE}/.MainActivity"
REMOTE_RUNNER_DIRECTORY = f"/sdcard/Android/data/{RUNNER_PACKAGE}/files/runs"
MANIFEST_NAME = "experiment_manifest.json"
RUNNER_SCHEMA_VERSION = 2
BASELINE_SECONDS = 60
REMOTE_FALLBACK_GRACE_SECONDS = 30
REMOTE_POLL_INTERVAL_SECONDS = 15
REMOTE_TAIL_LINES = 128
THERMAL_STATUS_RE = re.compile(r"Thermal Status:\s*(-?\d+)", re.IGNORECASE)
RUNNER_FAILURE_EVENTS = {
    "buffer_limit",
    "pilot_safety_rejected",
    "run_context_mismatch",
    "run_error",
}


class OrchestratorError(RuntimeError):
    pass


class WaitTimeout(OrchestratorError):
    pass


class RemoteRunnerAdbError(OrchestratorError):
    pass


class RemoteRunnerAmbiguityError(OrchestratorError):
    pass


class RemoteRunnerValidationError(OrchestratorError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def extract_json(line: str) -> dict[str, Any] | None:
    start = line.find("{")
    if start < 0:
        return None
    try:
        value = json.loads(line[start:])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def parse_adb_devices(text: str) -> dict[str, str]:
    devices: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("List of devices") or line.startswith("*"):
            continue
        fields = line.split()
        if len(fields) >= 2:
            devices[fields[0]] = fields[1]
    return devices


def select_device(devices: dict[str, str], requested_serial: str | None) -> str:
    if requested_serial:
        state = devices.get(requested_serial)
        if state != "device":
            raise OrchestratorError(
                f"requested ADB device is not ready: serial={requested_serial!r}, state={state!r}"
            )
        return requested_serial
    if len(devices) != 1:
        raise OrchestratorError(
            "exactly one ADB target is required when --serial is omitted; "
            f"found={devices}"
        )
    serial, state = next(iter(devices.items()))
    if state != "device":
        raise OrchestratorError(f"ADB target is not ready: serial={serial!r}, state={state!r}")
    return serial


@dataclass(frozen=True)
class SafetySnapshot:
    battery_percent: float
    battery_status: int
    battery_temperature_c: float
    ac_powered: bool
    usb_powered: bool
    wireless_powered: bool
    android_thermal_status: int

    @property
    def unplugged(self) -> bool:
        return not (self.ac_powered or self.usb_powered or self.wireless_powered)


@dataclass(frozen=True)
class SafetyEvaluation:
    mode: str
    pilot_safety_pass: bool
    formal_energy_eligible: bool
    mode_safety_pass: bool
    reasons: tuple[str, ...]

    def to_dict(self, snapshot: SafetySnapshot) -> dict[str, Any]:
        return {
            "checked_utc": utc_now(),
            "mode": self.mode,
            "snapshot": asdict(snapshot) | {"unplugged": snapshot.unplugged},
            "limits": {
                "pilot_battery_percent": [30, 100],
                "formal_battery_percent": [30, 90],
                "required_battery_status": 3,
                "max_battery_temperature_c": 35.0,
                "max_android_thermal_status": 1,
                "require_unplugged": True,
            },
            "pilot_safety_pass": self.pilot_safety_pass,
            "formal_energy_eligible": self.formal_energy_eligible,
            "mode_safety_pass": self.mode_safety_pass,
            "reasons": list(self.reasons),
        }


def _parse_bool(value: str, name: str) -> bool:
    lowered = value.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise ValueError(f"{name}: expected true/false, got {value!r}")


def parse_safety_snapshot(battery_text: str, thermal_text: str) -> SafetySnapshot:
    values: dict[str, str] = {}
    for line in battery_text.splitlines():
        match = re.match(r"^\s*([^:]+):\s*(.*?)\s*$", line)
        if match:
            values[match.group(1).strip().lower()] = match.group(2).strip()

    def required(name: str) -> str:
        value = values.get(name.lower())
        if value is None or value == "":
            raise ValueError(f"dumpsys battery missing {name!r}")
        return value

    try:
        level = int(required("level"))
        scale = int(required("scale"))
        status = int(required("status"))
        temperature_c = int(required("temperature")) / 10.0
    except ValueError as error:
        raise ValueError(f"malformed dumpsys battery: {error}") from error
    if scale <= 0:
        raise ValueError(f"malformed dumpsys battery: scale must be positive, got {scale}")
    thermal_match = THERMAL_STATUS_RE.search(thermal_text)
    if thermal_match is None:
        raise ValueError("dumpsys thermalservice missing Thermal Status")
    return SafetySnapshot(
        battery_percent=level * 100.0 / scale,
        battery_status=status,
        battery_temperature_c=temperature_c,
        ac_powered=_parse_bool(required("AC powered"), "AC powered"),
        usb_powered=_parse_bool(required("USB powered"), "USB powered"),
        wireless_powered=_parse_bool(required("Wireless powered"), "Wireless powered"),
        android_thermal_status=int(thermal_match.group(1)),
    )


def evaluate_safety(snapshot: SafetySnapshot, mode: str) -> SafetyEvaluation:
    reasons: list[str] = []
    if not snapshot.unplugged:
        reasons.append("device_plugged")
    if snapshot.battery_status != 3:
        reasons.append("not_discharging")
    if not 30.0 <= snapshot.battery_percent <= 100.0:
        reasons.append("pilot_battery_level")
    if not math.isfinite(snapshot.battery_temperature_c) or not (
        0.0 <= snapshot.battery_temperature_c <= 35.0
    ):
        reasons.append("battery_temperature")
    if not 0 <= snapshot.android_thermal_status <= 1:
        reasons.append("android_thermal_status")
    pilot_pass = not reasons
    formal_energy_eligible = pilot_pass and 30.0 <= snapshot.battery_percent <= 90.0
    if mode == "formal" and pilot_pass and not formal_energy_eligible:
        reasons.append("formal_battery_level")
    mode_pass = pilot_pass and (mode == "pilot" or formal_energy_eligible)
    return SafetyEvaluation(mode, pilot_pass, formal_energy_eligible, mode_pass, tuple(reasons))


def build_plan(resources: Iterable[str], repeat: int, seed: int | None) -> list[dict[str, Any]]:
    normalized = [value.upper() for value in resources]
    if not normalized or any(value not in {"CPU", "GPU"} for value in normalized):
        raise ValueError("resources must contain CPU and/or GPU")
    if len(set(normalized)) != len(normalized):
        raise ValueError("resources must not contain duplicates")
    if repeat < 1:
        raise ValueError("repeat must be at least 1")
    entries = [
        {"resource": resource, "repetition": repetition}
        for repetition in range(1, repeat + 1)
        for resource in normalized
    ]
    if seed is not None:
        random.Random(seed).shuffle(entries)
    for index, entry in enumerate(entries, 1):
        entry.update(
            {
                "slot_id": f"{index:03d}-{entry['resource'].lower()}-r{entry['repetition']:03d}",
                "order_index": index,
                "status": "pending",
                "attempts": 0,
                "failures": [],
                "steps": [],
            }
        )
    return entries


def runnable_slots(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Resume checkpoint rule: a completed slot is immutable and never scheduled again."""
    return [slot for slot in manifest["runs"] if slot.get("status") != "completed"]


def runner_intent_arguments(
    resource: str,
    cpu_threads: int,
    duration_s: int,
    warmup: int,
    run_id: str,
    command_id: str,
) -> list[str]:
    arguments = [
        "shell", "am", "start", "-W", "-n", RUNNER_ACTIVITY,
        "--ez", "d1_auto_start", "true",
        "--es", "d1_resource", resource,
    ]
    if resource == "CPU":
        arguments += ["--ei", "d1_cpu_threads", str(cpu_threads)]
    arguments += [
        "--es", "d1_limit_mode", "DURATION",
        "--el", "d1_duration_s", str(duration_s),
        "--ei", "d1_warmup_count", str(warmup),
        "--es", "d1_run_id", run_id,
        "--es", "d1_command_id", command_id,
        "--es", "d1_experiment_mode", "BASIC",
    ]
    return arguments


def start_run_arguments() -> list[str]:
    return [
        "shell", "am", "start", "-W", "-n", D1_ACTIVITY,
        "--es", "d1_automation_command", "START_RUN",
    ]


def stop_run_arguments() -> list[str]:
    return [
        "shell", "am", "start", "-W", "-n", D1_ACTIVITY,
        "--es", "d1_automation_command", "STOP_RUN",
    ]


def direct_stop_arguments() -> list[str]:
    return [
        "shell", "run-as", D1_PACKAGE,
        "am", "start-foreground-service", "--user", "0",
        "-a", D1_STOP_ACTION, "-n", D1_SERVICE,
    ]


class AdbClient:
    def __init__(self, adb: str, serial: str | None = None) -> None:
        self.adb = adb
        self.serial = serial

    @property
    def base(self) -> list[str]:
        return [self.adb] + (["-s", self.serial] if self.serial else [])

    def run(
        self,
        arguments: list[str],
        *,
        timeout: float = 30,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                self.base + arguments,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise OrchestratorError(
                f"ADB command timed out after {timeout}s: {self.base + arguments}"
            ) from error
        if check and result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "no output"
            raise OrchestratorError(
                f"ADB command failed rc={result.returncode}: {arguments}; {detail[:800]}"
            )
        return result

    def popen(self, arguments: list[str]) -> subprocess.Popen[str]:
        return subprocess.Popen(
            self.base + arguments,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )


class ProcessLines:
    _END = object()

    def __init__(self, process: subprocess.Popen[str], name: str) -> None:
        self.process = process
        self.name = name
        self.lines: deque[str] = deque(maxlen=20_000)
        self.queue: queue.Queue[str | object] = queue.Queue()
        self.thread = threading.Thread(target=self._pump, name=f"{name}-output", daemon=True)
        self.thread.start()

    def _pump(self) -> None:
        assert self.process.stdout is not None
        try:
            for line in self.process.stdout:
                value = line.rstrip("\r\n")
                self.lines.append(value)
                self.queue.put(value)
        finally:
            self.queue.put(self._END)

    def wait_for_line(
        self,
        predicate: Callable[[str], bool],
        timeout: float,
        description: str,
        companions: Iterable["ProcessLines"] = (),
    ) -> str:
        deadline = time.monotonic() + timeout
        while True:
            for companion in companions:
                code = companion.process.poll()
                if code is not None:
                    raise OrchestratorError(
                        f"{companion.name} exited unexpectedly rc={code}; "
                        f"tail={list(companion.lines)[-10:]}"
                    )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise WaitTimeout(f"timeout waiting for {description} after {timeout:.1f}s")
            try:
                item = self.queue.get(timeout=min(0.25, remaining))
            except queue.Empty:
                continue
            if item is self._END:
                code = self.process.poll()
                raise OrchestratorError(
                    f"{self.name} stdout EOF while waiting for {description}; rc={code}; "
                    f"tail={list(self.lines)[-10:]}"
                )
            line = str(item)
            if predicate(line):
                return line

    def wait_for_event(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        timeout: float,
        description: str,
        companions: Iterable["ProcessLines"] = (),
    ) -> dict[str, Any]:
        matched: dict[str, Any] = {}

        def matches(line: str) -> bool:
            event = extract_json(line)
            if event is not None and predicate(event):
                matched.update(event)
                return True
            return False

        self.wait_for_line(matches, timeout, description, companions)
        return matched

    def terminate(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.thread.join(timeout=2)


def stop_d1_run(
    adb: AdbClient,
    wait_for_stop: Callable[[float], dict[str, Any]],
    timeout: float,
) -> dict[str, Any]:
    activity_result = adb.run(stop_run_arguments(), timeout=20, check=False)
    activity_error: str | None = None
    if activity_result.returncode == 0:
        try:
            event = wait_for_stop(timeout)
            return {
                "event": event,
                "recovery_used": False,
                "activity_stop_error": None,
            }
        except WaitTimeout as error:
            activity_error = str(error)
    else:
        activity_error = (
            activity_result.stderr.strip()
            or activity_result.stdout.strip()
            or f"returncode={activity_result.returncode}"
        )
    recovery = adb.run(direct_stop_arguments(), timeout=20, check=False)
    if recovery.returncode != 0:
        detail = recovery.stderr.strip() or recovery.stdout.strip() or "no output"
        raise OrchestratorError(
            "STOP_RUN and direct service STOP both failed; "
            f"activity_error={activity_error!r}; direct_rc={recovery.returncode}; {detail[:800]}"
        )
    event = wait_for_stop(timeout)
    return {
        "event": event,
        "recovery_used": True,
        "activity_stop_error": activity_error,
    }


def classify_runner_terminal(event: dict[str, Any], run_id: str) -> str | None:
    if event.get("source") != "gpu" or event.get("run_id") != run_id:
        return None
    name = event.get("event")
    if name == "file_summary":
        return "success" if event.get("status") == "ok" else "failure"
    if name in RUNNER_FAILURE_EVENTS:
        return "failure"
    if name == "run_metadata" and event.get("experiment_valid") is False:
        return "failure"
    return None


@dataclass(frozen=True)
class RemoteRunnerProbe:
    state: str
    remote_path: str | None = None
    event: dict[str, Any] | None = None
    detail: str | None = None


@dataclass(frozen=True)
class RunnerTerminalDetection:
    kind: str
    event: dict[str, Any]
    source: str
    fallback_used: bool
    remote_runner_path: str | None
    logcat_terminal_missing: bool
    remote_probe_count: int
    final_remote_probe_used: bool


def _adb_failure_detail(result: subprocess.CompletedProcess[str]) -> str:
    return result.stderr.strip() or result.stdout.strip() or "no output"


def _is_remote_missing(result: subprocess.CompletedProcess[str]) -> bool:
    detail = f"{result.stdout}\n{result.stderr}".lower()
    return "no such file or directory" in detail


def probe_remote_runner(adb: AdbClient, run_id: str) -> RemoteRunnerProbe:
    listing = adb.run(
        ["shell", "ls", "-1", REMOTE_RUNNER_DIRECTORY],
        timeout=20,
        check=False,
    )
    if listing.returncode != 0:
        if _is_remote_missing(listing):
            return RemoteRunnerProbe("not_found", detail=_adb_failure_detail(listing))
        raise RemoteRunnerAdbError(
            f"remote runner ls failed rc={listing.returncode}: "
            f"{_adb_failure_detail(listing)[:800]}"
        )
    pattern = re.compile(
        rf"^gpu-events-{re.escape(run_id)}-([A-Za-z0-9-]+)\.jsonl$"
    )
    matches: list[tuple[str, str]] = []
    for raw_line in listing.stdout.splitlines():
        filename = Path(raw_line.strip()).name
        match = pattern.fullmatch(filename)
        if match:
            matches.append((filename, match.group(1)))
    if not matches:
        return RemoteRunnerProbe("not_found")
    if len(matches) != 1:
        paths = [f"{REMOTE_RUNNER_DIRECTORY}/{filename}" for filename, _ in matches]
        raise RemoteRunnerAmbiguityError(
            f"multiple remote runner files for run_id={run_id}: {paths}"
        )
    filename, expected_session_id = matches[0]
    remote_path = f"{REMOTE_RUNNER_DIRECTORY}/{filename}"
    tail = adb.run(
        ["shell", "tail", "-n", str(REMOTE_TAIL_LINES), remote_path],
        timeout=20,
        check=False,
    )
    if tail.returncode != 0:
        raise RemoteRunnerAdbError(
            f"remote runner tail failed rc={tail.returncode} path={remote_path}: "
            f"{_adb_failure_detail(tail)[:800]}"
        )
    raw_lines = [line for line in tail.stdout.splitlines() if line.strip()]
    if not raw_lines:
        return RemoteRunnerProbe("incomplete", remote_path, detail="empty remote tail")
    events: list[dict[str, Any]] = []
    for index, line in enumerate(raw_lines):
        event = extract_json(line)
        if event is None:
            if index == len(raw_lines) - 1:
                return RemoteRunnerProbe(
                    "incomplete", remote_path, detail="partial final JSONL record"
                )
            raise RemoteRunnerValidationError(
                f"invalid JSON in remote runner tail path={remote_path} line={index + 1}"
            )
        events.append(event)
    previous_sequence: int | None = None
    for event in events:
        if event.get("run_id") != run_id:
            raise RemoteRunnerValidationError(
                f"remote runner run_id mismatch path={remote_path}: {event.get('run_id')!r}"
            )
        if event.get("source") != "gpu":
            raise RemoteRunnerValidationError(
                f"remote runner source mismatch path={remote_path}: {event.get('source')!r}"
            )
        if event.get("schema_version") != RUNNER_SCHEMA_VERSION:
            raise RemoteRunnerValidationError(
                f"remote runner schema mismatch path={remote_path}: "
                f"{event.get('schema_version')!r}"
            )
        if event.get("runner_session_id") != expected_session_id:
            raise RemoteRunnerValidationError(
                f"remote runner session mismatch path={remote_path}: "
                f"{event.get('runner_session_id')!r}"
            )
        sequence = event.get("sequence")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
            raise RemoteRunnerValidationError(
                f"remote runner invalid sequence path={remote_path}: {sequence!r}"
            )
        if previous_sequence is not None and sequence != previous_sequence + 1:
            raise RemoteRunnerValidationError(
                f"remote runner non-contiguous tail sequence path={remote_path}: "
                f"{previous_sequence}->{sequence}"
            )
        previous_sequence = sequence
    failure = next(
        (
            event for event in reversed(events)
            if event.get("event") in RUNNER_FAILURE_EVENTS or event.get("status") == "error"
        ),
        None,
    )
    if failure is not None:
        return RemoteRunnerProbe("failure", remote_path, failure)
    final = events[-1]
    if final.get("event") != "file_summary":
        return RemoteRunnerProbe(
            "incomplete",
            remote_path,
            final,
            f"last event is {final.get('event')!r}, not file_summary",
        )
    if final.get("status") != "ok":
        return RemoteRunnerProbe("failure", remote_path, final)
    sequence = final["sequence"]
    if (
        final.get("sequence_first") != 0
        or final.get("sequence_last") != sequence
        or final.get("file_event_count") != sequence + 1
    ):
        raise RemoteRunnerValidationError(
            f"remote file_summary sequence metadata mismatch path={remote_path}"
        )
    return RemoteRunnerProbe("success", remote_path, final)


def wait_for_runner_terminal(
    run_id: str,
    wait_for_logcat: Callable[[float], dict[str, Any]],
    probe_remote: Callable[[bool], RemoteRunnerProbe],
    expected_completion_delay_s: float,
    hard_timeout_s: float,
    *,
    sparse_poll_interval_s: float = REMOTE_POLL_INTERVAL_SECONDS,
    monotonic: Callable[[], float] = time.monotonic,
) -> RunnerTerminalDetection:
    started = monotonic()
    fallback_at = started + expected_completion_delay_s
    deadline = started + hard_timeout_s
    next_probe = fallback_at
    probe_count = 0
    while True:
        now = monotonic()
        if now >= deadline:
            probe_count += 1
            final_probe = probe_remote(True)
            if final_probe.state in {"success", "failure"}:
                assert final_probe.event is not None
                return RunnerTerminalDetection(
                    final_probe.state,
                    final_probe.event,
                    "remote_runner_jsonl",
                    True,
                    final_probe.remote_path,
                    True,
                    probe_count,
                    True,
                )
            raise WaitTimeout(
                f"runner hard timeout after {hard_timeout_s:.1f}s; final remote state="
                f"{final_probe.state}; path={final_probe.remote_path}; "
                f"detail={final_probe.detail}"
            )
        wait_until = min(deadline, next_probe)
        if now < wait_until:
            try:
                event = wait_for_logcat(wait_until - now)
            except WaitTimeout:
                continue
            kind = classify_runner_terminal(event, run_id)
            if kind is None:
                continue
            return RunnerTerminalDetection(
                kind,
                event,
                "logcat",
                False,
                None,
                False,
                probe_count,
                False,
            )
        probe_count += 1
        current_probe = probe_remote(False)
        if current_probe.state in {"success", "failure"}:
            assert current_probe.event is not None
            return RunnerTerminalDetection(
                current_probe.state,
                current_probe.event,
                "remote_runner_jsonl",
                True,
                current_probe.remote_path,
                True,
                probe_count,
                False,
            )
        next_probe = monotonic() + sparse_poll_interval_s


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise OrchestratorError(f"expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            event = extract_json(line)
            if event is None:
                raise OrchestratorError(f"invalid JSONL at {path}:{line_number}")
            events.append(event)
    return events


def validate_result(
    run_dir: Path,
    resource: str,
    cpu_threads: int,
    duration_s: int,
    warmup: int,
    run_id: str,
    command_id: str,
    mode: str,
) -> dict[str, Any]:
    summary = load_json(run_dir / "merged" / "summary.json")
    capture = load_json(run_dir / "metadata.json")
    runner_paths = sorted((run_dir / "gpu").glob(f"gpu-events-{run_id}-*.jsonl"))
    if len(runner_paths) != 1:
        raise OrchestratorError(
            f"expected exactly one runner session for {run_id}, found {len(runner_paths)}"
        )
    events = load_jsonl(runner_paths[0])
    metadata = next((event for event in events if event.get("event") == "run_metadata"), None)
    footer = next((event for event in reversed(events) if event.get("event") == "file_summary"), None)
    if metadata is None or footer is None:
        raise OrchestratorError("runner file lacks run_metadata or file_summary")
    coverage = summary.get("thermal_coverage")
    coverage_pass = isinstance(coverage, dict) and coverage.get("passes_formal_requirement") is True
    checks = {
        "capture_clean": capture.get("capture_error") is None,
        "run_id": metadata.get("run_id") == run_id == summary.get("run_id"),
        "command_id": metadata.get("command_id") == command_id,
        "expected_run_id": metadata.get("expected_run_id") == run_id,
        "resource": metadata.get("resource") == resource == summary.get("resource"),
        "cpu_threads": (
            metadata.get("cpu_threads") == cpu_threads
            if resource == "CPU" else metadata.get("cpu_threads") is None
        ),
        "cpu_affinity_none": metadata.get("cpu_affinity") == "NONE",
        "auto_start": metadata.get("auto_start") is True,
        "basic_capture": str(metadata.get("experiment_mode", "")).upper() == "BASIC",
        "duration_mode": metadata.get("limit_mode") == "DURATION",
        "requested_duration": metadata.get("requested_duration_s") == duration_s,
        "target_duration": metadata.get("target_duration_ns") == duration_s * 1_000_000_000,
        "warmup": metadata.get("warmup_count") == warmup,
        "duration_complete": metadata.get("termination_reason") == "duration_complete",
        "runner_valid": metadata.get("experiment_valid") is True,
        "pilot_safety": metadata.get("pilot_safety_pass") is True,
        "file_summary": footer.get("status") == "ok",
        "run_envelope": summary.get("run_envelope_validation") == "pass",
        "single_runner_session": summary.get("runner_session_count") == 1,
        "thermal_coverage": coverage_pass,
        "inference_present": int(metadata.get("completed_inference_count") or 0) > 0,
    }
    if mode == "formal":
        checks["formal_energy_eligible"] = metadata.get("formal_energy_eligible") is True
        if resource == "GPU":
            checks["formal_gpu_valid"] = summary.get("formal_gpu_valid") is True
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "valid": not failed,
        "checks": checks,
        "failed_checks": failed,
        "summary_path": str(run_dir / "merged" / "summary.json"),
        "runner_file": str(runner_paths[0]),
        "summary": summary,
    }


class ExperimentOrchestrator:
    def __init__(self, args: argparse.Namespace, manifest: dict[str, Any], path: Path) -> None:
        self.args = args
        self.manifest = manifest
        self.manifest_path = path
        self.logger_path = Path(args.logger).resolve()
        self.runs_root = path.parent / "runs"
        self.adb: AdbClient | None = None

    def save(self) -> None:
        self.manifest["updated_utc"] = utc_now()
        atomic_write_json(self.manifest_path, self.manifest)

    def step(self, slot: dict[str, Any], name: str, **details: Any) -> None:
        slot["steps"].append({"utc": utc_now(), "name": name, **details})
        self.save()

    def _logger_command(self, command: str, *extra: str) -> list[str]:
        assert self.adb is not None and self.adb.serial is not None
        return [
            sys.executable, str(self.logger_path),
            "--adb", self.adb.adb, "--serial", self.adb.serial,
            command, *extra,
        ]

    @staticmethod
    def _run_host(command: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise OrchestratorError(f"host command timed out: {command}") from error
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "no output"
            raise OrchestratorError(
                f"host command failed rc={result.returncode}: {command}; {detail[:1200]}"
            )
        return result

    def connect(self) -> None:
        probe = AdbClient(self.args.adb)
        result = probe.run(["devices", "-l"], timeout=15)
        devices = parse_adb_devices(result.stdout)
        serial = select_device(devices, self.args.serial)
        self.adb = AdbClient(self.args.adb, serial)
        model = self.adb.run(["shell", "getprop", "ro.product.model"], timeout=10).stdout.strip()
        fingerprint = self.adb.run(
            ["shell", "getprop", "ro.build.fingerprint"], timeout=10
        ).stdout.strip()
        self.manifest["device"] = {
            "serial": serial,
            "model": model,
            "fingerprint": fingerprint,
        }
        self.save()

    def safety_check(self) -> tuple[SafetySnapshot, SafetyEvaluation]:
        assert self.adb is not None
        battery = self.adb.run(["shell", "dumpsys", "battery"], timeout=15).stdout
        thermal = self.adb.run(["shell", "dumpsys", "thermalservice"], timeout=15).stdout
        snapshot = parse_safety_snapshot(battery, thermal)
        return snapshot, evaluate_safety(snapshot, self.args.mode)

    def _wait_run_stop(
        self,
        monitor: ProcessLines,
        logger: ProcessLines,
        run_id: str,
        timeout: float,
    ) -> dict[str, Any]:
        try:
            return monitor.wait_for_event(
                lambda event: (
                    event.get("source") == "d1check"
                    and event.get("event") == "run_stop"
                    and event.get("run_id") == run_id
                    and event.get("status") == "ok"
                ),
                timeout,
                f"run_stop for {run_id}",
            )
        except WaitTimeout as error:
            logger_code = logger.process.poll()
            if logger_code not in (None, 0):
                raise OrchestratorError(
                    f"d1_logger exited abnormally rc={logger_code} before run_stop; "
                    f"tail={list(logger.lines)[-20:]}"
                ) from error
            raise

    def _failure_cleanup(
        self,
        slot: dict[str, Any],
        run_id: str | None,
        run_stopped: bool,
        monitor: ProcessLines | None,
        logger: ProcessLines | None,
    ) -> list[str]:
        assert self.adb is not None
        cleanup_errors: list[str] = []

        def record(name: str, **details: Any) -> None:
            try:
                self.step(slot, name, **details)
            except Exception as error:
                cleanup_errors.append(f"manifest step {name}: {error}")

        confirmed = run_stopped
        stop_event = slot.get("run_stop_event")
        activity_error: str | None = None
        if run_id is None:
            record(
                "failure_cleanup_activity_stop",
                status="skipped",
                attempted=False,
                reason="run_not_started",
            )
        elif confirmed:
            record(
                "failure_cleanup_activity_stop",
                status="skipped",
                attempted=False,
                reason="run_already_stopped",
            )
        else:
            try:
                activity = self.adb.run(stop_run_arguments(), timeout=20, check=False)
                activity_error = None if activity.returncode == 0 else _adb_failure_detail(activity)
                record(
                    "failure_cleanup_activity_stop",
                    status="ok" if activity.returncode == 0 else "error",
                    attempted=True,
                    returncode=activity.returncode,
                    error=activity_error,
                )
                if activity.returncode == 0 and monitor is not None and logger is not None:
                    try:
                        stop_event = self._wait_run_stop(monitor, logger, run_id, 5)
                        confirmed = True
                    except Exception as error:
                        activity_error = str(error)
            except Exception as error:
                activity_error = str(error)
                cleanup_errors.append(f"Activity STOP: {error}")
                record(
                    "failure_cleanup_activity_stop",
                    status="error",
                    attempted=True,
                    error=str(error),
                )

        direct_used = run_id is not None and not confirmed
        if not direct_used:
            record(
                "failure_cleanup_direct_service_stop",
                status="skipped",
                used=False,
                reason="run_not_started_or_already_stopped",
            )
        else:
            try:
                direct = self.adb.run(direct_stop_arguments(), timeout=20, check=False)
                record(
                    "failure_cleanup_direct_service_stop",
                    status="ok" if direct.returncode == 0 else "error",
                    used=True,
                    returncode=direct.returncode,
                    error=None if direct.returncode == 0 else _adb_failure_detail(direct),
                )
                if direct.returncode != 0:
                    cleanup_errors.append(
                        f"direct service STOP rc={direct.returncode}: {_adb_failure_detail(direct)}"
                    )
                elif monitor is not None and logger is not None:
                    try:
                        stop_event = self._wait_run_stop(monitor, logger, run_id, 5)
                        confirmed = True
                    except Exception as error:
                        cleanup_errors.append(f"run_stop after direct STOP: {error}")
            except Exception as error:
                cleanup_errors.append(f"direct service STOP: {error}")
                record(
                    "failure_cleanup_direct_service_stop",
                    status="error",
                    used=True,
                    error=str(error),
                )

        slot["stop_recovery_used"] = bool(slot.get("stop_recovery_used") or direct_used)
        slot["activity_stop_error"] = activity_error or slot.get("activity_stop_error")
        if stop_event is not None:
            slot["run_stop_event"] = stop_event
        record(
            "failure_cleanup_run_stop_confirmation",
            status="ok" if confirmed else "unconfirmed",
            confirmed=confirmed,
            run_id=run_id,
        )

        if logger is None:
            record(
                "failure_cleanup_logger",
                status="skipped",
                action="not_started",
            )
        else:
            initial_code = logger.process.poll()
            forced = initial_code is None
            try:
                if initial_code is None and confirmed:
                    try:
                        initial_code = logger.process.wait(timeout=10)
                        forced = False
                    except subprocess.TimeoutExpired:
                        pass
                if logger.process.poll() is None:
                    logger.terminate()
                final_code = logger.process.poll()
                slot["logger_cleanup_action"] = "forced_termination" if forced else "exited"
                if not forced and final_code != 0:
                    cleanup_errors.append(f"logger exited abnormally rc={final_code}")
                record(
                    "failure_cleanup_logger",
                    status=(
                        "forced" if forced else "ok" if final_code == 0 else "error"
                    ),
                    action=slot["logger_cleanup_action"],
                    initial_returncode=initial_code,
                    final_returncode=final_code,
                )
            except Exception as error:
                cleanup_errors.append(f"logger cleanup: {error}")
                record(
                    "failure_cleanup_logger",
                    status="error",
                    action="termination_failed",
                    error=str(error),
                )

        try:
            runner_stop = self.adb.run(
                ["shell", "am", "force-stop", RUNNER_PACKAGE], timeout=20, check=False
            )
            if runner_stop.returncode != 0:
                cleanup_errors.append(
                    f"runner force-stop rc={runner_stop.returncode}: "
                    f"{_adb_failure_detail(runner_stop)}"
                )
            record(
                "failure_cleanup_runner_force_stop",
                status="ok" if runner_stop.returncode == 0 else "error",
                returncode=runner_stop.returncode,
                error=None if runner_stop.returncode == 0 else _adb_failure_detail(runner_stop),
            )
        except Exception as error:
            cleanup_errors.append(f"runner force-stop: {error}")
            record(
                "failure_cleanup_runner_force_stop",
                status="error",
                error=str(error),
            )

        local_run_dir = self.runs_root / run_id if run_id else None
        local_runner_files = (
            [str(path) for path in sorted((local_run_dir / "gpu").glob("*.jsonl"))]
            if local_run_dir is not None and (local_run_dir / "gpu").is_dir()
            else []
        )
        remote_artifact = slot.get("remote_runner_path") or (
            f"{REMOTE_RUNNER_DIRECTORY}/gpu-events-{run_id}-*.jsonl" if run_id else None
        )
        slot["failure_artifacts"] = {
            "manifest": str(self.manifest_path),
            "local_run_dir": str(local_run_dir) if local_run_dir else None,
            "local_run_dir_exists": local_run_dir.is_dir() if local_run_dir else False,
            "local_runner_files": local_runner_files,
            "remote_runner_path_or_pattern": remote_artifact,
        }
        record(
            "failure_cleanup_artifacts",
            status="recorded",
            **slot["failure_artifacts"],
        )
        return cleanup_errors

    def run_slot(self, slot: dict[str, Any]) -> None:
        assert self.adb is not None
        slot["status"] = "running"
        slot["attempts"] += 1
        slot["attempt_started_utc"] = utc_now()
        slot["error"] = None
        slot["terminal_event_source"] = None
        slot["terminal_fallback_used"] = False
        slot["remote_runner_path"] = None
        slot["logcat_terminal_missing"] = False
        slot["remote_probe_count"] = 0
        slot["final_remote_probe_used"] = False
        slot["stop_recovery_used"] = None
        self.save()
        logger: ProcessLines | None = None
        monitor: ProcessLines | None = None
        run_id: str | None = None
        run_stopped = False
        try:
            self.adb.run(["shell", "am", "force-stop", RUNNER_PACKAGE], timeout=20)
            self.step(slot, "runner_force_stop", status="ok")

            initial_activity_stop = self.adb.run(
                stop_run_arguments(), timeout=20, check=False
            )
            initial_direct_stop = self.adb.run(
                direct_stop_arguments(), timeout=20, check=False
            )
            self.step(
                slot,
                "pre_capture_d1_quiesce",
                status="ok" if initial_direct_stop.returncode == 0 else "error",
                activity_returncode=initial_activity_stop.returncode,
                direct_returncode=initial_direct_stop.returncode,
            )
            if initial_direct_stop.returncode != 0:
                detail = (
                    initial_direct_stop.stderr.strip()
                    or initial_direct_stop.stdout.strip()
                    or "no output"
                )
                raise OrchestratorError(f"cannot quiesce D1Check before capture: {detail[:800]}")
            time.sleep(1.0)

            snapshot, safety = self.safety_check()
            slot["safety_preflight"] = safety.to_dict(snapshot)
            self.step(slot, "safety_preflight", status="ok" if safety.mode_safety_pass else "rejected")
            if not safety.mode_safety_pass:
                raise OrchestratorError(
                    "safety preflight rejected: " + ",".join(safety.reasons)
                )

            self._run_host(self._logger_command("clear"), timeout=30)
            self.step(slot, "logger_clear", status="ok")

            capture_process = subprocess.Popen(
                self._logger_command("capture", str(self.runs_root)),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            logger = ProcessLines(capture_process, "d1_logger")
            logger.wait_for_line(
                lambda line: "capture started" in line.lower(),
                20,
                "d1_logger capture started",
            )
            self.step(slot, "logger_capture_started", status="ok")

            monitor = ProcessLines(
                self.adb.popen([
                    "logcat", "-v", "raw", "D1CHECK_EVENT:I", "D1GPU:I", "*:S",
                ]),
                "orchestrator_logcat",
            )
            self.step(slot, "event_monitor_started", status="ok")

            self.adb.run(start_run_arguments(), timeout=20)
            previous_ids = {
                item.get("run_id") for item in self.manifest["runs"] if item.get("run_id")
            }
            run_start = monitor.wait_for_event(
                lambda event: (
                    event.get("source") == "d1check"
                    and event.get("event") == "run_start"
                    and event.get("status") == "ok"
                    and event.get("run_id") not in previous_ids
                ),
                20,
                "new D1Check run_start",
                [logger],
            )
            run_id = str(run_start.get("run_id"))
            try:
                run_id = str(uuid.UUID(run_id))
            except ValueError as error:
                raise OrchestratorError(f"run_start contains invalid UUID: {run_id!r}") from error
            command_id = str(uuid.uuid4())
            slot["run_id"] = run_id
            slot["command_id"] = command_id
            slot["run_start_event"] = run_start
            self.step(slot, "d1_run_started", status="ok", run_id=run_id)

            self.adb.run(
                runner_intent_arguments(
                    slot["resource"], self.args.cpu_threads, self.args.duration,
                    self.args.warmup, run_id, command_id,
                ),
                timeout=30,
            )
            self.step(slot, "runner_auto_start_sent", status="ok", command_id=command_id)

            runner_timeout = self.args.duration + 180 + min(self.args.warmup * 2, 3600)
            def remote_probe(final: bool) -> RemoteRunnerProbe:
                slot["terminal_fallback_used"] = True
                slot["logcat_terminal_missing"] = True
                slot["remote_probe_count"] += 1
                slot["final_remote_probe_used"] = final
                result = probe_remote_runner(self.adb, run_id)
                slot["remote_runner_path"] = result.remote_path
                slot["last_remote_probe_state"] = result.state
                slot["last_remote_probe_detail"] = result.detail
                return result

            terminal = wait_for_runner_terminal(
                run_id,
                lambda timeout: monitor.wait_for_event(
                    lambda event: classify_runner_terminal(event, run_id) is not None,
                    timeout,
                    f"runner terminal event for {run_id}",
                    [logger],
                ),
                remote_probe,
                BASELINE_SECONDS + self.args.duration + REMOTE_FALLBACK_GRACE_SECONDS,
                runner_timeout,
            )
            terminal_kind = terminal.kind
            slot["runner_terminal_event"] = terminal.event
            slot["terminal_event_source"] = terminal.source
            slot["terminal_fallback_used"] = terminal.fallback_used
            slot["remote_runner_path"] = terminal.remote_runner_path
            slot["logcat_terminal_missing"] = terminal.logcat_terminal_missing
            slot["remote_probe_count"] = terminal.remote_probe_count
            slot["final_remote_probe_used"] = terminal.final_remote_probe_used
            self.step(
                slot,
                "runner_terminal_event",
                status=terminal_kind,
                source=terminal.source,
                fallback_used=terminal.fallback_used,
                remote_runner_path=terminal.remote_runner_path,
            )

            stop_result = stop_d1_run(
                self.adb,
                lambda timeout: self._wait_run_stop(monitor, logger, run_id, timeout),
                15,
            )
            run_stopped = True
            slot["run_stop_event"] = stop_result["event"]
            slot["stop_recovery_used"] = stop_result["recovery_used"]
            slot["activity_stop_error"] = stop_result["activity_stop_error"]
            self.step(
                slot,
                "d1_run_stopped",
                status="ok",
                recovery_used=stop_result["recovery_used"],
            )

            try:
                logger_code = logger.process.wait(timeout=30)
            except subprocess.TimeoutExpired as error:
                raise OrchestratorError("d1_logger did not exit after run_stop") from error
            if logger_code != 0:
                raise OrchestratorError(
                    f"d1_logger exited abnormally rc={logger_code}; tail={list(logger.lines)[-20:]}"
                )
            self.step(slot, "logger_exited", status="ok", returncode=logger_code)

            if terminal_kind == "failure":
                raise OrchestratorError(
                    f"runner emitted failure event from {terminal.source}: {terminal.event}"
                )

            run_dir = self.runs_root / run_id
            if not run_dir.is_dir():
                raise OrchestratorError(f"logger run directory not found: {run_dir}")
            slot["run_dir"] = str(run_dir)
            self.step(slot, "run_directory_identified", status="ok", path=str(run_dir))

            analysis = self._run_host(
                [sys.executable, str(self.logger_path), "analyze", str(run_dir)],
                timeout=120,
            )
            slot["analyze_stdout"] = analysis.stdout[-4000:]
            self.step(slot, "analysis_completed", status="ok")

            validation = validate_result(
                run_dir, slot["resource"], self.args.cpu_threads,
                self.args.duration, self.args.warmup, run_id, command_id, self.args.mode,
            )
            slot["validation"] = validation
            if not validation["valid"]:
                raise OrchestratorError(
                    "result validation failed: " + ",".join(validation["failed_checks"])
                )
            slot["status"] = "completed"
            slot["completed_utc"] = utc_now()
            self.save()
        except Exception as error:
            slot["status"] = "failed"
            slot["error"] = f"{error.__class__.__name__}: {error}"
            slot["failed_utc"] = utc_now()
            cleanup_errors: list[str] = []
            try:
                self.step(slot, "failure_detected", status="error", error=slot["error"])
            except Exception as step_error:
                cleanup_errors.append(f"record failure_detected: {step_error}")
            try:
                cleanup_errors.extend(
                    self._failure_cleanup(slot, run_id, run_stopped, monitor, logger)
                )
            except Exception as cleanup_error:
                cleanup_errors.append(f"unexpected cleanup failure: {cleanup_error}")
            slot.setdefault("failures", []).append(
                {
                    "attempt": slot["attempts"],
                    "utc": utc_now(),
                    "run_id": slot.get("run_id"),
                    "command_id": slot.get("command_id"),
                    "run_dir": slot.get("run_dir"),
                    "error": slot["error"],
                    "cleanup_errors": cleanup_errors,
                }
            )
            try:
                self.save()
            except Exception as save_error:
                cleanup_errors.append(f"final failure manifest save: {save_error}")
            raise
        finally:
            if monitor is not None:
                monitor.terminate()
            if logger is not None:
                logger.terminate()

    def run(self) -> int:
        try:
            self.connect()
        except Exception as error:
            self.manifest["status"] = "failed"
            self.manifest["halt_reason"] = f"{error.__class__.__name__}: {error}"
            self.save()
            print(f"experiment halted safely: {error}", file=sys.stderr)
            return 1
        self.manifest["status"] = "running"
        self.manifest["halt_reason"] = None
        self.manifest["started_utc"] = self.manifest.get("started_utc") or utc_now()
        self.save()
        for slot in runnable_slots(self.manifest):
            try:
                self.run_slot(slot)
            except Exception as error:
                self.manifest["status"] = "failed"
                self.manifest["halt_reason"] = str(error)
                self.save()
                print(f"experiment halted safely: {error}", file=sys.stderr)
                return 1
        self.manifest["status"] = "completed"
        self.manifest["completed_utc"] = utc_now()
        self.manifest["halt_reason"] = None
        self.save()
        return 0


def experiment_config(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "mode": args.mode,
        "resources": list(args.resources),
        "cpu_threads": args.cpu_threads,
        "limit_mode": "DURATION",
        "duration_s": args.duration,
        "warmup_count": args.warmup,
        "repeat_per_resource": args.repeat,
        "seed": args.seed,
        "runner_experiment_mode": "BASIC",
        "energy_calculation": False,
        "current_raw_policy": "raw_unscaled_unit_unverified",
    }


def new_manifest(args: argparse.Namespace) -> dict[str, Any]:
    now = utc_now()
    return {
        "schema_version": 1,
        "orchestrator_version": VERSION,
        "experiment_id": str(uuid.uuid4()),
        "created_utc": now,
        "updated_utc": now,
        "status": "planned",
        "config": experiment_config(args),
        "device": None,
        "runs": build_plan(args.resources, args.repeat, args.seed),
        "limitations": {
            "energy_calculated": False,
            "current_raw_unit_verified": False,
            "duty_cycle_implemented": False,
            "accuracy_comparator_implemented": False,
        },
    }


def default_output_dir() -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("results") / f"D1Check_repeat_{stamp}"


def resolve_adb(value: str | None) -> str:
    candidates = [
        value,
        os.environ.get("D1_ADB"),
        str(Path.home() / "AppData/Local/Android/Sdk/platform-tools/adb.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    raise OrchestratorError("adb not found; pass --adb or set D1_ADB")


def dry_run_payload(args: argparse.Namespace) -> dict[str, Any]:
    placeholder_adb = args.adb or "adb"
    serial_prefix = [placeholder_adb, "-s", args.serial or "<selected-serial>"]
    plan = build_plan(args.resources, args.repeat, args.seed)
    commands = []
    for slot in plan:
        commands.append(
            {
                "slot_id": slot["slot_id"],
                "resource": slot["resource"],
                "force_stop": serial_prefix + ["shell", "am", "force-stop", RUNNER_PACKAGE],
                "start_run": serial_prefix + start_run_arguments(),
                "runner": serial_prefix + runner_intent_arguments(
                    slot["resource"], args.cpu_threads, args.duration, args.warmup,
                    "<run-id>", "<command-id>",
                ),
                "stop_run": serial_prefix + stop_run_arguments(),
                "direct_stop_recovery": serial_prefix + direct_stop_arguments(),
            }
        )
    return {
        "dry_run": True,
        "config": experiment_config(args),
        "plan": plan,
        "commands": commands,
        "performs_adb_calls": False,
        "writes_manifest": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb")
    parser.add_argument("--serial")
    parser.add_argument("--mode", choices=("pilot", "formal"), default="pilot")
    parser.add_argument(
        "--resources", nargs="+", choices=("CPU", "GPU"), default=["CPU", "GPU"]
    )
    parser.add_argument("--cpu-threads", type=int, default=4)
    parser.add_argument("--duration", type=int, default=600)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--logger",
        type=Path,
        default=Path(__file__).with_name("d1_logger_v4.py"),
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def validate_cli(args: argparse.Namespace) -> None:
    if not 1 <= args.cpu_threads <= 16:
        raise OrchestratorError("--cpu-threads must be in 1..16")
    if not 1 <= args.duration <= 3600:
        raise OrchestratorError("--duration must be in 1..3600")
    if not 0 <= args.warmup <= 10_000:
        raise OrchestratorError("--warmup must be in 0..10000")
    if args.repeat < 1:
        raise OrchestratorError("--repeat must be at least 1")
    if len(set(args.resources)) != len(args.resources):
        raise OrchestratorError("--resources must not contain duplicates")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    validate_cli(args)
    if args.dry_run:
        print(json.dumps(dry_run_payload(args), ensure_ascii=False, indent=2))
        return 0
    args.adb = resolve_adb(args.adb)
    if not Path(args.logger).is_file():
        raise OrchestratorError(f"d1_logger_v4.py not found: {args.logger}")
    output_dir = (args.output_dir or default_output_dir()).resolve()
    manifest_path = output_dir / MANIFEST_NAME
    if args.resume:
        if not manifest_path.is_file():
            raise OrchestratorError(f"resume manifest not found: {manifest_path}")
        manifest = load_json(manifest_path)
        if manifest.get("config") != experiment_config(args):
            raise OrchestratorError("resume options do not match experiment manifest config")
        previous_version = manifest.get("orchestrator_version")
        if previous_version != VERSION:
            manifest.setdefault("orchestrator_upgrades", []).append(
                {"utc": utc_now(), "from": previous_version, "to": VERSION}
            )
            manifest["orchestrator_version"] = VERSION
            atomic_write_json(manifest_path, manifest)
    else:
        if manifest_path.exists():
            raise OrchestratorError(
                f"manifest already exists; use --resume or a new --output-dir: {manifest_path}"
            )
        manifest = new_manifest(args)
        atomic_write_json(manifest_path, manifest)
    return ExperimentOrchestrator(args, manifest, manifest_path).run()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OrchestratorError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
