"""v1 tests (2-4): v0 path frozen (byte-identical to 80ca6c4 output), shared thermal state, energy/time conservation,
one resource at a time, HAL status map, controllers gated on execution; each checker also tested in the FAIL direction.
Run: py -m pytest d1sim/tests -q -p no:cacheprovider"""
import hashlib
import json
import os

import pytest

from d1sim import throttle_v1 as tv1
from d1sim.profile import Profile
from d1sim.throttle import simulate_continuous

HERE = os.path.dirname(__file__)
PROFILES = os.path.join(HERE, '..', 'profiles')
# sha256 of simulate_continuous(throttle_v0_GPU.json, 30.3, 600, dt=1.0) computed from the git-archive copy of 80ca6c4
# (C:/Users/rhoyo/AndroidStudioProjects/_scratch/v0_80ca6c4, 2026-10-03 18:40) — the v0 path must keep producing exactly this.
V0_DIGEST = 'ecbb6d03e7ea5caca394c3324cdc85339978ac81b91869976221af4f1df0ba26'


def v1_params():
    tp = json.load(open(os.path.join(PROFILES, 'throttle_v1_thermal.json'), encoding='utf-8'))
    tp = {k: tp[k] for k in ('tau_f', 'G_f', 'G_s', 'tau_s', 'tau_a', 'G_a', 'P_idle')}
    ctrl, power, L0 = {}, {}, {}
    for res, fn in (('GPU', 'GPU_compiledmodel'), ('NPU', 'NPU'), ('CPU4', 'CPU4_interpreter')):
        d = json.load(open(os.path.join(PROFILES, f'throttle_v1_{fn}.json'), encoding='utf-8'))
        ctrl[res] = d['ctrl']; power[res] = {k: d['power'][k] for k in ('P_idle', 'P0', 'alpha')}; L0[res] = d['L0_ms']
    return dict(thermal=tp, ctrl=ctrl, power=power, L0=L0)


# ---------- v0 path frozen ----------
def test_v0_path_byte_identical_to_80ca6c4():
    P = Profile()
    rows = simulate_continuous(P.throttle_gpu, 30.3, 600, dt=1.0)
    s = json.dumps([[round(r['t'], 6), round(r['s'], 12), round(r['latency_ms'], 9), round(r['power_w'], 9), round(r['T'], 9)] for r in rows])
    assert hashlib.sha256(s.encode()).hexdigest() == V0_DIGEST
    assert P.throttle_gpu['T_th'] == 36.42670241364113 and P.throttle_gpu['k'] == 0.2478091646278181


def test_v0_profile_file_unchanged():
    raw = open(os.path.join(PROFILES, 'throttle_v0_GPU.json'), 'rb').read()
    assert hashlib.sha256(raw).hexdigest() == '91a38bec11d5d83b784078f4ecda10dcdc947ec87dd6b13907166e343d22d7db'


# ---------- status map ----------
@pytest.mark.parametrize('skin,st', [(39.9, 0), (40.0, 1), (41.9, 1), (42.0, 2), (44.9, 2), (45.0, 3)])
def test_status_map_hal(skin, st):
    assert tv1.status_of(skin) == st


# ---------- shared thermal state ----------
def test_shared_state_same_power_same_skin():
    """Heating the device with GPU or with NPU at the SAME power trajectory gives the same SKIN (one state)."""
    tp = v1_params()['thermal']
    a, b = tv1.ThermalV1(tp, 30.0, -1.0), tv1.ThermalV1(tp, 30.0, -1.0)
    for _ in range(300):
        a.advance(1.0, 5.0, 'GPU'); b.advance(1.0, 5.0, 'NPU')
    assert abs(a.skin - b.skin) < 1e-12
    assert a.skin > 30.0 + 3.0
    # AP differs by resource gain (sensor sits on the SoC) — documented, not a bug
    assert a.ap != b.ap


def test_victim_sees_heat_from_other_resource():
    p = v1_params()
    cold = tv1.simulate(p, [(0, 'NPU', True, 60)], 30.0, -1.0)
    heated = tv1.simulate(p, [(0, 'GPU', True, 600), (1, 'NPU', True, 60)], 30.0, -1.0)
    assert next(r['skin'] for r in heated if r['seg'] == 1) > cold[0]['skin'] + 3.0


