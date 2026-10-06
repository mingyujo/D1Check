"""selftest.py — sim/정책비교_사전등록_v2.md §11 boundary selftest (two-way: what must fail fails, what must pass passes).

  py -m d1sim.policy_eval_v2.run_eval selftest     (also run by d1sim/tests/test_policy_eval_v2.py)
Checks: m_FG mean 0 · +inf · null · normal (2 CV) · m_BG sd null · tie < 0.05 ℃ · baseline (a) failure -> 기준선 서비스 부적격 ·
unfinished > 5 % -> P95 +inf (= 5 % finite) · window marker (BG unfinished · end SKIN + 1.0 ℃) · pace-perm same multiset ·
ref-const 125 combos + per-seed selection · guard (b) with +inf · judge ② take / control-lower · duty window · queue view = full
queue for prio_head · conservation on real runs · determinism.
"""
from __future__ import annotations

import math
import sys

from d1sim import workload_reg1 as wl
from d1sim.policies import prio_head
from d1sim.policy_eval_v2 import judge_v2 as J
from d1sim.policy_eval_v2 import kpi_v2
from d1sim.policy_eval_v2 import policies as P
from d1sim.policy_eval_v2.sim import R0, SimReg

INF = math.inf


def _row(p95=0.1, bg_rate=1.0, thr=100.0, guard_a=True, max_skin=38.0, end_skin=33.0, bg_unf=0, seed=1, key='x'):
    return dict(seed=seed, key=key, guard_a=guard_a, fg=dict(p95_all=p95, late=0, unfinished=0), bg=dict(on_time_rate=bg_rate, unfinished=bg_unf, late=0),
                thermal=dict(max_skin=max_skin, end_skin=end_skin, t38_s=0, t40_s=0, t42_s=0, throttle_s=0, throughput_inf_s=thr),
                completion=dict(bg_last_completion=1.0), duty_cmd_mean=None, conservation_ok=True)


def _stats(**kw):
    return J.policy_stats([_row(seed=s, **kw) for s in range(1, 11)])


def _small_scenario(seed=1, res='NPU', slack=1.5, lam=0.5):
    return wl.scenario_reg1(seed, slack, lam, R0[res], n_bursts=2, burst_work_s=20.0, period_s=120.0, jitter_s=10.0, tail_s=60.0)


def _run(spec, res='NPU', seed=1, residue='R0', model='v22', sc=None):
    sc = sc or _small_scenario(seed, res)
    sim = SimReg(res, model, sc['requests'], sc['horizon_s'], residue=residue)
    pol = P.make_policy(spec, res, 0.5)
    rec = sim.run(pol)
    return kpi_v2.summarize(sim, rec, pol), pol, sim


