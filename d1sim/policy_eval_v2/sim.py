"""sim.py — event simulator for the policy comparison v2 (sim/정책비교_사전등록_v2.md §2 · §4 · §5; adapter = v1 §7).

One resource (NPU or GPU) serves FG (single inference, deadline arrival + 1.5 s) and BG chunks (128 inferences, burst deadline D_b).
Jobs run one at a time and are not preempted (FG goes first at chunk boundaries = "FG 선점"). Same semantics as d1sim/env.Sim
(dispatch / switch cost / record / conservation), re-written lean because env.Sim's snapshot scans the whole queue per decision
(~8,000 BG chunks per NPU run): the policy sees the FG queue + the BG head only — prio_head on that view equals prio_head on the full
queue because BG is FIFO by (arrival, id) (selftest checks it).

Adapter (v1 §7 = env_v2 approximations): thermal sub-step <= 0.5 s · load u = executing fraction of the last 10 s in TIME (missing
history = idle) · status = HAL map of SKIN (capped at 2, env_v2) · the single resource's controller always steps (scheduled — the chain
replay rule of throttle_v21.simulate, under which the model was fitted; env_v2 freezes controllers when no job runs).
Models: 'v22' (main, V22-M with EffNet g_m — every run here is EffNet) · 'v21' (c6a7da2) · 'v2_t0.3' · 'v2_t0.75' (42338e7 via env_v2.v2_params).
Start state (§2): SKIN 30.5 · A0 -1.0 · BAT0 = SKIN0 - d_ref (z = 0; v2 has no body state).
Service: R0 (EffNet, cold d100, inferences per executing second) = NPU 1,130.7 · GPU 298.1 [P 등록 v1 §1]; rate = R0 * s (s = 1/ratio).
NPU residue R20 (등록 v1 §2 "NPU 가 60 s 이상 쉰 뒤 첫 20 s 지연 ×3.0" — P1f 가 정함 (결과 전)): "쉰" = no BG execution for >= 60 s
(FG single inferences do not count as work — the measured residue followed a d1 = 1 % load, NI300); when a BG chunk starts executing
after such a rest (the run start counts as rested), the next 20 s of wall time run at rate / 3.0 for every request (latency x3;
thermal power stays the controller-state power — the residue is not a thermal effect).
"""
from __future__ import annotations

import math
from collections import deque

from d1sim import env as env0
from d1sim import env_v2
from d1sim import throttle_v2 as tv2
from d1sim import throttle_v21 as tv21
from d1sim import throttle_v22 as tv22
from d1sim.profile import Profile, RESOURCES

DT = 0.5
WINDOW_S = 10.0
PERIOD_S = 10.0
T_START = 30.5
A0 = -1.0
R0 = {'NPU': 1130.7, 'GPU': 298.1}
THR = {'NPU': 1.06, 'GPU': 1.10}
TEMP_LEVELS = (38.0, 40.0, 42.0)
RESIDUE = dict(idle_s=60.0, window_s=20.0, factor=3.0)
MODELS = ('v22', 'v21', 'v2_t0.3', 'v2_t0.75')
_PROFILE = Profile()
INIT_S = {r: _PROFILE.init_s[r] for r in ('NPU', 'GPU')}


def model_params(model):
    if model == 'v22':
        return tv22.with_model(tv22.load_params('throttle_v22_'), 'effnet')
    if model == 'v21':
        return tv22.load_params('throttle_v21_')
    if model.startswith('v2_t'):
        return env_v2.v2_params(theta_npu=float(model[4:]), cooling='v2')
    raise ValueError(model)


class Device:
    """Thermal + the resource's controller. advance(h, executing) integrates exactly over h with power held (step start)."""

    def __init__(self, model, res, T_start=T_START, A0_=A0, params=None):
        self.model, self.res = model, res
        p = params or model_params(model)
        self.params = p
        if model in ('v22', 'v21'):
            self.th = tv21.ThermalV21(p['thermal'], T_start, A0_, T_start - p['thermal']['d_ref'])
            self.ctrl = tv21.make_controller(res, p)
        else:
            self.th = tv2.ThermalV2(p['thermal'], T_start, A0_)
            self.ctrl = tv2.make_controller(res, p)
        self.cp = self.ctrl.cp
        self.pp = p['power'][res]
        self.P_idle = p['thermal']['P_idle']
        self.win = deque()
        self.w_tot = 0.0
        self.w_act = 0.0

    def drv(self):
        c = self.ctrl
        return c.drv(self.th) if hasattr(c, 'drv') else tv2._sensor(self.cp, self.th)

    def s(self):
        c = self.ctrl
        if hasattr(c, 'last_T'):
            c.last_T = self.drv()
        return c.s

    def u(self):
        return self.w_act / WINDOW_S if self.w_tot > 0 else 0.0

    @property
    def skin(self):
        return self.th.skin

    def status(self):
        return min(2, tv2.status_of(self.th.skin))

    def power(self, executing):
        return tv2.power_of(self.s(), self.pp) if executing else self.P_idle

    def advance(self, h, executing):
        P = self.power(executing)
        self.th.advance(h, P, self.res if executing else None)
        self.win.append((h, executing))
        self.w_tot += h
        if executing:
            self.w_act += h
        while self.win and self.w_tot - self.win[0][0] >= WINDOW_S - 1e-9:
            hh, e = self.win.popleft()
            self.w_tot -= hh
            if e:
                self.w_act -= hh
        self.ctrl.step(h, self.th, executing, scheduled=True, u=self.u())
        return P

    def clone(self):
        c = object.__new__(Device)
        c.__dict__.update(self.__dict__)
        c.th = self.th.clone()
        c.ctrl = self.ctrl.clone()
        c.win = deque(self.win)
        return c

    def first_arm_temp(self, u):
        """First throttle (arm) threshold of the controller at load u — ours' thermal check (등록 v1 §4 "첫 조임 문턱 온도")."""
        cp = self.cp
        T = cp['T1'] if self.res == 'NPU' else cp['T_on']
        if cp.get('form') in ('Ht', 'Lk'):
            T += cp.get('kappa', 0.0) * (1.0 - u)
        return T


