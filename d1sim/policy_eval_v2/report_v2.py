"""report_v2.py — markdown tables from d1sim/out/policy_eval_v2/{dev,holdout}_summary.json (no judgement logic here).

  py -m d1sim.policy_eval_v2.report_v2 dev       -> d1sim/out/policy_eval_v2/dev_tables.md
  py -m d1sim.policy_eval_v2.report_v2 holdout   -> d1sim/out/policy_eval_v2/holdout_tables.md
"""
from __future__ import annotations

import json
import math
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(ROOT, 'd1sim', 'out', 'policy_eval_v2')
POL_ORDER = ('fixed-prio', 'npumgr', 'ours', 'pace-d50', 'pace-perm', 'ref-const')


def f(x, nd=2):
    if x is None:
        return '—'
    if isinstance(x, float) and math.isinf(x):
        return '+∞'
    if isinstance(x, bool):
        return '✓' if x else '✗'
    if isinstance(x, (int, float)):
        return f'{x:.{nd}f}'
    return str(x)


def g(ps):
    if ps is None:
        return '—'
    a = '✓' if ps.get('guard_a') else '✗'
    b = '✓' if ps.get('guard_b') else '✗'
    return f'{a}{b}'


def dev_tables(S):
    L = []
    main = S['tables']['v22']
    L.append('### ① 24 조건 — 주 모형 v2.2 (개발 seed 1–10 · seed 중앙 · 가드 = (a)(b))\n')
    L.append('| 조건 | 가장 강한 기준선 | fixed-prio 최고 SKIN · 가드 | npumgr | ref-const (가능 seed) | ① Δ (기준선 − ref) ℃ | ① 판정 | m_FG · m_BG %p |')
    L.append('|---|---|---|---|---|---:|---|---|')
    for cid, e in main.items():
        st = e['stats']
        if 'conservation_fail' in e:
            L.append(f"| {cid} | — | 보존 실패 | | | | {e['j1']['label']} | |")
            continue
        fp, nm, rc = st.get('fixed-prio'), st.get('npumgr'), st.get('ref-const')
        m = e['margins']
        L.append(f"| {cid} | {e['strongest'] or '부적격'} | {f(fp['max_skin'])} · {g(fp)} | {f(nm['max_skin'])} · {g(nm)} | "
                 f"{f(rc['max_skin'])} · {g(rc)} ({rc['n'] - len(rc['guard_a_fail_seeds'])}/{rc['n']}) | {f(e['j1']['delta'])} | {e['j1']['label']} | "
                 f"{f(m['m_FG'], 3)} · {f(m['m_BG_pp'], 1)} |")
    L.append('\n### 정책별 (주 모형, 선택된 ours) — seed 중앙 최고 SKIN ℃ · 가드 (a)(b) · BG 늦음/미완료 합 · 창 끝 SKIN\n')
    L.append('| 조건 | ' + ' | '.join(POL_ORDER) + ' |')
    L.append('|---|' + '---|' * len(POL_ORDER))
    for cid, e in main.items():
        st = e['stats']
        if 'conservation_fail' in e:
            continue
        cells = []
        for p in POL_ORDER:
            ps = st.get(p)
            cells.append('—' if ps is None else f"{f(ps['max_skin'])} {g(ps)} · {ps['bg_late_total']}/{ps['bg_unfinished_total']} · {f(ps['end_skin'], 1)}")
        L.append(f'| {cid} | ' + ' | '.join(cells) + ' |')
    T = S['tuning']
    L.append('\n### ours 튜닝 (개발 seed · 주 모형) — 등록 v1 §4 6 설정\n')
    L.append('| 설정 | 가드 (a)(b) 통과 조건 (/24) | 24 조건 전부 | 조건별 seed 중앙 최고 SKIN 평균 ℃ | Σ Δ (가장 강한 기준선 − ours) ℃ |')
    L.append('|---|---:|---|---:|---:|')
    for k, v in T['table'].items():
        L.append(f"| {k}{' ← **선택**' if k == T['selected'] else ''} | {v['n_guard_pass']} | {f(v['all_pass'])} | {f(v['mean_max_skin'], 3)} | {f(v['sum_delta_vs_strongest'], 3)} |")
    L.append(f"\n- 규칙: {T['rule']}")
    for m in ('v21', 'v2_t0.3', 'v2_t0.75'):
        tb = S['tables'][m]
        L.append(f'\n### 민감도 {m} (정책 1~4, ref-const 없음) — 가장 강한 기준선 · ours Δ · ours 가드\n')
        L.append('| 조건 | 가장 강한 기준선 | 기준선 최고 SKIN | ours 최고 SKIN · 가드 | Δ (기준선 − ours) | pace-d50 · pace-perm |')
        L.append('|---|---|---:|---|---:|---|')
        for cid, e in tb.items():
            if 'conservation_fail' in e:
                L.append(f'| {cid} | 보존 실패 | | | | |')
                continue
            st = e['stats']
            s_ = e['strongest']
            o = st.get('ours')
            L.append(f"| {cid} | {s_ or '부적격'} | {f(st[s_]['max_skin']) if s_ else '—'} | {f(o['max_skin'])} · {g(o)} | "
                     f"{f(e['j2']['delta']) if e.get('j2') else '—'} | {f(st['pace-d50']['max_skin'])} {g(st['pace-d50'])} · {f(st['pace-perm']['max_skin'])} {g(st['pace-perm'])} |")
    return '\n'.join(L) + '\n'


