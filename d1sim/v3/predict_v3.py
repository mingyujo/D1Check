"""predict_v3.py — V3 prediction freeze (sim/V3_사전등록_v1.md §6, commit 036f87b), written BEFORE any V3 phone cell.

Models (code and parameters untouched): main v2.2 V22-M (e52a922, EffNet g_m via throttle_v22.simulate(model='effnet')) ·
sensitivity v2.1 (c6a7da2, throttle_v21.simulate) · v2 θ0.3 · θ0.75 (42338e7, throttle_v2.simulate, env_v2.v2_params(theta_npu, 'v2') —
the same parameter dicts the policy simulator uses; equal to predict_night_1004.v2_params + NPU theta, checked at run time).
Chains = tools/chains/v3_{A,B}_{base,ours}_v1.json (read here; commanded duty, no merge needed — §2-3 not triggered).
Start columns SKIN 29.5 · 30.5 · A0 = -1.0 · BAT0 = SKIN0 - d_ref (v2.1 / v2.2; v2 has no body state) — §6.
R0 = EffNet NPU 1,130.7 inferences per executing second (정책비교_사전등록_v1.md §1, the policy simulator's R0).

P1g 가 정함 (결과 전 — 폰 V3 칸 0):
  (1) chain replay at dt = 1 s (the fitted models' step; throttle_v21.simulate contract). Per-second execution flags inside each
      10 s period anchored at the segment start (the runner's DutyCycleTracker phase): d100 = all on; d1 = idle (as in every earlier
      prediction — d1 tail_idle chains were fitted that way); other duties = Bresenham on-seconds per period
      floor(d(p+1)/10) - floor(dp/10) at the start of period p (d10 1 · d50 5 · d25 2,3,2,3… · d75 7,8,7,8… — mean = d exactly over 20 s).
      For d10 · d50 · d100 · d1 this equals predict_night_1005e.duty_flags (checked).
  (2) run metrics (§4) on the model rows (1 s): max SKIN · max AP (BAT not modelled -> null) · t38/t40/t42 = seconds with SKIN >= level ·
      status >= 1 seconds · window-end SKIN = state after the last second (one extra idle row read, not counted elsewhere) ·
      n = Σ over executing seconds of R0 · s (d1 contributes 0 in the model — the phone n includes the d1 inferences) ·
      throttle time = over active segments (duty >= 10) 10 s bins (floor(L/10) per segment, as bins10) whose median executing-second
      ratio 1/s >= 1.06 × reference, reference = median ratio of the executing seconds in the first 30 s of the first active segment.
  (3) block Δ = base − ours for max SKIN (main), t38 · t40 · throttle time · window-end SKIN (aux), r = n_ours / n_base — same column.
  (4) span ceiling (1-3) = ceil(1.3 × max over models and columns of predicted n incl. a d1 estimate (d1 seconds × 0.01 × R0)) to 100,000.

  py -m d1sim.v3.predict_v3            # -> d1sim/out/v3_prediction_1006.json
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import statistics
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from d1sim import env_v2  # noqa: E402
from d1sim import throttle_v2 as tv2  # noqa: E402
from d1sim import throttle_v21 as tv21  # noqa: E402
from d1sim import throttle_v22 as tv22  # noqa: E402

CH = os.path.join(ROOT, 'tools', 'chains')
OUT = os.path.join(ROOT, 'd1sim', 'out')
TL = os.path.join(OUT, 'v3_1006', 'timelines.json')
CHAINS = {'A': {'base': 'v3_A_base_v1', 'ours': 'v3_A_ours_v1'}, 'B': {'base': 'v3_B_base_v1', 'ours': 'v3_B_ours_v1'}}
POLKEY = {'base': 'fixed-prio', 'ours': 'ours(m0,o0)'}
COLUMNS = (29.5, 30.5)
A0 = -1.0
R0 = 1130.7
THR = 1.06
LEVELS = (38.0, 40.0, 42.0)
EPS = 1e-9
MODELS = ('v22', 'v21', 'v2_t0.3', 'v2_t0.75')
MAIN = 'v22'


def _sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def flags(duty, dur):
    if duty >= 100:
        return True
    if duty <= 1:
        return [False] * dur
    f = []
    for k in range(dur):
        p, ph = divmod(k, 10)
        on = (duty * (p + 1)) // 10 - (duty * p) // 10
        f.append(ph < on)
    return f


def schedule(chain):
    return [(i, s['accelerator'], flags(s['duty'], s['duration_s']), s['duration_s']) for i, s in enumerate(chain['segments'])]


def params(model):
    if model == 'v22':
        return tv22.load_params('throttle_v22_')
    if model == 'v21':
        return tv22.load_params('throttle_v21_')
    return env_v2.v2_params(theta_npu=float(model[4:]), cooling='v2')


def simulate(model, sched, T0):
    p = params(model)
    sched = list(sched) + [(len(sched), None, None, 1)]       # one extra idle second -> window-end state
    if model == 'v22':
        rows = tv22.simulate(p, sched, T0, A0, B0=T0 - p['thermal']['d_ref'], model='effnet')
    elif model == 'v21':
        rows = tv21.simulate(p, sched, T0, A0, B0=T0 - p['thermal']['d_ref'])
    else:
        rows = tv2.simulate(p, sched, T0, A0)
    return rows[:-1], rows[-1]


def run_metrics(chain, rows, end_row):
    segs = chain['segments']
    sk = [r['skin'] for r in rows]
    out = dict(max_skin=max(sk), max_ap=max(r['ap'] for r in rows), max_bat=None, end_skin=end_row['skin'],
               status_ge1_s=sum(1 for r in rows if r['status'] >= 1))
    for lv in LEVELS:
        out[f't{int(lv)}_s'] = sum(1 for x in sk if x >= lv - EPS)
    ex = [r for r in rows if r['ex'] and r['ratio'] is not None]
    out['n_model'] = sum(R0 / r['ratio'] for r in ex)
    d1_s = sum(s['duration_s'] for s in segs if s['duty'] <= 1)
    out['n_with_d1_est'] = out['n_model'] + d1_s * 0.01 * R0
    active = [i for i, s in enumerate(segs) if s['duty'] >= 10]
    first = active[0]
    ref = statistics.median([r['ratio'] for r in ex if r['seg'] == first and r['t'] < 30])
    bins = []
    for i in active:
        L = segs[i]['duration_s']
        for k in range(int(math.floor(L / 10 + 1e-9))):
            v = [r['ratio'] for r in ex if r['seg'] == i and 10 * k <= r['t'] < 10 * (k + 1)]
            bins.append(dict(seg=i, k=k, ratio=(statistics.median(v) / ref) if v else None))
    out['throttle_time_s'] = 10 * sum(1 for b in bins if b['ratio'] is not None and b['ratio'] >= THR - EPS)
    out['ref30_ratio'] = ref
    out['n_active_bins'] = len(bins)
    out['skin_series_60s'] = [round(sk[i], 3) for i in range(0, len(sk), 60)]
    return out


def block(base, ours):
    def d(k):
        return base[k] - ours[k]
    return dict(d_max_skin=d('max_skin'), d_t38_s=d('t38_s'), d_t40_s=d('t40_s'), d_t42_s=d('t42_s'), d_throttle_time_s=d('throttle_time_s'),
                d_end_skin=d('end_skin'), r_model=ours['n_model'] / base['n_model'] if base['n_model'] else None,
                r_with_d1_est=ours['n_with_d1_est'] / base['n_with_d1_est'])


def checks():
    from d1sim.tools.predict_night_1004 import v2_params
    from d1sim.tools import predict_night_1005e as P5
    out = {}
    for th in (0.3, 0.75):
        b = v2_params()
        b = dict(b, ctrl=dict(b['ctrl'], NPU=dict(b['ctrl']['NPU'], theta=th)))
        out[f'v2_t{th}_params_equal_night1004_route'] = json.dumps(params(f'v2_t{th}'), sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)
    out['flags_equal_duty_flags_d10_d50_d1'] = all(flags(d, 600) == P5.duty_flags(d, 600) for d in (10, 50, 1))
    out['flags_mean_exact_20s'] = {d: sum(flags(d, 20)) / 20 * 100 for d in (10, 25, 50, 75)}
    # driver reproduction: the frozen 1005e v2.1 NAe 29.5 / 30.5 prediction through this module's simulate + the 1005e metric code
    old = json.load(open(os.path.join(OUT, 'night_1005e_prediction_v21.json'), encoding='utf-8'))
    rep = {}
    for T0 in COLUMNS:
        sch = [(0, 'NPU', True, 300), (1, 'NPU', [False] * 600, 600)]
        rows, _ = simulate('v21', sch, T0)
        rep[str(T0)] = dict(max_skin_here=max(r['skin'] for r in rows), max_skin_frozen=old['cells']['NAe'][str(T0)]['max_skin'],
                            t38_here=sum(1 for r in rows if r['skin'] >= 38.0 - EPS), t38_frozen=old['cells']['NAe'][str(T0)]['t38_s'])
        rep[str(T0)]['equal'] = abs(rep[str(T0)]['max_skin_here'] - rep[str(T0)]['max_skin_frozen']) < 1e-9 and rep[str(T0)]['t38_here'] == rep[str(T0)]['t38_frozen']
    out['reproduce_1005e_v21_NAe'] = rep
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    tl = json.load(open(TL, encoding='utf-8'))
    chains, csha, fsha = {}, {}, {}
    for c, d in CHAINS.items():
        for role, cid in d.items():
            p = os.path.join(CH, cid + '.json')
            chains[cid] = json.load(open(p, encoding='utf-8'))
            fsha[cid] = _sha(p)
    runs = {cid: {} for cid in chains}
    for cid, ch in chains.items():
        sch = schedule(ch)
        for m in MODELS:
            for T0 in COLUMNS:
                rows, end = simulate(m, sch, T0)
                runs[cid].setdefault(m, {})[str(T0)] = run_metrics(ch, rows, end)
    blocks = {}
    for c, d in CHAINS.items():
        for m in MODELS:
            for T0 in COLUMNS:
                blocks.setdefault(c, {}).setdefault(m, {})[str(T0)] = block(runs[d['base']][m][str(T0)], runs[d['ours']][m][str(T0)])
    sim_hold = {}
    for c in CHAINS:
        C = tl['conditions'][c]
        pm = {role: C['policies'][POLKEY[role]]['metrics'] for role in ('base', 'ours')}
        sim_hold[c] = dict(condition=C['condition'], seed=C['seed'], condition_delta_holdout_median_c=C['delta_holdout_c'],
                           note='정책 시뮬 (FG 포함 · R20 잔재 · 실현 duty · 시작 30.5) — 체인 재생 예측 (명령 duty · FG 없음 · 잔재 없음) 과 다를 수 있다 (§6)',
                           base=pm['base'], ours=pm['ours'],
                           d_max_skin_seed=pm['base']['max_skin'] - pm['ours']['max_skin'], d_end_skin_seed=pm['base']['end_skin'] - pm['ours']['end_skin'],
                           d_t38_seed=pm['base']['t38_s'] - pm['ours']['t38_s'], d_t40_seed=pm['base']['t40_s'] - pm['ours']['t40_s'],
                           d_throttle_seed=pm['base']['throttle_s'] - pm['ours']['throttle_s'],
                           r_seed=pm['ours']['bg_completed_inf'] / pm['base']['bg_completed_inf'])
    spans = {}
    for cid in chains:
        mx = max(runs[cid][m][str(T0)]['n_with_d1_est'] for m in MODELS for T0 in COLUMNS)
        spans[cid] = dict(n_max_pred=mx, ceiling=int(math.ceil(1.3 * mx / 100_000.0)) * 100_000)
    res = dict(kind='v3_prediction_1006', registration='d1sim/docs/V3_사전등록_v1.md (036f87b) §6', main_model=MAIN, models=list(MODELS),
               model_notes=dict(v22='v2.2 V22-M e52a922 (throttle_v22.simulate model=effnet, g_m)', v21='v2.1 c6a7da2 (MobileNet 열 피팅 · g_m 없음)',
                                **{f'v2_t{t}': f'v2 V2-Lb 42338e7 θ_NPU {t}' for t in (0.3, 0.75)}),
               columns=list(COLUMNS), A0=A0, BAT0_rule='BAT0 = SKIN0 - d_ref (v2.1 · v2.2), v2 없음', R0_NPU=R0, throttle_threshold=THR,
               decisions=__doc__.split('P1g 가 정함 (결과 전 — 폰 V3 칸 0):')[1].split('py -m')[0].strip(),
               chains={cid: dict(file_sha256=fsha[cid], segments=[(s['duty'], s['duration_s']) for s in ch['segments']],
                                 sigma_s=sum(s['duration_s'] for s in ch['segments'])) for cid, ch in chains.items()},
               condition_chains=CHAINS, runs=runs, blocks=blocks, sim_holdout=sim_hold, span_ceiling=spans, checks=checks(),
               timelines_sha256=_sha(TL),
               model_files={k: _sha(os.path.join(ROOT, 'd1sim', k)) for k in ('throttle_v22.py', 'throttle_v21.py', 'throttle_v2.py', 'env_v2.py')},
               profiles={fn: _sha(os.path.join(ROOT, 'd1sim', 'profiles', fn)) for fn in sorted(os.listdir(os.path.join(ROOT, 'd1sim', 'profiles')))
                         if fn.startswith(('throttle_v22_', 'throttle_v21_', 'throttle_v2_')) and fn.endswith('.json')})
    p = os.path.join(OUT, 'v3_prediction_1006.json')
    s = json.dumps(res, indent=1, ensure_ascii=False, default=str)
    open(p, 'w', encoding='utf-8', newline='\n').write(s)
    print(json.dumps(res['checks'], ensure_ascii=False))
    for c in CHAINS:
        for m in MODELS:
            for T0 in COLUMNS:
                b = blocks[c][m][str(T0)]
                rb, ro = runs[CHAINS[c]['base']][m][str(T0)], runs[CHAINS[c]['ours']][m][str(T0)]
                print(f"{c} {m:8s} {T0}: base max {rb['max_skin']:.2f} ours {ro['max_skin']:.2f} Δ {b['d_max_skin']:+.2f} | "
                      f"Δt38 {b['d_t38_s']:+.0f} Δt40 {b['d_t40_s']:+.0f} Δthr {b['d_throttle_time_s']:+.0f} Δend {b['d_end_skin']:+.2f} r {b['r_model']:.3f}")
        h = sim_hold[c]
        print(f"   sim holdout seed {h['seed']}: Δmax {h['d_max_skin_seed']:+.2f} Δend {h['d_end_skin_seed']:+.2f} (cond median {h['condition_delta_holdout_median_c']:.3f}) r {h['r_seed']:.3f}")
    print('spans', {k: v['ceiling'] for k, v in spans.items()})
    print('->', p, _sha(p))
    return 0


if __name__ == '__main__':
    sys.exit(main())
