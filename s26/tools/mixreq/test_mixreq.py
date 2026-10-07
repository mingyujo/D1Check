"""P tests for the S26 mixed-request host tools.  Run:  py -3 -m pytest s26/tools/mixreq -q

Covers (prompt 4부 P 시험): plan determinism (16 + 4 smoke, blocks, pair numbers, budget) · request table == uuid5 derivation ·
validate: every rule has >= 1 failing case; NPU evidence (replacement 1/1 + ENN = PASS; no ENN / 0 of 1 / failure line / AOT mismatch = FAIL) ·
NPU contract synthetic vectors (cosine 0.99 boundary · top-1 differs · bit identical · second warmup only fails · missing output) ·
attempt folder refusal · readout (A24 formula == ours · hand-computed case · nearest-rank edges · no cross-block pairs · contract fail → Q3 기술만) ·
session dry-run.
"""
from __future__ import annotations

import base64
import json
import math
import struct
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import e2e_selftest as E  # noqa: E402
import mixreq_common as C  # noqa: E402
import mixreq_plan as P  # noqa: E402
import mixreq_readout as R  # noqa: E402
import mixreq_validate as V  # noqa: E402
import policy_ref  # noqa: E402

REPO = HERE.parents[2]


# ----------------------------------------------------------------------------------------------- fixtures: fake device dict + synthetic session
def fake_device(tmp: Path) -> dict:
    files = {"cls_model": ("efficientnet_lite0.tflite", b"cls"), "det_model": ("efficientdet_lite0.tflite", b"det"),
             "aot_model": ("efficientnet_lite0_Samsung_E9965.tflite", b"aot"), "png": ("00575b9132bb3746.png", b"png"),
             "anchors": ("anchors.json", b"[]"), "cls_labels": ("labels_without_background.txt", b"a\n"), "det_labels": ("labels.txt", b"b\n")}
    out = {}
    tmp.mkdir(parents=True, exist_ok=True)
    for key, (name, body) in files.items():
        p = tmp / name
        p.write_bytes(body)
        out[key] = dict(host_path=str(p), basename=name, bytes=len(body), sha256=C.sha256_bytes(body), device_path=f"{C.DEVICE_INPUT_DIR}/{name}")
    return out


def f32b64(values):
    return base64.b64encode(struct.pack("<%df" % len(values), *values)).decode()


def softmax_vec(shift=0.0, perturb=0.0):
    v = [0.0005 + (i % 7) * 1e-5 for i in range(1000)]
    for i, s in ((518, 0.2134), (671, 0.1125), (535, 0.0572), (870, 0.0551), (665, 0.0545)):
        v[i] = s
    return [x + shift + perturb * ((i % 3) - 1) for i, x in enumerate(v)]


def top5_results(vec):
    return [dict(label=f"cls{i}", class_index=i, score=s) for i, s in C.top5_from_softmax(vec)]


DET_RESULTS = [dict(label="person", score=0.7, box=[10.0, 20.0, 100.0, 200.0]), dict(label="bicycle", score=0.6, box=[300.0, 40.0, 80.0, 90.0])]


