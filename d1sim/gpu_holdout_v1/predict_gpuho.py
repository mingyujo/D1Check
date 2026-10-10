"""predict_gpuho.py — frozen-model predictions for the GPU holdout chains (prereg d1sim/docs/GPU홀드아웃_사전등록_v1.md §1, written BEFORE any phone cell).

Prediction path = the V3 v2 · P1j one, imported unmodified from d1sim/v3/predict_v3.py (flags · schedule · simulate · run_metrics):
models v2.2 V22-M e52a922 (main, throttle_v22.simulate model='effnet' → g_GPU) · v2.1 c6a7da2 · v2 V2-Lb θ_NPU 0.3 / 0.75 42338e7 —
code and parameters as committed (model file / profile SHAs are written and must equal the V3 v2 prediction's record — frozen_check).
GPU engine profile = CompiledModel (throttle_v22.load_params default engine 'CM' — the N2 GPU runs were CompiledModel runs).
Chains: GAh = tools/chains/gpu_eff_work100_v1.json (d100 300 s + d1 600 s) · GBh = gpu_eff_work50eq_v1.json (d50 T s + d1 900 − T s).

Start-state rule = V3 v2 rule (등록 §1): columns SKIN 29.5 · 30.5 · A0 = −1.0 · BAT0 = SKIN0 − d_ref (v2.1 · v2.2; v2 has no body state).
The comparison column per cell / block is chosen later (judge) by the measured start SKIN (nearest · tie 29.5 · no interpolation).
Per (chain · model · column): 1 s SKIN rows (900), 10 s bin means (90), max SKIN, SKIN at t = 899 s, window-end SKIN, t38/t40/t42,
10 s executing-ratio bins over the active segment (ref = median executing-second ratio in the first 30 s), first throttle bin
(k with k..k+3 all ≥ ×1.10 — GPU threshold, night1005 HOLD 3 rule), throttle time (bins ≥ ×1.10). No n prediction (no GPU R0).

Described-only extra (등록 §1 "기술 열", 판정 아님): --actual <cells_gpuho.json> AFTER the measurement replays each valid cell with
T0 = its actual load-start SKIN → predict_gpuho_actual.json (separate file; predict_gpuho.json is never rewritten).

  py -X utf8 -m d1sim.gpu_holdout_v1.predict_gpuho [--selftest] [--actual cells_gpuho.json] [--out-od DIR] [--out-repo DIR]
"""
from __future__ import annotations

import argparse
import math
import os
import statistics
import sys

from d1sim.gpu_holdout_v1 import common as C
from d1sim.v3 import predict_v3 as PV

C.stdout_utf8()
sys.path.insert(0, os.path.join(C.ROOT, 'tools'))
import npu_chain  # noqa: E402  (tools/npu_chain.py — canonical SHA, read only)

V3_PRED_V2 = os.path.join(C.ROOT, 'd1sim', 'out', 'v3_prediction_v2.json')


def load_chain(cell):
    info = npu_chain.load_chain(os.path.join(C.CHAIN_DIR, C.CELLS[cell]['chain'] + '.json'))
    if info['sha256'] != C.CELLS[cell]['canonical']:
        raise SystemExit(f'chain canonical SHA differs for {cell}: {info["sha256"]} ≠ {C.CELLS[cell]["canonical"]}')
    if any(s['accelerator'] != 'GPU' for s in info['spec']['segments']):
        raise SystemExit(f'{cell}: not a GPU chain')
    return info['spec'], info


def bin_means(skin_1s, n_bins, bin_s=C.BIN_S):
    out = []
    for k in range(n_bins):
        seg = skin_1s[k * bin_s:(k + 1) * bin_s]
        out.append(round(sum(seg) / len(seg), 4) if seg else None)
    return out


def ratio_bins(chain, rows):
    """10 s executing-ratio bins over active segments (duty ≥ 10), ratio = median(1/s)/ref — predict_v3.run_metrics arithmetic."""
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


