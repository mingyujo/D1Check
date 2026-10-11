"""Scheduling rules R1 ~ R7 (registration §5) + R8 Band (port, decided before results — DECISIONS D8).

Interface used by service_des.Engine:
  lanes()                          -> {lane: (resource, tasks)}
  ctx_key(task, res, lane)         -> key of the R3 stage-tuple distribution to draw from
  choose(engine, free_lanes)       -> (request, lane) to dispatch now | None (nothing now) | ('wait', t) (re-decide at t)
  on_dispatch(engine, job)         -> bookkeeping (Band EMA)

Waiting orders (definitions only — no A24 numbers):
  R1 FIFO: actual arrival, ordinal.  R2 / R3 / R4 / R5 / R7 urgent first, then ordinal (request-runner online order:
  'urgent first, then ordinal, then request_id' [D 계약 JSON a24_policies]).  R6 EDD: absolute deadline (scheduled + 1.5 s | 6 s),
  then ordinal.  EFT head-of-line (조민규 EFT_REFERENCE, tools/d1_empirical_request_policy.py @ 7475b18): the head request goes to the
  lane with the earliest predicted RESPONSE (ties: CPU first); if that lane is busy the head waits (no slower lane instead).
  Predicted response uses the R3 median stage durations x current controller ratio; a busy lane's end = its job's lane_available
  estimate (dispatch + median durations).  No aging (조민규 aging_ns is a PC-sim setting not defined for S26 — DECISIONS D7).
  R7: EFT, but an accelerator lane r is excluded when the SKIN predicted at the job end (one-job look-ahead on a device clone) is
  >= r's first-arm threshold + offset — unless every remaining lane misses the head's deadline.  CPU has no controller -> never excluded.
  R8 Band (BAND_HEFT_WHOLE_REQUEST_ADAPT_V1, tools/d1_external_rules.py @ 7475b18, Apache-2.0 origin noted there): FIFO window; per task the
  first request's shortest expected latency (expected + lane waiting); pick the largest; if its best lane is not idle, add its expected
  time to that lane's waiting and yield; EMA (0.1) of observed lane occupancy updates expected.
"""
from __future__ import annotations

import math

CLS, DET = 'classification', 'detection'


def urgent_first(q):
    return (0 if q['priority'] == 'urgent' else 1, q['ordinal'])


def edd(q):
    return (q['sched'] + q['deadline'], q['ordinal'])


class FixedLanes:
    """R1 · R2 (serial CPU) · R3 (GPU + CPU) · R4 (NPU + CPU): each free lane takes its first eligible waiting request."""

    def __init__(self, name, lanes, ctx, order):
        self.name, self._lanes, self.ctx, self.order = name, lanes, ctx, order

    def lanes(self):
        return self._lanes

    def ctx_key(self, task, res, lane):
        return (self.ctx, task, res)

    def choose(self, eng, free):
        cand = sorted(eng.waiting, key=self.order)
        for q in cand:
            for lane in free:
                if q['task'] in eng.lanes[lane]['tasks']:
                    return q, lane
        return None

    def on_dispatch(self, eng, job):
        pass


def R1():
    return FixedLanes('R1 CPU 직렬 FIFO', {'CPU': ('CPU', (CLS, DET))}, 'serial', lambda q: (q['actual'], q['ordinal']))


def R2():
    return FixedLanes('R2 CPU 직렬 긴급 우선', {'CPU': ('CPU', (CLS, DET))}, 'serial', urgent_first)


def R3():
    return FixedLanes('R3 고정 병행 GPU', {'GPU': ('GPU', (CLS,)), 'CPU': ('CPU', (DET,))}, 'par_gpu', urgent_first)


def R4():
    return FixedLanes('R4 고정 병행 NPU', {'NPU': ('NPU', (CLS,)), 'CPU': ('CPU', (DET,))}, 'par_npu', urgent_first)


LANES3 = {'CPU': ('CPU', (CLS, DET)), 'GPU': ('GPU', (CLS,)), 'NPU': ('NPU', (CLS,))}


def ctx3(task, res):
    if res == 'GPU':
        return ('par_gpu', task, 'GPU')
    if res == 'NPU':
        return ('par_npu', task, 'NPU')
    return ('serial', CLS, 'CPU') if task == CLS else ('par', DET, 'CPU')