def synth_session(tmp: Path, policy: str, block: str, n: int = 24, scale: int = 1, mutate=None, npu_softmax=None, gpu_perturb=1e-5) -> Path:
    """Consistent synthetic artifacts for a 'diagnostic' session (selftest). mutate(ctx) may edit rows/events/warmups/etc."""
    device = fake_device(tmp / "inputs")
    index = {policy_ref.POLICY_CPU: 0 if block == "A" else 8, policy_ref.POLICY_PAR: 1, policy_ref.POLICY_PAR_NPU: 9}[policy]
    m = P.manifest(C.SMOKE_EXPERIMENT_ID, "diagnostic", index, block, policy, device, n)
    m["time_scale"] = scale
    for r in m["runtimes"]:  # the validator looks the NPU artifact up in the AOT table by SHA (the fake file is not there)
        if r["key"] == "classification_NPU":
            r["model_sha256"] = C.AOT_MODEL_SHA256
    keys = sorted(policy_ref.BLOCK_KEYS[block])
    origin = 10_000_000_000_000
    rows, events = [], []
    seq = [0]

    def ev(kind, **kw):
        phase = kw.pop("phase", "x")
        events.append(dict(kind=kind, mono_ns=origin + seq[0] * 1000, sequence=seq[0], session_id=m["session_id"], phase=phase, **kw))
        seq[0] += 1
    ev("session_start")
    for k in keys:
        ev("runtime_submit", key=k)
        ev("runtime_return", key=k)
    for k in keys:
        for i in range(2):
            ev("warmup_submit", key=k, index=i)
            ev("warmup_return", key=k, index=i)
    # warmups
    warm = []
    cpu_vec = softmax_vec()
    for k in keys:
        task, lane = k.rsplit("_", 1)
        for i in range(2):
            if task == "classification":
                vec = cpu_vec if lane == "CPU" else (npu_softmax if (lane == "NPU" and npu_softmax is not None) else softmax_vec(perturb=gpu_perturb if lane == "GPU" else 5e-4))
                res = top5_results(vec)
                warm.append(dict(key=k, index=i, result=dict(results=res, input_tensor_sha256="t" * 64, raw_output_sha256=["r" * 64]),
                                 softmax_sha256="s" * 64, softmax_f32le_base64=f32b64(vec)))
            else:
                res = [dict(r, score=r["score"] + (1e-5 if lane == "GPU" else 0.0)) for r in DET_RESULTS]
                warm.append(dict(key=k, index=i, result=dict(results=res, input_tensor_sha256="d" * 64, raw_output_sha256=["r" * 64, "q" * 64]),
                                 softmax_sha256=None, softmax_f32le_base64=None))
    # requests: serial per lane, service 100 ms classification / 300 ms detection, lanes concurrent for PAR*
    lane_free = {"CPU": origin, "GPU": origin, "NPU": origin}
    svc = {"classification": 100_000_000, "detection": 700_000_000}  # 700 ms detections make the CPU lane span the next classification -> overlap under PAR*
    results = {}
    ev("common_start", scheduled_origin_ns=origin, window_ns=int(C.COMMON_S * 1e9 / scale))
    for q in m["requests"]:
        sched = origin + int(q["offset_ms"] * 1e6 / scale)
        lane = policy_ref.lane_for(policy, q["task_id"])
        if policy == policy_ref.POLICY_CPU:
            lane = "CPU"
        start = max(sched + 200_000, lane_free[lane])
        if policy == policy_ref.POLICY_CPU:
            start = max(start, max(lane_free.values()))
        d = start
        row = dict(request_id=q["request_id"], ordinal=q["ordinal"], task_id=q["task_id"], priority=q["priority"], scheduled_arrival_ns=sched,
                   actual_arrival_ns=sched + 50_000, deadline_ns=sched + int(q["deadline_ms"] * 1e6 / scale), terminal_status="succeeded",
                   queue_entry_ns=sched + 100_000, selected_backend=lane, decision_reason=policy_ref.REASON, dispatch_ns=d, execution_start_ns=d + 10_000,
                   host_inference_start_ns=d + 400_000, host_inference_return_ns=d + svc[q["task_id"]] // 2, output_ready_ns=d + svc[q["task_id"]] // 2 + 10_000,
                   persist_complete_ns=d + svc[q["task_id"]] // 2 + 2_000_000, worker_release_ns=d + svc[q["task_id"]] // 2 + 2_100_000,
                   lane_available_ns=d + int(svc[q["task_id"]] / scale) + 2_200_000)
        lane_free[lane] = row["lane_available_ns"]
        rows.append(row)
        key = f"{q['task_id']}_{lane}"
        w = next(x for x in warm if x["key"] == key and x["index"] == 0)
        results[q["request_id"]] = dict(results=w["result"]["results"], input_tensor_sha256=w["result"]["input_tensor_sha256"], task_id=q["task_id"])
    end = origin + int(C.COMMON_S * 1e9 / scale)
    ev("common_end", common_end_ns=end)
    ev("phase_end", phase="post_window_drain")
    for i in range(12):
        ev("power_sample", plugged=0, thermal_status=0, battery_temperature_deci_c=300, battery_level=70, interactive=True, current_raw=-500000,
           current_valid=True, voltage_mV=4000, charge_counter_raw=3_000_000 - i * 100, snapshot_start_ns=origin + int(i * 10e9 / scale),
           sensor_read_end_ns=origin + int(i * 10e9 / scale) + 1000)
    ev("app_cleanup", error=None)
    ctx = dict(manifest=m, rows=rows, events=events, warm=warm, results=results, origin=origin, end=end,
               summary=dict(status="completed", planned=n, terminal=n, policy=policy, block=block, common_start_ns=origin, common_end_ns=end, time_scale=scale),
               cleanup=dict(status="completed", error=None, stop_reason=None), start_check=dict(thermal_status=0, plugged=0, passed=True),
               boundary=dict(start_ns=origin, end_ns=end, planned=n), extra_files={})
    if mutate:
        mutate(ctx)
    dev = tmp / "device"
    dev.mkdir(parents=True, exist_ok=True)
    (dev / "manifest.json").write_bytes(C.canonical_json(ctx["manifest"]))
    C.write_json(dev / "summary.json", ctx["summary"])
    C.write_json(dev / "cleanup.json", ctx["cleanup"])
    C.write_json(dev / "requests.json", ctx["rows"])
    C.write_json(dev / "common_boundary.json", ctx["boundary"])
    C.write_json(dev / "warmup.json", ctx["warm"])
    C.write_json(dev / "start_check.json", ctx["start_check"])
    with open(dev / "progress.jsonl", "w", encoding="utf-8") as f:
        for e in ctx["events"]:
            f.write(json.dumps(e) + "\n")
    for rid, res in ctx["results"].items():
        C.write_json(dev / f"{rid}.result.json", res)
    for name, content in ctx["extra_files"].items():
        (dev / name).write_text(content, encoding="utf-8")
    return dev


