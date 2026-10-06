"""run_eval.py — runner for the policy comparison v2 (sim/정책비교_사전등록_v2.md, commit 582009e).

  py -m d1sim.policy_eval_v2.run_eval selftest                       # §11 selftest (must be all PASS before anything else)
  py -m d1sim.policy_eval_v2.run_eval manifest                       # d1sim/out/policy_eval_freeze_v2.json (before development seeds)
  py -m d1sim.policy_eval_v2.run_eval timing                         # §12: 1 condition (NPU · s1.5 · λ0.2 · R0 · seed 1), policies 1~5
  py -m d1sim.policy_eval_v2.run_eval dev [--workers N] [--reduce K] # development seeds 1–10 -> ① · ours tuning (+ sensitivity 1~4)
  py -m d1sim.policy_eval_v2.run_eval freeze                         # _frozen manifest (ours setting + policy SHA) — before the holdout
  py -m d1sim.policy_eval_v2.run_eval holdout [--workers N] [--reduce K]   # holdout seeds 51–60, ONCE, frozen policies -> ②
Deterministic (seeded workload, no other RNG except pace-perm's random.Random(seed + 1000)); parallel over processes only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from d1sim import workload_reg1 as wl  # noqa: E402
from d1sim.policy_eval_v2 import judge_v2 as J  # noqa: E402
from d1sim.policy_eval_v2 import kpi_v2  # noqa: E402
from d1sim.policy_eval_v2 import policies as P  # noqa: E402
from d1sim.policy_eval_v2.sim import R0, SimReg  # noqa: E402

OUT = os.path.join(ROOT, 'd1sim', 'out', 'policy_eval_v2')
MANIFEST = os.path.join(ROOT, 'd1sim', 'out', 'policy_eval_freeze_v2.json')
MANIFEST_FROZEN = os.path.join(ROOT, 'd1sim', 'out', 'policy_eval_freeze_v2_frozen.json')
REG = os.path.join(ROOT, 'd1sim', 'docs', '정책비교_사전등록_v2.md')
REG_COMMIT = '582009e8e961ab10e5278e49113e1e429e3d3602'
MAIN_MODEL = 'v22'
SENS_MODELS = ('v21', 'v2_t0.3', 'v2_t0.75')
DEV_SEEDS = tuple(wl.DEV_SEEDS)
HOLDOUT_SEEDS = tuple(wl.HOLDOUT_SEEDS)
BASIC = (('fixed-prio',), ('npumgr',), ('pace-d50',))
TIMING_COND = 'NPU-R0-s1.5-l0.2'
SLACKS = (1.0, 1.5, 2.0, 3.0)
LAMS = (0.2, 0.5)


def conditions():
    out = []
    for res in ('NPU', 'GPU'):
        for residue in (('R0', 'R20') if res == 'NPU' else ('R0',)):
            for s in SLACKS:
                for lam in LAMS:
                    out.append(dict(id=f'{res}-{residue}-s{s}-l{lam}', res=res, residue=residue, slack=s, lam=lam))
    return out


COND = {c['id']: c for c in conditions()}


def scenario(cond, seed):
    return wl.scenario_reg1(seed, cond['slack'], cond['lam'], R0[cond['res']], model='efficientnet_lite0')


def spec_key(spec):
    if spec[0] == 'ours':
        return f'ours(m{spec[1]:g},o{spec[2]:g})'
    if spec[0] == 'ref-const':
        return 'ref-const-' + '-'.join(str(d) for d in spec[1])
    return spec[0]


def run_one(model, cond, seed, spec, compact=False, sc=None):
    sc = sc or scenario(cond, seed)
    sim = SimReg(cond['res'], model, sc['requests'], sc['horizon_s'], residue=cond['residue'])
    pol = P.make_policy(spec, cond['res'], cond['lam'])
    t0 = time.perf_counter()
    rec = sim.run(pol)
    row = kpi_v2.summarize(sim, rec, pol)
    row.update(cond=cond['id'], seed=seed, model=model, key=spec_key(spec), kind=spec[0], wall_s=time.perf_counter() - t0)
    if spec[0] == 'ours':
        row['ours_log'] = {str(k): list(v) for k, v in pol.log.items()}
        row['ours_stats'] = dict(n_forward=pol.n_forward, n_stepdown=pol.n_stepdown, n_none=pol.n_none, margin_s=pol.margin, offset_c=pol.offset)
    if compact:
        for k in ('duty_real', 'duty_cmd', 'bursts'):
            row.pop(k, None)
    return row


def _error_row(model, cid, seed, spec, e):
    """v1 §5-4: a simulator exception is kept as a row and treated like a conservation failure (condition not judged)."""
    return dict(cond=cid, seed=seed, model=model, key=spec_key(spec), kind=spec[0], policy=spec_key(spec), error=repr(e),
                conservation_ok=False, conservation=['exception'], guard_a=False,
                fg=dict(p95_all=None, late=0, unfinished=0, planned=0), bg=dict(on_time_rate=None, unfinished=0, late=0, planned=0),
                thermal=dict(max_skin=None, end_skin=None, t38_s=None, t40_s=None, t42_s=None, throttle_s=None, throughput_inf_s=None),
                completion=dict(bg_last_completion=None, bursts_s=[]), duty_cmd_mean=None)


def _safe(model, cond, seed, spec, **kw):
    try:
        return run_one(model, cond, seed, spec, **kw)
    except Exception as e:  # noqa: BLE001
        return _error_row(model, cond['id'], seed, spec, e)


def job_basic(args):
    model, cid, seed, specs = args
    cond = COND[cid]
    sc = scenario(cond, seed)
    rows = []
    for spec in specs:
        rows.append(_safe(model, cond, seed, spec, sc=sc))
    return rows


def job_ours_perm(args):
    """ours (one setting) then pace-perm built from that ours' commanded duties (same seed · model)."""
    model, cid, seed, setting, with_perm = args
    cond = COND[cid]
    sc = scenario(cond, seed)
    o = _safe(model, cond, seed, ('ours',) + tuple(setting), sc=sc)
    rows = [o]
    if with_perm:
        if 'error' in o:
            rows.append(_error_row(model, cid, seed, ('pace-perm', {}), RuntimeError('ours failed')))
            return rows
        log = {int(k): tuple(v) for k, v in o['ours_log'].items()}
        sched = P.perm_schedule(log, seed)
        pr = _safe(model, cond, seed, ('pace-perm', sched), sc=sc)
        pr['perm_multiset_equal'] = sorted(v for v in sched.values()) == sorted(d for d, _ in log.values())
        rows.append(pr)
    return rows


