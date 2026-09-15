#!/usr/bin/env python3
"""D1Check v4 capture/merge tool. Current values always remain unscaled raw values."""

from __future__ import annotations

import argparse
import bisect
import csv
import datetime as dt
from enum import Enum
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections import defaultdict
from typing import Any, Iterable


VERSION = "4.1"
DEFAULT_INTERVAL_S = 1.0
RUNNER_PACKAGE = "com.example.d1check.benchmarkrunner"
RUNNER_OUTPUT_DIRECTORIES = ("runs", "diagnostics-v2")
TEMP_RE = re.compile(
    r"mValue=(-?[\d.]+),\s*mType=\d+,\s*mName=([^,}]+)", re.IGNORECASE
)
THERMAL_STATUS_RE = re.compile(r"Thermal Status:\s*(-?\d+)")
DELEGATE_REPLACE_RE = re.compile(
    r"Replacing\s+(\d+)\s+out of\s+(\d+)\s+node(?:\(s\)|s)?", re.IGNORECASE
)
GPU_DELEGATE_CREATED_RE = re.compile(
    r"Created\s+TensorFlow\s+Lite\s+delegate\s+for\s+GPU", re.IGNORECASE
)
GPU_DELEGATE_TYPE_RE = re.compile(r"TfLiteGpuDelegateV2", re.IGNORECASE)
GPU_KERNEL_RE = re.compile(r"Created\s+(\d+)\s+GPU\s+delegate\s+kernels?", re.IGNORECASE)
OPENCL_BACKEND_RE = re.compile(
    r"(?:Loaded\s+OpenCL|Initialized\s+OpenCL|OpenCL-based\s+API)", re.IGNORECASE
)
OPENGL_BACKEND_RE = re.compile(
    r"(?:OpenGL(?:\s+ES)?|GL-based\s+API)", re.IGNORECASE
)
DELEGATE_FAILURE_RE = re.compile(
    r"(?:failed\s+to\s+apply|restored\s+original\s+execution\s+plan|unsupported\s+op|"
    r"remaining\s+nodes?\s+run\s+on\s+CPU|fall(?:ing)?\s+back\s+to\s+CPU|CPU\s+fallback)",
    re.IGNORECASE,
)
PERFETTO_BUFFER_KB = 32768
MAX_DIAGNOSTIC_SECONDS = 3600
PERFETTO_DEVICE_CONFIG_ROOT = "/data/misc/perfetto-configs"
PERFETTO_DEVICE_TRACE_ROOT = "/data/misc/perfetto-traces"
LEGACY_PERFETTO_DEVICE_CONFIG_PATH = (
    "/data/misc/perfetto-configs/d1check-gpu-diagnostic.pbtxt"
)
LEGACY_PERFETTO_DEVICE_TRACE_PATH = (
    "/data/misc/perfetto-traces/d1check-diagnostic.perfetto-trace"
)
PERFETTO_PUSH_TIMEOUT_S = 30
PERFETTO_START_TIMEOUT_S = 30
PERFETTO_PROBE_TIMEOUT_S = 5
PERFETTO_STOP_TIMEOUT_S = 10
PERFETTO_PULL_TIMEOUT_S = 120
PERFETTO_CLEANUP_TIMEOUT_S = 20
PERFETTO_SIGNAL_GRACE_ATTEMPTS = 20
PERFETTO_SIGNAL_GRACE_INTERVAL_S = 0.1
DETACHED_SUCCESS_RETURN_CODES = {
    "pre_start_is_detached": 2,
    "config_push": 0,
    "start": 0,
    "ready_is_detached": 0,
    "stop": 0,
    "post_stop_is_detached": 2,
    "cleanup_files": 0,
}
DETACHED_READINESS_SEMANTICS = (
    "detached_session_exists_and_is_reattachable_not_all_data_sources_acknowledged"
)
DETACHED_PID_CONTROL = "not_applicable_detached_session"


