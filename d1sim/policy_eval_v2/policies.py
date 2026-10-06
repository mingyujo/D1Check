"""policies.py — policy ladder of sim/정책비교_사전등록_v2.md §4 (1 fixed-prio · 2 npumgr · 3 ours · 4a pace-d50 · 4b pace-perm · 5 ref-const).

Common duty rule (P1f 가 정함 (결과 전) — v1 §4 "duty 위상 통일"): global 10 s periods from t = 0; with duty d a BG chunk may START only
inside the on-window [10k, 10k + d/10 s) (it then runs to completion — chunks are not preempted); d = 100 = always; d = 0 = never.
FG is dispatched first whenever queued, regardless of the window (FG 선점 at chunk boundaries). Policies see the FG queue + BG head.
`cmd` = commanded duty per period (first decision with BG queued in that period) — the 10 s duty timeline.
"""
from __future__ import annotations

import itertools
import math
import random

from d1sim.policies import NpuManagerApprox
from d1sim.policy_eval_v2.sim import PERIOD_S, R0, RESIDUE

DUTIES = (10, 25, 50, 75, 100)
REF_COMBOS = tuple(itertools.product(DUTIES, repeat=3))       # 5^3 = 125 (bursts 0, 1, 2)
OURS_GRID = tuple((m, o) for m in (0.0, 30.0, 60.0) for o in (0.0, -0.5))   # 등록 v1 §4 튜닝 6 설정


def period_of(t):
    return int(math.floor(t / PERIOD_S + 1e-9))


def _overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


class DutyPolicy:
    name = 'duty'

    def __init__(self, res):
        self.res = res
        self.cmd = {}

    def duty(self, obs, k):
        raise NotImplementedError

    def decide(self, obs):
        fg = obs['fg_head']
        if fg is not None:
            return ('dispatch', fg['id'], self.res)
        bg = obs['bg_head']
        if bg is None:
            return ('wait', None)
        t = obs['t']
        k = period_of(t)
        d = self.duty(obs, k)
        self.cmd.setdefault(k, d)
        if d >= 100 or (d > 0 and t - k * PERIOD_S < PERIOD_S * d / 100.0 - 1e-9):
            return ('dispatch', bg['id'], self.res)
        return ('wait', (k + 1) * PERIOD_S)


class FixedPrio(DutyPolicy):
    """1 — 서비스 기준선: BG d100 연속 · FG 선점."""
    name = 'fixed-prio'

    def duty(self, obs, k):
        return 100


class PaceD50(DutyPolicy):
    """4a — 같은 가족 대조군: BG 늘 d50 (기한 무시) · FG 선점."""
    name = 'pace-d50'

    def duty(self, obs, k):
        return 50


class RefConst(DutyPolicy):
    """5 — 제한 상수 duty 참조: 묶음 b 의 청크는 duty combo[b] (FIFO 머리 청크의 묶음)."""

    def __init__(self, res, combo):
        super().__init__(res)
        self.combo = tuple(combo)
        self.name = 'ref-const-' + '-'.join(str(d) for d in self.combo)

    def duty(self, obs, k):
        return self.combo[obs['bg_head']['burst']]


class PacePerm(DutyPolicy):
    """4b — 사후 짝 대조군: ours 가 실제로 명령한 10 s duty 열을 묶음마다 무작위 순열 (같은 multiset), 같은 주기 칸에 재생 ·
    그 밖 주기 = 0 (쉼 — ours 와 같은 위치·길이) · 기한 무시 · FG 선점."""
    name = 'pace-perm'

    def __init__(self, res, schedule):
        super().__init__(res)
        self.schedule = dict(schedule)

    def duty(self, obs, k):
        return self.schedule.get(k, 0)


def perm_schedule(ours_log, seed):
    """ours_log = {period: (duty, burst)} -> {period: permuted duty}; one RNG random.Random(seed + 1000), bursts in order."""
    rng = random.Random(seed + 1000)
    by_b = {}
    for k in sorted(ours_log):
        d, b = ours_log[k]
        by_b.setdefault(b, []).append((k, d))
    sched = {}
    for b in sorted(by_b):
        ks = [k for k, _ in by_b[b]]
        ds = [d for _, d in by_b[b]]
        rng.shuffle(ds)
        sched.update(zip(ks, ds))
    return sched


class NpuMgr:
    """2 — d1sim.policies.NpuManagerApprox 무수정 ("연구용 근사") — 조건의 자원에 같은 규칙."""
    name = 'npumgr'

    def __init__(self, res):
        self.p = NpuManagerApprox(resource=res)
        self.cmd = {}

    def decide(self, obs):
        return self.p.decide(obs)


