"""Session validity (등록 §4, 9 rules) + §4-7 delegation evidence + §4-N NPU output contract for one pulled session.

  py -3 s26/tools/mixreq/mixreq_validate.py <session_dir> [--device-dir <dir>] [--logcat <threadtime.txt>]
      [--skin-watch <csv>] [--phone-watch <csv>] [--selftest] [--out validated.json] [--npu-out npu_contract.json]

<session_dir> is a host result folder (results\\S26_MIXREQ_<i>_<policy>_a<attempt>\\) with device/ (pulled app files) and host/
(logcat_threadtime.txt, skin_watch.csv, phone_watch.csv, hal.csv, ...), or a bare device folder (PC round trip:
request-runner/build/mixreq-roundtrip/<case>/a1). --selftest: accepts manifest.time_scale != 1 (window bounds scaled) and the
absence of host watch files; a confirmation session is never eligible under --selftest.

Evidence rules are imported, never re-typed: tools/compiled_model_evidence.py (REPLACE_RE · GPU_ENVIRONMENT_RE · FAILURE_RE ·
GPU_FAILURE_RE · THREADTIME_RE; GPU rule v1) and tools/d1_logger_v4.py (NPU_DISPATCH_REPLACE_RE · NPU_ENN_LOADED_RE ·
NPU_DISPATCH_FAILURE_RE · FORMAL_NPU_AOT_MODELS). evaluate_gpu / evaluate_npu are NOT called (등록 §4-7: they look up the
runner PID by the D1GPU/D1NPU tags and the CPU runtime's XNNPACK line would fail them). Windows are cut by the app's D1MIX marks.
"""
from __future__ import annotations

import argparse
import base64
import csv
import importlib.util
import json
import math
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402
import policy_ref  # noqa: E402

REPO_TOOLS = HERE.parents[2] / "tools"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"_mixreq_{name}", REPO_TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EVIDENCE = _load("compiled_model_evidence")   # GPU rule v1 regexes (frozen 2026-10-03)
LOGGER = _load("d1_logger_v4")                 # NPU dispatch evidence regexes + AOT table
MARK_RE = re.compile(r"^(?P<what>session_start|runtime create_start|runtime create_end|warmup_start|warmup_end|common_start|common_end|drain_end|session_end)\b(?P<rest>.*)$")
KV_RE = re.compile(r"(\w+)=(\S+)")
SCHEMA = "s26-mixreq-validated-v1"
NPU_SCHEMA = "npu-mixreq-contract-v1"


