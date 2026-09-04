#!/usr/bin/env python3
"""D1Check v4 capture/merge tool. Current values always remain unscaled raw values."""

from __future__ import annotations

import argparse
import bisect
import csv
import datetime as dt
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
TEMP_RE = re.compile(
    r"mValue=(-?[\d.]+),\s*mType=\d+,\s*mName=([^,}]+)", re.IGNORECASE
)
THERMAL_STATUS_RE = re.compile(r"Thermal Status:\s*(-?\d+)")
DELEGATE_REPLACE_RE = re.compile(
    r"Replacing\s+(\d+)\s+out of\s+(\d+)\s+node(?:\(s\)|s)?", re.IGNORECASE
)
FULL_DELEGATE_RE = re.compile(
    r"(?:whole graph|fully delegated|entire graph[^\n]*delegat|all nodes[^\n]*delegat)",
    re.IGNORECASE,
)
PERFETTO_BUFFER_KB = 32768
MAX_DIAGNOSTIC_SECONDS = 3600


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


def runner_session_from_filename(filename: str, run_id: str) -> str | None:
    prefix = f"gpu-events-{run_id}-"
    if not filename.startswith(prefix) or not filename.endswith(".jsonl"):
        return None
    session_id = filename[len(prefix):-len(".jsonl")]
    return session_id if re.fullmatch(r"[A-Za-z0-9-]+", session_id) else None


def delegate_evidence(raw_log: str) -> dict[str, Any]:
    matches = list(DELEGATE_REPLACE_RE.finditer(raw_log))
    replacement = matches[-1] if matches else None
    full_phrase = bool(FULL_DELEGATE_RE.search(raw_log))
    replaced = int(replacement.group(1)) if replacement else None
    total = int(replacement.group(2)) if replacement else None
    verified = replacement is not None and full_phrase and replaced == total
    return {
        "replaced_nodes": replaced,
        "total_nodes": total,
        "full_delegate": verified,
        "verification": "verified" if verified else "unverified",
        "full_delegate_phrase_found": full_phrase,
        "note": None if verified else (
            "No conclusive full-delegation evidence; this does not prove CPU fallback."
        ),
    }


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


def parse_uptime(value: str) -> int:
    return int(float(value.strip().split()[0]) * 1_000_000_000)


def thermal_dump(adb_command: list[str]) -> tuple[dict[str, Any], str]:
    script = (
        "echo __D1_UPTIME_BEFORE__; cat /proc/uptime; "
        "echo __D1_THERMAL__; dumpsys thermalservice; "
        "echo __D1_UPTIME_AFTER__; cat /proc/uptime"
    )
    result = subprocess.run(
        adb_command + ["shell", "sh", "-c", script],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=8,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "thermalservice failed")
    before_text, remainder = result.stdout.split("__D1_THERMAL__", 1)
    thermal_text, after_text = remainder.split("__D1_UPTIME_AFTER__", 1)
    before_ns = parse_uptime(before_text.split("__D1_UPTIME_BEFORE__", 1)[1])
    after_ns = parse_uptime(after_text)
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
    ) -> None:
        self.adb_command = adb_base(adb, serial)
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
        self.perfetto_device_path = "/data/local/tmp/d1check-diagnostic.perfetto-trace"
        self.capture_error: str | None = None
        self.capture_warnings: list[str] = []
        self.pending_raw_log: list[str] = []
        self.recovered_runner_files: set[str] = set()

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
                RUNNER_PACKAGE,
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
            f"/storage/emulated/0/Android/data/{RUNNER_PACKAGE}/files/runs/"
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
                "exec-out", "run-as", RUNNER_PACKAGE, "ls",
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
        config_device = "/data/local/tmp/d1check-gpu-diagnostic.pbtxt"
        subprocess.run(
            self.adb_command + ["push", str(self.perfetto_config), config_device], check=True
        )
        result = subprocess.run(
            self.adb_command
            + [
                "shell",
                "perfetto",
                "--txt",
                "-c",
                config_device,
                "-o",
                self.perfetto_device_path,
                "--background-wait",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.perfetto_pid = result.stdout.strip().splitlines()[-1]

    def stop_perfetto(self) -> None:
        if not self.perfetto_pid:
            return
        subprocess.run(self.adb_command + ["shell", "kill", "-INT", self.perfetto_pid])
        self.perfetto_pid = None
        time.sleep(1)
        if self.run_dir is not None:
            subprocess.run(
                self.adb_command
                + [
                    "pull",
                    self.perfetto_device_path,
                    str(self.run_dir / "diagnostics/d1check.perfetto-trace"),
                ]
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
                    self.capture_error = f"Perfetto start failed: {error}"
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
    thermal_samples = [event for event in thermal if event.get("event") == "sample"]
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
    galaxy_a24 = str(capture_metadata.get("device_model", "")).upper().startswith("SM-A245")
    formal_gpu_valid = (
        is_gpu
        and mode == "basic"
        and galaxy_a24
        and metadata_event.get("model_sha256") ==
            "D95B3C5EA86750CEF882FA867CA357DFE4D265D0B80B67E83277A0BDA310CFBB"
        and metadata_event.get("litert_version") == "1.4.2"
        and evidence["full_delegate"] is True
        and metadata_event.get("experiment_valid") is True
    )
    if mode == "diagnostic":
        analysis_warnings.append(
            f"Perfetto uses a {PERFETTO_BUFFER_KB} KiB ring buffer for up to "
            f"{MAX_DIAGNOSTIC_SECONDS}s; overwrite is possible"
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
        "load_start_mono_ns": load_start["mono_ns"],
        "load_end_mono_ns": load_end["mono_ns"],
        "run_start_mono_ns": run_start_ns,
        "run_stop_mono_ns": run_stop_ns,
        "run_envelope_validation": "pass",
        "delegate_evidence": evidence,
        "formal_gpu_valid": formal_gpu_valid if is_gpu else None,
        "analysis_warnings": analysis_warnings,
        "inference_latency": latency_stats(latencies),
    }
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
        args.diagnostic_perfetto, args.perfetto_config,
    ).run()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
