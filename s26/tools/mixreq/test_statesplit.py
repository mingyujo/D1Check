"""M5 host tests (pytest, no phone): request derivation · plan (keys equal to the R3/R4 manifests except the request table) · ABBA changed keys ·
determinism · M5 table rows do not change the existing table · statesplit_validate on the PC round-trip artifacts
(request-runner/build/statesplit-roundtrip, from StatesplitRoundTripTest) · statesplit_readout on them.

  py -3 -m pytest -q s26/tools/mixreq/test_statesplit.py
"""
from __future__ import annotations

import copy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402

BEFORE = {k: dict(v) for k, v in C.EXPERIMENTS.items()}
import statesplit_common as S  # noqa: E402
import statesplit_validate as SV  # noqa: E402
import e2e_selftest as E  # noqa: E402
import policy_ref  # noqa: E402

PLAN = REPO / "s26" / "results" / "statesplit_1012" / "plan_v4ss"
ABBA = REPO / "s26" / "results" / "statesplit_1012" / "plan_abba"
V3C = REPO / "s26" / "results" / "mixreq_1008" / "plan_v3c"
V3S = REPO / "s26" / "results" / "mixreq_1008" / "plan_v3s"
ROUNDTRIP = REPO / "request-runner" / "build" / "statesplit-roundtrip"
SAME_KEYS = ("protocol", "anchors", "image", "labels", "phases", "runtimes", "start_check", "stop_rules", "used_keys", "warmup_gate", "sample_period_ms",
             "time_scale", "block", "policy", "attempt")


def test_existing_rows_unchanged_and_m5_rows_added():
    for k, v in BEFORE.items():
        assert C.EXPERIMENTS[k] == v
    assert C.request_count_of(S.STATESPLIT_ID) == 522 and C.common_s_of(S.STATESPLIT_ID) == 120
    assert C.request_count_of(S.ABBA_SMOKE_ID) == 3000 and C.common_s_of(S.ABBA_ID) == 720
    assert C.experiment_kind(S.ABBA_ID) == "sustained" and C.experiment_kind(S.STATESPLIT_ID) == "statesplit"
    assert C.session_cap_s(S.STATESPLIT_ID, "N") == 180 + 60 + 30 + 120 + 30 + 60 + 240
    assert C.listing_period_s(S.STATESPLIT_ID) == 1.0 and C.listing_period_s(S.ABBA_ID) == 3.0


def test_requests_match_registration_and_kotlin():
    sid = S.session_id(S.STATESPLIT_ID, 0)
    assert sid == "1474672c-faec-564d-8c0c-7ecb75f31227"   # = StatesplitPlanTest (Kotlin)
    rows = S.requests(sid)
    assert len(rows) == 522
    assert rows[0]["request_id"] == "8996b6cd-5924-59ba-9aaf-c5f2d9c5a333" and rows[-1]["request_id"] == "ab3f776b-7730-520b-838b-3f81fef2899f"
    seg = {}
    for r in rows:
        seg.setdefault((S.segment_of(r["offset_ms"]), r["task_id"]), []).append(r["offset_ms"])
    assert {k: len(v) for k, v in seg.items()} == {("S1", "classification"): 250, ("S2", "detection"): 84, ("S3", "classification"): 125, ("S3", "detection"): 63}
    assert max(r["offset_ms"] for r in rows) == 119_900
    assert all(r["deadline_ms"] == (1500 if r["task_id"] == "classification" else 6000) for r in rows)
    bad = copy.deepcopy(rows)
    bad[5]["offset_ms"] += 1
    with pytest.raises(ValueError):
        S.validate_requests(bad)


def test_plan_manifests_keep_the_r4_keys():
    plan = C.read_json(PLAN / "plan.json")
    assert [s["letter"] for s in plan["sessions"]] == list("CGNNGCCGNNGC")
    assert [s["analysis_split"] for s in plan["sessions"]] == ["dev"] * 6 + ["confirm"] * 6
    assert [s["statesplit_block"] for s in plan["sessions"]] == [1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4]
    v3c = C.read_json(V3C / "plan.json")
    ref = {}
    for e in v3c["sessions"]:
        ref.setdefault((e["block"], e["policy"]), C.read_json(V3C / e["manifest"]))
    for e in plan["sessions"] + plan["smoke"]:
        m = C.read_json(PLAN / e["manifest"])
        assert C.sha256_bytes(C.canonical_json(m)) == e["manifest_sha256"]
        r = ref[(m["block"], m["policy"])]
        for k in SAME_KEYS:
            assert m[k] == r[k], (e["manifest"], k)
        assert m["requests"] == S.requests(m["session_id"])
        assert m["session_id"] == S.session_id(m["experiment_id"], m["session_index"])
        assert m["registration"]["sha256"] == S.REGISTRATION_SS["sha256"]
    smoke = C.read_json(PLAN / plan["smoke"][0]["manifest"])
    assert smoke["split"] == "diagnostic" and smoke["experiment_id"] == S.STATESPLIT_SMOKE_ID and smoke["policy"] == policy_ref.POLICY_CPU


