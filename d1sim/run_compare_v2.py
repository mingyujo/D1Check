"""run_compare_v2.py — policy x scenario x (v2 variant) x seed runner on throttle model v2 (SimV2). Pre-registration:
sim/시뮬_사전등록_v2.md (mirror d1sim/docs/). v0 env/policies/run_compare are imported unchanged.

  py -m d1sim.run_compare_v2 s0    --out d1sim/out/s0_v2.csv      # S0 control first (heat must not change the result)
  py -m d1sim.run_compare_v2 main  --out d1sim/out/main_v2.csv    # S0·S1·S2 x W1..W4 x policies x dev seeds
  py -m d1sim.run_compare_v2 report --main d1sim/out/main_v2.csv  # cell table + flip-axis verdict -> d1sim/out/report_v2.json/.md
Deterministic (fixed seeds). Parallel over processes only.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics as st
import sys
from concurrent.futures import ProcessPoolExecutor

from d1sim import run_compare as rc0
from d1sim.env_v2 import SimV2
from d1sim.kpi import conservation, kpis
from d1sim.policies import NpuManagerApprox, prio_head
from d1sim.profile import Profile
from d1sim.workload import DEV_SEEDS, scenario

VARIANTS = {'W1': dict(theta_npu=0.3, cooling='v2'), 'W2': dict(theta_npu=0.75, cooling='v2'),
            'W3': dict(theta_npu=0.3, cooling='c1'), 'W4': dict(theta_npu=0.75, cooling='c1')}
T_TH_V2 = 37.2          # v2 GPU CompiledModel gate T_on (SKIN) — ours-v0's "T_th" input [P-fit throttle_v2_GPU_compiledmodel.json]
OURS = {'hand': (0.0, 10.0, 2.0), 'random': (-0.153, 12.711, 2.422)}   # v0-selected settings, no retuning (prereg v2 §0)


class PacedNpuManager(NpuManagerApprox):
    """npumgr + fixed BG pacing: after a BG chunk that executed for e seconds, hold BG for e*(1/duty - 1) seconds."""
    name = 'pacing-50'

    def __init__(self, duty=0.5):
        super().__init__()
        self.duty = duty
        self.hold_until = -1.0
        self.last_bg = None       # (id, start)

    def decide(self, obs):
        # detect the end of the last BG chunk: it is no longer in the queue and we are being asked again
        if self.last_bg is not None and all(q['id'] != self.last_bg[0] for q in obs['queue']) and obs['loaded'] is not None:
            e = obs['t'] - self.last_bg[1]
            self.hold_until = obs['t'] + e * (1.0 / self.duty - 1.0)
            self.last_bg = None
        hot = obs['status'] >= 2
        if hot and not self.unloaded and obs['loaded'] is not None:
            self.unloaded = True
            return ('unload',)
        if not hot:
            self.unloaded = False
        block_bg = hot or obs['t'] < self.hold_until - 1e-9
        q = prio_head(obs['queue'], allow=(lambda x: x['cls'] != 'BG') if block_bg else (lambda x: True))
        if q is None:
            wake = self.hold_until if (obs['t'] < self.hold_until and not hot) else obs['t'] + self.recheck_s
            return ('wait', max(wake, obs['t'] + 1e-3))
        if q['cls'] == 'BG':
            self.last_bg = (q['id'], obs['t'])
        return ('dispatch', q['id'], self.r)


def make_policy(spec):
    if spec[0] == 'pacing':
        return PacedNpuManager(spec[1])
    return rc0.make_policy(spec, T_TH_V2)


def label(spec):
    return f'pacing-{int(spec[1] * 100)}' if spec[0] == 'pacing' else rc0.label(spec)


def one(job):
    spec, sc, vid, seed, tag = job
    P = Profile()
    reqs = scenario(sc, seed, P)
    rec = SimV2(P, reqs, VARIANTS[vid]).run(make_policy(spec))
    k = kpis(rec)
    thr = [t for t, _, sg, sn, sc4, _ in rec.trace if min(sg, sn, sc4) < 1 / 1.1]
    k['first_throttle_s'] = thr[0] if thr else None
    bad = conservation(rec)
    row = dict(tag=tag, policy=label(spec), scenario=sc, variant=vid, extra='{}', seed=seed, conservation_ok=not bad, conservation=';'.join(bad[:3]))
    row.update({x: k[x] for x in rc0.KEEP})
    return row


def run_jobs(jobs, out):
    rows = []
    with ProcessPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) - 2)) as ex:
        for i, r in enumerate(ex.map(one, jobs, chunksize=1)):
            rows.append(r)
            if i % 50 == 0:
                print(f'{i}/{len(jobs)}', flush=True)
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print('wrote', out, len(rows), 'conservation failures', sum(not r['conservation_ok'] for r in rows))


SPECS = [('fixed', 'NPU'), ('shortest',), ('npumgr',), ('pacing', 0.5), ('ours', OURS['hand']), ('ours', OURS['random'])]


def cmd_s0(a):
    run_jobs([(s, 'S0', vid, seed, 's0') for s in SPECS for vid in VARIANTS for seed in DEV_SEEDS], a.out)


def cmd_main(a):
    # S0 is run by `s0` (d1sim/out/s0_v2.csv) and merged in `report`; main covers S1·S2. --variants narrows the axis set
    # (P1c 18:4x: the full W1..W4 run was killed by the tool's 30-min background limit at 450/480 -> W1·W2 only, W3·W4 -> P1d)
    vids = a.variants or list(VARIANTS)
    run_jobs([(s, sc, vid, seed, 'main') for s in SPECS for sc in ('S1', 'S2') for vid in vids for seed in DEV_SEEDS], a.out)


def cmd_report(a):
    rows = rc0.load(a.main)
    s0 = os.path.join(os.path.dirname(a.main), 's0_v2.csv')
    if os.path.exists(s0):
        rows = rc0.load(s0) + rows
    cells = rc0.cell_stats(rows)
    pols = sorted({r['policy'] for r in rows})
    med = lambda d, k: st.median(rc0.fnum(r[k]) for r in d.values())  # noqa: E731
    out = dict(header='탐색 — 조건부, 검증 전 (개발 seed 1–10, 합성 워크로드, horizon 600 s, 스로틀 모형 v2 V2-Lb 42338e7 — 밤 1004 홀드아웃 전)', cells={}, flip={})
    lines = [f"> **{out['header']}**", '', '| 시나리오 | 변형 | 정책 | FG p95 (s) | FG p50 | 기한 위반율 | BG 완료율 | 처리량 | 스로틀 s GPU/NPU/CPU4 | 첫 스로틀 | status≥2 s | 최고 SKIN | 에너지 J (잠정) | npumgr 대비 비 | 가드 | 마진 승리 |',
             '|---|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|']
    for sc in ('S0', 'S1', 'S2'):
        for vid in VARIANTS:
            if not any(k[1] == sc and k[2] == vid for k in cells):
                continue
            b = cells.get(('npumgr', sc, vid, '{}'))
            cv = (st.pstdev([rc0.fnum(r['fg_p95_s']) for r in b.values()]) / med(b, 'fg_p95_s')) if b and med(b, 'fg_p95_s') not in (0, math.inf) else 0.0
            m = max(0.05, 2 * cv)
            ranked = []
            for p in pols:
                c = cells.get((p, sc, vid, '{}'))
                if not c:
                    continue
                rt = rc0.ratio(c, b) if b else None
                g = rc0.guards_ok(c, b) if b else None
                pair = sum(1 for s_ in c if s_ in b and rc0.fnum(c[s_]['fg_p95_s']) < rc0.fnum(b[s_]['fg_p95_s'])) if b else None
                win = bool(b and rt is not None and rt <= 1 - m and pair >= 8 and g) if p != 'npumgr' else None
                thr = '/'.join(f"{med(c, k):.0f}" for k in ('throttle_s_GPU', 'throttle_s_NPU', 'throttle_s_CPU4'))
                ft = [rc0.fnum(r['first_throttle_s']) for r in c.values() if r['first_throttle_s'] not in ('', 'None')]
                row = dict(policy=p, fg_p95=med(c, 'fg_p95_s'), fg_p50=med(c, 'fg_p50_s'), dvr=med(c, 'deadline_violation_rate'),
                           bg=(med(c, 'bg_completion') if rc0.fnum(next(iter(c.values()))['bg_completion']) is not None else None),
                           thru=med(c, 'throughput_inf_s'), throttle=thr, first_throttle=(st.median(ft) if ft else None), st2=med(c, 'status2_s'),
                           peak=med(c, 'peak_skin_c'), energy=med(c, 'energy_j'), ratio=rt, guards=g, pair_wins=pair, margin=m, win=win)
                ranked.append(row)
                lines.append(f"| {sc} | {vid} | {p} | {row['fg_p95']:.3f} | {row['fg_p50']:.3f} | {row['dvr']:.3f} | {('—' if row['bg'] is None else f'{row[chr(98)+chr(103)]:.3f}')} | {row['thru']:.1f} | {thr} | "
                             f"{('—' if row['first_throttle'] is None else f'{row[chr(102)+chr(105)+chr(114)+chr(115)+chr(116)+chr(95)+chr(116)+chr(104)+chr(114)+chr(111)+chr(116)+chr(116)+chr(108)+chr(101)]:.0f}')} | {row['st2']:.0f} | {row['peak']:.2f} | {row['energy']:.0f} | "
                             f"{('기준' if p == 'npumgr' else f'{rt:.3f}')} | {('기준' if p == 'npumgr' else ('✓' if g else '✗'))} | {('—' if win is None else ('✓' if win else '—'))} |")
            ranked.sort(key=lambda r: (r['fg_p95'], r['policy']))
            out['cells'][f'{sc}/{vid}'] = dict(rank=[r['policy'] for r in ranked], rows=ranked, margin=m)
    # flip-axis verdict (prereg v2 §3): rank 1·2 or guard pass changes between W1..W4 in any S1/S2 cell
    for axis, pairs in (('theta', [('W1', 'W2'), ('W3', 'W4')]), ('cooling', [('W1', 'W3'), ('W2', 'W4')])):
        flips, identical = [], True
        for sc in ('S1', 'S2'):
            for a_, b_ in pairs:
                if f'{sc}/{a_}' not in out['cells'] or f'{sc}/{b_}' not in out['cells']:
                    flips.append(f'{sc}: {a_}/{b_} 미실행')
                    continue
                ca, cb = out['cells'][f'{sc}/{a_}'], out['cells'][f'{sc}/{b_}']
                if ca['rank'][:2] != cb['rank'][:2]:
                    flips.append(f'{sc}: {a_} {ca["rank"][:2]} vs {b_} {cb["rank"][:2]}')
                ga = {r['policy']: r['guards'] for r in ca['rows']}; gb = {r['policy']: r['guards'] for r in cb['rows']}
                if ga != gb:
                    flips.append(f'{sc}: guards {a_} {ga} vs {b_} {gb}')
                va = [round(r['fg_p95'], 3) for r in sorted(ca['rows'], key=lambda r: r['policy'])]
                vb = [round(r['fg_p95'], 3) for r in sorted(cb['rows'], key=lambda r: r['policy'])]
                identical = identical and va == vb
        real = [f for f in flips if not f.endswith('미실행')]
        ran = any(not f.endswith('미실행') for f in flips) or len([f for f in flips if f.endswith('미실행')]) < 2 * len(pairs)
        out['flip'][axis] = dict(verdict=('미실행 (P1d)' if not ran else ('뒤집는 축' if real else ('미작동 (소수점 셋째 자리까지 같음)' if identical else '순위·가드 불변 (값은 다름)'))), detail=flips)
    lines += ['', '## 뒤집는 축 판정', *[f"- **{k}**: {v['verdict']}" + (''.join(f'\n  - {d}' for d in v['detail']) if v['detail'] else '') for k, v in out['flip'].items()]]
    json.dump(out, open(os.path.join(os.path.dirname(a.main), 'report_v2.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    open(os.path.join(os.path.dirname(a.main), 'report_v2.md'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('\n'.join(lines[-8:]))
    print('wrote report_v2.json/.md')


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd')
    ap.add_argument('--out')
    ap.add_argument('--main')
    ap.add_argument('--variants', nargs='*')
    a = ap.parse_args()
    {'s0': cmd_s0, 'main': cmd_main, 'report': cmd_report}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