class EFT:
    """R5 (urgent first) · R6 (EDD) · R7 (thermal-aware, offset) on three lanes (3 resources at once = extrapolation)."""

    def __init__(self, name, order, thermal_offset=None):
        self.name, self.order, self.offset = name, order, thermal_offset

    def lanes(self):
        return LANES3

    def ctx_key(self, task, res, lane):
        return ctx3(task, res)

    def est(self, eng, task, res):
        pre, inf, out, pers, rel = eng.svc.med[ctx3(task, res)]
        r = eng.dev.ratio(res) if res != 'CPU' else 1.0
        return pre, inf * r, out, pers, rel

    def lane_end(self, eng, lane):
        """Estimated end of the lane's current job = its dispatch + median stages (the true end is not visible to the rule)."""
        j = eng.lanes[lane]['job']
        if j is None:
            return eng.t
        pre, inf, out, pers, rel = eng.svc.med[j.key]
        return max(eng.t, j.dispatch + pre + inf * j.ratio + out + pers + rel)

    def predict(self, eng, q, lane):
        res = eng.lanes[lane]['res']
        pre, inf, out, pers, rel = self.est(eng, q['task'], res)
        start = self.lane_end(eng, lane)
        resp_end = start + pre + inf + out + (pers if q['priority'] == 'normal' else 0.0)
        return start, resp_end, start + pre + inf + out + pers + rel

    def hot(self, eng, lane, q, start, end):
        res = eng.lanes[lane]['res']
        if self.offset is None or res == 'CPU':
            return False
        thr = eng.dev.first_arm_temp(res)
        d = eng.dev.clone()
        t, act = eng.t, {res}
        while t < end - 1e-12:
            h = min(0.5, end - t)
            d.advance(h, act if t >= start - 1e-12 else set())
            t += h
        return d.skin >= thr + self.offset

    def choose(self, eng, free):
        if not eng.waiting:
            return None
        q = min(eng.waiting, key=self.order)
        lanes = [ln for ln in ('CPU', 'GPU', 'NPU') if q['task'] in eng.lanes[ln]['tasks']]
        pred = {ln: self.predict(eng, q, ln) for ln in lanes}
        ok = lanes
        if self.offset is not None:
            cool = [ln for ln in lanes if not self.hot(eng, ln, q, pred[ln][0], pred[ln][2])]
            meets = [ln for ln in cool if pred[ln][1] <= q['sched'] + q['deadline'] + 1e-12]
            ok = cool if meets else lanes
        best = min(ok, key=lambda ln: (pred[ln][1], ('CPU', 'GPU', 'NPU').index(ln)))
        if eng.lanes[best]['job'] is None:
            return q, best
        if pred[best][0] <= eng.t + 1e-9:
            return None                      # estimated end already passed: wait for the actual lane release event
        return ('wait', pred[best][0])

    def on_dispatch(self, eng, job):
        pass


def R5():
    return EFT('R5 3자원 EFT', urgent_first)


def R6():
    return EFT('R6 EDD + EFT', edd)


def R7(offset):
    return EFT(f'R7 열 인지 EFT (offset {offset:+.1f})', urgent_first, thermal_offset=offset)


class Band:
    """R8 Band HEFT (whole-request adaptation) on the three lanes; FIFO; EMA expected occupancy."""

    name = 'R8 Band HEFT (이식)'

    def __init__(self):
        self.expected = None
        self.running = []

    def lanes(self):
        return LANES3

    def ctx_key(self, task, res, lane):
        return ctx3(task, res)

    def _init(self, eng):
        if self.expected is None:
            self.expected = {}
            for task, ress in ((CLS, ('CPU', 'GPU', 'NPU')), (DET, ('CPU',))):
                for res in ress:
                    self.expected[(task, res)] = sum(eng.svc.med[ctx3(task, res)])

    def choose(self, eng, free):
        self._init(eng)
        still = []
        for job in self.running:                       # EMA only after the lane is actually released (public event)
            if job.lane_available <= eng.t + 1e-12:
                k = (job.req['task'], job.res)
                self.expected[k] = 0.1 * (job.lane_available - job.dispatch) + 0.9 * self.expected[k]
            else:
                still.append(job)
        self.running = still
        waiting = {}
        for ln, d in eng.lanes.items():
            j = d['job']
            waiting[ln] = 0.0 if j is None else max(0.0, j.dispatch + self.expected[(j.req['task'], j.res)] - eng.t)
        idle = set(free)
        fifo = sorted(eng.waiting, key=lambda q: (q['actual'], q['ordinal']))
        yielded = set()
        while True:
            target, largest, searched = None, -1.0, set()
            for q in fifo:
                if id(q) in yielded or q['task'] in searched:
                    continue
                searched.add(q['task'])
                best = None
                for ln in ('CPU', 'GPU', 'NPU'):
                    if q['task'] not in eng.lanes[ln]['tasks']:
                        continue
                    lat = self.expected[(q['task'], eng.lanes[ln]['res'])] + waiting[ln]
                    if best is None or lat <= best[0]:
                        best = (lat, ln)
                if best[0] > largest:
                    largest, target = best[0], (q, best[1])
            if target is None:
                return None
            q, ln = target
            if ln not in idle:
                waiting[ln] += self.expected[(q['task'], eng.lanes[ln]['res'])]
                yielded.add(id(q))
                continue
            return q, ln

    def on_dispatch(self, eng, job):
        self._init(eng)
        self.running.append(job)


def R8():
    return Band()


MEASURED = {'CPU_URGENT_ONLINE_V1': R2, 'B2_PARALLEL_ONLINE_V1': R3, 'S26_NPU_PARALLEL_V1': R4}
