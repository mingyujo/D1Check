"""Stage 4 — measured confirmation metrics from the committed R4 session copies (run ONLY after the frozen predictions are committed
and their SHA is in the OneDrive ledger). Reads, per valid session: device/common_boundary.json rows (request stage timestamps) and
host/hal.csv rows inside the common window. Session JSON files are opened read-only and never modified (SHA recorded).

Metric definitions = DECISIONS_P1l.md D10. Output: out/r4_measured.json (+ hal samples for the judge).

usage: python -m d1sim.parsim_v1.measure_r4 <mixreq_1008 folder> [--out PATH] [--selftest]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys

from d1sim.parsim_v1 import extract as ex
from d1sim.parsim_v1 import service_des as sd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out', 'r4_measured.json')


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def session_metrics(cb, hal_rows):
    t0, t1 = cb['start_ns'], cb['end_ns']
    urg, nor, on_time, done = [], [], 0, 0
    for r in cb['rows']:
        ok = r.get('terminal_status') == 'succeeded'
        end_key = 'output_ready_ns' if r['priority'] == 'urgent' else 'persist_complete_ns'
        resp = (r[end_key] - r['scheduled_arrival_ns']) / 1e9 if ok and r.get(end_key) else math.inf
        (urg if r['priority'] == 'urgent' else nor).append(resp)
        if ok:
            done += 1
            if r['deadline_ns'] >= r[end_key]:
                on_time += 1
    hal = [(h['t_s'] - t0 / 1e9, h['AP'], h['SKIN']) for h in hal_rows if t0 / 1e9 <= h['t_s'] <= t1 / 1e9]
    p95u, p95n = sd.nearest_rank_p95(urg), sd.nearest_rank_p95(nor)
    first38 = next((t for t, _, sk in hal if sk >= 38.0), None)
    return dict(planned=len(cb['rows']), completed=done, on_time=on_time,
                urgent_p95_ms=None if math.isinf(p95u) else p95u * 1000.0, normal_p95_ms=None if math.isinf(p95n) else p95n * 1000.0,
                urgent_unfinished=sum(1 for x in urg if math.isinf(x)),
                ap_max=max(a for _, a, _ in hal), skin_max=max(s for _, _, s in hal), skin_saturated=max(s for _, _, s in hal) >= 38.0,
                skin38_first_s=first38, window_s=(t1 - t0) / 1e9, hal=[[round(t, 3), a, s] for t, a, s in hal])


def measure(root, out=OUT):
    if os.path.exists(out):
        raise SystemExit(f'refuse: {out} exists (measured once)')
    start = list(csv.DictReader(open(os.path.join(HERE, 'data', 'r4_start.csv'), encoding='utf-8')))
    sessions, sources = [], []
    for s in start:
        if s['valid_log'] != 'True':
            continue
        d = os.path.join(root, f"{s['set']}_blocks", s['folder'])
        cbp = os.path.join(d, 'device', 'common_boundary.json')
        hp = os.path.join(d, 'host', 'hal.csv')
        cb = json.load(open(cbp, encoding='utf-8'))
        m = session_metrics(cb, ex.read_hal(hp))
        sessions.append(dict(set=s['set'], index=int(s['index']), folder=s['folder'], session_id=s['session_id'], policy=s['policy'],
                             block=s['block'], pair=int(s['pair']), **m))
        sources += [dict(path=os.path.relpath(p, root).replace('\\', '/'), sha256=sha(p)) for p in (cbp, hp)]
    doc = dict(what='P1l stage 4 — measured R4 confirmation metrics (DECISIONS D10)', sources=sources, sessions=sessions)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(doc, open(out, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('wrote', out, sha(out))
    return doc


def selftest():
    base = 1_000_000_000_000
    rows = []
    for i in range(20):
        sched = base + int((35 + 0.2 * i) * 1e9)
        urgent = i % 2 == 0
        end = sched + int((0.07 if urgent else 0.25) * 1e9)
        rows.append(dict(priority='urgent' if urgent else 'normal', terminal_status='succeeded', scheduled_arrival_ns=sched,
                         deadline_ns=sched + int((1.5 if urgent else 6.0) * 1e9), output_ready_ns=end - 1000, persist_complete_ns=end))
    rows[0]['terminal_status'] = 'failed'
    cb = dict(start_ns=base, end_ns=base + int(120e9), rows=rows)
    hal = [dict(t_s=base / 1e9 + t, AP=30 + t / 10, SKIN=30 + t / 100) for t in range(-5, 126, 2)]
    m = session_metrics(cb, hal)
    ok = m['completed'] == 19 and m['urgent_p95_ms'] is None and m['urgent_unfinished'] == 1
    ok &= abs(m['ap_max'] - (30 + 119 / 10)) < 1e-9 and m['hal'][0][0] == 1.0
    print('measure_r4 selftest', 'PASS' if ok else 'FAIL', m['urgent_p95_ms'], m['normal_p95_ms'], m['ap_max'])
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('root', nargs='?')
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args(argv)
    if a.selftest:
        return 0 if selftest() else 1
    measure(a.root, a.out)


if __name__ == '__main__':
    sys.exit(main())
