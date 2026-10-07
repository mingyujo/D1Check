"""One request-runner session on the phone (R2) — device check → gate → settings → push → logcat → start → observe → pull → validate.

  set ANDROID_SERIAL=<ip:port>   (never written to any file; logs show <SERIAL>)
  py -3 s26/tools/mixreq/mixreq_session.py --plan <plan_dir> --index <0..15> [--attempt 1] --results <results_root>
      [--smoke S1_warmup_only_blockN|S2_<policy>] [--dry-run] [--skip-gate] [--min-gap-s 90] [--stall-s 600]
      [--allow-settings-mismatch]

Rules implemented (등록 §3 · §4 · prompt 4부):
  * device = SM-S942N; request-runner installed (APK SHA recorded); the measurement app com.example.d1check.npurunner is never touched
  * gate = s26/tools/night_1005e/start_gate_1005e.py (plugged 0 · SOC 30~100 · SKIN<=32 · AP<=32 · BAT<=30, exit 2 = blocked) AND >= 90 s since
    the previous session end (results_root/last_session_end.txt)
  * phone settings read-only check: airplane 1 · zen_mode != 0 · brightness manual + 0 (mismatch = refuse unless --allow-settings-mismatch)
  * screen_off_timeout 86400000 for the session, restored at the end / on any exit path (original value in host/session_log.json)
  * adb logcat -c then `adb logcat -v threadtime` (no tag filter) into host/logcat_threadtime.txt — iccid/eSIM lines may be in it: never commit/copy
  * host HAL temperature sampler 2 s (tools/d1_logger_v4.parse_thermalservice, "Current temperatures from HAL" only) + device boottime bracket
  * skin watch (skin_watch_mixreq.py, SKIN >= 45 -> force-stop request-runner) + phone watch (phone_watch_mixreq.ps1) as subprocesses
  * progress = `ls -l` of the app output folder every 1 s (sizes/times only, files are never opened while being written);
    warmup.ready.json -> pull warmup.json -> §4-6 (used GPU key vs CPU #1) -> arm with the manifest SHA (or do not arm -> app gate timeout)
  * stall = listing unchanged for --stall-s (600) -> force-stop request-runner, exit 4; adb reconnect = disconnect/connect up to 3 (never kill-server)
  * attempt folders: device <sid>/a<attempt> and host results\\S26_MIXREQ_<i>_<policy>_a<attempt>\\ must not exist (exit 5)
Exit codes: 0 valid · 1 completed but invalid / failed · 2 gate blocked (thermal) · 3 settings or device mismatch · 4 stall · 5 folder exists · 6 gate blocked (SOC/plugged)
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
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402
import mixreq_validate as V  # noqa: E402
import policy_ref  # noqa: E402

ADB = os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
GATE_PY = REPO / "s26" / "tools" / "night_1005e" / "start_gate_1005e.py"
SKIN_WATCH_PY = HERE / "skin_watch_mixreq.py"
PHONE_WATCH_PS1 = HERE / "phone_watch_mixreq.ps1"
_spec = importlib.util.spec_from_file_location("_mixreq_logger", REPO / "tools" / "d1_logger_v4.py")
LOGGER = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(LOGGER)
EXPECTED_MODEL = "SM-S942N"


class Session:
    def __init__(self, args):
        self.args = args
        self.serial = os.environ.get("ANDROID_SERIAL", "")
        self.dry = args.dry_run
        if not self.serial and not self.dry:
            raise SystemExit("ANDROID_SERIAL not set")
        self.plan_dir = args.plan
        self.plan = C.read_json(self.plan_dir / "plan.json")
        self.device_inputs = C.read_json(self.plan_dir / "device_inputs.json")
        if args.smoke:
            entry = next(s for s in self.plan["smoke"] if s["name"] == args.smoke)
            label = args.smoke
        else:
            entry = next(s for s in self.plan["sessions"] if s["index"] == args.index)
            label = f"{entry['index']:02d}_{entry['policy']}"
        self.entry = entry
        manifest = C.read_json(self.plan_dir / entry["manifest"])
        if args.attempt != 1:
            manifest["attempt"] = args.attempt
        self.manifest = manifest
        self.manifest_bytes = C.canonical_json(manifest)
        self.manifest_sha = C.sha256_bytes(self.manifest_bytes)
        self.sid = manifest["session_id"]
        self.attempt = manifest["attempt"]
        self.results_root = args.results
        self.folder = self.results_root / (f"S26_MIXREQ_{label}_a{self.attempt}" if not args.smoke else f"S26_MIXREQ_SMOKE_{label}_a{self.attempt}")
        self.host = self.folder / "host"
        self.device_session_dir = f"{C.DEVICE_SESSION_DIR}/{self.sid}/a{self.attempt}"
        self.device_out = f"{C.APP_OUTPUT_DIR}/{self.sid}/a{self.attempt}"
        self.log_entries: list[str] = []
        self.session_log: dict = dict(session_id=self.sid, attempt=self.attempt, label=label, manifest_sha256=self.manifest_sha,
                                      commands=[], events=[])
        self.procs: dict[str, subprocess.Popen] = {}
        self.original_timeout = None

    # ------------------------------------------------------------------ helpers
    def mask(self, text: str) -> str:
        return text.replace(self.serial, "<SERIAL>") if self.serial else text

    def log(self, msg: str):
        line = f"[{dt.datetime.now().isoformat(timespec='seconds')}] {self.mask(msg)}"
        print(line, flush=True)
        self.log_entries.append(line)
        if self.host.exists():
            with open(self.host / "session_log.txt", "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def adb(self, *argv, timeout=60, check=False) -> subprocess.CompletedProcess:
        cmd = [ADB, "-s", self.serial, *argv]
        self.session_log["commands"].append(dict(t=time.time(), cmd=self.mask(" ".join(argv))))
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
        if not self.dry and model != EXPECTED_MODEL:
            raise SystemExit(f"device model {model!r} != {EXPECTED_MODEL} (exit 3)")
        path = self.shell(f"pm path {C.APP_PACKAGE}").strip().replace("package:", "")
        if not self.dry and not path:
            raise SystemExit(f"{C.APP_PACKAGE} is not installed (exit 3)")
        apk_sha = self.shell(f"sha256sum {path}").split()[0] if (path and not self.dry) else "dry-run"
        self.session_log.update(device_model=model or "dry-run", apk_path=path or "dry-run", apk_sha256=apk_sha)
        self.log(f"device model={model or 'dry'} apk_sha256={apk_sha}")
        if not self.dry:
            exists_dev = self.shell(f"ls -d {self.device_out} 2>/dev/null").strip()
            if exists_dev:
                raise SystemExit(f"device attempt folder exists: {self.device_out} (exit 5)")

    def gate(self) -> int:
        marker = self.results_root / "last_session_end.txt"
        if marker.is_file():
            last = float(marker.read_text().strip() or 0)
            wait = self.args.min_gap_s - (time.time() - last)
            if wait > 0 and not self.dry:
                self.log(f"inter-session gap: sleeping {wait:.0f} s (min {self.args.min_gap_s})")
                time.sleep(wait)
        if self.args.skip_gate or self.dry:
            self.log("gate skipped (dry-run/--skip-gate)")
            return 0
        gate_csv = self.results_root / "gate_log_mixreq.csv"
        r = subprocess.run([sys.executable, "-X", "utf8", str(GATE_PY), self.serial, self.folder.name, str(gate_csv)], capture_output=True, text=True, timeout=7200)
        last_line = (r.stdout.strip().splitlines() or [""])[-1]
        self.log(f"gate rc={r.returncode} last={last_line}")
        self.session_log["gate"] = dict(rc=r.returncode, last=last_line)
        return r.returncode

    def check_settings(self):
        values = dict(airplane=self.shell("settings get global airplane_mode_on").strip(),
                      zen_mode=self.shell("settings get global zen_mode").strip(),
                      brightness_mode=self.shell("settings get system screen_brightness_mode").strip(),
                      brightness=self.shell("settings get system screen_brightness").strip(),
                      screen_off_timeout=self.shell("settings get system screen_off_timeout").strip())
        self.session_log["settings_before"] = values
        self.log(f"settings {values}")
        if self.dry:
            return
        ok = values["airplane"] == "1" and values["zen_mode"] not in ("0", "") and values["brightness_mode"] == "0" and values["brightness"] == "0"
        if not ok and not self.args.allow_settings_mismatch:
            raise SystemExit("phone settings mismatch (airplane/dnd/brightness) — refuse (exit 3)")
        self.original_timeout = values["screen_off_timeout"]
        self.shell("settings put system screen_off_timeout 86400000")
        self.log("screen_off_timeout -> 86400000")

    def restore_settings(self):
        if self.original_timeout and not self.dry:
            self.shell(f"settings put system screen_off_timeout {self.original_timeout}")
            self.log(f"screen_off_timeout restored -> {self.original_timeout}")

    def push_inputs(self):
        self.shell(f"mkdir -p {C.DEVICE_INPUT_DIR} {self.device_session_dir}")
        for name, spec in self.device_inputs.items():
            present = self.shell(f"sha256sum {spec['device_path']} 2>/dev/null").split()
            if present and present[0] == spec["sha256"]:
                self.log(f"input {name} present (sha ok)")
                continue
            self.log(f"push {name} -> {spec['device_path']}")
            self.adb("push", spec["host_path"], spec["device_path"], timeout=600, check=True)
            after = self.shell(f"sha256sum {spec['device_path']}").split()
            if not self.dry and (not after or after[0] != spec["sha256"]):
                raise RuntimeError(f"pushed {name} SHA mismatch")
        local = self.host / "manifest_pushed.json"
        local.write_bytes(self.manifest_bytes)
        self.adb("push", str(local), f"{self.device_session_dir}/manifest.json", timeout=120, check=True)
        after = self.shell(f"sha256sum {self.device_session_dir}/manifest.json").split()
        if not self.dry and (not after or after[0] != self.manifest_sha):
            raise RuntimeError("pushed manifest SHA mismatch")

    def start_background(self):
        if self.dry:
            self.log("DRY: logcat -c; logcat -v threadtime > host/logcat_threadtime.txt; hal sampler; skin watch; phone watch")
            return
        self.adb("logcat", "-c", timeout=30)
        self.procs["logcat"] = subprocess.Popen([ADB, "-s", self.serial, "logcat", "-v", "threadtime"],
                                                stdout=open(self.host / "logcat_threadtime.txt", "wb"), stderr=subprocess.DEVNULL)
        self.procs["skin"] = subprocess.Popen([sys.executable, "-X", "utf8", str(SKIN_WATCH_PY), self.serial, str(self.host / "skin_watch.csv"), str(self.host / "watch.stop")])
        self.procs["phone"] = subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(PHONE_WATCH_PS1),
                                                "-OutCsv", str(self.host / "phone_watch.csv"), "-StopFile", str(self.host / "watch.stop")])
        self.hal_csv = open(self.host / "hal.csv", "w", encoding="utf-8", newline="")
        self.hal_writer = csv.writer(self.hal_csv)
        self.hal_writer.writerow(["pc_ms", "device_boottime_s", "SKIN", "AP", "BAT", "PA", "thermal_status"])
        self.next_hal = time.time()

    def sample_hal(self):
        if self.dry or time.time() < self.next_hal:
            return
        self.next_hal += 2.0
        try:
            out = self.shell("dumpsys thermalservice; echo __UPTIME__; cat /proc/uptime", timeout=20)
            thermal, _, up = out.partition("__UPTIME__")
            t = LOGGER.parse_thermalservice(thermal)
            boot = up.split()[0] if up.split() else ""
            self.hal_writer.writerow([int(time.time() * 1000), boot, t["SKIN"], t["AP"], t["BAT"], t["PA"], t["thermal_status"]])
            self.hal_csv.flush()
        except Exception as e:  # keep observing
            self.log(f"hal sample error {e!r}")

    def stop_background(self):
        (self.host / "watch.stop").write_text("stop")
        for name in ("skin", "phone"):
            p = self.procs.get(name)
            if p:
                try:
                    p.wait(timeout=40)
                except subprocess.TimeoutExpired:
                    p.kill()
        if "logcat" in self.procs:
            time.sleep(3)  # let the tail of the log drain
            self.procs["logcat"].terminate()
            try:
                self.procs["logcat"].wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.procs["logcat"].kill()
        if hasattr(self, "hal_csv"):
            self.hal_csv.close()

    def start_app(self):
        command_id = str(uuid.uuid4())
        self.session_log["command_id"] = command_id
        self.session_log["start_time"] = dt.datetime.now().isoformat(timespec="seconds")
        r = self.adb("shell", "am", "start", "-W", "-n", C.APP_ACTIVITY, "--es", "d1_session_manifest", f"{self.device_session_dir}/manifest.json",
                     "--es", "d1_session_id", self.sid, "--es", "d1_command_id", command_id, timeout=60)
        self.log(f"am start rc={r.returncode} {r.stdout.strip()[:120]}")

    def listing(self) -> str:
        return self.shell(f"ls -l {self.device_out} 2>/dev/null")

    def warmup_gate(self) -> bool:
        """Pull warmup.json, judge §4-6 for the used accelerated key (GPU) vs CPU #1 (NPU -> §4-N recorded only), arm or not."""
        local = self.host / "warmup_pulled.json"
        self.adb("pull", f"{self.device_out}/warmup.json", str(local), timeout=60, check=True)
        if self.dry:
            return True
        warmups = C.read_json(local)
        by_key: dict[str, list] = {}
        for w in warmups:
            by_key.setdefault(w["key"], []).append(w)
        used = policy_ref.USED_KEYS[self.manifest["policy"]]
        verdict = dict(used=list(used), checks={})
        ok = True
        cpu_cls = sorted(by_key.get("classification_CPU", []), key=lambda w: w["index"])
        cpu_det = sorted(by_key.get("detection_CPU", []), key=lambda w: w["index"])
        for key in used:
            task, lane = key.rsplit("_", 1)
            entries = sorted(by_key.get(key, []), key=lambda w: w["index"])
            ref_list = cpu_cls if task == "classification" else cpu_det
            if lane == "NPU":
                verdict["checks"][key] = "NPU: §4-N contract (not a gate condition)"
                continue
            if len(entries) != 2 or not ref_list:
                verdict["checks"][key] = "warmups missing"
                ok = False
                continue
            cmps = [V.compare_results(task, ref_list[0]["result"]["results"], e["result"]["results"]) for e in entries]
            if lane == "CPU":
                cmps = cmps[1:]
            passed = all(c["passed"] for c in cmps)
            verdict["checks"][key] = "PASS" if passed else "FAIL"
            ok = ok and passed
        if self.manifest["block"] == "N":
            try:
                data = dict(manifest=self.manifest, warmup=warmups)
                verdict["npu_contract_first_look"] = V.npu_contract(data)
            except Exception as e:  # recorded only
                verdict["npu_contract_first_look"] = f"error {e!r}"
        self.session_log["warmup_gate"] = verdict
        C.write_json(self.host / "warmup_gate.json", verdict)
        self.log(f"warmup gate {verdict['checks']} -> {'ARM' if ok else 'NOT ARMED (app will time out)'}")
        if ok:
            self.shell(f"echo {self.manifest_sha} > {self.device_session_dir}/warmup.arm")
        return ok

    def sample_top(self):
        """Observation only (조민규 10/8 12번: configured threads vs observed): `top -H` of the app process every 3 s until warmup ends."""
        if self.dry or time.time() < getattr(self, "next_top", 0):
            return
        self.next_top = time.time() + 3.0
        try:
            pid = self.shell(f"pidof {C.APP_PACKAGE}").strip()
            if pid:
                out = self.shell(f"top -H -b -n 1 -p {pid}", timeout=20)
                with open(self.host / "top_h.txt", "a", encoding="utf-8") as f:
                    f.write(f"### {dt.datetime.now().isoformat(timespec='seconds')} pid={pid}\n{out}\n")
        except Exception as e:
            self.log(f"top sample error {e!r}")

    def observe(self) -> str:
        """Returns 'done' | 'stall' | 'lost'."""
        last_listing, last_change = "", time.time()
        armed_checked = False
        started = time.time()
        while True:
            if not self.adb_ok():
                return "lost"
            text = self.listing()
            if text != last_listing:
                last_listing, last_change = text, time.time()
            if "cleanup.json" in text and "cleanup.json.part" not in text:
                return "done"
            if not armed_checked and "warmup.json" not in text:
                self.sample_top()
            if not armed_checked and "warmup.ready.json" in text and "warmup.json" in text and "warmup.json.part" not in text:
                armed_checked = True
                self.warmup_gate()
            if time.time() - last_change > self.args.stall_s:
                return "stall"
            if time.time() - started > 1200:  # absolute cap: setup 180 + gate 60 + 30 + 120 + 30 + 60 = 480 s nominal
                return "stall"
            self.sample_hal()
            if self.dry:
                return "done"
            time.sleep(1.0)

    def pull_and_stop(self):
        self.adb("pull", self.device_out, str(self.folder / "device_pull"), timeout=600)
        pulled = self.folder / "device_pull"
        if pulled.is_dir() and not (self.folder / "device").exists():
            inner = pulled / f"a{self.attempt}"
            (inner if inner.is_dir() else pulled).rename(self.folder / "device")
        self.adb("shell", "am", "force-stop", C.APP_PACKAGE, timeout=30)
        alive = self.shell(f"pidof {C.APP_PACKAGE}").strip()
        self.log(f"force-stop request-runner; alive_after='{alive}'")
        self.session_log["end_time"] = dt.datetime.now().isoformat(timespec="seconds")

    def run(self) -> int:
        if self.folder.exists():
            print(self.mask(f"host result folder exists: {self.folder} -> refuse to start (exit 5)"), flush=True)
            return 5
        self.folder.mkdir(parents=True, exist_ok=False)
        self.host.mkdir()
        try:
            self.log(f"SESSION START sid={self.sid} attempt={self.attempt} policy={self.manifest['policy']} block={self.manifest['block']} manifest_sha={self.manifest_sha}")
            if not self.adb_ok():
                raise SystemExit("adb not connected (exit 3)")
            self.check_device()
            grc = self.gate()
            if grc == 2:
                self.log("GATE BLOCKED (SOC/plugged) -> exit 6")
                return 6
            if grc != 0:
                self.log(f"GATE rc={grc} -> exit 2")
                return 2
            self.check_settings()
            self.push_inputs()
            self.start_background()
            self.start_app()
            result = self.observe()
            self.log(f"observe -> {result}")
            if result != "done":
                self.adb("shell", "am", "force-stop", C.APP_PACKAGE, timeout=30)
                self.session_log["stall"] = result
            self.pull_and_stop()
            self.stop_background()
            self.restore_settings()
            (self.results_root / "last_session_end.txt").write_text(str(time.time()))
            C.write_json(self.host / "session_log.json", self.session_log)
            if result != "done":
                return 4
            if self.dry:
                return 0
            validated, contract = V.validate(self.folder, None, self.host / "logcat_threadtime.txt", self.host / "skin_watch.csv", self.host / "phone_watch.csv", False)
            C.write_json(self.folder / "validated.json", validated)
            if contract is not None:
                C.write_json(self.folder / "npu_contract.json", contract)
            self.log(f"VALID={validated['eligible']} reasons={validated['reasons']} npu_contract={None if contract is None else contract.get('passed')}")
            return 0 if validated["eligible"] else 1
        finally:
            try:
                self.stop_background()
            except Exception:
                pass
            self.restore_settings()
            C.write_json(self.host / "session_log.json", self.session_log)
            self.log("SESSION END")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", required=True, type=Path)
    ap.add_argument("--index", type=int)
    ap.add_argument("--smoke")
    ap.add_argument("--attempt", type=int, default=1, choices=(1, 2))
    ap.add_argument("--results", required=True, type=Path)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-gate", action="store_true")
    ap.add_argument("--allow-settings-mismatch", action="store_true")
    ap.add_argument("--min-gap-s", type=int, default=90)
    ap.add_argument("--stall-s", type=int, default=600)
    args = ap.parse_args()
    if (args.index is None) == (args.smoke is None):
        raise SystemExit("give exactly one of --index / --smoke")
    args.results.mkdir(parents=True, exist_ok=True)
    try:
        return Session(args).run()
    except SystemExit as e:
        msg = str(e)
        print(msg, flush=True)
        m = re.search(r"\(exit (\d)\)", msg)
        return int(m.group(1)) if m else 3


if __name__ == "__main__":
    sys.exit(main())