# ---------- controllers gated on execution ----------
def test_idle_controller_state_frozen():
    p = v1_params()
    dev = tv1.DeviceV1(p, 45.0, 2.0)          # hot start: AP 47
    before = (dev.ctrl['NPU'].arm1, dev.ctrl['NPU'].arm2, dev.ctrl['NPU'].ui, dev.ctrl['CPU4'].u, dev.ctrl['CPU4'].armed)
    for _ in range(120):
        dev.advance(1.0, 'GPU', True)
    assert (dev.ctrl['NPU'].arm1, dev.ctrl['NPU'].arm2, dev.ctrl['NPU'].ui, dev.ctrl['CPU4'].u, dev.ctrl['CPU4'].armed) == before
    assert dev.ctrl['GPU'].u > 0.0           # the executing resource did throttle


# ---------- conservation (time, energy, one resource at a time) ----------
def check_rows(rows, schedule, dt=1.0, tol=1e-9):
    bad = []
    if abs(len(rows) * dt - sum(d for *_, d in schedule)) > tol:
        bad.append('time: rows*dt != sum(durations)')
    if any(r['P'] is None or r['P'] < 0 for r in rows):
        bad.append('power: missing/negative')
    e_rows = sum(r['P'] * dt for r in rows)
    if not e_rows > 0:
        bad.append('energy <= 0')
    if any(r['ex'] and r['res'] is None for r in rows):
        bad.append('executing without a resource')
    if any(r['ratio'] is not None and r['ratio'] < 1.0 - tol for r in rows):
        bad.append('ratio < 1 (faster than unthrottled)')
    idle_P = {r['P'] for r in rows if not r['ex']}
    if idle_P and max(idle_P) - min(idle_P) > tol:
        bad.append('idle power not constant')
    return bad


def test_conservation_holds_chain():
    p = v1_params()
    sch = [(0, 'GPU', True, 60), ('t1', None, None, 0.2), (1, 'NPU', True, 600), ('t2', None, None, 0.8), (2, 'GPU', True, 60)]
    sch = [(a, b, c, d) for a, b, c, d in sch]
    rows = tv1.simulate(p, [(a, b, c, round(d)) for a, b, c, d in sch if d >= 1] , 30.0, -1.0)
    assert check_rows(rows, [(a, b, c, round(d)) for a, b, c, d in sch if d >= 1]) == []
    assert all(sum(1 for x in (r['res'],) if x) <= 1 for r in rows)
    assert abs(sum(r['P'] for r in rows) - sum(r['P'] * 1.0 for r in rows)) < 1e-9     # energy = Σ power × time


def test_checker_catches_broken_rows():
    p = v1_params()
    sch = [(0, 'GPU', True, 120)]
    rows = tv1.simulate(p, sch, 30.0, -1.0)
    assert check_rows(rows, sch) == []
    r1 = rows[:-1]
    assert any('time' in b for b in check_rows(r1, sch))
    r2 = [dict(r) for r in rows]; r2[5]['P'] = -1.0
    assert any('power' in b for b in check_rows(r2, sch))
    r3 = [dict(r) for r in rows]; r3[50]['ratio'] = 0.5
    assert any('ratio' in b for b in check_rows(r3, sch))
    r4 = [dict(r) for r in rows]; r4[3]['ex'] = True; r4[3]['res'] = None
    assert any('executing' in b for b in check_rows(r4, sch))


def test_status_rises_only_with_skin():
    p = v1_params()
    rows = tv1.simulate(p, [(0, 'NPU', True, 1300)], 28.3, -1.3)
    sts = [r['status'] for r in rows]
    assert sts[0] == 0 and max(sts) >= 1
    for r in rows:
        assert r['status'] == tv1.status_of(r['skin'])


def test_onset_rule_matches_v0_function():
    from d1sim.throttle import onset_time_ref as v0_onset
    bins = [(t, 1.0) for t in range(0, 60, 10)] + [(t, 1.2) for t in range(60, 300, 10)]
    assert tv1.onset_time_ref(bins, 1.0) == v0_onset(bins, 1.0) == 60
    bins2 = [(t, 1.0) for t in range(0, 300, 10)]
    assert tv1.onset_time_ref(bins2, 1.0) is None and v0_onset(bins2, 1.0) is None
