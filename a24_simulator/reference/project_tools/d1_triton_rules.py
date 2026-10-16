"""Pinned Triton rate-limiter control flow on D1Check's whole-request ABI.

Adapted from NVIDIA Triton core rate_limiter.cc, BSD-3-Clause.
See docs/results/external_rules_02/NOTICE.md. Not a Triton server execution.
"""
from collections import deque
import copy

from tools import d1_external_rules as prior

OFF = 'TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1'
CONFIGS = {
    OFF: dict(enabled=False, capacity=2, weights={'classification': 1, 'detection': 1}),
    'TRITON_RATE_CAP1_EQUAL_REQUEST_ADAPT_V1': dict(enabled=True, capacity=1, weights={'classification': 1, 'detection': 1}),
    'TRITON_RATE_CAP2_EQUAL_REQUEST_ADAPT_V1': dict(enabled=True, capacity=2, weights={'classification': 1, 'detection': 1}),
    'TRITON_RATE_CAP1_CLASS_WEIGHT_REQUEST_ADAPT_V1': dict(enabled=True, capacity=1, weights={'classification': 1, 'detection': 2}),
    'TRITON_RATE_CAP2_CLASS_WEIGHT_REQUEST_ADAPT_V1': dict(enabled=True, capacity=2, weights={'classification': 1, 'detection': 2}),
}
MAP = {'classification': 'GPU', 'detection': 'CPU'}


class RateState:
    """Two fixed model instances; specific FIFO queues; source callback ordering.

    Scaled priority = completed executions * max(config priority, 1).
    At most two staged instances: equal scores keep the first staged entry,
    matching the two-element heap case. General upstream heap tie unspecified.
    """
    def __init__(self, config):
        self.config = copy.deepcopy(config)
        self.queue = {task: deque() for task in MAP}
        self.allocated = {task: None for task in MAP}
        self.executions = {task: 0 for task in MAP}
        self.staged = []
        self.dispatch = deque()
        self.events = []
        self.clock = 0

    def emit(self, event, **fields):
        self.events.append(dict(at_ns=self.clock, event=event, **fields))

    def priority(self, task):
        return self.executions[task] * max(self.config['weights'][task], 1)

    def allocate(self, task, q):
        if self.allocated[task] is not None:
            raise ValueError('duplicate instance allocation')
        self.allocated[task] = q['id']
        self.dispatch.append((task, q))
        self.emit('allocate', task=task, request_id=q['id'], score=self.priority(task),
                  occupied=sum(x is not None for x in self.allocated.values()))

    def attempt(self):
        # Source AttemptAllocation examines ONLY top, no skip-to-fitting scan.
        if not self.staged:
            return
        index = min(range(len(self.staged)), key=lambda i: self.priority(self.staged[i][0]))
        task, q = self.staged[index]
        if sum(x is not None for x in self.allocated.values()) >= self.config['capacity']:
            self.emit('resource_wait', task=task, request_id=q['id'], score=self.priority(task))
            return
        self.staged.pop(index)
        self.allocate(task, q)

    def stage(self, task):
        if (self.allocated[task] is not None or not self.queue[task]
                or any(t == task for t, _ in self.staged)):
            return
        q = self.queue[task].popleft()
        if self.config['enabled']:
            self.staged.append((task, q))
            self.emit('stage', task=task, request_id=q['id'], score=self.priority(task))
            self.attempt()  # OnStage -> AttemptAllocation immediately, per source.
        else:
            self.allocate(task, q)

    def submit(self, q):
        self.queue[q['task']].append(copy.deepcopy(q))
        self.emit('submit', task=q['task'], request_id=q['id'])
        self.stage(q['task'])

    def release(self, task, request_id):
        if self.allocated[task] != request_id:
            raise ValueError('release identity')
        self.executions[task] += 1  # Release(), not response completion.
        self.allocated[task] = None
        self.emit('release', task=task, request_id=request_id, executions=self.executions[task])
        self.stage(task)  # OnRelease restages own pending request BEFORE final attempt.
        if self.config['enabled']:
            self.attempt()


class Controller(prior.Timed):
    def __init__(self, frozen, initial, public_id):
        super().__init__(frozen, initial)
        self.public_id = public_id
        self.rate = RateState(CONFIGS[public_id])
        self.seen = set()
        self.previous_live = {task: None for task in MAP}

    def observe(self, now_ns, lanes):
        self.rate.clock = round(now_ns)
        # Engine's deterministic same-time release order CPU then GPU.
        for task in ('detection', 'classification'):
            row = lanes[MAP[task]]['request']
            current = row['id'] if row else None
            previous = self.previous_live[task]
            if previous is not None and previous != current:
                self.rate.release(task, previous)
            self.previous_live[task] = current
        super().observe(now_ns, lanes)

    def decide(self, config, queue, lanes, now_ns, settings, thermal_model, current_ap):
        self.validate_public(queue, lanes, now_ns)
        self.rate.clock = round(now_ns)
        for q in sorted(queue, key=lambda x: (x['arrival_ns'], x['ordinal'], x['id'])):
            if q['id'] not in self.seen:
                prior.p.backends(q)  # Strict supported tasks; no substituted cell.
                self.seen.add(q['id'])
                self.rate.submit(q)
        out = dict(now_ns=now_ns, selected=None, reason='Triton_resource_or_instance_wait',
                   candidates=[], public_id=self.public_id,
                   completed_execution_counts=dict(self.rate.executions))
        if self.rate.dispatch:
            task, q = self.rate.dispatch.popleft()
            if lanes[MAP[task]]['request'] is not None:
                raise ValueError('native lane not yet available')
            if not any(x['id'] == q['id'] for x in queue):
                raise ValueError('allocated request disappeared')
            out.update(selected=dict(request_id=q['id'], backend=MAP[task]),
                       reason='Triton_allocated_fixed_instance')
        return out


def simulate(frozen, initial, tickets, context, public_id):
    controller = Controller(frozen, initial, public_id)
    actual = prior.p.profile(frozen, context)
    vectors = dict(cells={key: [dict(source_request_id='shared_development_context_' + context,
                                   durations_ns=value) for _ in range(4)] for key, value in actual.items()})
    result = prior.old.engine.simulate(dict(protocol=prior.p.VERSION, cells=prior.p.profile(frozen)), vectors,
        tickets, policy=controller.policy, settings=prior.settings(), seed=201, decision_provider=controller)
    return result, controller
