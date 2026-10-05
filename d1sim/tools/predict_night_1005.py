"""predict_night_1005.py — frozen model predictions for the 2026-10-05 night cells (NA·NB·GA·GB), written BEFORE the measurement.

Cells (sim/밤1005_사전등록_v1.md §1, chains tools/chains/{npu,gpu}_work{100,50}_v1.json):
  NA: NPU d100 300 -> d1 600   NB: NPU d50 660 -> d1 240   GA: GPU d100 300 -> d1 600   GB: GPU d50 480 -> d1 420   (Σ 900 s each)
Driving rules = sim/스로틀모형_사전등록_v21.md §6: start SKIN 29.5 / 30.5 · A0 = -1.0 · BAT0 = SKIN0 - d_ref (z = 0) · no transition window ·
duty = first duty% of each 10 s period active · d1 = idle in the 1 s grid · throughput = R0_r / ratio per executing second
(R0_r = median over the cold d50 segment 0 of N50P·N50P2 (NPU) / G50P·G50P2 (GPU) of n / (length x 0.5) — data constant, not fitted).
Run metrics, pair deltas and the resource verdict are computed WITH THE NIGHT JUDGE'S OWN FUNCTIONS (sim/night1005_judge.py, SHA ca8680c2…)
so the frozen prediction uses the same rules the judgement will use.

  py d1sim/tools/predict_night_1005.py --model v21   # adopted v2.1 form + reference form -> d1sim/out/night_1005_prediction_v21.json
  py d1sim/tools/predict_night_1005.py --model v2    # frozen v2 (42338e7) theta 0.3 / 0.75 -> night_1005_prediction_v2.json
  py d1sim/tools/predict_night_1005.py --model v1    # frozen v1 (3050e09) fast / skin           -> night_1005_prediction_v1.json
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import statistics
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
PROFILES = os.path.join(ROOT, 'd1sim', 'profiles')
OUT = os.path.join(ROOT, 'd1sim', 'out')
DATA = os.path.join(ROOT, 'd1sim', 'data')
JUDGE_PATH = r'C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim\night1005_judge.py'
JUDGE_SHA_PREFIX = 'ca8680c2'
CELLS = {
    'NA': ('NPU', 'A', [('NPU', 100, 300), ('NPU', 1, 600)]),
    'NB': ('NPU', 'B', [('NPU', 50, 660), ('NPU', 1, 240)]),
    'GA': ('GPU', 'A', [('GPU', 100, 300), ('GPU', 1, 600)]),
    'GB': ('GPU', 'B', [('GPU', 50, 480), ('GPU', 1, 420)]),
}
COLUMNS = (29.5, 30.5)
A0 = -1.0


def _sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def load_judge():
    s = _sha(JUDGE_PATH)
    if not s.startswith(JUDGE_SHA_PREFIX):
        raise SystemExit(f'night1005_judge.py SHA {s[:8]} != frozen {JUDGE_SHA_PREFIX}')
    spec = importlib.util.spec_from_file_location('night1005_judge', JUDGE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, s


def duty_flags(duty, dur):
    return [(k % 10) < duty // 10 for k in range(dur)]


def schedule(cell):
    return [(i, res, (True if duty == 100 else duty_flags(duty, dur)), dur) for i, (res, duty, dur) in enumerate(CELLS[cell][2])]


def r0_constants():
    man = json.load(open(os.path.join(DATA, 'trace_v21_manifest.json'), encoding='utf-8'))
    out = {}
    for res, tags in (('NPU', ('n50p', 'n50p2')), ('GPU', ('g50p', 'g50p2'))):
        vals = []
        for t in tags:
            s0 = man[t]['segments'][0]
            L = (s0['end_ns'] - s0['start_ns']) / 1e9
            vals.append(s0['inference_count'] / (L * s0['duty'] / 100.0))
        out[res] = dict(R0=float(statistics.median(vals)), values=vals, tags=list(tags))
    return out


def run_metrics(J, rows, cell, R0):
    res, side, segs = CELLS[cell]
    thr = J.THR[res]
    L = segs[0][2]
    work = [r for r in rows if r['seg'] == 0]
    ex = [r for r in work if r['ex'] and r['ratio'] is not None]
    ref30 = statistics.median([r['ratio'] for r in ex if r['t'] < 30])
    bins = []
    for k in range(L // 10):
        v = sorted(r['ratio'] for r in ex if 10 * k <= r['t'] < 10 * (k + 1))
        bins.append((v[len(v) // 2] / ref30) if v else None)
    k1 = J.first_throttle(bins, thr)
    n_sec = [(r['t'], R0 / r['ratio']) for r in ex]
    n = sum(x for _, x in n_sec)
    cum = [dict(t_end=10 * (k + 1), cum=sum(x for t, x in n_sec if t < 10 * (k + 1))) for k in range(L // 10)]
    sk = [r['skin'] for r in rows]
    t899 = next(r for i, r in enumerate(rows) if i == 899)
    out = dict(first_throttle_s=None if k1 is None else 10 * k1, throttle_time_s=J.throttle_time(bins, thr), max_skin=max(sk),
               t38_s=sum(1 for x in sk if x >= 38.0 - J.EPS), t40_s=sum(1 for x in sk if x >= 40.0 - J.EPS), t42_s=sum(1 for x in sk if x >= 42.0 - J.EPS),
               skin_899=t899['skin'], ap_899=t899['ap'], rate_per_s=n / L, n=n, work_end_skin=work[-1]['skin'], max_ap=max(r['ap'] for r in rows),
               status_ge1_s=sum(1 for r in rows if r['status'] >= 1), bins_ratio=bins, cumulative=cum, ref30_ratio=ref30)
    return out


def as_judged(J, cell, m, T0):
    res, side, segs = CELLS[cell]
    return dict(kind='night1005_run', cell=cell, block=1, resource=res, side=side, run_id=f'model-{cell}', start_skin=T0, start={},
                work=dict(n=m['n'], rate_per_s=m['rate_per_s'], throttle_time_s=m['throttle_time_s'], cumulative=m['cumulative'],
                          first_throttle_s=m['first_throttle_s']),
                temps=dict(max_SKIN=m['max_skin'], t38_s=m['t38_s'], t40_s=m['t40_s'], t42_s=m['t42_s']))


def predict(J, sim, params_by_variant, R0):
    cells, pairs, resources = {}, {}, {}
    for var, (p, kw) in params_by_variant.items():
        for T0 in COLUMNS:
            col = f'{T0}' if var is None else f'{T0}/{var}'
            ms = {}
            for cell in CELLS:
                rows = sim(p, schedule(cell), T0, A0, **kw(T0))
                ms[cell] = run_metrics(J, rows, cell, R0[CELLS[cell][0]]['R0'])
                cells.setdefault(cell, {})[col] = {k: v for k, v in ms[cell].items() if k != 'cumulative'}
            for resn, (a, b) in (('NPU', ('NA', 'NB')), ('GPU', ('GA', 'GB'))):
                pj = J.pair_judge(as_judged(J, a, ms[a], T0), as_judged(J, b, ms[b], T0))
                pairs.setdefault(resn, {})[col] = dict(d_max_skin=pj['deltas']['d_max_skin'], d_t38_s=pj['deltas']['d_t38_s'], d_t40_s=pj['deltas']['d_t40_s'],
                                                       d_t42_s=pj['deltas']['d_t42_s'], d_throttle_time_s=pj['deltas']['d_throttle_time_s'],
                                                       work_ratio=pj['work_ratio'], same_work=pj['same_work'], signs=pj['signs'],
                                                       b_reach_s=pj['b_reach_s'], b_reach_minus_300_s=pj['b_reach_minus_300_s'],
                                                       rate_a=pj['rate_a'], rate_b=pj['rate_b'])
                p2 = [dict(pj, block=1), dict(pj, block=2)]
                v = J.resource_verdict(p2)
                resources.setdefault(resn, {})[col] = dict(verdict=v, sentence=J.sentence(resn, v, p2),
                                                           note='모형은 같은 시작 열의 두 블록을 같은 쌍으로 본다 (결정적) — 판정 문구는 같은 순서 규칙')
    return cells, pairs, resources


def v21_params(prefix='throttle_v21_'):
    tp = json.load(open(os.path.join(PROFILES, f'{prefix}thermal.json'), encoding='utf-8'))
    tp = {k: tp[k] for k in ('tau_f', 'G_f', 'G_s', 'tau_s', 'tau_a', 'G_a', 'P_idle', 'c_f', 'c_s', 'c_a', 'k_b', 'd_ref')}
    ctrl, power, L0 = {}, {}, {}
    for res, fn in (('GPU', 'GPU_compiledmodel'), ('NPU', 'NPU'), ('CPU4', 'CPU4_interpreter')):
        d = json.load(open(os.path.join(PROFILES, f'{prefix}{fn}.json'), encoding='utf-8'))
        ctrl[res] = dict(d['ctrl']); power[res] = {k: d['power'][k] for k in ('P_idle', 'P0', 'alpha')}; L0[res] = d['L0_ms']
    ctrl['CPU4'] = dict(ctrl['CPU4'], v1_controller=True)
    return dict(thermal=tp, ctrl=ctrl, power=power, L0=L0)


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True, choices=['v21', 'v2', 'v1'])
    a = ap.parse_args()
    J, jsha = load_judge()
    R0 = r0_constants()
    base = dict(cells_def={k: ' → '.join(f'{r} d{d} {s}' for r, d, s in v[2]) for k, v in CELLS.items()}, columns=list(COLUMNS), A0=A0,
                R0=R0, judge=dict(path=JUDGE_PATH, sha256=jsha), rule='sim/스로틀모형_사전등록_v21.md §6 · night1005_judge.py 함수로 지표·쌍·판정')
    if a.model == 'v21':
        from d1sim import throttle_v21 as tv21
        p = v21_params()
        fit = json.load(open(os.path.join(OUT, 'throttle_fit_v21.json'), encoding='utf-8'))
        d_ref = p['thermal']['d_ref']
        kw = lambda T0: dict(B0=T0 - d_ref)
        R = dict(model=f"v2.1 V21-{fit['adopted']} (d1sim/throttle_v21.py + profiles/throttle_v21_*.json)", adopted_form=f"V21-{fit['adopted']}",
                 v21_status=fit['v21_status'], BAT0_rule=f'BAT0 = SKIN0 - d_ref (d_ref {d_ref:.4f}, z = 0)', **base)
        R['cells'], R['pairs'], R['resources'] = predict(J, tv21.simulate, {None: (p, kw)}, R0)
        R['reference_forms'] = {}
        for other, cand in fit['candidates'].items():
            if other == fit['adopted']:
                continue
            po = cand['_params_cm']
            po['ctrl']['CPU4'] = dict(po['ctrl']['CPU4'], v1_controller=True)
            c, pr, rs = predict(J, tv21.simulate, {None: (po, kw)}, R0)
            R['reference_forms'][f'V21-{other}'] = dict(note='참고 — 선택에 쓰지 않음', cells=c, pairs=pr, resources=rs)
        out = os.path.join(OUT, 'night_1005_prediction_v21.json')
    elif a.model == 'v2':
        from d1sim import throttle_v2 as tv2
        from d1sim.tools.predict_night_1004 import v2_params
        p = v2_params()
        variants = {}
        for th in (0.3, 0.75):
            variants[f'theta_{th}'] = (dict(p, ctrl=dict(p['ctrl'], NPU=dict(p['ctrl']['NPU'], theta=th))), lambda T0: {})
        R = dict(model='v2 V2-Lb (d1sim/throttle_v2.py + profiles/throttle_v2_*.json, 고정 42338e7) — 밤 1005 칸, 새 구동 파일 (v2 코드 무수정)',
                 variants={k: float(k.split('_')[1]) for k in variants}, BAT0_rule='v2 는 BAT0 를 쓰지 않는다', **base)
        R['cells'], R['pairs'], R['resources'] = predict(J, tv2.simulate, variants, R0)
        out = os.path.join(OUT, 'night_1005_prediction_v2.json')
    else:
        from d1sim import throttle_v1 as tv1
        from d1sim.tools.predict_night_1003 import params as v1p
        p = v1p()
        variants = {rel: (dict(p, ctrl=dict(p['ctrl'], NPU=dict(p['ctrl']['NPU'], release=rel))), lambda T0: {}) for rel in ('fast', 'skin')}
        R = dict(model='v1 M-P r3 (d1sim/throttle_v1.py + profiles/throttle_v1_*.json, 고정 3050e09) — 밤 1005 칸, 새 구동 파일 (v1 코드 무수정)',
                 variants={k: k for k in variants}, BAT0_rule='v1 은 BAT0 를 쓰지 않는다', **base)
        R['cells'], R['pairs'], R['resources'] = predict(J, tv1.simulate, variants, R0)
        out = os.path.join(OUT, 'night_1005_prediction_v1.json')
    json.dump(R, open(out, 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    print('->', out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
