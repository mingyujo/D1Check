"""Public ATC ranking and the S26 ordered candidate union, with A24 routes."""
import math
from common_transfer import NS, tie


def atc_index(priority, occupied, response, due, now, mean_occupied):
    # Same log ATC as pinned S26 ranks(): urgency weight 2/1, k=2.
    return math.log((2. if priority == 'U' else 1.) / max(1e-9, occupied)) - max(
        0., due - now - response) / (2 * max(1e-9, mean_occupied))


def build(s, nominal, physics):
    queue = s['queue']
    if not queue:
        raise ValueError('Policy requires a nonempty ready queue')
    edf = sorted(queue, key=lambda q:(q['deadline_ns'], *tie(q)))
    fifo = sorted(queue, key=tie)
    vectors = {(q['request_id'], r):nominal.vector(q, r, s)
               for q in queue + s['owners'] for r in ('CPU', 'GPU')}
    free = [r for r in ('CPU', 'GPU') if sum(o['route'] == r for o in s['owners']) < (3 if r == 'CPU' else 1)]
    pairs = []
    for q in queue:
        for route in free:
            v = vectors[q['request_id'], route]
            if len(v) != 5 or any(not math.isfinite(x) or x < 0 for x in v):
                raise ValueError('ATC requires five finite nonnegative public phases')
            rate = physics.speed(s['sensor']['temperature_c'], route, 1, q['task'])
            response = sum(v[:2 if q['task'] == 'C' else 3]) - v[1] + v[1]/rate
            occupied = sum(v) - v[1] + v[1]/rate
            pairs.append(dict(q=q, route=route, response=response, occupied=occupied))
    mean = sum(p['occupied'] for p in pairs)/max(1, len(pairs))
    for p in pairs:
        p['ATC'] = atc_index(p['q']['priority'], p['occupied'], p['response'],
                             p['q']['deadline_ns']/NS, s['now_ns']/NS, mean)
    ranked = sorted(pairs, key=lambda p:(-p['ATC'], *tie(p['q']), p['response'], p['occupied'], p['route']))
    if not ranked:
        raise ValueError('No physical route slot is available')
    buckets = {}
    for q in fifo:
        buckets.setdefault((q['task'], q['priority']), []).append(q)
    rows = [buckets[k] for k in sorted(buckets)]
    # S26 order: EDF head; oldest/newest class representatives; ATC top six;
    # EDF fill. The union is bounded to eight requests, not eight routes.
    proposed = [edf[0], *[q for row in rows for q in (row[0], row[-1])],
                *[p['q'] for p in ranked[:6]], *edf]
    chosen = {}
    for q in proposed:
        if len(chosen) >= 8:
            break
        chosen[q['request_id']] = q
    selected = [q for q in edf if q['request_id'] in chosen]
    visible = {q['request_id']:q for q in selected}
    for k in range(len(queue)):
        if len(visible) >= min(32, len(queue)):
            break
        for row in rows:
            for i in (k, len(row)-1-k):
                if 0 <= i < len(row) and len(visible) < 32:
                    visible[row[i]['request_id']] = row[i]
    lookup = {(p['q']['request_id'], p['route']):p['ATC'] for p in ranked}
    return dict(chosen=selected, visible=visible, vectors=vectors, free=free,
                atc=lookup, best_atc=ranked[0]['ATC'], ranked=ranked)


def compatible_targets(s, actions, index):
    """Same observed EDF tie and physical task/route; never latent equality.

    A24 priorities are independent of task, so they must also match. S26's
    classification/urgent coupling made that extra check implicit.
    """
    chosen = actions[index]
    if chosen['kind'] != 'DISPATCH':
        return [a == chosen for a in actions]
    jobs = {q['request_id']:q for q in s['queue']}
    target = jobs[chosen['request_id']]
    return [a['kind'] == 'DISPATCH' and a['route'] == chosen['route']
            and all(jobs[a['request_id']][k] == target[k]
                    for k in ('task', 'priority', 'deadline_ns')) for a in actions]
