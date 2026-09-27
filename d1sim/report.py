"""Turn run_compare CSVs into the markdown tables of SIM_V0_결과 (numbers only from the CSV files).

  py -m d1sim.report --main d1sim/out/main_v0.csv --sweep d1sim/out/sweep_v0.csv --select d1sim/out/tune_select.json \
      --out d1sim/out/report_v0.md --json d1sim/out/report_v0.json
Rules applied here are the pre-registered ones (sim/시뮬_사전등록_v0.md §3, §6, §7).
"""
from __future__ import annotations

import argparse
import json
import math
import statistics as st

from d1sim.run_compare import VARIANTS, cell_stats, fnum, guards_ok, load

HEAD = '> **탐색 — 구조 변형 조건부, 검증 전.** 개발 seed 1–10, 합성 워크로드, horizon 600 s. 에너지는 잠정(절대 정확도 미인증).'


def med(d, k):
    v = [fnum(r[k]) for r in d.values()]
    v = [x for x in v if x is not None]
    return st.median(v) if v else None


def cv(d, k):
    v = [fnum(r[k]) for r in d.values()]
    if any(x is None or math.isinf(x) for x in v) or len(v) < 2:
        return None
    m = st.mean(v)
    return st.pstdev(v) / m if m else None


def fmt(x, nd=3):
    if x is None:
        return '—'
    if isinstance(x, float) and math.isinf(x):
        return '∞'
    return f'{x:.{nd}f}' if isinstance(x, float) else str(x)


