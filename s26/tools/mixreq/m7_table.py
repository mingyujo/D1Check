"""M7 session table · 연결표 · field_map (2026-10-13, 등록 M7 v2 §5) — inventory only. NO judgment · no J / 열 / 정책 비교 (조민규 / Cowork).
mixreq_readout.read_session · m6_readout (CLI, per plan) are imported / called unchanged.

  py -3 -X utf8 s26/tools/mixreq/m7_table.py --results results --out <dir> [--case-stand-wind "<영훈 진술>"] [--room 미기록]
      [--m6-table s26/results/m6_1012/session_table.csv --m6-table s26/results/m6_1012/confirm/session_table_confirm.csv] [--no-readout]

Writes <out>/session_table_m7.csv (등록 §5-2 열: M6-B 열 + cycle · item · condition · role · set · block · order_pos · prep_session_id ·
prep_last_available_host · k_app_start_host · gap_prep_to_k_s · stable · charge_end_to_start_s · hal_cont_path · power_coverage_after_last_available_s ·
hal_coverage_after_last_available_s · case_stand_wind · room_c · fingerprint) · apk_manifest_session_map.csv · field_map.json (요청 필드 ↔ 이벤트 이름 ·
없는 것 null + reason · 추정 채움 0) · fingerprint.txt · readouts (<out>/readout_<root>/ via m6_readout) · table_index.json.
Rows with cycle = m6 come from the M6-A / M6-B session tables (columns mapped, new columns empty) — 자료 재전송 아님.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import m7_common as M7  # noqa: E402  (M7 tables first)
import mixreq_common as C  # noqa: E402
import mixreq_readout as R  # noqa: E402
import m7_driver as D  # noqa: E402  (session_times · hal_rows — no device access here)

REPO = HERE.parents[2]
PLAN_ROOT = REPO / "s26" / "results" / "m7_1013"
ROOTS = {   # results root → (plan dir for readout, kind label)
    "S26_M7_K": ("plan_m7k", "K"), "S26_M7_P": ("plan_m7p", "P"), "S26_M7_PREP": ("plan_m7prep", "PREP"), "S26_M7_S": ("plan_m7s", "S"),
    "S26_M7_SMOKE": (None, "SMOKE"), "S26_M7_S7": (None, "S7"), "S26_M7_M6REPRO": (None, "M6REPRO"),
}
FIELDS = ["cycle", "kind", "idx", "label", "load", "rule", "policy", "attempt", "eligible", "reasons", "analysis_split", "item", "condition", "role", "set", "block",
          "order_pos", "experiment_id", "session_id", "start_time", "end_time", "start_SKIN", "start_AP", "start_BAT", "start_SOC", "band_result", "brightness",
          "brightness_mode", "airplane", "zen_mode", "screen_off_timeout", "wakefulness", "keyguard_showing", "device_locked", "focus_apps", "focus_non_session_rows",
          "previous_run", "previous_end", "gap_s", "in_block_charge", "prep_session_id", "prep_last_available_host", "k_app_start_host", "gap_prep_to_k_s", "gap_over",
          "stable", "idle_s", "charge_end_to_start_s", "last_power_disconnected", "hal_cont_path", "power_coverage_after_last_available_s", "hal_coverage_after_last_available_s",
          "coverage_note", "last_lane_available_s", "completed", "urgent_p95_ms", "normal_p95_ms", "deadline_met", "npu_contract", "apk_sha256", "manifest_sha256",
          "projection_sha256", "time_scale", "case_stand_wind", "room_c", "fingerprint", "folder"]
MAP_FIELDS = ["cycle", "kind", "label", "experiment_id", "idx", "attempt", "session_id", "policy", "block", "manifest_sha256_plan", "manifest_sha256_pushed", "manifest_sha256_device",
              "apk_sha256_session", "projection_sha256", "cls_model_sha256", "det_model_sha256", "aot_model_sha256", "png_sha256", "registration_sha256", "folder"]

# 등록 §5-3 — 조민규 요청 필드 ↔ 우리 이벤트 이름 (common_boundary.json 행 열 · requests.json 열 · progress.jsonl kind · <request_id>.result.json). 추정 채움 0.
FIELD_MAP = dict(
    schema="s26-m7-field-map-v1",
    source="request-runner SessionEngine (M7-apk · 엔진 diff 0 since R3): common_boundary.json rows = requests.json rows · progress.jsonl per-request events · <request_id>.result.json",
    units="*_ns · mono_ns = SystemClock.elapsedRealtimeNanos (기기 단조 시계) · 호스트 연결 = host start_time + (mono_ns − session_start mono_ns) (근사 · start_check 와 hal.csv 의 device_boottime 열이 정본)",
    fields={
        "arrival": dict(column="actual_arrival_ns", event="arrival", also=dict(planned="scheduled_arrival_ns"), note="예정 도착 = scheduled_arrival_ns · 실제 도착 = actual_arrival_ns"),
        "dispatch": dict(column="dispatch_ns", event="dispatch"),
        "execution_start": dict(column="execution_start_ns", event="request_start"),
        "host_inference_start": dict(column="host_inference_start_ns", event="host_inference_start"),
        "host_inference_return": dict(column="host_inference_return_ns", event="host_inference_return"),
        "output_ready": dict(column="output_ready_ns", event="output_ready"),
        "persist_complete": dict(column="persist_complete_ns", event="persist_complete"),
        "worker_release": dict(column="worker_release_ns", event="worker_release"),
        "AVAILABLE": dict(column="lane_available_ns", event="lane_available", note="차선 (runtime key) 이 다음 요청을 받을 수 있게 된 시각 · 등록 V2 의 기준"),
        "응답 시각": dict(column=None, event=None, reason="앱에 '요청자에게 응답을 돌려준' 별도 이벤트가 없다 (요청자 = 세션 엔진 자신). 가장 가까운 두 시각 = output_ready_ns (출력 준비) · persist_complete_ns (결과 파일 기록 완료). 추정 채움 0 — null"),
        "결과": dict(column=None, event=None, file="<request_id>.result.json", keys=["results", "raw_output_sha256", "raw_output_elements", "inference_ns", "write_run_read_ns", "input_tensor_sha256", "model_sha256", "image_sha256"],
                   note="요청별 결과 파일 (분류 top-5 / 탐지 상자) · terminal_status 는 common_boundary · requests 행"),
        "백엔드": dict(column="selected_backend", event="decision", also=dict(result_file=["requested_backend", "actual_backend", "runtime_key"]), note="정책 결정 (decision_reason) 과 실제 실행 백엔드 (result.json actual_backend)"),
    },
    extra_ours={"queue_entry": "queue_entry_ns (event queue_entry)", "deadline": "deadline_ns", "terminal_status": "succeeded | failed", "decision_reason": "online_arrived_priority_then_ordinal",
                "power": "progress.jsonl kind=power_sample (current_raw µA 방전 음수 · charge_counter_raw µAh · voltage_mV · battery_temperature_deci_c · battery_level · plugged · thermal_status · interactive · 900 ms)",
                "host_thermal": "host/hal.csv (세션 안 2 s: pc_ms device_boottime_s SKIN AP BAT PA thermal_status) · S26_M7_HAL/hal_cont_<label>.csv (연속 2.3 s · dumpsys battery 포함)"},
    power_gap=dict(reason="app not running between sessions (APK: power_sample only inside a session · cooling 60 s)", fill="null — 추정 채움 0"),
)


def jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.is_file() else []


def read_csv(p: Path) -> list[dict]:
    if not p.is_file():
        return []
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def focus_info(folder: Path) -> tuple[str, int | None]:
    rows = read_csv(folder / "host" / "phone_watch.csv")
    if not rows:
        return "", None
    apps = sorted({(r.get("focus") or "").split("/")[0] for r in rows if r.get("focus")})
    non = sum(1 for r in rows if "requestrunner" not in (r.get("focus") or ""))
    return "|".join(apps), non


def device_coverage(folder: Path) -> tuple[float | None, str]:
    """power_coverage_after_last_available_s on the device clock: (last power_sample − last lane_available) / 1e9 (K: no lane_available → null + reason)."""
    prog = folder / "device" / "progress.jsonl"
    if not prog.is_file():
        return None, "no progress.jsonl"
    la = ps = None
    with open(prog, encoding="utf-8") as f:
        for line in f:
            if '"lane_available"' in line or '"power_sample"' in line:
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if e.get("kind") == "lane_available":
                    la = max(la or 0, int(e["mono_ns"]))
                elif e.get("kind") == "power_sample":
                    ps = max(ps or 0, int(e["mono_ns"]))
    if la is None:
        return None, "no lane_available (requests 0 — K) → null"
    if ps is None:
        return None, "no power_sample"
    return round((ps - la) / 1e9, 3), "device clock: last power_sample − last lane_available"


def hal_coverage(hal_csv: str | None, last_avail_host: float | None) -> float | None:
    if not hal_csv or last_avail_host is None:
        return None
    rows = D.Driver.hal_rows(Path(hal_csv))
    ts = [r["host_epoch_s"] for r in rows if r.get("host_epoch_s") is not None and r.get("SKIN") is not None]
    return M7.coverage_after(last_avail_host, max(ts)) if ts else None


def session_rows(results: Path, events: list[dict], runs: list[dict], fingerprint: str, case: str, room: str) -> tuple[list[dict], list[dict]]:
    rows, maps = [], []
    ends = [r for r in runs if r.get("event") == "end"]
    starts = [r for r in runs if r.get("event") == "start"]
    ev_by = {}
    for e in events:
        if e.get("what") == "run_end":
            ev_by[(e.get("label"), e.get("attempt"))] = e
    for root_name, (plan_dir, kind) in ROOTS.items():
        root = results / root_name
        if not root.is_dir():
            continue
        bands = jsonl(root / "start_band.jsonl")
        awakes = jsonl(root / "awake.jsonl")
        for folder in sorted(p for p in root.iterdir() if p.is_dir()):
            host_log = C.read_json(folder / "host" / "session_log.json") if (folder / "host" / "session_log.json").is_file() else None
            mpath = folder / "device" / "manifest.json" if (folder / "device" / "manifest.json").is_file() else folder / "host" / "manifest_pushed.json"
            if not mpath.is_file():
                continue
            m = C.read_json(mpath)
            s = R.read_session(folder, False) if (folder / "validated.json").is_file() else None
            v = C.read_json(folder / "validated.json") if (folder / "validated.json").is_file() else {}
            label = m.get("m6_run") or m.get("m7_label") or (f"{m.get('m6_load')}-{m.get('m6_letter')}" if m.get("m6_load") else f"{kind}{m['session_index']}")
            is_smoke = m.get("split") == "diagnostic"
            # run log start record of this folder: same results root · same index (or smoke name) · same attempt → its label = driver/run label (P12 · K1A · S7_m7 · smoke name)
            start_rec = next((r for r in reversed(starts) if str(r.get("results", "")).replace("/", "\\").endswith(root_name) and r.get("attempt") == m["attempt"]
                              and ((r.get("smoke") and is_smoke and r.get("smoke") in folder.name) or (not r.get("smoke") and not is_smoke and r.get("index") == m["session_index"]))), None)
            run_label = (start_rec or {}).get("label") or (host_log or {}).get("label")
            ev = ev_by.get((run_label, m["attempt"])) or {}
            times = D.Driver.session_times(None, folder)
            band_keys = {f"index{m['session_index']:02d}", run_label, (start_rec or {}).get("smoke")}
            band = next((b for b in reversed(bands) if b.get("label") in band_keys and b.get("attempt") == m["attempt"]), None) or {}
            last_poll = (band.get("polls") or [{}])[-1] if band.get("polls") else {}
            start_state = ev.get("start_state") or {}
            awake = next((a for a in reversed(awakes) if a.get("label") == run_label), {}) or {}
            aw = awake.get("after_wakeup") or awake.get("first") or {}
            settings = (host_log or {}).get("settings_before") or {}
            focus_apps, focus_non = focus_info(folder)
            st = (host_log or {}).get("start_time")
            prev = None
            if start_rec:
                before = [r for r in ends if r.get("epoch", 0) < start_rec.get("epoch", 0)]
                prev = before[-1] if before else None
            gap_s = round(float(start_rec["epoch"]) - float(prev["epoch"])) if (start_rec and prev) else None
            pcov, pnote = device_coverage(folder)
            hcov = hal_coverage(ev.get("hal_csv"), times.get("last_lane_available_host_epoch"))
            svc = (s or {}).get("service") or {}
            gap_k = ev.get("gap_prep_to_k") or {}
            exp = m["experiment_id"]
            item = m.get("item") or (1 if exp.startswith("S26-M6-K") else 2 if exp.startswith("S26-M6-P") else 4 if exp.startswith("S26-MIXREQ-03") else "")
            row_kind = "PREP" if m.get("role") == "prep" else kind   # prep P sessions run inside the K driver (root S26_M7_K) — classify by role
            row = dict(cycle=m.get("cycle") or ("m7" if root_name.startswith("S26_M7") else ""), kind=row_kind, idx=m["session_index"], label=label, load=m.get("m6_load"),
                       rule=m.get("m6_letter"), policy=m["policy"], attempt=m["attempt"], eligible=v.get("eligible"), reasons=";".join(v.get("reasons") or []),
                       analysis_split=m.get("analysis_split") or ("regression" if kind == "S7" else "m6_repro" if kind == "M6REPRO" else "smoke" if kind == "SMOKE" else ""),
                       item=item, condition=ev.get("condition") or m.get("m7_cond") or (m.get("m6_load") and f"{m.get('m6_load')}" if exp.startswith("S26-M6-P") else ("S" if exp.startswith("S26-MIXREQ-03") else "")),
                       role=m.get("role") or ("main" if kind in ("P", "K", "S") else kind.lower()), set=ev.get("set") or m.get("m7_set"), block=m["block"], order_pos=m.get("order_pos"),
                       experiment_id=exp, session_id=m["session_id"], start_time=st, end_time=(host_log or {}).get("end_time"),
                       start_SKIN=last_poll.get("SKIN", start_state.get("SKIN")), start_AP=last_poll.get("AP", start_state.get("AP")), start_BAT=last_poll.get("BAT", start_state.get("BAT")),
                       start_SOC=last_poll.get("soc", start_state.get("soc")), band_result=band.get("result") or ("skipped" if ev.get("k_precheck") else ""),
                       brightness=settings.get("brightness"), brightness_mode=settings.get("brightness_mode"), airplane=settings.get("airplane"), zen_mode=settings.get("zen_mode"),
                       screen_off_timeout=settings.get("screen_off_timeout"), wakefulness=aw.get("wakefulness"), keyguard_showing=aw.get("keyguard_showing"), device_locked=aw.get("device_locked"),
                       focus_apps=focus_apps, focus_non_session_rows=focus_non, previous_run=(prev or {}).get("label"), previous_end=(prev or {}).get("t"), gap_s=gap_s,
                       in_block_charge=band.get("in_block_charge"), prep_session_id=None, prep_last_available_host=ev.get("prep_last_available_host_epoch"),
                       k_app_start_host=ev.get("k_app_start_host"), gap_prep_to_k_s=gap_k.get("gap_s"), gap_over=gap_k.get("gap_over"), stable=ev.get("stable"), idle_s=ev.get("idle_s"),
                       charge_end_to_start_s=ev.get("charge_end_to_start_s"), last_power_disconnected=ev.get("last_power_disconnected"), hal_cont_path=ev.get("hal_csv"),
                       power_coverage_after_last_available_s=pcov, hal_coverage_after_last_available_s=hcov, coverage_note=pnote,
                       last_lane_available_s=(s or {}).get("last_lane_available_s"), completed=svc.get("all", {}).get("completed"), urgent_p95_ms=svc.get("urgent", {}).get("p95_ms"),
                       normal_p95_ms=svc.get("normal", {}).get("p95_ms"), deadline_met=svc.get("all", {}).get("deadline_met"), npu_contract=((s or {}).get("contract") or {}).get("passed"),
                       apk_sha256=(host_log or {}).get("apk_sha256"), manifest_sha256=(host_log or {}).get("manifest_sha256"), projection_sha256=None, time_scale=m.get("time_scale"),
                       case_stand_wind=case, room_c=room, fingerprint=fingerprint, folder=f"{root_name}/{folder.name}")
            if ev.get("prep_session_folder"):
                pm = Path(ev["prep_session_folder"]) / "host" / "manifest_pushed.json"
                row["prep_session_id"] = C.read_json(pm)["session_id"] if pm.is_file() else None
            if m.get("requests"):
                import m6_common as M
                try:
                    row["projection_sha256"] = M.projection_sha256(m["requests"]) if len(m["requests"]) == M.REQUEST_COUNT else None
                except Exception:
                    row["projection_sha256"] = None
            rows.append(row)
            rt = {r["key"]: r.get("model_sha256") for r in m.get("runtimes", [])}
            dev_sha = (C.read_json(folder / "device" / "summary.json") or {}).get("manifest_sha256") if (folder / "device" / "summary.json").is_file() else None
            plan_sha = None
            for pd in ([plan_dir, "plan_m7prep"] if plan_dir else []):
                plan = C.read_json(PLAN_ROOT / pd / "plan.json")
                plan_sha = plan_sha or next((e["manifest_sha256"] for e in plan["sessions"] + plan["smoke"] if e["session_id"] == m["session_id"]), None)
            maps.append(dict(cycle=row["cycle"], kind=row_kind, label=label, experiment_id=exp, idx=m["session_index"], attempt=m["attempt"], session_id=m["session_id"], policy=m["policy"],
                             block=m["block"], manifest_sha256_plan=plan_sha, manifest_sha256_pushed=(host_log or {}).get("manifest_sha256"), manifest_sha256_device=dev_sha,
                             apk_sha256_session=(host_log or {}).get("apk_sha256"), projection_sha256=row["projection_sha256"], cls_model_sha256=rt.get("classification_CPU"),
                             det_model_sha256=rt.get("detection_CPU"), aot_model_sha256=rt.get("classification_NPU"), png_sha256=(m.get("image") or {}).get("sha256"),
                             registration_sha256=(m.get("registration") or {}).get("sha256"), folder=row["folder"]))
    return rows, maps


def m6_rows(tables: list[Path], fingerprint: str) -> list[dict]:
    out = []
    for t in tables:
        for r in read_csv(t):
            row = {k: "" for k in FIELDS}
            for k in FIELDS:
                if k in r:
                    row[k] = r[k]
            row.update(cycle="m6", fingerprint=fingerprint, role="main" if r.get("kind") in ("P", "K") else (r.get("kind") or "").lower(),
                       item=(1 if r.get("kind") == "K" else 2 if r.get("kind") == "P" else ""), condition=(r.get("load") or ("K" if r.get("kind") == "K" else "")),
                       block=r.get("block") or ("M" if r.get("kind") in ("P", "K") else ""), room_c=r.get("room_temp_c", ""), folder=f"m6:{t.name}:{r.get('folder', '')}",
                       coverage_note="cycle = m6 (M6-A/B 세션 표 행 · 새 열 비움 · 자료 재전송 아님)")
            out.append(row)
    return out


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if v is None else v) for k, v in r.items()})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", type=Path, default=REPO / "results")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--case-stand-wind", default="미확인")
    ap.add_argument("--room", default="미기록")
    ap.add_argument("--fingerprint", default="")
    ap.add_argument("--m6-table", type=Path, action="append", default=[])
    ap.add_argument("--no-readout", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    fp = args.fingerprint
    if not fp and os.environ.get("ANDROID_SERIAL"):
        import mixreq_session as MS
        fp = subprocess.run([MS.ADB, "-s", os.environ["ANDROID_SERIAL"], "shell", "getprop", "ro.build.fingerprint"], capture_output=True, text=True, timeout=30).stdout.strip() or "미확인"
    fp = fp or "미확인"
    (args.out / "fingerprint.txt").write_text(fp + "\n", encoding="utf-8")
    events = jsonl(args.results / "S26_M7_driver_events.jsonl")
    runs = jsonl(args.results / "S26_M7_runs.jsonl")
    rows, maps = session_rows(args.results, events, runs, fp, args.case_stand_wind, args.room)
    rows += m6_rows(args.m6_table, fp)
    write_csv(args.out / "session_table_m7.csv", FIELDS, rows)
    write_csv(args.out / "apk_manifest_session_map.csv", MAP_FIELDS, maps)
    C.write_json(args.out / "field_map.json", FIELD_MAP)
    readouts = {}
    if not args.no_readout:
        for root_name, (plan_dir, kind) in ROOTS.items():
            if plan_dir and (args.results / root_name).is_dir():
                jobs = [(plan_dir, args.out / f"readout_{root_name}")]
                if root_name == "S26_M7_K":   # prep P sessions (plan_m7prep) live in the K root — read them out against their own plan
                    jobs.append(("plan_m7prep", args.out / f"readout_{root_name}_prep"))
                for pd, out in jobs:
                    r = subprocess.run([sys.executable, "-X", "utf8", str(HERE / "m6_readout.py"), "--plan", str(PLAN_ROOT / pd / "plan.json"), "--results", str(args.results / root_name),
                                        "--out", str(out)], capture_output=True, text=True, cwd=str(REPO))
                    readouts[out.name] = dict(rc=r.returncode, last=(r.stdout.strip().splitlines() or [""])[-1][:300], err=r.stderr.strip()[-300:])
    index = dict(schema="s26-m7-table-v1", rows=len(rows), m7_rows=sum(1 for r in rows if r["cycle"] == "m7"), m6_rows=sum(1 for r in rows if r["cycle"] == "m6"),
                 by_kind={k: sum(1 for r in rows if r["kind"] == k and r["cycle"] == "m7") for k in ("K", "PREP", "P", "S", "SMOKE", "S7", "M6REPRO")},
                 valid={k: sum(1 for r in rows if r["kind"] == k and r["cycle"] == "m7" and str(r["eligible"]) == "True") for k in ("K", "PREP", "P", "S")},
                 fingerprint=fp, case_stand_wind=args.case_stand_wind, room_c=args.room, readouts=readouts, registration=M7.REGISTRATION,
                 note="inventory only — J · 열 · 정책 비교 계산 안 함 (조민규 / Cowork)")
    C.write_json(args.out / "table_index.json", index)
    print(json.dumps({k: v for k, v in index.items() if k in ("rows", "m7_rows", "m6_rows", "by_kind", "valid")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
