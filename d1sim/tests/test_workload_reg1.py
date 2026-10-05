"""Registered burst workload (sim/정책비교_사전등록_v1.md §2): determinism, conservation of BG work, slack -> deadline,
horizon rule, load ordering mean < sustained < burst, bad arguments rejected. Run: py -m pytest d1sim/tests -q"""
import pytest

from d1sim.workload_reg1 import scenario_reg1

R_NPU, R_GPU = 1130.7, 298.1     # EffNet cold d100 rates [P EffN420 · EffB2 G100 first 30 s]


def test_deterministic_per_seed_and_different_across_seeds():
    a = scenario_reg1(1, 2.0, 0.5, R_NPU)
    b = scenario_reg1(1, 2.0, 0.5, R_NPU)
    c = scenario_reg1(2, 2.0, 0.5, R_NPU)
    assert a == b and a['requests'] != c['requests']


@pytest.mark.parametrize('rate', [R_NPU, R_GPU])
@pytest.mark.parametrize('slack', [1.0, 1.5, 2.0, 3.0])
def test_bg_work_conserved_and_deadlines_follow_slack(rate, slack):
    s = scenario_reg1(7, slack, 0.2, rate)
    bg = [r for r in s['requests'] if r['cls'] == 'BG']
    for k, t0 in enumerate(s['burst_starts_s']):
        chunk = [r for r in bg if r['burst'] == k]
        assert sum(r['n_inf'] for r in chunk) == s['burst_work_inf'] == int(round(300.0 * rate))
        assert all(abs(r['deadline_s'] - (t0 + slack * 300.0)) < 1e-5 for r in chunk)
        assert all(r['arrival_s'] >= t0 - 1e-6 for r in chunk)     # arrival rounded to 6 decimals
    assert abs(s['horizon_s'] - (max(r['deadline_s'] for r in bg) + 300.0)) < 1e-5


@pytest.mark.parametrize('slack', [1.0, 3.0])
def test_load_ordering_mean_below_sustained_below_burst(slack):
    s = scenario_reg1(3, slack, 0.5, R_GPU)
    assert s['avg_bg_load_d100'] < 1 / 2.06 < 1.0     # GPU sustained ~0.49 (MobileNet v2.1 depth) < burst = 1.0
    assert s['avg_bg_load_d100'] < 1 / 1.19            # NPU sustained ~0.84


def test_fg_poisson_count_and_deadline():
    s = scenario_reg1(5, 2.0, 0.5, R_NPU)
    fg = [r for r in s['requests'] if r['cls'] == 'FG']
    exp = 0.5 * s['horizon_s']
    assert abs(len(fg) - exp) < 4 * exp ** 0.5
    assert all(abs(r['deadline_s'] - r['arrival_s'] - 1.5) < 1e-5 and r['n_inf'] == 1 for r in fg)
    assert len({r['id'] for r in s['requests']}) == len(s['requests'])


@pytest.mark.parametrize('kw', [dict(slack=0.0), dict(rate_d100=0.0), dict(n_bursts=0)])
def test_bad_arguments_rejected(kw):
    args = dict(seed=1, slack=2.0, lam_fg=0.5, rate_d100=R_NPU)
    args.update(kw)
    with pytest.raises(ValueError):
        scenario_reg1(**args)
