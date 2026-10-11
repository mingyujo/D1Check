"""Stage 2 extraction (P1l v2) — reads the committed session copies of origin/s26-mixreq (s26/results/mixreq_1008) and writes
small CSV/JSON tables under d1sim/parsim_v1/data/ + data/manifest.json (source path · SHA-256 · rows).

R3 (S26-MIXREQ-02, development): everything — per-request stage timestamps (device/common_boundary.json rows), HAL 2 s samples
(host/hal.csv), gate idle state, common window.
R4 (C = S26-MIXREQ-02C, S = S26-MIXREQ-03, confirmation): ONLY the start state and the planned request sequence (prompt v2 boundary):
  host/session_log.txt gate line + VALID line · host/hal.csv rows with device_boottime_s <= common start · common_boundary.json
  'start_ns' / 'end_ns' / 'planned' keys only · plan manifests (requests = offset/priority/task/deadline).
  Request outcome timestamps, in-window HAL and readouts are NOT read here (stage 4: measure_r4.py).

usage: python -m d1sim.parsim_v1.extract <mixreq_1008 folder> [--selftest]
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
STAGE_KEYS = ('scheduled_arrival_ns', 'actual_arrival_ns', 'deadline_ns', 'queue_entry_ns', 'dispatch_ns', 'execution_start_ns',
              'host_inference_start_ns', 'host_inference_return_ns', 'output_ready_ns', 'persist_complete_ns',
              'worker_release_ns', 'lane_available_ns')
GATE_RE = re.compile(r'gate rc=\d+ last=(\S+) (\S+) (\S+) ([\d.]+) ([\d.]+) ([\d.]+) (\d+) (\d+) (\S+) (\S+)')
SID_RE = re.compile(r'SESSION START sid=(\S+) attempt=(\d+) policy=(\S+) block=(\S+)')
VALID_RE = re.compile(r'VALID=(True|False)')


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def parse_session_log(path):
    """gate idle state (SKIN/AP/BAT/status/SOC), session id/policy/block, VALID flag — first gate line + last VALID line."""
    out = {}
    for ln in open(path, encoding='utf-8', errors='replace'):
        m = SID_RE.search(ln)
        if m and 'sid' not in out:
            out.update(sid=m.group(1), attempt=int(m.group(2)), policy=m.group(3), block=m.group(4))
        m = GATE_RE.search(ln)
        if m and 'gate_skin' not in out:
            out.update(gate_waited_s=float(m.group(3)), gate_skin=float(m.group(4)), gate_ap=float(m.group(5)),
                       gate_bat=float(m.group(6)), gate_status=int(m.group(7)), gate_soc=int(m.group(8)))
        m = VALID_RE.search(ln)
        if m:
            out['valid'] = (m.group(1) == 'True')
    return out


def read_hal(path, until_s=None):
    rows = []
    with open(path, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            t = float(r['device_boottime_s'])
            if until_s is not None and t > until_s:
                break
            rows.append(dict(t_s=t, SKIN=float(r['SKIN']), AP=float(r['AP']), BAT=float(r['BAT']),
                             PA=float(r['PA']) if r.get('PA') not in (None, '') else None, status=int(r['thermal_status'])))
    return rows


def session_dirs(block_dir):
    return sorted(d for d in glob.glob(os.path.join(block_dir, 'S26_MIXREQ_*')) if os.path.isdir(d))


def folder_index(name):
    return int(os.path.basename(name).split('_')[2])


def extract_r3(root, manifest):
    sess_rows, req_rows, hal_rows = [], [], []
    for d in session_dirs(os.path.join(root, 'R3_blocks')):
        name = os.path.basename(d)
        idx = folder_index(name)
        log = parse_session_log(os.path.join(d, 'host', 'session_log.txt'))
        val = json.load(open(os.path.join(d, 'validated.json'), encoding='utf-8'))
        cb_path = os.path.join(d, 'device', 'common_boundary.json')
        cb = json.load(open(cb_path, encoding='utf-8'))
        hal_path = os.path.join(d, 'host', 'hal.csv')
        hal = read_hal(hal_path)
        start_s = cb['start_ns'] / 1e9
        pre = [h for h in hal if h['t_s'] <= start_s]
        h0 = pre[-1] if pre else None
        sess_rows.append(dict(set='R3', index=idx, folder=name, session_id=log.get('sid'), policy=log.get('policy'), block=log.get('block'),
                              pair=val.get('pair'), attempt=log.get('attempt'), eligible=bool(val.get('eligible')), valid_log=log.get('valid'),
                              start_ns=cb['start_ns'], end_ns=cb['end_ns'], planned=cb['planned'],
                              gate_skin=log.get('gate_skin'), gate_ap=log.get('gate_ap'), gate_bat=log.get('gate_bat'),
                              gate_soc=log.get('gate_soc'),
                              start_hal_t_s=h0['t_s'] if h0 else None, start_skin=h0['SKIN'] if h0 else None,
                              start_ap=h0['AP'] if h0 else None, start_bat=h0['BAT'] if h0 else None))
        for r in cb['rows']:
            row = dict(set='R3', index=idx, ordinal=r['ordinal'], request_id=r['request_id'], task_id=r['task_id'], priority=r['priority'],
                       terminal_status=r['terminal_status'], selected_backend=r.get('selected_backend'))
            for k in STAGE_KEYS:
                row[k] = r.get(k)
            req_rows.append(row)
        for h in hal:
            hal_rows.append(dict(set='R3', index=idx, **h))
        for p in (cb_path, hal_path, os.path.join(d, 'host', 'session_log.txt'), os.path.join(d, 'validated.json')):
            manifest['sources'].append(dict(path=os.path.relpath(p, root).replace('\\', '/'), sha256=sha256_file(p)))
    return sess_rows, req_rows, hal_rows


def plan_requests(plan_dir):
    """plan manifests -> {session_id: dict(policy, block, pair, index, requests[...], manifest, sha256)}"""
    out = {}
    plan = json.load(open(os.path.join(plan_dir, 'plan.json'), encoding='utf-8'))
    for s in plan['sessions']:
        mp = os.path.join(plan_dir, s['manifest'])
        m = json.load(open(mp, encoding='utf-8'))
        out[s['session_id']] = dict(index=s['index'], policy=s['policy'], block=s['block'], pair=s['pair'], phases=m['phases'],
                                    requests=m['requests'], manifest=os.path.relpath(mp, os.path.dirname(plan_dir)).replace('\\', '/'),
                                    sha256=sha256_file(mp))
    return out


def extract_r4(root, which, manifest):
    """which = 'C' (R4C_blocks, plan_v3c) | 'S' (R4S_blocks, plan_v3s). Start state + schedule only."""
    block_dir = os.path.join(root, f'R4{which}_blocks')
    plans = plan_requests(os.path.join(root, 'plan_v3c' if which == 'C' else 'plan_v3s'))
    sess_rows, sched_rows = [], []
    for d in session_dirs(block_dir):
        name = os.path.basename(d)
        if not re.search(r'_a\d+$', name):          # _pre1_charge / _abort_* folders = not an attempt
            continue
        idx = folder_index(name)
        log = parse_session_log(os.path.join(d, 'host', 'session_log.txt'))
        cbp = os.path.join(d, 'device', 'common_boundary.json')
        start_ns = end_ns = planned = None
        if os.path.exists(cbp):
            cb = json.load(open(cbp, encoding='utf-8'))
            start_ns, end_ns, planned = cb.get('start_ns'), cb.get('end_ns'), cb.get('planned')
            del cb                                           # rows are results -> never touched before stage 4
        h0 = None
        hp = os.path.join(d, 'host', 'hal.csv')
        if start_ns is not None and os.path.exists(hp):
            pre = read_hal(hp, until_s=start_ns / 1e9)
            h0 = pre[-1] if pre else None
        p = plans.get(log.get('sid'))
        sess_rows.append(dict(set=f'R4{which}', index=idx, folder=name, session_id=log.get('sid'), policy=log.get('policy'),
                              block=log.get('block'), pair=p['pair'] if p else None, attempt=log.get('attempt'), valid_log=log.get('valid'),
                              plan_policy=p['policy'] if p else None, plan_manifest=p['manifest'] if p else None,
                              plan_sha256=p['sha256'] if p else None,
                              start_ns=start_ns, planned=planned, common_s=(p['phases']['common_s'] if p else None),
                              gate_skin=log.get('gate_skin'), gate_ap=log.get('gate_ap'), gate_bat=log.get('gate_bat'),
                              gate_soc=log.get('gate_soc'),
                              start_hal_t_s=h0['t_s'] if h0 else None, start_skin=h0['SKIN'] if h0 else None,
                              start_ap=h0['AP'] if h0 else None, start_bat=h0['BAT'] if h0 else None))
        manifest['sources'].append(dict(path=os.path.relpath(os.path.join(d, 'host', 'session_log.txt'), root).replace('\\', '/'),
                                        sha256=sha256_file(os.path.join(d, 'host', 'session_log.txt')), read='gate+sid+VALID lines'))
        if p and log.get('valid'):
            for r in p['requests']:
                sched_rows.append(dict(set=f'R4{which}', index=idx, session_id=log.get('sid'), ordinal=r['ordinal'], task_id=r['task_id'],
                                       priority=r['priority'], offset_ms=r['offset_ms'], deadline_ms=r['deadline_ms'],
                                       request_id=r['request_id']))
    for sid, p in plans.items():
        manifest['sources'].append(dict(path=f"plan_v3{which.lower()}/{os.path.basename(p['manifest'])}", sha256=p['sha256'], read='schedule'))
    return sess_rows, sched_rows


def write_csv(path, rows):
    if not rows:
        return 0
    keys = list(rows[0].keys())
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        w = csv.DictWriter(f, fieldnames=keys, lineterminator='\n')
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return len(rows)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('root', help='…/s26/results/mixreq_1008 (checkout of origin/s26-mixreq)')
    ap.add_argument('--out', default=DATA)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    manifest = dict(source_branch='origin/s26-mixreq', source_commit=os.environ.get('MIXREQ_COMMIT', 'unknown'), sources=[], outputs={})
    s3, q3, h3 = extract_r3(a.root, manifest)
    s4c, sc = extract_r4(a.root, 'C', manifest)
    s4s, ss = extract_r4(a.root, 'S', manifest)
    files = {'r3_sessions.csv': s3, 'r3_requests.csv': q3, 'r3_hal.csv': h3,
             'r4_start.csv': s4c + s4s, 'r4_schedule.csv': sc + ss}
    for fn, rows in files.items():
        n = write_csv(os.path.join(a.out, fn), rows)
        manifest['outputs'][fn] = dict(rows=n, sha256=sha256_file(os.path.join(a.out, fn)))
    json.dump(manifest, open(os.path.join(a.out, 'manifest.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(manifest['outputs'], ensure_ascii=False, indent=1))
    print('R3 sessions', len(s3), 'eligible', sum(r['eligible'] for r in s3), '| R4C', len(s4c), 'valid', sum(bool(r['valid_log']) for r in s4c),
          '| R4S attempts', len(s4s), 'valid', sum(bool(r['valid_log']) for r in s4s))


if __name__ == '__main__':
    sys.exit(main())
