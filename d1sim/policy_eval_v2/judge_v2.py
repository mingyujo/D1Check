"""judge_v2.py — decisions of sim/정책비교_사전등록_v2.md §3 · §4 · §5 (per condition, over seeds). Pure functions on kpi_v2 rows.

Screening (§5-6, fixed-prio on development seeds 1–10 of the condition; sample sd ddof = 1):
  FG P95 (relative):  CV = sd/mean -> m_FG = max(0.05, 2 CV); mean 0 · any +inf · any null · fewer than 2 values -> CV null -> 0.05
  BG on-time rate (0–1, %p): m_BG = max(5 %p, 2 sd * 100 %p); sd null -> 5 %p        throughput: m = max(0.05, 2 CV) (descriptive)
  ℃ metrics: Δ 1.0 ℃ · s metrics: 60 s (no CV / % on Celsius). Seeds = arrival-sample repeats, not device sessions.
P1f 가 정함 (결과 전): "seed 중앙" = per-policy median over the condition's seeds, Δ = median(A) - median(B); guard (b) on medians
  (+inf allowed: inf <= inf); guard (a) must hold in EVERY seed; margins for the holdout come from the development seeds.
Strongest baseline (§4): among fixed-prio / npumgr meeting (a) in the condition, lowest median max SKIN; |Δ| < 0.05 ℃ -> fixed-prio.
  Neither meets (a) -> "기준선 서비스 부적격" (kept in the table, excluded from ②; ① not judged).
① (dev): strongest - ref-const >= 1.0 ℃ and ref-const passes (a)+(b) -> "제한 참조 대비 차이 있음".
② (holdout): ours (a)+(b) · strongest - ours >= 1.0 ℃ · §5-5 (i) ours BG unfinished 0 in every seed (ii) median end SKIN of ours <=
  strongest + 1.0 ℃ · no (a)+(b)-passing control (4a · 4b) >= 1.0 ℃ below ours -> "가져옴"; a passing control within 1.0 ℃ of ours
  that also beats the strongest baseline by >= 1.0 ℃ -> "가족 대조군도 같은 이득 — 규칙 고유 효과라고 쓰지 않는다" (added note).
Reference-normalised difference (§3-6): (strongest - ours) / (strongest - ref-const); denominator <= 1.0 ℃ -> null + raw difference.
"""
from __future__ import annotations

import math
import statistics

SEL_C = 1.0
TIE_C = 0.05
BASELINES = ('fixed-prio', 'npumgr')
CONTROLS = ('pace-d50', 'pace-perm')


def _finite(xs):
    return all(x is not None and not (isinstance(x, float) and math.isinf(x)) for x in xs)


def cv_of(xs):
    if len(xs) < 2 or not _finite(xs):
        return None
    m = statistics.mean(xs)
    if m == 0:
        return None
    return statistics.stdev(xs) / m


def margins(base_rows):
    fg = [r['fg']['p95_all'] for r in base_rows]
    bg = [r['bg']['on_time_rate'] for r in base_rows]
    thr = [r['thermal']['throughput_inf_s'] for r in base_rows]
    cv_fg = cv_of(fg)
    sd_bg = statistics.stdev(bg) if (len(bg) >= 2 and _finite(bg)) else None
    cv_thr = cv_of(thr)
    return dict(m_FG=0.05 if cv_fg is None else max(0.05, 2.0 * cv_fg), cv_FG=cv_fg,
                m_BG_pp=5.0 if sd_bg is None else max(5.0, 2.0 * sd_bg * 100.0), sd_BG=sd_bg,
                m_thr=0.05 if cv_thr is None else max(0.05, 2.0 * cv_thr), n=len(base_rows))


