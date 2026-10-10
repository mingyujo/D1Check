"""predict_energyc.py — frozen-model predictions for the energy-C chains (prereg d1sim/docs/모형오차_사전등록_v1.md §1 · §3, 9e29851).

Prediction path = the V3 v2 one, imported unmodified from d1sim/v3/predict_v3.py (schedule · simulate · run_metrics · models ·
columns · R0 · THR). Models: v2.2 V22-M e52a922 (main) · v2.1 c6a7da2 · v2 V2-Lb θ_NPU 0.3 / 0.75 42338e7 — code and parameters
as committed (SHA-256 of every model file / profile is written into the output and must equal the V3 v2 prediction's record).
Chains: NAc = tools/chains/npu_eff_work100_v1.json (d100 300 s + d1 600 s) · NBc = npu_eff_work50eq_v1.json (d50 620 s + d1 280 s).

Start-state rule = V3 v2 rule (등록 §1): columns SKIN 29.5 · 30.5 · A0 = -1.0 · BAT0 = SKIN0 - d_ref (v2.1 · v2.2; v2 has no body state).
The comparison column per cell / block is chosen later (judge) by the measured start SKIN (nearest · tie 29.5 · no interpolation).
Described-only extra (declared before any run, not used in the §4 verdict): the same replay with T0 = each cell's actual
load-start SKIN ('actual' rows), which needs the 16 measured start SKINs (inputs, public in the cell tables) — read from the
energy-C judge JSONs' start.start_skin only.

Per (chain · model · column) the output has: 1 s SKIN rows (900), 10 s bin means (90, [0, 900) s), max SKIN, SKIN at t = 899 s,
window-end SKIN, t38/t40/t42, 10 s executing-ratio bins over the active segment (ref = median executing-second ratio in the first
30 s of the first active segment — predict_v3.run_metrics), first throttle bin (k with k..k+3 all >= 1.06 — night1005 HOLD 3 rule),
throttle time (predict_v3 definition), n_model, n_with_d1_est.

  py -X utf8 -m d1sim.model_error_v1.predict_energyc [--selftest] [--out-od DIR] [--out-repo DIR]
"""
from __future__ import annotations

import argparse
import math
import os
import statistics
import sys

from d1sim.model_error_v1 import common as C
from d1sim.v3 import predict_v3 as PV

C.stdout_utf8()
sys.path.insert(0, os.path.join(C.ROOT, 'tools'))
import npu_chain  # noqa: E402  (tools/npu_chain.py — canonical SHA, read only)

V3_PRED_V2 = os.path.join(C.ROOT, 'd1sim', 'out', 'v3_prediction_v2.json')


def load_chain(cell):
    info = npu_chain.load_chain(os.path.join(C.CHAIN_DIR, C.CELLS[cell]['chain'] + '.json'))
    if info['sha256'] != C.CELLS[cell]['canonical']:
        raise SystemExit(f'chain canonical SHA differs for {cell}: {info["sha256"]} ≠ {C.CELLS[cell]["canonical"]}')
    return info['spec'], info


def bin_means(skin_1s, n_bins=C.N_BINS, bin_s=C.BIN_S):
    out = []
    for k in range(n_bins):
        seg = skin_1s[k * bin_s:(k + 1) * bin_s]
        out.append(round(sum(seg) / len(seg), 4) if seg else None)
    return out


def ratio_bins(chain, rows):
    """10 s executing-ratio bins over active segments (duty >= 10), ratio = median(1/s)/ref — predict_v3.run_metrics arithmetic."""
    segs = chain['segments']
    ex = [r for r in rows if r['ex'] and r['ratio'] is not None]
    active = [i for i, s in enumerate(segs) if s['duty'] >= 10]
    first = active[0]
    ref = statistics.median([r['ratio'] for r in ex if r['seg'] == first and r['t'] < 30])
    bins = []
    for i in active:
        L = segs[i]['duration_s']
        for k in range(int(math.floor(L / 10 + 1e-9))):
            v = [r['ratio'] for r in ex if r['seg'] == i and 10 * k <= r['t'] < 10 * (k + 1)]
            bins.append((statistics.median(v) / ref) if v else None)
    return bins, ref


