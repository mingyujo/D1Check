"""M8 CONFIRM R21 host tests (pytest, no phone): 분석 계약 m8_readout_r21 (경계 양측 · gap 초과 → null · 보간 0 · 부호 · µAh · 계단 경계 · Holm · t 구간) ·
R21 계획 (21 슬롯 · 원 C 슬롯 대응 · 매니페스트 arm = 슬롯 arm · DEV 와 같은 도착/정책 · 결정적) · 드라이버 confirm 단계 (21 슬롯 밖 거절 · v5 상수 고정).

  py -3 -m pytest -q s26/tools/mixreq/test_m8_r21.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import m8_readout_r21 as R  # noqa: E402
import m8_common as M8  # noqa: E402
import mixreq_common as C  # noqa: E402

PREP = REPO / "s26" / "results" / "m8_prep"


# ---------------------------------------------------------------- 경계 · gap · 보간 0
def test_value_at_two_sided_linear_and_gap():
    s = [(0.0, 10.0), (2.0, 20.0)]
    assert R.value_at(s, 1.0, 2.5) == pytest.approx(15.0)
    assert R.value_at(s, 0.0, 2.5) == 10.0            # 정확히 그 시각 표본
    assert R.value_at(s, 1.0, 1.9) is None            # 양측 간격 2.0 > 1.9 → null
    assert R.value_at(s, 3.0, 5.0) is None            # 뒤쪽 표본 없음 → 외삽 0
    assert R.value_at(s, -1.0, 5.0) is None           # 앞쪽 표본 없음 → 외삽 0
    assert R.value_at([(0.0, 1.0), (1.0, None), (2.0, 3.0)], 1.0, 2.5) == pytest.approx(2.0)   # 결측 표본은 건너뛰고 양측 실제 표본


def test_integrate_trapezoid_boundaries_and_gap_null():
    s = [(t * 0.9 - 0.45, 2.0) for t in range(0, 300)]   # 상수 2 W · 0.9 s
    r = R.integrate(s, 0.0, 180.0, 2.5)
    assert r["value"] == pytest.approx(360.0)
    lin = [(t * 0.9 - 0.45, t * 0.9 - 0.45) for t in range(0, 300)]   # W = t → ∫0^180 = 16200
    assert R.integrate(lin, 0.0, 180.0, 2.5)["value"] == pytest.approx(16200.0)
    holes = [(x, v) for x, v in s if not (50.0 < x < 53.5)]          # 창 안 gap 3.6 s > 2.5
    h = R.integrate(holes, 0.0, 180.0, 2.5)
    assert h["value"] is None and h["reason"] == "gap_in_window"
    short = [(x, v) for x, v in s if x < 179.0]                        # 180 s 뒤 표본 없음 → tail 외삽 0
    assert R.integrate(short, 0.0, 180.0, 2.5)["value"] is None


def test_watts_sign_and_units():
    assert R.watts(-180000, 3800) == pytest.approx(0.684)    # 방전 음수 µA × mV / 1e9 = W (양수)
    assert R.watts(500000, 4300) < 0                          # 충전 (양수 전류) → 음수 W


def test_charge_consistency_uah_and_step_boundaries():
    # 1 A (= 1e6 µA) 방전 · 0.9 s 읽기 · charge_counter 가 4275 µAh 마다 감소 (≈ 15.39 s)
    t = [k * 0.9 for k in range(400)]
    I = [-1e6] * len(t)
    cc, q = [], 1_000_000.0
    for x in t:
        cc.append(1_000_000.0 - 4275.0 * math.floor(x * 1e6 / 3600 / 4275.0))
    r = R.charge_consistency(t, I, cc)
    assert r["step_sizes"] == [4275.0] and r["changes"] >= 2
    assert r["r"] == pytest.approx(1.0, abs=0.03)
    assert r["interval_s"][0] == t[next(k for k in range(1, len(cc)) if cc[k] != cc[k - 1])]
    assert R.charge_consistency(t[:5], I[:5], [1.0] * 5)["r"] is None          # 계단 < 2
    up = R.charge_consistency([0, 1, 2, 3], [1, 1, 1, 1], [0, 10, 20, 30])         # 증가 = 감소 아님
    assert up["r"] is None and up["increases"] == 3


def test_session_energy_gate_rules():
    ok = dict(plugged_any=False, charge=dict(r=0.9))
    assert R.session_energy_gate(ok, True) == (True, None)
    assert R.session_energy_gate(ok, False)[0] is False
    assert R.session_energy_gate(dict(plugged_any=True, charge=dict(r=0.9)), True)[0] is False
    assert R.session_energy_gate(dict(plugged_any=False, charge=dict(r=0.79)), True)[0] is False
    assert R.session_energy_gate(dict(plugged_any=False, charge=dict(r=1.26)), True)[0] is False
    assert R.session_energy_gate(dict(plugged_any=False, charge=dict(r=None, reason="x")), True)[0] is False


def test_dev_verdict_thresholds():
    base = dict(load_neg_fraction=1.0, load_samples=90, voltage_min_mv=3700, voltage_max_mv=4200, charge=dict(r=0.86))
    assert R.dev_verdict([base] * 3)["eligible"] is True
    assert R.dev_verdict([dict(base, load_neg_fraction=0.9)] * 3)["eligible"] is False
    assert R.dev_verdict([dict(base, voltage_max_mv=4700)] * 3)["eligible"] is False
    assert R.dev_verdict([dict(base, charge=dict(r=0.0009))] * 3)["eligible"] is False   # ×1000 배율이면 미확정 (보정 0)


# ---------------------------------------------------------------- 요약 · Holm · t
def test_summarize_and_t_interval():
    s = R.summarize([1.0, 2.0, 3.0])
    assert s["n"] == 3 and s["mean"] == 2.0 and s["median"] == 2.0 and s["pos"] == 3
    assert s["ci95"][0] == pytest.approx(2.0 - 4.30265272975 * 1.0 / math.sqrt(3))
    assert s["p"] == pytest.approx(0.0742, abs=1e-3)      # t = 3.464 · df 2 · 양측
    m = R.summarize([1.0, None, -1.0])
    assert m["n"] == 2 and m["d_b"] == [1.0, None, -1.0] and m["sign"].startswith("+1/−1")
    assert R.summarize([None, None, None])["mean"] is None
    assert R.t_cdf(0.0, 2) == pytest.approx(0.5)
    assert R.t_cdf(4.30265272975, 2) == pytest.approx(0.975, abs=1e-6)
    scipy = pytest.importorskip("scipy.stats")
    for t in (-3.0, -0.5, 0.7, 2.2, 9.0):
        for df in (1, 2, 4):
            assert R.t_cdf(t, df) == pytest.approx(scipy.t.cdf(t, df), abs=1e-9)


def test_holm():
    adj = R.holm([0.01, 0.04, 0.03, None])
    assert adj[0] == pytest.approx(0.03) and adj[2] == pytest.approx(0.06) and adj[1] == pytest.approx(0.06) and adj[3] is None


def test_overlap_dose():
    assert R.overlap_dose([(0, 10), (5, 20), (30, 40)]) == pytest.approx(5e-9)
    assert R.overlap_dose([(0, 1_000_000_000), (0, 1_000_000_000), (0, 500_000_000)]) == pytest.approx(1.0)


def test_pair_table_excludes_missing_block():
    by = {1: {"M128_BASE": {"J0_180": 100.0}, "M128_ORDER": {"J0_180": 110.0}}, 2: {"M128_BASE": {"J0_180": 100.0}}, 3: {"M128_BASE": {"J0_180": 90.0}, "M128_ORDER": {"J0_180": 95.0}}}
    t = R.pair_table(by, [1, 2, 3])
    p = next(x for x in t["J0_180"] if x["arm"] == "M128_ORDER")
    assert p["d_b"] == [10.0, None, 5.0] and p["n"] == 2


# ---------------------------------------------------------------- R21 계획
@pytest.mark.parametrize("name", ["r21_manifest", "r21_manifest_v2"])
def test_r21_plan_slots_and_manifests(name):
    man = json.loads((PREP / "plan_m8_r21" / f"{name}.json").read_text(encoding="utf-8"))
    v2 = name.endswith("_v2")
    assert C.sha256_bytes((PREP / "plan_m8_r21" / f"{name}.json").read_bytes()) == (PREP / "plan_m8_r21" / f"{name}_sha256.txt").read_text().strip()
    fz = json.loads((PREP / "CONFIRM_FREEZE_M8_v1.json").read_text(encoding="utf-8"))
    blocks = man["stages"]["confirm_blocks"]
    assert man["total"] == 21 and [len(b["sessions"]) for b in blocks] == [7, 7, 7]
    for b in blocks:
        c = next(x for x in fz["confirm_plan"]["order_precomputed"] if x["block_no"] == b["block_no"])
        orig = [s for s in c["sessions"] if s["arm"] in man["keep_groups"]]
        assert [s["origin_slot"]["label"] for s in b["sessions"]] == [s["label"] for s in sorted(orig, key=lambda s: s["order_pos"])]
        for s in b["sessions"]:
            assert s["session_id"] == M8.session_id(s["experiment_id"], s["index"]) and s["index"] >= M8.dev_count(s["experiment_id"])
            if v2:   # 앱 M8Plan.validateSession: arm = index % len(arms) · v1 index 보존
                assert M8.arm_of(s["experiment_id"], s["index"])["name"] == s["arm"] and s["v1_index"] == s["origin_slot"]["index"]
                assert (s.get("start_attempt", 1) == 2) == (s["label"] == "R1-0-M128_PAIR_G")
            else:
                assert s["index"] == s["origin_slot"]["index"] and s["session_id"] == s["origin_slot"]["session_id"]
            assert s["perfetto"] == "off" and s["label"].startswith(f"R{b['block_no']}-") and s["revision_id"] == man["revision_id"]
            plan = json.loads((PREP / s["plan_dir"] / "plan.json").read_text(encoding="utf-8"))
            e = next(x for x in plan["sessions"] if x["index"] == s["index"])
            m = json.loads((PREP / s["plan_dir"] / e["manifest"]).read_text(encoding="utf-8"))
            assert C.sha256_bytes(C.canonical_json(m)) == e["manifest_sha256"] == s["manifest_sha256"]
            assert m["arm"] == s["arm"] and m["analysis_split"] == "confirm" and m["pair"] == 1 and len(m["requests"]) == 128
            sd = s["plan_dir"].replace("_r21v2", "").replace("_r21", "")
            src = json.loads((PREP / sd / "plan.json").read_text(encoding="utf-8"))
            d0 = next(x for x in src["sessions"] if x["arm"] == s["arm"])
            dm = json.loads((PREP / sd / d0["manifest"]).read_text(encoding="utf-8"))
            for k in ("policy", "policy_args", "prep", "runtimes", "phases", "block", "bank", "used_keys", "stop_rules", "start_check", "image", "time_scale"):
                assert m[k] == dm[k], k
            assert [{k: v for k, v in r.items() if k != "request_id"} for r in m["requests"]] == [{k: v for k, v in r.items() if k != "request_id"} for r in dm["requests"]]
    assert set(man["keep_groups"]).isdisjoint(man["excluded_groups"]) and len(man["keep_groups"]) + len(man["excluded_groups"]) == 19


def test_driver_confirm_rejects_outside_slots(tmp_path):
    import m8_driver as D
    man = json.loads((PREP / "plan_m8_r21" / "r21_manifest_v2.json").read_text(encoding="utf-8"))
    items = man["stages"]["confirm_blocks"][0]["sessions"]
    D.check_confirm_items(man, items)                              # 통과
    bad = [dict(items[0], index=502)]
    with pytest.raises(SystemExit):
        D.check_confirm_items(man, bad)
    bad2 = [dict(items[0], perfetto="on")]
    with pytest.raises(SystemExit):
        D.check_confirm_items(man, bad2)
    assert D.CONFIRM_GATE == dict(tref_band_c=1.0, gate_window_s=120, gate_slope_max=0.2, gate_force_after_s=1800)
