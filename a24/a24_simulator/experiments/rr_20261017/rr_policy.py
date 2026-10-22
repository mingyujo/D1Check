"""Request-level round robin between C/D queues; no inference preemption.

The turn advances on DISPATCH only. Busy/empty calls cannot consume a turn.
Within-class FIFO uses the same public scheduled-arrival key as the baseline.
"""
from contextlib import contextmanager

SPEC = {'RR_CPU_FIRST': {
    'queue_cycle': ['C', 'D'], 'initial_turn': 'C',
    'within_queue': ['scheduled_arrival_ns', 'ordinal', 'request_id'],
    'empty_queue': 'skip; next turn is opposite the actually dispatched class',
    'routes': ['CPU', 'GPU'], 'preemption': False,
    'quantum': 'one whole request', 'equal_time_guarantee': False,
    'voluntary_WAIT': False, 'future_information': False,
    'owner_release': 'AVAILABLE', 'maximum_owners': 2}}


class RoundRobin:
    def __init__(self):
        self.turn = 'C'
        self.trace = []

    def __call__(self, state):
        busy = [o['route'] for o in state['owners']]
        if len(busy) != len(set(busy)) or not set(busy) <= {'CPU', 'GPU'}:
            raise ValueError('Invalid resource owners')
        queue = list(state['queue'])
        if len({q['request_id'] for q in queue}) != len(queue):
            raise ValueError('Duplicate ready identity')
        if any(q['task'] not in ('C', 'D') or
               q['queue_entry_ns'] > state['now_ns'] or
               q['scheduled_arrival_ns'] > state['now_ns'] for q in queue):
            raise ValueError('Unknown task or future ready request')
        free = [r for r in ('CPU', 'GPU') if r not in busy]
        if not queue or not free:
            return {'kind': 'RESOURCE_WAIT'}
        before = self.turn
        preferred = [q for q in queue if q['task'] == before]
        head = min(preferred or queue,
                   key=lambda q: (q['scheduled_arrival_ns'], q['ordinal'], q['request_id']))
        action = {'kind': 'DISPATCH', 'request_id': head['request_id'], 'route': free[0]}
        self.turn = 'D' if head['task'] == 'C' else 'C'
        self.trace.append({'time_ns': state['now_ns'], 'turn_before': before,
                           'turn_after': self.turn, 'selected_task': head['task'],
                           'empty_class_skipped': not bool(preferred), 'action': dict(action)})
        return action


@contextmanager
def installed(kernel, trace=None):
    original, policies = kernel._rule_action, kernel.POLICIES
    actor = RoundRobin()
    def hook(policy, snapshot, rows, model, pair_scope, mobile_energy, allow_busy=False):
        if policy == 'RR_CPU_FIRST':
            action = actor(snapshot)
            if trace is not None and action['kind'] == 'DISPATCH':
                trace.append(dict(actor.trace[-1]))
            return action
        return original(policy, snapshot, rows, model, pair_scope, mobile_energy, allow_busy)
    kernel._rule_action, kernel.POLICIES = hook, (*policies, 'RR_CPU_FIRST')
    try:
        yield actor
    finally:
        kernel._rule_action, kernel.POLICIES = original, policies