def job_ref(args):
    model, cid, seed, combos = args
    cond = COND[cid]
    sc = scenario(cond, seed)
    return [_safe(model, cond, seed, ('ref-const', c), compact=True, sc=sc) for c in combos]


def ref_select(combo_rows, fixed_row, m):
    """Per seed (P1f 가 정함 (결과 전)): (a) this run · (b) vs fixed-prio of the SAME seed with the condition's dev margins ->
    among passing combos the lowest max SKIN · tie (exact) -> smaller duty sum -> lexicographic. None pass -> flagged min-max-SKIN row."""
    base = dict(fg_p95=fixed_row['fg']['p95_all'], bg_on_rate=fixed_row['bg']['on_time_rate'])

    def ok(r):
        gb, _ = J.guard_b(dict(fg_p95=r['fg']['p95_all'], bg_on_rate=r['bg']['on_time_rate']), base, m)
        return r['guard_a'] and gb

    key = lambda r: (r['thermal']['max_skin'], sum(int(x) for x in r['key'].split('-')[2:]), r['key'])  # noqa: E731
    passing = [r for r in combo_rows if ok(r)]
    if passing:
        best = min(passing, key=key)
        return dict(best, ref_feasible=True, ref_n_passing=len(passing))
    best = min(combo_rows, key=key)
    return dict(best, ref_feasible=False, ref_n_passing=0, guard_a=False)


def run_pool(fn, jobs, workers):
    out = []
    if workers <= 1:
        for j in jobs:
            out.append(fn(j))
        return out
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(fn, jobs, chunksize=1):
            out.append(r)
    return out


def _flat(lists):
    return [r for lst in lists for r in lst]


def _sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def _rel(p):
    return os.path.relpath(p, ROOT).replace('\\', '/')


def dump_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str, sort_keys=True) + '\n')


def load_jsonl(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(x) for x in f if x.strip()]


# ============================================================ aggregation
def by(rows, *keys):
    out = {}
    for r in rows:
        out.setdefault(tuple(r[k] for k in keys), []).append(r)
    return out


