"""M6 gauge diagnostic run E (등록 M6 v3 §2) — one GaugeDiagActivity run on the phone (+ the E-T device-side loop), pull, validity. 계산 안 함.

  set ANDROID_SERIAL=<ip:port>   (never written to any file; logs show <SERIAL>)
  py -3 -X utf8 s26/tools/mixreq/m6_gauge.py --plan s26/results/m6_1012/plan_m6e --run E1|E2|E3|ET|E_smoke --results <root> --runlog <runs.jsonl>
      [--attempt 1|2] [--et-loop] [--loop-only-s 10] [--band-wait-s 1200] [--dry-run]

Steps (start conditions = 등록 §3-4, same as P/K): screen_off_timeout get/put 86400000 · awake / keyguard · SOC 30 ~ 90 unplugged · start SKIN band
29.5 ~ 31.5 (20 min wait, then proceed + mark) · ≥ 90 s since the previous run end (run log) · start_gate_1005e (SKIN ≤ 32 · AP ≤ 32 · BAT ≤ 30) ·
settings record (airplane · DND · brightness) · push inputs if missing (SHA) + config → logcat (threadtime, unfiltered: never commit raw) ·
skin_watch (15 s) · phone_watch (10 s) as for sessions (no host HAL 2 s sampler in E — the E-T loop is the only extra reader, 등록 §2-2) ·
[E-T: start the device-side loop → host/et_loop.txt] · am start GaugeDiagActivity · poll the device folder every 5 s for summary.json ·
[E-T: stop the loop] · pull → <results>/<run>_a<attempt>/device · rename the device folder <run_id> → <run_id>__a<attempt> (attempt 2 can run) ·
gauge_validated.json (등록 §2-4: plugged 0 · screen on · start SKIN 29.5 ~ 31.5 · poll interval median ≤ 25 ms · no safety stop).
--loop-only-s N: E-T smoke = the device loop alone for N s (no app) → host/et_loop.txt (form · read interval only).
Exit codes: 0 valid · 1 invalid · 2 gate · 3 device · 4 stall · 5 folder exists · 6 charge needed · 7 locked · 8 SOC > 90.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402
import mixreq_session as MS  # noqa: E402
import m6_common as M  # noqa: E402
import m6_session as S  # noqa: E402

ACTIVITY = f"{C.APP_PACKAGE}/.GaugeDiagActivity"
DEVICE_GAUGE_DIR = f"/storage/emulated/0/Android/data/{C.APP_PACKAGE}/files/gauge"
DEVICE_CONFIG_DIR = f"{C.DEVICE_INPUT_DIR}/gauge"
POLL_MEDIAN_MAX_MS = 25.0
SKIN_BAND = (29.5, 31.5)


class Run:
    def __init__(self, args):
        self.args = args
        self.serial = os.environ.get("ANDROID_SERIAL", "")
        if not self.serial and not args.dry_run:
            raise SystemExit("ANDROID_SERIAL not set")
        self.plan = C.read_json(args.plan / "plan.json")
        entry = next((r for r in self.plan["runs"] + self.plan["smoke"] if r["run_id"] == args.run), None)
        if entry is None:
            raise SystemExit(f"run {args.run} not in plan")
        self.entry = entry
        self.config_bytes = (args.plan / entry["config"]).read_bytes()
        if C.sha256_bytes(self.config_bytes) != entry["config_sha256"]:
            raise SystemExit("config SHA != plan record — stop")
        self.config = json.loads(self.config_bytes)
        self.run_id = self.config["run_id"]
        self.device_inputs = C.read_json(REPO / "s26" / "results" / "m6_1012" / "plan_m6p" / "device_inputs.json")
        suffix = "_loop" if args.loop_only_s else ""
        self.folder = args.results / f"{args.run}{suffix}_a{args.attempt}"
        self.host = self.folder / "host"
        self.procs: dict[str, subprocess.Popen] = {}
        self.log_rec: dict = dict(run=args.run, run_id=self.run_id, attempt=args.attempt, config_sha256=entry["config_sha256"], commands=[], events=[])

    def mask(self, text: str) -> str:
        return text.replace(self.serial, "<SERIAL>") if self.serial else text

    def log(self, msg: str):
        line = f"[{dt.datetime.now().isoformat(timespec='seconds')}] {self.mask(msg)}"
        print(line, flush=True)
        if self.host.exists():
            with open(self.host / "gauge_log.txt", "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def adb(self, *argv, timeout=60) -> subprocess.CompletedProcess:
        self.log_rec["commands"].append(dict(t=time.time(), cmd=self.mask(" ".join(argv))))
        return subprocess.run([MS.ADB, "-s", self.serial, *argv], capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")

    def shell(self, command: str, timeout=60) -> str:
        return self.adb("shell", command, timeout=timeout).stdout

    # ------------------------------------------------------------------ before
    def gap_wait(self):
        prev = S.previous_run(self.args.runlog)
        self.log_rec["previous_run"] = prev
        if prev:
            wait = 90 - (time.time() - float(prev.get("epoch", 0)))
            if wait > 0:
                self.log(f"inter-run gap: sleeping {wait:.0f} s (min 90)")
                time.sleep(wait)

    def gate(self) -> int:
        r = subprocess.run([sys.executable, "-X", "utf8", str(MS.GATE_PY), self.serial, self.folder.name, str(self.args.results / "gate_log_m6e.csv")],
                           capture_output=True, text=True, timeout=7200)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        self.log(f"gate rc={r.returncode} last={last}")
        self.log_rec["gate"] = dict(rc=r.returncode, last=last)
        return r.returncode

    def settings(self):
        v = dict(airplane=self.shell("settings get global airplane_mode_on").strip(), zen_mode=self.shell("settings get global zen_mode").strip(),
                 brightness_mode=self.shell("settings get system screen_brightness_mode").strip(),
                 brightness=self.shell("settings get system screen_brightness").strip(),
                 screen_off_timeout=self.shell("settings get system screen_off_timeout").strip())
        self.log_rec["settings"] = v
        self.log(f"settings {v}")

    def push(self):
        self.shell(f"mkdir -p {C.DEVICE_INPUT_DIR} {DEVICE_CONFIG_DIR}")
        for name in ("cls_model", "png", "cls_labels"):
            spec = self.device_inputs[name]
            present = self.shell(f"sha256sum {spec['device_path']} 2>/dev/null").split()
            if present and present[0] == spec["sha256"]:
                continue
            self.log(f"push {name}")
            r = self.adb("push", str(REPO / spec["host_path"]), spec["device_path"], timeout=600)
            if r.returncode != 0:
                raise RuntimeError(f"push {name} failed")
        local = self.host / "config_pushed.json"
        local.write_bytes(self.config_bytes)
        dev = f"{DEVICE_CONFIG_DIR}/{self.run_id}.json"
        self.adb("push", str(local), dev, timeout=60)
        after = self.shell(f"sha256sum {dev}").split()
        if not after or after[0] != self.entry["config_sha256"]:
            raise RuntimeError("pushed config SHA mismatch")
        self.device_config = dev
        exists = self.shell(f"ls -d {DEVICE_GAUGE_DIR}/{self.run_id} 2>/dev/null").strip()
        if exists:
            raise SystemExit(f"device run folder exists: {self.run_id} (exit 5)")

    def start_background(self):
        self.adb("logcat", "-c", timeout=30)
        self.procs["logcat"] = subprocess.Popen([MS.ADB, "-s", self.serial, "logcat", "-v", "threadtime"],
                                                stdout=open(self.host / "logcat_threadtime.txt", "wb"), stderr=subprocess.DEVNULL)
        self.procs["skin"] = subprocess.Popen([sys.executable, "-X", "utf8", str(MS.SKIN_WATCH_PY), self.serial, str(self.host / "skin_watch.csv"), str(self.host / "watch.stop")])
        self.procs["phone"] = subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(MS.PHONE_WATCH_PS1),
                                                "-OutCsv", str(self.host / "phone_watch.csv"), "-StopFile", str(self.host / "watch.stop")])
        self.log(f"background pids logcat={self.procs['logcat'].pid} skin={self.procs['skin'].pid} phone={self.procs['phone'].pid}")

    def stop_background(self):
        (self.host / "watch.stop").write_text("stop")
        for name in ("skin", "phone"):
            p = self.procs.get(name)
            if p:
                try:
                    p.wait(timeout=40)
                except subprocess.TimeoutExpired:
                    p.kill()
        p = self.procs.get("logcat")
        if p:
            time.sleep(2)
            p.terminate()
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()

    # ------------------------------------------------------------------ E-T loop
    def start_loop(self):
        loop = self.plan["et_device_loop"]
        self.loop_out = open(self.host / "et_loop.txt", "wb")
        self.procs["loop"] = subprocess.Popen([MS.ADB, "-s", self.serial, "shell", loop], stdout=self.loop_out, stderr=subprocess.STDOUT)
        self.log_rec["et_loop"] = dict(command=loop, started=time.time(), pid=self.procs["loop"].pid)
        self.log(f"E-T device loop started (host pid {self.procs['loop'].pid})")

    def stop_loop(self):
        p = self.procs.get("loop")
        if not p:
            return
        p.terminate()
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
        self.loop_out.close()
        left = self.shell("ps -A -o PID,ARGS | grep -F 'thermal_zone' | grep -v grep").strip()
        if left:
            pids = [ln.split()[0] for ln in left.splitlines() if ln.split()]
            self.shell("kill " + " ".join(pids))
        self.log_rec["et_loop"].update(stopped=time.time(), device_leftover=left)
        self.log(f"E-T device loop stopped (device leftover killed: {bool(left)})")

    # ------------------------------------------------------------------ run
    def run_app(self) -> str:
        r = self.adb("shell", "am", "start", "-W", "-n", ACTIVITY, "--es", "d1_gauge_config", self.device_config, "--es", "d1_gauge_run_id", self.run_id, timeout=60)
        self.log_rec["start_time"] = dt.datetime.now().isoformat(timespec="seconds")
        self.log(f"am start rc={r.returncode} {r.stdout.strip()[:120]}")
        seg = (self.config["idle_ms"] + self.config["load_ms"] + self.config["rest_ms"]) / 1000.0
        cap = seg + 300
        t0 = time.time()
        while True:
            time.sleep(5)
            if not S_adb_ok(self):
                return "lost"
            text = self.shell(f"ls {DEVICE_GAUGE_DIR}/{self.run_id} 2>/dev/null")
            if "summary.json" in text.split():
                return "done"
            if time.time() - t0 > cap:
                return "stall"

    def pull(self):
        dev = f"{DEVICE_GAUGE_DIR}/{self.run_id}"
        self.adb("pull", dev, str(self.folder / "device_pull"), timeout=600)
        pulled = self.folder / "device_pull"
        if pulled.is_dir():
            inner = pulled / self.run_id
            (inner if inner.is_dir() else pulled).rename(self.folder / "device")
            if pulled.exists():
                try:
                    pulled.rmdir()
                except OSError:
                    pass
        self.adb("shell", "am", "force-stop", C.APP_PACKAGE, timeout=30)
        moved = f"{dev}__a{self.args.attempt}"
        self.shell(f"mv {dev} {moved}")
        self.log_rec["device_folder_renamed_to"] = moved.rsplit("/", 1)[-1]
        self.log_rec["end_time"] = dt.datetime.now().isoformat(timespec="seconds")

    def validate(self, band_rec: dict | None) -> dict:
        d = self.folder / "device"
        summary = C.read_json(d / "summary.json") if (d / "summary.json").is_file() else {}
        samples = []
        if (d / "samples.jsonl").is_file():
            with open(d / "samples.jsonl", encoding="utf-8") as f:
                samples = [json.loads(l) for l in f if l.strip()]
        t0 = [s["t0"] for s in samples]
        gaps_ms = [(b - a) / 1e6 for a, b in zip(t0, t0[1:])]
        median_ms = statistics.median(gaps_ms) if gaps_ms else None
        plugged_bad = sum(1 for s in samples if (s.get("sticky") or {}).get("plugged") not in (0,))
        status_rows = [s["status"] for s in samples if isinstance(s.get("status"), dict)]
        screen_off = sum(1 for st in status_rows if st.get("interactive") is not True)
        start_skin = (band_rec or {}).get("start_skin")
        in_band = start_skin is not None and SKIN_BAND[0] <= float(start_skin) <= SKIN_BAND[1]
        watch = dict(skin=None)
        if (self.host / "skin_watch.csv").is_file():
            import csv
            with open(self.host / "skin_watch.csv", encoding="utf-8") as f:
                watch["skin"] = sum(1 for row in csv.DictReader(f) if (row.get("action") or "").strip())
        rules = dict(
            completed=dict(passed=summary.get("status") == "completed" and summary.get("stop_reason") is None, detail=dict(status=summary.get("status"), stop_reason=summary.get("stop_reason"))),
            plugged_zero=dict(passed=bool(samples) and plugged_bad == 0, detail=dict(samples=len(samples), plugged_nonzero=plugged_bad)),
            screen_on=dict(passed=bool(status_rows) and screen_off == 0, detail=dict(status_rows=len(status_rows), interactive_false=screen_off)),
            start_skin_band=dict(passed=in_band, detail=dict(start_skin=start_skin, band=list(SKIN_BAND), band_result=(band_rec or {}).get("result"))),
            poll_median=dict(passed=median_ms is not None and median_ms <= POLL_MEDIAN_MAX_MS, detail=dict(median_ms=median_ms, max_ms=POLL_MEDIAN_MAX_MS,
                             p05_ms=sorted(gaps_ms)[int(0.05 * (len(gaps_ms) - 1))] if gaps_ms else None, p95_ms=sorted(gaps_ms)[int(0.95 * (len(gaps_ms) - 1))] if gaps_ms else None)),
            safety=dict(passed=watch["skin"] in (0, None) and summary.get("stop_reason") is None, detail=dict(skin_watch_actions=watch["skin"])),
        )
        reasons = [k for k, v in rules.items() if not v["passed"]]
        if self.config["experiment_id"] == M.E_SMOKE_ID:
            reasons_note = "smoke — 판정 밖 (기록)"
        else:
            reasons_note = None
        return dict(schema="s26-m6-gauge-validated-v1", run=self.args.run, run_id=self.run_id, attempt=self.args.attempt, experiment_id=self.config["experiment_id"],
                    eligible=not reasons, reasons=reasons, rules=rules, note=reasons_note, registration=M.REGISTRATION,
                    sysfs_polled=summary.get("sysfs_polled"), polls=summary.get("polls"), energy_counter_first=summary.get("energy_counter_first"))


def S_adb_ok(run: Run) -> bool:
    for k in range(4):
        st = run.adb("get-state", timeout=15).stdout.strip()
        if st == "device":
            return True
        if k == 3:
            break
        run.log(f"adb state '{st}' -> disconnect/connect try {k + 1}")
        subprocess.run([MS.ADB, "disconnect", run.serial], capture_output=True, timeout=30)
        time.sleep(2)
        subprocess.run([MS.ADB, "connect", run.serial], capture_output=True, timeout=30)
        time.sleep(5 if k == 0 else 30)
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", required=True, type=Path)
    ap.add_argument("--run", required=True)
    ap.add_argument("--attempt", type=int, default=1, choices=(1, 2))
    ap.add_argument("--results", required=True, type=Path)
    ap.add_argument("--runlog", required=True, type=Path)
    ap.add_argument("--et-loop", action="store_true")
    ap.add_argument("--loop-only-s", type=int, default=0)
    ap.add_argument("--band-wait-s", type=int, default=1200)
    ap.add_argument("--skin-band", default="29.5,31.5")
    ap.add_argument("--in-block-charge", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    args.attempt = int(args.attempt)
    run = Run(args)
    args.results.mkdir(parents=True, exist_ok=True)
    if run.folder.exists():
        print(run.mask(f"host run folder exists: {run.folder} (exit 5)"), flush=True)
        return 5
    if args.dry_run:
        print(f"DRY {args.run} config {run.entry['config_sha256']} folder {run.folder}")
        return 0
    label = f"{args.run}{'_loop' if args.loop_only_s else ''}"
    S.ensure_screen_timeout(run.serial, args.results, label)
    rc = S.ensure_awake(run.serial, args.results, label)
    if rc:
        return rc
    band_rec = None
    if not args.loop_only_s:
        args.index, args.smoke = None, None
        rc = S.precheck(args, run.serial, label)
        if rc:
            return rc
        recs = [json.loads(l) for l in (args.results / "start_band.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        band_rec = recs[-1] if recs else None
    run.folder.mkdir(parents=True)
    run.host.mkdir()
    S.append_jsonl(args.runlog, dict(event="start", label=label, kind="gauge", run=args.run, attempt=args.attempt, results=str(args.results),
                                     t=S.now_iso(), epoch=time.time(), in_block_charge=args.in_block_charge))
    rc = 3
    try:
        run.log(f"GAUGE START run={args.run} run_id={run.run_id} attempt={args.attempt} config={run.entry['config_sha256']}")
        if args.loop_only_s:
            run.start_loop()
            time.sleep(args.loop_only_s)
            run.stop_loop()
            rc = 0
            return rc
        run.gap_wait()
        grc = run.gate()
        if grc != 0:
            rc = 6 if grc == 2 else 2
            return rc
        apk_path = run.shell(f"pm path {C.APP_PACKAGE}").strip().replace("package:", "")
        run.log_rec["apk_sha256"] = run.shell(f"sha256sum {apk_path}").split()[0] if apk_path else None
        run.log(f"apk_sha256={run.log_rec['apk_sha256']}")
        run.settings()
        run.push()
        run.start_background()
        if args.et_loop:
            run.start_loop()
        result = run.run_app()
        run.log(f"app -> {result}")
        if args.et_loop:
            run.stop_loop()
        run.pull()
        run.stop_background()
        if result != "done":
            run.log_rec["stall"] = result
            rc = 4
            return rc
        validated = run.validate(band_rec)
        C.write_json(run.folder / "gauge_validated.json", validated)
        run.log(f"VALID={validated['eligible']} reasons={validated['reasons']} poll_median_ms={validated['rules']['poll_median']['detail']['median_ms']}")
        rc = 0 if validated["eligible"] else 1
        return rc
    except SystemExit as e:
        msg = str(e)
        run.log(msg)
        m = re.search(r"\(exit (\d)\)", msg)
        rc = int(m.group(1)) if m else 3
        return rc
    finally:
        try:
            run.stop_background()
        except Exception:
            pass
        run.log_rec["band"] = band_rec
        C.write_json(run.host / "gauge_log.json", run.log_rec)
        S.append_jsonl(args.runlog, dict(event="end", label=label, kind="gauge", rc=rc, attempt=args.attempt, t=S.now_iso(), epoch=time.time()))
        run.log(f"GAUGE END rc={rc}")


if __name__ == "__main__":
    sys.exit(main())
