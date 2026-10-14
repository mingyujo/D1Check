"""coverage_check (2026-10-14 · session_m8.json coverage_check · 조민규 답 10/14 §5) — 세션의 실제 계측 창을 앱 power 와 host HAL 로 **따로** 검사한다 (이어붙임 0 · 보간 0 · tail 외삽 0).

  py -3 -X utf8 s26/tools/mixreq/coverage_check.py <session folder> [--hal-cont <hal_cont csv>] [--out coverage.json]
  py -3 -X utf8 s26/tools/mixreq/coverage_check.py --m7 --results results --compare s26/results/m7_1013/derived_1014/coverage_m7.csv --out <json>

App (progress.jsonl power_sample · 기기 시계 mono_ns · common 기준 s): valid = current_valid true & current_raw not null · 결측 = 나머지 (셈 · 메우지 않음) ·
  pre_t0 ≥ 60 s · post_t0 ≥ 210 s · 0/35/120/180 양측 표본 (gap ≤ 2.5 s) · 최대 gap 기록 · 방전 음수 (양수 = FAIL 이유) · 단위 µA (API 명목).
Host (hal_cont CSV · device_uptime_s = 같은 boottime 시계): AP 첫/마지막 (common 기준) · pre ≥ 60 · post ≥ 210 · AP 35/180 양측 (gap ≤ 5 s) · current_now/voltage 0/180 양측 · err 행 = 결측.
Result = app PASS/FAIL + reasons · host PASS/FAIL + reasons · overall = both. 상수 = session_m8.json v1 (DEV 확정 · 확인 전 봉인). host J180 은 계산하지 않는다.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402
import m8_common as M8  # noqa: E402

SCHEMA = "s26-m8-coverage-check-v1"


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def both_sides(times: list[float], t: float, max_gap: float) -> dict:
    before = [x for x in times if x <= t]
    after = [x for x in times if x >= t]
    b = max(before) if before else None
    a = min(after) if after else None
    gap = (a - b) if (a is not None and b is not None) else None
    return dict(point_s=t, before_s=None if b is None else round(b, 3), after_s=None if a is None else round(a, 3), gap_s=None if gap is None else round(gap, 3),
                ok=(gap is not None and gap <= max_gap), max_gap_s=max_gap)


def read_power(progress: Path) -> tuple[int | None, list[dict], dict]:
    cs, samples, misc = None, [], dict(kinds=0)
    if not progress.is_file():
        return None, [], misc
    with open(progress, encoding="utf-8") as f:
        for line in f:
            if '"common_start"' not in line and '"power_sample"' not in line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("kind") == "common_start":
                cs = int(e["mono_ns"])
            elif e.get("kind") == "power_sample":
                samples.append(dict(t=int(e["mono_ns"]), current=e.get("current_raw"), valid=(e.get("current_valid") is True and e.get("current_raw") is not None),
                                    charge=e.get("charge_counter_raw"), voltage=e.get("voltage_mV")))
    return cs, samples, misc


def hal_cont_rows(p: Path | None) -> list[dict]:
    rows = []
    if not p or not Path(p).is_file():
        return rows
    with open(p, encoding="utf-8-sig", errors="replace", newline="") as f:
        for r in csv.DictReader(f):
            rows.append(dict(boot=num(r.get("device_uptime_s")), host_ms=num(r.get("host_ms")), AP=num(r.get("AP")), SKIN=num(r.get("SKIN")),
                             current=num(r.get("current_now_uA")), voltage=num(r.get("voltage_mV")), err=(r.get("err") or "")))
    return rows


def check_app(cs: int | None, samples: list[dict], scale: int = 1) -> dict:
    out = dict(unit="current_raw µA (BatteryManager CURRENT_NOW · 방전 음수 · 기기 스케일 미검증) · charge_counter µAh · voltage mV", clock="common 기준 s (기기 boottime · time_scale 로 되돌림)",
               samples=len(samples), valid=0, missing=0, reasons=[], passed=False)
    if cs is None:
        out["reasons"].append("no common_start")
        return out
    valid = [s for s in samples if s["valid"]]
    ts = sorted((s["t"] - cs) / 1e9 * scale for s in valid)
    gaps = [b - a for a, b in zip(ts, ts[1:])]
    out.update(valid=len(valid), missing=len(samples) - len(valid), first_valid_s=round(ts[0], 3) if ts else None, last_valid_s=round(ts[-1], 3) if ts else None,
               interval_median_s=round(statistics.median(gaps), 3) if gaps else None, max_gap_s=round(max(gaps), 3) if gaps else None,
               pre_t0_s=round(-ts[0], 3) if ts else None, post_t0_s=round(ts[-1], 3) if ts else None,
               sign_discharge_negative=all((s["current"] or 0) <= 0 for s in valid) if valid else None, positive_samples=sum(1 for s in valid if (s["current"] or 0) > 0),
               charge_counter_changes=sum(1 for a, b in zip(valid, valid[1:]) if a["charge"] != b["charge"]), voltage_changes=sum(1 for a, b in zip(valid, valid[1:]) if a["voltage"] != b["voltage"]),
               points={str(int(p)): both_sides(ts, p, M8.APP_MAX_GAP_S) for p in M8.APP_POINTS_S},
               rules=dict(pre_t0_min_s=M8.APP_PRE_T0_MIN_S, post_t0_min_s=M8.APP_POST_T0_MIN_S, max_gap_s=M8.APP_MAX_GAP_S, points_s=list(M8.APP_POINTS_S)))
    if not ts:
        out["reasons"].append("no valid power_sample")
        return out
    if out["pre_t0_s"] < M8.APP_PRE_T0_MIN_S:
        out["reasons"].append(f"pre_t0 {out['pre_t0_s']} < {M8.APP_PRE_T0_MIN_S}")
    if out["post_t0_s"] < M8.APP_POST_T0_MIN_S:
        out["reasons"].append(f"post_t0 {out['post_t0_s']} < {M8.APP_POST_T0_MIN_S}")
    for k, v in out["points"].items():
        if not v["ok"]:
            out["reasons"].append(f"app point {k}s both-sides missing (gap {v['gap_s']})")
    if out["positive_samples"]:
        out["reasons"].append(f"{out['positive_samples']} positive current samples (charging?)")
    out["passed"] = not out["reasons"]
    return out


def check_host(cs: int | None, rows: list[dict], scale: int = 1) -> dict:
    out = dict(unit="HAL ℃ 0.1 (dumpsys thermalservice Current temperatures from HAL) · dumpsys battery current_now µA · voltage mV · 2.3 s 목표 · 갱신 시각 미제공",
               clock="common 기준 s (hal_cont device_uptime_s = 기기 boottime)", rows=len(rows), err_rows=sum(1 for r in rows if r["err"]), reasons=[], passed=False)
    if cs is None:
        out["reasons"].append("no common_start")
        return out
    t0 = cs / 1e9
    ap = sorted((r["boot"] - t0) * scale for r in rows if r["boot"] is not None and r["AP"] is not None and not r["err"])
    iv = sorted((r["boot"] - t0) * scale for r in rows if r["boot"] is not None and r["current"] is not None and r["voltage"] is not None and not r["err"])
    gaps = [b - a for a, b in zip(ap, ap[1:])]
    out.update(ap_first_s=round(ap[0], 3) if ap else None, ap_last_s=round(ap[-1], 3) if ap else None, ap_rows=len(ap), iv_rows=len(iv),
               interval_median_s=round(statistics.median(gaps), 3) if gaps else None, max_gap_s=round(max(gaps), 3) if gaps else None,
               pre_t0_s=round(-ap[0], 3) if ap else None, post_t0_s=round(ap[-1], 3) if ap else None,
               ap_points={str(int(p)): both_sides(ap, p, M8.HAL_MAX_GAP_S) for p in M8.HAL_AP_POINTS_S}, iv_points={str(int(p)): both_sides(iv, p, M8.HAL_MAX_GAP_S) for p in M8.HAL_IV_POINTS_S},
               rules=dict(pre_t0_min_s=M8.APP_PRE_T0_MIN_S, post_t0_min_s=M8.APP_POST_T0_MIN_S, max_gap_s=M8.HAL_MAX_GAP_S, ap_points_s=list(M8.HAL_AP_POINTS_S), iv_points_s=list(M8.HAL_IV_POINTS_S)))
    if not ap:
        out["reasons"].append("no host HAL rows")
        return out
    if out["pre_t0_s"] < M8.APP_PRE_T0_MIN_S:
        out["reasons"].append(f"host pre_t0 {out['pre_t0_s']} < {M8.APP_PRE_T0_MIN_S}")
    if out["post_t0_s"] < M8.APP_POST_T0_MIN_S:
        out["reasons"].append(f"host post_t0 {out['post_t0_s']} < {M8.APP_POST_T0_MIN_S}")
    for k, v in out["ap_points"].items():
        if not v["ok"]:
            out["reasons"].append(f"host AP {k}s both-sides missing (gap {v['gap_s']})")
    for k, v in out["iv_points"].items():
        if not v["ok"]:
            out["reasons"].append(f"host I/V {k}s both-sides missing (gap {v['gap_s']})")
    out["passed"] = not out["reasons"]
    return out


def check_session(folder: Path, hal_cont: Path | None, scale: int | None = None) -> dict:
    device = folder / "device" if (folder / "device").is_dir() else folder
    manifest = C.read_json(device / "manifest.json") if (device / "manifest.json").is_file() else {}
    scale = scale or int(manifest.get("time_scale", 1) or 1)
    cs, samples, _ = read_power(device / "progress.jsonl")
    app = check_app(cs, samples, scale)
    host = check_host(cs, hal_cont_rows(hal_cont), scale)
    return dict(schema=SCHEMA, folder=str(folder), session_id=manifest.get("session_id"), experiment_id=manifest.get("experiment_id"), time_scale=scale, hal_cont=str(hal_cont) if hal_cont else None,
                app=app, host=host, passed=bool(app["passed"] and host["passed"]), reasons=app["reasons"] + host["reasons"],
                separation="앱 power 와 host HAL/battery 는 따로 판정 · 이어붙임 0 · 보간 0 · tail 외삽 0 · host J180 계산 0",
                note="time_scale ≠ 1 (스모크) 은 common 기준 s 를 time_scale 로 되돌려 검사 (판정 밖 · 기록)")


def m7_rows(results: Path) -> list[dict]:
    """A-4 검증: M7-A 세션 (P · PREP · K · S) 을 같은 검사기로 — hal_cont 는 드라이버 run_end 의 times.folder + host_start 로 연결 (derive 와 같은 규칙)."""
    events = [json.loads(l) for l in (results / "S26_M7_driver_events.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    hal_by = {}
    for e in events:
        t = e.get("times") or {}
        if e.get("what") == "run_end" and e.get("hal_csv") and t.get("folder"):
            hal_by[(Path(t["folder"]).name, t.get("host_start"))] = e["hal_csv"]
    out = []
    for root in ("S26_M7_K", "S26_M7_P", "S26_M7_S"):
        d = results / root
        if not d.is_dir():
            continue
        for folder in sorted(p for p in d.iterdir() if p.is_dir()):
            sl = C.read_json(folder / "host" / "session_log.json") if (folder / "host" / "session_log.json").is_file() else {}
            hal = hal_by.get((folder.name.replace("_screenoff_1322", ""), sl.get("start_time")))
            r = check_session(folder, Path(hal) if hal else None)
            r["root"] = root
            out.append(r)
    return out


def compare_with_a4(rows: list[dict], a4_csv: Path) -> dict:
    a4 = {r["folder"]: r for r in csv.DictReader(open(a4_csv, encoding="utf-8-sig", newline=""))}
    diffs, n = [], 0
    for r in rows:
        key = f"{r['root']}/{Path(r['folder']).name}"
        a = a4.get(key)
        if not a or not a.get("app_last_valid_s"):
            continue
        n += 1
        pairs = [("app_last_valid_s", r["app"].get("last_valid_s"), num(a["app_last_valid_s"])),
                 ("app_180_both_sides", r["app"].get("points", {}).get("180", {}).get("ok"), a["app_180_both_sides"] == "True"),
                 ("app_120_both_sides", r["app"].get("points", {}).get("120", {}).get("ok"), a["app_120_both_sides"] == "True"),
                 ("host_ap35_both_sides", r["host"].get("ap_points", {}).get("35", {}).get("ok"), a["host_ap35_both_sides"] == "True"),
                 ("host_ap180_both_sides", r["host"].get("ap_points", {}).get("180", {}).get("ok"), a["host_ap180_both_sides"] == "True"),
                 ("host_iv0_both_sides", r["host"].get("iv_points", {}).get("0", {}).get("ok"), a["host_iv0_both_sides"] == "True"),
                 ("host_iv180_both_sides", r["host"].get("iv_points", {}).get("180", {}).get("ok"), a["host_iv180_both_sides"] == "True"),
                 ("app_missing_samples", r["app"].get("missing"), int(a["app_missing_samples"] or 0))]
        for name, mine, theirs in pairs:
            same = (abs(mine - theirs) < 0.0015) if isinstance(mine, float) and isinstance(theirs, float) else (mine == theirs)
            if not same:
                diffs.append(dict(folder=key, field=name, checker=mine, a4=theirs))
    return dict(compared=n, differences=diffs, same=not diffs)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("session", nargs="?", type=Path)
    ap.add_argument("--hal-cont", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--m7", action="store_true", help="run over the M7-A result roots (A-4 verification)")
    ap.add_argument("--results", type=Path, default=M8.REPO / "results")
    ap.add_argument("--compare", type=Path, help="derived_1014/coverage_m7.csv to compare against (--m7)")
    args = ap.parse_args()
    if args.m7:
        rows = m7_rows(args.results)
        p18 = [r for r in rows if r["root"] == "S26_M7_P"]
        summary = dict(schema=SCHEMA + "-m7", sessions=len(rows), p_sessions=len(p18),
                       p_app_180_both=f"{sum(1 for r in p18 if r['app']['points']['180']['ok'])}/{len(p18)}", p_app_pass=f"{sum(1 for r in p18 if r['app']['passed'])}/{len(p18)}",
                       p_host_ap35=f"{sum(1 for r in p18 if r['host']['ap_points']['35']['ok'])}/{len(p18)}", p_host_ap180=f"{sum(1 for r in p18 if r['host']['ap_points']['180']['ok'])}/{len(p18)}",
                       p_host_iv0=f"{sum(1 for r in p18 if r['host']['iv_points']['0']['ok'])}/{len(p18)}", p_host_iv180=f"{sum(1 for r in p18 if r['host']['iv_points']['180']['ok'])}/{len(p18)}",
                       p_app_post_t0_min_max=[min(r["app"]["post_t0_s"] for r in p18), max(r["app"]["post_t0_s"] for r in p18)],
                       note="M7-A 는 cooling 60 → 앱 post_t0 ≈ 179.5 ~ 179.9 < 210 → 앱 FAIL 이 기대값 (M8 cooling 90 의 근거) · host 는 PASS")
        if args.compare:
            summary["compare_with_a4"] = compare_with_a4(rows, args.compare)
        summary["sessions_detail"] = rows
        if args.out:
            C.write_json(args.out, summary)
        print(json.dumps({k: v for k, v in summary.items() if k != "sessions_detail"}, ensure_ascii=False, indent=1))
        return 0
    if not args.session:
        raise SystemExit("session folder or --m7")
    r = check_session(args.session, args.hal_cont)
    if args.out:
        C.write_json(args.out, r)
    print(json.dumps(dict(passed=r["passed"], reasons=r["reasons"], app_last=r["app"].get("last_valid_s"), host_last=r["host"].get("ap_last_s")), ensure_ascii=False))
    return 0 if r["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
