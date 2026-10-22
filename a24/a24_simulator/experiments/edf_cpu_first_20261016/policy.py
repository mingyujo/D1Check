"""Nonpreemptive EDF; resource tie is CPU then GPU, never a cost estimate."""
from contextlib import contextmanager

POLICY = 'EDF_CPU_FIRST'
SPEC = {
    'policy': POLICY,
    'request_order': ['absolute_deadline_ns', 'scheduled_arrival_ns', 'ordinal', 'request_id'],
    'resource_order': ['CPU', 'GPU'],
    'both_tasks_allow': ['CPU', 'GPU'],
    'preemption': False, 'voluntary_WAIT': False,
    'uses_response_prediction_for_selection': False,
    'uses_energy_or_thermal_prediction_for_selection': False,
    'resource_owned_until': 'AVAILABLE',
}


def select(snapshot):
    now = snapshot['now_ns']
    owners = snapshot.get('owners', [])
    if isinstance(owners, dict):
        busy = {k for k, v in owners.items() if v is not None}
    else:
        busy = {v['route'] for v in owners}
    if not busy.issubset({'CPU', 'GPU'}):
        raise ValueError('EDF CPU/GPU scope')
    free = [r for r in SPEC['resource_order'] if r not in busy]
    queue = list(snapshot['queue'])
    for q in queue:
        if q['scheduled_arrival_ns'] > now or q.get('queue_entry_ns', 0) > now:
            raise ValueError('Future request in public ready queue')
        if q['task'] not in ('C', 'D'):
            raise ValueError('Unsupported task')
    if not free or not queue:
        return {'kind': 'RESOURCE_WAIT'}
    q = min(queue, key=lambda q: (q['deadline_ns'], q['scheduled_arrival_ns'],
                                  q['ordinal'], q['request_id']))
    return {'kind': 'DISPATCH', 'request_id': q['request_id'], 'route': free[0]}


@contextmanager
def installed(kernel, backend):
    """Extend only the in-process dispatch hook; preserve original source bytes."""
    original = kernel._rule_action
    policies = kernel.POLICIES
    old_label = backend.LABELS.get(POLICY)
    def dispatch(kind, snapshot, rows, model, pair_scope, mobile_energy, allow_busy=False):
        if kind == POLICY:
            return select(snapshot)
        return original(kind, snapshot, rows, model, pair_scope, mobile_energy, allow_busy)
    kernel._rule_action = dispatch
    kernel.POLICIES = (*policies, POLICY)
    backend.LABELS[POLICY] = '비선점 EDF · 빈 자원, 동시 유휴 CPU 우선'
    try:
        yield
    finally:
        kernel._rule_action = original
        kernel.POLICIES = policies
        if old_label is None:
            del backend.LABELS[POLICY]
        else:
            backend.LABELS[POLICY] = old_label


def window_heat(summary, lo, hi):
    import numpy as np
    t = np.asarray(summary['AP']['t_s'], dtype=float)
    y = np.asarray(summary['AP']['ap_c'], dtype=float)
    if not (len(t) == len(y) and len(t) > 1 and (np.diff(t) > 0).all()
            and t[0] <= lo < hi <= t[-1] and np.isfinite(y).all()):
        raise ValueError('AP coverage/order/finite')
    x = np.r_[lo, t[(t > lo) & (t < hi)], hi]
    v = np.interp(x, t, y)
    return {'mean_AP_c': float(np.trapezoid(v, x)/(hi-lo)),
            'peak_AP_c': float(v.max()), 'end_AP_c': float(v[-1]),
            'method': 'exact common endpoints, linear interpolation, trapezoid time mean'}


def metrics(summary, lo, hi):
    d = summary['diagnostics']
    if d['common_work_window_s'] != [lo, hi]:
        raise ValueError('Common input-defined window differs')
    rows = summary['requests']
    responded = [q for q in rows if q['response_ns'] is not None]
    available = [q for q in rows if q['available_ns'] is not None]
    tardiness = sum(max(0, q['response_ns']-q['deadline_ns'])/1e9 for q in responded)
    return {
        'policy': summary['policy'], 'window_s': [lo, hi],
        'baseline_J_proxy': d['work_window_total_J_proxy']-d['work_window_increment_J_proxy'],
        'total_J_proxy': d['work_window_total_J_proxy'],
        'increment_J_proxy': d['work_window_increment_J_proxy'],
        **window_heat(summary, lo, hi),
        'planned': len(rows),
        'on_time': sum(q['response_ns'] <= q['deadline_ns'] for q in responded),
        'responded': len(responded), 'response_missing': len(rows)-len(responded),
        'responded_by_window_end': sum(q['response_ns']/1e9 <= hi for q in responded),
        'AVAILABLE_by_window_end': sum(q['available_ns']/1e9 <= hi for q in available),
        'total_tardiness_s': tardiness if len(responded) == len(rows) else None,
        'total_tardiness_lower_bound_s': tardiness,
        'wait_s': summary['wait_s'], 'route_counts': summary['route_counts'],
        'measured_J': None, 'device_validation': False,
    }
