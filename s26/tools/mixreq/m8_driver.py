"""M8 driver (2026-10-14 · gate_m8.json · session_m8.json · blocks.json · 영훈 추가 지시 10/14 22:2x) — runs blocks.json stages with the M8-apk. Output goes to files only
(console file via m8_driver.ps1 · driver log · events jsonl · prestart ledger); never pipe this into bash. m7_driver (HAL start/stop · phone state · power events) is imported unchanged.

  set ANDROID_SERIAL=<ip:port>
  py -3 -X utf8 s26/tools/mixreq/m8_driver.py --stage smoke [--only SMOKE_M128_BASE,...]        (D-1: 별도 ID · 게이트 없음 (SOC · 잠금만) · 판정 밖)
  py -3 -X utf8 s26/tools/mixreq/m8_driver.py --stage p0   [--only ...]                          (D-2: 계측 4 · 기능 6 · Tref 게이트)
  py -3 -X utf8 s26/tools/mixreq/m8_driver.py --stage dev --block 1                              (D-3: 블록 1 · 19 세션 · 등록 순서)
Per session: safety (SKIN ≥ 43 · status ≥ 3 → STOP) → charge rule (SOC < 20 → "케이블 꽂으세요" · 60 s 폴 · 분리 + 1,200 s 뒤 이어서 · in_block_charge) → HAL ≥ 60 s before →
Tref_day v2 (드라이버 시작 날짜 1회 · 유휴 ≥ 1,200 s 뒤 처음 확보한 안정 60 s AP 창 중앙값 · m8_gate · 블록 안 재산출 0) → START gate (60 s · ≤ 600 s · PRESTART_REJECT → ledger · 그 블록 안 1회 재시도) → m8_session (--skin-band 0,100 ·
--band-wait-s 0 · --hal-cont) → HAL until origin + 300 s → run_end event · retry ONCE (rc 1 · attempt 2) → invalid_twice (folders kept · a2 재사용 0).
Lock: results\\S26_M8_driver.lock (pid). Child session process is killed as a tree (taskkill /T) on STOP / Ctrl-C. No screen_off_timeout restore anywhere.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import m8_common as M8  # noqa: E402
import m8_gate as G  # noqa: E402
import mixreq_common as C  # noqa: E402
import mixreq_session as MS  # noqa: E402
import m7_driver as D7  # noqa: E402

REPO = HERE.parents[2]
PLAN_ROOT = REPO / "s26" / "results" / "m8_prep"
SESSION_PY = HERE / "m8_session.py"
PERFETTO_CFG = HERE / "m8_perfetto_battery.cfg"
PY = sys.executable
ROOT_BY_STAGE = {"smoke": "S26_M8_SMOKE", "p0": "S26_M8_P0", "dev": "S26_M8_DEV", "confirm": "S26_M8_CONFIRM"}
# CONFIRM R21 판 (동결 R21 · 등록 v5): 게이트 상수 고정 — 플래그로 바꾸지 못함 · 사람 강제 START (--gate-force-start) · 고정 유휴 생략 (--no-fixed-idle) 거부
CONFIRM_GATE = dict(tref_band_c=1.0, gate_window_s=120, gate_slope_max=0.2, gate_force_after_s=1800)
CONFIRM_REVISION = "M8_CONFIRM_R21_v2"   # v2 = 앱 arm = index % len 규칙에 맞춘 index (v1 idx 502 앱 거부 · 05:4x 사고)
CONFIRM_REVISIONS = ("M8_CONFIRM_R21_v1", "M8_CONFIRM_R21_v2")
CONFIRM_PLAN_DIRS = ("plan_m8m128_r21", "plan_m8s128_r21", "plan_m8m128_r21v2", "plan_m8s128_r21v2")


def check_confirm_items(man: dict, items: list[dict]) -> None:
    """R21 manifest 의 21 슬롯 밖 (index · session_id · plan_dir · label 조합) 이면 거부 · Perfetto on 거부 · revision_id 확인."""
    if man.get("revision_id") not in CONFIRM_REVISIONS:
        raise SystemExit(f"confirm plan revision {man.get('revision_id')} not in {CONFIRM_REVISIONS}")
    allowed = {(s["plan_dir"], s["index"], s["session_id"], s["label"]) for b in man["stages"]["confirm_blocks"] for s in b["sessions"]}
    if len(allowed) != 21:
        raise SystemExit(f"confirm plan has {len(allowed)} slots (21 expected)")
    for i in items:
        if (i.get("plan_dir"), i.get("index"), i.get("session_id"), i.get("label")) not in allowed or i.get("plan_dir") not in CONFIRM_PLAN_DIRS:
            raise SystemExit(f"slot outside R21 manifest refused: {i.get('label')} idx {i.get('index')} {i.get('plan_dir')}")
        if i.get("perfetto") not in (None, "off"):
            raise SystemExit(f"Perfetto must be OFF in CONFIRM (정책 비교군): {i.get('label')}")
        if i.get("revision_id") != man.get("revision_id"):
            raise SystemExit(f"slot revision_id mismatch: {i.get('label')}")


def now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


class Stop(Exception):
    pass


class Driver(D7.Driver):
    """Reuses m7_driver.Driver helpers (adb · phone_state · power_events · HAL start/stop · hal_rows · session_times · wait_until). Overrides the run loop."""

    def __init__(self, args):
        self.args = args
        self.kind = args.stage
        self.serial = os.environ.get("ANDROID_SERIAL", "")
        if not self.serial:
            raise SystemExit("ANDROID_SERIAL not set")
        self.base = Path(args.results_base) if args.results_base else REPO / "results"
        self.root = self.base / ROOT_BY_STAGE[args.stage]
        self.root.mkdir(parents=True, exist_ok=True)
        self.hal_dir = self.base / "S26_M8_HAL"
        self.hal_dir.mkdir(parents=True, exist_ok=True)
        self.runlog = self.base / "S26_M8_runs.jsonl"
        self.events = self.base / "S26_M8_driver_events.jsonl"
        self.prestart = self.base / "S26_M8_prestart_ledger.jsonl"
        self.tref_file = self.base / "S26_M8_tref.json"
        self.lock = self.base / "S26_M8_driver.lock"
        self.tag = dt.datetime.now().strftime("%m%d_%H%M%S")
        self.driver_log = self.root / f"driver_log_{args.stage}.txt"
        self.state_file = self.root / f"driver_state_{args.stage}_{self.tag}.json"
        self.state = dict(stage=args.stage, block=args.block, driver="m8-v1", started=now_iso(), items={}, stop_reason="", retries=0, invalid_twice=[], prestart_rejects=[],
                          connection_events=0, pre_start_moves=[], lock_waits=0, hal=[], charges=[])
        self.blocks = C.read_json(PLAN_ROOT / "plan_m8" / "blocks.json")
        self.consecutive_conn = 0
        self.hal_procs = {}
        self.child = None
        # CONFIRM 판: 재시작에도 남는 슬롯별 진행 (잔여 휴식 · 거절 한도 · gate_attempt_id) — driver_progress_confirm.json
        self.progress_file = self.root / "driver_progress_confirm.json"
        self.progress = C.read_json(self.progress_file) if (args.stage == "confirm" and self.progress_file.is_file()) else {}
        self.pending_hal = []
        self.host_commit = self.git_head()

    # ------------------------------------------------------------------ CONFIRM 판 helpers
    def git_head(self) -> dict:
        def run(*a):
            try:
                return subprocess.run(["git", *a], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(REPO), timeout=30).stdout.strip()
            except Exception as e:   # noqa: BLE001
                return f"error {e!r}"
        tools = HERE
        return dict(commit=run("rev-parse", "HEAD"), dirty_tools=bool(run("status", "--porcelain", str(tools.relative_to(REPO)))),
                    driver_sha256=C.sha256_bytes(Path(__file__).read_bytes()), readout_r21_sha256=C.sha256_bytes((HERE / "m8_readout_r21.py").read_bytes()) if (HERE / "m8_readout_r21.py").is_file() else None)

    def prog(self, label: str) -> dict:
        return self.progress.setdefault(label, dict(gate_attempts=0, gate_retry_used=False, gate_elapsed_s=0, reject_rest_until=None, attempts={}, driver_restarts=0))

    def save_progress(self):
        if self.args.stage == "confirm":
            C.write_json(self.progress_file, self.progress)

    def sha_file(self, p: str | None) -> str | None:
        try:
            return C.sha256_bytes(Path(p).read_bytes()) if p and Path(p).is_file() else None
        except OSError:
            return None

    def flush_hal_sha(self, wait: bool = False):
        """예약 정지 (origin + 300 s) 가 지난 세션 HAL csv 의 SHA · 행 수를 이벤트로 (gate_attempt_id 별 경로 · SHA)."""
        keep = []
        for p in self.pending_hal:
            if wait and time.time() < p["stop_at"] + 15:
                time.sleep(max(0.0, p["stop_at"] + 15 - time.time()))
            if time.time() >= p["stop_at"] + 15:
                self.event(what="hal_final", label=p["label"], attempt=p["attempt"], gate_attempt_id=p["gate_attempt_id"], csv=p["csv"], sha256=self.sha_file(p["csv"]), rows=self.hal_row_count(Path(p["csv"])))
            else:
                keep.append(p)
        self.pending_hal = keep

    def app_resident(self) -> dict:
        out = (self.adb("shell", f"pidof {C.APP_PACKAGE}", timeout=20) or "").strip()
        return dict(app_pid_present=bool(out), resident_note="START 직전 앱 프로세스 존재 (resident) · 런타임 상주 여부는 앱 warmup 기록")

    def prev_run(self, before_epoch: float) -> dict:
        if not self.runlog.is_file():
            return {}
        ends = [json.loads(l) for l in self.runlog.read_text(encoding="utf-8").splitlines() if l.strip()]
        ends = [r for r in ends if r.get("event") == "end" and float(r.get("epoch", 0)) < before_epoch]
        if not ends:
            return {}
        e = ends[-1]
        return dict(prev_label=e.get("label"), prev_end=e.get("t"), prev_end_epoch=e.get("epoch"), rest_s=round(before_epoch - float(e["epoch"]), 1))

    # ------------------------------------------------------------------ lock · process tree
    def acquire_lock(self):
        if self.lock.is_file():
            pid = self.lock.read_text(encoding="utf-8").strip()
            alive = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout or ""   # 10/15 10:02: stdout None → TypeError 고침
            if pid and pid in alive:
                raise SystemExit(f"driver lock held by pid {pid} ({self.lock}) — refuse to start")
            self.log(f"stale lock (pid {pid}) removed")
        self.lock.write_text(str(os.getpid()), encoding="utf-8")

    def release_lock(self):
        if self.lock.is_file() and self.lock.read_text(encoding="utf-8").strip() == str(os.getpid()):
            self.lock.unlink()

    def kill_child(self, why: str):
        if self.child and self.child.poll() is None:
            self.log(f"killing session process tree pid={self.child.pid} ({why})")
            subprocess.run(["taskkill", "/PID", str(self.child.pid), "/T", "/F"], capture_output=True)
            self.event(what="child_killed", pid=self.child.pid, why=why)

    # ------------------------------------------------------------------ session subprocess (Popen so the tree can be killed)
    def run_session(self, plan_dir: Path, index: int | None, smoke: str | None, attempt: int, label: str, hal_csv: str, extra: list[str]) -> int:
        root = self.results_root(plan_dir, smoke)
        argv = [PY, "-X", "utf8", str(SESSION_PY), "--plan", str(plan_dir), "--attempt", str(attempt), "--results", str(root), "--runlog", str(self.runlog),
                "--label", label, "--allow-settings-mismatch", "--skin-band", "0,100", "--band-wait-s", "0", "--hal-cont", hal_csv, *extra]
        argv += ["--smoke", smoke] if smoke else ["--index", str(index)]
        console = self.root / f"console_{label}_a{attempt}_{dt.datetime.now().strftime('%H%M%S')}.txt"
        self.log(f"RUN {label} plan={plan_dir.name} index={index} smoke={smoke} attempt={attempt} extra={extra} console={console.name}")
        self.event(what="run_start", label=label, plan=plan_dir.name, index=index, smoke=smoke, attempt=attempt, extra=extra)
        with open(console, "w", encoding="utf-8") as out:
            self.child = subprocess.Popen(argv, stdout=out, stderr=subprocess.STDOUT, cwd=str(REPO))
            try:
                rc = self.child.wait()
            except KeyboardInterrupt:
                self.kill_child("KeyboardInterrupt")
                raise
        self.child = None
        self.log(f"RESULT {label} attempt={attempt} rc={rc} (0 valid · 1 invalid · 2 gate · 3 device · 4 stall · 5 folder exists · 6 charge needed · 7 locked · 8 SOC>max)")
        return rc

    def run_attempt(self, plan_dir: Path, index: int | None, smoke: str | None, attempt: int, label: str, hal_csv: str, extra: list[str]) -> int:
        lock_t0 = time.time()
        while True:
            rc = self.run_session(plan_dir, index, smoke, attempt, label, hal_csv, extra)
            if rc == 7:
                self.state["lock_waits"] += 1
                self.save_state()
                if time.time() - lock_t0 >= self.args.lock_wait_s:
                    raise Stop(f"LOCKED for {self.args.lock_wait_s} s at {label}")
                self.log("폰 잠금 해제 부탁 (waiting 60 s, attempt not consumed)")
                time.sleep(60)
                continue
            if rc == 6:
                st = self.phone_state()
                if st.get("soc") is not None and st["soc"] >= M8.SOC_MIN_START and not st["plugged"]:
                    self.consecutive_conn += 1
                    self.log(f"rc 6 but phone reads SOC={st['soc']} plugged={st['plugged']} -> transient adb read (x{self.consecutive_conn})")
                    self.event(what="rc6_transient", label=label, attempt=attempt, state=st)
                    if self.consecutive_conn >= 3:
                        raise Stop(f"rc 6 x3 at {label} — adb reads unstable (새 주소 확인)")
                    self.wait_adb(self.args.reconnect_wait_s)
                    time.sleep(30)
                    continue
                return rc
            if rc not in (2, 3, 4):
                self.consecutive_conn = 0
                return rc
            folder = self.host_folder_m8(plan_dir, index, smoke, attempt)
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
                raise Stop(f"CONNECTION x3 at {label} (새 주소)")
            self.wait_adb(self.args.reconnect_wait_s)
            time.sleep(5)

    def results_root(self, plan_dir: Path, smoke: str | None) -> Path:
        """10/15 10:07 사고 2: 세션 폴더 이름 = index + policy 라 실험 (plan_dir) 이 다른 세션끼리 겹침 (B1-00 L64 idx 4 · B1-03 RECENT idx 4 둘 다 FIFO_SERIAL_CG → rc 5) → DEV/P0 는 plan_dir 별 하위 root."""
        if smoke or self.args.stage == "smoke":
            return self.root
        r = self.root / plan_dir.name
        r.mkdir(parents=True, exist_ok=True)
        return r

    def host_folder_m8(self, plan_dir: Path, index: int | None, smoke: str | None, attempt: int) -> Path:
        if smoke:
            return self.root / f"S26_MIXREQ_SMOKE_{smoke}_a{attempt}"
        plan = C.read_json(plan_dir / "plan.json")
        e = next(s for s in plan["sessions"] if s["index"] == index)
        return self.results_root(plan_dir, smoke) / f"S26_MIXREQ_{index:02d}_{e['policy']}_a{attempt}"

    # ------------------------------------------------------------------ charge · Tref · gate
    def safety(self, where: str) -> None:
        """m7_driver.safety + adb 빈 읽기 (SKIN None) 는 연결 문제로 (STOP 아님 · wait_adb)."""
        s = self.phone_state()
        self.log(f"phone {where}: SKIN={s['SKIN']} AP={s['AP']} BAT={s['BAT']} status={s['thermal_status']} SOC={s['soc']} plugged={s['plugged']} last_disconnect={s['last_power_disconnected']}")
        if s["SKIN"] is None and s["soc"] is None:
            self.log("phone_state empty at safety -> adb connection problem · wait_adb")
            self.event(what="adb_lost", where=where)
            if not self.wait_adb(self.args.reconnect_wait_s):
                raise Stop(f"adb lost at {where} (새 주소)")
            s = self.phone_state()
        if (s["SKIN"] is not None and s["SKIN"] >= M8.SAFETY_SKIN_C) or (s["thermal_status"] is not None and s["thermal_status"] >= M8.SAFETY_THERMAL_STATUS):
            self.state["stop_reason"] = f"SAFETY SKIN={s['SKIN']} status={s['thermal_status']} at {where}"
            raise Stop(self.state["stop_reason"])

    def charge_rule(self, label: str):
        """영훈 운영 결정: SOC < 20 → '케이블 꽂으세요 (SOC n)' · 60 s 폴 · plugged 동안 대기 · 분리 + 1,200 s 뒤 이어서 (in_block_charge 표시 · 무효 아님)."""
        s = self.phone_state()
        if s["soc"] is not None and s["soc"] >= M8.SOC_MIN_START and not s["plugged"]:
            return False
        charged = False
        t0 = time.time()
        while True:
            s = self.phone_state()
            if s["soc"] is None:
                # adb 가 비었다 (offline · 끊김) — 충전이 아니라 연결 문제 (D-1 01:34 사고: SOC None 을 '케이블 꽂으세요' 로 잘못 읽음)
                self.log("phone_state empty (SOC None) -> adb connection problem, not charging · wait_adb")
                self.event(what="adb_lost", label=label, where="charge_rule")
                if not self.wait_adb(self.args.reconnect_wait_s):
                    raise Stop(f"adb lost at {label} (reconnect failed within {self.args.reconnect_wait_s} s · 새 주소)")
                continue
            if s["plugged"]:
                charged = True
                if s["soc"] is not None and s["soc"] >= self.args.charge_to_soc:
                    self.log(f"SOC {s['soc']} ≥ {self.args.charge_to_soc}: 케이블 뽑으세요 (분리 + 1,200 s 뒤 이어서)")
                else:
                    self.log(f"charging SOC {s['soc']} (target {self.args.charge_to_soc})")
            elif s["soc"] is None or s["soc"] < M8.SOC_MIN_START:
                self.log(f"케이블 꽂으세요 (SOC {s['soc']}) — waiting 60 s (영훈 하한 {M8.SOC_MIN_START})")
            else:
                break
            self.event(what="charge_wait", label=label, soc=s["soc"], plugged=s["plugged"])
            if time.time() - t0 > 4 * 3600:
                raise Stop("charge wait > 4 h — 케이블 꽂으세요 / 뽑으세요")
            time.sleep(60)
        d = s.get("last_power_disconnected_epoch")
        if charged and d:
            if self.args.no_fixed_idle:
                self.log("charge unplugged -> 고정 유휴 1,200 s 생략 (영훈 10/15 08:xx · 온도 게이트만) · 바로 HAL → 게이트")
                self.state["charges"].append(dict(label=label, unplugged=s.get("last_power_disconnected"), resume_at=now_iso(), fixed_idle_skipped=True))
                self.event(what="charge_rest_skipped", label=label, unplugged=s.get("last_power_disconnected"), reason="영훈 10/15 08:xx 지시 · 온도 조건만")
            else:
                until = d + M8.CHARGE_TO_FIRST_RUN_MIN_S
                self.state["charges"].append(dict(label=label, unplugged=s.get("last_power_disconnected"), resume_at=dt.datetime.fromtimestamp(until).isoformat(timespec="seconds")))
                self.wait_until(until, "charge rest 1,200 s after unplug")
        return charged

    def last_run_end_any(self) -> float | None:
        ends = []
        for f in (self.runlog, self.base / "S26_M7_runs.jsonl", self.base / "S26_M6_runs.jsonl"):
            if f.is_file():
                ends += [json.loads(l)["epoch"] for l in f.read_text(encoding="utf-8").splitlines() if l.strip() and '"end"' in l]
        return max(ends) if ends else None

    def tref_day(self, h: dict) -> dict:
        """Tref_day v2 (조민규 01:5x #5 · m8_gate TREF_DAY_FIRST_STABLE_AP60_V2): 드라이버 시작 날짜에 한 번만 — 직전 실행 끝/충전 분리 뒤 ≥ 1,200 s 유휴 → 같은 준비·유휴 조건의 호스트 HAL 에서
        처음 확보한 안정 60 s AP 창 (|기울기| ≤ 0.1 ℃/min · 표본 ≥ 20 · gap ≤ 5 s) 의 중앙값. 탐색 ≤ 1,200 s · 없으면 "Tref 판정 불가" 원장 + 최소 |기울기| 창 (stable_miss). 블록 안 재산출 0 (S26_M8_tref.json 날짜별 · sealed)."""
        day = self.state["started"][:10]
        key = self.args.tref_key or day
        store = C.read_json(self.tref_file) if self.tref_file.is_file() else {}
        if key in store and store[key].get("tref_c") is not None:
            return store[key]
        s = self.phone_state()
        anchors = [x for x in (self.last_run_end_any(), s.get("last_power_disconnected_epoch")) if x]
        idle_from = max(anchors) if anchors else time.time()
        if self.args.no_fixed_idle:
            # 영훈 10/15 08:xx: 고정 유휴 1,200 s 생략 · HAL 시작부터 바로 안정 60 s 창 탐색 (온도 조건만 · 탐색 상한 없음)
            search_from = h["started_epoch"]
            self.log(f"Tref key={key} (v2 AP 첫 안정 60 s · 영훈 지시 --no-fixed-idle: 유휴 1,200 s 생략 · 탐색 상한 없음): idle since {dt.datetime.fromtimestamp(idle_from).isoformat(timespec='seconds')} ({round(time.time() - idle_from)} s 전) -> search from HAL start {dt.datetime.fromtimestamp(search_from).isoformat(timespec='seconds')}")
        else:
            search_from = max(idle_from + M8.TREF_IDLE_S, h["started_epoch"])
            self.log(f"Tref key={key} (v2 AP 첫 안정 60 s): idle since {dt.datetime.fromtimestamp(idle_from).isoformat(timespec='seconds')} -> search from {dt.datetime.fromtimestamp(search_from).isoformat(timespec='seconds')}")
        self.wait_until(search_from + M8.TREF_WINDOW_S, "Tref idle ≥ 1,200 s + 60 s")
        checks = []
        undecidable_logged = False
        while True:
            cand = G.tref_candidate(self.hal_rows(Path(h["csv"])), search_from, time.time())
            cand["t"] = now_iso()
            checks.append({k: v for k, v in cand.items() if k not in ("status",)})
            self.log(f"Tref candidate AP median {cand['tref_c']} slope {cand.get('ap_slope_c_per_min')} samples {cand.get('ap_samples')} gap {cand.get('max_gap_s')} windows {cand.get('checked_windows')} -> {'stable' if cand['stable'] else cand.get('reason')}")
            if cand["stable"]:
                break
            if self.args.stage == "confirm" and time.time() - search_from >= M8.TREF_SEARCH_MAX_S:
                # CONFIRM 판 (동결 v1 next_driver_confirm): stable_miss = TREF_UNDECIDABLE · 최소 |기울기| 창을 Tref 로 쓰지 않음 (대체값 0) → 원장 1회 · 안정 창까지 탐색 계속
                if not undecidable_logged:
                    undecidable_logged = True
                    self.log(f"TREF_UNDECIDABLE ({M8.TREF_SEARCH_MAX_S} s 안 안정 60 s AP 창 없음) -> 대체값 0 · 탐색 계속 (원장)")
                    with open(self.prestart, "a", encoding="utf-8") as f:
                        f.write(json.dumps(dict(t=now_iso(), epoch=time.time(), stage=self.args.stage, label=f"Tref_block {key}", result="TREF_UNDECIDABLE", reason=cand.get("reason"),
                                                note="CONFIRM 판: 대체값 Tref 0 · 안정 창까지 탐색 계속", candidate={k: v for k, v in cand.items() if k != "status"}), ensure_ascii=False, default=str) + "\n")
                    self.event(what="tref_undecidable", key=key, reason=cand.get("reason"))
                time.sleep(M8.GATE_POLL_S)
                continue
            if time.time() - search_from >= M8.TREF_SEARCH_MAX_S and not self.args.no_fixed_idle:
                self.log(f"Tref 판정 불가 (안정 60 s AP 창 없음 · {M8.TREF_SEARCH_MAX_S} s 탐색) -> 최소 |기울기| 창 사용 · stable_miss 표시 (REJECT 아님 · 원장)")
                with open(self.prestart, "a", encoding="utf-8") as f:
                    f.write(json.dumps(dict(t=now_iso(), epoch=time.time(), stage=self.args.stage, label="Tref_day", result="TREF_UNDECIDABLE", reason=cand.get("reason"),
                                            candidate={k: v for k, v in cand.items() if k != "status"}), ensure_ascii=False, default=str) + "\n")
                break
            time.sleep(M8.GATE_POLL_S)
        rec = dict(cand, day=day, key=key, stable_miss=not cand["stable"], checks=checks, idle_from_epoch=idle_from, idle_before_search_s=round(search_from - idle_from), search_from_epoch=search_from, hal_csv=h["csv"], status=G.STATUS,
                   sealed=True, fixed_before_first_dev_policy_run=True, recompute_within_block=False, fixed_idle_skipped=bool(self.args.no_fixed_idle),
                   tref_undecidable_logged=undecidable_logged, stage=self.args.stage,
                   note=("영훈 10/15 08:xx 지시: 충전 뒤 고정 유휴 1,200 s 생략 · 온도 조건 (안정 60 s 창) 만 · 등록 v2 §3-2 와 다른 점" if self.args.no_fixed_idle else None))
        store[key] = rec
        C.write_json(self.tref_file, store)
        self.event(what="tref_day", **{k: v for k, v in rec.items() if k not in ("checks", "t", "what")})   # rec["t"] 는 이벤트 로거의 t 와 겹침 (03:08 TypeError 고침)
        return rec

    def start_decision_v(self, rows, t_now, tref_c, soc, plugged) -> dict:
        """등록 v5 부록 3: START 판정 동안만 창 길이 · 표본 하한 · 기울기 상한을 바꾼다 (Tref 산출은 v2 상수 그대로 · 복원)."""
        if not (self.args.gate_window_s or self.args.gate_slope_max):
            return G.start_decision(rows, t_now, tref_c, soc, plugged)
        keep = (M8.GATE_WINDOW_S, M8.GATE_MIN_SAMPLES, M8.SLOPE_MAX_C_PER_MIN)
        try:
            if self.args.gate_window_s:
                M8.GATE_WINDOW_S = self.args.gate_window_s
                M8.GATE_MIN_SAMPLES = max(20, int(self.args.gate_window_s / 3))   # 120 s → 40 (60 s → 20 과 같은 비율)
            if self.args.gate_slope_max:
                M8.SLOPE_MAX_C_PER_MIN = self.args.gate_slope_max
            d = G.start_decision(rows, t_now, tref_c, soc, plugged)
            d.update(gate_version="v5", window_s_rule=M8.GATE_WINDOW_S, min_samples_rule=M8.GATE_MIN_SAMPLES, slope_max=M8.SLOPE_MAX_C_PER_MIN, band_c=M8.TREF_BAND_C)
            return d
        finally:
            M8.GATE_WINDOW_S, M8.GATE_MIN_SAMPLES, M8.SLOPE_MAX_C_PER_MIN = keep

    def gate(self, label: str, h: dict, tref: dict, stage: str, max_wait_s: int = M8.GATE_MAX_WAIT_S) -> dict:
        """START 게이트 v2: 직전 60 s AP 중앙값 ∈ Tref ± 0.5 · |AP|,|SKIN| 기울기 ≤ 0.1 · SOC ≥ 20 · plugged 0 · 30 s 폴 · ≤ 600 s.
        판정 불가 (표본/gap/결측) = 원장 행 (REJECT 아님) · 600 s 뒤에도 불가 = GATE_UNDECIDABLE (REJECT 와 구분 · 흐름은 같음: 300 s 뒤 1회 더). RECENT 준비 전 = 앱 시작 전 (같은 규칙)."""
        t0 = time.time()
        decisions = []
        undecidable_logged = 0
        while True:
            s = self.phone_state()
            d = self.start_decision_v(self.hal_rows(Path(h["csv"])), time.time(), tref.get("tref_c"), s["soc"], s["plugged"])
            d["t"] = s["t"]
            decisions.append(d)
            self.log(f"gate {label}: AP med {d['ap_median']} (Tref {tref.get('tref_c')}) slopes AP {d['ap_slope_c_per_min']} / SKIN {d['skin_slope_c_per_min']} samples {d['ap_samples']} gap {d['max_gap_s']} SOC {s['soc']} -> {'START' if d['start'] else d['reasons']}")
            if d["start"]:
                return dict(result="start", waited_s=round(time.time() - t0), decisions=decisions, tref=tref.get("tref_c"))
            if not d.get("decidable", True) and undecidable_logged < 3:
                undecidable_logged += 1
                with open(self.prestart, "a", encoding="utf-8") as f:
                    f.write(json.dumps(dict(t=now_iso(), epoch=time.time(), stage=stage, label=label, result="GATE_UNDECIDABLE_POLL", reason=d["reasons"], note="판정 불가 (결측/gap/표본) · REJECT 아님 · 폴 계속"),
                                       ensure_ascii=False, default=str) + "\n")
            if time.time() - t0 >= max_wait_s:
                reason = G.reject_reason(decisions)
                result = "GATE_UNDECIDABLE" if reason == "undecidable" else "PRESTART_REJECT"
                rec = dict(t=now_iso(), epoch=time.time(), stage=stage, label=label, result=result, reason=reason, waited_s=round(time.time() - t0), tref=tref.get("tref_c"),
                           decisions=decisions, note="START 아님 · 계획 coverage 분모 · 실제 서비스율 분모와 구분 · 소비 = 대기 시간" + (" · 판정 불가 (REJECT 아님)" if result == "GATE_UNDECIDABLE" else ""))
                with open(self.prestart, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
                self.state["prestart_rejects"].append(dict(label=label, reason=reason, result=result))
                self.event(what="prestart_reject", label=label, reason=reason, result=result, waited_s=rec["waited_s"])
                return dict(result=result, reason=reason, waited_s=rec["waited_s"], decisions=decisions, tref=tref.get("tref_c"))
            time.sleep(M8.GATE_POLL_S)

    # ------------------------------------------------------------------ perfetto (P0 PERFETTO_ON)
    def perfetto_start(self, label: str) -> dict:
        if not PERFETTO_CFG.is_file():
            return dict(supported="미확인", reason="config missing")
        # P0 PERFETTO_ON_C32 (10/15 03:56): perfetto 가 /data/local/tmp 의 config 를 읽지 못함 (errno 13) → config 를 stdin 으로 (perfetto -c - --txt) · 파일 push 없음
        out = f"/data/misc/perfetto-traces/m8_{label}.perfetto-trace"
        cmd = [MS.ADB, "-s", self.serial, "shell", f"perfetto -c - --txt -o {out}"]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            p.stdin.write(PERFETTO_CFG.read_text(encoding="utf-8"))
            p.stdin.close()
        except OSError as e:
            self.event(what="perfetto", label=label, supported="미지원/오류", detail=f"stdin: {e}")
            return dict(supported="미지원/오류", detail=str(e))
        time.sleep(5)
        if p.poll() is not None:
            err = (p.stdout.read() if p.stdout else "")[:400]
            self.event(what="perfetto", label=label, supported="미지원/오류", detail=self.mask(err))
            return dict(supported="미지원/오류", detail=err)
        self.event(what="perfetto", label=label, supported="running", pid=p.pid, out=out)
        return dict(supported="running", proc=p, out=out)

    def perfetto_stop(self, label: str, rec: dict) -> dict:
        p = rec.get("proc")
        if not p:
            return rec
        self.adb("shell", "pkill -INT perfetto", timeout=30)
        try:
            p.wait(timeout=60)
        except subprocess.TimeoutExpired:
            p.kill()
        local = self.root / f"perfetto_{label}.perfetto-trace"
        r = self.adb("pull", rec["out"], str(local), timeout=300)
        rec = dict(supported="recorded" if local.is_file() else "pull_failed", out=rec["out"], local=str(local), bytes=local.stat().st_size if local.is_file() else None)
        self.event(what="perfetto_stop", label=label, **rec)
        return rec

    # ------------------------------------------------------------------ one planned session (with retry · gate · HAL)
    def do_session(self, item: dict, stage: str):
        label = item["label"]
        plan_dir = PLAN_ROOT / item["plan_dir"]
        smoke = item.get("name") if stage == "smoke" else None
        index = None if smoke else item["index"]
        attempt = 1
        gate_retry_used = False
        gate_elapsed_s = 0
        if smoke:   # 재스모크 (코드 고침 뒤): a1 호스트 폴더가 있으면 a2 자리 · 둘 다 있으면 건너뜀 (앱 attempt 1..2 · 쓴 자리 재사용 0)
            if self.host_folder_m8(plan_dir, index, smoke, 2).exists():
                self.log(f"{label}: smoke a1 · a2 both used -> skip (새 스모크 자리 없음 · 기록)")
                self.event(what="smoke_skipped", label=label, reason="a1 and a2 host folders exist")
                return
            if self.host_folder_m8(plan_dir, index, smoke, 1).exists():
                attempt = 2
                self.log(f"{label}: smoke a1 folder exists -> re-smoke as a2")
        P = self.prog(label) if stage == "confirm" else None
        if P is not None:
            # CONFIRM 판: 재시작 뒤 거절 한도 · 누적 게이트 대기 · 잔여 휴식 복원 (DEV 블록 1 EDD a1→a2 482~526 s 사례)
            if P["gate_attempts"] or P["attempts"]:
                P["driver_restarts"] += 1
                self.log(f"{label}: resume CONFIRM progress (gate_attempts {P['gate_attempts']} · retry_used {P['gate_retry_used']} · elapsed {P['gate_elapsed_s']} s · attempts {P['attempts']})")
                self.event(what="confirm_resume", label=label, progress=P)
            gate_retry_used, gate_elapsed_s = bool(P["gate_retry_used"]), int(P["gate_elapsed_s"])
            a1 = self.host_folder_m8(plan_dir, index, smoke, 1)
            if (C.read_json(a1 / "validated.json") or {}).get("eligible") if (a1 / "validated.json").is_file() else False:
                self.log(f"{label}: a1 already valid -> skip")
                self.event(what="skipped_done", label=label, attempt=1)
                return
            if P.get("reject_rest_until") and time.time() < P["reject_rest_until"] and not (a1.exists() and self.app_started(a1)):
                self.wait_until(P["reject_rest_until"], "잔여 재게이트 휴식 300 s (재시작 복원)")
            if int(item.get("start_attempt") or 1) == 2:
                # R21 v2: 이 슬롯의 a1 = 이전 판에서 소비된 실패 START (prior_consumed · 보존) → 재시도 1회 규칙대로 a2 · a1 끝 + retry_rest_s 잔여 휴식
                a2 = self.host_folder_m8(plan_dir, index, smoke, 2)
                if a2.exists() and self.app_started(a2):
                    self.log(f"{label}: start_attempt 2 and a2 already consumed -> skip")
                    self.event(what="skipped_consumed", label=label)
                    return
                attempt = 2
                pc = (item.get("prior_consumed") or [{}])[-1]
                end = dt.datetime.fromisoformat(pc["end"]).timestamp() if pc.get("end") else time.time()
                self.log(f"{label}: a1 consumed in earlier revision ({pc.get('revision_id')} idx {pc.get('index')} rc {pc.get('rc')}) -> attempt 2 (재시도 1회 규칙)")
                self.event(what="start_attempt_2", label=label, prior_consumed=item.get("prior_consumed"))
                P["attempts"].setdefault("1", dict(rc=pc.get("rc"), end_epoch=end, app_started=True, valid=False, prior_revision=pc.get("revision_id"), index=pc.get("index")))
                self.wait_until(end + self.args.retry_rest_s, f"재시도 휴식 {self.args.retry_rest_s} s (이전 판 a1 끝 기준)")
            self.save_progress()
        if not smoke and attempt == 1 and self.host_folder_m8(plan_dir, index, smoke, 1).exists() and self.app_started(self.host_folder_m8(plan_dir, index, smoke, 1)):
            # 드라이버 재시작 뒤 (10/15 11:2x adb 사고): a1 이 이미 소비됨 (앱 시작) → 바로 a2 (rc 5 로 600 s 낭비 0 · a2 가 있으면 건너뜀)
            if self.host_folder_m8(plan_dir, index, smoke, 2).exists():
                self.log(f"{label}: a1 · a2 host folders both exist -> skip (자리 소비 완료)")
                self.event(what="skipped_consumed", label=label)
                return
            attempt = 2
            self.log(f"{label}: a1 host folder exists (app started) -> resume as a2")
            self.state["retries"] += 1
            if P is not None:
                a1_end = ((P["attempts"].get("1") or {}).get("end_epoch")) or (self.session_times(self.host_folder_m8(plan_dir, index, smoke, 1)).get("host_start_epoch") or time.time())
                self.wait_until(float(a1_end) + self.args.retry_rest_s, f"잔여 재시도 휴식 {self.args.retry_rest_s} s (재시작 복원 · a1 끝 기준)")
        while True:
            self.safety(f"before {label} a{attempt}")
            in_block_charge = self.charge_rule(label)
            s0 = self.phone_state()
            if P is not None:
                P["gate_attempts"] += 1
                gid = P["gate_attempts"]
                while (self.hal_dir / f"hal_cont_{label}_a{attempt}_g{gid}.csv").exists():   # 덮어쓰기 0
                    gid += 1
                P["gate_attempts"] = gid
                self.save_progress()
                h = self.hal_start(f"{label}_a{attempt}_g{gid}")
                h["gate_attempt_id"] = gid
            else:
                h = self.hal_start(f"{label}_a{attempt}")
            self.wait_until(h["started_epoch"] + M8.HAL_PRE_START_S, f"HAL pre-start {M8.HAL_PRE_START_S} s before {label}")
            gate = dict(result="skipped (smoke)")
            if stage != "smoke":
                tref = self.tref_day(h)
                second_max = max(M8.GATE_MAX_WAIT_S, self.args.gate_force_after_s - gate_elapsed_s) if (gate_retry_used and self.args.gate_force_after_s) else M8.GATE_MAX_WAIT_S
                gate = self.gate(label, h, tref, stage, second_max)
                gate_elapsed_s += gate.get("waited_s") or 0
                if gate["result"] in ("PRESTART_REJECT", "GATE_UNDECIDABLE") and self.args.gate_force_after_s and gate_retry_used:
                    # 영훈 10/15 10:5x: 원래 기준 (600 s 거절 → 300 s → 재시도) 그대로 두되 누적 대기가 상한 (기본 1,800 s) 에 닿으면 자리 비우지 않고 START (거절 원장 보존 · forced_start 표시 · 등록 밖)
                    self.log(f"{gate['result']} twice at {label} ({gate['reason']}) · cumulative gate wait {gate_elapsed_s} s ≥ {self.args.gate_force_after_s} -> FORCED START (영훈 완주 지시 · 거절 기록 보존)")
                    self.event(what="gate_forced_start", label=label, reason=gate["reason"], waited_s=gate["waited_s"], cumulative_wait_s=gate_elapsed_s, tref=gate.get("tref"), last=(gate["decisions"] or [{}])[-1])
                    gate = dict(gate, result=gate["result"] + "_FORCED_START", forced_start=True, cumulative_wait_s=gate_elapsed_s, note="영훈 10/15 완주 지시 · 거절 2회 뒤 상한 도달 START · 등록 밖")
                elif gate["result"] in ("PRESTART_REJECT", "GATE_UNDECIDABLE") and self.args.gate_force_start:
                    # 영훈 10/15 10:1x: "기준 온도 안 맞아도 중단하지 말고 무조건 완주" → 600 s 자연 대기 뒤 거절이어도 그 자리에서 START (거절 기록 보존 · out_of_band 표시 · 자리 비움 0 · 안전 정지는 그대로)
                    self.log(f"{gate['result']} at {label} ({gate['reason']}) -> FORCED START (영훈 완주 지시 · 거절 기록 보존 · out_of_band)")
                    self.event(what="gate_forced_start", label=label, reason=gate["reason"], waited_s=gate["waited_s"], tref=gate.get("tref"), last=(gate["decisions"] or [{}])[-1])
                    gate = dict(gate, result=gate["result"] + "_FORCED_START", forced_start=True, note="영훈 10/15 완주 지시 · 온도 조건 미충족 START · 등록 밖")
                elif gate["result"] in ("PRESTART_REJECT", "GATE_UNDECIDABLE"):
                    self.hal_stop(h, gate["result"].lower())
                    self.event(what="run_end", label=label, run_kind=stage, index=index, attempt=attempt, rc=None, prestart_reject=gate["reason"], gate=gate, start_state=s0, item=item,
                               hal_csv=h["csv"], gate_attempt_id=h.get("gate_attempt_id"), hal_sha256=self.sha_file(h["csv"]), hal_rows=self.hal_row_count(Path(h["csv"])))
                    if gate_retry_used:
                        self.log(f"PRESTART_REJECT twice at {label} -> slot left empty (계획 밖 재시도 0)")
                        self.state["items"].setdefault(label, {})["prestart_reject"] = 2
                        self.save_state()
                        if P is not None:
                            P["slot_empty"] = True
                            self.save_progress()
                        return
                    gate_retry_used = True
                    gate_elapsed_s += 300
                    if P is not None:
                        P.update(gate_retry_used=True, gate_elapsed_s=gate_elapsed_s, reject_rest_until=time.time() + 300)
                        self.save_progress()
                    self.log(f"PRESTART_REJECT at {label} ({gate['reason']}) -> one more gate attempt after 300 s (같은 블록 안 1회{' · 상한 ' + str(self.args.gate_force_after_s) + ' s 뒤 강제 START' if self.args.gate_force_after_s else ''})")
                    time.sleep(300)
                    continue
                if P is not None:
                    P.update(gate_retry_used=gate_retry_used, gate_elapsed_s=gate_elapsed_s)
                    self.save_progress()
            perf = None
            if item.get("perfetto") == "on":
                perf = self.perfetto_start(label)
            extra = ["--in-block-charge"] if in_block_charge else []
            # 기존 mixreq 게이트 (start_gate_1005e: SOC 30~100 · SKIN/AP ≤ 32 · BAT ≤ 30) 는 M8 에서 쓰지 않는다 — 영훈 SOC 하한 20 과 충돌 · M8 게이트 = Tref (m8_gate) + precheck (SOC · plugged · 잠금) + 앱 start_check
            extra += ["--skip-gate"]
            pre = None
            if P is not None:
                pre = dict(self.prev_run(time.time()), **self.app_resident(), host_start_wall=now_iso(), hour=dt.datetime.now().hour)
            rc = self.run_attempt(plan_dir, index, smoke, attempt, label, h["csv"], extra)
            if perf is not None:
                perf = self.perfetto_stop(label, perf)
            folder = self.host_folder_m8(plan_dir, index, smoke, attempt)
            t = self.session_times(folder)
            stop_at = (t["origin_host_epoch"] + M8.HAL_AFTER_ORIGIN_S) if t.get("origin_host_epoch") else time.time() + 60
            self.hal_stop_at(h, stop_at, f"origin + {M8.HAL_AFTER_ORIGIN_S} s" if t.get("origin_host_epoch") else "no origin (fallback 60 s)")
            v = C.read_json(folder / "validated.json") if (folder / "validated.json").is_file() else {}
            gate = dict(gate, gate_version=("v5" if (self.args.gate_window_s or self.args.gate_slope_max) else "v4" if self.args.tref_band_c else "v2"), band_c=M8.TREF_BAND_C, window_s=self.args.gate_window_s or M8.GATE_WINDOW_S, slope_max=self.args.gate_slope_max or M8.SLOPE_MAX_C_PER_MIN, in_band=(not gate.get("forced_start", False)) if gate.get("result") else None)
            end_state = self.phone_state()
            extra_ev = {}
            if P is not None:
                last = (gate.get("decisions") or [{}])[-1]
                a7 = ((v.get("rules") or {}).get("A7_wait") or {}).get("detail") or {}
                tr = self.tref_day(h) if stage != "smoke" else {}
                gate_summary = dict(result=gate.get("result"), waited_s=gate.get("waited_s"), cumulative_wait_s=gate_elapsed_s, retry_used=gate_retry_used, forced_gate_auto_1800=bool(gate.get("forced_start")),
                                    in_band=gate.get("in_band"), AP_median=last.get("ap_median"), AP_slope=last.get("ap_slope_c_per_min"), SKIN_slope=last.get("skin_slope_c_per_min"),
                                    ap_samples=last.get("ap_samples"), reasons=last.get("reasons"), gate_version=gate.get("gate_version"), band_c=gate.get("band_c"), window_s=gate.get("window_s"), slope_max=gate.get("slope_max"))
                initial = dict(tref_key=tr.get("key"), tref_block_c=tr.get("tref_c"), gate_result=gate.get("result"), start_AP=s0.get("AP"), start_SKIN=s0.get("SKIN"), start_BAT=s0.get("BAT"),
                               slope_120s_AP=last.get("ap_slope_c_per_min"), gate_AP_median_120s=last.get("ap_median"), SOC_start=s0.get("soc"), SOC_end=end_state.get("soc"),
                               plugged_start=s0.get("plugged"), in_block_charge=in_block_charge, **(pre or {}),
                               human_interventions=0, human_note="사람 START/강제 0 (CONFIRM 판 · --gate-force-start 거부) · 드라이버 재시작 수는 driver_restarts",
                               driver_restarts=P["driver_restarts"], forced_gate_auto_1800=bool(gate.get("forced_start")), auto_wait_count=a7.get("waits"),
                               wait_nominal_total_ms=a7.get("nominal_total_ms"), wait_planned_total_ms=a7.get("planned_total_ms"), wait_dose_total_ms=a7.get("dose_total_ms"),
                               wait_overrun_total_ms=a7.get("overrun_total_ms"), wait_cut=(len(a7.get("cut") or []) if a7 else None),
                               note="초기 상태 기록만 · 군별 보정/재정렬/대체 0")
                extra_ev = dict(initial_state=initial, gate_summary=gate_summary, gate_attempt_id=h.get("gate_attempt_id"), host_commit=self.host_commit, revision_id=item.get("revision_id"),
                                origin_slot=item.get("origin_slot"), v1_index=item.get("v1_index"), prior_consumed=item.get("prior_consumed"))
                P["attempts"][str(attempt)] = dict(rc=rc, end_epoch=time.time(), app_started=self.app_started(folder), valid=v.get("eligible"))
                self.save_progress()
                self.pending_hal.append(dict(label=label, attempt=attempt, gate_attempt_id=h.get("gate_attempt_id"), csv=h["csv"], stop_at=stop_at))
            self.event(what="run_end", label=label, run_kind=stage, index=index, attempt=attempt, rc=rc, item=item, gate=gate, in_block_charge=in_block_charge, perfetto=perf,
                       hal_csv=h["csv"], hal_started_epoch=h["started_epoch"], hal_stop_at_epoch=stop_at, start_state=s0, end_state=end_state, **self.charge_fields(s0, t.get("host_start_epoch")),
                       times=t, validated=v.get("eligible"), reasons=v.get("reasons"), coverage=(v.get("rules") or {}).get("A10_coverage", {}).get("detail"), **extra_ev)
            self.state["items"].setdefault(label, {})[f"attempt{attempt}"] = rc
            self.save_state()
            if rc in (6, 8):
                if rc == 6:
                    self.log(f"rc 6 at {label}: 충전 규칙으로 돌아감 (attempt {attempt} 소비 여부 = 앱 시작 {self.app_started(folder)})")
                    if not self.app_started(folder):
                        if folder.exists():
                            moved = folder.with_name(folder.name + f"_pre{attempt}_{dt.datetime.now().strftime('%H%M%S')}")
                            folder.rename(moved)
                        continue
                else:
                    raise Stop(f"SOC above max at {label}")
            if rc == 0 or attempt == 2 or stage == "smoke":
                if rc != 0 and stage != "smoke":
                    self.state["invalid_twice"].append(label)
                    self.log(f"INVALID_TWICE: {label}")
                elif rc != 0:
                    self.log(f"SMOKE FAIL: {label} (코드 고침 → 재스모크 · 판정 밖)")
                break
            self.log(f"RETRY: resting {self.args.retry_rest_s} s before attempt 2 of {label} (rc={rc})")
            self.state["retries"] += 1
            time.sleep(self.args.retry_rest_s)
            attempt = 2
        if stage != "smoke":
            prev = self.last_run_end()
            if prev:
                self.wait_until(float(prev["epoch"]) + M8.RUN_GAP_MIN_S, "run gap ≥ 90 s")

    def items(self) -> list[dict]:
        st = (C.read_json(Path(self.args.plan_file)) if self.args.plan_file else self.blocks)["stages"]
        if self.args.stage == "smoke":
            lst = st["smoke"]
        elif self.args.stage == "p0":
            lst = st["p0"]
        elif self.args.stage == "confirm":
            man = C.read_json(Path(self.args.plan_file))
            blk = next(b for b in st["confirm_blocks"] if b["block_no"] == self.args.block)
            lst = blk["sessions"]
            check_confirm_items(man, lst)
            for pd, sha in man["plan_sha256"].items():   # 계획 폴더 plan.json SHA = manifest 기록값
                got = C.sha256_bytes((PLAN_ROOT / pd / "plan.json").read_bytes())
                if got != sha:
                    raise SystemExit(f"{pd}/plan.json SHA {got} != manifest {sha}")
        else:
            blk = next(b for b in st["dev_blocks"] if b["block_no"] == self.args.block)
            lst = blk["sessions"]
        if self.args.only:
            keep = set(x.strip() for x in self.args.only.split(",") if x.strip())
            lst = [i for i in lst if i["label"] in keep]
        return lst

    def run(self) -> int:
        items = self.items()
        self.acquire_lock()
        self.log(f"DRIVER START stage={self.args.stage} block={self.args.block} items={[i['label'] for i in items]} base={self.base}")
        self.log("NOTE: laptop lid OPEN · screen_off_timeout 86400000 kept · SOC start min 20 (영훈) · Tref gate = v2 (AP 첫 안정 60 s · 조민규 01:5x 확정)")
        self.log(f"FLAGS: tref_key={self.args.tref_key or '(day)'} no_fixed_idle={self.args.no_fixed_idle} gate_force_start={self.args.gate_force_start} gate_force_after_s={self.args.gate_force_after_s} tref_band_c={M8.TREF_BAND_C} gate_window_s={self.args.gate_window_s or M8.GATE_WINDOW_S} gate_slope_max={self.args.gate_slope_max or M8.SLOPE_MAX_C_PER_MIN} (gate_version={'v5' if (self.args.gate_window_s or self.args.gate_slope_max) else 'v4' if self.args.tref_band_c else 'v2'}) plan_file={self.args.plan_file or '(blocks.json)'}")
        try:
            if self.adb_state() != "device" and not self.wait_adb(self.args.reconnect_wait_s):
                raise Stop("adb not connected at start (새 주소)")
            if self.args.stage == "confirm":
                self.event(what="confirm_driver_start", block=self.args.block, plan_file=self.args.plan_file, plan_file_sha256=C.sha256_bytes(Path(self.args.plan_file).read_bytes()),
                           host_commit=self.host_commit, gate=CONFIRM_GATE, tref_key=self.args.tref_key, revision_id=C.read_json(Path(self.args.plan_file)).get("revision_id"), items=[i["label"] for i in items])
            for item in items:
                done = self.state["items"].get(item["label"], {})
                if done.get("attempt1") == 0 or done.get("attempt2") == 0:
                    continue
                if self.args.stage == "confirm" and self.prog(item["label"]).get("slot_empty"):
                    self.log(f"{item['label']}: slot empty (PRESTART_REJECT 2회 · 재시작 복원) -> skip")
                    continue
                self.flush_hal_sha()
                self.do_session(item, self.args.stage)
            self.flush_hal_sha(wait=True)
            if not self.state["stop_reason"]:
                self.state["stop_reason"] = "completed"
        except Stop as e:
            self.state["stop_reason"] = str(e)
            self.log(f"STOP: {e}")
        except KeyboardInterrupt:
            self.state["stop_reason"] = "interrupted"
            self.kill_child("interrupted")
        except Exception as e:
            self.state["stop_reason"] = f"error {e!r}"
            self.log(f"ERROR: {e!r}")
            raise
        finally:
            self.kill_child("driver end")
            for h in list(self.hal_procs.values()):
                if h["proc"].poll() is None and not h.get("stop_scheduled_epoch"):
                    self.hal_stop(h, "driver end")
            self.save_state()
            self.release_lock()
            self.log(f"DRIVER END stage={self.args.stage} reason={self.state['stop_reason']} retries={self.state['retries']} invalid_twice={self.state['invalid_twice']} prestart_rejects={self.state['prestart_rejects']}")
        return 0 if self.state["stop_reason"] == "completed" else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", required=True, choices=("smoke", "p0", "dev", "confirm"))
    ap.add_argument("--block", type=int, default=1)
    ap.add_argument("--only", default="")
    ap.add_argument("--results-base", default="")
    ap.add_argument("--retry-rest-s", type=int, default=600)
    ap.add_argument("--reconnect-wait-s", type=int, default=600)
    ap.add_argument("--lock-wait-s", type=int, default=3600)
    ap.add_argument("--charge-to-soc", type=int, default=60, help="SOC < 20 로 충전할 때 '뽑으세요' 를 말할 SOC (영훈 운영 · 상한 없음)")
    ap.add_argument("--tref-key", default="", help="S26_M8_tref.json 의 키 (기본 = 드라이버 시작 날짜). 10/15 영훈: 블록 1 (낮) · 블록 2 는 각각 새 측정 구간 → 키를 나눠 재산출 (블록 안 재산출 0 은 그대로)")
    ap.add_argument("--no-fixed-idle", action="store_true", help="영훈 10/15 08:xx: 충전 분리 뒤 1,200 s 고정 유휴 · Tref 전 1,200 s 고정 유휴 생략 — 온도 조건 (안정 60 s 창 · 게이트) 만 적용 · Tref 탐색 상한 없음 (안정 창까지)")
    ap.add_argument("--gate-window-s", type=int, default=0, help="등록 v5 부록 3: START 판정 창 (v2 60 → v5 120 s · 표본 하한 = 창/3) · 0 = v2")
    ap.add_argument("--gate-slope-max", type=float, default=0.0, help="등록 v5 부록 3: START 기울기 상한 ℃/min (v2 0.1 → v5 0.2) · 0 = v2")
    ap.add_argument("--tref-band-c", type=float, default=0.0, help="등록 v4 부록 2 (조민규 10/15 12:4x 답 · 블록 2 · CONFIRM): START 밴드 Tref ± N (v2 0.5 → v4 1.0). 0 = v2 상수 그대로")
    ap.add_argument("--gate-force-after-s", type=int, default=0, help="영훈 10/15 10:5x: 원래 기준 (600 s 거절 → 300 s → 재시도) 뒤에도 거절이면 누적 대기 상한 (예 1800) 에서 START (자리 비움 0 · 거절 원장 보존)")
    ap.add_argument("--gate-force-start", action="store_true", help="영훈 10/15 10:1x: 게이트 600 s 뒤 거절이어도 START (거절 원장 보존 · forced_start 표시 · 자리 비움 0)")
    ap.add_argument("--plan-file", default="", help="blocks.json 대신 쓸 계획 파일 (예: plan_m8/p0_supp.json · stages.p0 한 세션 · P0 보충)")
    args = ap.parse_args()
    if args.stage == "confirm":
        # CONFIRM R21 판: v5 게이트 상수 고정 · 사람 강제 START · 고정 유휴 생략 거부 · R21 manifest 필수
        if args.gate_force_start or args.no_fixed_idle or not args.plan_file or args.only:
            raise SystemExit("confirm: --gate-force-start / --no-fixed-idle / --only refused · --plan-file (R21 manifest) required")
        for k, v in CONFIRM_GATE.items():
            cur = getattr(args, k)
            if cur not in (0, 0.0, v):
                raise SystemExit(f"confirm: {k}={cur} differs from CONFIRM R21 판 {v}")
            setattr(args, k, v)
        if not args.tref_key:
            raise SystemExit("confirm: --tref-key (블록별 Tref_block 키) required")
    if args.tref_band_c:
        M8.TREF_BAND_C = args.tref_band_c   # m8_gate.start_decision / tref_candidate 는 호출 시점의 M8.TREF_BAND_C 를 읽는다 (v2 상수 파일 무변경 · 원장 기록)
    M8.activate()
    return Driver(args).run()


if __name__ == "__main__":
    sys.exit(main())
