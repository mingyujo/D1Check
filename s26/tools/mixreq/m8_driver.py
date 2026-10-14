"""M8 driver (2026-10-14 · gate_m8.json · session_m8.json · blocks.json · 영훈 추가 지시 10/14 22:2x) — runs blocks.json stages with the M8-apk. Output goes to files only
(console file via m8_driver.ps1 · driver log · events jsonl · prestart ledger); never pipe this into bash. m7_driver (HAL start/stop · phone state · power events) is imported unchanged.

  set ANDROID_SERIAL=<ip:port>
  py -3 -X utf8 s26/tools/mixreq/m8_driver.py --stage smoke [--only SMOKE_M128_BASE,...]        (D-1: 별도 ID · 게이트 없음 (SOC · 잠금만) · 판정 밖)
  py -3 -X utf8 s26/tools/mixreq/m8_driver.py --stage p0   [--only ...]                          (D-2: 계측 4 · 기능 6 · Tref 게이트)
  py -3 -X utf8 s26/tools/mixreq/m8_driver.py --stage dev --block 1                              (D-3: 블록 1 · 19 세션 · 등록 순서)
Per session: safety (SKIN ≥ 43 · status ≥ 3 → STOP) → charge rule (SOC < 20 → "케이블 꽂으세요" · 60 s 폴 · 분리 + 1,200 s 뒤 이어서 · in_block_charge) → HAL ≥ 60 s before →
Tref_day (그 날 첫 세션 전 · 유휴 ≥ 1,200 s 뒤 120 s · m8_gate) → START gate (60 s · ≤ 600 s · PRESTART_REJECT → ledger · 그 블록 안 1회 재시도) → m8_session (--skin-band 0,100 ·
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
ROOT_BY_STAGE = {"smoke": "S26_M8_SMOKE", "p0": "S26_M8_P0", "dev": "S26_M8_DEV"}


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

    # ------------------------------------------------------------------ lock · process tree
    def acquire_lock(self):
        if self.lock.is_file():
            pid = self.lock.read_text(encoding="utf-8").strip()
            alive = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True).stdout
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
        root = self.root
        argv = [PY, "-X", "utf8", str(SESSION_PY), "--plan", str(plan_dir), "--attempt", str(attempt), "--results", str(root), "--runlog", str(self.runlog),
                "--label", label, "--allow-settings-mismatch", "--skin-band", "0,100", "--band-wait-s", "0", "--hal-cont", hal_csv, *extra]
        argv += ["--smoke", smoke] if smoke else ["--index", str(index)]
        console = root / f"console_{label}_a{attempt}_{dt.datetime.now().strftime('%H%M%S')}.txt"
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

    def host_folder_m8(self, plan_dir: Path, index: int | None, smoke: str | None, attempt: int) -> Path:
        if smoke:
            return self.root / f"S26_MIXREQ_SMOKE_{smoke}_a{attempt}"
        plan = C.read_json(plan_dir / "plan.json")
        e = next(s for s in plan["sessions"] if s["index"] == index)
        return self.root / f"S26_MIXREQ_{index:02d}_{e['policy']}_a{attempt}"

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
        """그 날 (local date) 의 Tref_day 를 한 번만 산출: 직전 실행 끝/충전 분리 뒤 ≥ 1,200 s 유휴 → 120 s SKIN 중앙값 (m8_gate.tref_candidate). 파일 S26_M8_tref.json 에 날짜별 보관."""
        day = dt.date.today().isoformat()
        store = C.read_json(self.tref_file) if self.tref_file.is_file() else {}
        if day in store and store[day].get("tref_c") is not None:
            return store[day]
        s = self.phone_state()
        anchors = [x for x in (self.last_run_end_any(), s.get("last_power_disconnected_epoch")) if x]
        idle_from = max(anchors) if anchors else time.time()
        target = max(idle_from + M8.TREF_IDLE_S, h["started_epoch"] + M8.TREF_WINDOW_S)
        self.log(f"Tref_day {day}: idle since {dt.datetime.fromtimestamp(idle_from).isoformat(timespec='seconds')} -> window ends ≥ {dt.datetime.fromtimestamp(target).isoformat(timespec='seconds')}")
        self.wait_until(target, "Tref idle ≥ 1,200 s")
        t_check0 = time.time()
        checks = []
        while True:
            cand = G.tref_candidate(self.hal_rows(Path(h["csv"])), time.time())
            cand["t"] = now_iso()
            checks.append(cand)
            self.log(f"Tref candidate SKIN median {cand['tref_c']} slope {cand['skin_slope_c_per_min']} samples {cand['samples']} -> {'stable' if cand['stable'] else 'not yet'}")
            if cand["stable"] or time.time() - t_check0 >= M8.TREF_IDLE_S:
                break
            time.sleep(60)
        rec = dict(cand, day=day, stable_miss=not cand["stable"], checks=checks, idle_from_epoch=idle_from, hal_csv=h["csv"], status=G.STATUS, sealed=False)
        store[day] = rec
        C.write_json(self.tref_file, store)
        self.event(what="tref_day", **{k: v for k, v in rec.items() if k != "checks"})
        return rec

    def gate(self, label: str, h: dict, tref: dict, stage: str) -> dict:
        t0 = time.time()
        decisions = []
        while True:
            s = self.phone_state()
            d = G.start_decision(self.hal_rows(Path(h["csv"])), time.time(), tref.get("tref_c"), s["soc"], s["plugged"])
            d["t"] = s["t"]
            decisions.append(d)
            self.log(f"gate {label}: SKIN med {d['skin_median']} (Tref {tref.get('tref_c')}) slopes {d['skin_slope_c_per_min']}/{d['ap_slope_c_per_min']} SOC {s['soc']} -> {'START' if d['start'] else d['reasons']}")
            if d["start"]:
                return dict(result="start", waited_s=round(time.time() - t0), decisions=decisions, tref=tref.get("tref_c"))
            if time.time() - t0 >= M8.GATE_MAX_WAIT_S:
                reason = G.reject_reason(decisions)
                rec = dict(t=now_iso(), epoch=time.time(), stage=stage, label=label, result="PRESTART_REJECT", reason=reason, waited_s=round(time.time() - t0), tref=tref.get("tref_c"),
                           decisions=decisions, note="START 아님 · 계획 coverage 분모 · 실제 서비스율 분모와 구분 · 소비 = 대기 시간")
                with open(self.prestart, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
                self.state["prestart_rejects"].append(dict(label=label, reason=reason))
                self.event(what="prestart_reject", label=label, reason=reason, waited_s=rec["waited_s"])
                return dict(result="PRESTART_REJECT", reason=reason, waited_s=rec["waited_s"], decisions=decisions, tref=tref.get("tref_c"))
            time.sleep(M8.GATE_POLL_S)

    # ------------------------------------------------------------------ perfetto (P0 PERFETTO_ON)
    def perfetto_start(self, label: str) -> dict:
        if not PERFETTO_CFG.is_file():
            return dict(supported="미확인", reason="config missing")
        self.adb("push", str(PERFETTO_CFG), "/data/local/tmp/mixreq/perfetto_battery.cfg", timeout=60)
        out = f"/data/misc/perfetto-traces/m8_{label}.perfetto-trace"
        cmd = [MS.ADB, "-s", self.serial, "shell", f"perfetto -c /data/local/tmp/mixreq/perfetto_battery.cfg --txt -o {out}"]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
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
        while True:
            self.safety(f"before {label} a{attempt}")
            in_block_charge = self.charge_rule(label)
            s0 = self.phone_state()
            h = self.hal_start(f"{label}_a{attempt}")
            self.wait_until(h["started_epoch"] + M8.HAL_PRE_START_S, f"HAL pre-start {M8.HAL_PRE_START_S} s before {label}")
            gate = dict(result="skipped (smoke)")
            if stage != "smoke":
                tref = self.tref_day(h)
                gate = self.gate(label, h, tref, stage)
                if gate["result"] == "PRESTART_REJECT":
                    self.hal_stop(h, "prestart reject")
                    self.event(what="run_end", label=label, run_kind=stage, index=index, attempt=attempt, rc=None, prestart_reject=gate["reason"], gate=gate, start_state=s0, item=item)
                    if gate_retry_used:
                        self.log(f"PRESTART_REJECT twice at {label} -> slot left empty (계획 밖 재시도 0)")
                        self.state["items"].setdefault(label, {})["prestart_reject"] = 2
                        self.save_state()
                        return
                    gate_retry_used = True
                    self.log(f"PRESTART_REJECT at {label} ({gate['reason']}) -> one more gate attempt after 300 s (같은 블록 안 1회)")
                    time.sleep(300)
                    continue
            perf = None
            if item.get("perfetto") == "on":
                perf = self.perfetto_start(label)
            extra = ["--in-block-charge"] if in_block_charge else []
            # 기존 mixreq 게이트 (start_gate_1005e: SOC 30~100 · SKIN/AP ≤ 32 · BAT ≤ 30) 는 M8 에서 쓰지 않는다 — 영훈 SOC 하한 20 과 충돌 · M8 게이트 = Tref (m8_gate) + precheck (SOC · plugged · 잠금) + 앱 start_check
            extra += ["--skip-gate"]
            rc = self.run_attempt(plan_dir, index, smoke, attempt, label, h["csv"], extra)
            if perf is not None:
                perf = self.perfetto_stop(label, perf)
            folder = self.host_folder_m8(plan_dir, index, smoke, attempt)
            t = self.session_times(folder)
            stop_at = (t["origin_host_epoch"] + M8.HAL_AFTER_ORIGIN_S) if t.get("origin_host_epoch") else time.time() + 60
            self.hal_stop_at(h, stop_at, f"origin + {M8.HAL_AFTER_ORIGIN_S} s" if t.get("origin_host_epoch") else "no origin (fallback 60 s)")
            v = C.read_json(folder / "validated.json") if (folder / "validated.json").is_file() else {}
            self.event(what="run_end", label=label, run_kind=stage, index=index, attempt=attempt, rc=rc, item=item, gate=gate, in_block_charge=in_block_charge, perfetto=perf,
                       hal_csv=h["csv"], hal_started_epoch=h["started_epoch"], hal_stop_at_epoch=stop_at, start_state=s0, **self.charge_fields(s0, t.get("host_start_epoch")),
                       times=t, validated=v.get("eligible"), reasons=v.get("reasons"), coverage=(v.get("rules") or {}).get("A10_coverage", {}).get("detail"))
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
        st = self.blocks["stages"]
        if self.args.stage == "smoke":
            lst = st["smoke"]
        elif self.args.stage == "p0":
            lst = st["p0"]
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
        self.log("NOTE: laptop lid OPEN · screen_off_timeout 86400000 kept · SOC start min 20 (영훈) · Tref gate = 제안 v1")
        try:
            if self.adb_state() != "device" and not self.wait_adb(self.args.reconnect_wait_s):
                raise Stop("adb not connected at start (새 주소)")
            for item in items:
                done = self.state["items"].get(item["label"], {})
                if done.get("attempt1") == 0 or done.get("attempt2") == 0:
                    continue
                self.do_session(item, self.args.stage)
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
    ap.add_argument("--stage", required=True, choices=("smoke", "p0", "dev"))
    ap.add_argument("--block", type=int, default=1)
    ap.add_argument("--only", default="")
    ap.add_argument("--results-base", default="")
    ap.add_argument("--retry-rest-s", type=int, default=600)
    ap.add_argument("--reconnect-wait-s", type=int, default=600)
    ap.add_argument("--lock-wait-s", type=int, default=3600)
    ap.add_argument("--charge-to-soc", type=int, default=60, help="SOC < 20 로 충전할 때 '뽑으세요' 를 말할 SOC (영훈 운영 · 상한 없음)")
    args = ap.parse_args()
    M8.activate()
    return Driver(args).run()


if __name__ == "__main__":
    sys.exit(main())