def cell_metrics(chain, rows, end_row, thr=C.THR):
    m = PV.run_metrics(chain, rows, end_row)                 # max_skin · end_skin · t38/40/42 (unchanged arithmetic; its throttle_time uses ×1.06 — replaced below)
    skin = [r['skin'] for r in rows]
    sigma = sum(s['duration_s'] for s in chain['segments'])
    if len(skin) != sigma:
        raise SystemExit(f'replay rows {len(skin)} ≠ Σ {sigma}')
    rb, ref = ratio_bins(chain, rows)
    k1 = C.first_throttle(rb, thr)
    thr_time = C.BIN_S * sum(1 for b in rb if b is not None and b >= thr - C.EPS)
    return dict(max_skin=C.r6(m['max_skin']), skin_899=C.r6(skin[C.T_899]) if len(skin) > C.T_899 else None, end_skin=C.r6(m['end_skin']),
                t38_s=m['t38_s'], t40_s=m['t40_s'], t42_s=m['t42_s'], status_ge1_s=m['status_ge1_s'],
                throttle_threshold=thr, throttle_time_s=thr_time, first_throttle_bin=k1, first_throttle_s=None if k1 is None else k1 * C.BIN_S,
                ref30_ratio=C.r6(ref), ratio_bins=[C.r6(x) for x in rb], n_active_bins=len(rb),
                bin_mean_skin=bin_means(skin, sigma // C.BIN_S), skin_1s=[round(x, 4) for x in skin], max_ap=C.r6(m['max_ap']))


def predict_all(start_skins=None):
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


def result_record(runs, info, fc, extra=None):
    res = dict(kind='gpuho_predict_v1', registration=f'{C.REG} ({C.REG_COMMIT[:7]}) §1', main_model=C.MAIN, models=list(C.MODELS), model_labels=C.MODEL_LABEL,
               columns=list(C.COLUMNS), A0=PV.A0, BAT0_rule='BAT0 = SKIN0 - d_ref (v2.1 · v2.2), v2 없음', gpu_engine='CM (throttle_v22.load_params 기본 · GPU_compiledmodel 프로파일)',
               throttle_threshold=C.THR, first_throttle_rule='칸 k 와 뒤 3칸 모두 ≥ ×1.10 (GPU · night1005_judge HOLD 3) · 모형 10 s 칸 = predict_v3.run_metrics 칸',
               skin_899_rule='1 s 재생 행 t = 899 (구간 0 시작 = 0) 의 SKIN', bin_rule='10 s 칸 k = [10k, 10k+10) s 의 1 s 행 평균 · 90칸',
               n_note='GPU R0 없음 — n (추론 수) 예측 없음 (등록 §3 r 은 실측 기술만)',
               chains={cell: dict(chain_id=info[cell]['chain_id'], canonical_sha256=info[cell]['sha256'], file_sha256=info[cell]['source_file_sha256'],
                                  segments=[(s['duty'], s['duration_s']) for s in info[cell]['spec']['segments']], sigma_s=info[cell]['total_duration_s']) for cell in C.CELLS},
               runs=runs, frozen_check=fc, shas=model_shas(), checks=PV.checks())
    if extra:
        res.update(extra)
    return res


def read_actual_starts(cells_json):
    """valid cells' load-start SKIN (= judge JSON start_skin) from cells_gpuho.json (written after the measurement)."""
    cj = C.load_json(cells_json)
    out = {}
    for c in cj['cells']:
        if c.get('status') != 'valid':
            continue
        J = C.load_json(os.path.join(C.OD, c['judge_json']))
        out[C.cell_key(c['cell'], c['block'])] = J['start']['start_skin']
    return out, C.sha256_file(cells_json)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--actual', help='cells_gpuho.json (after the measurement) → described-only actual-start rows file')
    ap.add_argument('--out-od', default=C.OUT_OD)
    ap.add_argument('--out-repo', default=C.OUT_REPO)
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    fc = frozen_check()
    if not (fc['model_files_equal'] and fc['profiles_equal'] and fc['predict_v3_py_equal']):
        print('frozen model / prediction path differs from the V3 v2 record — stop (등록 §0-1)', fc)
        return 8
    if a.actual:
        starts, csha = read_actual_starts(a.actual)
        runs, actual, info = predict_all(starts)
        res = result_record(runs, info, fc, dict(kind='gpuho_predict_actual_v1', note='기술만 — 판정 아님 (등록 §1 기술 열 · T0 = 칸의 실제 부하 시작 SKIN)',
                                                   cells_json_sha256=csha, start_skins=starts, actual_rows=actual))
        p1 = os.path.join(a.out_od, 'predict_gpuho_actual.json')
    else:
        p1 = os.path.join(a.out_od, 'predict_gpuho.json')
        if os.path.exists(p1):
            print('predict_gpuho.json already exists — the pre-measurement prediction is written once (refused)', p1)
            return 9
        runs, _, info = predict_all(None)
        res = result_record(runs, info, fc)
    os.makedirs(a.out_od, exist_ok=True)
    os.makedirs(a.out_repo, exist_ok=True)
    s1 = C.write_json(p1, res)
    s2 = C.write_json(os.path.join(a.out_repo, os.path.basename(p1)), res)
    print('frozen_check', fc)
    for cell in C.CELLS:
        for m in C.MODELS:
            for T0 in C.COLUMNS:
                r = runs[cell][m][str(T0)]
                print(f"{cell} {m:8s} {T0}: max {r['max_skin']:.2f} · 899 s {r['skin_899']:.2f} · 1st throttle {r['first_throttle_s']} · thr {r['throttle_time_s']} s")
    for m in C.MODELS:
        for T0 in C.COLUMNS:
            d = runs['GAh'][m][str(T0)]['max_skin'] - runs['GBh'][m][str(T0)]['max_skin']
            print(f"Δmax SKIN (A − B) {m:8s} {T0}: {d:+.3f}")
    print('->', p1, s1, '| repo copy', s2)
    return 0


# ============================================================ selftest (양방향 · 결과 전 — 실제 체인 예측은 main 에서만)
def selftest():
    res = []

    def check(name, cond, got=''):
        res.append((name, bool(cond), got))
    chains = {c: load_chain(c)[0] for c in C.CELLS}
    check('① chain: GAh = (100,300)(1,600) GPU · GBh = (50,T)(1,900−T) GPU · canonical SHA = common',
          [(s['duty'], s['duration_s']) for s in chains['GAh']['segments']] == [(100, 300), (1, 600)]
          and chains['GBh']['segments'][0]['duty'] == 50 and chains['GBh']['segments'][1]['duty'] == 1
          and chains['GBh']['segments'][0]['duration_s'] + chains['GBh']['segments'][1]['duration_s'] == 900
          and all(s['accelerator'] == 'GPU' for c in chains.values() for s in c['segments']), [(s['duty'], s['duration_s']) for s in chains['GBh']['segments']])
    fc = frozen_check()
    check('① frozen: model files · profiles · predict_v3.py SHA = V3 v2 prediction record', fc['model_files_equal'] and fc['profiles_equal'] and fc['predict_v3_py_equal'], fc)
    syn_a = dict(segments=[dict(accelerator='GPU', duty=100, duration_s=60), dict(accelerator='GPU', duty=1, duration_s=30)])
    syn_b = dict(segments=[dict(accelerator='GPU', duty=50, duration_s=100), dict(accelerator='GPU', duty=1, duration_s=20)])
    sch = PV.schedule(syn_a)
    rows, end = PV.simulate('v22', sch, 29.5)
    rows2, end2 = PV.simulate('v22', sch, 29.5)
    check('② determinism: same GPU replay twice → identical rows (합성 체인)', rows == rows2 and end == end2, len(rows))
    mt = cell_metrics(syn_a, rows, end)
    pm = PV.run_metrics(syn_a, rows, end)
    check('② cell_metrics reuses predict_v3.run_metrics (max · end · t38 equal) · threshold 1.10 · 90 rows · 9 bins · 6 active bins · skin_899 None (Σ ≤ 899)',
          abs(mt['max_skin'] - pm['max_skin']) < 1e-6 and abs(mt['end_skin'] - pm['end_skin']) < 1e-6 and mt['t38_s'] == pm['t38_s'] and mt['throttle_threshold'] == 1.10
          and len(mt['skin_1s']) == 90 and len(mt['bin_mean_skin']) == 9 and mt['n_active_bins'] == 6 and mt['skin_899'] is None)
    mb = cell_metrics(syn_b, *PV.simulate('v22', PV.schedule(syn_b), 30.5))
    check('② d50 합성 체인: 10 active bins · 모든 칸에 가동 초 있음', mb['n_active_bins'] == 10 and all(x is not None for x in mb['ratio_bins']))
    check('③ first_throttle GPU ×1.10 경계: [1,1,1.10,1.10,1.10,1.10] → 2 · [1.09]*5 → None · [1,1.07,1.07,1.07,1.07] (NPU 문턱이면 1) → None',
          C.first_throttle([1, 1, 1.10, 1.10, 1.10, 1.10], C.THR) == 2 and C.first_throttle([1.09] * 5, C.THR) is None
          and C.first_throttle([1, 1.07, 1.07, 1.07, 1.07], C.THR) is None and C.first_throttle([1, 1.07, 1.07, 1.07, 1.07], 1.06) == 1)
    check('③ ratio_bins ref = first-30 s median → bins 0..2 ≈ 1 when no throttling', all(abs(x - 1) < 0.02 for x in mt['ratio_bins'][:3]))
    ok_models = True
    for m in C.MODELS:
        for T0 in C.COLUMNS:
            r, e = PV.simulate(m, sch, T0)
            ok_models &= len(r) == 90 and math.isfinite(r[-1]['skin'])
    check('④ 모형 4 변형 × 열 2 가 GPU 합성 체인에서 전부 돈다 (유한 SKIN)', ok_models)
    # GPU engine = CM: the v22 GPU route equals throttle_v22.simulate with load_params(engine='CM') and differs from INT
    from d1sim import throttle_v22 as tv22
    p_cm = tv22.load_params('throttle_v22_', 'CM')
    sched = list(sch) + [(len(sch), None, None, 1)]
    rows_cm = tv22.simulate(p_cm, sched, 29.5, PV.A0, B0=29.5 - p_cm['thermal']['d_ref'], model='effnet')[:-1]
    p_int = tv22.load_params('throttle_v22_', 'INT')
    rows_int = tv22.simulate(p_int, sched, 29.5, PV.A0, B0=29.5 - p_int['thermal']['d_ref'], model='effnet')[:-1]
    check('④ v2.2 GPU 경로 = CompiledModel 프로파일 (CM 행과 같음 · INT 행과 다름)', [r['skin'] for r in rows] == [r['skin'] for r in rows_cm] and [r['skin'] for r in rows] != [r['skin'] for r in rows_int])
    check('④ PV.checks(): v2 θ params = night1004 route · flags = 1005e duty_flags · 1005e v21 NAe reproduced',
          (lambda ck: ck['v2_t0.3_params_equal_night1004_route'] and ck['v2_t0.75_params_equal_night1004_route'] and ck['flags_equal_duty_flags_d10_d50_d1']
           and all(v['equal'] for v in ck['reproduce_1005e_v21_NAe'].values()))(PV.checks()))
    check('⑤ pick_column: 30.0 → 29.5 (tie) · 30.1 → 30.5 · 27.2 → 29.5 (범위 밖 표시) · None → None',
          C.pick_column(30.0) == 29.5 and C.pick_column(30.1) == 30.5 and C.pick_column(27.2) == 29.5 and C.pick_column(None) is None and C.in_range(27.2) is False and C.in_range(28.3) is True)
    check('⑥ predict_gpuho.json 이 이미 있으면 거부 (한 번만) — 파일 유무 확인', True, os.path.exists(os.path.join(C.OUT_OD, 'predict_gpuho.json')))
    return C.print_table(res)


if __name__ == '__main__':
    sys.exit(main())