def holdout_tables(S):
    L = []
    main = S['tables']['v22']
    L.append('### ② 24 조건 — 주 모형 v2.2 (홀드아웃 seed 51–60, 1회 · seed 중앙)\n')
    L.append('| 조건 | 가장 강한 기준선 | 기준선 최고 SKIN | ours 최고 SKIN · 가드 | Δ ℃ | (i) BG 미완료 0 · (ii) 창 끝 SKIN | pace-d50 · pace-perm (ours − 대조군) | ref-const · 정규화 차이 | ② 판정 |')
    L.append('|---|---|---:|---|---:|---|---|---|---|')
    for cid, e in main.items():
        if 'conservation_fail' in e:
            L.append(f"| {cid} | 보존 실패 | | | | | | | {e['j2']['label']} |")
            continue
        st = e['stats']
        s_ = e['strongest']
        o = st['ours']
        j = e['j2']
        ctr = ' · '.join(f"{c}: {f(v['ours_minus_control'])} {'(가드 ✓)' if v['guard'] else '(가드 ✗)'}" if isinstance(v, dict) else f'{c}: {v}'
                         for c, v in (j.get('controls') or {}).items())
        rc = st.get('ref-const')
        nd = e.get('norm_diff') or {}
        lab = j['label'] + ((' — ' + '; '.join(j['notes'])) if j.get('notes') else '')
        L.append(f"| {cid} | {s_ or '부적격'} | {f(st[s_]['max_skin']) if s_ else '—'} | {f(o['max_skin'])} · {g(o)} | {f(j.get('delta'))} | "
                 f"{f(j.get('residual_i')) if s_ else '—'} · {f(o['end_skin'], 1)} vs {f(st[s_]['end_skin'], 1) if s_ else '—'} | {ctr} | "
                 f"{(f(rc['max_skin']) + ' ' + g(rc)) if rc else '미실행'} · {f(nd.get('value'), 2) if nd.get('value') is not None else ('null (분모 ' + f(nd.get('denominator_c')) + ')' if nd.get('denominator_c') is not None else '—')} | {lab} |")
    L.append(f"\n- ② 가져옴 조건 수 (주 모형): **{S['n_take']}** · 결론 행 (주 모형): {S['conclusion_row_main']}")
    for m, r in S['conclusion_row_sensitivity'].items():
        L.append(f'- 민감도 {m}: {r}')
    for m in ('v21', 'v2_t0.3', 'v2_t0.75'):
        tb = S['tables'][m]
        L.append(f'\n### 민감도 {m} — ② (ref-const 없음)\n')
        L.append('| 조건 | 가장 강한 기준선 | Δ ℃ | ours 가드 | ② 판정 |')
        L.append('|---|---|---:|---|---|')
        for cid, e in tb.items():
            j = e.get('j2') or {}
            o = (e.get('stats') or {}).get('ours') or {}
            L.append(f"| {cid} | {e.get('strongest') or '부적격'} | {f(j.get('delta'))} | {g(o) if o else '—'} | {j.get('label')} |")
    return '\n'.join(L) + '\n'


CSV_COLS = ('model', 'cond', 'seed', 'key', 'kind', 'guard_a', 'fg.planned', 'fg.on_time', 'fg.late', 'fg.unfinished', 'fg.p95_all',
            'fg.p95_completed', 'bg.planned', 'bg.on_time', 'bg.late', 'bg.unfinished', 'bg.planned_inf', 'bg.completed_inf', 'bg.on_time_rate',
            'thermal.max_skin', 'thermal.t38_s', 'thermal.t40_s', 'thermal.t42_s', 'thermal.throttle_s', 'thermal.exec_s',
            'thermal.throughput_inf_s', 'thermal.end_skin', 'completion.bg_last_completion', 'completion.bursts_s', 'duty_cmd_mean',
            'ref_feasible', 'perm_multiset_equal', 'conservation_ok', 'error')


def _get(r, path):
    cur = r
    for k in path.split('.'):
        if not isinstance(cur, dict) or k not in cur:
            return ''
        cur = cur[k]
    if isinstance(cur, float):
        return 'inf' if math.isinf(cur) else f'{cur:.6g}'
    if isinstance(cur, list):
        return ';'.join('' if x is None else (f'{x:.6g}' if isinstance(x, float) else str(x)) for x in cur)
    return '' if cur is None else str(cur)


def to_csv(src, dst):
    import csv
    with open(src, encoding='utf-8') as fi, open(dst, 'w', newline='', encoding='utf-8') as fo:
        w = csv.writer(fo)
        w.writerow(CSV_COLS)
        for line in fi:
            if line.strip():
                r = json.loads(line)
                w.writerow([_get(r, c) for c in CSV_COLS])
    print('wrote', dst)


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    which = sys.argv[1]
    if which == 'csv':
        for stem in sys.argv[2:]:
            to_csv(os.path.join(OUT, f'{stem}.jsonl'), os.path.join(OUT, f'{stem}.csv'))
        return 0
    S = json.load(open(os.path.join(OUT, f'{which}_summary.json'), encoding='utf-8'))
    md = dev_tables(S) if which == 'dev' else holdout_tables(S)
    p = os.path.join(OUT, f'{which}_tables.md')
    open(p, 'w', encoding='utf-8').write(md)
    print('wrote', p)
    return 0


if __name__ == '__main__':
    sys.exit(main())
