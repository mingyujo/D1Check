"""M6 host tests (pytest, no phone): request table determinism · L / B formulas (= Kotlin M6PlanTest uuid5) · projection SHA (three rules
equal per load) · V2 boundary (119.999 s passes / 120.000 s fails) · K manifests (requests 0 · 780 s · block M) · plan determinism ·
existing tables unchanged · m6_validate on the PC round-trip artifacts (request-runner/build/m6-roundtrip, from M6RoundTripTest) ·
GaugeDiag output form (request-runner/build/m6-gauge, from GaugeDiagTest) · m6_readout on the round trip.

  py -3 -m pytest -q s26/tools/mixreq/test_m6.py
"""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402
import policy_ref  # noqa: E402

BEFORE = {k: dict(v) for k, v in C.EXPERIMENTS.items()}
BEFORE_KEYS = {k: tuple(v) for k, v in policy_ref.BLOCK_KEYS.items()}
BEFORE_POL = {k: tuple(v) for k, v in policy_ref.BLOCK_POLICIES.items()}
BEFORE_PHASES = {k: dict(v) for k, v in C.PHASES.items()}
import m6_common as M  # noqa: E402
import m6_validate as MV  # noqa: E402
import e2e_selftest as E  # noqa: E402

PLAN_P = REPO / "s26" / "results" / "m6_1012" / "plan_m6p"
PLAN_K = REPO / "s26" / "results" / "m6_1012" / "plan_m6k"
PLAN_E = REPO / "s26" / "results" / "m6_1012" / "plan_m6e"
PLAN_SS = REPO / "s26" / "results" / "statesplit_1012" / "plan_v4ss"
ROUNDTRIP = REPO / "request-runner" / "build" / "m6-roundtrip"
GAUGE = REPO / "request-runner" / "build" / "m6-gauge"
SAME_KEYS = ("protocol", "anchors", "image", "labels", "runtimes", "start_check", "stop_rules", "warmup_gate", "sample_period_ms", "time_scale", "attempt")


def test_existing_rows_unchanged_and_m6_rows_added():
    for k, v in BEFORE.items():
        assert C.EXPERIMENTS[k] == v
    for k, v in BEFORE_KEYS.items():
        assert tuple(policy_ref.BLOCK_KEYS[k]) == v
    for k, v in BEFORE_POL.items():
        assert tuple(policy_ref.BLOCK_POLICIES[k]) == v
    for k, v in BEFORE_PHASES.items():
        assert C.PHASES[k] == v
    assert C.request_count_of(M.P_ID) == 100 and C.common_s_of(M.P_SMOKE_ID) == 120
    assert C.request_count_of(M.K_ID) == 0 and C.common_s_of(M.K_SMOKE_ID) == 780
    assert C.session_cap_s(M.K_ID, "M") == 180 + 60 + 30 + 780 + 30 + 60 + 240
    assert C.session_cap_s(M.P_ID, "M") == 180 + 60 + 30 + 120 + 30 + 60 + 240
    assert C.listing_period_s(M.P_ID) == 1.0 and C.listing_period_s(M.K_ID) == 1.0
    assert set(policy_ref.BLOCK_KEYS["M"]) == set(policy_ref.BLOCK_KEYS["N"]) and len(policy_ref.BLOCK_KEYS["M"]) == 5
    assert set(policy_ref.BLOCK_POLICIES["M"]) == set(policy_ref.POLICIES)
    assert C.PHASES["M"] == C.PHASES["N"]


