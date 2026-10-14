"""M8 host tests (pytest, no phone): tables = 계약표 v1 verbatim · uuid5 새 계보 == app (Kotlin M8PlanTest 값) · bank 4 식 · 537.155 재계산 · SMOOTH 균등식 · arm/index 대역 ·
plan files (blocks.json counts · seed 순서 결정적 · manifests = M8 계약 · 쓴 자리 재사용 0) · activate()/deactivate() 가 m6 표를 되돌림 · m8_gate (Tref · START · REJECT 이유) ·
coverage_check (합성 표본 · A-4 대조 결과 파일) · m8_validate (Robolectric M8 round-trip 산출물 · 있을 때만) · policy rule cases (policies_m8.json) vs Python head rule.

  py -3 -m pytest -q s26/tools/mixreq/test_m8.py
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
import m8_common as M8  # noqa: E402
import mixreq_common as C  # noqa: E402
import m6_common as M6  # noqa: E402
import m8_gate as G  # noqa: E402
import coverage_check as CC  # noqa: E402
import m8_validate as MV  # noqa: E402

PREP = REPO / "s26" / "results" / "m8_prep"
CONTRACT = PREP / "contract"


def test_ids_and_banks_match_app():
    assert str(M8.M8_NS) == "e4abc988-c5f5-5657-b7d7-e3060cda0ac6"
    assert M8.session_id(M8.FN_ID, 0) == "e74fd67f-c716-5716-b0ce-f4a1afe628d8"
    assert M8.session_id(M8.M128_ID, 999) == "09f3d194-ec61-536c-b874-dc31d9010d5d"
    assert M8.session_id("S26-M8-M128-SMOKE", 0) == "db4555ad-59a3-534e-acbc-85a81e8a27dd"
    sid = M8.session_id(M8.M128_ID, 0)
    assert M8.request_id(sid, 0) == "8f95ef14-320c-563d-b257-32ea5a70e761" and M8.request_id(sid, 127) == "907ad989-87d1-5565-b9c9-d37302ae8b58"
    assert sid != C.session_id(M8.M128_ID, 0)
    l, c, m, s = (M8.slots(b) for b in ("L64", "C252", "M128", "SMOOTH128"))
    assert len(l) == 64 and l[-1][1] == 98_000_000 and l[1][0] == "detection"
    assert len(c) == 252 and c[-1][1] == 118_633_200 and c[1][1] == 35_333_200
    assert [x[1] for x in m[:8]] == [35_000_000] * 8 and m[8][1] == 35_537_155 and m[-1][1] == 43_057_325 and "".join("C" if t == "classification" else "D" for t, _ in m[:8]) == "CCCDCCCD"
    assert [t for t, _ in s] == [t for t, _ in m] and s[0][1] == 35_000_000 and s[-1][1] == 43_057_325 and s[1][1] == 35_063_444 and s[64][1] == 39_060_384 and s[126][1] == 42_993_881
    assert M8.burst_interval_us(73.5442, 241.7197) == 537_155 == M8.BURST_INTERVAL_US and M8.burst_interval_us(73.6814, 241.3512) == 536_336
    rows = M8.requests(M8.M128_ID, 0, sid)
    assert rows[8]["offset_ms"] == 35_537 and rows[8]["offset_us"] == 35_537_155 and rows[0]["deadline_ms"] == 800 and rows[3]["deadline_ms"] == 2000 and rows[3]["priority"] == "normal"
    b = M8.burst_index_of(rows)
    assert b[rows[7]["request_id"]] == 0 and b[rows[8]["request_id"]] == 1 and b[rows[127]["request_id"]] == 15
    with pytest.raises(ValueError):
        M8.validate_bank(rows[:-1], "M128")
    recalc = C.read_json(CONTRACT / "burst_interval_recalc.json")
    assert recalc["match"] and recalc["match"][0]["dataset"] == "M6_dev_idx0_5" and recalc["match"][0]["interval_ms"] == 537.155


def test_arms_bands_and_tables():
    assert [a["name"] for a in M8.arms(M8.FN_ID)] == ["C252_CPU", "C252_GPU", "C252_NPU", "M128_BASE", "M128_PAIR_G", "M128_PAIR_N"]
    assert len(M8.arms(M8.M128_ID)) == 8 and M8.arm_of(M8.M128_ID, 15)["name"] == "M128_WAIT1000x12" and M8.repetition_of(M8.M128_ID, 15) == 1
    assert M8.arm_of(M8.M128_ID, 3)["wait"] == M8.WAIT200X16 and M8.arm_of(M8.RECENT_ID, 3)["prep"] == "IDLE60" and M8.arm_of(M8.IDLE_ID, 0)["block"] == "NONE"
    assert M8.index_of(M8.M128_ID, "M128_ORDER", 2) == 17 and M8.dev_count(M8.M128_ID) == 500 and M8.analysis_split_of(M8.M128_ID, 500) == "confirm"
    assert M8.lane_for(M8.P_FIFO_WAIT_CG, "classification") == "GPU" and M8.lane_for(M8.P_FIFO_SERIAL_CN, "detection") == "CPU" and M8.lane_for(M8.P_FIFO_SERIAL_CPU, "classification") == "CPU"
    assert M8.SELECTION[M8.P_EDD_SERIAL_CG] == "EDD" and M8.CONCURRENCY[M8.P_FIFO_PAIR_CN] == "PAIR" and M8.CONCURRENCY[M8.P_FIFO_WAIT_CG] == "SERIAL"
    pol = C.read_json(CONTRACT / "policies_m8.json")
    assert [p["id"] for p in pol["policies"]] == ["FIFO_SERIAL_CPU_V1", "FIFO_SERIAL_CG_V1", "FIFO_SERIAL_CN_V1", "EDD_SERIAL_CG_V1", "FIFO_PAIR_CG_V1", "FIFO_PAIR_CN_V1", "FIFO_WAIT_CG_V1"]
    assert set(M8.M8_POLICIES) == {p["id"] for p in pol["policies"]}
    wv = pol["policies"][-1]["wait"]["variants"]
    assert wv["WAIT200x16"] == M8.WAIT200X16 and wv["WAIT200x12"] == M8.WAIT200X12 and wv["WAIT1000x12"] == M8.WAIT1000X12
    assert M8.SOC_MIN_START == 20 and M8.SOC_NEW_BAND == (40, 80) and M8.COOLING_S == 90 and M8.BASELINE_S == 60


def test_activate_restores_m6_tables():
    assert M6.SOC_MIN == 30 and C.session_cap_s("S26-M6-P", "M") == 720
    with pytest.raises(ValueError):
        C.experiment_of(M8.M128_ID)
    M8.activate()
    try:
        assert M6.SOC_MIN == 20 and C.session_cap_s(M8.M128_ID, "M") == 845 and C.session_cap_s("S26-M6-P", "M") == 720 and C.request_count_of("S26-M8-IDLE-SMOKE") == 0
        import policy_ref
        assert policy_ref.USED_KEYS[M8.P_FIFO_WAIT_CG] == ("classification_GPU", "detection_CPU") and policy_ref.BLOCK_KEYS["NONE"] == ()
    finally:
        M8.deactivate()
    assert M6.SOC_MIN == 30 and C.session_cap_s("S26-M6-P", "M") == 720


def test_plan_files_and_blocks():
    b = C.read_json(PREP / "plan_m8" / "blocks.json")
    assert b["counts"] == dict(smoke=6, p0=10, dev=38, confirm_planned=95) and b["dev_seed"] == 20261014 and b["sessions_per_block"] == 19
    o1, o2 = b["stages"]["dev_blocks"][0]["order"], b["stages"]["dev_blocks"][1]["order"]
    assert sorted(o1) == list(range(19)) == sorted(o2) and o1 != o2
    import random
    rng = random.Random(20261014)
    e1 = list(range(19)); rng.shuffle(e1); e2 = list(range(19)); rng.shuffle(e2)
    assert o1 == e1 and o2 == e2                                   # 결정적 (seed 고정 · 결과 전)
    used = set()
    for st in ("p0", "dev_blocks"):
        items = b["stages"][st] if st == "p0" else [s for blk in b["stages"]["dev_blocks"] for s in blk["sessions"]]
        for s in items:
            key = (s["experiment_id"], s["index"])
            assert key not in used, key                             # 쓴 자리 재사용 0
            used.add(key)
            assert s["index"] < M8.dev_count(s["experiment_id"]) and M8.arm_of(s["experiment_id"], s["index"])["name"] == s["arm"]
    for plan_dir in M8.PLAN_DIR.values():
        plan = C.read_json(PREP / plan_dir / "plan.json")
        assert plan["contract"] == "M8" and (PREP / plan_dir / "plan_sha256.txt").read_text().strip() == b["plan_sha256"][plan_dir]
        for e in plan["sessions"] + plan["smoke"]:
            m = C.read_json(PREP / plan_dir / e["manifest"])
            assert C.sha256_bytes(C.canonical_json(m)) == e["manifest_sha256"]
            a = M8.arm_of(m["experiment_id"], m["session_index"])
            assert m["contract"] == "M8" and m["policy"] == a["policy"] and m["block"] == a["block"] and m["policy_args"] == a["wait"] and m["prep"]["kind"] == a["prep"]
            assert m["phases"] == dict(setup_s=180, gate_s=60, baseline_s=60, common_s=120, drain_s=30, cooling_s=90)
            assert m["requests"] == M8.requests(m["experiment_id"], m["session_index"], m["session_id"]) and m["session_id"] == M8.session_id(m["experiment_id"], m["session_index"])
            assert (len(m["runtimes"]) == 0) == (m["block"] == "NONE") and (len(m["runtimes"]) in (0, 5))
            assert (m["split"] == "diagnostic") == ("SMOKE" in m["experiment_id"])
    assert len(C.read_json(PREP / "plan_m8c252" / "plan.json")["sessions"]) == 0     # C252 (P1) = RECENT IDLE60 arm (blocks.json rules.c252_in_block)


def test_gate_rules():
    rows = [dict(host_epoch_s=1000 + i * 2.3, AP=25.0, SKIN=27.6 + (0.1 if i % 7 == 0 else 0.0)) for i in range(600)]
    t = rows[-1]["host_epoch_s"]
    cand = G.tref_candidate(rows, t)
    assert cand["stable"] and cand["tref_c"] == 27.6 and cand["algorithm"] == "TREF_DAY_IDLE_MEDIAN_V1"
    d = G.start_decision(rows, t, 27.6, 55, False)
    assert d["start"] and not d["reasons"] and d["soc_in_new_band_reference_only"]
    assert not G.start_decision(rows, t, 27.6, 19, False)["start"] and G.reject_reason([G.start_decision(rows, t, 27.6, 19, False)]) == "soc"
    assert not G.start_decision(rows, t, 27.6, 55, True)["start"]
    assert G.reject_reason([G.start_decision(rows, t, 28.3, 55, False)]) == "tref"
    hot = [dict(r, SKIN=r["SKIN"] + 0.5 * (r["host_epoch_s"] - 1000) / 60) for r in rows]
    assert G.reject_reason([G.start_decision(hot, t, hot[-1]["SKIN"], 55, False)]) == "slope"
    assert not G.start_decision(rows, t, None, 55, False)["start"]
    assert G.start_decision(rows, t, 27.6, 90, False)["start"]      # 상한 없음 (영훈)


def test_coverage_check_synthetic_and_a4(tmp_path):
    cs = 1_000_000_000_000
    samples = [dict(t=cs + int((-70 + 0.9 * i) * 1e9), current=-500_000, valid=True, charge=1, voltage=4000) for i in range(320)]   # −70 ~ +217 s
    app = CC.check_app(cs, samples)
    assert app["passed"] and app["points"]["180"]["ok"] and app["pre_t0_s"] >= 60 and app["post_t0_s"] >= 210
    short = [s for s in samples if (s["t"] - cs) / 1e9 < 179.9]
    a2 = CC.check_app(cs, short)
    assert not a2["passed"] and not a2["points"]["180"]["ok"] and any("post_t0" in r for r in a2["reasons"])
    pos = [dict(s, current=100) for s in samples]
    assert any("positive" in r for r in CC.check_app(cs, pos)["reasons"])
    hal = [dict(boot=cs / 1e9 - 90 + 2.3 * i, host_ms=None, AP=25.0, SKIN=27.0, current=-60000.0, voltage=4200.0, err="") for i in range(200)]
    host = CC.check_host(cs, hal)
    assert host["passed"] and host["ap_points"]["180"]["ok"] and host["iv_points"]["0"]["ok"]
    gap = [r for r in hal if not (170 < r["boot"] - cs / 1e9 < 190)]
    assert not CC.check_host(cs, gap)["ap_points"]["180"]["ok"]
    res = C.read_json(PREP / "coverage_check_vs_A4.json")
    assert res["compare_with_a4"]["same"] and res["compare_with_a4"]["compared"] == 40 and res["p_app_180_both"] == "0/18" and res["p_host_ap180"] == "18/18"


def test_head_rule_cases_from_contract():
    pol = C.read_json(CONTRACT / "policies_m8.json")
    assert len(pol["test_cases"]["cases"]) == 19
    S = 1_000_000_000

    def t(tag):   # "C0@35.000" · "D5@35.537 (dl 37.0)"
        name, rest = tag.split("@")
        arr = float(rest.split()[0])
        task = "classification" if name[0] == "C" else "detection"
        dl = arr + (0.8 if task == "classification" else 2.0)
        if "(dl" in rest:
            dl = float(rest.split("(dl")[1].strip(" )"))
        return dict(request_id=name, task_id=task, ordinal=int(name[1:]), scheduled_arrival_ns=int(arr * S), deadline_ns=int(dl * S))
    checks = {"FIFO 순서 = scheduled_arrival → ordinal → id": "C1", "EDD 절대기한 우선": "C1", "EDD 동점 = FIFO": "C1", "CPU 직렬 FIFO (urgent 우선 없음)": "D0"}
    for case in pol["test_cases"]["cases"]:
        if case["name"] in checks:
            policy = case["policy"].split()[0]
            assert MV.head_of(policy, [t(w) for w in case["W"]])["request_id"] == checks[case["name"]], case["name"]


def test_m8_validate_on_roundtrip_outputs():
    root = REPO / "request-runner" / "build" / "m8-roundtrip"
    if not root.is_dir():
        pytest.skip("M8 round-trip outputs missing (run request-runner unit tests first)")
    seen = 0
    for case in sorted(p for p in root.iterdir() if p.is_dir() and p.name != "_inputs"):
        out = case / "a1"
        if not (out / "manifest.json").is_file():
            continue
        v, contract = MV.validate(out, out, None, None, None, True)
        seen += 1
        names = [n for n in v["rules"]]
        assert names == ["A0_artifacts", "A1_rows", "A2_order", "A3_window", "A4_route_residents", "A5_concurrency_head", "A6_response", "A7_wait", "A8_prep", "A9_safety", "A10_coverage"]
        gating = [n for n in names if n != "A10_coverage"]
        assert all(v["rules"][n]["passed"] for n in gating), (case.name, [(n, v["rules"][n]["detail"]) for n in gating if not v["rules"][n]["passed"]])
        if "WAIT" in case.name:
            assert v["rules"]["A7_wait"]["detail"]["waits"] == 16
        if "slow" in case.name:
            assert v["counts"].get("undispatched", 0) > 0 and v["service"]["all"]["undispatched"] > 0
        if "RECENT" in case.name:
            assert v["rules"]["A8_prep"]["detail"]["kind"] == "CPU60"
        if "NO_RUNTIME" in case.name:
            assert v["block"] == "NONE" and v["rules"]["A4_route_residents"]["passed"]
    assert seen >= 6
