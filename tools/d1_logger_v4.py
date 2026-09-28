#!/usr/bin/env python3
"""D1Check v4 capture/merge tool. Current values always remain unscaled raw values."""

from __future__ import annotations

import argparse
import bisect
import csv
import datetime as dt
from enum import Enum
import json
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
from collections import defaultdict
from typing import Any, Iterable


VERSION = "4.1"
DEFAULT_INTERVAL_S = 1.0
RUNNER_PACKAGE = "com.example.d1check.benchmarkrunner"

# Devices whose GPU measurement path has been validated end to end: the
# delegate is created, takes every node, leaves no fallback evidence, and
# produces outputs numerically equivalent to CPU. Adding a prefix here is a
# claim that this evidence exists; see s26/patches/README.md patch 2.
#   SM-A245  Galaxy A24  the device the v4 stack was built and validated on
#   SM-S942  Galaxy S26  validated 2026-09-13, s26/results/PILOT_RESULTS.md
#            its LiteRT compatibility-list verdict is false, so its runs
#            carry formal_gpu_compat_list_override=True
FORMAL_GPU_VALIDATED_DEVICE_PREFIXES = ("SM-A245", "SM-S942")
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
DELEGATE_FAILURE_RE = re.compile(
    r"(?:failed\s+to\s+apply|restored\s+original\s+execution\s+plan|unsupported\s+op|"
    r"remaining\s+nodes?\s+run\s+on\s+CPU|fall(?:ing)?\s+back\s+to\s+CPU|CPU\s+fallback)",
    re.IGNORECASE,
)
# NPU (npu-runner, LiteRT Next CompiledModel + Samsung dispatch). Mirrors the GPU constants above:
# adding a device prefix, runtime pairing or model hash here is a claim that on-device evidence exists.
#   SM-S942  Galaxy S26  G4 passed 2026-09-24, s26/npu/results/G4_VERDICT_0924.md
NPU_RUNNER_PACKAGE = "com.example.d1check.npurunner"
FORMAL_NPU_VALIDATED_DEVICE_PREFIXES = ("SM-S942",)
# The one runtime pairing verified on device: AAR litert 2.2.0 + dispatch built from LiteRT main@9380426b.
NPU_LITERT_RUNTIME_VERSION = "2.2.0"
NPU_DISPATCH_LIB_SHA256 = "f08656a642c46e7b06b64fbe1e0800de9e73b0b69c1641b87995562b4a16840f"
# AOT outputs from npu-runner/src/main/assets/models/aot_manifest.json (merged G1 + G1-B), keyed by
# output SHA-256. dispatch/non_dispatch op counts are the static partition the runtime log must match.
FORMAL_NPU_AOT_MODELS = {
    "1415b2c87d01b67a9380b8f912e2b4ef4561502105b06f313332c97c1c8cb5cf": {
        "model": "mobilenet_v1_1.0_224_Samsung_E9965.tflite", "compile_batch": "G1",
        "ai_edge_litert": "2.3.0.dev20260917", "dispatch_ops": 1, "non_dispatch_ops": 0,
    },
    "36c75e6acdb711628f2486c7880a9c84fe1dc94c986d4f8dc53eb94ee773e5fa": {
        "model": "mobilenet_v1_1.0_224_quant_Samsung_E9965.tflite", "compile_batch": "G1",
        "ai_edge_litert": "2.3.0.dev20260917", "dispatch_ops": 1, "non_dispatch_ops": 0,
    },
    # G1-B (2026-09-24) — compiled by a newer SDK and not yet run on device. Listed so the
    # partition check can run; formal validity still needs every other condition.
    "311e4aac8fa1d8def4e13359c731ddc1c92f4c9ff7074e0d3860b036df8b2a31": {
        "model": "efficientnet_lite0_Samsung_E9965.tflite", "compile_batch": "G1-B",
        "ai_edge_litert": "2.3.0.dev20260922", "dispatch_ops": 1, "non_dispatch_ops": 0,
    },
    "f51d082dbf68bef94092f9d2e262920ebb0fe6149df314453a767d50f8c9bc7a": {
        "model": "efficientdet_lite0_Samsung_E9965.tflite", "compile_batch": "G1-B",
        "ai_edge_litert": "2.3.0.dev20260922", "dispatch_ops": 1, "non_dispatch_ops": 0,
    },
}
NPU_QUALITY_GATE_N = 32
NPU_QUALITY_COSINE_MIN = 0.99
# "Replacing 1 out of 1 node(s) with delegate (DispatchDelegate) node, yielding 1 partitions" (tag tflite).
# This line is printed even when the dispatch runtime then fails, so it is never sufficient alone.
NPU_DISPATCH_REPLACE_RE = re.compile(
    r"Replacing\s+(\d+)\s+out of\s+(\d+)\s+node(?:\(s\)|s)?\s+with\s+delegate\s+"
    r"\(DispatchDelegate\)(?:\s+node,\s+yielding\s+(\d+)\s+partitions?)?",
    re.IGNORECASE,
)
# "[enn_manager.cc:124] SetGenAiPerfConfigFromSoc: SOC=s5e9965, mode=7" (tag litert): ENN actually loaded.
NPU_ENN_LOADED_RE = re.compile(r"SetGenAiPerfConfigFromSoc:\s*SOC=([A-Za-z0-9_]+)", re.IGNORECASE)
NPU_DISPATCH_FAILURE_RE = re.compile(
    r"(?:No\s+dispatch\s+library\s+found|Failed\s+to\s+initialize\s+Dispatch\s+API|"
    r"No\s+usable\s+Dispatch\s+runtime\s+found|Failed\s+to\s+create\s+a\s+dispatch\s+delegate\s+kernel|"
    r"Failed\s+to\s+load\s+enn\s+runtime|Found\s+Dispatch\s+API\s+with\s+an\s+unsupported\s+version|"
    r"Failed\s+to\s+allocate\s+tensors|\(DELEGATE\)\s+failed\s+to\s+prepare)",
    re.IGNORECASE,
)
PERFETTO_BUFFER_KB = 32768
MAX_DIAGNOSTIC_SECONDS = 3600
PERFETTO_DEVICE_CONFIG_PATH = (
    "/data/misc/perfetto-configs/d1check-gpu-diagnostic.pbtxt"
)
PERFETTO_DEVICE_TRACE_PATH = (
    "/data/misc/perfetto-traces/d1check-diagnostic.perfetto-trace"
)


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