def cell_metrics(chain, rows, end_row):
    m = PV.run_metrics(chain, rows, end_row)                 # max_skin · end_skin · t38/40/42 · n · throttle_time (unchanged arithmetic)
    skin = [r['skin'] for r in rows]
    sigma = sum(s['duration_s'] for s in chain['segments'])
    if len(skin) != sigma:
        raise SystemExit(f'replay rows {len(skin)} ≠ Σ {sigma}')
    rb, ref = ratio_bins(chain, rows)
    k1 = C.first_throttle(rb)
    out = dict(max_skin=C.r6(m['max_skin']), skin_899=C.r6(skin[C.T_899]) if len(skin) > C.T_899 else None, end_skin=C.r6(m['end_skin']),
               t38_s=m['t38_s'], t40_s=m['t40_s'], t42_s=m['t42_s'], status_ge1_s=m['status_ge1_s'],
               n_model=C.r6(m['n_model']), n_with_d1_est=C.r6(m['n_with_d1_est']),
               throttle_time_s=m['throttle_time_s'], first_throttle_bin=k1, first_throttle_s=None if k1 is None else k1 * C.BIN_S,
               ref30_ratio=C.r6(ref), ratio_bins=[C.r6(x) for x in rb], n_active_bins=len(rb),
               bin_mean_skin=bin_means(skin, n_bins=sigma // C.BIN_S), skin_1s=[round(x, 4) for x in skin], max_ap=C.r6(m['max_ap']))
    return out


def predict_all(start_skins=None):
    """start_skins: {cell_key: start SKIN} for the described-only 'actual' rows (None -> skipped)."""
    chains, info = {}, {}
    for cell in C.CELLS:
        chains[cell], info[cell] = load_chain(cell)
    runs = {}
    for cell, ch in chains.items():
        sch = PV.schedule(ch)
        for m in C.MODELS:
            for T0 in C.COLUMNS:
                rows, end = PV.simulate(m, sch, T0)
                runs.setdefault(cell, {}).setdefault(m, {})[str(T0)] = cell_metrics(ch, rows, end)
    actual = {}
    if start_skins:
        for key, T0 in sorted(start_skins.items()):
            cell = key.split('_b')[0]
            sch = PV.schedule(chains[cell])
            for m in C.MODELS:
                rows, end = PV.simulate(m, sch, float(T0))
                mt = cell_metrics(chains[cell], rows, end)
                mt.pop('skin_1s')
                actual.setdefault(key, dict(cell=cell, T0=float(T0)))[m] = mt
    return runs, actual, info


def model_shas():
    prof = os.path.join(C.ROOT, 'd1sim', 'profiles')
    return dict(model_files={k: C.sha256_file(os.path.join(C.ROOT, 'd1sim', k)) for k in ('throttle_v22.py', 'throttle_v21.py', 'throttle_v2.py', 'env_v2.py')},
                profiles={fn: C.sha256_file(os.path.join(prof, fn)) for fn in sorted(os.listdir(prof))
                          if fn.startswith(('throttle_v22_', 'throttle_v21_', 'throttle_v2_')) and fn.endswith('.json')},
                predict_v3_py=C.sha256_file(PV.__file__), npu_chain_py=C.sha256_file(npu_chain.__file__),
                this=C.sha256_file(os.path.abspath(__file__)), common_py=C.sha256_file(C.__file__))


def frozen_check():
    v2 = C.load_json(V3_PRED_V2)
    s = model_shas()
    return dict(v3_prediction_v2_sha256=C.sha256_file(V3_PRED_V2), model_files_equal=(s['model_files'] == v2['model_files']),
                profiles_equal=(s['profiles'] == v2['profiles']), predict_v3_py_equal=(s['predict_v3_py'] == v2['code']['predict_v3_py']))


def read_start_skins():
    """16 valid cells' load-start SKIN from the energy-C judge JSONs (inputs for the 'actual' rows)."""
    out = {}
    for b in C.BLOCKS:
        sess = '1008c' if b <= 4 else '1009c'
        for cell in C.CELLS:
            suf = '_re' if (cell, b) in (('NAc', 8), ('NBc', 7)) else ''
            J = C.load_json(os.path.join(C.OD_SIM, f'out_{sess}', f'{cell}_b{b}{suf}.json'))
            out[C.cell_key(cell, b)] = J['start']['start_skin']
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--out-od', default=C.OUT_OD)
    ap.add_argument('--out-repo', default=C.OUT_REPO)
    ap.add_argument('--no-actual', action='store_true', help='skip the described-only actual-start rows')
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    fc = frozen_check()
    if not (fc['model_files_equal'] and fc['profiles_equal'] and fc['predict_v3_py_equal']):
        print('frozen model / prediction path differs from the V3 v2 record — stop', fc)
        return 8
    starts = None if a.no_actual else read_start_skins()
    runs, actual, info = predict_all(starts)
    res = dict(kind='modelerr_predict_energyc_v1', registration=f'{C.REG} ({C.REG_COMMIT[:7]}) §1 · §3', main_model=C.MAIN, models=list(C.MODELS),
               model_labels=C.MODEL_LABEL, columns=list(C.COLUMNS), A0=PV.A0, BAT0_rule='BAT0 = SKIN0 - d_ref (v2.1 · v2.2), v2 없음',
               R0_NPU=PV.R0, throttle_threshold=C.THR, first_throttle_rule='칸 k 와 뒤 3칸 모두 ≥ ×1.06 (night1005_judge HOLD 3) · 모형 10 s 칸 = predict_v3.run_metrics 칸',
               skin_899_rule='1 s 재생 행 t = 899 (구간 0 시작 = 0) 의 SKIN', bin_rule='10 s 칸 k = [10k, 10k+10) s 의 1 s 행 평균 · 90칸',
               chains={cell: dict(chain_id=info[cell]['chain_id'], canonical_sha256=info[cell]['sha256'], file_sha256=info[cell]['source_file_sha256'],
                                  segments=[(s['duty'], s['duration_s']) for s in info[cell]['spec']['segments']], sigma_s=info[cell]['total_duration_s']) for cell in C.CELLS},
               runs=runs, actual_start_rows=dict(note='기술만 — 판정 아님 (결과 전 선언 · freeze_modelerr.txt (b)) · T0 = 칸의 실제 부하 시작 SKIN', start_skins=starts, rows=actual),
               frozen_check=fc, shas=model_shas(), checks=PV.checks())
    os.makedirs(a.out_od, exist_ok=True)
    os.makedirs(a.out_repo, exist_ok=True)
    p1 = os.path.join(a.out_od, 'predict_energyc.json')
    s1 = C.write_json(p1, res)
    s2 = C.write_json(os.path.join(a.out_repo, 'predict_energyc.json'), res)
    print('frozen_check', fc)
    for cell in C.CELLS:
        for m in C.MODELS:
            for T0 in C.COLUMNS:
                r = runs[cell][m][str(T0)]
                print(f"{cell} {m:8s} {T0}: max {r['max_skin']:.2f} · 899 s {r['skin_899']:.2f} · 1st throttle {r['first_throttle_s']} · thr {r['throttle_time_s']} s · n {r['n_model']:.0f}")
    for m in C.MODELS:
        for T0 in C.COLUMNS:
            d = runs['NAc'][m][str(T0)]['max_skin'] - runs['NBc'][m][str(T0)]['max_skin']
            print(f"Δmax SKIN (A − B) {m:8s} {T0}: {d:+.3f}")
    print('->', p1, s1, '| repo copy', s2)
    return 0


# ============================================================ selftest (양방향 · 결과 전)
def selftest():
    res = []

    def check(name, cond, got=''):
        res.append((name, bool(cond), got))
    check('① flags: d100 → True · d1 → all False · d50 → 5 on-seconds per 10 s (20 s → 10)',
          PV.flags(100, 10) is True and PV.flags(1, 20) == [False] * 20 and sum(PV.flags(50, 20)) == 10 and PV.flags(50, 10) == [True] * 5 + [False] * 5,
          PV.flags(50, 10))
    chains = {c: load_chain(c)[0] for c in C.CELLS}
    check('① chain canonical SHA = 에너지C_체인기록 (NAc 4433e259… · NBc ba74ed03…) · Σ 900 · 구간 (100,300)(1,600) / (50,620)(1,280)',
          [(s['duty'], s['duration_s']) for s in chains['NAc']['segments']] == [(100, 300), (1, 600)]
          and [(s['duty'], s['duration_s']) for s in chains['NBc']['segments']] == [(50, 620), (1, 280)])
    fc = frozen_check()
    check('① frozen: model files · profiles · predict_v3.py SHA = V3 v2 prediction record', fc['model_files_equal'] and fc['profiles_equal'] and fc['predict_v3_py_equal'], fc)
    # 합성 체인만 재생한다 (에너지 C 체인의 예측은 커밋 ② 뒤 4단계에서 처음 계산) — d100 60 s + d1 30 s · d50 100 s + d1 20 s
    syn_a = dict(segments=[dict(accelerator='NPU', duty=100, duration_s=60), dict(accelerator='NPU', duty=1, duration_s=30)])
    syn_b = dict(segments=[dict(accelerator='NPU', duty=50, duration_s=100), dict(accelerator='NPU', duty=1, duration_s=20)])
    sch = PV.schedule(syn_a)
    rows, end = PV.simulate('v22', sch, 29.5)
    rows2, end2 = PV.simulate('v22', sch, 29.5)
    check('② determinism: same replay twice → identical rows (합성 체인)', rows == rows2 and end == end2, len(rows))
    mt = cell_metrics(syn_a, rows, end)
    pm = PV.run_metrics(syn_a, rows, end)
    check('② cell_metrics reuses predict_v3.run_metrics (max · end · t38 · throttle_time · n equal)',
          abs(mt['max_skin'] - pm['max_skin']) < 1e-6 and abs(mt['end_skin'] - pm['end_skin']) < 1e-6 and mt['t38_s'] == pm['t38_s']
          and mt['throttle_time_s'] == pm['throttle_time_s'] and abs(mt['n_model'] - pm['n_model']) < 1e-3)
    check('② rows = Σ (90) · bins = Σ/10 (9) · bin 0 mean = mean(rows 0..9) · skin_899 None when Σ ≤ 899 · 6 active bins',
          len(mt['skin_1s']) == 90 and len(mt['bin_mean_skin']) == 9 and abs(mt['bin_mean_skin'][0] - sum(r['skin'] for r in rows[:10]) / 10) < 1e-3
          and mt['skin_899'] is None and mt['n_active_bins'] == 6)
    mb = cell_metrics(syn_b, *PV.simulate('v22', PV.schedule(syn_b), 30.5))
    check('② d50 합성 체인: 10 active bins · 모든 칸에 가동 초 있음 (ratio not None)', mb['n_active_bins'] == 10 and all(x is not None for x in mb['ratio_bins']))
    check('③ first_throttle HOLD 3: [1,1,1.07,1.07,1.07,1.07] → 2 · [1,1.07,1.0,1.07,1.07,1.07] → None · [1.06]*4 → 0 (경계 포함) · None 칸 → 실패',
          C.first_throttle([1, 1, 1.07, 1.07, 1.07, 1.07]) == 2 and C.first_throttle([1, 1.07, 1.0, 1.07, 1.07, 1.07]) is None
          and C.first_throttle([1.06] * 4) == 0 and C.first_throttle([1.07, None, 1.07, 1.07, 1.07]) is None and C.first_throttle([1.07, 1.07, 1.07]) is None
          and C.first_throttle([1.0, None, 1.07, 1.07, 1.07, 1.07]) == 2)
    check('③ ratio_bins ref = first-30 s median → bins 0..2 ≈ 1 when no throttling', all(abs(x - 1) < 0.02 for x in mt['ratio_bins'][:3]))
    # 등록 §1: 모형 4 변형 · 열 2 가 모두 도는지 (합성 체인)
    ok_models = True
    for m in C.MODELS:
        for T0 in C.COLUMNS:
            r, e = PV.simulate(m, sch, T0)
            ok_models &= len(r) == 90 and math.isfinite(r[-1]['skin'])
    check('④ 모형 4 변형 × 열 2 가 합성 체인에서 전부 돈다 (유한 SKIN)', ok_models)
    # Σ 900 합성 체인 (d1 900 s — 에너지 C 체인 아님): skin_899 = 행 899 · 90 bins
    syn_c = dict(segments=[dict(accelerator='NPU', duty=1, duration_s=900)])
    rows_c, end_c = PV.simulate('v22', PV.schedule(syn_c), 29.5)
    mc = cell_metrics(syn_c, rows_c, end_c) if False else None  # cell_metrics needs an active segment (ref30); only the row/bin arithmetic is checked here
    check('④ Σ 900 재생: 900 rows · skin_899 = rows[899] · bin_means 90', len(rows_c) == 900 and len(bin_means([r['skin'] for r in rows_c], 90)) == 90
          and abs(rows_c[C.T_899]['skin'] - rows_c[899]['skin']) < 1e-12 and mc is None)
    check('④ PV.checks(): v2 θ params = night1004 route · flags = 1005e duty_flags · 1005e v21 NAe reproduced',
          (lambda ck: ck['v2_t0.3_params_equal_night1004_route'] and ck['v2_t0.75_params_equal_night1004_route'] and ck['flags_equal_duty_flags_d10_d50_d1']
           and all(v['equal'] for v in ck['reproduce_1005e_v21_NAe'].values()))(PV.checks()))
    check('⑤ pick_column: 30.0 → 29.5 (tie) · 30.1 → 30.5 · 27.2 → 29.5 (범위 밖 표시) · None → None',
          C.pick_column(30.0) == 29.5 and C.pick_column(30.1) == 30.5 and C.pick_column(27.2) == 29.5 and C.pick_column(None) is None and C.in_range(27.2) is False and C.in_range(28.3) is True)
    ok = all(c for _, c, _ in res)
    print('| 시험 | 결과 | 값 |\n|---|---|---|')
    for name, c, got in res:
        print(f"| {name} | {'PASS' if c else 'FAIL'} | {str(got)[:160]} |")
    print(f"\nselftest 전체: {'PASS' if ok else 'FAIL'} ({sum(1 for _, c, _ in res if c)}/{len(res)})")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
