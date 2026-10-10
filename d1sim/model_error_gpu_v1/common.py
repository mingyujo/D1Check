"""common.py — paths · constants · run table · helpers shared by the GPU model-error v1 scripts
(prereg d1sim/docs/GPU모형오차_사전등록_v1.md, commit 35c9342 — written before any error computation).

Nothing here changes any frozen file. Measured side = d1sim/data extracted traces (1 s HAL · 10 s runner latency, extract_traces_v1
functions, extracted 10/3 ~ 10/6 and cross-checked against the judge JSONs then) + the judge JSONs in OneDrive sim/out_*.
Predicted side = frozen prediction JSONs (used as-is where an item exists) + series regenerated with each 판's frozen code and its own
frozen driving rule (reproduction-checked against the frozen scalars). Rules (a)~(j): sim/out_gpuerr/preflight.txt.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OD = r"C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice"
OD_SIM = os.path.join(OD, 'sim')
OUT_OD = os.path.join(OD_SIM, 'out_gpuerr')                      # 원장 (OneDrive)
OUT_REPO = os.path.join(ROOT, 's26', 'results', 'gpuerr_1011')    # 레포 사본
DATA = os.path.join(ROOT, 'd1sim', 'data')
PKG = os.path.dirname(os.path.abspath(__file__))
CELLS_JSON = os.path.join(PKG, 'cells_gpu.json')
PRED_JSON = os.path.join(PKG, 'predictions_gpu.json')

REG = 'd1sim/docs/GPU모형오차_사전등록_v1.md'
REG_SHA = 'a569b86207410fe28a0469b94057200f8a075e490b2ae4da4c1c5afd402866eb'
REG_COMMIT = '35c934249a67e22b30ea7047167e06cecd02ac09'

COLUMNS = (29.5, 30.5)                              # V3 v2 · P1j 시작 열 규칙 (두 점)
DEV_RANGE = (28.3, 31.6)                            # night1003_judge.DEV_RANGE — 밖이면 "범위 밖" 표시 (판정은 함)
BIN_S = 10
HOLD = 3                                            # 첫 조임 = 칸 k + 뒤 3칸 (night1005_judge.HOLD)
THR = {'GPU': 1.10, 'NPU': 1.06}                    # night1005_judge.THR (자원별 조임 문턱)
EPS = 1e-9
PASS_ABS = 1.0                                      # 등록 §4 쌍 규칙 |예측 Δ − 실측 Δ| ≤ 1.0 ℃
A0 = -1.0
REPRO_TOL = 1e-6

PAN_LABEL = {'v0': 'v0 2노드 (402acab)', 'v1': 'v1 M-P r3 (3050e09 · 예측 동결 b40cbc9 · 5d7681a)', 'v2': 'v2 V2-Lb (42338e7 · 예측 동결 4cc7b87)',
             'v21': 'v2.1 V21-Hθ r1 (c6a7da2 · 예측 동결 e092b75 · 3786f16)', 'v22': 'v2.2 V22-M (e52a922, 주)', 'v22_2pt': 'v2.2 V22-M 열 두 점 (기술 — N1 · N2 동결 파일 대신 V3 규칙으로 돌린 값)'}
HOLDOUT_PANS = ('v0', 'v1', 'v2', 'v21')
VERDICT_FIT = 'GPU 적합도 오차 (개발 자료)'


def verdict_holdout(pan):
    return f'GPU 홀드아웃 오차 (판 {pan} · 동결 예측)'


# ---------------------------------------------------------------- run table (등록 §2 + 비교용 NPU)
# judge_ft = (section path, segment index) of the measured first-throttle item with the "칸 k + 뒤 3칸" rule in that run's own judge JSON
RUNS = {
    'c1a':            dict(prefix='v1', label='C1a GPU d100 1300 s (Interpreter)', resource='GPU', model='mobilenet', engine='INT', group='v0', role='GPU',
                           judge='out_0928/C1a.json', judge_ft=('v0_holdout:T1', 0), holdout='v0', v22='generated', kind='v0 홀드아웃 (T1) · v2.2 적합도'),
    'm3':             dict(prefix='v1', label='M3 GPU d50 600 s (Interpreter)', resource='GPU', model='mobilenet', engine='INT', group='v0', role='GPU',
                           judge='out_0928/M3.json', judge_ft=('v0_holdout:T2', 0), holdout='v0', v22='generated', kind='v0 홀드아웃 (T2) · v2.2 적합도'),
    'm1g_r2':         dict(prefix='v2', label='M1-GPU 2런째 (d10 60 / d100 1200 / d10 300)', resource='GPU', model='mobilenet', engine='CM', group='v1', role='GPU',
                           judge='out_1003/M1_gpu_r2.json', judge_ft=('heat_extra.onset_1_1_s', 1), holdout='v1', v22='generated', kind='v1 홀드아웃 · v2.2 적합도'),
    'gpace':          dict(prefix='v2', label='GPU 페이싱 (d10 60 / d100 600 / d10 60 / d100 300)', resource='GPU', model='mobilenet', engine='CM', group='v1', role='GPU',
                           judge='out_1003/GPUpace.json', judge_ft=('heat.onset_1_1_s', 1), holdout='v1', v22='generated', kind='v1 홀드아웃 · v2.2 적합도'),
    'g50p':           dict(prefix='v21', label='G50P (d50 60 / d100 300 / d50 480)', resource='GPU', model='mobilenet', engine='CM', group='v2', role='GPU',
                           judge='out_1004/G50P.json', judge_ft=('heat.onset_1_1_s', 1), holdout='v2', v22='generated', kind='v2 홀드아웃 · v2.2 적합도'),
    'gi300':          dict(prefix='v21', label='GI300 (d10 60 / d100 600 / d1 300 / d100 300)', resource='GPU', model='mobilenet', engine='CM', group='v2', role='GPU',
                           judge='out_1004/GI300.json', judge_ft=('heat.onset_1_1_s', 1), holdout='v2', v22='generated', kind='v2 홀드아웃 · v2.2 적합도'),
    'g50p2':          dict(prefix='v21', label='G50P2 (10/5 · 같은 체인)', resource='GPU', model='mobilenet', engine='CM', group='v2', role='GPU',
                           judge='out_1005/G50P2.json', judge_ft=('heat.onset_1_1_s', 1), holdout='v2', v22='generated', kind='v2 홀드아웃 · v2.2 적합도'),
    'n1_ga_b1':       dict(prefix='v22', label='N1 GA b1 (MobileNet GPU d100 300 / d1 600)', resource='GPU', model='mobilenet', engine='CM', group='N1', role='GPU', cell='GA', block=1, side='A',
                           judge='out_1005n/GA_b1.json', judge_ft=('work.first_throttle_s', 0), holdout='v21', v22='frozen_N1', kind='v2.1 홀드아웃 · v2.2 적합도'),
    'n1_ga_b2':       dict(prefix='v22', label='N1 GA b2', resource='GPU', model='mobilenet', engine='CM', group='N1', role='GPU', cell='GA', block=2, side='A',
                           judge='out_1005n/GA_b2.json', judge_ft=('work.first_throttle_s', 0), holdout='v21', v22='frozen_N1', kind='v2.1 홀드아웃 · v2.2 적합도'),
    'n1_gb_b1':       dict(prefix='v22', label='N1 GB b1 (MobileNet GPU d50 480 / d1 420)', resource='GPU', model='mobilenet', engine='CM', group='N1', role='GPU', cell='GB', block=1, side='B',
                           judge='out_1005n/GB_b1.json', judge_ft=('work.first_throttle_s', 0), holdout='v21', v22='frozen_N1', kind='v2.1 홀드아웃 · v2.2 적합도'),
    'n1_gb_b2':       dict(prefix='v22', label='N1 GB b2 (하한 미달 시작 · 범위 밖)', resource='GPU', model='mobilenet', engine='CM', group='N1', role='GPU', cell='GB', block=2, side='B',
                           judge='out_1005n/GB_b2.json', judge_ft=('work.first_throttle_s', 0), holdout='v21', v22='frozen_N1', kind='v2.1 홀드아웃 · v2.2 적합도 (범위 밖 표시)'),
    'h_gb_b2_re':     dict(prefix='v22', label='N1 보충 GB b2_re', resource='GPU', model='mobilenet', engine='CM', group='N1s', role='GPU', cell='GB', block=2, side='B',
                           judge='out_1005n/GB_b2_re.json', judge_ft=('work.first_throttle_s', 0), holdout='v21', v22='frozen_N1supp', kind='v2.1 홀드아웃 · v2.2 약한 홀드아웃'),
    'n2_gae_b1':      dict(prefix='v22', label='N2 GAe b1 (EffNet GPU d100 300 / d1 600)', resource='GPU', model='effnet', engine='CM', group='N2', role='GPU', cell='GAe', block=1, side='A',
                           judge='out_1005e/GAe_b1.json', judge_ft=('work.first_throttle_s', 0), holdout='v21', v22='frozen_N2', kind='v2.1 홀드아웃 · v2.2 g_GPU 피팅 자료'),
    'n2_gae_b2':      dict(prefix='v22', label='N2 GAe b2', resource='GPU', model='effnet', engine='CM', group='N2', role='GPU', cell='GAe', block=2, side='A',
                           judge='out_1005e/GAe_b2.json', judge_ft=('work.first_throttle_s', 0), holdout='v21', v22='frozen_N2', kind='v2.1 홀드아웃 · v2.2 g_GPU 피팅 자료'),
    'n2_gbe_b1':      dict(prefix='v22', label='N2 GBe b1 (EffNet GPU d50 720 / d1 180)', resource='GPU', model='effnet', engine='CM', group='N2', role='GPU', cell='GBe', block=1, side='B',
                           judge='out_1005e/GBe_b1.json', judge_ft=('work.first_throttle_s', 0), holdout='v21', v22='frozen_N2', kind='v2.1 홀드아웃 · v2.2 g_GPU 피팅 자료'),
    'n2_gbe_b2':      dict(prefix='v22', label='N2 GBe b2', resource='GPU', model='effnet', engine='CM', group='N2', role='GPU', cell='GBe', block=2, side='B',
                           judge='out_1005e/GBe_b2.json', judge_ft=('work.first_throttle_s', 0), holdout='v21', v22='frozen_N2', kind='v2.1 홀드아웃 · v2.2 g_GPU 피팅 자료'),
    'n4_gie_b1':      dict(prefix='v22', label='N4 GIe b1 (EffNet GPU d10 60 / d100 600 / d1 300 / d100 300)', resource='GPU', model='effnet', engine='CM', group='N4', role='GPU',
                           judge='out_1005r/GIe_b1.json', judge_ft=('heat.onset_1_1_s', 1), holdout=None, v22='generated', kind='v2.2 적합도'),
    'n4_gie_b2':      dict(prefix='v22', label='N4 GIe b2', resource='GPU', model='effnet', engine='CM', group='N4', role='GPU',
                           judge='out_1005r/GIe_b2.json', judge_ft=('heat.onset_1_1_s', 1), holdout=None, v22='generated', kind='v2.2 적합도'),
    'h_gie_b1_spare': dict(prefix='v22', label='N4 예비 GIe b1 (피팅 안 씀)', resource='GPU', model='effnet', engine='CM', group='N4s', role='GPU',
                           judge='out_1005r/GIe_b1_spare.json', judge_ft=('heat.onset_1_1_s', 1), holdout=None, v22='generated', kind='v2.2 기술 (약한 홀드아웃)'),
    # 비교용 NPU 같은 묶음 (등록 §2 끝)
    'n1_na_b1':       dict(prefix='v22', label='N1 NA b1 (MobileNet NPU d100 300 / d1 600)', resource='NPU', model='mobilenet', engine='CM', group='N1', role='NPU', cell='NA', block=1, side='A',
                           judge='out_1005n/NA_b1.json', judge_ft=('work.first_throttle_s', 0), holdout=None, v22='frozen_N1', kind='v2.2 적합도 (NPU 비교)'),
    'n1_na_b2':       dict(prefix='v22', label='N1 NA b2', resource='NPU', model='mobilenet', engine='CM', group='N1', role='NPU', cell='NA', block=2, side='A',
                           judge='out_1005n/NA_b2.json', judge_ft=('work.first_throttle_s', 0), holdout=None, v22='frozen_N1', kind='v2.2 적합도 (NPU 비교)'),
    'n1_nb_b1':       dict(prefix='v22', label='N1 NB b1 (MobileNet NPU d50 660 / d1 240)', resource='NPU', model='mobilenet', engine='CM', group='N1', role='NPU', cell='NB', block=1, side='B',
                           judge='out_1005n/NB_b1.json', judge_ft=('work.first_throttle_s', 0), holdout=None, v22='frozen_N1', kind='v2.2 적합도 (NPU 비교)'),
    'n1_nb_b2':       dict(prefix='v22', label='N1 NB b2', resource='NPU', model='mobilenet', engine='CM', group='N1', role='NPU', cell='NB', block=2, side='B',
                           judge='out_1005n/NB_b2.json', judge_ft=('work.first_throttle_s', 0), holdout=None, v22='frozen_N1', kind='v2.2 적합도 (NPU 비교)'),
    'h_nb_b2_re':     dict(prefix='v22', label='N1 보충 NB b2_re', resource='NPU', model='mobilenet', engine='CM', group='N1s', role='NPU', cell='NB', block=2, side='B',
                           judge='out_1005n/NB_b2_re.json', judge_ft=('work.first_throttle_s', 0), holdout=None, v22='frozen_N1supp', kind='v2.2 약한 홀드아웃 (NPU 비교)'),
    'n2_nae_b1':      dict(prefix='v22', label='N2 NAe b1 (EffNet NPU d100 300 / d1 600)', resource='NPU', model='effnet', engine='CM', group='N2', role='NPU', cell='NAe', block=1, side='A',
                           judge='out_1005e/NAe_b1.json', judge_ft=('work.first_throttle_s', 0), holdout=None, v22='frozen_N2', kind='v2.2 g_NPU 피팅 자료 (NPU 비교)'),
    'n2_nae_b2':      dict(prefix='v22', label='N2 NAe b2', resource='NPU', model='effnet', engine='CM', group='N2', role='NPU', cell='NAe', block=2, side='A',
                           judge='out_1005e/NAe_b2.json', judge_ft=('work.first_throttle_s', 0), holdout=None, v22='frozen_N2', kind='v2.2 g_NPU 피팅 자료 (NPU 비교)'),
    'n2_nbe_b1':      dict(prefix='v22', label='N2 NBe b1 (EffNet NPU d50 660 / d1 240)', resource='NPU', model='effnet', engine='CM', group='N2', role='NPU', cell='NBe', block=1, side='B',
                           judge='out_1005e/NBe_b1.json', judge_ft=('work.first_throttle_s', 0), holdout=None, v22='frozen_N2', kind='v2.2 g_NPU 피팅 자료 (NPU 비교)'),
    'n2_nbe_b2':      dict(prefix='v22', label='N2 NBe b2', resource='NPU', model='effnet', engine='CM', group='N2', role='NPU', cell='NBe', block=2, side='B',
                           judge='out_1005e/NBe_b2.json', judge_ft=('work.first_throttle_s', 0), holdout=None, v22='frozen_N2', kind='v2.2 g_NPU 피팅 자료 (NPU 비교)'),
    'n4_nie_b1':      dict(prefix='v22', label='N4 NIe b1 (EffNet NPU d10 60 / d100 300 / d1 300 / d100 180)', resource='NPU', model='effnet', engine='CM', group='N4', role='NPU',
                           judge='out_1005r/NIe_b1.json', judge_ft=('heat.onset_1_1_s', 1), holdout=None, v22='generated', kind='v2.2 적합도 (NPU 비교)'),
    'n4_nie_b2':      dict(prefix='v22', label='N4 NIe b2', resource='NPU', model='effnet', engine='CM', group='N4', role='NPU',
                           judge='out_1005r/NIe_b2.json', judge_ft=('heat.onset_1_1_s', 1), holdout=None, v22='generated', kind='v2.2 적합도 (NPU 비교)'),
}
GPU_TAGS = [t for t, r in RUNS.items() if r['role'] == 'GPU']
NPU_TAGS = [t for t, r in RUNS.items() if r['role'] == 'NPU']
NIGHT_OF = {'N1': 'N1', 'N1s': 'N1', 'N2': 'N2'}

# 세기 A/B 쌍 (m5) — 측정 pair JSON · 예측 = 동결 pairs (열 = A·B 시작 평균에 가까운 쪽) — N1 · N2 만 (등록 §3 m5)
PAIRS = {
    'N1_GPU_b1':  dict(resource='GPU', group='N1', block=1, a='n1_ga_b1', b='n1_gb_b1', judge='out_1005n/pair_G_b1.json', pans=('v21', 'v22')),
    'N1_GPU_b2':  dict(resource='GPU', group='N1', block=2, a='n1_ga_b2', b='n1_gb_b2', judge='out_1005n/pair_G_b2.json', pans=('v21', 'v22'), note='B 시작 27.8 범위 밖 (판정기 cmp 는 unsupported) — 등록 §2 대로 넣고 표시'),
    'N1_GPU_b2s': dict(resource='GPU', group='N1s', block=2, a='n1_ga_b2', b='h_gb_b2_re', judge='out_1005n/pair_G_b2s.json', pans=('v21', 'v22'), note='보충 쌍 (약한 홀드아웃)'),
    'N2_GPU_b1':  dict(resource='GPU', group='N2', block=1, a='n2_gae_b1', b='n2_gbe_b1', judge='out_1005e/pair_GPU_b1.json', pans=('v21', 'v22')),
    'N2_GPU_b2':  dict(resource='GPU', group='N2', block=2, a='n2_gae_b2', b='n2_gbe_b2', judge='out_1005e/pair_GPU_b2.json', pans=('v21', 'v22')),
    'N1_NPU_b1':  dict(resource='NPU', group='N1', block=1, a='n1_na_b1', b='n1_nb_b1', judge='out_1005n/pair_N_b1.json', pans=('v22',)),
    'N1_NPU_b2':  dict(resource='NPU', group='N1', block=2, a='n1_na_b2', b='n1_nb_b2', judge='out_1005n/pair_N_b2.json', pans=('v22',)),
    'N1_NPU_b2s': dict(resource='NPU', group='N1s', block=2, a='n1_na_b2', b='h_nb_b2_re', judge='out_1005n/pair_N_b2s.json', pans=('v22',), note='보충 쌍 (약한 홀드아웃)'),
    'N2_NPU_b1':  dict(resource='NPU', group='N2', block=1, a='n2_nae_b1', b='n2_nbe_b1', judge='out_1005e/pair_NPU_b1.json', pans=('v22',)),
    'N2_NPU_b2':  dict(resource='NPU', group='N2', block=2, a='n2_nae_b2', b='n2_nbe_b2', judge='out_1005e/pair_NPU_b2.json', pans=('v22',)),
}
# 자원 판정 문구 (m6) — 측정 resource JSON · 예측 = night1005_judge.resource_verdict(블록별 열의 예측 쌍) (cmp_one 순서)
RESOURCES = {
    'N1_GPU':      dict(resource='GPU', group='N1', pairs=('N1_GPU_b1', 'N1_GPU_b2'), judge='out_1005n/resource_G.json', pans=('v21', 'v22'), note='GB_b2 범위 밖 — 판정기 cmp 에서는 unsupported (표시)'),
    'N1_GPU_supp': dict(resource='GPU', group='N1s', pairs=('N1_GPU_b1', 'N1_GPU_b2s'), judge='out_1005n/resource_G_supp.json', pans=('v21', 'v22'), note='보충 쌍 판'),
    'N2_GPU':      dict(resource='GPU', group='N2', pairs=('N2_GPU_b1', 'N2_GPU_b2'), judge='out_1005e/res_GPU.json', pans=('v21', 'v22')),
    'N1_NPU':      dict(resource='NPU', group='N1', pairs=('N1_NPU_b1', 'N1_NPU_b2'), judge='out_1005n/resource_N.json', pans=('v22',)),
    'N1_NPU_supp': dict(resource='NPU', group='N1s', pairs=('N1_NPU_b1', 'N1_NPU_b2s'), judge='out_1005n/resource_N_supp.json', pans=('v22',), note='보충 쌍 판'),
    'N2_NPU':      dict(resource='NPU', group='N2', pairs=('N2_NPU_b1', 'N2_NPU_b2'), judge='out_1005e/res_NPU.json', pans=('v22',)),
}
JUDGE_SHA_PREFIX = {'night1005_judge.py': 'ca8680c2', 'night1005e_judge.py': '2db1cda5', 'night1003_judge.py': 'a5ceab41'}


# ---------------------------------------------------------------- helpers
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


def r4(x):
    return None if x is None else round(float(x), 4)


def fl(v):
    return None if v in ('', None) else float(v)


def pick_column(start_skin, columns=COLUMNS):
    """비교 열 = 실제 시작 SKIN 에 가까운 쪽 (같으면 작은 쪽 · 보간 없음) — night1003_judge._pick_col 과 같은 규칙. columns 는 float 열 값들."""
    if start_skin is None or not columns:
        return None
    cands = sorted((abs(float(c) - start_skin), float(c)) for c in columns)
    return cands[0][1]


def col_key(c):
    """동결 예측 JSON 의 열 키 문자열 (predict_night_1005 · fit_throttle_v22: f'{T0}' of a float)."""
    return f'{float(c)}'


def in_range(start_skin):
    return None if start_skin is None else (DEV_RANGE[0] <= start_skin <= DEV_RANGE[1])


def sign(d):
    """+ · − · 0 after 6-decimal rounding (P1j judge_modelerr.sign · v3_judge ④)."""
    if d is None:
        return None
    d = round(float(d), 6)
    return '+' if d > 0 else ('-' if d < 0 else '0')


def first_throttle(ratios, thr, hold=HOLD):
    """칸 k 와 뒤 hold 칸이 모두 ≥ 문턱인 첫 k (None 칸은 실패) — night1005_judge.first_throttle 과 같은 규칙. 없으면 None."""
    for k in range(0, len(ratios) - hold):
        win = ratios[k:k + 1 + hold]
        if all(r is not None and r >= thr - EPS for r in win):
            return k
    return None


def bin_means(values_by_t, n_bins, bin_s=BIN_S):
    """values_by_t: list of (t_abs_s, value) · bin k = [10k, 10k+10) mean (None if empty)."""
    sums, cnts = [0.0] * n_bins, [0] * n_bins
    for t, v in values_by_t:
        if v is None:
            continue
        k = int(t // bin_s)
        if 0 <= k < n_bins:
            sums[k] += v
            cnts[k] += 1
    return [round(sums[k] / cnts[k], 4) if cnts[k] else None for k in range(n_bins)], cnts


# ---------------------------------------------------------------- measured raw (추출 trace · manifest · 판정 JSON) — 읽기만
def manifest(prefix):
    return load_json(os.path.join(DATA, f'trace_{prefix}_manifest.json'))


def run_manifest(tag):
    return manifest(RUNS[tag]['prefix'])[tag]


def trace1(tag):
    return list(csv.DictReader(open(os.path.join(DATA, f"trace_{RUNS[tag]['prefix']}_{tag}.csv"), encoding='utf-8')))


def trace10(tag):
    return list(csv.DictReader(open(os.path.join(DATA, f"trace_{RUNS[tag]['prefix']}_10s_{tag}.csv"), encoding='utf-8')))


def trace_paths(tag):
    pre = RUNS[tag]['prefix']
    return os.path.join(DATA, f'trace_{pre}_{tag}.csv'), os.path.join(DATA, f'trace_{pre}_10s_{tag}.csv')


def judge_path(tag_or_rel):
    rel = RUNS[tag_or_rel]['judge'] if tag_or_rel in RUNS else tag_or_rel
    return os.path.join(OD_SIM, rel)


def seg_offsets_meas(tag):
    """실측 구간 시작의 체인 절대 시각 (s) = manifest start_ns 차 (전환 포함)."""
    m = run_manifest(tag)
    s0 = m['segments'][0]['start_ns']
    return [(s['start_ns'] - s0) / 1e9 for s in m['segments']]


def seg_offsets_model(tag):
    """예측 체인 (전환 0 s) 의 구간 시작 절대 시각 = 앞 구간 길이 합."""
    m = run_manifest(tag)
    out, acc = [], 0
    for s in m['segments']:
        out.append(acc)
        acc += s['duration_s']
    return out


def chain_segments(tag):
    """체인 명령 (duty · duration · accelerator) = manifest segments."""
    return [dict(accelerator=s['accelerator'], duty=s['duty'], duration_s=s['duration_s']) for s in run_manifest(tag)['segments']]


def get_path(d, dotted):
    for k in dotted.split('.'):
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def load_judge_module(name):
    """OneDrive sim 판정기를 경로로 import (SHA 접두 검사 · 수정 0)."""
    p = os.path.join(OD_SIM, name)
    s = sha256_file(p)
    if not s.startswith(JUDGE_SHA_PREFIX[name]):
        raise SystemExit(f'{name} SHA {s[:8]} != frozen {JUDGE_SHA_PREFIX[name]}')
    spec = importlib.util.spec_from_file_location(name[:-3], p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, s


def stdout_utf8():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def print_table(res):
    ok = all(c for _, c, _ in res)
    print('| 시험 | 결과 | 값 |\n|---|---|---|')
    for name, c, got in res:
        print(f"| {name} | {'PASS' if c else 'FAIL'} | {str(got)[:170]} |")
    print(f"\nselftest 전체: {'PASS' if ok else 'FAIL'} ({sum(1 for _, c, _ in res if c)}/{len(res)})")
    return 0 if ok else 1
