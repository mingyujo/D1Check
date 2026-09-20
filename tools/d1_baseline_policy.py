"""Pure B0/B1 decisions for plan 4.4; no clock advance, dispatch or simulation."""


class SerialBaseline:
    def __init__(self, policy_id, fixed_mapping, aging_ns):
        if policy_id not in ('4.4/B0', '4.4/B1') or type(aging_ns) is not int or aging_ns <= 0:
            raise ValueError('explicit policy and common aging required')
        if not fixed_mapping or any(b not in ('CPU', 'GPU') for b in fixed_mapping.values()):
            raise ValueError('invalid fixed task mapping')
        self.policy_id, self.mapping, self.aging_ns = policy_id, dict(fixed_mapping), aging_ns

    def decide(self, snapshot):
        now = snapshot['now_ns']
        if type(now) is not int or now < 0:
            raise ValueError('invalid current monotonic time')
        empty = lambda reason: dict(starts=[], wait_until_ns=None, reason=reason)
        if not snapshot['common_constraints_allow_start']:
            return empty('common_constraint_gate')
        if snapshot['in_flight']:
            return empty('serial_busy')
        queue = snapshot['queue']
        ids = set()
        for q in queue:
            if q['request_id'] in ids or q['priority'] not in ('urgent', 'normal') or type(q['arrival_ns']) is not int or not 0 <= q['arrival_ns'] <= now:
                raise ValueError('invalid arrived queue')
            ids.add(q['request_id'])
            if q['task_id'] not in self.mapping:
                raise ValueError('unmapped task')
            d = q['deadline_ns']
            if d is not None and (type(d) is not int or d < q['arrival_ns']):
                raise ValueError('invalid calibrated deadline')
        if not queue:
            return empty('empty')
        def order(q):
            fifo = (q['arrival_ns'], q['request_id'])
            if self.policy_id == '4.4/B0':
                return fifo
            # Common aging promotes old normal requests ahead of urgent; FIFO among aged.
            if now - q['arrival_ns'] >= self.aging_ns:
                return (0, 0, *fifo)
            return (1 if q['priority'] == 'urgent' else 2,
                    q['deadline_ns'] if q['deadline_ns'] is not None else float('inf'), *fifo)
        selected = min(queue, key=order)
        backend = self.mapping[selected['task_id']]
        if snapshot['capability'].get(selected['task_id'], {}).get(backend) != 'passed':
            return empty('fixed_backend_not_approved')
        return dict(starts=[dict(request_id=selected['request_id'], backend=backend)], wait_until_ns=None,
                    reason=self.policy_id)