# ----------------------------------------------------------------------------------------------- loading
def load_session(session_dir: Path, device_dir: Path | None):
    device = device_dir or (session_dir / "device" if (session_dir / "device").is_dir() else session_dir)
    host = session_dir / "host" if (session_dir / "host").is_dir() else None
    need = ["manifest.json", "cleanup.json", "progress.jsonl"]
    missing = [n for n in need if not (device / n).is_file()]
    data = dict(device_dir=str(device), host_dir=str(host) if host else None, missing=missing)
    if missing:
        return data
    data["manifest"] = C.read_json(device / "manifest.json")
    data["cleanup"] = C.read_json(device / "cleanup.json")
    for optional in ("summary.json", "requests.json", "common_boundary.json", "warmup.json", "start_check.json", "session_failure.json"):
        data[optional[:-5]] = C.read_json(device / optional) if (device / optional).is_file() else None
    events = []
    with open(device / "progress.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    data["events"] = events
    data["results"] = {}
    for p in device.glob("*.result.json"):
        data["results"][p.name[:-len(".result.json")]] = C.read_json(p)
    data["failure_files"] = sorted(p.name for p in device.glob("*.failure.json"))
    data["part_files"] = sorted(p.name for p in device.glob("*.part"))
    return data


# ----------------------------------------------------------------------------------------------- quality (A24 rule)
def compare_classification(ref: list[dict], cand: list[dict]) -> dict:
    pairs = [dict(label=a["label"] == b["label"], index=a["class_index"] == b["class_index"], score_delta=abs(a["score"] - b["score"]))
             for a, b in zip(ref, cand)]
    passed = len(ref) == len(cand) == 5 and all(p["label"] and p["index"] and p["score_delta"] <= C.CLS_SCORE_TOL for p in pairs)
    return dict(passed=passed, pairs=pairs, reference_count=len(ref), candidate_count=len(cand))


def compare_detection(ref: list[dict], cand: list[dict]) -> dict:
    """A24 tools/d1_probe_compare.compare_decoded: positional pairs after the canonical sort; |dscore| <= 1e-3, box <= 2 px."""
    pairs = [dict(label=a["label"] == b["label"], score_delta=abs(a["score"] - b["score"]),
                  max_box_delta_px=max(abs(x - y) for x, y in zip(a["box"], b["box"]))) for a, b in zip(ref, cand)]
    passed = len(ref) == len(cand) and all(p["label"] and p["score_delta"] <= C.DET_SCORE_TOL and p["max_box_delta_px"] <= C.DET_BOX_TOL_PX for p in pairs)
    return dict(passed=passed, pairs=pairs, reference_count=len(ref), candidate_count=len(cand))


def compare_results(task: str, ref: list[dict], cand: list[dict]) -> dict:
    return compare_classification(ref, cand) if task == "classification" else compare_detection(ref, cand)


def softmax_of(warmup_entry: dict) -> list[float] | None:
    b64 = warmup_entry.get("softmax_f32le_base64")
    if not b64:
        return None
    raw = base64.b64decode(b64)
    return list(struct.unpack("<%df" % (len(raw) // 4), raw))


# ----------------------------------------------------------------------------------------------- lane busy / overlap
def busy_intervals(rows: list[dict], lane: str) -> list[tuple[int, int]]:
    out = []
    for r in rows:
        if r.get("selected_backend") == lane and r.get("dispatch_ns") is not None and r.get("lane_available_ns") is not None:
            out.append((int(r["dispatch_ns"]), int(r["lane_available_ns"])))
    return sorted(out)


def overlap_ns(rows: list[dict], lane_a: str, lane_b: str) -> int:
    """Time both lanes are busy (busy = dispatch_ns .. lane_available_ns, the scheduler's own busy flag). Lanes are serial, so
    intervals of one lane never overlap each other and a double loop is exact."""
    total = 0
    a_iv, b_iv = busy_intervals(rows, lane_a), busy_intervals(rows, lane_b)
    for a0, a1 in a_iv:
        for b0, b1 in b_iv:
            total += max(0, min(a1, b1) - max(a0, b0))
    return total


# ----------------------------------------------------------------------------------------------- logcat evidence
def parse_logcat(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    return EVIDENCE.parse_log(text)


def marks_for(rows, sid: str):
    """D1MIX marks of the runner process that logged session_start for this sid. Returns (pid, [(line, what, kv)])."""
    starts = [r for r in rows if r["tag"] == C.LOG_TAG and r["msg"].startswith("session_start") and f"sid={sid}" in r["msg"]]
    if len(starts) != 1:
        return None, [], f"session_start marks for sid: {len(starts)}"
    pid = starts[0]["pid"]
    marks = []
    for r in rows:
        if r["pid"] != pid or r["tag"] != C.LOG_TAG:
            continue
        m = MARK_RE.match(r["msg"].strip())
        if m:
            marks.append((r["line"], m.group("what"), dict(KV_RE.findall(m.group("rest")))))
    return pid, marks, None


def window(marks, start_what, start_kv, end_what, end_kv):
    s = [l for l, w, kv in marks if w == start_what and all(kv.get(k) == v for k, v in start_kv.items())]
    e = [l for l, w, kv in marks if w == end_what and all(kv.get(k) == v for k, v in end_kv.items())]
    if len(s) != 1 or len(e) != 1 or e[0] < s[0]:
        return None
    return s[0], e[0]


def key_windows(marks, key: str):
    """The app creates every runtime first (sorted keys) and then warms each key twice in a row, so the lines that belong to one
    runtime are two disjoint windows: [create_start(key), create_end(key)] and [warmup_start(key, 0), warmup_end(key, 1)]
    (등록 §4-7: 앱의 runtime 생성 / warmup 시작 · 끝 표시로 자른다). Returns None when a mark is missing."""
    create = window(marks, "runtime create_start", {"key": key}, "runtime create_end", {"key": key})
    warm = window(marks, "warmup_start", {"key": key, "index": "0"}, "warmup_end", {"key": key, "index": "1"})
    if create is None or warm is None:
        return None
    return [create, warm]


def in_windows(line: int, windows) -> bool:
    return any(a <= line <= b for a, b in windows)


def gpu_evidence(rows, pid, marks, key: str) -> dict:
    """등록 §4-7 GPU = compiled_model_evidence GPU rule v1 regexes inside the key's creation + warmup windows."""
    win = key_windows(marks, key)
    if win is None:
        return dict(verdict="FAIL", reason="window marks missing", key=key)
    mine = [r for r in rows if r["pid"] == pid and in_windows(r["line"], win)]
    replacements = [(r, m) for r in mine for m in [EVIDENCE.REPLACE_RE.search(r["msg"])] if m]
    gpu = [(r, m) for r, m in replacements if m.group("name") == EVIDENCE.GPU_DELEGATE]
    other = [(r, m) for r, m in replacements if m.group("name") != EVIDENCE.GPU_DELEGATE]
    failures = [r for r in mine if EVIDENCE.FAILURE_RE.search(r["msg"]) or EVIDENCE.GPU_FAILURE_RE.search(r["msg"])]
    conditions = {
        "litert_cl_full_replacement": bool(gpu) and all(int(m.group("x")) == int(m.group("y")) > 0 for _, m in gpu),
        "gpu_environment_created": any(EVIDENCE.GPU_ENVIRONMENT_RE.search(r["msg"].rstrip()) for r in mine),
        "no_other_delegate_replacement": not other,
        "no_failure_or_fallback_line": not failures,
    }
    failed = [k for k, v in conditions.items() if not v]
    return dict(rule=EVIDENCE.GPU_RULE_VERSION, key=key, verdict="PASS" if not failed else "FAIL", conditions=conditions,
                failed_conditions=failed, window_lines=[list(w) for w in win], replacement_lines=[r["line"] for r, _ in replacements],
                replacements=[f"{m.group('x')}/{m.group('y')} {m.group('name')}" for _, m in replacements],
                failure_lines=[r["line"] for r in failures])


def npu_evidence(rows, pid, marks, key: str, model_sha256: str) -> dict:
    """등록 §4-7 NPU = npu-dispatch-evidence-v1 conditions: ① DispatchDelegate x==y==1 (AOT table) in [create_start, warmup_end 1]
    ② ENN loaded line (runner PID) in [session_start, NPU warmup end] ≥ 1 (necessary only) ③ dispatch failure 0 in the NPU window
    and in [common_start, drain_end]."""
    win = key_windows(marks, key)
    if win is None:
        return dict(verdict="FAIL", reason="window marks missing", key=key)
    session_start = [l for l, w, _ in marks if w == "session_start"]
    common = window(marks, "common_start", {}, "drain_end", {})
    partition = LOGGER.FORMAL_NPU_AOT_MODELS.get(str(model_sha256).lower())
    mine_win = [r for r in rows if r["pid"] == pid and in_windows(r["line"], win)]
    dispatch = [(r, m) for r in mine_win for m in [LOGGER.NPU_DISPATCH_REPLACE_RE.search(r["msg"])] if m]
    npu_warmup_end = win[1][1]
    enn = [r for r in rows if r["pid"] == pid and LOGGER.NPU_ENN_LOADED_RE.search(r["msg"]) and session_start and session_start[0] <= r["line"] <= npu_warmup_end]
    failures_win = [r for r in mine_win if LOGGER.NPU_DISPATCH_FAILURE_RE.search(r["msg"])]
    failures_common = [r for r in rows if r["pid"] == pid and common and common[0] <= r["line"] <= common[1] and LOGGER.NPU_DISPATCH_FAILURE_RE.search(r["msg"])]
    other = [(r, m) for r in mine_win for m in [EVIDENCE.REPLACE_RE.search(r["msg"])] if m and m.group("name") != "DispatchDelegate"]
    conditions = {
        "aot_partition_known": partition is not None,
        "dispatch_replacement_matches_aot": bool(dispatch) and partition is not None and all(
            int(m.group(1)) == partition["dispatch_ops"] and int(m.group(2)) == partition["dispatch_ops"] + partition["non_dispatch_ops"] for _, m in dispatch),
        "enn_loaded_in_runner_pid": bool(enn),
        "no_dispatch_failure_in_npu_window": not failures_win,
        "no_dispatch_failure_in_common_window": not failures_common and common is not None,
        "no_other_delegate_replacement_in_npu_window": not other,
    }
    failed = [k for k, v in conditions.items() if not v]
    return dict(rule="npu-dispatch-evidence-v1 (conditions, windowed by D1MIX marks)", key=key, verdict="PASS" if not failed else "FAIL",
                conditions=conditions, failed_conditions=failed, window_lines=[list(w) for w in win], common_window_lines=list(common) if common else None,
                dispatch_lines=[r["line"] for r, _ in dispatch], dispatch_replacements=[f"{m.group(1)}/{m.group(2)}" for _, m in dispatch],
                enn_lines=[r["line"] for r in enn], failure_lines=[r["line"] for r in failures_win + failures_common],
                aot_partition=partition, note="ENN load alone is not NPU evidence (CPU runs print it too); NPU core execution is not observable from the app")


# ----------------------------------------------------------------------------------------------- NPU contract §4-N
def npu_contract(data: dict) -> dict:
    m = data["manifest"]
    out = dict(schema=NPU_SCHEMA, session_id=m["session_id"], block=m["block"], policy=m["policy"], applicable=m["block"] == "N",
               used_by_policy=policy_ref.POLICY_PAR_NPU == m["policy"], passed=None, warmups=[], reason=None)
    if m["block"] != "N":
        out["reason"] = "block A: no NPU runtime"
        return out
    warmups = data.get("warmup") or []
    cpu = [w for w in warmups if w["key"] == "classification_CPU"]
    npu = [w for w in warmups if w["key"] == "classification_NPU"]
    if not cpu or not npu:
        out["passed"] = False
        out["reason"] = "warmup outputs missing (CPU %d, NPU %d)" % (len(cpu), len(npu))
        return out
    ref = softmax_of(sorted(cpu, key=lambda w: w["index"])[0])
    if ref is None:
        out["passed"] = False
        out["reason"] = "CPU warmup softmax missing"
        return out
    ref_top = C.top5_from_softmax(ref)
    all_pass = True
    for w in sorted(npu, key=lambda w: w["index"]):
        cand = softmax_of(w)
        entry = dict(index=w["index"])
        if cand is None or len(cand) != len(ref):
            entry.update(passed=False, reason="NPU softmax missing or size mismatch")
            all_pass = False
            out["warmups"].append(entry)
            continue
        cand_top = C.top5_from_softmax(cand)
        cos = C.cosine(ref, cand)
        deltas = [abs(a - b) for a, b in zip(ref, cand)]
        entry.update(
            top1_cpu=ref_top[0][0], top1_npu=cand_top[0][0], top1_equal=ref_top[0][0] == cand_top[0][0], cosine=cos,
            passed=(ref_top[0][0] == cand_top[0][0]) and cos is not None and cos >= C.NPU_COSINE_MIN,
            top5_order_equal=[i for i, _ in ref_top] == [i for i, _ in cand_top],
            top5_overlap=len({i for i, _ in ref_top} & {i for i, _ in cand_top}),
            max_abs_delta=max(deltas), mean_abs_delta=sum(deltas) / len(deltas),
            fp32_tolerance_violations=sum(1 for a, d in zip(ref, deltas) if d > 1e-4 + 1e-3 * abs(a)),
            bit_identical_to_cpu=all(a == b for a, b in zip(ref, cand)),
            npu_top1_score=cand_top[0][1], cpu_top1_score=ref_top[0][1],
        )
        all_pass = all_pass and entry["passed"]
        out["warmups"].append(entry)
    out["passed"] = all_pass and len(out["warmups"]) == C.WARMUPS_PER_KEY
    out["criteria"] = "top-1 index equal AND cosine >= 0.99, both NPU warmups vs CPU warmup #1 (등록 §4-N; A24 contract is separate)"
    return out


# ----------------------------------------------------------------------------------------------- rules
def validate(session_dir: Path, device_dir: Path | None, logcat: Path | None, skin_watch: Path | None, phone_watch: Path | None,
             selftest: bool) -> tuple[dict, dict | None]:
    data = load_session(session_dir, device_dir)
    rules: dict[str, dict] = {}
    differences: list[str] = []
    if data["missing"]:
        return dict(schema=SCHEMA, eligible=False, reasons=[f"missing device artifacts: {data['missing']}"], rules=rules,
                    device_dir=data["device_dir"]), None
    m = data["manifest"]
    policy, block, sid = m["policy"], m["block"], m["session_id"]
    scale = int(m.get("time_scale", 1))
    used = list(policy_ref.USED_KEYS[policy])
    keys = sorted(policy_ref.BLOCK_KEYS[block])
    planned = len(m["requests"])
    rows = data.get("requests") or []
    by_id = {r["request_id"]: r for r in rows}

    # 0 artifacts / completion / time scale
    summary, cleanup = data.get("summary"), data["cleanup"]
    r0 = dict(summary_completed=bool(summary) and summary.get("status") == "completed",
              cleanup_completed=cleanup.get("status") == "completed", requests_json=bool(rows),
              common_boundary=data.get("common_boundary") is not None, warmup_json=data.get("warmup") is not None,
              result_files=len(data["results"]) == planned, part_files_zero=not data["part_files"],
              time_scale_ok=(scale == 1) or (selftest and m.get("split") == "diagnostic"),
              split=m.get("split"), time_scale=scale)
    rules["0_artifacts"] = dict(passed=all(v for k, v in r0.items() if isinstance(v, bool)), detail=r0)

    # 1 all succeeded + result quality vs the same runtime's two warmups (+ same input tensor)
    warmups = data.get("warmup") or []
    wm = {}
    for w in warmups:
        wm.setdefault(w["key"], []).append(w)
    quality_fail, tensor_fail, status_fail = [], [], []
    for q in m["requests"]:
        r = by_id.get(q["request_id"])
        if r is None or r.get("terminal_status") != "succeeded":
            status_fail.append(q["request_id"])
            continue
        res = data["results"].get(q["request_id"])
        key = f"{q['task_id']}_{r.get('selected_backend')}"
        refs = sorted(wm.get(key, []), key=lambda w: w["index"])
        if res is None or len(refs) != C.WARMUPS_PER_KEY:
            quality_fail.append(q["request_id"])
            continue
        for w in refs:
            cmp = compare_results(q["task_id"], w["result"]["results"], res["results"])
            if not cmp["passed"]:
                quality_fail.append(q["request_id"])
                break
            if w["result"]["input_tensor_sha256"] != res.get("input_tensor_sha256"):
                tensor_fail.append(q["request_id"])
                break
    rules["1_requests_succeeded_quality"] = dict(
        passed=len(rows) == planned and not status_fail and not quality_fail and not tensor_fail,
        detail=dict(planned=planned, rows=len(rows), succeeded=sum(1 for r in rows if r.get("terminal_status") == "succeeded"),
                    status_fail=status_fail[:10], quality_fail=quality_fail[:10], input_tensor_fail=tensor_fail[:10],
                    quality_rule="same runtime key, both warmups: top-5 label/index + |ds|<=1e-3 / count+labels + |ds|<=1e-3 + box<=2px"))

    # 2 time order
    order = ["scheduled_arrival_ns", "actual_arrival_ns", "queue_entry_ns", "dispatch_ns", "execution_start_ns", "host_inference_start_ns",
             "host_inference_return_ns", "output_ready_ns", "persist_complete_ns", "worker_release_ns", "lane_available_ns"]
    bad_order = [r["request_id"] for r in rows if any(r.get(k) is None for k in order) or
                 any(int(r[a]) > int(r[b]) for a, b in zip(order, order[1:]))]
    rules["2_time_order"] = dict(passed=bool(rows) and not bad_order, detail=dict(violations=bad_order[:10], fields=order))

    # 3 window [35 s, 120 s) relative to the common origin (scaled under --selftest)
    boundary = data.get("common_boundary") or {}
    origin = boundary.get("start_ns")
    lo, hi = C.WINDOW_START_S * 1e9 / scale, C.COMMON_S * 1e9 / scale
    out_of_window = []
    if origin is not None:
        for r in rows:
            for k in ("dispatch_ns", "lane_available_ns"):
                if r.get(k) is None or not (lo <= int(r[k]) - int(origin) < hi):
                    out_of_window.append((r["request_id"], k))
    rules["3_window"] = dict(passed=origin is not None and bool(rows) and not out_of_window,
                             detail=dict(origin_ns=origin, bounds_s=[lo / 1e9, hi / 1e9], violations=out_of_window[:10],
                                         last_lane_available_s=max((int(r["lane_available_ns"]) - int(origin)) / 1e9 for r in rows if r.get("lane_available_ns")) if origin and rows else None))

    # 4 assignment == 등록 §2 and every resident runtime created + warmed (detection_GPU exception recorded)
    created = {e["key"] for e in data["events"] if e.get("kind") == "runtime_return"}
    warmed = {}
    for e in data["events"]:
        if e.get("kind") == "warmup_return":
            warmed.setdefault(e["key"], set()).add(e["index"])
    create_failed = {e["key"] for e in data["events"] if e.get("kind") == "runtime_create_failed"}
    wrong_lane = [r["request_id"] for r in rows if r.get("selected_backend") != policy_ref.lane_for(policy, r["task_id"])]
    missing_created = [k for k in keys if k not in created]
    missing_warm = [k for k in keys if warmed.get(k) != {0, 1}]
    if missing_created == ["detection_GPU"] and "detection_GPU" in create_failed:
        differences.append("A24 와 다름: detection_GPU 생성 실패 → 그 runtime 없이 진행 (등록 §3-1)")
        missing_created, missing_warm = [], [k for k in missing_warm if k != "detection_GPU"]
    rules["4_assignment_residents"] = dict(passed=bool(rows) and not wrong_lane and not missing_created and not missing_warm,
                                           detail=dict(wrong_lane=wrong_lane[:10], created=sorted(created), missing_created=missing_created,
                                                       missing_warmed=missing_warm, create_failed=sorted(create_failed), used_keys=used))

    # 5 overlap — v1 (등록 §4 규칙 5): CPU overlap 0 · PAR / PAR-NPU overlap > 0 are validity conditions.
    #             v2 (등록 v2 #4, experiment_id S26-MIXREQ-02*): only CPU overlap 0 is a validity condition; PAR / PAR-NPU overlap_s is
    #             recorded (the readout turns "any valid PAR/PAR-NPU session with overlap 0" into the tag "병행 겹침 없음 — 기술만", v2 #3).
    reg_version = C.registration_version(m["experiment_id"])
    lane_a, lane_b = [k.rsplit("_", 1)[1] for k in policy_ref.overlap_keys(policy)]
    ov = overlap_ns(rows, lane_a, lane_b) if lane_a != lane_b else 0
    foreign = [r["request_id"] for r in rows if r.get("selected_backend") not in (lane_a, lane_b)]
    if policy == policy_ref.POLICY_CPU:
        passed5 = ov == 0 and not foreign and all(r.get("selected_backend") == "CPU" for r in rows)
        expected5 = "0"
    elif reg_version == 1:
        passed5 = ov > 0 and not foreign
        expected5 = ">0"
    else:
        passed5 = not foreign
        expected5 = "recorded only (v2 #4); overlap 0 -> readout tag"
    rules["5_overlap"] = dict(passed=bool(rows) and passed5, detail=dict(lanes=[lane_a, lane_b], overlap_s=ov / 1e9 * scale, overlap_ns_raw=ov,
                                                                        foreign_lane_rows=foreign[:10], expected=expected5,
                                                                        registration_version=reg_version, overlap_zero=(ov == 0)))

    # 6 warmup quality (GPU vs CPU #1; CPU #2 vs #1; detection_CPU #2 vs #1) — only used keys judge; residents recorded
    wq = {}
    cpu1 = {task: sorted(wm.get(f"{task}_CPU", []), key=lambda w: w["index"]) for task in ("classification", "detection")}
    for key in keys:
        task, lane = key.rsplit("_", 1)
        entries = sorted(wm.get(key, []), key=lambda w: w["index"])
        if lane == "NPU":
            wq[key] = dict(judged=False, reason="NPU → §4-N contract, not the A24 tolerance")
            continue
        if not cpu1[task] or len(entries) != C.WARMUPS_PER_KEY:
            wq[key] = dict(judged=key in used, passed=False, reason="warmups missing")
            continue
        ref = cpu1[task][0]["result"]["results"]
        cmps = [compare_results(task, ref, e["result"]["results"]) for e in entries]
        if lane == "CPU":
            cmps = cmps[1:]  # CPU #1 is the reference itself; judge CPU #2 vs #1
        wq[key] = dict(judged=key in used, passed=all(c["passed"] for c in cmps), comparisons=cmps)
    judged = [v for v in wq.values() if v.get("judged")]
    rules["6_warmup_quality"] = dict(passed=bool(judged) and all(v["passed"] for v in judged),
                                     detail={k: {kk: vv for kk, vv in v.items() if kk != "comparisons"} for k, v in wq.items()})
    rules["6_warmup_quality"]["comparisons"] = {k: v.get("comparisons") for k, v in wq.items()}
    for k, v in wq.items():
        if k not in used and v.get("passed") is False:
            differences.append(f"상주만 하는 {k} 의 warmup 이 CPU 기준과 불일치 (표시만, 판정 아님)")

    # 7 delegation evidence (used accelerated runtimes only)
    ev = dict(logcat=str(logcat) if logcat else None, runtimes={})
    accelerated_used = [k for k in used if not k.endswith("_CPU")]
    if logcat is None or not Path(logcat).is_file():
        rules["7_delegation_evidence"] = dict(passed=(not accelerated_used) and selftest, detail=dict(ev, reason="logcat missing" if accelerated_used or not selftest else "no accelerated runtime used"))
    else:
        rows_log = parse_logcat(Path(logcat))
        pid, marks, err = marks_for(rows_log, sid)
        ev["runner_pid"] = pid
        ev["mark_count"] = len(marks)
        if err:
            ev["error"] = err
            rules["7_delegation_evidence"] = dict(passed=False, detail=ev)
        else:
            for key in keys:
                lane = key.rsplit("_", 1)[1]
                spec = next(r for r in m["runtimes"] if r["key"] == key)
                if lane == "GPU":
                    ev["runtimes"][key] = gpu_evidence(rows_log, pid, marks, key)
                elif lane == "NPU":
                    ev["runtimes"][key] = npu_evidence(rows_log, pid, marks, key, spec["model_sha256"])
                ev["runtimes"].get(key, {})["used_by_policy"] = key in used
            rules["7_delegation_evidence"] = dict(passed=all(ev["runtimes"][k]["verdict"] == "PASS" for k in accelerated_used), detail=ev)

    # 8 plugged 0 for every sample + start check thermal ≤ 1
    samples = [e for e in data["events"] if e.get("kind") == "power_sample"]
    plugged_bad = [e.get("mono_ns") for e in samples if e.get("plugged") != 0]
    start = data.get("start_check") or {}
    rules["8_plugged_start"] = dict(passed=bool(samples) and not plugged_bad and start.get("passed") is True,
                                    detail=dict(samples=len(samples), plugged_nonzero=len(plugged_bad), start_check=start.get("passed"),
                                                start_thermal_status=start.get("thermal_status")))

    # 9 watch events 0 + no in-app stop
    stop_reason = cleanup.get("stop_reason")
    watch = dict(skin=None, phone=None)
    if skin_watch and Path(skin_watch).is_file():
        with open(skin_watch, encoding="utf-8") as f:
            watch["skin"] = sum(1 for row in csv.DictReader(f) if (row.get("action") or "").strip())
    if phone_watch and Path(phone_watch).is_file():
        with open(phone_watch, encoding="utf-8") as f:
            watch["phone"] = sum(1 for row in csv.DictReader(f) if row.get("ok") == "1" and row.get("basic_normal") != "1")
    watch_ok = (watch["skin"] == 0 and watch["phone"] == 0) or (selftest and watch["skin"] is None and watch["phone"] is None)
    rules["9_watch_stop"] = dict(passed=stop_reason is None and not data["failure_files"] and data.get("session_failure") is None and watch_ok,
                                 detail=dict(stop_reason=stop_reason, failure_files=data["failure_files"], watch_events=watch,
                                             watch_source="host csv" if (skin_watch or phone_watch) else ("absent (selftest)" if selftest else "absent")))

    # eligible = every rule passed. --selftest (PC round trip / synthetic) can never make a *confirmation* session eligible: real
    # sessions are judged without --selftest, with the host watch files present. Diagnostic (smoke) sessions get the same 9 rules;
    # the readout only ever pairs confirmation sessions from the plan.
    reasons = [name for name, r in rules.items() if not r["passed"]]
    if selftest and m.get("split") == "confirmation":
        reasons.append("selftest cannot judge a confirmation session")
    eligible = not reasons
    validated = dict(schema=SCHEMA, session_id=sid, session_index=m["session_index"], block=block, pair=m["pair"], policy=policy,
                     attempt=m["attempt"], experiment_id=m["experiment_id"], registration_version=reg_version, split=m["split"],
                     time_scale=scale, selftest=selftest,
                     eligible=eligible, reasons=reasons, rules=rules, a24_differences=differences,
                     device_dir=data["device_dir"], host_dir=data["host_dir"],
                     counts=dict(planned=planned, succeeded=sum(1 for r in rows if r.get("terminal_status") == "succeeded"),
                                 failed=sum(1 for r in rows if r.get("terminal_status") == "failed"),
                                 unfinished=planned - len(rows) + sum(1 for r in rows if r.get("terminal_status") not in ("succeeded", "failed"))))
    contract = npu_contract(data) if block == "N" else None
    return validated, contract


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("session_dir", type=Path)
    ap.add_argument("--device-dir", type=Path)
    ap.add_argument("--logcat", type=Path)
    ap.add_argument("--skin-watch", type=Path)
    ap.add_argument("--phone-watch", type=Path)
    ap.add_argument("--selftest", action="store_true", help="PC round trip: allow time_scale != 1 and absent host watch files")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--npu-out", type=Path)
    args = ap.parse_args()
    host = args.session_dir / "host"
    logcat = args.logcat or (host / "logcat_threadtime.txt" if (host / "logcat_threadtime.txt").is_file() else None)
    skin = args.skin_watch or (host / "skin_watch.csv" if (host / "skin_watch.csv").is_file() else None)
    phone = args.phone_watch or (host / "phone_watch.csv" if (host / "phone_watch.csv").is_file() else None)
    validated, contract = validate(args.session_dir, args.device_dir, logcat, skin, phone, args.selftest)
    out = args.out or args.session_dir / "validated.json"
    C.write_json(out, validated)
    if contract is not None:
        C.write_json(args.npu_out or args.session_dir / "npu_contract.json", contract)
    print(json.dumps(dict(eligible=validated.get("eligible"), reasons=validated.get("reasons"),
                          npu_contract=None if contract is None else contract.get("passed")), ensure_ascii=False))
    return 0 if validated.get("eligible") else 1


if __name__ == "__main__":
    sys.exit(main())