def condition_table(rows, model, seeds, margins_by_cond, ours_key=None):
    """{cond: {stats per policy key, strongest, ①, ② (if ours_key), norm diff}} for one model."""
    out = {}
    g = by([r for r in rows if r['model'] == model and r['seed'] in seeds], 'cond')
    for (cid,), rr in sorted(g.items()):
        pk = by(rr, 'key')
        S = {k[0]: J.policy_stats(v) for k, v in pk.items()}
        ref = [r for r in rr if r['kind'] == 'ref-const']
        if ref:
            S['ref-const'] = J.policy_stats(ref)
            for k in list(S):
                if k.startswith('ref-const-'):
                    S.pop(k)
        m = margins_by_cond[cid]
        if ours_key and ours_key in S:
            S['ours'] = S[ours_key]
        bad = [f"{r['key']} s{r['seed']}" for r in rr if not r.get('conservation_ok', False)]
        if bad:      # v1 §5-4: conservation failure / exception -> keep the rows, do not judge the condition
            e = dict(stats={k: dict(n=v['n']) for k, v in S.items()}, margins=m, strongest=None, conservation_fail=bad[:10],
                     j1=dict(label='보존 실패 — 판정 안 함', delta=None))
            if ours_key:
                e['j2'] = dict(label='보존 실패 — 판정 안 함', delta=None, take=False)
            out[cid] = e
            continue
        S = J.guards(S, m)
        st = J.strongest_baseline(S)
        e = dict(stats=S, margins=m, strongest=st, j1=J.judge_1(S, st) if 'ref-const' in S else None)
        if ours_key and 'ours' in S:
            e['j2'] = J.judge_2(S, st)
            e['norm_diff'] = J.norm_diff(S, st)
            e['window_flag_ours'] = J.window_flag(S['ours'], S[st]) if st else None
        out[cid] = e
    return out


