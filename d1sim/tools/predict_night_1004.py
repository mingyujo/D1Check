"""predict_night_1004.py — frozen model predictions for the 2026-10-04 night cells, written BEFORE the measurement.

Cells (sim/밤1004_사전등록_v1.md §2~§5, chains tools/chains/*.json):
  n50p  : NPU d50 60 -> d100 420 -> d50 480        g50p : GPU d50 60 -> d100 300 -> d50 480
  gi300 : GPU d10 60 -> d100 600 -> d1 300 -> d100 300   ni300: NPU d10 60 -> d100 300 -> d1 300 -> d100 180
  (EffN420: unsupported — no EfficientNet NPU power trace in the model)
Start SKIN 29.5 and 30.5, A0 = -1.0 [P typical]. Duty = first duty% of each 10 s period active; d1 = idle in the 1 s grid.
Judgement rules are the pre-registered ones (ref_d50 = segment-0 median; release = bin k and next 3 <= ref x (1+delta),
NPU delta 0.03 / GPU 0.10; retighten = bin k and next 3 >= ref_d100 x 1.10 (GPU) / 1.06 (NPU); classes as in the prereg).

  py d1sim/tools/predict_night_1004.py              # v2 adopted form (+ variants) + reference forms  -> d1sim/out/night_1004_prediction_v2.json
  py d1sim/tools/predict_night_1004.py --model v1   # frozen v1 (3050e09) through its own module, no v1 code touched -> night_1004_prediction_v1.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
PROFILES = os.path.join(ROOT, 'd1sim', 'profiles')
OUT = os.path.join(ROOT, 'd1sim', 'out')
CHAINS = {
    'n50p': [('NPU', 50, 60), ('NPU', 100, 420), ('NPU', 50, 480)],
    'g50p': [('GPU', 50, 60), ('GPU', 100, 300), ('GPU', 50, 480)],
    'gi300': [('GPU', 10, 60), ('GPU', 100, 600), ('GPU', 1, 300), ('GPU', 100, 300)],
    'ni300': [('NPU', 10, 60), ('NPU', 100, 300), ('NPU', 1, 300), ('NPU', 100, 180)],
}


def duty_flags(duty, dur):
    return [(k % 10) < duty // 10 for k in range(dur)]


def schedule(cell):
    return [(i, res, (True if duty == 100 else duty_flags(duty, dur)), dur) for i, (res, duty, dur) in enumerate(CHAINS[cell])]


def med(rows, seg, a, b):
    v = sorted(r['ratio'] for r in rows if r['seg'] == seg and a <= r['t'] < b and r['ratio'] is not None)
    return v[len(v) // 2] if v else None


def at(rows, seg, t):
    return next((r for r in rows if r['seg'] == seg and r['t'] == t), None)


def held(bins, level, start=30, n=3):
    vals = [(t, m) for t, m in bins if m is not None]
    for i, (t, m) in enumerate(vals):
        if t >= start and m >= level and i + n < len(vals) and all(vals[j][1] >= level for j in range(i + 1, i + 1 + n)):
            return t
    return None


def first_k(pr, pred, last_k):
    for k in range(0, min(last_k, len(pr) - 4) + 1):
        if all(x is not None and pred(x) for x in pr[k:k + 4]):
            return k
    return None


def shape_of(pr, k):
    if k is None:
        return '중도절단'
    if k == 0:
        return '즉시'
    total = pr[0] - pr[k]
    steps = [pr[j - 1] - pr[j] for j in range(1, k + 1)]
    return '계단형' if (total > 0 and max(steps) / total >= 0.5) else '점진형'


def temps(rows, seg, ts):
    return [dict(t=t, skin=at(rows, seg, t)['skin'], ap=at(rows, seg, t)['ap'], status=at(rows, seg, t)['status']) for t in ts if at(rows, seg, t)]


def probe_cell(sim, bins_ratio, onset_rule, p, cell, T0, delta, heat_len, cls_fast=40):
    rows = sim(p, schedule(cell), T0, -1.0)
    ref = med(rows, 0, 0, 60)                                   # ref_d50 = segment-0 all-median (model: cold, ~1)
    a3 = [None if m is None else m / ref for t, m in bins_ratio(rows, 0)]
    hb = bins_ratio(rows, 1)
    ref30 = med(rows, 1, 0, 30)
    onset = onset_rule(hb, ref30)
    s1 = held(hb, 1.045 * ref30)
    end = at(rows, 1, heat_len - 1)
    pb = [None if m is None else m / ref for t, m in bins_ratio(rows, 2)]
    k = first_k(pb, lambda x: x <= 1 + delta, 44)
    rec = 10 * k if k is not None else None
    cls = ('R50-fast' if rec <= cls_fast else ('미분류' if rec == 50 else 'R50-slow')) if rec is not None else 'R50-none (440 s 안 미회복)'
    rel = at(rows, 2, rec) if rec is not None else None
    # re-tighten after release (k' and next 3 >= ref x 1.06 / 1.10)
    kk = None
    if k is not None:
        rest = pb[k + 4:]
        j = first_k(rest, lambda x: x >= 1 + 2 * delta, len(rest))
        kk = 10 * (k + 4 + j) if j is not None else None
    heat_win = (360, 420) if cell == 'n50p' else (240, 300)
    out = dict(T_start=T0, ref_d50_ratio=ref, A3_bins=a3, A3_stable=all(x is not None and abs(x - 1) <= 0.05 for x in a3),
               heat_onset_1_1_s=onset, heat_step1_s=s1, heat_ratio_window=f'{heat_win[0]}~{heat_win[1]}', heat_ratio_end=(med(rows, 1, *heat_win) / ref30 if ref30 else None),
               heat_onset_skin_ap=(dict(skin=at(rows, 1, onset)['skin'], ap=at(rows, 1, onset)['ap']) if onset is not None else None),
               heat_step1_skin_ap=(dict(skin=at(rows, 1, s1)['skin'], ap=at(rows, 1, s1)['ap']) if s1 is not None else None),
               heat_end_skin=end['skin'], heat_end_ap=end['ap'], heat_end_status=end['status'], heat_end_bat='미모형화',
               heating_sufficient=((med(rows, 1, *heat_win) / ref30) >= (1.06 if cell == 'n50p' else 1.5)) if ref30 else None,
               probe_bins_ratio_first12=pb[:12], probe_release_s=rec, probe_release_shape=shape_of(pb, k), probe_class=cls,
               probe_bins_1_5_median=(sorted(x for x in pb[1:6] if x is not None)[len([x for x in pb[1:6] if x is not None]) // 2] if any(x is not None for x in pb[1:6]) else None),
               release_skin_ap=(dict(skin=rel['skin'], ap=rel['ap'], status=rel['status']) if rel else None), retighten_after_release_s=kk,
               probe_temps=temps(rows, 2, (0, 60, 120, 240, 479)))
    return out


def idle_cell(sim, bins_ratio, onset_rule, p, cell, T0):
    rows = sim(p, schedule(cell), T0, -1.0)
    ref = med(rows, 0, 0, 60)
    hb = bins_ratio(rows, 1)
    ref100 = med(rows, 1, 0, 30)
    onset = onset_rule(hb, ref100)
    s1 = held(hb, 1.045 * ref100)
    heat_len = CHAINS[cell][1][2]
    end = at(rows, 1, heat_len - 1)
    win = (540, 600) if cell == 'gi300' else (240, 300)
    rest = temps(rows, 2, (0, 60, 120, 180, 240, 299))
    pb = [None if m is None else m / ref100 for t, m in bins_ratio(rows, 3)]
    thr = 1.10 if cell == 'gi300' else 1.06
    last_k = 26 if cell == 'gi300' else 14
    k = first_k(pb, lambda x: x >= thr, last_k)
    ret = 10 * k if k is not None else None
    if ret is None:
        cls = '재조임 없음'
    elif ret <= 20:
        cls = '300 s 유휴로도 재조임을 못 늦춘다 (≤ 20 s)'
    elif ret >= 60:
        cls = '300 s 유휴가 재조임을 늦춘다 (유예 레버, ≥ 60 s)'
    else:
        cls = '중간 (30~50 s)'
    rr = at(rows, 3, ret) if ret is not None else None
    reheat_len = CHAINS[cell][3][2]
    return dict(T_start=T0, ref_d10_ratio=ref, ref_d100_ratio=ref100, heat_onset_1_1_s=onset, heat_step1_s=s1,
                heat_ratio_window=f'{win[0]}~{win[1]}', heat_ratio_end=(med(rows, 1, *win) / ref100 if ref100 else None),
                heat_end_skin=end['skin'], heat_end_ap=end['ap'], heat_end_status=end['status'],
                heating_sufficient=((med(rows, 1, *win) / ref100) >= 1.06) if (cell == 'ni300' and ref100) else None,
                rest_temps=rest, reheat_bins_ratio_first12=pb[:12], retighten_s=ret, retighten_class=cls,
                retighten_skin_ap=(dict(skin=rr['skin'], ap=rr['ap'], status=rr['status']) if rr else None),
                reheat_first_bin=pb[0] if pb else None, reheat_ratio_240_300=(med(rows, 3, 240, reheat_len) / ref100 if (cell == 'gi300' and ref100) else None),
                reheat_end_skin_ap=dict(skin=at(rows, 3, reheat_len - 1)['skin'], ap=at(rows, 3, reheat_len - 1)['ap']))


def cells_for(sim, bins_ratio, onset_rule, p, label):
    out = {}
    for T0 in (29.5, 30.5):
        out.setdefault('n50p', {})[f'{T0}/{label}'] = probe_cell(sim, bins_ratio, onset_rule, p, 'n50p', T0, 0.03, 420)
        out.setdefault('g50p', {})[f'{T0}/{label}'] = probe_cell(sim, bins_ratio, onset_rule, p, 'g50p', T0, 0.10, 300)
        out.setdefault('gi300', {})[f'{T0}/{label}'] = idle_cell(sim, bins_ratio, onset_rule, p, 'gi300', T0)
        out.setdefault('ni300', {})[f'{T0}/{label}'] = idle_cell(sim, bins_ratio, onset_rule, p, 'ni300', T0)
    return out


def merge(dst, src):
    for cell, d in src.items():
        dst.setdefault(cell, {}).update(d)


def v2_params(prefix='throttle_v2_'):
    tp = json.load(open(os.path.join(PROFILES, f'{prefix}thermal.json'), encoding='utf-8'))
    tp = {k: tp[k] for k in ('tau_f', 'G_f', 'G_s', 'tau_s', 'tau_a', 'G_a', 'P_idle', 'c_f', 'c_s', 'c_a')}
    ctrl, power, L0 = {}, {}, {}
    for res, fn in (('GPU', 'GPU_compiledmodel'), ('NPU', 'NPU'), ('CPU4', 'CPU4_interpreter')):
        d = json.load(open(os.path.join(PROFILES, f'{prefix}{fn}.json'), encoding='utf-8'))
        ctrl[res] = dict(d['ctrl']); power[res] = {k: d['power'][k] for k in ('P_idle', 'P0', 'alpha')}; L0[res] = d['L0_ms']
    return dict(thermal=tp, ctrl=ctrl, power=power, L0=L0)


def npu_variants(p):
    """Variants frozen because the data cannot fix them (prereg v2 §7): kappa_NPU (Lk) or theta_NPU (Lb)."""
    c = p['ctrl']['NPU']
    if c['form'] == 'Lk':
        kv = c.get('kappa_variants') or {'kappa_lo': c['kappa'], 'kappa_2': 2 * c['kappa'], 'kappa_inf': 1e9}
        return {name: dict(p, ctrl=dict(p['ctrl'], NPU=dict(c, kappa=val))) for name, val in kv.items()}
    if c['form'] == 'Lb':
        return {f'theta_{t}': dict(p, ctrl=dict(p['ctrl'], NPU=dict(c, theta=t))) for t in (0.3, 0.75)}
    return {'S': p}


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', default='v2', choices=['v1', 'v2'])
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if a.model == 'v1':
        from d1sim import throttle_v1 as tv1
        from d1sim.tools.predict_night_1003 import params as v1p
        p = v1p()
        R = dict(model='v1 M-P r3 (d1sim/throttle_v1.py + profiles/throttle_v1_*.json, 커밋 3050e09) — 밤 1004 칸, 새 구동 파일 (v1 코드 무수정)',
                 chains={k: ' → '.join(f'{r} d{d} {s}' for r, d, s in v) for k, v in CHAINS.items()},
                 variants=['fast', 'skin'], cells={})
        onset = lambda hb, ref: tv1.onset_time_ref(hb, ref)
        for rel in ('fast', 'skin'):
            pp = dict(p, ctrl=dict(p['ctrl'], NPU=dict(p['ctrl']['NPU'], release=rel)))
            merge(R['cells'], cells_for(tv1.simulate, tv1.bins_ratio, onset, pp, rel))
        out = os.path.join(OUT, 'night_1004_prediction_v1.json')
    else:
        from d1sim import throttle_v2 as tv2
        p = v2_params()
        form = p['ctrl']['NPU']['form']
        fit = json.load(open(os.path.join(OUT, 'throttle_fit_v2.json'), encoding='utf-8'))
        R = dict(model=f'v2 V2-{form} (d1sim/throttle_v2.py + profiles/throttle_v2_*.json)', adopted_form=f'V2-{form}', v2_status=fit.get('v2_status'),
                 chains={k: ' → '.join(f'{r} d{d} {s}' for r, d, s in v) for k, v in CHAINS.items()},
                 sensors={r: p['ctrl'][r]['sensor'] for r in ('GPU', 'NPU')}, variants={}, cells={}, reference_forms={})
        onset = lambda hb, ref: tv2.onset_time_ref(hb, ref)
        vars_ = npu_variants(p)
        R['variants'] = {k: (v['ctrl']['NPU'].get('kappa') if form == 'Lk' else v['ctrl']['NPU'].get('theta')) for k, v in vars_.items()}
        for name, pp in vars_.items():
            merge(R['cells'], cells_for(tv2.simulate, tv2.bins_ratio, onset, pp, name))
        # reference: cooling c = 1 (v1 cooling) on the adopted form; and the non-adopted forms' closed-loop params
        pc1 = dict(p, thermal=dict(p['thermal'], c_f=1.0, c_s=1.0, c_a=1.0))
        R['reference_forms']['adopted_form_cooling_c1'] = cells_for(tv2.simulate, tv2.bins_ratio, onset, pc1, 'c1')
        for other, cand in fit.get('candidates', {}).items():
            if other == form or '_params_cm' not in cand:
                continue
            po = cand['_params_cm']
            po['ctrl']['CPU4'] = dict(po['ctrl']['CPU4'], v1_controller=True)
            R['reference_forms'][f'V2-{other}'] = {}
            for name, pp in npu_variants(po).items():
                merge(R['reference_forms'][f'V2-{other}'], cells_for(tv2.simulate, tv2.bins_ratio, onset, pp, name))
        out = os.path.join(OUT, 'night_1004_prediction_v2.json')
    R['effn420'] = 'unsupported — EfficientNet NPU 전력 자료 없음 (모형 예측 만들지 않음)'
    json.dump(R, open(out, 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    print('->', out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