class Ours(DutyPolicy):
    """3 — 기한 인지 페이싱 (등록 v1 §4 — 정의 그대로, 구현 세부는 P1f 가 정함 (결과 전)):
    at the first decision of each 10 s period with BG queued: the LOWEST d in {10, 25, 50, 75, 100} whose forward prediction finishes
    every queued burst b by D_b - margin_s (FIFO, the burst's own deadline; FG load λ·L0 subtracted from the BG rate); none -> 100.
    Thermal step-down: if the predicted driver temperature (SKIN for every model here) within the next 10 s at that d reaches the
    controller's first arm threshold at load u = d/100 (+ offset_c), take one step lower IF that lower d still finishes every burst
    by D_b (the deadline itself — "기한 우선"; the margin is what the step-down may spend). Predictor = a clone of the simulator's own
    device (perfect-model assumption, 등록 v1 §10) advanced on a 1 s fluid grid (env sub-steps are <= 0.5 s events — an approximation)
    with the same duty windows and the R20 residue state. Only queued work is known (no future arrivals)."""

    def __init__(self, res, margin_s=0.0, offset_c=0.0, lam_fg=0.0):
        super().__init__(res)
        self.margin, self.offset, self.lam = float(margin_s), float(offset_c), float(lam_fg)
        self.name = f'ours(m{margin_s:g},o{offset_c:g})'
        self.k_cur, self.d_cur = None, None
        self.log = {}
        self.n_forward = 0
        self.n_stepdown = 0
        self.n_none = 0

    def duty(self, obs, k):
        if k != self.k_cur:
            self.k_cur = k
            self.d_cur = self._choose(obs)
            self.log[k] = (self.d_cur, obs['bg_head']['burst'])
        return self.d_cur

    def _choose(self, obs):
        sim = obs['sim']
        t0 = obs['t']
        backlog = sim.bg_backlog()
        res_until, armed = sim.residue_state()
        r0 = R0[self.res]
        fg_share = self.lam / r0
        chosen = None
        for d in DUTIES:
            ok, info = self._forward(sim.dev, t0, backlog, d, self.margin, res_until, armed, r0, fg_share)
            if ok:
                chosen = (d, info)
                break
        if chosen is None:
            self.n_none += 1
            return 100
        d, info = chosen
        if info['drv_max10'] >= sim.dev.first_arm_temp(d / 100.0) + self.offset - 1e-9:
            i = DUTIES.index(d)
            if i > 0:
                ok2, _ = self._forward(sim.dev, t0, backlog, DUTIES[i - 1], 0.0, res_until, armed, r0, fg_share)
                if ok2:
                    self.n_stepdown += 1
                    return DUTIES[i - 1]
        return d

    def _forward(self, dev0, t0, backlog, d, margin, res_until, armed, r0, fg_share):
        frac = d / 100.0
        cap = r0 * frac * (1.0 - fg_share)
        cum = 0.0
        targets = []
        for _, rem, D in backlog:
            cum += rem
            if t0 + cum / cap > D - margin + 1e-9:            # cannot finish even unthrottled, no residue
                return False, None
            targets.append((cum, D - margin))
        self.n_forward += 1
        dev = dev0.clone()
        t, done, idx = t0, 0.0, 0
        drv_max10 = dev.drv()
        on_len = PERIOD_S * frac
        ru, arm = res_until, armed
        while True:
            if d >= 100:
                f = 1.0
            else:
                k = period_of(t)
                ph = t - k * PERIOD_S
                f = _overlap(ph, ph + 1.0, 0.0, on_len) + _overlap(ph - PERIOD_S, ph + 1.0 - PERIOD_S, 0.0, on_len)
                f = min(1.0, f)
            factor = 1.0
            if f > 0:
                if arm:
                    ru, arm = t + RESIDUE['window_s'], False
                if t < ru - 1e-12:
                    factor = 1.0 / RESIDUE['factor']
                done += r0 * dev.s() * factor * f * (1.0 - fg_share)
                dev.advance(f, True)
            if f < 1.0:
                dev.advance(1.0 - f, False)
            t += 1.0
            if t - t0 <= PERIOD_S + 1e-9:
                drv_max10 = max(drv_max10, dev.drv())
            while idx < len(targets) and done >= targets[idx][0] - 1e-6:
                if t > targets[idx][1] + 1e-9:
                    return False, None
                idx += 1
            if idx == len(targets):
                return True, dict(drv_max10=drv_max10, finish_s=t)
            if t > targets[idx][1] + 1e-9:
                return False, None


def make_policy(spec, res, lam_fg=0.0):
    kind = spec[0]
    if kind == 'fixed-prio':
        return FixedPrio(res)
    if kind == 'npumgr':
        return NpuMgr(res)
    if kind == 'pace-d50':
        return PaceD50(res)
    if kind == 'ours':
        return Ours(res, spec[1], spec[2], lam_fg)
    if kind == 'pace-perm':
        return PacePerm(res, spec[1])
    if kind == 'ref-const':
        return RefConst(res, spec[1])
    raise ValueError(spec)
