"""v0_driver_1003.py — run the FROZEN throttle model v0 against the 0928 / 1002 measurements (T1~T7).

Pre-registration: 산공학회/D1_ondevice/sim/v0_홀드아웃_사전등록_1003.md (mirror d1sim/docs/). v0 is imported from the
git-archive copies in C:/Users/rhoyo/AndroidStudioProjects/_scratch (80ca6c4 = frozen model, 4708788 = last v0 with
variants) — NOT from the working tree, and nothing in v0 is modified. Measured traces come from
d1sim/tools/extract_traces_v1.py (d1sim/data/trace_v1_*.csv). All verdicts are computed here and written to
d1sim/out/v0_holdout_1003.json (+ .md table). Deterministic, no randomness.

  py d1sim/tools/v0_driver_1003.py
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import statistics as st
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DATA = os.path.join(ROOT, 'd1sim', 'data')
OUT = os.path.join(ROOT, 'd1sim', 'out')
SIM = r'C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim'
SCR = r'C:\Users\rhoyo\AndroidStudioProjects\_scratch'
V0_FIX = os.path.join(SCR, 'v0_80ca6c4')
V0_LAST = os.path.join(SCR, 'v0_4708788')

# ---- import v0 (frozen copies only) ----
sys.path.insert(0, V0_LAST)
import d1sim.env as v0env            # noqa: E402
import d1sim.profile as v0prof       # noqa: E402
assert os.path.abspath(v0env.__file__).startswith(os.path.abspath(V0_LAST)), v0env.__file__
_spec = importlib.util.spec_from_file_location('v0fix_throttle', os.path.join(V0_FIX, 'd1sim', 'throttle.py'))
thr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(thr)
P_V0 = json.load(open(os.path.join(V0_FIX, 'd1sim', 'profiles', 'throttle_v0_GPU.json'), encoding='utf-8'))
PROF = v0prof.Profile(os.path.join(V0_LAST, 'd1sim', 'profiles', 'device_profile_S26.yaml'))

# ---- criteria (pre-registered) ----
CRIT = dict(T1=dict(onset_s=10, eq_pct=10, lat_mae_ms=0.5, skin_mae_c=0.5),
            T2=dict(onset_s=10, end_ratio_pct=10, skin_mae_c=0.5),
            T3=dict(recovery_diff_s=10, shape='계단형'),
            T4=dict(gain_low_min=0.03),
            T5=dict(onset_s=30, ratio_abs=0.05),
            T6=dict(onset_s=20, ratio_pct=10),
            T7=dict(first10_max=1.10, bin1_min=1.5))
S_THR = 1.10


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def fl(v):
    return None if v in ('', None) else float(v)


def rows1(tag, seg=0):
    return [r for r in csv.DictReader(open(os.path.join(DATA, f'trace_v1_{tag}.csv'), encoding='utf-8')) if int(r['seg']) == seg]


def rows10(tag, seg=0):
    rr = [r for r in csv.DictReader(open(os.path.join(DATA, f'trace_v1_10s_{tag}.csv'), encoding='utf-8')) if int(r['seg']) == seg]
    ref = next(r for r in rr if r['t_s'] == '-1')
    bins = [(int(r['t_s']), fl(r['lat_med_ms']), int(r['n_inf']), fl(r['power_w']), fl(r['SKIN'])) for r in rr if r['t_s'] != '-1']
    return dict(ref_lat=fl(ref['lat_med_ms']), ref_pw=fl(ref['power_w']), bins=bins)


MANIFEST = json.load(open(os.path.join(DATA, 'trace_v1_manifest.json'), encoding='utf-8'))


def t_start_of(tag, seg=0):
    for r in rows1(tag, seg):
        if r['SKIN'] != '':
            return float(r['SKIN'])
    raise RuntimeError(tag)


def active_flags(tag, seg=0):
    return [int(r['n_inf']) > 0 for r in rows1(tag, seg)]


# ============================================================ model runners
def sim_flags(p, T_start, flags, dt=1.0):
    """Frozen throttle.ThrottleState driven by a per-second busy pattern. Rows: t, s, lat (None when idle), power, T."""
    stt = thr.ThrottleState(p, T_start)
    out = []
    for k, busy in enumerate(flags):
        s = stt.s
        out.append(dict(t=k, s=s, lat=(p['L0'] / s) if busy else None, power=stt.power(busy), T=stt.T))
        stt.advance(dt, busy)
    return out


def bins10_model(rows, L):
    """10 s bins of model latency (median of the 1 s values with a latency), complete bins only."""
    n = int(L // 10)
    out = []
    for k in range(n):
        v = [r['lat'] for r in rows[k * 10:(k + 1) * 10] if r['lat'] is not None]
        out.append((k * 10, st.median(v) if v else None))
    return out


def onset(bins, ref):
    """1-1 rule via the frozen v0 function (None medians are skipped by filtering)."""
    return thr.onset_time_ref([(t, m) for t, m in bins if m is not None], ref)


def run_schedule(variant, T_start, schedule, dt=0.5):
    """Last-v0 Thermal (env.py) over segments. schedule = [(seg_id, resource, flags_per_second | None(idle), duration_s)].
    Returns rows: seg, t_seg, resource, executing, s(resource), skin, inv_s (latency ratio to L0 when executing)."""
    th = v0env.Thermal(PROF, dict(v0env.DEFAULT_VARIANT, **variant))
    th.t_start = T_start
    out = []
    for seg_id, res, flags, dur in schedule:
        n = int(round(dur / dt))
        for i in range(n):
            t = i * dt
            if flags is None:
                ex = False
            else:
                k = int(t)
                ex = bool(flags[k]) if k < len(flags) else False
            s = th.s(res) if res is not None else None
            out.append(dict(seg=seg_id, t=t, res=res, ex=ex, s=s, skin=th.skin(), inv_s=(1.0 / s) if (ex and s) else None))
            th.advance(dt, res if ex else None, ex)
    return out


def seg_bins(rows, seg_id, bin_s=10):
    rr = [r for r in rows if r['seg'] == seg_id]
    L = max(r['t'] for r in rr) + (rr[1]['t'] - rr[0]['t'])
    n = int(L // bin_s)
    out = []
    for k in range(n):
        v = [r['inv_s'] for r in rr if k * bin_s <= r['t'] < (k + 1) * bin_s and r['inv_s'] is not None]
        out.append((k * bin_s, st.median(v) if v else None))
    return out


def seg_median(rows, seg_id, t0=None, t1=None):
    v = [r['inv_s'] for r in rows if r['seg'] == seg_id and r['inv_s'] is not None and (t0 is None or r['t'] >= t0) and (t1 is None or r['t'] < t1)]
    return st.median(v) if v else None


def chain_schedule(tag, resources):
    """Build schedule from the manifest: segments with measured active flags, transitions idle."""
    man = MANIFEST[tag]
    sch = []
    for i, seg in enumerate(man['segments']):
        if i > 0:
            tr = man['transitions'][i - 1]
            sch.append((f't{i}', None, None, tr['duration_s']))
        sch.append((i, resources[i], active_flags(tag, i), seg['duration_s']))
    return sch


def p_for(resource):
    p = dict(P_V0)
    if resource != 'GPU':
        p['P0'] = PROF.P_load[resource]
        p['L0'] = PROF.L0_ms[resource]
    return p


# ============================================================ tests
def T1():
    tag = 'c1a'
    r1, r10 = rows1(tag), rows10(tag)
    T0 = t_start_of(tag)
    L = len(r1)
    mod = sim_flags(P_V0, T0, [True] * L)
    m10 = bins10_model(mod, L)
    meas10 = [(t, m) for t, m, n, pw, sk in r10['bins']]
    on_meas, on_mod = onset(meas10, r10['ref_lat']), onset(m10, P_V0['L0'])
    eq_meas = st.mean(fl(r['lat_med_ms']) for r in r1 if 1000 <= int(r['t_s']) < 1300 and r['lat_med_ms'] != '')
    eq_mod = st.mean(mod[t]['lat'] for t in range(1000, 1300))
    lat_mae = st.mean(abs(mm - m) for (t, m, n, pw, sk), (_, mm) in zip(r10['bins'], m10) if m is not None and mm is not None)
    pw_mae = st.mean(abs(st.mean(x['power'] for x in mod[t:t + 10]) - pw) for t, m, n, pw, sk in r10['bins'] if pw is not None)
    skin_mae = st.mean(abs(mod[int(r['t_s'])]['T'] - float(r['SKIN'])) for r in r1 if r['SKIN'] != '')
    c = CRIT['T1']
    fails = []
    if on_meas is None or on_mod is None or abs(on_mod - on_meas) > c['onset_s']:
        fails.append('진입')
    eq_err = 100 * (eq_mod / eq_meas - 1)
    if abs(eq_err) > c['eq_pct']:
        fails.append('평형 지연')
    if lat_mae > c['lat_mae_ms']:
        fails.append('지연 MAE')
    if skin_mae > c['skin_mae_c']:
        fails.append('SKIN MAE')
    # v0 §5-style 1200 s value (60 s window mean 1140~1200 / 1200~1260) for the C1a_결과 §6 side-by-side
    w = lambda a, b: dict(lat_ms=st.mean(mod[t]['lat'] for t in range(a, b)), power_w=st.mean(mod[t]['power'] for t in range(a, b)), T=mod[b - 1]['T'])  # noqa: E731
    return dict(test='T1', data='C1a GPU d100 1300 s (Interpreter)', nature='진짜 홀드아웃', T_start=T0, ref_meas_ms=r10['ref_lat'], L0_model_ms=P_V0['L0'],
                onset_meas_s=on_meas, onset_model_s=on_mod, onset_err_s=(on_mod - on_meas) if (on_mod is not None and on_meas is not None) else 'mismatch',
                eq_meas_ms=eq_meas, eq_model_ms=eq_mod, eq_err_pct=eq_err, lat_mae_ms=lat_mae, power_mae_w=pw_mae, skin_mae_c=skin_mae,
                model_1140_1200=w(1140, 1200), model_1200_1260=w(1200, 1260), model_600_660=w(600, 660),
                meas_skin_end=fl(r1[-1]['SKIN']), model_skin_end=mod[-1]['T'],
                criteria=c, fails=fails, verdict='v0 통과' if not fails else f"v0 불통과 ({'·'.join(fails)})",
                model_bins10=m10, meas_bins10=meas10)


def T2():
    tag = 'm3'
    r1, r10 = rows1(tag), rows10(tag)
    T0 = t_start_of(tag)
    flags = active_flags(tag)
    mod = sim_flags(P_V0, T0, flags)
    m10 = bins10_model(mod, len(flags))
    meas10 = [(t, m) for t, m, n, pw, sk in r10['bins']]
    on_meas, on_mod = onset(meas10, r10['ref_lat']), onset(m10, P_V0['L0'])
    end_meas_1s = st.median(fl(r['lat_med_ms']) for r in r1 if int(r['t_s']) >= len(flags) - 60 and r['lat_med_ms'] != '') / r10['ref_lat']
    exact = json.load(open(os.path.join(SIM, 'out_0928', 'M3.json'), encoding='utf-8'))[0]['end60']['lat_ratio']
    end_mod = st.median(x['lat'] for x in mod[-60:] if x['lat'] is not None) / P_V0['L0']
    skin_mae = st.mean(abs(mod[int(r['t_s'])]['T'] - float(r['SKIN'])) for r in r1 if r['SKIN'] != '')
    c = CRIT['T2']
    fails = []
    on_err = (on_mod - on_meas) if (on_mod is not None and on_meas is not None) else 'mismatch'
    if on_err == 'mismatch' or abs(on_err) > c['onset_s']:
        fails.append('진입')
    end_err = 100 * (end_mod / exact - 1)
    if abs(end_err) > c['end_ratio_pct']:
        fails.append('끝 배율')
    if skin_mae > c['skin_mae_c']:
        fails.append('SKIN MAE')
    active_pattern = [k % 10 for k, f in enumerate(flags[:40]) if f]
    return dict(test='T2', data='M3 GPU d50 600 s (Interpreter)', nature='진짜 홀드아웃', T_start=T0, ref_meas_ms=r10['ref_lat'],
                active_seconds_in_period_first40=sorted(set(active_pattern)), onset_meas_s=on_meas, onset_model_s=on_mod, onset_err_s=on_err,
                end60_ratio_meas_exact=exact, end60_ratio_meas_from_1s=end_meas_1s, end60_ratio_model=end_mod, end60_err_pct=end_err,
                skin_mae_c=skin_mae, meas_skin_end=fl(r1[-1]['SKIN']), model_skin_end=mod[-1]['T'],
                criteria=c, fails=fails, verdict='v0 통과' if not fails else f"v0 불통과 ({'·'.join(fails)})",
                model_bins10=m10, meas_bins10=meas10)


def m1_judge_rule(pr):
    """M1M2 v1 §2 on a list of probe bin ratios."""
    last = len(pr) - 1 - 3
    k_rec = None
    for k in range(0, last + 1):
        win = pr[k:k + 4]
        if all(r is not None and r <= S_THR for r in win):
            k_rec = k
            break
    if k_rec is None:
        return dict(recovered=False, recovery_s=None, shape='중도절단', step_fraction=None)
    if k_rec == 0:
        return dict(recovered=True, recovery_s=0, shape='즉시 회복 — 모양 판정 해당 없음', step_fraction=None)
    total = pr[0] - pr[k_rec]
    steps = [pr[j - 1] - pr[j] for j in range(1, k_rec + 1)]
    frac = (max(steps) / total) if total > 0 else None
    return dict(recovered=True, recovery_s=10 * k_rec, shape=('계단형' if frac is not None and frac >= 0.5 else '점진형'), step_fraction=frac)


def T3():
    tag = 'm1'
    T0 = t_start_of(tag, 0)
    judge = json.load(open(os.path.join(SIM, 'out_1002', 'M1_judge.json'), encoding='utf-8'))
    meas = dict(recovery_s=judge['recovery']['recovery_s'], shape=judge['shape'], ref_d10_ms=judge['ref_d10_ms'],
                probe_bins_ratio=judge['probe']['bins_ratio'][:8], heat=judge['heat_segment'])
    out = dict(test='T3', data='M1 GPU d10 60 → d100 1200 → d10 300 (CompiledModel) — 배율만', nature='구조 시험 (엔진 다름)', T_start=T0,
               measured=meas, variants={}, criteria=CRIT['T3'])
    for rec in ('same', 'slow'):
        rows = run_schedule(dict(recovery=rec), T0, chain_schedule(tag, ['GPU', 'GPU', 'GPU']))
        ref_d10 = seg_median(rows, 0)
        pb = seg_bins(rows, 2)
        pr = [None if m is None else m / ref_d10 for t, m in pb]
        j = m1_judge_rule(pr)
        hb = seg_bins(rows, 1)
        heat = dict(onset_s=onset(hb, 1.0), ratio_540_600=seg_median(rows, 1, 540, 600), ratio_1000_1200=seg_median(rows, 1, 1000, 1200))
        diff = None if j['recovery_s'] is None else j['recovery_s'] - meas['recovery_s']
        keep = diff is not None and abs(diff) <= CRIT['T3']['recovery_diff_s'] and j['shape'] == meas['shape']
        skin_probe0 = next(r['skin'] for r in rows if r['seg'] == 2)
        out['variants'][rec] = dict(ref_d10_model_ratio=ref_d10, probe_bins_ratio=pr[:8], judge=j, recovery_diff_s=diff, heat=heat,
                                    model_skin_probe_start=skin_probe0, meas_skin_probe_start=judge['probe']['start_thermal']['SKIN'],
                                    verdict='회복 구조 유지' if keep else '기각')
    return out


def T4():
    judges = {'m2': json.load(open(os.path.join(SIM, 'out_1002', 'M2_npu_judge.json'), encoding='utf-8')),
              'm2r': json.load(open(os.path.join(SIM, 'out_1002', 'M2r_gpu_judge.json'), encoding='utf-8'))}
    res_of = {'m2': ['GPU', 'NPU'], 'm2r': ['NPU', 'GPU']}
    out = dict(test='T4', data='M2 (GPU→NPU) 4 + M2r (NPU→GPU) 4', nature='구조 시험', criteria=CRIT['T4'],
               measured={g: dict(gain_low=j['gain_low'], s_C=j['s_C'], v_ms=j['v_ms'], decision=j['decision']) for g, j in judges.items()},
               variants={})
    for coup in ('independent', 'shared'):
        for npu in ('none', 'scaled'):
            vid = f'{coup}/{npu}'
            res = {}
            for g in ('m2', 'm2r'):
                v, first, second, starts = {}, {}, {}, {}
                for arm in ('C1', 'H1', 'H2', 'C2'):
                    tag = f'{g}_{arm}'
                    T0 = t_start_of(tag, 0)
                    rows = run_schedule(dict(coupling=coup, npu_cpu_throttle=npu), T0, chain_schedule(tag, res_of[g]))
                    v[arm] = seg_median(rows, 1)
                    first[arm] = seg_median(rows, 1, 0, 10)
                    second[arm] = seg_median(rows, 1, 10, 20)
                    starts[arm] = dict(T_start=T0, model_skin_victim_start=next(r['skin'] for r in rows if r['seg'] == 1),
                                       meas_skin_victim_start=judges[g]['arms'][arm]['victim_start_thermal']['SKIN'])
                gl = min(v['H1'], v['H2']) / max(v['C1'], v['C2']) - 1
                cmean = (v['C1'] + v['C2']) / 2
                res[g] = dict(v_model_ratio=v, gain_low=gl, victim_first10_over_control={a: first[a] / cmean for a in ('H1', 'H2')},
                              victim_10_20_over_control={a: second[a] / cmean for a in ('H1', 'H2')}, starts=starts,
                              ok=gl >= CRIT['T4']['gain_low_min'])
            out['variants'][vid] = dict(directions=res, verdict='유지' if all(r['ok'] for r in res.values()) else
                                        f"기각 ({'·'.join(g for g, r in res.items() if not r['ok'])} gain_low < 3 %)")
    return out


def T5():
    tag = 'n1300'
    r1, r10 = rows1(tag), rows10(tag)
    T0 = t_start_of(tag)
    L = len(r1)
    meas10 = [(t, m) for t, m, n, pw, sk in r10['bins']]
    on_meas = onset(meas10, r10['ref_lat'])
    tab = json.load(open(os.path.join(SIM, 'out_1002', 'N1300_table.json'), encoding='utf-8'))
    end_meas = tab['last60']['ratio']
    out = dict(test='T5', data='N1300 NPU d100 1300 s (CompiledModel)', nature='구조 시험', T_start=T0, ref_meas_ms=r10['ref_lat'],
               onset_meas_s=on_meas, end60_ratio_meas=end_meas, criteria=CRIT['T5'], variants={})
    for npu in ('none', 'scaled'):
        if npu == 'none':
            on_mod, end_mod, first_s_below = None, 1.0, None
            m10 = [(t, 1.0) for t, _ in meas10]
        else:
            p = p_for('NPU')
            mod = sim_flags(p, T0, [True] * L)
            m10 = bins10_model(mod, L)
            m10 = [(t, None if m is None else m / p['L0']) for t, m in m10]
            on_mod = onset(m10, 1.0)
            end_mod = st.median(x['lat'] for x in mod[-60:]) / p['L0']
            first_s_below = next((x['t'] for x in mod if x['s'] < 1 / S_THR), None)
        on_err = (on_mod - on_meas) if (on_mod is not None and on_meas is not None) else 'mismatch'
        r_err = end_mod - end_meas
        keep = on_err != 'mismatch' and abs(on_err) <= CRIT['T5']['onset_s'] and abs(r_err) <= CRIT['T5']['ratio_abs']
        out['variants'][npu] = dict(onset_model_s=on_mod, onset_err_s=on_err, end60_ratio_model=end_mod, end60_ratio_err=r_err,
                                    first_second_s_below_1_over_1p1=first_s_below, model_bins10_ratio_300_500=[(t, m) for t, m in m10 if 280 <= t <= 500],
                                    verdict='유지' if keep else '기각')
    return out


def T6():
    out = dict(test='T6', data='CPU4 d100 600 s r1·r2 (Interpreter)', nature='구조 시험', criteria=CRIT['T6'], runs={})
    p = p_for('CPU4')
    allok = True
    for tag in ('c600_r1', 'c600_r2'):
        r1, r10 = rows1(tag), rows10(tag)
        T0 = t_start_of(tag)
        L = len(r1)
        mod = sim_flags(p, T0, [True] * L)
        m10 = [(t, None if m is None else m / p['L0']) for t, m in bins10_model(mod, L)]
        meas10 = [(t, m) for t, m, n, pw, sk in r10['bins']]
        on_meas, on_mod = onset(meas10, r10['ref_lat']), onset(m10, 1.0)
        plat_meas = st.mean(fl(r['lat_med_ms']) for r in r1 if 240 <= int(r['t_s']) < 600 and r['lat_med_ms'] != '') / r10['ref_lat']
        plat_mod = st.mean(mod[t]['lat'] for t in range(240, 600)) / p['L0']
        on_err = (on_mod - on_meas) if (on_mod is not None and on_meas is not None) else 'mismatch'
        r_err = 100 * (plat_mod / plat_meas - 1)
        ok = on_err != 'mismatch' and abs(on_err) <= CRIT['T6']['onset_s'] and abs(r_err) <= CRIT['T6']['ratio_pct']
        allok &= ok
        skin_mae = st.mean(abs(mod[int(r['t_s'])]['T'] - float(r['SKIN'])) for r in r1 if r['SKIN'] != '')
        out['runs'][tag] = dict(T_start=T0, ref_meas_ms=r10['ref_lat'], onset_meas_s=on_meas, onset_model_s=on_mod, onset_err_s=on_err,
                                plateau_240_600_meas=plat_meas, plateau_240_600_model=plat_mod, plateau_err_pct=r_err, skin_mae_c=skin_mae,
                                first10_ratio_meas=meas10[0][1] / r10['ref_lat'], ok=ok)
    out['verdict'] = '유지' if allok else '기각'
    return out


def T7(t4):
    judge = json.load(open(os.path.join(SIM, 'out_1002', 'M2r_gpu_judge.json'), encoding='utf-8'))
    cmean = (judge['v_ms']['C1'] + judge['v_ms']['C2']) / 2
    meas = {a: dict(skin_start=judge['arms'][a]['victim_start_thermal']['SKIN'], status=judge['arms'][a]['victim_start_thermal']['thermal_status'],
                    first10_over_control=judge['arms'][a]['bins10'][0]['median_ms'] / cmean,
                    bin_10_20_over_control=judge['arms'][a]['bins10'][1]['median_ms'] / cmean) for a in ('H1', 'H2')}
    static = {}
    for a in ('H1', 'H2'):
        s = thr.s_of(meas[a]['skin_start'], P_V0)
        static[a] = dict(s=s, first10_ratio=1 / s, bin_10_20_ratio=1 / s)
    static_ok = all(st_['first10_ratio'] <= CRIT['T7']['first10_max'] and st_['bin_10_20_ratio'] >= CRIT['T7']['bin1_min'] for st_ in static.values())
    chain = {}
    for vid, v in t4['variants'].items():
        d = v['directions']['m2r']
        f, s2 = d['victim_first10_over_control'], d['victim_10_20_over_control']
        ok = all(f[a] <= CRIT['T7']['first10_max'] and s2[a] >= CRIT['T7']['bin1_min'] for a in ('H1', 'H2'))
        chain[vid] = dict(first10=f, bin_10_20=s2, verdict='유지' if ok else '정적 지도 기각')
    return dict(test='T7', data='M2r H1·H2 피해자 GPU 첫 10 s / 10~20 s (대조 피해자 평균 대비)', nature='판별 관측', criteria=CRIT['T7'],
                measured=meas, static_map=static, static_verdict='유지' if static_ok else '정적 지도 기각', chain_from_T4=chain)


# ============================================================ report
def fmt(x, n=3):
    if x is None:
        return '—'
    if isinstance(x, str):
        return x
    return f'{x:.{n}f}'


def md_table(R):
    L = ['# v0 홀드아웃 판정 — 출력 (d1sim/tools/v0_driver_1003.py)', '',
         f"v0 import: `{R['v0']['fixed_dir']}` throttle.py SHA `{R['v0']['throttle_sha'][:16]}…` · params SHA `{R['v0']['params_sha'][:16]}…` · env.py (4708788) SHA `{R['v0']['env_sha'][:16]}…`", '',
         '| 시험 | 설정 | 지표 | 예측 (v0) | 실측 | 오차 | 기준 | 판정 |', '|---|---|---|---|---|---|---|---|']
    t = R['T1']
    L.append(f"| T1 C1a | 고정판 | 진입 s | {fmt(t['onset_model_s'],0)} | {fmt(t['onset_meas_s'],0)} | {fmt(t['onset_err_s'],0)} | ≤ 10 | {t['verdict']} |")
    L.append(f"| | | 평형 지연 1000~1300 s ms | {fmt(t['eq_model_ms'])} | {fmt(t['eq_meas_ms'])} | {fmt(t['eq_err_pct'],1)} % | ≤ 10 % | |")
    L.append(f"| | | 지연 MAE 10 s ms | | | {fmt(t['lat_mae_ms'])} | ≤ 0.5 | |")
    L.append(f"| | | 전력 MAE 10 s W (보고만) | | | {fmt(t['power_mae_w'])} | — | |")
    L.append(f"| | | SKIN MAE 1 s ℃ | 끝 {fmt(t['model_skin_end'],2)} | 끝 {fmt(t['meas_skin_end'],1)} | {fmt(t['skin_mae_c'])} | ≤ 0.5 | |")
    t = R['T2']
    L.append(f"| T2 M3 d50 | 고정판 · 가동 초 {t['active_seconds_in_period_first40']} | 진입 s | {fmt(t['onset_model_s'],0)} | {fmt(t['onset_meas_s'],0)} | {fmt(t['onset_err_s'],0)} | ≤ 10 | {t['verdict']} |")
    L.append(f"| | | 끝 60 s 배율 | {fmt(t['end60_ratio_model'])} | {fmt(t['end60_ratio_meas_exact'])} | {fmt(t['end60_err_pct'],1)} % | ≤ 10 % | |")
    L.append(f"| | | SKIN MAE ℃ | 끝 {fmt(t['model_skin_end'],2)} | 끝 {fmt(t['meas_skin_end'],1)} | {fmt(t['skin_mae_c'])} | ≤ 0.5 | |")
    t = R['T3']
    for k, v in t['variants'].items():
        L.append(f"| T3 M1 | recovery={k} | 회복 s · 모양 | {fmt(v['judge']['recovery_s'],0)} · {v['judge']['shape']} | {t['measured']['recovery_s']} · {t['measured']['shape']} | {fmt(v['recovery_diff_s'],0)} | ≤ 10 · 계단형 | {v['verdict']} |")
        L.append(f"| | | 탐침 첫 8칸 배율 | {[round(x,3) if x else None for x in v['probe_bins_ratio']]} | {[round(x,3) for x in t['measured']['probe_bins_ratio']]} | | 보조 | |")
        L.append(f"| | | 가열 진입 · ×540~600 · ×1000~1200 | {fmt(v['heat']['onset_s'],0)} · {fmt(v['heat']['ratio_540_600'])} · {fmt(v['heat']['ratio_1000_1200'])} | {t['measured']['heat']['onset_s']} · {fmt(t['measured']['heat']['ratio_540_600'])} · {fmt(t['measured']['heat']['ratio_1000_1200'])} | | 보조 | |")
    t = R['T4']
    for k, v in t['variants'].items():
        d = v['directions']
        L.append(f"| T4 M2 | {k} | gain_low GPU→NPU / NPU→GPU | {fmt(d['m2']['gain_low'],4)} / {fmt(d['m2r']['gain_low'],4)} | {fmt(t['measured']['m2']['gain_low'],4)} / {fmt(t['measured']['m2r']['gain_low'],4)} | | 둘 다 ≥ 0.03 | {v['verdict']} |")
    t = R['T5']
    for k, v in t['variants'].items():
        L.append(f"| T5 N1300 | npu={k} | 진입 s · 끝 60 s 배율 | {fmt(v['onset_model_s'],0)} · {fmt(v['end60_ratio_model'])} | {t['onset_meas_s']} · {fmt(t['end60_ratio_meas'])} | {fmt(v['onset_err_s'],0)} · {fmt(v['end60_ratio_err'])} | ≤ 30 · ≤ 0.05 | {v['verdict']} |")
    t = R['T6']
    for k, v in t['runs'].items():
        L.append(f"| T6 {k} | cpu=scaled | 진입 s · ×240~600 | {fmt(v['onset_model_s'],0)} · {fmt(v['plateau_240_600_model'])} | {v['onset_meas_s']} · {fmt(v['plateau_240_600_meas'])} | {fmt(v['onset_err_s'],0)} · {fmt(v['plateau_err_pct'],1)} % | ≤ 20 · ≤ 10 % | {'유지' if v['ok'] else '기각'} (전체 {t['verdict']}) |")
    t = R['T7']
    for a, v in t['static_map'].items():
        m = t['measured'][a]
        L.append(f"| T7 M2r {a} | 정적 지도 T={m['skin_start']} | 첫 10 s · 10~20 s 배율 | {fmt(v['first10_ratio'],2)} · {fmt(v['bin_10_20_ratio'],2)} | {fmt(m['first10_over_control'],2)} · {fmt(m['bin_10_20_over_control'],2)} | | ≤ 1.10 · ≥ 1.5 | {t['static_verdict']} |")
    for k, v in t['chain_from_T4'].items():
        L.append(f"| T7 연쇄 | {k} | 첫 10 s · 10~20 s (H1/H2) | {fmt(v['first10']['H1'],2)}/{fmt(v['first10']['H2'],2)} · {fmt(v['bin_10_20']['H1'],2)}/{fmt(v['bin_10_20']['H2'],2)} | 위와 같음 | | | {v['verdict']} |")
    return '\n'.join(L) + '\n'


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    os.makedirs(OUT, exist_ok=True)
    R = dict(v0=dict(fixed_dir=V0_FIX, last_dir=V0_LAST,
                     throttle_sha=sha(os.path.join(V0_FIX, 'd1sim', 'throttle.py')),
                     throttle_sha_last=sha(os.path.join(V0_LAST, 'd1sim', 'throttle.py')),
                     params_sha=sha(os.path.join(V0_FIX, 'd1sim', 'profiles', 'throttle_v0_GPU.json')),
                     env_sha=sha(os.path.join(V0_LAST, 'd1sim', 'env.py')), params=P_V0,
                     manifest_tags=sorted(k for k in MANIFEST if not k.startswith('_'))))
    R['T1'] = T1(); print('T1', R['T1']['verdict'], flush=True)
    R['T2'] = T2(); print('T2', R['T2']['verdict'], flush=True)
    R['T3'] = T3(); print('T3', {k: v['verdict'] for k, v in R['T3']['variants'].items()}, flush=True)
    R['T4'] = T4(); print('T4', {k: v['verdict'] for k, v in R['T4']['variants'].items()}, flush=True)
    R['T5'] = T5(); print('T5', {k: v['verdict'] for k, v in R['T5']['variants'].items()}, flush=True)
    R['T6'] = T6(); print('T6', R['T6']['verdict'], flush=True)
    R['T7'] = T7(R['T4']); print('T7', R['T7']['static_verdict'], flush=True)
    json.dump(R, open(os.path.join(OUT, 'v0_holdout_1003.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    md = md_table(R)
    open(os.path.join(OUT, 'v0_holdout_1003.md'), 'w', encoding='utf-8').write(md)
    print(md)
    return 0


if __name__ == '__main__':
    sys.exit(main())