def validate_synth(tmp: Path, policy: str, block: str, mutate=None, variant="good", **kw):
    dev = synth_session(tmp, policy, block, mutate=mutate, **kw)
    log = tmp / "logcat.txt"
    log.write_text(E.synthetic_logcat(dev, variant), encoding="utf-8")
    return V.validate(tmp, dev, log, None, None, True)


# ----------------------------------------------------------------------------------------------- plan
def test_plan_is_deterministic_and_has_registered_order(tmp_path):
    class A:  # argparse stand-in
        pass
    args = A()
    dev = fake_device(tmp_path / "in")
    for k, (opt, exp) in {"cls_model": ("cls_model", C.CLS_MODEL_SHA256), "det_model": ("det_model", C.DET_MODEL_SHA256), "aot_model": ("aot_model", C.AOT_MODEL_SHA256),
                          "png": ("png", C.PNG_SHA256), "anchors": ("anchors", C.ANCHORS_SHA256), "cls_labels": ("cls_labels", C.CLS_LABEL_SHA256),
                          "det_labels": ("det_labels", C.DET_LABEL_SHA256)}.items():
        setattr(args, opt, Path(dev[k]["host_path"]))
    with pytest.raises(SystemExit):  # pinned SHA mismatch stops the plan (fake files)
        P.build(args)
    # with the real inputs when present: byte determinism
    real = dict(cls_model=REPO / "local_models" / "efficientnet_lite0.tflite", det_model=REPO / "local_inputs" / "public" / "efficientdet_lite0.tflite",
                aot_model=REPO / "npu-runner" / "src" / "main" / "assets" / "models" / "efficientnet_lite0_Samsung_E9965.tflite",
                png=REPO / "local_inputs" / "canonical_v123" / "00575b9132bb3746.png", anchors=REPO / "local_inputs" / "reference_pc" / "anchors.json",
                cls_labels=REPO / "local_inputs" / "reference_pc" / "labels_without_background.txt", det_labels=REPO / "local_inputs" / "reference_pc" / "labels.txt")
    if not all(p.is_file() for p in real.values()):
        pytest.skip("real inputs (git 밖) missing")
    for k, v in real.items():
        setattr(args, k, v)
    a = P.write(tmp_path / "p1", P.build(args))
    b = P.write(tmp_path / "p2", P.build(args))
    assert a == b
    assert (tmp_path / "p1" / "plan.json").read_bytes() == (tmp_path / "p2" / "plan.json").read_bytes()
    plan = C.read_json(tmp_path / "p1" / "plan.json")
    assert len(plan["sessions"]) == 16 and len(plan["smoke"]) == 4
    assert [s["policy"] for s in plan["sessions"]] == [p for _, p in C.SESSION_ORDER]
    assert [s["block"] for s in plan["sessions"]] == ["A"] * 8 + ["N"] * 8
    assert [s["pair"] for s in plan["sessions"]] == [0, 0, 1, 1, 2, 2, 3, 3] * 2
    assert plan["budget"]["calls_total"] == 3216 and plan["budget"]["smoke_calls"] == 108
    assert plan["sessions"][0]["session_id"] == "20b64aab-fe48-54ea-b5c8-476ec1972d7d"
    for s in plan["sessions"]:
        m = C.read_json(tmp_path / "p1" / s["manifest"])
        assert m["session_id"] == C.session_id(C.EXPERIMENT_ID, s["index"])
        assert [r["key"] for r in m["runtimes"]] == sorted(policy_ref.BLOCK_KEYS[s["block"]])
        C.validate_requests(m["requests"])
        assert m["requests"][0]["request_id"] == C.request_id(m["session_id"], 0)


