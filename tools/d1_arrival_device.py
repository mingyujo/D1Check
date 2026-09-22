"""Bounded, no-retry A24 runner for a separately approved arrival pilot."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import time
from pathlib import Path

from tools import d1_arrival_plan as p
from tools.d1_telemetry_v4 import delegate_proof

PACKAGE = "com.example.d1check.benchmarkrunner.modelprobe"
ACTIVITY = "com.example.d1check.benchmarkrunner.ArrivalSchedulerActivity"
ACTION = "com.example.d1check.benchmarkrunner.action.ARRIVAL_SCHEDULER"


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def write_new(path, value):
    path = Path(path)
    with path.open("xb") as stream:
        stream.write(p.canonical(value))


class Device:
    def __init__(self, adb, serial):
        self.adb, self.serial = str(adb), serial

    def call(self, *args, timeout=30, check=True):
        cmd = [self.adb] + (["-s", self.serial] if self.serial else []) + list(map(str, args))
        completed = subprocess.run(cmd, capture_output=True, timeout=timeout)
        if check and completed.returncode:
            raise RuntimeError(f"ADB failed {cmd}: {completed.stderr.decode(errors='replace')[:500]}")
        return completed

    def identify(self, fingerprint):
        lines = self.call("devices", "-l").stdout.decode().splitlines()[1:]
        online = [row.split() for row in lines if row.strip() and len(row.split()) >= 2 and row.split()[1] == "device"]
        if len(online) != 1 or (self.serial and online[0][0] != self.serial):
            raise RuntimeError("exactly one selected online device required")
        self.serial = online[0][0]
        model = self.call("shell", "getprop", "ro.product.model").stdout.decode().strip()
        actual = self.call("shell", "getprop", "ro.build.fingerprint").stdout.decode().strip()
        if model != "SM-A245N" or actual != fingerprint:
            raise RuntimeError(f"unexpected device: {model}, {actual}")
        return dict(serial=self.serial, model=model, fingerprint=actual)


def recover(device, sid, folder):
    """Read existing device output only; never launches the Activity."""
    remote = f"files/arrival-scheduler-v1/{sid}"
    listing = device.call("shell", "run-as", PACKAGE, "ls", remote, check=False)
    if listing.returncode:
        return dict(status="device_output_missing", files=[])
    folder.mkdir(parents=True, exist_ok=True)
    names = listing.stdout.decode(errors="replace").splitlines()
    copied = []
    for name in names:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,126}", name) or name.endswith(".part"):
            continue
        target = folder / name
        data = device.call("exec-out", "run-as", PACKAGE, "cat", remote + "/" + name, timeout=45).stdout
        if target.exists() and target.read_bytes() != data:
            raise RuntimeError(f"local artifact conflict: {target}")
        if not target.exists():
            target.write_bytes(data)
        copied.append(dict(name=name, bytes=len(data), sha256=p.digest(target)))
    return dict(status="recovered", files=copied)


def run(plan_file, apk, adb, serial, output, approved_cap, expected_plan_sha256):
    plan_file, apk, output = Path(plan_file), Path(apk), Path(output)
    if p.digest(plan_file) != expected_plan_sha256:
        raise RuntimeError("frozen arrival plan SHA-256 mismatch")
    plan = p.read(plan_file)
    p.validate(plan, plan_file.parent)
    if plan["session_cap"] != approved_cap:
        raise RuntimeError("approved session cap does not match the frozen plan")
    if p.digest(apk) != plan["apk_sha256"]:
        raise RuntimeError("APK changed after plan freeze")
    device = Device(adb, serial)
    identity = device.identify(plan["device_fingerprint"])
    output.mkdir(parents=True, exist_ok=True)
    for entry in plan["entries"]:
        folder = output / f"{entry['index']:02d}_{entry['session_id']}"
        if folder.exists() and not (folder / "validated.json").exists():
            raise RuntimeError(f"prior attempt requires recovery, no automatic retry: {folder}")
    installed = device.call("shell", "pm", "path", PACKAGE, check=False)
    if installed.returncode == 0 and installed.stdout.strip():
        # -r retains app data. This runner never clears data or uninstalls.
        pass
    device.call("install", "-r", apk, timeout=120)
    identity_path = output / "device_identity.json"
    if identity_path.exists():
        if p.read(identity_path) != identity:
            raise RuntimeError("resume device identity changed")
    else:
        write_new(identity_path, identity)
    block_temperatures = {}
    for prior in plan["entries"]:
        prior_folder = output / f"{prior['index']:02d}_{prior['session_id']}"
        battery_path = prior_folder / "before_battery.txt"
        if (prior_folder / "validated.json").exists() and battery_path.exists():
            match = re.search(r"temperature:\s*(\d+)", battery_path.read_text(encoding="utf-8"))
            if match:
                block_temperatures.setdefault(prior["pair_id"], int(match.group(1)))
    for entry in plan["entries"]:
        sid = entry["session_id"]
        folder = output / f"{entry['index']:02d}_{sid}"
        if (folder / "validated.json").exists():
            continue
        if folder.exists():
            raise RuntimeError(f"prior attempt requires recovery, no automatic retry: {folder}")
        folder.mkdir()
        write_new(folder / "attempt.json", dict(status="started", utc=utc(), entry=entry,
                                                apk_sha256=plan["apk_sha256"], device=identity))
        remote_input = f"files/arrival-scheduler-inputs/{sid}"
        remote_output = f"files/arrival-scheduler-v1/{sid}"
        shared = f"/data/local/tmp/d1check-arrival/{sid}"
        try:
            thermal = device.call("shell", "dumpsys", "thermalservice").stdout.decode(errors="replace")
            (folder / "before_thermal.txt").write_text(thermal, encoding="utf-8")
            if not re.search(r"Thermal Status:\s*0\b", thermal):
                raise RuntimeError("thermal gate outside zero")
            battery = device.call("shell", "dumpsys", "battery").stdout.decode(errors="replace")
            (folder / "before_battery.txt").write_text(battery, encoding="utf-8")
            match = re.search(r"temperature:\s*(\d+)", battery)
            if not match:
                raise RuntimeError("battery temperature unavailable")
            temperature = int(match.group(1))
            reference = block_temperatures.setdefault(entry["pair_id"], temperature)
            if abs(temperature - reference) > 10:
                raise RuntimeError("paired block start temperature differs by more than 1 C")
            device.call("shell", "am", "force-stop", PACKAGE)
            for path, prefix in ((remote_input, ("run-as", PACKAGE)),
                                 (remote_output, ("run-as", PACKAGE)), (shared, ())):
                if device.call("shell", *prefix, "test", "-e", path, check=False).returncode == 0:
                    raise RuntimeError(f"stale device path: {path}")
            device.call("shell", "mkdir", "-p", shared)
            device.call("shell", "run-as", PACKAGE, "mkdir", "-p", remote_input)
            manifest = plan_file.parent / entry["manifest"]
            sources = {name: info["path"] for name, info in plan["source_files"].items()}
            sources["manifest.json"] = manifest
            for name, source in sorted(sources.items()):
                source = Path(source)
                expected = p.digest(source)
                device.call("push", source, shared + "/" + name + ".part", timeout=90)
                device.call("shell", "run-as", PACKAGE, "cp", shared + "/" + name + ".part",
                            remote_input + "/" + name + ".part")
                actual = device.call("shell", "run-as", PACKAGE, "sha256sum",
                                     remote_input + "/" + name + ".part").stdout.decode().split()[0]
                if actual != expected:
                    raise RuntimeError(f"staged file hash mismatch: {name}")
                device.call("shell", "run-as", PACKAGE, "mv", remote_input + "/" + name + ".part",
                            remote_input + "/" + name)
            device.call("shell", "am", "start", "-W", "-n", PACKAGE + "/" + ACTIVITY,
                        "-a", ACTION, "--es", "session_id", sid)
            pid = device.call("shell", "pidof", PACKAGE + ":model_probe").stdout.decode().strip()
            if not re.fullmatch(r"\d+", pid):
                raise RuntimeError("model probe process ID unavailable")
            deadline = time.monotonic() + 125
            while time.monotonic() < deadline:
                if device.call("shell", "run-as", PACKAGE, "test", "-s",
                               remote_output + "/cleanup.json", check=False).returncode == 0:
                    break
                if device.call("shell", "run-as", PACKAGE, "test", "-s",
                               remote_output + "/failure.json", check=False).returncode == 0:
                    break
                time.sleep(1)
            result = recover(device, sid, folder / "artifacts")
            summary_file = folder / "artifacts" / "summary.json"
            if not summary_file.exists():
                raise RuntimeError("session did not finalize within bound")
            summary = p.read(summary_file)
            if summary["session_id"] != sid or summary["request_count"] != entry["request_count"]:
                raise RuntimeError("summary identity/count mismatch")
            if not (folder / "artifacts" / "requests.json").exists():
                raise RuntimeError("request ledger missing")
            cleanup = p.read(folder / "artifacts" / "cleanup.json")
            if cleanup["status"] != "completed":
                raise RuntimeError("runtime cleanup failed")
            manifest_data = p.read(manifest)
            rows = p.read(folder / "artifacts" / "requests.json")
            if len(rows) != entry["request_count"] or p.digest(folder / "artifacts" / "manifest.json") != entry["manifest_sha256"]:
                raise RuntimeError("artifact count or manifest mismatch")
            for row in rows:
                event_file = folder / "artifacts" / (row["request_id"] + ".event.json")
                if not event_file.exists() or p.read(event_file)["request_id"] != row["request_id"]:
                    raise RuntimeError("request event missing or mismatched")
                if row["terminal_status"] == "succeeded":
                    payload = folder / "artifacts" / (row["request_id"] + ".result.json")
                    if not payload.exists() or p.digest(payload) != row["result_sha256"]:
                        raise RuntimeError("request result missing or mismatched")
            log = device.call("logcat", "-d", "-v", "threadtime", "--pid=" + pid,
                              "-s", "D1ARRIVAL:I", "tflite:I").stdout.decode(errors="replace")
            (folder / "delegate_log.txt").write_text(log, encoding="utf-8")
            gpu = delegate_proof(manifest_data, log)
            write_new(folder / "validated.json", dict(utc=utc(), summary=summary, recovery=result,
                                                      gpu=gpu))
            if summary["status"] != "completed" or summary["arrival_lag_exceeded"]:
                raise RuntimeError("quality or completion gate failed; preserve and stop")
        except BaseException as error:
            (folder / "error.json").write_bytes(p.canonical(dict(utc=utc(), error=repr(error))))
            try:
                recover(device, sid, folder / "partial")
            except BaseException as recovery_error:
                (folder / "recovery_error.txt").write_text(repr(recovery_error), encoding="utf-8")
            raise
        finally:
            try:
                device.call("shell", "am", "force-stop", PACKAGE)
                (folder / "after_thermal.txt").write_bytes(
                    device.call("shell", "dumpsys", "thermalservice").stdout)
            except BaseException as cleanup_error:
                (folder / "cleanup_error.txt").write_text(repr(cleanup_error), encoding="utf-8")
        if entry["index"] < len(plan["entries"]) - 1:
            time.sleep(plan["cool_down_seconds"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("preflight")
    pre.add_argument("--plan", type=Path, required=True)
    pre.add_argument("--adb", type=Path, required=True)
    pre.add_argument("--serial")
    run_parser = sub.add_parser("run")
    for argument in ("--plan", "--apk", "--adb", "--output"):
        run_parser.add_argument(argument, type=Path, required=True)
    run_parser.add_argument("--serial")
    run_parser.add_argument("--approved-cap", type=int, required=True)
    run_parser.add_argument("--expected-plan-sha256", required=True)
    rec = sub.add_parser("recover")
    rec.add_argument("--adb", type=Path, required=True)
    rec.add_argument("--serial", required=True)
    rec.add_argument("--session-id", required=True)
    rec.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "preflight":
        plan = p.read(args.plan)
        p.validate(plan, args.plan.parent)
        print(json.dumps(Device(args.adb, args.serial).identify(plan["device_fingerprint"]), indent=2))
    elif args.command == "run":
        run(args.plan, args.apk, args.adb, args.serial, args.output,
            args.approved_cap, args.expected_plan_sha256)
    else:
        print(json.dumps(recover(Device(args.adb, args.serial), args.session_id, args.output), indent=2))


if __name__ == "__main__":
    main()