def v3_candidates(hold_rows, hold_tables, sel_key, out_dir):
    """등록 v2 §9-2 / v1 §9-1 (P1f 가 정함 (결과 전) 세부): among ② 가져옴 conditions (main model) the 1~2 with the largest Δ (strongest
    baseline − ours, seed medians) — up to 2; tie -> NPU first -> smaller slack -> smaller λ -> condition id. Representative seed = the
    seed whose (ours − strongest) max-SKIN difference is closest to the condition median of that difference (tie -> smaller seed).
    Writes the 24-condition ② table (selection history), the picks + reasons, and both policies' BG duty timelines (10 s grid)."""
    os.makedirs(out_dir, exist_ok=True)
    T = hold_tables[MAIN_MODEL]
    table = {cid: dict(j2=e.get('j2'), strongest=e.get('strongest'), norm_diff=e.get('norm_diff')) for cid, e in T.items()}
    takes = [cid for cid, e in T.items() if e.get('j2', {}).get('take')]
    rank = sorted(takes, key=lambda c: (-T[c]['j2']['delta'], COND[c]['res'] != 'NPU', COND[c]['slack'], COND[c]['lam'], c))
    picks = rank[:2]
    out = dict(rule=v3_candidates.__doc__, n_take=len(takes), ranked=rank, picks=picks, table_24=table, candidates=[])
    for cid in picks:
        st = T[cid]['strongest']
        rows = [r for r in hold_rows if r['model'] == MAIN_MODEL and r['cond'] == cid]
        diffs = {}
        for s in HOLDOUT_SEEDS:
            o = next(r for r in rows if r['seed'] == s and r['key'] == sel_key)
            b = next(r for r in rows if r['seed'] == s and r['key'] == st)
            diffs[s] = o['thermal']['max_skin'] - b['thermal']['max_skin']
        mdn = statistics.median(diffs.values())
        rep = min(diffs, key=lambda s: (abs(diffs[s] - mdn), s))
        tl = {}
        for k in (st, sel_key):
            r = next(x for x in rows if x['seed'] == rep and x['key'] == k)
            tl[k] = dict(duty_cmd=r.get('duty_cmd'), duty_real_pct=r.get('duty_real'), max_skin=r['thermal']['max_skin'],
                         bg_completed_inf=r['bg']['completed_inf'], bursts=r.get('bursts'))
        sc = scenario(COND[cid], rep)
        out['candidates'].append(dict(condition=cid, delta_c=T[cid]['j2']['delta'], strongest=st, representative_seed=rep,
                                      seed_diffs_ours_minus_strongest=diffs, median_diff=mdn, horizon_s=sc['horizon_s'],
                                      burst_starts_s=sc['burst_starts_s'], timelines_10s=tl,
                                      work_ratio_ours_over_strongest=(tl[sel_key]['bg_completed_inf'] / tl[st]['bg_completed_inf'])
                                      if tl[st]['bg_completed_inf'] else None))
    json.dump(out, open(os.path.join(out_dir, 'v3_candidates.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    return out


def tuning_select(dev_rows, margins_by_cond):
    """ours tuning on development seeds, main model (등록 v1 §4 rule; fallback P1f 가 정함 (결과 전) — manifest 'tuning_rule')."""
    table = {}
    for setting in P.OURS_GRID:
        key = spec_key(('ours',) + setting)
        per = {}
        for cid in COND:
            rr = [r for r in dev_rows if r['model'] == MAIN_MODEL and r['cond'] == cid and r['key'] in (key, 'fixed-prio', 'npumgr')]
            S = {k[0]: J.policy_stats(v) for k, v in by(rr, 'key').items()}
            S = J.guards(S, margins_by_cond[cid])
            st = J.strongest_baseline(S)
            o = S[key]
            per[cid] = dict(guard=o['guard'], guard_a=o['guard_a'], max_skin=o['max_skin'], strongest=st,
                            delta=(S[st]['max_skin'] - o['max_skin']) if st else None)
        n_pass = sum(1 for v in per.values() if v['guard'])
        mean_max = statistics.mean(v['max_skin'] for v in per.values())
        sum_delta = sum(v['delta'] for v in per.values() if v['delta'] is not None)
        table[key] = dict(setting=setting, n_guard_pass=n_pass, all_pass=n_pass == len(COND), mean_max_skin=mean_max,
                          sum_delta_vs_strongest=sum_delta, per_cond=per)
    allp = [k for k, v in table.items() if v['all_pass']]
    if allp:
        pick = min(allp, key=lambda k: (round(table[k]['mean_max_skin'], 9), table[k]['setting'][0], table[k]['setting'][1] != 0.0))
        rule = 'step 1 (등록 v1 §4): 24 개발 조건 전부 가드 (a)(b) 통과 설정 중 조건별 seed 중앙 최고 SKIN 평균 최저 → 동률 margin 작은 쪽 → offset 0'
    else:
        pick = max(table, key=lambda k: (table[k]['n_guard_pass'], round(table[k]['sum_delta_vs_strongest'], 9),
                                         table[k]['setting'] == (0.0, 0.0), -table[k]['setting'][0], table[k]['setting'][1] == 0.0))
        rule = ('step 2 (P1f 가 정함 (결과 전), 프롬프트 6단계): step 1 해당 없음 → 가드 (a)(b) 통과 조건 수 최다 → 동률이면 개발 seed 중앙 '
                '최고 SKIN Δ (가장 강한 기준선 − ours) 합 최대 → 동률이면 margin 0 · offset 0 (→ margin 작은 쪽 → offset 0)')
    return dict(table=table, selected=pick, selected_setting=table[pick]['setting'], rule=rule)


# ============================================================ commands
def cmd_timing(a):
    cond = COND[TIMING_COND]
    seed = 1
    sc = scenario(cond, seed)
    res = {}
    t0 = time.perf_counter()
    for spec in BASIC + (('ours', 0.0, 0.0),):
        r = run_one(MAIN_MODEL, cond, seed, spec, sc=sc)
        res[r['key']] = r['wall_s']
    o = run_one(MAIN_MODEL, cond, seed, ('ours', 0.0, 0.0), sc=sc)
    sched = P.perm_schedule({int(k): tuple(v) for k, v in o['ours_log'].items()}, seed)
    r = run_one(MAIN_MODEL, cond, seed, ('pace-perm', sched), sc=sc)
    res['pace-perm'] = r['wall_s']
    ts = time.perf_counter()
    rr = [run_one(MAIN_MODEL, cond, seed, ('ref-const', c), compact=True, sc=sc) for c in P.REF_COMBOS]
    res['ref-const x125'] = time.perf_counter() - ts
    res['ref-const per combo'] = res['ref-const x125'] / len(P.REF_COMBOS)
    res['total_one_condition_s'] = time.perf_counter() - t0
    # extrapolation (§12) — NPU timing used for every condition (GPU runs have ~4x fewer chunks: conservative)
    n_cond, n_dev, n_hold = len(COND), len(DEV_SEEDS), len(HOLDOUT_SEEDS)
    one_basic = res['fixed-prio'] + res['npumgr'] + res['pace-d50']
    ours = res['ours(m0,o0)']
    dev_main = n_cond * n_dev * (one_basic + 6 * ours + res['pace-perm'] + res['ref-const x125'])
    dev_sens = 3 * n_cond * n_dev * (one_basic + ours + res['pace-perm'])
    hold_main = n_cond * n_hold * (one_basic + ours + res['pace-perm'] + res['ref-const x125'])
    hold_sens = 3 * n_cond * n_hold * (one_basic + ours + res['pace-perm'])
    serial = dev_main + dev_sens + hold_main + hold_sens
    workers = max(1, (os.cpu_count() or 2) - 2)
    est = dict(serial_total_h=serial / 3600, dev_main_h=dev_main / 3600, dev_sens_h=dev_sens / 3600, hold_main_h=hold_main / 3600,
               hold_sens_h=hold_sens / 3600, workers=workers, parallel_total_h=serial / 3600 / workers,
               ref_const_share=(n_cond * (n_dev + n_hold) * res['ref-const x125']) / serial)
    out = dict(condition=TIMING_COND, seed=seed, model=MAIN_MODEL, wall_s=res, estimate=est, cpu_count=os.cpu_count(),
               ref_feasible_combos=sum(1 for x in rr if x['guard_a']), rule='등록 §12: > 6 h 면 ① 병렬 → ② ref-const 주 모형만 → ③ 홀드아웃 ref-const 는 가져옴 후보만 → ④ ref-const-27')
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(os.path.join(OUT, 'timing.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    return 0


def _margins_from(rows):
    out = {}
    for cid in COND:
        base = [r for r in rows if r['cond'] == cid and r['key'] == 'fixed-prio' and r['model'] == MAIN_MODEL and r['seed'] in DEV_SEEDS]
        out[cid] = J.margins(sorted(base, key=lambda r: r['seed']))
    return out


def cmd_dev(a):
    os.makedirs(OUT, exist_ok=True)
    t0 = time.perf_counter()
    W = a.workers
    combos = P.REF_COMBOS if a.reduce < 4 else tuple((x, y, z) for x in (10, 50, 100) for y in (10, 50, 100) for z in (10, 50, 100))
    jobs = [(MAIN_MODEL, cid, s, BASIC) for cid in COND for s in DEV_SEEDS]
    rows = _flat(run_pool(job_basic, jobs, W))
    print('basic main', len(rows), f'{time.perf_counter() - t0:.0f}s', flush=True)
    margins = _margins_from(rows)
    jobs = [(MAIN_MODEL, cid, s, st, False) for cid in COND for s in DEV_SEEDS for st in P.OURS_GRID]
    rows += _flat(run_pool(job_ours_perm, jobs, W))
    print('ours x6 main', len(rows), f'{time.perf_counter() - t0:.0f}s', flush=True)
    jobs = [(MAIN_MODEL, cid, s, combos) for cid in COND for s in DEV_SEEDS]
    refrows = _flat(run_pool(job_ref, jobs, W))
    print('ref-const main', len(refrows), f'{time.perf_counter() - t0:.0f}s', flush=True)
    fixed = {(r['cond'], r['seed']): r for r in rows if r['key'] == 'fixed-prio'}
    chosen = []
    for (cid, s), rr in sorted(by(refrows, 'cond', 'seed').items()):
        c = ref_select(rr, fixed[(cid, s)], margins[cid])
        chosen.append(dict(c, kind='ref-const'))
    dump_jsonl(os.path.join(OUT, 'dev_refconst_all.jsonl'), refrows)
    rows += chosen
    tune = tuning_select(rows, margins)
    sel = tune['selected_setting']
    print('tuning selected', tune['selected'], tune['rule'][:40], flush=True)
    jobs = [(MAIN_MODEL, cid, s, sel, True) for cid in COND for s in DEV_SEEDS]
    perm = _flat(run_pool(job_ours_perm, jobs, W))
    rows += [r for r in perm if r['kind'] == 'pace-perm']
    print('pace-perm main', f'{time.perf_counter() - t0:.0f}s', flush=True)
    # sensitivity models: policies 1~4 only (프롬프트 6단계 · 등록 v2 §7) — ours = the setting selected above
    jobs = [(m, cid, s, BASIC) for m in SENS_MODELS for cid in COND for s in DEV_SEEDS]
    rows += _flat(run_pool(job_basic, jobs, W))
    jobs = [(m, cid, s, sel, True) for m in SENS_MODELS for cid in COND for s in DEV_SEEDS]
    rows += _flat(run_pool(job_ours_perm, jobs, W))
    print('sensitivity', f'{time.perf_counter() - t0:.0f}s', flush=True)
    dump_jsonl(os.path.join(OUT, 'dev_rows.jsonl'), rows)
    sel_key = spec_key(('ours',) + tuple(sel))
    tables = {MAIN_MODEL: condition_table(rows, MAIN_MODEL, DEV_SEEDS, margins, ours_key=sel_key)}
    for m in SENS_MODELS:
        tables[m] = condition_table(rows, m, DEV_SEEDS, margins, ours_key=sel_key)
    summ = dict(stage='development seeds 1–10 — 확인 아님', margins=margins, tuning=tune, tables=tables,
                j1={cid: e['j1'] for cid, e in tables[MAIN_MODEL].items()},
                reduce_step=a.reduce, ref_combos=len(combos), wall_s=time.perf_counter() - t0,
                conservation_fail=sum(1 for r in rows + refrows if not r['conservation_ok']))
    json.dump(summ, open(os.path.join(OUT, 'dev_summary.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    print('dev done', f'{time.perf_counter() - t0:.0f}s', 'conservation fails', summ['conservation_fail'])
    return 0


def cmd_holdout(a):
    fr = json.load(open(MANIFEST_FROZEN, encoding='utf-8'))
    pol_sha = _sha(os.path.join(ROOT, 'd1sim', 'policy_eval_v2', 'policies.py'))
    if fr['frozen']['policies_sha256'] != pol_sha:
        raise SystemExit('policies.py changed after the freeze — refuse (새 판 필요)')
    if os.path.exists(os.path.join(OUT, 'holdout_rows.jsonl')):
        raise SystemExit('holdout already run once — refuse (등록 §6: 1회)')
    sel = tuple(fr['frozen']['ours_setting'])
    margins = {k: v for k, v in fr['frozen']['margins'].items()}
    W = a.workers
    t0 = time.perf_counter()
    rows = _flat(run_pool(job_basic, [(MAIN_MODEL, cid, s, BASIC) for cid in COND for s in HOLDOUT_SEEDS], W))
    rows += _flat(run_pool(job_ours_perm, [(MAIN_MODEL, cid, s, sel, True) for cid in COND for s in HOLDOUT_SEEDS], W))
    print('main 1~4', f'{time.perf_counter() - t0:.0f}s', flush=True)
    sel_key = spec_key(('ours',) + sel)
    pre = condition_table(rows, MAIN_MODEL, HOLDOUT_SEEDS, margins, ours_key=sel_key)
    ref_conds = list(COND) if a.reduce < 3 else [cid for cid, e in pre.items() if e['j2']['take']]
    combos = P.REF_COMBOS if a.reduce < 4 else tuple((x, y, z) for x in (10, 50, 100) for y in (10, 50, 100) for z in (10, 50, 100))
    refrows = _flat(run_pool(job_ref, [(MAIN_MODEL, cid, s, combos) for cid in ref_conds for s in HOLDOUT_SEEDS], W))
    fixed = {(r['cond'], r['seed']): r for r in rows if r['key'] == 'fixed-prio'}
    for (cid, s), rr in sorted(by(refrows, 'cond', 'seed').items()):
        rows.append(dict(ref_select(rr, fixed[(cid, s)], margins[cid]), kind='ref-const'))
    print('ref-const', len(refrows), f'{time.perf_counter() - t0:.0f}s', flush=True)
    rows += _flat(run_pool(job_basic, [(m, cid, s, BASIC) for m in SENS_MODELS for cid in COND for s in HOLDOUT_SEEDS], W))
    rows += _flat(run_pool(job_ours_perm, [(m, cid, s, sel, True) for m in SENS_MODELS for cid in COND for s in HOLDOUT_SEEDS], W))
    dump_jsonl(os.path.join(OUT, 'holdout_rows.jsonl'), rows)
    dump_jsonl(os.path.join(OUT, 'holdout_refconst_all.jsonl'), refrows)
    tables = {m: condition_table(rows, m, HOLDOUT_SEEDS, margins, ours_key=sel_key) for m in (MAIN_MODEL,) + SENS_MODELS}
    dev = json.load(open(os.path.join(OUT, 'dev_summary.json'), encoding='utf-8'))
    takes = [e['j2']['take'] for e in tables[MAIN_MODEL].values()]
    row_main = J.conclusion_row([v['label'] for v in dev['j1'].values() if v], takes)
    rows_sens = {m: J.conclusion_row([v['label'] for v in dev['j1'].values() if v], [e['j2']['take'] for e in tables[m].values()]) for m in SENS_MODELS}
    v3 = v3_candidates(rows, tables, sel_key, os.path.join(ROOT, 'd1sim', 'out', 'v3_candidates_1006'))
    summ = dict(stage='holdout seeds 51–60 (1회, 정책 동결 뒤)', frozen_manifest_sha256=_sha(MANIFEST_FROZEN), ours_setting=sel,
                v3_picks=v3['picks'], v3_n_take=v3['n_take'],
                tables=tables, j2={cid: e['j2'] for cid, e in tables[MAIN_MODEL].items()},
                n_take=sum(takes), conclusion_row_main=row_main, conclusion_row_sensitivity=rows_sens,
                reduce_step=a.reduce, ref_conditions=ref_conds, wall_s=time.perf_counter() - t0,
                conservation_fail=sum(1 for r in rows + refrows if not r['conservation_ok']))
    json.dump(summ, open(os.path.join(OUT, 'holdout_summary.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    print('holdout done', f'{time.perf_counter() - t0:.0f}s', 'take', sum(takes), row_main)
    return 0


FILES = {
    'registration': 'd1sim/docs/정책비교_사전등록_v2.md',
    'registration_v1': 'd1sim/docs/정책비교_사전등록_v1.md',
    'generator': 'd1sim/workload_reg1.py',
    'policies': 'd1sim/policy_eval_v2/policies.py',
    'npumgr_source': 'd1sim/policies.py',
    'adapter_sim': 'd1sim/policy_eval_v2/sim.py',
    'env_v0': 'd1sim/env.py',
    'env_v2_params': 'd1sim/env_v2.py',
    'kpi': 'd1sim/policy_eval_v2/kpi_v2.py',
    'kpi_conservation': 'd1sim/kpi.py',
    'judge': 'd1sim/policy_eval_v2/judge_v2.py',
    'runner': 'd1sim/policy_eval_v2/run_eval.py',
    'selftest': 'd1sim/policy_eval_v2/selftest.py',
    'model_v22_py': 'd1sim/throttle_v22.py',
    'model_v21_py': 'd1sim/throttle_v21.py',
    'model_v2_py': 'd1sim/throttle_v2.py',
    'model_v1_py': 'd1sim/throttle_v1.py',
    'profile_yaml': 'd1sim/profiles/device_profile_S26.yaml',
}
PROFILE_GLOBS = ('throttle_v22_', 'throttle_v21_', 'throttle_v2_')

P1F_DECISIONS = [
    'duty 위상: 전역 10 s 주기 (t = 0 부터), on-창 [10k, 10k + d/10 s) 안에서만 BG 청크 시작 · 청크는 끝까지 (비선점) · FG 는 창과 무관하게 먼저',
    'ours: 주기마다 BG 가 있을 때 첫 결정에서 duty 선택 · 기한 = 각 묶음 자기 D_b (FIFO) · 예측기 = 시뮬레이터 장치 복제 (완벽 모형) 1 s 유체 격자 · FG 부하 λ/R0 를 BG 율에서 뺌 · 가능한 d 없으면 100',
    'ours 열 단계: 예측 구동 온도 (모든 모형 SKIN) 10 s 안 최대 ≥ 첫 arm 문턱 (u = d/100, Ht/Lk 는 T + κ(1−u)) + offset → 한 단계 낮춤, 단 낮춘 d 로 D_b (margin 없이) 를 맞출 때만',
    'ours 예측기는 각 모형 실행에서 그 모형 자신 (민감도 실행도 완벽 모형 가정)',
    'pace-perm: ours 의 명령 duty (주기마다 첫 결정 값) 를 묶음별로 순열 (random.Random(seed + 1000), 묶음 순서), ours 가 그 묶음에 쓴 주기 칸에만 재생 · 그 밖 주기 0 (쉼 위치·길이 같음) · 남은 일은 다음 칸·묶음 칸으로 (FIFO) · horizon 에서 남으면 미완료',
    'ref-const: 묶음 b 청크 = combo[b] · seed 마다 고름 — (a) 그 런 + (b) 같은 seed fixed-prio 대비 (조건 개발 seed 의 m_FG · m_BG) 통과 조합 중 최고 SKIN 최저 → 같으면 duty 합 작은 쪽 → 사전순 · 통과 조합 없으면 그 seed ref-const 가드 실패',
    'seed 중앙 = 정책별 seed 중앙값, Δ = 중앙값 차 · 가드 (a) = 모든 seed · 가드 (b) = 중앙값 (+inf 허용) · 홀드아웃 margin = 개발 seed 값',
    '기준선 서비스 부적격 = fixed-prio · npumgr 둘 다 (a) 실패 (fixed-prio 만 실패하면 가장 강한 기준선 = npumgr, 상대 가드 기준은 여전히 fixed-prio)',
    'R20 잔재: "쉰" = BG 실행 없음 ≥ 60 s (FG 단일 추론은 일로 세지 않음; 런 시작 = 쉰 상태) · 그 뒤 BG 시작부터 20 s 벽시계 동안 모든 요청 속도 1/3 · 열 전력은 그대로',
    '자원 하나 — 제어기는 늘 scheduled (tv21.simulate 체인 재생 규칙; env_v2 는 일 없을 때 멈춤)',
    '튜닝 고르기: step 1 = 등록 v1 §4 그대로 (24 조건 전부 가드 통과 설정 중 조건별 seed 중앙 최고 SKIN 평균 최저 → margin 작은 쪽 → offset 0) · step 1 해당 없음 → step 2 = 가드 통과 조건 수 최다 → 개발 seed 중앙 최고 SKIN Δ 합 최대 → margin 0 · offset 0',
    '결론 행 (전체): ② 가져옴 ≥ 1 → "1행 후보 — ③ V3 · ④ 전이 판정 전 (지금은 4행)" · 아니면 ① 차이 있음 ≥ 1 → 2행 · 아니면 3행 · 민감도 모형에서 행이 다르면 "모형 따라 다름"',
    '모델: 프롬프트 6단계 범위 = EffNet (주 모델) 만 — 등록 v2 §1 · §3 의 MobileNet 개발 seed 민감도 (정책 1~4) 는 이 세션에서 돌리지 않는다 (못 한 것으로 보고)',
    '처리 시간: R0 / ratio (EffNet 식은 d100 실행 초당) · 전환 비용 = device_profile_S26.yaml init_s (NPU 0.111 · GPU 0.273 s, npumgr unload 뒤 다시) · FG 는 단일 추론',
    'V3 후보 (§9-2): ② 가져옴 조건 중 Δ 큰 순 최대 2개 (동률 NPU → 여유 s 작은 → λ 작은 → 조건 id) · 대표 seed = (ours − 기준선) 최고 SKIN 차가 조건 중앙값에 가장 가까운 seed (동률 작은 seed) · 타임라인 = 명령 duty + 실현 BG 실행 % (10 s)',
]


def build_manifest(frozen=None):
    import numpy
    import scipy
    import yaml
    files = {k: dict(path=v, sha256=_sha(os.path.join(ROOT, v))) for k, v in FILES.items()}
    prof = {}
    for pre in PROFILE_GLOBS:
        for fn in sorted(os.listdir(os.path.join(ROOT, 'd1sim', 'profiles'))):
            if fn.startswith(pre) and fn.endswith('.json') and not (pre == 'throttle_v2_' and fn.startswith('throttle_v21_')) \
                    and not (pre == 'throttle_v2_' and fn.startswith('throttle_v22_')):
                prof[fn] = _sha(os.path.join(ROOT, 'd1sim', 'profiles', fn))
    m = dict(kind='policy_eval_freeze_v2', created=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
             registration=dict(path=FILES['registration'], sha256=files['registration']['sha256'], commit=REG_COMMIT),
             files=files, profiles=prof,
             models=dict(main=MAIN_MODEL + ' (v2.2 V22-M, e52a922 — g_m on, every run EffNet)', sensitivity=list(SENS_MODELS),
                         adapter='d1sim/policy_eval_v2/sim.py Device (thermal sub-step <= 0.5 s · u 10 s time window · status HAL map)'),
             R0=R0, init_s=__import__('d1sim.policy_eval_v2.sim', fromlist=['INIT_S']).INIT_S,
             grid=dict(conditions=[c['id'] for c in conditions()], slack=SLACKS, lam=LAMS, start_skin=30.5, bursts=3, burst_work_s=300,
                       period_s=900, jitter_s=60, chunk=128, tail_s=300, fg_deadline_s=1.5),
             seeds=dict(dev=list(DEV_SEEDS), holdout=list(HOLDOUT_SEEDS), unused=list(range(61, 66))),
             policies=['1 fixed-prio', '2 npumgr (NpuManagerApprox 무수정)', '3 ours', '4a pace-d50', '4b pace-perm', '5 ref-const (5^3 = 125)'],
             ours_tuning_grid=[list(x) for x in P.OURS_GRID], duties=list(P.DUTIES),
             kpi='§5-1 분모 · §5-2 (a)(b) · §5-3 nearest-rank P95 (+inf) · §5-4 공통 창 열 지표 · §5-5 완료 시간 · 창 끝 SKIN · §5-6 선별 기준',
             judge='①(개발) · ②(홀드아웃) · 가장 강한 기준선 · 참조 정규화 차이 · 결론 행 — judge_v2.py',
             reduction_order_s12=['① 병렬 (코어 − 2)', '② ref-const 주 모형만', '③ 홀드아웃 ref-const 는 가져옴 후보만', '④ ref-const-27'],
             p1f_decisions=P1F_DECISIONS,
             python=platform.python_version(), packages=dict(numpy=numpy.__version__, scipy=scipy.__version__, pyyaml=yaml.__version__),
             platform=platform.platform())
    if frozen:
        m['frozen'] = frozen
    return m


def cmd_manifest(a):
    m = build_manifest()
    json.dump(m, open(MANIFEST, 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    print('wrote', MANIFEST)
    return 0


def cmd_freeze(a):
    dev = json.load(open(os.path.join(OUT, 'dev_summary.json'), encoding='utf-8'))
    sel = dev['tuning']['selected_setting']
    frozen = dict(ours_setting=sel, ours_key=dev['tuning']['selected'], tuning_rule=dev['tuning']['rule'],
                  policies_sha256=_sha(os.path.join(ROOT, 'd1sim', 'policy_eval_v2', 'policies.py')),
                  dev_summary_sha256=_sha(os.path.join(OUT, 'dev_summary.json')),
                  dev_rows_sha256=_sha(os.path.join(OUT, 'dev_rows.jsonl')),
                  base_manifest_sha256=_sha(MANIFEST), margins=dev['margins'])
    m = build_manifest(frozen)
    json.dump(m, open(MANIFEST_FROZEN, 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    print('wrote', MANIFEST_FROZEN, sel)
    return 0


def cmd_selftest(a):
    from d1sim.policy_eval_v2 import selftest
    return selftest.main()


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['selftest', 'manifest', 'timing', 'dev', 'freeze', 'holdout'])
    ap.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument('--reduce', type=int, default=1, help='§12 step reached (1 = parallel only)')
    a = ap.parse_args()
    return {'selftest': cmd_selftest, 'manifest': cmd_manifest, 'timing': cmd_timing, 'dev': cmd_dev, 'freeze': cmd_freeze,
            'holdout': cmd_holdout}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