def test_request_table_matches_kotlin_expectations():
    sid0 = C.session_id(C.EXPERIMENT_ID, 0)
    assert sid0 == "20b64aab-fe48-54ea-b5c8-476ec1972d7d"
    assert C.request_id(sid0, 0) == "aab496ba-5456-50de-8472-6ee42998c6cb"
    assert C.request_id(sid0, 191) == "538200cc-58a0-5fbd-a00b-456462c781f6"
    rows = C.requests(sid0)
    assert len(rows) == 192 and rows[-1]["offset_ms"] == 111_400
    with pytest.raises(ValueError):
        C.validate_requests([dict(r, offset_ms=r["offset_ms"] + 1) for r in rows])
    with pytest.raises(ValueError):
        C.validate_requests(rows[:-1])
    assert C.pair_of("N", 9) == 0 and C.pair_of("A", 7) == 3


# ----------------------------------------------------------------------------------------------- validate rules
@pytest.mark.parametrize("policy,block", [(policy_ref.POLICY_CPU, "A"), (policy_ref.POLICY_PAR, "A"), (policy_ref.POLICY_CPU, "N"), (policy_ref.POLICY_PAR_NPU, "N")])
def test_good_synthetic_session_is_eligible(tmp_path, policy, block):
    v, contract = validate_synth(tmp_path, policy, block)
    assert v["eligible"], v["reasons"]
    if block == "N":
        assert contract["passed"] is True
    else:
        assert contract is None


def _fail(tmp_path, policy, block, rule, mutate=None, variant="good", **kw):
    v, _ = validate_synth(tmp_path, policy, block, mutate=mutate, variant=variant, **kw)
    assert not v["eligible"]
    assert rule in v["reasons"], (rule, v["reasons"])
    return v


def test_rule0_missing_summary(tmp_path):
    def m(ctx): ctx["summary"] = dict(status="failed")
    _fail(tmp_path, policy_ref.POLICY_CPU, "A", "0_artifacts", m)


def test_rule1_failed_request_and_quality_and_tensor(tmp_path):
    def m(ctx): ctx["rows"][3]["terminal_status"] = "failed"
    _fail(tmp_path, policy_ref.POLICY_CPU, "A", "1_requests_succeeded_quality", m)

    def q(ctx):
        rid = ctx["rows"][2]["request_id"]
        ctx["results"][rid] = dict(ctx["results"][rid], results=[dict(r, score=r["score"] + 0.01) for r in ctx["results"][rid]["results"]])
    _fail(tmp_path / "q", policy_ref.POLICY_CPU, "A", "1_requests_succeeded_quality", q)

    def t(ctx):
        rid = ctx["rows"][2]["request_id"]
        ctx["results"][rid] = dict(ctx["results"][rid], input_tensor_sha256="z" * 64)
    _fail(tmp_path / "t", policy_ref.POLICY_CPU, "A", "1_requests_succeeded_quality", t)


