"""predict_night_1003.py — frozen v1 (M-P r3) predictions for the 2026-10-03 night cells, written BEFORE the measurement.

  M1-GPU 2nd run : tools/chains/m1_recovery_gpu_v1.json  (GPU d10 60 -> d100 1200 -> d10 300)
  M1-NPU         : tools/chains/m1_recovery_npu_v1.json  (NPU d10 60 -> d100 600 -> d10 600), release R-fast / R-skin
Start SKIN 29.5 and 30.5 (prompt 2-5), A0 = -1.0 [P typical]. Duty: first duty% of each 10 s period active (runner period 10 s).
Output d1sim/out/night_1003_prediction.json (+ .md). sim/v1_예측_밤1003.md quotes this file.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
from d1sim import throttle_v1 as tv1  # noqa: E402

PROFILES = os.path.join(ROOT, 'd1sim', 'profiles')
OUT = os.path.join(ROOT, 'd1sim', 'out')


def params():
    tp = json.load(open(os.path.join(PROFILES, 'throttle_v1_thermal.json'), encoding='utf-8'))
    tp = {k: tp[k] for k in ('tau_f', 'G_f', 'G_s', 'tau_s', 'tau_a', 'G_a', 'P_idle')}
    ctrl, power, L0 = {}, {}, {}
    for res, fn in (('GPU', 'GPU_compiledmodel'), ('NPU', 'NPU'), ('CPU4', 'CPU4_interpreter')):
        d = json.load(open(os.path.join(PROFILES, f'throttle_v1_{fn}.json'), encoding='utf-8'))
        ctrl[res] = dict(d['ctrl']); power[res] = {k: d['power'][k] for k in ('P_idle', 'P0', 'alpha')}; L0[res] = d['L0_ms']
    return dict(thermal=tp, ctrl=ctrl, power=power, L0=L0)


def duty_flags(duty, dur):
    return [(k % 10) < duty // 10 for k in range(dur)]


def recovery(pr):
    k_rec = None
    for k in range(0, len(pr) - 3):
        if all(x is not None and x <= 1.10 for x in pr[k:k + 4]):
            k_rec = k
            break
    if k_rec is None:
        return dict(recovery_s=None, censored=True, shape='중도절단')
    if k_rec == 0:
        return dict(recovery_s=0, censored=False, shape='즉시')
    total = pr[0] - pr[k_rec]
    steps = [pr[j - 1] - pr[j] for j in range(1, k_rec + 1)]
    return dict(recovery_s=10 * k_rec, censored=False, shape=('계단형' if total > 0 and max(steps) / total >= 0.5 else '점진형'))


def med(rows, seg, a, b):
    v = sorted(r['ratio'] for r in rows if r['seg'] == seg and a <= r['t'] < b and r['ratio'] is not None)
    return v[len(v) // 2] if v else None


def at(rows, seg, t):
    return next((r for r in rows if r['seg'] == seg and r['t'] == t), None)


def m1_gpu(p, T0):
    sch = [(0, 'GPU', duty_flags(10, 60), 60), ('t1', None, None, 0), (1, 'GPU', True, 1200), (2, 'GPU', duty_flags(10, 300), 300)]
    sch = [s for s in sch if s[3] > 0]
    rows = tv1.simulate(p, sch, T0, -1.0)
    ref = med(rows, 0, 0, 60)
    hb = tv1.bins_ratio(rows, 1)
    pb = [None if m is None else m / ref for t, m in tv1.bins_ratio(rows, 2)]
    rec = recovery(pb)
    k = rec['recovery_s'] // 10 if rec['recovery_s'] is not None else None
    heat_end = at(rows, 1, 1199)
    return dict(T_start=T0, heat_onset_s=tv1.onset_time_ref(hb, 1.0), ratio_540_600=med(rows, 1, 540, 600), ratio_1000_1200=med(rows, 1, 1000, 1200),
                heat_end_skin=heat_end['skin'], heat_end_ap=heat_end['ap'], heat_end_status=heat_end['status'],
                probe_bins_ratio_first8=pb[:8], recovery=rec,
                release_skin_ap=(dict(skin=at(rows, 2, 10 * k)['skin'], ap=at(rows, 2, 10 * k)['ap']) if k is not None else None))


def m1_npu(p, T0, release):
    pp = dict(p, ctrl=dict(p['ctrl'], NPU=dict(p['ctrl']['NPU'], release=release)))
    sch = [(0, 'NPU', duty_flags(10, 60), 60), (1, 'NPU', True, 600), (2, 'NPU', duty_flags(10, 600), 600)]
    rows = tv1.simulate(pp, sch, T0, -1.0)
    ref = med(rows, 0, 0, 60)
    hb = tv1.bins_ratio(rows, 1)
    # step times: first bin >= 1.045 held 3 (step 1) ; 1-1 onset (step 2)
    def held(level):
        vals = [(t, m) for t, m in hb if m is not None]
        for i, (t, m) in enumerate(vals):
            if t >= 30 and m >= level and i + 3 < len(vals) and all(vals[j][1] >= level for j in range(i + 1, i + 4)):
                return t
        return None
    s1, s2 = held(1.045), tv1.onset_time_ref(hb, 1.0)
    pb = [None if m is None else m / ref for t, m in tv1.bins_ratio(rows, 2)]
    # NPU recovery per M1_NPU prereg: bin k and next 3 all <= ref*(1+delta), delta = 0.03 (1/3 of step 1) — see sim/M1_NPU_사전등록_v1.md
    def rec_delta(delta):
        for k in range(0, len(pb) - 3):
            if all(x is not None and x <= 1 + delta for x in pb[k:k + 4]):
                return 10 * k
        return None
    r03 = rec_delta(0.03)
    k = r03 // 10 if r03 is not None else None
    heat_end = at(rows, 1, 599)
    out = dict(T_start=T0, release=release, step1_s=s1, step2_s=s2, ratio_540_600=med(rows, 1, 540, 600), end60_ratio=med(rows, 1, 540, 600),
               heat_end_skin=heat_end['skin'], heat_end_ap=heat_end['ap'], heat_end_status=heat_end['status'],
               step1_skin_ap=(dict(skin=at(rows, 1, s1)['skin'], ap=at(rows, 1, s1)['ap']) if s1 is not None else None),
               step2_skin_ap=(dict(skin=at(rows, 1, s2)['skin'], ap=at(rows, 1, s2)['ap']) if s2 is not None else None),
               probe_bins_ratio_first12=pb[:12], recovery_delta003_s=r03, recovery_delta010_s=rec_delta(0.10),
               release_skin_ap=(dict(skin=at(rows, 2, 10 * k)['skin'], ap=at(rows, 2, 10 * k)['ap']) if k is not None else None),
               probe_skin_at=[dict(t=t, skin=at(rows, 2, t)['skin'], ap=at(rows, 2, t)['ap']) for t in (0, 30, 60, 120, 180, 300, 599)])
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    p = params()
    R = dict(model='v1 M-P r3 (d1sim/throttle_v1.py + profiles/throttle_v1_*.json)', m1_gpu={}, m1_npu={})
    for T0 in (29.5, 30.5):
        R['m1_gpu'][str(T0)] = m1_gpu(p, T0)
        for rel in ('fast', 'skin'):
            R['m1_npu'][f'{T0}/{rel}'] = m1_npu(p, T0, rel)
    os.makedirs(OUT, exist_ok=True)
    json.dump(R, open(os.path.join(OUT, 'night_1003_prediction.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    print(json.dumps(R, indent=1, ensure_ascii=False, default=str))
    return 0


if __name__ == '__main__':
    sys.exit(main())