def med(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    return statistics.median(sorted(xs))


def policy_stats(rows):
    return dict(n=len(rows), guard_a=all(r['guard_a'] for r in rows), guard_a_fail_seeds=[r['seed'] for r in rows if not r['guard_a']],
                max_skin=med([r['thermal']['max_skin'] for r in rows]), end_skin=med([r['thermal']['end_skin'] for r in rows]),
                t38=med([r['thermal']['t38_s'] for r in rows]), t40=med([r['thermal']['t40_s'] for r in rows]),
                t42=med([r['thermal']['t42_s'] for r in rows]), throttle=med([r['thermal']['throttle_s'] for r in rows]),
                throughput=med([r['thermal']['throughput_inf_s'] for r in rows]),
                fg_p95=med([r['fg']['p95_all'] for r in rows]), bg_on_rate=med([r['bg']['on_time_rate'] for r in rows]),
                bg_unfinished_total=sum(r['bg']['unfinished'] for r in rows), fg_late_total=sum(r['fg']['late'] for r in rows),
                bg_late_total=sum(r['bg']['late'] for r in rows), fg_unfinished_total=sum(r['fg']['unfinished'] for r in rows),
                duty_cmd_mean=med([r.get('duty_cmd_mean') for r in rows]),
                bg_completion_s=med([r['completion']['bg_last_completion'] for r in rows]),
                conservation_ok=all(r['conservation_ok'] for r in rows))


def guard_b(ps, base, m):
    fg_ok = ps['fg_p95'] is not None and base['fg_p95'] is not None and ps['fg_p95'] <= base['fg_p95'] * (1.0 + m['m_FG']) + 1e-12
    bg_ok = (ps['bg_on_rate'] is not None and base['bg_on_rate'] is not None
             and ps['bg_on_rate'] * 100.0 >= base['bg_on_rate'] * 100.0 - m['m_BG_pp'] - 1e-9)
    return bool(fg_ok and bg_ok), dict(fg=bool(fg_ok), bg=bool(bg_ok))


def guards(S, m):
    """S = {policy: policy_stats}; adds guard_b / guard (a and b) using fixed-prio as the relative reference."""
    base = S['fixed-prio']
    for p, ps in S.items():
        gb, det = guard_b(ps, base, m)
        ps['guard_b'], ps['guard_b_detail'] = gb, det
        ps['guard'] = bool(ps['guard_a'] and gb)
    return S


def strongest_baseline(S):
    c = [p for p in BASELINES if p in S and S[p]['guard_a']]
    if not c:
        return None
    if len(c) == 1:
        return c[0]
    a, b = S['fixed-prio']['max_skin'], S['npumgr']['max_skin']
    if abs(a - b) < TIE_C - 1e-12:
        return 'fixed-prio'
    return 'fixed-prio' if a < b else 'npumgr'


def judge_1(S, strongest, ref_key='ref-const'):
    if strongest is None:
        return dict(label='기준선 서비스 부적격', delta=None)
    ref = S.get(ref_key)
    if ref is None:
        return dict(label='ref-const 없음 (미실행)', delta=None)
    d = round(S[strongest]['max_skin'] - ref['max_skin'], 6)
    if not ref['guard']:
        return dict(label='ref-const 가드 실패 — 차이 판정 안 함', delta=d)
    return dict(label='제한 참조 대비 차이 있음' if d >= SEL_C - 1e-9 else '차이 관측 안 됨', delta=d)


def judge_2(S, strongest, ours_key='ours'):
    if strongest is None:
        return dict(label='기준선 서비스 부적격 (② 판정에서 뺌)', delta=None, take=False)
    o = S[ours_key]
    d = round(S[strongest]['max_skin'] - o['max_skin'], 6)
    res = dict(delta=d, guard=o['guard'], guard_a=o['guard_a'], guard_b=o['guard_b'], take=False,
               residual_i=o['bg_unfinished_total'] == 0,
               residual_ii=(o['end_skin'] is not None and o['end_skin'] <= S[strongest]['end_skin'] + SEL_C + 1e-9),
               controls={}, notes=[])
    lower_ctrl, same_ctrl = [], []
    for c in CONTROLS:
        if c not in S:
            res['controls'][c] = '미실행'
            continue
        cs = S[c]
        dc = round(o['max_skin'] - cs['max_skin'], 6)
        res['controls'][c] = dict(guard=cs['guard'], ours_minus_control=dc, delta_vs_strongest=round(S[strongest]['max_skin'] - cs['max_skin'], 6))
        if cs['guard'] and dc >= SEL_C - 1e-9:
            lower_ctrl.append(c)
        elif cs['guard'] and abs(dc) < SEL_C and S[strongest]['max_skin'] - cs['max_skin'] >= SEL_C - 1e-9:
            same_ctrl.append(c)
    if not o['guard']:
        res['label'] = '가드 실패'
    elif d < SEL_C - 1e-9:
        res['label'] = '기준 안 (Δ < 1.0 ℃)'
    elif not (res['residual_i'] and res['residual_ii']):
        res['label'] = '창 밖으로 밀린 일·잔열 — 절감으로 세지 않는다'
    elif lower_ctrl:
        res['label'] = '대조군이 ours 보다 1.0 ℃ 이상 낮음 (' + ' · '.join(lower_ctrl) + ')'
    else:
        res['label'] = '가져옴'
        res['take'] = True
        if same_ctrl:
            res['notes'].append('가족 대조군도 같은 이득 — 규칙 고유 효과라고 쓰지 않는다 (' + ' · '.join(same_ctrl) + ')')
    return res


def norm_diff(S, strongest, ours_key='ours', ref_key='ref-const'):
    if strongest is None or ref_key not in S or ours_key not in S:
        return dict(value=None, raw_c=None, denominator_c=None)
    den = S[strongest]['max_skin'] - S[ref_key]['max_skin']
    raw = S[strongest]['max_skin'] - S[ours_key]['max_skin']
    return dict(value=(raw / den) if den > SEL_C + 1e-9 else None, raw_c=round(raw, 6), denominator_c=round(den, 6))


def conclusion_row(j1_labels, j2_takes):
    """Overall row of §3 table from the per-condition ① (dev) labels and ② (holdout) "가져옴" flags (P1f 가 정함 (결과 전)):
    any ② 가져옴 -> "1행 후보 — ③ V3 · ④ 전이 판정 전 (지금은 4행: 전이 미확인 — 폰 효과 결론 보류)";
    else any ① 차이 있음 -> 2행; else -> 3행."""
    if any(j2_takes):
        return '1행 후보 — ③ V3 · ④ 전이 판정 전 (지금은 4행: 전이 미확인이라 폰 효과 결론 보류)'
    if any(lb == '제한 참조 대비 차이 있음' for lb in j1_labels):
        return '2행'
    return '3행'


def window_flag(o, comp):
    """§5-5 marker for one policy vs a comparator (policy_stats): BG unfinished or end SKIN > comparator + 1.0 ℃."""
    pushed = o['bg_unfinished_total'] > 0 or (o['end_skin'] is not None and comp['end_skin'] is not None and o['end_skin'] > comp['end_skin'] + SEL_C + 1e-9)
    return '창 밖으로 밀린 일·잔열 — 절감으로 세지 않는다' if pushed else None
