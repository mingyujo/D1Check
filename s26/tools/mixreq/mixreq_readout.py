"""Readout — KPI (등록 §5) · block judgments (§6) · Q2 table (§7, block A) · inventory CSV (조민규 10/8 형식안) · A24 cross-checks.

  py -3 s26/tools/mixreq/mixreq_readout.py --plan <plan.json> --results <dir with session result folders> --out <readout_dir>
      [--selftest] [--registration-commit <sha>] [--apk-sha256 <hex>] [--source-commit <sha>]

A session result folder = <results>/<anything>/ containing validated.json (+ npu_contract.json for block N), device/ or the bare
device artifacts, and optionally host/hal.csv (host HAL temperatures, 2 s) for the thermal KPIs. Sessions without validated.json
are skipped with a note; planned sessions never attempted appear in the inventory as not_attempted.

A24 cross-checks (등록 §5): (a) response / P95 / deadline_met = the formula of tools/d1_online_policy_model.py 199~208
(feature/arrival-scheduling-20260923 @ d588323, file SHA-256 a4e28dc489f221b1f85e8754b23385c60ba134af20ac701a3660293cac63156a)
transcribed in a24_service_formula(); (b) energy = vendor_a24/d1_energy_thermal.integrate (unmodified copy, scale_ua=1, max_gap 2.5 s)
vs our own trapezoid. A mismatch raises (stop and report).
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402
import policy_ref  # noqa: E402

_spec = importlib.util.spec_from_file_location("_a24_energy", HERE / "vendor_a24" / "d1_energy_thermal.py")
A24_ENERGY = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A24_ENERGY)

SCHEMA = "s26-mixreq-readout-v1"
INVENTORY_FIELDS = ["experiment_id", "session_id", "split", "terminal_status", "planned_request_count", "completed_count", "on_time_count",
                    "failed_count", "unfinished_count", "reason", "device_profile_id", "model_sha256", "input_sha256", "apk_sha256",
                    "source_commit", "engine_version", "precision", "requested_backend", "observed_backend_or_unknown",
                    "cpu_threads_or_unknown", "fallback_status", "policy_id", "policy_sha256", "registration_commit", "registration_time",
                    "start_time", "end_time", "raw_relative_path", "filename", "bytes", "sha256", "validation_status",
                    # S26 additions (not in the 10/8 draft): kept at the end so the draft columns stay in place
                    "session_index", "block", "pair", "attempt", "rejected_expired_cancelled_counts"]
POLICY_SHA256 = {  # SHA-256 of the policy *definition text* (등록 §2 line per policy) — a stable identifier, not code
    policy_ref.POLICY_CPU: C.sha256_bytes("CPU_URGENT_ONLINE_V1: CPU and GPU lanes both free -> all requests on *_CPU (A24 ArrivalPolicyStudy.choose)".encode()),
    policy_ref.POLICY_PAR: C.sha256_bytes("B2_PARALLEL_ONLINE_V1: classification -> GPU lane, detection -> CPU lane (A24 ArrivalPolicyStudy.choose, CG_DC)".encode()),
    policy_ref.POLICY_PAR_NPU: C.sha256_bytes("S26_NPU_PARALLEL_V1: classification -> NPU lane (AOT), detection -> CPU lane (등록 §2)".encode()),
}


# ----------------------------------------------------------------------------------------------- A24 formula (transcribed)
def a24_service_formula(rows: list[dict], requests: list[dict]) -> dict:
    """출처: tools/d1_online_policy_model.py @ d588323 199~208행 (SHA-256 a4e28dc4…). Only the *actual* side is kept; the
    structure (field by priority · response = (C − scheduled_arrival_ns)/1e6 · nearest-rank P95 · deadline_met) is verbatim.
    A24 line 199: field='output_ready_ns' if r['priority']=='urgent' else 'persist_complete_ns'
    A24 line 200: actual_response_ms=(r[field]-r['scheduled_arrival_ns'])/1e6
    A24 line 203: deadline_ms=next(q['deadline_ms'] for q in c['manifest_requests'] if q['request_id']==r['request_id'])
    A24 line 206-208: for priority in ('urgent','normal','all'): rows=[...]; v=[r['actual_response_ms'] for r in rows];
                      dict(planned=len(rows),completed=len(rows),p95_ms=sorted(v)[math.ceil(.95*len(v))-1],deadline_met=sum(a<=r['deadline_ms'] ...))
    A24 lines 62~67 (load_case) reject the case when any request failed or dispatch/lane_available fall outside [35 s, 120 s);
    that is our validity rule 3, applied before this function is used."""
    timing = []
    for r in rows:
        field = 'output_ready_ns' if r['priority'] == 'urgent' else 'persist_complete_ns'
        timing.append(dict(id=r['request_id'], priority=r['priority'], actual_response_ms=(r[field] - r['scheduled_arrival_ns']) / 1e6,
                           deadline_ms=next(q['deadline_ms'] for q in requests if q['request_id'] == r['request_id'])))
    service = {}
    for priority in ('urgent', 'normal', 'all'):
        trows = [r for r in timing if priority == 'all' or r['priority'] == priority]
        v = [r['actual_response_ms'] for r in trows]
        service['actual_' + priority] = dict(planned=len(trows), completed=len(trows), p95_ms=sorted(v)[math.ceil(.95 * len(v)) - 1],
                                             deadline_met=sum(a <= r['deadline_ms'] for a, r in zip(v, trows)))
    return service


# ----------------------------------------------------------------------------------------------- our KPI
def our_service(rows: list[dict], requests: list[dict]) -> dict:
    """등록 §5: response_i = C_i − scheduled; P95 nearest-rank with the denominator = planned per class; missing → +inf."""
    by_id = {r["request_id"]: r for r in rows}
    out = {}
    for cls in ("urgent", "normal", "all"):
        planned = [q for q in requests if cls == "all" or q["priority"] == cls]
        values, met = [], 0
        for q in planned:
            r = by_id.get(q["request_id"])
            if r is None or r.get("terminal_status") != "succeeded":
                continue
            field = "output_ready_ns" if q["priority"] == "urgent" else "persist_complete_ns"
            resp = (r[field] - r["scheduled_arrival_ns"]) / 1e6
            values.append(resp)
            met += resp <= q["deadline_ms"]
        out[cls] = dict(planned=len(planned), completed=len(values), p95_ms=C.nearest_rank_p95(values, len(planned)), deadline_met=met,
                        mean_ms=sum(values) / len(values) if values else None, max_ms=max(values) if values else None)
    return out


def queue_aux_p95(rows: list[dict], requests: list[dict]) -> dict:
    out = {}
    by_id = {r["request_id"]: r for r in rows}
    for cls in ("urgent", "normal"):
        planned = [q for q in requests if q["priority"] == cls]
        v = []
        for q in planned:
            r = by_id.get(q["request_id"])
            if r and r.get("terminal_status") == "succeeded" and r.get("queue_entry_ns") is not None:
                field = "output_ready_ns" if cls == "urgent" else "persist_complete_ns"
                v.append((r[field] - r["queue_entry_ns"]) / 1e6)
        out[cls] = C.nearest_rank_p95(v, len(planned))
    return out


def lane_service(rows: list[dict]) -> dict:
    out = {}
    for r in rows:
        if r.get("terminal_status") != "succeeded":
            continue
        key = f"{r['task_id']}_{r['selected_backend']}"
        out.setdefault(key, []).append((r["output_ready_ns"] - r["execution_start_ns"]) / 1e6)
    return {k: dict(n=len(v), median_ms=sorted(v)[len(v) // 2], p95_ms=C.nearest_rank_p95(v, len(v))) for k, v in out.items()}


def overlap_s(rows, policy, scale=1):
    from mixreq_validate import overlap_ns
    a, b = [k.rsplit("_", 1)[1] for k in policy_ref.overlap_keys(policy)]
    return 0.0 if a == b else overlap_ns(rows, a, b) / 1e9 * scale


def arrival_delay(rows):
    d = [(r["actual_arrival_ns"] - r["scheduled_arrival_ns"]) / 1e6 for r in rows if r.get("actual_arrival_ns") is not None]
    return dict(max_ms=max(d) if d else None, p95_ms=C.nearest_rank_p95(d, len(d)) if d else None)


# ----------------------------------------------------------------------------------------------- energy (기술만)
def power_samples(events: list[dict]) -> list[dict]:
    """A24 energy_thermal sample layout: mono_ns = midpoint of snapshot_start/sensor_read_end (등록 §5 · d1_online_policy_model)."""
    out = []
    for e in events:
        if e.get("kind") != "power_sample":
            continue
        t = (int(e["snapshot_start_ns"]) + int(e["sensor_read_end_ns"])) // 2
        out.append(dict(mono_ns=t, current_raw=e.get("current_raw"), current_valid=e.get("current_valid"), voltage_mV=e.get("voltage_mV"),
                        plugged=e.get("plugged"), charge_counter_raw=e.get("charge_counter_raw")))
    return out


def our_integrate(samples, start_ns, end_ns, max_gap_s=2.5):
    """Same definition as A24 integrate (trapezoid on power, clip at edges, no bridging > 2.5 s), S26 µA interpretation (scale 1)."""
    s = sorted(samples, key=lambda x: x["mono_ns"])
    energy = covered = 0.0

    def power(x):
        i, v = x.get("current_raw"), x.get("voltage_mV")
        if x.get("current_valid") is not True or x.get("plugged") != 0 or i is None or v is None or i == -2147483648 or i > 0 or v <= 0:
            return None
        return -i * 1 * v * 1e-9
    for a, b in zip(s, s[1:]):
        lo, hi = max(a["mono_ns"], start_ns), min(b["mono_ns"], end_ns)
        if hi <= lo:
            continue
        dt = (b["mono_ns"] - a["mono_ns"]) / 1e9
        if dt > max_gap_s:
            continue
        pa, pb = power(a), power(b)
        if pa is None or pb is None:
            continue
        p0 = pa + (pb - pa) * (lo - a["mono_ns"]) / (b["mono_ns"] - a["mono_ns"])
        p1 = pa + (pb - pa) * (hi - a["mono_ns"]) / (b["mono_ns"] - a["mono_ns"])
        el = (hi - lo) / 1e9
        energy += (p0 + p1) / 2 * el
        covered += el
    duration = (end_ns - start_ns) / 1e9
    return dict(covered_energy_j=energy if covered else None, covered_s=covered, missing_s=max(0.0, duration - covered),
                full_energy_j=energy if abs(duration - covered) < 1e-6 else None)


def energy_block(events, origin_ns, scale):
    samples = power_samples(events)
    end = origin_ns + int(C.COMMON_S * 1e9 / scale)
    a24 = A24_ENERGY.integrate(samples, origin_ns, end, 1, 2.5)
    ours = our_integrate(samples, origin_ns, end)
    for k in ("covered_energy_j", "full_energy_j"):
        x, y = a24[k], ours[k]
        if (x is None) != (y is None) or (x is not None and abs(x - y) > 1e-9 * max(1.0, abs(x))):
            raise RuntimeError(f"energy cross-check mismatch {k}: a24={x} ours={y}")
    cc = [s["charge_counter_raw"] for s in samples if origin_ns <= s["mono_ns"] <= end and s.get("charge_counter_raw") not in (None, -2147483648)]
    return dict(a24_integrate=a24, ours=ours, charge_counter_delta_uAh=(cc[-1] - cc[0]) if len(cc) >= 2 else None,
                samples_in_window=sum(1 for s in samples if origin_ns <= s["mono_ns"] <= end), unit="S26 µA interpretation (scale_ua=1) — 기술만, J 적격성 미확보")


# ----------------------------------------------------------------------------------------------- thermal (host HAL csv)
def thermal_block(hal_csv: Path | None, start_ns, end_ns):
    """host/hal.csv rows: pc_ms, device_boottime_s, SKIN, AP, BAT, PA, thermal_status (mixreq_session.py, 2 s). The common window is
    selected by the device boot-time bracket (/proc/uptime read in the same adb call = CLOCK_BOOTTIME = elapsedRealtimeNanos domain),
    never by subtracting PC wall clock. Returns None when absent."""
    if not hal_csv or not Path(hal_csv).is_file() or start_ns is None or end_ns is None:
        return None
    rows = []
    with open(hal_csv, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                t = float(r["device_boottime_s"])
            except (KeyError, ValueError, TypeError):
                continue
            if start_ns / 1e9 - 2.5 <= t <= end_ns / 1e9 + 2.5:
                rows.append(dict(t=t, SKIN=float(r["SKIN"]) if r.get("SKIN") else None, AP=float(r["AP"]) if r.get("AP") else None,
                                 BAT=float(r["BAT"]) if r.get("BAT") else None))
    if not rows:
        return dict(samples=0)
    first, last = rows[0], rows[-1]
    skin = [r["SKIN"] for r in rows if r["SKIN"] is not None]
    ap = [r["AP"] for r in rows if r["AP"] is not None]
    return dict(samples=len(rows), start_skin=first["SKIN"], start_ap=first["AP"], peak_skin=max(skin) if skin else None,
                peak_ap=max(ap) if ap else None, end_skin=last["SKIN"], end_ap=last["AP"], sensor_names="HAL SKIN / AP (Current temperatures from HAL)")


# ----------------------------------------------------------------------------------------------- per session
def read_session(folder: Path, selftest: bool) -> dict | None:
    v_path = folder / "validated.json"
    if not v_path.is_file():
        return None
    validated = C.read_json(v_path)
    device = Path(validated.get("device_dir") or folder)
    manifest = C.read_json(device / "manifest.json")
    summary = C.read_json(device / "summary.json") if (device / "summary.json").is_file() else None
    rows = C.read_json(device / "requests.json") if (device / "requests.json").is_file() else []
    boundary = C.read_json(device / "common_boundary.json") if (device / "common_boundary.json").is_file() else {}
    events = []
    if (device / "progress.jsonl").is_file():
        with open(device / "progress.jsonl", encoding="utf-8") as f:
            events = [json.loads(l) for l in f if l.strip()]
    contract = C.read_json(folder / "npu_contract.json") if (folder / "npu_contract.json").is_file() else None
    host_log = C.read_json(folder / "host" / "session_log.json") if (folder / "host" / "session_log.json").is_file() else {}
    scale = int(manifest.get("time_scale", 1))
    s = dict(folder=str(folder), session_id=manifest["session_id"], index=manifest["session_index"], block=manifest["block"],
             pair=manifest["pair"], policy=manifest["policy"], attempt=manifest["attempt"], split=manifest["split"],
             eligible=bool(validated.get("eligible")), reasons=validated.get("reasons", []), validated=validated, manifest=manifest,
             summary=summary, rows=rows, contract=contract, time_scale=scale, host_log=host_log,
             a24_differences=(summary or {}).get("a24_differences", []) + validated.get("a24_differences", []))
    if rows and summary and summary.get("status") == "completed":
        ours = our_service(rows, manifest["requests"])
        s["service"] = ours
        if all(r.get("terminal_status") == "succeeded" for r in rows) and len(rows) == len(manifest["requests"]):
            a24 = a24_service_formula(rows, manifest["requests"])
            for cls in ("urgent", "normal", "all"):
                a, o = a24["actual_" + cls], ours[cls]
                if a["p95_ms"] != o["p95_ms"] or a["deadline_met"] != o["deadline_met"] or a["planned"] != o["planned"]:
                    raise RuntimeError(f"A24 service cross-check mismatch ({s['session_id']} {cls}): a24={a} ours={o}")
            s["a24_service_cross_check"] = "match"
        s["queue_aux_p95_ms"] = queue_aux_p95(rows, manifest["requests"])
        s["lane_service_ms"] = lane_service(rows)
        s["overlap_s"] = overlap_s(rows, manifest["policy"], scale)
        s["arrival_delay_ms"] = arrival_delay(rows)
        origin = boundary.get("start_ns")
        s["last_lane_available_s"] = max((r["lane_available_ns"] - origin) / 1e9 * scale for r in rows if r.get("lane_available_ns")) if origin else None
        s["energy"] = energy_block(events, origin, scale) if origin is not None else None
        s["thermal"] = thermal_block(Path(folder) / "host" / "hal.csv", origin, boundary.get("end_ns"))
    return s


# ----------------------------------------------------------------------------------------------- judgments (§6)
def direction(deltas: list[float], refs: list[float], frac: float):
    if all(d < 0 for d in deltas) and all(abs(d) >= frac * abs(r) for d, r in zip(deltas, refs)):
        return "병행이 긴급 응답을 줄였다"
    if all(d < 0 for d in deltas):
        return "같은 방향 · 일부 작음"
    if all(d > 0 for d in deltas) and all(abs(d) >= frac * abs(r) for d, r in zip(deltas, refs)):
        return "병행이 긴급 응답을 늘렸다"
    return "엇갈림"


def thermal_direction(deltas: list[float | None]):
    if any(d is None for d in deltas):
        return "열 자료 없음"
    if all(abs(d) < 1.0 for d in deltas):
        return "열 차이 기준 안 (1.0 ℃)"
    if all(d >= 1.0 for d in deltas):
        return "병행이 더 뜨거웠다"
    if all(d <= -1.0 for d in deltas):
        return "병행이 덜 뜨거웠다"
    return "엇갈림"


TAG_A24_FAIL = "이식 대조 FAIL — 기술만"          # 등록 v2 #5 (Q1 · Q2 · Q3 전부)
TAG_NO_OVERLAP = "병행 겹침 없음 — 기술만"         # 등록 v2 #3 (유효 PAR / PAR-NPU 세션 중 겹침 0 이 하나라도)
Q2_TITLE_V1 = "동일 요청 정의의 기기 · 엔진별 이식 평가 (조민규 확인 뒤 본문 이름)"
Q2_TITLE_V2 = "간격이 다른 이식 (S26 200 ms · A24 400 ms) — 나란히 기술만"
Q2_SAME_DEFINITION_LINE_V2 = "같은 정의 (400 ms) S26 관측 = v1 스모크 24요청 · 겹침 0 (R2, s26-mixreq 03f271a)"
CONCLUSION_SUFFIX_V2 = "도착 간격 200 ms (A24 400 ms 의 절반 · v1 스모크 뒤 설계)"


def judge_block(block: str, sessions: list[dict], reg_version: int = 1, a24_compare_fail: bool = False) -> dict:
    par_policy = policy_ref.POLICY_PAR if block == "A" else policy_ref.POLICY_PAR_NPU
    label = "병행" if block == "A" else "NPU 병행"
    valid = [s for s in sessions if s["block"] == block and s["eligible"]]
    # one valid attempt per slot (등록 §4: the valid one; if both, the second)
    by_index = {}
    for s in sorted(valid, key=lambda s: s["attempt"]):
        by_index[s["index"]] = s
    pairs = []
    for p in range(4):
        cpu = [s for s in by_index.values() if s["pair"] == p and s["policy"] == policy_ref.POLICY_CPU]
        par = [s for s in by_index.values() if s["pair"] == p and s["policy"] == par_policy]
        if cpu and par:
            c, x = cpu[0], par[0]
            pairs.append(dict(pair=p, cpu_index=c["index"], par_index=x["index"],
                              cpu_urgent_p95_ms=c["service"]["urgent"]["p95_ms"], par_urgent_p95_ms=x["service"]["urgent"]["p95_ms"],
                              d_urgent_p95_ms=x["service"]["urgent"]["p95_ms"] - c["service"]["urgent"]["p95_ms"],
                              d_normal_p95_ms=x["service"]["normal"]["p95_ms"] - c["service"]["normal"]["p95_ms"],
                              cpu_normal_p95_ms=c["service"]["normal"]["p95_ms"],
                              d_peak_skin_c=(x["thermal"]["peak_skin"] - c["thermal"]["peak_skin"]) if x.get("thermal") and c.get("thermal") and x["thermal"].get("peak_skin") is not None and c["thermal"].get("peak_skin") is not None else None,
                              d_peak_ap_c=(x["thermal"]["peak_ap"] - c["thermal"]["peak_ap"]) if x.get("thermal") and c.get("thermal") and x["thermal"].get("peak_ap") is not None and c["thermal"].get("peak_ap") is not None else None,
                              d_start_skin_c=(x["thermal"]["start_skin"] - c["thermal"]["start_skin"]) if x.get("thermal") and c.get("thermal") and x["thermal"].get("start_skin") is not None and c["thermal"].get("start_skin") is not None else None,
                              d_energy_j=((x["energy"]["ours"]["full_energy_j"] or math.nan) - (c["energy"]["ours"]["full_energy_j"] or math.nan)) if x.get("energy") and c.get("energy") else None))
    out = dict(block=block, parallel_policy=par_policy, valid_sessions=sorted(s["index"] for s in by_index.values()), pairs=pairs, n=len(pairs),
               registration_version=reg_version, tags=[])
    # service judgment
    deadline = {pol: sum(s["service"]["all"]["planned"] - s["service"]["all"]["deadline_met"] for s in by_index.values() if s["policy"] == pol)
                for pol in (policy_ref.POLICY_CPU, par_policy)}
    out["deadline_missed_by_policy"] = deadline
    out["service_judgment"] = "두 정책 모두 기한 충족" if all(v == 0 for v in deadline.values()) and by_index else "기한 미충족 있음"
    # v2 #3: any valid parallel session (paired or not) with overlap 0 -> tag (recorded for v1 too, but only v2 uses it as a judgment)
    par_valid = [s for s in by_index.values() if s["policy"] == par_policy]
    out["parallel_overlap_zero_sessions"] = sorted(s["index"] for s in par_valid if s.get("overlap_s") is not None and s["overlap_s"] == 0)
    out["parallel_overlap_s"] = {str(s["index"]): s.get("overlap_s") for s in sorted(par_valid, key=lambda s: s["index"])}
    # tag precedence (R3 원장 1-2 ①, fixed before any v2 session): 이식 대조 FAIL > NPU 계약 실패 > 병행 겹침 없음 > 쌍 부족 > 방향 판정
    if a24_compare_fail:
        out["tags"].append(TAG_A24_FAIL)
    if block == "N":
        contracts = [s for s in valid if s["policy"] == par_policy]
        failed = [s["index"] for s in contracts if not (s.get("contract") and s["contract"].get("passed") is True)]
        out["npu_contract_failed_sessions"] = failed
        if failed or not contracts:
            out["tags"].append("NPU 출력 계약 실패 — 같은 일로 보지 않음 · 기술만" if failed else "유효 PAR-NPU 세션 없음 — 기술만")
            out["note"] = "서비스 · 응답 · 열 판정 없음 (등록 §6 Q3 ①); 쌍별 Δ · 기한 충족 수만 기술"
    if reg_version == 2 and out["parallel_overlap_zero_sessions"]:
        out["tags"].append(TAG_NO_OVERLAP)
    if len(pairs) < 3:
        out["tags"].append("쌍 부족 — 기술만")
    if out["tags"]:
        out["judgment"] = out["tags"][0]
        return out
    d_urgent = [p["d_urgent_p95_ms"] for p in pairs]
    out["urgent_judgment"] = direction(d_urgent, [p["cpu_urgent_p95_ms"] for p in pairs], 0.05).replace("병행", label)
    out["normal_judgment"] = direction([p["d_normal_p95_ms"] for p in pairs], [p["cpu_normal_p95_ms"] for p in pairs], 0.05).replace("병행", label)
    out["thermal_skin_judgment"] = thermal_direction([p["d_peak_skin_c"] for p in pairs]).replace("병행", label)
    out["thermal_ap_judgment"] = thermal_direction([p["d_peak_ap_c"] for p in pairs]).replace("병행", label)
    out["energy_judgment"] = "판정 없음 (기술만)"
    out["judgment"] = out["urgent_judgment"]
    return out


# ----------------------------------------------------------------------------------------------- slots (v2 #6 · inventory)
def slot_status(plan: dict, sessions: list[dict]) -> dict:
    """Per planned index: valid (an eligible attempt) · invalid_twice (two attempts, none eligible — the driver moved on, 등록 v2 #6) ·
    invalid_once (one ineligible attempt only — e.g. the block stopped before the retry) · not_attempted."""
    out = {}
    for entry in plan["sessions"]:
        tries = sorted((s for s in sessions if s["index"] == entry["index"]), key=lambda s: s["attempt"])
        if any(s["eligible"] for s in tries):
            status = "valid"
        elif len(tries) >= 2:
            status = "invalid_twice"
        elif tries:
            status = "invalid_once"
        else:
            status = "not_attempted"
        out[str(entry["index"])] = dict(status=status, attempts=[dict(attempt=s["attempt"], eligible=s["eligible"], reasons=s["reasons"]) for s in tries],
                                        block=entry["block"], policy=entry["policy"])
    return out


# ----------------------------------------------------------------------------------------------- inventory
def inventory_rows(plan: dict, sessions: list[dict], args) -> list[dict]:
    rows = []
    attempted = {}
    for s in sessions:
        attempted.setdefault(s["index"], []).append(s)
    for entry in plan["sessions"]:
        idx = entry["index"]
        if idx not in attempted:
            rows.append(dict(experiment_id=plan["experiment_id"], session_id=entry["session_id"], split="confirmation", terminal_status="not_attempted",
                             planned_request_count=192, completed_count=0, on_time_count=0, failed_count=0, unfinished_count=192,
                             reason="not_attempted", device_profile_id="S26-anon", model_sha256="unknown", input_sha256=plan["inputs"]["png"]["sha256"],
                             apk_sha256=args.apk_sha256 or "unknown", source_commit=args.source_commit or "unknown", engine_version="litert-compiled-model 2.2.0",
                             precision="FP32 io; GPU FP32 requested; NPU AOT FP16 weights [E]", requested_backend=";".join(policy_ref.USED_KEYS[entry["policy"]]),
                             observed_backend_or_unknown="unknown", cpu_threads_or_unknown="1 (configured) / unknown (observed)", fallback_status="unknown",
                             policy_id=entry["policy"], policy_sha256=POLICY_SHA256[entry["policy"]], registration_commit=plan["registration"]["commit"],
                             registration_time=plan["registration"]["time"], start_time="missing", end_time="missing", raw_relative_path="missing",
                             filename="missing", bytes="missing", sha256="missing", validation_status="not_attempted", session_index=idx,
                             block=entry["block"], pair=entry["pair"], attempt=0, rejected_expired_cancelled_counts="0/0/0"))
            continue
        slot = slot_status(plan, sessions)[str(idx)]["status"]
        for s in sorted(attempted[idx], key=lambda s: s["attempt"]):
            v = s["validated"]
            counts = v.get("counts", {})
            svc = s.get("service", {}).get("all", {})
            observed = []
            ev = (v.get("rules", {}).get("7_delegation_evidence", {}).get("detail") or {}).get("runtimes") or {}
            for key in policy_ref.USED_KEYS[s["policy"]]:
                if key.endswith("_CPU"):
                    observed.append(f"{key}=CPU")
                elif key in ev and ev[key].get("verdict") == "PASS":
                    observed.append(f"{key}=" + ("GPU (LITERT_CL)" if key.endswith("_GPU") else "NPU (ENN 경로)"))
                else:
                    observed.append(f"{key}=unknown")
            status = "completed" if (s.get("summary") or {}).get("status") == "completed" else ("stopped" if (v.get("rules", {}).get("9_watch_stop", {}).get("detail") or {}).get("stop_reason") else "failed")
            rows.append(dict(experiment_id=s["manifest"]["experiment_id"], session_id=s["session_id"], split=s["split"], terminal_status=status,
                             planned_request_count=counts.get("planned", 192), completed_count=counts.get("succeeded", 0), on_time_count=svc.get("deadline_met", "unknown"),
                             failed_count=counts.get("failed", 0), unfinished_count=counts.get("unfinished", 0),
                             reason=(";".join(s["reasons"]) if s["reasons"] else ("eligible" if s["eligible"] else "unknown")) + (f";slot={slot}" if slot != "valid" else ""),
                             device_profile_id="S26-anon", model_sha256=";".join(sorted({r["model_sha256"] for r in s["manifest"]["runtimes"] if r["key"] in policy_ref.USED_KEYS[s["policy"]]})),
                             input_sha256=s["manifest"]["image"]["sha256"], apk_sha256=((s.get("summary") or {}).get("apk_sha256") or args.apk_sha256 or "unknown"),
                             source_commit=args.source_commit or "unknown", engine_version="litert-compiled-model 2.2.0",
                             precision="FP32 io; GPU FP32 requested; NPU AOT FP16 weights [E]", requested_backend=";".join(policy_ref.USED_KEYS[s["policy"]]),
                             observed_backend_or_unknown=";".join(observed), cpu_threads_or_unknown="1 (configured) / unknown (observed)",
                             fallback_status="none observed (evidence rule PASS)" if all("unknown" not in o for o in observed) else "unknown",
                             policy_id=s["policy"], policy_sha256=POLICY_SHA256[s["policy"]], registration_commit=plan["registration"]["commit"],
                             registration_time=plan["registration"]["time"], start_time=s["host_log"].get("start_time", "missing"), end_time=s["host_log"].get("end_time", "missing"),
                             raw_relative_path=str(Path(s["folder"]).name), filename="see files inventory", bytes="see files inventory", sha256="see files inventory",
                             validation_status="eligible" if s["eligible"] else "ineligible", session_index=idx, block=s["block"], pair=s["pair"], attempt=s["attempt"],
                             rejected_expired_cancelled_counts="0/0/0"))
    return rows


def files_inventory(sessions: list[dict]) -> list[dict]:
    rows = []
    for s in sessions:
        device = Path(s["validated"].get("device_dir") or s["folder"])
        for p in sorted(device.iterdir()):
            if p.is_file():
                rows.append(dict(session_id=s["session_id"], attempt=s["attempt"], filename=p.name, bytes=p.stat().st_size, sha256=C.sha256_file(p)))
    return rows


def write_csv(path: Path, rows: list[dict], fields: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


# ----------------------------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", required=True, type=Path)
    ap.add_argument("--results", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--apk-sha256")
    ap.add_argument("--source-commit")
    ap.add_argument("--a24-compare", type=Path, help="v2 #5: mixreq_a24_compare.py output json of the v2 APK smoke; verdict FAIL -> Q1 · Q2 · Q3 '이식 대조 FAIL — 기술만'")
    args = ap.parse_args()
    plan = C.read_json(args.plan)
    reg_version = C.registration_version(plan["experiment_id"])
    a24_compare = C.read_json(args.a24_compare) if args.a24_compare and args.a24_compare.is_file() else None
    if args.a24_compare and a24_compare is None:
        raise SystemExit(f"--a24-compare {args.a24_compare} not found (v2 #5 needs the verdict; pass the smoke a24_compare.json)")
    a24_fail = bool(a24_compare) and a24_compare.get("verdict") != "PASS"
    sessions = []
    skipped = []
    for folder in sorted(p for p in args.results.iterdir() if p.is_dir()):
        s = read_session(folder, args.selftest)
        if s is None:
            skipped.append(folder.name)
        else:
            sessions.append(s)
    blocks = {b: judge_block(b, sessions, reg_version, a24_fail) for b in ("A", "N")}
    slots = slot_status(plan, sessions)
    # Q2 (block A only) table rows
    q2 = [dict(index=s["index"], policy=s["policy"], attempt=s["attempt"], eligible=s["eligible"],
               deadline_met=s.get("service", {}).get("all", {}).get("deadline_met"), urgent_p95_ms=s.get("service", {}).get("urgent", {}).get("p95_ms"),
               normal_p95_ms=s.get("service", {}).get("normal", {}).get("p95_ms"), overlap_s=s.get("overlap_s"), last_lane_available_s=s.get("last_lane_available_s"),
               start_skin_c=(s.get("thermal") or {}).get("start_skin"), peak_skin_c=(s.get("thermal") or {}).get("peak_skin"), peak_ap_c=(s.get("thermal") or {}).get("peak_ap"),
               energy_j_uA_interpretation=((s.get("energy") or {}).get("ours") or {}).get("full_energy_j"))
          for s in sessions if s["block"] == "A"]
    aux = dict(par_vs_parnpu="다른 블록 · 다른 분류 artifact · 정밀도 — 순위 아님 (기술만)",
               block_A_par_minus_cpu=[p["d_urgent_p95_ms"] for p in blocks["A"]["pairs"]],
               block_N_parnpu_minus_cpu=[p["d_urgent_p95_ms"] for p in blocks["N"]["pairs"]],
               cpu_urgent_p95_block_A=[s["service"]["urgent"]["p95_ms"] for s in sessions if s["block"] == "A" and s["policy"] == policy_ref.POLICY_CPU and s.get("service")],
               cpu_urgent_p95_block_N=[s["service"]["urgent"]["p95_ms"] for s in sessions if s["block"] == "N" and s["policy"] == policy_ref.POLICY_CPU and s.get("service")])
    a24_reference = dict(source="등록 §1-6 [D] (Cowork 가 등록 전에 본 A24 숫자)", sessions="8/8", deadline="192/192",
                         urgent_p95_cpu_ms="422.5~430.2", urgent_p95_par_ms="291.1~302.3", pair_delta_ms="−127.9~−131.4", overlap_par_s="21.92~22.58",
                         last_lane_s="112.01~112.07", energy_j_mA_interpretation="184.5~199.2", peak_ap_delta_c="−0.4~+0.4", verdict="정책 우열 미판정")
    q2_table = dict(title=Q2_TITLE_V2 if reg_version == 2 else Q2_TITLE_V1, judgment=(TAG_A24_FAIL if a24_fail else "관측만 · 우열 · 기기 효과 판정 없음"),
                    rows=q2, a24_reference=a24_reference)
    if reg_version == 2:
        q2_table["same_definition_s26_observation"] = Q2_SAME_DEFINITION_LINE_V2
        q2_table["note"] = "A24 400 ms · S26 200 ms — 같은 요청 정의가 아니다 (등록 v2 #9); 같은 부하로 읽지 않는다 (v2 §2 반대 해석 18)"
    notes = ["J = S26 µA 해석 · 기술만 (적격성 미확보)", "열 = 호스트 HAL SKIN/AP (센서 이름 그대로) · A24 는 AP",
             "NPU 문장: Samsung ENN NPU 경로로 실행 (코어 직접 증거 없음)", "조민규 확인 전 = 부록 관측 (등록 §9)"]
    if reg_version == 2:
        notes += [f"결론 문장에 늘 붙인다: {CONCLUSION_SUFFIX_V2} (등록 v2 §3)", "결과 지위 = S26 부록 관측 (등록 v2 §3)",
                  "꼬리표 우선순위 (R3 원장 1-2): 이식 대조 FAIL > NPU 계약 실패 > 병행 겹침 없음 > 쌍 부족 > 방향 판정"]
    readout = dict(schema=SCHEMA, plan=str(args.plan), plan_sha256=C.sha256_file(args.plan), selftest=args.selftest, sessions=len(sessions), skipped=skipped,
                   registration_version=reg_version, registration=plan.get("registration"), step_ms=plan.get("step_ms", 400),
                   a24_compare=dict(path=str(args.a24_compare) if args.a24_compare else None, verdict=(a24_compare or {}).get("verdict"), fail=a24_fail),
                   slots=slots, slot_counts={k: sum(1 for v in slots.values() if v["status"] == k) for k in ("valid", "invalid_twice", "invalid_once", "not_attempted")},
                   per_session=[{k: v for k, v in s.items() if k not in ("validated", "manifest", "rows", "host_log")} for s in sessions],
                   blocks=blocks, q2_block_A=q2, q2_table=q2_table, a24_reference_for_q2=a24_reference, auxiliary=aux, notes=notes)
    C.write_json(args.out / "readout.json", readout)
    write_csv(args.out / "inventory.csv", inventory_rows(plan, sessions, args), INVENTORY_FIELDS)
    write_csv(args.out / "files_inventory.csv", files_inventory(sessions), ["session_id", "attempt", "filename", "bytes", "sha256"])
    write_csv(args.out / "metrics.csv", [dict(index=s["index"], block=s["block"], pair=s["pair"], policy=s["policy"], attempt=s["attempt"], eligible=s["eligible"],
                                             urgent_p95_ms=s.get("service", {}).get("urgent", {}).get("p95_ms"), normal_p95_ms=s.get("service", {}).get("normal", {}).get("p95_ms"),
                                             all_p95_ms=s.get("service", {}).get("all", {}).get("p95_ms"), deadline_met=s.get("service", {}).get("all", {}).get("deadline_met"),
                                             completed=s.get("service", {}).get("all", {}).get("completed"), overlap_s=s.get("overlap_s"), last_lane_available_s=s.get("last_lane_available_s"),
                                             arrival_delay_max_ms=(s.get("arrival_delay_ms") or {}).get("max_ms"), queue_aux_urgent_p95_ms=(s.get("queue_aux_p95_ms") or {}).get("urgent"),
                                             energy_j=((s.get("energy") or {}).get("ours") or {}).get("full_energy_j"), peak_skin_c=(s.get("thermal") or {}).get("peak_skin"),
                                             peak_ap_c=(s.get("thermal") or {}).get("peak_ap"), npu_contract=(s.get("contract") or {}).get("passed")) for s in sessions],
              ["index", "block", "pair", "policy", "attempt", "eligible", "urgent_p95_ms", "normal_p95_ms", "all_p95_ms", "deadline_met", "completed", "overlap_s",
               "last_lane_available_s", "arrival_delay_max_ms", "queue_aux_urgent_p95_ms", "energy_j", "peak_skin_c", "peak_ap_c", "npu_contract"])
    print(json.dumps(dict(sessions=len(sessions), skipped=skipped, registration_version=reg_version, a24_compare_fail=a24_fail,
                          block_A=blocks["A"].get("judgment"), block_N=blocks["N"].get("judgment"), tags_A=blocks["A"]["tags"], tags_N=blocks["N"]["tags"],
                          q2_title=q2_table["title"], pairs_A=blocks["A"]["n"], pairs_N=blocks["N"]["n"], slot_counts=readout["slot_counts"]), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