def compare(c, b):
    """Pre-registered margin rule §6: ratio of seed medians <= 1 - m, m = max(5 %, 2 CV_base), and >= 8/10 paired wins."""
    mc, mb = med(c, 'fg_p95_s'), med(b, 'fg_p95_s')
    cvb = cv(b, 'fg_p95_s')
    m = max(0.05, 2 * cvb) if cvb is not None else 0.05
    wins = sum(1 for s in c if fnum(c[s]['fg_p95_s']) < fnum(b[s]['fg_p95_s']))
    losses = sum(1 for s in c if fnum(c[s]['fg_p95_s']) > fnum(b[s]['fg_p95_s']))
    if math.isinf(mb):
        ratio = 0.0 if not math.isinf(mc) else 1.0
    else:
        ratio = mc / mb if mb else None
    better = ratio is not None and ratio <= 1 - m and wins >= 8
    worse = ratio is not None and ratio >= 1 + m and losses >= 8
    return dict(ratio=ratio, margin=m, wins=wins, losses=losses,
                verdict='낮음(마진 통과)' if better else '높음(마진 통과)' if worse else '차이 없음')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--main'); ap.add_argument('--sweep'); ap.add_argument('--select')
    ap.add_argument('--out'); ap.add_argument('--json')
    a = ap.parse_args()
    rows = load(a.main)
    cells = cell_stats(rows)
    sel = json.load(open(a.select, encoding='utf-8'))
    pols = []
    for r in rows:
        if r['policy'] not in pols:
            pols.append(r['policy'])
    ours = [p for p in pols if p.startswith('ours')]
    out, J = [HEAD, ''], dict(cells={}, compare={}, sweep={})
    out.append(f"재현: `py -m d1sim.run_compare main --select d1sim/out/tune_select.json --out d1sim/out/main_v0.csv` → "
               f"`py -m d1sim.report ...` (이 파일 머리 docstring). 보존 검사 실패 런: "
               f"{sum(r['conservation_ok'] != 'True' for r in rows)} / {len(rows)}")
    out.append('')
    out.append(f"선택된 설정: 손 조정 = `{sel['hand']['best_feasible']}` · 무작위 = `{sel['random']['best_feasible']}` "
               f"(가드 무시 최선: {sel['hand']['best_ignoring_guards']} / {sel['random']['best_ignoring_guards']})")
    for sc in ('S0', 'S1', 'S2'):
        out += ['', f'### {sc}', '', HEAD, '']
        out.append('| 변형 | 정책 | FG p95 (s) | FG p50 | 기한 위반율 | BG 완료율 | 처리량 (추론/s) | 스로틀 s GPU/NPU/CPU4 | 첫 스로틀 (s) | status≥2 (s) | 최고 SKIN | 에너지 J (잠정) | 가드 |')
        out.append('|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---|')
        for vid in VARIANTS:
            b = cells.get(('npumgr', sc, vid, '{}'))
            for p in pols:
                c = cells.get((p, sc, vid, '{}'))
                if c is None:
                    continue
                g = '기준' if p == 'npumgr' else ('OK' if (b and sc != 'S0' and guards_ok(c, b)) else ('—' if sc == 'S0' else '위반'))
                thr = '/'.join(fmt(med(c, f'throttle_s_{r}'), 0) for r in ('GPU', 'NPU', 'CPU4'))
                out.append(f"| {vid} | {p} | {fmt(med(c, 'fg_p95_s'))} | {fmt(med(c, 'fg_p50_s'))} | "
                           f"{fmt(med(c, 'deadline_violation_rate'))} | {fmt(med(c, 'bg_completion'))} | "
                           f"{fmt(med(c, 'throughput_inf_s'), 1)} | {thr} | {fmt(med(c, 'first_throttle_s'), 0)} | "
                           f"{fmt(med(c, 'status2_s'), 0)} | {fmt(med(c, 'peak_skin_c'), 2)} | {fmt(med(c, 'energy_j'), 0)} | {g} |")
                J['cells'][f'{sc}/{vid}/{p}'] = {k: med(c, k) for k in ('fg_p95_s', 'fg_p50_s', 'deadline_violation_rate', 'bg_completion',
                                                                       'throughput_inf_s', 'throttle_s_GPU', 'throttle_s_NPU',
                                                                       'throttle_s_CPU4', 'first_throttle_s', 'status2_s',
                                                                       'peak_skin_c', 'energy_j')}
    out += ['', '### ours vs npumgr — 채택 마진 규칙 (§6)', '', HEAD, '',
            '| 시나리오 | 변형 | 정책 | p95 비 (seed 중앙) | 마진 m | 쌍대 이김/짐 (10) | 판정 | 가드 |', '|---|---|---|---:|---:|---|---|---|']
    for sc in ('S1', 'S2'):
        for vid in VARIANTS:
            b = cells[('npumgr', sc, vid, '{}')]
            for p in ours:
                c = cells[(p, sc, vid, '{}')]
                r = compare(c, b)
                J['compare'][f'{sc}/{vid}/{p}'] = dict(r, guards=guards_ok(c, b))
                out.append(f"| {sc} | {vid} | {p} | {fmt(r['ratio'])} | {fmt(r['margin'])} | {r['wins']}/{r['losses']} | "
                           f"{r['verdict']} | {'OK' if guards_ok(c, b) else '위반'} |")
    if a.sweep:
        srows = load(a.sweep)
        sc_ = cell_stats(srows)
        out += ['', '### 민감도 스윕 (V2·V4) — 기준값 대비 FG p95 · BG 완료율 · 스로틀 시간 (seed 중앙)', '', HEAD, '',
                '| 시나리오 | 변형 | 정책 | 스윕 | FG p95 | BG 완료율 | 기한 위반율 | 스로틀 s 합 | 기준값과 소수점까지 같음? |',
                '|---|---|---|---|---:|---:|---:|---:|---|']
        for (p, sc, vid, ex), c in sorted(sc_.items()):
            base = cells.get((p, sc, vid, '{}'))
            same = None
            if base is not None:
                same = all(abs((fnum(c[s][k]) or 0) - (fnum(base[s][k]) or 0)) < 1e-12 or
                           (fnum(c[s][k]) == fnum(base[s][k]))
                           for s in c for k in ('fg_p95_s', 'bg_completion', 'throttle_s_NPU', 'throttle_s_GPU', 'energy_j'))
            tsum = st.median(sum(fnum(r[f'throttle_s_{x}']) for x in ('GPU', 'NPU', 'CPU4')) for r in c.values())
            J['sweep'][f'{sc}/{vid}/{p}/{ex}'] = dict(fg_p95=med(c, 'fg_p95_s'), bg=med(c, 'bg_completion'), same_as_base=same)
            out.append(f"| {sc} | {vid} | {p} | `{ex}` | {fmt(med(c, 'fg_p95_s'))} | {fmt(med(c, 'bg_completion'))} | "
                       f"{fmt(med(c, 'deadline_violation_rate'))} | {fmt(tsum, 0)} | {'**같음 → 미작동**' if same else '다름'} |")
    open(a.out, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    json.dump(J, open(a.json, 'w', encoding='utf-8'), indent=1, default=str)
    print('wrote', a.out)


if __name__ == '__main__':
    main()