def test_requests_match_registration_and_kotlin():
    sid = M.session_id(M.P_ID, 0)
    assert sid == "89f44a8e-c543-5ac1-a184-9c2c3624cc38"   # = M6PlanTest (Kotlin)
    assert M.session_id(M.K_SMOKE_ID, 0) == "3ec2bf32-bc1e-515e-bbed-358c58db8652"
    rows = M.requests(M.P_ID, 0, sid)
    assert rows[0]["request_id"] == "064a4c21-eafc-5711-a279-fd638f01800e" and rows[-1]["request_id"] == "8df6aeef-4cdf-5e0a-a330-231cca2d50f0"
    L = M.load_requests(sid, "L")
    assert [r["offset_ms"] for r in L] == [35_000 + 400 * i for i in range(100)]
    assert all((r["ordinal"] % 2 == 0) == (r["task_id"] == "classification") for r in L)
    B = M.load_requests(sid, "B")
    assert [r["offset_ms"] for r in B] == [35_000 + 4_000 * k + 50 * j for k in range(10) for j in range(10)]
    assert B[-1]["offset_ms"] == 71_450 and L[-1]["offset_ms"] == 74_600
    assert all(((r["ordinal"] % 10) % 2 == 0) == (r["task_id"] == "classification") for r in B)
    for rows in (L, B):
        assert sum(r["task_id"] == "classification" for r in rows) == 50
        assert all(r["priority"] == ("urgent" if r["task_id"] == "classification" else "normal") for r in rows)
        assert all(r["deadline_ms"] == (1500 if r["task_id"] == "classification" else 6000) for r in rows)
    assert M.load_requests(sid, "L") == L   # deterministic
    bad = copy.deepcopy(L)
    bad[3]["offset_ms"] += 1
    with pytest.raises(ValueError):
        M.validate_load(bad, "L")
    with pytest.raises(ValueError):
        M.validate_load(L, "B")
    assert M.requests(M.K_ID, 2, M.session_id(M.K_ID, 2)) == []


def test_order_and_projection_sha():
    assert M.P_ORDER[:6] == ("L-C", "B-G", "L-N", "B-C", "L-G", "B-N")
    assert M.P_ORDER[6:] == tuple(reversed(M.P_ORDER[:6]))
    plan = C.read_json(PLAN_P / "plan.json")
    for load in ("L", "B"):
        shas = {M.projection_sha256(M.requests(M.P_ID, i, M.session_id(M.P_ID, i))) for i in range(12) if M.load_of(i) == load}
        assert len(shas) == 1
        assert plan["projection"][load]["equal"] is True and plan["projection"][load]["sha256"] == shas.pop()
    assert plan["projection"]["L"]["sha256"] != plan["projection"]["B"]["sha256"]
    # request ids differ between rules (uuid5 of each session id) while the projection is the same
    a = M.requests(M.P_ID, 0, M.session_id(M.P_ID, 0))
    b = M.requests(M.P_ID, 2, M.session_id(M.P_ID, 2))
    assert M.projection(a) == M.projection(b) and a[0]["request_id"] != b[0]["request_id"]


def test_plan_manifests():
    plan = C.read_json(PLAN_P / "plan.json")
    assert [f"{s['load']}-{s['letter']}" for s in plan["sessions"]] == list(M.P_ORDER)
    assert [s["analysis_split"] for s in plan["sessions"]] == ["dev"] * 6 + ["confirm"] * 6
    assert plan["execution"]["m6a"] == ["K0", "K1", "P0", "P1", "P2", "P3", "P4", "P5"]
    ss = C.read_json(PLAN_SS / "plan.json")
    ref = C.read_json(PLAN_SS / ss["sessions"][2]["manifest"])   # an M5 block-N manifest (5 keys) for the shared keys
    for e in plan["sessions"] + plan["smoke"]:
        m = C.read_json(PLAN_P / e["manifest"])
        assert C.sha256_bytes(C.canonical_json(m)) == e["manifest_sha256"]
        assert m["block"] == "M" and m["policy"] == M.LETTER_POLICY[e["letter"]]
        for k in SAME_KEYS:
            assert m[k] == ref[k], (e["manifest"], k)
        assert m["phases"] == dict(ref["phases"], common_s=120) and m["phases"]["setup_s"] == 180
        assert m["requests"] == M.requests(m["experiment_id"], m["session_index"], m["session_id"])
        assert m["used_keys"] == list(policy_ref.USED_KEYS[m["policy"]])
        assert m["registration"]["sha256"] == M.REGISTRATION["sha256"]
    smoke = C.read_json(PLAN_P / plan["smoke"][0]["manifest"])
    assert smoke["split"] == "diagnostic" and smoke["experiment_id"] == M.P_SMOKE_ID and smoke["session_index"] == 3
    assert smoke["policy"] == policy_ref.POLICY_CPU and smoke["m6_load"] == "B" and smoke["time_scale"] == 1 and len(smoke["requests"]) == 100


