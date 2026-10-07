"""predict_v3_v2.py — V3 v2 prediction freeze (sim/V3_사전등록_v2.md §6, commit d0a513c), written BEFORE any v2 phone cell.

= v1 §6 applied to 4 chains: baseline v2 (v3_A_base_v2 · v3_B_base_v2) + ours v1 (v3_A_ours_v1 · v3_B_ours_v1).
Everything is imported from d1sim/v3/predict_v3.py unmodified (schedule · simulate · run_metrics · block · checks · models ·
columns · R0 · thresholds · decisions (1)-(4)); only the chain table and the output file differ.
§6: the ours rows must equal the v1 prediction (v3_prediction_1006.json 5aa7755e…) — otherwise exit 7 and nothing is written.

  py -m d1sim.v3.predict_v3_v2            # -> d1sim/out/v3_prediction_v2.json
"""
from __future__ import annotations

import json
import math
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from d1sim.v3 import predict_v3 as PV  # noqa: E402

CHAINS = {'A': {'base': 'v3_A_base_v2', 'ours': 'v3_A_ours_v1'}, 'B': {'base': 'v3_B_base_v2', 'ours': 'v3_B_ours_v1'}}
V1_PRED = os.path.join(PV.OUT, 'v3_prediction_1006.json')
V1_PRED_SHA = '5aa7755e6c4a3d6839003e7bfa5163e10d4a8cf5bdf034222c58e5540e105f9f'


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    if PV._sha(V1_PRED) != V1_PRED_SHA:
        print('v1 prediction SHA differs — stop')
        return 8
    v1 = json.load(open(V1_PRED, encoding='utf-8'))
    tl = json.load(open(PV.TL, encoding='utf-8'))
    chains, fsha = {}, {}
    for c, d in CHAINS.items():
        for role, cid in d.items():
            p = os.path.join(PV.CH, cid + '.json')
            chains[cid] = json.load(open(p, encoding='utf-8'))
            fsha[cid] = PV._sha(p)
    runs = {cid: {} for cid in chains}
    for cid, ch in chains.items():
        sch = PV.schedule(ch)
        for m in PV.MODELS:
            for T0 in PV.COLUMNS:
                rows, end = PV.simulate(m, sch, T0)
                runs[cid].setdefault(m, {})[str(T0)] = PV.run_metrics(ch, rows, end)
    # §6: ours rows = v1 prediction (JSON round trip so floats compare as written)
    ours_eq = {}
    for c in CHAINS:
        cid = CHAINS[c]['ours']
        here = json.loads(json.dumps(runs[cid], default=str))
        ours_eq[cid] = dict(equal=(here == v1['runs'][cid]), v1_file_sha256=v1['chains'][cid]['file_sha256'], file_sha256=fsha[cid])
        ours_eq[cid]['equal'] = ours_eq[cid]['equal'] and ours_eq[cid]['v1_file_sha256'] == fsha[cid]
    print('ours rows = v1 prediction:', {k: v['equal'] for k, v in ours_eq.items()})
    if not all(v['equal'] for v in ours_eq.values()):
        print('§6 stop — ours rows differ from v3_prediction_1006.json; nothing written')
        return 7
    blocks = {}
    for c, d in CHAINS.items():
        for m in PV.MODELS:
            for T0 in PV.COLUMNS:
                blocks.setdefault(c, {}).setdefault(m, {})[str(T0)] = PV.block(runs[d['base']][m][str(T0)], runs[d['ours']][m][str(T0)])
    spans = {}
    for cid in chains:
        mx = max(runs[cid][m][str(T0)]['n_with_d1_est'] for m in PV.MODELS for T0 in PV.COLUMNS)
        spans[cid] = dict(n_max_pred=mx, ceiling=int(math.ceil(1.3 * mx / 100_000.0)) * 100_000)
    res = dict(kind='v3_prediction_v2', registration='d1sim/docs/V3_사전등록_v2.md (d0a513c) §6 = V3_사전등록_v1.md (036f87b) §6 on 4 chains',
               main_model=PV.MAIN, models=list(PV.MODELS), model_notes=v1['model_notes'],
               columns=list(PV.COLUMNS), A0=PV.A0, BAT0_rule=v1['BAT0_rule'], R0_NPU=PV.R0, throttle_threshold=PV.THR,
               decisions=v1['decisions'], code=dict(predict_v3_py=PV._sha(PV.__file__), predict_v3_v2_py=PV._sha(os.path.abspath(__file__))),
               chains={cid: dict(file_sha256=fsha[cid], segments=[(s['duty'], s['duration_s']) for s in ch['segments']],
                                 sigma_s=sum(s['duration_s'] for s in ch['segments'])) for cid, ch in chains.items()},
               condition_chains=CHAINS, runs=runs, blocks=blocks, sim_holdout=v1['sim_holdout'], span_ceiling=spans, checks=PV.checks(),
               ours_equal_v1_prediction=dict(v1_prediction='d1sim/out/v3_prediction_1006.json', v1_sha256=V1_PRED_SHA, rows=ours_eq),
               v1_blocks_for_reference=v1['blocks'], timelines_sha256=PV._sha(PV.TL),
               model_files={k: PV._sha(os.path.join(ROOT, 'd1sim', k)) for k in ('throttle_v22.py', 'throttle_v21.py', 'throttle_v2.py', 'env_v2.py')},
               profiles={fn: PV._sha(os.path.join(ROOT, 'd1sim', 'profiles', fn)) for fn in sorted(os.listdir(os.path.join(ROOT, 'd1sim', 'profiles')))
                         if fn.startswith(('throttle_v22_', 'throttle_v21_', 'throttle_v2_')) and fn.endswith('.json')})
    assert res['model_files'] == v1['model_files'] and res['profiles'] == v1['profiles'] and res['timelines_sha256'] == v1['timelines_sha256']
    p = os.path.join(PV.OUT, 'v3_prediction_v2.json')
    s = json.dumps(res, indent=1, ensure_ascii=False, default=str)
    open(p, 'w', encoding='utf-8', newline='\n').write(s)
    print(json.dumps(res['checks'], ensure_ascii=False))
    for c in CHAINS:
        for m in PV.MODELS:
            for T0 in PV.COLUMNS:
                b = blocks[c][m][str(T0)]
                rb, ro = runs[CHAINS[c]['base']][m][str(T0)], runs[CHAINS[c]['ours']][m][str(T0)]
                print(f"{c} {m:8s} {T0}: base max {rb['max_skin']:.2f} ours {ro['max_skin']:.2f} Δ {b['d_max_skin']:+.2f} | "
                      f"Δt38 {b['d_t38_s']:+.0f} Δt40 {b['d_t40_s']:+.0f} Δthr {b['d_throttle_time_s']:+.0f} Δend {b['d_end_skin']:+.2f} "
                      f"r {b['r_model']:.3f} r(d1) {b['r_with_d1_est']:.3f} | base maxAP {rb['max_ap']:.2f}")
    print('spans', {k: v['ceiling'] for k, v in spans.items()})
    print('->', p, PV._sha(p))
    return 0


if __name__ == '__main__':
    sys.exit(main())
