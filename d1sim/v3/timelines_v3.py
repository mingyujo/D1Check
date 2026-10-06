"""timelines_v3.py — V3 1-2: condition A · B BG duty timelines recomputed with the FROZEN policy-eval code (31fb686), checked against
v3_candidates.json (A) and holdout_rows.jsonl (B) — sim/V3_사전등록_v1.md §1 · §2-1 (commit 036f87b).

  py -m d1sim.v3.timelines_v3            # -> d1sim/out/v3_1006/timelines.json (exit 1 if any §2-1 check fails -> stop)

Nothing in d1sim/policy_eval_v2 is modified; run_one / COND / scenario / v3-rep-seed rule are imported or re-applied verbatim.
P1g 가 정함 (결과 전 — 폰 V3 칸 0):
  (a) §2-1 tolerances: max SKIN · window-end SKIN <= 0.01 ℃, BG last completion <= 0.1 s, plus BG completed inferences equal and
      the commanded duty dict identical (A: vs v3_candidates.json; B: vs holdout_rows.jsonl, main model v22).
  (b) "same timeline" = identical commanded duty dict (10 s period -> duty) for BOTH policies (fixed-prio and ours(m0,o0)).
  (c) B's representative seed = run_eval.v3_candidates rule applied to holdout rows of NPU-R20-s2.0-l0.5 (ours − strongest, closest
      to the median, tie -> smaller seed). λ 0.2 is compared at B's seed (and its own representative seed is reported).
  (d) window [0, min(horizon, 3600)] (§2-2); grid cells k = [10k, 10k + 10) clipped at the window end; Σ = ceil(window) whole seconds.
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
from d1sim.policy_eval_v2 import run_eval as RE  # noqa: E402

OUT = os.path.join(ROOT, 'd1sim', 'out', 'v3_1006')
CAND = os.path.join(ROOT, 'd1sim', 'out', 'v3_candidates_1006', 'v3_candidates.json')
HOLD = os.path.join(ROOT, 'd1sim', 'out', 'policy_eval_v2', 'holdout_rows.jsonl')
FROZEN = os.path.join(ROOT, 'd1sim', 'out', 'policy_eval_freeze_v2_frozen.json')
MODEL = RE.MAIN_MODEL
OURS = ('ours', 0.0, 0.0)
OURS_KEY = RE.spec_key(OURS)
BASE_KEY = 'fixed-prio'
TOL_C = 0.01
TOL_S = 0.1
MAX_WIN = 3600.0
COND_A = 'NPU-R20-s3.0-l0.2'
COND_A_TWIN = 'NPU-R20-s3.0-l0.5'
COND_B = 'NPU-R20-s2.0-l0.5'
COND_B_TWIN = 'NPU-R20-s2.0-l0.2'
COND_B_NEXT = 'NPU-R0-s1.5-l0.2'


def _sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def run_pol(cid, seed, spec):
    return RE.run_one(MODEL, RE.COND[cid], seed, spec)


def metrics(r):
    return dict(max_skin=r['thermal']['max_skin'], end_skin=r['thermal']['end_skin'], bg_last_completion=r['completion']['bg_last_completion'],
                bg_completed_inf=r['bg']['completed_inf'], t38_s=r['thermal']['t38_s'], t40_s=r['thermal']['t40_s'],
                throttle_s=r['thermal']['throttle_s'], guard_a=r['guard_a'])


def cmd_of(r):
    return {str(k): int(v) for k, v in (r.get('duty_cmd') or {}).items()}


def cmp_metrics(new, ref):
    out, ok = {}, True
    for k, tol in (('max_skin', TOL_C), ('end_skin', TOL_C), ('bg_last_completion', TOL_S)):
        a, b = new.get(k), ref.get(k)
        good = a is not None and b is not None and abs(a - b) <= tol
        out[k] = dict(recomputed=a, reference=b, diff=None if (a is None or b is None) else a - b, tol=tol, ok=good)
        ok &= good
    if 'bg_completed_inf' in ref:
        good = new['bg_completed_inf'] == ref['bg_completed_inf']
        out['bg_completed_inf'] = dict(recomputed=new['bg_completed_inf'], reference=ref['bg_completed_inf'], ok=good)
        ok &= good
    return out, ok


def grid(cmd, horizon):
    """Commanded duty per 10 s cell over [0, window] (0 = no BG in that cell) and the cell lengths (last one clipped)."""
    win = min(horizon, MAX_WIN)
    total = int(math.ceil(win - 1e-9))
    n = int(math.ceil(total / 10.0 - 1e-9))
    cells, lens = [], []
    for k in range(n):
        cells.append(int(cmd.get(str(k), 0)))
        lens.append(min(10, total - 10 * k))
    beyond = sorted(int(k) for k in cmd if int(k) >= n)
    return dict(window_s=win, sigma_s=total, n_cells=n, duty=cells, cell_len_s=lens, cmd_cells_beyond_window=beyond)


def rep_seed(rows, cid, strongest):
    diffs = {}
    for s in RE.HOLDOUT_SEEDS:
        o = next(r for r in rows if r['cond'] == cid and r['seed'] == s and r['key'] == OURS_KEY)
        b = next(r for r in rows if r['cond'] == cid and r['seed'] == s and r['key'] == strongest)
        diffs[s] = o['thermal']['max_skin'] - b['thermal']['max_skin']
    mdn = statistics.median(diffs.values())
    rep = min(diffs, key=lambda s: (abs(diffs[s] - mdn), s))
    return rep, diffs, mdn


def load_hold(conds):
    out = []
    with open(HOLD, encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get('model') == MODEL and r.get('cond') in conds and r.get('key') in (OURS_KEY, BASE_KEY, 'npumgr'):
                out.append(r)
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    cand = json.load(open(CAND, encoding='utf-8'))
    hold = load_hold({COND_A, COND_A_TWIN, COND_B, COND_B_TWIN, COND_B_NEXT})
    summ = json.load(open(os.path.join(ROOT, 'd1sim', 'out', 'policy_eval_v2', 'holdout_summary.json'), encoding='utf-8'))
    T = summ['tables'][MODEL]
    res = dict(kind='v3_timelines_1006', registration='d1sim/docs/V3_사전등록_v1.md (036f87b)', model=MODEL, ours=OURS_KEY,
               frozen_manifest_sha256=_sha(FROZEN), candidates_sha256=_sha(CAND), holdout_rows_sha256=_sha(HOLD),
               policies_sha256=_sha(os.path.join(ROOT, 'd1sim', 'policy_eval_v2', 'policies.py')),
               decisions=__doc__.split('P1g 가 정함 (결과 전 — 폰 V3 칸 0):')[1].strip(), conditions={}, checks={})
    all_ok = True

    # ---------------- A
    cA = next(c for c in cand['candidates'] if c['condition'] == COND_A)
    seedA = cA['representative_seed']
    A = {}
    for spec, key in (((BASE_KEY,), BASE_KEY), (OURS, OURS_KEY)):
        r = run_pol(COND_A, seedA, spec)
        ref_c = cA['timelines_10s'][key]
        ref_h = next(x for x in hold if x['cond'] == COND_A and x['seed'] == seedA and x['key'] == key)
        m = metrics(r)
        c1, ok1 = cmp_metrics(m, dict(max_skin=ref_c['max_skin'], bg_completed_inf=ref_c['bg_completed_inf'],
                                      end_skin=ref_h['thermal']['end_skin'], bg_last_completion=ref_h['completion']['bg_last_completion']))
        cmd_same = cmd_of(r) == {str(k): int(v) for k, v in ref_c['duty_cmd'].items()}
        A[key] = dict(metrics=m, check_vs_candidates=c1, cmd_identical_to_candidates=cmd_same, duty_cmd=cmd_of(r),
                      duty_real_pct=r['duty_real'], bursts=r['bursts'], grid=grid(cmd_of(r), cA['horizon_s']))
        all_ok &= ok1 and cmd_same
    twinA = {}
    for spec, key in (((BASE_KEY,), BASE_KEY), (OURS, OURS_KEY)):
        r = run_pol(COND_A_TWIN, seedA, spec)
        twinA[key] = dict(cmd_identical=cmd_of(r) == A[key]['duty_cmd'], max_skin=r['thermal']['max_skin'])
    res['conditions']['A'] = dict(condition=COND_A, seed=seedA, horizon_s=cA['horizon_s'], burst_starts_s=cA['burst_starts_s'],
                                  delta_holdout_c=cA['delta_c'], strongest=cA['strongest'], policies=A,
                                  twin=dict(condition=COND_A_TWIN, seed=seedA, policies=twinA,
                                            same_timeline=all(v['cmd_identical'] for v in twinA.values())),
                                  work_ratio_ours_over_base=A[OURS_KEY]['metrics']['bg_completed_inf'] / A[BASE_KEY]['metrics']['bg_completed_inf'])

    # ---------------- B
    stB = T[COND_B]['strongest']
    seedB, diffsB, mdnB = rep_seed(hold, COND_B, stB)
    hB = RE.scenario(RE.COND[COND_B], seedB)
    B = {}
    for spec, key in (((BASE_KEY,), BASE_KEY), (OURS, OURS_KEY)):
        r = run_pol(COND_B, seedB, spec)
        ref_h = next(x for x in hold if x['cond'] == COND_B and x['seed'] == seedB and x['key'] == key)
        m = metrics(r)
        c1, ok1 = cmp_metrics(m, dict(max_skin=ref_h['thermal']['max_skin'], end_skin=ref_h['thermal']['end_skin'],
                                      bg_last_completion=ref_h['completion']['bg_last_completion'], bg_completed_inf=ref_h['bg']['completed_inf']))
        cmd_same = cmd_of(r) == cmd_of(ref_h)
        B[key] = dict(metrics=m, check_vs_holdout_rows=c1, cmd_identical_to_holdout_row=cmd_same, duty_cmd=cmd_of(r),
                      duty_real_pct=r['duty_real'], bursts=r['bursts'], grid=grid(cmd_of(r), hB['horizon_s']))
        all_ok &= ok1 and cmd_same
    twinB = {}
    for spec, key in (((BASE_KEY,), BASE_KEY), (OURS, OURS_KEY)):
        r = run_pol(COND_B_TWIN, seedB, spec)
        twinB[key] = dict(cmd_identical=cmd_of(r) == B[key]['duty_cmd'], max_skin=r['thermal']['max_skin'])
    seedB2, _, _ = rep_seed(hold, COND_B_TWIN, T[COND_B_TWIN]['strongest'])
    sameAB = {k: B[k]['duty_cmd'] == A[k]['duty_cmd'] for k in (BASE_KEY, OURS_KEY)}
    res['conditions']['B'] = dict(condition=COND_B, seed=seedB, seed_rule='run_eval.v3_candidates rule (ours − strongest closest to median, tie smaller)',
                                  seed_diffs_ours_minus_strongest=diffsB, median_diff=mdnB, strongest=stB,
                                  horizon_s=hB['horizon_s'], burst_starts_s=hB['burst_starts_s'], delta_holdout_c=T[COND_B]['j2']['delta'],
                                  policies=B,
                                  twin=dict(condition=COND_B_TWIN, seed=seedB, policies=twinB, same_timeline=all(v['cmd_identical'] for v in twinB.values()),
                                            twin_own_representative_seed=seedB2),
                                  same_as_A=dict(per_policy=sameAB, same=all(sameAB.values())),
                                  work_ratio_ours_over_base=B[OURS_KEY]['metrics']['bg_completed_inf'] / B[BASE_KEY]['metrics']['bg_completed_inf'])
    res['checks'] = dict(all_section_2_1_ok=all_ok,
                         A_twin_same_timeline=res['conditions']['A']['twin']['same_timeline'],
                         B_twin_same_timeline=res['conditions']['B']['twin']['same_timeline'],
                         B_same_as_A=res['conditions']['B']['same_as_A']['same'])
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, 'timelines.json')
    json.dump(res, open(p, 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    print(json.dumps(res['checks'], ensure_ascii=False))
    for c in ('A', 'B'):
        C = res['conditions'][c]
        print(c, C['condition'], 'seed', C['seed'], 'horizon', round(C['horizon_s'], 3), 'Δhold', C['delta_holdout_c'])
        for k, v in C['policies'].items():
            chk = v.get('check_vs_candidates') or v.get('check_vs_holdout_rows')
            print('  ', k, {kk: (round(vv['diff'], 6) if vv.get('diff') is not None else vv['ok']) for kk, vv in chk.items()},
                  'cmd same', v.get('cmd_identical_to_candidates', v.get('cmd_identical_to_holdout_row')),
                  'Σ', v['grid']['sigma_s'], 'beyond', v['grid']['cmd_cells_beyond_window'])
    print('->', p)
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
