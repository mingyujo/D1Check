"""Q20 phone driver (2부): device check → thermal check → push inputs/models/manifest (SHA verified) → per backend (CPU → GPU → NPU):
logcat -c · logcat -v threadtime → am start -W → wait for summary.json (cap 15 min) → pull → force-stop (quality-runner only) → 60 s rest.

  set ANDROID_SERIAL=<ip:port>   (never written to any file; logs show <SERIAL>)
  py -3 -X utf8 s26/tools/quality20/q20_run.py --run-id q20_1009a --apk local_inputs/apk/quality-runner-debug_<sha8>.apk
      [--inputs <extracted zip dir>] [--original-model <path>] [--aot-model <path>] [--backends CPU,GPU,NPU] [--results <dir>]
      [--rest-s 60] [--timeout-s 900] [--skin-max 34.0] [--bat-max 32.0] [--skip-thermal] [--dry-run]

Rules (등록 §2 · prompt 1-4 · 2부):
  * device = SM-S942N; quality-runner installed and its APK SHA (pm path → sha256sum) == --apk / --apk-sha (1부 recorded value);
    com.example.d1check.npurunner and com.example.d1check.requestrunner are never touched
  * thermal check instead of start_gate_1005e.py (that gate requires plugged 0 and SKIN<=32/AP<=32/BAT<=30 and cannot be relaxed by flag):
    HAL SKIN <= 34.0 and BAT <= 32.0 (prompt 1-4), polled every 60 s up to 2 h, before every backend; plugged is recorded, not required
  * screen_off_timeout: read; if not 86400000 put 86400000 and record the original (never restored here — 2부 7 restores 600000 explicitly)
  * inputs: 20 × input.f32le + 2 models + q20_manifest.json pushed to /data/local/tmp/quality20 (skipped when sha256sum already matches),
    device SHA verified after every push; the manifest's model SHAs are the registered ones (6c7ab0a6… / 311e4aac…)
  * one app start per backend (intent d1_q20_manifest · d1_q20_backend · d1_q20_run_id); progress = `ls -l` of the app output folder every
    3 s (files are never opened while being written); done = summary.json present and no .part; app gone without summary = failed
  * logcat (no filter) may contain iccid/eSIM lines: results/ is git-ignored, never copy host/logcat_threadtime.txt to OneDrive or the repo
  * adb reconnect = disconnect/connect only (never kill-server)
Exit: 0 all requested backends produced summary.json · 1 some backend failed/timed out · 2 device/apk mismatch · 3 thermal wait exceeded.
Retry policy (2부 5) is the operator's: run again with --backends <one> and a NEW --run-id (the app refuses an existing run folder).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import q20_common as C  # noqa: E402

ADB = os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
_spec = importlib.util.spec_from_file_location("_q20_logger", C.REPO / "tools" / "d1_logger_v4.py")
LOGGER = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(LOGGER)


class Runner:
    def __init__(self, args):
        self.args = args
        self.dry = args.dry_run
        self.serial = os.environ.get("ANDROID_SERIAL", "")
        if not self.serial and not self.dry:
            raise SystemExit("ANDROID_SERIAL not set")
        self.run_id = args.run_id
        self.results = Path(args.results) if args.results else C.REPO / "results" / f"S26_Q20_{self.run_id}"
        self.host = self.results / "host"
        self.host.mkdir(parents=True, exist_ok=True)
        self.record: dict = dict(schema="s26-q20-run-record-v1", run_id=self.run_id, started_at=C.now_iso(), backends={}, commands=0,
                                 args={k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()})
        self.procs: dict[str, subprocess.Popen] = {}
        self.inputs_dir = Path(args.inputs)
        self.manifest = C.load_tensor_manifest(self.inputs_dir)

    # ------------------------------------------------------------------ plumbing
    def mask(self, text: str) -> str:
        return text.replace(self.serial, "<SERIAL>") if self.serial else text

    def log(self, msg: str):
        line = f"[{dt.datetime.now().isoformat(timespec='seconds')}] {self.mask(msg)}"
        print(line, flush=True)
        with open(self.host / "run_log.txt", "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def adb(self, *argv, timeout=60, check=False) -> subprocess.CompletedProcess:
        cmd = [ADB, "-s", self.serial, *argv]
        self.record["commands"] += 1
        if self.dry:
            print("DRY adb", self.mask(" ".join(argv)))
            return subprocess.CompletedProcess(cmd, 0, "", "")
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
        if check and r.returncode != 0:
            raise RuntimeError(f"adb {argv[0]} rc={r.returncode}: {self.mask(r.stderr.strip()[:200])}")
        return r

    def shell(self, command: str, timeout=60) -> str:
        return self.adb("shell", command, timeout=timeout).stdout

    def adb_ok(self) -> bool:
        if self.dry:
            return True
        for k in range(4):
            st = self.adb("get-state", timeout=15).stdout.strip()
            if st == "device":
                return True
            if k == 3:
                break
            self.log(f"adb state '{st}' -> disconnect/connect try {k + 1}")
            subprocess.run([ADB, "disconnect", self.serial], capture_output=True, timeout=30)
            time.sleep(2)
            subprocess.run([ADB, "connect", self.serial], capture_output=True, timeout=30)
            time.sleep(5 if k == 0 else 30)
        return False

    # ------------------------------------------------------------------ steps
    def check_device(self):
        model = self.shell("getprop ro.product.model").strip()
        if not self.dry and model != C.EXPECTED_MODEL:
            raise SystemExit(f"device model {model!r} != {C.EXPECTED_MODEL} (exit 2)")
        path = self.shell(f"pm path {C.APP_PACKAGE}").strip().replace("package:", "")
        if not self.dry and not path:
            raise SystemExit(f"{C.APP_PACKAGE} is not installed (exit 2)")
        apk_sha = self.shell(f"sha256sum {path}").split()[0] if (path and not self.dry) else "dry-run"
        expected = self.args.apk_sha or (C.sha256_file(self.args.apk) if self.args.apk else None)
        if not self.dry and expected and apk_sha != expected:
            raise SystemExit(f"installed APK sha {apk_sha} != expected {expected} (exit 2)")
        other = {p: self.shell(f"pm path {p}").strip().replace("package:", "") for p in (C.MEASURE_APP_PACKAGE, C.MIXREQ_APP_PACKAGE)}
        other_sha = {p: (self.shell(f"sha256sum {v}").split()[0] if v and not self.dry else "") for p, v in other.items()}
        self.record.update(device_model=model or "dry-run", apk_path=path or "dry-run", apk_sha256=apk_sha, apk_sha256_expected=expected,
                           other_apps_untouched=other_sha, build_display=self.shell("getprop ro.build.display.id").strip(),
                           sdk=self.shell("getprop ro.build.version.sdk").strip())
        self.log(f"device model={model or 'dry'} apk_sha256={apk_sha} expected={expected}")

    def read_state(self) -> dict:
        out = self.shell("dumpsys thermalservice; echo __B__; dumpsys battery; echo __S__; settings get system screen_off_timeout; "
                         "echo __W__; dumpsys power | grep -m1 mWakefulness=; dumpsys window | grep -m1 mCurrentFocus=", timeout=30)
        thermal, _, rest = out.partition("__B__")
        battery, _, rest = rest.partition("__S__")
        timeout_s, _, window = rest.partition("__W__")
        t = LOGGER.parse_thermalservice(thermal)
        lvl = re.search(r"^\s*level:\s*(\d+)", battery, re.M)
        plugged = bool(re.search(r"(AC|USB|Wireless|Dock) powered:\s*true", battery))
        status = re.search(r"^\s*status:\s*(\d+)", battery, re.M)
        temp = re.search(r"^\s*temperature:\s*(-?\d+)", battery, re.M)
        return dict(t=C.now_iso(), SKIN=t["SKIN"], AP=t["AP"], BAT=t["BAT"], PA=t["PA"], thermal_status=t["thermal_status"],
                    soc=int(lvl.group(1)) if lvl else None, plugged=plugged, charge_status=int(status.group(1)) if status else None,
                    battery_temp_deci=int(temp.group(1)) if temp else None, screen_off_timeout=timeout_s.strip(),
                    wakefulness=(re.search(r"mWakefulness=(\w+)", window) or [None, None])[1],
                    focus=(re.search(r"mCurrentFocus=(.*)", window) or [None, None])[1])

    def thermal_wait(self, label: str) -> bool:
        """HAL SKIN <= skin_max and BAT <= bat_max (prompt 1-4 — start_gate_1005e needs plugged 0 and cannot be relaxed). 60 s polls, 2 h cap."""
        if self.args.skip_thermal or self.dry:
            self.log(f"thermal check skipped ({label})")
            return True
        csv_path = self.host / "thermal_wait.csv"
        new = not csv_path.exists()
        t0 = time.time()
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["label", "t", "waited_s", "SKIN", "AP", "BAT", "thermal_status", "soc", "plugged", "pass"])
            while True:
                s = self.read_state()
                try:
                    ok = float(s["SKIN"]) <= self.args.skin_max and float(s["BAT"]) <= self.args.bat_max
                except ValueError:
                    ok = False
                w.writerow([label, s["t"], round(time.time() - t0), s["SKIN"], s["AP"], s["BAT"], s["thermal_status"], s["soc"], s["plugged"], ok])
                f.flush()
                self.log(f"thermal {label}: SKIN={s['SKIN']} AP={s['AP']} BAT={s['BAT']} status={s['thermal_status']} soc={s['soc']} plugged={s['plugged']} pass={ok}")
                if ok:
                    return True
                if time.time() - t0 > 7200:
                    return False
                time.sleep(60)

    def screen_timeout(self):
        s = self.read_state()
        self.record["phone_state_at_start"] = s
        if s["screen_off_timeout"] != "86400000" and not self.dry:
            self.shell("settings put system screen_off_timeout 86400000")
            self.record["screen_off_timeout_original"] = s["screen_off_timeout"]
            self.log(f"screen_off_timeout {s['screen_off_timeout']} -> 86400000 (NOT restored by this script; 2부 7 restores 600000)")
        else:
            self.record["screen_off_timeout_original"] = s["screen_off_timeout"]
        if s["wakefulness"] and s["wakefulness"] != "Awake":
            self.log(f"WARNING phone wakefulness={s['wakefulness']} — unlock the phone before the app runs")
        if s["focus"] and ("Keyguard" in s["focus"] or "keyguard" in s["focus"]):
            self.log(f"WARNING phone focus={s['focus']} (locked?) — unlock the phone before the app runs")

    def push_all(self):
        self.shell(f"mkdir -p {C.DEVICE_ROOT}/models {C.DEVICE_ROOT}/inputs")
        for spec in C.device_files(self.manifest, self.inputs_dir, Path(self.args.original_model), Path(self.args.aot_model)):
            host_sha = C.sha256_file(spec["host"])
            if host_sha != spec["sha256"]:
                raise SystemExit(f"host file {spec['name']} sha {host_sha} != registered {spec['sha256']}")
            present = self.shell(f"sha256sum {spec['device']} 2>/dev/null").split()
            if present and present[0] == spec["sha256"]:
                continue
            self.shell(f"mkdir -p {spec['device'].rsplit('/', 1)[0]}")
            self.log(f"push {spec['name']} -> {spec['device']}")
            self.adb("push", spec["host"], spec["device"], timeout=600, check=True)
            after = self.shell(f"sha256sum {spec['device']}").split()
            if not self.dry and (not after or after[0] != spec["sha256"]):
                raise RuntimeError(f"pushed {spec['name']} SHA mismatch")
        app_manifest = C.build_app_manifest(self.manifest, self.run_id, C.ORIGINAL_MODEL_SHA256, C.AOT_MODEL_SHA256)
        local = self.host / "q20_manifest.json"
        C.write_json(local, app_manifest)
        self.manifest_sha = C.sha256_file(local)
        device_manifest = f"{C.DEVICE_ROOT}/q20_manifest_{self.run_id}.json"
        self.adb("push", str(local), device_manifest, timeout=120, check=True)
        after = self.shell(f"sha256sum {device_manifest}").split()
        if not self.dry and (not after or after[0] != self.manifest_sha):
            raise RuntimeError("pushed manifest SHA mismatch")
        self.device_manifest = device_manifest
        self.record["manifest_sha256"] = self.manifest_sha
        self.log(f"manifest pushed sha256={self.manifest_sha} -> {device_manifest}")

    def backend_dirs(self, backend: str):
        folder = self.results / backend
        host = folder / "host"
        host.mkdir(parents=True, exist_ok=True)
        return folder, host, f"{C.APP_OUTPUT_DIR}/{self.run_id}/{backend}"

    def run_backend(self, backend: str) -> str:
        folder, host, device_out = self.backend_dirs(backend)
        info = dict(started_at=C.now_iso(), device_out=device_out)
        self.record["backends"][backend] = info
        if not self.dry and self.shell(f"ls -d {device_out} 2>/dev/null").strip():
            info["status"] = "device_folder_exists"
            self.log(f"{backend}: device folder exists ({device_out}) — use a new --run-id")
            return "exists"
        info["state_before"] = self.read_state()
        if not self.dry:
            self.adb("logcat", "-c", timeout=30)
            self.procs["logcat"] = subprocess.Popen([ADB, "-s", self.serial, "logcat", "-v", "threadtime"],
                                                    stdout=open(host / "logcat_threadtime.txt", "wb"), stderr=subprocess.DEVNULL)
        r = self.adb("shell", "am", "start", "-W", "-n", C.APP_ACTIVITY, "--es", "d1_q20_manifest", self.device_manifest,
                     "--es", "d1_q20_backend", backend, "--es", "d1_q20_run_id", self.run_id, timeout=60)
        info["am_start"] = dict(rc=r.returncode, out=r.stdout.strip()[:200])
        self.log(f"{backend}: am start rc={r.returncode} {r.stdout.strip()[:120]}")
        status = self.observe(device_out, info)
        info["status"] = status
        info["state_after"] = self.read_state()
        if not self.dry:
            self.adb("pull", device_out, str(folder / "device_pull"), timeout=600)
            pulled = folder / "device_pull"
            if pulled.is_dir() and not (folder / "device").exists():
                pulled.rename(folder / "device")
            self.adb("shell", "am", "force-stop", C.APP_PACKAGE, timeout=30)
            alive = self.shell(f"pidof {C.APP_PACKAGE}").strip()
            self.log(f"{backend}: force-stop {C.APP_PACKAGE}; alive_after='{alive}'")
            if "logcat" in self.procs:
                time.sleep(2)
                self.procs["logcat"].terminate()
                try:
                    self.procs["logcat"].wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.procs["logcat"].kill()
                self.procs.pop("logcat")
        info["ended_at"] = C.now_iso()
        summary = folder / "device" / "summary.json"
        info["summary_present"] = summary.is_file()
        if summary.is_file():
            s = C.read_json(summary)
            info["app_status"] = s.get("status")
            info["images_ok"] = s.get("images_ok")
            info["runtime_created"] = s.get("runtime_created")
            self.log(f"{backend}: app status={s.get('status')} images_ok={s.get('images_ok')} runtime_created={s.get('runtime_created')}")
        return status

    def observe(self, device_out: str, info: dict) -> str:
        started = time.time()
        last = ""
        while True:
            if not self.adb_ok():
                info["adb_lost"] = True
                return "adb_lost"
            text = self.shell(f"ls -l {device_out} 2>/dev/null")
            if text != last:
                last = text
                self.log("listing: " + " ".join(l.split()[-1] for l in text.splitlines() if l.strip() and not l.startswith("total"))[-300:])
            if "summary.json" in text and "summary.json.part" not in text:
                return "done"
            if self.dry:
                return "done"
            alive = self.shell(f"pidof {C.APP_PACKAGE}").strip()
            if not alive and time.time() - started > 15:
                return "app_gone"
            if time.time() - started > self.args.timeout_s:
                self.adb("shell", "am", "force-stop", C.APP_PACKAGE, timeout=30)
                return "timeout"
            time.sleep(3.0)

    def run(self) -> int:
        try:
            if not self.adb_ok():
                raise SystemExit("adb not connected (exit 2)")
            self.check_device()
            self.screen_timeout()
            self.push_all()
            rc = 0
            backends = [b.strip().upper() for b in self.args.backends.split(",") if b.strip()]
            for b in backends:
                if b not in C.BACKENDS:
                    raise SystemExit(f"unknown backend {b}")
            for i, backend in enumerate(backends):
                if i > 0 and not self.dry:
                    self.log(f"rest {self.args.rest_s} s before {backend}")
                    time.sleep(self.args.rest_s)
                if not self.thermal_wait(backend):
                    self.log(f"{backend}: thermal wait exceeded 2 h (exit 3)")
                    self.record["backends"].setdefault(backend, {})["status"] = "thermal_wait_exceeded"
                    rc = 3
                    break
                status = self.run_backend(backend)
                if status != "done":
                    rc = rc or 1
            self.record["ended_at"] = C.now_iso()
            self.record["exit_code"] = rc
            return rc
        finally:
            for p in self.procs.values():
                try:
                    p.terminate()
                except Exception:
                    pass
            if not self.dry:
                self.adb("shell", "am", "force-stop", C.APP_PACKAGE, timeout=30)
            C.write_json(self.host / "run_record.json", self.record)
            self.log("run_record.json written")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--apk", help="local APK copy (expected SHA computed from it)")
    ap.add_argument("--apk-sha", help="expected installed APK SHA-256 (alternative to --apk)")
    ap.add_argument("--inputs", default=str(C.DEFAULT_INPUTS_DIR))
    ap.add_argument("--original-model", default=str(C.DEFAULT_ORIGINAL_MODEL))
    ap.add_argument("--aot-model", default=str(C.DEFAULT_AOT_MODEL))
    ap.add_argument("--backends", default="CPU,GPU,NPU")
    ap.add_argument("--results")
    ap.add_argument("--rest-s", type=int, default=60)
    ap.add_argument("--timeout-s", type=int, default=900)
    ap.add_argument("--skin-max", type=float, default=34.0)
    ap.add_argument("--bat-max", type=float, default=32.0)
    ap.add_argument("--skip-thermal", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", args.run_id):
        raise SystemExit("run_id must match [A-Za-z0-9_.-]{1,64}")
    return Runner(args).run()


if __name__ == "__main__":
    sys.exit(main())
