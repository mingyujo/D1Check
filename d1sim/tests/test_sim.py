"""Step-3 tests: determinism, masks, throttle monotonicity, conservation (both directions), policy read-only,
env <-> frozen throttle model consistency, S0 thermal sanity. Run: py -m pytest d1sim/tests -q"""
import copy
import json

import pytest

from d1sim.env import Sim, freeze
from d1sim.kpi import conservation, kpis
from d1sim.policies import Fixed, NpuManagerApprox, OursV0, ShortestLatency
from d1sim.profile import Profile
from d1sim.throttle import simulate_continuous
from d1sim.workload import scenario

P = Profile()
TTH = P.throttle_gpu['T_th']


def small(sc='S1', seed=3, horizon=120.0, **kw):
    return scenario(sc, seed, P, horizon=horizon, **kw)


def run(reqs, pol, horizon=120.0, **v):
    return Sim(P, reqs, v, horizon=horizon).run(pol)


# ---------- determinism ----------
@pytest.mark.parametrize('sc', ['S0', 'S1', 'S2'])
def test_same_seed_same_result(sc):
    a = kpis(run(small(sc), OursV0(T_th=TTH)))
    b = kpis(run(small(sc), OursV0(T_th=TTH)))
    assert a == b
    assert small(sc, seed=3) == small(sc, seed=3)
    assert small(sc, seed=3) != small(sc, seed=4)


# ---------- profile / masks ----------
def test_int8_masked_not_zero():
    assert P.raw['quality']['INT8']['value'] is None
    assert not P.supported('NPU', 'INT8')
    reqs = [dict(r, min_tier='INT8') for r in small('S0')[:3]]
    with pytest.raises(ValueError, match='masked'):
        run(reqs, Fixed('NPU'))


def test_placeholders_listed_with_status():
    ph = {k: v for k, v, _ in P.placeholders()}
    assert 'throttle.NPU.params' in ph and ph['throttle.NPU.params'] is None
    assert 'limits.battery_budget_j' in ph


# ---------- throttle ----------
def test_env_matches_frozen_throttle_model():
    """A continuous GPU job in the env follows throttle.simulate_continuous (same equations, dt 0.5)."""
    reqs = [dict(id=0, arrival_s=0.0, deadline_s=1e9, weight=1, min_tier='FP32', model='m', cls='BG', n_inf=10 ** 7)]
    sim = Sim(P, reqs, {}, horizon=300.0)
    sim.loaded = 'GPU'
    rec = sim.run(Fixed('GPU'))
    ref = simulate_continuous(P.throttle_gpu, P.t_start, 300.5, dt=0.5)
    ref_T = {round(x['t'], 6): x['T'] for x in ref}
    checked = 0
    for t, skin, *_ in rec.trace:
        if round(t, 6) in ref_T:
            assert abs(skin - ref_T[round(t, 6)]) < 1e-9
            checked += 1
    assert checked > 250
    assert rec.exec_s['GPU'] > 299.0


def test_throttle_monotone_longer_load_slower():
    means = []
    for dur in (30, 60, 120, 300):
        rows = simulate_continuous(P.throttle_gpu, P.t_start, dur)
        means.append(sum(1 / r['s'] for r in rows) / len(rows))
    assert all(b >= a - 1e-12 for a, b in zip(means, means[1:]))
    assert means[-1] > 1.1 and abs(means[0] - 1.0) < 1e-9


def test_s0_heat_does_not_change_results():
    reqs = small('S0', horizon=600.0)
    for pol in (Fixed('GPU'), Fixed('NPU'), NpuManagerApprox(), ShortestLatency(), OursV0(T_th=TTH)):
        on = kpis(run(reqs, copy.deepcopy(pol), horizon=600.0))
        off = kpis(run(reqs, copy.deepcopy(pol), horizon=600.0, throttle=False))
        for k in ('fg_p95_s', 'fg_p50_s', 'weighted_tardiness', 'deadline_violation_rate', 'throughput_inf_s'):
            assert on[k] == off[k], (pol.name, k)
        assert on['throttle_s_GPU'] == 0 and on['throttle_s_NPU'] == 0 and on['throttle_s_CPU4'] == 0


