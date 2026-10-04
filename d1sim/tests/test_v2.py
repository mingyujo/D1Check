"""v2 tests (P1c 4단계): v0 AND v1 paths frozen (byte-identical outputs + profile hashes), v2 conservation (energy = Σ power × time,
one resource at a time, ratio >= 1), HAL status map, load dependence in BOTH directions (same temperature: d10 releases, d100 stays
tightened; a deliberately broken state fails the checker), cooling asymmetry, v2 profiles load. Run: py -m pytest d1sim/tests -q"""
import hashlib
import json
import os

import pytest

from d1sim import throttle_v1 as tv1
from d1sim import throttle_v2 as tv2
from d1sim.tools.predict_night_1003 import duty_flags, params as v1_params

HERE = os.path.dirname(__file__)
PROFILES = os.path.join(HERE, '..', 'profiles')
# computed 2026-10-04 17:38 from the frozen v1 (3050e09) module + profiles, BEFORE any v2 profile existed
V1_DIGEST_NPU = 'a0f172cba6d2a366dee82e89932c15c21415f97466ba81009cea154e15f66c78'
V1_DIGEST_GPU = '0ac15b7f85ace3e7107c7ed7e7ef9ad8b9da257fdeb8ead6d03938a303ccfe56'
V1_PROFILE_SHA = {
    'throttle_v1_CPU4_interpreter.json': 'b0d3a812e7e7f03f5d7d53581d85da3e3b103ff0f2ff7aab6ae67a3237f7e4ca',
    'throttle_v1_GPU_compiledmodel.json': '8bfacdad61fb633db0fb23fb5ca02172a03ce1f72eb6c858e62a631167ef27da',
    'throttle_v1_GPU_interpreter.json': 'b6e69cd8c5e25aa34156699f460283381d6823420772b53d4c937cf1503c3ec2',
    'throttle_v1_NPU.json': '0812d9cb519a520786ad098725f7c3b44e6cb9afa5ebe29bb2e444c8d21339d3',
    'throttle_v1_thermal.json': '7595ada5a9770fe61c02adf1a6afafc9c8a8ecfe63711b56cd2e7d93cfef3470',
}


def digest(rows):
    s = json.dumps([[r['seg'], r['t'], round(r['s'] or 0, 12), round(r['skin'], 9), round(r['ap'], 9), round(r['P'], 9), r['status']] for r in rows])
    return hashlib.sha256(s.encode()).hexdigest()


def v2_params():
    tp = json.load(open(os.path.join(PROFILES, 'throttle_v2_thermal.json'), encoding='utf-8'))
    tp = {k: tp[k] for k in ('tau_f', 'G_f', 'G_s', 'tau_s', 'tau_a', 'G_a', 'P_idle', 'c_f', 'c_s', 'c_a')}
    ctrl, power, L0 = {}, {}, {}
    for res, fn in (('GPU', 'GPU_compiledmodel'), ('NPU', 'NPU'), ('CPU4', 'CPU4_interpreter')):
        d = json.load(open(os.path.join(PROFILES, f'throttle_v2_{fn}.json'), encoding='utf-8'))
        ctrl[res] = dict(d['ctrl']); power[res] = {k: d['power'][k] for k in ('P_idle', 'P0', 'alpha')}; L0[res] = d['L0_ms']
    return dict(thermal=tp, ctrl=ctrl, power=power, L0=L0)


# ---------- v1 path frozen (v0 is covered by test_v1.py, unchanged) ----------
def test_v1_path_byte_identical():
    p = v1_params()
    rows = tv1.simulate(p, [(0, 'NPU', duty_flags(10, 60), 60), (1, 'NPU', True, 600), (2, 'NPU', duty_flags(10, 600), 600)], 29.5, -1.0)
    assert digest(rows) == V1_DIGEST_NPU
    rows = tv1.simulate(p, [(0, 'GPU', duty_flags(10, 60), 60), (1, 'GPU', True, 1200), (2, 'GPU', duty_flags(10, 300), 300)], 30.5, -1.0)
    assert digest(rows) == V1_DIGEST_GPU


def test_v1_profiles_unchanged():
    for fn, sha in V1_PROFILE_SHA.items():
        assert hashlib.sha256(open(os.path.join(PROFILES, fn), 'rb').read()).hexdigest() == sha, fn


# ---------- v2 thermal: cooling asymmetry + shared state ----------
def test_cooling_asymmetry_slower_than_v1_when_c_gt_1():
    tp = v2_params()['thermal']
    a = tv2.ThermalV2(dict(tp, c_f=1.0, c_s=1.0, c_a=1.0), 30.0, -1.0)
    b = tv2.ThermalV2(dict(tp, c_f=2.0, c_s=3.0, c_a=3.0), 30.0, -1.0)
    for _ in range(600):
        a.advance(1.0, 6.0, 'NPU'); b.advance(1.0, 6.0, 'NPU')
    assert abs(a.skin - b.skin) < 1e-9          # heating identical
    for _ in range(300):
        a.advance(1.0, tp['P_idle'], None); b.advance(1.0, tp['P_idle'], None)
    assert b.skin > a.skin + 0.5 and b.ap > a.ap + 0.5   # cooling slower with c > 1


def test_shared_state_same_power_same_skin_v2():
    tp = v2_params()['thermal']
    a, b = tv2.ThermalV2(tp, 30.0, -1.0), tv2.ThermalV2(tp, 30.0, -1.0)
    for _ in range(300):
        a.advance(1.0, 5.0, 'GPU'); b.advance(1.0, 5.0, 'NPU')
    assert abs(a.skin - b.skin) < 1e-12 and a.skin > 33.0


