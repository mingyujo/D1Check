"""cells_gpu.py — run list for the GPU model-error check (prereg §2, commit 35c9342) → d1sim/model_error_gpu_v1/cells_gpu.json.
Written and committed BEFORE any error computation. Identifiers · start states · judge-JSON SHAs only — no error numbers, no measured
thermal metrics beyond the start SKIN (public in every result document). results/ · judge JSONs · traces are read only.

  py -X utf8 -m d1sim.model_error_gpu_v1.cells_gpu [--selftest]
"""
from __future__ import annotations

import argparse
import os
import sys

from d1sim.model_error_gpu_v1 import common as C

C.stdout_utf8()


def start_skin_trace(tag):
    for r in C.trace1(tag):
        if r['SKIN'] != '':
            return float(r['SKIN'])
    raise SystemExit(f'no SKIN in trace {tag}')


def start_skin_judge(tag, J):
    r = C.RUNS[tag]
    if r['judge'].startswith('out_0928'):
        T = 'T1' if tag == 'c1a' else 'T2'
        return C.load_json(os.path.join(C.ROOT, 'd1sim', 'out', 'v0_holdout_1003.json'))[T]['T_start']
    if 'start_skin' in J:
        return J['start_skin']
    st = (J.get('segment_start_thermal') or {}).get('0') or {}
    return st.get('SKIN')


def build():
    runs = {}
    for tag, r in C.RUNS.items():
        m = C.run_manifest(tag)
        jp = C.judge_path(tag)
        J = C.load_json(jp)
        sk = start_skin_trace(tag)
        skj = start_skin_judge(tag, J)
        pans = ([r['holdout']] if r['holdout'] else []) + ['v22']
        if r['v22'] != 'generated':
            pans.append('v22_2pt')
        t1, t10 = C.trace_paths(tag)
        lower = C.get_path(J, 'start.lower.label')
        runs[tag] = dict(label=r['label'], resource=r['resource'], model=r['model'], engine=r['engine'], group=r['group'], role=r['role'], kind=r['kind'],
                         cell=r.get('cell'), block=r.get('block'), side=r.get('side'), run_id=m['run_id'], result_dir=m['result_dir'],
                         raw_results_present=os.path.isdir(os.path.join(C.ROOT, m['result_dir'])),
                         segments=[(s['accelerator'], s['duty'], s['duration_s']) for s in m['segments']], sigma_s=sum(s['duration_s'] for s in m['segments']),
                         rows_1s=m['rows_1s'], trace_1s=os.path.relpath(t1, C.ROOT), trace_1s_sha256=C.sha256_file(t1), trace_10s_sha256=C.sha256_file(t10),
                         judge_json=r['judge'], judge_json_sha256=C.sha256_file(jp), judge_run_id_equal=(J.get('run_id') == m['run_id']) if 'run_id' in J else None,
                         start_skin=sk, start_skin_judge=skj, start_skin_equal=(skj is None or abs(skj - sk) < 1e-9), in_range=C.in_range(sk),
                         lower=lower, column_2pt=C.pick_column(sk), holdout_pan=r['holdout'], v22_source=r['v22'], pans=pans, judge_ft=list(r['judge_ft']))
    pairs = {}
    for key, p in C.PAIRS.items():
        jp = C.judge_path(p['judge'])
        J = C.load_json(jp)
        a, b = runs[p['a']], runs[p['b']]
        mean = (a['start_skin'] + b['start_skin']) / 2
        pairs[key] = dict(resource=p['resource'], group=p['group'], block=p['block'], a=p['a'], b=p['b'], judge_json=p['judge'], judge_json_sha256=C.sha256_file(jp),
                          judge_run_ids_equal=(J['a']['run_id'] == a['run_id'] and J['b']['run_id'] == b['run_id']),
                          start_skin_a=a['start_skin'], start_skin_b=b['start_skin'], start_skin_mean=round(mean, 3), column_2pt=C.pick_column(mean),
                          in_range=(a['in_range'] and b['in_range']), pans=list(p['pans']), note=p.get('note'))
    resources = {}
    for key, r in C.RESOURCES.items():
        jp = C.judge_path(r['judge'])
        resources[key] = dict(resource=r['resource'], group=r['group'], pairs=list(r['pairs']), judge_json=r['judge'], judge_json_sha256=C.sha256_file(jp), pans=list(r['pans']), note=r.get('note'))
    judges = {n: C.sha256_file(os.path.join(C.OD_SIM, n)) for n in ('night1003_judge.py', 'night1004_judge.py', 'night1005_judge.py', 'night1005e_judge.py', 'm1m2_judge_1002.py', 'predict_pacing_v1_1003.py')}
    return dict(kind='gpuerr_cells_v1', registration=f'{C.REG} ({C.REG_COMMIT[:7]}) §2', n_runs=len(runs), n_gpu=len(C.GPU_TAGS), n_npu=len(C.NPU_TAGS),
                columns_2pt=list(C.COLUMNS), dev_range=list(C.DEV_RANGE), thr=C.THR, hold=C.HOLD, pass_abs=C.PASS_ABS,
                runs=runs, pairs=pairs, resources=resources, judges=judges,
                manifests={pre: C.sha256_file(os.path.join(C.DATA, f'trace_{pre}_manifest.json')) for pre in ('v1', 'v2', 'v21', 'v22')},
                note='식별자 · 시작 상태 · 판정 JSON SHA 만 — 오차 숫자 0 (등록 §2 · 결과 전 커밋). 10/4 까지 런의 원시 results/ 폴더는 Drive zip (preflight (a)).')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    res = build()
    s = C.write_json(C.CELLS_JSON, res)
    for tag, r in res['runs'].items():
        print(f"{tag:15s} {r['resource']} {r['model']:9s} {r['engine']} start {r['start_skin']} (judge {r['start_skin_judge']}) → col {r['column_2pt']} {'범위 안' if r['in_range'] else '범위 밖'} · pans {r['pans']} · judge {r['judge_json']} {r['judge_json_sha256'][:8]}")
    for k, p in res['pairs'].items():
        print(f"pair {k}: {p['a']} {p['start_skin_a']} · {p['b']} {p['start_skin_b']} → mean {p['start_skin_mean']} col {p['column_2pt']}")
    print('->', C.CELLS_JSON, s)
    return 0


