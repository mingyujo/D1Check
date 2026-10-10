"""predict_gpuerr.py — predicted side of the GPU model-error check (prereg §1, commit 35c9342) → d1sim/model_error_gpu_v1/predictions_gpu.json.
Written and run BEFORE commit ② (no measured thermal value is read here: inputs = chain commands, the frozen prediction files, the
start-SKIN columns (two-point rule, or the run's own public start SKIN for the frozen v2.2 N1 · N2 files) and each 판's frozen code).

Per run × 판 × column the record says where every number comes from (preflight (b) · (c)):
  frozen   : the item is copied from the frozen prediction JSON (path · SHA · column key) — never recomputed.
  generated: the SKIN series (1 s rows · 10 s bins) and the items the frozen file lacks are regenerated with THAT 판's frozen code and
             THAT 판's frozen driving rule, and the regeneration must reproduce the frozen scalars (REPRO_TOL) — else the 판 is flagged.
  v0  : d1sim/tools/v0_driver_1003 (frozen _scratch copies 80ca6c4 = 402acab tree) · T0 = the run's actual start SKIN · measured on/off flags (its own rule)
  v1  : d1sim/tools/predict_night_1003 (m1_gpu schedule) · sim/predict_pacing_v1_1003 schedule · throttle_v1 · columns 29.5 / 30.5 · A0 −1.0
  v2  : d1sim/tools/predict_night_1004 (schedule · v2_params · theta variants — GPU cells do not depend on θ_NPU, checked) · throttle_v2
  v2.1: d1sim/tools/predict_night_1005e (schedule · v21_params · run_metrics with the night judge's own threshold functions) · throttle_v21 · B0 = T0 − d_ref
  v2.2 frozen (N1 · N2 · N1 보충): same driving as fit_throttle_v22.predict_night (predict_night_1005e driver, model=effnet for N2) at the run's own start column
  v2.2 generated (no frozen file) and v2.2 two-point description rows: V3 v2 · P1j path (predict_v3.flags/schedule, Bresenham duty, A0 −1.0,
       BAT0 = SKIN0 − d_ref, throttle_v22.simulate model=mobilenet|effnet, engine INT (C1a · M3) | CM) at columns 29.5 / 30.5.

  py -X utf8 -m d1sim.model_error_gpu_v1.predict_gpuerr [--selftest]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import statistics
import subprocess
import sys

from d1sim.model_error_gpu_v1 import common as C

C.stdout_utf8()
from d1sim import throttle_v1 as tv1  # noqa: E402
from d1sim import throttle_v2 as tv2  # noqa: E402
from d1sim import throttle_v21 as tv21  # noqa: E402
from d1sim import throttle_v22 as tv22  # noqa: E402
from d1sim.tools import predict_night_1003 as pn3  # noqa: E402
from d1sim.tools import predict_night_1004 as pn4  # noqa: E402
from d1sim.tools import predict_night_1005e as pn5e  # noqa: E402
from d1sim.v3 import predict_v3 as PV  # noqa: E402

OUT = os.path.join(C.ROOT, 'd1sim', 'out')
FROZEN = {
    'v0': os.path.join(OUT, 'v0_holdout_1003.json'),
    'v1_m1gpu': os.path.join(OUT, 'night_1003_prediction.json'),
    'v1_pacing': os.path.join(C.ROOT, 's26', 'results', 'night_1003', 'night_1003_prediction_v1_pacing.json'),
    'v2': os.path.join(OUT, 'night_1004_prediction_v2.json'),
    'v21_N1': os.path.join(OUT, 'night_1005_prediction_v21.json'),
    'v21_N2': os.path.join(OUT, 'night_1005e_prediction_v21.json'),
    'v22_N1': os.path.join(OUT, 'v22_score_pred_M_N1.json'),
    'v22_N2': os.path.join(OUT, 'v22_score_pred_M_N2.json'),
    'v22_N1supp': os.path.join(OUT, 'v22_weak_holdout_prediction_N1supp.json'),
    'v22_weak': os.path.join(OUT, 'v22_weak_holdout.json'),
    'v3_v2': os.path.join(OUT, 'v3_prediction_v2.json'),
}
V2_CELL = {'g50p': 'g50p', 'g50p2': 'g50p', 'gi300': 'gi300'}
_JE = None
_V0 = None
_PACE = None


def judge_e():
    global _JE
    if _JE is None:
        _JE = pn5e.load_judge()
    return _JE


def v0_replay(tag):
    """v0 replay in its own process (v0_replay.py → frozen v0_driver_1003 with the _scratch v0 tree first on sys.path; its own assert)."""
    global _V0
    if _V0 is None:
        _V0 = {}
    if tag not in _V0:
        r = subprocess.run([sys.executable, '-X', 'utf8', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'v0_replay.py'), tag], capture_output=True, text=True, encoding='utf-8', cwd=C.ROOT)
        if r.returncode != 0:
            raise SystemExit(f'v0_replay {tag} failed: {r.stderr[-2000:]}')
        _V0[tag] = json.loads(r.stdout)
    return _V0[tag]


def pacing_module():
    global _PACE
    if _PACE is None:
        p = os.path.join(C.OD_SIM, 'predict_pacing_v1_1003.py')
        spec = importlib.util.spec_from_file_location('predict_pacing_v1_1003', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _PACE = (mod, C.sha256_file(p))
    return _PACE


def close(a, b, tol=C.REPRO_TOL):
    if a is None or b is None:
        return a is None and b is None
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return a == b


def series_bins(skin):
    n = len(skin) // C.BIN_S
    return [round(sum(skin[k * C.BIN_S:(k + 1) * C.BIN_S]) / C.BIN_S, 4) for k in range(n)]


def pack(skin, offsets_model, T_start, source, file=None, file_sha=None, column_key=None, items=None, repro=None, first_throttle_abs_s=None, ft_note=None, driving=None, extra=None):
    out = dict(source=source, file=(os.path.relpath(file, C.ROOT) if file else None), file_sha256=file_sha, column_key=column_key, T0=T_start,
               items=items or {}, repro=repro, driving=driving, n_rows=len(skin), seg_offsets_model=offsets_model,
               gen=dict(max_skin=C.r6(max(skin)), skin_1s=[round(x, 4) for x in skin], bin_mean_skin=series_bins(skin), n_bins=len(skin) // C.BIN_S),
               first_throttle_abs_s=first_throttle_abs_s, first_throttle_note=ft_note)
    if extra:
        out.update(extra)
    return out


# ============================================================ v0 (frozen driver · actual start · measured flags)
def gen_v0(tag):
    F = C.load_json(FROZEN['v0'])
    T = 'T1' if tag == 'c1a' else 'T2'
    f = F[T]
    g = v0_replay(tag)
    T0 = g['T0']
    skin = g['skin']
    repro = dict(skin_mae_c=dict(frozen=f['skin_mae_c'], here=g['skin_mae_c_1s'], equal=close(f['skin_mae_c'], g['skin_mae_c_1s'])),
                 model_skin_end=dict(frozen=f['model_skin_end'], here=g['model_skin_end'], equal=close(f['model_skin_end'], g['model_skin_end'])),
                 onset_model_s=dict(frozen=f['onset_model_s'], here=g['onset_model_s'], equal=close(f['onset_model_s'], g['onset_model_s'])),
                 T_start=dict(frozen=f['T_start'], here=T0, equal=close(f['T_start'], T0)),
                 v0_throttle_sha=dict(frozen=F['v0']['throttle_sha'], here=g['v0_throttle_sha'], equal=(F['v0']['throttle_sha'] == g['v0_throttle_sha'])))
    repro['all'] = all(v['equal'] for v in repro.values() if isinstance(v, dict))
    items = dict(onset_model_s=f['onset_model_s'], onset_meas_s_in_file=f['onset_meas_s'], skin_mae_c_1s=f['skin_mae_c'], model_skin_end=f['model_skin_end'], verdict_in_file=f['verdict'])
    return {col_key_actual(T0): pack(skin, [0], T0, 'frozen+generated_series', FROZEN['v0'], C.sha256_file(FROZEN['v0']), T, items, repro,
                                     first_throttle_abs_s=f['onset_model_s'], ft_note='동결 onset_model_s (v0 onset_time_ref: +10 % · 30 s 유지 · t ≥ 30) · 구간 0 = 절대 시각',
                                     driving='v0_driver_1003.sim_flags(P_V0, T0 = 실제 시작 SKIN, 실측 가동 플래그)' + (' · d100 전부 on' if tag == 'c1a' else ' · trace n_inf > 0') + f" (독립 프로세스 v0_replay.py · env {os.path.basename(os.path.dirname(g['env_file']))})",
                                     extra=dict(skin_1s_rows=g['rows_1s'], v0_env_file=g['env_file']))}


def col_key_actual(T0):
    return f'actual:{T0}'


# ============================================================ v1 (frozen night-1003 driver · columns 29.5 / 30.5)
def gen_v1(tag):
    p = pn3.params()
    out = {}
    if tag == 'm1g_r2':
        F = C.load_json(FROZEN['v1_m1gpu'])
        fp = FROZEN['v1_m1gpu']
        for T0 in C.COLUMNS:
            sch = [(0, 'GPU', pn3.duty_flags(10, 60), 60), (1, 'GPU', True, 1200), (2, 'GPU', pn3.duty_flags(10, 300), 300)]
            rows = tv1.simulate(p, sch, T0, C.A0)
            f = F['m1_gpu'][str(T0)]
            hb = tv1.bins_ratio(rows, 1)
            here = dict(heat_end_skin=pn3.at(rows, 1, 1199)['skin'], heat_onset_s=tv1.onset_time_ref(hb, 1.0), ratio_540_600=pn3.med(rows, 1, 540, 600),
                        ratio_1000_1200=pn3.med(rows, 1, 1000, 1200), heat_end_ap=pn3.at(rows, 1, 1199)['ap'])
            repro = {k: dict(frozen=f[k], here=here[k], equal=close(f[k], here[k])) for k in here}
            repro['all'] = all(v['equal'] for v in repro.values() if isinstance(v, dict))
            skin = [r['skin'] for r in rows]
            out[C.col_key(T0)] = pack(skin, [0, 60, 1260], T0, 'frozen+generated_series', fp, C.sha256_file(fp), str(T0),
                                      dict(heat_onset_s=f['heat_onset_s'], heat_end_skin=f['heat_end_skin'], recovery=f['recovery'], ratio_540_600=f['ratio_540_600']), repro,
                                      first_throttle_abs_s=None if f['heat_onset_s'] is None else 60 + f['heat_onset_s'],
                                      ft_note='동결 heat_onset_s (tv1.onset_time_ref 구간 1 · ref 1.0 · +10 % 30 s 유지) + 구간 1 오프셋 60 s',
                                      driving='predict_night_1003.m1_gpu 구동 (duty_flags 앞 duty % · A0 −1.0 · tv1.simulate)')
    else:
        mod, msha = pacing_module()
        F = C.load_json(FROZEN['v1_pacing'])
        fp = FROZEN['v1_pacing']
        for T0 in C.COLUMNS:
            sch = [(0, 'GPU', mod.duty_flags(10, 60), 60), (1, 'GPU', True, 600), (2, 'GPU', mod.duty_flags(10, 60), 60), (3, 'GPU', True, 300)]
            rows = tv1.simulate(mod.params(), sch, T0, -1.0)
            f = F['pacing'][str(T0)]
            ref_d100 = mod.med(rows, 1, 0, 30)
            here = dict(heat_end_skin=mod.at(rows, 1, 599)['skin'], rest_end_skin=mod.at(rows, 2, 59)['skin'], reheat_end_skin=mod.at(rows, 3, 299)['skin'],
                        heat_onset_s=tv1.onset_time_ref(tv1.bins_ratio(rows, 1), ref_d100), reheat_ratio_240_300=mod.med(rows, 3, 240, 300) / ref_d100)
            repro = {k: dict(frozen=f[k], here=here[k], equal=close(f[k], here[k])) for k in here}
            repro['all'] = all(v['equal'] for v in repro.values() if isinstance(v, dict))
            skin = [r['skin'] for r in rows]
            out[C.col_key(T0)] = pack(skin, [0, 60, 660, 720], T0, 'frozen+generated_series', fp, C.sha256_file(fp), str(T0),
                                      dict(heat_onset_s=f['heat_onset_s'], heat_end_skin=f['heat_end_skin'], rest_end_skin=f['rest_end_skin'], reheat_end_skin=f['reheat_end_skin'],
                                           retighten=f['retighten'], classification=f['classification']), repro,
                                      first_throttle_abs_s=None if f['heat_onset_s'] is None else 60 + f['heat_onset_s'],
                                      ft_note='동결 heat_onset_s (tv1.onset_time_ref 구간 1 · ref_d100) + 60 s',
                                      driving=f'sim/predict_pacing_v1_1003.pacing 구동 (sha {msha[:8]}) · tv1.simulate')
    return out


# ============================================================ v2 (frozen night-1004 driver · columns 29.5 / 30.5)
def gen_v2(tag):
    F = C.load_json(FROZEN['v2'])
    fp = FROZEN['v2']
    cell = V2_CELL[tag]
    p = pn4.v2_params()
    variants = pn4.npu_variants(p)
    out = {}
    for T0 in C.COLUMNS:
        rows_by = {name: tv2.simulate(pp, pn4.schedule(cell), T0, -1.0) for name, pp in variants.items()}
        names = sorted(rows_by)
        rows = rows_by[names[0]]
        same_variants = all([r['skin'] for r in rows_by[n]] == [r['skin'] for r in rows] for n in names[1:])
        f = F['cells'][cell][f'{T0}/{names[0]}']
        f_other = {n: F['cells'][cell][f'{T0}/{n}'] for n in names[1:]}
        hb = tv2.bins_ratio(rows, 1)
        ref30 = pn4.med(rows, 1, 0, 30)
        heat_len = pn4.CHAINS[cell][1][2]
        here = dict(heat_end_skin=pn4.at(rows, 1, heat_len - 1)['skin'], heat_onset_1_1_s=tv2.onset_time_ref(hb, ref30), heat_end_ap=pn4.at(rows, 1, heat_len - 1)['ap'])
        if cell == 'g50p':
            here['probe_temps_last_skin'] = pn4.at(rows, 2, 479)['skin']
            fz = dict(heat_end_skin=f['heat_end_skin'], heat_onset_1_1_s=f['heat_onset_1_1_s'], heat_end_ap=f['heat_end_ap'], probe_temps_last_skin=f['probe_temps'][-1]['skin'])
        else:
            here['rest_temps_last_skin'] = pn4.at(rows, 2, 299)['skin']
            here['reheat_end_skin'] = pn4.at(rows, 3, 299)['skin']
            fz = dict(heat_end_skin=f['heat_end_skin'], heat_onset_1_1_s=f['heat_onset_1_1_s'], heat_end_ap=f['heat_end_ap'], rest_temps_last_skin=f['rest_temps'][-1]['skin'], reheat_end_skin=f['reheat_end_skin_ap']['skin'])
        repro = {k: dict(frozen=fz[k], here=here[k], equal=close(fz[k], here[k])) for k in here}
        repro['theta_variants_identical_gpu'] = dict(equal=same_variants and all(close(f['heat_end_skin'], fo['heat_end_skin']) for fo in f_other.values()))
        repro['all'] = all(v['equal'] for v in repro.values() if isinstance(v, dict))
        skin = [r['skin'] for r in rows]
        items = dict(heat_onset_1_1_s=f['heat_onset_1_1_s'], heat_end_skin=f['heat_end_skin'])
        items.update({k: f[k] for k in ('probe_class', 'probe_release_s', 'retighten_s', 'retighten_class') if k in f})
        offs = [0, 60, 360] if cell == 'g50p' else [0, 60, 660, 960]
        out[C.col_key(T0)] = pack(skin, offs, T0, 'frozen+generated_series', fp, C.sha256_file(fp), f'{T0}/{names[0]}', items, repro,
                                  first_throttle_abs_s=None if f['heat_onset_1_1_s'] is None else 60 + f['heat_onset_1_1_s'],
                                  ft_note='동결 heat_onset_1_1_s (tv2.onset_time_ref 구간 1 · ref30) + 60 s',
                                  driving=f'predict_night_1004.schedule({cell!r}) · v2_params · θ 변형 {names[0]} (GPU 칸은 θ_NPU 무관 — 변형 간 동일 검사) · tv2.simulate A0 −1.0')
    return out


# ============================================================ v2.1 (frozen night-1005 / 1005e driver · columns 29.5 / 30.5)
def _cells_R0(group):
    if group == 'N2':
        return pn5e.CELLS_E, pn5e.R0_EFFNET
    return pn5e.CELLS_M, pn5e.r0_mobilenet()


def _metrics_v21_like(sim, p, kw, cells, cell, R0, T0):
    JE, _ = judge_e()
    rows = sim(p, pn5e.schedule(cells, cell), T0, pn5e.A0, **kw)
    m = pn5e.run_metrics(JE.N5, cells, rows, cell, R0[cells[cell][0]]['R0'])
    return rows, m


def gen_v21(tag):
    r = C.RUNS[tag]
    cells, R0 = _cells_R0(C.NIGHT_OF[r['group']])
    fp = FROZEN['v21_N2'] if r['group'] == 'N2' else FROZEN['v21_N1']
    F = C.load_json(fp)
    p = pn5e.v21_params()
    d_ref = p['thermal']['d_ref']
    out = {}
    for T0 in C.COLUMNS:
        rows, m = _metrics_v21_like(tv21.simulate, p, dict(B0=T0 - d_ref), cells, r['cell'], R0, T0)
        f = F['cells'][r['cell']][C.col_key(T0)]
        keys = ('max_skin', 'skin_899', 'first_throttle_s', 'throttle_time_s', 't38_s', 'n')
        repro = {k: dict(frozen=f[k], here=m[k], equal=close(f[k], m[k])) for k in keys}
        repro['all'] = all(v['equal'] for v in repro.values() if isinstance(v, dict))
        skin = [x['skin'] for x in rows]
        out[C.col_key(T0)] = pack(skin, [0, cells[r['cell']][2][0][2]], T0, 'frozen+generated_series', fp, C.sha256_file(fp), C.col_key(T0),
                                  {k: f[k] for k in keys}, repro, first_throttle_abs_s=f['first_throttle_s'],
                                  ft_note='동결 first_throttle_s (night1005_judge.first_throttle · 구간 0 · HOLD 3 · 자원 문턱) · 구간 0 = 절대 시각',
                                  driving='predict_night_1005(e) 구동 (duty_flags · A0 −1.0 · BAT0 = T0 − d_ref · tv21.simulate · run_metrics = 판정기 문턱 함수)')
    return out


# ============================================================ v2.2 frozen (N1 · N2 · N1 보충) at the run's own start column
def gen_v22_frozen(tag, start_skin):
    r = C.RUNS[tag]
    night = C.NIGHT_OF[r['group']]
    cells, R0 = _cells_R0(night)
    fp = {'frozen_N1': FROZEN['v22_N1'], 'frozen_N2': FROZEN['v22_N2'], 'frozen_N1supp': FROZEN['v22_N1supp']}[r['v22']]
    F = C.load_json(fp)
    p = tv22.load_params('throttle_v22_', 'CM')
    d_ref = p['thermal']['d_ref']
    model = 'effnet' if night == 'N2' else 'mobilenet'
    T0 = float(start_skin)
    ck = C.col_key(T0)
    if ck not in F['cells'][r['cell']]:
        raise SystemExit(f'{tag}: column {ck} not in {os.path.basename(fp)} {sorted(F["cells"][r["cell"]])}')
    sim = lambda pp, sch, T, A, B0=None: tv22.simulate(pp, sch, T, A, B0, model=model)  # noqa: E731
    rows, m = _metrics_v21_like(sim, p, dict(B0=T0 - d_ref), cells, r['cell'], R0, T0)
    f = F['cells'][r['cell']][ck]
    keys = ('max_skin', 'skin_899', 'first_throttle_s', 'throttle_time_s', 't38_s', 'n')
    repro = {k: dict(frozen=f[k], here=m[k], equal=close(f[k], m[k])) for k in keys}
    repro['all'] = all(v['equal'] for v in repro.values() if isinstance(v, dict))
    skin = [x['skin'] for x in rows]
    return {ck: pack(skin, [0, cells[r['cell']][2][0][2]], T0, 'frozen+generated_series', fp, C.sha256_file(fp), ck, {k: f[k] for k in keys}, repro,
                     first_throttle_abs_s=f['first_throttle_s'], ft_note='동결 first_throttle_s (구간 0 · HOLD 3 · 자원 문턱)',
                     driving=f'fit_throttle_v22.predict_night 구동 (predict_night_1005e 드라이버 · 실제 시작 SKIN 열 {ck} · BAT0 = T0 − d_ref · model={model})')}


# ============================================================ v2.2 generated (V3 v2 · P1j path · two-point columns) — also the 2-pt description rows
def params_v22(engine):
    return tv22.load_params('throttle_v22_', engine)


def simulate_2pt(segs, T0, model, engine):
    p = params_v22(engine)
    sched = list(PV.schedule({'segments': segs})) + [(len(segs), None, None, 1)]
    rows = tv22.simulate(p, sched, T0, C.A0, B0=T0 - p['thermal']['d_ref'], model=model)
    return rows[:-1], rows[-1]


def metrics_2pt(segs, rows, end_row, resource):
    """predict_v3.run_metrics arithmetic + P1j ratio bins / first throttle (HOLD 3, resource threshold) mapped to chain-absolute time."""
    m = PV.run_metrics({'segments': segs}, rows, end_row)
    thr = C.THR[resource]
    ex = [r for r in rows if r['ex'] and r['ratio'] is not None]
    active = [i for i, s in enumerate(segs) if s['duty'] >= 10]
    first = active[0]
    ref = statistics.median([r['ratio'] for r in ex if r['seg'] == first and r['t'] < 30])
    offs, acc = [], 0
    for s in segs:
        offs.append(acc)
        acc += s['duration_s']
    bins, abs_t = [], []
    for i in active:
        L = segs[i]['duration_s']
        for k in range(int(math.floor(L / 10 + 1e-9))):
            v = [r['ratio'] for r in ex if r['seg'] == i and 10 * k <= r['t'] < 10 * (k + 1)]
            bins.append((statistics.median(v) / ref) if v else None)
            abs_t.append(offs[i] + 10 * k)
    k1 = C.first_throttle(bins, thr)
    thr_time = 10 * sum(1 for b in bins if b is not None and b >= thr - C.EPS)
    return dict(max_skin=C.r6(m['max_skin']), end_skin_after=C.r6(m['end_skin']), t38_s=m['t38_s'], t40_s=m['t40_s'], t42_s=m['t42_s'],
                first_throttle_bin=k1, first_throttle_abs_s=None if k1 is None else abs_t[k1], throttle_time_s=thr_time, ref30_ratio=C.r6(ref),
                ratio_bins=[C.r6(x) for x in bins], n_active_bins=len(bins), threshold=thr), offs


def gen_v22_2pt(tag):
    r = C.RUNS[tag]
    segs = C.chain_segments(tag)
    out = {}
    for T0 in C.COLUMNS:
        rows, end = simulate_2pt(segs, T0, r['model'], r['engine'])
        it, offs = metrics_2pt(segs, rows, end, r['resource'])
        skin = [x['skin'] for x in rows]
        if len(skin) != sum(s['duration_s'] for s in segs):
            raise SystemExit(f'{tag}: rows {len(skin)} ≠ Σ')
        out[C.col_key(T0)] = pack(skin, offs, T0, 'generated', None, None, C.col_key(T0), it, dict(all=True, note='동결 파일 없음 — 재현 검사 대상 없음 (frozen_check 는 전체 기록)'),
                                  first_throttle_abs_s=it['first_throttle_abs_s'],
                                  ft_note=f"생성 (predict_v3.run_metrics 칸 · 가동 구간 · 기준 = 첫 가동 구간 처음 30 s · HOLD 3 · ×{C.THR[r['resource']]}) → 절대 시각",
                                  driving=f"V3 v2 · P1j 경로: predict_v3.flags (Bresenham) · A0 −1.0 · BAT0 = T0 − d_ref · tv22.simulate(model={r['model']}, engine={r['engine']})")
    return out


def frozen_check():
    v2 = C.load_json(FROZEN['v3_v2'])
    prof = os.path.join(C.ROOT, 'd1sim', 'profiles')
    mf = {k: C.sha256_file(os.path.join(C.ROOT, 'd1sim', k)) for k in ('throttle_v22.py', 'throttle_v21.py', 'throttle_v2.py', 'env_v2.py')}
    pf = {fn: C.sha256_file(os.path.join(prof, fn)) for fn in sorted(os.listdir(prof)) if fn.startswith(('throttle_v22_', 'throttle_v21_', 'throttle_v2_')) and fn.endswith('.json')}
    v1f = {fn: C.sha256_file(os.path.join(prof, fn)) for fn in sorted(os.listdir(prof)) if fn.startswith('throttle_v1_') and fn.endswith('.json')}
    return dict(model_files_equal=(mf == v2['model_files']), profiles_equal=(pf == v2['profiles']), predict_v3_py_equal=(C.sha256_file(PV.__file__) == v2['code']['predict_v3_py']),
                model_files=mf, profiles=pf, v1_profiles=v1f, throttle_v1_py=C.sha256_file(tv1.__file__),
                drivers={k: C.sha256_file(m.__file__) for k, m in (('predict_night_1003', pn3), ('predict_night_1004', pn4), ('predict_night_1005e', pn5e), ('predict_v3', PV))},
                pacing_driver=pacing_module()[1], judge_e=judge_e()[1], judge_n5=C.sha256_file(judge_e()[0]._N5_PATH),
                frozen_files={k: C.sha256_file(p) for k, p in FROZEN.items()})


# ============================================================ pairs · resources (frozen pair items at the pair column)
def pair_predictions(cells):
    out = {}
    for key, p in C.PAIRS.items():
        mean = cells['pairs'][key]['start_skin_mean']
        out[key] = {}
        for pan in p['pans']:
            if pan == 'v21':
                fp = FROZEN['v21_N2'] if p['group'] == 'N2' else FROZEN['v21_N1']
                F = C.load_json(fp)
                col = C.pick_column(mean, [float(k) for k in F['pairs'][p['resource']]])
                ck = C.col_key(col)
                pp = F['pairs'][p['resource']][ck]
                ca, cb = F['cells'][C.RUNS[p['a']]['cell']][ck], F['cells'][C.RUNS[p['b']]['cell']][ck]
            else:
                src = C.RUNS[p['b']]['v22']
                fp = {'frozen_N1': FROZEN['v22_N1'], 'frozen_N2': FROZEN['v22_N2'], 'frozen_N1supp': FROZEN['v22_N1supp']}[src]
                F = C.load_json(fp)
                ck = C.col_key(mean)
                if ck not in F['pairs'][p['resource']]:
                    raise SystemExit(f'pair {key}: column {ck} not in {os.path.basename(fp)}')
                pp = F['pairs'][p['resource']][ck]
                ca, cb = F['cells'][C.RUNS[p['a']]['cell']][ck], F['cells'][C.RUNS[p['b']]['cell']][ck]
            d_from_cells = C.r6(ca['max_skin'] - cb['max_skin'])
            fa, fb = ca['first_throttle_s'], cb['first_throttle_s']
            out[key][pan] = dict(source='frozen', file=os.path.relpath(fp, C.ROOT), file_sha256=C.sha256_file(fp), column_key=ck,
                                 d_max_skin=pp['d_max_skin'], d_max_skin_from_cells=d_from_cells, d_max_skin_consistent=close(pp['d_max_skin'], d_from_cells, 1e-5),
                                 d_t38_s=pp['d_t38_s'], d_t40_s=pp['d_t40_s'], d_throttle_time_s=pp['d_throttle_time_s'], work_ratio=pp['work_ratio'], same_work=pp['same_work'], signs=pp['signs'],
                                 first_throttle_a=fa, first_throttle_b=fb, d_first_throttle_s=None if (fa is None or fb is None) else fa - fb, pair_item=pp)
        # 2-pt description for v22 (generated at the pair's two-point column from the runs' 2-pt series)
    return out


def resource_predictions(pairs_pred, cells):
    JE, _ = judge_e()
    N5 = JE.N5
    out = {}
    for key, r in C.RESOURCES.items():
        out[key] = {}
        for pan in r['pans']:
            lst = []
            for pk in r['pairs']:
                pp = pairs_pred[pk][pan]
                lst.append(dict(N5._pred_pair_as_judged(pp['pair_item']), block=C.PAIRS[pk]['block'], column=pp['column_key']))
            lst = sorted(lst, key=lambda x: x['block'])
            pv = N5.resource_verdict(lst)
            out[key][pan] = dict(predicted_verdict=pv, columns=[x['column'] for x in lst], pairs=r['pairs'], signs=[x['signs'] for x in lst], same_work=[x['same_work'] for x in lst],
                                 rule='night1005_judge.resource_verdict(블록별 열의 예측 쌍 → _pred_pair_as_judged) — cmp_one 과 같은 순서')
    return out


def predict_all(cells):
    runs = {}
    for tag, r in C.RUNS.items():
        rec = {}
        sk = cells['runs'][tag]['start_skin']
        if r['holdout'] == 'v0':
            rec['v0'] = gen_v0(tag)
        elif r['holdout'] == 'v1':
            rec['v1'] = gen_v1(tag)
        elif r['holdout'] == 'v2':
            rec['v2'] = gen_v2(tag)
        elif r['holdout'] == 'v21':
            rec['v21'] = gen_v21(tag)
        if r['v22'] == 'generated':
            rec['v22'] = gen_v22_2pt(tag)
        else:
            rec['v22'] = gen_v22_frozen(tag, sk)
            rec['v22_2pt'] = gen_v22_2pt(tag)
        runs[tag] = rec
    pairs = pair_predictions(cells)
    resources = resource_predictions(pairs, cells)
    return runs, pairs, resources


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    fc = frozen_check()
    if not (fc['model_files_equal'] and fc['profiles_equal'] and fc['predict_v3_py_equal']):
        print('frozen model / prediction path differs from the V3 v2 record — stop', {k: fc[k] for k in ('model_files_equal', 'profiles_equal', 'predict_v3_py_equal')})
        return 8
    cells = C.load_json(C.CELLS_JSON)
    runs, pairs, resources = predict_all(cells)
    bad = [(t, pan, ck) for t, rec in runs.items() for pan, cols in rec.items() for ck, v in cols.items() if not v['repro']['all']]
    res = dict(kind='gpuerr_predictions_v1', registration=f'{C.REG} ({C.REG_COMMIT[:7]}) §1', cells_sha256=C.sha256_file(C.CELLS_JSON), columns_2pt=list(C.COLUMNS), A0=C.A0,
               thr=C.THR, hold=C.HOLD, pan_labels=C.PAN_LABEL, frozen_check=fc, repro_failures=bad, runs=runs, pairs=pairs, resources=resources,
               v22_weak_holdout_gie_spare=C.load_json(FROZEN['v22_weak']).get('gie_b1_spare'),
               shas=dict(this=C.sha256_file(os.path.abspath(__file__)), common_py=C.sha256_file(C.__file__)),
               note='예측값 · 출처만 (실측 열 값 0 — 입력 = 체인 명령 · 동결 파일 · 시작 열). 오차 계산은 judge_gpuerr (커밋 ② 뒤).')
    s = C.write_json(C.PRED_JSON, res)
    for t, rec in runs.items():
        for pan, cols in rec.items():
            for ck, v in cols.items():
                print(f"{t:15s} {pan:8s} col {ck:14s} {v['source']:24s} max {v['gen']['max_skin']:.3f} · 1st thr {v['first_throttle_abs_s']} · rows {v['n_rows']} · repro {'OK' if v['repro']['all'] else 'FAIL'}")
    for k, pp in pairs.items():
        print(f"pair {k}: " + ' · '.join(f"{pan} col {v['column_key']} Δmax {v['d_max_skin']:+.3f} Δthr {v['d_first_throttle_s']}" for pan, v in pp.items()))
    for k, rr in resources.items():
        print(f"resource {k}: " + ' · '.join(f"{pan} {v['predicted_verdict']} {v['columns']}" for pan, v in rr.items()))
    print('repro failures', bad)
    print('->', C.PRED_JSON, s)
    return 0


# ============================================================ selftest (합성 · 양방향 · 결과 전 — 실제 런 예측은 main 에서만)
def selftest():
    res = []

    def check(name, cond, got=''):
        res.append((name, bool(cond), got))
    fc = frozen_check()
    check('① frozen: 모형 파일 · 프로파일 · predict_v3.py = V3 v2 기록', fc['model_files_equal'] and fc['profiles_equal'] and fc['predict_v3_py_equal'])
    check('① 판정기 SHA: night1005e 2db1cda5 · night1005 ca8680c2 · 페이싱 구동 파일 있음', fc['judge_e'].startswith('2db1cda5') and fc['judge_n5'].startswith('ca8680c2') and len(fc['pacing_driver']) == 64)
    syn = [dict(accelerator='GPU', duty=10, duration_s=20), dict(accelerator='GPU', duty=100, duration_s=60), dict(accelerator='GPU', duty=1, duration_s=30)]
    rows, end = simulate_2pt(syn, 29.5, 'mobilenet', 'CM')
    rows2, end2 = simulate_2pt(syn, 29.5, 'mobilenet', 'CM')
    check('② 결정성: 합성 체인 두 번 → 같은 행', rows == rows2 and end == end2, len(rows))
    it, offs = metrics_2pt(syn, rows, end, 'GPU')
    check('② metrics_2pt: 행 110 · 오프셋 [0, 20, 80] · 가동 칸 2 + 6 = 8 · 문턱 1.10 · max = max(rows)', len(rows) == 110 and offs == [0, 20, 80] and it['n_active_bins'] == 8 and it['threshold'] == 1.10
          and abs(it['max_skin'] - max(r['skin'] for r in rows)) < 1e-6, (offs, it['n_active_bins']))
    # the generated v2.2 path equals predict_v3.simulate for an EffNet / CM chain (same driving) — same rows
    rows_pv, end_pv = PV.simulate('v22', PV.schedule({'segments': syn}), 29.5)
    rows_e, end_e = simulate_2pt(syn, 29.5, 'effnet', 'CM')
    check('② effnet · CM 합성 체인: simulate_2pt == predict_v3.simulate(v22) (같은 구동)', [r['skin'] for r in rows_e] == [r['skin'] for r in rows_pv] and end_e == end_pv)
    rows_m, _ = simulate_2pt(syn, 29.5, 'mobilenet', 'CM')
    rows_i, _ = simulate_2pt(syn, 29.5, 'mobilenet', 'INT')
    check('② model=mobilenet ≠ effnet (g_m) · engine INT ≠ CM (GPU 프로파일 다름) — 합성 체인에서 행이 다르다', [r['skin'] for r in rows_m] != [r['skin'] for r in rows_e] and [r['skin'] for r in rows_i] != [r['skin'] for r in rows_m])
    # absolute-time mapping of the first throttle bin: synthetic ratio list over two active segments
    thr = C.THR['GPU']
    check('③ first_throttle HOLD 3 · ×1.10 경계 포함: [1,1,1.10,1.10,1.10,1.10] → 2 · [1.09]*5 → None · None 칸 실패', C.first_throttle([1, 1, 1.10, 1.10, 1.10, 1.10], thr) == 2
          and C.first_throttle([1.09] * 5, thr) is None and C.first_throttle([1.1, None, 1.1, 1.1, 1.1], thr) is None)
    check('③ bins: 25 행 → 2 칸 · 칸 0 = mean(rows 0..9)', len(series_bins(list(range(25)))) == 2 and series_bins(list(range(25)))[0] == 4.5)
    check('④ pick_column / col_key: 29.45 → "29.45" · 30.0 → "30.0" · 29.4 → 29.5 (두 점)', C.col_key(29.45) == '29.45' and C.col_key(30.0) == '30.0' and C.pick_column(29.4) == 29.5)
    # v0 driver import works and the frozen copy SHA matches the holdout record
    g = v0_replay('m3')
    F0 = C.load_json(FROZEN['v0'])
    check('⑤ v0 독립 프로세스 재생 (m3): 동결 사본 throttle.py SHA = v0_holdout 기록 · env 는 _scratch 트리 · 601 행 · skin_mae 1 s = 동결 0.396 (재현)',
          g['v0_throttle_sha'] == F0['v0']['throttle_sha'] and '_scratch' in g['env_file'] and g['n_rows'] == 601 and close(g['skin_mae_c_1s'], F0['T2']['skin_mae_c']), (g['skin_mae_c_1s'], F0['T2']['skin_mae_c']))
    # frozen v2.1 N1 reproduction through this module's driver on the NA cell (NPU) — the prediction-path check predict_v3.checks() already covers v21 NAe; here N1 NA 29.5
    cells, R0 = _cells_R0('N1')
    p = pn5e.v21_params()
    rows_na, m_na = _metrics_v21_like(tv21.simulate, p, dict(B0=29.5 - p['thermal']['d_ref']), cells, 'NA', R0, 29.5)
    f_na = C.load_json(FROZEN['v21_N1'])['cells']['NA']['29.5']
    check('⑥ v2.1 구동 재현 (NA 29.5 · NPU, GPU 런 아님): max_skin · skin_899 · first_throttle = 동결 night_1005_prediction_v21', close(f_na['max_skin'], m_na['max_skin']) and close(f_na['skin_899'], m_na['skin_899']) and f_na['first_throttle_s'] == m_na['first_throttle_s'], (f_na['max_skin'], m_na['max_skin']))
    # pair/resource arithmetic on a synthetic frozen pair: resource_verdict reproduces '차이 없음' for all-zero signs and 'B 낮음' for all-minus
    JE, _ = judge_e()
    N5 = JE.N5
    zero = dict(d_max_skin=0.0, d_t38_s=0, d_t40_s=0, d_throttle_time_s=0, work_ratio=1.0)
    plus = dict(d_max_skin=2.0, d_t38_s=100, d_t40_s=0, d_throttle_time_s=100, work_ratio=1.0)
    minus = dict(d_max_skin=-2.0, d_t38_s=-100, d_t40_s=0, d_throttle_time_s=-100, work_ratio=1.0)
    v0_ = N5.resource_verdict([N5._pred_pair_as_judged(zero), N5._pred_pair_as_judged(zero)])
    v1_ = N5.resource_verdict([N5._pred_pair_as_judged(plus), N5._pred_pair_as_judged(plus)])
    v2_ = N5.resource_verdict([N5._pred_pair_as_judged(minus), N5._pred_pair_as_judged(minus)])
    v3_ = N5.resource_verdict([N5._pred_pair_as_judged(plus), N5._pred_pair_as_judged(minus)])
    check('⑦ resource_verdict (판정기 함수 그대로): 전부 0 → "차이 없음 (2쌍)" · 전부 + (A − B > 0) → "B 낮음 (2쌍)" · 전부 − → "B 높음 (2쌍)" · 블록 엇갈림 → "엇갈림"',
          v0_ == '차이 없음 (2쌍)' and v1_ == 'B 낮음 (2쌍)' and v2_ == 'B 높음 (2쌍)' and v3_ == '엇갈림', (v0_, v1_, v2_, v3_))
    return C.print_table(res)


if __name__ == '__main__':
    sys.exit(main())