def test_rule2_time_order(tmp_path):
    def m(ctx): ctx["rows"][5]["output_ready_ns"], ctx["rows"][5]["host_inference_return_ns"] = ctx["rows"][5]["host_inference_return_ns"] - 1, ctx["rows"][5]["output_ready_ns"]
    _fail(tmp_path, policy_ref.POLICY_PAR, "A", "2_time_order", m)


def test_rule3_window(tmp_path):
    def m(ctx): ctx["rows"][0]["dispatch_ns"] = ctx["origin"] + int(34.9e9)
    _fail(tmp_path, policy_ref.POLICY_CPU, "A", "3_window", m)

    def late(ctx): ctx["rows"][-1]["lane_available_ns"] = ctx["origin"] + int(120.0e9)
    _fail(tmp_path / "l", policy_ref.POLICY_CPU, "A", "3_window", late)


def test_rule4_assignment_and_residents(tmp_path):
    def wrong(ctx): ctx["rows"][0]["selected_backend"] = "GPU"
    _fail(tmp_path, policy_ref.POLICY_CPU, "A", "4_assignment_residents", wrong)

    def missing(ctx): ctx["events"] = [e for e in ctx["events"] if not (e["kind"] == "runtime_return" and e["key"] == "classification_NPU")]
    _fail(tmp_path / "m", policy_ref.POLICY_PAR_NPU, "N", "4_assignment_residents", missing)

    def det_gpu_exception(ctx):
        ctx["events"] = [e for e in ctx["events"] if not (e.get("key") == "detection_GPU" and e["kind"] in ("runtime_return", "warmup_return", "warmup_submit"))]
        ctx["events"].insert(3, dict(kind="runtime_create_failed", key="detection_GPU", error="x", mono_ns=0, sequence=999, session_id="s", phase="runtime_setup"))
        ctx["warm"] = [w for w in ctx["warm"] if w["key"] != "detection_GPU"]
    v, _ = validate_synth(tmp_path / "d", policy_ref.POLICY_PAR, "A", mutate=det_gpu_exception)
    assert v["eligible"], v["reasons"]
    assert any("detection_GPU" in d for d in v["a24_differences"])


def test_rule5_overlap(tmp_path):
    def serial(ctx):  # PAR without any overlap: push every GPU row after the CPU lane is idle
        t = ctx["origin"] + int(100e9)
        for r in ctx["rows"]:
            if r["selected_backend"] == "GPU":
                shift = t - r["dispatch_ns"]
                for k in ("dispatch_ns", "execution_start_ns", "host_inference_start_ns", "host_inference_return_ns", "output_ready_ns", "persist_complete_ns", "worker_release_ns", "lane_available_ns"):
                    r[k] += shift
                t = r["lane_available_ns"] + 1
    _fail(tmp_path, policy_ref.POLICY_PAR, "A", "5_overlap", serial)


def test_rule6_warmup_quality_only_for_used_keys(tmp_path):
    def gpu_bad(ctx):
        for w in ctx["warm"]:
            if w["key"] == "classification_GPU" and w["index"] == 1:
                w["result"]["results"][0]["score"] += 0.01
    _fail(tmp_path, policy_ref.POLICY_PAR, "A", "6_warmup_quality", gpu_bad)
    v, _ = validate_synth(tmp_path / "cpu", policy_ref.POLICY_CPU, "A", mutate=gpu_bad)  # GPU not used by CPU policy -> flag only
    assert v["eligible"]
    assert any("classification_GPU" in d for d in v["a24_differences"])


@pytest.mark.parametrize("policy,block,variant", [(policy_ref.POLICY_PAR, "A", "gpu_partial"), (policy_ref.POLICY_PAR, "A", "gpu_other_delegate"),
                                                  (policy_ref.POLICY_PAR_NPU, "N", "no_enn"), (policy_ref.POLICY_PAR_NPU, "N", "npu_zero"),
                                                  (policy_ref.POLICY_PAR_NPU, "N", "npu_failure")])
def test_rule7_evidence_variants_fail(tmp_path, policy, block, variant):
    v = _fail(tmp_path, policy, block, "7_delegation_evidence", variant=variant)
    assert v["reasons"] == ["7_delegation_evidence"]