# ---------- conservation: holds on real runs ----------
@pytest.mark.parametrize('sc', ['S0', 'S1', 'S2'])
@pytest.mark.parametrize('v', [{}, {'npu_cpu_throttle': 'scaled', 'coupling': 'shared', 'recovery': 'slow',
                                    'status_model': 'hal40'}])
def test_conservation_holds(sc, v):
    for pol in (Fixed('GPU'), NpuManagerApprox(), OursV0(T_th=TTH), ShortestLatency()):
        rec = run(small(sc), pol, **v)
        assert conservation(rec) == [], (sc, pol.name)


# ---------- conservation: checker catches broken records ----------
def _rec():
    return run(small('S1'), NpuManagerApprox())


def test_checker_passes_clean_record():
    assert conservation(_rec()) == []


def test_checker_catches_start_before_arrival():
    rec = _rec()
    i = next(k for k, r in rec.requests.items() if r['status'] == 'done' and r['arrival_s'] > 0.01)
    rec.requests[i]['start'] = rec.requests[i]['arrival_s'] - 0.01
    assert any('start<arrival' in b for b in conservation(rec))


def test_checker_catches_missing_request():
    rec = _rec()
    i = next(k for k, r in rec.requests.items() if r['status'] == 'done')
    rec.requests[i]['status'] = 'lost'
    assert any('arrivals' in b for b in conservation(rec))


def test_checker_catches_missing_energy_segment():
    rec = _rec()
    del rec.energy[len(rec.energy) // 2]
    assert any('energy' in b for b in conservation(rec))


def test_checker_catches_response_mismatch():
    rec = _rec()
    i = next(k for k, r in rec.requests.items() if r['status'] == 'done')
    rec.requests[i]['exec_s'] += 0.5
    assert any('response' in b for b in conservation(rec))


def test_checker_catches_overlap():
    rec = _rec()
    a, b = rec.busy['NPU'][0], rec.busy['NPU'][1]
    rec.busy['NPU'][1] = (a[0], b[1])
    assert any('concurrent' in x or 'global' in x for x in conservation(rec))


def test_checker_catches_throttle_over_exec():
    rec = _rec()
    rec.throttle_s['NPU'] = rec.exec_s['NPU'] + 1.0
    assert any('throttle_s' in x for x in conservation(rec))


# ---------- policies are read-only ----------
class Mutator:
    name = 'mutator'

    def __init__(self, what):
        self.what = what

    def decide(self, obs):
        if self.what == 'queue':
            obs['queue'][0]['deadline_s'] = 1e9
        elif self.what == 'obs':
            obs['status'] = 0
        elif self.what == 'thermal':
            obs['s']['GPU'] = 1.0
        return ('dispatch', obs['queue'][0]['id'], 'NPU')


@pytest.mark.parametrize('what', ['queue', 'obs', 'thermal'])
def test_policy_cannot_mutate_state(what):
    with pytest.raises(TypeError):
        run(small('S0'), Mutator(what))


def test_predict_is_pure():
    sim = Sim(P, small('S1'), {'npu_cpu_throttle': 'scaled'}, horizon=120.0)
    sim.run(Fixed('NPU'))
    before = json.dumps(sim.th.H) + json.dumps(sim.th.s_hold)
    obs = sim.snapshot()
    for r in ('GPU', 'NPU', 'CPU4'):
        obs['predict'](r, 50000, t_delay=5.0)
    assert json.dumps(sim.th.H) + json.dumps(sim.th.s_hold) == before


def test_policy_decision_does_not_change_state():
    """A normal policy call on a snapshot leaves the simulator state unchanged (the 'must pass' direction)."""
    sim = Sim(P, small('S1'), {}, horizon=60.0)
    sim.run(NpuManagerApprox())
    digest = (json.dumps(sim.th.H), len(sim.rec.energy), sim.rec.energy_j, sim.t)
    sim.queue = [freeze(r) for r in small('S1')[:5]]
    OursV0(T_th=TTH).decide(sim.snapshot())
    assert (json.dumps(sim.th.H), len(sim.rec.energy), sim.rec.energy_j, sim.t) == digest