def test_k_manifests():
    plan = C.read_json(PLAN_K / "plan.json")
    assert [s["analysis_split"] for s in plan["sessions"]] == ["dev", "dev", "confirm", "confirm"]
    for e in plan["sessions"] + plan["smoke"]:
        m = C.read_json(PLAN_K / e["manifest"])
        assert m["requests"] == [] and m["phases"]["common_s"] == 780 and m["phases"]["setup_s"] == 180
        assert m["block"] == "M" and m["policy"] == policy_ref.POLICY_CPU and len(m["runtimes"]) == 5
    smoke = C.read_json(PLAN_K / plan["smoke"][0]["manifest"])
    assert smoke["split"] == "diagnostic" and smoke["time_scale"] == M.K_SMOKE_TIME_SCALE and smoke["experiment_id"] == M.K_SMOKE_ID
    for e in plan["sessions"]:
        m = C.read_json(PLAN_K / e["manifest"])
        assert m["split"] == "confirmation" and m["time_scale"] == 1


def test_gauge_configs():
    plan = C.read_json(PLAN_E / "plan.json")
    assert plan["order"] == ["E1", "E2", "E3", "ET"]
    for r in plan["runs"]:
        c = C.read_json(PLAN_E / r["config"])
        assert c["experiment_id"] == M.E_ID and (c["idle_ms"], c["load_ms"], c["rest_ms"], c["poll_target_ms"]) == (60_000, 120_000, 120_000, 20)
        assert c["model"]["path"].endswith("/efficientnet_lite0.tflite") and c["run_id"] == r["run_id"]
    s = C.read_json(PLAN_E / plan["smoke"][0]["config"])
    assert s["experiment_id"] == M.E_SMOKE_ID and s["idle_ms"] + s["load_ms"] + s["rest_ms"] == 30_000
    assert "thermal_zone" in plan["et_device_loop"] and "/proc/uptime" in plan["et_device_loop"]


def test_v2_boundary():
    origin = 1_000_000_000_000
    def case(last_s: float, null_last: bool = False, scale: int = 1):
        rows = [dict(request_id=f"r{i}", lane_available_ns=origin + int((40 + i * 0.1) * 1e9 / scale)) for i in range(100)]
        if null_last:
            rows[-1]["lane_available_ns"] = None
        events = [dict(kind="lane_available", mono_ns=r["lane_available_ns"] or origin + int(121e9 / scale)) for r in rows]
        events[-1]["mono_ns"] = origin + round(last_s * 1e9 / scale)
        return MV.v2(dict(start_ns=origin, rows=rows), events, 100, scale)
    assert case(119.999)["passed"] is True
    assert case(120.000)["passed"] is False
    assert case(120.001)["passed"] is False
    assert case(119.999, null_last=True)["passed"] is False          # null in common_boundary
    assert case(119.999, scale=4)["passed"] is True and case(120.0, scale=4)["passed"] is False
    assert case(119.999)["detail"]["last_lane_available_s"] == pytest.approx(119.999)
    short = MV.v2(dict(start_ns=origin, rows=[]), [], 100, 1)
    assert short["passed"] is False


def test_plans_are_deterministic(tmp_path):
    aot = REPO / "npu-runner/src/main/assets/models/efficientnet_lite0_Samsung_E9965.tflite"
    if not aot.is_file():
        pytest.skip("AOT artifact missing (git 밖)")
    args = ["--cls-model", "local_models/efficientnet_lite0.tflite", "--det-model", "local_inputs/public/efficientdet_lite0.tflite",
            "--aot-model", "npu-runner/src/main/assets/models/efficientnet_lite0_Samsung_E9965.tflite",
            "--png", "local_inputs/canonical_v123/00575b9132bb3746.png", "--anchors", "local_inputs/reference_pc/anchors.json",
            "--cls-labels", "local_inputs/reference_pc/labels_without_background.txt", "--det-labels", "local_inputs/reference_pc/labels.txt"]
    subprocess.run([sys.executable, "-X", "utf8", str(HERE / "m6_plan.py"), "--out-root", str(tmp_path), *args], cwd=REPO, check=True, capture_output=True)
    for name, ref in (("plan_m6p", PLAN_P), ("plan_m6k", PLAN_K), ("plan_m6e", PLAN_E)):
        a = tmp_path / name
        files = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
        assert files == sorted(p.relative_to(ref) for p in ref.rglob("*") if p.is_file())
        for f in files:
            assert (a / f).read_bytes() == (ref / f).read_bytes(), f