def test_rule7_npu_aot_table_mismatch(tmp_path):
    def m(ctx):
        for r in ctx["manifest"]["runtimes"]:
            if r["key"] == "classification_NPU":
                r["model_sha256"] = "0" * 64
    _fail(tmp_path, policy_ref.POLICY_PAR_NPU, "N", "7_delegation_evidence", m)


def test_rule7_logcat_missing_blocks_accelerated_sessions_only(tmp_path):
    dev = synth_session(tmp_path, policy_ref.POLICY_PAR, "A")
    v, _ = V.validate(tmp_path, dev, None, None, None, True)
    assert "7_delegation_evidence" in v["reasons"]
    dev2 = synth_session(tmp_path / "cpu", policy_ref.POLICY_CPU, "A")
    v2, _ = V.validate(tmp_path / "cpu", dev2, None, None, None, True)
    assert v2["eligible"]


def test_rule8_plugged_and_start(tmp_path):
    def m(ctx): ctx["events"][-3]["plugged"] = 1
    _fail(tmp_path, policy_ref.POLICY_CPU, "A", "8_plugged_start", m)

    def s(ctx): ctx["start_check"] = dict(thermal_status=2, plugged=0, passed=False)
    _fail(tmp_path / "s", policy_ref.POLICY_CPU, "A", "8_plugged_start", s)


def test_rule9_stop_and_watch(tmp_path):
    def m(ctx): ctx["cleanup"]["stop_reason"] = "environment/plugged_1"
    _fail(tmp_path, policy_ref.POLICY_CPU, "A", "9_watch_stop", m)
    dev = synth_session(tmp_path / "w", policy_ref.POLICY_CPU, "A")
    skin = tmp_path / "skin.csv"
    skin.write_text("local_time,thermal_status,SKIN,AP,BAT,battery_level,any_powered,action\nx,0,30,30,30,70,False,FORCE_STOP_SKIN_GE_45.0\n")
    v, _ = V.validate(tmp_path / "w", dev, None, skin, None, True)
    assert "9_watch_stop" in v["reasons"]


def test_confirmation_split_never_eligible_under_selftest(tmp_path):
    def m(ctx):
        ctx["manifest"]["split"] = "confirmation"
    v, _ = validate_synth(tmp_path, policy_ref.POLICY_CPU, "A", mutate=m)
    assert not v["eligible"]


# ----------------------------------------------------------------------------------------------- NPU evidence unit (regex windows)
def test_npu_evidence_pass_and_fail_lines():
    rows = []
    sid = "s"
    n = [0]

    def add(tag, msg, pid=1):
        n[0] += 1
        rows.append(dict(line=n[0], pid=str(pid), tid="1", level="I", tag=tag, msg=msg))
    add("D1MIX", f"session_start sid={sid} x=1")
    add("litert", "SetGenAiPerfConfigFromSoc: SOC=s5e9965, mode=7")
    add("D1MIX", "runtime create_start key=classification_NPU")
    add("tflite", "Replacing 1 out of 1 node(s) with delegate (DispatchDelegate) node, yielding 1 partitions")
    add("D1MIX", "runtime create_end key=classification_NPU ok")
    add("D1MIX", "warmup_start key=classification_NPU index=0"); add("D1MIX", "warmup_end key=classification_NPU index=0 ok")
    add("D1MIX", "warmup_start key=classification_NPU index=1"); add("D1MIX", "warmup_end key=classification_NPU index=1 ok")
    add("D1MIX", "common_start origin_ns=1"); add("D1MIX", "drain_end")
    pid, marks, err = V.marks_for(rows, sid)
    assert err is None and pid == "1"
    good = V.npu_evidence(rows, pid, marks, "classification_NPU", C.AOT_MODEL_SHA256)
    assert good["verdict"] == "PASS", good
    bad = V.npu_evidence(rows, pid, marks, "classification_NPU", "f" * 64)
    assert bad["verdict"] == "FAIL" and "aot_partition_known" in bad["failed_conditions"]
    rows2 = [r for r in rows if "SetGenAiPerfConfigFromSoc" not in r["msg"]]
    assert V.npu_evidence(rows2, pid, marks, "classification_NPU", C.AOT_MODEL_SHA256)["failed_conditions"] == ["enn_loaded_in_runner_pid"]


