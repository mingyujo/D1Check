"""M8 session table · provenance · field_map (readback 포함) — inventory only (계산 0). m8_readout is called per stage.

  py -3 -X utf8 s26/tools/mixreq/m8_table.py --results results --out <dir> [--case-stand-wind "..."] [--room NA] [--fingerprint ...]
Writes session_table_m8.csv · provenance_m8.csv · field_map_m8.json · coverage_m8.csv · usage_m8.json · readout_m8/ · table_index.json.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402
import m8_common as M8  # noqa: E402
import m8_readout as R  # noqa: E402

PLAN_ROOT = M8.REPO / "s26" / "results" / "m8_prep"
FIELDS = ["cycle", "stage", "block_no", "order_pos", "label", "experiment_id", "idx", "arm", "bank", "policy", "policy_args", "prep", "block", "attempt", "eligible", "reasons", "analysis_split", "session_id",
          "start_time", "end_time", "start_SKIN", "start_AP", "start_BAT", "start_SOC", "end_SOC", "soc_delta", "in_block_charge_yes_no", "soc_40_80_satisfied", "soc_condition", "soc_in_m8_start_band", "soc_in_new_band_reference_only", "gate_result", "gate_version", "band_c", "in_band", "gate_waited_s", "tref_c",
          "gate_skin_median", "gate_skin_slope", "gate_ap_slope", "in_block_charge", "charge_end_to_start_s", "last_power_disconnected", "previous_run", "gap_s", "perfetto",
          "hal_cont_path", "coverage_app", "coverage_host", "app_post_t0_s", "host_post_t0_s", "last_dispatch_s", "last_available_s", "planned", "succeeded", "undispatched", "failed",
          "urgent_p95_ms", "normal_p95_ms", "svc70", "svc80", "svc90", "svc95", "svc100", "all_completed", "wait_count", "wait_dose_total_ms", "wait_nominal_total_ms", "wait_overrun_total_ms", "readback_ok", "prep_calls", "npu_contract",
          "apk_sha256", "manifest_sha256", "plan_sha256", "registration_sha256", "time_scale", "case_stand_wind", "room_c", "fingerprint", "folder"]
PROV_FIELDS = ["stage", "label", "experiment_id", "idx", "attempt", "session_id", "source_commit", "apk_sha256_session", "apk_sha256_registered", "signer_sha256", "plan", "plan_sha256",
               "blocks_sha256", "manifest_sha256_plan", "manifest_sha256_pushed", "manifest_sha256_device", "device_inputs_sha256", "input_image_sha256", "registration_sha256", "folder"]

FIELD_MAP = dict(
    schema="s26-m8-field-map-v1",
    source="request-runner SessionEngineM8 (contract M8) · requests.json rows · progress.jsonl events · <request_id>.result.json · prep.json · summary.json",
    units="*_ns = SystemClock.elapsedRealtimeNanos (기기 단조 · 한 세션 한 시계 · 센서 표본 같은 시계) · host 연결 = session hal.csv (pc_ms ↔ device_boottime_s)",
    fields={
        "예정 도착": dict(column="scheduled_arrival_ns", event="arrival(scheduled)", also="offset_us"),
        "실제 도착": dict(column="actual_arrival_ns", event="arrival"),
        "enqueue": dict(column="queue_entry_ns", event="queue_entry", note="enqueue 지연 = queue_entry − scheduled"),
        "WAIT": dict(column="wait_burst_index · wait_planned_ms · wait_dose_ms · wait_cut_reason", event="wait_start · wait_end", note="묶음 head 요청에만 · 정책 인자 없으면 null · summary.wait"),
        "dispatch": dict(column="dispatch_ns", event="dispatch"),
        "execution_start": dict(column="execution_start_ns", event="request_start"),
        "inference start/return": dict(column="host_inference_start_ns · host_inference_return_ns", event="host_inference_start · host_inference_return"),
        "output": dict(column="output_ready_ns", event="output_ready", note="긴급 응답 경계"),
        "persist": dict(column="persist_complete_ns", event="persist_complete", note=".part → fsync → rename"),
        "readback": dict(column="readback_start_ns · readback_end_ns · readback_ok · readback_sha256 · readback_expected_sha256 · readback_error · readback_skipped", event="readback",
                         note="normal 만 수행 (urgent = readback_skipped 'urgent') · 앱이 기록 · host pull 시각 대체 0"),
        "응답": dict(column="response_ns · response_boundary", event="(앱이 priority 로 선택)", note="urgent = output_ready_ns · normal = readback_end_ns · 주응답 = response − scheduled"),
        "release": dict(column="worker_release_ns", event="worker_release"),
        "AVAILABLE": dict(column="lane_available_ns", event="lane_available", note="응답 경계와 별개"),
        "terminal": dict(column="terminal_status", values=["succeeded", "failed", "undispatched (120 s 경계 뒤 waiting · undispatched_reason)", "unfinished (앱 정지)"]),
        "결정": dict(event="decision", keys=["policy", "waiting", "running", "selected", "backend", "reason"], note="null 포함 전부"),
        "준비": dict(file="prep.json", keys=["kind", "prep_start_ns", "prep_end_ns", "prep_last_available_ns", "calls", "call_records"], event="prep_call_start · prep_call_end · prep_end"),
        "결과": dict(file="<request_id>.result.json", keys=["results", "raw_output_sha256", "inference_ns", "input_tensor_sha256", "model_sha256", "image_sha256"]),
        "백엔드": dict(column="selected_backend", also="result.json actual_backend · runtime_key"),
    },
    power="progress.jsonl kind=power_sample (current_raw µA 방전 음수 · charge_counter µAh · voltage mV · deci-℃ · level · plugged · thermal_status · interactive · 900 ms · 준비부터 연속)",
    host_thermal="host/hal.csv (세션 안 2 s) · S26_M8_HAL/hal_cont_<label>_a<n>.csv (연속 2.3 s · dumpsys battery 포함 · 앱 시작 ≥ 60 s 전 → origin + 300 s)",
    gate="S26_M8_driver_events.jsonl run_end.gate (decisions · tref) · S26_M8_prestart_ledger.jsonl · S26_M8_tref.json (날짜별 Tref_day · 제안 v1)",
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", type=Path, default=M8.REPO / "results")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--case-stand-wind", default="케이스 없음 · 책상 위 눕힘 · 바람 없음")
    ap.add_argument("--room", default="NA")
    ap.add_argument("--fingerprint", default="미확인")
    ap.add_argument("--apk-sha256", default="")
    ap.add_argument("--signer-sha256", default="")
    ap.add_argument("--source-commit", default="")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([sys.executable, "-X", "utf8", str(HERE / "m8_readout.py"), "--results", str(args.results), "--out", str(args.out / "readout_m8")], capture_output=True, text=True, cwd=str(M8.REPO))
    if r.returncode != 0:
        raise SystemExit(f"m8_readout failed: {r.stderr[-600:]}")
    evs = R.stage_events(args.results)
    runs = [json.loads(l) for l in (args.results / "S26_M8_runs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()] if (args.results / "S26_M8_runs.jsonl").is_file() else []
    ends = [x for x in runs if x.get("event") == "end"]
    starts = [x for x in runs if x.get("event") == "start"]
    blocks = C.read_json(PLAN_ROOT / "plan_m8" / "blocks.json") if (PLAN_ROOT / "plan_m8" / "blocks.json").is_file() else {}
    rows, prov, cov = [], [], []
    for stage, root in R.ROOTS.items():
        d = args.results / root
        if not d.is_dir():
            continue
        for folder in R.session_folders(d):
            hl = C.read_json(folder / "host" / "session_log.json") if (folder / "host" / "session_log.json").is_file() else {}
            mp = folder / "device" / "manifest.json" if (folder / "device" / "manifest.json").is_file() else folder / "host" / "manifest_pushed.json"
            if not mp.is_file():
                continue
            m = C.read_json(mp)
            ev = evs.get((folder.name, hl.get("start_time"))) or {}
            full = R.read(folder, ev) or {}
            row0 = full.get("row") or {}
            gate = ev.get("gate") or {}
            last_dec = (gate.get("decisions") or [{}])[-1] if gate.get("decisions") else {}
            st = ev.get("start_state") or {}
            item = ev.get("item") or {}
            start_rec = next((x for x in reversed(starts) if x.get("label") == ev.get("label") and x.get("attempt") == m.get("attempt")), None)
            prev = None
            if start_rec:
                before = [x for x in ends if x.get("epoch", 0) < start_rec.get("epoch", 0)]
                prev = before[-1] if before else None
            soc = st.get("soc")
            soc_end = (ev.get("end_state") or {}).get("soc")
            band = M8.SOC_NEW_BAND
            soc_40_80 = (band[0] <= soc <= band[1] and band[0] <= soc_end <= band[1]) if (soc is not None and soc_end is not None) else None
            plan = C.read_json(PLAN_ROOT / item["plan_dir"] / "plan.json") if item.get("plan_dir") and (PLAN_ROOT / item["plan_dir"] / "plan.json").is_file() else {}
            pe = next((e for e in (plan.get("sessions", []) + plan.get("smoke", [])) if e["session_id"] == m["session_id"]), {}) if plan else {}
            rows.append(dict(cycle=M8.CYCLE, stage=stage, block_no=item.get("block_no"), order_pos=item.get("order_pos"), label=row0.get("label") or ev.get("label"), experiment_id=m["experiment_id"], idx=m["session_index"],
                             arm=m.get("arm"), bank=m.get("bank"), policy=m["policy"], policy_args=json.dumps(m.get("policy_args")) if m.get("policy_args") else "", prep=(m.get("prep") or {}).get("kind"), block=m["block"],
                             attempt=m["attempt"], eligible=row0.get("eligible"), reasons=row0.get("reasons"), analysis_split=m.get("analysis_split"), session_id=m["session_id"],
                             start_time=hl.get("start_time"), end_time=hl.get("end_time"), start_SKIN=st.get("SKIN"), start_AP=st.get("AP"), start_BAT=st.get("BAT"), start_SOC=soc,
                             end_SOC=soc_end, soc_delta=(soc_end - soc) if (soc is not None and soc_end is not None) else None, in_block_charge_yes_no=("yes" if ev.get("in_block_charge") else "no"),
                             soc_40_80_satisfied=soc_40_80, soc_condition="SOC ≥ 20 · 상한 없음 (영훈 운영 결정) — 원래 40~80 제안과 다른 조건 · 기준 밖 자료 삭제 0 · '원래 조건 준수' 표기 0",
                             soc_in_m8_start_band=(soc is not None and soc >= M8.SOC_MIN_START), soc_in_new_band_reference_only=(soc is not None and M8.SOC_NEW_BAND[0] <= soc <= M8.SOC_NEW_BAND[1]),
                             gate_result=gate.get("result"), gate_version=gate.get("gate_version") or ("v2" if gate else None), band_c=gate.get("band_c", 0.5 if gate else None), in_band=gate.get("in_band", (not gate.get("forced_start")) if gate else None), gate_waited_s=gate.get("waited_s"), tref_c=gate.get("tref"), gate_skin_median=last_dec.get("skin_median"), gate_skin_slope=last_dec.get("skin_slope_c_per_min"),
                             gate_ap_slope=last_dec.get("ap_slope_c_per_min"), in_block_charge=ev.get("in_block_charge"), charge_end_to_start_s=ev.get("charge_end_to_start_s"), last_power_disconnected=ev.get("last_power_disconnected"),
                             previous_run=(prev or {}).get("label"), gap_s=round(float(start_rec["epoch"]) - float(prev["epoch"])) if (start_rec and prev) else None,
                             perfetto=((ev.get("perfetto") or {}).get("supported") if isinstance(ev.get("perfetto"), dict) else ev.get("perfetto")), hal_cont_path=ev.get("hal_csv"),
                             coverage_app=row0.get("coverage_app"), coverage_host=row0.get("coverage_host"), app_post_t0_s=row0.get("app_post_t0_s"), host_post_t0_s=row0.get("host_post_t0_s"),
                             last_dispatch_s=row0.get("last_dispatch_s"), last_available_s=row0.get("last_available_s"), planned=row0.get("planned"), succeeded=row0.get("succeeded"), undispatched=row0.get("undispatched"),
                             failed=row0.get("failed"), urgent_p95_ms=row0.get("urgent_p95_ms"), normal_p95_ms=row0.get("normal_p95_ms"), **{f"svc{lv}": row0.get(f"svc{lv}") for lv in (70, 80, 90, 95, 100)},
                             all_completed=row0.get("all_completed"), wait_count=row0.get("wait_count"), wait_dose_total_ms=row0.get("wait_dose_total_ms"), wait_nominal_total_ms=row0.get("wait_nominal_total_ms"),
                             wait_overrun_total_ms=row0.get("wait_overrun_total_ms"), readback_ok=row0.get("readback_ok"), prep_calls=row0.get("prep_calls"),
                             npu_contract=(C.read_json(folder / "validated.json").get("npu_contract") if (folder / "validated.json").is_file() else None),
                             apk_sha256=hl.get("apk_sha256"), manifest_sha256=hl.get("manifest_sha256"), plan_sha256=(blocks.get("plan_sha256") or {}).get(item.get("plan_dir")), registration_sha256=(m.get("registration") or {}).get("sha256"),
                             time_scale=m.get("time_scale"), case_stand_wind=args.case_stand_wind, room_c=args.room, fingerprint=args.fingerprint, folder=f"{root}/{folder.relative_to(d).as_posix()}"))
            dev_sha = (C.read_json(folder / "device" / "summary.json") or {}).get("manifest_sha256") if (folder / "device" / "summary.json").is_file() else None
            prov.append(dict(stage=stage, label=rows[-1]["label"], experiment_id=m["experiment_id"], idx=m["session_index"], attempt=m["attempt"], session_id=m["session_id"], source_commit=args.source_commit,
                             apk_sha256_session=hl.get("apk_sha256"), apk_sha256_registered=args.apk_sha256, signer_sha256=args.signer_sha256, plan=item.get("plan_dir"), plan_sha256=rows[-1]["plan_sha256"],
                             blocks_sha256=C.sha256_file(PLAN_ROOT / "plan_m8" / "blocks.json") if (PLAN_ROOT / "plan_m8" / "blocks.json").is_file() else None, manifest_sha256_plan=pe.get("manifest_sha256"),
                             manifest_sha256_pushed=hl.get("manifest_sha256"), manifest_sha256_device=dev_sha, device_inputs_sha256=C.sha256_file(PLAN_ROOT / item["plan_dir"] / "device_inputs.json") if item.get("plan_dir") else None,
                             input_image_sha256=(m.get("image") or {}).get("sha256"), registration_sha256=(m.get("registration") or {}).get("sha256"), folder=f"{root}/{folder.relative_to(d).as_posix()}"))
            c = (full.get("coverage") or {})
            cov.append(dict(stage=stage, label=rows[-1]["label"], attempt=m["attempt"], passed=c.get("passed"), reasons=";".join(c.get("reasons") or []),
                            **{f"app_{k}": v for k, v in (c.get("app") or {}).items() if not isinstance(v, (dict, list))}, **{f"host_{k}": v for k, v in (c.get("host") or {}).items() if not isinstance(v, (dict, list))},
                            **{f"app_{p}_both": ((c.get("app") or {}).get("points") or {}).get(p, {}).get("ok") for p in ("0", "35", "120", "180")},
                            **{f"host_ap{p}_both": ((c.get("host") or {}).get("ap_points") or {}).get(p, {}).get("ok") for p in ("35", "180")},
                            **{f"host_iv{p}_both": ((c.get("host") or {}).get("iv_points") or {}).get(p, {}).get("ok") for p in ("0", "180")}, folder=f"{root}/{folder.relative_to(d).as_posix()}"))

    def write(path, fields, rs):
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            for x in rs:
                w.writerow({k: ("" if v is None else v) for k, v in x.items()})
    write(args.out / "session_table_m8.csv", FIELDS, rows)
    write(args.out / "provenance_m8.csv", PROV_FIELDS, prov)
    cfields = []
    for x in cov:
        for k in x:
            if k not in cfields:
                cfields.append(k)
    write(args.out / "coverage_m8.csv", cfields, cov)
    C.write_json(args.out / "field_map_m8.json", FIELD_MAP)
    # usage (run log · 기술만)
    use_rows, st_by = [], {}
    for x in runs:
        key = (x.get("label"), x.get("attempt"))
        if x.get("event") == "start":
            st_by[key] = x
        elif x.get("event") == "end" and key in st_by:
            s = st_by.pop(key)
            use_rows.append(dict(label=x["label"], attempt=x.get("attempt"), start=s["t"], end=x["t"], run_s=round(float(x["epoch"]) - float(s["epoch"]), 1), rc=x.get("rc")))
    use_rows.sort(key=lambda u: u["start"])
    waits = [dict(after=a["label"], before=b["label"], wait_s=round((dt.datetime.fromisoformat(b["start"]) - dt.datetime.fromisoformat(a["end"])).total_seconds(), 1)) for a, b in zip(use_rows, use_rows[1:])]
    C.write_json(args.out / "usage_m8.json", dict(sessions=use_rows, pure_run_s=round(sum(u["run_s"] for u in use_rows), 1), waits=waits, wait_total_s=round(sum(w["wait_s"] for w in waits), 1),
                                                   first=use_rows[0]["start"] if use_rows else None, last=use_rows[-1]["end"] if use_rows else None))
    index = dict(schema="s26-m8-table-v1", rows=len(rows), valid=sum(1 for x in rows if x["eligible"] is True), by_stage={s: sum(1 for x in rows if x["stage"] == s) for s in R.ROOTS},
                 valid_by_stage={s: sum(1 for x in rows if x["stage"] == s and x["eligible"] is True) for s in R.ROOTS}, fingerprint=args.fingerprint, case_stand_wind=args.case_stand_wind, room_c=args.room,
                 readout=(r.stdout.strip().splitlines() or [""])[-1][:300], note="inventory only — 계산 0 (조민규 / Cowork)")
    C.write_json(args.out / "table_index.json", index)
    print(json.dumps({k: v for k, v in index.items() if k in ("rows", "valid", "by_stage", "valid_by_stage")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