def delegate_evidence(raw_log: str) -> dict[str, Any]:
    matches = list(DELEGATE_REPLACE_RE.finditer(raw_log))
    replacement = matches[-1] if matches else None
    kernel_matches = list(GPU_KERNEL_RE.finditer(raw_log))
    replaced = int(replacement.group(1)) if replacement else None
    total = int(replacement.group(2)) if replacement else None
    kernel_count = int(kernel_matches[-1].group(1)) if kernel_matches else None
    gpu_created = bool(GPU_DELEGATE_CREATED_RE.search(raw_log))
    gpu_type = bool(GPU_DELEGATE_TYPE_RE.search(raw_log))
    failure_matches = sorted({match.group(0) for match in DELEGATE_FAILURE_RE.finditer(raw_log)})
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
    return {
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


def npu_delegate_evidence(raw_log: str, model_sha256: Any) -> dict[str, Any]:
    """NPU counterpart of delegate_evidence(). Verified only when the dispatch delegate took the
    nodes the AOT manifest says it should, ENN was actually loaded, and no dispatch failure line exists."""
    matches = list(NPU_DISPATCH_REPLACE_RE.finditer(raw_log))
    replacement = matches[-1] if matches else None
    replaced = int(replacement.group(1)) if replacement else None
    total = int(replacement.group(2)) if replacement else None
    partitions = (
        int(replacement.group(3)) if replacement and replacement.group(3) else None
    )
    enn_soc = [match.group(1) for match in NPU_ENN_LOADED_RE.finditer(raw_log)]
    failure_matches = sorted({match.group(0) for match in NPU_DISPATCH_FAILURE_RE.finditer(raw_log)})
    partition = FORMAL_NPU_AOT_MODELS.get(str(model_sha256 or "").lower())
    partition_match = (
        partition is not None
        and replaced == partition["dispatch_ops"]
        and total == partition["dispatch_ops"] + partition["non_dispatch_ops"]
    )
    verified = (
        replaced is not None
        and total is not None
        and 0 < replaced <= total
        and bool(enn_soc)
        and not failure_matches
        and partition_match
    )
    return {
        "dispatch_replaced_nodes": replaced,
        "dispatch_total_nodes": total,
        "dispatch_partitions": partitions,
        "enn_soc": enn_soc[-1] if enn_soc else None,
        "failure_or_fallback_evidence": failure_matches,
        "aot_partition": partition,
        "partition_matches_aot_manifest": partition_match,
        "npu_full": verified and replaced == total,
        "npu_partial_delegation": (
            partition["non_dispatch_ops"] > 0 if partition is not None else None
        ),
        "verification": "verified" if verified else "unverified",
        "note": None if verified else (
            "No conclusive NPU dispatch evidence (needs DispatchDelegate X/Y matching the AOT "
            "manifest, an ENN load line, and no dispatch failure line)."
        ),
    }


def experiment_npu_quality_context(run_dir: Path) -> dict[str, Any] | None:
    """NPU quality preflight recorded by the orchestrator (npu-runner quality gate, n=32)."""
    manifest_path = run_dir.parent.parent / "experiment_manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    value = manifest.get("npu_quality_preflight") if isinstance(manifest, dict) else None
    return value if isinstance(value, dict) else None


def npu_quality_gate_passes(preflight: Any, model_sha256: Any) -> bool:
    """Criteria fixed before results (CLAUDE.md §5): bit_identical_to_cpu is False (True means it ran
    on CPU), argmax 32/32, cosine_min >= 0.99 — and the preflight must be for the same model file."""
    if not isinstance(preflight, dict) or preflight.get("status") != "passed":
        return False
    gate = preflight.get("quality_gate")
    if not isinstance(gate, dict):
        return False
    n = gate.get("n")
    cosine_min = gate.get("cosine_min")
    return (
        str(preflight.get("candidate_model_sha256") or "").lower()
        == str(model_sha256 or "").lower() != ""
        and gate.get("verdict") == "PASS"
        and gate.get("bit_identical_to_cpu") is False
        and n == NPU_QUALITY_GATE_N
        and gate.get("argmax_agreement") == f"{n}/{n}"
        and isinstance(cosine_min, (int, float))
        and not isinstance(cosine_min, bool)
        and cosine_min >= NPU_QUALITY_COSINE_MIN
    )


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
        runner_package: str = RUNNER_PACKAGE,
        extra_logcat_tags: Iterable[str] = (),
        keep_files_open: bool = False,
    ) -> None:
        self.adb_command = adb_base(adb, serial)
        # NPU runs pass npu-runner's package and "litert:I"; CPU/GPU use the defaults unchanged.
        self.runner_package = runner_package
        self.extra_logcat_tags = list(extra_logcat_tags)
        self.output_root = output_root
        self.interval_s = interval_s
        self.diagnostic_perfetto = diagnostic_perfetto
        self.perfetto_config = perfetto_config
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.run_id: str | None = None
        self.run_dir: Path | None = None
        self.pending_thermal: list[dict[str, Any]] = []
        self.logcat_process: subprocess.Popen[str] | None = None
        self.perfetto_pid: str | None = None
        self.perfetto_state = PerfettoState.IDLE
        self.perfetto_lock = threading.Lock()
        self.perfetto_cleanup_done = False
        self.capture_error: str | None = None
        self.capture_warnings: list[str] = []
        self.pending_raw_log: list[str] = []
        self.recovered_runner_files: set[str] = set()
        # 2026-09-28 opt-in (capture --keep-files-open): see _stream(). Default = open/append/close per line.
        self.keep_files_open = keep_files_open
        self._open_streams: dict[Path, Any] = {}

    def activate_run(self, run_id: str, run_start_mono_ns: int) -> None:
        with self.lock:
            if self.run_id == run_id:
                return
            self.run_id = run_id
            self.run_dir = self.output_root / run_id
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

    def _stream(self, path: Path) -> Any:
        # --keep-files-open: one line-buffered handle per file instead of open/append/close per line.
        # Same bytes (every write ends with "\n" and is flushed there); the end-of-run D1GPU burst drains
        # ~12x faster (60,077-line synthetic stream, this PC: 843 -> 10,587 lines/s). Closed in run().
        stream = self._open_streams.get(path)
        if stream is None:
            stream = path.open("a", encoding="utf-8", newline="\n", buffering=1)
            self._open_streams[path] = stream
        return stream

    def close_capture_files(self) -> None:
        with self.lock:
            for stream in self._open_streams.values():
                stream.close()
            self._open_streams.clear()

    def _append_raw_log(self, line: str) -> None:
        if self.run_dir is None:
            self.pending_raw_log.append(line)
            return
        if self.keep_files_open:
            self._stream(self.run_dir / "raw/logcat.txt").write(line.rstrip("\r\n") + "\n")
            return
        with (self.run_dir / "raw/logcat.txt").open(
            "a", encoding="utf-8", newline="\n"
        ) as stream:
            stream.write(line.rstrip("\r\n") + "\n")

    def _append_json(self, relative: str, event: dict[str, Any]) -> None:
        if self.run_dir is None:
            return
        path = self.run_dir / relative
        if self.keep_files_open:
            self._stream(path).write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
            return
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")

    def record_logcat(self, event: dict[str, Any]) -> None:
        if event.get("source") == "d1check" and event.get("event") == "run_start":
            if self.run_id is not None and event.get("run_id") != self.run_id:
                with self.lock:
                    self._append_json("raw/logcat.jsonl", event)
                self.capture_error = "new D1Check run appeared before the captured run stopped"
                self.stop.set()
                return
            self.activate_run(str(event["run_id"]), int(event["mono_ns"]))
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
        validate_gpu_file(load_jsonl(destination), str(self.run_id), session_id)

    def pull_runner_file(self, event: dict[str, Any]) -> None:
        if self.run_dir is None:
            return
        device_path = str(event.get("file_path", ""))
        session_id = str(event.get("runner_session_id", ""))
        if not device_path or not session_id:
            raise ValueError("file_summary lacks file_path or runner_session_id")
        filename = Path(device_path).name
        if filename in self.recovered_runner_files:
            return
        destination = self.run_dir / "gpu" / filename
        result = subprocess.run(
            self.adb_command + ["pull", device_path, str(destination)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            self._validate_pulled_file(destination)
            self.recovered_runner_files.add(filename)
            return
        fallback = subprocess.run(
            self.adb_command
            + [
                "exec-out",
                "run-as",
                self.runner_package,
                "cat",
                f"files/runs/{filename}",
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
        pattern = (
            f"/storage/emulated/0/Android/data/{self.runner_package}/files/runs/"
            f"gpu-events-{self.run_id}-*.jsonl"
        )
        result = subprocess.run(
            self.adb_command + ["shell", "ls", pattern], capture_output=True, text=True
        )
        paths = [
            line.strip() for line in result.stdout.splitlines()
            if line.strip().endswith(".jsonl")
        ]
        internal = subprocess.run(
            self.adb_command + [
                "exec-out", "run-as", self.runner_package, "ls",
                f"files/runs/gpu-events-{self.run_id}-*.jsonl",
            ],
            capture_output=True,
            text=True,
        )
        for line in internal.stdout.splitlines():
            value = line.strip()
            if value.endswith(".jsonl"):
                paths.append(value if "/" in value else f"files/runs/{value}")
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
                push = subprocess.run(
                    self.adb_command + [
                        "push", str(self.perfetto_config), PERFETTO_DEVICE_CONFIG_PATH,
                    ],
                    capture_output=True,
                    text=True,
                    errors="replace",
                )
                if push.returncode != 0:
                    raise RuntimeError(self._perfetto_failure("config push", push))
                result = subprocess.run(
                    self.adb_command + [
                        "shell", "perfetto", "--txt",
                        "-c", PERFETTO_DEVICE_CONFIG_PATH,
                        "-o", PERFETTO_DEVICE_TRACE_PATH,
                        "--background-wait",
                    ],
                    capture_output=True,
                    text=True,
                    errors="replace",
                )
                if result.returncode != 0:
                    raise RuntimeError(self._perfetto_failure("start", result))
                pid_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
                if not pid_lines:
                    raise RuntimeError(
                        "Perfetto start failed: returncode=0 but stdout contained no "
                        f"background PID; stderr={result.stderr.strip()[:500]!r}"
                    )
                self.perfetto_pid = pid_lines[-1]
                self.perfetto_state = PerfettoState.RUNNING
            except Exception as error:
                self.perfetto_pid = None
                self.perfetto_state = PerfettoState.FAILED
                detail = str(error)
                self.capture_error = (
                    detail if detail.startswith("Perfetto ")
                    else f"Perfetto start failed: {detail}"
                )
                raise RuntimeError(self.capture_error) from error

    @staticmethod
    def _perfetto_failure(operation: str, result: subprocess.CompletedProcess[str]) -> str:
        stderr = result.stderr.strip()[:500]
        stdout = result.stdout.strip()[:500]
        return (
            f"Perfetto {operation} failed: returncode={result.returncode}; "
            f"stderr={stderr!r}; stdout={stdout!r}"
        )

    def cleanup_perfetto(self) -> None:
        with self.perfetto_lock:
            if not self.diagnostic_perfetto or self.perfetto_cleanup_done:
                return
            result = subprocess.run(
                self.adb_command + [
                    "shell", "rm", "-f",
                    PERFETTO_DEVICE_CONFIG_PATH,
                    PERFETTO_DEVICE_TRACE_PATH,
                ],
                capture_output=True,
                text=True,
                errors="replace",
            )
            self.perfetto_cleanup_done = True
            if result.returncode != 0:
                self.capture_warnings.append(self._perfetto_failure("cleanup", result))

    def stop_perfetto(self) -> None:
        if not self.diagnostic_perfetto:
            return
        with self.perfetto_lock:
            if self.perfetto_state is not PerfettoState.RUNNING:
                return
            self.perfetto_state = PerfettoState.STOPPING
            pid = self.perfetto_pid
            self.perfetto_pid = None
        temporary: Path | None = None
        try:
            if not pid:
                raise RuntimeError("Perfetto stop failed: RUNNING state had no PID")
            killed = subprocess.run(
                self.adb_command + ["shell", "kill", "-INT", pid],
                capture_output=True,
                text=True,
                errors="replace",
            )
            if killed.returncode != 0:
                raise RuntimeError(self._perfetto_failure("stop", killed))
            time.sleep(1)
            if self.run_dir is None:
                raise RuntimeError("Perfetto pull failed: capture run directory is unavailable")
            destination = self.run_dir / "diagnostics/d1check.perfetto-trace"
            if destination.is_file() and destination.stat().st_size > 0:
                with self.perfetto_lock:
                    self.perfetto_state = PerfettoState.COMPLETED
                self.cleanup_perfetto()
                return
            temporary = destination.with_name(destination.name + ".part")
            temporary.unlink(missing_ok=True)
            pulled = subprocess.run(
                self.adb_command + [
                    "pull", PERFETTO_DEVICE_TRACE_PATH, str(temporary),
                ],
                capture_output=True,
                text=True,
                errors="replace",
            )
            if pulled.returncode != 0:
                raise RuntimeError(self._perfetto_failure("pull", pulled))
            if not temporary.is_file():
                raise RuntimeError("Perfetto pull failed: local temporary trace was not created")
            if temporary.stat().st_size <= 0:
                raise RuntimeError("Perfetto pull failed: local temporary trace is empty")
            if destination.exists():
                raise RuntimeError(
                    f"Perfetto pull refused to overwrite existing trace: {destination}"
                )
            os.replace(temporary, destination)
            temporary = None
            if destination.stat().st_size <= 0:
                raise RuntimeError("Perfetto pull failed: final local trace is empty")
            with self.perfetto_lock:
                self.perfetto_state = PerfettoState.COMPLETED
            self.cleanup_perfetto()
        except Exception as error:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            with self.perfetto_lock:
                self.perfetto_state = PerfettoState.FAILED
            detail = str(error)
            self.capture_error = (
                f"{detail}; remote_trace={PERFETTO_DEVICE_TRACE_PATH}; "
                "remote trace retained for manual recovery"
            )

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
        self.record_logcat(event)
        if event.get("source") == "gpu" and event.get("run_id") == self.run_id:
            if event.get("event") == "diagnostic_trace_start":
                try:
                    self.start_perfetto()
                except Exception as error:
                    detail = str(error)
                    self.capture_error = (
                        detail if detail.startswith("Perfetto ")
                        else f"Perfetto start failed: {detail}"
                    )
                    self.stop.set()
            if event.get("event") in ("diagnostic_trace_stop", "load_end"):
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
                "tflite:I", "TfLite:I", *self.extra_logcat_tags, "*:S",
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
        threads = [
            threading.Thread(target=self.thermal_loop, name="thermal", daemon=True),
            threading.Thread(target=self.logcat_loop, name="logcat", daemon=True),
        ]
        for thread in threads:
            thread.start()
        print("capture started; now start a new D1Check run", file=sys.stderr)
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
                # A started PID is always killed, even if no run directory was ever created.
                self.stop_perfetto()
            if self.keep_files_open:
                self.close_capture_files()
            if self.run_dir is not None:
                metadata_path = self.run_dir / "metadata.json"
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
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
    events: list[dict[str, Any]], run_id: str, runner_session_id: str | None = None
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
    summary = events[-1]
    if summary.get("event") != "file_summary":
        raise ValueError("runner JSONL has no file_summary footer")
    if int(summary.get("file_event_count", -1)) != len(events):
        raise ValueError("runner file_event_count mismatch")
    if int(summary.get("sequence_last", -1)) != sequences[-1]:
        raise ValueError("runner sequence_last mismatch")


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
        if raw_log_path.exists() else ""
    )
    (merged_dir / "delegate_evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    metadata_path = run_dir / "metadata.json"
    capture_metadata = (
        json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
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
    device_model = str(capture_metadata.get("device_model", "")).upper()
    gpu_validated_device = device_model.startswith(
        FORMAL_GPU_VALIDATED_DEVICE_PREFIXES
    )
    formal_gpu_valid = (
        is_gpu
        and mode == "basic"
        and gpu_validated_device
        and metadata_event.get("model_sha256") ==
            "D95B3C5EA86750CEF882FA867CA357DFE4D265D0B80B67E83277A0BDA310CFBB"
        and metadata_event.get("litert_version") == "1.4.2"
        and evidence["full_delegate"] is True
        and profile_validation["valid"] is True
        and metadata_event.get("experiment_valid") is True
        and coverage["passes_formal_requirement"] is True
    )
    is_npu = str(metadata_event.get("resource", "")).upper() == "NPU"
    npu_summary: dict[str, Any] = {}
    if is_npu:
        # Mirrors formal_gpu_valid's nine conditions. The GPU-only ones (TfLiteGpuDelegateV2 log
        # evidence, GPU delegate profile) are replaced by NPU dispatch evidence and the NPU quality gate.
        npu_model_sha = str(metadata_event.get("model_sha256") or "").lower()
        npu_evidence = npu_delegate_evidence(
            raw_log_path.read_text(encoding="utf-8", errors="replace")
            if raw_log_path.exists() else "",
            npu_model_sha,
        )
        (merged_dir / "npu_delegate_evidence.json").write_text(
            json.dumps(npu_evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        npu_quality = experiment_npu_quality_context(run_dir)
        npu_conditions = {
            "resource_npu": True,
            "basic_mode": mode == "basic",
            "validated_device": device_model.startswith(FORMAL_NPU_VALIDATED_DEVICE_PREFIXES),
            "known_aot_model": npu_model_sha in FORMAL_NPU_AOT_MODELS,
            "validated_runtime_pairing": (
                metadata_event.get("litert_version") == NPU_LITERT_RUNTIME_VERSION
                and str(metadata_event.get("npu_dispatch_lib_sha256") or "").lower()
                == NPU_DISPATCH_LIB_SHA256
            ),
            "dispatch_evidence_verified": npu_evidence["verification"] == "verified",
            "quality_gate_pass": npu_quality_gate_passes(npu_quality, npu_model_sha),
            "runner_experiment_valid": metadata_event.get("experiment_valid") is True,
            "thermal_coverage": coverage["passes_formal_requirement"] is True,
        }
        # 2026-09-28: chain-mode runs (npu-runner --npu-chain) are pilot-only and never formal.
        # The key exists only for chain runs, so ordinary NPU summaries are unchanged.
        if metadata_event.get("chain_mode") is True:
            npu_conditions["not_chain_run"] = False
        if npu_quality is None:
            analysis_warnings.append(
                "no npu_quality_preflight in experiment manifest; formal_npu_valid is false"
            )
        npu_summary = {
            "engine": metadata_event.get("engine"),
            "npu_delegate_evidence": npu_evidence,
            "npu_partial_delegation": npu_evidence["npu_partial_delegation"],
            "npu_quality_preflight": npu_quality,
            "formal_npu_conditions": npu_conditions,
            "formal_npu_valid": all(npu_conditions.values()),
        }
    if mode == "diagnostic":
        analysis_warnings.append(
            f"Perfetto uses a {PERFETTO_BUFFER_KB} KiB ring buffer for up to "
            f"{MAX_DIAGNOSTIC_SECONDS}s; overwrite is possible"
        )
    provenance = measurement_provenance(metadata_event)
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
        "gpu_compatibility_list_supported": (
            metadata_event.get("gpu_compatibility_list_supported")
            if is_gpu else None
        ),
        "formal_gpu_compat_list_override": (
            metadata_event.get("gpu_compatibility_list_supported") is False
            if is_gpu else None
        ),
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
    # NPU keys only on NPU runs, so CPU/GPU summaries stay byte-for-byte what they were.
    summary.update(npu_summary)
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
    capture_parser.add_argument("--diagnostic-perfetto", action="store_true")
    capture_parser.add_argument(
        "--runner-package", default=RUNNER_PACKAGE,
        choices=(RUNNER_PACKAGE, NPU_RUNNER_PACKAGE),
        help="package whose files/runs holds the runner JSONL (npu-runner for NPU runs)",
    )
    capture_parser.add_argument(
        "--extra-logcat-tag", action="append", default=[],
        help="additional logcat filterspec such as litert:I (NPU dispatch/ENN evidence)",
    )
    capture_parser.add_argument(
        "--perfetto-config",
        type=Path,
        default=Path(__file__).with_name("perfetto") / "gpu_diagnostic.pbtxt",
    )
    capture_parser.add_argument(
        "--keep-files-open", action="store_true",
        help="2026-09-28: one line-buffered handle per capture file (same bytes, faster burst drain)",
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
    for tag in args.extra_logcat_tag:
        if re.fullmatch(r"[A-Za-z0-9_.-]+:[VDIWEF]", tag) is None:
            raise ValueError(f"invalid --extra-logcat-tag: {tag!r}")
    return CaptureSession(
        adb, args.serial, args.output_root, args.interval,
        args.diagnostic_perfetto, args.perfetto_config,
        args.runner_package, args.extra_logcat_tag,
        keep_files_open=args.keep_files_open,
    ).run()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
