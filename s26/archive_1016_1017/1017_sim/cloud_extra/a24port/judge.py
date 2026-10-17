"""PREREG_A24PORT_1017 judgement. Baselines and RULE from the existing E4 measured-device runs."""
import json, statistics as st, subprocess
from pathlib import Path
BASE = ['FIFO_FREE', 'EDF_FREE', 'FIFO_PAIR_CN', 'FIFO_PAIR_CG']
rate = lambda r: 100 * r['on_time'] / r['planned']
key = lambda r: json.dumps(r['load'], sort_keys=True)
by = {}
for x in open('/home/claude/work/vd/runs/Ameas_B0.jsonl'):
    r = json.loads(x)
    if 'error' not in r: by.setdefault(key(r), {})[r['policy']] = r
for f in sorted(Path('runs').glob('out_*.jsonl')):
    for x in f.open():
        r = json.loads(x); assert 'error' not in r
        assert r['on_time'] <= r['completed'] and r['completed'] + r['unfinished'] == r['planned']
        by[key(r)]['ATC_A24'] = r
assert all(len(v) == 6 for v in by.values()), 'missing policy'
over = [k for k in by if max(rate(by[k][p]) for p in BASE) < 99]
d1 = [rate(by[k]['ATC_A24']) - max(rate(by[k][p]) for p in BASE) for k in over]
d2 = [rate(by[k]['RULE']) - rate(by[k]['ATC_A24']) for k in over]
H1 = sum(x >= .5 for x in d1) / len(d1) >= .8 and st.mean(d1) > .5
def routes(p, ks):
    c = {x: sum(by[k][p]['routes']['classification_' + x] for k in ks) for x in ('CPU', 'GPU', 'NPU')}; t = sum(c.values())
    return {x: round(100 * v / t, 1) for x, v in c.items()}
def urg(p, ks): return round(100 * sum(by[k][p]['U_on'] for k in ks) / sum(by[k][p]['U_planned'] for k in ks), 1)
out = {'pairs': len(by), 'overload_pairs': len(over),
       'H1_ATC_A24_vs_best_baseline': {'pass': H1, 'mean_pp': st.mean(d1), 'share_ge_0.5': sum(x >= .5 for x in d1) / len(d1), 'min': min(d1), 'max': max(d1)},
       'H2_RULE_minus_ATC_A24': {'mean_pp': st.mean(d2), 'min': min(d2), 'max': max(d2), 'share_RULE_higher': sum(x > 0 for x in d2) / len(d2), 'share_tie': sum(abs(x) < 1e-9 for x in d2) / len(d2)},
       'mean_on_time_overload': {p: round(st.mean(rate(by[k][p]) for k in over), 2) for p in ['RULE', 'ATC_A24'] + BASE},
       'urgent_on_time_overload': {p: urg(p, over) for p in ['RULE', 'ATC_A24', 'FIFO_FREE', 'EDF_FREE']},
       'R21_on_time': {p: [round(rate(by[k][p]), 1) for k in by if json.loads(k)['kind'] == 'R21'] for p in ['RULE', 'ATC_A24', 'FIFO_FREE']},
       'class_routes_overload': {p: routes(p, over) for p in ['RULE', 'ATC_A24', 'FIFO_FREE']},
       'class_routes_all': {p: routes(p, list(by)) for p in ['RULE', 'ATC_A24', 'FIFO_FREE']},
       'dJ_dAP_vs_FIFO_FREE_overload': {p: {'dJ': round(st.mean(by[k][p]['J'] - by[k]['FIFO_FREE']['J'] for k in over), 2),
                                           'dAPmean': round(st.mean(by[k][p]['AP_mean'] - by[k]['FIFO_FREE']['AP_mean'] for k in over), 3),
                                           'dAPpeak': round(st.mean(by[k][p]['AP_peak'] - by[k]['FIFO_FREE']['AP_peak'] for k in over), 3)} for p in ['RULE', 'ATC_A24']}}
json.dump(out, open('runs/JUDGEMENT.json', 'w'), indent=1, ensure_ascii=False)
print(json.dumps(out, indent=1, ensure_ascii=False))
