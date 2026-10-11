"""P1l parallel simulator — component selftests (synthetic inputs + committed data tables only; no R4 outcome)."""
from d1sim.parsim_v1 import fit, judge_parsim, ladder, measure_r4, predict, thermal_sum


def test_thermal_sum_selftest():
    assert thermal_sum.selftest()


def test_fit_selftest():
    assert fit.selftest()


def test_predict_selftest():
    assert predict.selftest()


def test_measure_selftest():
    assert measure_r4.selftest()


def test_judge_selftest():
    assert judge_parsim.selftest()


def test_ladder_selftest():
    assert ladder.selftest()
