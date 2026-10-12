"""M6 one session = mixreq_session.Session (unchanged, imported) + M6 operating checks before it + m6_validate. No screen restore.

  set ANDROID_SERIAL=<ip:port>   (never written to any file; logs show <SERIAL>)
  py -3 -X utf8 s26/tools/mixreq/m6_session.py --plan <plan_dir> (--index <i> | --smoke <name>) --results <root> --runlog <runs.jsonl>
      [--attempt 1|2] [--label K1] [--in-block-charge] [--legacy-validate] [--skin-band 29.5,31.5] [--band-wait-s 1200] [--dry-run]

Before the session (등록 M6 v3 §3-4 · 프롬프트 M6-A "폰 · PC 꺼짐 방지"):
  1. screen_off_timeout: get → if != 86400000 put 86400000 and record (results_root/screen_timeout.jsonl) — never restored (M6-A ~ M6-B)
  2. mWakefulness=Awake and keyguard not showing: asleep → KEYCODE_WAKEUP → still asleep / keyguard showing → exit 7 "폰 잠금 해제 부탁"
  3. SOC 30 ~ 90 and unplugged: SOC < 30 or plugged → exit 6 "CHARGE NEEDED (SOC n)" · SOC > 90 → poll 60 s (up to 90 min, then exit 8)
  4. start SKIN band 29.5 ~ 31.5 ℃: poll 60 s up to --band-wait-s (20 min); still outside → proceed and mark out_of_band
  one line per attempt → results_root/start_band.jsonl (same file / form as M5) and the run log (--runlog, all M6 runs: E · K · P · smoke ·
  regression) gets start / end records → 직전 실행 · 끝 시각 · 간격 for the session table.
Then mixreq_session.Session.run() exactly as R3/R4/M5 (90 s gap · start_gate_1005e · settings · push · logcat · watches · warmup gate ·
observe · pull) with two replacements: Session.restore_settings = check-only (screen_off_timeout stays 86400000; logs the value) and
V.validate → m6_validate.validate (M6 experiments) or mixreq_validate.validate unchanged (--legacy-validate, S6 regression on plan_v3c).
Exit codes = mixreq_session (0 valid · 1 invalid · 2 gate · 3 device · 4 stall · 5 folder exists · 6 charge needed) + 7 locked · 8 SOC > 90.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import time
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402
import mixreq_session as MS  # noqa: E402
import mixreq_validate as V  # noqa: E402
import m6_common as M  # noqa: E402
import m6_validate as MV  # noqa: E402

SCREEN_TIMEOUT = "86400000"


def adb(serial: str, *argv, timeout=30) -> str:
    return subprocess.run([MS.ADB, "-s", serial, *argv], capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace").stdout


def now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def append_jsonl(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def ensure_screen_timeout(serial: str, results: Path, label: str) -> dict:
    before = adb(serial, "shell", "settings get system screen_off_timeout").strip()
    rec = dict(t=now_iso(), label=label, before=before, put=False)
    if before != SCREEN_TIMEOUT:
        adb(serial, "shell", f"settings put system screen_off_timeout {SCREEN_TIMEOUT}")
        rec.update(put=True, after=adb(serial, "shell", "settings get system screen_off_timeout").strip())
        print(f"[{rec['t']}] screen_off_timeout was {before} -> put {SCREEN_TIMEOUT} (after {rec['after']})", flush=True)
    append_jsonl(results / "screen_timeout.jsonl", rec)
    return rec


def awake_state(serial: str) -> dict:
    power = adb(serial, "shell", "dumpsys power")
    wake = re.search(r"mWakefulness=(\w+)", power)
    window = adb(serial, "shell", "dumpsys window")
    shown = re.search(r"isKeyguardShowing=(true|false)", window)
    trust = adb(serial, "shell", "dumpsys trust")
    locked = re.search(r"deviceLocked=(true|false|0|1),", trust)
    return dict(wakefulness=wake.group(1) if wake else None, keyguard_showing=(shown.group(1) == "true") if shown else None,
                device_locked=(locked.group(1) in ("true", "1")) if locked else None)


def ensure_awake(serial: str, results: Path, label: str) -> int:
    s = awake_state(serial)
    rec = dict(t=now_iso(), label=label, first=s)
    if s["wakefulness"] != "Awake":
        adb(serial, "shell", "input keyevent KEYCODE_WAKEUP")
        time.sleep(2)
        s = awake_state(serial)
        rec["after_wakeup"] = s
    ok = s["wakefulness"] == "Awake" and s["keyguard_showing"] is not True and s["device_locked"] is not True
    rec["ok"] = ok
    append_jsonl(results / "awake.jsonl", rec)
    if not ok:
        print(f"[{now_iso()}] 폰 잠금 해제 부탁 — wakefulness={s['wakefulness']} keyguard={s['keyguard_showing']} locked={s['device_locked']} (exit 7)", flush=True)
        return 7
    return 0


def phone_state(serial: str) -> dict:
    th = adb(serial, "shell", "dumpsys thermalservice")
    t = MS.LOGGER.parse_thermalservice(th)
    b = adb(serial, "shell", "dumpsys battery")
    lvl = re.search(r"^\s*level:\s*(\d+)", b, re.M)
    plugged = bool(re.search(r"(AC|USB|Wireless|Dock) powered:\s*true", b))
    bright = adb(serial, "shell", "settings get system screen_brightness").strip()
    mode = adb(serial, "shell", "settings get system screen_brightness_mode").strip()
    return dict(t=now_iso(), SKIN=t["SKIN"], AP=t["AP"], BAT=t["BAT"], thermal_status=t["thermal_status"],
                soc=int(lvl.group(1)) if lvl else None, plugged=plugged, brightness=bright, brightness_mode=mode)


def previous_run(runlog: Path) -> dict | None:
    if not runlog.is_file():
        return None
    ends = [json.loads(l) for l in runlog.read_text(encoding="utf-8").splitlines() if l.strip()]
    ends = [r for r in ends if r.get("event") == "end"]
    return ends[-1] if ends else None


def precheck(args, serial: str, label: str) -> int:
    lo, hi = (float(x) for x in args.skin_band.split(","))
    prev = previous_run(args.runlog)
    rec = dict(label=label, attempt=args.attempt, min_soc=M.SOC_MIN, max_soc=M.SOC_MAX, band=[lo, hi], band_wait_s=args.band_wait_s, polls=[],
               in_block_charge=args.in_block_charge, previous_run=prev)
    if args.dry_run:
        rec.update(result="dry-run")
        return 0
    t0 = time.time()
    high_since = None
    try:
        while True:
            s = phone_state(serial)
            rec["polls"].append(s)
            print(f"[{s['t']}] precheck {label}: SOC={s['soc']} plugged={s['plugged']} SKIN={s['SKIN']} AP={s['AP']} BAT={s['BAT']} status={s['thermal_status']}", flush=True)
            if s["plugged"] or s["soc"] is None or s["soc"] < M.SOC_MIN:
                rec.update(result="charge_needed")
                print(f"CHARGE NEEDED (SOC {s['soc']}) plugged={s['plugged']} (exit 6)", flush=True)
                return 6
            if s["soc"] > M.SOC_MAX:
                high_since = high_since or time.time()
                if time.time() - high_since > 90 * 60:
                    rec.update(result="soc_above_90")
                    print(f"SOC {s['soc']} > {M.SOC_MAX} for 90 min (exit 8)", flush=True)
                    return 8
                time.sleep(60)
                continue
            try:
                skin = float(s["SKIN"])
            except (TypeError, ValueError):
                skin = None
            waited = time.time() - t0
            if skin is not None and lo <= skin <= hi:
                rec.update(result="in_band", start_skin=skin, waited_s=round(waited), start=s)
                return 0
            if waited >= args.band_wait_s:
                rec.update(result="out_of_band_after_wait", start_skin=skin, waited_s=round(waited), start=s)
                print(f"start SKIN {skin} outside {lo}~{hi} after {waited:.0f} s -> proceed (marked out_of_band)", flush=True)
                return 0
            time.sleep(60)
    finally:
        append_jsonl(args.results / "start_band.jsonl", rec)


def patch_session(legacy: bool) -> None:
    def restore_check_only(self):
        if self.dry:
            return
        value = self.shell("settings get system screen_off_timeout").strip()
        self.log(f"screen_off_timeout kept (M6: no restore) = {value}")
        if value != SCREEN_TIMEOUT:
            self.shell(f"settings put system screen_off_timeout {SCREEN_TIMEOUT}")
            self.log(f"screen_off_timeout was {value} -> put {SCREEN_TIMEOUT}")

    MS.Session.restore_settings = restore_check_only
    if not legacy:
        MS.V = types.SimpleNamespace(validate=MV.validate, compare_results=V.compare_results, npu_contract=V.npu_contract)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", required=True, type=Path)
    ap.add_argument("--index", type=int)
    ap.add_argument("--smoke")
    ap.add_argument("--attempt", type=int, default=1, choices=(1, 2))
    ap.add_argument("--results", required=True, type=Path)
    ap.add_argument("--runlog", required=True, type=Path)
    ap.add_argument("--label", help="run label for the run log (K1 · P0 · smoke_B-C · S6 ...)")
    ap.add_argument("--in-block-charge", action="store_true", help="등록 v3 §3-4 표시: 블록 안 충전 뒤 실행")
    ap.add_argument("--legacy-validate", action="store_true", help="S6 regression: mixreq_validate unchanged (plan_v3c)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-gate", action="store_true")
    ap.add_argument("--allow-settings-mismatch", action="store_true")
    ap.add_argument("--min-gap-s", type=int, default=90)
    ap.add_argument("--stall-s", type=int, default=600)
    ap.add_argument("--skin-band", default="29.5,31.5")
    ap.add_argument("--band-wait-s", type=int, default=1200)
    ap.add_argument("--skip-precheck", action="store_true")
    args = ap.parse_args()
    if (args.index is None) == (args.smoke is None):
        raise SystemExit("give exactly one of --index / --smoke")
    args.results.mkdir(parents=True, exist_ok=True)
    serial = MS.os.environ.get("ANDROID_SERIAL", "")
    label = args.label or (args.smoke or f"index{args.index:02d}")
    band_label = args.smoke or f"index{args.index:02d}"
    patch_session(args.legacy_validate)
    if not args.dry_run:
        ensure_screen_timeout(serial, args.results, label)
        rc = ensure_awake(serial, args.results, label)
        if rc:
            return rc
    if not args.skip_precheck:
        rc = precheck(args, serial, band_label)
        if rc:
            return rc
    prev = previous_run(args.runlog)
    if prev and not args.dry_run:   # 등록 §3-4 세션 사이 ≥ 90 s — results root 가 달라도 (K → P · P → K) run log 기준으로
        wait = args.min_gap_s - (time.time() - float(prev.get("epoch", 0)))
        if wait > 0:
            print(f"[{now_iso()}] cross-run gap: sleeping {wait:.0f} s after {prev.get('label')} (min {args.min_gap_s})", flush=True)
            time.sleep(wait)
    append_jsonl(args.runlog, dict(event="start", label=label, kind="session", plan=str(args.plan), index=args.index, smoke=args.smoke,
                                   attempt=args.attempt, results=str(args.results), t=now_iso(), epoch=time.time(), in_block_charge=args.in_block_charge))
    rc = 3
    try:
        rc = MS.Session(args).run()
        return rc
    except SystemExit as e:
        msg = str(e)
        print(msg, flush=True)
        m = re.search(r"\(exit (\d)\)", msg)
        rc = int(m.group(1)) if m else 3
        return rc
    finally:
        append_jsonl(args.runlog, dict(event="end", label=label, kind="session", rc=rc, attempt=args.attempt, t=now_iso(), epoch=time.time()))


if __name__ == "__main__":
    sys.exit(main())
