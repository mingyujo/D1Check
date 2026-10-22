"""Visible-only rollout with truthful coverage and a common action horizon.

    Timing vectors, continuation rule, costs and CPU3/GPU1 capacity are inherited
    from the frozen S26-method ORIGINAL model. No future arrivals or latents.
"""
import copy
import math
from common_transfer import NS, tie

EPS = 1e-10


def horizon(s, jobs, vectors, case):
    now = s['now_ns'] / NS
    work = sum(min(sum(vectors[q['request_id'], r]) for r in ('CPU', 'GPU'))
               for q in jobs)
    return max(now + 1e-6, min(case['service_stop_s'],
               now + max(10., 3 * work + 3 * len(s['owners']))))


def predict(s, first, jobs, vectors, physics, case, *, horizon_end_s=None,
            max_steps=800):
    if not isinstance(max_steps, int) or max_steps < 1:
        raise ValueError('max_steps must be a positive integer')
    now = start = s['now_ns'] / NS
    H = horizon(s, jobs, vectors, case) if horizon_end_s is None else horizon_end_s
    if not math.isfinite(H) or H <= start:
        raise ValueError('Forecast horizon must be finite and after now')
    state = {k: copy.deepcopy(v) for k, v in s['sensor'].items()
             if k not in ('peak_c', 'increment_so_far')}
    queue = {q['request_id']: q for q in jobs}
    public = {q['request_id']: q for q in jobs + s['owners']}
    owners, responses, finished = [], {}, set()
    for o in s['owners']:
        vec = vectors[o['request_id'], o['route']]
        owners.append(dict(request_id=o['request_id'], task=o['task'],
                           route=o['route'], stage=o['stage'],
                           remaining=max(0., vec[o['stage']] - o['public_progress_s']),
                           vec=vec))
        if o['response_ns'] is not None:
            responses[o['request_id']] = o['response_ns'] / NS
    wait, pending = 0., copy.deepcopy(first)
    J = heat = 0.
    peak, steps = state['temperature_c'], 0

    def free(route):
        return sum(o['route'] == route for o in owners) < (3 if route == 'CPU' else 1)

    def settle():
        # Also used immediately after dispatch and at the closed right boundary.
        # Zero-work phases consume no time and cannot hold an occupied slot.
        for o in owners.copy():
            while o['remaining'] <= EPS:
                if (o['task'] == 'C' and o['stage'] == 1) or (o['task'] == 'D' and o['stage'] == 2):
                    responses[o['request_id']] = now
                o['stage'] += 1
                if o['stage'] == 5:
                    owners.remove(o)
                    finished.add(o['request_id'])
                    break
                o['remaining'] = o['vec'][o['stage']]

    def dispatch(q, route):
        if not free(route):
            raise ValueError('Forecast dispatch requires a free route slot')
        queue.pop(q['request_id'])
        vec = vectors[q['request_id'], route]
        owners.append(dict(request_id=q['request_id'], task=q['task'], route=route,
                           stage=0, remaining=vec[0], vec=vec))
        settle()

    while now < H - EPS and steps < max_steps:
        settle()
        if pending:
            a, pending = pending, None
            if a['kind'] == 'DISPATCH':
                dispatch(queue[a['request_id']], a['route'])
            elif a['kind'] == 'WAIT':
                wait = now + a['wait_ns'] / NS
            else:
                wait = min(H, now + .5, now + min(
                    (sum(o['vec'][o['stage']:]) - o['vec'][o['stage']] + o['remaining']
                     for o in owners), default=.5))
        if now >= wait - EPS and queue:
            # Unchanged public EDF / route-score continuation.
            while queue:
                q = min(queue.values(), key=lambda q: (q['deadline_ns'], *tie(q)))
                opts = []
                for route in ('CPU', 'GPU'):
                    vec = vectors[q['request_id'], route]
                    load = sorted(sum(o['vec'][o['stage']:]) - o['vec'][o['stage']] + o['remaining']
                                  for o in owners if o['route'] == route)
                    release = load[0] if not free(route) else 0.
                    f = physics.speed(state['temperature_c'], route, 1, q['task'])
                    resp = sum(vec[:2 if q['task'] == 'C' else 3]) - vec[1] + vec[1] / f
                    power = physics.solo[('classification' if q['task'] == 'C' else 'detection') + '_' + route]
                    score = power * sum(vec) / .35 + 12 * max(
                        0, now + release + resp - q['deadline_ns'] / NS) / max(
                            .05, (q['deadline_ns'] - q['scheduled_arrival_ns']) / NS)
                    opts.append((score, release, route))
                _, release, route = min(opts)
                if release > EPS:
                    break
                dispatch(q, route)
        if not owners:
            dt = H - now if not queue else min(H - now, max(.001, wait - now))
        else:
            rates = physics.rates(state['temperature_c'], owners)
            dt = min(H - now, .5, min(max(1e-9, o['remaining'] / rates[o['request_id']])
                                     for o in owners))
            if wait > now + EPS:
                dt = min(dt, wait - now)
        state, terms = physics.transition(state, owners, dt)
        for o in owners:
            o['remaining'] = max(0., o['remaining'] - dt * terms['speeds'][o['request_id']])
        J += terms['increment']
        heat += terms['temperature_area'] - physics.c.idle_c * dt
        peak = max(peak, terms['peak'])
        now += dt
        steps += 1
    settle()
    n = max(1, len(public))
    # A capped standalone result reports only its actual integrated interval.
    cost = [J / n, max(0., heat) / (now - start) / 10, 0., 0.,
            len(set(public) - finished) / n]
    for rid, q in public.items():
        due = q['deadline_ns'] / NS
        ttl = max(.05, (q['deadline_ns'] - q['scheduled_arrival_ns']) / NS)
        late = max(0., responses.get(rid, now) - due)
        g = 2 if q['priority'] == 'U' else 3
        den = max(1, sum(v['priority'] == q['priority'] for v in public.values()))
        cost[g] += (float(rid not in responses or late > 1e-8)
                    + .02 * min(5, late / ttl)) / den
    return dict(cost=cost, AP_end=state['temperature_c'], peak=peak, H_s=now,
                requested_H_s=H, steps=steps, capped=now < H - EPS,
                visible_ids=sorted(public), no_future_arrivals=True, no_future_latents=True)


def predict_actions(s, actions, jobs, vectors, physics, case, *, max_steps=800):
    """Return comparable scores, even when one candidate reaches the step cap.

    If any candidate is truncated, recompute every alternative over the shortest
    covered prefix. Two passes at most; never extrapolate a partial cost to H.
    """
    requested = horizon(s, jobs, vectors, case)
    first = [predict(s, a, jobs, vectors, physics, case, horizon_end_s=requested,
                     max_steps=max_steps) for a in actions]
    reduced = any(f['capped'] for f in first)
    common = min((f['H_s'] for f in first), default=requested)
    results = ([predict(s, a, jobs, vectors, physics, case, horizon_end_s=common,
                        max_steps=max_steps) for a in actions] if reduced else first)
    for previous, f in zip(first, results):
        if f['capped'] or not math.isclose(f['H_s'], common, rel_tol=0., abs_tol=1e-8):
            raise ValueError('Forecast candidates did not reach a common horizon')
        f.update(requested_H_s=requested, capped=reduced, horizon_reduced=reduced,
                 comparison_complete=True,
                 evaluation_steps=previous['steps'] + f['steps'] if reduced else f['steps'])
    return results
