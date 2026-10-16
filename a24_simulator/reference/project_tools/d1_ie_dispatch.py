"""Three source-defined sequencing/routing rules in the unchanged PC plant.

ECT minimizes predicted whole lane completion (all five phases). FIFO/SPT/EDD
choose the head request independently. This is a bounded adaptation, not an
industrial product, StarPU/HEFT reproduction, or a new thermal controller.
"""
from __future__ import annotations
from tools import d1_external_rules as external

p, old = external.p, external.old
POLICIES = ('IE_FIFO_ECT_LANE_PC_V1', 'IE_SPT_ECT_LANE_PC_V1', 'IE_EDD_ECT_LANE_PC_V1')


def order_key(q, estimates, rule):
    tie = (q['arrival_ns'], q['ordinal'], q['id'])
    if rule == 'FIFO': return tie
    if rule == 'SPT': return (min(sum(estimates[p.key(q, b)]) for b in p.backends(q)), *tie)
    if rule == 'EDD': return (q['arrival_ns'] + q['deadline_offset_ns'], *tie)
    raise ValueError('unknown sequencing rule')


class Controller(external.Timed):
    def __init__(self, frozen, initial, policy):
        if policy not in POLICIES: raise ValueError('unknown IE policy')
        super().__init__(frozen, initial)
        self.public_policy = policy
        self.rule = policy.split('_')[1]

    def decide(self, config, queue, lanes, now_ns, settings, thermal_model, current_ap):
        self.validate_public(queue, lanes, now_ns)
        now = now_ns / 1e9
        out = dict(now_ns=now_ns, selected=None, reason='empty', public_policy=self.public_policy,
                   modeled_ap_c=self.t, candidates=[])
        if not queue: return out
        ordered = sorted(queue, key=lambda q: order_key(q, self.estimates, self.rule))
        q = ordered[0]
        out.update(head_request_id=q['id'], sequencing_rule=self.rule,
                   ordered_ids=[r['id'] for r in ordered])
        active = self.active_jobs(lanes, now)
        if active is None: return dict(out, reason='unknown_overrun_wait_for_public_event')
        choices = [self.place(q, b, now, active) for b in p.backends(q)]
        chosen = min(choices, key=lambda j: (j['end'], j['backend'] != 'CPU'))
        out.update(candidates=choices, chosen_backend=chosen['backend'], planned_start_s=chosen['start'],
                   predicted_lane_end_s=chosen['end'], predicted_response_s=chosen['response'])
        b = chosen['backend']
        if chosen['start'] > now + 1e-9:
            return dict(out, reason='ECT_wait_for_best_resource',
                        wait_until_ns=max(now_ns + 1., chosen['start'] * 1e9))
        # A forecast never releases an actually occupied lane or expands support.
        if lanes[b]['request'] is not None:
            return dict(out, reason='actual_lane_still_owned_wait_for_public_event')
        members = [r['request']['task']+'_'+lane for lane, r in lanes.items() if r['request']]
        p.state(members + [q['task']+'_'+b])
        return dict(out, selected=dict(request_id=q['id'], backend=b), reason=self.public_policy)


def simulate(frozen, initial, tickets, context, policy):
    c = Controller(frozen, initial, policy)
    actual = p.profile(frozen, context)
    vectors = dict(cells={k: [dict(source_request_id='shared_development_context_'+context,
                                 durations_ns=v) for _ in range(4)] for k, v in actual.items()})
    result = old.engine.simulate(dict(protocol=p.VERSION, cells=p.profile(frozen)), vectors,
        tickets, policy=c.policy, settings=external.settings(), seed=201, decision_provider=c)
    return result, c