def selftest():
    res = []

    def check(name, cond, got=''):
        res.append((name, bool(cond), got))
    cells = build()
    rs = cells['runs']
    check('① 런 수 30 = GPU 19 + NPU 11 · 전부 manifest run_id · 판정 JSON · trace 1 s · 10 s 존재', len(rs) == 30 and cells['n_gpu'] == 19 and cells['n_npu'] == 11
          and all(os.path.exists(C.judge_path(t)) and all(os.path.exists(p) for p in C.trace_paths(t)) for t in rs), (len(rs), cells['n_gpu'], cells['n_npu']))
    check('② 판정 JSON run_id = manifest run_id (run_id 가 있는 모든 런)', all(r['judge_run_id_equal'] in (True, None) for r in rs.values()), [t for t, r in rs.items() if r['judge_run_id_equal'] is False])
    check('③ 시작 SKIN: trace 첫 행 = 판정 JSON (있는 런 전부 · 1e-9)', all(r['start_skin_equal'] for r in rs.values()), [(t, r['start_skin'], r['start_skin_judge']) for t, r in rs.items() if not r['start_skin_equal']])
    check('④ 범위 밖 = n1_gb_b2 (27.8) 만 · 열: 28.5 → 29.5 · 30.7 → 30.5 · 30.0 → 29.5 (동률 작은 쪽)', [t for t, r in rs.items() if not r['in_range']] == ['n1_gb_b2']
          and rs['g50p']['column_2pt'] == 29.5 and rs['gi300']['column_2pt'] == 30.5 and rs['n1_na_b2']['column_2pt'] == 29.5, [(t, r['start_skin']) for t, r in rs.items() if not r['in_range']])
    check('⑤ 판: v0 런 [v0, v22] · N1 GPU [v21, v22, v22_2pt] · N4 [v22] · NPU N1 [v22, v22_2pt]', rs['c1a']['pans'] == ['v0', 'v22'] and rs['n1_ga_b1']['pans'] == ['v21', 'v22', 'v22_2pt']
          and rs['n4_gie_b1']['pans'] == ['v22'] and rs['n1_na_b1']['pans'] == ['v22', 'v22_2pt'] and rs['h_gb_b2_re']['pans'] == ['v21', 'v22', 'v22_2pt'])
    check('⑥ 쌍 10 (GPU 5 · NPU 5) · pair JSON run_id = A · B run_id · 열 = 평균에 가까운 쪽', len(cells['pairs']) == 10 and all(p['judge_run_ids_equal'] for p in cells['pairs'].values())
          and all(p['column_2pt'] == C.pick_column(p['start_skin_mean']) for p in cells['pairs'].values()), [(k, p['start_skin_mean'], p['column_2pt']) for k, p in cells['pairs'].items()])
    check('⑦ 자원 6 · 쌍 키 전부 pairs 에 있음 · 판정기 SHA 접두 (ca8680c2 · 2db1cda5 · a5ceab41)', len(cells['resources']) == 6 and all(pk in cells['pairs'] for r in cells['resources'].values() for pk in r['pairs'])
          and cells['judges']['night1005_judge.py'].startswith('ca8680c2') and cells['judges']['night1005e_judge.py'].startswith('2db1cda5') and cells['judges']['night1003_judge.py'].startswith('a5ceab41'))
    check('⑧ 오차 숫자 없음: 런 항목에 max · 899 · mae · delta 키 없음', not any(any(k in ('max_skin', 'skin_899', 'm1', 'm3', 'd_max_skin') for k in r) for r in rs.values()))
    check('⑨ 결정성: 같은 입력 두 번 → 같은 JSON 바이트', C.dumps(build()) == C.dumps(cells))
    return C.print_table(res)


if __name__ == '__main__':
    sys.exit(main())
