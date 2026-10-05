"""v2.1 tests (P1d 3-2): v1 AND v2 paths frozen (byte-identical outputs + profile hashes; v0 stays covered by test_v1.py), v2.1 delegates
to v2 unchanged when no v2.1 feature is on, body initial condition (SKIN(0) kept, cold body heats slower), fast thermal loop == class,
conservation (energy = sum P x dt, one resource at a time, ratio >= 1), release in BOTH directions (same temperature: d10 releases,
a deep step at d50 holds; V21-F: d10 cools the fast node and releases, d100 holds) and a deliberately broken state fails the checker.
Run: py -m pytest d1sim/tests -q"""
import hashlib
import json
import math
import os

import pytest

from d1sim import throttle_v1 as tv1
from d1sim import throttle_v2 as tv2
from d1sim import throttle_v21 as tv21
from d1sim.tests.test_v2 import V1_DIGEST_GPU, V1_DIGEST_NPU, digest, v2_params
from d1sim.tools.predict_night_1003 import duty_flags, params as v1_params

HERE = os.path.dirname(__file__)
PROFILES = os.path.join(HERE, '..', 'profiles')
# computed 2026-10-05 14:2x from the frozen v2 (42338e7) module + profiles, BEFORE any v2.1 profile existed
V2_DIGEST_NPU = '89699a2b2af49564b7c69f82a0904f62162c48a6786e592627c0983057e52dfc'
V2_DIGEST_GPU = '8a51cba74a48eb7e0c6c752303c2840c053531f376bfed0cb2102c698fff8ab9'
V2_DIGEST_N50_T075 = '433940eede23078b1fbf01dab18e100d276b30529fe50b40bc661a0ab4d4276e'
V2_PROFILE_SHA = {
    'throttle_v2_CPU4_interpreter.json': '051d1a995fe6860f104f7d0d12be4e302e28a9afda5c42348a52f91e7d201d9a',
    'throttle_v2_GPU_compiledmodel.json': '827bb50abebc5e4220028d5246b5b194fa97965711c4c3facb0cd1f5b1d11f24',
    'throttle_v2_GPU_interpreter.json': '3a4c780ee52b4d79de5ebc8dc8e9481bac4e88148da40558dedfb66ae3767507',
    'throttle_v2_NPU.json': '234e0df63aabc2f78997f92ca24c9081a76470bac7c5bb0cbe4b3ba2c9b9ee9d',
    'throttle_v2_thermal.json': 'ad10f9affd441f54e6de28c8ad44073eb6fcaf22081ba3d6a3f241a294101cdb',
}
SCH_NPU = [(0, 'NPU', duty_flags(10, 60), 60), (1, 'NPU', True, 600), (2, 'NPU', duty_flags(10, 600), 600)]
SCH_GPU = [(0, 'GPU', duty_flags(10, 60), 60), (1, 'GPU', True, 1200), (2, 'GPU', duty_flags(10, 300), 300)]
SCH_N50 = [(0, 'NPU', duty_flags(50, 60), 60), (1, 'NPU', True, 420), (2, 'NPU', duty_flags(50, 480), 480)]


def ht_params(form='Ht', kappa=1.0):
    p = v2_params()
    p['ctrl'] = dict(p['ctrl'])
    p['ctrl']['NPU'] = dict(form=form, sensor='SKIN', d_on=10.0, theta_low=0.3, T1=38.0, T2=40.0, T3=42.0, a1=0.09, a2=0.035, a3=0.068,
                            h=0.5, kappa=kappa, tau_F=20.0, g_F=0.3)
    p['ctrl']['GPU'] = dict(form=form, sensor='SKIN', d_on=10.0, theta_low=0.3, T_on=37.2, kappa=kappa, h=0.3, W=1.2, D=1.2, tau_F=20.0, g_F=0.3)
    p['ctrl']['CPU4'] = dict(p['ctrl']['CPU4'], v1_controller=True)
    p['thermal'] = dict(p['thermal'], k_b=1.0, d_ref=2.0)
    return p


# ---------- v1 · v2 paths frozen ----------
def test_v1_path_byte_identical_v21():
    p = v1_params()
    assert digest(tv1.simulate(p, SCH_NPU, 29.5, -1.0)) == V1_DIGEST_NPU
    assert digest(tv1.simulate(p, SCH_GPU, 30.5, -1.0)) == V1_DIGEST_GPU


def test_v2_path_byte_identical():
    p = v2_params()
    assert digest(tv2.simulate(p, SCH_NPU, 29.5, -1.0)) == V2_DIGEST_NPU
    assert digest(tv2.simulate(p, SCH_GPU, 30.5, -1.0)) == V2_DIGEST_GPU
    pp = dict(p, ctrl=dict(p['ctrl'], NPU=dict(p['ctrl']['NPU'], theta=0.75)))
    assert digest(tv2.simulate(pp, SCH_N50, 30.5, -1.0)) == V2_DIGEST_N50_T075