def _session(case: str, tmp_path: Path) -> tuple[Path, Path]:
    device = ROUNDTRIP / case / "a1"
    if not (device / "manifest.json").is_file():
        pytest.skip("run gradlew :request-runner:testDebugUnitTest (M6RoundTripTest) first")
    out = tmp_path / case
    (out / "host").mkdir(parents=True)
    log = out / "host" / "logcat_threadtime.txt"
    log.write_text(E.synthetic_logcat(device), encoding="utf-8")
    return out, device


@pytest.mark.parametrize("case", ["B-C", "L-G", "B-N"])
def test_roundtrip_policy_sessions_validate(case, tmp_path):
    out, device = _session(case, tmp_path)
    validated, contract = MV.validate(out, device, out / "host" / "logcat_threadtime.txt", None, None, True)
    assert validated["eligible"], validated["reasons"]
    assert set(validated["rules"]) == {"V1_dispatch_terminal", "V2_all_available_by_120s", "V3_samples_drain", "V4_overlap_npu", "V5_safety"}
    assert validated["rules"]["V1_dispatch_terminal"]["detail"]["succeeded"] == 100
    assert contract is not None and contract.get("passed") is True   # NPU resident in block M for every rule
    shutil.copytree(device, out / "device")
    validated["device_dir"] = str(out / "device")
    C.write_json(out / "validated.json", validated)
    import mixreq_readout as R
    s = R.read_session(out, True)
    assert s["service"]["all"]["planned"] == 100 and s["service"]["all"]["completed"] == 100


def test_roundtrip_cooling_validates_and_v2_tamper(tmp_path):
    out, device = _session("K", tmp_path)
    validated, _ = MV.validate(out, device, None, None, None, True)
    assert set(validated["rules"]) == {"K1_requests_zero", "K2_phases", "K3_samples"}
    assert validated["eligible"], (validated["reasons"], validated["rules"])
    assert validated["rules"]["K2_phases"]["detail"]["window_s"] >= 780.0
    # a P session whose last lane_available is moved to exactly 120.000 s (scaled) fails V2 only
    out2, dev2 = _session("B-C", tmp_path / "t")
    work = tmp_path / "tampered"
    shutil.copytree(dev2, work)
    origin = C.read_json(work / "common_boundary.json")["start_ns"]
    scale = C.read_json(work / "manifest.json")["time_scale"]
    lines = (work / "progress.jsonl").read_text(encoding="utf-8").splitlines()
    idx = max(i for i, l in enumerate(lines) if '"kind":"lane_available"' in l.replace(" ", ""))
    ev = json.loads(lines[idx])
    for at, expect in ((origin + int(119.999e9 / scale), True), (origin + int(120e9 / scale), False)):
        ev["mono_ns"] = at
        lines[idx] = json.dumps(ev)
        (work / "progress.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        v, _ = MV.validate(out2, work, out2 / "host" / "logcat_threadtime.txt", None, None, True)
        assert v["rules"]["V2_all_available_by_120s"]["passed"] is expect


def test_gauge_output_form():
    d = GAUGE / "ok"
    if not (d / "summary.json").is_file():
        pytest.skip("run gradlew :request-runner:testDebugUnitTest (GaugeDiagTest) first")
    summary = C.read_json(d / "summary.json")
    header = C.read_json(d / "header.json")
    assert summary["schema"] == header["schema"] == "s26-m6-gauge-diag-v1" and summary["status"] == "completed"
    samples = [json.loads(l) for l in (d / "samples.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    for s in samples:
        for k in ("seq", "phase", "t0", "t1", "current_now", "t_current_now", "current_avg", "charge_counter", "energy_counter", "sticky", "t_sticky"):
            assert k in s, k
    markers = [json.loads(l)["marker"] for l in (d / "markers.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    assert markers == ["setup_start", "warmup", "warmup", "idle_start", "idle_end", "load_start", "load_end", "rest_start", "rest_end"]
    assert summary["polls"] == len(samples) and summary["poll_interval_ns"]["median"] is not None
