"""경계 시험 (조민규 10/15 22:xx): slope_ok 는 0 · -0.0 을 숫자로 통과시키고 None 은 null (False 아님) 로 보존 · ±0.1 경계 · pick() 의 before/nearest/null."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import m8_b1_corrections as B  # noqa: E402


@pytest.mark.parametrize("ap,skin,expected", [
    (0.0, 0.0, True), (-0.0, 0.0, True), (0.0, -0.0, True),
    (0.1, 0.0, True), (-0.1, 0.0, True), (0.0, 0.1, True),
    (0.1000001, 0.0, False), (-0.1000001, 0.0, False), (0.0, 0.2, False),
    (None, 0.0, None), (0.0, None, None), (None, None, None),
])
def test_slope_ok_boundaries(ap, skin, expected):
    out = B.slope_ok(dict(ap_slope_c_per_min=ap, skin_slope_c_per_min=skin), 0.1)
    assert out is expected if expected is None else out == expected
    if expected is None:
        assert out is not False, "결측은 False/0 과 구분해 None 으로 보존"


def test_slope_ok_zero_is_number_not_missing():
    assert B.slope_ok(dict(ap_slope_c_per_min=0.0, skin_slope_c_per_min=-0.0), 0.1) is True
    assert B.slope_ok(dict(ap_slope_c_per_min=0, skin_slope_c_per_min=0), 0.1) is True


def test_pick_before_and_nearest_and_null():
    rows = [dict(up=100.0, AP=30.0, SKIN=31.0), dict(up=102.3, AP=30.3, SKIN=31.2), dict(up=104.6, AP=30.6, SKIN=31.4)]
    b = B.pick(rows, "up", 103.0, "before", 10.0)
    assert b["AP"] == 30.3 and b["sample"] == 102.3 and b["delta_s"] < 0      # 직전 표본만 (이후 104.6 은 쓰지 않음)
    n = B.pick(rows, "up", 103.5, "nearest", 6.0)
    assert n["AP"] == 30.6                                                     # nearest 는 양쪽
    assert B.pick(rows, "up", 99.0, "before", 10.0)["AP"] is None              # target 이전 표본 없음 → null
    assert B.pick(rows, "up", 200.0, "nearest", 6.0)["AP"] is None             # tol 밖 → null
    assert B.pick(rows, "up", None, "nearest", 6.0)["AP"] is None              # target 없음 → null
