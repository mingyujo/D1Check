"""Policy comparison v2 harness (sim/정책비교_사전등록_v2.md §11): the boundary selftest must be all PASS."""
from d1sim.policy_eval_v2 import run_eval, selftest


def test_selftest_all_pass():
    res = selftest.checks()
    bad = [n for n, ok, _ in res if not ok]
    assert not bad, bad
    assert len(res) >= 45


def test_grid_24_conditions():
    c = run_eval.conditions()
    assert len(c) == 24
    assert sum(1 for x in c if x['res'] == 'NPU') == 16 and sum(1 for x in c if x['res'] == 'GPU') == 8
    assert {x['residue'] for x in c if x['res'] == 'GPU'} == {'R0'}
    assert run_eval.DEV_SEEDS == tuple(range(1, 11)) and run_eval.HOLDOUT_SEEDS == tuple(range(51, 61))