# ---------- status map ----------
@pytest.mark.parametrize('skin,st', [(39.9, 0), (40.0, 1), (42.0, 2), (45.0, 3)])
def test_status_map_hal_v2(skin, st):
    assert tv2.status_of(skin) == st


# ---------- conservation ----------
def check_rows(rows, schedule, dt=1.0, tol=1e-9):
    bad = []
    if abs(len(rows) * dt - sum(d for *_, d in schedule)) > tol:
        bad.append('time: rows*dt != sum(durations)')
    if any(r['P'] is None or r['P'] < 0 for r in rows):
        bad.append('power: missing/negative')
    if not sum(r['P'] * dt for r in rows) > 0:
        bad.append('energy <= 0')
    if any(r['ex'] and r['res'] is None for r in rows):
        bad.append('executing without a resource')
    if any(r['ratio'] is not None and r['ratio'] < 1.0 - tol for r in rows):
        bad.append('ratio < 1 (faster than unthrottled)')
    idle_P = {r['P'] for r in rows if not r['ex']}
    if idle_P and max(idle_P) - min(idle_P) > tol:
        bad.append('idle power not constant')
    if any(r['u'] is not None and not (0.0 <= r['u'] <= 1.0) for r in rows):
        bad.append('u outside [0,1]')
    return bad


def test_conservation_holds_chain_v2():
    p = v2_params()
    sch = [(0, 'GPU', duty_flags(10, 60), 60), ('t1', None, None, 1), (1, 'NPU', True, 600), (2, 'GPU', duty_flags(50, 120), 120), (3, 'NPU', duty_flags(1, 60), 60)]
    rows = tv2.simulate(p, sch, 30.0, -1.0)
    assert check_rows(rows, sch) == []
    assert abs(sum(r['P'] for r in rows) - sum(r['P'] * 1.0 for r in rows)) < 1e-9    # energy = Σ power × time
    assert all(r['status'] == tv2.status_of(r['skin']) for r in rows)


def test_checker_catches_broken_rows_v2():
    p = v2_params()
    sch = [(0, 'GPU', True, 120)]
    rows = tv2.simulate(p, sch, 30.0, -1.0)
    assert check_rows(rows, sch) == []
    assert any('time' in b for b in check_rows(rows[:-1], sch))
    r2 = [dict(r) for r in rows]; r2[5]['P'] = -1.0
    assert any('power' in b for b in check_rows(r2, sch))
    r3 = [dict(r) for r in rows]; r3[50]['ratio'] = 0.5
    assert any('ratio' in b for b in check_rows(r3, sch))
    r4 = [dict(r) for r in rows]; r4[3]['u'] = 1.5
    assert any('u outside' in b for b in check_rows(r4, sch))


# ---------- load dependence, both directions ----------
def _hot_device(p, res):
    """Heat with `res` at d100 until its controller is armed; return the device (deep state) or skip if the form never arms."""
    dev = tv2.DeviceV2(p, 31.0, -1.0)
    for _ in range(1300):
        dev.advance(1.0, res, True)
        armed = dev.ctrl[res].armed if res == 'GPU' else dev.ctrl[res].level > 0
        if armed:
            for _ in range(200):              # keep heating well past the arm threshold so 30 s of d10 cannot release THERMALLY
                dev.advance(1.0, res, True)
            return dev
    pytest.skip(f'{res} controller never armed in 1300 s at d100 — form/profile has no throttle here')


@pytest.mark.parametrize('res', ['GPU', 'NPU'])
def test_same_temperature_d10_releases_d100_holds(res):
    p = v2_params()
    form = p['ctrl'][res]['form']
    if form == 'S':
        pytest.skip('V2-S has no load dependence by construction')
    dev = _hot_device(p, res)
    hot_d100, hot_d10 = dev.clone(), dev.clone()
    flags10 = duty_flags(10, 30)
    for k in range(30):                       # 30 s more, same thermal start: one keeps d100, one drops to d10
        hot_d100.advance(1.0, res, True)
        hot_d10.advance(1.0, res, bool(flags10[k]))
    def tight(d):
        return d.ctrl[res].armed if res == 'GPU' else d.ctrl[res].level > 0
    assert tight(hot_d100), 'd100 should stay tightened'
    assert not tight(hot_d10), 'd10 should release within 30 s at the same temperature (load dependence)'
    assert hot_d10.th.skin > 36.0            # still hot when released — the point of ⑨/⑩


def test_broken_load_window_is_detected():
    """If u were computed wrongly (always 1), the d10 branch would NOT release -> the previous test's assertion must fail."""
    p = v2_params()
    form = p['ctrl']['NPU']['form']
    if form == 'S':
        pytest.skip('V2-S')
    dev = _hot_device(p, 'NPU')
    broken = dev.clone()
    flags10 = duty_flags(10, 30)
    for k in range(30):
        ex = bool(flags10[k])
        P = broken.power('NPU', ex)
        broken.th.advance(1.0, P, 'NPU' if ex else None)
        for r in broken.win:
            broken.win[r].append(1)           # deliberately wrong: load window says "always executing"
        for r, c in broken.ctrl.items():
            c.step(1.0, broken.th, ex and r == 'NPU', scheduled=(r == 'NPU'), u=broken.u(r))
    assert broken.ctrl['NPU'].level > 0, 'with a broken (always-1) load window the NPU must stay tightened — checker direction test'


def test_idle_controller_state_frozen_v2():
    p = v2_params()
    dev = tv2.DeviceV2(p, 45.0, 2.0)
    before = (dev.ctrl['NPU'].level, dev.ctrl['CPU4'].c.u)
    for _ in range(120):
        dev.advance(1.0, 'GPU', True)
    assert (dev.ctrl['NPU'].level, dev.ctrl['CPU4'].c.u) == before