def canonical_uuid(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a canonical UUID string")
    try:
        normalized = str(uuid.UUID(value))
    except (ValueError, AttributeError) as error:
        raise ValueError(f"{label} must be a canonical UUID string") from error
    if normalized != value:
        raise ValueError(f"{label} must use canonical UUID format")
    return normalized


def contained_child(directory: Path, filename: str) -> Path:
    root = directory.resolve()
    candidate = (root / filename).resolve()
    if candidate.parent != root:
        raise ValueError(f"path escapes designated directory: {filename!r}")
    return candidate


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class PerfettoState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"


def parse_thermalservice(text: str) -> dict[str, str]:
    """Galaxy A24 parser preserved from d1_logger.py v0.3."""
    section_match = re.search(
        r"Current temperatures from HAL:?\s*(.*?)(?:\n\s*(?:Current cooling devices|"
        r"Temperature static|Temperature headroom|HAL Ready|$))",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    section = section_match.group(1) if section_match else text
    temps: dict[str, str] = {}
    for match in TEMP_RE.finditer(section):
        name = match.group(2).strip().upper()
        temps[name] = match.group(1)
    status = THERMAL_STATUS_RE.search(text)
    return {
        "AP": temps.get("AP", ""),
        "SKIN": temps.get("SKIN", ""),
        "BAT": temps.get("BAT", ""),
        "PA": temps.get("PA") or temps.get("PATHM") or temps.get("PA1THM") or "",
        "thermal_status": status.group(1) if status else "",
    }


def extract_json(line: str) -> dict[str, Any] | None:
    start = line.find("{")
    if start < 0:
        return None
    try:
        value = json.loads(line[start:])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def measurement_provenance(metadata: dict[str, Any]) -> dict[str, Any]:
    accuracy = metadata.get("accuracy_preflight")
    if not isinstance(accuracy, dict):
        accuracy = {
            "status": "not_run",
            "deterministic_input_count": 0,
            "reference_resource": None,
            "comparator_version": None,
            "tolerance": None,
            "mismatch_count": None,
            "note": "accuracy comparator was not run",
        }
    energy = metadata.get("energy_measurement")
    if not isinstance(energy, dict):
        energy = {
            "status": "raw_unverified",
            "current_raw_policy": "raw_unscaled_unit_unverified",
            "voltage_available": None,
            "current_unit_verified": False,
            "charge_counter_unit_verified": False,
            "calculation_performed": False,
            "note": "no calibrated energy result is available",
        }
    return {
        "accuracy_preflight": accuracy,
        "energy_measurement": energy,
    }


GPU_PROFILE_FIELDS = (
    "profile_id",
    "configuration_sha256",
    "precision_loss_allowed",
    "quantized_models_allowed",
    "inference_preference",
    "force_backend",
    "actual_fp16_execution",
)


def _profile_from_accuracy(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    cache = value.get("cache_provenance")
    if isinstance(cache, dict) and isinstance(cache.get("gpu_delegate_profile"), dict):
        return cache["gpu_delegate_profile"]
    direct = value.get("gpu_delegate_profile")
    return direct if isinstance(direct, dict) else None


def experiment_profile_context(run_dir: Path) -> dict[str, Any]:
    """Read optional orchestrator context without making standalone analysis impossible."""
    manifest_path = run_dir.parent.parent / "experiment_manifest.json"
    if not manifest_path.is_file():
        return {"manifest_available": False, "config_profile": None, "preflight_profile": None}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {
            "manifest_available": True,
            "manifest_error": f"{error.__class__.__name__}: {error}",
            "config_profile": None,
            "preflight_profile": None,
        }
    config = manifest.get("config") if isinstance(manifest, dict) else None
    return {
        "manifest_available": True,
        "manifest_error": None,
        "config_profile": (
            config.get("gpu_delegate_profile") if isinstance(config, dict) else None
        ),
        "preflight_profile": _profile_from_accuracy(manifest.get("accuracy_preflight")),
    }


def validate_gpu_execution_profile(
    resource: Any,
    run_profile: Any,
    config_profile: Any = None,
    preflight_profile: Any = None,
    *,
    manifest_available: bool = False,
    manifest_error: str | None = None,
) -> dict[str, Any]:
    """Validate explicit execution-profile provenance; never infer legacy defaults."""
    normalized_resource = str(resource or "").upper()
    if normalized_resource != "GPU":
        unexpected = run_profile is not None
        return {
            "status": "failed" if unexpected else "not_applicable",
            "valid": not unexpected,
            "resource": normalized_resource,
            "failure_reasons": ["cpu_run_has_gpu_delegate_profile"] if unexpected else [],
            "comparisons": {"config": "not_applicable", "accuracy_preflight": "not_applicable"},
        }

    if not isinstance(run_profile, dict):
        return {
            "status": "legacy_missing",
            "valid": False,
            "resource": "GPU",
            "failure_reasons": ["timed_run_gpu_delegate_profile_missing"],
            "comparisons": {
                "config": "unverified",
                "accuracy_preflight": "unverified",
            },
        }

    failures: list[str] = []
    profile = {field: run_profile.get(field) for field in GPU_PROFILE_FIELDS}
    if not isinstance(profile["profile_id"], str) or not profile["profile_id"]:
        failures.append("timed_profile_id_invalid")
    profile_hash = profile["configuration_sha256"]
    if not isinstance(profile_hash, str) or re.fullmatch(r"[0-9a-fA-F]{64}", profile_hash) is None:
        failures.append("timed_profile_hash_invalid")
    for key in ("precision_loss_allowed", "quantized_models_allowed"):
        if not isinstance(profile[key], bool):
            failures.append(f"timed_{key}_invalid")
    for key in ("inference_preference", "force_backend", "actual_fp16_execution"):
        if not isinstance(profile[key], str) or not profile[key]:
            failures.append(f"timed_{key}_invalid")

    comparisons: dict[str, str] = {}
    for source, candidate in (
        ("config", config_profile), ("accuracy_preflight", preflight_profile),
    ):
        if candidate is None:
            comparisons[source] = "unavailable"
            if manifest_available and source == "config":
                failures.append("experiment_config_gpu_delegate_profile_missing")
            continue
        if not isinstance(candidate, dict):
            comparisons[source] = "invalid"
            failures.append(f"{source}_gpu_delegate_profile_invalid")
            continue
        id_match = candidate.get("profile_id") == profile.get("profile_id")
        hash_match = candidate.get("configuration_sha256") == profile.get(
            "configuration_sha256"
        )
        comparisons[source] = "match" if id_match and hash_match else "mismatch"
        if not id_match:
            failures.append(f"{source}_gpu_profile_id_mismatch")
        if not hash_match:
            failures.append(f"{source}_gpu_profile_hash_mismatch")
    if manifest_error:
        failures.append("experiment_manifest_profile_context_invalid")
    failures = list(dict.fromkeys(failures))
    return {
        "status": "pass" if not failures else "failed",
        "valid": not failures,
        "resource": "GPU",
        "profile_id": profile.get("profile_id"),
        "configuration_sha256": profile.get("configuration_sha256"),
        "comparisons": comparisons,
        "failure_reasons": failures,
    }


def runner_session_from_filename(filename: str, run_id: str) -> str | None:
    prefix = f"gpu-events-{run_id}-"
    if not filename.startswith(prefix) or not filename.endswith(".jsonl"):
        return None
    session_id = filename[len(prefix):-len(".jsonl")]
    return session_id if re.fullmatch(r"[A-Za-z0-9-]+", session_id) else None


def delegate_evidence(raw_log: str, diagnostic_v2: bool = False) -> dict[str, Any]:
    matches = list(DELEGATE_REPLACE_RE.finditer(raw_log))
    replacement = matches[-1] if matches else None
    kernel_matches = list(GPU_KERNEL_RE.finditer(raw_log))
    replaced = int(replacement.group(1)) if replacement else None
    total = int(replacement.group(2)) if replacement else None
    kernel_count = int(kernel_matches[-1].group(1)) if kernel_matches else None
    gpu_created = bool(GPU_DELEGATE_CREATED_RE.search(raw_log))
    gpu_type = bool(GPU_DELEGATE_TYPE_RE.search(raw_log))
    failure_matches = sorted({match.group(0) for match in DELEGATE_FAILURE_RE.finditer(raw_log)})
    opencl_observed = bool(OPENCL_BACKEND_RE.search(raw_log))
    opengl_observed = bool(OPENGL_BACKEND_RE.search(raw_log))
    actual_backend_observed = (
        "conflicting_opencl_and_opengl"
        if opencl_observed and opengl_observed
        else "OPENCL" if opencl_observed
        else "OPENGL" if opengl_observed
        else "unknown"
    )
    verified = (
        gpu_created
        and gpu_type
        and replaced is not None
        and total is not None
        and total > 0
        and replaced == total
        and kernel_count is not None
        and kernel_count > 0
        and not failure_matches
    )
    evidence = {
        "replaced_nodes": replaced,
        "total_nodes": total,
        "gpu_delegate_created": gpu_created,
        "gpu_delegate_type": "TfLiteGpuDelegateV2" if gpu_type else None,
        "gpu_delegate_kernel_count": kernel_count,
        "failure_or_fallback_evidence": failure_matches,
        "full_delegate": verified,
        "verification": "verified" if verified else "unverified",
        "note": None if verified else (
            "No conclusive full-delegation evidence; this does not prove CPU fallback."
        ),
    }
    if diagnostic_v2:
        evidence.update({
            "gpu_delegate_kernel_count_semantics": (
                "LiteRT_delegate_reported_logical_kernels_not_physical_GPU_kernel_launches"
                if kernel_count is not None else None
            ),
            "actual_backend_observed": actual_backend_observed,
            "backend_observation": {
                "opencl_log_observed": opencl_observed,
                "opengl_log_observed": opengl_observed,
                "source": "raw_LiteRT_log",
                "inferred_from_force_backend": False,
            },
        })
    return evidence


def resolve_adb(cli_value: str | None) -> str:
    candidates = [
        cli_value,
        os.environ.get("D1_ADB"),
        shutil.which("adb"),
        str(Path.home() / "AppData/Local/Android/Sdk/platform-tools/adb.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate))
    raise FileNotFoundError("adb not found; pass --adb or set D1_ADB")


def adb_base(adb: str, serial: str | None) -> list[str]:
    command = [adb]
    if serial:
        command += ["-s", serial]
    return command


def clear_logcat(adb: str, serial: str | None) -> int:
    return subprocess.run(adb_base(adb, serial) + ["logcat", "-c"]).returncode


def parse_uptime(value: str, source: str = "/proc/uptime") -> int:
    tokens = value.strip().split()
    if len(tokens) < 2:
        raise ValueError(
            f"{source}: expected at least 2 uptime tokens, got {len(tokens)}; "
            f"stdout={value[:160]!r}"
        )
    try:
        uptime_seconds = float(tokens[0])
    except ValueError as error:
        raise ValueError(
            f"{source}: first uptime token is not numeric: {tokens[0]!r}"
        ) from error
    if not math.isfinite(uptime_seconds) or uptime_seconds < 0:
        raise ValueError(f"{source}: invalid uptime seconds: {tokens[0]!r}")
    return int(uptime_seconds * 1_000_000_000)


def current_now_discharge_magnitude_ua(current_raw: float) -> float:
    """Return positive discharge magnitude using Android's negative-discharge convention."""
    if not math.isfinite(current_raw):
        raise ValueError("current_raw must be finite")
    if current_raw > 0:
        raise ValueError("current_raw indicates charging, not discharge")
    return -current_raw


def charge_counter_discharge_magnitude_ua(
    start_uah: float, end_uah: float, elapsed_seconds: float
) -> float:
    """Return positive discharge magnitude derived from a decreasing charge counter."""
    if not all(math.isfinite(value) for value in (start_uah, end_uah, elapsed_seconds)):
        raise ValueError("charge-counter inputs must be finite")
    if elapsed_seconds <= 0:
        raise ValueError("charge-counter elapsed_seconds must be positive")
    discharged_uah = start_uah - end_uah
    if discharged_uah < 0:
        raise ValueError("charge counter increased; interval is not a discharge interval")
    return discharged_uah * 3600.0 / elapsed_seconds


def adb_text(adb_command: list[str], arguments: list[str], source: str) -> str:
    result = subprocess.run(
        adb_command + arguments,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=8,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no diagnostic output"
        raise RuntimeError(f"{source}: adb returncode={result.returncode}; {detail}")
    if not result.stdout.strip():
        raise RuntimeError(f"{source}: adb returned empty stdout")
    return result.stdout


def thermal_dump(adb_command: list[str]) -> tuple[dict[str, Any], str]:
    before_text = adb_text(
        adb_command, ["exec-out", "cat", "/proc/uptime"], "uptime before thermalservice"
    )
    thermal_text = adb_text(
        adb_command, ["shell", "dumpsys", "thermalservice"], "thermalservice"
    )
    after_text = adb_text(
        adb_command, ["exec-out", "cat", "/proc/uptime"], "uptime after thermalservice"
    )
    before_ns = parse_uptime(before_text, "uptime before thermalservice")
    after_ns = parse_uptime(after_text, "uptime after thermalservice")
    values: dict[str, Any] = parse_thermalservice(thermal_text)
    values.update(
        {
            "schema_version": 2,
            "source": "thermalservice",
            "event": "sample",
            "sample_before_mono_ns": before_ns,
            "sample_after_mono_ns": after_ns,
            "mono_ns": (before_ns + after_ns) // 2,
            "sampling_uncertainty_ns": (after_ns - before_ns) // 2,
        }
    )
    missing = [name for name in ("AP", "SKIN", "BAT", "PA") if not values[name]]
    values["parse_status"] = "ok" if not missing else "missing_sensor"
    values["missing_sensors"] = ",".join(missing)
    return values, thermal_text


class CaptureSession:
    def __init__(
        self,
        adb: str,
        serial: str | None,
        output_root: Path,
        interval_s: float,
        diagnostic_perfetto: bool,
        perfetto_config: Path,
        protocol_version: int | None = None,
        diagnostic_session_id: str | None = None,
        perfetto_duration_ms: int | None = None,
    ) -> None:
        self.adb_command = adb_base(adb, serial)
        self.output_root = output_root
        self.interval_s = interval_s
        self.diagnostic_perfetto = diagnostic_perfetto
        self.perfetto_config = perfetto_config
        self.perfetto_duration_ms = perfetto_duration_ms
        self.protocol_version = protocol_version
        self.diagnostic_session_id = diagnostic_session_id
        if protocol_version == 2:
            if diagnostic_session_id is None:
                raise ValueError("protocol v2 capture requires diagnostic_session_id")
            diagnostic_session_id = canonical_uuid(
                diagnostic_session_id, "diagnostic_session_id"
            )
            self.diagnostic_session_id = diagnostic_session_id
            if diagnostic_perfetto and self.perfetto_duration_ms is None:
                self.perfetto_duration_ms = MAX_DIAGNOSTIC_SECONDS * 1000
        elif diagnostic_session_id is not None:
            raise ValueError("diagnostic_session_id is only valid for protocol v2")
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.run_id: str | None = None
        self.run_dir: Path | None = None
        self.pending_thermal: list[dict[str, Any]] = []
        self.logcat_process: subprocess.Popen[str] | None = None
        self.perfetto_pid: str | None = None
        self.perfetto_start_pid: str | None = None
        self.perfetto_session_may_exist = False
        self.perfetto_remote_files_may_exist = False
        self.perfetto_control_results: dict[str, dict[str, Any]] = {}
        self.perfetto_config_write_into_file: bool | None = None
        self.perfetto_config_duration_ms: int | None = None
        self.perfetto_state = PerfettoState.IDLE
        self.perfetto_lock = threading.Lock()
        self.perfetto_cleanup_done = False
        self.perfetto_started_successfully = False
        self.perfetto_process_exited: bool | None = None
        self.pulled_trace_size_bytes: int | None = None
        self.pulled_trace_sha256: str | None = None
        self.capture_error: str | None = None
        self.capture_warnings: list[str] = []
        self.pending_raw_log: list[str] = []
        self.recovered_runner_files: set[str] = set()
        self.runner_output_directories = ("runs",)
        if self.protocol_version == 2:
            self.runner_output_directories = ("diagnostics-v2",)

    @property
    def perfetto_device_config_path(self) -> str:
        if self.protocol_version != 2:
            return LEGACY_PERFETTO_DEVICE_CONFIG_PATH
        if self.diagnostic_session_id is None:
            raise RuntimeError("Perfetto path requires diagnostic session id")
        return (
            f"{PERFETTO_DEVICE_CONFIG_ROOT}/"
            f"d1check-{self.diagnostic_session_id}.pbtxt"
        )

    @property
    def perfetto_device_trace_path(self) -> str:
        if self.protocol_version != 2:
            return LEGACY_PERFETTO_DEVICE_TRACE_PATH
        if self.diagnostic_session_id is None:
            raise RuntimeError("Perfetto path requires diagnostic session id")
        return (
            f"{PERFETTO_DEVICE_TRACE_ROOT}/"
            f"d1check-{self.diagnostic_session_id}.perfetto-trace"
        )

    @property
    def diagnostic_trace_filename(self) -> str | None:
        if not self.diagnostic_perfetto:
            return None
        if self.protocol_version != 2:
            return "d1check.perfetto-trace"
        return Path(self.perfetto_device_trace_path).name

    @property
    def perfetto_session_key(self) -> str | None:
        if self.protocol_version != 2:
            return None
        if self.diagnostic_session_id is None:
            raise RuntimeError("Perfetto detached session requires diagnostic session id")
        return f"d1check-{self.diagnostic_session_id}"

    def perfetto_control_metadata(self) -> dict[str, Any]:
        uses_detached_session = (
            self.protocol_version == 2 and self.diagnostic_perfetto
        )
        return {
            "diagnostic_perfetto_control_mode": (
                "detached_session" if uses_detached_session else None
            ),
            "diagnostic_perfetto_session_key": (
                self.perfetto_session_key if uses_detached_session else None
            ),
            "diagnostic_perfetto_start_pid": self.perfetto_start_pid,
            "diagnostic_perfetto_control_results": dict(self.perfetto_control_results),
            "diagnostic_perfetto_readiness_semantics": (
                DETACHED_READINESS_SEMANTICS if uses_detached_session else None
            ),
            "diagnostic_perfetto_pid_control": (
                DETACHED_PID_CONTROL if uses_detached_session else None
            ),
            "diagnostic_perfetto_config_write_into_file": (
                self.perfetto_config_write_into_file if uses_detached_session else None
            ),
            "diagnostic_perfetto_config_duration_ms": (
                self.perfetto_config_duration_ms if uses_detached_session else None
            ),
        }

    def activate_run(self, run_id: str, run_start_mono_ns: int) -> None:
        run_id = canonical_uuid(run_id, "run_id")
        run_dir = contained_child(self.output_root, run_id)
        with self.lock:
            if self.run_id == run_id:
                return
            self.run_id = run_id
            self.run_dir = run_dir
            for relative in ("raw", "gpu", "merged", "diagnostics"):
                (self.run_dir / relative).mkdir(parents=True, exist_ok=True)
            metadata = {
                "logger_version": VERSION,
                "run_id": run_id,
                "current_scale": "raw",
                "experiment_mode": "diagnostic" if self.diagnostic_perfetto else "basic",
                "capture_started_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "device_model": self._device_property("ro.product.model"),
                "device_fingerprint": self._device_property("ro.build.fingerprint"),
            }
            if self.protocol_version == 2:
                metadata.update({
                    "protocol_version": 2,
                    "diagnostic_session_id": self.diagnostic_session_id,
                    "diagnostic_perfetto_enabled": self.diagnostic_perfetto,
                    "requested_trace_mode": "on" if self.diagnostic_perfetto else "off",
                    "diagnostic_perfetto_started": self.perfetto_started_successfully,
                    "diagnostic_trace_filename": self.diagnostic_trace_filename,
                    "diagnostic_trace_session_id": self.diagnostic_session_id,
                    "diagnostic_trace_size_bytes": None,
                    "diagnostic_trace_sha256": None,
                    "diagnostic_perfetto_process_exited": self.perfetto_process_exited,
                    **self.perfetto_control_metadata(),
                })
            (self.run_dir / "metadata.json").write_text(
                json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
            )
            for line in self.pending_raw_log:
                self._append_raw_log(line)
            self.pending_raw_log.clear()
            for sample in self.pending_thermal:
                if int(sample["mono_ns"]) >= run_start_mono_ns:
                    sample["run_id"] = run_id
                    self._append_json("raw/thermalservice.jsonl", sample)
            self.pending_thermal.clear()

    def _device_property(self, name: str) -> str:
        result = subprocess.run(
            self.adb_command + ["shell", "getprop", name], capture_output=True, text=True
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    def _append_raw_log(self, line: str) -> None:
        if self.run_dir is None:
            self.pending_raw_log.append(line)
            return
        with (self.run_dir / "raw/logcat.txt").open(
            "a", encoding="utf-8", newline="\n"
        ) as stream:
            stream.write(line.rstrip("\r\n") + "\n")

    def _append_json(self, relative: str, event: dict[str, Any]) -> None:
        if self.run_dir is None:
            return
        path = self.run_dir / relative
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")

    def record_logcat(self, event: dict[str, Any]) -> None:
        if event.get("source") == "d1check" and event.get("event") == "run_start":
            try:
                event_run_id = canonical_uuid(event.get("run_id"), "run_id")
            except ValueError as error:
                self.capture_error = str(error)
                self.stop.set()
                return
            if self.run_id is not None and event.get("run_id") != self.run_id:
                with self.lock:
                    self._append_json("raw/logcat.jsonl", event)
                self.capture_error = "new D1Check run appeared before the captured run stopped"
                self.stop.set()
                return
            self.activate_run(event_run_id, int(event["mono_ns"]))
        if (
            self.protocol_version == 2
            and event.get("source") == "gpu"
            and self.run_id is not None
            and event.get("run_id") == self.run_id
        ):
            if (
                event.get("protocol_version") != 2
                or event.get("diagnostic_session_id") != self.diagnostic_session_id
                or event.get("requested_trace_mode")
                != ("on" if self.diagnostic_perfetto else "off")
            ):
                self.capture_error = (
                    "diagnostic protocol/session/trace-mode mismatch in Logcat record"
                )
                self.stop.set()
                return
        with self.lock:
            if self.run_id and event.get("run_id") == self.run_id:
                self._append_json("raw/logcat.jsonl", event)

    def record_thermal(self, event: dict[str, Any], raw: str) -> None:
        with self.lock:
            if self.run_id:
                event["run_id"] = self.run_id
                self._append_json("raw/thermalservice.jsonl", event)
                probe = self.run_dir / "raw/thermalservice-probe.txt"  # type: ignore[operator]
                if not probe.exists():
                    probe.write_text(raw, encoding="utf-8")
            else:
                self.pending_thermal.append(event)

    def _validate_pulled_file(self, destination: Path) -> None:
        if not destination.is_file() or destination.stat().st_size <= 0:
            raise ValueError(f"pulled runner file is empty: {destination}")
        session_id = runner_session_from_filename(destination.name, str(self.run_id))
        if session_id is None:
            raise ValueError(f"invalid runner filename: {destination.name}")
        validate_gpu_file(
            load_jsonl(destination),
            str(self.run_id),
            session_id,
            self.diagnostic_session_id if self.protocol_version == 2 else None,
            "on" if self.diagnostic_perfetto else "off"
            if self.protocol_version == 2 else None,
        )

    def pull_runner_file(self, event: dict[str, Any]) -> None:
        if self.run_dir is None:
            return
        device_path = str(event.get("file_path", ""))
        session_id = str(event.get("runner_session_id", ""))
        if not device_path or not session_id:
            raise ValueError("file_summary lacks file_path or runner_session_id")
        normalized_device_path = device_path.replace("\\", "/")
        if ".." in normalized_device_path.split("/") or not normalized_device_path.startswith("/"):
            raise ValueError(f"unsafe runner file path: {device_path!r}")
        filename = normalized_device_path.rsplit("/", 1)[-1]
        expected_filename = f"gpu-events-{self.run_id}-{session_id}.jsonl"
        if filename != expected_filename:
            raise ValueError("runner filename does not match run/session identity")
        expected_root = (
            "diagnostics-v2" if self.protocol_version == 2 else "runs"
        )
        allowed_paths = {
            f"/storage/emulated/0/Android/data/{RUNNER_PACKAGE}/files/"
            f"{expected_root}/{filename}",
            f"/sdcard/Android/data/{RUNNER_PACKAGE}/files/{expected_root}/{filename}",
        }
        if normalized_device_path not in allowed_paths:
            raise ValueError("runner file is outside the expected output root")
        if filename in self.recovered_runner_files:
            return
        destination = contained_child(self.run_dir / "gpu", filename)
        result = subprocess.run(
            self.adb_command + ["pull", device_path, str(destination)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            self._validate_pulled_file(destination)
            self.recovered_runner_files.add(filename)
            return
        output_directory = next(
            (
                name for name in RUNNER_OUTPUT_DIRECTORIES
                if f"/files/{name}/" in device_path.replace("\\", "/")
            ),
            "runs",
        )
        fallback = subprocess.run(
            self.adb_command
            + [
                "exec-out",
                "run-as",
                RUNNER_PACKAGE,
                "cat",
                f"files/{output_directory}/{filename}",
            ],
            capture_output=True,
        )
        if fallback.returncode != 0:
            raise RuntimeError(
                "runner JSONL pull failed: "
                + (result.stderr.strip() or fallback.stderr.decode(errors="replace").strip())
            )
        destination.write_bytes(fallback.stdout)
        self._validate_pulled_file(destination)
        self.recovered_runner_files.add(filename)

    def discover_runner_paths(self) -> list[str]:
        if not self.run_id or not re.fullmatch(r"[A-Za-z0-9-]+", self.run_id):
            return []
        paths: list[str] = []
        for output_directory in self.runner_output_directories:
            pattern = (
                f"/storage/emulated/0/Android/data/{RUNNER_PACKAGE}/files/"
                f"{output_directory}/gpu-events-{self.run_id}-*.jsonl"
            )
            result = subprocess.run(
                self.adb_command + ["shell", "ls", pattern],
                capture_output=True,
                text=True,
            )
            paths.extend(
                line.strip() for line in result.stdout.splitlines()
                if line.strip().endswith(".jsonl")
            )
            internal = subprocess.run(
                self.adb_command + [
                    "exec-out", "run-as", RUNNER_PACKAGE, "ls",
                    f"files/{output_directory}/gpu-events-{self.run_id}-*.jsonl",
                ],
                capture_output=True,
                text=True,
            )
            for line in internal.stdout.splitlines():
                value = line.strip()
                if value.endswith(".jsonl"):
                    paths.append(
                        value if "/" in value else f"files/{output_directory}/{value}"
                    )
        return sorted(set(paths))

    def recover_runner_files(self) -> None:
        """Fallback used at run_stop, Ctrl-C, EOF, and every capture exit."""
        for device_path in self.discover_runner_paths():
            filename = Path(device_path).name
            session_id = runner_session_from_filename(filename, str(self.run_id))
            if session_id is None:
                continue
            self.pull_runner_file(
                {"file_path": device_path, "runner_session_id": session_id}
            )

    def start_perfetto(self) -> None:
        if not self.diagnostic_perfetto:
            return
        with self.perfetto_lock:
            if self.perfetto_state is not PerfettoState.IDLE:
                return
            try:
                if self.protocol_version == 2:
                    self._start_detached_perfetto()
                else:
                    self._start_signal_perfetto()
                self.perfetto_state = PerfettoState.RUNNING
                self.perfetto_started_successfully = True
            except Exception as error:
                self.perfetto_state = PerfettoState.FAILED
                detail = str(error)
                self.capture_error = (
                    detail if detail.startswith("Perfetto ")
                    else f"Perfetto start failed: {detail}"
                )
                raise RuntimeError(self.capture_error) from error

    @staticmethod
    def _output_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode(errors="replace")
        return str(value)

    def _run_perfetto_command(
        self,
        stage: str,
        arguments: list[str],
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                self.adb_command + arguments,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            stdout = self._output_text(error.stdout).strip()
            stderr = self._output_text(error.stderr).strip()
            self.perfetto_control_results[stage] = {
                "status": "timeout",
                "returncode": None,
                "stdout": stdout,
                "stderr": stderr,
                "timeout_seconds": timeout,
            }
            raise RuntimeError(
                f"Perfetto {stage} timed out after {timeout}s; "
                f"stderr={stderr!r}; stdout={stdout!r}"
            ) from error
        except OSError as error:
            self.perfetto_control_results[stage] = {
                "status": "os_error",
                "returncode": None,
                "stdout": "",
                "stderr": str(error),
                "timeout_seconds": timeout,
            }
            raise RuntimeError(
                f"Perfetto {stage} failed to execute: {error}"
            ) from error
        self.perfetto_control_results[stage] = {
            "status": "completed",
            "returncode": result.returncode,
            "stdout": self._output_text(result.stdout),
            "stderr": self._output_text(result.stderr),
            "timeout_seconds": timeout,
        }
        return result

    def _detached_probe(self, stage: str) -> subprocess.CompletedProcess[str]:
        session_key = self.perfetto_session_key
        if session_key is None:
            raise RuntimeError("Perfetto detached session key is unavailable")
        return self._run_perfetto_command(
            stage,
            ["shell", "perfetto", f"--is_detached={session_key}"],
            PERFETTO_PROBE_TIMEOUT_S,
        )

    @staticmethod
    def _perfetto_pbtxt_field(text: str, name: str) -> str | None:
        uncommented = re.sub(r"(?m)(?://|#).*$", "", text)
        declarations = re.findall(rf"(?m)^\s*{re.escape(name)}\s*:", uncommented)
        if len(declarations) > 1:
            raise RuntimeError(f"Perfetto config has duplicate {name}")
        if not declarations:
            return None
        match = re.search(
            rf"(?m)^\s*{re.escape(name)}\s*:\s*([^\s{{}}]+)\s*$",
            uncommented,
        )
        if match is None:
            raise RuntimeError(f"Perfetto config has invalid {name}")
        return match.group(1)

    @classmethod
    def _validate_detached_perfetto_config_text(cls, text: str) -> int:
        write_value = cls._perfetto_pbtxt_field(text, "write_into_file")
        if write_value is None:
            raise RuntimeError("Perfetto config lacks write_into_file")
        if write_value != "true":
            raise RuntimeError("Perfetto config write_into_file must be true")
        duration_value = cls._perfetto_pbtxt_field(text, "duration_ms")
        if duration_value is None:
            raise RuntimeError("Perfetto config lacks duration_ms")
        if re.fullmatch(r"[0-9]+", duration_value) is None:
            raise RuntimeError("Perfetto config duration_ms must be a positive integer")
        duration_ms = int(duration_value)
        if duration_ms <= 0:
            raise RuntimeError("Perfetto config duration_ms must be positive")
        return duration_ms

    def _prepare_detached_perfetto_config(
        self,
    ) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
        try:
            source = self.perfetto_config.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise RuntimeError(f"Perfetto config cannot be read: {error}") from error
        write_value = self._perfetto_pbtxt_field(source, "write_into_file")
        if write_value is not None and write_value != "true":
            raise RuntimeError("Perfetto config write_into_file must be true")
        duration_value = self._perfetto_pbtxt_field(source, "duration_ms")
        if duration_value is not None:
            if re.fullmatch(r"[0-9]+", duration_value) is None:
                raise RuntimeError("Perfetto config duration_ms must be a positive integer")
            duration_ms = int(duration_value)
            if duration_ms <= 0:
                raise RuntimeError("Perfetto config duration_ms must be positive")
        else:
            duration_ms = self.perfetto_duration_ms
            if (
                isinstance(duration_ms, bool)
                or not isinstance(duration_ms, int)
                or duration_ms <= 0
            ):
                raise RuntimeError(
                    "Perfetto config lacks duration_ms and no positive bounded duration was provided"
                )
        if write_value is not None and duration_value is not None:
            validated_duration_ms = self._validate_detached_perfetto_config_text(source)
            self.perfetto_config_write_into_file = True
            self.perfetto_config_duration_ms = validated_duration_ms
            return self.perfetto_config, None
        additions: list[str] = []
        if write_value is None:
            additions.append("write_into_file: true")
        if duration_value is None:
            additions.append(f"duration_ms: {duration_ms}")
        temporary = tempfile.TemporaryDirectory(prefix="d1check-perfetto-")
        generated = Path(temporary.name) / "gpu_diagnostic.generated.pbtxt"
        generated_text = source.rstrip() + "\n" + "\n".join(additions) + "\n"
        validated_duration_ms = self._validate_detached_perfetto_config_text(
            generated_text
        )
        self.perfetto_config_write_into_file = True
        self.perfetto_config_duration_ms = validated_duration_ms
        generated.write_text(generated_text, encoding="utf-8")
        return generated, temporary

    def _start_detached_perfetto(self) -> None:
        session_key = self.perfetto_session_key
        if session_key is None:
            raise RuntimeError("Perfetto detached session key is unavailable")
        prepared_config, temporary = self._prepare_detached_perfetto_config()
        try:
            preflight = self._detached_probe("pre_start_is_detached")
            if preflight.returncode == 0:
                raise RuntimeError(
                    f"Perfetto stale/replay detached session already exists: {session_key}"
                )
            if preflight.returncode != 2:
                raise RuntimeError(
                    self._perfetto_failure("pre-start detached-session probe", preflight)
                )

            self.perfetto_remote_files_may_exist = True
            push = self._run_perfetto_command(
                "config_push",
                ["push", str(prepared_config), self.perfetto_device_config_path],
                PERFETTO_PUSH_TIMEOUT_S,
            )
            if push.returncode != 0:
                raise RuntimeError(self._perfetto_failure("config push", push))

            self.perfetto_session_may_exist = True
            result = self._run_perfetto_command(
                "start",
                [
                    "shell", "perfetto", "--txt",
                    f"--detach={session_key}",
                    "--config", self.perfetto_device_config_path,
                    "--out", self.perfetto_device_trace_path,
                ],
                PERFETTO_START_TIMEOUT_S,
            )
            if result.returncode != 0:
                raise RuntimeError(self._perfetto_failure("start", result))
            self.perfetto_start_pid = None

            ready = self._detached_probe("ready_is_detached")
            if ready.returncode != 0:
                raise RuntimeError(
                    self._perfetto_failure("ready detached-session probe", ready)
                )
        finally:
            if temporary is not None:
                temporary.cleanup()

    def _start_signal_perfetto(self) -> None:
        push = subprocess.run(
            self.adb_command + [
                "push", str(self.perfetto_config), self.perfetto_device_config_path,
            ],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=PERFETTO_PUSH_TIMEOUT_S,
        )
        if push.returncode != 0:
            raise RuntimeError(self._perfetto_failure("config push", push))
        result = subprocess.run(
            self.adb_command + [
                "shell", "perfetto", "--txt",
                "-c", self.perfetto_device_config_path,
                "-o", self.perfetto_device_trace_path,
                "--background-wait",
            ],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=PERFETTO_START_TIMEOUT_S,
        )
        if result.returncode != 0:
            raise RuntimeError(self._perfetto_failure("start", result))
        pid_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if not pid_lines:
            raise RuntimeError(
                "Perfetto start failed: returncode=0 but stdout contained no "
                f"background PID; stderr={result.stderr.strip()!r}"
            )
        if re.fullmatch(r"[1-9][0-9]*", pid_lines[-1]) is None:
            raise RuntimeError(
                f"Perfetto start failed: invalid background PID {pid_lines[-1]!r}"
            )
        pid = pid_lines[-1]
        self.perfetto_pid = pid
        self.perfetto_start_pid = pid
        alive = subprocess.run(
            self.adb_command + ["shell", "kill", "-0", pid],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=PERFETTO_PROBE_TIMEOUT_S,
        )
        if alive.returncode != 0:
            raise RuntimeError(
                self._perfetto_failure("ready PID liveness probe", alive)
            )

    @staticmethod
    def _perfetto_failure(operation: str, result: subprocess.CompletedProcess[str]) -> str:
        stderr = CaptureSession._output_text(result.stderr).strip()
        stdout = CaptureSession._output_text(result.stdout).strip()
        return (
            f"Perfetto {operation} failed: returncode={result.returncode}; "
            f"stderr={stderr!r}; stdout={stdout!r}"
        )

    def _record_capture_error(self, detail: str, *, cleanup: bool = False) -> None:
        if self.capture_error is None:
            self.capture_error = detail
        else:
            prefix = "suppressed cleanup error" if cleanup else "suppressed error"
            self.capture_warnings.append(f"{prefix}: {detail}")

    def _wait_for_perfetto_exit(self, pid: str) -> bool:
        for attempt in range(PERFETTO_SIGNAL_GRACE_ATTEMPTS):
            try:
                probe = subprocess.run(
                    self.adb_command + ["shell", "kill", "-0", pid],
                    capture_output=True,
                    text=True,
                    errors="replace",
                    timeout=PERFETTO_PROBE_TIMEOUT_S,
                )
            except subprocess.TimeoutExpired as error:
                self.capture_warnings.append(
                    f"Perfetto PID probe timed out after {error.timeout}s"
                )
            else:
                if probe.returncode != 0:
                    self.perfetto_process_exited = True
                    self.perfetto_pid = None
                    return True
            if attempt + 1 < PERFETTO_SIGNAL_GRACE_ATTEMPTS:
                time.sleep(PERFETTO_SIGNAL_GRACE_INTERVAL_S)
        self.perfetto_process_exited = False
        return False

    def _terminate_perfetto_process(self, pid: str) -> str:
        signal_failures: list[str] = []
        for signal in ("INT", "TERM", "KILL"):
            try:
                result = subprocess.run(
                    self.adb_command + ["shell", "kill", f"-{signal}", pid],
                    capture_output=True,
                    text=True,
                    errors="replace",
                    timeout=PERFETTO_STOP_TIMEOUT_S,
                )
            except subprocess.TimeoutExpired as error:
                signal_failures.append(
                    f"SIG{signal} timed out after {error.timeout}s"
                )
            else:
                if result.returncode != 0:
                    signal_failures.append(self._perfetto_failure(f"SIG{signal}", result))
            if self._wait_for_perfetto_exit(pid):
                self.capture_warnings.extend(
                    f"suppressed termination error: {detail}" for detail in signal_failures
                )
                return signal
        detail = (
            "Perfetto cleanup failure: process remains alive after SIGINT/SIGTERM/SIGKILL"
        )
        if signal_failures:
            detail += "; " + "; ".join(signal_failures)
        raise RuntimeError(detail)

    def cleanup_perfetto(self) -> None:
        with self.perfetto_lock:
            if not self.diagnostic_perfetto:
                return
            if self.protocol_version == 2:
                self._cleanup_detached_perfetto()
                return
            pid = self.perfetto_pid
        if pid is not None:
            try:
                outcome = self._terminate_perfetto_process(pid)
                if outcome != "INT":
                    self._record_capture_error(
                        f"Perfetto required SIG{outcome}; forced trace is not finalized",
                        cleanup=True,
                    )
            except Exception as error:
                self._record_capture_error(str(error), cleanup=True)
                return
        with self.perfetto_lock:
            if self.perfetto_cleanup_done:
                return
            self.perfetto_cleanup_done = True
        try:
            result = subprocess.run(
                self.adb_command + [
                    "shell", "rm", "-f",
                    self.perfetto_device_config_path,
                    self.perfetto_device_trace_path,
                ],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=PERFETTO_CLEANUP_TIMEOUT_S,
            )
            if result.returncode != 0:
                self.capture_warnings.append(self._perfetto_failure("cleanup", result))
        except subprocess.TimeoutExpired:
            self.capture_warnings.append(
                f"Perfetto cleanup timed out after {PERFETTO_CLEANUP_TIMEOUT_S}s"
            )

    def _cleanup_detached_perfetto(self) -> None:
        if self.perfetto_cleanup_done:
            return
        self.perfetto_cleanup_done = True
        if self.perfetto_session_may_exist:
            session_key = self.perfetto_session_key
            assert session_key is not None
            try:
                before_stop = self._detached_probe("cleanup_is_detached_before_stop")
            except Exception as error:
                self._record_capture_error(str(error), cleanup=True)
                return
            if before_stop.returncode == 2:
                self.perfetto_session_may_exist = False
                self.perfetto_process_exited = True
            elif before_stop.returncode != 0:
                self._record_capture_error(
                    self._perfetto_failure(
                        "detached cleanup pre-stop probe", before_stop
                    ),
                    cleanup=True,
                )
                return
            else:
                try:
                    stopped = self._run_perfetto_command(
                        "cleanup_stop",
                        ["shell", "perfetto", f"--attach={session_key}", "--stop"],
                        PERFETTO_STOP_TIMEOUT_S,
                    )
                    if stopped.returncode != 0:
                        self._record_capture_error(
                            self._perfetto_failure("detached cleanup stop", stopped),
                            cleanup=True,
                        )
                except Exception as error:
                    self._record_capture_error(str(error), cleanup=True)
                try:
                    detached = self._detached_probe("cleanup_is_detached")
                except Exception as error:
                    self._record_capture_error(str(error), cleanup=True)
                    return
                if detached.returncode == 0:
                    self.perfetto_process_exited = False
                    self._record_capture_error(
                        "Perfetto cleanup failure: detached session remains active",
                        cleanup=True,
                    )
                    return
                if detached.returncode != 2:
                    self._record_capture_error(
                        self._perfetto_failure("detached cleanup final probe", detached),
                        cleanup=True,
                    )
                    return
                self.perfetto_session_may_exist = False
                self.perfetto_process_exited = True
        if not self.perfetto_remote_files_may_exist:
            return
        try:
            result = self._run_perfetto_command(
                "cleanup_files",
                [
                    "shell", "rm", "-f",
                    self.perfetto_device_config_path,
                    self.perfetto_device_trace_path,
                ],
                PERFETTO_CLEANUP_TIMEOUT_S,
            )
            if result.returncode != 0:
                self._record_capture_error(
                    self._perfetto_failure("cleanup", result), cleanup=True
                )
        except Exception as error:
            self._record_capture_error(str(error), cleanup=True)

    def _pull_perfetto_trace(self) -> None:
        if self.run_dir is None:
            raise RuntimeError("Perfetto pull failed: capture run directory is unavailable")
        trace_filename = self.diagnostic_trace_filename
        if trace_filename is None:
            raise RuntimeError("Perfetto pull failed: trace filename is unavailable")
        expected_trace_filename = (
            f"d1check-{self.diagnostic_session_id}.perfetto-trace"
            if self.protocol_version == 2 else "d1check.perfetto-trace"
        )
        if trace_filename != expected_trace_filename:
            raise RuntimeError("Perfetto trace filename/session mismatch")
        destination = contained_child(self.run_dir / "diagnostics", trace_filename)
        temporary = destination.with_name(destination.name + ".part")
        temporary.unlink(missing_ok=True)
        try:
            pulled = subprocess.run(
                self.adb_command + [
                    "pull", self.perfetto_device_trace_path, str(temporary),
                ],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=PERFETTO_PULL_TIMEOUT_S,
            )
            if pulled.returncode != 0:
                raise RuntimeError(self._perfetto_failure("pull", pulled))
            if not temporary.is_file():
                raise RuntimeError("Perfetto pull failed: local temporary trace was not created")
            if temporary.stat().st_size <= 0:
                raise RuntimeError("Perfetto pull failed: local temporary trace is empty")
            pulled_size = temporary.stat().st_size
            pulled_sha256 = sha256_file(temporary)
            if destination.exists():
                raise RuntimeError(
                    f"Perfetto pull refused to overwrite existing trace: {destination}"
                )
            os.replace(temporary, destination)
            if (
                destination.stat().st_size != pulled_size
                or sha256_file(destination) != pulled_sha256
            ):
                raise RuntimeError("Perfetto pull failed: finalized trace integrity mismatch")
            self.pulled_trace_size_bytes = pulled_size
            self.pulled_trace_sha256 = pulled_sha256
        finally:
            temporary.unlink(missing_ok=True)

    def stop_perfetto(self) -> None:
        if not self.diagnostic_perfetto:
            return
        with self.perfetto_lock:
            if self.perfetto_state in {
                PerfettoState.IDLE, PerfettoState.STOPPING, PerfettoState.COMPLETED,
            }:
                return
            use_detached_session = self.protocol_version == 2
            if use_detached_session:
                cleanup_failed_session = self.perfetto_state is PerfettoState.FAILED
                if not cleanup_failed_session:
                    self.perfetto_state = PerfettoState.STOPPING
            if self.perfetto_pid is None:
                pid = None
            else:
                self.perfetto_state = PerfettoState.STOPPING
                pid = self.perfetto_pid
        if use_detached_session:
            if cleanup_failed_session:
                self.cleanup_perfetto()
            else:
                self._stop_detached_perfetto()
            return
        if pid is None:
            return
        try:
            assert pid is not None
            termination = self._terminate_perfetto_process(pid)
            if termination != "INT":
                raise RuntimeError(
                    f"Perfetto required SIG{termination}; forced trace is not finalized"
                )
            self._pull_perfetto_trace()
            with self.perfetto_lock:
                self.perfetto_state = PerfettoState.COMPLETED
            self.cleanup_perfetto()
        except Exception as error:
            with self.perfetto_lock:
                self.perfetto_state = PerfettoState.FAILED
            detail = str(error)
            self._record_capture_error(
                f"{detail}; remote_trace={self.perfetto_device_trace_path}; "
                "remote trace retained for manual recovery",
                cleanup=True,
            )

    def _stop_detached_perfetto(self) -> None:
        session_key = self.perfetto_session_key
        assert session_key is not None
        try:
            stopped = self._run_perfetto_command(
                "stop",
                ["shell", "perfetto", f"--attach={session_key}", "--stop"],
                PERFETTO_STOP_TIMEOUT_S,
            )
            if stopped.returncode != 0:
                raise RuntimeError(self._perfetto_failure("detached stop", stopped))
            detached = self._detached_probe("post_stop_is_detached")
            if detached.returncode == 0:
                raise RuntimeError(
                    "Perfetto detached stop failed: session remains active"
                )
            if detached.returncode != 2:
                raise RuntimeError(
                    self._perfetto_failure("detached post-stop probe", detached)
                )
            self.perfetto_session_may_exist = False
            self.perfetto_process_exited = True
            self._pull_perfetto_trace()
            self.perfetto_state = PerfettoState.COMPLETED
            self.cleanup_perfetto()
        except Exception as error:
            self.perfetto_state = PerfettoState.FAILED
            self._record_capture_error(
                f"{error}; remote_trace={self.perfetto_device_trace_path}; "
                "trace was not finalized",
                cleanup=True,
            )
            self.cleanup_perfetto()

    def thermal_loop(self) -> None:
        while not self.stop.is_set():
            started = time.monotonic()
            try:
                event, raw = thermal_dump(self.adb_command)
                self.record_thermal(event, raw)
            except Exception as error:
                with self.lock:
                    if self.run_id:
                        self._append_json(
                            "raw/thermalservice.jsonl",
                            {
                                "schema_version": 2,
                                "source": "thermalservice",
                                "event": "sample_error",
                                "run_id": self.run_id,
                                "error": str(error),
                            },
                        )
            self.stop.wait(max(0.0, self.interval_s - (time.monotonic() - started)))

    def handle_logcat_line(self, line: str) -> None:
        with self.lock:
            self._append_raw_log(line)
        event = extract_json(line)
        if event is None:
            return
        if (
            event.get("source") == "gpu"
            and event.get("run_id") == self.run_id
            and event.get("protocol_version") == 2
        ):
            self.runner_output_directories = ("diagnostics-v2",)
        self.record_logcat(event)
        if self.stop.is_set() and self.capture_error:
            return
        if event.get("source") == "gpu" and event.get("run_id") == self.run_id:
            is_live_control_marker = "sequence" not in event
            if event.get("event") == "diagnostic_trace_start" and is_live_control_marker:
                if not self.diagnostic_perfetto:
                    self.capture_error = self.capture_error or (
                        "trace marker received while Perfetto is off"
                    )
                    self.stop.set()
                elif self.protocol_version != 2:
                    try:
                        self.start_perfetto()
                    except RuntimeError:
                        self.stop.set()
                elif self.perfetto_state is not PerfettoState.RUNNING:
                    self.capture_error = self.capture_error or (
                        "load marker arrived before Perfetto readiness"
                    )
                    self.stop.set()
            if (
                event.get("event") == "diagnostic_trace_stop"
                and is_live_control_marker
            ):
                self.stop_perfetto()
            if event.get("event") == "file_summary":
                try:
                    self.pull_runner_file(event)
                    print("runner JSONL recovered", file=sys.stderr)
                except Exception as error:
                    self.capture_warnings.append(str(error))
                    print(f"warning: {error}", file=sys.stderr)
        if event.get("source") == "d1check" and event.get("event") == "run_stop":
            try:
                self.recover_runner_files()
            except Exception as error:
                self.capture_warnings.append(str(error))
            self.stop.set()

    def consume_logcat(self, lines: Iterable[str]) -> None:
        for line in lines:
            if self.stop.is_set():
                break
            self.handle_logcat_line(line)
        if not self.stop.is_set():
            return_code = self.logcat_process.poll() if self.logcat_process else None
            self.capture_error = f"logcat stdout EOF (returncode={return_code})"
            self.stop.set()

    def logcat_loop(self) -> None:
        self.logcat_process = subprocess.Popen(
            self.adb_command
            + [
                "logcat", "-v", "threadtime", "D1CHECK_EVENT:I", "D1GPU:I",
                "tflite:I", "TfLite:I", "*:S",
            ],
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert self.logcat_process.stdout is not None
        self.consume_logcat(self.logcat_process.stdout)

    def run(self) -> int:
        self.output_root.mkdir(parents=True, exist_ok=True)
        if self.diagnostic_perfetto and self.protocol_version == 2:
            try:
                self.start_perfetto()
            except Exception as error:
                primary_error = self.capture_error or f"Perfetto start failed: {error}"
                self.capture_error = primary_error
                print(f"error: {primary_error}", file=sys.stderr, flush=True)
                warning_count = len(self.capture_warnings)
                try:
                    self.cleanup_perfetto()
                except Exception as cleanup_error:
                    self._record_capture_error(str(cleanup_error), cleanup=True)
                for warning in self.capture_warnings[warning_count:]:
                    detail = warning
                    if not detail.startswith("suppressed cleanup error:"):
                        detail = f"suppressed cleanup error: {detail}"
                    print(f"warning: {detail}", file=sys.stderr, flush=True)
                return 1
        threads = [
            threading.Thread(target=self.thermal_loop, name="thermal", daemon=True),
            threading.Thread(target=self.logcat_loop, name="logcat", daemon=True),
        ]
        for thread in threads:
            thread.start()
        readiness = (
            f"; diagnostic_session_id={self.diagnostic_session_id}"
            f"; perfetto_ready={'true' if self.perfetto_state is PerfettoState.RUNNING else 'false'}"
            if self.protocol_version == 2 else ""
        )
        print(
            f"capture started{readiness}; now start a new D1Check run",
            file=sys.stderr,
        )
        try:
            while not self.stop.wait(0.25):
                pass
        except KeyboardInterrupt:
            self.stop.set()
        finally:
            if self.logcat_process and self.logcat_process.poll() is None:
                self.logcat_process.terminate()
            for thread in threads:
                thread.join(timeout=3)
            try:
                self.recover_runner_files()
            except Exception as error:
                self.capture_warnings.append(str(error))
            finally:
                # Cleanup is independent of run-directory creation; v2 uses the detached key.
                self.stop_perfetto()
            if self.run_dir is not None:
                metadata_path = self.run_dir / "metadata.json"
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                metadata["capture_warnings"] = self.capture_warnings
                if self.protocol_version == 2:
                    trace_path = (
                        self.run_dir / "diagnostics" / self.diagnostic_trace_filename
                        if self.diagnostic_trace_filename is not None else None
                    )
                    trace_size = (
                        trace_path.stat().st_size
                        if trace_path is not None and trace_path.is_file() else None
                    )
                    trace_sha256 = (
                        sha256_file(trace_path)
                        if trace_size is not None and trace_size > 0 else None
                    )
                    if self.diagnostic_perfetto and (
                        trace_size != self.pulled_trace_size_bytes
                        or trace_sha256 != self.pulled_trace_sha256
                    ):
                        self.capture_error = self.capture_error or (
                            "Perfetto trace was not finalized from this capture"
                        )
                    metadata.update({
                        "protocol_version": 2,
                        "diagnostic_session_id": self.diagnostic_session_id,
                        "diagnostic_perfetto_enabled": self.diagnostic_perfetto,
                        "requested_trace_mode": "on" if self.diagnostic_perfetto else "off",
                        "diagnostic_perfetto_started": self.perfetto_started_successfully,
                        "diagnostic_trace_filename": self.diagnostic_trace_filename,
                        "diagnostic_trace_session_id": self.diagnostic_session_id,
                        "diagnostic_trace_size_bytes": trace_size,
                        "diagnostic_trace_sha256": trace_sha256,
                        "diagnostic_perfetto_process_exited": self.perfetto_process_exited,
                        "perfetto_state": self.perfetto_state.value,
                        **self.perfetto_control_metadata(),
                    })
                metadata["capture_error"] = self.capture_error
                metadata["capture_warnings"] = self.capture_warnings
                metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        return 1 if self.capture_error else 0


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not path.exists():
        return events
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            event = extract_json(line)
            if event is None:
                raise ValueError(f"invalid JSON event at {path}:{line_number}")
            events.append(event)
    return events


def validate_gpu_file(
    events: list[dict[str, Any]],
    run_id: str,
    runner_session_id: str | None = None,
    diagnostic_session_id: str | None = None,
    requested_trace_mode: str | None = None,
) -> None:
    if not events:
        raise ValueError("authoritative runner JSONL is missing or empty")
    sequences = [int(event["sequence"]) for event in events]
    if sequences != list(range(len(events))):
        raise ValueError("runner sequence is not continuous from zero")
    if any(event.get("run_id") != run_id for event in events):
        raise ValueError("runner JSONL contains a different run_id")
    session_ids = {event.get("runner_session_id") for event in events}
    if None in session_ids or len(session_ids) != 1:
        raise ValueError("runner_session_id is missing or inconsistent")
    if runner_session_id is not None and session_ids != {runner_session_id}:
        raise ValueError("runner_session_id does not match filename")
    protocol_versions = {event.get("protocol_version") for event in events}
    diagnostic_ids = {event.get("diagnostic_session_id") for event in events}
    trace_modes = {event.get("requested_trace_mode") for event in events}
    is_v2 = (
        protocol_versions != {None}
        or diagnostic_ids != {None}
        or trace_modes != {None}
    )
    if is_v2:
        if protocol_versions != {2}:
            raise ValueError("protocol_version is missing or inconsistent in v2 JSONL")
        if None in diagnostic_ids or len(diagnostic_ids) != 1:
            raise ValueError("diagnostic_session_id is missing or inconsistent in v2 JSONL")
        only_diagnostic_id = next(iter(diagnostic_ids))
        try:
            normalized_diagnostic_id = str(uuid.UUID(str(only_diagnostic_id)))
        except ValueError as error:
            raise ValueError("diagnostic_session_id is not a UUID") from error
        if normalized_diagnostic_id != only_diagnostic_id:
            raise ValueError("diagnostic_session_id is not canonical")
        if diagnostic_session_id is not None and diagnostic_ids != {diagnostic_session_id}:
            raise ValueError("diagnostic_session_id does not match capture session")
        if trace_modes not in ({"off"}, {"on"}):
            raise ValueError("requested_trace_mode is missing or inconsistent in v2 JSONL")
        if requested_trace_mode is not None and trace_modes != {requested_trace_mode}:
            raise ValueError("requested_trace_mode does not match capture session")
    elif diagnostic_session_id is not None:
        raise ValueError("protocol v2 capture received a v1 runner artifact")
    summary = events[-1]
    if summary.get("event") != "file_summary":
        raise ValueError("runner JSONL has no file_summary footer")
    if int(summary.get("file_event_count", -1)) != len(events):
        raise ValueError("runner file_event_count mismatch")
    if int(summary.get("sequence_last", -1)) != sequences[-1]:
        raise ValueError("runner sequence_last mismatch")


def validate_diagnostic_trace_artifacts(
    run_dir: Path,
    capture_metadata: dict[str, Any],
    diagnostic_session_id: str,
) -> None:
    if capture_metadata.get("diagnostic_trace_session_id") != diagnostic_session_id:
        raise ValueError("Perfetto trace diagnostic session mismatch")
    expected_trace_name = f"d1check-{diagnostic_session_id}.perfetto-trace"
    metadata_trace_name = capture_metadata.get("diagnostic_trace_filename")
    trace_paths = sorted((run_dir / "diagnostics").glob("*.perfetto-trace"))
    requested_trace_mode = capture_metadata.get("requested_trace_mode")
    if requested_trace_mode == "off":
        if any((
            capture_metadata.get("diagnostic_perfetto_control_mode") is not None,
            capture_metadata.get("diagnostic_perfetto_session_key") is not None,
            capture_metadata.get("diagnostic_perfetto_start_pid") is not None,
            capture_metadata.get("diagnostic_perfetto_control_results") != {},
            capture_metadata.get("diagnostic_perfetto_readiness_semantics") is not None,
            capture_metadata.get("diagnostic_perfetto_pid_control") is not None,
            capture_metadata.get("diagnostic_perfetto_config_write_into_file") is not None,
            capture_metadata.get("diagnostic_perfetto_config_duration_ms") is not None,
        )):
            raise ValueError("trace-off metadata must not contain Perfetto control evidence")
        if metadata_trace_name is not None:
            raise ValueError("trace-off metadata must not name a trace artifact")
        if trace_paths:
            raise ValueError("trace-off analysis refuses a Perfetto trace artifact")
        return
    if requested_trace_mode != "on":
        raise ValueError("invalid requested_trace_mode in logger metadata")
    expected_session_key = f"d1check-{diagnostic_session_id}"
    if capture_metadata.get("diagnostic_perfetto_control_mode") != "detached_session":
        raise ValueError("trace-on metadata lacks detached-session control mode")
    if capture_metadata.get("diagnostic_perfetto_session_key") != expected_session_key:
        raise ValueError("Perfetto detached session key does not match diagnostic session")
    start_pid = capture_metadata.get("diagnostic_perfetto_start_pid")
    if start_pid is not None:
        raise ValueError("Perfetto PID must be null for detached-session control")
    if capture_metadata.get(
        "diagnostic_perfetto_readiness_semantics"
    ) != DETACHED_READINESS_SEMANTICS:
        raise ValueError("Perfetto detached readiness semantics are missing")
    if capture_metadata.get("diagnostic_perfetto_pid_control") != DETACHED_PID_CONTROL:
        raise ValueError("Perfetto detached PID control must be not_applicable")
    if capture_metadata.get("diagnostic_perfetto_config_write_into_file") is not True:
        raise ValueError("Perfetto config write_into_file evidence is invalid")
    config_duration_ms = capture_metadata.get("diagnostic_perfetto_config_duration_ms")
    if (
        isinstance(config_duration_ms, bool)
        or not isinstance(config_duration_ms, int)
        or config_duration_ms <= 0
    ):
        raise ValueError("Perfetto config duration_ms evidence is invalid")
    control_results = capture_metadata.get("diagnostic_perfetto_control_results")
    if not isinstance(control_results, dict) or set(control_results) != set(
        DETACHED_SUCCESS_RETURN_CODES
    ):
        raise ValueError("Perfetto detached-session control evidence is incomplete")
    for stage, expected_returncode in DETACHED_SUCCESS_RETURN_CODES.items():
        result = control_results.get(stage)
        if not isinstance(result, dict) or (
            result.get("status") != "completed"
            or result.get("returncode") != expected_returncode
        ):
            raise ValueError(f"Perfetto detached-session stage failed validation: {stage}")
    if metadata_trace_name != expected_trace_name:
        raise ValueError("trace filename does not match diagnostic session")
    if len(trace_paths) != 1 or trace_paths[0].name != expected_trace_name:
        raise ValueError("trace-on analysis found mixed or missing trace artifacts")
    actual_size = trace_paths[0].stat().st_size
    actual_sha256 = sha256_file(trace_paths[0])
    if actual_size != capture_metadata.get("diagnostic_trace_size_bytes") or (
        actual_sha256 != capture_metadata.get("diagnostic_trace_sha256")
    ):
        raise ValueError("Perfetto trace size or SHA-256 mismatch")


def validate_run_envelope(
    d1_events: list[dict[str, Any]], gpu_events: list[dict[str, Any]], run_id: str
) -> tuple[int, int, int, int]:
    foreign_starts = [
        event for event in d1_events
        if event.get("event") == "run_start" and event.get("run_id") != run_id
    ]
    if foreign_starts:
        raise ValueError("a new D1Check run appeared during capture")
    starts = [event for event in d1_events if event.get("event") == "run_start"]
    stops = [event for event in d1_events if event.get("event") == "run_stop"]
    if len(starts) != 1 or len(stops) != 1:
        raise ValueError("analysis requires exactly one D1Check run_start and run_stop")
    load_starts = [event for event in gpu_events if event.get("event") == "load_start"]
    load_ends = [event for event in gpu_events if event.get("event") == "load_end"]
    if len(load_starts) != 1 or len(load_ends) != 1:
        raise ValueError("analysis requires exactly one GPU load_start and load_end")
    run_start_ns = int(starts[0]["mono_ns"])
    run_stop_ns = int(stops[0]["mono_ns"])
    load_start_ns = int(load_starts[0]["mono_ns"])
    load_end_ns = int(load_ends[0]["mono_ns"])
    if not run_start_ns <= load_start_ns <= load_end_ns <= run_stop_ns:
        raise ValueError("GPU load is not fully enclosed by D1Check run_start/run_stop")
    return run_start_ns, run_stop_ns, load_start_ns, load_end_ns


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def latency_stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "mean_ms": None, "median_ms": None, "p95_ms": None}
    return {
        "count": len(values),
        "mean_ms": statistics.fmean(values),
        "median_ms": statistics.median(values),
        "p95_ms": percentile(values, 0.95),
        "min_ms": min(values),
        "max_ms": max(values),
    }


def thermal_coverage(
    events: list[dict[str, Any]], load_start_ns: int, load_end_ns: int
) -> dict[str, Any]:
    samples = [event for event in events if event.get("event") == "sample"]
    valid_samples = [event for event in samples if event.get("parse_status") == "ok"]
    errors = [event for event in events if event.get("event") == "sample_error"]
    attempt_count = len(samples) + len(errors)
    valid_ratio = len(valid_samples) / attempt_count if attempt_count else None
    load_valid_samples = [
        event for event in valid_samples
        if load_start_ns <= int(event["mono_ns"]) <= load_end_ns
    ]
    passes = (
        valid_ratio is not None
        and valid_ratio >= 0.95
        and bool(load_valid_samples)
    )
    return {
        "attempt_count": attempt_count,
        "valid_sample_count": len(valid_samples),
        "error_count": len(errors),
        "invalid_sample_count": len(samples) - len(valid_samples),
        "valid_ratio": valid_ratio,
        "load_valid_sample_count": len(load_valid_samples),
        "passes_formal_requirement": passes,
    }


def nearest_sample(
    samples: list[dict[str, Any]], times: list[int], mono_ns: int
) -> dict[str, Any] | None:
    if not samples:
        return None
    position = bisect.bisect_left(times, mono_ns)
    choices = [index for index in (position - 1, position) if 0 <= index < len(samples)]
    return samples[min(choices, key=lambda index: abs(times[index] - mono_ns))]


def write_jsonl(path: Path, events: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for event in events:
            stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


def analyze(run_dir: Path) -> None:
    run_id = run_dir.name
    logcat = load_jsonl(run_dir / "raw/logcat.jsonl")
    thermal = load_jsonl(run_dir / "raw/thermalservice.jsonl")
    gpu_paths = sorted((run_dir / "gpu").glob(f"gpu-events-{run_id}-*.jsonl"))
    if not gpu_paths:
        raise ValueError("no runner session file found")
    sessions: list[tuple[Path, list[dict[str, Any]]]] = []
    for gpu_path in gpu_paths:
        session_id = runner_session_from_filename(gpu_path.name, run_id)
        if session_id is None:
            continue
        session_events = load_jsonl(gpu_path)
        validate_gpu_file(session_events, run_id, session_id)
        sessions.append((gpu_path, session_events))
    if not sessions:
        raise ValueError("no valid runner session file found")
    modes = {str(events[0].get("experiment_mode", "basic")).lower() for _, events in sessions}
    contains_v2 = any(events[0].get("protocol_version") == 2 for _, events in sessions)
    if contains_v2 and len(sessions) != 1:
        raise ValueError("diagnostic v2 analysis refuses mixed or replayed runner artifacts")
    if len(sessions) > 1 and "basic" in modes:
        raise ValueError("formal experiment has multiple runner sessions for one D1Check run")
    analysis_warnings: list[str] = []
    if len(sessions) > 1:
        analysis_warnings.append("multiple diagnostic runner sessions; newest file analyzed")
    gpu_path, gpu = max(sessions, key=lambda item: item[0].stat().st_mtime_ns)

    d1 = [event for event in logcat if event.get("source") == "d1check"]
    run_start_ns, run_stop_ns, load_start_ns, load_end_ns = validate_run_envelope(d1, gpu, run_id)
    samples = [event for event in d1 if event.get("event") == "sample"]
    coverage = thermal_coverage(thermal, load_start_ns, load_end_ns)
    thermal_samples = [
        event for event in thermal
        if event.get("event") == "sample" and event.get("parse_status") == "ok"
    ]
    d1_times = [int(event["mono_ns"]) for event in samples]
    thermal_times = [int(event["mono_ns"]) for event in thermal_samples]
    inference = [event for event in gpu if event.get("event") == "inference"]
    load_start = next(event for event in gpu if event.get("event") == "load_start")
    load_end = next(event for event in reversed(gpu) if event.get("event") == "load_end")
    events = sorted(d1 + thermal + gpu, key=lambda event: int(event.get("mono_ns", -1)))
    for event in events:
        mono_ns = int(event.get("mono_ns", -1))
        event["analysis_phase"] = (
            "BASELINE" if mono_ns < load_start_ns
            else "LOAD" if mono_ns <= load_end_ns
            else "COOLDOWN"
        )
    merged_dir = run_dir / "merged"
    merged_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(merged_dir / "events.jsonl", events)

    fields = [
        "run_id", "sequence", "inference_index", "start_mono_ns", "end_mono_ns",
        "load_elapsed_s", "latency_ms", "d1_sample_delta_ms", "thermal_sample_delta_ms",
        "headroom_now", "headroom_60s", "thermal_status", "current_raw", "current_valid",
        "voltage_mV", "battery_temp_C", "charge_counter_raw", "plugged",
        "AP", "SKIN", "BAT", "PA", "thermalservice_status",
    ]
    with (merged_dir / "latency_timeline.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for event in inference:
            end_ns = int(event["mono_ns"])
            d1_sample = nearest_sample(samples, d1_times, end_ns)
            thermal_sample = nearest_sample(thermal_samples, thermal_times, end_ns)
            row: dict[str, Any] = {
                "run_id": run_id,
                "sequence": event["sequence"],
                "inference_index": event["inference_index"],
                "start_mono_ns": event["start_mono_ns"],
                "end_mono_ns": end_ns,
                "load_elapsed_s": (end_ns - int(load_start["mono_ns"])) / 1e9,
                "latency_ms": event["latency_ms"],
            }
            if d1_sample:
                row["d1_sample_delta_ms"] = (end_ns - int(d1_sample["mono_ns"])) / 1e6
                for key in (
                    "headroom_now", "headroom_60s", "thermal_status", "current_raw",
                    "current_valid", "voltage_mV", "battery_temp_C",
                    "charge_counter_raw", "plugged",
                ):
                    row[key] = d1_sample.get(key)
            if thermal_sample:
                row["thermal_sample_delta_ms"] = (
                    end_ns - int(thermal_sample["mono_ns"])
                ) / 1e6
                for key in ("AP", "SKIN", "BAT", "PA"):
                    row[key] = thermal_sample.get(key)
                row["thermalservice_status"] = thermal_sample.get("thermal_status")
            writer.writerow(row)

    metadata_event = gpu[0]
    mode = str(metadata_event.get("experiment_mode", "UNKNOWN")).lower()
    latencies = [float(event["latency_ms"]) for event in inference]
    raw_log_path = run_dir / "raw/logcat.txt"
    evidence = delegate_evidence(
        raw_log_path.read_text(encoding="utf-8", errors="replace")
        if raw_log_path.exists() else "",
        diagnostic_v2=metadata_event.get("protocol_version") == 2,
    )
    (merged_dir / "delegate_evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    metadata_path = run_dir / "metadata.json"
    capture_metadata = (
        json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    )
    if metadata_event.get("protocol_version") == 2:
        diagnostic_session_id = metadata_event.get("diagnostic_session_id")
        validate_gpu_file(
            gpu,
            run_id,
            metadata_event.get("runner_session_id"),
            diagnostic_session_id,
            metadata_event.get("requested_trace_mode"),
        )
        if capture_metadata.get("protocol_version") != 2 or (
            capture_metadata.get("diagnostic_session_id") != diagnostic_session_id
        ):
            raise ValueError("logger metadata and runner diagnostic identity differ")
        if (
            capture_metadata.get("requested_trace_mode")
            != metadata_event.get("requested_trace_mode")
        ):
            raise ValueError("trace-off and trace-on artifacts cannot be combined")
        validate_diagnostic_trace_artifacts(
            run_dir, capture_metadata, str(diagnostic_session_id)
        )
    is_gpu = str(metadata_event.get("resource", "")).upper() == "GPU"
    profile_context = experiment_profile_context(run_dir)
    gpu_profile = metadata_event.get("gpu_delegate_profile")
    profile_validation = validate_gpu_execution_profile(
        metadata_event.get("resource"),
        gpu_profile,
        profile_context.get("config_profile"),
        profile_context.get("preflight_profile"),
        manifest_available=bool(profile_context.get("manifest_available")),
        manifest_error=profile_context.get("manifest_error"),
    )
    if is_gpu and profile_validation["status"] == "legacy_missing":
        analysis_warnings.append(
            "legacy GPU run lacks explicit gpu_delegate_profile; no profile was inferred"
        )
    galaxy_a24 = str(capture_metadata.get("device_model", "")).upper().startswith("SM-A245")
    formal_gpu_valid = (
        is_gpu
        and mode == "basic"
        and galaxy_a24
        and metadata_event.get("model_sha256") ==
            "D95B3C5EA86750CEF882FA867CA357DFE4D265D0B80B67E83277A0BDA310CFBB"
        and metadata_event.get("litert_version") == "1.4.2"
        and evidence["full_delegate"] is True
        and profile_validation["valid"] is True
        and metadata_event.get("experiment_valid") is True
        and coverage["passes_formal_requirement"] is True
    )
    if mode == "diagnostic" and capture_metadata.get("diagnostic_perfetto_enabled") is True:
        analysis_warnings.append(
            f"Perfetto uses a {PERFETTO_BUFFER_KB} KiB ring buffer for up to "
            f"{MAX_DIAGNOSTIC_SECONDS}s; overwrite is possible"
        )
    provenance = measurement_provenance(metadata_event)
    finalized_runner_metadata_path: Path | None = None
    if metadata_event.get("protocol_version") == 2:
        finalized_runner_metadata = dict(metadata_event)
        for key in (
            "diagnostic_perfetto_enabled",
            "requested_trace_mode",
            "diagnostic_perfetto_started",
            "diagnostic_trace_filename",
            "diagnostic_trace_session_id",
            "diagnostic_trace_size_bytes",
            "diagnostic_trace_sha256",
            "diagnostic_perfetto_process_exited",
            "diagnostic_perfetto_control_mode",
            "diagnostic_perfetto_session_key",
            "diagnostic_perfetto_start_pid",
            "diagnostic_perfetto_control_results",
            "diagnostic_perfetto_readiness_semantics",
            "diagnostic_perfetto_pid_control",
            "diagnostic_perfetto_config_write_into_file",
            "diagnostic_perfetto_config_duration_ms",
        ):
            finalized_runner_metadata[key] = capture_metadata.get(key)
        finalized_runner_metadata["trace_metadata_finalization"] = (
            "host_logger_after_trace_stop_preserving_authoritative_runner_jsonl"
        )
        finalized_runner_metadata["actual_backend_observed"] = evidence[
            "actual_backend_observed"
        ]
        gpu_capabilities = finalized_runner_metadata.get("gpu_diagnostic_capabilities")
        if isinstance(gpu_capabilities, dict):
            gpu_capabilities = dict(gpu_capabilities)
            gpu_capabilities["actual_backend_observed"] = evidence[
                "actual_backend_observed"
            ]
            gpu_capabilities["backend_observation_source"] = "raw_LiteRT_log"
            finalized_runner_metadata["gpu_diagnostic_capabilities"] = gpu_capabilities
        finalized_runner_metadata_path = merged_dir / "runner_metadata.json"
        finalized_runner_metadata_path.write_text(
            json.dumps(finalized_runner_metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    summary = {
        "schema_version": 2,
        "run_id": run_id,
        "statistics_group": "diagnostic" if mode == "diagnostic" else "basic",
        "resource": metadata_event.get("resource"),
        "model_id": metadata_event.get("model_id"),
        "model_sha256": metadata_event.get("model_sha256"),
        "gpu_file_validation": "pass",
        "gpu_file_event_count": len(gpu),
        "runner_session_id": metadata_event.get("runner_session_id"),
        "runner_session_count": len(sessions),
        "telemetry_sample_count": len(samples),
        "thermalservice_sample_count": len(thermal_samples),
        "thermalservice_error_count": coverage["error_count"],
        "thermal_coverage": coverage,
        "load_start_mono_ns": load_start["mono_ns"],
        "load_end_mono_ns": load_end["mono_ns"],
        "run_start_mono_ns": run_start_ns,
        "run_stop_mono_ns": run_stop_ns,
        "run_envelope_validation": "pass",
        "delegate_evidence": evidence,
        "gpu_delegate_profile": gpu_profile if is_gpu and isinstance(gpu_profile, dict) else None,
        "profile_consistency_validation": profile_validation,
        "formal_gpu_valid": formal_gpu_valid if is_gpu else None,
        "analysis_warnings": analysis_warnings,
        "inference_latency": latency_stats(latencies),
        "duty_cycle": {
            key: metadata_event.get(key)
            for key in (
                "requested_duty_cycle_percent",
                "duty_cycle_period_ns",
                "target_active_duration_ns",
                "actual_active_duration_ns",
                "actual_idle_duration_ns",
                "achieved_duty_cycle_percent",
                "completed_duty_cycle_count",
                "duty_cycle_active_overrun_ns",
                "completed_inference_count",
                "termination_reason",
            )
        },
        "accuracy_preflight": provenance["accuracy_preflight"],
        "energy_measurement": provenance["energy_measurement"],
    }
    if metadata_event.get("protocol_version") == 2:
        summary.update({
            "statistics_group":
                f"diagnostic_v2_trace_{capture_metadata.get('requested_trace_mode')}",
            "protocol_version": 2,
            "diagnostic_session_id": metadata_event.get("diagnostic_session_id"),
            "diagnostic_perfetto_enabled": capture_metadata.get(
                "diagnostic_perfetto_enabled"
            ),
            "requested_trace_mode": capture_metadata.get("requested_trace_mode"),
            "diagnostic_perfetto_started": capture_metadata.get(
                "diagnostic_perfetto_started"
            ),
            "diagnostic_trace_filename": capture_metadata.get(
                "diagnostic_trace_filename"
            ),
            "diagnostic_trace_session_id": capture_metadata.get(
                "diagnostic_trace_session_id"
            ),
            "diagnostic_trace_size_bytes": capture_metadata.get(
                "diagnostic_trace_size_bytes"
            ),
            "diagnostic_trace_sha256": capture_metadata.get(
                "diagnostic_trace_sha256"
            ),
            "diagnostic_perfetto_process_exited": capture_metadata.get(
                "diagnostic_perfetto_process_exited"
            ),
            "diagnostic_perfetto_control_mode": capture_metadata.get(
                "diagnostic_perfetto_control_mode"
            ),
            "diagnostic_perfetto_session_key": capture_metadata.get(
                "diagnostic_perfetto_session_key"
            ),
            "diagnostic_perfetto_start_pid": capture_metadata.get(
                "diagnostic_perfetto_start_pid"
            ),
            "diagnostic_perfetto_control_results": capture_metadata.get(
                "diagnostic_perfetto_control_results"
            ),
            "diagnostic_perfetto_readiness_semantics": capture_metadata.get(
                "diagnostic_perfetto_readiness_semantics"
            ),
            "diagnostic_perfetto_pid_control": capture_metadata.get(
                "diagnostic_perfetto_pid_control"
            ),
            "diagnostic_perfetto_config_write_into_file": capture_metadata.get(
                "diagnostic_perfetto_config_write_into_file"
            ),
            "diagnostic_perfetto_config_duration_ms": capture_metadata.get(
                "diagnostic_perfetto_config_duration_ms"
            ),
            "finalized_runner_metadata_path": str(finalized_runner_metadata_path),
            "actual_backend_observed": evidence["actual_backend_observed"],
        })
    (merged_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def run_self_test() -> None:
    thermal = """Thermal Status: 0
Current temperatures from HAL:
 Temperature{mValue=34.6, mType=0, mName=AP, mStatus=0}
 Temperature{mValue=29.9, mType=3, mName=SKIN, mStatus=0}
 Temperature{mValue=28.7, mType=2, mName=BAT, mStatus=0}
 Temperature{mValue=32.0, mType=0, mName=PA1THM, mStatus=0}
Current cooling devices from HAL:
"""
    assert parse_thermalservice(thermal) == {
        "AP": "34.6",
        "SKIN": "29.9",
        "BAT": "28.7",
        "PA": "32.0",
        "thermal_status": "0",
    }
    assert percentile([0.0, 100.0], 0.95) == 95.0
    print("self-test PASS")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb")
    parser.add_argument("--serial")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("clear", help="clear logcat before capture")
    capture_parser = subparsers.add_parser("capture")
    capture_parser.add_argument("output_root", type=Path, default=Path("results"), nargs="?")
    capture_parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_S)
    capture_parser.add_argument(
        "--diagnostic-perfetto", nargs="?", const="on",
        choices=("off", "on"), default="off",
    )
    capture_parser.add_argument("--protocol-version", type=int, choices=(2,))
    capture_parser.add_argument("--diagnostic-session-id")
    capture_parser.add_argument("--perfetto-duration-ms", type=int)
    capture_parser.add_argument(
        "--perfetto-config",
        type=Path,
        default=Path(__file__).with_name("perfetto") / "gpu_diagnostic.pbtxt",
    )
    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("run_dir", type=Path)
    subparsers.add_parser("self-test")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "self-test":
        run_self_test()
        return 0
    if args.command == "analyze":
        analyze(args.run_dir)
        return 0
    adb = resolve_adb(args.adb)
    if args.command == "clear":
        return clear_logcat(adb, args.serial)
    if args.interval < 0.5:
        raise ValueError("--interval must be at least 0.5 seconds")
    return CaptureSession(
        adb, args.serial, args.output_root, args.interval,
        args.diagnostic_perfetto == "on", args.perfetto_config,
        args.protocol_version, args.diagnostic_session_id, args.perfetto_duration_ms,
    ).run()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
