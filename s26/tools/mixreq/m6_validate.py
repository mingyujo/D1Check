"""M6 session validity — 등록 M6 v3 §3-6 (P: V1 ~ V5) · K (요청 0 · 단계 · 표본 결측만). mixreq_validate (unchanged) is imported and its
9 rules are run and RECORDED (mixreq_rules, 판정 밖); eligibility = the registered rules below only. Fixed before any measurement.

  py -3 -X utf8 s26/tools/mixreq/m6_validate.py <session_dir> [--selftest] [--out validated.json]

P (S26-M6-P · -SMOKE):
  V1  planned 100 · requests.json 100 rows · every row dispatched (dispatch_ns) · every row terminal (succeeded | failed) — 기한 미충족은 유효성 아님
  V2  common_boundary.json: lane_available_ns null 0 (all 100 rows) AND every `lane_available` event in progress.jsonl < origin + 120.000 s
      (origin = common_boundary.start_ns · bound scaled by time_scale) — 119.999 s passes, 120.000 s fails
  V3  power_sample / drain = the R3 rules: mixreq rule 0 (summary · cleanup completed · requests.json · result files · no .part · time_scale) +
      power_sample count ≥ 1 + drain completed (post_window_drain phase_end) — max power_sample gap recorded (기록만)
  V4  C session: mixreq rule 5 (CPU overlap 0 · CPU lane only) · N session: NPU contract PASS (mixreq npu_contract on the block-M warmups) ·
      G session: no condition (recorded)
  V5  no in-app stop (cleanup.stop_reason none — covers screen_off · plugged · thermal · BAT · SOC) · no failure files · watch events 0 ·
      every power_sample plugged 0 and interactive true · start_check passed
K (S26-M6-K · -SMOKE):
  K1  requests 0: manifest requests [] · requests.json [] · common_boundary planned 0 and rows []
  K2  phases: summary · cleanup completed · runtime_setup → warmup → resident_baseline → common_start → common_end → post_window_drain →
      resident_cooling in this order · common_end − common_start ≥ 780 s / time_scale · resident keys = block M (5) created and warmed {0, 1}
  K3  samples: power_sample count ≥ 1 · plugged 0 and interactive true in every sample · start_check passed · no stop · no failure files ·
      watch events 0 (max power_sample gap recorded)
NPU contract is computed for every M6 session (NPU resident in block M) and written to npu_contract.json; only N sessions use it (V4).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402
import mixreq_validate as V  # noqa: E402
import policy_ref  # noqa: E402
import m6_common as M  # noqa: E402

SCHEMA = "s26-m6-validated-v1"
K_PHASE_ORDER = ("runtime_setup", "warmup", "resident_baseline", "common_start", "common_end", "post_window_drain", "resident_cooling")


def sample_stats(events: list[dict]) -> dict:
    samples = [e for e in events if e.get("kind") == "power_sample"]
    ts = [int(e["mono_ns"]) for e in samples]
    gaps = [(b - a) / 1e9 for a, b in zip(ts, ts[1:])]
    return dict(count=len(samples), max_gap_s=max(gaps) if gaps else None,
                plugged_nonzero=sum(1 for e in samples if e.get("plugged") != 0),
                interactive_false=sum(1 for e in samples if e.get("interactive") is not True))


def phase_marks(events: list[dict]) -> list[tuple[str, int]]:
    out = []
    for e in events:
        k = e.get("kind")
        if k == "phase_start" and e.get("phase") in ("runtime_setup", "warmup", "resident_baseline", "post_window_drain", "resident_cooling"):
            out.append((e["phase"], int(e["mono_ns"])))
        elif k in ("common_start", "common_end"):
            out.append((k, int(e["mono_ns"])))
    return out


def drain_completed(events: list[dict]) -> bool:
    return any(e.get("kind") == "phase_end" and e.get("phase") == "post_window_drain" for e in events)


def npu_contract_m(data: dict) -> dict:
    """mixreq npu_contract applies to block "N" only; block M has the same classification_NPU resident → evaluate it the same way."""
    view = dict(data, manifest=dict(data["manifest"], block="N"))
    out = V.npu_contract(view)
    out.update(block=data["manifest"]["block"], evaluated_as="block N rule (block M has classification_NPU resident)")
    return out


def v2(boundary: dict, events: list[dict], planned: int, scale: int) -> dict:
    """등록 §3-6 V2: common_boundary lane_available null 0 AND every lane_available event < origin + 120.000 s (scaled)."""
    origin = boundary.get("start_ns")
    bound_ns = int(M.V2_BOUND_S * 1e9 / scale)
    brows = boundary.get("rows") or []
    null_rows = [r.get("request_id") for r in brows if r.get("lane_available_ns") is None]
    la = [int(e["mono_ns"]) for e in events if e.get("kind") == "lane_available"]
    late = [t for t in la if origin is None or t - int(origin) >= bound_ns]
    last_s = max((t - int(origin)) / 1e9 * scale for t in la) if la and origin is not None else None
    return dict(passed=origin is not None and len(brows) == planned and not null_rows and len(la) == planned and not late,
                detail=dict(origin_ns=origin, bound_s=M.V2_BOUND_S, boundary_rows=len(brows), boundary_lane_available_null=len(null_rows),
                            null_ids=null_rows[:10], lane_available_events=len(la), events_at_or_after_bound=len(late), last_lane_available_s=last_s))


def watch_and_stop(mixreq_rules: dict) -> tuple[bool, dict]:
    r9 = mixreq_rules.get("9_watch_stop") or {}
    return bool(r9.get("passed")), r9.get("detail") or {}


def validate(session_dir: Path, device_dir: Path | None, logcat: Path | None, skin_watch: Path | None, phone_watch: Path | None,
             selftest: bool) -> tuple[dict, dict | None]:
    data = V.load_session(session_dir, device_dir)
    if data["missing"]:
        return dict(schema=SCHEMA, eligible=False, reasons=[f"missing device artifacts: {data['missing']}"], rules={}, device_dir=data["device_dir"]), None
    m = data["manifest"]
    if not M.is_m6(m["experiment_id"]):
        raise SystemExit(f"not an M6 session: {m['experiment_id']}")
    mixreq_validated, _ = V.validate(session_dir, device_dir, logcat, skin_watch, phone_watch, selftest)
    mrules = mixreq_validated.get("rules", {})
    scale = int(m.get("time_scale", 1))
    events = data["events"]
    rows = data.get("requests") or []
    boundary = data.get("common_boundary") or {}
    origin = boundary.get("start_ns")
    stats = sample_stats(events)
    start = data.get("start_check") or {}
    watch_ok, watch_detail = watch_and_stop(mrules)
    contract = npu_contract_m(data)
    rules: dict[str, dict] = {}

    if M.is_k(m["experiment_id"]):
        brows = boundary.get("rows")
        rules["K1_requests_zero"] = dict(passed=m["requests"] == [] and data.get("requests") == [] and boundary.get("planned") == 0 and brows == [],
                                         detail=dict(manifest_requests=len(m["requests"]), requests_json=None if data.get("requests") is None else len(data["requests"]),
                                                     boundary_planned=boundary.get("planned"), boundary_rows=None if brows is None else len(brows)))
        marks = phase_marks(events)
        names = [n for n, _ in marks]
        order_ok = [n for n in names if n in K_PHASE_ORDER] == list(K_PHASE_ORDER)
        cs = next((t for n, t in marks if n == "common_start"), None)
        ce = next((t for n, t in marks if n == "common_end"), None)
        window_ok = cs is not None and ce is not None and (ce - cs) >= int(C.common_s_of(m["experiment_id"]) * 1e9 / scale)
        created = {e["key"] for e in events if e.get("kind") == "runtime_return"}
        warmed: dict[str, set] = {}
        for e in events:
            if e.get("kind") == "warmup_return":
                warmed.setdefault(e["key"], set()).add(e["index"])
        keys = sorted(policy_ref.BLOCK_KEYS[M.BLOCK])
        residents_ok = all(k in created and warmed.get(k) == {0, 1} for k in keys)
        summary, cleanup = data.get("summary") or {}, data.get("cleanup") or {}
        rules["K2_phases"] = dict(passed=summary.get("status") == "completed" and cleanup.get("status") == "completed" and order_ok and window_ok and residents_ok,
                                  detail=dict(order=names, order_ok=order_ok, window_s=(ce - cs) / 1e9 * scale if cs and ce else None, window_ok=window_ok,
                                              residents=keys, created=sorted(created), warmed={k: sorted(v) for k, v in warmed.items()},
                                              summary_status=summary.get("status"), cleanup_status=cleanup.get("status")))
        rules["K3_samples"] = dict(passed=stats["count"] >= 1 and stats["plugged_nonzero"] == 0 and stats["interactive_false"] == 0 and start.get("passed") is True
                                   and watch_ok, detail=dict(samples=stats, start_check=start.get("passed"), watch_stop=watch_detail))
    else:
        planned = len(m["requests"])
        dispatched = [r for r in rows if r.get("dispatch_ns") is not None]
        terminal = [r for r in rows if r.get("terminal_status") in ("succeeded", "failed")]
        rules["V1_dispatch_terminal"] = dict(passed=planned == M.REQUEST_COUNT and len(rows) == planned and len(dispatched) == planned and len(terminal) == planned,
                                             detail=dict(planned=planned, rows=len(rows), dispatched=len(dispatched), terminal=len(terminal),
                                                         succeeded=sum(1 for r in rows if r.get("terminal_status") == "succeeded")))
        rules["V2_all_available_by_120s"] = v2(boundary, events, planned, scale)
        r0 = mrules.get("0_artifacts") or {}
        drained = drain_completed(events)
        rules["V3_samples_drain"] = dict(passed=bool(r0.get("passed")) and stats["count"] >= 1 and drained,
                                         detail=dict(mixreq_rule0=r0.get("passed"), rule0_detail=r0.get("detail"), samples=stats, drain_completed=drained))
        policy = m["policy"]
        if policy == policy_ref.POLICY_CPU:
            r5 = mrules.get("5_overlap") or {}
            rules["V4_overlap_npu"] = dict(passed=bool(r5.get("passed")), detail=dict(condition="C: CPU overlap 0", mixreq_rule5=r5.get("detail")))
        elif policy == policy_ref.POLICY_PAR_NPU:
            rules["V4_overlap_npu"] = dict(passed=contract.get("passed") is True, detail=dict(condition="N: NPU contract PASS", npu_contract=contract.get("passed")))
        else:
            r5 = mrules.get("5_overlap") or {}
            rules["V4_overlap_npu"] = dict(passed=True, detail=dict(condition="G: none (overlap recorded)", overlap_s=(r5.get("detail") or {}).get("overlap_s")))
        rules["V5_safety"] = dict(passed=watch_ok and stats["plugged_nonzero"] == 0 and stats["interactive_false"] == 0 and stats["count"] >= 1 and start.get("passed") is True,
                                  detail=dict(watch_stop=watch_detail, samples=stats, start_check=start.get("passed")))

    reasons = [name for name, r in rules.items() if not r["passed"]]
    if selftest and m.get("split") == "confirmation":
        reasons.append("selftest cannot judge a confirmation session")
    validated = dict(schema=SCHEMA, session_id=m["session_id"], session_index=m["session_index"], block=m["block"], pair=m["pair"], policy=m["policy"],
                     attempt=m["attempt"], experiment_id=m["experiment_id"], split=m["split"], analysis_split=m.get("analysis_split"),
                     m6_load=m.get("m6_load"), m6_letter=m.get("m6_letter"), m6_run=m.get("m6_run"), time_scale=scale, selftest=selftest,
                     eligible=not reasons, reasons=reasons, rules=rules, registration=M.REGISTRATION,
                     mixreq_rules={k: dict(passed=v.get("passed")) for k, v in mrules.items()},
                     mixreq_rules_note="mixreq_validate 9규칙 = 기록 (판정 밖) · 유효 = 등록 M6 v3 §3-6 V1 ~ V5 (P) / K1 ~ K3 (K)",
                     mixreq_reasons=mixreq_validated.get("reasons"), a24_differences=mixreq_validated.get("a24_differences"),
                     device_dir=data["device_dir"], host_dir=data["host_dir"], counts=mixreq_validated.get("counts"),
                     npu_contract=contract.get("passed"))
    return validated, contract


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("session_dir", type=Path)
    ap.add_argument("--device-dir", type=Path)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--npu-out", type=Path)
    args = ap.parse_args()
    host = args.session_dir / "host"
    logcat = host / "logcat_threadtime.txt" if (host / "logcat_threadtime.txt").is_file() else None
    skin = host / "skin_watch.csv" if (host / "skin_watch.csv").is_file() else None
    phone = host / "phone_watch.csv" if (host / "phone_watch.csv").is_file() else None
    validated, contract = validate(args.session_dir, args.device_dir, logcat, skin, phone, args.selftest)
    C.write_json(args.out or args.session_dir / "validated.json", validated)
    if contract is not None:
        C.write_json(args.npu_out or args.session_dir / "npu_contract.json", contract)
    print(json.dumps(dict(eligible=validated.get("eligible"), reasons=validated.get("reasons"), npu_contract=validated.get("npu_contract")), ensure_ascii=False))
    return 0 if validated.get("eligible") else 1


if __name__ == "__main__":
    sys.exit(main())