# ----------------------------------------------------------------------------------------------- NPU contract vectors
def contract_for(npu_vecs: list[list[float]] | None, drop_npu=False, cpu=None):
    cpu = cpu or softmax_vec()
    warm = [dict(key="classification_CPU", index=i, softmax_f32le_base64=f32b64(cpu)) for i in range(2)]
    if not drop_npu:
        for i, v in enumerate(npu_vecs or []):
            warm.append(dict(key="classification_NPU", index=i, softmax_f32le_base64=f32b64(v) if v is not None else None))
    data = dict(manifest=dict(session_id="s", block="N", policy=policy_ref.POLICY_PAR_NPU), warmup=warm)
    return V.npu_contract(data)


def scaled_cos_vec(target_cos: float):
    """A vector with cosine exactly-ish target against softmax_vec(): mix with an orthogonal-ish direction."""
    base = softmax_vec()
    other = [1.0 if i % 2 == 0 else 0.0 for i in range(1000)]
    # Gram-Schmidt to make `other` orthogonal to base, then combine
    dot = sum(a * b for a, b in zip(base, other)) / sum(a * a for a in base)
    orth = [o - dot * b for o, b in zip(other, base)]
    nb = math.sqrt(sum(b * b for b in base)); no = math.sqrt(sum(o * o for o in orth))
    s = math.sqrt(1 - target_cos ** 2) / target_cos * nb / no
    return [b + s * o for b, o in zip(base, orth)]


def test_npu_contract_boundaries():
    exact = scaled_cos_vec(0.99)
    c = contract_for([exact, exact])
    assert abs(c["warmups"][0]["cosine"] - 0.99) < 1e-9
    below = scaled_cos_vec(0.9899)
    assert contract_for([below, below])["passed"] is False
    above = scaled_cos_vec(0.995)
    assert contract_for([above, above])["passed"] is True
    near_tie = softmax_vec()
    near_tie[671] = 0.2133  # CPU reference with a near tie 518 (0.2134) vs 671
    swapped = list(near_tie)
    swapped[671] = 0.2135  # top-1 becomes 671 while cosine stays ~1: the contract fails on top-1 alone (AND of the two conditions)
    r = contract_for([swapped, swapped], cpu=near_tie)
    assert r["passed"] is False and r["warmups"][0]["top1_equal"] is False and r["warmups"][0]["cosine"] > 0.99
    ident = contract_for([softmax_vec(), softmax_vec()])
    assert ident["passed"] is True and ident["warmups"][0]["bit_identical_to_cpu"] is True
    second_only = contract_for([above, below])
    assert second_only["passed"] is False and second_only["warmups"][0]["passed"] and not second_only["warmups"][1]["passed"]
    assert contract_for([above, None])["passed"] is False
    assert contract_for(None, drop_npu=True)["passed"] is False
    assert contract_for([above])["passed"] is False  # one warmup only


# ----------------------------------------------------------------------------------------------- readout
def test_a24_formula_equals_ours_and_hand_case(tmp_path):
    dev = synth_session(tmp_path, policy_ref.POLICY_PAR, "A")
    rows = C.read_json(dev / "requests.json"); m = C.read_json(dev / "manifest.json")
    a24 = R.a24_service_formula(rows, m["requests"]); ours = R.our_service(rows, m["requests"])
    for cls in ("urgent", "normal", "all"):
        assert a24["actual_" + cls]["p95_ms"] == ours[cls]["p95_ms"]
        assert a24["actual_" + cls]["deadline_met"] == ours[cls]["deadline_met"]
    # hand case: 10 planned, 9 completed -> nearest rank ceil(9.5)=10 -> the +inf slot
    assert C.nearest_rank_p95([1, 2, 3, 4, 5, 6, 7, 8, 9], 10) == math.inf
    assert C.nearest_rank_p95(list(range(1, 21)), 20) == 19   # ceil(19)=19 -> sorted[18] = 19
    assert C.nearest_rank_p95([7.0], 1) == 7.0
    assert C.nearest_rank_p95([5.0] * 96, 96) == 5.0
    assert C.nearest_rank_p95([], 0) is None


