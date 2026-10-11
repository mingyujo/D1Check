"""DECISIONS D12 — description only (not used by the judgement): thermal driven by the MEASURED R4 activity (open loop), so the
thermal-part error can be read apart from the service sampling. Run after judge_parsim.

usage: python -m d1sim.parsim_v1.describe_open_loop <mixreq_1008 folder>
"""
from __future__ import annotations

import csv
import json
import os
import statistics
import sys

from d1sim.parsim_v1 import fit
from d1sim.parsim_v1 import judge_parsim as jp
from d1sim.parsim_v1 import service_des as sd
from d1sim.parsim_v1 import thermal_sum as ts

HERE = os.path.dirname(os.path.abspath(__file__))


def main(argv=None):
    root = (argv or sys.argv[1:])[0]
    prof = json.load(open(fit.PROFILE, encoding='utf-8'))
    meas = {(m['set'], m['index']): m for m in json.load(open(os.path.join(HERE, 'out', 'r4_measured.json'), encoding='utf-8'))['sessions']}
    params = ts.load_v22()
    rows = []
    for s in csv.DictReader(open(os.path.join(HERE, 'data', 'r4_start.csv'), encoding='utf-8')):
        if s['valid_log'] != 'True':
            continue
        cb = json.load(open(os.path.join(root, f"{s['set']}_blocks", s['folder'], 'device', 'common_boundary.json'), encoding='utf-8'))
        rr = [dict(r, selected_backend=r.get('selected_backend')) for r in cb['rows'] if r.get('lane_available_ns')]
        iv = fit.intervals_from_rows(rr, cb['start_ns'])
        m = meas[(s['set'], int(s['index']))]
        st = fit.start_state(s)
        for form, (g, kappa) in (('M-sup', (prof['M_sup']['g'], 1.0)), ('M-kappa', (prof['M_kappa']['g'], prof['M_kappa']['kappa']))):
            pt, pk, pa = fit.open_loop(params, g, kappa, st, iv, m['window_s'])
            path_ap = [sd.interp(pt, pa, float(t)) for t in range(int(m['window_s']) + 1)]
            path_sk = [sd.interp(pt, pk, float(t)) for t in range(int(m['window_s']) + 1)]
            apmax = max(jp.at(path_ap, t) for t, _, _ in m['hal'])
            skmax = max(jp.at(path_sk, t) for t, _, _ in m['hal'])
            rows.append(dict(set=s['set'], index=int(s['index']), policy=s['policy'], form=form, open_ap_max_err=apmax - m['ap_max'],
                             open_ap_path_mae=jp.path_mae(path_ap, m['hal'], 1), open_skin_max_err=skmax - m['skin_max']))
    summ = {}
    for st_ in ('R4C', 'R4S'):
        for form in ('M-sup', 'M-kappa'):
            x = [r for r in rows if r['set'] == st_ and r['form'] == form]
            summ[f'{st_} {form}'] = dict(ap_max_err_median=statistics.median(r['open_ap_max_err'] for r in x),
                                         ap_path_mae_median=statistics.median(r['open_ap_path_mae'] for r in x),
                                         skin_max_err_median=statistics.median(r['open_skin_max_err'] for r in x))
    out = os.path.join(HERE, 'out', 'open_loop_describe.json')
    json.dump(dict(what='D12 open-loop thermal (measured R4 activity) — description only, not a verdict', summary=summ, sessions=rows),
              open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(summ, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    sys.exit(main())