def test_abba_only_changed_keys():
    plan = C.read_json(ABBA / "plan.json")
    assert plan["order"] == ["A", "B", "B", "A"]
    assert [s["policy"] for s in plan["sessions"]] == [policy_ref.POLICY_CPU, policy_ref.POLICY_PAR, policy_ref.POLICY_PAR, policy_ref.POLICY_CPU]
    for e in plan["sessions"]:
        m = C.read_json(ABBA / e["manifest"])
        src = C.read_json(V3S / e["source"]["manifest"])
        assert m["session_id"] == S.session_id(S.ABBA_ID, e["index"]) and m["session_index"] == e["index"] and m["experiment_id"] == S.ABBA_ID
        diff = sorted(k for k in set(m) | set(src) if m.get(k) != src.get(k))
        assert diff == sorted(["experiment_id", "session_id", "session_index", "pair", "requests"]) or diff == sorted(["experiment_id", "session_id", "requests"]) \
            or set(diff) <= {"experiment_id", "session_id", "session_index", "pair", "requests"}
        assert [(q["ordinal"], q["task_id"], q["offset_ms"], q["deadline_ms"], q["priority"]) for q in m["requests"]] == \
               [(q["ordinal"], q["task_id"], q["offset_ms"], q["deadline_ms"], q["priority"]) for q in src["requests"]]
        assert m["phases"]["common_s"] == 720 and len(m["requests"]) == 3000


def test_plans_are_deterministic(tmp_path):
    args = ["--cls-model", "local_models/efficientnet_lite0.tflite", "--det-model", "local_inputs/public/efficientdet_lite0.tflite",
            "--aot-model", "npu-runner/src/main/assets/models/efficientnet_lite0_Samsung_E9965.tflite",
            "--png", "local_inputs/canonical_v123/00575b9132bb3746.png", "--anchors", "local_inputs/reference_pc/anchors.json",
            "--cls-labels", "local_inputs/reference_pc/labels_without_background.txt", "--det-labels", "local_inputs/reference_pc/labels.txt"]
    if not (REPO / "npu-runner/src/main/assets/models/efficientnet_lite0_Samsung_E9965.tflite").is_file():
        pytest.skip("AOT artifact missing (git 밖)")
    subprocess.run([sys.executable, "-X", "utf8", str(HERE / "statesplit_plan.py"), "statesplit", "--out", str(tmp_path / "ss"), *args], cwd=REPO, check=True, capture_output=True)
    subprocess.run([sys.executable, "-X", "utf8", str(HERE / "statesplit_plan.py"), "abba", "--out", str(tmp_path / "ab"), "--source", str(V3S),
                    "--device-inputs", str(PLAN / "device_inputs.json")], cwd=REPO, check=True, capture_output=True)
    for a, b in ((tmp_path / "ss", PLAN), (tmp_path / "ab", ABBA)):
        files = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
        assert files == sorted(p.relative_to(b) for p in b.rglob("*") if p.is_file())
        for f in files:
            assert (a / f).read_bytes() == (b / f).read_bytes(), f


@pytest.mark.parametrize("case", ["C", "G", "N"])
def test_roundtrip_artifacts_validate(case, tmp_path):
    device = ROUNDTRIP / case / "a1"
    if not (device / "manifest.json").is_file():
        pytest.skip("run gradlew :request-runner:testDebugUnitTest (StatesplitRoundTripTest) first")
    out = tmp_path / case
    (out / "host").mkdir(parents=True)
    log = out / "host" / "logcat_threadtime.txt"
    log.write_text(E.synthetic_logcat(device), encoding="utf-8")
    validated, contract = SV.validate(out, device, log, None, None, True)
    assert validated["rules"]["3_window"]["passed"], validated["rules"]["3_window"]
    assert validated["rules"]["3_window"]["detail"]["request_table_matches_statesplit"]
    assert validated["eligible"], validated["reasons"]
    assert validated["counts"]["succeeded"] == 522
    if case == "N":
        assert contract is not None and contract.get("passed") is True
    # readout (no judgment): read_session works on the 522-request session
    C.write_json(out / "validated.json", validated)
    shutil.copytree(device, out / "device")
    validated["device_dir"] = str(out / "device")
    C.write_json(out / "validated.json", validated)
    import mixreq_readout as R
    s = R.read_session(out, True)
    assert s["service"]["all"]["planned"] == 522 and s["service"]["all"]["completed"] == 522


def test_rule3_replacement_only_for_statesplit(tmp_path):
    device = ROUNDTRIP / "C" / "a1"
    if not (device / "manifest.json").is_file():
        pytest.skip("round-trip artifacts missing")
    out = tmp_path / "x"
    (out / "host").mkdir(parents=True)
    log = out / "host" / "logcat_threadtime.txt"
    log.write_text(E.synthetic_logcat(device), encoding="utf-8")
    validated, _ = SV.validate(out, device, log, None, None, True)
    d = validated["rules"]["3_window"]["detail"]
    assert d["bounds_s"] == [S.WINDOW_S[0] / 4, S.WINDOW_S[1] / 4]   # time_scale 4 in the round trip
    assert d["mixreq_rule3_result"]["bounds_s"] == [35 / 4, 120 / 4]
