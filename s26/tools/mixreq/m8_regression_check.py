"""D-1 회귀 판독 (기존 계약 · M8-apk · 판정 밖 · 기술값만): B2 (plan_v2 idx 1 a2) 긴급 P95 70 ~ 80 ms · M7 L-C (P_smoke_L-C a2) 마지막 AVAILABLE 72 ~ 75 s · 투영 SHA ad29e819 · cooling 60 그대로 ·
요청 행 키 = 기준 (M8 키 0) · 이벤트 종류 = 기준. 기존 행이 M8-apk 에서 M7-apk 와 같은 동작인지의 실기 근거.

  py -3 -X utf8 s26/tools/mixreq/m8_regression_check.py --results results/S26_M8_REGRESSION --out s26/results/m8_prep/regression_m8.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402
import m6_common as M  # noqa: E402

BASE_ROW_KEYS = {"request_id", "ordinal", "task_id", "priority", "scheduled_arrival_ns", "actual_arrival_ns", "deadline_ns", "terminal_status", "queue_entry_ns", "selected_backend",
                 "decision_reason", "dispatch_ns", "execution_start_ns", "host_inference_start_ns", "host_inference_return_ns", "output_ready_ns", "persist_complete_ns", "worker_release_ns", "lane_available_ns"}
M8_ONLY = {"readback_start_ns", "readback_end_ns", "readback_ok", "response_ns", "response_boundary", "wait_burst_index", "burst_index", "offset_us", "undispatched_reason", "readback_skipped"}
M8_EVENTS = {"wait_start", "wait_end", "readback", "dispatch_closed", "prep_end", "prep_call_start", "prep_call_end"}


def read(folder: Path) -> dict:
    dev = folder / "device"
    m = C.read_json(dev / "manifest.json")
    rows = C.read_json(dev / "requests.json") if (dev / "requests.json").is_file() else []
    b = C.read_json(dev / "common_boundary.json") if (dev / "common_boundary.json").is_file() else {}
    s = C.read_json(dev / "summary.json") if (dev / "summary.json").is_file() else {}
    v = C.read_json(folder / "validated.json") if (folder / "validated.json").is_file() else {}
    hl = C.read_json(folder / "host" / "session_log.json") if (folder / "host" / "session_log.json").is_file() else {}
    origin = b.get("start_ns")
    urg = sorted((r["output_ready_ns"] - r["scheduled_arrival_ns"]) / 1e6 for r in rows if r.get("priority") == "urgent" and r.get("output_ready_ns"))
    kinds = set()
    with open(dev / "progress.jsonl", encoding="utf-8") as f:
        for l in f:
            try:
                kinds.add(json.loads(l).get("kind"))
            except json.JSONDecodeError:
                pass
    keys = set().union(*[set(r) for r in rows]) if rows else set()
    out = dict(folder=folder.name, experiment_id=m["experiment_id"], session_index=m["session_index"], attempt=m["attempt"], policy=m["policy"], block=m["block"], contract=m.get("contract", "M6 (없음 = 기존)"),
               apk_sha256=hl.get("apk_sha256"), manifest_sha256=hl.get("manifest_sha256"), start_time=hl.get("start_time"), end_time=hl.get("end_time"), eligible=v.get("eligible"), reasons=v.get("reasons"),
               planned=len(m["requests"]), succeeded=sum(1 for r in rows if r.get("terminal_status") == "succeeded"), urgent_p95_ms=C.nearest_rank_p95(urg, len(urg)) if urg else None,
               last_lane_available_s=max(((r["lane_available_ns"] - origin) / 1e9 for r in rows if r.get("lane_available_ns")), default=None) if origin else None,
               cooling_s=m["phases"]["cooling_s"], baseline_s=m["phases"]["baseline_s"], row_keys_equal_base=(keys == BASE_ROW_KEYS), m8_keys_present=sorted(keys & M8_ONLY),
               m8_events_present=sorted(kinds & M8_EVENTS), summary_contract_key=("contract" in s), event_kinds=sorted(k for k in kinds if k))
    if len(m["requests"]) == M.REQUEST_COUNT:
        out["projection_sha256"] = M.projection_sha256(m["requests"])
        out["projection_matches_registered_L"] = out["projection_sha256"] == "ad29e8196e3f96a018d0f4483b9c14a2eab1150b6e670a4ccfb685d4364f39c6"
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    rows = [read(p) for p in sorted(args.results.iterdir()) if p.is_dir() and (p / "device" / "manifest.json").is_file()]
    rec = dict(schema="s26-m8-regression-v1", sessions=rows, targets=dict(b2_urgent_p95_ms=[70, 80], m7_lc_last_available_s=[72, 75], projection_L="ad29e819…", cooling_s=60),
               note="기존 계약 행 · M8-apk · 판정 밖 · 기술값 · 기존 행 동작 보존의 실기 근거 (SessionEngine.kt diff 0 과 함께)")
    for r in rows:
        if r["policy"] == "B2_PARALLEL_ONLINE_V1":
            r["in_target"] = r["urgent_p95_ms"] is not None and 70 <= r["urgent_p95_ms"] <= 80
        elif r["planned"] == 100:
            r["in_target"] = r["last_lane_available_s"] is not None and 72 <= r["last_lane_available_s"] <= 75 and r.get("projection_matches_registered_L")
    if args.out:
        C.write_json(args.out, rec)
    print(json.dumps([{k: r[k] for k in ("folder", "eligible", "urgent_p95_ms", "last_lane_available_s", "cooling_s", "row_keys_equal_base", "m8_keys_present", "m8_events_present", "summary_contract_key", "in_target") if k in r} for r in rows], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