def test_v2_profiles_unchanged():
    for fn, sha in V2_PROFILE_SHA.items():
        assert hashlib.sha256(open(os.path.join(PROFILES, fn), 'rb').read()).hexdigest() == sha, fn


def test_v21_simulate_equals_v2_without_v21_features():
    """v2 controllers + no body init (B0 None) through throttle_v21.simulate -> the same bytes as throttle_v2.simulate."""
    p = v2_params()
    assert digest(tv21.simulate(p, SCH_NPU, 29.5, -1.0, None)) == V2_DIGEST_NPU
    assert digest(tv21.simulate(p, SCH_GPU, 30.5, -1.0, None)) == V2_DIGEST_GPU
    pk = dict(p, thermal=dict(p['thermal'], k_b=0.0, d_ref=2.0))       # k_b = 0 -> body term off even with B0 given
    assert digest(tv21.simulate(pk, SCH_NPU, 29.5, -1.0, 27.0)) == V2_DIGEST_NPU


# ---------- body initial condition ----------
def test_body_init_keeps_skin0_and_cold_body_heats_slower():
    tp = ht_params()['thermal']
    warm = tv21.ThermalV21(tp, 30.0, -1.0, 28.0)        # z = 0
    cold = tv21.ThermalV21(tp, 30.0, -1.0, 26.0)        # z = +2 (body colder than usual)
    assert warm.skin == pytest.approx(30.0) and cold.skin == pytest.approx(30.0)
    assert warm.ap == pytest.approx(29.0) and cold.ap == pytest.approx(29.0)
    for _ in range(300):
        warm.advance(1.0, 6.0, 'NPU'); cold.advance(1.0, 6.0, 'NPU')
    assert cold.skin < warm.skin - 0.3
    none = tv21.ThermalV21(tp, 30.0, -1.0, None)
    ref = tv2.ThermalV2({k: v for k, v in tp.items() if k not in ('k_b', 'd_ref')}, 30.0, -1.0)
    for _ in range(200):
        none.advance(1.0, 5.0, 'GPU'); ref.advance(1.0, 5.0, 'GPU')
    assert none.skin == ref.skin and none.ap == ref.ap