class SimReg:
    """requests = workload_reg1.scenario_reg1(...)['requests'] (dicts with id, arrival_s, deadline_s, cls, n_inf, burst)."""

    def __init__(self, res, model, requests, horizon, residue='R0', params=None):
        if res not in ('NPU', 'GPU'):
            raise ValueError(res)
        self.res, self.model, self.horizon = res, model, float(horizon)
        self.residue = residue == 'R20' and res == 'NPU'
        self.dev = Device(model, res, params=params)
        self.r0 = R0[res]
        self.reqs = sorted((dict(r) for r in requests), key=lambda r: (r['arrival_s'], r['id']))
        self.rec = env0.Record(self.horizon)
        self.t = 0.0
        self.fg, self.bg = deque(), deque()
        self.loaded = False
        self.job = None
        self.wake = None
        self.last_bg_exec_end = -1e18
        self.residue_until = -1.0
        # bursts are atomic arrivals (workload_reg1: "all chunks arrive at the burst time"; the 1e-6 s id offsets only order them):
        # once a burst's first chunk is admitted, policies know its whole remaining work (bg_backlog)
        self.b_total, self.b_first, self.b_dl, self.b_disp = {}, {}, {}, {}
        for r in self.reqs:
            if r['cls'] == 'BG':
                b = r['burst']
                self.b_total[b] = self.b_total.get(b, 0) + r['n_inf']
                self.b_first[b] = min(self.b_first.get(b, r['arrival_s']), r['arrival_s'])
                self.b_dl[b] = r['deadline_s']
                self.b_disp[b] = 0
        self.b_order = sorted(self.b_total, key=lambda b: (self.b_first[b], b))
        self.n_per = int(math.ceil(self.horizon / PERIOD_S)) + 1
        self.bg_exec_per = [0.0] * self.n_per     # realised BG executing seconds per 10 s period
        self.therm = dict(max_skin=self.dev.skin, t_level={lv: 0.0 for lv in TEMP_LEVELS}, throttle_s=0.0, exec_s=0.0)
        self.decisions = 0

    # ---------------- policy view
    def obs(self):
        fh = self.fg[0] if self.fg else None
        bh = self.bg[0] if self.bg else None
        q = list(self.fg)
        if bh is not None:
            q.append(bh)
        return dict(t=self.t, loaded=(self.res if self.loaded else None), queue=q, fg_head=fh, bg_head=bh,
                    status=self.dev.status(), skin=self.dev.skin, sim=self)

    def bg_backlog(self):
        """FIFO list of (burst, remaining not-yet-dispatched inferences, deadline) over the bursts that have ARRIVED (first chunk
        admitted) — what ours knows (no future bursts)."""
        return [(b, self.b_total[b] - self.b_disp[b], self.b_dl[b]) for b in self.b_order
                if self.b_first[b] <= self.t + 1e-12 and self.b_total[b] - self.b_disp[b] > 0]

    def residue_state(self):
        """(active_until, armed): armed = the next BG execution would start a residue window."""
        if not self.residue:
            return -1.0, False
        return self.residue_until, (self.t - self.last_bg_exec_end >= RESIDUE['idle_s'] - 1e-9 and self.t >= self.residue_until)

    # ---------------- core
    def _admit(self, ai):
        reqs = self.reqs
        while ai < len(reqs) and reqs[ai]['arrival_s'] <= self.t + 1e-12:
            r = reqs[ai]
            self.rec.requests[r['id']]['status'] = 'queued'
            if r['cls'] == 'FG':
                self.fg.append(r)
            else:
                self.bg.append(r)
            ai += 1
        return ai

    def _step(self, h, executing):
        dev = self.dev
        sk0 = dev.skin
        tl = self.therm['t_level']
        for lv in TEMP_LEVELS:
            if sk0 >= lv - 1e-9:
                tl[lv] += h
        if executing:
            s = dev.s()
            self.therm['exec_s'] += h
            self.rec.exec_s[self.res] += h
            if 1.0 / s >= THR[self.res] - 1e-9:
                self.therm['throttle_s'] += h
                self.rec.throttle_s[self.res] += h
        st = dev.status()
        P = dev.advance(h, executing)
        self.rec.status_s[st] += h
        self.rec.energy.append((self.t, self.t + h, P))
        self.rec.energy_j += P * h
        self.t += h
        if dev.skin > self.therm['max_skin']:
            self.therm['max_skin'] = dev.skin

    def _idle_to(self, t_target):
        while t_target - self.t > 1e-12:
            self._step(min(DT, t_target - self.t), False)

    def _dispatch(self, rid):
        if self.fg and self.fg[0]['id'] == rid:
            req = self.fg.popleft()
        elif self.bg and self.bg[0]['id'] == rid:
            req = self.bg.popleft()
            self.b_disp[req['burst']] += req['n_inf']
        else:
            req = next((q for q in self.fg if q['id'] == rid), None)
            if req is None:
                raise ValueError(f'dispatch of a request not at a queue head: {rid}')
            self.fg.remove(req)
        sw = 0.0 if self.loaded else INIT_S[self.res]
        self.loaded = True
        self.job = dict(req=req, start=self.t, switch_end=self.t + sw, work_left=req['n_inf'] / self.r0)
        self.rec.requests[req['id']].update(status='running', resource=self.res, start=self.t, switch_s=sw)

    def _run_job(self):
        j = self.job
        while j['switch_end'] - self.t > 1e-12 and self.horizon - self.t > 1e-12:
            self._step(min(DT, j['switch_end'] - self.t, self.horizon - self.t), False)
        is_bg = j['req']['cls'] == 'BG'
        if (self.residue and is_bg and self.t - self.last_bg_exec_end >= RESIDUE['idle_s'] - 1e-9 and self.t >= self.residue_until
                and self.horizon - self.t > 1e-12):
            self.residue_until = self.t + RESIDUE['window_s']
        while j['work_left'] > 1e-12 and self.horizon - self.t > 1e-12:
            rate = self.dev.s() / (RESIDUE['factor'] if (self.residue and self.t < self.residue_until - 1e-12) else 1.0)
            h = min(DT, j['work_left'] / rate, self.horizon - self.t)
            if self.residue and self.t < self.residue_until - 1e-12:
                h = min(h, self.residue_until - self.t)
            if is_bg:
                k = int(self.t // PERIOD_S)
                h = min(h, (k + 1) * PERIOD_S - self.t) if (k + 1) * PERIOD_S - self.t > 1e-9 else h
                if k < self.n_per:
                    self.bg_exec_per[k] += h
            self._step(h, True)
            j['work_left'] -= rate * h
            if is_bg:
                self.last_bg_exec_end = self.t
        if j['work_left'] <= 1e-12:
            self.rec.busy[self.res].append((j['start'], self.t))
            self.rec.requests[j['req']['id']].update(status='done', completion=self.t, exec_s=self.t - j['switch_end'])
            self.job = None

    def _decide(self, policy):
        for _ in range(10_000):
            if self.job is not None or not (self.fg or self.bg):
                return
            self.decisions += 1
            act = policy.decide(self.obs())
            kind = act[0]
            if kind == 'dispatch':
                if act[2] != self.res:
                    raise ValueError(f'masked action: {act[2]} on a {self.res} condition')
                self._dispatch(act[1])
                return
            if kind == 'unload':
                self.loaded = False
                continue
            if kind == 'wait':
                self.wake = act[1] if len(act) > 1 and act[1] is not None and act[1] > self.t + 1e-9 else None
                return
            raise ValueError(f'unknown action {act}')
        raise RuntimeError('policy loop did not terminate')

    def run(self, policy):
        for r in self.reqs:
            self.rec.requests[r['id']] = dict(r, status='pending')
        ai = 0
        N = len(self.reqs)
        while True:
            ai = self._admit(ai)
            if self.wake is not None and self.wake <= self.t + 1e-12:
                self.wake = None
            self._decide(policy)
            if self.t >= self.horizon - 1e-12:
                break
            if self.job is not None:
                self._run_job()
                continue
            nxt = self.horizon
            if ai < N:
                nxt = min(nxt, self.reqs[ai]['arrival_s'])
            if self.wake is not None:
                nxt = min(nxt, self.wake)
            if nxt <= self.t + 1e-12:          # safety: time always moves
                nxt = min(self.horizon, self.t + DT)
            self._idle_to(nxt)
        if self.job is not None:
            j = self.job
            self.rec.busy[self.res].append((j['start'], self.t))
            self.rec.requests[j['req']['id']]['status'] = 'unfinished'
            self.job = None
        for q in list(self.fg) + list(self.bg):
            self.rec.requests[q['id']]['status'] = 'unfinished'
        self.rec.requests = {k: v for k, v in self.rec.requests.items() if v['arrival_s'] < self.horizon}
        self.end_skin = self.dev.skin
        return self.rec


__all__ = ['SimReg', 'Device', 'model_params', 'R0', 'THR', 'PERIOD_S', 'DT', 'MODELS', 'RESIDUE', 'T_START', 'A0', 'INIT_S', 'RESOURCES']
