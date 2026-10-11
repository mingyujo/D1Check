"""Minimal external event-based scheduler on top of ParallelDevice (library use).

Rule here (illustration only, not a registered rule): urgent first; classification goes to the lane (GPU / NPU / CPU) with the
earliest predicted output_ready from dev.estimate(); detection goes to CPU. Run from the repo root:
    python -m d1sim.parsim_v1.examples.example_external_scheduler
"""
import json
import os

from d1sim.parsim_v1.adapter import ParallelDevice

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    reqs = json.load(open(os.path.join(HERE, 'requests_192_200ms.json'), encoding='utf-8'))
    dev = ParallelDevice(form='M-sup', start=json.load(open(os.path.join(HERE, 'start_30p5.json'))), seed=1)
    pending, t, done = sorted(reqs, key=lambda q: q['sched']), 0.0, []
    waiting = []
    while pending or waiting:
        # next event = next arrival or next lane release
        busy = [v for v in dev.state()['lanes'].values() if v is not None]
        t = min(([pending[0]['sched']] if pending else []) + busy)
        dev.advance(t)
        while pending and pending[0]['sched'] <= t + 1e-12:
            waiting.append(pending.pop(0))
        waiting.sort(key=lambda q: (q['priority'] != 'urgent', q['ordinal']))
        lanes = dev.state()['lanes']
        for q in list(waiting):
            cands = ['GPU', 'NPU', 'CPU'] if q['task'] == 'classification' else ['CPU']
            free = [r for r in cands if lanes[r] is None]
            if not free:
                continue
            best = min(free, key=lambda r: sum(v for k, v in dev.estimate(q['task'], r).items() if k in ('prepare', 'execution', 'out')))
            done.append(dict(dev.dispatch(t, f"req-{q['ordinal']}", q['task'], q['priority'], best), sched=q['sched']))
            waiting.remove(q)
            lanes = dev.state()['lanes']
    dev.advance(max(j['lane_available'] for j in done) + 30.0)
    urg = sorted(j['output_ready'] - j['sched'] for j in done if j['priority'] == 'urgent')
    st = dev.state()
    print(json.dumps(dict(dispatched=len(done), urgent_p95_ms=round(urg[int(0.95 * len(urg)) - 1] * 1000, 3),
                          lanes={r: sum(1 for j in done if j['resource'] == r) for r in ('CPU', 'GPU', 'NPU')},
                          end_skin=round(st['skin'], 3), end_ap=round(st['ap'], 3)), ensure_ascii=False))


if __name__ == '__main__':
    main()