def test_pairs_never_cross_blocks_and_contract_failure_makes_q3_descriptive():
    def sess(index, block, policy, eligible=True, p95=400.0, contract=True):
        return dict(index=index, block=block, pair=C.pair_of(block, index), policy=policy, attempt=1, eligible=eligible,
                    service=dict(urgent=dict(p95_ms=p95, planned=96, deadline_met=96), normal=dict(p95_ms=900.0, planned=96, deadline_met=96),
                                 all=dict(planned=192, deadline_met=192)), thermal=None, energy=None,
                    contract=dict(passed=contract) if block == "N" and policy == policy_ref.POLICY_PAR_NPU else None)
    sessions = [sess(0, "A", policy_ref.POLICY_CPU), sess(1, "A", policy_ref.POLICY_PAR, p95=300.0),
                sess(8, "N", policy_ref.POLICY_CPU), sess(9, "N", policy_ref.POLICY_PAR_NPU, p95=250.0, contract=False)]
    a = R.judge_block("A", sessions)
    assert a["n"] == 1 and a["pairs"][0]["cpu_index"] == 0 and a["pairs"][0]["par_index"] == 1
    assert a["judgment"] == "쌍 부족 — 기술만"
    n = R.judge_block("N", sessions)
    assert n["n"] == 1 and n["judgment"].startswith("NPU 출력 계약 실패")
    # three pairs, all faster by >= 5 % -> direction judgment
    many = [sess(0, "A", policy_ref.POLICY_CPU), sess(1, "A", policy_ref.POLICY_PAR, p95=300.0), sess(2, "A", policy_ref.POLICY_PAR, p95=310.0),
            sess(3, "A", policy_ref.POLICY_CPU, p95=410.0), sess(4, "A", policy_ref.POLICY_PAR, p95=290.0), sess(5, "A", policy_ref.POLICY_CPU, p95=420.0)]
    j = R.judge_block("A", many)
    assert j["n"] == 3 and j["urgent_judgment"] == "병행이 긴급 응답을 줄였다"
    assert j["thermal_skin_judgment"] == "열 자료 없음"
    mixed = many + [sess(6, "A", policy_ref.POLICY_CPU, p95=300.0), sess(7, "A", policy_ref.POLICY_PAR, p95=350.0)]
    assert R.judge_block("A", mixed)["urgent_judgment"] == "엇갈림"


def test_energy_cross_check_matches_vendor(tmp_path):
    dev = synth_session(tmp_path, policy_ref.POLICY_CPU, "A")
    events = [json.loads(l) for l in (dev / "progress.jsonl").read_text().splitlines()]
    boundary = C.read_json(dev / "common_boundary.json")
    e = R.energy_block(events, boundary["start_ns"], 1)
    assert e["a24_integrate"]["covered_energy_j"] == pytest.approx(e["ours"]["covered_energy_j"])
    assert e["a24_integrate"]["unit_hypothesis_ua_per_raw"] == 1


# ----------------------------------------------------------------------------------------------- session dry-run / attempt refusal
def test_session_dry_run_and_attempt_folder_refusal(tmp_path):
    plan_dir = REPO / "s26" / "results" / "mixreq_1008" / "plan_v1"
    if not (plan_dir / "plan.json").is_file():
        pytest.skip("plan_v1 missing")
    results = tmp_path / "results"
    cmd = [sys.executable, "-X", "utf8", str(HERE / "mixreq_session.py"), "--plan", str(plan_dir), "--index", "1", "--results", str(results), "--dry-run", "--skip-gate"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env={**__import__("os").environ, "ANDROID_SERIAL": ""})
    assert r.returncode == 0, r.stdout + r.stderr
    folder = results / "S26_MIXREQ_01_B2_PARALLEL_ONLINE_V1_a1"
    log = C.read_json(folder / "host" / "session_log.json")
    cmds = " || ".join(c["cmd"] for c in log["commands"])
    assert "am start -W -n com.example.d1check.requestrunner/.SessionActivity" in cmds
    assert "logcat" not in cmds or "-c" in cmds  # dry-run prints, never records a serial
    assert "<SERIAL>" not in str(folder) and "npurunner" not in cmds
    r2 = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r2.returncode == 5  # same attempt folder exists -> refuse
