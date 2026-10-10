"""common.py — paths · constants · helpers for the GPU holdout v1 scripts (prereg d1sim/docs/GPU홀드아웃_사전등록_v1.md).

Reuses the model-error v1 helpers by import (d1sim/model_error_v1/common.py — unchanged): sha256 · json · rounding · column pick ·
sign · first_throttle (HOLD 3, threshold argument). Nothing here changes any frozen file. The predicted side comes from
d1sim.v3.predict_v3 (imported, unmodified — the V3 v2 · P1j prediction path); the measured side from the GH judge outputs
(night1005e_judge_h.py wrapper over the frozen night1005e_judge.py 2db1cda5) and the raw HAL series.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from d1sim.model_error_v1 import common as C1  # noqa: E402  (helpers only — unchanged module)

sha256_file, sha256_text, load_json, dumps, write_json, r6 = C1.sha256_file, C1.sha256_text, C1.load_json, C1.dumps, C1.write_json, C1.r6
pick_column, in_range, sign, first_throttle, cell_key, stdout_utf8 = C1.pick_column, C1.in_range, C1.sign, C1.first_throttle, C1.cell_key, C1.stdout_utf8

OD = C1.OD
OD_SIM = C1.OD_SIM
OUT_OD = os.path.join(OD_SIM, 'out_gpuho')                        # 원장 (OneDrive)
OUT_REPO = os.path.join(ROOT, 's26', 'results', 'gpuho_1011')     # 레포 사본
CHAIN_DIR = C1.CHAIN_DIR
N2_OUT = os.path.join(OD_SIM, 'out_1005e')                         # N2 judge outputs (T calculation input)

REG = 'd1sim/docs/GPU홀드아웃_사전등록_v1.md'
REG_SHA = 'eaad42e3500a4b4fe0f0aacc93ea20b15be3c8261e01fea2485d13adb200832b'
REG_COMMIT = 'b3f84a75d9de120103d6af075f1d18daa7552822'                                      # filled after commit ① (before commit ②)

RESOURCE = 'GPU'
SESSION_SFX = '1011h'
# 칸 (등록 §2-2): A = N2 GPU d100 chain unchanged · B = new same-work chain (work_d50 GPU 50 · T s → tail_idle GPU 1 · 900 − T s)
CELLS = {'GAh': dict(chain='gpu_eff_work100_v1', side='A', canonical='df0ffa2f15ddc9c1c0cab60cd09daeff48e34165296af64aaf77e58bc85eb513'),
         'GBh': dict(chain='gpu_eff_work50eq_v1', side='B', canonical='28d84c5c4c286dd94cfca13c9ef5dd2f46c7e34224c3a378ed0be50ae6838205')}
SMOKE = dict(chain='smoke_gpu_eff_v1', canonical='16c951ba993423b82b2921b2e000957afeb7ea8e5b192121590a381ae29aea29')
A_CHAIN_TEMPLATE_B = dict(chain='gpu_eff_work50_v1', canonical='4af89784ae20fce30f356ca30c69d4ec54aab65f9582901e846a0b4ac54cf53c', durs=(720, 180))
GPU_MODEL_SHA = '6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0'
BLOCKS = tuple(range(1, 9))
ORDER = {k: (('GAh', 'GBh') if k % 2 == 1 else ('GBh', 'GAh')) for k in BLOCKS}   # 거울 순서 (등록 §2-3)
MODELS = C1.MODELS                                  # ('v22', 'v21', 'v2_t0.3', 'v2_t0.75')
MAIN = C1.MAIN
MODEL_LABEL = C1.MODEL_LABEL
COLUMNS = C1.COLUMNS                                # (29.5, 30.5)
DEV_RANGE = C1.DEV_RANGE
BIN_S = C1.BIN_S
N_BINS = C1.N_BINS
T_899 = C1.T_899
THR = 1.10                                          # GPU 조임 문턱 (night1005_judge.THR['GPU'])
HOLD = C1.HOLD
EPS = C1.EPS
PASS_ABS = C1.PASS_ABS                              # 등록 §4-2 |예측 Δ − 실측 Δ| ≤ 1.0 ℃
WINDOW_S = 900
T_CAP_S = 840                                       # 등록 §2-2 T 상한


def ceil10(x):
    import math
    return int(math.ceil(x / 10.0 - 1e-9) * 10)


def verdict_label(k, n=8):
    """등록 §4-3 (결과 전 고정)."""
    if k >= 7:
        return f'GPU 재현 확인 (같은 계열 새 세션 · {n}블록 중 {k})'
    if 5 <= k <= 6:
        return f'GPU 부분 재현 ({k}/{n})'
    return f'GPU 재현 미확인 ({k}/{n})'


def print_table(res):
    ok = all(c for _, c, _ in res)
    print('| 시험 | 결과 | 값 |\n|---|---|---|')
    for name, c, got in res:
        print(f"| {name} | {'PASS' if c else 'FAIL'} | {str(got)[:170]} |")
    print(f"\nselftest 전체: {'PASS' if ok else 'FAIL'} ({sum(1 for _, c, _ in res if c)}/{len(res)})")
    return 0 if ok else 1
