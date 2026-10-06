"""Throttle model v2.2 (prereg sim/스로틀모형_사전등록_v22.md, commit 9056685): v0/v1/v2/v2.1 untouched + v2.2 additions."""
import hashlib
import math
import os

from d1sim import throttle_v2 as tv2
from d1sim import throttle_v21 as tv21
from d1sim import throttle_v22 as tv22

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PROF = os.path.join(ROOT, 'd1sim', 'profiles')
# frozen v2.1 (c6a7da2) — the files the v2.2 controller / power / L0 are copied from
V21_SHA = {
    'throttle_v21_thermal.json': '43b873e5e97797398e5b5db1e96cfd2d72b0c5e97c5a1f3c53504112a794cc18',
    'throttle_v21_NPU.json': 'ad52e3cb6a61f96a8c1b58fd2dce83d00acc7341be7ef23245e0040ebcf3dad6',
    'throttle_v21_GPU_compiledmodel.json': '01d1c5ac405ba998cef6295bd01029be2184d4d5979b8e87a04b83659fd589d4',
    'throttle_v21_GPU_interpreter.json': '8ce9470ea8194b6675bbd5637c95384755cc929ca06c31938cba763fd8539a32',
    'throttle_v21_CPU4_interpreter.json': 'a71d3b11fbadf863d247031e985891c001a6d7ec9777af78cd245d18e6b0fd7c',
}
V21_PY_SHA = '76d76e7148f323fe1666fe899736d059331d375a7679579a2cc6085b6ef74293'


def _sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def _sched():
    return [(0, 'NPU', True, 200), ('t1', None, None, 0.2), (1, 'NPU', [(k % 10) < 5 for k in range(120)], 120),
            ('t2', None, None, 0.2), (2, 'NPU', [False] * 60, 60)]


def test_v21_files_unchanged():
    for fn, s in V21_SHA.items():
        assert _sha(os.path.join(PROF, fn)) == s, fn
    assert _sha(os.path.join(ROOT, 'd1sim', 'throttle_v21.py')) == V21_PY_SHA


def test_simulate_without_gm_is_v21():
    p = tv22.load_params('throttle_v21_')
    assert 'g_m' not in p['thermal']
    a = tv21.simulate(p, _sched(), 30.5, -1.0, 28.5)
    for model in ('mobilenet', 'effnet'):
        b = tv22.simulate(p, _sched(), 30.5, -1.0, 28.5, model=model)
        assert a == b


def test_gm_scales_thermal_input_exactly():
    p = tv22.load_params('throttle_v21_')
    p['thermal']['g_m'] = {'NPU': 0.8, 'GPU': 1.2}
    q = tv22.with_model(p, 'effnet')
    for r, g in (('NPU', 0.8), ('GPU', 1.2)):
        for s in (1.0, 0.93, 0.7, 0.45):
            dq = tv2.power_of(s, q['power'][r]) - q['power'][r]['P_idle']
            dp = tv2.power_of(s, p['power'][r]) - p['power'][r]['P_idle']
            assert math.isclose(dq, g * dp, rel_tol=1e-12)
    assert q['power']['CPU4'] == p['power']['CPU4']


def test_gm_only_effnet_and_no_mutation():
    p = tv22.load_params('throttle_v21_')
    p0 = dict(p['power']['NPU'])
    p['thermal']['g_m'] = {'NPU': 0.5, 'GPU': 0.5}
    assert tv22.with_model(p, 'mobilenet') is p
    q = tv22.with_model(p, 'effnet')
    assert p['power']['NPU'] == p0 and q['power']['NPU']['P0'] != p0['P0']
    a = tv22.simulate(p, _sched(), 30.5, -1.0, 28.5, model='mobilenet')
    b = tv22.simulate(p, _sched(), 30.5, -1.0, 28.5, model='effnet')
    assert max(r['skin'] for r in b) < max(r['skin'] for r in a)      # g < 1 -> less heat in


def test_v22_profiles_controller_power_equal_v21():
    p21 = tv22.load_params('throttle_v21_')
    p22 = tv22.load_params('throttle_v22_')
    assert p22['ctrl'] == p21['ctrl'] and p22['power'] == p21['power'] and p22['L0'] == p21['L0']
    for k in tv22.THERMAL_KEYS:
        assert k in p22['thermal']
    assert p22['thermal']['tau_f'] == p21['thermal']['tau_f'] and p22['thermal']['P_idle'] == p21['thermal']['P_idle']


def test_extract_v22_run_table_split():
    from d1sim.tools import extract_traces_v22 as x22
    from d1sim.tools import fit_throttle_v22 as f22
    assert len(x22.RUNS) == 23 and len(x22.DEV_TAGS) == 20 and len(x22.HOLDOUT_TAGS) == 3
    fit_tags = {t for t, _ in f22.FIT_THERMAL22}
    assert not (set(x22.HOLDOUT_TAGS) & fit_tags)
    assert len(f22.FIT_THERMAL22) == 36 and len(f22.EFFNET_DEV) == 12
    assert set(x22.HOLDOUT_TAGS) == {'h_nb_b2_re', 'h_gb_b2_re', 'h_gie_b1_spare'}