def checks():
    out = []

    def ck(name, cond, detail=''):
        out.append((name, bool(cond), detail))

    # ---- §5-6 screening
    m = J.margins([_row(p95=0.0, seed=s) for s in range(10)])
    ck('m_FG mean 0 -> 0.05', m['m_FG'] == 0.05 and m['cv_FG'] is None)
    m = J.margins([_row(p95=(INF if s == 3 else 0.1 + 0.01 * s), seed=s) for s in range(10)])
    ck('m_FG +inf -> 0.05', m['m_FG'] == 0.05 and m['cv_FG'] is None)
    m = J.margins([_row(p95=(None if s == 2 else 0.1), seed=s) for s in range(10)])
    ck('m_FG null -> 0.05', m['m_FG'] == 0.05)
    xs = [0.1, 0.3] * 5
    m = J.margins([_row(p95=x, seed=i) for i, x in enumerate(xs)])
    cv = (sum((x - 0.2) ** 2 for x in xs) / 9) ** 0.5 / 0.2
    ck('m_FG normal = max(0.05, 2 CV) (ddof 1)', abs(m['m_FG'] - 2 * cv) < 1e-12 and m['m_FG'] > 0.05, f"{m['m_FG']:.4f}")
    m = J.margins([_row(bg_rate=1.0)])
    ck('m_BG sd null (1 value) -> 5 %p', m['m_BG_pp'] == 5.0)
    m = J.margins([_row(bg_rate=r, seed=i) for i, r in enumerate([0.5, 1.0] * 5)])
    ck('m_BG = max(5, 2 sd 100)', abs(m['m_BG_pp'] - 2 * (sum((x - 0.75) ** 2 for x in [0.5, 1.0] * 5) / 9) ** 0.5 * 100) < 1e-9)
    # ---- strongest baseline · tie · ineligible
    S = {'fixed-prio': _stats(max_skin=39.00), 'npumgr': _stats(max_skin=38.97)}
    ck('tie < 0.05 -> fixed-prio', J.strongest_baseline(S) == 'fixed-prio')
    S = {'fixed-prio': _stats(max_skin=39.00), 'npumgr': _stats(max_skin=38.90)}
    ck('npumgr lower by >= 0.05 -> npumgr', J.strongest_baseline(S) == 'npumgr')
    S = {'fixed-prio': _stats(max_skin=39.0, guard_a=False), 'npumgr': _stats(max_skin=38.0, guard_a=False),
         'ref-const': _stats(max_skin=36.0), 'ours': _stats(max_skin=36.0), 'pace-d50': _stats(), 'pace-perm': _stats()}
    S = J.guards(S, dict(m_FG=0.05, m_BG_pp=5.0))
    st = J.strongest_baseline(S)
    ck('both baselines (a) fail -> 기준선 서비스 부적격', st is None and J.judge_1(S, st)['label'] == '기준선 서비스 부적격'
       and J.judge_2(S, st)['label'].startswith('기준선 서비스 부적격'))
    S['npumgr'] = _stats(max_skin=38.0)
    ck('only fixed-prio fails (a) -> strongest npumgr', J.strongest_baseline(S) == 'npumgr')
    # ---- P95 nearest-rank (+inf)
    v = [0.1] * 94 + [INF] * 6
    ck('unfinished > 5 % -> P95 +inf', math.isinf(kpi_v2.nearest_rank(v)))
    v = [0.1] * 95 + [INF] * 5
    ck('unfinished = 5 % -> P95 finite', kpi_v2.nearest_rank(v) == 0.1)
    ck('nearest-rank index ceil(.95 N) - 1', kpi_v2.nearest_rank(list(range(1, 21))) == 19 and kpi_v2.nearest_rank([]) is None)
    # ---- guard (b) +inf
    gb, _ = J.guard_b(dict(fg_p95=INF, bg_on_rate=1.0), dict(fg_p95=INF, bg_on_rate=1.0), dict(m_FG=0.05, m_BG_pp=5.0))
    ck('guard (b) inf <= inf passes', gb)
    gb, _ = J.guard_b(dict(fg_p95=0.2, bg_on_rate=1.0), dict(fg_p95=0.1, bg_on_rate=1.0), dict(m_FG=0.05, m_BG_pp=5.0))
    ck('guard (b) FG P95 x2 fails', not gb)
    gb, _ = J.guard_b(dict(fg_p95=0.1, bg_on_rate=0.94), dict(fg_p95=0.1, bg_on_rate=1.0), dict(m_FG=0.05, m_BG_pp=5.0))
    ck('guard (b) BG -6 %p fails (m 5)', not gb)
    # ---- window marker · judge ②
    base = _stats(max_skin=40.0, end_skin=33.0)
    ck('window marker: BG unfinished', J.window_flag(_stats(bg_unf=1, end_skin=33.0), base) is not None)
    ck('window marker: end SKIN > comparator + 1.0', J.window_flag(_stats(end_skin=34.2), base) is not None)
    ck('window marker: none', J.window_flag(_stats(end_skin=33.9), base) is None)
    mm = dict(m_FG=0.05, m_BG_pp=5.0)
    S = J.guards({'fixed-prio': _stats(max_skin=40.0), 'npumgr': _stats(max_skin=40.5), 'ours': _stats(max_skin=38.5),
                  'pace-d50': _stats(max_skin=39.9), 'pace-perm': _stats(max_skin=39.8), 'ref-const': _stats(max_skin=37.5)}, mm)
    j2 = J.judge_2(S, J.strongest_baseline(S))
    ck('② 가져옴 (Δ 1.5, controls not lower, residual ok)', j2['take'] and j2['label'] == '가져옴' and not j2['notes'])
    S2 = dict(S, **{'pace-d50': dict(S['pace-d50'], max_skin=37.4)})
    ck('② control >= 1.0 below ours -> not 가져옴', not J.judge_2(S2, 'fixed-prio')['take'])
    S3 = dict(S, **{'pace-perm': dict(S['pace-perm'], max_skin=38.6)})
    j3 = J.judge_2(S3, 'fixed-prio')
    ck('② control same gain -> 가져옴 + note', j3['take'] and j3['notes'])
    S4 = dict(S, ours=dict(S['ours'], end_skin=34.5))
    ck('② residual (ii) fails -> 창 밖 label', J.judge_2(S4, 'fixed-prio')['label'].startswith('창 밖'))
    nd = J.norm_diff(S, 'fixed-prio')
    ck('norm diff (40-38.5)/(40-37.5) = 0.6', abs(nd['value'] - 0.6) < 1e-9)
    S5 = dict(S, **{'ref-const': dict(S['ref-const'], max_skin=39.2)})
    ck('norm diff denominator <= 1.0 -> null', J.norm_diff(S5, 'fixed-prio')['value'] is None)
    j1 = J.judge_1(S, 'fixed-prio')
    ck('① 차이 있음 (Δ 2.5, ref guard ok)', j1['label'] == '제한 참조 대비 차이 있음')
    ck('① 차이 관측 안 됨 (Δ 0.8)', J.judge_1(S5, 'fixed-prio')['label'] == '차이 관측 안 됨')
    # ---- ref-const combos and per-seed selection
    ck('ref-const 125 unique combos over {10,25,50,75,100}', len(P.REF_COMBOS) == 125 and len(set(P.REF_COMBOS)) == 125
       and all(d in P.DUTIES for c in P.REF_COMBOS for d in c))
    fixed_row = _row(p95=0.1, bg_rate=1.0)
    rows = []
    for c, mx, ga in (((10, 10, 10), 35.0, False), ((25, 25, 25), 36.0, True), ((50, 25, 25), 36.0, True), ((100, 100, 100), 39.0, True)):
        r = _row(max_skin=mx, guard_a=ga)
        r['key'] = 'ref-const-' + '-'.join(map(str, c))
        rows.append(r)
    from d1sim.policy_eval_v2.run_eval import ref_select
    sel = ref_select(rows, fixed_row, dict(m_FG=0.05, m_BG_pp=5.0))
    ck('ref-const per-seed pick = min SKIN among passing, tie -> smaller duty sum', sel['key'] == 'ref-const-25-25-25' and sel['ref_feasible'])
    sel2 = ref_select([dict(rows[0])], fixed_row, dict(m_FG=0.05, m_BG_pp=5.0))
    ck('ref-const none passing -> flagged guard fail', not sel2['ref_feasible'] and not sel2['guard_a'])
    # ---- queue view = full queue for prio_head
    q_full = [dict(id=i, arrival_s=float(i), cls='BG') for i in range(50)] + [dict(id=100 + i, arrival_s=10.0 + i, cls='FG') for i in range(3)]
    view = [x for x in q_full if x['cls'] == 'FG'] + [min((x for x in q_full if x['cls'] == 'BG'), key=lambda x: (x['arrival_s'], x['id']))]
    ck('prio_head(view) == prio_head(full)', prio_head(view)['id'] == prio_head(q_full)['id']
       and prio_head(view, lambda x: x['cls'] != 'BG')['id'] == prio_head(q_full, lambda x: x['cls'] != 'BG')['id'])
    # ---- duty window
    pol = P.PaceD50('NPU')
    bgq = dict(id=1, cls='BG', burst=0)
    ck('pace-d50 dispatches at phase 2 s', pol.decide(dict(t=12.0, fg_head=None, bg_head=bgq))[0] == 'dispatch')
    a = pol.decide(dict(t=16.0, fg_head=None, bg_head=bgq))
    ck('pace-d50 waits at phase 6 s until 20 s', a == ('wait', 20.0))
    ck('FG first in the off-window', pol.decide(dict(t=16.0, fg_head=dict(id=7, cls='FG'), bg_head=bgq)) == ('dispatch', 7, 'NPU'))
    ck('fixed-prio always dispatches BG', P.FixedPrio('NPU').decide(dict(t=16.0, fg_head=None, bg_head=bgq))[0] == 'dispatch')
    # ---- burst = atomic arrival: at the first chunk's arrival ours sees the whole burst
    sc = _small_scenario(3, 'NPU', 1.5, 0.5)
    sim0 = SimReg('NPU', 'v22', sc['requests'], sc['horizon_s'])
    for r in sim0.reqs:
        sim0.rec.requests[r['id']] = dict(r, status='pending')
    b0 = min((r for r in sim0.reqs if r['cls'] == 'BG'), key=lambda r: (r['arrival_s'], r['id']))
    sim0.t = b0['arrival_s']
    sim0._admit(0)
    bl = sim0.bg_backlog()
    ck('backlog at first chunk arrival = whole burst', bl and bl[0][1] == sc['burst_work_inf'] and len(sim0.bg) < bl[0][1] / 128)
    # ---- real runs: conservation · determinism · pace-perm multiset · residue
    allok = True
    for spec in (('fixed-prio',), ('npumgr',), ('pace-d50',), ('ours', 0.0, 0.0), ('ref-const', (25, 50, 100))):
        r, _, _ = _run(spec, sc=sc)
        allok = allok and r['conservation_ok']
    ck('conservation holds (5 policies, NPU)', allok)
    r1, pol1, _ = _run(('ours', 30.0, -0.5), sc=sc)
    r2, _, _ = _run(('ours', 30.0, -0.5), sc=sc)
    strip = lambda r: {k: v for k, v in r.items() if k not in ('wall_s',)}  # noqa: E731
    ck('determinism (same input twice = same summary)', strip(r1) == strip(r2))
    sched = P.perm_schedule(pol1.log, 3)
    ck('pace-perm same multiset & same slots', sorted(sched.values()) == sorted(d for d, _ in pol1.log.values()) and set(sched) == set(pol1.log))
    rp, _, _ = _run(('pace-perm', sched), sc=sc)
    ck('pace-perm conservation', rp['conservation_ok'])
    g, _, _ = _run(('fixed-prio',), res='GPU', sc=_small_scenario(3, 'GPU'))
    ck('conservation holds (GPU)', g['conservation_ok'])
    a0, _, _ = _run(('fixed-prio',), sc=sc, residue='R0')
    a20, _, s20 = _run(('fixed-prio',), sc=sc, residue='R20')
    ck('R20 slows the first BG after rest (later last completion)', a20['completion']['bg_last_completion'] is not None
       and a0['completion']['bg_last_completion'] is not None and a20['completion']['bg_last_completion'] > a0['completion']['bg_last_completion'])
    for mdl in ('v21', 'v2_t0.3', 'v2_t0.75'):
        rm, _, _ = _run(('fixed-prio',), sc=sc, model=mdl)
        ck(f'model {mdl} runs (conservation)', rm['conservation_ok'])
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    res = checks()
    for name, ok, det in res:
        print('PASS' if ok else 'FAIL', name, det)
    n_fail = sum(1 for _, ok, _ in res if not ok)
    print(f'{len(res) - n_fail}/{len(res)} PASS')
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
