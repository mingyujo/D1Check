"""M8 readout (response_m8.json session_summary · gate_m8.json after_start) — per-session JSON + inventory. NO ΔJ120/180 · 열 · 정책 비교 (조민규 몫) — 분모 · 단계 · 서비스 70~100 ·
긴급/일반 · 전량완료 · 납기손해 · 미완료 (undispatched/failed/unfinished) · 잔열 표본 위치 (계산 없음) · WAIT dose · 준비 · readback · PRESTART ledger 만.

  py -3 -X utf8 s26/tools/mixreq/m8_readout.py --results results --out <readout dir> [--stage p0|dev|smoke|all]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402
import m8_common as M8  # noqa: E402
import m8_validate as MV  # noqa: E402

ROOTS = {"smoke": "S26_M8_SMOKE", "p0": "S26_M8_P0", "dev": "S26_M8_DEV"}
FIELDS = ["stage", "label", "experiment_id", "index", "arm", "policy", "policy_args", "prep", "block", "attempt", "eligible", "reasons", "analysis_split", "planned", "succeeded", "undispatched",
          "failed", "unfinished", "urgent_p95_ms", "urgent_met", "urgent_late", "normal_p95_ms", "normal_met", "normal_late", "all_completed", "svc70", "svc80", "svc90", "svc95", "svc100",
          "wait_count", "wait_dose_total_ms", "wait_planned_total_ms", "wait_nominal_total_ms", "wait_overrun_total_ms", "wait_cut", "readback_ok", "prep_calls", "prep_actual_s", "last_dispatch_s", "last_available_s", "coverage_app", "coverage_host",
          "app_post_t0_s", "host_post_t0_s", "start_time", "end_time", "folder"]


def session_folders(root: Path) -> list[Path]:
    """세션 폴더 (device/manifest.json 또는 host/manifest_pushed.json 이 있는 폴더) — root 바로 아래 또는 plan_dir 하위 (10/15 사고 2: 실험별 하위 root)."""
    out = []
    for p in sorted(x for x in root.iterdir() if x.is_dir()):
        if (p / "device" / "manifest.json").is_file() or (p / "host" / "manifest_pushed.json").is_file():
            out.append(p)
        else:
            out += [q for q in sorted(x for x in p.iterdir() if x.is_dir()) if (q / "device" / "manifest.json").is_file() or (q / "host" / "manifest_pushed.json").is_file()]
    return out


def stage_events(results: Path) -> dict:
    out = {}
    p = results / "S26_M8_driver_events.jsonl"
    if p.is_file():
        for l in p.read_text(encoding="utf-8").splitlines():
            if not l.strip():
                continue
            e = json.loads(l)
            if e.get("what") == "run_end" and e.get("rc") == 5:
                continue   # 10/15 사고 2: rc 5 (폴더 있음 · 시작 0) 이벤트의 times 는 남의 폴더 (B1-00) 를 읽은 값 → 키 충돌로 라벨이 덮임
            if e.get("what") == "run_end" and (e.get("times") or {}).get("folder"):
                out[(Path(e["times"]["folder"]).name, (e["times"] or {}).get("host_start"))] = e
    return out


def read(folder: Path, ev: dict) -> dict | None:
    v = C.read_json(folder / "validated.json") if (folder / "validated.json").is_file() else None
    if v is None:
        return None
    hl = C.read_json(folder / "host" / "session_log.json") if (folder / "host" / "session_log.json").is_file() else {}
    svc = v.get("service") or {}
    r = v.get("rules") or {}
    a7 = (r.get("A7_wait") or {}).get("detail") or {}
    a8 = (r.get("A8_prep") or {}).get("detail") or {}
    a3 = (r.get("A3_window") or {}).get("detail") or {}
    a10 = (r.get("A10_coverage") or {}).get("detail") or {}
    a6 = (r.get("A6_response") or {}).get("detail") or {}
    prep = a8.get("prep") or {}
    item = (ev or {}).get("item") or {}
    row = dict(stage=item.get("stage") or (ev or {}).get("run_kind"), label=item.get("label") or (ev or {}).get("label"), experiment_id=v.get("experiment_id"), index=v.get("session_index"),
               arm=v.get("arm"), policy=v.get("policy"), policy_args=json.dumps(v.get("policy_args")) if v.get("policy_args") else "", prep=v.get("prep"), block=v.get("block"), attempt=v.get("attempt"),
               eligible=v.get("eligible"), reasons=";".join(v.get("reasons") or []), analysis_split=v.get("analysis_split"), planned=(v.get("counts") or {}).get("planned"),
               succeeded=(v.get("counts") or {}).get("succeeded"), undispatched=(v.get("counts") or {}).get("undispatched"), failed=(v.get("counts") or {}).get("failed"), unfinished=(v.get("counts") or {}).get("unfinished"),
               urgent_p95_ms=(svc.get("urgent") or {}).get("p95_ms"), urgent_met=(svc.get("urgent") or {}).get("deadline_met"), urgent_late=(svc.get("urgent") or {}).get("late"),
               normal_p95_ms=(svc.get("normal") or {}).get("p95_ms"), normal_met=(svc.get("normal") or {}).get("deadline_met"), normal_late=(svc.get("normal") or {}).get("late"),
               all_completed=(svc.get("all") or {}).get("all_completed"), **{f"svc{lv}": ((svc.get("all") or {}).get("levels") or {}).get(str(lv)) for lv in (70, 80, 90, 95, 100)},
               wait_count=a7.get("waits"), wait_dose_total_ms=a7.get("dose_total_ms"), wait_planned_total_ms=a7.get("planned_total_ms"), wait_nominal_total_ms=a7.get("nominal_total_ms"),
               wait_overrun_total_ms=a7.get("overrun_total_ms"), wait_cut=len(a7.get("cut") or []) if a7 else None, readback_ok=a6.get("readback_ok"),
               prep_calls=prep.get("calls"), prep_actual_s=(prep.get("actual_prep_ns") or 0) / 1e9 if prep else None, last_dispatch_s=a3.get("last_dispatch_s"), last_available_s=a3.get("last_available_s"),
               coverage_app=a10.get("app_passed"), coverage_host=a10.get("host_passed"), app_post_t0_s=a10.get("app_post_t0_s"), host_post_t0_s=a10.get("host_post_t0_s"),
               start_time=hl.get("start_time"), end_time=hl.get("end_time"), folder=f"{folder.parent.name}/{folder.name}")
    full = dict(row=row, validated_rules={k: dict(passed=x.get("passed"), detail=x.get("detail")) for k, x in r.items()}, service=svc, coverage=v.get("coverage"), gate=(ev or {}).get("gate"),
                perfetto=(ev or {}).get("perfetto"), start_state=(ev or {}).get("start_state"), in_block_charge=(ev or {}).get("in_block_charge"), apk_sha256=hl.get("apk_sha256"),
                manifest_sha256=hl.get("manifest_sha256"), note="readout only — ΔJ120/180 · 열 · 정책 비교 계산 0 (조민규 / Cowork) · 잔열 = host hal_cont 의 origin + 180 s 표본 위치만 (coverage)")
    return full


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", type=Path, default=M8.REPO / "results")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--stage", default="all")
    args = ap.parse_args()
    (args.out / "sessions").mkdir(parents=True, exist_ok=True)
    evs = stage_events(args.results)
    rows = []
    for stage, root in ROOTS.items():
        if args.stage != "all" and args.stage != stage:
            continue
        d = args.results / root
        if not d.is_dir():
            continue
        for folder in session_folders(d):
            hl = C.read_json(folder / "host" / "session_log.json") if (folder / "host" / "session_log.json").is_file() else {}
            full = read(folder, evs.get((folder.name, hl.get("start_time"))))
            if full is None:
                continue
            full["row"]["stage"] = full["row"]["stage"] or stage
            C.write_json(args.out / "sessions" / f"{stage}_{full['row']['label']}_a{full['row']['attempt']}.json", full)
            rows.append(full["row"])
    with open(args.out / "inventory.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if v is None else v) for k, v in r.items()})
    pres = args.results / "S26_M8_prestart_ledger.jsonl"
    prestart = [json.loads(l) for l in pres.read_text(encoding="utf-8").splitlines() if l.strip()] if pres.is_file() else []
    C.write_json(args.out / "prestart_ledger.json", dict(rejects=prestart, count=len(prestart), note="PRESTART_REJECT = START 아님 · 계획 coverage 분모 · 실제 서비스율 분모와 구분"))
    index = dict(schema="s26-m8-readout-index-v1", sessions=len(rows), valid=sum(1 for r in rows if r["eligible"] is True), by_stage={s: sum(1 for r in rows if r["stage"] == s) for s in ROOTS},
                 prestart_rejects=len(prestart), planned_coverage_note="분모 = 계획 세션 (REJECT 포함) 과 START 세션 (예정 도착 전부) 를 따로 명시",
                 note="readout only — ΔJ120/180 계산 안 함 (조민규 / Cowork)")
    C.write_json(args.out / "readout_index.json", index)
    print(json.dumps({k: v for k, v in index.items() if k in ("sessions", "valid", "by_stage", "prestart_rejects")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
