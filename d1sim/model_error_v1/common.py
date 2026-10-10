"""common.py — paths · constants · helpers shared by the model-error v1 scripts (prereg d1sim/docs/모형오차_사전등록_v1.md, 9e29851).

Nothing here changes any frozen file. The measured side is read from the energy-C judge outputs (night1005e_judge_c.py 4e4dbcd3,
already produced on 10/8) and the raw HAL series; the predicted side comes from d1sim.v3.predict_v3 (imported, unmodified).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OD = r"C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice"
OD_SIM = os.path.join(OD, 'sim')
OUT_OD = os.path.join(OD_SIM, 'out_modelerr')                      # 원장 (OneDrive)
OUT_REPO = os.path.join(ROOT, 's26', 'results', 'modelerr_1009')    # 레포 사본
CHAIN_DIR = os.path.join(ROOT, 'tools', 'chains')

REG = 'd1sim/docs/모형오차_사전등록_v1.md'
REG_SHA = '4d144c0a398e2c513788a3cc153bafb3064a570495dc94326a743e5b9997365b'
REG_COMMIT = '9e29851858f6b695b964cb3cdf75e74269d96a8c'

# 칸 (등록 §2 · 에너지C_체인기록.md §1)
CELLS = {'NAc': dict(chain='npu_eff_work100_v1', side='A', canonical='4433e25923aa7aacfaa5f123466135e145b10100e27c7d416874abab8337f09c'),
         'NBc': dict(chain='npu_eff_work50eq_v1', side='B', canonical='ba74ed03e26ec5d7132c430504af544f6c9a7a0336c8a382ba715ecd2c12b4fa')}
BLOCKS = tuple(range(1, 9))
MODELS = ('v22', 'v21', 'v2_t0.3', 'v2_t0.75')      # = predict_v3.MODELS (주 v22 · 민감도 셋)
MAIN = 'v22'
MODEL_LABEL = {'v22': 'v2.2 V22-M (주, e52a922)', 'v21': 'v2.1 V21-Hθ r1 (민감도, c6a7da2)',
               'v2_t0.3': 'v2 V2-Lb θ_NPU 0.3 (민감도, 42338e7)', 'v2_t0.75': 'v2 V2-Lb θ_NPU 0.75 (민감도, 42338e7)'}
COLUMNS = (29.5, 30.5)                              # V3 v2 시작 열 규칙 (predict_v3.COLUMNS)
DEV_RANGE = (28.3, 31.6)                            # night1003_judge.DEV_RANGE — 밖이면 "범위 밖" 표시 (판정은 함)
BIN_S = 10
N_BINS = 90                                         # [0, 900) s
T_899 = 899
THR = 1.06                                          # NPU 조임 문턱 (night1005_judge.THR['NPU'] = predict_v3.THR)
HOLD = 3                                            # 첫 조임 = 칸 k + 뒤 3칸 (night1005_judge.HOLD)
EPS = 1e-9
PASS_ABS = 1.0                                      # 등록 §4 |예측 Δ − 실측 Δ| ≤ 1.0 ℃
WINDOW_S = 900


def sha256_file(p):
    with open(p, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def sha256_text(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def load_json(p):
    with open(p, encoding='utf-8') as fh:
        return json.load(fh)


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True, default=str)


def write_json(p, obj):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    s = dumps(obj)
    with open(p, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(s + '\n')
    return sha256_text(s + '\n')


def r6(x):
    return None if x is None else round(float(x), 6)


def pick_column(start_skin, columns=COLUMNS):
    """비교 열 = 실제 시작 SKIN 에 가까운 쪽 (같으면 작은 쪽 29.5 · 보간 없음) — night1003_judge._pick_col 과 같은 규칙."""
    if start_skin is None:
        return None
    cands = sorted((abs(c - start_skin), c) for c in columns)
    return cands[0][1]


def in_range(start_skin):
    return None if start_skin is None else (DEV_RANGE[0] <= start_skin <= DEV_RANGE[1])


def sign(d):
    """+ (> 0) · − (< 0) · 0 (= 0) after 6-decimal rounding (v3_judge ④ · night1005 _sign)."""
    if d is None:
        return None
    d = round(float(d), 6)
    return '+' if d > 0 else ('-' if d < 0 else '0')


def first_throttle(ratios, thr=THR, hold=HOLD):
    """칸 k 와 뒤 hold 칸이 모두 ≥ 문턱인 첫 k (None 칸은 실패) — night1005_judge.first_throttle 과 같은 규칙. 없으면 None."""
    for k in range(0, len(ratios) - hold):
        win = ratios[k:k + 1 + hold]
        if all(r is not None and r >= thr - EPS for r in win):
            return k
    return None


def cell_key(cell, block):
    return f'{cell}_b{block}'


def stdout_utf8():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