def test_fast_thermal_series_equals_class():
    tp = dict(ht_params()['thermal'], G_a={'GPU': 1.2, 'NPU': 1.1, 'CPU4': 1.6})
    P = [1.0 + 5.0 * (0.5 + 0.5 * math.sin(i / 37.0)) for i in range(900)]
    res = ['NPU' if (i // 100) % 2 else 'GPU' for i in range(900)]
    sk, ap = tv21.thermal_series(tp, P, res, 30.0, -1.0, 27.5)
    th = tv21.ThermalV21(tp, 30.0, -1.0, 27.5)
    for i, (p, r) in enumerate(zip(P, res)):
        assert sk[i] == pytest.approx(th.skin, abs=1e-12) and ap[i] == pytest.approx(th.ap, abs=1e-12)
        th.advance(1.0, p, r)


# ---------- conservation ----------
def _check(rows, params):
    """Invariants a v2.1 run must satisfy (returns list of violations)."""
    bad = []
    pi = params['thermal']['P_idle']
    for r in rows:
        if r['ex'] and r['ratio'] is not None and r['ratio'] < 1.0 - 1e-12:
            bad.append(('ratio<1', r['seg'], r['t']))
        if (not r['ex']) and abs(r['P'] - pi) > 1e-12:
            bad.append(('idle power', r['seg'], r['t']))
        if r['ex'] and r['P'] < pi - 1e-12:
            bad.append(('power<idle', r['seg'], r['t']))
    return bad


@pytest.mark.parametrize('form', ['Ht', 'F'])
def test_conservation_holds_chain_v21(form):
    p = ht_params(form)
    sch = [(0, 'NPU', duty_flags(50, 60), 60), (1, 'NPU', True, 420), ('t2', None, None, 2), (2, 'GPU', duty_flags(50, 480), 480)]
    rows = tv21.simulate(p, sch, 30.0, -1.0, 28.5)
    assert _check(rows, p) == []
    energy = sum(r['P'] for r in rows)
    assert energy == pytest.approx(sum(r['P'] * 1.0 for r in rows))
    assert len(rows) == 60 + 420 + 2 + 480
    assert all(r['res'] in ('NPU', 'GPU', None) for r in rows)


def test_checker_catches_broken_rows_v21():
    p = ht_params()
    rows = tv21.simulate(p, [(0, 'NPU', True, 30)], 30.0, -1.0, 28.0)
    broken = [dict(r) for r in rows]
    broken[5]['ratio'] = 0.9
    broken[6]['ex'] = False
    assert len(_check(broken, p)) >= 2


# ---------- release in both directions (same temperature) ----------
class _Fixed:
    def __init__(self, T):
        self.skin = self.ap = T


def _run_gate(cp, res, T, flags_before, flags_after):
    """Arm at d100 for 60 s at temperature T, then continue with `flags_after`; return armed state per second after the switch."""
    c = tv21.NpuV21(cp) if res == 'NPU' else tv21.GpuV21(cp)
    th = _Fixed(T)
    win = []
    for f in flags_before:
        win = (win + [1 if f else 0])[-10:]
        c.fast_advance(1.0, 4.0 if f else 0.0, f)
        c.step(1.0, th, f, True, sum(win) / 10.0)
    armed0 = c.level if res == 'NPU' else c.armed
    out = []
    for f in flags_after:
        win = (win + [1 if f else 0])[-10:]
        c.fast_advance(1.0, 4.0 if f else 0.0, f)
        c.step(1.0, th, f, True, sum(win) / 10.0)
        out.append(c.level if res == 'NPU' else c.armed)
    return armed0, out


@pytest.mark.parametrize('res', ['NPU', 'GPU'])
def test_same_temperature_d10_releases_d50_deep_step_holds(res):
    cp = ht_params('Ht', kappa=1.0)['ctrl'][res]
    T = 41.0      # above T2 + kappa*0.5 - h (NPU) and above T_on + kappa*0.5 - h (GPU): deep, hot
    a0, d10 = _run_gate(cp, res, T, [True] * 60, duty_flags(10, 60))
    assert a0 and (d10[-1] == 0 or d10[-1] is False)          # d10: released (u <= theta_low)
    assert next(i for i, x in enumerate(d10) if not x) <= 12
    a0, d50 = _run_gate(cp, res, T, [True] * 60, duty_flags(50, 120))
    assert a0 and all(bool(x) for x in d50)                    # d50 at the same temperature: holds
    if res == 'NPU':
        assert min(d50) >= 2                                   # deep step kept


def test_ht_d50_releases_when_cooler():
    """Shallow step at d50: stays while T >= thr(0.5) - h, releases once T falls below it (the ⑭ direction)."""
    cp = ht_params('Ht', kappa=1.0)['ctrl']['NPU']
    a0, d50 = _run_gate(cp, 'NPU', 38.2, [True] * 60, duty_flags(50, 60))    # d50 thr(0.5) = 38.5 -> release below 38.0
    assert a0 == 1 and all(x == 1 for x in d50)                             # 38.2 >= 38.0 -> holds
    c = tv21.NpuV21(cp)
    th = _Fixed(38.2)
    for _ in range(20):
        c.step(1.0, th, True, True, 1.0)
    assert c.level == 1
    th.skin = th.ap = 37.9
    c.step(1.0, th, True, True, 0.5)
    assert c.level == 0


def test_f_form_d10_cools_fast_node_and_releases_d100_holds():
    cp = ht_params('F')['ctrl']['NPU']
    cp = dict(cp, T1=40.0, T2=41.0, T3=60.0, h=0.4, g_F=0.5, tau_F=10.0)     # d100 at P-Pidle 4 W -> F -> 2.0 C
    a0, d10 = _run_gate(cp, 'NPU', 39.2, [True] * 120, duty_flags(10, 60))   # T_drv -> 41.2 at d100 -> 2 steps
    assert a0 == 2 and d10[-1] == 0
    a0, d100 = _run_gate(cp, 'NPU', 39.2, [True] * 120, [True] * 60)
    assert a0 == 2 and all(x == 2 for x in d100)


def test_broken_release_state_is_detected():
    """A gate that stays armed while u <= theta_low violates the Htheta rule — the checker below must flag it."""
    cp = ht_params('Ht')['ctrl']['GPU']

    def violates(c, u):
        return c.armed and u <= cp['theta_low']
    c = tv21.GpuV21(cp)
    th = _Fixed(39.0)
    for _ in range(20):
        c.step(1.0, th, True, True, 1.0)
    assert c.armed
    c.step(1.0, th, False, True, 0.1)
    assert not violates(c, 0.1)
    c.gate.armed = True               # deliberately broken
    assert violates(c, 0.1)


def test_v21_profiles_load_if_present():
    fn = os.path.join(PROFILES, 'throttle_v21_thermal.json')
    if not os.path.exists(fn):
        pytest.skip('v2.1 profiles not written yet')
    tp = json.load(open(fn, encoding='utf-8'))
    for k in ('G_f', 'G_s', 'tau_s', 'c_f', 'c_s', 'c_a', 'k_b', 'd_ref'):
        assert k in tp
    for fn in ('NPU', 'GPU_compiledmodel', 'GPU_interpreter'):
        d = json.load(open(os.path.join(PROFILES, f'throttle_v21_{fn}.json'), encoding='utf-8'))
        assert d['ctrl']['form'] in ('Ht', 'F')
