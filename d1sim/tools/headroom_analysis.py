"""Step 2: does getThermalHeadroom predict the operational throttle entry? (PC analysis only)

Rule fixed before computing r2 (sim/headroom_분석_0927.md §1, 18:18 KST):
  signals  : headroom_now, headroom_60s, SKIN, AP  (1 s trace, d1sim/data/trace_<tag>.csv)
  entry    : operational onset (d1sim/throttle.py:onset_time_ref) on 10 s bins
  threshold: theta = r1 value of the signal at t = entry_r1 - LEAD_TARGET (20 s)  -- chosen on r1 only
  alarm    : first t (s) with signal >= theta ; lead = entry - alarm
  report   : r1 lead (by construction ~20 s for monotone signals), r2 lead, 9/14 60 s runs alarm time (entry not
             reached in 60 s there), linear fit headroom_now ~ SKIN (R^2) on r1 as a descriptive check.
Usage: py d1sim/tools/headroom_analysis.py
"""
import csv, json, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from d1sim.tools.fit_throttle import load  # noqa: E402
from d1sim.throttle import onset_time_ref  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), '..', 'data')
LEAD_TARGET = 20
SIGNALS = ('headroom_now', 'headroom_60s', 'SKIN', 'AP')


def series(tag):
    out = {s: [] for s in SIGNALS}
    for r in csv.DictReader(open(os.path.join(DATA, f'trace_{tag}.csv'), encoding='utf-8')):
        for s in SIGNALS:
            if r[s] != '':
                out[s].append((int(r['t_s']), float(r[s])))
    return out


def entry(tag):
    d = load(tag)
    return onset_time_ref([(t, m) for t, m, _ in d['ten']], d['ref_lat'])


def alarm(ser, theta):
    return next((t for t, v in ser if v >= theta), None)


def main():
    tags = ['c1p_r1', 'c1p_r2'] + [f'f914_gpu_d100_r00{i}' for i in range(1, 6)]
    S = {t: series(t) for t in tags}
    E = {t: entry(t) for t in tags}
    res = dict(rule=__doc__.split('Usage')[0], entry=E, signals={})
    for s in SIGNALS:
        at = E['c1p_r1'] - LEAD_TARGET
        theta = next(v for t, v in S['c1p_r1'][s] if t >= at)
        row = dict(theta=theta)
        for t in tags:
            a = alarm(S[t][s], theta)
            row[t] = dict(alarm_s=a, lead_s=(E[t] - a) if (a is not None and E[t] is not None) else None,
                          max=max(v for _, v in S[t][s]), value_at_entry=(next(v for tt, v in S[t][s] if tt >= E[t])
                                                                          if E[t] is not None else None))
        res['signals'][s] = row
    # descriptive: headroom_now vs SKIN on r1 (same-second pairs)
    sk = dict(S['c1p_r1']['SKIN']); hn = [(sk[t], v) for t, v in S['c1p_r1']['headroom_now'] if t in sk]
    x, y = np.array([a for a, _ in hn]), np.array([b for _, b in hn])
    A = np.vstack([x, np.ones_like(x)]).T
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    r2 = 1 - ((y - A @ coef) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    res['headroom_now_vs_SKIN_r1'] = dict(slope_per_C=float(coef[0]), intercept=float(coef[1]), R2=float(r2), n=len(x))
    out = os.path.join(os.path.dirname(__file__), '..', 'out', 'headroom_0927.json')
    json.dump(res, open(out, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in res.items() if k != 'rule'}, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
