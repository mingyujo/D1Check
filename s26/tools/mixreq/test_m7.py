"""M7 host tests (pytest, no phone): tables = 등록 §1-5 · §2-3 · §4-4 verbatim · index 자리 (P 12.. · prep 42.. · K 4.. · S 16..) · 라틴 방진 · 정책 자리 균형 ·
projection SHA (all P/prep rows = registered L / B) · plan files (counts · manifests · K columns = M6 K · S form = R4 (S)) · m6 tables untouched without m7 import ·
slope / gap / coverage helpers · field_map keys · hal_cont CSV parse · plan determinism.

  py -3 -m pytest -q s26/tools/mixreq/test_m7.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import m7_common as M7  # noqa: E402
import mixreq_common as C  # noqa: E402
import policy_ref  # noqa: E402
import m6_common as M  # noqa: E402
import m7_table as T  # noqa: E402
import m7_driver as D  # noqa: E402

ROOT = REPO / "s26" / "results" / "m7_1013"
PLAN_P, PLAN_PREP, PLAN_K, PLAN_S = (ROOT / n for n in ("plan_m7p", "plan_m7prep", "plan_m7k", "plan_m7s"))
PLAN_M6K = REPO / "s26" / "results" / "m6_1012" / "plan_m6k"
PLAN_V3S = REPO / "s26" / "results" / "mixreq_1008" / "plan_v3s"
REG_L = "ad29e8196e3f96a018d0f4483b9c14a2eab1150b6e670a4ccfb685d4364f39c6"
REG_B = "9fc5ef9f5afc2fba46ad9c5b26a4d2c65e0b2a1c87a09a07b175e5f21e954c0b"


def test_tables_verbatim_from_registration():
    assert M7.P_BLOCKS["D1"] == ("L-C", "B-C", "L-G", "B-G", "L-N", "B-N")
    assert M7.P_BLOCKS["D2"] == ("B-G", "L-G", "B-N", "L-N", "B-C", "L-C")
    assert M7.P_BLOCKS["D3"] == ("L-N", "B-N", "L-C", "B-C", "L-G", "B-G")
    assert M7.P_BLOCKS["K1"] == ("B-C", "L-C", "B-N", "L-N", "B-G", "L-G")
    assert M7.P_BLOCKS["K2"] == ("L-G", "B-G", "L-C", "B-C", "L-N", "B-N")
    assert M7.K_SETS == {1: "ABC", 2: "BCA", 3: "CAB", 4: "ACB", 5: "BAC"}
    assert M7.S_ORDER == ("C", "G", "N", "N", "G", "C", "G", "C", "N", "N", "C", "G")
    assert M7.latin_square_ok(M7.K_SETS) and not M7.latin_square_ok({1: "ABC", 2: "ABC", 3: "CAB", 4: "ACB", 5: "BAC"})
    assert M7.p_positions_ok(M7.P_BLOCKS) and not M7.p_positions_ok(dict(M7.P_BLOCKS, D2=M7.P_BLOCKS["D1"]))
    # index 자리 (등록 v2 머리 단락): M6 · R4 자리 뒤
    assert [M7.p_index("D1", 0), M7.p_index("D2", 0), M7.p_index("D3", 0), M7.p_index("K1", 0), M7.p_index("K2", 5)] == [12, 18, 24, 30, 41]
    assert [M7.prep_index(1, "B"), M7.prep_index(1, "C"), M7.prep_index(5, "C")] == [42, 43, 51]
    assert [M7.k_index(1, 0), M7.k_index(2, 0), M7.k_index(5, 2)] == [4, 7, 18]
    assert [M7.k_cond(1, 0), M7.k_cond(2, 0), M7.k_cond(3, 1), M7.k_cond(5, 2)] == ["A", "B", "A", "C"]
    assert M7.k_set_of(4) == (1, 0, "A") and M7.k_set_of(18) == (5, 2, "C") and M7.prep_set_of(43) == (1, "C")
    assert M7.s_letter_of(16) == "C" and M7.s_label(27) == "S12" and M7.s_analysis_split(21) == "dev" and M7.s_analysis_split(22) == "confirm"
    assert M7.p_analysis_split(29) == "dev" and M7.p_analysis_split(30) == "confirm"
    assert len(M7.EXTENDED_P_ORDER) == 52 and M7.EXTENDED_P_ORDER[:12] == M7.M6_P_ORDER == ("L-C", "B-G", "L-N", "B-C", "L-G", "B-N", "B-N", "L-G", "B-C", "L-N", "B-G", "L-C")
    assert M7.EXTENDED_P_ORDER[12:18] == M7.P_BLOCKS["D1"] and M7.EXTENDED_P_ORDER[42:52] == M7.PREP_ROWS and M7.load_of(13) == "B" and M7.policy_of(43) == policy_ref.POLICY_PAR_NPU
    assert M7.REGISTRATION["sha256"] == "c3da26cc05c496ed4ebaf718f9c7d3293204e5223e0830a1fb0c378968a226bb"
    # importing m7_common changes nothing in m6_common (test_m6 shares this process); extended() does, and restores
    assert len(M.P_ORDER) == 12 and M.REGISTRATION["sha256"].startswith("b57b8957")
    with M7.extended():
        assert len(M.P_ORDER) == 52 and M.REGISTRATION["sha256"] == M7.REGISTRATION["sha256"]
    assert len(M.P_ORDER) == 12 and M.REGISTRATION["sha256"].startswith("b57b8957")
    assert M7.M6_REGISTRATION["sha256"].startswith("b57b8957")


def test_m6_tables_untouched_without_m7_import():
    code = ("import sys; sys.path.insert(0, %r); import m6_common as M; import mixreq_common as C\n"
            "assert len(M.P_ORDER) == 12 and M.REGISTRATION['sha256'].startswith('b57b8957'), (len(M.P_ORDER), M.REGISTRATION)\n"
            "print('ok')") % str(HERE)
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", code], capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == "ok", r.stderr


def test_uuid5_and_projection_match_registration():
    assert M.session_id(M.P_ID, 12) == "470dd4dc-00e6-53aa-928f-d76656a17e80"
    assert M.session_id(M.K_ID, 4) == "fd605c9a-0e89-58c8-8edb-4238a3996936"
    assert C.session_id(M7.S_ID, 16) == "b2e7af7b-c06c-53a1-b6e4-4a63b3a9e9fa"
    with M7.extended():
        for i in range(12, 52):
            rows = M.requests(M.P_ID, i, M.session_id(M.P_ID, i))
            assert M.projection_sha256(rows) == (REG_L if M.load_of(i) == "L" else REG_B)
        assert all(M.load_of(i) == "L" for i in range(42, 52)) and [M.letter_of(i) for i in range(42, 52)] == list("CNCNCNCNCN")
    with pytest.raises(IndexError):
        M.load_of(12)   # m6_common alone = M6 rows only


def test_plan_p_and_prep():
    plan = C.read_json(PLAN_P / "plan.json")
    assert [s["index"] for s in plan["sessions"]] == list(range(12, 42))
    assert [f"{s['load']}-{s['letter']}" for s in plan["sessions"]] == [x for b in M7.P_BLOCK_ORDER for x in M7.P_BLOCKS[b]]
    assert [s["analysis_split"] for s in plan["sessions"]] == ["dev"] * 18 + ["confirm"] * 12
    assert plan["projection"]["L"]["matches_registered"] and plan["projection"]["B"]["matches_registered"]
    assert plan["projection"]["L"]["sha256"] == REG_L and plan["projection"]["B"]["sha256"] == REG_B
    assert plan["blocks"]["D1"] == [12, 13, 14, 15, 16, 17] and plan["execution"]["m7b"] == list(range(30, 42))
    ref = C.read_json(PLAN_M6K / C.read_json(PLAN_M6K / "plan.json")["sessions"][0]["manifest"])
    same = ("protocol", "anchors", "image", "labels", "runtimes", "start_check", "stop_rules", "warmup_gate", "sample_period_ms", "attempt", "block")
    for e in plan["sessions"] + plan["smoke"]:
        m = C.read_json(PLAN_P / e["manifest"])
        assert C.sha256_bytes(C.canonical_json(m)) == e["manifest_sha256"]
        assert m["block"] == "M" and m["policy"] == M.LETTER_POLICY[e["letter"]] and m["cycle"] == "m7" and len(m["requests"]) == 100
        for k in same:
            assert m[k] == ref[k], (e["manifest"], k)
        assert m["phases"] == dict(ref["phases"], common_s=120) and m["registration"]["sha256"] == M7.REGISTRATION["sha256"]
        with M7.extended():
            assert m["requests"] == M.requests(m["experiment_id"], m["session_index"], m["session_id"]) and m["time_scale"] == 1
    smoke = C.read_json(PLAN_P / plan["smoke"][0]["manifest"])
    assert smoke["experiment_id"] == M.P_SMOKE_ID and smoke["session_index"] == 12 and smoke["split"] == "diagnostic" and smoke["m6_load"] == "L" and smoke["m6_letter"] == "C"
    prep = C.read_json(PLAN_PREP / "plan.json")
    assert [s["index"] for s in prep["sessions"]] == list(range(42, 52)) and all(s["role"] == "prep" for s in prep["sessions"])
    assert [(s["m7_set"], s["m7_cond"], s["load"], s["letter"]) for s in prep["sessions"]][:4] == [(1, "B", "L", "C"), (1, "C", "L", "N"), (2, "B", "L", "C"), (2, "C", "L", "N")]
    assert [s["k_index"] for s in prep["sessions"]] == [M7.k_index(s, M7.K_SETS[s].index(c)) for s in range(1, 6) for c in "BC"]
    assert prep["projection"]["L"]["matches_registered"]
    assert {s["session_id"] for s in plan["sessions"]}.isdisjoint({s["session_id"] for s in prep["sessions"]})
    m6p = C.read_json(REPO / "s26" / "results" / "m6_1012" / "plan_m6p" / "plan.json")
    assert {s["session_id"] for s in m6p["sessions"]}.isdisjoint({s["session_id"] for s in plan["sessions"] + prep["sessions"]})


def test_plan_k():
    plan = C.read_json(PLAN_K / "plan.json")
    assert [s["index"] for s in plan["sessions"]] == list(range(4, 19))
    assert [s["condition"] for s in plan["sessions"]] == list("ABCBCACABACBBAC")
    assert [s["analysis_split"] for s in plan["sessions"]] == ["dev"] * 9 + ["confirm"] * 6
    for s in plan["sessions"]:
        assert (s["prep_index"] is None) == (s["condition"] == "A")
        if s["prep_index"] is not None:
            assert M7.prep_set_of(s["prep_index"]) == (s["set"], s["condition"])
    ref = C.read_json(PLAN_M6K / C.read_json(PLAN_M6K / "plan.json")["sessions"][0]["manifest"])
    skip = {"session_id", "session_index", "m6_run", "analysis_split", "registration", "cycle", "item", "role", "m7_set", "m7_cond", "order_pos", "pair"}
    for e in plan["sessions"]:
        m = C.read_json(PLAN_K / e["manifest"])
        assert C.sha256_bytes(C.canonical_json(m)) == e["manifest_sha256"]
        for k in set(ref) - skip:
            assert m[k] == ref[k], (e["manifest"], k)   # 계약 열 = M6 K
        assert m["requests"] == [] and m["phases"]["common_s"] == 780 and m["block"] == "M" and m["policy"] == policy_ref.POLICY_CPU
    smoke = C.read_json(PLAN_K / plan["smoke"][0]["manifest"])
    assert smoke["experiment_id"] == M.K_SMOKE_ID and smoke["session_index"] == 4 and smoke["time_scale"] == 10 and smoke["split"] == "diagnostic"
    assert plan["sets"]["1"][0]["condition"] == "A" and plan["sets"]["2"][0]["condition"] == "B" and plan["sets"]["3"][0]["condition"] == "C"   # JSON keys are strings


def test_plan_s_matches_r4_form():
    plan = C.read_json(PLAN_S / "plan.json")
    assert [s["index"] for s in plan["sessions"]] == list(range(16, 28)) and [s["letter"] for s in plan["sessions"]] == list(M7.S_ORDER)
    ref = C.read_json(PLAN_V3S / C.read_json(PLAN_V3S / "plan.json")["sessions"][0]["manifest"])   # R4 (S) block A CPU manifest
    skip = {"session_id", "session_index", "pair", "policy", "block", "runtimes", "requests", "used_keys", "phases", "registration", "registration_v1", "registration_v2",
            "registration_mixreq_v3", "analysis_split", "cycle", "item", "role", "m7_s", "m6_letter", "m7_label"}
    for e in plan["sessions"]:
        m = C.read_json(PLAN_S / e["manifest"])
        assert C.sha256_bytes(C.canonical_json(m)) == e["manifest_sha256"]
        assert m["experiment_id"] == "S26-MIXREQ-03" and len(m["requests"]) == 3000 and m["phases"]["common_s"] == 720 and m["time_scale"] == 1
        assert m["block"] == M7.S_BLOCK_OF_LETTER[e["letter"]] and m["policy"] == M7.LETTER_POLICY[e["letter"]] and 0 <= m["pair"] <= 3
        assert m["requests"] == C.requests(m["session_id"], 3000)
        assert m["registration"]["sha256"] == M7.REGISTRATION["sha256"] and m["registration_mixreq_v3"]["sha256"].startswith("45f151d3")
        for k in set(ref) - skip:
            assert m[k] == ref[k], (e["manifest"], k)
        assert m["phases"] == ref["phases"] if m["block"] == "A" else m["phases"]["setup_s"] == 180
    smoke = C.read_json(PLAN_S / plan["smoke"][0]["manifest"])
    assert smoke["experiment_id"] == "S26-MIXREQ-03-SMOKE" and smoke["session_index"] == 16 and len(smoke["requests"]) == 24 and smoke["time_scale"] == 10 and smoke["block"] == "A"


def test_slope_gap_coverage():
    rows = [dict(host_epoch_s=1000 + i * 2.3, AP=30.0 + 0.05 * (i * 2.3 / 60), SKIN=29.0) for i in range(60)]
    st = M7.stable_from_hal(rows, 1000 + 59 * 2.3)
    assert st["stable"] and abs(st["ap_slope_c_per_min"] - 0.05) < 1e-6 and st["skin_slope_c_per_min"] == 0 and st["samples"] == 53
    rows2 = [dict(r, SKIN=29.0 + 0.3 * (r["host_epoch_s"] - 1000) / 60) for r in rows]
    assert not M7.stable_from_hal(rows2, 1000 + 59 * 2.3)["stable"]
    assert M7.stable_from_hal(rows[:1], 1000)["stable"] is False and M7.slope_c_per_min([]) is None
    assert M7.gap_record(100.0, 193.5) == dict(gap_s=93.5, gap_over=False, gap_under=False, target_s=90, max_ok_s=100)
    assert M7.gap_record(100.0, 201.0)["gap_over"] is True and M7.gap_record(100.0, 185.0)["gap_under"] is True
    assert M7.gap_record(None, 5.0)["gap_s"] is None
    assert M7.coverage_after(10.0, 115.4) == 105.4 and M7.coverage_after(None, 1.0) is None


def test_field_map_and_table_fields():
    f = T.FIELD_MAP["fields"]
    assert set(f) == {"arrival", "dispatch", "execution_start", "host_inference_start", "host_inference_return", "output_ready", "persist_complete", "worker_release",
                      "AVAILABLE", "응답 시각", "결과", "백엔드"}
    for k, v in f.items():
        assert ("column" in v and "event" in v), k
        if v["column"] is None and v["event"] is None:
            assert v.get("reason") or v.get("file"), k   # null → reason (추정 채움 0)
    for col in ("cycle", "item", "condition", "role", "set", "block", "order_pos", "prep_session_id", "prep_last_available_host", "k_app_start_host", "gap_prep_to_k_s", "stable",
                "charge_end_to_start_s", "hal_cont_path", "power_coverage_after_last_available_s", "hal_coverage_after_last_available_s", "case_stand_wind", "room_c", "fingerprint"):
        assert col in T.FIELDS, col


def test_hal_cont_csv_parse(tmp_path):
    p = tmp_path / "hal.csv"
    p.write_text("host_ms,host_iso,device_uptime_s,AP,SKIN,BAT,PA,skin_status,level,status,plugged,current_now_uA,voltage_mV,bat_temp_deci_c,cmd_ms,interval_ms,err,tag\n"
                 "1000000,2026-10-13T00:00:00.000+09:00,1.0,24.9,27.2,24.7,24.8,0,90,3,0,-78906,4341,247,256,,,t\n"
                 "1002300,2026-10-13T00:00:02.300+09:00,3.3,,,,,,,,,,,,10,2300,adb_rc_1,t\n", encoding="utf-8")
    rows = D.Driver.hal_rows(p)
    assert rows[0]["host_epoch_s"] == 1000.0 and rows[0]["AP"] == 24.9 and rows[0]["SKIN"] == 27.2 and rows[1]["SKIN"] is None and rows[1]["err"] == "adb_rc_1"
    assert D.Driver.hal_row_count(p) == 2


def test_power_events_parse():
    dump = ("[EventLogBuffer]\n10-13 19:03:45.303  android.intent.action.ACTION_POWER_CONNECTED\n10-13 19:54:36.487  android.intent.action.ACTION_POWER_DISCONNECTED\n")
    d = D.Driver.power_events(None, dump)
    assert d["last_power_disconnected"].endswith("19:54:36.487") and d["unplugged_since_last_disconnect"] is True
    d2 = D.Driver.power_events(None, dump + "10-13 20:00:00.000  android.intent.action.ACTION_POWER_CONNECTED\n")
    assert d2["unplugged_since_last_disconnect"] is False


def test_plans_are_deterministic(tmp_path):
    aot = REPO / "npu-runner/src/main/assets/models/efficientnet_lite0_Samsung_E9965.tflite"
    if not aot.is_file():
        pytest.skip("AOT artifact missing (git 밖)")
    args = ["--cls-model", "local_models/efficientnet_lite0.tflite", "--det-model", "local_inputs/public/efficientdet_lite0.tflite",
            "--aot-model", "npu-runner/src/main/assets/models/efficientnet_lite0_Samsung_E9965.tflite",
            "--png", "local_inputs/canonical_v123/00575b9132bb3746.png", "--anchors", "local_inputs/reference_pc/anchors.json",
            "--cls-labels", "local_inputs/reference_pc/labels_without_background.txt", "--det-labels", "local_inputs/reference_pc/labels.txt"]
    subprocess.run([sys.executable, "-X", "utf8", str(HERE / "m7_plan.py"), "--out-root", str(tmp_path), *args], cwd=REPO, check=True, capture_output=True)
    for name in ("plan_m7p", "plan_m7prep", "plan_m7k", "plan_m7s"):
        a, ref = tmp_path / name, ROOT / name
        files = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
        assert files == sorted(p.relative_to(ref) for p in ref.rglob("*") if p.is_file())
        for f in files:
            assert (a / f).read_bytes() == (ref / f).read_bytes(), f
