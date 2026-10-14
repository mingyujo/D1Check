"""M8 session validity (계약표 v1 §1 ~ §6 · policies/response/session_m8.json) — fixed before any M8 measurement. mixreq_validate (unchanged) is imported for load_session · npu_contract only.

  py -3 -X utf8 s26/tools/mixreq/m8_validate.py <session_dir> [--hal-cont <csv>] [--selftest] [--out validated.json]

Rules (eligible = all pass; 미완료 · 납기 손해 · undispatched 는 유효 결과 — 분모에 남긴다):
  A0 artifacts   summary completed (contract M8) · cleanup completed · requests.json · common_boundary · warmup.json · result files = succeeded · .part 0 · time_scale 1 (confirmation)
  A1 rows        planned = rows · terminal ∈ {succeeded, undispatched} (failed / unfinished / unobserved → 무효) · undispatched 는 dispatch_ns 없음
  A2 order       dispatched rows: scheduled ≤ queue_entry ≤ dispatch ≤ execution ≤ inference start ≤ return ≤ output_ready ≤ persist ≤ (readback start ≤ end) ≤ release ≤ available
  A3 window      모든 dispatch ∈ [origin, origin + 120 s) · common_end ≥ origin + 120 s · 모든 available 은 drain 안 (≤ common_end + 30 s)
  A4 route       selected_backend = route(policy, task) · 상주 = 블록 키 전부 생성 + warmup 2 (NONE: 0)
  A5 concurrency SERIAL: 동시 running ≤ 1 · PAIR: ≤ 2 · 허용 조합 키만 · strict head: dispatch 시각의 waiting 중 FIFO/EDD head = 그 요청
  A6 response    urgent: response = output_ready · normal: readback_ok true · response = readback_end · boundary 라벨
  A7 wait        WAIT 정책: wait_end 이벤트 ≤ first_n · 묶음 유일 · planned ≤ wait_ms · 누적 ≤ cap · wait 구간 안 dispatch 0 · wait 시작 때 running 0 · 다른 정책: wait 이벤트 0
  A8 prep        RECENT: prep.json kind = 매니페스트 · origin = prep_end + 5 s − 35 s (scaled) · 첫 예정 도착 = prep_end + 5 s · NONE: prep.json 없음
  A9 safety      stop 없음 · failure 파일 0 · session_failure 없음 · 표본 plugged 0 · interactive true · start_check passed · 표본 ≥ 1
  A10 coverage   coverage_check (앱 · host 따로) PASS — confirmation 만 (selftest/스모크 = 기록)
NPU contract (classification_NPU 상주) 는 블록 M 세션마다 계산 · 기록 (CN 정책만 판정에 포함 = A4 의 일부).
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
import m8_common as M8  # noqa: E402
import coverage_check as CC  # noqa: E402

SCHEMA = "s26-m8-validated-v1"
ORDER = ["scheduled_arrival_ns", "queue_entry_ns", "dispatch_ns", "execution_start_ns", "host_inference_start_ns", "host_inference_return_ns", "output_ready_ns", "persist_complete_ns",
         "readback_start_ns", "readback_end_ns", "worker_release_ns", "lane_available_ns"]


def rule(passed: bool, **detail) -> dict:
    return dict(passed=bool(passed), detail=detail)


def head_of(policy: str, waiting: list[dict]) -> dict | None:
    if not waiting:
        return None
    if M8.SELECTION[policy] == "EDD":
        return min(waiting, key=lambda r: (r["deadline_ns"], r["scheduled_arrival_ns"], r["ordinal"], r["request_id"]))
    return min(waiting, key=lambda r: (r["scheduled_arrival_ns"], r["ordinal"], r["request_id"]))


def validate(session_dir: Path, device_dir: Path | None, logcat: Path | None, skin_watch: Path | None, phone_watch: Path | None, selftest: bool,
             hal_cont: Path | None = None) -> tuple[dict, dict | None]:
    data = V.load_session(session_dir, device_dir)
    if data["missing"]:
        return dict(schema=SCHEMA, eligible=False, reasons=[f"missing device artifacts: {data['missing']}"], rules={}, device_dir=data["device_dir"]), None
    m = data["manifest"]
    if not M8.is_m8(m["experiment_id"]) or m.get("contract") != M8.CONTRACT:
        raise SystemExit(f"not an M8 session: {m['experiment_id']} contract {m.get('contract')}")
    policy, block = m["policy"], m["block"]
    scale = int(m.get("time_scale", 1))
    events = data["events"]
    rows = data.get("requests") or []
    summary, cleanup, boundary = data.get("summary") or {}, data["cleanup"], data.get("common_boundary") or {}
    origin = boundary.get("start_ns")
    planned = len(m["requests"])
    rules: dict[str, dict] = {}

    r0 = dict(summary_completed=summary.get("status") == "completed", summary_contract_m8=summary.get("contract") == M8.CONTRACT, cleanup_completed=cleanup.get("status") == "completed",
              requests_json=data.get("requests") is not None, common_boundary=bool(boundary), warmup_json=data.get("warmup") is not None,
              result_files=len(data["results"]) == sum(1 for r in rows if r.get("terminal_status") == "succeeded"), part_files_zero=not data["part_files"],
              time_scale_ok=(scale == 1) or (selftest and m.get("split") == "diagnostic"))
    rules["A0_artifacts"] = rule(all(v for v in r0.values() if isinstance(v, bool)), **r0, time_scale=scale, split=m.get("split"))

    terminal = {}
    for r in rows:
        terminal[r.get("terminal_status")] = terminal.get(r.get("terminal_status"), 0) + 1
    und_bad = [r["request_id"] for r in rows if r.get("terminal_status") == "undispatched" and r.get("dispatch_ns") is not None]
    rules["A1_rows"] = rule(len(rows) == planned and all(r.get("terminal_status") in ("succeeded", "undispatched") for r in rows) and not und_bad,
                            planned=planned, rows=len(rows), terminal=terminal, undispatched_with_dispatch=und_bad[:5])

    dispatched = [r for r in rows if r.get("dispatch_ns") is not None]
    bad_order = []
    for r in dispatched:
        seq = [(k, r[k]) for k in ORDER if r.get(k) is not None]
        if any(a[1] > b[1] for a, b in zip(seq, seq[1:])):
            bad_order.append(r["request_id"])
    rules["A2_order"] = rule(not bad_order, violations=bad_order[:10], fields=ORDER)

    window_ns = int(M8.COMMON_S * 1e9 / scale)
    drain_ns = int(M8.DRAIN_S * 1e9 / scale)
    end = boundary.get("end_ns")
    out_w = [r["request_id"] for r in dispatched if not (origin is not None and origin <= r["dispatch_ns"] < origin + window_ns)]
    late_av = [r["request_id"] for r in dispatched if r.get("lane_available_ns") is not None and end is not None and r["lane_available_ns"] > end + drain_ns]
    rules["A3_window"] = rule(origin is not None and end is not None and end >= origin + window_ns and not out_w and not late_av,
                              origin_ns=origin, window_s=M8.COMMON_S, end_ns=end, dispatch_outside=out_w[:10], available_after_drain=late_av[:10],
                              last_dispatch_s=max(((r["dispatch_ns"] - origin) / 1e9 * scale for r in dispatched), default=None) if origin else None,
                              last_available_s=max(((r["lane_available_ns"] - origin) / 1e9 * scale for r in dispatched if r.get("lane_available_ns")), default=None) if origin else None)

    wrong_lane = [r["request_id"] for r in dispatched if policy != M8.P_NO_RUNTIME and r.get("selected_backend") != M8.lane_for(policy, r["task_id"])]
    keys = sorted(M8.KEYS_M if block == M8.BLOCK_M else M8.KEYS_NONE)
    created = {e["key"] for e in events if e.get("kind") == "runtime_return"}
    warmed: dict[str, set] = {}
    for e in events:
        if e.get("kind") == "warmup_return":
            warmed.setdefault(e["key"], set()).add(e["index"])
    residents_ok = all(k in created and warmed.get(k) == {0, 1} for k in keys) and (keys or not created)
    rules["A4_route_residents"] = rule(not wrong_lane and residents_ok, wrong_lane=wrong_lane[:10], residents=keys, created=sorted(created), warmed={k: sorted(v) for k, v in warmed.items()})

    busy = [(r["dispatch_ns"], r["lane_available_ns"], f"{r['task_id']}_{r['selected_backend']}", r["request_id"]) for r in dispatched if r.get("lane_available_ns")]
    max_conc, bad_pair = 0, []
    allowed = set(M8.USED_KEYS_M8.get(policy, ())) if policy in M8.CONCURRENCY and M8.CONCURRENCY[policy] == "PAIR" else None
    for s, e, k, rid in busy:
        conc = [k2 for (s2, e2, k2, _) in busy if s2 <= s < e2]
        max_conc = max(max_conc, len(conc))
        if allowed is not None and any(k2 not in allowed for k2 in conc):
            bad_pair.append(rid)
    limit = 2 if allowed is not None else 1
    # strict head: at each dispatch, the waiting set (queue_entry ≤ t < dispatch or undispatched with queue_entry ≤ t) must have this request as head
    head_viol = []
    if policy in M8.SELECTION:
        for r in dispatched:
            t = r["dispatch_ns"]
            waiting = [x for x in rows if x.get("queue_entry_ns") is not None and x["queue_entry_ns"] <= t and (x.get("dispatch_ns") is None or x["dispatch_ns"] >= t)]
            h = head_of(policy, waiting)
            if h is None or h["request_id"] != r["request_id"]:
                head_viol.append(dict(id=r["request_id"], head=(h or {}).get("request_id")))
    rules["A5_concurrency_head"] = rule(max_conc <= limit and not bad_pair and not head_viol and policy != M8.P_NO_RUNTIME or (policy == M8.P_NO_RUNTIME and not dispatched),
                                        concurrency=M8.CONCURRENCY.get(policy), max_concurrent=max_conc, limit=limit, allowed_pair=sorted(allowed) if allowed else None,
                                        outside_allowed_pair=bad_pair[:10], strict_head_violations=head_viol[:10], selection=M8.SELECTION.get(policy))

    succ = [r for r in rows if r.get("terminal_status") == "succeeded"]
    bad_resp = []
    for r in succ:
        if r.get("priority") == "urgent":
            if r.get("response_ns") != r.get("output_ready_ns") or r.get("response_boundary") != "output_ready":
                bad_resp.append(r["request_id"])
        else:
            if r.get("readback_ok") is not True or r.get("response_ns") != r.get("readback_end_ns") or r.get("response_boundary") != "readback_complete":
                bad_resp.append(r["request_id"])
    rules["A6_response"] = rule(not bad_resp, violations=bad_resp[:10], urgent=sum(1 for r in succ if r.get("priority") == "urgent"), normal=sum(1 for r in succ if r.get("priority") == "normal"),
                                readback_ok=sum(1 for r in succ if r.get("readback_ok") is True), boundary="urgent = output_ready · normal = readback_complete (priority)")

    waits = [e for e in events if e.get("kind") == "wait_end"]
    args = m.get("policy_args")
    if args:
        bursts = [w.get("burst_index") for w in waits]
        in_wait = [r["request_id"] for r in dispatched if any(w["wait_start_ns"] <= r["dispatch_ns"] < w["wait_end_ns"] for w in waits)]
        running_at_start = [w.get("burst_index") for w in waits if any(s < w["wait_start_ns"] < e for (s, e, _, _) in busy)]
        cum = sum(w.get("planned_ms", 0) for w in waits)
        ok = len(waits) <= args["first_n_bursts"] and len(bursts) == len(set(bursts)) and all(w.get("planned_ms", 0) <= args["wait_ms"] for w in waits) and cum <= args["cap_ms"] and not in_wait and not running_at_start
        rules["A7_wait"] = rule(ok, policy_args=args, waits=len(waits), bursts=bursts, planned_total_ms=cum, dose_total_ms=round(sum(w.get("dose_ms", 0) for w in waits), 3),
                                cut=[w.get("cut_reason") for w in waits if w.get("cut_reason")], dispatch_inside_wait=in_wait[:10], running_at_wait_start=running_at_start, interventions=len(waits))
    else:
        rules["A7_wait"] = rule(not waits, waits=len(waits), note="WAIT 정책 아님 · wait 이벤트 0 이어야")

    prep_kind = (m.get("prep") or {}).get("kind", "NONE")
    prep = C.read_json(Path(data["device_dir"]) / "prep.json") if (Path(data["device_dir"]) / "prep.json").is_file() else None
    if prep_kind != "NONE":
        gap = int(M8.PREP_GAP_S * 1e9 / scale)
        first = int(M8.FIRST_OFFSET_US * 1e3 / scale)
        pe = (prep or {}).get("prep_end_ns")
        first_arrival = min((r["scheduled_arrival_ns"] for r in rows if r.get("scheduled_arrival_ns")), default=None)
        ok = prep is not None and prep.get("kind") == prep_kind and origin is not None and pe is not None and origin == pe + gap - first and first_arrival == pe + gap
        rules["A8_prep"] = rule(ok, kind=prep_kind, prep=({k: v for k, v in (prep or {}).items() if k != "call_records"} if prep else None), origin_ns=origin, first_arrival_ns=first_arrival,
                                rule="origin = prep_end + 5 s − 35 s · first = prep_end + 5 s")
    else:
        rules["A8_prep"] = rule(prep is None, kind="NONE", prep_json_present=prep is not None)

    samples = [e for e in events if e.get("kind") == "power_sample"]
    start = data.get("start_check") or {}
    rules["A9_safety"] = rule(cleanup.get("stop_reason") is None and not data["failure_files"] and data.get("session_failure") is None and samples and
                              all(e.get("plugged") == 0 and e.get("interactive") is True for e in samples) and start.get("passed") is True,
                              stop_reason=cleanup.get("stop_reason"), failure_files=data["failure_files"][:5], samples=len(samples), start_check=start.get("passed"),
                              watch_files=dict(skin=bool(skin_watch and Path(skin_watch).is_file()), phone=bool(phone_watch and Path(phone_watch).is_file())))

    cov = CC.check_session(session_dir, hal_cont, scale)
    gate_cov = m.get("split") == "confirmation" and not selftest
    rules["A10_coverage"] = rule(cov["passed"] if gate_cov else True, gated=gate_cov, app_passed=cov["app"]["passed"], host_passed=cov["host"]["passed"], reasons=cov["reasons"],
                                 app_post_t0_s=cov["app"].get("post_t0_s"), app_pre_t0_s=cov["app"].get("pre_t0_s"), host_post_t0_s=cov["host"].get("post_t0_s"), hal_cont=str(hal_cont) if hal_cont else None)

    contract = None
    if block == M8.BLOCK_M:
        view = dict(data, manifest=dict(m, block="N"))
        contract = V.npu_contract(view)
        contract.update(block=block, evaluated_as="block N rule (block M has classification_NPU resident)", used_by_policy=policy in (M8.P_FIFO_SERIAL_CN, M8.P_FIFO_PAIR_CN))
        if policy in (M8.P_FIFO_SERIAL_CN, M8.P_FIFO_PAIR_CN):
            rules["A4_route_residents"]["detail"]["npu_contract"] = contract.get("passed")
            rules["A4_route_residents"]["passed"] = bool(rules["A4_route_residents"]["passed"] and contract.get("passed") is True)
    reasons = [name for name, r in rules.items() if not r["passed"]]
    if selftest and m.get("split") == "confirmation":
        reasons.append("selftest cannot judge a confirmation session")
    svc = service_levels(rows, scale)
    validated = dict(schema=SCHEMA, session_id=m["session_id"], session_index=m["session_index"], experiment_id=m["experiment_id"], contract=M8.CONTRACT, block=block, policy=policy,
                     policy_args=args, prep=prep_kind, arm=m.get("arm"), attempt=m["attempt"], split=m["split"], analysis_split=m.get("analysis_split"), time_scale=scale, selftest=selftest,
                     eligible=not reasons, reasons=reasons, rules=rules, registration=m.get("registration"), service=svc, coverage=cov, device_dir=data["device_dir"], host_dir=data["host_dir"],
                     counts=dict(planned=planned, **terminal), npu_contract=contract.get("passed") if contract else None,
                     note="유효 = A0 ~ A10 · 미완료 · 납기 손해 · undispatched 는 유효 결과 (분모 유지) · J · 열 · 정책 비교 계산 0")
    return validated, contract


def service_levels(rows: list[dict], scale: int) -> dict:
    """분모 = planned (completed 만 남기지 않음) · 주응답 = response − scheduled_arrival · 기한 = deadline − scheduled · 70/80/90/95/100 = 그 비율 이상이 기한 안인지."""
    out = {}
    for cls in ("urgent", "normal", "all"):
        rs = [r for r in rows if cls == "all" or r.get("priority") == cls]
        n = len(rs)
        resp = [((r["response_ns"] - r["scheduled_arrival_ns"]) / 1e6 * scale) for r in rs if r.get("response_ns") and r.get("scheduled_arrival_ns")]
        met = sum(1 for r in rs if r.get("response_ns") and r.get("deadline_ns") and r["response_ns"] <= r["deadline_ns"])
        late = sum(1 for r in rs if r.get("response_ns") and r.get("deadline_ns") and r["response_ns"] > r["deadline_ns"])
        und = sum(1 for r in rs if r.get("terminal_status") == "undispatched")
        p95 = C.nearest_rank_p95(sorted(resp), n) if resp else None
        out[cls] = dict(planned=n, responded=len(resp), deadline_met=met, late=late, undispatched=und, failed=sum(1 for r in rs if r.get("terminal_status") == "failed"),
                        p95_ms=p95, mean_ms=(sum(resp) / len(resp)) if resp else None, max_ms=max(resp) if resp else None,
                        levels={str(lv): (met >= lv / 100.0 * n) if n else None for lv in (70, 80, 90, 95, 100)}, all_completed=(met + late == n) if n else None,
                        note="분모 planned · response_ns = urgent output_ready / normal readback_end · undispatched/failed 는 응답 없음 (분모 유지)")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("session_dir", type=Path)
    ap.add_argument("--device-dir", type=Path)
    ap.add_argument("--hal-cont", type=Path)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--npu-out", type=Path)
    args = ap.parse_args()
    host = args.session_dir / "host"
    skin = host / "skin_watch.csv" if (host / "skin_watch.csv").is_file() else None
    phone = host / "phone_watch.csv" if (host / "phone_watch.csv").is_file() else None
    validated, contract = validate(args.session_dir, args.device_dir, None, skin, phone, args.selftest, args.hal_cont)
    C.write_json(args.out or args.session_dir / "validated.json", validated)
    if contract is not None:
        C.write_json(args.npu_out or args.session_dir / "npu_contract.json", contract)
    print(json.dumps(dict(eligible=validated["eligible"], reasons=validated["reasons"], counts=validated["counts"]), ensure_ascii=False))
    return 0 if validated["eligible"] else 1


if __name__ == "__main__":
    sys.exit(main())
