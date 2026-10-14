"""M7 driver (2026-10-13, 등록 M7 v2 §1-2 · §1-4 · §2-4 · §2-6 · §4-3 · 프롬프트 M7-A 1단계-4) — runs the registered order with the M7-apk.
Output goes to files only (console file via m7_driver.ps1 · driver log · events jsonl); never pipe this into bash (M6-A 사고 6).
m6_session.py / mixreq_session.py / m6_validate.py are NOT modified: every session is `m7_session.py` (= m6_session with the M7 tables).

  set ANDROID_SERIAL=<ip:port>
  py -3 -X utf8 s26/tools/mixreq/m7_driver.py --kind p    --items 12,13,14,15,16,17          (P block: HAL ≥ 60 s before → session → HAL until origin + 300 s)
  py -3 -X utf8 s26/tools/mixreq/m7_driver.py --kind k    --items 4,5,6 [--cond A|B|C]       (K: condition from plan_m7k unless --cond; A = idle ≥ 1,200 s + 120 s slope
                                                                                              check (stable / stable_miss, ≤ +1,200 s); B/C = HAL ≥ 120 s → prep P (plan_m7prep)
                                                                                              → 90 s → K (precheck · gate skipped, 등록 §1-2) → HAL off after K run log end)
  py -3 -X utf8 s26/tools/mixreq/m7_driver.py --kind s    --items 16,17,18                   (S: HAL ≥ 120 s before → session (mixreq sustained rules · ≥ 600 s between)
                                                                                              → HAL until window end + 600 s)
  py -3 -X utf8 s26/tools/mixreq/m7_driver.py --kind prep --items 42                         (a prep P alone — smoke / repair only)
  py -3 -X utf8 s26/tools/mixreq/m7_driver.py --kind smoke --smoke p|k|s                     (plan smoke manifests, 판정 밖)
Rules kept from m6_driver.ps1 (M5 → M6): registered order; an invalid run (rc 1) is retried ONCE after --retry-rest-s (600) rest as attempt 2 (B/C: the prep
is run again on its next attempt, then K attempt 2); a second invalid → slot invalid_twice (folders kept); connection-class rc (2/3/4) before the app
started → host folder moved aside · adb wait · same attempt (3 in a row → STOP); rc 6 CHARGE NEEDED → STOP; rc 7 locked → wait 60 s (attempt not
consumed); rc 8 → STOP. Phone safety between runs: SKIN ≥ 43 ℃ or thermal_status ≥ 3 → STOP. No screen_off_timeout restore anywhere.
Every run: last power-disconnect time (dumpsys battery EventLogBuffer) → charge_end_to_start_s · start SKIN/AP/BAT/SOC · HAL file per session
(results\\S26_M7_HAL\\hal_cont_<label>_a<attempt>.csv) · one record in results\\S26_M7_driver_events.jsonl.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import m7_common as M7  # noqa: E402  (extends the M6 tables first)
import mixreq_common as C  # noqa: E402
import mixreq_session as MS  # noqa: E402  (ADB path · thermal parser only)

REPO = HERE.parents[2]
PLAN_ROOT = REPO / "s26" / "results" / "m7_1013"
PLAN_BY_KIND = {"p": "plan_m7p", "prep": "plan_m7prep", "k": "plan_m7k", "s": "plan_m7s"}
ROOT_BY_KIND = {"p": "S26_M7_P", "prep": "S26_M7_PREP", "k": "S26_M7_K", "s": "S26_M7_S", "smoke": "S26_M7_SMOKE"}
HAL_PS1 = HERE / "m7_hal_cont.ps1"
SESSION_PY = HERE / "m7_session.py"
PY = sys.executable


def now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def iso_to_epoch(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s).timestamp()
    except ValueError:
        return None


def read_json(p: Path):
    return C.read_json(p) if Path(p).is_file() else None


class Stop(Exception):
    pass


class Driver:
    def __init__(self, args):
        self.args = args
        self.kind = args.kind
        self.serial = os.environ.get("ANDROID_SERIAL", "")
        if not self.serial:
            raise SystemExit("ANDROID_SERIAL not set")
        self.base = Path(args.results_base) if args.results_base else REPO / "results"
        self.root = self.base / ROOT_BY_KIND[self.kind]
        self.root.mkdir(parents=True, exist_ok=True)
        self.hal_dir = self.base / "S26_M7_HAL"
        self.hal_dir.mkdir(parents=True, exist_ok=True)
        self.runlog = self.base / "S26_M7_runs.jsonl"
        self.events = self.base / "S26_M7_driver_events.jsonl"
        self.tag = dt.datetime.now().strftime("%m%d_%H%M%S")
        self.driver_log = self.root / f"driver_log_{self.kind}.txt"
        self.state_file = self.root / f"driver_state_{self.kind}_{self.tag}.json"
        self.state = dict(kind=self.kind, driver="m7-v1", started=now_iso(), items={}, stop_reason="", retries=0, invalid_twice=[], connection_events=0,
                          pre_start_moves=[], lock_waits=0, hal=[])
        self.plans = {k: read_json(PLAN_ROOT / v / "plan.json") for k, v in PLAN_BY_KIND.items()}
        self.consecutive_conn = 0
        self.hal_procs: dict[str, dict] = {}

    # ------------------------------------------------------------------ logging
    def mask(self, s: str) -> str:
        return s.replace(self.serial, "<SERIAL>") if self.serial else s

    def log(self, msg: str) -> None:
        line = f"[{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S %z')}] {self.mask(msg)}"
        print(line, flush=True)
        for _ in range(5):
            try:
                with open(self.driver_log, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
                return
            except OSError:
                time.sleep(0.3)

    def event(self, **rec) -> None:
        rec = dict(t=now_iso(), epoch=time.time(), kind=self.kind, **rec)
        with open(self.events, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")

    def save_state(self) -> None:
        C.write_json(self.state_file, self.state)

    # ------------------------------------------------------------------ adb · phone
    def adb(self, *argv, timeout=30) -> str:
        try:
            r = subprocess.run([MS.ADB, "-s", self.serial, *argv], capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
            return r.stdout
        except subprocess.TimeoutExpired:
            return ""

    def adb_state(self) -> str:
        return self.adb("get-state", timeout=15).strip()

    def phone_state(self) -> dict:
        th = self.adb("shell", "dumpsys thermalservice")
        t = MS.LOGGER.parse_thermalservice(th)
        b = self.adb("shell", "dumpsys battery")
        lvl = re.search(r"^\s*level:\s*(\d+)", b, re.M)
        cur = re.search(r"^\s*current now:\s*(-?\d+)", b, re.M)
        plugged = bool(re.search(r"(AC|USB|Wireless|Dock) powered:\s*true", b))
        disc = self.power_events(b)

        def f(x):
            try:
                return float(x)
            except (TypeError, ValueError):
                return None
        return dict(t=now_iso(), epoch=time.time(), SKIN=f(t["SKIN"]), AP=f(t["AP"]), BAT=f(t["BAT"]), PA=f(t["PA"]),
                    thermal_status=int(t["thermal_status"]) if str(t["thermal_status"]).isdigit() else None,
                    soc=int(lvl.group(1)) if lvl else None, plugged=plugged, current_now_uA=int(cur.group(1)) if cur else None, **disc)

    def power_events(self, battery_dump: str) -> dict:
        """Last ACTION_POWER_DISCONNECTED / CONNECTED lines of dumpsys battery EventLogBuffer (device local time, this year)."""
        year = dt.datetime.now().year
        last = {}
        for m in re.finditer(r"^(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d)\.(\d{3})\s+android\.intent\.action\.ACTION_POWER_(CONNECTED|DISCONNECTED)", battery_dump, re.M):
            mo, d, hh, mm, ss, ms, what = m.groups()
            try:
                ts = dt.datetime(year, int(mo), int(d), int(hh), int(mm), int(ss), int(ms) * 1000)
            except ValueError:
                continue
            last[what] = ts
        out = dict(last_power_disconnected=last["DISCONNECTED"].isoformat(timespec="milliseconds") if "DISCONNECTED" in last else None,
                   last_power_connected=last["CONNECTED"].isoformat(timespec="milliseconds") if "CONNECTED" in last else None,
                   last_power_disconnected_epoch=last["DISCONNECTED"].timestamp() if "DISCONNECTED" in last else None)
        out["unplugged_since_last_disconnect"] = ("DISCONNECTED" in last) and ("CONNECTED" not in last or last["CONNECTED"] < last["DISCONNECTED"])
        return out

    def safety(self, where: str) -> None:
        s = self.phone_state()
        self.log(f"phone {where}: SKIN={s['SKIN']} AP={s['AP']} BAT={s['BAT']} status={s['thermal_status']} SOC={s['soc']} plugged={s['plugged']} last_disconnect={s['last_power_disconnected']}")
        if (s["SKIN"] is not None and s["SKIN"] >= M7.SAFETY_SKIN_C) or (s["thermal_status"] is not None and s["thermal_status"] >= M7.SAFETY_THERMAL_STATUS):
            self.state["stop_reason"] = f"SAFETY SKIN={s['SKIN']} status={s['thermal_status']} at {where}"
            raise Stop(self.state["stop_reason"])

    def wait_adb(self, max_s: int) -> bool:
        t0 = time.time()
        while True:
            st = self.adb_state()
            if st == "device":
                self.log("adb reconnected (get-state device)")
                return True
            if time.time() - t0 >= max_s:
                self.log(f"adb still not connected after {int(time.time() - t0)} s (state '{st}')")
                return False
            self.log(f"adb state '{st}' -> disconnect/connect, waiting 60 s")
            subprocess.run([MS.ADB, "disconnect", self.serial], capture_output=True, timeout=30)
            time.sleep(3)
            subprocess.run([MS.ADB, "connect", self.serial], capture_output=True, timeout=30)
            time.sleep(57)

    # ------------------------------------------------------------------ run log · session folders
    def last_run_end(self) -> dict | None:
        if not self.runlog.is_file():
            return None
        ends = [json.loads(l) for l in self.runlog.read_text(encoding="utf-8").splitlines() if l.strip()]
        ends = [r for r in ends if r.get("event") == "end"]
        return ends[-1] if ends else None

    def plan_entry(self, kind: str, index: int) -> dict:
        plan = self.plans[kind]
        return next(s for s in plan["sessions"] if s["index"] == index)

    def host_folder(self, kind: str, index: int, attempt: int, root: Path | None = None) -> Path:
        e = self.plan_entry(kind, index)
        return (root or self.root) / f"S26_MIXREQ_{index:02d}_{e['policy']}_a{attempt}"

    def session_times(self, folder: Path) -> dict:
        """Host start/end from host/session_log.json; origin · last lane_available · session end as host epochs via progress.jsonl mono offsets."""
        out = dict(folder=str(folder), host_start=None, host_start_epoch=None, host_end=None, origin_host_epoch=None, window_end_host_epoch=None,
                   last_lane_available_host_epoch=None, last_power_sample_host_epoch=None, common_s=None)
        sl = read_json(folder / "host" / "session_log.json") or {}
        out["host_start"], out["host_end"] = sl.get("start_time"), sl.get("end_time")
        start_epoch = iso_to_epoch(sl.get("start_time"))
        out["host_start_epoch"] = start_epoch
        prog = folder / "device" / "progress.jsonl"
        if start_epoch is None or not prog.is_file():
            return out
        t_session_start = t_common_start = t_common_end = None
        la, ps = [], []
        with open(prog, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                k = e.get("kind")
                if k == "session_start":
                    t_session_start = int(e["mono_ns"])
                elif k == "common_start":
                    t_common_start = int(e["mono_ns"])
                elif k == "common_end":
                    t_common_end = int(e["mono_ns"])
                elif k == "lane_available":
                    la.append(int(e["mono_ns"]))
                elif k == "power_sample":
                    ps.append(int(e["mono_ns"]))
        if t_session_start is None:
            return out

        def host(mono):   # host clock of a device mono_ns: am start time + offset from the app's first event (≈ 1 s activity launch, 기록)
            return None if mono is None else start_epoch + (mono - t_session_start) / 1e9
        out.update(origin_host_epoch=host(t_common_start), window_end_host_epoch=host(t_common_end), last_lane_available_host_epoch=host(max(la)) if la else None,
                   last_power_sample_host_epoch=host(max(ps)) if ps else None, method="host start_time + (mono_ns − session_start mono_ns)")
        return out

    def app_started(self, folder: Path) -> bool:
        sl = read_json(folder / "host" / "session_log.json")
        return bool(sl and sl.get("start_time"))

    # ------------------------------------------------------------------ continuous HAL
    def hal_start(self, tag: str) -> dict:
        csv_path = self.hal_dir / f"hal_cont_{tag}.csv"
        stop = self.hal_dir / f"hal_cont_{tag}.stop"
        if stop.exists():
            stop.unlink()
        p = subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", str(HAL_PS1),
                              "-OutCsv", str(csv_path), "-StopFile", str(stop), "-Tag", tag], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        h = dict(tag=tag, csv=str(csv_path), stop=str(stop), pid=p.pid, started=now_iso(), started_epoch=time.time(), proc=p)
        self.hal_procs[tag] = h
        self.state["hal"].append({k: v for k, v in h.items() if k != "proc"})
        self.log(f"HAL start tag={tag} pid={p.pid} -> {csv_path.name}")
        self.event(what="hal_start", tag=tag, csv=str(csv_path), pid=p.pid)
        return h

    def hal_stop(self, h: dict, reason: str = "") -> None:
        Path(h["stop"]).write_text("stop", encoding="utf-8")
        try:
            h["proc"].wait(timeout=20)
        except subprocess.TimeoutExpired:
            pass
        h["stopped_epoch"] = time.time()
        self.log(f"HAL stop tag={h['tag']} ({reason}) rows={self.hal_row_count(Path(h['csv']))}")
        self.event(what="hal_stop", tag=h["tag"], csv=h["csv"], reason=reason, rows=self.hal_row_count(Path(h["csv"])))

    def hal_stop_at(self, h: dict, at_epoch: float, reason: str) -> None:
        """Stop later without blocking: a detached powershell sleeps until at_epoch then creates the stop file (M6 driver never blocks on this)."""
        delay = max(0.0, at_epoch - time.time())
        cmd = f"Start-Sleep -Milliseconds {int(delay * 1000)}; Set-Content -Path '{h['stop']}' -Value 'stop'"
        subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        h["stop_scheduled_epoch"] = at_epoch
        self.log(f"HAL stop scheduled tag={h['tag']} in {delay:.0f} s ({reason})")
        self.event(what="hal_stop_scheduled", tag=h["tag"], at_epoch=at_epoch, reason=reason)

    @staticmethod
    def hal_row_count(csv_path: Path) -> int:
        if not csv_path.is_file():
            return 0
        with open(csv_path, encoding="utf-8-sig", errors="replace") as f:
            return max(0, sum(1 for _ in f) - 1)

    @staticmethod
    def hal_rows(csv_path: Path) -> list[dict]:
        rows = []
        if not csv_path.is_file():
            return rows
        with open(csv_path, encoding="utf-8-sig", errors="replace", newline="") as f:
            for r in csv.DictReader(f):
                def num(k):
                    try:
                        return float(r[k])
                    except (KeyError, TypeError, ValueError):
                        return None
                ms = num("host_ms")
                rows.append(dict(host_epoch_s=ms / 1000.0 if ms is not None else None, AP=num("AP"), SKIN=num("SKIN"), BAT=num("BAT"), err=r.get("err", "")))
        return rows

    # ------------------------------------------------------------------ one session (subprocess · output to file)
    def run_session(self, kind: str, index: int, attempt: int, label: str, extra: list[str], legacy: bool = False, smoke: str | None = None) -> int:
        plan_dir = PLAN_ROOT / PLAN_BY_KIND[kind]
        root = self.base / ROOT_BY_KIND[self.kind]
        argv = [PY, "-X", "utf8", str(SESSION_PY), "--plan", str(plan_dir), "--attempt", str(attempt), "--results", str(root), "--runlog", str(self.runlog),
                "--label", label, "--allow-settings-mismatch", *extra]
        argv += ["--smoke", smoke] if smoke else ["--index", str(index)]
        if legacy:
            argv.append("--legacy-validate")
        if self.args.band_wait_s is not None and "--band-wait-s" not in extra:
            argv += ["--band-wait-s", str(self.args.band_wait_s)]   # operator override (영훈 13:3x "대기 그만하고 바로 시작") — recorded in the run log args
        if self.args.in_block_charge:
            argv.append("--in-block-charge")
        console = root / f"console_{label}_a{attempt}_{dt.datetime.now().strftime('%H%M%S')}.txt"
        self.log(f"RUN {label} kind={kind} index={index} attempt={attempt} extra={extra} legacy={legacy} console={console.name}")
        self.event(what="run_start", label=label, run_kind=kind, index=index, attempt=attempt, extra=extra)
        with open(console, "w", encoding="utf-8") as out:
            rc = subprocess.run(argv, stdout=out, stderr=subprocess.STDOUT, cwd=str(REPO)).returncode
        self.log(f"RESULT {label} attempt={attempt} rc={rc} (0 valid · 1 invalid · 2 gate · 3 device · 4 stall · 5 folder exists · 6 charge needed · 7 locked · 8 SOC>max)")
        return rc

    def run_attempt(self, kind: str, index: int, attempt: int, label: str, extra: list[str], legacy: bool = False, smoke: str | None = None) -> int:
        """rc 7 → wait (not consumed) · connection-class before app start → folder aside · adb wait · same attempt (3 → STOP)."""
        lock_t0 = time.time()
        while True:
            rc = self.run_session(kind, index, attempt, label, extra, legacy, smoke)
            if rc == 7:
                self.state["lock_waits"] += 1
                self.save_state()
                if time.time() - lock_t0 >= self.args.lock_wait_s:
                    raise Stop(f"LOCKED for {self.args.lock_wait_s} s at {label}")
                self.log("PHONE LOCKED: 폰 잠금 해제 부탁 (waiting 60 s, attempt not consumed)")
                time.sleep(60)
                continue
            if rc == 6 and not self.app_started(self.host_folder(kind, index, attempt, self.base / ROOT_BY_KIND[self.kind]) if not smoke else Path("_none_")):
                # m6_session precheck says CHARGE NEEDED also when one adb read came back empty (SOC None) — verify before stopping (M7-A 21:54 사고)
                st = self.phone_state()
                if st.get("soc") is not None and st["soc"] >= 30 and not st["plugged"]:
                    self.consecutive_conn += 1
                    self.state["connection_events"] += 1
                    self.log(f"rc 6 but phone reads SOC={st['soc']} plugged={st['plugged']} -> transient adb read, attempt not consumed (x{self.consecutive_conn})")
                    self.event(what="rc6_transient", label=label, attempt=attempt, state=st)
                    self.save_state()
                    if self.consecutive_conn >= 3:
                        raise Stop(f"rc 6 x3 with SOC ok at {label} — adb reads unstable (operator: check the wireless debugging link)")
                    if not self.wait_adb(self.args.reconnect_wait_s):
                        self.log("WAIT: adb not back -> one more attempt anyway")
                    time.sleep(30)
                    continue
            if rc not in (2, 3, 4):
                self.consecutive_conn = 0
                return rc
            root = self.base / ROOT_BY_KIND[self.kind]
            folder = self.host_folder(kind, index, attempt, root) if not smoke else root / f"S26_MIXREQ_SMOKE_{smoke}_a{attempt}"
            if self.app_started(folder):
                self.log(f"connection-class rc={rc} but the app had started -> attempt {attempt} consumed")
                return rc
            self.consecutive_conn += 1
            self.state["connection_events"] += 1
            if folder.exists():
                moved = folder.with_name(folder.name + f"_pre{attempt}_{dt.datetime.now().strftime('%H%M%S')}")
                folder.rename(moved)
                self.state["pre_start_moves"].append(str(moved))
                self.log(f"pre-start failure rc={rc} -> host folder moved aside: {moved.name} (attempt not consumed)")
            self.save_state()
            if self.consecutive_conn >= 3:
                raise Stop(f"CONNECTION x3 at {label} (reconnect, then resume from this item)")
            if not self.wait_adb(self.args.reconnect_wait_s):
                self.log("WAIT: adb not back -> one more attempt anyway (operator: check the wireless debugging address)")
            time.sleep(5)

    def check_stop_rc(self, rc: int, label: str) -> None:
        if rc == 6:
            raise Stop(f"CHARGE NEEDED at {label} — 케이블 꽂으세요 (SOC < 30 또는 plugged) · 충전 뒤 분리 20 min · 같은 항목부터 --in-block-charge")
        if rc == 8:
            raise Stop(f"SOC above max at {label}")

    def start_record(self, label: str, kind: str, index: int, attempt: int) -> dict:
        folder = self.host_folder(kind, index, attempt, self.base / ROOT_BY_KIND[self.kind])
        band = None
        bands = self.base / ROOT_BY_KIND[self.kind] / "start_band.jsonl"
        if bands.is_file():
            recs = [json.loads(l) for l in bands.read_text(encoding="utf-8").splitlines() if l.strip()]
            recs = [r for r in recs if r.get("label") == f"index{index:02d}" and r.get("attempt") == attempt]
            band = recs[-1] if recs else None
        return dict(times=self.session_times(folder), start_band=(band or {}).get("result"), start_skin_band=(band or {}).get("start_skin"),
                    validated=(read_json(folder / "validated.json") or {}).get("eligible"), reasons=(read_json(folder / "validated.json") or {}).get("reasons"))

    # ------------------------------------------------------------------ kinds
    def wait_until(self, epoch: float, why: str, safety_every_s: int = 300) -> None:
        last = time.time()
        while time.time() < epoch:
            if time.time() - last >= safety_every_s:
                self.safety(f"waiting ({why})")
                last = time.time()
            time.sleep(min(30.0, max(0.5, epoch - time.time())))

    def charge_fields(self, s: dict, start_epoch: float | None) -> dict:
        d = s.get("last_power_disconnected_epoch")
        return dict(last_power_disconnected=s.get("last_power_disconnected"), last_power_connected=s.get("last_power_connected"),
                    unplugged_since_last_disconnect=s.get("unplugged_since_last_disconnect"),
                    charge_end_to_start_s=round(start_epoch - d, 1) if (d is not None and start_epoch is not None and s.get("unplugged_since_last_disconnect")) else None)

    def do_p(self, items: list[int], kind: str = "p") -> None:
        for index in items:
            e = self.plan_entry(kind, index)
            label = f"{'P' if kind == 'p' else 'PREP'}{index}"
            attempt = 1
            while True:
                self.safety(f"before {label} a{attempt}")
                s0 = self.phone_state()
                h = self.hal_start(f"{label}_a{attempt}")
                prev = self.last_run_end()
                expected_start = max(time.time(), float(prev["epoch"]) + M7.RUN_GAP_MIN_S) if prev else time.time()
                need = h["started_epoch"] + M7.HAL_PRE_START_P_S
                if expected_start < need:
                    self.wait_until(need, f"HAL pre-start {M7.HAL_PRE_START_P_S} s before {label}")
                rc = self.run_attempt(kind, index, attempt, label, [])
                rec = self.start_record(label, kind, index, attempt)
                t = rec["times"]
                stop_at = (t["origin_host_epoch"] + M7.HAL_P_AFTER_ORIGIN_S) if t.get("origin_host_epoch") else time.time() + 60
                self.hal_stop_at(h, stop_at, f"origin + {M7.HAL_P_AFTER_ORIGIN_S} s" if t.get("origin_host_epoch") else "no origin (fallback 60 s)")
                self.event(what="run_end", label=label, run_kind=kind, index=index, attempt=attempt, rc=rc, load=e.get("load"), letter=e.get("letter"),
                           role=e.get("role"), m7_block=e.get("m7_block"), order_pos=e.get("order_pos"), hal_csv=h["csv"], hal_started_epoch=h["started_epoch"],
                           hal_stop_at_epoch=stop_at, start_state=s0, **self.charge_fields(s0, t.get("host_start_epoch")), **rec)
                self.state["items"].setdefault(str(index), {})[f"attempt{attempt}"] = rc
                self.save_state()
                self.check_stop_rc(rc, label)
                if rc == 0 or attempt == 2:
                    if rc != 0:
                        self.state["invalid_twice"].append(index)
                        self.log(f"INVALID_TWICE: {label}")
                    break
                self.log(f"RETRY: resting {self.args.retry_rest_s} s before attempt 2 of {label} (rc={rc})")
                self.state["retries"] += 1
                time.sleep(self.args.retry_rest_s)
                attempt = 2

    def do_k(self, items: list[int], cond_override: str | None) -> None:
        for index in items:
            e = self.plan_entry("k", index)
            cond = cond_override or e["condition"]
            label = f"K{e['set']}{cond}"
            k_attempt, prep_attempt = 1, 1
            while True:
                self.safety(f"before {label} a{k_attempt}")
                if cond == "A":
                    rec = self.k_idle(index, label, k_attempt, e)
                else:
                    rec = self.k_after_prep(index, label, k_attempt, prep_attempt, cond, e)
                    prep_attempt = rec.get("prep_attempt", prep_attempt)
                rc = rec["rc"]
                self.state["items"].setdefault(str(index), {})[f"attempt{k_attempt}"] = rc
                self.save_state()
                self.check_stop_rc(rc, label)
                if rc == 0 or k_attempt == 2 or rec.get("prep_exhausted"):
                    if rc != 0:
                        self.state["invalid_twice"].append(index)
                        self.log(f"INVALID_TWICE: {label} (rc={rc} prep_exhausted={rec.get('prep_exhausted')})")
                    break
                self.log(f"RETRY: resting {self.args.retry_rest_s} s before attempt 2 of {label} (rc={rc})")
                self.state["retries"] += 1
                time.sleep(self.args.retry_rest_s)
                k_attempt = 2
                if cond != "A":
                    prep_attempt = min(2, prep_attempt + 1)

    def k_idle(self, index: int, label: str, attempt: int, e: dict) -> dict:
        h = self.hal_start(f"{label}_a{attempt}")
        prev = self.last_run_end()
        prev_epoch = float(prev["epoch"]) if prev else None
        target = (prev_epoch + M7.IDLE_MIN_S) if prev_epoch else time.time() + M7.IDLE_MIN_S
        self.log(f"{label} A: previous run end = {prev.get('label') if prev else None} {prev.get('t') if prev else None} -> idle until +{M7.IDLE_MIN_S} s ({dt.datetime.fromtimestamp(target).isoformat(timespec='seconds')})")
        self.wait_until(target, f"idle ≥ {M7.IDLE_MIN_S} s before {label}")
        # start band 29.5 ~ 31.5 (M6 v3 §3-4 · m6_session precheck 와 같은 규칙: 60 s 폴 · 최대 1,200 s · 미달이면 진행 · 표시) — 드라이버가 먼저 기다리고
        # 기울기는 앱 시작 직전 120 s 에 검사한다 (K1A 때 세션 안 띠 대기가 기울기 검사 뒤에 와서 20 min 벌어진 것을 고침 · 규칙 · 값 같음 · 순서만)
        lo, hi = 29.5, 31.5
        t_band0 = time.time()
        band_polls = []
        while True:
            s = self.phone_state()
            band_polls.append(dict(t=s["t"], SKIN=s["SKIN"], AP=s["AP"], BAT=s["BAT"], soc=s["soc"], plugged=s["plugged"]))
            if s["SKIN"] is not None and lo <= s["SKIN"] <= hi:
                band_result = "in_band"
                break
            if time.time() - t_band0 >= 1200:
                band_result = "out_of_band_after_wait"
                self.log(f"{label} A: start SKIN {s['SKIN']} outside {lo}~{hi} after {int(time.time() - t_band0)} s -> proceed (marked out_of_band)")
                break
            time.sleep(60)
        t_check0 = time.time()
        checks = []
        while True:
            st = M7.stable_from_hal(self.hal_rows(Path(h["csv"])), time.time())
            st["t"] = now_iso()
            checks.append(st)
            self.log(f"{label} A slope check: AP {st['ap_slope_c_per_min']} SKIN {st['skin_slope_c_per_min']} ℃/min over {st['samples']} samples -> {'stable' if st['stable'] else 'not yet'}")
            if st["stable"]:
                stable = "stable"
                break
            if time.time() - t_check0 >= M7.STABLE_EXTRA_MAX_S:
                stable = "stable_miss"
                self.log(f"{label} A: slope not within {M7.STABLE_SLOPE_C_PER_MIN} ℃/min after +{M7.STABLE_EXTRA_MAX_S} s -> proceed as stable_miss (자료 보존)")
                break
            time.sleep(M7.STABLE_RECHECK_S)
        s0 = self.phone_state()
        rc = self.run_attempt("k", index, attempt, label, ["--band-wait-s", "0"])   # 띠 대기는 위에서 끝남 (세션 precheck 는 SOC · plugged 만 다시 봄)
        rec = self.start_record(label, "k", index, attempt)
        rec["start_band"] = rec.get("start_band") if rec.get("start_band") == "in_band" else band_result
        rec["driver_band_polls"] = band_polls
        rec["driver_band_waited_s"] = round(t_check0 - t_band0)
        self.hal_stop(h, "K run log end (A)")
        t = rec["times"]
        idle = (t["host_start_epoch"] - prev_epoch) if (t.get("host_start_epoch") and prev_epoch) else None
        self.event(what="run_end", label=label, run_kind="k", index=index, attempt=attempt, rc=rc, condition="A", set=e["set"], order_pos=e["pos"], stable=stable,
                   stable_checks=checks, idle_s=round(idle, 1) if idle else None, previous_run=prev, k_app_start_host=t.get("host_start"), hal_csv=h["csv"],
                   hal_started_epoch=h["started_epoch"], hal_stopped_epoch=h.get("stopped_epoch"), start_state=s0, **self.charge_fields(s0, t.get("host_start_epoch")), **rec)
        return dict(rc=rc)

    def k_after_prep(self, index: int, label: str, k_attempt: int, prep_attempt: int, cond: str, e: dict) -> dict:
        prep_index = e["prep_index"]
        pe = self.plan_entry("prep", prep_index)
        prep_label = f"PREP{e['set']}{cond}"
        h = self.hal_start(f"{label}_a{k_attempt}")
        self.wait_until(h["started_epoch"] + M7.HAL_PRE_START_BC_S, f"HAL pre-start {M7.HAL_PRE_START_BC_S} s before {prep_label}")
        # --- prep P (precheck · gate as every P) · invalid → one more prep attempt (if any left) · K only after a valid prep
        prep_rc, prep_rec = None, None
        while True:
            if prep_attempt > 2:
                self.hal_stop(h, "prep attempts exhausted")
                self.event(what="run_end", label=label, run_kind="k", index=index, attempt=k_attempt, rc=None, condition=cond, set=e["set"], prep_label=prep_label,
                           prep_index=prep_index, prep_exhausted=True, hal_csv=h["csv"])
                return dict(rc=1, prep_attempt=prep_attempt, prep_exhausted=True)
            s0 = self.phone_state()
            prep_rc = self.run_attempt("prep", prep_index, prep_attempt, prep_label, [])
            prep_rec = self.start_record(prep_label, "prep", prep_index, prep_attempt)
            self.event(what="run_end", label=prep_label, run_kind="prep", index=prep_index, attempt=prep_attempt, rc=prep_rc, role="prep", condition=cond, set=e["set"],
                       load=pe.get("load"), letter=pe.get("letter"), for_k=label, hal_csv=h["csv"], start_state=s0,
                       **self.charge_fields(s0, prep_rec["times"].get("host_start_epoch")), **prep_rec)
            self.state["items"].setdefault(f"prep{prep_index}", {})[f"attempt{prep_attempt}"] = prep_rc
            self.save_state()
            self.check_stop_rc(prep_rc, prep_label)
            if prep_rc == 0:
                break
            self.log(f"prep {prep_label} a{prep_attempt} rc={prep_rc} -> resting {self.args.retry_rest_s} s, prep attempt {prep_attempt + 1}")
            self.state["retries"] += 1
            time.sleep(self.args.retry_rest_s)
            prep_attempt += 1
        prep_end = self.last_run_end()
        prep_end_epoch = float(prep_end["epoch"]) if prep_end else None
        # --- K: 90 s after the prep run-log end (m7_session's cross-run gap = 90 s) · precheck/gate skipped (등록 §1-2 · plan k_after_prep_gate)
        s1 = self.phone_state()
        rc = self.run_attempt("k", index, k_attempt, label, ["--skip-precheck", "--skip-gate"])
        rec = self.start_record(label, "k", index, k_attempt)
        self.hal_stop(h, f"K run log end ({cond})")
        t = rec["times"]
        gap = M7.gap_record(prep_end_epoch, t.get("host_start_epoch"))
        self.log(f"{label}: prep end -> K app start gap {gap['gap_s']} s (over={gap['gap_over']})")
        self.event(what="run_end", label=label, run_kind="k", index=index, attempt=k_attempt, rc=rc, condition=cond, set=e["set"], order_pos=e["pos"],
                   prep_label=prep_label, prep_index=prep_index, prep_attempt=prep_attempt, prep_session_folder=prep_rec["times"]["folder"],
                   prep_last_available_host_epoch=prep_rec["times"].get("last_lane_available_host_epoch"), prep_run_end_epoch=prep_end_epoch,
                   k_app_start_host=t.get("host_start"), gap_prep_to_k=gap, hal_csv=h["csv"], hal_started_epoch=h["started_epoch"], hal_stopped_epoch=h.get("stopped_epoch"),
                   start_state=s1, k_precheck="skipped (등록 §1-2 90 s)", **self.charge_fields(s1, t.get("host_start_epoch")), **rec)
        return dict(rc=rc, prep_attempt=prep_attempt)

    def do_s(self, items: list[int]) -> None:
        for index in items:
            e = self.plan_entry("s", index)
            label = f"{e['label']}-{e['letter']}"
            attempt = 1
            if self.host_folder("s", index, 1).exists():   # resume after a stop: attempt 1 already used (folder kept) → go to attempt 2
                attempt = 2
                self.log(f"{label}: attempt 1 folder exists -> starting at attempt 2 (retry slot)")
            while True:
                self.safety(f"before {label} a{attempt}")
                s0 = self.phone_state()
                h = self.hal_start(f"{label}_a{attempt}")
                prev = self.last_run_end()
                expected_start = max(time.time(), float(prev["epoch"]) + M7.S_GAP_MIN_S) if prev else time.time()
                need = h["started_epoch"] + M7.HAL_PRE_START_BC_S
                if expected_start < need:
                    self.wait_until(need, f"HAL pre-start before {label}")
                rc = self.run_attempt("s", index, attempt, label, ["--min-gap-s", str(M7.S_GAP_MIN_S)], legacy=True)
                rec = self.start_record(label, "s", index, attempt)
                t = rec["times"]
                stop_at = (t["window_end_host_epoch"] + M7.HAL_S_AFTER_WINDOW_S) if t.get("window_end_host_epoch") else time.time() + 60
                self.hal_stop_at(h, stop_at, f"window end + {M7.HAL_S_AFTER_WINDOW_S} s" if t.get("window_end_host_epoch") else "no window end (fallback 60 s)")
                self.event(what="run_end", label=label, run_kind="s", index=index, attempt=attempt, rc=rc, letter=e.get("letter"), s_block=e.get("s_block"),
                           hal_csv=h["csv"], hal_started_epoch=h["started_epoch"], hal_stop_at_epoch=stop_at, start_state=s0, **self.charge_fields(s0, t.get("host_start_epoch")), **rec)
                self.state["items"].setdefault(str(index), {})[f"attempt{attempt}"] = rc
                self.save_state()
                self.check_stop_rc(rc, label)
                if rc == 0 or attempt == 2:
                    if rc != 0:
                        self.state["invalid_twice"].append(index)
                        self.log(f"INVALID_TWICE: {label}")
                    break
                self.log(f"RETRY: resting {self.args.retry_rest_s} s before attempt 2 of {label} (rc={rc})")
                self.state["retries"] += 1
                time.sleep(self.args.retry_rest_s)
                attempt = 2

    def do_smoke(self, which: str) -> None:
        plan_kind = {"p": "p", "k": "k", "s": "s"}[which]
        plan = self.plans[plan_kind]
        sm = plan["smoke"][0]
        label = sm["name"]
        self.safety(f"before smoke {label}")
        s0 = self.phone_state()
        h = self.hal_start(f"smoke_{label}")
        self.wait_until(h["started_epoch"] + M7.HAL_PRE_START_P_S, "HAL pre-start before smoke")
        # smoke = 판정 밖: K smoke skips the precheck (time_scale 10); P / S smokes keep SOC · plugged checks but not the 20 min start-band wait
        extra = ["--skip-precheck"] if which == "k" else ["--band-wait-s", "0"]
        rc = self.run_attempt(plan_kind, sm["index"], 1, label, extra, legacy=(which == "s"), smoke=label)
        folder = self.base / ROOT_BY_KIND["smoke"] / f"S26_MIXREQ_SMOKE_{label}_a1"
        t = self.session_times(folder)
        stop_at = (t["origin_host_epoch"] + M7.HAL_P_AFTER_ORIGIN_S) if t.get("origin_host_epoch") else time.time() + 30
        self.wait_until(stop_at, "smoke HAL tail")
        self.hal_stop(h, "smoke end")
        v = read_json(folder / "validated.json") or {}
        self.event(what="run_end", label=label, run_kind="smoke", index=sm["index"], attempt=1, rc=rc, smoke=which, hal_csv=h["csv"], times=t, validated=v.get("eligible"),
                   reasons=v.get("reasons"), start_state=s0, power_coverage_after_last_available_s=M7.coverage_after(t.get("last_lane_available_host_epoch"), t.get("last_power_sample_host_epoch")),
                   hal_coverage_after_last_available_s=M7.coverage_after(t.get("last_lane_available_host_epoch"), h.get("stopped_epoch")))
        self.state["items"][label] = dict(attempt1=rc)
        self.save_state()

    def charge_rest(self) -> None:
        """등록 §2-4 · 프롬프트: 충전은 부 사이 · 분리 → 첫 실행 ≥ 1,200 s. plugged 이면 '케이블 뽑으세요' 를 남기고 60 s 폴 (≤ 3 h), 분리 시각 + 1,200 s 까지 대기."""
        t0 = time.time()
        while True:
            s = self.phone_state()
            if not s["plugged"]:
                break
            if time.time() - t0 > 3 * 3600:
                raise Stop("still plugged after 3 h — operator: 케이블 뽑으세요")
            self.log(f"PLUGGED (SOC {s['soc']}): 케이블 뽑으세요 — waiting 60 s (분리 뒤 20 min 쉼 자동)")
            self.event(what="charge_wait", soc=s["soc"], plugged=True)
            time.sleep(60)
        d = s.get("last_power_disconnected_epoch")
        if d and s.get("unplugged_since_last_disconnect"):
            until = d + M7.CHARGE_TO_FIRST_RUN_MIN_S
            if time.time() < until:
                self.log(f"charge rest: last disconnect {s['last_power_disconnected']} -> first run not before +{M7.CHARGE_TO_FIRST_RUN_MIN_S} s ({dt.datetime.fromtimestamp(until).isoformat(timespec='seconds')})")
                self.wait_until(until, "charge rest 20 min after unplug")

    # ------------------------------------------------------------------ main
    def run(self) -> int:
        items = [int(x) for x in self.args.items.split(",") if x.strip()] if self.args.items else []
        self.log(f"DRIVER START kind={self.kind} items={items} cond={self.args.cond} smoke={self.args.smoke} base={self.base} in_block_charge={self.args.in_block_charge}")
        self.log("NOTE: laptop lid must stay OPEN (Modern Standby stops the PC); screen_off_timeout is kept at 86400000 by every session (no restore)")
        try:
            if self.adb_state() != "device" and not self.wait_adb(self.args.reconnect_wait_s):
                raise Stop("adb not connected at start")
            self.charge_rest()
            if self.kind == "p":
                self.do_p(items, "p")
            elif self.kind == "prep":
                self.do_p(items, "prep")
            elif self.kind == "k":
                self.do_k(items, self.args.cond)
            elif self.kind == "s":
                self.do_s(items)
            elif self.kind == "smoke":
                self.do_smoke(self.args.smoke)
            if not self.state["stop_reason"]:
                self.state["stop_reason"] = "completed"
        except Stop as e:
            self.state["stop_reason"] = str(e)
            self.log(f"STOP: {e}")
        except Exception as e:  # keep the state file · never lose the reason
            self.state["stop_reason"] = f"error {e!r}"
            self.log(f"ERROR: {e!r}")
            raise
        finally:
            for h in list(self.hal_procs.values()):
                if h["proc"].poll() is None and not h.get("stop_scheduled_epoch"):
                    self.hal_stop(h, "driver end")
            self.save_state()
            self.log(f"DRIVER END kind={self.kind} reason={self.state['stop_reason']} retries={self.state['retries']} invalid_twice={self.state['invalid_twice']} "
                     f"pre_start_moves={len(self.state['pre_start_moves'])} lock_waits={self.state['lock_waits']}")
        return 0 if self.state["stop_reason"] == "completed" else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kind", required=True, choices=("p", "prep", "k", "s", "smoke"))
    ap.add_argument("--items", default="", help="plan indices, comma separated (p: 12..41 · prep: 42..51 · k: 4..18 · s: 16..27)")
    ap.add_argument("--cond", choices=("A", "B", "C"), help="K only: override the plan condition (normally taken from plan_m7k)")
    ap.add_argument("--smoke", choices=("p", "k", "s"), help="--kind smoke: which plan's smoke manifest")
    ap.add_argument("--results-base", default="")
    ap.add_argument("--retry-rest-s", type=int, default=600)
    ap.add_argument("--reconnect-wait-s", type=int, default=600)
    ap.add_argument("--lock-wait-s", type=int, default=3600)
    ap.add_argument("--in-block-charge", action="store_true")
    ap.add_argument("--band-wait-s", type=int, default=None, help="override the session start-band wait (seconds · 0 = proceed at once · marked out_of_band)")
    args = ap.parse_args()
    if args.kind == "smoke" and not args.smoke:
        raise SystemExit("--kind smoke needs --smoke p|k|s")
    return Driver(args).run()


if __name__ == "__main__":
    sys.exit(main())
